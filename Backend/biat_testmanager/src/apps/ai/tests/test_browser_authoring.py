from __future__ import annotations

import json
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from selenium.common.exceptions import TimeoutException, WebDriverException

from apps.accounts.models import Organization, Team, UserProfile
from apps.accounts.models.choices import OrganizationRole
from apps.ai.providers.base import ChatResponse, parse_json_content
from apps.ai.workflows.authoring.browser_tools import (
    AuthoringBrowserCapabilities,
    SelenoidWebDriverAuthoringTool,
    build_browser_authoring_tool,
)
from apps.ai.workflows.authoring.prompts import (
    BROWSER_AUTHORING_PROMPT_VERSION,
    build_browser_next_action_messages,
)
from apps.ai.workflows.authoring.schemas import (
    ALLOWED_BROWSER_TOOLS,
    BROWSER_ACTION_SCHEMA,
)
from apps.ai.workflows.authoring.service import (
    run_browser_authoring_session,
    start_browser_authoring_session,
)
from apps.ai.workflows.authoring.success import evaluate_success
from apps.automation.models import AutomationScript, ExecutionStep, TestExecution
from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
    AutomationScriptGeneratedBy,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionTriggerType,
)
from apps.automation.serializers import ExecutionStepSerializer
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
        payload = self.decisions.pop(0)
        return ChatResponse(
            content=payload if isinstance(payload, str) else json.dumps(payload),
            input_tokens=10,
            output_tokens=8,
            finish_reason="stop",
            raw={},
        )

    def chat_json(self, messages, schema, **opts):
        self.calls.append({"messages": messages, "schema": schema, "opts": opts})
        payload = self.decisions.pop(0)
        return parse_json_content(payload if isinstance(payload, str) else json.dumps(payload))


class FakeBrowserTool:
    """In-process tool for run-loop tests; satisfies BrowserAuthoringTool Protocol."""

    def __init__(self):
        self.started = False
        self.closed = False
        self.executed = []
        self.logged_in = False
        self.captcha = False

    def start(self):
        self.started = True

    def observe(self):
        if self.captcha:
            return {
                "current_url": "https://example.test/security",
                "page_title": "Security check",
                "visible_text_summary": "Please complete the CAPTCHA to continue.",
                "snapshot": "Page Title: Security check\nPlease complete the CAPTCHA to continue.",
                "interactive_elements": [],
            }
        if self.logged_in:
            return {
                "current_url": "https://orangehrm.example/web/index.php/dashboard/index",
                "page_title": "OrangeHRM",
                "visible_text_summary": "Dashboard Time at Work Quick Launch",
                "snapshot": "Page URL: https://orangehrm.example/web/index.php/dashboard/index\n- heading \"Dashboard\"",
                "interactive_elements": [],
            }
        return {
            "current_url": "https://orangehrm.example/auth/login",
            "page_title": "OrangeHRM",
            "visible_text_summary": "Username Password Login",
            "snapshot": "Page URL: https://orangehrm.example/auth/login\n- textbox \"Username\" [ref=1]\n- textbox \"Password\" [ref=2]\n- button \"Login\" [ref=3]",
            "interactive_elements": [
                {
                    "id": "1",
                    "ref": "1",
                    "role": "textbox",
                    "name": "Username",
                    "line": '- textbox "Username" [ref=1]',
                    "target_attrs": {"tag": "input", "name": "username"},
                },
                {
                    "id": "2",
                    "ref": "2",
                    "role": "textbox",
                    "name": "Password",
                    "line": '- textbox "Password" [ref=2]',
                    "target_attrs": {"tag": "input", "type": "password", "name": "password"},
                },
                {
                    "id": "3",
                    "ref": "3",
                    "role": "button",
                    "name": "Login",
                    "line": '- button "Login" [ref=3]',
                    "target_attrs": {"tag": "button", "text": "Login"},
                }
            ],
        }

    def execute(self, action, observation):
        self.executed.append(action)
        tool = action.get("tool")
        if tool == "browser_navigate":
            return {"status": "passed", "action": "navigate", "target": action["url"]}
        if tool == "browser_fill_form":
            results = []
            for field in action["fields"]:
                target_attrs = (
                    {"tag": "input", "name": "username"}
                    if field["target"] == "1"
                    else {"tag": "input", "type": "password", "name": "password"}
                )
                results.append(
                    {
                        "status": "passed",
                        "action": "fill",
                        "target": field["target"],
                        "field": field,
                        "target_attrs": target_attrs,
                    }
                )
            return {
                "status": "passed",
                "action": "fill_form",
                "target": "form",
                "field_results": results,
            }
        if tool == "browser_click":
            self.logged_in = True
            return {
                "status": "passed",
                "action": "click",
                "target": action.get("target") or "",
                "target_attrs": {"tag": "button", "text": "Login"},
            }
        return {
            "status": "passed",
            "action": "fill",
            "target": action.get("target") or "",
            "target_attrs": {"tag": "input", "name": "username"},
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
        self.attributes = {"value": "", "type": "text"}

    def click(self):
        self.clicked = True

    def clear(self):
        self.cleared = True
        self.attributes["value"] = ""

    def send_keys(self, value):
        self.sent.append(value)
        self.attributes["value"] = f"{self.attributes.get('value', '')}{value}"

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def get_attribute(self, name):
        return self.attributes.get(name, "")


class FakeWebDriver:
    """In-process driver double for SelenoidWebDriverAuthoringTool tests.

    Records every find_element call and serves a fixed observation payload
    from execute_script so we can assert the CSS-selector pattern the agent
    uses for refs.
    """

    session_id = "selenoid-fake-session"
    current_url = "https://orangehrm.example/auth/login"
    title = "OrangeHRM"
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
        if args and not isinstance(args[0], str):
            return None
        if args and isinstance(args[0], str):
            ref = args[0]
            if ref == "1":
                return {"tag": "input", "name": "username", "type": "text"}
            if ref == "2":
                return {"tag": "button", "text": "Login"}
            if ref == "3":
                return {"tag": "input", "name": "password", "type": "password"}
            return {}
        return {
            "current_url": self.current_url,
            "page_title": "OrangeHRM",
            "snapshot": "Page URL: ...\n- textbox \"Username\" value=\"\" [ref=1]\n- button \"Login\" [ref=2]",
            "visible_text_summary": "Username Password Login",
            "interactive_elements": [
                {
                    "id": "1",
                    "ref": "1",
                    "role": "textbox",
                    "name": "Username",
                    "value": "",
                    "disabled": False,
                    "checked": False,
                    "selected": False,
                    "readonly": False,
                    "placeholder": "Username",
                    "target_attrs": {"tag": "input", "name": "username"},
                    "line": "",
                },
                {
                    "id": "2",
                    "ref": "2",
                    "role": "button",
                    "name": "Login",
                    "value": "",
                    "disabled": False,
                    "checked": False,
                    "selected": False,
                    "readonly": False,
                    "placeholder": "",
                    "target_attrs": {"tag": "button", "text": "Login"},
                    "line": "",
                },
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

    def set_script_timeout(self, seconds):
        pass

    def get_log(self, kind):
        return [{"level": "INFO", "message": "ready"}]

    def get_screenshot_as_base64(self):
        return "ZmFrZQ=="


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


@override_settings(AI_AUTHORING_TYPE_DELAY_MS=0, AI_AUTHORING_VISUAL_ACTION_DELAY_MS=0)
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

    def test_browser_action_v2_schema_exposes_explicit_tools(self):
        self.assertIn("oneOf", BROWSER_ACTION_SCHEMA)
        self.assertIn("browser_fill_form", ALLOWED_BROWSER_TOOLS)
        self.assertIn("browser_finish", ALLOWED_BROWSER_TOOLS)
        self.assertIn("browser_detect_blocker", ALLOWED_BROWSER_TOOLS)
        self.assertNotIn("browser_snapshot", ALLOWED_BROWSER_TOOLS)
        self.assertNotIn("stop", ALLOWED_BROWSER_TOOLS)
        fill_form_schema = next(
            item
            for item in BROWSER_ACTION_SCHEMA["oneOf"]
            if item["properties"]["tool"]["enum"] == ["browser_fill_form"]
        )
        verify_text_schema = next(
            item
            for item in BROWSER_ACTION_SCHEMA["oneOf"]
            if item["properties"]["tool"]["enum"] == ["browser_verify_text_visible"]
        )
        self.assertIn("fields", fill_form_schema["required"])
        self.assertIn("text", verify_text_schema["required"])

    def test_browser_authoring_v2_prompt_guides_tool_use_and_blockers(self):
        messages = build_browser_next_action_messages(
            goal={"title": "Login", "expected_result": "Dashboard is displayed."},
            observation={"interactive_elements": []},
            trace=[],
            max_steps=5,
        )
        system_prompt = messages[0]["content"]
        self.assertEqual(BROWSER_AUTHORING_PROMPT_VERSION, "browser_authoring_v2")
        self.assertIn("browser_fill_form", system_prompt)
        self.assertIn("CAPTCHA", system_prompt)
        self.assertIn("browser_finish", system_prompt)
        self.assertIn("success_evidence", system_prompt)

    def test_browser_authoring_prompt_guides_next_action_after_completed_fill(self):
        observation = FakeBrowserTool().observe()
        trace = [
            {
                "tool": "browser_fill_form",
                "action": "fill_form",
                "status": "passed",
                "fields": [
                    {"target": "1", "element": "Username", "value": "Admin"},
                    {"target": "2", "element": "Password", "value": "admin123"},
                ],
            }
        ]

        messages = build_browser_next_action_messages(
            goal={"title": "Login", "expected_result": "Dashboard is displayed."},
            observation=observation,
            trace=trace,
            max_steps=5,
        )
        context = json.loads(messages[-1]["content"])

        guidance = context["state_guidance"]
        self.assertEqual(guidance["do_not_repeat_targets"], ["1", "2"])
        self.assertEqual(guidance["submit_candidates"][0]["target"], "3")
        self.assertIn("browser_click", guidance["recommended_next_tools"])
        self.assertEqual(guidance["completed_fills"][1]["value"], "********")

    def test_browser_authoring_prompt_surfaces_visible_text_facts(self):
        messages = build_browser_next_action_messages(
            goal={
                "title": "Read credentials from the page and log in",
                "expected_result": "Dashboard is displayed.",
            },
            observation={
                "current_url": "https://example.test/login",
                "page_title": "Login",
                "visible_text_summary": "Username : Admin Password : admin123",
                "snapshot": '- textbox "Username" [ref=1]\n- textbox "Password" [ref=2]',
                "interactive_elements": [],
            },
            trace=[],
            max_steps=5,
        )
        context = json.loads(messages[-1]["content"])

        self.assertIn(
            {"label": "Username", "value": "Admin"},
            context["observation"]["text_facts"],
        )
        self.assertIn(
            {"label": "Password", "value": "admin123"},
            context["observation"]["text_facts"],
        )

    def test_browser_authoring_prompt_marks_post_login_objective_as_remaining_work(self):
        messages = build_browser_next_action_messages(
            goal={
                "title": "Read the credentials, login, then navigate to the admin panel and a user",
                "expected_result": "The user profile is visible.",
            },
            observation=FakeBrowserTool().observe(),
            trace=[],
            max_steps=8,
        )
        context = json.loads(messages[-1]["content"])

        post_auth = context["state_guidance"]["post_auth_objective"]
        self.assertIn("admin", post_auth["terms"])
        self.assertIn("user", post_auth["terms"])
        self.assertIn("Login is only a milestone", post_auth["instruction"])

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
                    "tool": "browser_fill_form",
                    "reason": "Login credentials are visible.",
                    "fields": [
                        {"target": "1", "element": "Username", "value": "Admin"},
                        {"target": "2", "element": "Password", "value": "admin123"},
                    ],
                },
                {
                    "tool": "browser_click",
                    "target": "3",
                    "element": "Login",
                    "reason": "Submit the login form.",
                },
                {
                    "tool": "browser_click",
                    "target": "3",
                    "element": "Should not be used",
                    "reason": "Auto-stop should happen before this call.",
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
        self.assertEqual([step.action for step in steps], ["navigate", "fill", "fill", "click", "assert_url"])
        self.assertEqual(steps[1].target_element, "username")
        self.assertEqual(steps[1].selector_used, "By.NAME=username")
        self.assertEqual(steps[1].input_value, "Admin")
        self.assertEqual(steps[1].target_attrs, {"tag": "input", "name": "username"})
        self.assertEqual(steps[1].status, "passed")
        self.assertEqual(steps[2].target_element, "password")
        self.assertEqual(steps[2].input_value, "admin123")
        self.assertEqual(steps[3].target_element, "Login")
        self.assertEqual(steps[4].action, "assert_url")
        self.assertIn("dashboard", steps[4].input_value.lower())
        self.assertEqual(fake_provider.calls[0]["opts"]["temperature"], 0.4)
        self.assertEqual(fake_provider.calls[0]["opts"]["max_tokens"], 777)
        self.assertEqual(len(fake_provider.calls), 2)
        script = AutomationScript.objects.get(test_case=self.test_case)
        self.assertEqual(script.framework, AutomationFramework.SELENIUM)
        self.assertEqual(script.language, AutomationLanguage.PYTHON)
        self.assertEqual(script.generated_by, AutomationScriptGeneratedBy.AI)
        self.assertTrue(script.is_active)

    def test_authoring_rejects_finish_before_success_evidence(self):
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
                    "tool": "browser_finish",
                    "reason": "I think the test is complete.",
                    "success_evidence": ["Dashboard is visible"],
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
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        steps = list(ExecutionStep.objects.filter(execution=execution).order_by("step_index"))
        self.assertEqual(steps[-1].action, "finish")
        self.assertEqual(steps[-1].status, "failed")
        self.assertFalse(AutomationScript.objects.filter(test_case=self.test_case).exists())

    def test_authoring_retries_incomplete_verification_tool_call(self):
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
                    "tool": "browser_verify_text_visible",
                    "target": "current page",
                    "reason": "Check the current page.",
                },
                {
                    "tool": "browser_fill_form",
                    "reason": "Login credentials are visible.",
                    "fields": [
                        {"target": "1", "element": "Username", "value": "Admin"},
                        {"target": "2", "element": "Password", "value": "admin123"},
                    ],
                },
                {
                    "tool": "browser_click",
                    "target": "3",
                    "element": "Login",
                    "reason": "Submit the login form.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        steps = list(ExecutionStep.objects.filter(execution=execution).order_by("step_index"))
        self.assertEqual(
            [step.action for step in steps],
            ["navigate", "fill", "fill", "click", "assert_url"],
        )
        self.assertEqual(len(fake_provider.calls), 3)
        retry_context = json.loads(fake_provider.calls[1]["messages"][-1]["content"])
        rejected = retry_context["trace"][-1]
        self.assertEqual(rejected["status"], "rejected")
        self.assertIn("requires a non-empty text", rejected["error"])

    def test_authoring_rejects_non_visible_text_verification_and_recovers(self):
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
                    "tool": "browser_verify_text_visible",
                    "text": "Login successfully",
                    "reason": "Check login success text.",
                },
                {
                    "tool": "browser_fill_form",
                    "reason": "Login credentials are visible.",
                    "fields": [
                        {"target": "1", "element": "Username", "value": "Admin"},
                        {"target": "2", "element": "Password", "value": "admin123"},
                    ],
                },
                {
                    "tool": "browser_click",
                    "target": "3",
                    "element": "Login",
                    "reason": "Submit the login form.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        retry_context = json.loads(fake_provider.calls[1]["messages"][-1]["content"])
        rejected = retry_context["trace"][-1]
        self.assertEqual(rejected["status"], "rejected")
        self.assertIn("not visible", rejected["error"])
        self.assertNotIn("Login successfully", [step.input_value for step in execution.steps.all()])

    def test_auth_success_accepts_dashboard_when_expected_text_is_generic(self):
        success = evaluate_success(
            goal={
                "title": "Login with valid email and password",
                "expected_result": "Login successfully",
            },
            observation={
                "current_url": "https://opensource-demo.orangehrmlive.com/web/index.php/dashboard/index",
                "page_title": "OrangeHRM",
                "snapshot": 'Page URL: dashboard\n- heading "Dashboard"',
                "visible_text_summary": "Dashboard Time at Work Quick Launch",
                "interactive_elements": [],
            },
            trace=[],
        )

        self.assertTrue(success.satisfied)
        self.assertIn("url contains: dashboard", success.evidence)

    def test_auth_success_does_not_stop_complex_post_login_objective(self):
        dashboard_observation = {
            "current_url": "https://opensource-demo.orangehrmlive.com/web/index.php/dashboard/index",
            "page_title": "OrangeHRM",
            "snapshot": 'Page URL: dashboard\n- heading "Dashboard"',
            "visible_text_summary": "Dashboard Time at Work Quick Launch",
            "interactive_elements": [],
        }
        goal = {
            "title": (
                "The user read the username and password from the page then "
                "uses them to login and navigate to the admin panel and a user"
            ),
            "expected_result": "The selected user is visible.",
        }

        success = evaluate_success(goal=goal, observation=dashboard_observation, trace=[])

        self.assertFalse(success.satisfied)

        early_finish = evaluate_success(
            goal=goal,
            observation=dashboard_observation,
            trace=[],
            success_evidence=["Dashboard is visible"],
        )

        self.assertFalse(early_finish.satisfied)

        admin_success = evaluate_success(
            goal=goal,
            observation={
                **dashboard_observation,
                "current_url": "https://example.test/admin/users",
                "visible_text_summary": "Admin User Management System Users",
            },
            trace=[],
            success_evidence=["Admin User Management"],
        )

        self.assertTrue(admin_success.satisfied)

    def test_authoring_retries_empty_fill_form_tool_call(self):
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
                    "tool": "browser_fill_form",
                    "reason": "Fill the visible login form.",
                },
                {
                    "tool": "browser_fill_form",
                    "reason": "Fill the visible login form.",
                    "fields": [
                        {"target": "1", "element": "Username", "value": "Admin"},
                        {"target": "2", "element": "Password", "value": "admin123"},
                    ],
                },
                {
                    "tool": "browser_click",
                    "target": "Login",
                    "element": "Login",
                    "reason": "Submit login.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        self.assertEqual(fake_tool.executed[1]["tool"], "browser_fill_form")
        self.assertEqual(fake_tool.executed[1]["fields"][0]["target"], "1")
        self.assertEqual(fake_tool.executed[2]["target"], "3")
        retry_context = json.loads(fake_provider.calls[1]["messages"][-1]["content"])
        self.assertEqual(retry_context["trace"][-1]["status"], "rejected")
        self.assertIn("requires a non-empty fields", retry_context["trace"][-1]["error"])

    def test_authoring_normalizes_human_target_to_snapshot_ref(self):
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
                    "tool": "browser_fill",
                    "target": "username",
                    "value": "Admin",
                    "reason": "Fill username.",
                },
                {
                    "tool": "browser_fill",
                    "target": "password",
                    "value": "admin123",
                    "reason": "Fill password.",
                },
                {
                    "tool": "browser_click",
                    "target": "login",
                    "reason": "Submit login.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        self.assertEqual(fake_tool.executed[1]["target"], "1")
        self.assertEqual(fake_tool.executed[2]["target"], "2")
        self.assertEqual(fake_tool.executed[3]["target"], "3")

    def test_authoring_rejects_repeated_fill_form_and_recovers(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.QUEUED,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            stream_enabled=True,
        )
        fake_tool = FakeBrowserTool()
        repeated_fill = {
            "tool": "browser_fill_form",
            "reason": "Fill login credentials.",
            "fields": [
                {"target": "1", "element": "Username", "value": "Admin"},
                {"target": "2", "element": "Password", "value": "admin123"},
            ],
        }
        fake_provider = FakeProvider(
            [
                repeated_fill,
                repeated_fill,
                {
                    "tool": "browser_click",
                    "target": "3",
                    "element": "Login",
                    "reason": "Submit the already-filled login form.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        executed_tools = [action["tool"] for action in fake_tool.executed]
        self.assertEqual(
            executed_tools,
            ["browser_navigate", "browser_fill_form", "browser_click"],
        )
        retry_context = json.loads(fake_provider.calls[2]["messages"][-1]["content"])
        rejected = retry_context["trace"][-1]
        self.assertEqual(rejected["status"], "rejected")
        self.assertIn("repeats fields already filled", rejected["error"])
        self.assertEqual(retry_context["trace"][-2]["fields"][0]["target"], "1")
        self.assertEqual(retry_context["trace"][-2]["fields"][1]["value"], "********")

    def test_authoring_retries_invalid_json_response(self):
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
                "not a json object",
                {
                    "tool": "browser_fill_form",
                    "reason": "Fill login credentials.",
                    "fields": [
                        {"target": "1", "element": "Username", "value": "Admin"},
                        {"target": "2", "element": "Password", "value": "admin123"},
                    ],
                },
                {
                    "tool": "browser_click",
                    "target": "Login",
                    "reason": "Submit login.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: fake_tool,
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.PASSED)
        retry_context = json.loads(fake_provider.calls[1]["messages"][-1]["content"])
        self.assertEqual(retry_context["trace"][-1]["status"], "rejected")
        self.assertIn("JSON", retry_context["trace"][-1]["error"])

    def test_authoring_fails_after_repeated_invalid_tool_calls(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.QUEUED,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            stream_enabled=True,
        )
        fake_provider = FakeProvider(
            [
                {
                    "tool": "browser_verify_text_visible",
                    "target": "current page",
                    "reason": "Missing text.",
                },
                {
                    "tool": "browser_wait_for",
                    "reason": "Missing wait condition.",
                },
                {
                    "tool": "browser_fill",
                    "target": "1",
                    "reason": "Missing value.",
                },
            ]
        )

        run_browser_authoring_session(
            str(execution.id),
            target_url="https://orangehrm.example/auth/login",
            max_steps=5,
            browser_tool_factory=lambda browser: FakeBrowserTool(),
            provider=fake_provider,
        )

        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        steps = list(ExecutionStep.objects.filter(execution=execution).order_by("step_index"))
        self.assertEqual(steps[-1].action, "fill")
        self.assertEqual(steps[-1].status, ExecutionStepStatus.FAILED)
        self.assertIn("requires a value", steps[-1].error_message)

    def test_authoring_detects_captcha_and_pauses_for_user(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.QUEUED,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            stream_enabled=True,
        )
        fake_tool = FakeBrowserTool()
        fake_tool.captcha = True
        fake_provider = FakeProvider([])

        def cancel_after_pause(paused_execution):
            paused_execution.status = ExecutionStatus.CANCELLED
            paused_execution.pause_requested = True
            paused_execution.save(update_fields=["status", "pause_requested"])

        with patch(
            "apps.ai.workflows.authoring.service._wait_until_resumed",
            side_effect=cancel_after_pause,
        ) as wait_mock:
            run_browser_authoring_session(
                str(execution.id),
                target_url="https://orangehrm.example/auth/login",
                max_steps=4,
                browser_tool_factory=lambda browser: fake_tool,
                provider=fake_provider,
            )

        wait_mock.assert_called_once()
        steps = list(ExecutionStep.objects.filter(execution=execution).order_by("step_index"))
        self.assertEqual(steps[-1].action, "ask_user")
        self.assertEqual(steps[-1].status, "pending")
        self.assertIn("captcha", steps[-1].target_element.lower())
        self.assertEqual(len(fake_provider.calls), 0)

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
        self.assertEqual(capabilities.get("pageLoadStrategy"), "eager")
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
                "tool": "browser_fill",
                "target": "1",
                "value": "Admin",
                "reason": "Username textbox is visible.",
            },
            observation,
        )
        tool.execute(
            {
                "tool": "browser_click",
                "target": "2",
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

    def test_browser_navigate_recovers_from_renderer_timeout(self):
        class TimeoutOnGetDriver(FakeWebDriver):
            def get(self, url):
                self.gets.append(url)
                raise TimeoutException(
                    "timeout: Timed out receiving message from renderer: 28.583"
                )

        fake_driver = TimeoutOnGetDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        result = tool.execute(
            {
                "tool": "browser_navigate",
                "url": "https://slow.example.test",
                "reason": "Open target URL.",
            },
            {},
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["action"], "navigate")
        self.assertTrue(result["navigation_timed_out"])
        self.assertTrue(result["recovered"])
        self.assertIn("renderer", result["warning"].lower())
        self.assertTrue(any("window.stop" in script for script in fake_driver.scripts))

    def test_observe_falls_back_when_dom_walker_renderer_times_out(self):
        class RendererTimeoutDriver(FakeWebDriver):
            def execute_script(self, script, *args):
                if not args:
                    raise WebDriverException(
                        "timeout: Timed out receiving message from renderer: 28.583"
                    )
                return super().execute_script(script, *args)

        fake_driver = RendererTimeoutDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        observation = tool.observe()

        self.assertEqual(observation["current_url"], fake_driver.current_url)
        self.assertEqual(observation["page_title"], fake_driver.title)
        self.assertEqual(observation["interactive_elements"], [])
        self.assertIn("observation_warning", observation)
        self.assertIn("Browser observation warning", observation["snapshot"])

    def test_snapshot_includes_v2_element_state_and_target_attrs(self):
        fake_driver = FakeWebDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        observation = tool.observe()

        first = observation["interactive_elements"][0]
        self.assertEqual(first["ref"], "1")
        self.assertEqual(first["role"], "textbox")
        self.assertIn("value", first)
        self.assertIn("disabled", first)
        self.assertEqual(first["target_attrs"]["name"], "username")

    def test_browser_fill_form_tool_returns_per_field_results(self):
        fake_driver = FakeWebDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        observation = tool.observe()
        result = tool.execute(
            {
                "tool": "browser_fill_form",
                "reason": "Fill login fields.",
                "fields": [
                    {"target": "1", "element": "Username", "value": "Admin"},
                    {"target": "1", "element": "Username", "value": "2"},
                ],
            },
            observation,
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["action"], "fill_form")
        self.assertEqual(len(result["field_results"]), 2)
        self.assertEqual(result["field_results"][0]["target_attrs"]["name"], "username")

    @override_settings(AI_AUTHORING_TYPE_DELAY_MS=7, AI_AUTHORING_VISUAL_ACTION_DELAY_MS=11)
    def test_browser_fill_uses_visual_typing_pacing(self):
        fake_driver = FakeWebDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        observation = tool.observe()
        with patch("apps.ai.workflows.authoring.browser_tools.time.sleep") as sleep:
            tool.execute(
                {
                    "tool": "browser_fill",
                    "target": "1",
                    "value": "Admin",
                    "reason": "Fill username.",
                },
                observation,
            )

        self.assertEqual(fake_driver._elements["1"].sent, ["A", "d", "m", "i", "n"])
        delays = [call.args[0] for call in sleep.call_args_list]
        self.assertEqual(delays, [0.007, 0.007, 0.007, 0.007, 0.007, 0.011])

    def test_browser_verify_text_and_value_tools(self):
        fake_driver = FakeWebDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        observation = tool.observe()
        text_result = tool.execute(
            {"tool": "browser_verify_text_visible", "text": "Login", "reason": "Login text is visible."},
            observation,
        )
        tool.execute(
            {"tool": "browser_fill", "target": "1", "value": "Admin", "reason": "Fill username."},
            observation,
        )
        value_result = tool.execute(
            {
                "tool": "browser_verify_value",
                "target": "1",
                "element": "Username",
                "value": "Admin",
                "reason": "Username value is entered.",
            },
            observation,
        )

        self.assertEqual(text_result["action"], "assert_text")
        self.assertEqual(value_result["action"], "assert_value")

    def test_browser_detect_blocker_reports_captcha(self):
        fake_driver = FakeWebDriver()
        tool = SelenoidWebDriverAuthoringTool(
            capabilities=AuthoringBrowserCapabilities(browser_name="chrome"),
            hub_url="http://selenoid.test/wd/hub",
            driver_factory=lambda command_executor, options: fake_driver,
        )

        tool.start()
        result = tool.execute(
            {"tool": "browser_detect_blocker", "reason": "Check for blockers."},
            {
                "visible_text_summary": "Please solve this CAPTCHA before continuing.",
                "snapshot": "",
                "interactive_elements": [],
            },
        )

        self.assertTrue(result["blocked"])
        self.assertEqual(result["blocker_type"], "captcha")

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
            target_attrs={"tag": "input", "name": "username"},
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
        self.assertEqual(self.test_case.steps[1]["step"], "Fill username with Admin.")

    def test_execution_step_serializer_masks_password_display_values(self):
        execution = TestExecution.objects.create(
            test_case=self.test_case,
            triggered_by=self.owner,
            status=ExecutionStatus.RUNNING,
            trigger_type=ExecutionTriggerType.AI_AUTHORING,
            stream_enabled=True,
        )
        step = ExecutionStep.objects.create(
            execution=execution,
            step_index=1,
            action="fill",
            target_element="password",
            selector_used="By.NAME=customer[password]",
            input_value="password123",
            target_attrs={
                "tag": "input",
                "type": "password",
                "name": "customer[password]",
            },
            status="passed",
        )

        data = ExecutionStepSerializer(step).data

        self.assertEqual(data["display_target"], "password")
        self.assertEqual(data["display_input_value"], "********")
        self.assertEqual(data["display_summary"], "Fill password = ********")
        self.assertEqual(data["input_value"], "password123")
        self.assertEqual(data["target_attrs"]["type"], "password")
