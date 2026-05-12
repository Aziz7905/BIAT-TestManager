from __future__ import annotations

import json
from typing import Any

CRITIC_PROMPT_VERSION = "test_critic_v1"


def build_test_critic_messages(
    *,
    objective: str,
    draft_payload: dict[str, Any],
    rag_context: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are BIAT TestManager's test-design critic. Review the draft for "
                "duplicate tests, missing negative/edge coverage, weak expected "
                "results, unsupported claims, unclear preconditions, and inconsistent "
                "priority/type/polarity. Return a JSON object with two keys: "
                "critic_report and draft_payload. The draft_payload must keep the same "
                "schema as the original draft and may include small fixes only."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "objective": objective,
                    "draft_payload": draft_payload,
                    "rag_context": rag_context,
                    "repository_memory": repository_memory,
                },
                ensure_ascii=True,
                default=str,
            ),
        },
    ]
