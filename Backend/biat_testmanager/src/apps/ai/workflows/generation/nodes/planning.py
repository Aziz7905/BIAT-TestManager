from __future__ import annotations

from django.utils import timezone

from apps.ai.models import AIGenerationSessionStatus
from apps.ai.workflows.generation.events import (
    append_generation_event,
    merge_generation_metadata,
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
    messages = build_generation_plan_messages(
        objective=session.objective,
        project_name=session.project.name,
        requirement_extraction=state.get(
            "requirement_extraction",
            empty_requirement_extraction(),
        ),
        rag_context=state.get("rag_context", []),
        temporary_context=state.get("temporary_context", []),
        repository_memory=state.get("repository_memory", []),
        generation_limits=state.get("generation_limits", CLOUD_GENERATION_LIMITS),
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
    )
    plan = _ensure_actionable_plan(plan, objective=session.objective)
    state["generation_plan"] = plan
    state["clarification_required"] = not bool(plan.get("selected_scenarios"))
    merge_generation_metadata(
        session,
        generation_plan=plan,
        plan_summary={
            "candidate_count": len(plan.get("candidate_pool", [])),
            "selected_count": len(plan.get("selected_scenarios", [])),
            "excluded_count": len(plan.get("excluded_candidates", [])),
        },
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
    session.completed_at = timezone.now()
    session.input_tokens = int(state.get("input_tokens") or 0)
    session.output_tokens = int(state.get("output_tokens") or 0)
    session.duration_ms = int(state.get("duration_ms") or 0)
    session.save(
        update_fields=[
            "status",
            "draft_payload",
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


def _ensure_actionable_plan(plan: dict, *, objective: str) -> dict:
    if plan.get("selected_scenarios"):
        return plan
    if not _objective_is_actionable(objective):
        return plan
    title = _title_from_objective(objective)
    assumptions = [
        "Exact alternate outcomes not supplied; generated reasonable coverage from the objective."
    ]
    candidate_pool = [
        {
            "candidate_id": "cand_1",
            "title": title,
            "category": "functional",
            "priority": "must_have",
            "user_story": objective,
            "source_refs": [],
            "assumptions": assumptions,
        },
        {
            "candidate_id": "cand_2",
            "title": f"{title} alternate and edge coverage"[:500],
            "category": "functional",
            "priority": "should_have",
            "user_story": objective,
            "source_refs": [],
            "assumptions": assumptions,
        },
    ]
    max_scenarios = int(plan.get("limits", {}).get("max_scenarios") or 2)
    selected_candidates = candidate_pool[: max(1, min(2, max_scenarios))]
    plan["candidate_pool"] = candidate_pool
    plan["selected_scenarios"] = [
        {
            "draft_scenario_id": f"scenario_{index + 1}",
            "candidate_id": candidate["candidate_id"],
            "title": candidate["title"],
            "category": candidate["category"],
            "priority": candidate["priority"],
            "intended_case_count": min(
                3,
                int(plan.get("limits", {}).get("max_cases_per_scenario") or 3),
            ),
            "user_story": objective,
            "source_refs": [],
            "assumptions": assumptions,
        }
        for index, candidate in enumerate(selected_candidates)
    ]
    selected_ids = {candidate["candidate_id"] for candidate in selected_candidates}
    plan["excluded_candidates"] = [
        {
            "candidate_id": candidate["candidate_id"],
            "reason": "Not selected within the scenario budget.",
        }
        for candidate in candidate_pool
        if candidate["candidate_id"] not in selected_ids
    ]
    plan["open_questions"] = []
    return plan


def _objective_is_actionable(objective: str) -> bool:
    words = " ".join(str(objective or "").split())
    return len(words) >= 16 and any(char.isalpha() for char in words)


def _title_from_objective(objective: str) -> str:
    title = " ".join(str(objective or "").split())[:120].rstrip()
    return title or "Generated test scenario"
