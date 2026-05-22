from __future__ import annotations

from typing import Any

BROWSER_TOOL_SCHEMA_VERSION = "browser_action_v2"

ALLOWED_BROWSER_TOOLS = [
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_fill",
    "browser_fill_form",
    "browser_select_option",
    "browser_press_key",
    "browser_wait_for",
    "browser_verify_text_visible",
    "browser_verify_element_visible",
    "browser_verify_value",
    "browser_console_messages",
    "browser_take_screenshot",
    "browser_detect_blocker",
    "browser_finish",
    "browser_ask_user",
]

_FIELD_ARRAY_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["target", "value"],
        "properties": {
            "target": {"type": "string"},
            "element": {"type": "string"},
            "value": {"type": "string"},
        },
    },
}


def _tool_schema(
    tool: str,
    required: list[str] | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["tool", "reason", *(required or [])],
        "properties": {
            "tool": {"enum": [tool]},
            "reason": {"type": "string"},
            **(properties or {}),
        },
        "additionalProperties": False,
    }


BROWSER_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "oneOf": [
        _tool_schema("browser_navigate", ["url"], {"url": {"type": "string"}}),
        _tool_schema(
            "browser_click",
            ["target"],
            {"target": {"type": "string"}, "element": {"type": "string"}},
        ),
        _tool_schema(
            "browser_type",
            ["target", "value"],
            {
                "target": {"type": "string"},
                "element": {"type": "string"},
                "value": {"type": "string"},
                "submit": {"type": "boolean"},
            },
        ),
        _tool_schema(
            "browser_fill",
            ["target", "value"],
            {
                "target": {"type": "string"},
                "element": {"type": "string"},
                "value": {"type": "string"},
            },
        ),
        _tool_schema("browser_fill_form", ["fields"], {"fields": _FIELD_ARRAY_SCHEMA}),
        _tool_schema(
            "browser_select_option",
            ["target", "values"],
            {
                "target": {"type": "string"},
                "element": {"type": "string"},
                "values": {"type": "array", "items": {"type": "string"}},
            },
        ),
        _tool_schema("browser_press_key", ["key"], {"key": {"type": "string"}}),
        _tool_schema(
            "browser_wait_for",
            properties={
                "text": {"type": "string"},
                "textGone": {"type": "string"},
                "urlContains": {"type": "string"},
                "time": {"type": "number"},
            },
        ),
        _tool_schema("browser_verify_text_visible", ["text"], {"text": {"type": "string"}}),
        _tool_schema(
            "browser_verify_element_visible",
            ["target"],
            {"target": {"type": "string"}, "element": {"type": "string"}},
        ),
        _tool_schema(
            "browser_verify_value",
            ["target", "value"],
            {
                "target": {"type": "string"},
                "element": {"type": "string"},
                "value": {"type": "string"},
            },
        ),
        _tool_schema("browser_console_messages", properties={"level": {"type": "string"}}),
        _tool_schema("browser_take_screenshot"),
        _tool_schema("browser_detect_blocker"),
        _tool_schema(
            "browser_finish",
            ["success_evidence"],
            {"success_evidence": {"type": "array", "items": {"type": "string"}}},
        ),
        _tool_schema("browser_ask_user", ["message"], {"message": {"type": "string"}}),
    ],
}

# Backwards-compatible names for current imports. They now point at the V2 tool
# contract; the authoring service intentionally reads ``tool`` not ``action``.
ALLOWED_BROWSER_ACTIONS = ALLOWED_BROWSER_TOOLS
