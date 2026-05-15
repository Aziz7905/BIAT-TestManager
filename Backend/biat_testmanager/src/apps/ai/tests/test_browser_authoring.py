from __future__ import annotations

import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.ai.providers.base import ChatResponse
from apps.ai.workflows.authoring.browser_tools import (
    AuthoringBrowserCapabilities,
    SelenoidWebDriverAuthoringTool,
    build_browser_authoring_tool,
)
from apps.ai.workflows.authoring.service import (
    run_browser_authoring_session,
    start_browser_authoring_session,
)
from apps.automation.models import AutomationScript, ExecutionStep, TestExecution
from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
    AutomationScriptGeneratedBy,
    ExecutionStatus,
    ExecutionTriggerType,
)
from apps.projects.models import Project, ProjectMember, ProjectMemberRole
from apps.testing.models import TestCase as RepositoryTestCase  # noqa: F401
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
    """In-process tool for run-loop tests; satisfies BrowserAuthoringTool Protocol."""

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
                    "id": "1",
                    "ref": "1",
                    "role": "textbox",
                    "name": "Username",
                    "line": '- textbox "Username" [ref=1]',
                }
            ],
        }

    def execute(self, action, observation):
        self.executed.append(action)
        if action["action"] == "navigate":
            return {"status": "passed", "target": action["url"]}
        return {
            "status": "passed",
            "target": action.get("ref") or action.get("element_ref") or "",
        }

    def get_stream_session_id(self):
        return "fake-authoring-session"

    def close(self):
        self.closed = True


class FakeWebElement:
    """Minimal stand-in for selenium.webdriver.remote.webelement.WebElement."""

    def __init__(self, ref):
        self.ref = ref
        self.cleared = False
        self.clicked = False
        self.sent = []

    def click(self):
        self.clicked = True

    def clear(self):
        self.cleared = True

    def send_keys(self, value):
        self.sent.append(value)

    def is_displayed(self):
        return True


class FakeWebDriver:
    """In-process driver double for SelenoidWebDriverAuthoringTool tests.

    Records every find_element call and serves a fixed observation payload
    from execute_script so we can assert the CSS-selector pattern the agent
    uses for refs.
    """

    session_id = "selenoid-fake-session"
    current_url = "https://orangehrm.example/auth/login"
    page_source = "<html><body>Dashboard</body></html>"

    def __init__(self, *, command_executor=None, options=None):
        self.command_executor = command_executor
        self.options = options
        self.find_element_calls = []
        self.gets = []
        self.scripts = []
        self.quit_called = False
        self._elements = {}

    def execute_script(self, script, *args):
        self.scripts.append(script)
        return {
            "current_url": self.current_url,
            "page_title": "OrangeHRM",
            "snapshot": "Page URL: ...\n- textbox \"Username\" [ref=1]\n- button \"Login\" [ref=2]",
            "visible_text_summary": "Username Password Login",
            "interactive_elements": [
                {"id": "1", "ref": "1", "role": "textbox", "name": "Username", "line": ""},
                {"id": "2", "ref": "2", "role": "button", "name": "Login", "line": ""},
            ],
        }

    def find_element(self, by, value):
        self.find_element_calls.append((by, value))
        ref = value.split('"')[1] if '"' in value else value
        if ref not in self._elements:
            self._elements[ref] = FakeWebElement(ref)
        return self._elements[ref]

    def get(self, url):
        self.gets.append(url)

    def quit(self):
        self.quit_called = True

    def set_page_load_timeout(self, seconds):
        pass


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
        ) as mock_enqueue:
            execution = start_browser_authoring_session(
                user=self.owner,
                test_case=self.test_case,
                target_url="https://orangehrm.example/auth/login",
            )

        self.assertEqual(execution.status, ExecutionStatus.QUEUED)
        self.assertTrue(execution.stream_enabled)
        self.assertEqual(execution.celery_task_id, "task-author-1")
        self.assertEqual(execution.script_id, None)
        self.assertEqual(
            mock_enqueue.call_args.kwargs["max_steps"],
            settings.AI_AUTHORING_DEFAULT_MAX_STEPS,
        )
        self.assertEqual(
            mock_enqueue.call_args.kwargs["temperature"],
            settings.AI_AUTHORING_DEFAULT_TEMPERATURE,
        )
        self.assertEqual(
            mock_enqueue.call_args.kwargs["max_tokens_per_step"],
            settings.AI_AUTHORING_DEFAULT_MAX_TOKENS_PER_STEP,
        )

    def test_start_authoring_session_passes_authoring_parameters_to_task(self):
        with patch(
            "apps.ai.workflows.authoring.service.get_team_brain",
            return_value=FakeProvider([]),
        ), patch(
            "apps.ai.tasks.enqueue_authoring_session_task",
            return_value="task-author-1",
        ) as mock_enqueue:
            start_browser_authoring_session(
                user=self.owner,
                test_case=self.test_case,
                target_url="https://orangehrm.example/auth/login",
                max_steps=25,
                temperature=0.3,
                max_tokens_per_step=1200,
            )

        self.assertEqual(mock_enqueue.call_args.kwargs["max_steps"], 25)
        self.assertEqual(mock_enqueue.call_args.kwargs["temperature"], 0.3)
        self.assertEqual(mock_enqueue.call_args.kwargs["max_tokens_per_step"], 1200)

    def test_authoring_uses_ai_authoring_trigger_type(self):
        """AI authoring discriminator: the trigger_type must be AI_AUTHORING so the
        frontend can switch the live page into AI-authoring-only controls without
        affecting regression or manual execution surfaces."""
        with patch(
            "apps.ai.workflows.authoring.service.get_team_brain",
            return_value=FakeProvider([]),
        ), patch(
            "apps.ai.tasks.enqueue_authoring_session_task",
            return_value="task-author-1",
        ):
            execution = start_browser_authoring_session(
                user=self.owner,
                test_case=self.test_case,
                target_url="https://orangehrm.example/auth/login",
            )
        self.assertEqual(execution.trigger_type, ExecutionTriggerType.AI_AUTHORING)

    def test_authoring_loop_records_browser_trace_steps(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.QUEUED,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            stream_enabled=True,
        )
        fake_tool = FakeBrowserTool()
        fake_provider = FakeProvider(
            [
                {
                    "action": "fill",
                    "element_ref": "1",
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
            temperature=0.4,
            max_tokens_per_step=777,
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
        self.assertEqual(fake_provider.calls[0]["opts"]["temperature"], 0.4)
        self.assertEqual(fake_provider.calls[0]["opts"]["max_tokens"], 777)
        script = AutomationScript.objects.get(test_case=self.test_case)
        self.assertEqual(script.framework, AutomationFramework.SELENIUM)
        self.assertEqual(script.language, AutomationLanguage.PYTHON)
        self.assertEqual(script.generated_by, AutomationScriptGeneratedBy.AI)
        self.assertTrue(script.is_active)

    def test_default_authoring_tool_is_selenoid_webdriver(self):
        tool = build_browser_authoring_tool("chrome")

        self.assertIsInstance(tool, SelenoidWebDriverAuthoringTool)
        self.assertEqual(tool.capabilities.browser_name, "chrome")
        self.assertTrue(tool.capabilities.enable_vnc)
        self.assertFalse(tool.capabilities.enable_video)
        self.assertEqual(tool.capabilities.session_timeout, "10m")

    def test_capabilities_pass_through_to_selenoid_options(self):
        """Backend is capability-based; selenoid:options carries the live-viewer
        knobs (enableVNC, sessionTimeout, enableVideo)."""
        caps = AuthoringBrowserCapabilities(
            browser_name="chrome",
            browser_version="120",
            enable_vnc=True,
            enable_video=False,
            session_timeout="15m",
        )
        options = caps.to_options()
        capabilities = options.to_capabilities()
        self.assertEqual(capabilities.get("browserName"), "chrome")
        self.assertEqual(capabilities.get("browserVersion"), "120")
        selenoid_options = capabilities.get("selenoid:options") or {}
        self.assertTrue(selenoid_options.get("enableVNC"))
        self.assertFalse(selenoid_options.get("enableVideo"))
        self.assertEqual(selenoid_options.get("sessionTimeout"), "15m")

    def test_resolver_falls_back_when_agent_sends_css_selector(self):
        """If the LLM forgets the bare ref and sends ``input[name='username']``
        instead, the resolver should still find the matching element by
        substring-matching the extracted hint against the observation."""
        from apps.ai.workflows.authoring.browser_tools import _resolve_element_ref

        observation = {
            "interactive_elements": [
                {
                    "id": "1",
                    "ref": "1",
                    "role": "textbox",
                    "name": "username",
                    "line": '- textbox "username" [ref=1]',
                },
                {
                    "id": "2",
                    "ref": "2",
                    "role": "button",
                    "name": "Login",
                    "line": '- button "Login" [ref=2]',
                },
            ]
        }
        # Agent slips and sends a CSS selector — resolver still finds ref "1".
        ref = _resolve_element_ref(
            {"action": "fill", "selector": "input[name='username']"},
            observation,
        )
        self.assertEqual(ref, "1")

        # Agent sends an id-style selector — should still resolve to ref "2".
        ref = _resolve_element_ref(
            {"action": "click", "selector": "#Login"},
            observation,
        )
        self.assertEqual(ref, "2")

    def test_selenoid_webdriver_tool_uses_dom_refs_for_actions(self):
        """The action layer must address elements via [data-biat-ref="<ref>"]
        from the DOM walker, never via invented CSS selectors."""
        fake_driver = FakeWebDriver()
        caps = AuthoringBrowserCapabilities(browser_name="chrome")
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=caps,
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        observation = tool.observe()
        tool.execute(
            {
                "action": "fill",
                "element_ref": "1",
                "value": "Admin",
                "reason": "Username textbox is visible.",
            },
            observation,
        )
        tool.execute(
            {
                "action": "click",
                "element_ref": "2",
                "reason": "Submit the login form.",
            },
            observation,
        )

        # find_element receives the BIAT ref selector for both actions.
        selectors = [value for _, value in fake_driver.find_element_calls]
        self.assertIn('[data-biat-ref="1"]', selectors)
        self.assertIn('[data-biat-ref="2"]', selectors)

        # Stream session id resolves to the real driver session.
        self.assertEqual(tool.get_stream_session_id(), fake_driver.session_id)

        tool.close()
        self.assertTrue(fake_driver.quit_called)

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
        ) as mock_enqueue:
            response = client.post(
                reverse("ai-authoring-session-start"),
                {
                    "test_case": str(self.test_case.id),
                    "target_url": "https://orangehrm.example/auth/login",
                    "max_steps": 50,
                    "temperature": 0.2,
                    "max_tokens_per_step": 900,
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["test_case"], self.test_case.id)
        self.assertTrue(response.data["stream_enabled"])
        self.assertIsNone(response.data["script"])
        self.assertEqual(mock_enqueue.call_args.kwargs["max_steps"], 50)
        self.assertEqual(mock_enqueue.call_args.kwargs["temperature"], 0.2)
        self.assertEqual(mock_enqueue.call_args.kwargs["max_tokens_per_step"], 900)

    def test_authoring_start_api_validates_authoring_parameter_bounds(self):
        client = APIClient()
        client.force_authenticate(self.owner)

        response = client.post(
            reverse("ai-authoring-session-start"),
            {
                "test_case": str(self.test_case.id),
                "target_url": "https://orangehrm.example/auth/login",
                "max_steps": settings.AI_AUTHORING_MAX_STEPS_LIMIT + 1,
                "temperature": 1.1,
                "max_tokens_per_step": settings.AI_AUTHORING_MAX_TOKENS_PER_STEP_LIMIT + 1,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_steps", response.data)
        self.assertIn("temperature", response.data)
        self.assertIn("max_tokens_per_step", response.data)

    def test_save_authoring_trace_updates_case_draft_steps(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.PASSED,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
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
            target_element="1",
            selector_used="1",
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
        self.assertEqual(self.test_case.steps[1]["step"], "Fill 1 with Admin.")
