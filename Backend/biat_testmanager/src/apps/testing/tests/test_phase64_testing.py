"""
Phase 6.4 — Testing cleanup tests.

Covers:
- Design-status workflow endpoints (approve, archive)
- Run expansion filters out draft/archived cases
- Suite/section/scenario service functions
- Clone service function
- TestSuiteSummarySerializer on list vs TestSuiteSerializer on detail
- TestCaseSummarySerializer on list vs TestCaseSerializer on detail
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import (
    TestCase as TestCaseModel,
    TestCaseDesignStatus,
    TestPlan,
    TestRun,
    TestRunCase,
    TestRunStatus,
    TestScenario,
    TestSection,
    TestSuite,
)
from apps.testing.services.repository import (
    clone_test_scenario,
    create_test_case_with_revision,
    create_test_scenario,
    create_test_section,
    create_test_suite,
    get_or_create_default_section,
    approve_test_case,
    archive_test_case,
)
from apps.testing.services.runs import (
    create_test_run,
    expand_run_from_suite,
    expand_run_from_section,
)


def _make_user(username, email, org, org_role=OrganizationRole.MEMBER):
    user_model = get_user_model()
    user = user_model.objects.create_user(username=username, password="Pass1234!", email=email)  # NOSONAR
    UserProfile.objects.create(user=user, organization=org, organization_role=org_role)
    return user


class RepositoryServiceTests(TestCase):
    """Service-level tests for suite/section/scenario/clone."""

    def setUp(self):
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.user = _make_user("svc_user", "svc@biat.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.user)

    def test_create_test_suite_also_creates_default_section(self):
        suite = create_test_suite(self.project, name="Login Suite", created_by=self.user)
        self.assertIsNotNone(suite.pk)
        self.assertEqual(suite.sections.count(), 1)
        default_section = suite.sections.first()
        self.assertIsNone(default_section.parent)

    def test_create_test_section_creates_child_section(self):
        suite = create_test_suite(self.project, name="Auth Suite", created_by=self.user)
        section = create_test_section(suite, name="Edge Cases", order_index=1)
        self.assertEqual(section.suite, suite)
        self.assertIsNone(section.parent)
        self.assertEqual(section.name, "Edge Cases")

    def test_create_test_scenario_in_section(self):
        suite = create_test_suite(self.project, name="Payment Suite", created_by=self.user)
        section = get_or_create_default_section(suite)
        scenario = create_test_scenario(section, title="Happy path payment")
        self.assertEqual(scenario.section, section)
        self.assertEqual(scenario.title, "Happy path payment")

    def test_clone_test_scenario_copies_cases_and_revisions(self):
        suite = create_test_suite(self.project, name="Clone Suite", created_by=self.user)
        section = get_or_create_default_section(suite)
        scenario = create_test_scenario(section, title="Original scenario")
        create_test_case_with_revision(
            scenario=scenario,
            title="Case A",
            expected_result="Result A",
            created_by=self.user,
        )
        create_test_case_with_revision(
            scenario=scenario,
            title="Case B",
            expected_result="Result B",
            created_by=self.user,
        )

        cloned = clone_test_scenario(scenario)

        self.assertNotEqual(cloned.pk, scenario.pk)
        self.assertEqual(cloned.section, section)
        self.assertIn("Copy", cloned.title)
        self.assertEqual(cloned.cases.count(), 2)
        for cloned_case in cloned.cases.all():
            self.assertEqual(cloned_case.revisions.count(), 1)
            source_id = cloned_case.revisions.first().source_snapshot_json.get(
                "cloned_from_scenario_id"
            )
            self.assertEqual(source_id, str(scenario.id))


class DesignStatusServiceTests(TestCase):
    """Unit tests for approve/archive service functions."""

    def setUp(self):
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.user = _make_user("ds_user", "ds@biat.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.user)
        self.suite = create_test_suite(self.project, name="Suite", created_by=self.user)
        self.section = get_or_create_default_section(self.suite)
        self.scenario = create_test_scenario(self.section, title="Scenario")
        self.case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Draft case",
            expected_result="Result",
            created_by=self.user,
        )

    def test_approve_sets_approved_status(self):
        self.assertEqual(self.case.design_status, TestCaseDesignStatus.DRAFT)
        updated = approve_test_case(self.case)
        self.assertEqual(updated.design_status, TestCaseDesignStatus.APPROVED)
        self.case.refresh_from_db()
        self.assertEqual(self.case.design_status, TestCaseDesignStatus.APPROVED)

    def test_approve_is_idempotent(self):
        approve_test_case(self.case)
        approve_test_case(self.case)
        self.case.refresh_from_db()
        self.assertEqual(self.case.design_status, TestCaseDesignStatus.APPROVED)

    def test_archive_sets_archived_status(self):
        updated = archive_test_case(self.case)
        self.assertEqual(updated.design_status, TestCaseDesignStatus.ARCHIVED)
        self.case.refresh_from_db()
        self.assertEqual(self.case.design_status, TestCaseDesignStatus.ARCHIVED)


class RunExpansionFilterTests(TestCase):
    """Expansion only includes approved cases."""

    def setUp(self):
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.user = _make_user("exp_user", "exp@biat.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.user)
        self.suite = create_test_suite(self.project, name="Suite", created_by=self.user)
        self.section = get_or_create_default_section(self.suite)
        self.scenario = create_test_scenario(self.section, title="Scenario")

        self.draft_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Draft case",
            expected_result="Result",
            created_by=self.user,
            design_status=TestCaseDesignStatus.DRAFT,
        )
        self.approved_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Approved case",
            expected_result="Result",
            created_by=self.user,
            design_status=TestCaseDesignStatus.APPROVED,
        )
        self.archived_case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Archived case",
            expected_result="Result",
            created_by=self.user,
            design_status=TestCaseDesignStatus.ARCHIVED,
        )
        self.run = create_test_run(self.project, name="Sprint 1", created_by=self.user)

    def test_expand_from_suite_only_includes_approved_cases(self):
        run_cases = expand_run_from_suite(self.run, self.suite)
        case_ids = {rc.test_case_id for rc in run_cases}
        self.assertIn(self.approved_case.pk, case_ids)
        self.assertNotIn(self.draft_case.pk, case_ids)
        self.assertNotIn(self.archived_case.pk, case_ids)

    def test_expand_from_section_only_includes_approved_cases(self):
        run_cases = expand_run_from_section(self.run, self.section)
        case_ids = {rc.test_case_id for rc in run_cases}
        self.assertIn(self.approved_case.pk, case_ids)
        self.assertNotIn(self.draft_case.pk, case_ids)
        self.assertNotIn(self.archived_case.pk, case_ids)

    def test_expand_from_suite_with_no_approved_cases_returns_empty(self):
        suite2 = create_test_suite(self.project, name="Empty Suite", created_by=self.user)
        run2 = create_test_run(self.project, name="Empty run", created_by=self.user)
        run_cases = expand_run_from_suite(run2, suite2)
        self.assertEqual(run_cases, [])


class DesignStatusApiTests(TestCase):
    """API tests for approve/archive workflow endpoints."""

    def setUp(self):
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.user = _make_user("api_user", "api@biat.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.viewer = _make_user("viewer", "viewer@biat.tn", self.org)
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.user)
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        ProjectMember.objects.create(
            project=self.project, user=self.viewer, role=ProjectMemberRole.VIEWER
        )
        self.suite = create_test_suite(self.project, name="Suite", created_by=self.user)
        self.section = get_or_create_default_section(self.suite)
        self.scenario = create_test_scenario(self.section, title="Scenario")
        self.case = create_test_case_with_revision(
            scenario=self.scenario,
            title="Draft case",
            expected_result="Result",
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_approve_endpoint_transitions_to_approved(self):
        url = reverse("test-case-approve", kwargs={"case_pk": self.case.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["design_status"], TestCaseDesignStatus.APPROVED)
        self.case.refresh_from_db()
        self.assertEqual(self.case.design_status, TestCaseDesignStatus.APPROVED)

    def test_archive_endpoint_transitions_to_archived(self):
        url = reverse("test-case-archive", kwargs={"case_pk": self.case.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["design_status"], TestCaseDesignStatus.ARCHIVED)
        self.case.refresh_from_db()
        self.assertEqual(self.case.design_status, TestCaseDesignStatus.ARCHIVED)

    def test_viewer_cannot_approve(self):
        self.client.force_authenticate(self.viewer)
        url = reverse("test-case-approve", kwargs={"case_pk": self.case.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_archive(self):
        self.client.force_authenticate(self.viewer)
        url = reverse("test-case-archive", kwargs={"case_pk": self.case.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_approve(self):
        self.client.force_authenticate(None)
        url = reverse("test-case-approve", kwargs={"case_pk": self.case.pk})
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class SuiteListDetailSerializerTests(TestCase):
    """List responses use summary serializer; detail uses full serializer."""

    def setUp(self):
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.user = _make_user("list_user", "list@biat.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.user)
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite = create_test_suite(self.project, name="Auth Suite", created_by=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_response_does_not_include_nested_sections(self):
        url = reverse("test-suite-list-create")
        response = self.client.get(url, {"project": str(self.project.pk)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        suite_data = response.data["results"][0]
        # Summary serializer — no nested sections
        self.assertNotIn("sections", suite_data)
        self.assertNotIn("linked_specifications", suite_data)
        # But counts should be present
        self.assertIn("section_count", suite_data)
        self.assertIn("total_case_count", suite_data)

    def test_detail_response_includes_nested_sections(self):
        url = reverse("test-suite-detail", kwargs={"pk": self.suite.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sections", response.data)
        self.assertIn("linked_specifications", response.data)
        self.assertIn("default_section_id", response.data)
