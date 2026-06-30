from __future__ import annotations

from django.utils import timezone

from apps.ai.models import AIGenerationSessionStatus
from apps.ai.workflows.generation.events import (
    append_generation_event,
    merge_generation_metadata,
)
from apps.ai.workflows.generation.evidence import (
    build_coverage_obligations,
    compile_semantic_evidence,
)
from apps.ai.workflows.generation.nodes._llm import (
    accumulate_usage,
    call_llm_json,
    limit_value,
)
from apps.ai.workflows.generation.nodes.shared import agent_limits, stop_if_cancelled
from apps.ai.workflows.generation.plan import (
    PLAN_JSON_SCHEMA,
    build_generation_plan_messages,
    normalize_generation_plan,
)
from apps.ai.workflows.generation.prompts import empty_requirement_extraction
from apps.ai.workflows.generation.schemas import SCHEMA_VERSION
from apps.ai.workflows.generation.state import (
    CLOUD_GENERATION_LIMITS,
    TestGenerationState,
)


def route_after_generation_planner(state: TestGenerationState) -> str:
    if state.get("clarification_required"):
        return "persist_clarification_required"
    return "scenario_expand_loop"


def generation_planner(state: TestGenerationState) -> TestGenerationState:
    stop_if_cancelled(state)
    session = state["session"]
    limits = agent_limits(state)
    semantic_evidence = compile_semantic_evidence(
        objective=session.objective,
        generation_context=[
            *(state.get("rag_context") or []),
            *(state.get("temporary_context") or []),
        ],
        requirement_extraction=state.get(
            "requirement_extraction",
            empty_requirement_extraction(),
        ),
    )
    coverage_obligations, coverage_metadata = build_coverage_obligations(
        semantic_evidence
    )
    state["semantic_evidence"] = semantic_evidence
    state["coverage_obligations"] = coverage_obligations
    state["coverage_metadata"] = coverage_metadata
    messages = build_generation_plan_messages(
        objective=session.objective,
        project_name=session.project.name,
        requirement_extraction=state.get(
            "requirement_extraction",
            empty_requirement_extraction(),
        ),
        rag_context=state.get("rag_context", []),
        temporary_context=state.get("temporary_context", []),
        temporary_inventory=state.get("temporary_inventory", []),
        repository_memory=state.get("repository_memory", []),
        generation_limits=state.get("generation_limits", CLOUD_GENERATION_LIMITS),
        semantic_evidence=semantic_evidence,
        coverage_obligations=coverage_obligations,
    )
    append_generation_event(
        session,
        "planning_started",
        message="Planning candidate scenarios from the available context.",
    )
    result = call_llm_json(
        state["provider"],
        messages=messages,
        schema=PLAN_JSON_SCHEMA,
        max_tokens=limit_value(state, "planning_max_tokens"),
        retry_max_tokens=limit_value(state, "json_retry_max_tokens"),
        num_ctx=limit_value(state, "num_ctx"),
        max_json_retries=2,
    )
    accumulate_usage(state, result)
    plan = normalize_generation_plan(
        result.payload,
        objective=session.objective,
        limits=limits,
        coverage_obligations=coverage_obligations,
    )
    state["generation_plan"] = plan
    state["clarification_required"] = not bool(plan.get("selected_scenarios"))
    merge_generation_metadata(
        session,
        generation_plan=plan,
        plan_summary={
            "candidate_count": len(plan.get("candidate_pool", [])),
            "selected_count": len(plan.get("selected_scenarios", [])),
            "excluded_count": len(plan.get("excluded_candidates", [])),
            "obligation_count": len(coverage_obligations),
        },
        semantic_evidence={
            "count": len(semantic_evidence),
            "types": _count_by_key(semantic_evidence, "evidence_type"),
        },
        coverage_metadata=coverage_metadata,
    )
    append_generation_event(
        session,
        "planning_completed",
        message=(
            "Selected "
            f"{len(plan.get('selected_scenarios', []))} scenarios from "
            f"{len(plan.get('candidate_pool', []))} candidates."
        ),
        payload={"clarification_required": state["clarification_required"]},
    )
    return state


def _count_by_key(items: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        value = str(item.get(key) or "")
        counts[value] = counts.get(value, 0) + 1
    return counts


def persist_clarification_required(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    plan = state.get("generation_plan") or {}
    session.status = AIGenerationSessionStatus.CLARIFICATION_REQUIRED
    session.draft_payload = {
        "schema_version": SCHEMA_VERSION,
        "summary": session.objective,
        "assumptions": plan.get("assumptions", []),
        "open_questions": plan.get("open_questions", []),
        "suite": {
            "draft_id": "suite_pending",
            "name": "Clarification required",
            "description": session.objective,
        },
        "sections": [],
    }
    session.critic_report = {
        "generation_plan": plan,
        "agent_actions": state.get("agent_actions", []),
        "agent_observations": state.get("agent_observations", []),
        "retrieval_attempts": state.get("retrieval_attempts", []),
        "obligation_state_summary": state.get("obligation_state_summary", {}),
        "clarification_questions": plan.get("open_questions", []),
        "agent_termination_reason": state.get("agent_termination_reason") or "clarification_required",
    }
    session.completed_at = timezone.now()
    session.input_tokens = int(state.get("input_tokens") or 0)
    session.output_tokens = int(state.get("output_tokens") or 0)
    session.duration_ms = int(state.get("duration_ms") or 0)
    session.save(
        update_fields=[
            "status",
            "draft_payload",
            "critic_report",
            "completed_at",
            "input_tokens",
            "output_tokens",
            "duration_ms",
            "updated_at",
        ]
    )
    append_generation_event(
        session,
        "clarification_required",
        message="Generation needs a clearer objective before drafting tests.",
        payload={"open_questions": plan.get("open_questions", [])},
    )
    return state
