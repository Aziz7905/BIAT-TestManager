"""Integration tests for committing an AI authoring trace as an AutomationScript.

Covers:
- happy path: passed trace becomes an active Selenium/Python AutomationScript
  with generated_by=AI, pinned to the latest revision of the test case
- prior active script for the same (case, framework, language) is deactivated
- a non-passed execution refuses to commit
- a non-AI-authoring execution refuses to commit
- permission denial for viewers
- API endpoint returns 201 with the new script payload
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status as http_status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.ai.workflows.authoring.commit_script import (
    commit_authoring_trace_as_selenium_script,
)
from apps.ai.workflows.authoring.service import AIAuthoringError
from apps.automation.models import AutomationScript, ExecutionStep, TestExecution
from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
    AutomationScriptGeneratedBy,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionTriggerType,
)
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.services import (
    create_test_case_with_revision,
    create_test_scenario,
    create_test_suite,
    get_or_create_default_section,
)

User = get_user_model()


def _make_user(username, organization, role=OrganizationRole.MEMBER):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@biat.tn",
        password="Pass1234!",
    )
    UserProfile.objects.create(
        user=user,
        organization=organization,
        organization_role=role,
    )
    return user


class AIAuthoringScriptCommitTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="BIAT Script Commit",
            domain="commit.biat.tn",
        )
        self.owner = _make_user("commit.owner", self.organization, OrganizationRole.ORG_ADMIN)
        self.viewer = _make_user("commit.viewer", self.organization)
        self.team = Team.objects.create(organization=self.organization, name="QA")
        self.project = Project.objects.create(
            team=self.team,
            name="OrangeHRM",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=self.project, user=self.owner, role=ProjectMemberRole.OWNER,
        )
        ProjectMember.objects.create(
            project=self.project, user=self.viewer, role=ProjectMemberRole.VIEWER,
        )
        suite = create_test_suite(self.project, name="Authentication", created_by=self.owner)
        section = get_or_create_default_section(suite)
        scenario = create_test_scenario(
            section, title="Login flow", description="login"
        )
        self.test_case = create_test_case_with_revision(
            scenario=scenario,
            title="Valid login",
            preconditions="On login page.",
            steps=[
                {
                    "step_index": 1,
                    "action": "Fill username",
                    "expected_outcome": "Filled.",
                }
            ],
            expected_result="Dashboard visible.",
            test_data={},
            automation_status="manual",
        )

    def _make_passed_execution(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            status=ExecutionStatus.PASSED,
            stream_enabled=True,
            selenium_session_id="selenoid-xyz",
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_index=1,
            action="navigate",
            target_element="https://orangehrm.example/auth/login",
            status=ExecutionStepStatus.PASSED,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_index=2,
            action="fill",
            target_element="1",
            selector_used="1",
            input_value="Admin",
            target_attrs={"tag": "input", "name": "username"},
            status=ExecutionStepStatus.PASSED,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_index=3,
            action="click",
            target_element="2",
            selector_used="2",
            target_attrs={"tag": "button", "data_testid": "login-submit"},
            status=ExecutionStepStatus.PASSED,
        )
        return execution

    # ------------------------------------------------------------------
    # Service-level
    # ------------------------------------------------------------------

    def test_commit_creates_active_selenium_python_ai_script(self):
        execution = self._make_passed_execution()

        script = commit_authoring_trace_as_selenium_script(
            execution=execution, user=self.owner
        )

        self.assertEqual(script.framework, AutomationFramework.SELENIUM)
        self.assertEqual(script.language, AutomationLanguage.PYTHON)
        self.assertEqual(script.generated_by, AutomationScriptGeneratedBy.AI)
        self.assertTrue(script.is_active)
        self.assertEqual(script.script_version, 1)
        self.assertIn("driver.get(", script.script_content)
        self.assertIn("By.NAME, 'username'", script.script_content)
        self.assertIn('[data-testid="login-submit"]', script.script_content)
        self.assertIsNotNone(script.test_case_revision_id)

    def test_commit_deactivates_prior_active_script_for_same_test_case(self):
        execution = self._make_passed_execution()
        prior = AutomationScript.objects.create(
            test_case=self.test_case,
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.PYTHON,
            script_content="# old",
            generated_by=AutomationScriptGeneratedBy.USER,
            is_active=True,
        )
        # Model auto-assigns script_version on save (Max + 1). Capture the
        # actual assigned version so the assertion isn't coupled to that.
        prior_version = prior.script_version

        script = commit_authoring_trace_as_selenium_script(
            execution=execution, user=self.owner
        )

        prior.refresh_from_db()
        self.assertFalse(prior.is_active)
        self.assertTrue(script.is_active)
        self.assertEqual(script.script_version, prior_version + 1)

    def test_commit_is_idempotent_for_same_trace(self):
        execution = self._make_passed_execution()

        first = commit_authoring_trace_as_selenium_script(
            execution=execution, user=self.owner
        )
        second = commit_authoring_trace_as_selenium_script(
            execution=execution, user=self.owner
        )

        self.assertEqual(second.id, first.id)
        self.assertEqual(
            AutomationScript.objects.filter(test_case=self.test_case).count(),
            1,
        )

    def test_commit_rejects_non_passed_execution(self):
        execution = self._make_passed_execution()
        execution.status = ExecutionStatus.FAILED
        execution.save(update_fields=["status"])

        with self.assertRaises(AIAuthoringError):
            commit_authoring_trace_as_selenium_script(
                execution=execution, user=self.owner
            )

    def test_commit_rejects_non_ai_authoring_execution(self):
        execution = self._make_passed_execution()
        execution.trigger_type = ExecutionTriggerType.MANUAL
        execution.save(update_fields=["trigger_type"])

        with self.assertRaises(AIAuthoringError):
            commit_authoring_trace_as_selenium_script(
                execution=execution, user=self.owner
            )

    def test_commit_rejects_when_no_passed_steps(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            status=ExecutionStatus.PASSED,
            stream_enabled=True,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_index=1,
            action="fill",
            status=ExecutionStepStatus.FAILED,
        )

        with self.assertRaises(AIAuthoringError):
            commit_authoring_trace_as_selenium_script(
                execution=execution, user=self.owner
            )

    def test_viewer_cannot_commit(self):
        execution = self._make_passed_execution()
        with self.assertRaises(AIAuthoringError):
            commit_authoring_trace_as_selenium_script(
                execution=execution, user=self.viewer
            )

    # ------------------------------------------------------------------
    # API endpoint
    # ------------------------------------------------------------------

    def test_api_returns_created_with_new_script(self):
        execution = self._make_passed_execution()
        client = APIClient()
        client.force_authenticate(self.owner)

        response = client.post(
            reverse("ai-authoring-script-save", kwargs={"execution_pk": execution.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        self.assertEqual(response.data["framework"], AutomationFramework.SELENIUM)
        self.assertEqual(response.data["language"], AutomationLanguage.PYTHON)
        self.assertEqual(response.data["generated_by"], AutomationScriptGeneratedBy.AI)
        self.assertTrue(response.data["is_active"])

    def test_api_rejects_viewer_with_validation_error(self):
        execution = self._make_passed_execution()
        client = APIClient()
        client.force_authenticate(self.viewer)

        response = client.post(
            reverse("ai-authoring-script-save", kwargs={"execution_pk": execution.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
