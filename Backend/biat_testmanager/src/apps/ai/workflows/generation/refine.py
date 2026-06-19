from __future__ import annotations

import json
from typing import Any

from apps.accounts.models import ModelProfilePurpose
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.providers.base import LLMProviderError
from apps.ai.providers.brain import get_team_brain
from apps.ai.workflows.generation.contracts import contract_for_prompt
from apps.ai.workflows.generation.events import append_generation_event
from apps.ai.workflows.generation.nodes._llm import call_llm_json
from apps.ai.workflows.generation.schemas import (
    DRAFT_JSON_SCHEMA,
    DraftValidationError,
    normalize_draft_payload,
)
from apps.ai.workflows.generation.state import CLOUD_GENERATION_LIMITS, LOCAL_GENERATION_LIMITS

REFINE_PROMPT_VERSION = "ai_generation_refine_v1"


def run_draft_refinement(
    session_id: str,
    instruction: str,
    draft_ids: list[str] | None = None,
) -> AIGenerationSession:
    """Apply a reviewer instruction to an existing ready draft via a single LLM patch."""
    session = AIGenerationSession.objects.select_related("team", "project").get(pk=session_id)
    instruction = (instruction or "").strip()
    focus_ids = [str(item) for item in (draft_ids or []) if str(item).strip()]

    base_payload = session.draft_payload if isinstance(session.draft_payload, dict) else {}
    try:
        normalized_base = normalize_draft_payload(base_payload)
    except DraftValidationError:
        normalized_base = base_payload

    try:
        provider = get_team_brain(session.team, purpose=ModelProfilePurpose.TEST_DESIGN)
        limits = LOCAL_GENERATION_LIMITS if provider.name == "ollama" else CLOUD_GENERATION_LIMITS
        messages = build_refine_messages(
            objective=session.objective,
            project_name=session.project.name,
            draft_payload=normalized_base,
            instruction=instruction,
            focus_draft_ids=focus_ids,
        )
        result = call_llm_json(
            provider,
            messages=messages,
            schema=DRAFT_JSON_SCHEMA,
            max_tokens=_limit(limits, "design_max_tokens"),
            retry_max_tokens=_limit(limits, "json_retry_max_tokens"),
            num_ctx=_limit(limits, "num_ctx"),
        )
        refined = normalize_draft_payload(result.payload)
    except (LLMProviderError, DraftValidationError, ValueError) as exc:
        return _restore_ready_with_warning(session, exc)

    session.draft_payload = refined
    session.status = AIGenerationSessionStatus.READY_FOR_REVIEW
    session.input_tokens = int(session.input_tokens or 0) + result.response.input_tokens
    session.output_tokens = int(session.output_tokens or 0) + result.response.output_tokens
    session.duration_ms = int(session.duration_ms or 0) + result.duration_ms
    session.prompt_version = REFINE_PROMPT_VERSION
    session.save(
        update_fields=[
            "draft_payload",
            "status",
            "input_tokens",
            "output_tokens",
            "duration_ms",
            "prompt_version",
            "updated_at",
        ]
    )
    append_generation_event(
        session,
        "draft_refined",
        message="Applied your requested changes to the draft.",
        payload={"focus_count": len(focus_ids)},
    )
    return session


def build_refine_messages(
    *,
    objective: str,
    project_name: str,
    draft_payload: dict[str, Any],
    instruction: str,
    focus_draft_ids: list[str],
) -> list[dict[str, str]]:
    context = {
        "project_name": project_name,
        "objective": objective,
        "generation_contract": contract_for_prompt(),
        "current_draft": draft_payload,
        "focus_draft_ids": focus_draft_ids,
        "reviewer_instruction": instruction,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are refining an existing BIAT test-design draft based on a reviewer's "
                "instruction. Return the COMPLETE updated draft as one JSON object using the same "
                "draft schema and the exact field names and enum values from generation_contract. "
                "Preserve every existing draft_id for scenarios and cases you keep so reviewer "
                "selections stay stable; only add, edit, or remove what the instruction requires. "
                "If focus_draft_ids is non-empty, limit changes to those scenarios/cases and leave "
                "the rest unchanged. Every test step requires action and expected_outcome. Do not "
                "invent URLs, credentials, selectors, or business rules. Return strict JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Reviewer instruction:\n{instruction}\n\n"
                "Refinement context JSON:\n"
                f"{json.dumps(context, ensure_ascii=True, default=str)}"
            ),
        },
    ]


def _restore_ready_with_warning(
    session: AIGenerationSession,
    error: Exception,
) -> AIGenerationSession:
    session.status = AIGenerationSessionStatus.READY_FOR_REVIEW
    session.save(update_fields=["status", "updated_at"])
    append_generation_event(
        session,
        "refine_failed",
        message="Could not apply the requested changes; kept the previous draft.",
        payload={"error": str(error)[:500]},
    )
    return session


def _limit(limits: dict[str, int], key: str) -> int | None:
    try:
        value = int(limits.get(key))
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None
