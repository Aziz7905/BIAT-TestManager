from __future__ import annotations

import shutil
from unittest import mock

import redis as redis_lib
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.models import Organization, Team, TeamMembership, UserProfile
from apps.accounts.models.choices import OrganizationRole, TeamMembershipRole
from apps.automation.models import (
    AutomationScript,
    ExecutionSchedule,
    ExecutionStatus,
    TestArtifact,
    TestExecution,
)
from apps.automation.models.choices import (
    ArtifactType,
    AutomationFramework,
    AutomationLanguage,
    ExecutionTriggerType,
)
from apps.automation.services.execution_runner import (
    create_execution_record,
    select_execution_script,
)
from apps.automation.services.manual_browser import create_and_queue_manual_browser_execution
from apps.automation.services.python_script_runner import (
    build_execution_environment,
    prepare_runner_workspace,
)
from apps.automation.services.control import is_execution_stop_signaled
from apps.automation.services.results import finalize_execution_result
from apps.automation.services.scheduling import compute_next_run_for_schedule
from apps.automation.services.script_validation import validate_script_content
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as QaTestCase
from apps.testing.models import TestScenario, TestSection, TestSuite


class AutomationServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="service.owner",
            password="Pass1234!",  # NOSONAR
            email="service.owner@biat-it.tn",
        )
        self.organization = Organization.objects.create(
            name="BIAT IT",
            domain="biat-services.tn",
        )
        UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="Execution Team",
            manager=self.user,
        )
        TeamMembership.objects.create(
            team=self.team,
            user=self.user,
            role=TeamMembershipRole.TESTER,
            is_active=True,
        )
        self.project = Project.objects.create(
            team=self.team,
            name="Execution Project",
            created_by=self.user,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMemberRole.OWNER,
        )
        self.suite = TestSuite.objects.create(
            project=self.project,
            name="Smoke Suite",
            folder_path="Smoke",
            created_by=self.user,
        )
        self.section = TestSection.objects.create(
            suite=self.suite,
            name="General",
            order_index=0,
        )
        self.scenario = TestScenario.objects.create(
            section=self.section,
            title="Open app",
            description="Check that the app can be opened.",
        )
        self.test_case = QaTestCase.objects.create(
            scenario=self.scenario,
            title="Open login page",
            steps=[{"step": "Open app", "outcome": "Login page is visible"}],
            expected_result="Login page is visible.",
        )

    def test_validate_script_content_detects_invalid_python(self):
        validation = validate_script_content(
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="def broken(:\n    pass",
        )

        self.assertFalse(validation["is_valid"])
        self.assertTrue(validation["errors"])

    def test_validate_script_content_accepts_selenium_python(self):
        validation = validate_script_content(
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.PYTHON,
            script_content="print('selenium smoke')",
        )

        self.assertTrue(validation["is_valid"])
        self.assertEqual(validation["errors"], [])

    def test_select_execution_script_prefers_latest_active_version(self):
        AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="print('v1 playwright')",
            is_active=False,
        )
        latest_script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="print('v2 playwright')",
            is_active=True,
        )

        selected_script = select_execution_script(self.test_case)

        self.assertEqual(selected_script.id, latest_script.id)

    def test_finalize_execution_result_creates_result_and_updates_status(self):
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
        )

        result = finalize_execution_result(
            execution,
            status=ExecutionStatus.PASSED,
            duration_ms=550,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        self.assertIsNotNone(execution.ended_at)
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.total_steps, 1)

    def test_execution_pause_resume_and_stop_methods_are_state_safe(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.user,
            status=ExecutionStatus.RUNNING,
            browser="chromium",
            platform="desktop",
        )

        execution.pause()
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PAUSED)
        self.assertTrue(execution.pause_requested)

        execution.resume()
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.QUEUED)
        self.assertFalse(execution.pause_requested)

        execution.stop()
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)
        self.assertIsNotNone(execution.ended_at)

    def test_schedule_save_computes_next_run(self):
        schedule = ExecutionSchedule.objects.create(
            project=self.project,
            suite=self.suite,
            name="Nightly",
            cron_expression="0 2 * * *",
            timezone="UTC",
            browser="chromium",
            platform="desktop",
            created_by=self.user,
        )

        self.assertIsNotNone(schedule.next_run_at)

    def test_compute_next_run_for_schedule_handles_invalid_values(self):
        with self.assertLogs("apps.automation.services.scheduling", level="WARNING"):
            invalid_timezone_result = compute_next_run_for_schedule(
                cron_expression="0 2 * * *",
                timezone_name="Invalid/Zone",
            )
            invalid_cron_result = compute_next_run_for_schedule(
                cron_expression="invalid cron",
                timezone_name="UTC",
            )

        self.assertIsNone(invalid_timezone_result)
        self.assertIsNone(invalid_cron_result)

    def test_create_execution_record_stores_selected_script(self):
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.PYTHON,
            script_content="print('playwright smoke')",
        )

        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            script=script,
        )

        self.assertEqual(execution.script_id, script.id)

    def test_manual_browser_execution_enables_pixel_stream(self):
        with mock.patch(
            "apps.automation.tasks.enqueue_manual_browser_session_task",
            return_value="task-1",
        ):
            execution = create_and_queue_manual_browser_execution(
                test_case=self.test_case,
                triggered_by=self.user,
                target_url="https://example.test",
            )

        self.assertTrue(execution.stream_enabled)
        self.assertEqual(execution.celery_task_id, "task-1")

    def test_artifact_records_use_storage_key(self):
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
        )

        artifact = TestArtifact.objects.create(
            execution=execution,
            artifact_type=ArtifactType.LOG,
            storage_backend="minio",
            storage_key="projects/p1/executions/e1/log/stdout.log",
        )

        self.assertEqual(artifact.storage_backend, "minio")
        self.assertEqual(artifact.storage_key, "projects/p1/executions/e1/log/stdout.log")

    @override_settings(AUTOMATION_PYTHON_RUNNER_IMAGE="biat-python-test:latest")
    def test_python_runner_workspace_is_container_only(self):
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.PYTHON,
            script_content="print('selenium smoke')",
        )
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            script=script,
        )

        workspace = prepare_runner_workspace(execution)
        try:
            self.assertEqual(workspace.image, "biat-python-test:latest")
            self.assertEqual(workspace.command, ["python3", "/workspace/script.py"])
            self.assertTrue((workspace.host_root / "script.py").exists())
            self.assertTrue((workspace.host_root / "apps" / "automation" / "runtime.py").exists())
        finally:
            shutil.rmtree(workspace.host_root, ignore_errors=True)

    @override_settings(AUTOMATION_JAVA_RUNNER_IMAGE="biat-java-test:latest")
    def test_java_runner_workspace_uses_public_class_name(self):
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.JAVA,
            script_content="""
public class BankSmoke {
    public static void main(String[] args) {}
}
""".strip(),
        )
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            script=script,
        )

        workspace = prepare_runner_workspace(execution)
        try:
            self.assertEqual(workspace.image, "biat-java-test:latest")
            self.assertIn("-Dexec.mainClass=BankSmoke", workspace.command)
            self.assertTrue((workspace.host_root / "BankSmoke.java").exists())
            self.assertTrue((workspace.host_root / "BiatRuntime.java").exists())
            self.assertTrue((workspace.host_root / "pom.xml").exists())
        finally:
            shutil.rmtree(workspace.host_root, ignore_errors=True)

    @override_settings(
        SELENOID_RUNNER_HUB_URL="http://selenoid:4444/wd/hub",
        MINIO_RUNNER_ENDPOINT_URL="http://minio:9000",
        MINIO_ACCESS_KEY="runner-access",
        MINIO_SECRET_KEY="runner-secret",
        MINIO_BUCKET_NAME="runner-artifacts",
    )
    def test_runner_environment_targets_selenoid_and_minio(self):
        script = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.PYTHON,
            script_content="print('env smoke')",
        )
        execution = create_execution_record(
            test_case=self.test_case,
            triggered_by=self.user,
            trigger_type=ExecutionTriggerType.MANUAL,
            browser="chromium",
            platform="desktop",
            script=script,
        )

        env = build_execution_environment(execution)

        self.assertEqual(env["BIAT_WEBDRIVER_URL"], "http://selenoid:4444/wd/hub")
        self.assertEqual(env["MINIO_ENDPOINT_URL"], "http://minio:9000")
        self.assertEqual(env["MINIO_ACCESS_KEY"], "runner-access")
        self.assertEqual(env["MINIO_SECRET_KEY"], "runner-secret")
        self.assertEqual(env["MINIO_BUCKET_NAME"], "runner-artifacts")
        self.assertEqual(env["BIAT_ENABLE_VNC"], "1")
        self.assertEqual(env["BIAT_STREAM_HOLD_SECONDS"], "20")
        self.assertEqual(env["PYTHONPATH"], "/workspace")
        self.assertNotIn("PATH", env)
        self.assertNotIn("Path", env)
        self.assertNotIn("BIAT_ARTIFACT_STORAGE_BACKEND", env)

    def test_stop_signal_check_survives_redis_failure(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.user,
            status=ExecutionStatus.RUNNING,
            browser="chromium",
            platform="desktop",
        )

        with mock.patch(
            "apps.automation.services.control.redis_lib.from_url",
            side_effect=redis_lib.RedisError("down"),
        ):
            self.assertFalse(is_execution_stop_signaled(execution))
