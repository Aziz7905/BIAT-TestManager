from __future__ import annotations

from typing import Any

ALLOWED_BROWSER_ACTIONS = [
    "navigate",
    "click",
    "fill",
    "select",
    "wait",
    "assert_visible",
    "assert_text",
    "stop",
    "ask_user",
]

BROWSER_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["action", "reason"],
    "properties": {
        "action": {"enum": ALLOWED_BROWSER_ACTIONS},
        "reason": {"type": "string"},
        "element_id": {"type": "string"},
        "element_ref": {"type": "string"},
        "ref": {"type": "string"},
        "selector": {"type": "string"},
        "value": {"type": "string"},
        "url": {"type": "string"},
        "assertion": {"type": "string"},
        "success": {"type": "boolean"},
        "message": {"type": "string"},
    },
}
