"""Unit tests for the AI authoring trace -> Selenium Python translator.

These exercise only the translator function. No database, no Selenoid.
The translator takes a list of step-like objects with attribute access and
returns a runnable Python script string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.test import SimpleTestCase

from apps.ai.workflows.authoring.translator import render_selenium_python


@dataclass
class _FakeStep:
    """Stand-in for ExecutionStep — only the fields the translator touches."""

    action: str
    target_element: str = ""
    input_value: str = ""
    target_attrs: dict[str, Any] = field(default_factory=dict)


class AuthoringTranslatorTests(SimpleTestCase):
    def _render(self, steps: list[_FakeStep], *, url: str = "https://app.example/login") -> str:
        return render_selenium_python(
            test_case_title="OrangeHRM login",
            target_url=url,
            steps=steps,
        )

    # ------------------------------------------------------------------
    # Header / footer / shape
    # ------------------------------------------------------------------

    def test_script_has_imports_run_function_and_main_block(self):
        script = self._render([_FakeStep(action="navigate", target_element="https://x")])
        self.assertIn("from selenium import webdriver", script)
        self.assertIn("from selenium.common.exceptions import (", script)
        self.assertIn("from selenium.webdriver.common.by import By", script)
        self.assertIn("def _wait_for_any(", script)
        self.assertIn("def _click(", script)
        self.assertIn("def _wait_for_new_text(", script)
        self.assertIn("def _wait_for_url_contains(", script)
        self.assertIn("def _unique_email(", script)
        self.assertIn("def _create_driver(", script)
        self.assertIn("def _run_step(", script)
        self.assertIn("biat_runtime.report_step_started(", script)
        self.assertIn("biat_runtime.report_step_failed(", script)
        self.assertIn("def run(driver):", script)
        self.assertIn('if __name__ == "__main__":', script)
        self.assertIn("BIAT_WEBDRIVER_URL", script)
        self.assertIn("BIAT_SELENIUM_GRID_URL", script)
        self.assertIn("driver = _create_driver()", script)
        self.assertIn("driver.quit()", script)

    def test_test_case_title_appears_in_docstring(self):
        script = self._render([_FakeStep(action="navigate", target_element="https://x")])
        self.assertIn("OrangeHRM login", script)

    # ------------------------------------------------------------------
    # Action mapping
    # ------------------------------------------------------------------

    def test_navigate_step_emits_driver_get(self):
        script = self._render(
            [_FakeStep(action="navigate", target_element="https://orangehrm.example/login")]
        )
        self.assertIn("driver.get('https://orangehrm.example/login')", script)
        self.assertIn("_wait_for_page_ready(driver)", script)

    def test_click_step_uses_best_selector(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={"tag": "button", "data_testid": "login-btn"},
            )
        ]
        script = self._render(steps)
        self.assertIn("_biat_previous_body_text = _run_step(", script)
        self.assertIn("lambda: _click_and_wait(driver, [", script)
        self.assertIn("(By.CSS_SELECTOR, '[data-testid=\"login-btn\"]')", script)
        self.assertIn("By.CSS_SELECTOR=[data-testid=\"login-btn\"]", script)

    def test_fill_step_clears_then_sends_keys(self):
        steps = [
            _FakeStep(
                action="fill",
                input_value="Admin",
                target_attrs={"tag": "input", "name": "username"},
            )
        ]
        script = self._render(steps)
        self.assertIn("_fill(driver, [(By.NAME, 'username')", script)
        self.assertIn("element.clear()", script)
        self.assertIn("element.send_keys(str(value))", script)

    def test_select_step_falls_back_to_value_when_visible_text_fails(self):
        steps = [
            _FakeStep(
                action="select",
                input_value="EN",
                target_attrs={"tag": "select", "name": "lang"},
            )
        ]
        script = self._render(steps)
        self.assertIn("_select_option(driver, [(By.NAME, 'lang')", script)
        self.assertIn("Select(element)", script)
        self.assertIn("select.select_by_visible_text(str(value))", script)
        self.assertIn("select.select_by_value(str(value))", script)

    def test_wait_numeric_emits_time_sleep_with_cap(self):
        script = self._render([_FakeStep(action="wait", input_value="2.5")])
        self.assertIn("time.sleep(2.5)", script)

    def test_wait_numeric_clamps_to_safe_range(self):
        script = self._render([_FakeStep(action="wait", input_value="9999")])
        self.assertIn("time.sleep(5.0)", script)

    def test_wait_text_emits_webdriverwait_for_body_text(self):
        script = self._render([_FakeStep(action="wait", input_value="Dashboard")])
        self.assertIn("_wait_for_text(driver, 'Dashboard')", script)
        self.assertIn(
            "EC.text_to_be_present_in_element((By.TAG_NAME, \"body\"), str(text))",
            script,
        )

    def test_assert_text_emits_webdriverwait(self):
        script = self._render([_FakeStep(action="assert_text", input_value="Welcome")])
        self.assertIn("_wait_for_new_text(driver, 'Welcome', _biat_previous_body_text)", script)
        self.assertIn("WebDriverWait(driver, timeout).until(", script)
        self.assertIn("Skipping pre-existing text assertion", script)
        self.assertNotIn("Refusing to assert text already present", script)

    def test_assert_url_emits_url_wait(self):
        script = self._render([_FakeStep(action="assert_url", input_value="dashboard")])
        self.assertIn("_wait_for_url_contains(driver, 'dashboard')", script)
        self.assertIn("current_driver.current_url.lower()", script)

    def test_assert_visible_emits_is_displayed_assertion(self):
        steps = [
            _FakeStep(
                action="assert_visible",
                target_attrs={"tag": "div", "id": "dashboard-grid"},
            )
        ]
        script = self._render(steps)
        self.assertIn("_assert_visible(driver, [(By.ID, 'dashboard-grid')", script)
        self.assertIn("assert element.is_displayed()", script)

    def test_ask_user_step_becomes_comment(self):
        steps = [_FakeStep(action="ask_user", target_element="captcha solve")]
        script = self._render(steps)
        self.assertIn("# Manual step during AI authoring", script)
        self.assertIn("captcha solve", script)

    # ------------------------------------------------------------------
    # Selector priority
    # ------------------------------------------------------------------

    def test_data_testid_is_primary_before_id_and_name(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={
                    "tag": "button",
                    "data_testid": "submit-form",
                    "id": "submit",
                    "name": "submitBtn",
                },
            )
        ]
        script = self._render(steps)
        self.assertIn(
            "lambda: _click_and_wait(driver, [(By.CSS_SELECTOR, '[data-testid=\"submit-form\"]'), "
            "(By.ID, 'submit'), (By.NAME, 'submitBtn')",
            script,
        )

    def test_broad_input_fallbacks_are_not_emitted_when_stable_selectors_exist(self):
        steps = [
            _FakeStep(
                action="fill",
                input_value="John",
                target_attrs={
                    "tag": "input",
                    "type": "text",
                    "id": "first_name",
                    "name": "customer[first_name]",
                },
            )
        ]
        script = self._render(steps)
        self.assertIn("(By.ID, 'first_name')", script)
        self.assertIn("(By.NAME, 'customer[first_name]')", script)
        self.assertNotIn("input[type=\"text\"]", script)
        self.assertNotIn("(By.TAG_NAME, 'input')", script)

    def test_input_type_fallback_is_only_used_without_stable_selector(self):
        steps = [
            _FakeStep(
                action="fill",
                input_value="someone@example.com",
                target_attrs={"tag": "input", "type": "email"},
            )
        ]
        script = self._render(steps)
        self.assertIn("(By.CSS_SELECTOR, 'input[type=\"email\"]')", script)
        self.assertIn("(By.TAG_NAME, 'input')", script)

    def test_email_fill_generates_unique_email_value(self):
        steps = [
            _FakeStep(
                action="fill",
                input_value="johndoe@example.com",
                target_attrs={"tag": "input", "type": "email", "name": "customer[email]"},
            )
        ]
        script = self._render(steps)
        self.assertIn("_unique_email('johndoe@example.com')", script)
        self.assertIn("import uuid", script)

    def test_volatile_id_is_skipped_in_favor_of_name(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={
                    "tag": "button",
                    "id": "mui-12345",
                    "name": "loginBtn",
                },
            )
        ]
        script = self._render(steps)
        self.assertIn("By.NAME, 'loginBtn'", script)
        self.assertNotIn("By.ID, 'mui-12345'", script)

    def test_aria_label_used_when_no_id_or_name(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={"tag": "div", "aria_label": "Close dialog"},
            )
        ]
        script = self._render(steps)
        self.assertIn('[aria-label="Close dialog"]', script)

    def test_button_text_falls_back_to_xpath(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={"tag": "button", "text": "Login"},
            )
        ]
        script = self._render(steps)
        self.assertIn("By.XPATH", script)
        self.assertIn("//button[normalize-space()='Login']", script)

    def test_submit_input_text_narrows_selector_by_value(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={"tag": "input", "type": "submit", "text": "Create Account"},
            )
        ]
        script = self._render(steps)
        self.assertIn(
            '(By.CSS_SELECTOR, \'input[type="submit"][value="Create Account"]\')',
            script,
        )
        self.assertNotIn("(By.TAG_NAME, 'input')", script)

    def test_unknown_target_falls_back_to_body(self):
        """If the agent recorded a step without durable attrs, the translator
        should still produce a syntactically valid script (reviewer fixes it
        manually). It must NOT crash."""
        steps = [_FakeStep(action="click", target_attrs={})]
        script = self._render(steps)
        self.assertIn("lambda: _click_and_wait(driver, [(By.TAG_NAME, 'body')])", script)
        # Either tag fallback or body fallback — must not raise.

    # ------------------------------------------------------------------
    # Escaping
    # ------------------------------------------------------------------

    def test_quoted_values_are_safely_escaped(self):
        steps = [
            _FakeStep(
                action="fill",
                input_value="it's \"complex\"",
                target_attrs={"tag": "input", "name": "note"},
            )
        ]
        script = self._render(steps)
        # repr() ensures the string literal is valid Python — exec the snippet
        # in a sandbox to confirm it parses.
        compile(script, "<translated>", "exec")
