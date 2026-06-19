from __future__ import annotations

from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.providers.brain import get_team_brain
from apps.ai.services.capacity import check_ai_generation_capacity
from apps.ai.workflows.generation.context import retrieve_generation_context
from apps.ai.workflows.generation.events import append_generation_event
from apps.ai.workflows.generation.nodes._llm import accumulate_usage, call_llm_json, limit_value
from apps.ai.workflows.generation.nodes.shared import combined_generation_context
from apps.ai.workflows.generation.prompts import (
    DESIGN_PROMPT_VERSION,
    REQUIREMENT_EXTRACTION_SCHEMA,
    build_requirement_extraction_messages,
    normalize_requirement_extraction,
)
from apps.ai.workflows.generation.repository_memory import search_repository_memory
from apps.ai.workflows.generation.schemas import SCHEMA_VERSION
from apps.ai.workflows.generation.state import (
    CLOUD_GENERATION_LIMITS,
    LOCAL_GENERATION_LIMITS,
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
        LOCAL_GENERATION_LIMITS if provider.name == "ollama" else CLOUD_GENERATION_LIMITS
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


def plan_context_router(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    source_refs = session.source_refs if isinstance(session.source_refs, dict) else {}
    temporary_context = _temporary_context_from_source_refs(source_refs)
    selected_ids = _selected_spec_ids(source_refs, session)
    state["temporary_context"] = temporary_context
    state["context_plan"] = {
        "use_selected_specs": bool(selected_ids),
        "use_temporary_context": bool(temporary_context),
        "use_project_rag": bool(
            source_refs.get("force_project_rag")
            or (not selected_ids and not temporary_context)
        ),
        "use_repository_memory": _project_has_repository_cases(session),
    }
    append_generation_event(
        session,
        "context_resolution_started",
        message="Resolving available generation context.",
        payload=state["context_plan"],
    )
    return state


def selected_spec_context(state: TestGenerationState) -> TestGenerationState:
    if not state.get("context_plan", {}).get("use_selected_specs"):
        state["rag_context"] = []
        return state
    limits = state.get("generation_limits", CLOUD_GENERATION_LIMITS)
    state["rag_context"] = retrieve_generation_context(
        state["session"],
        top_k=int(limits.get("rag_top_k") or CLOUD_GENERATION_LIMITS["rag_top_k"]),
        max_content_chars=int(
            limits.get("max_chunk_chars") or CLOUD_GENERATION_LIMITS["max_chunk_chars"]
        ),
    )
    append_generation_event(
        state["session"],
        "selected_specs_loaded",
        message="Loaded selected project specifications.",
        payload={"context_count": len(state["rag_context"])},
    )
    return state


def temporary_attachment_context(state: TestGenerationState) -> TestGenerationState:
    temporary_context = state.get("temporary_context") or []
    if temporary_context:
        append_generation_event(
            state["session"],
            "attachment_extracted",
            message="Extracted temporary attachment context.",
            payload={"fragment_count": len(temporary_context)},
        )
    return state


def project_rag_context(state: TestGenerationState) -> TestGenerationState:
    if not state.get("context_plan", {}).get("use_project_rag"):
        return state
    limits = state.get("generation_limits", CLOUD_GENERATION_LIMITS)
    state["rag_context"] = retrieve_generation_context(
        state["session"],
        top_k=int(limits.get("rag_top_k") or CLOUD_GENERATION_LIMITS["rag_top_k"]),
        max_content_chars=int(
            limits.get("max_chunk_chars") or CLOUD_GENERATION_LIMITS["max_chunk_chars"]
        ),
    )
    append_generation_event(
        state["session"],
        "retrieval_completed",
        message="Retrieved project-scoped specification context.",
        payload={"context_count": len(state.get("rag_context") or [])},
    )
    return state


def repository_memory_gate(state: TestGenerationState) -> TestGenerationState:
    if not state.get("context_plan", {}).get("use_repository_memory"):
        state["repository_memory"] = []
    return state


def route_after_context_router(state: TestGenerationState) -> str:
    if state.get("context_plan", {}).get("use_selected_specs"):
        return "selected_spec_context"
    return "temporary_attachment_context"


def route_after_temporary_context(state: TestGenerationState) -> str:
    if state.get("context_plan", {}).get("use_project_rag"):
        return "project_rag_context"
    return "repository_memory_gate"


def route_after_repository_memory_gate(state: TestGenerationState) -> str:
    if state.get("context_plan", {}).get("use_repository_memory"):
        return "repository_memory_search"
    return "intent_normalizer"


def repository_memory_search(state: TestGenerationState) -> TestGenerationState:
    state["repository_memory"] = search_repository_memory(state["session"], limit=8)
    append_generation_event(
        state["session"],
        "repository_memory_checked",
        message="Checked existing repository tests for possible duplicates.",
        payload={"match_count": len(state["repository_memory"])},
    )
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
        "has_temporary_context": bool(state.get("temporary_context")),
        "has_repository_memory": bool(state.get("repository_memory")),
    }
    return state


def requirement_extraction(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    messages = build_requirement_extraction_messages(
        objective=session.objective,
        project_name=session.project.name,
        rag_context=combined_generation_context(state),
        repository_memory=state.get("repository_memory", []),
    )
    result = call_llm_json(
        state["provider"],
        messages=messages,
        schema=REQUIREMENT_EXTRACTION_SCHEMA,
        max_tokens=limit_value(state, "extraction_max_tokens"),
        retry_max_tokens=limit_value(state, "json_retry_max_tokens"),
        num_ctx=limit_value(state, "num_ctx"),
    )
    accumulate_usage(state, result)
    state["requirement_extraction"] = normalize_requirement_extraction(result.payload)
    return state


def _temporary_context_from_source_refs(source_refs: dict) -> list[dict]:
    fragments: list[dict] = []
    for attachment in source_refs.get("temporary_attachments") or []:
        if not isinstance(attachment, dict):
            continue
        for fragment in attachment.get("fragments") or []:
            if isinstance(fragment, dict):
                fragments.append(
                    {
                        "context_type": "temporary_attachment",
                        "attachment_id": fragment.get("attachment_id"),
                        "fragment_id": fragment.get("fragment_id"),
                        "filename": fragment.get("filename"),
                        "title": fragment.get("title"),
                        "content": fragment.get("content"),
                        "provenance": fragment.get("provenance") or {},
                    }
                )
    return fragments


def _selected_spec_ids(source_refs: dict, session) -> list[str]:
    values: list[str] = []
    for key in ("specification_ids", "selected_specification_ids"):
        raw = source_refs.get(key)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw if item)
        elif raw:
            values.append(str(raw))
    if session.attached_specification_id:
        values.append(str(session.attached_specification_id))
    return sorted(set(values))


def _project_has_repository_cases(session) -> bool:
    from apps.testing.models import TestCase

    return TestCase.objects.filter(
        scenario__section__suite__project=session.project,
    ).exists()
