"""AI authoring lives on the ai_agent queue. Regression dispatch must never
touch an AI_AUTHORING execution.

These tests guard the queue boundary at the service layer:

- ``run_execution`` (the regression task's body) must early-return for
  AI_AUTHORING executions without overwriting status or result.
- ``request_execution_resume`` must NOT enqueue the regression task for
  AI_AUTHORING executions; the ai_agent worker's polling loop picks up
  ``pause_requested = False`` and resumes in-process.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.automation.models import TestExecution
from apps.automation.models.choices import ExecutionStatus, ExecutionTriggerType
from apps.automation.services.execution_runner import (
    request_execution_resume,
    run_execution,
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


class AIAuthoringQueueIsolationTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="BIAT Queue",
            domain="queue.biat.tn",
        )
        self.owner = _make_user("queue.owner", self.organization, OrganizationRole.ORG_ADMIN)
        self.team = Team.objects.create(organization=self.organization, name="QA")
        self.project = Project.objects.create(
            team=self.team,
            name="OrangeHRM",
            created_by=self.owner,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMemberRole.OWNER,
        )
        suite = create_test_suite(self.project, name="Auth", created_by=self.owner)
        section = get_or_create_default_section(suite)
        scenario = create_test_scenario(
            section, title="Login", description="login scenario"
        )
        self.test_case = create_test_case_with_revision(
            scenario=scenario,
            title="Valid login",
            preconditions="...",
            steps=[
                {
                    "step_index": 1,
                    "action": "Open login page",
                    "expected_outcome": "Login form visible",
                }
            ],
            expected_result="Dashboard visible",
            test_data={},
            automation_status="manual",
        )

    def _make_authoring_execution(self, status=ExecutionStatus.PAUSED, pause_requested=False):
        return TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            status=status,
            pause_requested=pause_requested,
            stream_enabled=True,
            selenium_session_id="selenoid-abc",
        )

    def test_run_execution_skips_ai_authoring_without_touching_status(self):
        """A stray automation.run_test_execution dispatch must NOT overwrite
        the AI authoring execution's status with regression-style errors."""
        execution = self._make_authoring_execution(status=ExecutionStatus.RUNNING)

        with patch(
            "apps.automation.services.execution_runner.finalize_execution_result"
        ) as mock_finalize:
            returned = run_execution(str(execution.id))

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)
        self.assertEqual(execution.selenium_session_id, "selenoid-abc")
        self.assertEqual(returned.id, execution.id)
        mock_finalize.assert_not_called()

    def test_resume_does_not_queue_regression_task_for_ai_authoring(self):
        """Resume on an AI authoring execution clears pause_requested in-place;
        it must NOT call queue_execution which would route to the regression
        worker."""
        execution = self._make_authoring_execution(
            status=ExecutionStatus.PAUSED,
            pause_requested=True,
        )

        with patch(
            "apps.automation.services.execution_runner.queue_execution"
        ) as mock_queue:
            request_execution_resume(execution)

        mock_queue.assert_not_called()
        execution.refresh_from_db()
        self.assertFalse(execution.pause_requested)

    def test_resume_still_queues_regression_task_for_non_ai_executions(self):
        """Sanity check: the resume guard is AI-authoring-specific and does
        not regress regression resume behavior."""
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            trigger_type=ExecutionTriggerType.MANUAL,
            status=ExecutionStatus.PAUSED,
            pause_requested=True,
            stream_enabled=True,
        )

        with patch(
            "apps.automation.services.execution_runner.queue_execution"
        ) as mock_queue:
            request_execution_resume(execution)

        mock_queue.assert_called_once()
