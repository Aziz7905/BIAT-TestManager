from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.projects.models import Project
from apps.testing.models import (
    TestCaseDesignStatus,
    TestPlan,
    TestRun,
    TestRunKind,
    TestScenario,
    TestSuite,
)
from apps.testing.services.repository import (
    create_test_case_with_revision,
    get_or_create_default_section,
)
from apps.testing.services.runs import (
    create_test_plan,
    create_test_run,
    get_or_create_adhoc_run_case,
)


class RunKindTests(TestCase):
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
        self.scenario = TestScenario.objects.create(
            section=self.section,
            title="Login scenarios",
            description="",
        )
        self.case_a = create_test_case_with_revision(
            scenario=self.scenario,
            title="Valid login",
            expected_result="User is logged in",
            created_by=self.user,
            design_status=TestCaseDesignStatus.APPROVED,
        )

    def test_create_run_without_plan_defaults_to_standalone(self):
        run = create_test_run(self.project, name="Sanity check", created_by=self.user)
        self.assertEqual(run.run_kind, TestRunKind.STANDALONE)

    def test_create_run_with_plan_defaults_to_planned(self):
        plan = create_test_plan(self.project, name="Release v1", created_by=self.user)
        run = create_test_run(
            self.project, name="Chrome regression", created_by=self.user, plan=plan
        )
        self.assertEqual(run.run_kind, TestRunKind.PLANNED)

    def test_adhoc_execution_creates_system_generated_run(self):
        run_case = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)
        self.assertEqual(run_case.run.run_kind, TestRunKind.SYSTEM_GENERATED)

    def test_adhoc_reuses_existing_pending_system_generated_run(self):
        first = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)
        second = get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)
        self.assertEqual(first.pk, second.pk)

    def test_runs_list_excludes_system_generated_by_default(self):
        plan = create_test_plan(self.project, name="Release v1", created_by=self.user)
        planned = create_test_run(
            self.project, name="Planned run", created_by=self.user, plan=plan
        )
        standalone = create_test_run(
            self.project, name="Standalone run", created_by=self.user
        )
        get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)

        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(
            reverse("test-run-list-create"), {"project": str(self.project.id)}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        ids = {row["id"] for row in results}
        self.assertIn(str(planned.id), ids)
        self.assertIn(str(standalone.id), ids)
        for row in results:
            self.assertNotEqual(row["run_kind"], TestRunKind.SYSTEM_GENERATED)

    def test_runs_list_includes_system_generated_when_requested(self):
        get_or_create_adhoc_run_case(self.case_a, triggered_by=self.user)

        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get(
            reverse("test-run-list-create"),
            {"project": str(self.project.id), "include_system": "true"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        kinds = {row["run_kind"] for row in results}
        self.assertIn(TestRunKind.SYSTEM_GENERATED, kinds)
