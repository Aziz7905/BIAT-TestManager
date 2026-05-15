"""Translate a passed AI authoring trace into a runnable Selenium Python script.

The trace lives in ``ExecutionStep`` rows captured during the live agent loop in
Selenoid. Each step has:

- ``action`` ∈ {navigate, click, fill, select, wait, assert_visible, assert_text, ask_user}
- ``target_element`` — the session-local ref (e.g. "1") used during authoring
- ``input_value`` — the value for fill/select/assert_text/wait actions
- ``target_attrs`` — durable element identifiers captured at action time
  (id, name, aria_label, data_testid, role, text, tag, type, placeholder)

The translator never touches the database. It is a pure function over the step
rows. The commit service is what persists the resulting script as an
``AutomationScript`` row.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from apps.automation.models import ExecutionStep

INDENT = "    "

# Selenoid issues VNC sessions; this matches the existing runner contract that
# expects BIAT_SELENIUM_GRID_URL on the runner container.
_GRID_ENV_VAR = "BIAT_SELENIUM_GRID_URL"

# Auto-generated id patterns we should never use as a stable selector.
_VOLATILE_ID_PATTERNS = (
    re.compile(r"^__"),                # __vue__, __BVID__, __auto
    re.compile(r"^mui-\d+"),           # MUI auto ids
    re.compile(r"^chakra-"),           # Chakra auto ids
    re.compile(r"^react-aria-\d+"),    # React Aria auto ids
    re.compile(r"^radix-"),            # Radix UI auto ids
    re.compile(r"^[A-Za-z]?:r[0-9a-z]+"),  # React `:r0:`, `:r1a:` ids
    re.compile(r"^[a-f0-9]{8,}-[a-f0-9]{4,}"),  # UUID-ish
)


def render_selenium_python(
    *,
    test_case_title: str,
    target_url: str,
    steps: Iterable[ExecutionStep],
) -> str:
    """Build a complete runnable Selenium Python script for a passed trace."""
    body_lines: list[str] = []
    for step in steps:
        body_lines.extend(_render_step(step))

    if not body_lines:
        body_lines = [f"{INDENT}pass  # No replayable steps."]

    header = _render_header(test_case_title=test_case_title, target_url=target_url)
    footer = _render_footer()
    body = "\n".join(body_lines)
    return f"{header}\n{body}\n{footer}\n"


# ---------------------------------------------------------------------------
# Step rendering
# ---------------------------------------------------------------------------

def _render_step(step: ExecutionStep) -> list[str]:
    action = (step.action or "").strip().lower()
    if action == "navigate":
        return _render_navigate(step)
    if action == "click":
        return _render_click(step)
    if action == "fill":
        return _render_fill(step)
    if action == "select":
        return _render_select(step)
    if action == "wait":
        return _render_wait(step)
    if action == "assert_visible":
        return _render_assert_visible(step)
    if action == "assert_text":
        return _render_assert_text(step)
    if action == "ask_user":
        # ask_user is a manual handoff during live authoring. We cannot replay it
        # automatically; preserve it as a comment so reviewers see the gap.
        return [
            f"{INDENT}# Manual step during AI authoring "
            f"(not auto-replayed): {_escape(step.target_element or '')}"
        ]
    return [f"{INDENT}# Unsupported AI action skipped: {_escape(action)}"]


def _render_navigate(step: ExecutionStep) -> list[str]:
    url = (step.target_element or "").strip()
    if not url:
        return [f"{INDENT}# navigate step has no URL; skipped"]
    return [f"{INDENT}driver.get({_py_str(url)})"]


def _render_click(step: ExecutionStep) -> list[str]:
    by, value = _pick_selector(step.target_attrs or {})
    return [_find_element_line(by, value) + ".click()"]


def _render_fill(step: ExecutionStep) -> list[str]:
    by, value = _pick_selector(step.target_attrs or {})
    text = step.input_value or ""
    locator = _find_element_line(by, value)
    return [
        f"{locator}.clear()",
        f"{locator}.send_keys({_py_str(text)})",
    ]


def _render_select(step: ExecutionStep) -> list[str]:
    by, value = _pick_selector(step.target_attrs or {})
    text = step.input_value or ""
    locator = _find_element_line(by, value)
    return [
        f"{INDENT}_select = Select({locator[len(INDENT):]})",
        f"{INDENT}try:",
        f"{INDENT * 2}_select.select_by_visible_text({_py_str(text)})",
        f"{INDENT}except Exception:",
        f"{INDENT * 2}_select.select_by_value({_py_str(text)})",
    ]


def _render_wait(step: ExecutionStep) -> list[str]:
    value = (step.input_value or step.target_element or "").strip()
    # Numeric wait → time.sleep with safety cap (matches authoring tool cap).
    try:
        seconds = float(value) if value else 1.0
        seconds = max(0.1, min(seconds, 5.0))
        return [f"{INDENT}time.sleep({seconds:.1f})"]
    except ValueError:
        # Text wait → WebDriverWait for body text.
        return [
            f"{INDENT}WebDriverWait(driver, 30).until(",
            f"{INDENT * 2}EC.text_to_be_present_in_element("
            f"(By.TAG_NAME, \"body\"), {_py_str(value)})",
            f"{INDENT})",
        ]


def _render_assert_visible(step: ExecutionStep) -> list[str]:
    by, value = _pick_selector(step.target_attrs or {})
    locator = _find_element_line(by, value)
    return [f"{INDENT}assert {locator[len(INDENT):]}.is_displayed()"]


def _render_assert_text(step: ExecutionStep) -> list[str]:
    text = (step.input_value or step.target_element or "").strip()
    return [
        f"{INDENT}WebDriverWait(driver, 30).until(",
        f"{INDENT * 2}EC.text_to_be_present_in_element("
        f"(By.TAG_NAME, \"body\"), {_py_str(text)})",
        f"{INDENT})",
    ]


# ---------------------------------------------------------------------------
# Selector picker
# ---------------------------------------------------------------------------

def _pick_selector(attrs: dict[str, Any]) -> tuple[str, str]:
    """Pick the best stable selector for an element from captured attrs.

    Order: data-testid → stable id → name → aria-label → text-xpath (for
    buttons/links) → role+name CSS attr → 'body' fallback.
    """
    data_testid = (attrs.get("data_testid") or "").strip()
    if data_testid:
        return "By.CSS_SELECTOR", f'[data-testid="{_escape_attr(data_testid)}"]'

    element_id = (attrs.get("id") or "").strip()
    if element_id and _is_stable_id(element_id):
        return "By.ID", element_id

    name = (attrs.get("name") or "").strip()
    if name:
        return "By.NAME", name

    aria_label = (attrs.get("aria_label") or "").strip()
    if aria_label:
        return "By.CSS_SELECTOR", f'[aria-label="{_escape_attr(aria_label)}"]'

    tag = (attrs.get("tag") or "").strip().lower()
    text = (attrs.get("text") or "").strip()
    if text and tag in {"button", "a", "summary", "label"}:
        return "By.XPATH", f"//{tag}[normalize-space()={_xpath_str(text)}]"

    role = (attrs.get("role") or "").strip()
    if role and text:
        return (
            "By.XPATH",
            f"//*[@role={_xpath_str(role)} and normalize-space()={_xpath_str(text)}]",
        )

    if tag == "input":
        input_type = (attrs.get("type") or "").strip()
        placeholder = (attrs.get("placeholder") or "").strip()
        if placeholder:
            return "By.CSS_SELECTOR", f'input[placeholder="{_escape_attr(placeholder)}"]'
        if input_type:
            return "By.CSS_SELECTOR", f'input[type="{_escape_attr(input_type)}"]'

    if tag:
        return "By.TAG_NAME", tag

    # Fallback: the trace is missing durable attrs. Reviewer will need to fix.
    return "By.TAG_NAME", "body"


def _is_stable_id(value: str) -> bool:
    if not value:
        return False
    for pattern in _VOLATILE_ID_PATTERNS:
        if pattern.match(value):
            return False
    return True


# ---------------------------------------------------------------------------
# Header / footer
# ---------------------------------------------------------------------------

def _render_header(*, test_case_title: str, target_url: str) -> str:
    safe_title = (test_case_title or "AI authored test").strip()
    return (
        '"""\n'
        f"Generated by BIAT AI authoring on Selenoid.\n"
        f"Test case: {safe_title}\n"
        f"Target URL: {target_url or '(unknown)'}\n"
        "Review and edit before running in regression. "
        "The agent's live trace was translated mechanically.\n"
        '"""\n\n'
        "import os\n"
        "import time\n"
        "\n"
        "from selenium import webdriver\n"
        "from selenium.webdriver.common.by import By\n"
        "from selenium.webdriver.support.ui import Select, WebDriverWait\n"
        "from selenium.webdriver.support import expected_conditions as EC\n"
        "\n"
        "\n"
        "def run(driver):"
    )


def _render_footer() -> str:
    return (
        "\n"
        'if __name__ == "__main__":\n'
        f'    hub = os.environ["{_GRID_ENV_VAR}"]\n'
        "    options = webdriver.ChromeOptions()\n"
        "    driver = webdriver.Remote(command_executor=hub, options=options)\n"
        "    try:\n"
        "        run(driver)\n"
        "    finally:\n"
        "        driver.quit()"
    )


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def _find_element_line(by: str, value: str) -> str:
    return f"{INDENT}driver.find_element({by}, {_py_str(value)})"


def _py_str(value: str) -> str:
    """Render a Python string literal safe for any input."""
    if value is None:
        return '""'
    # repr() always returns a Python-valid string literal with proper escaping.
    return repr(str(value))


def _escape_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape(value: str) -> str:
    return (value or "").replace("\n", " ").replace("\r", " ")


def _xpath_str(value: str) -> str:
    """Build an XPath-safe string literal, handling single/double quotes."""
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    # Mixed quotes — use concat().
    parts = value.split("'")
    chunks = ["'" + p + "'" for p in parts]
    return "concat(" + ", \"'\", ".join(chunks) + ")"
