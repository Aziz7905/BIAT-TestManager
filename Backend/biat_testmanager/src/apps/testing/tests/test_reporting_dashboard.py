from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.automation.models import TestExecution, TestResult
from apps.automation.models.choices import TestResultStatus
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import (
    TestCaseDesignStatus,
    TestRunCaseStatus,
    TestRunStatus,
)
from apps.testing.services import (
    build_project_pass_rate_trend,
    build_project_quality_dashboard,
    create_test_case_with_revision,
    create_test_run,
    create_test_scenario,
    create_test_suite,
    expand_run_from_cases,
    get_or_create_default_section,
    list_project_failure_hotspots,
)


def _make_user(username, email, org, role=OrganizationRole.MEMBER):
    user_model = get_user_model()
    user = user_model.objects.create_user(username=username, password="Pass1234!", email=email)  # NOSONAR
    UserProfile.objects.create(user=user, organization=org, organization_role=role)
    return user


class ReportingDashboardServiceTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.owner = _make_user("report.owner", "report.owner@biat.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.project = Project.objects.create(team=self.team, name="Portal", created_by=self.owner)
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMemberRole.OWNER,
        )

        self.suite = create_test_suite(self.project, name="Payments", created_by=self.owner)
        self.section = get_or_create_default_section(self.suite)
        self.scenario = create_test_scenario(self.section, title="Payments scenario")
        self.case_a = create_test_case_with_revision(
            scenario=self.scenario,
            title="Transfer succeeds",
            expected_result="Transfer succeeds",
            created_by=self.owner,
            design_status=TestCaseDesignStatus.APPROVED,
        )
        self.case_b = create_test_case_with_revision(
            scenario=self.scenario,
            title="Transfer fails",
            expected_result="Failure is shown",
            created_by=self.owner,
            design_status=TestCaseDesignStatus.APPROVED,
        )

        self.run_failed = create_test_run(self.project, name="Nightly 1", created_by=self.owner)
        self.run_active = create_test_run(self.project, name="Live run", created_by=self.owner)
        self.run_error = create_test_run(self.project, name="Nightly 2", created_by=self.owner)

        self.failed_run_cases = expand_run_from_cases(self.run_failed, [self.case_a, self.case_b])
        self.active_run_cases = expand_run_from_cases(self.run_active, [self.case_a])
        self.error_run_cases = expand_run_from_cases(self.run_error, [self.case_b])

        self._set_run_case_status(self.failed_run_cases[0], TestRunCaseStatus.PASSED)
        self._set_run_case_status(self.failed_run_cases[1], TestRunCaseStatus.FAILED)
        self._set_run_case_status(self.active_run_cases[0], TestRunCaseStatus.RUNNING)
        self._set_run_case_status(self.error_run_cases[0], TestRunCaseStatus.ERROR)

        self._set_run_status(self.run_failed, TestRunStatus.FAILED, now - timedelta(days=2))
        self._set_run_status(self.run_active, TestRunStatus.RUNNING, now)
        self._set_run_status(self.run_error, TestRunStatus.FAILED, now - timedelta(days=1))

        self._create_result(
            run_case=self.failed_run_cases[0],
            test_case=self.case_a,
            status=TestResultStatus.PASSED,
            created_at=now - timedelta(days=2),
        )
        self._create_result(
            run_case=self.failed_run_cases[1],
            test_case=self.case_b,
            status=TestResultStatus.FAILED,
            created_at=now - timedelta(days=2),
        )
        self._create_result(
            run_case=self.error_run_cases[0],
            test_case=self.case_b,
            status=TestResultStatus.ERROR,
            created_at=now - timedelta(days=1),
        )

    def _set_run_case_status(self, run_case, status_value):
        run_case.status = status_value
        run_case.save(update_fields=["status", "updated_at"])

    def _set_run_status(self, run, status_value, started_at):
        ended_at = started_at + timedelta(minutes=5) if status_value != TestRunStatus.RUNNING else None
        run.status = status_value
        run.started_at = started_at
        run.ended_at = ended_at
        run.save(update_fields=["status", "started_at", "ended_at"])

    def _create_result(self, *, run_case, test_case, status, created_at):
        execution = TestExecution.objects.create(
            test_case=test_case,
            triggered_by=self.owner,
            run_case=run_case,
            status=status,
        )
        result = TestResult.objects.create(
            execution=execution,
            status=status,
            duration_ms=1500,
            total_steps=3,
            passed_steps=3 if status == TestResultStatus.PASSED else 1,
            failed_steps=0 if status == TestResultStatus.PASSED else 1,
            error_message="boom" if status != TestResultStatus.PASSED else "",
        )
        TestResult.objects.filter(pk=result.pk).update(created_at=created_at)
        TestExecution.objects.filter(pk=execution.pk).update(
            started_at=created_at - timedelta(seconds=2),
            ended_at=created_at,
        )
        result.refresh_from_db()
        execution.refresh_from_db()
        return result

    def test_build_project_quality_dashboard_returns_summary_and_recent_runs(self):
        payload = build_project_quality_dashboard(self.project, recent_run_limit=2)

        self.assertEqual(payload["project"]["id"], self.project.id)
        self.assertEqual(payload["summary"]["total_runs"], 3)
        self.assertEqual(payload["summary"]["active_runs"], 1)
        self.assertEqual(payload["summary"]["completed_runs"], 2)
        self.assertEqual(payload["summary"]["total_run_cases"], 4)
        self.assertEqual(payload["summary"]["passed_run_cases"], 1)
        self.assertEqual(payload["summary"]["failed_run_cases"], 2)
        self.assertEqual(payload["summary"]["pass_rate"], 25.0)
        self.assertEqual(len(payload["recent_runs"]), 2)

    def test_build_project_pass_rate_trend_returns_daily_points(self):
        payload = build_project_pass_rate_trend(self.project, days=3)

        self.assertEqual(payload["days"], 3)
        self.assertEqual(len(payload["points"]), 3)
        self.assertEqual(payload["points"][0]["failed_results"], 1)
        self.assertEqual(payload["points"][0]["passed_results"], 1)
        self.assertEqual(payload["points"][0]["pass_rate"], 50.0)
        self.assertEqual(payload["points"][1]["failed_results"], 1)

    def test_list_project_failure_hotspots_returns_failing_case_first(self):
        payload = list_project_failure_hotspots(self.project, days=7, limit=5)

        self.assertEqual(len(payload["items"]), 1)
        hotspot = payload["items"][0]
        self.assertEqual(hotspot["test_case_id"], self.case_b.id)
        self.assertEqual(hotspot["failure_count"], 1)
        self.assertEqual(hotspot["error_count"], 1)
        self.assertEqual(hotspot["suite_name"], self.suite.name)


class ReportingDashboardApiTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.org = Organization.objects.create(name="BIAT API", domain="biat-api.tn")
        self.owner = _make_user("dash.owner", "dash.owner@biat-api.tn", self.org, OrganizationRole.ORG_ADMIN)
        self.viewer = _make_user("dash.viewer", "dash.viewer@biat-api.tn", self.org)
        self.outsider_org = Organization.objects.create(name="Other", domain="other.tn")
        self.outsider = _make_user("dash.outsider", "dash.outsider@other.tn", self.outsider_org)
        self.team = Team.objects.create(organization=self.org, name="QA API")
        self.project = Project.objects.create(team=self.team, name="API Portal", created_by=self.owner)
        ProjectMember.objects.create(project=self.project, user=self.owner, role=ProjectMemberRole.OWNER)
        ProjectMember.objects.create(project=self.project, user=self.viewer, role=ProjectMemberRole.VIEWER)

        suite = create_test_suite(self.project, name="API Suite", created_by=self.owner)
        section = get_or_create_default_section(suite)
        scenario = create_test_scenario(section, title="API scenario")
        case = create_test_case_with_revision(
            scenario=scenario,
            title="API case",
            expected_result="200 OK",
            created_by=self.owner,
            design_status=TestCaseDesignStatus.APPROVED,
        )
        run = create_test_run(self.project, name="API run", created_by=self.owner)
        run_case = expand_run_from_cases(run, [case])[0]
        run_case.status = TestRunCaseStatus.PASSED
        run_case.save(update_fields=["status", "updated_at"])
        run.status = TestRunStatus.PASSED
        run.started_at = now - timedelta(hours=1)
        run.ended_at = now - timedelta(minutes=50)
        run.save(update_fields=["status", "started_at", "ended_at"])

        execution = TestExecution.objects.create(
            test_case=case,
            triggered_by=self.owner,
            run_case=run_case,
            status=TestResultStatus.PASSED,
        )
        TestResult.objects.create(
            execution=execution,
            status=TestResultStatus.PASSED,
            duration_ms=800,
            total_steps=2,
            passed_steps=2,
            failed_steps=0,
        )

        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_reporting_overview_endpoint_returns_dashboard_payload(self):
        response = self.client.get(
            reverse("project-reporting-overview", kwargs={"project_pk": self.project.pk}),
            {"recent_runs": 3},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["project"]["id"], str(self.project.id))
        self.assertIn("summary", response.data)
        self.assertIn("recent_runs", response.data)
        self.assertEqual(response.data["summary"]["total_runs"], 1)

    def test_pass_rate_trend_endpoint_returns_points(self):
        response = self.client.get(
            reverse(
                "project-reporting-pass-rate-trend",
                kwargs={"project_pk": self.project.pk},
            ),
            {"days": 7},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 7)
        self.assertEqual(len(response.data["points"]), 7)

    def test_failure_hotspots_endpoint_returns_items(self):
        response = self.client.get(
            reverse(
                "project-reporting-failure-hotspots",
                kwargs={"project_pk": self.project.pk},
            ),
            {"days": 30, "limit": 5},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["project"]["id"], str(self.project.id))
        self.assertEqual(response.data["items"], [])

    def test_project_viewer_can_access_reporting(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.get(
            reverse("project-reporting-overview", kwargs={"project_pk": self.project.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_outsider_cannot_access_reporting(self):
        self.client.force_authenticate(self.outsider)
        response = self.client.get(
            reverse("project-reporting-overview", kwargs={"project_pk": self.project.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
