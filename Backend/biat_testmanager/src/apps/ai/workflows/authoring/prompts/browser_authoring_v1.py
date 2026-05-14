from __future__ import annotations

import json
from typing import Any

from apps.ai.workflows.authoring.schemas import ALLOWED_BROWSER_ACTIONS

BROWSER_AUTHORING_PROMPT_VERSION = "browser_authoring_v1"


def build_browser_next_action_messages(
    *,
    goal: dict[str, Any],
    observation: dict[str, Any],
    trace: list[dict[str, Any]],
    max_steps: int,
) -> list[dict[str, str]]:
    context = {
        "goal": goal,
        "observation": observation,
        "trace": trace[-6:],
        "max_steps": max_steps,
        "allowed_actions": ALLOWED_BROWSER_ACTIONS,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are BIAT TestManager's live browser authoring controller. "
                "Choose exactly one next browser action that advances the saved test "
                "case goal. Use only the allowed action names. Use element_ref/ref values "
                "from observation.interactive_elements; these are Playwright MCP snapshot "
                "refs. Do not invent CSS selectors, legacy Selenium ids, or screen content "
                "that is not visible in the observation. Stop only when the test goal has "
                "been verified. Ask the user only when required data or a manual step "
                "blocks progress.\n\n"
                "Return strict JSON matching the supplied action schema. The browser "
                "trace will later be reviewed and converted to Selenium, so every "
                "action must be concrete and reproducible."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(context, ensure_ascii=True, default=str),
        },
    ]
