from __future__ import annotations

import json
import re
from typing import Any

from apps.ai.workflows.authoring.schemas import ALLOWED_BROWSER_TOOLS
from apps.ai.workflows.authoring.success import (
    has_post_auth_objective,
    post_auth_objective_terms,
)

BROWSER_AUTHORING_PROMPT_VERSION = "browser_authoring_v2"
_MAX_VISIBLE_TEXT_CHARS = 900
_MAX_SNAPSHOT_CHARS = 1600
_MAX_ELEMENT_COUNT = 40
_MAX_TRACE_COUNT = 5


def build_browser_next_action_messages(
    *,
    goal: dict[str, Any],
    observation: dict[str, Any],
    trace: list[dict[str, Any]],
    max_steps: int,
) -> list[dict[str, str]]:
    context = {
        "goal": _compact_goal(goal),
        "observation": _compact_observation(observation),
        "trace": _compact_trace(trace),
        "state_guidance": _state_guidance(goal, observation, trace),
        "max_steps": max_steps,
        "allowed_tools": ALLOWED_BROWSER_TOOLS,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are BIAT TestManager's live Selenium browser authoring "
                "controller. Choose exactly one BIAT browser tool call that "
                "advances the saved test case objective.\n\n"
                "TOOL CALL RULES:\n"
                "- Return exactly one strict JSON object with top-level fields "
                "`tool` and `reason`.\n"
                "- Use only tools listed in allowed_tools.\n"
                "- Target elements only by `target`, using exact refs from "
                "observation.interactive_elements. Refs are short strings like "
                "\"1\", \"2\", \"3\".\n"
                "- The `element` field is only a human-readable description for "
                "review; it is not a selector.\n"
                "- Do not invent CSS selectors, XPath, ids, or attributes.\n\n"
                "BROWSER TOOL GUIDANCE:\n"
                "- A fresh browser snapshot is already provided in `observation` "
                "before every decision. Do not ask for another snapshot as your "
                "tool call; choose an action, wait, verify, ask the user, or finish.\n"
                "- Prefer `browser_fill_form` when filling related fields in the "
                "same form, such as username and password.\n"
                "- For `browser_fill_form`, always include a non-empty `fields` "
                "array. Each field must include `target` and `value`; take values "
                "from goal.test_data when available.\n"
                "- Use `browser_click` for buttons, links, checkboxes, and "
                "menu items.\n"
                "- Do not repeat a passed fill/fill_form for the same target "
                "refs and values. Once fields are filled, choose the next "
                "transition action such as clicking Submit/Login/Continue/Save, "
                "waiting for a transition, or verifying the expected state.\n"
                "- If state_guidance recommends next tools or submit candidates, "
                "follow it unless the current observation clearly contradicts it.\n"
                "- Use `browser_select_option` for native select elements.\n"
                "- Use `browser_wait_for` only for a concrete wait condition: "
                "`text`, `textGone`, `urlContains`, or a short `time`.\n"
                "- Use verification tools after important transitions: "
                "`browser_verify_text_visible`, `browser_verify_element_visible`, "
                "or `browser_verify_value`.\n"
                "- For `browser_verify_text_visible`, always include a concrete "
                "non-empty `text` value, for example "
                "{\"tool\":\"browser_verify_text_visible\",\"text\":\"Dashboard\","
                "\"reason\":\"Dashboard is visible.\"}. Do not put "
                "\"current page\" or \"body\" in `target` as a substitute.\n"
                "- For element tools, `target` must be an exact visible ref from "
                "the latest snapshot. For text verification, use `text`, not "
                "`target`.\n"
                "- If CAPTCHA, MFA, OTP, Cloudflare, or a human verification gate "
                "blocks progress, use `browser_ask_user` with a clear message.\n"
                "- Use `browser_finish` only when the objective is satisfied and "
                "you can cite success_evidence visible in the current observation.\n\n"
                "QUALITY RULES:\n"
                "- If the objective contains work after login/sign-in, treat login "
                "as a milestone only. Continue until the post-login objective is "
                "also satisfied.\n"
                "- Do not finish on a page that merely still shows the starting "
                "form.\n"
                "- Do not assert text that existed before the previous action "
                "unless it is the objective success signal.\n"
                "- If the latest observation does not contain the needed ref, do "
                "not guess; wait, choose a visible alternative, or ask the user.\n"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(context, ensure_ascii=True, default=str),
        },
    ]


def _compact_goal(goal: dict[str, Any]) -> dict[str, Any]:
    steps = goal.get("steps") if isinstance(goal.get("steps"), list) else []
    return {
        "title": _truncate(goal.get("title"), 200),
        "preconditions": _truncate(goal.get("preconditions"), 350),
        "expected_result": _truncate(goal.get("expected_result"), 300),
        "test_data": goal.get("test_data") or {},
        "steps": [_compact_goal_step(step) for step in steps[:6] if isinstance(step, dict)],
    }


def _compact_goal_step(step: dict[str, Any]) -> dict[str, str]:
    return {
        "action": _truncate(
            step.get("action") or step.get("step") or step.get("description"),
            180,
        ),
        "expected": _truncate(
            step.get("expected_outcome") or step.get("expected") or step.get("expected_result"),
            180,
        ),
    }


def _compact_observation(observation: dict[str, Any]) -> dict[str, Any]:
    elements = []
    for element in observation.get("interactive_elements") or []:
        if not isinstance(element, dict):
            continue
        elements.append(_compact_element(element))
        if len(elements) >= _MAX_ELEMENT_COUNT:
            break

    return {
        "current_url": _truncate(observation.get("current_url"), 300),
        "page_title": _truncate(observation.get("page_title"), 180),
        "visible_text_summary": _truncate(
            observation.get("visible_text_summary"),
            _MAX_VISIBLE_TEXT_CHARS,
        ),
        "text_facts": _extract_text_facts(observation),
        "snapshot": _truncate(observation.get("snapshot"), _MAX_SNAPSHOT_CHARS),
        "interactive_elements": elements,
    }


def _compact_element(element: dict[str, Any]) -> dict[str, Any]:
    attrs = element.get("target_attrs") if isinstance(element.get("target_attrs"), dict) else {}
    compact_attrs = {
        key: _truncate(attrs.get(key), 120)
        for key in ("tag", "type", "id", "name", "aria_label", "placeholder", "text")
        if attrs.get(key)
    }
    return {
        "ref": str(element.get("ref") or element.get("id") or ""),
        "role": _truncate(element.get("role"), 60),
        "name": _truncate(element.get("name"), 140),
        "value": _truncate(element.get("value"), 120),
        "placeholder": _truncate(element.get("placeholder"), 120),
        "disabled": bool(element.get("disabled")),
        "checked": bool(element.get("checked")),
        "selected": bool(element.get("selected")),
        "target_attrs": compact_attrs,
        "line": _truncate(element.get("line"), 220),
    }


def _compact_trace(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for event in trace[-_MAX_TRACE_COUNT:]:
        if not isinstance(event, dict):
            continue
        compact.append(
            _drop_empty(
                {
                "tool": event.get("tool") or event.get("action") or "",
                "status": event.get("status") or "",
                "target": _truncate(event.get("target"), 160),
                "reason": _truncate(event.get("reason"), 160),
                "error": _truncate(event.get("error") or event.get("message"), 240),
                "fields": _compact_trace_fields(event),
                }
            )
        )
    return compact


def _state_guidance(
    goal: dict[str, Any],
    observation: dict[str, Any],
    trace: list[dict[str, Any]],
) -> dict[str, Any]:
    completed_fills = _completed_fill_fields(trace)
    submit_candidates = _submit_candidates(observation)
    guidance: dict[str, Any] = {}

    if completed_fills:
        guidance["completed_fills"] = completed_fills[:8]
        guidance["do_not_repeat_targets"] = sorted(
            {
                field["target"]
                for field in completed_fills
                if field.get("target")
            }
        )
        guidance["recommended_next_tools"] = [
            "browser_click",
            "browser_wait_for",
            "browser_verify_text_visible",
            "browser_finish",
        ]
        guidance["instruction"] = (
            "The listed fields are already filled. Do not fill them again. "
            "Choose a transition action, then wait or verify the expected state."
        )

    if submit_candidates:
        guidance["submit_candidates"] = submit_candidates[:5]
        if completed_fills:
            guidance["instruction"] = (
                f"{guidance['instruction']} Prefer browser_click on one visible "
                "submit candidate if it matches the objective."
            )

    if has_post_auth_objective(goal):
        terms = list(post_auth_objective_terms(goal))
        guidance["post_auth_objective"] = {
            "terms": terms,
            "instruction": (
                "Do not stop immediately after login. Login is only a milestone; "
                "continue with the visible navigation/actions needed for these "
                "post-login objective terms."
            ),
        }
        guidance["recommended_next_tools"] = [
            "browser_click",
            "browser_wait_for",
            "browser_verify_text_visible",
            "browser_verify_element_visible",
            "browser_finish",
        ]

    return guidance


def _extract_text_facts(observation: dict[str, Any]) -> list[dict[str, str]]:
    source = "\n".join(
        str(part or "")
        for part in (
            observation.get("visible_text_summary"),
            observation.get("snapshot"),
        )
    )
    facts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    pattern = re.compile(
        r"\b([A-Za-z][A-Za-z0-9 _/\-]{1,40})\s*[:=]\s*"
        r"([^\n\r:=]{1,80}?)(?=\s+[A-Za-z][A-Za-z0-9 _/\-]{1,40}\s*[:=]|\n|$)"
    )
    for match in pattern.finditer(source):
        key = " ".join(match.group(1).split())
        value = " ".join(match.group(2).split())
        if not key or not value:
            continue
        signature = (key.lower(), value.lower())
        if signature in seen:
            continue
        seen.add(signature)
        facts.append({"label": _truncate(key, 60), "value": _truncate(value, 100)})
        if len(facts) >= 8:
            break
    return facts


def _completed_fill_fields(trace: list[dict[str, Any]]) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for event in trace:
        if not isinstance(event, dict):
            continue
        if str(event.get("status") or "").lower() != "passed":
            continue
        action = str(event.get("action") or event.get("tool") or "").lower()
        event_fields: list[Any] = []
        if action in {"fill_form", "browser_fill_form"}:
            if isinstance(event.get("fields"), list):
                event_fields.extend(event["fields"])
            if isinstance(event.get("field_results"), list):
                event_fields.extend(
                    result.get("field")
                    for result in event["field_results"]
                    if isinstance(result, dict)
                )
        elif action in {"fill", "browser_fill", "browser_type"}:
            event_fields.append(
                {
                    "target": event.get("target") or "",
                    "element": event.get("element") or event.get("target") or "",
                    "value": event.get("value") or "",
                }
            )

        for field in event_fields:
            if not isinstance(field, dict):
                continue
            target = _truncate(field.get("target"), 40)
            value = str(field.get("value") or "")
            if not target or not value:
                continue
            signature = (target, value)
            if signature in seen:
                continue
            seen.add(signature)
            fields.append(
                {
                    "target": target,
                    "element": _truncate(field.get("element"), 100),
                    "value": _truncate(_mask_if_secret(field, value), 120),
                }
            )
    return fields


def _submit_candidates(observation: dict[str, Any]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    transition_words = (
        "login",
        "log in",
        "sign in",
        "submit",
        "continue",
        "next",
        "save",
        "create",
        "register",
        "send",
        "search",
        "confirm",
    )
    for element in observation.get("interactive_elements") or []:
        if not isinstance(element, dict):
            continue
        ref = str(element.get("ref") or element.get("id") or "")
        if not ref or element.get("disabled"):
            continue
        role = str(element.get("role") or "").lower()
        name = str(element.get("name") or "")
        line = str(element.get("line") or "")
        attrs = element.get("target_attrs") if isinstance(element.get("target_attrs"), dict) else {}
        text = " ".join(
            str(part or "")
            for part in (
                role,
                name,
                line,
                attrs.get("text"),
                attrs.get("type"),
                attrs.get("name"),
                attrs.get("id"),
            )
        ).lower()
        is_transition_role = role in {"button", "link", "menuitem", "tab"}
        is_transition_input = "submit" in text or "button" in text
        if not (is_transition_role or is_transition_input):
            continue
        if not any(word in text for word in transition_words):
            continue
        candidates.append(
            {
                "target": ref,
                "element": _truncate(name or attrs.get("text") or line, 120),
                "role": _truncate(role, 40),
            }
        )
    return candidates


def _compact_trace_fields(event: dict[str, Any]) -> list[dict[str, str]]:
    fields = event.get("fields")
    if not isinstance(fields, list):
        field_results = event.get("field_results")
        if isinstance(field_results, list):
            fields = [
                result.get("field")
                for result in field_results
                if isinstance(result, dict) and isinstance(result.get("field"), dict)
            ]
    if not isinstance(fields, list):
        return []

    compact_fields = []
    for field in fields[:6]:
        if not isinstance(field, dict):
            continue
        value = str(field.get("value") or "")
        compact_fields.append(
            {
                "target": _truncate(field.get("target"), 40),
                "element": _truncate(field.get("element"), 100),
                "value": _truncate(_mask_if_secret(field, value), 120),
            }
        )
    return compact_fields


def _mask_if_secret(field: dict[str, Any], value: str) -> str:
    haystack = " ".join(
        str(field.get(key) or "").lower()
        for key in ("element", "target", "name", "label")
    )
    if "password" in haystack or "secret" in haystack or "token" in haystack:
        return "********"
    return value


def _drop_empty(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value not in ("", [], {}, None)
    }


def _truncate(value: Any, limit: int) -> str:
    text = str(value or "").replace("\x00", "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
