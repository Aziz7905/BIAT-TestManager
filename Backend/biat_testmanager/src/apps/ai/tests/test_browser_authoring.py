from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.ai.providers.base import ChatResponse
from apps.ai.workflows.authoring.browser_tools import (
    PlaywrightMCPBrowserAuthoringTool,
    build_browser_authoring_tool,
)
from apps.ai.workflows.authoring.service import (
    run_browser_authoring_session,
    start_browser_authoring_session,
)
from apps.automation.models import ExecutionStep, TestExecution
from apps.automation.models.choices import ExecutionStatus
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as RepositoryTestCase
from apps.testing.services import (
    create_test_case_with_revision,
    create_test_scenario,
    create_test_suite,
    get_or_create_default_section,
)

User = get_user_model()


class FakeProvider:
    name = "groq"
    model_name = "llama-3.3-70b-versatile"

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    def chat(self, messages, **opts):
        self.calls.append({"messages": messages, "opts": opts})
        return ChatResponse(
            content=json.dumps(self.decisions.pop(0)),
            input_tokens=10,
            output_tokens=8,
            finish_reason="stop",
            raw={},
        )


class FakeBrowserTool:
    def __init__(self):
        self.started = False
        self.closed = False
        self.executed = []

    def start(self):
        self.started = True

    def observe(self):
        return {
            "current_url": "https://orangehrm.example/auth/login",
            "page_title": "OrangeHRM",
            "visible_text_summary": "Username Password Login Dashboard",
            "interactive_elements": [
                {
                    "id": "el_1",
                    "role": "textbox",
                    "name": "Username",
                    "selector": "input[name='username']",
                }
            ],
        }

    def execute(self, action, observation):
        self.executed.append(action)
        if action["action"] == "navigate":
            return {"status": "passed", "target": action["url"]}
        return {
            "status": "passed",
            "target": action.get("selector") or action.get("element_id") or "",
        }

    def get_stream_session_id(self):
        return "fake-authoring-session"

    def close(self):
        self.closed = True


class FakeMCPClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        self.calls = []
        self.tool_schemas = {
            "browser_snapshot": {},
            "browser_navigate": {"properties": {"url": {"type": "string"}}},
            "browser_type": {"properties": {"ref": {}, "text": {}}},
            "browser_click": {"properties": {"ref": {}, "element": {}}},
            "browser_close": {},
        }

    def start(self):
        self.started = True

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments or {}))
        if name == "browser_snapshot":
            return {
                "content": [
                    {
                        "text": "\n".join(
                            [
                                "Page URL: https://orangehrm.example/auth/login",
                                "Page Title: OrangeHRM",
                                '- textbox "Username" [ref=e1]',
                                '- textbox "Password" [ref=e2]',
                                '- button "Login" [ref=e3]',
                            ]
                        )
                    }
                ]
            }
        return {"content": [{"text": f"{name} ok"}]}

    def close(self):
        self.closed = True


def make_user(username, organization, role=OrganizationRole.MEMBER):
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


class AIBrowserAuthoringTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name="BIAT Authoring",
            domain="authoring.biat.tn",
        )
        self.owner = make_user("author.owner", self.organization, OrganizationRole.ORG_ADMIN)
        self.viewer = make_user("author.viewer", self.organization)
        self.team = Team.objects.create(organization=self.organization, name="AI QA")
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
        ProjectMember.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMemberRole.VIEWER,
        )
        suite = create_test_suite(self.project, name="Authentication", created_by=self.owner)
        section = get_or_create_default_section(suite)
        scenario = create_test_scenario(
            section,
            title="Valid login",
            description="Author a login flow.",
        )
        self.test_case = create_test_case_with_revision(
            scenario=scenario,
            title="Login with valid credentials",
            preconditions="User is on the OrangeHRM login page.",
            steps=[
                {
                    "step_index": 1,
                    "action": "Fill Username with Admin",
                    "expected_outcome": "Username is entered.",
                }
            ],
            expected_result="Dashboard is displayed.",
            test_data={"username": "Admin", "password": "admin123"},
            automation_status="manual",
        )

    def test_start_authoring_session_creates_trace_execution(self):
        fake_provider = FakeProvider([])

        with patch(
            "apps.ai.workflows.authoring.service.get_team_brain",
            return_value=fake_provider,
        ), patch(
            "apps.ai.tasks.enqueue_authoring_session_task",
            return_value="task-author-1",
        ):
            execution = start_browser_authoring_session(
                user=self.owner,
                test_case=self.test_case,
                target_url="https://orangehrm.example/auth/login",
            )

        self.assertEqual(execution.status, ExecutionStatus.QUEUED)
        self.assertTrue(execution.stream_enabled)
        self.assertEqual(execution.celery_task_id, "task-author-1")
        self.assertEqual(execution.script_id, None)

    def test_authoring_loop_records_browser_trace_steps(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.QUEUED,
            stream_enabled=True,
        )
        fake_tool = FakeBrowserTool()
        fake_provider = FakeProvider(
            [
                {
                    "action": "fill",
                    "element_id": "el_1",
                    "value": "Admin",
                    "reason": "Username field is visible.",
                },
                {
                    "action": "stop",
                    "success": True,
                    "reason": "The dashboard assertion is satisfied.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=4,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        self.assertTrue(fake_tool.started)
        self.assertTrue(fake_tool.closed)
        steps = list(ExecutionStep.objects.filter(execution=execution).order_by("step_index"))
        self.assertEqual([step.action for step in steps], ["navigate", "fill"])
        self.assertEqual(steps[1].input_value, "Admin")
        self.assertEqual(steps[1].status, "passed")

    def test_default_authoring_tool_is_playwright_mcp(self):
        tool = build_browser_authoring_tool("chromium")

        self.assertIsInstance(tool, PlaywrightMCPBrowserAuthoringTool)

    def test_playwright_mcp_tool_uses_snapshot_refs_for_actions(self):
        fake_client = FakeMCPClient()
        tool = PlaywrightMCPBrowserAuthoringTool(
            browser="chromium",
            command="npx",
            args=["@playwright/mcp@latest", "--headless"],
            client_factory=lambda **kwargs: fake_client,
        )

        tool.start()
        observation = tool.observe()
        tool.execute(
            {
                "action": "fill",
                "element_ref": "e1",
                "value": "Admin",
                "reason": "Username textbox is visible.",
            },
            observation,
        )
        tool.execute(
            {
                "action": "click",
                "element_id": "Login",
                "reason": "Submit the login form.",
            },
            observation,
        )
        tool.close()

        self.assertTrue(fake_client.started)
        self.assertTrue(fake_client.closed)
        self.assertIn(("browser_type", {"ref": "e1", "text": "Admin"}), fake_client.calls)
        self.assertIn(("browser_click", {"ref": "e3", "element": "Submit the login form."}), fake_client.calls)

    def test_authoring_start_api_rejects_viewer(self):
        client = APIClient()
        client.force_authenticate(self.viewer)

        response = client.post(
            reverse("ai-authoring-session-start"),
            {
                "test_case": str(self.test_case.id),
                "target_url": "https://orangehrm.example/auth/login",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authoring_start_api_returns_execution_for_owner(self):
        client = APIClient()
        client.force_authenticate(self.owner)

        with patch(
            "apps.ai.workflows.authoring.service.get_team_brain",
            return_value=FakeProvider([]),
        ), patch(
            "apps.ai.tasks.enqueue_authoring_session_task",
            return_value="task-author-1",
        ):
            response = client.post(
                reverse("ai-authoring-session-start"),
                {
                    "test_case": str(self.test_case.id),
                    "target_url": "https://orangehrm.example/auth/login",
                    "max_steps": 4,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["test_case"], self.test_case.id)
        self.assertTrue(response.data["stream_enabled"])
        self.assertIsNone(response.data["script"])

    def test_save_authoring_trace_updates_case_draft_steps(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.PASSED,
            stream_enabled=True,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_index=1,
            action="navigate",
            target_element="https://orangehrm.example/auth/login",
            status="passed",
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_index=2,
            action="fill",
            target_element="e1",
            selector_used="e1",
            input_value="Admin",
            status="passed",
        )
        client = APIClient()
        client.force_authenticate(self.owner)

        response = client.post(
            reverse("ai-authoring-trace-save", kwargs={"execution_pk": execution.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.test_case.refresh_from_db()
        self.assertEqual(response.data["step_count"], 2)
        self.assertEqual(self.test_case.version, 2)
        self.assertEqual(self.test_case.steps[1]["step"], "Fill e1 with Admin.")
