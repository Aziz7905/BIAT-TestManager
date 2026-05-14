from __future__ import annotations

import json
import time
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.providers.base import LLMProvider, parse_json_content
from apps.ai.providers.brain import get_team_brain
from apps.ai.services.capacity import check_ai_generation_capacity
from apps.ai.workflows.generation.context import retrieve_generation_context
from apps.ai.workflows.generation.prompts import (
    CRITIC_PROMPT_VERSION,
    DESIGN_PROMPT_VERSION,
    EXTRACTION_PROMPT_VERSION,
    REQUIREMENT_EXTRACTION_SCHEMA,
    build_requirement_extraction_messages,
    build_test_critic_messages,
    build_test_design_messages,
    empty_requirement_extraction,
    normalize_requirement_extraction,
)
from apps.ai.workflows.generation.quality import (
    evaluate_draft_quality,
    format_quality_repair_instruction,
)
from apps.ai.workflows.generation.repository_memory import search_repository_memory
from apps.ai.workflows.generation.schemas import (
    ALLOWED_SCENARIO_TYPES,
    DRAFT_JSON_SCHEMA,
    SCHEMA_VERSION,
    normalize_draft_payload,
)
from apps.ai.workflows.generation.state import (
    CLOUD_GENERATION_LIMITS,
    LOCAL_GENERATION_LIMITS,
    LLMJSONResult,
    TestGenerationState,
)


def request_gate(state: TestGenerationState) -> TestGenerationState:
    session = AIGenerationSession.objects.select_related(
        "team",
        "project",
        "project__team",
        "target_suite",
        "target_suite__project",
        "target_section",
        "target_section__suite",
        "target_section__suite__project",
        "attached_specification",
        "attached_specification__project",
        "created_by",
    ).get(pk=state["session_id"])

    if session.project.team_id != session.team_id:
        raise ValueError("AI generation project must belong to the session team.")
    if session.target_suite_id and session.target_suite.project_id != session.project_id:
        raise ValueError("Target suite must belong to the selected project.")
    if session.target_section_id:
        section = session.target_section
        if section.suite.project_id != session.project_id:
            raise ValueError("Target section must belong to the selected project.")
        if session.target_suite_id and section.suite_id != session.target_suite_id:
            raise ValueError("Target section must belong to the selected suite.")
    if (
        session.attached_specification_id
        and session.attached_specification.project_id != session.project_id
    ):
        raise ValueError("Attached specification must belong to the selected project.")

    session.status = AIGenerationSessionStatus.GENERATING
    session.started_at = timezone.now()
    session.error_message = ""
    session.save(update_fields=["status", "started_at", "error_message", "updated_at"])
    state["session"] = session
    return state


def brain_resolver(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    provider = get_team_brain(session.team, purpose=ModelProfilePurpose.TEST_DESIGN)
    state["provider"] = provider
    state["provider_name"] = provider.name
    state["model_name"] = provider.model_name
    state["generation_limits"] = (
        LOCAL_GENERATION_LIMITS
        if provider.name == "ollama"
        else CLOUD_GENERATION_LIMITS
    )

    session.provider_name = provider.name
    session.model_name = provider.model_name
    session.purpose = ModelProfilePurpose.TEST_DESIGN
    session.prompt_version = DESIGN_PROMPT_VERSION
    session.schema_version = SCHEMA_VERSION
    session.save(
        update_fields=[
            "provider_name",
            "model_name",
            "purpose",
            "prompt_version",
            "schema_version",
            "updated_at",
        ]
    )
    return state


def capacity_check(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    check_ai_generation_capacity(session.team, exclude_session_id=str(session.id))
    return state


def context_retrieval(state: TestGenerationState) -> TestGenerationState:
    limits = state.get("generation_limits", CLOUD_GENERATION_LIMITS)
    state["rag_context"] = retrieve_generation_context(
        state["session"],
        top_k=int(limits.get("rag_top_k") or CLOUD_GENERATION_LIMITS["rag_top_k"]),
        max_content_chars=int(
            limits.get("max_chunk_chars") or CLOUD_GENERATION_LIMITS["max_chunk_chars"]
        ),
    )
    return state


def repository_memory_search(state: TestGenerationState) -> TestGenerationState:
    state["repository_memory"] = search_repository_memory(state["session"], limit=8)
    return state


def intent_normalizer(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    state["normalized_intent"] = {
        "objective": session.objective,
        "source_type": session.source_type,
        "platform": "web",
        "target_suite_id": str(session.target_suite_id) if session.target_suite_id else None,
        "target_section_id": (
            str(session.target_section_id) if session.target_section_id else None
        ),
        "has_spec_context": bool(state.get("rag_context")),
        "has_repository_memory": bool(state.get("repository_memory")),
    }
    return state


def requirement_extraction(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    messages = build_requirement_extraction_messages(
        objective=session.objective,
        project_name=session.project.name,
        rag_context=state.get("rag_context", []),
        repository_memory=state.get("repository_memory", []),
    )
    result = _call_llm_json(
        state["provider"],
        messages=messages,
        schema=REQUIREMENT_EXTRACTION_SCHEMA,
        max_tokens=_limit_value(state, "extraction_max_tokens"),
        num_ctx=_limit_value(state, "num_ctx"),
    )
    _accumulate_usage(state, result)
    state["requirement_extraction"] = normalize_requirement_extraction(result.payload)
    return state


def test_design_generator(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    messages = build_test_design_messages(
        objective=session.objective,
        project_name=session.project.name,
        target_suite_name=session.target_suite.name if session.target_suite_id else None,
        target_section_name=session.target_section.name if session.target_section_id else None,
        normalized_intent=state.get("normalized_intent", {}),
        requirement_extraction=state.get("requirement_extraction", empty_requirement_extraction()),
        rag_context=state.get("rag_context", []),
        repository_memory=state.get("repository_memory", []),
        generation_limits=state.get("generation_limits", CLOUD_GENERATION_LIMITS),
        allowed_scenario_types=sorted(ALLOWED_SCENARIO_TYPES),
        jira_issue_key=session.jira_issue_key,
    )
    result = _call_llm_json(
        state["provider"],
        messages=messages,
        schema=DRAFT_JSON_SCHEMA,
        allow_invalid_json=True,
        max_tokens=_limit_value(state, "design_max_tokens"),
        num_ctx=_limit_value(state, "num_ctx"),
    )
    _accumulate_usage(state, result)
    state["raw_draft_payload"] = result.payload
    return state


def draft_schema_validator(state: TestGenerationState) -> TestGenerationState:
    try:
        state["draft_payload"] = _attach_repository_duplicates(
            _attach_requirement_extraction(
                normalize_draft_payload(state["raw_draft_payload"]),
                state.get("requirement_extraction", {}),
            ),
            state.get("repository_memory", []),
        )
        state.pop("validation_error", None)
    except Exception as exc:
        state["validation_error"] = str(exc)
    return state


def draft_repair(state: TestGenerationState) -> TestGenerationState:
    if not state.get("validation_error"):
        return state

    instruction = (
        "Repair the supplied draft so it validates against BIAT's test generation "
        "schema. Return only the repaired draft JSON object."
    )
    return _repair_draft(state, instruction=instruction, error_message=state["validation_error"])


def draft_quality_gate(state: TestGenerationState) -> TestGenerationState:
    if not state.get("draft_payload"):
        return state
    result = evaluate_draft_quality(
        state["draft_payload"],
        state.get("requirement_extraction", {}),
        source_context_count=len(state.get("rag_context") or []),
    )
    state["quality_warnings"] = result.warnings
    if result.should_repair:
        state["quality_repair_instruction"] = format_quality_repair_instruction(result)
    else:
        state.pop("quality_repair_instruction", None)
    return state


def quality_repair(state: TestGenerationState) -> TestGenerationState:
    instruction = state.get("quality_repair_instruction")
    if not instruction:
        return state
    try:
        _repair_draft(state, instruction=instruction, error_message="")
        result = evaluate_draft_quality(
            state["draft_payload"],
            state.get("requirement_extraction", {}),
            source_context_count=len(state.get("rag_context") or []),
        )
        state["quality_warnings"] = result.warnings
    except Exception as exc:
        warnings = list(state.get("quality_warnings") or [])
        warnings.append(f"Quality repair failed: {exc}")
        state["quality_warnings"] = warnings
    return state


def _repair_draft(
    state: TestGenerationState,
    *,
    instruction: str,
    error_message: str = "",
) -> TestGenerationState:
    messages = [
        {
            "role": "system",
            "content": instruction,
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "validation_error": error_message,
                    "requirement_extraction": state.get("requirement_extraction", {}),
                    "generation_limits": state.get("generation_limits", CLOUD_GENERATION_LIMITS),
                    "draft_payload": state.get("draft_payload")
                    or state.get("raw_draft_payload", {}),
                },
                ensure_ascii=True,
                default=str,
            ),
        },
    ]
    result = _call_llm_json(
        state["provider"],
        messages=messages,
        schema=DRAFT_JSON_SCHEMA,
        max_tokens=_limit_value(state, "repair_max_tokens"),
        num_ctx=_limit_value(state, "num_ctx"),
    )
    _accumulate_usage(state, result)
    state["raw_draft_payload"] = result.payload
    state["draft_payload"] = _attach_repository_duplicates(
        _attach_requirement_extraction(
            normalize_draft_payload(result.payload),
            state.get("requirement_extraction", {}),
        ),
        state.get("repository_memory", []),
    )
    state.pop("validation_error", None)
    return state


def test_critic(state: TestGenerationState) -> TestGenerationState:
    if not getattr(settings, "AI_GENERATION_ENABLE_CRITIC", False):
        state["critic_report"] = {
            "status": "critic_skipped",
            "reason": "Critic is disabled by default to avoid blocking review on extra LLM calls.",
        }
        return state
    messages = build_test_critic_messages(
        objective=state["session"].objective,
        draft_payload=state["draft_payload"],
        rag_context=state.get("rag_context", []),
        repository_memory=state.get("repository_memory", []),
    )
    try:
        result = _call_llm_json(
            state["provider"],
            messages=messages,
            schema={
                "type": "object",
                "required": ["critic_report", "draft_payload"],
                "properties": {
                    "critic_report": {"type": "object"},
                    "draft_payload": DRAFT_JSON_SCHEMA,
                },
            },
            max_tokens=_limit_value(state, "critic_max_tokens"),
            num_ctx=_limit_value(state, "num_ctx"),
        )
        _accumulate_usage(state, result)
        critic_payload = result.payload
        if isinstance(critic_payload.get("draft_payload"), dict):
            state["draft_payload"] = _attach_repository_duplicates(
                _attach_requirement_extraction(
                    normalize_draft_payload(critic_payload["draft_payload"]),
                    state.get("requirement_extraction", {}),
                ),
                state.get("repository_memory", []),
            )
        state["critic_report"] = _critic_report(critic_payload.get("critic_report"))
    except Exception as exc:
        state["critic_report"] = {
            "status": "critic_failed",
            "message": str(exc),
        }
    return state


def persist_ready_for_review(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    session.status = AIGenerationSessionStatus.READY_FOR_REVIEW
    session.draft_payload = state["draft_payload"]
    session.critic_report = {
        "prompt_version": CRITIC_PROMPT_VERSION,
        "extraction_prompt_version": EXTRACTION_PROMPT_VERSION,
        "quality_warnings": state.get("quality_warnings", []),
        **state.get("critic_report", {}),
    }
    session.input_tokens = int(state.get("input_tokens") or 0)
    session.output_tokens = int(state.get("output_tokens") or 0)
    session.duration_ms = int(state.get("duration_ms") or 0)
    session.mlflow_run_id = state.get("mlflow_run_id", "")
    session.completed_at = timezone.now()
    session.error_message = ""
    session.save(
        update_fields=[
            "status",
            "draft_payload",
            "critic_report",
            "input_tokens",
            "output_tokens",
            "duration_ms",
            "mlflow_run_id",
            "completed_at",
            "error_message",
            "updated_at",
        ]
    )
    return state


def _call_llm_json(
    provider: LLMProvider,
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    allow_invalid_json: bool = False,
    max_tokens: int | None = None,
    num_ctx: int | None = None,
) -> LLMJSONResult:
    schema_text = json.dumps(schema, ensure_ascii=True)
    json_messages = [
        {
            "role": "system",
            "content": (
                "Return only one valid JSON object. Do not wrap it in markdown. "
                f"The JSON object must match this schema: {schema_text}"
            ),
        },
        *messages,
    ]
    started = time.monotonic()
    chat_options: dict[str, Any] = {
        "response_format": {"type": "json_object"},
    }
    if max_tokens:
        chat_options["max_tokens"] = max_tokens
    if num_ctx:
        chat_options["num_ctx"] = num_ctx
    response = provider.chat(
        json_messages,
        **chat_options,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    try:
        payload = parse_json_content(response.content)
    except Exception:
        if not allow_invalid_json:
            raise
        payload = {"_invalid_json_content": response.content}
    return LLMJSONResult(payload=payload, response=response, duration_ms=duration_ms)


def _accumulate_usage(state: TestGenerationState, result: LLMJSONResult) -> None:
    state["input_tokens"] = int(state.get("input_tokens") or 0) + result.response.input_tokens
    state["output_tokens"] = int(state.get("output_tokens") or 0) + result.response.output_tokens
    state["duration_ms"] = int(state.get("duration_ms") or 0) + result.duration_ms


def _limit_value(state: TestGenerationState, key: str) -> int | None:
    value = state.get("generation_limits", {}).get(key)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _critic_report(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"status": "critic_returned_no_report"}


def _attach_requirement_extraction(
    draft_payload: dict[str, Any],
    requirement_extraction: dict[str, Any],
) -> dict[str, Any]:
    draft_payload["requirement_extraction"] = (
        requirement_extraction
        if isinstance(requirement_extraction, dict)
        else empty_requirement_extraction()
    )
    return draft_payload


def _attach_repository_duplicates(
    draft_payload: dict[str, Any],
    repository_memory: list[dict[str, Any]],
) -> dict[str, Any]:
    if not repository_memory:
        return draft_payload
    existing = draft_payload.get("possible_duplicates") or []
    seen = {
        item.get("test_case_id")
        for item in existing
        if isinstance(item, dict) and item.get("test_case_id")
    }
    for item in repository_memory[:5]:
        test_case_id = item.get("test_case_id")
        if not test_case_id or test_case_id in seen:
            continue
        existing.append(
            {
                "test_case_id": test_case_id,
                "title": item.get("title", ""),
                "score": item.get("score"),
                "similarity_reason": item.get("similarity_reason", ""),
            }
        )
        seen.add(test_case_id)
    draft_payload["possible_duplicates"] = existing
    return draft_payload
