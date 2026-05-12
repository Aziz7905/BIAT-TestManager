from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, TypedDict

from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.prompts import (
    CRITIC_PROMPT_VERSION,
    DESIGN_PROMPT_VERSION,
    build_test_critic_messages,
    build_test_design_messages,
)
from apps.ai.providers.base import ChatResponse, LLMProvider, parse_json_content
from apps.ai.schemas import DRAFT_JSON_SCHEMA, SCHEMA_VERSION, normalize_draft_payload
from apps.ai.services.brain import get_team_brain
from apps.ai.services.capacity import check_ai_generation_capacity
from apps.ai.services.context_retrieval import retrieve_generation_context
from apps.ai.services.repository_memory import search_repository_memory
from apps.specs.services.mlflow_tracking import MLflowRunLogger


class TestGenerationState(TypedDict, total=False):
    session_id: str
    session: AIGenerationSession
    provider: LLMProvider
    provider_name: str
    model_name: str
    normalized_intent: dict[str, Any]
    rag_context: list[dict[str, Any]]
    repository_memory: list[dict[str, Any]]
    raw_draft_payload: dict[str, Any]
    draft_payload: dict[str, Any]
    critic_report: dict[str, Any]
    validation_error: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    mlflow_run_id: str


@dataclass
class LLMJSONResult:
    payload: dict[str, Any]
    response: ChatResponse
    duration_ms: int


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
    state["rag_context"] = retrieve_generation_context(state["session"], top_k=10)
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


def test_design_generator(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    messages = build_test_design_messages(
        objective=session.objective,
        project_name=session.project.name,
        target_suite_name=session.target_suite.name if session.target_suite_id else None,
        target_section_name=session.target_section.name if session.target_section_id else None,
        normalized_intent=state.get("normalized_intent", {}),
        rag_context=state.get("rag_context", []),
        repository_memory=state.get("repository_memory", []),
        jira_issue_key=session.jira_issue_key,
    )
    result = _call_llm_json(
        state["provider"],
        messages=messages,
        schema=DRAFT_JSON_SCHEMA,
        allow_invalid_json=True,
    )
    _accumulate_usage(state, result)
    state["raw_draft_payload"] = result.payload
    return state


def draft_schema_validator(state: TestGenerationState) -> TestGenerationState:
    try:
        state["draft_payload"] = _attach_repository_duplicates(
            normalize_draft_payload(state["raw_draft_payload"]),
            state.get("repository_memory", []),
        )
        state.pop("validation_error", None)
    except Exception as exc:
        state["validation_error"] = str(exc)
    return state


def draft_repair(state: TestGenerationState) -> TestGenerationState:
    if not state.get("validation_error"):
        return state

    messages = [
        {
            "role": "system",
            "content": (
                "Repair the supplied draft so it validates against BIAT's test generation "
                "schema. Return only the repaired draft JSON object."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "validation_error": state["validation_error"],
                    "draft_payload": state.get("raw_draft_payload", {}),
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
    )
    _accumulate_usage(state, result)
    state["raw_draft_payload"] = result.payload
    state["draft_payload"] = _attach_repository_duplicates(
        normalize_draft_payload(result.payload),
        state.get("repository_memory", []),
    )
    state.pop("validation_error", None)
    return state


def test_critic(state: TestGenerationState) -> TestGenerationState:
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
        )
        _accumulate_usage(state, result)
        critic_payload = result.payload
        if isinstance(critic_payload.get("draft_payload"), dict):
            state["draft_payload"] = _attach_repository_duplicates(
                normalize_draft_payload(critic_payload["draft_payload"]),
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


def run_test_generation_workflow(session_id: str) -> TestGenerationState:
    from apps.ai.graphs.test_generation_graph import run_test_generation_graph

    state: TestGenerationState = {"session_id": session_id}
    with MLflowRunLogger(
        "ai_test_generation",
        params={
            "session_id": session_id,
            "schema_version": SCHEMA_VERSION,
            "prompt_version": DESIGN_PROMPT_VERSION,
        },
        tags={"pipeline": "ai_test_generation"},
    ) as tracker:
        if getattr(tracker, "_run", None):
            state["mlflow_run_id"] = tracker._run.info.run_id
        try:
            result = run_test_generation_graph(state)
            tracker.log_params(
                {
                    "provider": result.get("provider_name", ""),
                    "model": result.get("model_name", ""),
                }
            )
            tracker.log_metrics(
                {
                    "input_tokens": float(result.get("input_tokens") or 0),
                    "output_tokens": float(result.get("output_tokens") or 0),
                    "duration_ms": float(result.get("duration_ms") or 0),
                    "retrieved_chunk_count": float(len(result.get("rag_context") or [])),
                    "repository_memory_count": float(len(result.get("repository_memory") or [])),
                }
            )
            tracker.log_dict(result.get("draft_payload", {}), "draft_payload.json")
            tracker.log_dict(result.get("critic_report", {}), "critic_report.json")
            return result
        except Exception as exc:
            mark_generation_failed(session_id, str(exc), state=state)
            raise


def mark_generation_failed(
    session_id: str,
    message: str,
    *,
    state: TestGenerationState | None = None,
) -> None:
    update_fields = ["status", "error_message", "completed_at", "updated_at"]
    session = AIGenerationSession.objects.filter(pk=session_id).first()
    if session is None:
        return
    session.status = AIGenerationSessionStatus.FAILED
    session.error_message = message[:5000]
    session.completed_at = timezone.now()
    if state:
        session.input_tokens = int(state.get("input_tokens") or session.input_tokens)
        session.output_tokens = int(state.get("output_tokens") or session.output_tokens)
        session.duration_ms = int(state.get("duration_ms") or session.duration_ms or 0)
        session.mlflow_run_id = state.get("mlflow_run_id", session.mlflow_run_id)
        update_fields.extend(
            ["input_tokens", "output_tokens", "duration_ms", "mlflow_run_id"]
        )
    session.save(update_fields=update_fields)


def _call_llm_json(
    provider: LLMProvider,
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    allow_invalid_json: bool = False,
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
    response = provider.chat(
        json_messages,
        response_format={"type": "json_object"},
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


def _critic_report(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {"status": "critic_returned_no_report"}


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
