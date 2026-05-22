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

from apps.ai.workflows.authoring.trace_utils import (
    describe_target,
    format_selector,
    selector_candidates as build_selector_candidates,
)
from apps.automation.models import ExecutionStep

INDENT = "    "

# Prefer the BIAT regression runner WebDriver env var; keep the old authoring
# Selenoid env var as a standalone fallback for generated scripts.
_GRID_ENV_VAR = "BIAT_SELENIUM_GRID_URL"
_WEBDRIVER_ENV_VAR = "BIAT_WEBDRIVER_URL"

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
    for step_index, step in enumerate(steps, start=1):
        body_lines.extend(_render_step(step, step_index))

    if not body_lines:
        body_lines = [f"{INDENT}pass  # No replayable steps."]

    header = _render_header(test_case_title=test_case_title, target_url=target_url)
    footer = _render_footer()
    body = "\n".join(body_lines)
    return f"{header}\n{body}\n{footer}\n"


# ---------------------------------------------------------------------------
# Step rendering
# ---------------------------------------------------------------------------

def _render_step(step: ExecutionStep, step_index: int) -> list[str]:
    action = (step.action or "").strip().lower()
    if action == "navigate":
        return _render_navigate(step, step_index)
    if action == "click":
        return _render_click(step, step_index)
    if action == "fill":
        return _render_fill(step, step_index)
    if action == "select":
        return _render_select(step, step_index)
    if action == "wait":
        return _render_wait(step, step_index)
    if action == "assert_visible":
        return _render_assert_visible(step, step_index)
    if action == "assert_text":
        return _render_assert_text(step, step_index)
    if action == "assert_url":
        return _render_assert_url(step, step_index)
    if action == "ask_user":
        # ask_user is a manual handoff during live authoring. We cannot replay it
        # automatically; preserve it as a comment so reviewers see the gap.
        return [
            f"{INDENT}# Manual step during AI authoring "
            f"(not auto-replayed): {_escape(step.target_element or '')}"
        ]
    return [f"{INDENT}# Unsupported AI action skipped: {_escape(action)}"]


def _render_navigate(step: ExecutionStep, step_index: int) -> list[str]:
    url = (step.target_element or "").strip()
    if not url:
        return [f"{INDENT}# navigate step has no URL; skipped"]
    return [
        f"{INDENT}_run_step(",
        f"{INDENT * 2}{step_index}, 'navigate', {_py_str(url)}, '', '',",
        f"{INDENT * 2}lambda: (driver.get({_py_str(url)}), _wait_for_page_ready(driver)),",
        f"{INDENT})",
    ]


def _render_click(step: ExecutionStep, step_index: int) -> list[str]:
    candidate_pairs = _selector_candidates(step.target_attrs or {})
    candidates = _candidate_list(candidate_pairs)
    selector = _candidate_list_for_event(candidate_pairs)
    target = _event_target(step)
    return [
        f"{INDENT}_biat_previous_body_text = _run_step(",
        f"{INDENT * 2}{step_index}, 'click', {_py_str(target)}, {_py_str(selector)}, '',",
        f"{INDENT * 2}lambda: _click_and_wait(driver, {candidates}),",
        f"{INDENT})",
    ]


def _render_fill(step: ExecutionStep, step_index: int) -> list[str]:
    candidate_pairs = _selector_candidates(step.target_attrs or {})
    candidates = _candidate_list(candidate_pairs)
    selector = _candidate_list_for_event(candidate_pairs)
    target = _event_target(step)
    text = step.input_value or ""
    if _is_email_fill(step):
        value_expr = f"_unique_email({_py_str(text)})"
    else:
        value_expr = _py_str(text)
    return [
        f"{INDENT}_run_step(",
        f"{INDENT * 2}{step_index}, 'fill', {_py_str(target)}, {_py_str(selector)}, {_py_str(text)},",
        f"{INDENT * 2}lambda: _fill(driver, {candidates}, {value_expr}),",
        f"{INDENT})",
    ]


def _render_select(step: ExecutionStep, step_index: int) -> list[str]:
    candidate_pairs = _selector_candidates(step.target_attrs or {})
    candidates = _candidate_list(candidate_pairs)
    selector = _candidate_list_for_event(candidate_pairs)
    target = _event_target(step)
    text = step.input_value or ""
    return [
        f"{INDENT}_run_step(",
        f"{INDENT * 2}{step_index}, 'select', {_py_str(target)}, {_py_str(selector)}, {_py_str(text)},",
        f"{INDENT * 2}lambda: (_select_option(driver, {candidates}, {_py_str(text)}), _wait_for_page_ready(driver)),",
        f"{INDENT})",
    ]


def _render_wait(step: ExecutionStep, step_index: int) -> list[str]:
    value = (step.input_value or step.target_element or "").strip()
    # Numeric wait → time.sleep with safety cap (matches authoring tool cap).
    try:
        seconds = float(value) if value else 1.0
        seconds = max(0.1, min(seconds, 5.0))
        return [
            f"{INDENT}_run_step(",
            f"{INDENT * 2}{step_index}, 'wait', {_py_str(value)}, '', {_py_str(value)},",
            f"{INDENT * 2}lambda: (time.sleep({seconds:.1f}), _wait_for_page_ready(driver)),",
            f"{INDENT})",
        ]
    except ValueError:
        # Text wait -> WebDriverWait for body text.
        return [
            f"{INDENT}_run_step(",
            f"{INDENT * 2}{step_index}, 'wait', {_py_str(value)}, '', {_py_str(value)},",
            f"{INDENT * 2}lambda: _wait_for_text(driver, {_py_str(value)}),",
            f"{INDENT})",
        ]


def _render_assert_visible(step: ExecutionStep, step_index: int) -> list[str]:
    candidate_pairs = _selector_candidates(step.target_attrs or {})
    candidates = _candidate_list(candidate_pairs)
    selector = _candidate_list_for_event(candidate_pairs)
    target = _event_target(step)
    return [
        f"{INDENT}_run_step(",
        f"{INDENT * 2}{step_index}, 'assert_visible', {_py_str(target)}, {_py_str(selector)}, '',",
        f"{INDENT * 2}lambda: _assert_visible(driver, {candidates}),",
        f"{INDENT})",
    ]


def _render_assert_text(step: ExecutionStep, step_index: int) -> list[str]:
    text = (step.input_value or step.target_element or "").strip()
    return [
        f"{INDENT}_run_step(",
        f"{INDENT * 2}{step_index}, 'assert_text', {_py_str(text)}, '', {_py_str(text)},",
        f"{INDENT * 2}lambda: _wait_for_new_text(driver, {_py_str(text)}, _biat_previous_body_text),",
        f"{INDENT})",
    ]


def _render_assert_url(step: ExecutionStep, step_index: int) -> list[str]:
    expected = (step.input_value or step.target_element or "").strip()
    prefix = "url contains"
    if expected.lower().startswith(prefix):
        expected = expected[len(prefix) :].lstrip(" :")
    return [
        f"{INDENT}_run_step(",
        f"{INDENT * 2}{step_index}, 'assert_url', {_py_str(expected)}, '', {_py_str(expected)},",
        f"{INDENT * 2}lambda: _wait_for_url_contains(driver, {_py_str(expected)}),",
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
    return _selector_candidates(attrs)[0]


def _selector_candidates(attrs: dict[str, Any]) -> list[tuple[str, str]]:
    return build_selector_candidates(attrs, include_weak=True)


def _is_stable_id(value: str) -> bool:
    if not value:
        return False
    for pattern in _VOLATILE_ID_PATTERNS:
        if pattern.match(value):
            return False
    return True


def _is_email_fill(step: ExecutionStep) -> bool:
    attrs = step.target_attrs or {}
    haystack = " ".join(
        [
            _attr(attrs, "type"),
            _attr(attrs, "id"),
            _attr(attrs, "name"),
            _attr(attrs, "aria_label", "aria-label"),
            _attr(attrs, "placeholder"),
            step.input_value or "",
        ]
    ).lower()
    return "email" in haystack and "@" in (step.input_value or haystack)


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
        "The agent's live trace was translated with resilient Selenium helpers.\n"
        '"""\n\n'
        "import os\n"
        "import time\n"
        "import traceback\n"
        "import uuid\n"
        "\n"
        "from selenium import webdriver\n"
        "try:\n"
        "    from apps.automation import runtime as biat_runtime\n"
        "except Exception:\n"
        "    biat_runtime = None\n"
        "\n"
        "from selenium.common.exceptions import (\n"
        "    NoSuchElementException,\n"
        "    StaleElementReferenceException,\n"
        "    TimeoutException,\n"
        ")\n"
        "from selenium.webdriver.common.by import By\n"
        "from selenium.webdriver.support.ui import Select, WebDriverWait\n"
        "from selenium.webdriver.support import expected_conditions as EC\n"
        "\n"
        "\n"
        "_DEFAULT_TIMEOUT = 30\n"
        "\n"
        "\n"
        "def _wait_for_page_ready(driver, timeout=_DEFAULT_TIMEOUT):\n"
        "    try:\n"
        "        WebDriverWait(driver, timeout).until(\n"
        "            lambda current_driver: current_driver.execute_script(\"return document.readyState\") in {\"interactive\", \"complete\"}\n"
        "        )\n"
        "    except Exception:\n"
        "        # Some pages or drivers do not expose readyState reliably.\n"
        "        pass\n"
        "\n"
        "\n"
        "def _wait_for_any(driver, candidates, *, require_visible=False, require_enabled=False, timeout=_DEFAULT_TIMEOUT):\n"
        "    if not candidates:\n"
        "        candidates = [(By.TAG_NAME, \"body\")]\n"
        "\n"
        "    def locate(current_driver):\n"
        "        for by, value in candidates:\n"
        "            try:\n"
        "                element = current_driver.find_element(by, value)\n"
        "                if require_visible and not element.is_displayed():\n"
        "                    continue\n"
        "                if require_enabled and not element.is_enabled():\n"
        "                    continue\n"
        "                return element\n"
        "            except (NoSuchElementException, StaleElementReferenceException):\n"
        "                continue\n"
        "        return False\n"
        "\n"
        "    try:\n"
        "        return WebDriverWait(driver, timeout).until(locate)\n"
        "    except TimeoutException as exc:\n"
        "        locators = \", \".join(f\"{by}={value}\" for by, value in candidates)\n"
        "        raise AssertionError(\n"
        "            f\"Could not locate element using any selector: {locators}\"\n"
        "        ) from exc\n"
        "\n"
        "\n"
        "def _scroll_into_view(driver, element):\n"
        "    try:\n"
        "        driver.execute_script(\n"
        "            \"arguments[0].scrollIntoView({block: 'center', inline: 'center'});\",\n"
        "            element,\n"
        "        )\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "\n"
        "def _click(driver, candidates):\n"
        "    element = _wait_for_any(driver, candidates, require_visible=True, require_enabled=True)\n"
        "    _scroll_into_view(driver, element)\n"
        "    try:\n"
        "        element.click()\n"
        "    except Exception:\n"
        "        element = _wait_for_any(driver, candidates, require_visible=True, require_enabled=True)\n"
        "        _scroll_into_view(driver, element)\n"
        "        driver.execute_script(\"arguments[0].click();\", element)\n"
        "\n"
        "\n"
        "def _fill(driver, candidates, value):\n"
        "    element = _wait_for_any(driver, candidates, require_visible=True, require_enabled=True)\n"
        "    _scroll_into_view(driver, element)\n"
        "    try:\n"
        "        element.clear()\n"
        "    except Exception:\n"
        "        driver.execute_script(\"arguments[0].value = '';\", element)\n"
        "    element.send_keys(str(value))\n"
        "\n"
        "\n"
        "def _select_option(driver, candidates, value):\n"
        "    element = _wait_for_any(driver, candidates, require_visible=True, require_enabled=True)\n"
        "    _scroll_into_view(driver, element)\n"
        "    select = Select(element)\n"
        "    try:\n"
        "        select.select_by_visible_text(str(value))\n"
        "    except Exception:\n"
        "        select.select_by_value(str(value))\n"
        "\n"
        "\n"
        "def _assert_visible(driver, candidates):\n"
        "    element = _wait_for_any(driver, candidates, require_visible=True)\n"
        "    assert element.is_displayed()\n"
        "\n"
        "\n"
        "def _wait_for_text(driver, text, timeout=_DEFAULT_TIMEOUT):\n"
        "    WebDriverWait(driver, timeout).until(\n"
        "        EC.text_to_be_present_in_element((By.TAG_NAME, \"body\"), str(text))\n"
        "    )\n"
        "\n"
        "\n"
        "def _body_text(driver):\n"
        "    try:\n"
        "        return driver.find_element(By.TAG_NAME, \"body\").text or \"\"\n"
        "    except Exception:\n"
        "        return \"\"\n"
        "\n"
        "\n"
        "def _wait_for_new_text(driver, text, previous_body_text, timeout=_DEFAULT_TIMEOUT):\n"
        "    expected = str(text)\n"
        "    if expected.lower() in str(previous_body_text or \"\").lower():\n"
        "        print(\n"
        "            f\"Skipping pre-existing text assertion because it was visible before the previous action: {expected!r}\"\n"
        "        )\n"
        "        return\n"
        "    _wait_for_text(driver, expected, timeout)\n"
        "\n"
        "\n"
        "def _wait_for_url_contains(driver, text, timeout=_DEFAULT_TIMEOUT):\n"
        "    expected = str(text)\n"
        "    WebDriverWait(driver, timeout).until(\n"
        "        lambda current_driver: expected.lower() in current_driver.current_url.lower()\n"
        "    )\n"
        "\n"
        "\n"
        "def _unique_email(seed):\n"
        "    local, separator, domain = str(seed or \"\").partition(\"@\")\n"
        "    domain = domain if separator and domain else \"example.com\"\n"
        "    prefix = \"\".join(ch for ch in local if ch.isalnum())[:20] or \"biat\"\n"
        "    return f\"{prefix}-{uuid.uuid4().hex[:10]}@{domain}\"\n"
        "\n"
        "\n"
        "def _create_driver():\n"
        f"    if biat_runtime is not None and os.environ.get(\"{_WEBDRIVER_ENV_VAR}\"):\n"
        "        return biat_runtime.create_driver()\n"
        "\n"
        f"    hub = os.environ.get(\"{_WEBDRIVER_ENV_VAR}\") or os.environ.get(\"{_GRID_ENV_VAR}\")\n"
        "    if not hub:\n"
        "        raise RuntimeError(\n"
        f"            \"{_WEBDRIVER_ENV_VAR} is not set. Run this script through the BIAT automation runner \"\n"
        f"            \"or configure {_GRID_ENV_VAR} for standalone execution.\"\n"
        "        )\n"
        "    options = webdriver.ChromeOptions()\n"
        "    return webdriver.Remote(command_executor=hub, options=options)\n"
        "\n"
        "\n"
        "def _report_step_started(step_index, action, target, selector, input_value):\n"
        "    if biat_runtime is None:\n"
        "        return\n"
        "    try:\n"
        "        biat_runtime.report_step_started(\n"
        "            step_index=step_index,\n"
        "            action=action,\n"
        "            target_element=target,\n"
        "            selector_used=selector,\n"
        "            input_value=input_value,\n"
        "        )\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "\n"
        "def _report_step_passed(step_index, started):\n"
        "    if biat_runtime is None:\n"
        "        return\n"
        "    try:\n"
        "        biat_runtime.report_step_passed(\n"
        "            step_index=step_index,\n"
        "            duration_ms=int((time.monotonic() - started) * 1000),\n"
        "        )\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "\n"
        "def _report_step_failed(step_index, started, exc):\n"
        "    if biat_runtime is None:\n"
        "        return\n"
        "    try:\n"
        "        biat_runtime.report_step_failed(\n"
        "            step_index=step_index,\n"
        "            error_message=str(exc),\n"
        "            stack_trace=traceback.format_exc(),\n"
        "            duration_ms=int((time.monotonic() - started) * 1000),\n"
        "        )\n"
        "    except Exception:\n"
        "        pass\n"
        "\n"
        "\n"
        "def _run_step(step_index, action, target, selector, input_value, operation):\n"
        "    started = time.monotonic()\n"
        "    _report_step_started(step_index, action, target, selector, input_value)\n"
        "    try:\n"
        "        result = operation()\n"
        "    except Exception as exc:\n"
        "        _report_step_failed(step_index, started, exc)\n"
        "        raise\n"
        "    _report_step_passed(step_index, started)\n"
        "    return result\n"
        "\n"
        "\n"
        "def _click_and_wait(driver, candidates):\n"
        "    previous_body_text = _body_text(driver)\n"
        "    _click(driver, candidates)\n"
        "    _wait_for_page_ready(driver)\n"
        "    return previous_body_text\n"
        "\n"
        "\n"
        "def run(driver):\n"
        f"{INDENT}_biat_previous_body_text = \"\""
    )


def _render_footer() -> str:
    return (
        "\n"
        'if __name__ == "__main__":\n'
        "    driver = _create_driver()\n"
        "    try:\n"
        "        run(driver)\n"
        "    finally:\n"
        "        driver.quit()"
    )


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def _candidate_list(candidates: list[tuple[str, str]]) -> str:
    rendered = ", ".join(f"({by}, {_py_str(value)})" for by, value in candidates)
    return f"[{rendered}]"


def _candidate_list_for_event(candidates: list[tuple[str, str]]) -> str:
    return ", ".join(format_selector(candidate) for candidate in candidates)


def _event_target(step: ExecutionStep) -> str:
    return describe_target(step.target_attrs or {}, fallback=step.target_element or "current page")


def _attr(attrs: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = attrs.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return ""


def _normalise_space(value: str) -> str:
    return " ".join(str(value or "").split())


def _field_name(value: str) -> str:
    if not value:
        return ""
    if "[" in value and value.endswith("]"):
        value = value.rsplit("[", 1)[-1].rstrip("]")
    return _normalise_space(value.replace("_", " ").replace("-", " "))


def _dedupe_candidates(candidates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


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
