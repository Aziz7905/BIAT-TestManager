from __future__ import annotations

import sys

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, Team, TeamMembership, UserProfile
from apps.accounts.models.choices import OrganizationRole, TeamMembershipRole
from apps.automation.models import AutomationScript, ExecutionSchedule, TestExecution
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as QaTestCase
from apps.testing.models import TestScenario, TestSection, TestSuite


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
)
class AutomationApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="qa.owner",
            password="Pass1234!",  # NOSONAR
            email="qa.owner@biat-it.tn",
            first_name="QA",
            last_name="Owner",
        )
        self.viewer = user_model.objects.create_user(
            username="qa.viewer",
            password="Pass1234!",  # NOSONAR
            email="qa.viewer@biat-it.tn",
        )

        self.organization = Organization.objects.create(
            name="BIAT IT",
            domain="biat-it.tn",
        )
        UserProfile.objects.create(
            user=self.user,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        UserProfile.objects.create(
            user=self.viewer,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )

        self.team = Team.objects.create(
            organization=self.organization,
            name="QA Team",
            manager=self.user,
        )
        TeamMembership.objects.create(
            team=self.team,
            user=self.user,
            role=TeamMembershipRole.TESTER,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=self.team,
            user=self.viewer,
            role=TeamMembershipRole.VIEWER,
            is_active=True,
        )
        self.project = Project.objects.create(
            team=self.team,
            name="Automation Workspace",
            created_by=self.user,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.user,
            role=ProjectMemberRole.OWNER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMemberRole.VIEWER,
        )

        self.suite = TestSuite.objects.create(
            project=self.project,
            name="Authentication Suite",
            folder_path="Core/Auth",
            created_by=self.user,
        )
        self.section = TestSection.objects.create(
            suite=self.suite,
            name="General",
            order_index=0,
        )
        self.scenario = TestScenario.objects.create(
            section=self.section,
            title="Successful login",
            description="Check valid login flow.",
        )
        self.test_case = QaTestCase.objects.create(
            scenario=self.scenario,
            title="Login with valid credentials",
            preconditions="User exists",
            steps=[
                {"step": "Open login page", "outcome": "Form is visible"},
                {"step": "Submit valid credentials", "outcome": "Dashboard loads"},
            ],
            expected_result="Dashboard is displayed.",
        )

        self.client.force_authenticate(self.user)

    def _script_payload(self, *, framework="playwright", script_content="print('playwright smoke')"):
        return {
            "test_case": self.test_case,
            "framework": framework,
            "language": "python",
            "script_content": script_content,
            "generated_by": "user",
            "is_active": True,
        }

    def _script_request_payload(self, **kwargs):
        payload = self._script_payload(**kwargs).copy()
        payload["test_case"] = str(self.test_case.id)
        return payload

    def test_create_script_and_filter_by_test_case(self):
        create_response = self.client.post(
            reverse("automation-script-list-create"),
            self._script_request_payload(),
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        created_script = AutomationScript.objects.get(test_case=self.test_case)
        self.assertEqual(created_script.script_version, 1)
        self.assertTrue(created_script.is_active)

        list_response = self.client.get(
            reverse("automation-script-list-create"),
            {"test_case": str(self.test_case.id)},
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["results"]), 1)
        self.assertNotIn("validation", list_response.data["results"][0])

    def test_validate_endpoint_returns_script_validation_summary(self):
        script = AutomationScript.objects.create(**self._script_payload())

        response = self.client.post(
            reverse("automation-script-validate", kwargs={"pk": script.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_valid"])
        self.assertEqual(response.data["errors"], [])

    def test_create_execution_runs_and_returns_result_payload(self):
        script = AutomationScript.objects.create(**self._script_payload())

        response = self.client.post(
            reverse("test-execution-list-create"),
            {
                "test_case": str(self.test_case.id),
                "script": str(script.id),
                "browser": "chromium",
                "platform": "desktop",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution = TestExecution.objects.select_related("result").get(
            pk=response.data["id"],
        )
        self.assertEqual(execution.status, "passed")
        self.assertIsNotNone(execution.result)
        self.assertEqual(execution.result.total_steps, 2)
        self.assertEqual(execution.result.passed_steps, 2)

        filtered_response = self.client.get(
            reverse("test-execution-list-create"),
            {"project": str(self.project.id), "status": "passed"},
        )
        self.assertEqual(filtered_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(filtered_response.data["results"]), 1)

    def test_create_selenium_execution_runs_and_returns_result_payload(self):
        script = AutomationScript.objects.create(
            **self._script_payload(
                framework="selenium",
                script_content="print('selenium smoke')",
            )
        )

        response = self.client.post(
            reverse("test-execution-list-create"),
            {
                "test_case": str(self.test_case.id),
                "script": str(script.id),
                "browser": "chromium",
                "platform": "desktop",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        execution = TestExecution.objects.select_related("result").get(pk=response.data["id"])
        self.assertEqual(execution.status, "passed")
        self.assertIsNotNone(execution.result)
        self.assertEqual(execution.result.status, "passed")

    def test_pause_resume_and_stop_endpoints_update_execution_state(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.user,
            status="running",
            browser="chromium",
            platform="desktop",
        )

        pause_response = self.client.post(
            reverse("test-execution-pause", kwargs={"pk": execution.id}),
        )
        self.assertEqual(pause_response.status_code, status.HTTP_200_OK)
        execution.refresh_from_db()
        self.assertEqual(execution.status, "paused")

        resume_response = self.client.post(
            reverse("test-execution-resume", kwargs={"pk": execution.id}),
        )
        self.assertEqual(resume_response.status_code, status.HTTP_200_OK)
        execution.refresh_from_db()
        self.assertEqual(execution.status, "error")

        execution.status = "running"
        execution.pause_requested = False
        execution.save(update_fields=["status", "pause_requested"])
        stop_response = self.client.post(
            reverse("test-execution-stop", kwargs={"pk": execution.id}),
        )
        self.assertEqual(stop_response.status_code, status.HTTP_200_OK)
        execution.refresh_from_db()
        self.assertEqual(execution.status, "cancelled")

    def test_viewer_cannot_create_scripts_or_executions(self):
        self.client.force_authenticate(self.viewer)

        script_response = self.client.post(
            reverse("automation-script-list-create"),
            self._script_request_payload(),
            format="json",
        )
        self.assertEqual(script_response.status_code, status.HTTP_400_BAD_REQUEST)

        execution_response = self.client.post(
            reverse("test-execution-list-create"),
            {
                "test_case": str(self.test_case.id),
                "browser": "chromium",
                "platform": "desktop",
            },
            format="json",
        )
        self.assertEqual(execution_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_schedule_and_trigger_now(self):
        AutomationScript.objects.create(**self._script_payload())
        create_response = self.client.post(
            reverse("execution-schedule-list-create"),
            {
                "project": str(self.project.id),
                "suite": str(self.suite.id),
                "name": "Nightly Smoke",
                "cron_expression": "0 2 * * *",
                "timezone": "UTC",
                "browser": "chromium",
                "platform": "desktop",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        schedule = ExecutionSchedule.objects.get(pk=create_response.data["id"])
        self.assertIsNotNone(schedule.next_run_at)

        trigger_response = self.client.post(
            reverse("execution-schedule-trigger", kwargs={"pk": schedule.id}),
        )

        self.assertEqual(trigger_response.status_code, status.HTTP_201_CREATED)
        # Trigger now returns a TestRun object, not a list of executions.
        data = trigger_response.data
        self.assertIn("run_id", data)
        self.assertIn("run_case_count", data)
        self.assertEqual(data["trigger_type"], "scheduled")
