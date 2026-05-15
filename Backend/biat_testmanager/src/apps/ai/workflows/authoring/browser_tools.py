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
        elif browser == "firefox":
            options = webdriver.FirefoxOptions()
        elif browser == "edge":
            options = webdriver.EdgeOptions()
        else:
            raise BrowserAuthoringError(
                f"Unsupported authoring browser: {browser}. "
                "Configure a Selenoid image first."
            )

        options.set_capability("browserName", "chrome" if browser == "chromium" else browser)
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

// Clear stale refs first so SPA re-renders never leave us pointing at gone nodes.
document.querySelectorAll('[data-biat-ref]').forEach(el => el.removeAttribute('data-biat-ref'));

function isVisible(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  const style = window.getComputedStyle(el);
  return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
}

function elementName(el) {
  return (
    el.getAttribute('aria-label') ||
    el.getAttribute('placeholder') ||
    el.getAttribute('alt') ||
    el.getAttribute('title') ||
    (el.innerText || '').trim().slice(0, 120) ||
    el.getAttribute('name') ||
    el.getAttribute('id') ||
    ''
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
    if (t === 'submit' || t === 'button') return 'button';
    return 'textbox';
  }
  return tag;
}

const elements = [];
let ref = 0;
const nodes = document.querySelectorAll(SELECTOR);
for (const el of nodes) {
  if (!isVisible(el)) continue;
  ref += 1;
  el.setAttribute('data-biat-ref', String(ref));
  const role = elementRole(el);
  const name = elementName(el).replace(/\s+/g, ' ').trim();
  const line = `- ${role}` + (name ? ` "${name}"` : '') + ` [ref=${ref}]`;
  elements.push({
    id: String(ref),
    ref: String(ref),
    role: role,
    name: name.slice(0, 200),
    line: line.slice(0, 300),
  });
  if (elements.length >= 80) break;
}

const bodyText = (document.body && document.body.innerText) || '';
const compactText = bodyText.replace(/\s+/g, ' ').trim().slice(0, 1500);

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

    def observe(self) -> dict[str, Any]:
        driver = self._require_driver()
        try:
            payload = driver.execute_script(_DOM_WALKER_JS)
        except WebDriverException as exc:
            raise BrowserAuthoringError(f"DOM walker failed: {exc}") from exc

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
        action_name = action.get("action")
        started = time.monotonic()

        if action_name == "navigate":
            url = action.get("url") or action.get("value")
            if not url:
                raise BrowserAuthoringError("navigate action requires a url.")
            driver.get(url)
            return _action_result(action_name, url, "Navigation requested.", started)

        if action_name == "wait":
            return self._wait(action, started)

        if action_name == "assert_text":
            return self._assert_text(action, observation, started)

        ref = _resolve_element_ref(action, observation)
        target_attrs = self._capture_target_attrs(ref)

        if action_name == "click":
            element = self._find_by_ref(ref)
            element.click()
            return _action_result(action_name, ref, "Element clicked.", started, target_attrs)

        if action_name == "fill":
            value = action.get("value")
            if value is None:
                raise BrowserAuthoringError("fill action requires value.")
            element = self._find_by_ref(ref)
            try:
                element.clear()
            except WebDriverException:
                pass
            element.send_keys(str(value))
            return _action_result(action_name, ref, "Element filled.", started, target_attrs)

        if action_name == "select":
            value = action.get("value")
            if value is None:
                raise BrowserAuthoringError("select action requires value.")
            element = self._find_by_ref(ref)
            select = Select(element)
            try:
                select.select_by_visible_text(str(value))
            except WebDriverException:
                select.select_by_value(str(value))
            return _action_result(action_name, ref, "Option selected.", started, target_attrs)

        if action_name == "assert_visible":
            element = self._find_by_ref(ref)
            if not element.is_displayed():
                raise AssertionError(f"Element ref is not visible: {ref}")
            return _action_result(action_name, ref, "Element is visible.", started, target_attrs)

        raise BrowserAuthoringError(f"Unsupported browser action: {action_name}")

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
            "role": str(payload.get("role") or ""),
            "text": str(payload.get("text") or "").strip()[:200],
            "placeholder": str(payload.get("placeholder") or ""),
        }

    def _wait(self, action: dict[str, Any], started: float) -> dict[str, Any]:
        driver = self._require_driver()
        text = action.get("assertion") or action.get("value")
        observe_timeout = int(
            getattr(settings, "AI_AUTHORING_OBSERVE_TIMEOUT_SECONDS", 30) or 30
        )

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
            seconds = float(text) if text else 1.0
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
        expected = str(action.get("assertion") or action.get("value") or "").strip()
        if not expected:
            raise BrowserAuthoringError("assert_text requires assertion or value.")

        haystack = (
            observation.get("snapshot")
            or observation.get("visible_text_summary")
            or driver.page_source
            or ""
        )
        if expected.lower() not in str(haystack).lower():
            raise AssertionError(f"Expected text not found on page: {expected}")
        return _action_result("assert_text", expected, "Text present on page.", started)


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
        action.get("element_ref"),
        action.get("ref"),
        action.get("element_id"),
        action.get("selector"),
        action.get("target"),
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
  data_testid: (
    el.getAttribute('data-testid')
    || el.getAttribute('data-test-id')
    || el.getAttribute('data-test')
    || el.getAttribute('data-cy')
    || el.getAttribute('data-qa')
    || ''
  ),
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
