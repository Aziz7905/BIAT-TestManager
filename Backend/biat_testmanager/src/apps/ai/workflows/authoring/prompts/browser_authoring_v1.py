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
                "case goal. Use only the allowed action names.\n\n"
                "ADDRESSING ELEMENTS — STRICT:\n"
                "- Every interactive element in observation.interactive_elements has a "
                "  `ref` field. Refs are short integer strings like \"1\", \"2\", \"3\".\n"
                "- To target an element, put its ref in the `element_ref` field of the "
                "  action JSON. Example: {\"action\": \"fill\", \"element_ref\": \"3\", "
                "  \"value\": \"Admin\", \"reason\": \"...\"}.\n"
                "- DO NOT put CSS selectors, XPath, attribute selectors, or element "
                "  ids in the action JSON. Strings like \"input[name='username']\", "
                "  \"#login-btn\", or \".submit\" will be rejected.\n"
                "- If you cannot find a matching ref in the latest observation, the "
                "  element is not currently interactable — choose a different action "
                "  or use `ask_user` to escalate.\n\n"
                "OTHER RULES:\n"
                "- Stop only when the test goal has been verified.\n"
                "- Ask the user only when required data or a manual step blocks "
                "  progress.\n\n"
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
