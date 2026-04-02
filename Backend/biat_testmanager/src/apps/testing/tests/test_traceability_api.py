from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import UserProfileRole
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.specs.models import Specification, SpecificationSourceType
from apps.testing.models import TestCase, TestScenario, TestSuite


class TraceabilityApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()

        self.organization = Organization.objects.create(
            name="BIAT IT",
            domain="biat-it.tn",
        )
        self.other_organization = Organization.objects.create(
            name="Other Org",
            domain="other-org.tn",
        )

        self.user = user_model.objects.create_user(
            username="qa.manager",
            password="Pass1234!",
            first_name="QA",
            last_name="Manager",
            email="qa.manager@biat-it.tn",
        )
        UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
            role=UserProfileRole.TESTER,
        )

        self.team = Team.objects.create(
            organization=self.organization,
            name="Devops",
            manager=self.user,
        )
        self.other_team = Team.objects.create(
            organization=self.other_organization,
            name="External",
        )

        self.project = Project.objects.create(
            team=self.team,
            name="Workspace Project",
            created_by=self.user,
        )
        self.other_project = Project.objects.create(
            team=self.other_team,
            name="Other Project",
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMemberRole.OWNER,
        )

        self.specification = Specification.objects.create(
            project=self.project,
            title="REQ-LOGIN",
            content="Login requirement",
            source_type=SpecificationSourceType.MANUAL,
            external_reference="REQ-LOGIN",
            uploaded_by=self.user,
        )
        self.uncovered_specification = Specification.objects.create(
            project=self.project,
            title="REQ-UNLINKED",
            content="Unlinked requirement",
            source_type=SpecificationSourceType.MANUAL,
            external_reference="REQ-UNLINKED",
            uploaded_by=self.user,
        )
        self.foreign_specification = Specification.objects.create(
            project=self.other_project,
            title="REQ-FOREIGN",
            content="Foreign requirement",
            source_type=SpecificationSourceType.MANUAL,
            external_reference="REQ-FOREIGN",
        )

        self.direct_suite = TestSuite.objects.create(
            project=self.project,
            specification=self.specification,
            name="Authentication Suite",
            folder_path="Core/Auth",
            created_by=self.user,
        )
        self.indirect_suite = TestSuite.objects.create(
            project=self.project,
            name="Regression Suite",
            folder_path="Regression",
            created_by=self.user,
        )

        self.direct_scenario = TestScenario.objects.create(
            suite=self.direct_suite,
            title="Successful login",
            description="Verify the user can log in successfully.",
        )
        self.indirect_scenario = TestScenario.objects.create(
            suite=self.indirect_suite,
            title="Logout coverage",
            description="Verify logout flow keeps login requirement traceable.",
        )

        self.direct_case = TestCase.objects.create(
            scenario=self.direct_scenario,
            title="Login with valid credentials",
            expected_result="User reaches the dashboard.",
            steps=[{"step": "Enter credentials", "outcome": "Dashboard shown"}],
        )
        self.direct_case.linked_specifications.add(self.specification)

        self.indirect_case = TestCase.objects.create(
            scenario=self.indirect_scenario,
            title="Logout returns to login",
            expected_result="User is returned to the login screen.",
            steps=[{"step": "Click logout", "outcome": "Login screen shown"}],
        )
        self.indirect_case.linked_specifications.add(self.specification)

        self.client.force_authenticate(self.user)

    def test_create_test_case_persists_multiple_linked_specifications(self):
        response = self.client.post(
            reverse(
                "test-case-list-create",
                kwargs={"scenario_pk": self.direct_scenario.id},
            ),
            {
                "title": "Password lockout",
                "preconditions": "Account exists",
                "steps": [
                    {"step": "Enter invalid password five times", "outcome": "Account locks"}
                ],
                "expected_result": "The account is locked.",
                "test_data": {},
                "status": "draft",
                "automation_status": "manual",
                "jira_issue_key": None,
                "on_failure": "fail_but_continue",
                "timeout_ms": 120000,
                "order_index": 0,
                "linked_specification_ids": [
                    str(self.specification.id),
                    str(self.uncovered_specification.id),
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_case = TestCase.objects.get(title="Password lockout")
        self.assertCountEqual(
            created_case.linked_specifications.values_list("id", flat=True),
            [self.specification.id, self.uncovered_specification.id],
        )

    def test_cannot_link_test_case_to_specification_from_another_project(self):
        response = self.client.post(
            reverse(
                "test-case-list-create",
                kwargs={"scenario_pk": self.direct_scenario.id},
            ),
            {
                "title": "Invalid cross-project link",
                "preconditions": "Account exists",
                "steps": [
                    {"step": "Attempt cross-project link", "outcome": "Validation error"}
                ],
                "expected_result": "The API rejects the link.",
                "test_data": {},
                "status": "draft",
                "automation_status": "manual",
                "jira_issue_key": None,
                "on_failure": "fail_but_continue",
                "timeout_ms": 120000,
                "order_index": 0,
                "linked_specification_ids": [str(self.foreign_specification.id)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("linked_specification_ids", response.data)

    def test_test_suite_filter_returns_direct_and_indirect_matches_once(self):
        response = self.client.get(
            reverse("test-suite-list-create"),
            {
                "project": str(self.project.id),
                "specification": str(self.specification.id),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        returned_suite_ids = {item["id"] for item in response.data}
        self.assertSetEqual(
            returned_suite_ids,
            {str(self.direct_suite.id), str(self.indirect_suite.id)},
        )

    def test_specification_serializer_exposes_coverage_counts(self):
        response = self.client.get(
            reverse("specification-list-create"),
            {"project": str(self.project.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        specification_payload = next(
            item for item in response.data if item["id"] == str(self.specification.id)
        )
        uncovered_payload = next(
            item
            for item in response.data
            if item["id"] == str(self.uncovered_specification.id)
        )

        self.assertEqual(specification_payload["linked_test_case_count"], 2)
        self.assertEqual(specification_payload["linked_scenario_count"], 2)
        self.assertEqual(specification_payload["linked_suite_count"], 2)
        self.assertEqual(specification_payload["coverage_status"], "covered")
        self.assertEqual(len(specification_payload["linked_test_cases"]), 2)

        self.assertEqual(uncovered_payload["linked_test_case_count"], 0)
        self.assertEqual(uncovered_payload["linked_scenario_count"], 0)
        self.assertEqual(uncovered_payload["linked_suite_count"], 0)
        self.assertEqual(uncovered_payload["coverage_status"], "uncovered")
        self.assertEqual(uncovered_payload["linked_test_cases"], [])
