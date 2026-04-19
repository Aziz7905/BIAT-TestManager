from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.automation.models import AutomationScript, TestExecution, TestResult
from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
    TestResultStatus,
)
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.specs.models import Specification, SpecificationSourceType
from apps.testing.models import TestCaseAutomationStatus, TestCaseDesignStatus, TestPriority
from apps.testing.serializers.repository import ProjectRepositoryTreeSerializer
from apps.testing.services import (
    build_project_repository_tree_summary,
    build_test_case_workspace,
    build_test_scenario_overview,
    clone_test_case,
    create_test_case_with_revision,
    create_test_scenario,
    create_test_suite,
    get_or_create_default_section,
    get_repository_tree_suites,
)


def _make_user(username, email, organization, role=OrganizationRole.MEMBER):
    user_model = get_user_model()
    user = user_model.objects.create_user(username=username, password="Pass1234!", email=email)  # NOSONAR
    UserProfile.objects.create(user=user, organization=organization, organization_role=role)
    return user


class RepositoryWorkspaceServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="BIAT Repo", domain="repo.biat.tn")
        self.owner = _make_user(
            "repo.owner",
            "repo.owner@biat.tn",
            self.organization,
            OrganizationRole.ORG_ADMIN,
        )
        self.team = Team.objects.create(organization=self.organization, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.owner)
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMemberRole.OWNER,
        )

        self.suite = create_test_suite(
            self.project,
            name="Checkout",
            created_by=self.owner,
            description="Checkout coverage",
            folder_path="web/checkout",
        )
        self.section = get_or_create_default_section(self.suite)
        self.scenario = create_test_scenario(
            self.section,
            title="Visa payment succeeds",
            description="Validate successful payment with a Visa card.",
            priority=TestPriority.HIGH,
        )
        self.specification = Specification.objects.create(
            project=self.project,
            title="REQ-3DS",
            content="Checkout must support 3DS authentication.",
            source_type=SpecificationSourceType.MANUAL,
            external_reference="REQ-3DS",
            uploaded_by=self.owner,
        )
        self.test_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="3DS flow succeeds",
            preconditions="User is on checkout.",
            steps=[{"step": "Submit payment", "outcome": "3DS challenge opens"}],
            expected_result="Order is confirmed.",
            test_data={"card_type": "visa"},
            created_by=self.owner,
            design_status=TestCaseDesignStatus.APPROVED,
            automation_status=TestCaseAutomationStatus.AUTOMATED,
            on_failure="fail_but_continue",
            timeout_ms=180000,
            linked_specifications=[self.specification],
        )

        self.script = AutomationScript.objects.create(
            test_case=self.test_case,
            test_case_revision=self.test_case.revisions.first(),
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.TYPESCRIPT,
            script_content="test('checkout', async () => {});",
            is_active=True,
        )
        self.execution = TestExecution.objects.create(
            test_case=self.test_case,
            script=self.script,
            triggered_by=self.owner,
            status=TestResultStatus.PASSED,
        )
        self.result = TestResult.objects.create(
            execution=self.execution,
            status=TestResultStatus.PASSED,
            duration_ms=1450,
            total_steps=3,
            passed_steps=3,
            failed_steps=0,
        )
        started_at = timezone.now() - timedelta(minutes=5)
        TestExecution.objects.filter(pk=self.execution.pk).update(
            started_at=started_at,
            ended_at=started_at + timedelta(seconds=2),
        )
        self.execution.refresh_from_db()

    def test_project_tree_serializer_excludes_inline_cases_and_keeps_summary(self):
        serializer = ProjectRepositoryTreeSerializer(
            {
                "project_id": self.project.id,
                "project_name": self.project.name,
                "summary": build_project_repository_tree_summary(self.project),
                "suites": get_repository_tree_suites(self.project),
            }
        )

        payload = serializer.data
        self.assertEqual(payload["summary"]["case_count"], 1)
        self.assertEqual(payload["summary"]["approved_case_count"], 1)

        scenario_payload = payload["suites"][0]["sections"][0]["scenarios"][0]
        self.assertEqual(scenario_payload["title"], self.scenario.title)
        self.assertEqual(scenario_payload["case_count"], 1)
        self.assertNotIn("cases", scenario_payload)

    def test_case_workspace_service_returns_automation_snapshot_and_history(self):
        payload = build_test_case_workspace(self.test_case)

        self.assertEqual(payload["title"], self.test_case.title)
        self.assertEqual(payload["design"]["on_failure"], self.test_case.on_failure)
        self.assertEqual(payload["design"]["timeout_ms"], self.test_case.timeout_ms)
        self.assertTrue(payload["automation"]["has_active_script"])
        self.assertEqual(payload["automation"]["active_script_count"], 1)
        self.assertEqual(payload["automation"]["latest_execution"]["status"], TestResultStatus.PASSED)
        self.assertEqual(payload["history"]["version_history"][0]["version_number"], 1)
        self.assertEqual(payload["history"]["recent_results"][0]["status"], TestResultStatus.PASSED)

    def test_clone_test_case_copies_design_and_resets_revision_history(self):
        cloned_case = clone_test_case(self.test_case, created_by=self.owner)

        self.assertNotEqual(cloned_case.id, self.test_case.id)
        self.assertEqual(cloned_case.scenario_id, self.test_case.scenario_id)
        self.assertEqual(cloned_case.title, f"{self.test_case.title} Copy")
        self.assertEqual(cloned_case.preconditions, self.test_case.preconditions)
        self.assertEqual(cloned_case.steps, self.test_case.steps)
        self.assertEqual(cloned_case.expected_result, self.test_case.expected_result)
        self.assertEqual(cloned_case.test_data, self.test_case.test_data)
        self.assertEqual(cloned_case.design_status, self.test_case.design_status)
        self.assertEqual(cloned_case.automation_status, self.test_case.automation_status)
        self.assertEqual(cloned_case.on_failure, self.test_case.on_failure)
        self.assertEqual(cloned_case.timeout_ms, self.test_case.timeout_ms)
        self.assertEqual(cloned_case.version, 1)
        self.assertEqual(cloned_case.revisions.count(), 1)
        self.assertSetEqual(
            set(cloned_case.linked_specifications.values_list("id", flat=True)),
            {self.specification.id},
        )
        self.assertGreater(cloned_case.order_index, self.test_case.order_index)

    def test_scenario_overview_service_returns_compact_case_rows(self):
        payload = build_test_scenario_overview(self.scenario)

        self.assertEqual(payload["coverage"]["case_count"], 1)
        self.assertEqual(payload["coverage"]["automated_case_count"], 1)
        self.assertEqual(payload["execution_snapshot"]["recent_execution_count"], 1)
        self.assertEqual(len(payload["cases"]), 1)
        self.assertEqual(payload["cases"][0]["latest_result_status"], TestResultStatus.PASSED)
        self.assertTrue(payload["cases"][0]["has_active_script"])


class RepositoryWorkspaceApiTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="BIAT Repo API", domain="repo-api.biat.tn")
        self.owner = _make_user(
            "repo.api.owner",
            "repo.api.owner@biat.tn",
            self.organization,
            OrganizationRole.ORG_ADMIN,
        )
        self.viewer = _make_user(
            "repo.api.viewer",
            "repo.api.viewer@biat.tn",
            self.organization,
        )
        outsider_organization = Organization.objects.create(name="Other", domain="other.tn")
        self.outsider = _make_user(
            "repo.api.outsider",
            "repo.api.outsider@other.tn",
            outsider_organization,
        )

        self.team = Team.objects.create(organization=self.organization, name="QA API")
        self.project = Project.objects.create(team=self.team, name="Payments Portal", created_by=self.owner)
        ProjectMember.objects.create(project=self.project, user=self.owner, role=ProjectMemberRole.OWNER)
        ProjectMember.objects.create(project=self.project, user=self.viewer, role=ProjectMemberRole.VIEWER)

        self.suite = create_test_suite(
            self.project,
            name="Checkout",
            created_by=self.owner,
            folder_path="web/checkout",
        )
        self.section = get_or_create_default_section(self.suite)
        self.scenario = create_test_scenario(
            self.section,
            title="Visa payment succeeds",
            description="Validate successful payment with a Visa card.",
            priority=TestPriority.HIGH,
        )
        self.specification = Specification.objects.create(
            project=self.project,
            title="REQ-CHECKOUT",
            content="Checkout requirement",
            source_type=SpecificationSourceType.MANUAL,
            external_reference="REQ-CHECKOUT",
            uploaded_by=self.owner,
        )
        self.test_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="3DS flow succeeds",
            preconditions="User is on checkout.",
            steps=[{"step": "Submit payment", "outcome": "3DS challenge opens"}],
            expected_result="Order is confirmed.",
            test_data={"card_type": "visa"},
            created_by=self.owner,
            design_status=TestCaseDesignStatus.APPROVED,
            automation_status=TestCaseAutomationStatus.AUTOMATED,
            on_failure="fail_but_continue",
            timeout_ms=180000,
            linked_specifications=[self.specification],
        )

        self.script = AutomationScript.objects.create(
            test_case=self.test_case,
            test_case_revision=self.test_case.revisions.first(),
            framework=AutomationFramework.PLAYWRIGHT,
            language=AutomationLanguage.TYPESCRIPT,
            script_content="test('checkout', async () => {});",
            is_active=True,
        )
        self.execution = TestExecution.objects.create(
            test_case=self.test_case,
            script=self.script,
            triggered_by=self.owner,
            status=TestResultStatus.PASSED,
        )
        TestResult.objects.create(
            execution=self.execution,
            status=TestResultStatus.PASSED,
            duration_ms=900,
            total_steps=2,
            passed_steps=2,
            failed_steps=0,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_project_tree_endpoint_returns_lazy_scenario_nodes(self):
        response = self.client.get(reverse("project-tree", kwargs={"pk": self.project.pk}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["summary"]["case_count"], 1)
        scenario_payload = response.data["suites"][0]["sections"][0]["scenarios"][0]
        self.assertEqual(scenario_payload["case_count"], 1)
        self.assertNotIn("cases", scenario_payload)

    def test_scenario_cases_endpoint_returns_compact_case_summary(self):
        response = self.client.get(
            reverse("test-case-list-create", kwargs={"scenario_pk": self.scenario.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        case_payload = response.data[0]
        self.assertEqual(case_payload["title"], self.test_case.title)
        self.assertEqual(case_payload["latest_result_status"], TestResultStatus.PASSED)
        self.assertTrue(case_payload["has_active_script"])
        self.assertNotIn("expected_result", case_payload)

    def test_repository_workspace_endpoints_return_payloads_for_project_viewer(self):
        self.client.force_authenticate(self.viewer)

        responses = {
            "project": self.client.get(
                reverse("project-repository-overview", kwargs={"project_pk": self.project.pk})
            ),
            "suite": self.client.get(
                reverse("test-suite-overview", kwargs={"suite_pk": self.suite.pk})
            ),
            "section": self.client.get(
                reverse("test-section-overview", kwargs={"section_pk": self.section.pk})
            ),
            "scenario": self.client.get(
                reverse("test-scenario-overview", kwargs={"scenario_pk": self.scenario.pk})
            ),
            "case": self.client.get(
                reverse("test-case-workspace", kwargs={"case_pk": self.test_case.pk})
            ),
        }

        for response in responses.values():
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertIn("summary", responses["project"].data)
        self.assertIn("sections", responses["suite"].data)
        self.assertIn("child_sections", responses["section"].data)
        self.assertIn("cases", responses["scenario"].data)
        self.assertIn("automation", responses["case"].data)
        self.assertIn("history", responses["case"].data)
        self.assertIn("on_failure", responses["case"].data["design"])
        self.assertIn("timeout_ms", responses["case"].data["design"])

    def test_case_clone_endpoint_returns_compact_summary_and_copies_links(self):
        response = self.client.post(
            reverse("test-case-clone", kwargs={"case_pk": self.test_case.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], f"{self.test_case.title} Copy")
        self.assertEqual(response.data["design_status"], self.test_case.design_status)
        cloned_case = self.test_case.scenario.cases.get(pk=response.data["id"])
        self.assertEqual(cloned_case.version, 1)
        self.assertSetEqual(
            set(cloned_case.linked_specifications.values_list("id", flat=True)),
            {self.specification.id},
        )

    def test_outsider_cannot_clone_case(self):
        self.client.force_authenticate(self.outsider)

        response = self.client.post(
            reverse("test-case-clone", kwargs={"case_pk": self.test_case.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_outsider_cannot_access_repository_workspace_endpoints(self):
        self.client.force_authenticate(self.outsider)

        endpoints = [
            reverse("project-tree", kwargs={"pk": self.project.pk}),
            reverse("project-repository-overview", kwargs={"project_pk": self.project.pk}),
            reverse("test-suite-overview", kwargs={"suite_pk": self.suite.pk}),
            reverse("test-section-overview", kwargs={"section_pk": self.section.pk}),
            reverse("test-scenario-overview", kwargs={"scenario_pk": self.scenario.pk}),
            reverse("test-case-workspace", kwargs={"case_pk": self.test_case.pk}),
        ]

        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
