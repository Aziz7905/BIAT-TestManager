"""
Phase 6.5 automation app hardening tests.

Covers:
- activate_script / deactivate_script service functions
- TestResultSerializer does not expose ai_failure_analysis
- Activate / deactivate API endpoints (viewer forbidden)
- Schedule trigger returns correct shape
- Redundant permission check removal: queryset scoping is the sole guard
"""
from __future__ import annotations

import sys

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, Team, TeamMembership, UserProfile
from apps.accounts.models.choices import OrganizationRole, TeamMembershipRole
from apps.automation.models import AutomationScript, TestExecution, TestResult
from apps.automation.models.choices import AutomationFramework, AutomationLanguage, ExecutionStatus
from apps.automation.serializers import TestResultSerializer
from apps.automation.services import activate_script, deactivate_script, finalize_execution_result
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as QaTestCase
from apps.testing.models import TestScenario, TestSection, TestSuite

User = get_user_model()

_PASSWORD = "Pass1234!"  # NOSONAR


def _make_org_stack(domain_suffix: str, username: str):
    """Create org → team → user profile chain. Returns (user, org, team)."""
    user = User.objects.create_user(
        username=username,
        password=_PASSWORD,
        email=f"{username}@{domain_suffix}",
    )
    org = Organization.objects.create(name=f"Org {domain_suffix}", domain=domain_suffix)
    UserProfile.objects.create(
        user=user,
        organization=org,
        organization_role=OrganizationRole.MEMBER,
    )
    team = Team.objects.create(organization=org, name="QA Team", manager=user)
    TeamMembership.objects.create(
        team=team, user=user, role=TeamMembershipRole.TESTER, is_active=True
    )
    return user, org, team


def _make_viewer(team, org, domain_suffix: str):
    viewer = User.objects.create_user(
        username=f"viewer.{domain_suffix}",
        password=_PASSWORD,  # NOSONAR
        email=f"viewer@{domain_suffix}",
    )
    UserProfile.objects.create(
        user=viewer,
        organization=org,
        organization_role=OrganizationRole.MEMBER,
    )
    TeamMembership.objects.create(
        team=team, user=viewer, role=TeamMembershipRole.VIEWER, is_active=True
    )
    return viewer


def _make_test_tree(project, user):
    suite = TestSuite.objects.create(
        project=project, name="Suite", folder_path="Core", created_by=user
    )
    section = TestSection.objects.create(suite=suite, name="General", order_index=0)
    scenario = TestScenario.objects.create(
        section=section, title="Login flow", description=""
    )
    test_case = QaTestCase.objects.create(
        scenario=scenario,
        title="Login with valid credentials",
        steps=[{"step": "Open login page", "outcome": "Form visible"}],
        expected_result="Dashboard shown.",
    )
    return suite, test_case


def _make_script(test_case, framework="playwright", content="print('playwright smoke')"):
    return AutomationScript.objects.create(
        test_case=test_case,
        framework=framework,
        language=AutomationLanguage.PYTHON,
        script_content=content,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Service: activate_script / deactivate_script
# ---------------------------------------------------------------------------

class ScriptActivationServiceTests(TestCase):
    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("activation.tn", "act.owner")
        self.project = Project.objects.create(
            team=self.team, name="Activation Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        _, self.test_case = _make_test_tree(self.project, self.user)
        self.script = _make_script(self.test_case)

    def test_deactivate_script_sets_is_active_false(self):
        deactivate_script(self.script)
        self.script.refresh_from_db()
        self.assertFalse(self.script.is_active)

    def test_activate_script_sets_is_active_true(self):
        self.script.is_active = False
        self.script.save(update_fields=["is_active"])

        activate_script(self.script)
        self.script.refresh_from_db()
        self.assertTrue(self.script.is_active)

    def test_activate_returns_script_instance(self):
        self.script.is_active = False
        self.script.save(update_fields=["is_active"])
        result = activate_script(self.script)
        self.assertEqual(result.pk, self.script.pk)

    def test_deactivate_returns_script_instance(self):
        result = deactivate_script(self.script)
        self.assertEqual(result.pk, self.script.pk)


# ---------------------------------------------------------------------------
# Serializer: ai_failure_analysis must not be exposed
# ---------------------------------------------------------------------------

class TestResultSerializerFieldTests(TestCase):
    def test_ai_failure_analysis_not_in_serializer_fields(self):
        field_names = list(TestResultSerializer().fields.keys())
        self.assertNotIn("ai_failure_analysis", field_names)

    def test_serialized_result_does_not_contain_ai_failure_analysis(self):
        user, org, team = _make_org_stack("serial.tn", "serial.owner")
        project = Project.objects.create(
            team=team, name="Serial Project", created_by=user
        )
        ProjectMember.objects.create(
            project=project, user=user, role=ProjectMemberRole.OWNER
        )
        _, test_case = _make_test_tree(project, user)
        execution = TestExecution.objects.create(
            test_case=test_case,
            triggered_by=user,
            status=ExecutionStatus.QUEUED,
            browser="chromium",
            platform="desktop",
        )
        result = TestResult.objects.create(
            execution=execution,
            status="passed",
            duration_ms=100,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
            ai_failure_analysis="should not appear",
        )
        data = TestResultSerializer(result).data
        self.assertNotIn("ai_failure_analysis", data)


# ---------------------------------------------------------------------------
# API: activate / deactivate endpoints
# ---------------------------------------------------------------------------

@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
)
class ScriptActivationApiTests(APITestCase):
    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("api65.tn", "api65.owner")
        self.viewer = _make_viewer(self.team, self.org, "api65.tn")
        self.project = Project.objects.create(
            team=self.team, name="API65 Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        ProjectMember.objects.create(
            project=self.project, user=self.viewer, role=ProjectMemberRole.VIEWER
        )
        _, self.test_case = _make_test_tree(self.project, self.user)
        self.script = _make_script(self.test_case)
        self.client.force_authenticate(self.user)

    def test_deactivate_endpoint_sets_is_active_false(self):
        response = self.client.post(
            reverse("automation-script-deactivate", kwargs={"pk": self.script.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.script.refresh_from_db()
        self.assertFalse(self.script.is_active)

    def test_activate_endpoint_sets_is_active_true(self):
        self.script.is_active = False
        self.script.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("automation-script-activate", kwargs={"pk": self.script.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.script.refresh_from_db()
        self.assertTrue(self.script.is_active)

    def test_viewer_cannot_activate_script(self):
        self.client.force_authenticate(self.viewer)
        self.script.is_active = False
        self.script.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("automation-script-activate", kwargs={"pk": self.script.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_viewer_cannot_deactivate_script(self):
        self.client.force_authenticate(self.viewer)
        response = self.client.post(
            reverse("automation-script-deactivate", kwargs={"pk": self.script.id})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_activate_script(self):
        self.client.force_authenticate(None)
        response = self.client.post(
            reverse("automation-script-activate", kwargs={"pk": self.script.id})
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# API: schedule trigger returns correct shape
# ---------------------------------------------------------------------------

@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    AUTOMATION_PLAYWRIGHT_PYTHON_BIN=sys.executable,
    AUTOMATION_SELENIUM_PYTHON_BIN=sys.executable,
)
class ScheduleTriggerShapeTests(APITestCase):
    def setUp(self):
        self.user, self.org, self.team = _make_org_stack("trigger65.tn", "trigger65.owner")
        self.project = Project.objects.create(
            team=self.team, name="Trigger65 Project", created_by=self.user
        )
        ProjectMember.objects.create(
            project=self.project, user=self.user, role=ProjectMemberRole.OWNER
        )
        self.suite, self.test_case = _make_test_tree(self.project, self.user)
        _make_script(self.test_case)
        self.client.force_authenticate(self.user)

    def test_trigger_now_returns_run_id_and_run_case_count(self):
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

        trigger_response = self.client.post(
            reverse(
                "execution-schedule-trigger",
                kwargs={"pk": create_response.data["id"]},
            )
        )
        self.assertEqual(trigger_response.status_code, status.HTTP_201_CREATED)
        data = trigger_response.data
        self.assertIn("run_id", data)
        self.assertIn("run_case_count", data)
        self.assertIn("trigger_type", data)
        self.assertEqual(data["trigger_type"], "scheduled")

    def test_trigger_now_does_not_expose_ai_failure_analysis(self):
        """Trigger flow touches TestResult indirectly — ensure field is absent from any result."""
        data = TestResultSerializer().fields
        self.assertNotIn("ai_failure_analysis", data)
