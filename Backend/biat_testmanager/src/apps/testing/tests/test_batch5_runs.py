from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import (
    TestPlan,
    TestPlanStatus,
    TestRun,
    TestRunCase,
    TestRunCaseStatus,
    TestRunStatus,
    TestSuite,
)
from apps.testing.services.repository import (
    create_test_case_with_revision,
    get_or_create_default_section,
)
from apps.testing.services.runs import (
    close_test_run,
    create_test_plan,
    create_test_run,
    expand_run_from_cases,
    expand_run_from_suite,
    get_or_create_adhoc_run_case,
    sync_run_case_status_from_execution,
)


class Batch5RunsServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="runner",
            password="Pass1234!",
            email="runner@biat.tn",
            first_name="Run",
            last_name="Ner",
        )
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            organization_role=OrganizationRole.ORG_ADMIN,
        )
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(
            team=self.team, name="Banking App", created_by=self.user
        )
        self.suite = TestSuite.objects.create(
            project=self.project, name="Login Suite", created_by=self.user
        )
        self.section = get_or_create_default_section(self.suite)
        from apps.testing.models import TestScenario
        self.scenario = TestScenario.objects.create(
            section=self.section,
            title="Login scenarios",
            description="",
        )
        from apps.testing.models import TestCaseDesignStatus
        self.case_a = create_test_case_with_revision(
            scenario=self.scenario,
            title="Valid login",
            expected_result="User is logged in",
            created_by=self.user,
            design_status=TestCaseDesignStatus.APPROVED,
        )
        self.case_b = create_test_case_with_revision(
            scenario=self.scenario,
            title="Invalid credentials",
            expected_result="Error message shown",
            created_by=self.user,
            design_status=TestCaseDesignStatus.APPROVED,
        )

    # ------------------------------------------------------------------
    # Plan creation
    # ------------------------------------------------------------------

    def test_create_plan_sets_project_and_draft_status(self):
        plan = create_test_plan(self.project, name="Sprint 1", created_by=self.user)

        self.assertEqual(plan.project_id, self.project.id)
        self.assertEqual(plan.status, TestPlanStatus.DRAFT)
        self.assertEqual(plan.created_by_id, self.user.id)

    # ------------------------------------------------------------------
    # Run creation
    # ------------------------------------------------------------------

    def test_create_run_without_plan(self):
        run = create_test_run(self.project, name="Ad-hoc run", created_by=self.user)

        self.assertIsNone(run.plan_id)
        self.assertEqual(run.status, TestRunStatus.PENDING)
        self.assertEqual(run.project_id, self.project.id)

    def test_create_run_linked_to_plan(self):
        plan = create_test_plan(self.project, name="Sprint 1", created_by=self.user)
        run = create_test_run(
            self.project, name="Sprint 1 Run 1", created_by=self.user, plan=plan
        )

        self.assertEqual(run.plan_id, plan.id)

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def test_expand_run_from_cases_creates_run_cases_with_revision(self):
        run = create_test_run(self.project, name="Explicit run", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a, self.case_b])

        self.assertEqual(len(run_cases), 2)
        for run_case in run_cases:
            self.assertIsNotNone(run_case.pk)
            self.assertIsNotNone(run_case.test_case_revision_id)
            self.assertEqual(run_case.status, TestRunCaseStatus.PENDING)

    def test_expand_run_from_suite_covers_all_cases(self):
        run = create_test_run(self.project, name="Suite run", created_by=self.user)
        run_cases = expand_run_from_suite(run, self.suite)

        self.assertEqual(len(run_cases), 2)
        case_ids = {rc.test_case_id for rc in run_cases}
        self.assertIn(self.case_a.id, case_ids)
        self.assertIn(self.case_b.id, case_ids)

    def test_run_case_revision_matches_latest_case_revision(self):
        run = create_test_run(self.project, name="Rev check", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a])

        expected_revision = self.case_a.revisions.order_by("-version_number").first()
        self.assertEqual(run_cases[0].test_case_revision_id, expected_revision.id)

    def test_run_case_revision_is_pinned_after_case_update(self):
        """Updating the case after expansion must not change the run-case revision pointer."""
        from apps.testing.services.repository import update_test_case_with_revision

        run = create_test_run(self.project, name="Pin check", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a])
        pinned_revision_id = run_cases[0].test_case_revision_id

        update_test_case_with_revision(
            self.case_a,
            title="Valid login — updated",
            expected_result="User is redirected to dashboard",
            created_by=self.user,
        )

        run_cases[0].refresh_from_db()
        self.assertEqual(run_cases[0].test_case_revision_id, pinned_revision_id)

    # ------------------------------------------------------------------
    # Compatibility shim
    # ------------------------------------------------------------------

    def test_adhoc_shim_creates_run_and_run_case(self):
        run_case = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)

        self.assertIsNotNone(run_case.pk)
        self.assertIsNotNone(run_case.run_id)
        self.assertEqual(run_case.test_case_id, self.case_a.id)
        self.assertIsNotNone(run_case.test_case_revision_id)

    def test_adhoc_shim_reuses_pending_run_case(self):
        rc1 = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)
        rc2 = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)

        self.assertEqual(rc1.id, rc2.id)

    def test_adhoc_shim_creates_new_run_case_when_previous_is_done(self):
        rc1 = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)
        rc1.status = TestRunCaseStatus.PASSED
        rc1.save(update_fields=["status", "updated_at"])

        rc2 = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)
        self.assertNotEqual(rc1.id, rc2.id)

    # ------------------------------------------------------------------
    # Status sync
    # ------------------------------------------------------------------

    def test_sync_run_case_status_from_execution_maps_passed(self):
        run = create_test_run(self.project, name="Status sync", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a])
        run_case = run_cases[0]

        sync_run_case_status_from_execution(run_case, "passed")

        run_case.refresh_from_db()
        self.assertEqual(run_case.status, TestRunCaseStatus.PASSED)

    def test_sync_run_case_status_does_not_overwrite_terminal_state(self):
        run = create_test_run(self.project, name="Terminal guard", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a])
        run_case = run_cases[0]
        run_case.status = TestRunCaseStatus.PASSED
        run_case.save(update_fields=["status", "updated_at"])

        sync_run_case_status_from_execution(run_case, "failed")

        run_case.refresh_from_db()
        self.assertEqual(run_case.status, TestRunCaseStatus.PASSED)

    # ------------------------------------------------------------------
    # Run close / pass rate
    # ------------------------------------------------------------------

    def test_close_run_derives_failed_status_when_any_case_failed(self):
        run = create_test_run(self.project, name="Close test", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a, self.case_b])
        run_cases[0].status = TestRunCaseStatus.PASSED
        run_cases[0].save(update_fields=["status", "updated_at"])
        run_cases[1].status = TestRunCaseStatus.FAILED
        run_cases[1].save(update_fields=["status", "updated_at"])

        close_test_run(run)

        run.refresh_from_db()
        self.assertEqual(run.status, TestRunStatus.FAILED)
        self.assertIsNotNone(run.ended_at)

    def test_close_run_derives_passed_status_when_all_cases_passed(self):
        run = create_test_run(self.project, name="All pass", created_by=self.user)
        run_cases = expand_run_from_cases(run, [self.case_a, self.case_b])
        for rc in run_cases:
            rc.status = TestRunCaseStatus.PASSED
            rc.save(update_fields=["status", "updated_at"])

        close_test_run(run)

        run.refresh_from_db()
        self.assertEqual(run.status, TestRunStatus.PASSED)


class Batch5RunsAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="api.runner",
            password="Pass1234!",
            email="api.runner@biat.tn",
            first_name="Api",
            last_name="Runner",
        )
        self.org = Organization.objects.create(name="BIAT API", domain="biat-api.tn")
        UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            organization_role=OrganizationRole.ORG_ADMIN,
        )
        self.team = Team.objects.create(organization=self.org, name="QA API")
        self.project = Project.objects.create(
            team=self.team, name="API App", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMemberRole.OWNER,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.suite = TestSuite.objects.create(
            project=self.project, name="API Suite", created_by=self.user
        )
        section = get_or_create_default_section(self.suite)
        from apps.testing.models import TestScenario
        scenario = TestScenario.objects.create(
            section=section, title="API scenarios", description=""
        )
        from apps.testing.models import TestCaseDesignStatus
        self.case = create_test_case_with_revision(
            scenario=scenario,
            title="API test case",
            expected_result="API responds 200",
            created_by=self.user,
            design_status=TestCaseDesignStatus.APPROVED,
        )

    def test_create_plan_via_api(self):
        response = self.client.post("/api/test-plans/", {
            "project": str(self.project.id),
            "name": "Sprint 1",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Sprint 1")

    def test_create_run_via_api(self):
        response = self.client.post("/api/test-runs/", {
            "project": str(self.project.id),
            "name": "Sprint 1 Run",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], TestRunStatus.PENDING)

    def test_expand_run_from_suite_via_api(self):
        run = create_test_run(self.project, name="Expand run", created_by=self.user)
        response = self.client.post(
            f"/api/test-runs/{run.id}/expand/",
            {"suite_id": str(self.suite.id)},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created_count"], 1)

    def test_viewer_cannot_create_plan(self):
        User = get_user_model()
        viewer = User.objects.create_user(
            username="viewer2",
            password="Pass1234!",
            email="viewer2@biat-api.tn",
            first_name="View",
            last_name="Er",
        )
        UserProfile.objects.create(
            user=viewer,
            organization=self.org,
            organization_role=OrganizationRole.MEMBER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=viewer,
            role=ProjectMemberRole.VIEWER,
        )
        self.client.force_authenticate(user=viewer)
        response = self.client.post("/api/test-plans/", {
            "project": str(self.project.id),
            "name": "Should fail",
        })
        self.assertIn(response.status_code, [400, 403])
