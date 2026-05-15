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
        self.assertIn("from selenium.webdriver.common.by import By", script)
        self.assertIn("def run(driver):", script)
        self.assertIn('if __name__ == "__main__":', script)
        self.assertIn("BIAT_SELENIUM_GRID_URL", script)
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

    def test_click_step_uses_best_selector(self):
        steps = [
            _FakeStep(
                action="click",
                target_attrs={"tag": "button", "data_testid": "login-btn"},
            )
        ]
        script = self._render(steps)
        self.assertIn(
            "driver.find_element(By.CSS_SELECTOR, '[data-testid=\"login-btn\"]').click()",
            script,
        )

    def test_fill_step_clears_then_sends_keys(self):
        steps = [
            _FakeStep(
                action="fill",
                input_value="Admin",
                target_attrs={"tag": "input", "name": "username"},
            )
        ]
        script = self._render(steps)
        self.assertIn("driver.find_element(By.NAME, 'username').clear()", script)
        self.assertIn(
            "driver.find_element(By.NAME, 'username').send_keys('Admin')", script
        )

    def test_select_step_falls_back_to_value_when_visible_text_fails(self):
        steps = [
            _FakeStep(
                action="select",
                input_value="EN",
                target_attrs={"tag": "select", "name": "lang"},
            )
        ]
        script = self._render(steps)
        self.assertIn("Select(driver.find_element(By.NAME, 'lang'))", script)
        self.assertIn("select_by_visible_text('EN')", script)
        self.assertIn("select_by_value('EN')", script)

    def test_wait_numeric_emits_time_sleep_with_cap(self):
        script = self._render([_FakeStep(action="wait", input_value="2.5")])
        self.assertIn("time.sleep(2.5)", script)

    def test_wait_numeric_clamps_to_safe_range(self):
        script = self._render([_FakeStep(action="wait", input_value="9999")])
        self.assertIn("time.sleep(5.0)", script)

    def test_wait_text_emits_webdriverwait_for_body_text(self):
        script = self._render([_FakeStep(action="wait", input_value="Dashboard")])
        self.assertIn("WebDriverWait(driver, 30).until(", script)
        self.assertIn(
            "EC.text_to_be_present_in_element((By.TAG_NAME, \"body\"), 'Dashboard')",
            script,
        )

    def test_assert_text_emits_webdriverwait(self):
        script = self._render([_FakeStep(action="assert_text", input_value="Welcome")])
        self.assertIn("WebDriverWait(driver, 30).until(", script)
        self.assertIn("'Welcome'", script)

    def test_assert_visible_emits_is_displayed_assertion(self):
        steps = [
            _FakeStep(
                action="assert_visible",
                target_attrs={"tag": "div", "id": "dashboard-grid"},
            )
        ]
        script = self._render(steps)
        self.assertIn(
            "assert driver.find_element(By.ID, 'dashboard-grid').is_displayed()",
            script,
        )

    def test_ask_user_step_becomes_comment(self):
        steps = [_FakeStep(action="ask_user", target_element="captcha solve")]
        script = self._render(steps)
        self.assertIn("# Manual step during AI authoring", script)
        self.assertIn("captcha solve", script)

    # ------------------------------------------------------------------
    # Selector priority
    # ------------------------------------------------------------------

    def test_data_testid_beats_id_and_name(self):
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
        self.assertIn('[data-testid="submit-form"]', script)
        self.assertNotIn("By.ID, 'submit'", script)
        self.assertNotIn("By.NAME, 'submitBtn'", script)

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

    def test_unknown_target_falls_back_to_body(self):
        """If the agent recorded a step without durable attrs, the translator
        should still produce a syntactically valid script (reviewer fixes it
        manually). It must NOT crash."""
        steps = [_FakeStep(action="click", target_attrs={})]
        script = self._render(steps)
        self.assertIn("driver.find_element(", script)
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
