"""Live browser authoring tool backed by Selenoid via Selenium-Remote WebDriver.

The agent's `observe → decide → execute` loop runs on the `ai_agent` Celery queue.
This module opens a real visible browser inside Selenoid (later Moon) so the user
can watch the agent work, pause it, take control over the same noVNC stream, and
resume. It is intentionally separate from the regression and interactive queues
which run pre-written Selenium scripts inside runner containers.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from django.conf import settings
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


class BrowserAuthoringTool(Protocol):
    def start(self) -> None: ...

    def observe(self) -> dict[str, Any]: ...

    def execute(self, action: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]: ...

    def get_stream_session_id(self) -> str | None: ...

    def close(self) -> None: ...


class BrowserAuthoringError(RuntimeError):
    """Raised when the Selenoid authoring browser cannot start or execute."""

    def __init__(
        self,
        message: str,
        *,
        target_attrs: dict[str, Any] | None = None,
        target_ref: str = "",
    ):
        super().__init__(message)
        self.target_attrs = target_attrs or {}
        self.target_ref = target_ref


@dataclass
class AuthoringBrowserCapabilities:
    """Capability bag for the AI authoring browser.

    Backend is capability-based, not hardcoded. V1 UI exposes Chrome only;
    later UI/team settings can drive every field. Each field maps cleanly to
    Selenoid today and Moon tomorrow.
    """

    browser_name: str = "chrome"
    # Empty by default — Selenoid uses whatever default version its browsers.json
    # advertises. Passing the literal string "latest" makes Selenoid 404 with
    # "Requested environment is not available". Override with a real version
    # (e.g. "120.0") only when the team needs a pin.
    browser_version: str = ""
    platform_name: str = ""  # empty → Selenoid default
    enable_vnc: bool = True
    enable_video: bool = False
    session_timeout: str = "10m"
    extra_selenoid_options: dict[str, Any] = field(default_factory=dict)

    def to_options(self) -> Any:
        """Build the Selenium 4 options object for this browser with Selenoid caps."""
        browser = (self.browser_name or "chrome").lower()
        if browser in {"chrome", "chromium"}:
            options = webdriver.ChromeOptions()
            options.add_argument("--disable-dev-shm-usage")
        elif browser == "firefox":
            options = webdriver.FirefoxOptions()
        elif browser == "edge":
            options = webdriver.EdgeOptions()
            options.add_argument("--disable-dev-shm-usage")
        else:
            raise BrowserAuthoringError(
                f"Unsupported authoring browser: {browser}. "
                "Configure a Selenoid image first."
            )

        options.set_capability("browserName", "chrome" if browser == "chromium" else browser)
        options.set_capability("pageLoadStrategy", "eager")
        if self.browser_version:
            options.set_capability("browserVersion", self.browser_version)
        if self.platform_name:
            options.set_capability("platformName", self.platform_name)

        selenoid_options: dict[str, Any] = {
            "enableVNC": bool(self.enable_vnc),
            "enableVideo": bool(self.enable_video),
            "sessionTimeout": self.session_timeout,
        }
        selenoid_options.update(self.extra_selenoid_options or {})
        options.set_capability("selenoid:options", selenoid_options)
        return options


# JavaScript DOM walker. Tags every interactive element with `data-biat-ref="<n>"`
# (reset on every observe) and returns a structured snapshot the LLM prompt
# already knows how to consume. Keeps the contract the MCP version exposed
# so the prompt and graph are unchanged.
_DOM_WALKER_JS = r"""
const SELECTOR = [
  'a[href]', 'button', 'input', 'select', 'textarea', 'summary',
  '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="radio"]',
  '[role="menuitem"]', '[role="option"]', '[role="tab"]', '[role="switch"]',
  '[role="combobox"]', '[role="textbox"]', '[contenteditable="true"]',
  '[onclick]', '[tabindex]:not([tabindex="-1"])'
].join(',');

document.querySelectorAll('[data-biat-ref]').forEach(el => el.removeAttribute('data-biat-ref'));

function clean(value, limit = 200) {
  return String(value || '').replace(/\s+/g, ' ').trim().slice(0, limit);
}

function isVisible(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const style = window.getComputedStyle(el);
  return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
}

function labelTextFor(el) {
  const id = el.id || el.getAttribute('id') || '';
  if (id) {
    const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
    if (label) return clean(label.innerText || label.textContent, 120);
  }
  const wrappingLabel = el.closest && el.closest('label');
  if (wrappingLabel) return clean(wrappingLabel.innerText || wrappingLabel.textContent, 120);
  return '';
}

function elementName(el) {
  return clean(
    el.getAttribute('aria-label') ||
    el.getAttribute('placeholder') ||
    labelTextFor(el) ||
    el.getAttribute('alt') ||
    el.getAttribute('title') ||
    el.value ||
    el.innerText ||
    el.getAttribute('name') ||
    el.getAttribute('id') ||
    '',
    160
  );
}

function elementRole(el) {
  const role = el.getAttribute('role');
  if (role) return role;
  const tag = el.tagName.toLowerCase();
  if (tag === 'a') return 'link';
  if (tag === 'button') return 'button';
  if (tag === 'select') return 'combobox';
  if (tag === 'textarea') return 'textbox';
  if (tag === 'input') {
    const t = (el.getAttribute('type') || 'text').toLowerCase();
    if (t === 'checkbox') return 'checkbox';
    if (t === 'radio') return 'radio';
    if (t === 'submit' || t === 'button' || t === 'reset') return 'button';
    return 'textbox';
  }
  return tag;
}

function targetAttrs(el) {
  const tag = el.tagName.toLowerCase();
  const text = clean(el.innerText || el.value || '', 200);
  return {
    tag,
    type: el.getAttribute('type') || '',
    id: el.id || '',
    name: el.getAttribute('name') || '',
    aria_label: el.getAttribute('aria-label') || '',
    data_testid: el.getAttribute('data-testid') || '',
    data_test_id: el.getAttribute('data-test-id') || '',
    data_test: el.getAttribute('data-test') || '',
    data_cy: el.getAttribute('data-cy') || '',
    data_qa: el.getAttribute('data-qa') || '',
    role: el.getAttribute('role') || '',
    text,
    placeholder: el.getAttribute('placeholder') || '',
  };
}

function stateFor(el) {
  const tag = el.tagName.toLowerCase();
  return {
    disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true'),
    checked: Boolean(el.checked || el.getAttribute('aria-checked') === 'true'),
    selected: Boolean(el.selected || el.getAttribute('aria-selected') === 'true'),
    readonly: Boolean(el.readOnly || el.getAttribute('readonly') !== null),
    value: tag === 'input' || tag === 'textarea' || tag === 'select' ? clean(el.value, 200) : '',
  };
}

const elements = [];
let ref = 0;
const nodes = document.querySelectorAll(SELECTOR);
for (const el of nodes) {
  if (!isVisible(el)) continue;
  ref += 1;
  el.setAttribute('data-biat-ref', String(ref));
  const role = elementRole(el);
  const name = elementName(el);
  const attrs = targetAttrs(el);
  const state = stateFor(el);
  const rect = el.getBoundingClientRect();
  const flags = [];
  if (state.disabled) flags.push('disabled');
  if (state.checked) flags.push('checked');
  if (state.selected) flags.push('selected');
  if (state.readonly) flags.push('readonly');
  const stateText = flags.length ? ` [${flags.join(',')}]` : '';
  const valueText = state.value && attrs.type !== 'password' ? ` value="${state.value}"` : '';
  const line = `- ${role}` + (name ? ` "${name}"` : '') + valueText + stateText + ` [ref=${ref}]`;
  elements.push({
    id: String(ref),
    ref: String(ref),
    role,
    name,
    value: attrs.type === 'password' ? '' : state.value,
    disabled: state.disabled,
    checked: state.checked,
    selected: state.selected,
    readonly: state.readonly,
    placeholder: attrs.placeholder,
    target_attrs: attrs,
    box: {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
    },
    line: line.slice(0, 420),
  });
  if (elements.length >= 100) break;
}

const bodyText = (document.body && document.body.innerText) || '';
const compactText = clean(bodyText, 2000);

const snapshotLines = [
  `Page URL: ${location.href}`,
  `Page Title: ${document.title || ''}`,
  '',
  ...elements.map(e => e.line),
];

return {
  current_url: location.href,
  page_title: document.title || '',
  snapshot: snapshotLines.join('\n'),
  visible_text_summary: compactText,
  interactive_elements: elements,
};
"""


@dataclass
class SelenoidWebDriverAuthoringTool:
    """Live browser authoring tool that drives Selenoid (and later Moon) directly.

    Same contract as the previous Playwright MCP tool (observe / execute / start /
    close / get_stream_session_id) so the agent prompt and graph are unchanged.
    """

    capabilities: AuthoringBrowserCapabilities = field(default_factory=AuthoringBrowserCapabilities)
    hub_url: str | None = None
    driver_factory: Callable[..., WebDriver] = webdriver.Remote
    _driver: WebDriver | None = field(default=None, init=False)

    def start(self) -> None:
        hub_url = self.hub_url or settings.SELENOID_HUB_URL
        options = self.capabilities.to_options()
        try:
            self._driver = self.driver_factory(command_executor=hub_url, options=options)
        except WebDriverException as exc:
            raise BrowserAuthoringError(
                f"Selenoid did not accept the authoring session: {exc}"
            ) from exc

        action_timeout = int(
            getattr(settings, "AI_AUTHORING_ACTION_TIMEOUT_SECONDS", 30) or 30
        )
        try:
            self._driver.set_page_load_timeout(action_timeout)
        except WebDriverException:
            pass
        try:
            self._driver.set_script_timeout(action_timeout)
        except WebDriverException:
            pass

    def observe(self) -> dict[str, Any]:
        driver = self._require_driver()
        try:
            payload = driver.execute_script(_DOM_WALKER_JS)
        except WebDriverException as exc:
            return self._fallback_observation(exc)

        if not isinstance(payload, dict):
            return {
                "current_url": "",
                "page_title": "",
                "snapshot": "",
                "visible_text_summary": "",
                "interactive_elements": [],
            }

        # Normalise types the JS layer may return in browser-specific ways.
        return {
            "current_url": str(payload.get("current_url") or driver.current_url),
            "page_title": str(payload.get("page_title") or ""),
            "snapshot": str(payload.get("snapshot") or ""),
            "visible_text_summary": str(payload.get("visible_text_summary") or ""),
            "interactive_elements": payload.get("interactive_elements") or [],
        }

    def execute(self, action: dict[str, Any], observation: dict[str, Any]) -> dict[str, Any]:
        driver = self._require_driver()
        tool_name = _tool_name(action)
        started = time.monotonic()

        if tool_name == "browser_snapshot":
            snapshot = self.observe()
            return {
                **snapshot,
                "status": "passed",
                "action": "snapshot",
                "target": snapshot.get("current_url") or "",
                "message": "Browser snapshot captured.",
                "duration_ms": int((time.monotonic() - started) * 1000),
            }

        if tool_name == "browser_navigate":
            url = action.get("url") or action.get("value")
            if not url:
                raise BrowserAuthoringError("browser_navigate requires a url.")
            try:
                driver.get(url)
            except TimeoutException as exc:
                return self._recover_from_navigation_timeout(url, started, exc)
            except WebDriverException as exc:
                if _looks_like_renderer_timeout(exc):
                    return self._recover_from_navigation_timeout(url, started, exc)
                raise
            self._visual_action_pause()
            return _action_result("navigate", url, "Navigation requested.", started)

        if tool_name == "browser_wait_for":
            return self._wait(action, started)

        if tool_name == "browser_verify_text_visible":
            return self._assert_text(action, observation, started)

        if tool_name == "browser_console_messages":
            return self._console_messages(action, started)

        if tool_name == "browser_take_screenshot":
            return self._take_screenshot(action, started)

        if tool_name == "browser_detect_blocker":
            from apps.ai.workflows.authoring.blockers import detect_blocker

            detection = detect_blocker(observation)
            return {
                "status": "passed",
                "action": "detect_blocker",
                "target": detection.blocker_type or "page",
                "message": detection.message or "No blocker detected.",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "blocked": detection.blocked,
                "blocker_type": detection.blocker_type,
                "evidence": list(detection.evidence),
                "target_attrs": {},
            }

        if tool_name == "browser_fill_form":
            return self._fill_form(action, observation, started)

        if tool_name == "browser_press_key" and not any(
            action.get(key) for key in ("target", "element_ref", "ref", "element_id", "selector")
        ):
            key = str(action.get("key") or action.get("value") or "").strip()
            if not key:
                raise BrowserAuthoringError("browser_press_key requires key.")
            try:
                element = driver.switch_to.active_element
            except Exception:
                element = driver.find_element(By.TAG_NAME, "body")
            element.send_keys(_selenium_key(key))
            return _action_result("press_key", "active element", f"Pressed key {key}.", started)

        ref = _resolve_element_ref(action, observation)
        target_attrs = self._capture_target_attrs(ref)

        if tool_name == "browser_click":
            element = self._wait_for_ref(ref, require_visible=True, require_enabled=True)
            self._scroll_into_view(element)
            try:
                element.click()
            except Exception as exc:
                try:
                    driver.execute_script("arguments[0].click();", element)
                except Exception:
                    raise BrowserAuthoringError(
                        str(exc),
                        target_attrs=target_attrs,
                        target_ref=ref,
                    ) from exc
            self._visual_action_pause()
            return _action_result("click", ref, "Element clicked.", started, target_attrs)

        if tool_name in {"browser_fill", "browser_type"}:
            value = action.get("value")
            if value is None:
                raise BrowserAuthoringError(f"{tool_name} requires value.")
            element = self._wait_for_ref(ref, require_visible=True, require_enabled=True)
            self._scroll_into_view(element)
            if tool_name == "browser_fill":
                try:
                    element.clear()
                except WebDriverException:
                    driver.execute_script("arguments[0].value = '';", element)
            try:
                self._type_value(element, str(value))
                if tool_name == "browser_type" and action.get("submit"):
                    element.send_keys(Keys.ENTER)
            except Exception as exc:
                raise BrowserAuthoringError(
                    str(exc),
                    target_attrs=target_attrs,
                    target_ref=ref,
                ) from exc
            self._visual_action_pause()
            message = "Text typed." if tool_name == "browser_type" else "Element filled."
            return _action_result("fill", ref, message, started, target_attrs)

        if tool_name == "browser_select_option":
            values = action.get("values")
            if not isinstance(values, list) or not values:
                values = [action.get("value")]
            values = [str(value) for value in values if value is not None]
            if not values:
                raise BrowserAuthoringError("browser_select_option requires values.")
            element = self._wait_for_ref(ref, require_visible=True, require_enabled=True)
            self._scroll_into_view(element)
            select = Select(element)
            for value in values:
                try:
                    select.select_by_visible_text(value)
                except WebDriverException:
                    try:
                        select.select_by_value(value)
                    except Exception as exc:
                        raise BrowserAuthoringError(
                            str(exc),
                            target_attrs=target_attrs,
                            target_ref=ref,
                        ) from exc
            return _action_result("select", ref, "Option selected.", started, target_attrs)

        if tool_name == "browser_press_key":
            key = str(action.get("key") or action.get("value") or "").strip()
            if not key:
                raise BrowserAuthoringError("browser_press_key requires key.")
            element = self._wait_for_ref(ref, require_visible=True, require_enabled=False)
            self._scroll_into_view(element)
            try:
                element.send_keys(_selenium_key(key))
            except Exception as exc:
                raise BrowserAuthoringError(
                    str(exc),
                    target_attrs=target_attrs,
                    target_ref=ref,
                ) from exc
            self._visual_action_pause()
            return _action_result("press_key", ref, f"Pressed key {key}.", started, target_attrs)

        if tool_name == "browser_verify_element_visible":
            element = self._wait_for_ref(ref, require_visible=True, require_enabled=False)
            if not element.is_displayed():
                raise BrowserAuthoringError(
                    f"Element ref is not visible: {ref}",
                    target_attrs=target_attrs,
                    target_ref=ref,
                )
            return _action_result("assert_visible", ref, "Element is visible.", started, target_attrs)

        if tool_name == "browser_verify_value":
            expected = str(action.get("value") or "").strip()
            element = self._wait_for_ref(ref, require_visible=True, require_enabled=False)
            actual = _element_value(element)
            if actual != expected:
                raise BrowserAuthoringError(
                    f"Expected value {expected!r}, found {actual!r}.",
                    target_attrs=target_attrs,
                    target_ref=ref,
                )
            return _action_result("assert_value", ref, "Element value matched.", started, target_attrs)

        raise BrowserAuthoringError(f"Unsupported browser tool: {tool_name}")

    def get_stream_session_id(self) -> str | None:
        """Selenoid issues a session id that maps 1:1 to the noVNC stream URL."""
        return self._driver.session_id if self._driver else None

    def close(self) -> None:
        if self._driver is None:
            return
        try:
            self._driver.quit()
        except WebDriverException:
            pass
        finally:
            self._driver = None

    # internal helpers ------------------------------------------------------

    def _require_driver(self) -> WebDriver:
        if self._driver is None:
            raise BrowserAuthoringError("Authoring tool was not started.")
        return self._driver

    def _find_by_ref(self, ref: str):
        driver = self._require_driver()
        try:
            return driver.find_element(By.CSS_SELECTOR, f'[data-biat-ref="{ref}"]')
        except NoSuchElementException as exc:
            raise BrowserAuthoringError(
                f"Element ref {ref!r} is no longer in the DOM. "
                "The agent must observe again before retrying."
            ) from exc

    def _wait_for_ref(
        self,
        ref: str,
        *,
        require_visible: bool,
        require_enabled: bool,
    ):
        timeout = int(getattr(settings, "AI_AUTHORING_ACTION_TIMEOUT_SECONDS", 30) or 30)

        def locate(_driver):
            element = self._find_by_ref(ref)
            if require_visible and not element.is_displayed():
                return False
            if require_enabled and hasattr(element, "is_enabled") and not element.is_enabled():
                return False
            return element

        try:
            return WebDriverWait(self._require_driver(), timeout).until(locate)
        except TimeoutException as exc:
            raise BrowserAuthoringError(
                f"Element ref {ref!r} was not ready for interaction.",
                target_ref=ref,
                target_attrs=self._capture_target_attrs(ref),
            ) from exc

    def _scroll_into_view(self, element) -> None:
        try:
            self._require_driver().execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
                element,
            )
        except WebDriverException:
            pass

    def _type_value(self, element, value: str) -> None:
        delay_ms = max(0, int(getattr(settings, "AI_AUTHORING_TYPE_DELAY_MS", 0) or 0))
        if delay_ms <= 0 or len(value) <= 1:
            element.send_keys(value)
            return
        delay = delay_ms / 1000.0
        for character in value:
            element.send_keys(character)
            time.sleep(delay)

    def _visual_action_pause(self) -> None:
        delay_ms = max(
            0,
            int(getattr(settings, "AI_AUTHORING_VISUAL_ACTION_DELAY_MS", 0) or 0),
        )
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

    def _capture_target_attrs(self, ref: str) -> dict[str, Any]:
        """Read the live element's durable attributes for later Selenium translation.

        Best-effort: failures return an empty dict. The trace -> Selenium script
        translator falls back to other selector strategies when fields are
        missing.
        """
        driver = self._require_driver()
        try:
            payload = driver.execute_script(_TARGET_ATTRS_JS, ref)
        except WebDriverException:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            "tag": str(payload.get("tag") or ""),
            "type": str(payload.get("type") or ""),
            "id": str(payload.get("id") or ""),
            "name": str(payload.get("name") or ""),
            "aria_label": str(payload.get("aria_label") or ""),
            "data_testid": str(payload.get("data_testid") or ""),
            "data_test_id": str(payload.get("data_test_id") or ""),
            "data_test": str(payload.get("data_test") or ""),
            "data_qa": str(payload.get("data_qa") or ""),
            "data_cy": str(payload.get("data_cy") or ""),
            "role": str(payload.get("role") or ""),
            "text": str(payload.get("text") or "").strip()[:200],
            "placeholder": str(payload.get("placeholder") or ""),
        }

    def _fill_form(
        self,
        action: dict[str, Any],
        observation: dict[str, Any],
        started: float,
    ) -> dict[str, Any]:
        fields = action.get("fields")
        if not isinstance(fields, list) or not fields:
            raise BrowserAuthoringError("browser_fill_form requires a non-empty fields array.")

        field_results: list[dict[str, Any]] = []
        for field in fields:
            if not isinstance(field, dict):
                raise BrowserAuthoringError("Each browser_fill_form field must be an object.")
            field_action = {
                "tool": "browser_fill",
                "target": field.get("target"),
                "element": field.get("element"),
                "value": field.get("value"),
                "reason": action.get("reason") or "Fill form field.",
            }
            try:
                result = self.execute(field_action, observation)
                field_results.append(
                    {
                        **result,
                        "field": field,
                        "status": "passed",
                    }
                )
            except Exception as exc:
                field_results.append(
                    {
                        "status": "failed",
                        "action": "fill",
                        "field": field,
                        "target": field.get("target") or "",
                        "message": str(exc),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "target_attrs": getattr(exc, "target_attrs", {}) or {},
                    }
                )
                return {
                    "status": "failed",
                    "action": "fill_form",
                    "target": "form",
                    "message": str(exc),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "field_results": field_results,
                    "target_attrs": {},
                }

        return {
            "status": "passed",
            "action": "fill_form",
            "target": "form",
            "message": "Form fields filled.",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "field_results": field_results,
            "target_attrs": {},
        }

    def _wait(self, action: dict[str, Any], started: float) -> dict[str, Any]:
        driver = self._require_driver()
        text = action.get("text") or action.get("assertion") or action.get("value")
        text_gone = action.get("textGone")
        url_contains = action.get("urlContains")
        observe_timeout = int(
            getattr(settings, "AI_AUTHORING_OBSERVE_TIMEOUT_SECONDS", 30) or 30
        )

        if url_contains:
            expected = str(url_contains)
            try:
                WebDriverWait(driver, observe_timeout).until(
                    lambda current_driver: expected in current_driver.current_url
                )
            except TimeoutException as exc:
                raise BrowserAuthoringError(
                    f"Timed out waiting for URL to contain {expected!r}."
                ) from exc
            return _action_result("wait", expected, "URL condition satisfied.", started)

        if text_gone:
            expected = str(text_gone)
            try:
                WebDriverWait(driver, observe_timeout).until_not(
                    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), expected)
                )
            except TimeoutException as exc:
                raise BrowserAuthoringError(
                    f"Timed out waiting for text to disappear: {expected!r}."
                ) from exc
            return _action_result("wait", expected, "Text disappeared.", started)

        if text and not str(text).replace(".", "", 1).isdigit():
            try:
                WebDriverWait(driver, observe_timeout).until(
                    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), str(text))
                )
            except TimeoutException as exc:
                raise BrowserAuthoringError(
                    f"Timed out waiting for text {text!r}."
            ) from exc
            return _action_result("wait", str(text), "Text appeared.", started)

        try:
            seconds = float(action.get("time") if action.get("time") is not None else text) if (text or action.get("time") is not None) else 1.0
        except (TypeError, ValueError):
            seconds = 1.0
        seconds = min(max(seconds, 0.1), 5.0)
        time.sleep(seconds)
        return _action_result("wait", f"{seconds:.1f}s", "Sleep completed.", started)

    def _assert_text(
        self,
        action: dict[str, Any],
        observation: dict[str, Any],
        started: float,
    ) -> dict[str, Any]:
        driver = self._require_driver()
        expected = str(
            action.get("text") or action.get("assertion") or action.get("value") or ""
        ).strip()
        if not expected:
            raise BrowserAuthoringError("browser_verify_text_visible requires text.")

        haystack = observation.get("snapshot") or observation.get("visible_text_summary") or ""
        if not haystack:
            try:
                haystack = driver.page_source or ""
            except WebDriverException:
                haystack = ""
        if expected.lower() not in str(haystack).lower():
            raise AssertionError(f"Expected text not found on page: {expected}")
        return _action_result("assert_text", expected, "Text present on page.", started)

    def _console_messages(self, action: dict[str, Any], started: float) -> dict[str, Any]:
        level = str(action.get("level") or "browser")
        try:
            messages = self._require_driver().get_log("browser")
        except Exception:
            messages = []
        return {
            "status": "passed",
            "action": "console_messages",
            "target": level,
            "message": f"{len(messages)} console messages captured.",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "messages": messages,
            "target_attrs": {},
        }

    def _take_screenshot(self, action: dict[str, Any], started: float) -> dict[str, Any]:
        try:
            screenshot = self._require_driver().get_screenshot_as_base64()
        except Exception as exc:
            raise BrowserAuthoringError(f"Screenshot failed: {exc}") from exc
        return {
            "status": "passed",
            "action": "screenshot",
            "target": "page",
            "message": "Screenshot captured.",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "screenshot_base64": screenshot,
            "target_attrs": {},
        }

    def _recover_from_navigation_timeout(
        self,
        url: str,
        started: float,
        exc: WebDriverException,
    ) -> dict[str, Any]:
        """Treat Chrome renderer page-load stalls as recoverable authoring state.

        Real sites can leave Chrome waiting on subresources or SPA bootstrap
        work long after the visible page is usable. For live authoring, failing
        the whole AI session here is worse than stopping the load and letting
        the agent observe whatever the browser currently shows.
        """
        driver = self._require_driver()
        try:
            driver.execute_script("window.stop();")
        except WebDriverException:
            pass

        warning = _short_webdriver_message(exc)
        result = _action_result(
            "navigate",
            url,
            "Navigation timed out in Chrome, stopped page load, and continued with current browser state.",
            started,
        )
        result["warning"] = warning
        result["recovered"] = True
        result["navigation_timed_out"] = True
        return result

    def _fallback_observation(self, exc: WebDriverException) -> dict[str, Any]:
        driver = self._require_driver()
        warning = _short_webdriver_message(exc)
        current_url = _safe_driver_value(lambda: driver.current_url)
        page_title = _safe_driver_value(lambda: driver.title)
        body_text = ""
        try:
            body_text = str(driver.find_element(By.TAG_NAME, "body").text or "")[:2000]
        except Exception:
            body_text = ""

        snapshot_lines = [
            f"Page URL: {current_url}",
            f"Page Title: {page_title}",
            "",
            f"Browser observation warning: {warning}",
        ]
        if body_text:
            snapshot_lines.extend(["", body_text])

        return {
            "current_url": current_url,
            "page_title": page_title,
            "snapshot": "\n".join(snapshot_lines),
            "visible_text_summary": body_text,
            "interactive_elements": [],
            "observation_warning": warning,
        }


def _resolve_element_ref(action: dict[str, Any], observation: dict[str, Any]) -> str:
    """Pick the best ref from the agent's action against the latest observation.

    The prompt tells the agent to use only the integer ``element_ref``. In
    practice models sometimes fall back to CSS selectors or ids. This resolver
    has three tiers:

      1. Exact match: candidate is already a ref like "1".
      2. Hint extraction: pull identifier tokens out of CSS patterns
         (``input[name='username']``, ``#login``, ``.submit``, etc.) and
         substring-match them against element name/role/line.
      3. Plain-string substring match against element name/role/line.

    Only after all three fail do we ask the agent to observe again.
    """
    raw_candidates = [
        action.get("target"),
        action.get("element_ref"),
        action.get("ref"),
        action.get("element_id"),
        action.get("selector"),
    ]
    elements = [
        element
        for element in observation.get("interactive_elements", [])
        if isinstance(element, dict)
    ]
    refs = {
        str(element.get("ref") or element.get("id")): element
        for element in elements
        if element.get("ref") or element.get("id")
    }

    # Tier 1: exact ref match.
    for candidate in raw_candidates:
        if not candidate:
            continue
        candidate_text = str(candidate).strip()
        if candidate_text in refs:
            return candidate_text

    # Tiers 2 + 3: build hint tokens from each candidate and substring-match.
    hint_tokens: list[str] = []
    for candidate in raw_candidates:
        if not candidate:
            continue
        hint_tokens.extend(_extract_hint_tokens(str(candidate)))

    normalized_hints = [_normalize(token) for token in hint_tokens if token]
    for element in elements:
        haystack = _normalize(
            " ".join(
                str(element.get(key) or "")
                for key in ("name", "role", "line")
            )
        )
        if any(hint and hint in haystack for hint in normalized_hints):
            return str(element.get("ref") or element.get("id"))

    raise BrowserAuthoringError(
        "Action references an element that is not in the latest observation. "
        "The agent must observe again."
    )


def _looks_like_renderer_timeout(exc: WebDriverException) -> bool:
    message = str(exc).lower()
    timeout_markers = [
        "timed out receiving message from renderer",
        "timeout: timed out",
        "page load timeout",
        "script timeout",
    ]
    return any(marker in message for marker in timeout_markers)


def _short_webdriver_message(exc: WebDriverException) -> str:
    message = str(exc).strip()
    if "Stacktrace:" in message:
        message = message.split("Stacktrace:", 1)[0].strip()
    return message[:1000]


def _safe_driver_value(getter: Callable[[], Any], default: str = "") -> str:
    try:
        return str(getter() or "")
    except Exception:
        return default


def _tool_name(action: dict[str, Any]) -> str:
    """Return the V2 tool name, accepting old names only inside the tool layer.

    The service validates V2 strictly. This compatibility keeps low-level unit
    doubles and direct tool smoke tests from being needlessly brittle.
    """
    raw = str(action.get("tool") or action.get("action") or "").strip()
    legacy_map = {
        "navigate": "browser_navigate",
        "click": "browser_click",
        "fill": "browser_fill",
        "select": "browser_select_option",
        "wait": "browser_wait_for",
        "assert_visible": "browser_verify_element_visible",
        "assert_text": "browser_verify_text_visible",
    }
    return legacy_map.get(raw, raw)


def _selenium_key(key: str):
    lookup = {
        "enter": Keys.ENTER,
        "escape": Keys.ESCAPE,
        "esc": Keys.ESCAPE,
        "tab": Keys.TAB,
        "backspace": Keys.BACKSPACE,
        "delete": Keys.DELETE,
        "arrowleft": Keys.ARROW_LEFT,
        "arrowright": Keys.ARROW_RIGHT,
        "arrowup": Keys.ARROW_UP,
        "arrowdown": Keys.ARROW_DOWN,
        "space": Keys.SPACE,
    }
    normalized = "".join(ch for ch in key.lower() if ch.isalnum())
    return lookup.get(normalized, key)


def _element_value(element) -> str:
    try:
        checked = element.get_attribute("checked")
        element_type = (element.get_attribute("type") or "").lower()
        if element_type in {"checkbox", "radio"}:
            return "true" if checked in {True, "true", "checked", "1"} else "false"
    except Exception:
        pass
    try:
        return str(element.get_attribute("value") or "")
    except Exception:
        return ""


# Tokens we extract from CSS-shaped strings so the substring fallback can
# still find an element when the agent forgets to use the bare ref.
_CSS_ATTR_PATTERN = re.compile(r"\[([a-zA-Z-]+)\s*[*^$~|]?=\s*['\"]?([^'\"\]]+)['\"]?\]")
_CSS_ID_PATTERN = re.compile(r"#([A-Za-z_][\w-]*)")
_CSS_CLASS_PATTERN = re.compile(r"\.([A-Za-z_][\w-]+)")


def _extract_hint_tokens(value: str) -> list[str]:
    """Pull human-readable identifier tokens out of a candidate string.

    Examples:
        "input[name='username']" -> ["input", "username"]
        "#login-btn"             -> ["login-btn"]
        ".btn.submit"            -> ["btn", "submit"]
        "Username"               -> ["Username"]
    """
    raw = value.strip()
    if not raw:
        return []

    tokens: list[str] = []
    for _attr, attr_value in _CSS_ATTR_PATTERN.findall(raw):
        if attr_value:
            tokens.append(attr_value)
    for id_value in _CSS_ID_PATTERN.findall(raw):
        tokens.append(id_value)
    for class_value in _CSS_CLASS_PATTERN.findall(raw):
        tokens.append(class_value)

    # Strip all CSS-specific syntax to get a plain remainder candidate.
    plain = _CSS_ATTR_PATTERN.sub("", raw)
    plain = _CSS_ID_PATTERN.sub("", plain)
    plain = _CSS_CLASS_PATTERN.sub("", plain)
    plain = plain.strip().strip(":,>+~ ")
    if plain:
        tokens.append(plain)
    elif not tokens:
        # Fully plain candidate — use the whole value.
        tokens.append(raw)
    return tokens


def _normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _action_result(
    action_name: str,
    target: Any,
    message: str,
    started: float,
    target_attrs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "passed",
        "action": action_name,
        "target": str(target or ""),
        "message": message,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "target_attrs": target_attrs or {},
    }


# Reads the live element's durable identifier attributes so the trace -> Selenium
# script translator can pick a stable selector (id / data-testid / name /
# aria-label / text-xpath) instead of the session-local data-biat-ref. Best-effort
# — fields that don't exist on the element return "".
_TARGET_ATTRS_JS = r"""
const ref = arguments[0];
const el = document.querySelector('[data-biat-ref="' + ref + '"]');
if (!el) return {};
const tag = el.tagName.toLowerCase();
const text = (el.innerText || el.value || '').replace(/\s+/g, ' ').trim().slice(0, 200);
return {
  tag: tag,
  type: el.getAttribute('type') || '',
  id: el.id || '',
  name: el.getAttribute('name') || '',
  aria_label: el.getAttribute('aria-label') || '',
  data_testid: el.getAttribute('data-testid') || '',
  data_test_id: el.getAttribute('data-test-id') || '',
  data_test: el.getAttribute('data-test') || '',
  data_cy: el.getAttribute('data-cy') || '',
  data_qa: el.getAttribute('data-qa') || '',
  role: el.getAttribute('role') || '',
  text: text,
  placeholder: el.getAttribute('placeholder') || '',
};
"""


def build_browser_authoring_tool(browser: str | None = None) -> BrowserAuthoringTool:
    """Default factory: Selenoid WebDriver tool with Chrome capabilities.

    `browser` is the request-supplied hint (UI dropdown today). Falls back to
    the team/global default `AI_AUTHORING_DEFAULT_BROWSER` setting.
    """
    default_browser = getattr(settings, "AI_AUTHORING_DEFAULT_BROWSER", "chrome")
    default_version = getattr(settings, "AI_AUTHORING_DEFAULT_BROWSER_VERSION", "latest")
    session_timeout = getattr(settings, "AI_AUTHORING_SESSION_TIMEOUT", "10m")
    enable_vnc = bool(getattr(settings, "AI_AUTHORING_ENABLE_VNC", True))
    enable_video = bool(getattr(settings, "AI_AUTHORING_ENABLE_VIDEO", False))

    caps = AuthoringBrowserCapabilities(
        browser_name=(browser or default_browser),
        browser_version=default_version,
        enable_vnc=enable_vnc,
        enable_video=enable_video,
        session_timeout=session_timeout,
    )
    return SelenoidWebDriverAuthoringTool(capabilities=caps)


__all__ = [
    "AuthoringBrowserCapabilities",
    "BrowserAuthoringError",
    "BrowserAuthoringTool",
    "SelenoidWebDriverAuthoringTool",
    "build_browser_authoring_tool",
]


# Convenience JSON dumper for places that want to log the capability config.
def capabilities_to_json(caps: AuthoringBrowserCapabilities) -> str:
    return json.dumps(
        {
            "browser_name": caps.browser_name,
            "browser_version": caps.browser_version,
            "platform_name": caps.platform_name,
            "enable_vnc": caps.enable_vnc,
            "enable_video": caps.enable_video,
            "session_timeout": caps.session_timeout,
            "extra_selenoid_options": caps.extra_selenoid_options,
        },
        ensure_ascii=True,
    )
