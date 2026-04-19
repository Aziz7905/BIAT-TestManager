"""
Batch 6 — Execution Hardening Tests
Covers:
- ExecutionEnvironment model creation and constraints
- AutomationScript revision-awareness (test_case_revision FK)
- ExecutionEngine contract: EngineResult shape, registry selection
- SeleniumExecutionEngine uses the same EngineResult contract as Playwright
- Scheduler produces TestRun + TestRunCase (not direct executions)
- _persist_engine_artifacts bulk-creates TestArtifact records
- TestRunCase lease fields (attempt_count, leased_at, leased_by)
- attempt_number increments per run_case
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Organization, Team, TeamMembership, UserProfile
from apps.accounts.models.choices import OrganizationRole, TeamMembershipRole
from apps.automation.models import (
    ArtifactType,
    AutomationFramework,
    AutomationLanguage,
    AutomationScript,
    ExecutionEnvironment,
    ExecutionStatus,
    TestArtifact,
    TestExecution,
)
from apps.automation.models.choices import ExecutionTriggerType
from apps.automation.services.engine import (
    EngineResult,
    PlaywrightExecutionEngine,
    SeleniumExecutionEngine,
    get_engine_for_execution,
)
from apps.automation.services.execution_runner import (
    _next_attempt_number,
    _persist_engine_artifacts,
    create_execution_record,
)
from apps.automation.services.playwright_runner import UnsupportedExecutionConfigurationError
from apps.automation.services.scheduling import trigger_execution_schedule
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as QaTestCase
from apps.testing.models import (
    TestRun,
    TestRunCase,
    TestScenario,
    TestSection,
    TestSuite,
)
from apps.testing.models.choices import TestCaseDesignStatus
from apps.testing.services.repository import create_test_case_with_revision


class ExecutionEnvironmentModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="env.owner",
            password="Pass1234!",
            email="env.owner@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Env Org", domain="env-org.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Env Team", manager=self.user
        )

    def test_create_execution_environment_defaults(self):
        env = ExecutionEnvironment.objects.create(
            team=self.team,
            name="CI Playwright",
        )
        self.assertEqual(env.engine, AutomationFramework.PLAYWRIGHT)
        self.assertEqual(env.browser, "chromium")
        self.assertEqual(env.platform, "desktop")
        self.assertEqual(env.max_parallelism, 1)
        self.assertTrue(env.is_active)
        self.assertEqual(env.capabilities_json, {})

    def test_execution_environment_unique_name_per_team(self):
        ExecutionEnvironment.objects.create(team=self.team, name="Staging")
        with self.assertRaises(IntegrityError):
            ExecutionEnvironment.objects.create(team=self.team, name="Staging")

    def test_execution_environment_same_name_different_teams(self):
        team2 = Team.objects.create(
            organization=self.org, name="Another Team", manager=self.user
        )
        env1 = ExecutionEnvironment.objects.create(team=self.team, name="Shared Name")
        env2 = ExecutionEnvironment.objects.create(team=team2, name="Shared Name")
        self.assertNotEqual(env1.id, env2.id)

    def test_str_representation(self):
        env = ExecutionEnvironment.objects.create(
            team=self.team, name="Mobile Safari", engine="playwright", browser="webkit", platform="mobile"
        )
        label = str(env)
        self.assertIn("webkit", label)
        self.assertIn("Mobile Safari", label)


class AutomationScriptRevisionAwarenessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="rev.script",
            password="Pass1234!",
            email="rev.script@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Script Org", domain="script.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Script Team", manager=self.user
        )
        self.project = Project.objects.create(
            team=self.team, name="Script Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Script Suite", folder_path="Scripts", created_by=self.user
        )
        self.section = TestSection.objects.create(
            suite=self.suite, name="Auth", order_index=0
        )
        self.scenario = TestScenario.objects.create(
            section=self.section, title="Login flow", description=""
        )
        self.test_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Login with valid credentials",
            steps=[{"step": "Enter credentials", "outcome": "Logged in"}],
            expected_result="User is logged in.",
            created_by=self.user,
        )

    def test_script_can_reference_test_case_revision(self):
        revision = self.test_case.revisions.first()
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="print('login')",
            test_case_revision=revision,
        )
        script.refresh_from_db()
        self.assertEqual(script.test_case_revision_id, revision.id)

    def test_script_test_case_revision_is_nullable(self):
        # Scripts not yet pinned to a revision are still valid
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="print('unversioned')",
            test_case_revision=None,
        )
        self.assertIsNone(script.test_case_revision_id)


class EngineContractTests(TestCase):
    """Verify engine registry + EngineResult shape without hitting subprocess."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="engine.tester",
            password="Pass1234!",
            email="engine.tester@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Engine Org", domain="engine.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Engine Team", manager=self.user
        )
        self.project = Project.objects.create(
            team=self.team, name="Engine Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Engine Suite", folder_path="E", created_by=self.user
        )
        self.section = TestSection.objects.create(
            suite=self.suite, name="Root", order_index=0
        )
        self.scenario = TestScenario.objects.create(
            section=self.section, title="Engine scenario", description=""
        )
        self.test_case = QaTestCase.objects.create(
            scenario=self.scenario,
            title="Engine test case",
            steps=[{"step": "Open", "outcome": "Opened"}],
            expected_result="Opened.",
        )
        self.script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="print('engine')",
        )

    def _make_execution(self, script=None):
        return create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            script=script or self.script,
        )

    def test_engine_result_is_dataclass_with_required_fields(self):
        result = EngineResult(status="passed")
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.error_message, "")
        self.assertEqual(result.stack_trace, "")
        self.assertEqual(result.artifacts, [])

    def test_get_engine_for_execution_returns_playwright_engine_by_script(self):
        execution = self._make_execution()
        engine = get_engine_for_execution(execution)
        self.assertIsInstance(engine, PlaywrightExecutionEngine)

    def test_get_engine_for_execution_falls_back_to_environment_engine(self):
        # Create a test case with NO scripts so select_execution_script returns None
        scriptless_scenario = TestScenario.objects.create(
            section=self.section, title="Scriptless scenario", description=""
        )
        scriptless_case = QaTestCase.objects.create(
            scenario=scriptless_scenario,
            title="Scriptless test case",
            steps=[],
            expected_result="",
        )
        env = ExecutionEnvironment.objects.create(
            team=self.team, name="Selenium CI", engine=AutomationFramework.SELENIUM
        )
        execution = create_execution_record(
            test_case=scriptless_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            script=None,
            environment=env,
        )
        # No script on the case → falls back to environment.engine (Selenium)
        engine = get_engine_for_execution(execution)
        self.assertIsInstance(engine, SeleniumExecutionEngine)

    def test_selenium_engine_run_returns_engine_result(self):
        engine = SeleniumExecutionEngine()
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.PYTHON,
            script_content="print('selenium')",
        )
        execution = self._make_execution(script=script)

        with patch(
            "apps.automation.services.selenium_runner.run_selenium_execution",
            return_value={
                "status": "passed",
                "stdout": "ok",
                "stderr": "",
                "error_message": "",
                "stack_trace": "",
                "artifacts": [],
            },
        ):
            result = engine.run(execution)

        self.assertIsInstance(result, EngineResult)
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.error_message, "")

    def test_playwright_engine_run_returns_engine_result(self):
        """Playwright runner is mocked so no subprocess is spawned."""
        execution = self._make_execution()
        playwright_engine = PlaywrightExecutionEngine()

        with patch(
            "apps.automation.services.playwright_runner.run_playwright_execution",
            return_value={
                "status": "passed",
                "stdout": "ok",
                "stderr": "",
                "error_message": "",
                "stack_trace": "",
                "artifacts": [],
            },
        ):
            result = playwright_engine.run(execution)

        self.assertIsInstance(result, EngineResult)
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.error_message, "")

    def test_get_engine_raises_for_no_script_no_environment(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.user,
            status=ExecutionStatus.QUEUED,
            browser="chromium",
            platform="desktop",
        )
        with self.assertRaises(UnsupportedExecutionConfigurationError):
            get_engine_for_execution(execution)


class ArtifactPersistenceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="artifact.user",
            password="Pass1234!",
            email="artifact.user@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Artifact Org", domain="artifacts.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Artifact Team", manager=self.user
        )
        self.project = Project.objects.create(
            team=self.team, name="Artifact Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Artifact Suite", folder_path="Art", created_by=self.user
        )
        self.section = TestSection.objects.create(
            suite=self.suite, name="Root", order_index=0
        )
        self.scenario = TestScenario.objects.create(
            section=self.section, title="Artifact scenario", description=""
        )
        self.test_case = QaTestCase.objects.create(
            scenario=self.scenario,
            title="Artifact test case",
            steps=[{"step": "Capture", "outcome": "Screenshot taken"}],
            expected_result="Screenshot exists.",
        )

    def test_persist_engine_artifacts_creates_test_artifact_records(self):
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
        )
        engine_result = EngineResult(
            status="passed",
            artifacts=[
                {"type": ArtifactType.SCREENSHOT, "path": "/tmp/shot.png", "metadata": {"width": 1280}},
                {"type": ArtifactType.LOG, "path": "/tmp/run.log"},
            ],
        )

        _persist_engine_artifacts(execution, engine_result)

        artifacts = list(TestArtifact.objects.filter(execution=execution).order_by("created_at"))
        self.assertEqual(len(artifacts), 2)
        self.assertEqual(artifacts[0].artifact_type, ArtifactType.SCREENSHOT)
        self.assertEqual(artifacts[0].storage_path, "/tmp/shot.png")
        self.assertEqual(artifacts[0].metadata_json, {"width": 1280})
        self.assertEqual(artifacts[1].artifact_type, ArtifactType.LOG)

    def test_persist_engine_artifacts_skips_entries_without_path(self):
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
        )
        engine_result = EngineResult(
            status="failed",
            artifacts=[
                {"type": ArtifactType.SCREENSHOT, "path": ""},  # empty path → skip
                {"type": ArtifactType.TRACE, "path": "/tmp/trace.zip"},
            ],
        )

        _persist_engine_artifacts(execution, engine_result)

        artifacts = TestArtifact.objects.filter(execution=execution)
        self.assertEqual(artifacts.count(), 1)
        self.assertEqual(artifacts.first().artifact_type, ArtifactType.TRACE)


class AttemptNumberTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="attempt.user",
            password="Pass1234!",
            email="attempt.user@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Attempt Org", domain="attempt.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Attempt Team", manager=self.user
        )
        self.project = Project.objects.create(
            team=self.team, name="Attempt Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Attempt Suite", folder_path="Att", created_by=self.user
        )
        self.section = TestSection.objects.create(
            suite=self.suite, name="Root", order_index=0
        )
        self.scenario = TestScenario.objects.create(
            section=self.section, title="Attempt scenario", description=""
        )
        self.test_case = QaTestCase.objects.create(
            scenario=self.scenario,
            title="Attempt test case",
            steps=[{"step": "Open", "outcome": "Opened"}],
            expected_result="Opened.",
        )

    def test_next_attempt_number_starts_at_one_for_no_run_case(self):
        self.assertEqual(_next_attempt_number(None), 1)

    def test_attempt_number_increments_on_subsequent_executions(self):
        exec1 = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
        )
        # Same run_case → second attempt
        exec2 = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            run_case=exec1.run_case,
        )
        self.assertEqual(exec1.attempt_number, 1)
        self.assertEqual(exec2.attempt_number, 2)


class TestRunCaseLeaseFieldTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="lease.user",
            password="Pass1234!",
            email="lease.user@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Lease Org", domain="lease.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Lease Team", manager=self.user
        )
        TeamMembership.objects.create(
            team=self.team, user=self.user, role=TeamMembershipRole.TESTER, is_active=True
        )
        self.project = Project.objects.create(
            team=self.team, name="Lease Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Lease Suite", folder_path="Lease", created_by=self.user
        )
        self.section = TestSection.objects.create(
            suite=self.suite, name="Root", order_index=0
        )
        self.scenario = TestScenario.objects.create(
            section=self.section, title="Lease scenario", description=""
        )
        self.test_case = QaTestCase.objects.create(
            scenario=self.scenario,
            title="Lease test case",
            steps=[{"step": "Open", "outcome": "Opened"}],
            expected_result="Opened.",
            design_status=TestCaseDesignStatus.APPROVED,
        )

    def test_run_case_lease_fields_have_correct_defaults(self):
        from apps.testing.services.runs import create_test_run, expand_run_from_suite

        run = create_test_run(
            self.project,
            name="Lease Run",
            created_by=self.user,
        )
        expand_run_from_suite(run, self.suite)

        run_case = TestRunCase.objects.filter(run=run).first()
        self.assertIsNotNone(run_case)
        self.assertEqual(run_case.attempt_count, 0)
        self.assertIsNone(run_case.leased_at)
        self.assertEqual(run_case.leased_by, "")

    def test_run_case_lease_fields_can_be_updated(self):
        from apps.testing.services.runs import create_test_run, expand_run_from_suite

        run = create_test_run(self.project, name="Lease Write Run", created_by=self.user)
        expand_run_from_suite(run, self.suite)

        run_case = TestRunCase.objects.filter(run=run).first()
        now = timezone.now()
        run_case.attempt_count = 1
        run_case.leased_at = now
        run_case.leased_by = "celery-worker-01"
        run_case.save(update_fields=["attempt_count", "leased_at", "leased_by"])

        run_case.refresh_from_db()
        self.assertEqual(run_case.attempt_count, 1)
        self.assertEqual(run_case.leased_by, "celery-worker-01")
        self.assertIsNotNone(run_case.leased_at)


class SchedulerRunLayerTests(TestCase):
    """
    trigger_execution_schedule must create a TestRun and TestRunCase records
    rather than dispatching executions directly. Celery queuing is patched out.
    """

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="sched.owner",
            password="Pass1234!",
            email="sched.owner@biat-it.tn",
        )
        self.org = Organization.objects.create(name="Sched Org", domain="sched.tn")
        UserProfile.objects.create(
            user=self.user, organization=self.org, organization_role=OrganizationRole.MEMBER
        )
        self.team = Team.objects.create(
            organization=self.org, name="Sched Team", manager=self.user
        )
        TeamMembership.objects.create(
            team=self.team, user=self.user, role=TeamMembershipRole.TESTER, is_active=True
        )
        self.project = Project.objects.create(
            team=self.team, name="Sched Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Nightly Suite", folder_path="Nightly", created_by=self.user
        )
        self.section = TestSection.objects.create(
            suite=self.suite, name="Smoke", order_index=0
        )
        self.scenario = TestScenario.objects.create(
            section=self.section, title="Homepage load", description=""
        )
        self.test_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Load homepage",
            steps=[{"step": "Open /", "outcome": "200 OK"}],
            expected_result="Page loads.",
            created_by=self.user,
            design_status=TestCaseDesignStatus.APPROVED,
        )
        from apps.automation.models import ExecutionSchedule
        self.schedule = ExecutionSchedule.objects.create(
            project=self.project,
            suite=self.suite,
            name="Nightly Smoke",
            cron_expression="0 2 * * *",
            timezone="UTC",
            browser="chromium",
            platform="desktop",
            created_by=self.user,
        )

    def test_trigger_execution_schedule_creates_test_run(self):
        run = trigger_execution_schedule(self.schedule)

        self.assertIsInstance(run, TestRun)
        self.assertEqual(run.project_id, self.project.id)
        self.assertIn("Scheduled", run.name)

    def test_trigger_execution_schedule_creates_run_cases(self):
        run = trigger_execution_schedule(self.schedule)

        run_cases = TestRunCase.objects.filter(run=run)
        self.assertGreater(run_cases.count(), 0)

    def test_trigger_execution_schedule_pinned_to_revision(self):
        run = trigger_execution_schedule(self.schedule)

        run_case = TestRunCase.objects.filter(run=run).first()
        # Each run-case should be revision-pinned at expand time
        self.assertIsNotNone(run_case.test_case_revision_id)

    def test_trigger_execution_schedule_no_direct_executions_created(self):
        """
        The redesigned scheduler must NOT create TestExecution records directly —
        that happens later when workers pick up run-cases.
        """
        before_count = TestExecution.objects.count()
        trigger_execution_schedule(self.schedule)
        after_count = TestExecution.objects.count()

        self.assertEqual(before_count, after_count)
