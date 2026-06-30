from __future__ import annotations

from collections import Counter
from typing import Any

from apps.ai.workflows.generation.context import retrieve_generation_context
from apps.ai.workflows.generation.evidence import (
    build_coverage_obligations,
    compile_semantic_evidence,
    selected_scenarios_from_obligations,
)
from apps.ai.workflows.generation.events import append_generation_event, merge_generation_metadata
from apps.ai.workflows.generation.nodes.shared import combined_generation_context, stop_if_cancelled
from apps.ai.workflows.generation.prompts import empty_requirement_extraction
from apps.ai.workflows.generation.repository_memory import search_repository_memory
from apps.ai.workflows.generation.state import CLOUD_GENERATION_LIMITS, TestGenerationState
from apps.specs.models import SpecChunk

OBLIGATION_COVERED = "covered"
OBLIGATION_NOT_YET_COVERED = "not_yet_covered"
OBLIGATION_MERGED = "merged"
OBLIGATION_UNSUPPORTED = "unsupported"
OBLIGATION_NEEDS_CLARIFICATION = "needs_clarification"

ACTION_RETRIEVE = "retrieve_more_context"
ACTION_SEARCH_MEMORY = "search_repository_memory"
ACTION_REVISE_HIERARCHY = "revise_hierarchy"
ACTION_REQUEST_CLARIFICATION = "request_clarification"
ACTION_PROCEED = "proceed_to_expansion"


def route_after_coverage_agent(state: TestGenerationState) -> str:
    if state.get("clarification_required"):
        return "persist_clarification_required"
    return "scenario_expand_loop"


def coverage_agent_loop(state: TestGenerationState) -> TestGenerationState:
    """Close planning gaps with targeted retrieval and deterministic hierarchy revision."""
    stop_if_cancelled(state)
    session = state["session"]
    limits = state.get("generation_limits", CLOUD_GENERATION_LIMITS)
    max_iterations = int(limits.get("max_agent_iterations") or CLOUD_GENERATION_LIMITS["max_agent_iterations"])
    max_retrieval_attempts = int(
        limits.get("max_targeted_retrieval_attempts")
        or CLOUD_GENERATION_LIMITS["max_targeted_retrieval_attempts"]
    )
    agent_actions: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    retrieval_attempts: list[dict[str, Any]] = []
    hierarchy_choices: list[dict[str, Any]] = []
    searched_memory_queries: set[str] = set()
    retrieved_queries: set[str] = set()

    for iteration in range(1, max_iterations + 1):
        stop_if_cancelled(state)
        observation = _build_observation(state)
        observations.append(observation)
        action = _decide_next_action(
            state,
            observation,
            retrieval_attempt_count=len(retrieval_attempts),
            max_retrieval_attempts=max_retrieval_attempts,
            retrieved_queries=retrieved_queries,
            searched_memory_queries=searched_memory_queries,
        )
        action["iteration"] = iteration
        agent_actions.append(action)

        if action["action"] == ACTION_PROCEED:
            state["agent_termination_reason"] = "coverage_agent_ready"
            break
        if action["action"] == ACTION_REQUEST_CLARIFICATION:
            state["clarification_required"] = True
            _add_clarification_questions(state, observation)
            state["agent_termination_reason"] = "coverage_agent_needs_clarification"
            break
        if action["action"] == ACTION_SEARCH_MEMORY:
            searched_memory_queries.add(action["query"])
            _merge_repository_memory(state, query=action["query"])
            continue
        if action["action"] == ACTION_RETRIEVE:
            retrieved_queries.add(action["query"])
            attempt = _retrieve_targeted_context(state, action)
            retrieval_attempts.append(attempt)
            _merge_repository_memory(state, query=action["query"])
            _rebuild_evidence_and_obligations(state)
            choice = _revise_generation_plan_from_obligations(
                state,
                reason="targeted_retrieval",
            )
            hierarchy_choices.append(choice)
            continue
        if action["action"] == ACTION_REVISE_HIERARCHY:
            choice = _revise_generation_plan_from_obligations(
                state,
                reason=action.get("reason") or "coverage_gap",
            )
            hierarchy_choices.append(choice)
            continue

    else:
        state["agent_termination_reason"] = "coverage_agent_iteration_limit_reached"

    final_observation = _build_observation(state)
    state["agent_observations"] = observations + [final_observation]
    state["agent_actions"] = agent_actions
    state["retrieval_attempts"] = retrieval_attempts
    state["obligation_state_summary"] = final_observation["state_summary"]
    if hierarchy_choices:
        state["selected_hierarchy_strategy"] = hierarchy_choices[-1]["selected"]
        state["rejected_hierarchy_strategies"] = hierarchy_choices[-1]["rejected"]
    else:
        state["selected_hierarchy_strategy"] = _strategy_report(
            "existing_plan",
            state.get("generation_plan", {}).get("selected_scenarios", []),
            state.get("coverage_obligations", []),
        )
        state["rejected_hierarchy_strategies"] = []

    merge_generation_metadata(
        session,
        coverage_agent={
            "termination_reason": state.get("agent_termination_reason"),
            "state_summary": state["obligation_state_summary"],
            "action_count": len(agent_actions),
            "retrieval_attempt_count": len(retrieval_attempts),
        },
    )
    append_generation_event(
        session,
        "coverage_agent_completed",
        message="Coverage agent resolved planning state.",
        payload={
            "termination_reason": state.get("agent_termination_reason"),
            "state_summary": state["obligation_state_summary"],
        },
    )
    return state


def _decide_next_action(
    state: TestGenerationState,
    observation: dict[str, Any],
    *,
    retrieval_attempt_count: int,
    max_retrieval_attempts: int,
    retrieved_queries: set[str],
    searched_memory_queries: set[str],
) -> dict[str, Any]:
    plan = state.get("generation_plan") or {}
    obligations = state.get("coverage_obligations") or []
    unresolved = [
        item for item in observation["obligations"]
        if item["state"] == OBLIGATION_NOT_YET_COVERED
    ]
    if not obligations and not plan.get("selected_scenarios"):
        return {
            "action": ACTION_REQUEST_CLARIFICATION,
            "reason": "No testable coverage obligations were found.",
        }

    query = _query_for_obligation(unresolved[0]) if unresolved else ""
    if (
        unresolved
        and observation["has_source_context"]
        and _project_has_rag_sources(state)
        and retrieval_attempt_count < max_retrieval_attempts
        and query
        and query not in retrieved_queries
    ):
        return {
            "action": ACTION_RETRIEVE,
            "reason": "A source-backed obligation is not assigned to any planned scenario.",
            "obligation_id": unresolved[0]["obligation_id"],
            "query": query,
        }
    if query and query not in searched_memory_queries and state.get("repository_memory") is not None:
        return {
            "action": ACTION_SEARCH_MEMORY,
            "reason": "Check existing tests for possible duplicate coverage before expansion.",
            "query": query,
        }
    if unresolved and observation["has_source_context"]:
        return {
            "action": ACTION_REVISE_HIERARCHY,
            "reason": "Source-backed obligations must be assigned before expansion.",
        }
    if not plan.get("selected_scenarios") and obligations:
        return {
            "action": ACTION_REVISE_HIERARCHY,
            "reason": "Coverage obligations exist but no scenarios were selected.",
        }
    if observation["state_summary"].get(OBLIGATION_NEEDS_CLARIFICATION):
        return {
            "action": ACTION_REQUEST_CLARIFICATION,
            "reason": "At least one obligation needs clarification.",
        }
    return {"action": ACTION_PROCEED, "reason": "All actionable obligations have a final planning state."}


def _build_observation(state: TestGenerationState) -> dict[str, Any]:
    obligations = state.get("coverage_obligations") or []
    plan = state.get("generation_plan") or {}
    planned_ids = _planned_obligation_ids(plan.get("selected_scenarios", []))
    merged_ids = {
        str(item.get("obligation_id"))
        for item in (state.get("coverage_metadata") or {}).get("merged_obligations", [])
        if item.get("obligation_id")
    }
    has_source_context = bool(combined_generation_context(state))
    observed: list[dict[str, Any]] = []
    for obligation in obligations:
        obligation_id = str(obligation.get("obligation_id") or "")
        if not obligation.get("evidence_ids") and not obligation.get("source_refs"):
            obligation_state = OBLIGATION_UNSUPPORTED
        elif obligation_id in planned_ids:
            obligation_state = OBLIGATION_COVERED
        elif obligation_id in merged_ids:
            obligation_state = OBLIGATION_MERGED
        elif obligation.get("assumptions") and has_source_context:
            obligation_state = OBLIGATION_NEEDS_CLARIFICATION
        elif has_source_context:
            obligation_state = OBLIGATION_NOT_YET_COVERED
        else:
            obligation_state = OBLIGATION_UNSUPPORTED
        observed.append(
            {
                "obligation_id": obligation_id,
                "state": obligation_state,
                "behavior": obligation.get("behavior"),
                "module_or_area": obligation.get("module_or_area"),
                "scenario_type": obligation.get("scenario_type"),
                "polarity": obligation.get("polarity"),
                "requirement_ids": obligation.get("requirement_ids", []),
                "evidence_ids": obligation.get("evidence_ids", []),
                "source_type": obligation.get("source_type"),
            }
        )
    summary = Counter(item["state"] for item in observed)
    return {
        "has_source_context": has_source_context,
        "source_context_count": len(combined_generation_context(state)),
        "planned_scenario_count": len(plan.get("selected_scenarios") or []),
        "obligation_count": len(obligations),
        "state_summary": dict(summary),
        "obligations": observed,
    }


def _retrieve_targeted_context(state: TestGenerationState, action: dict[str, Any]) -> dict[str, Any]:
    limits = state.get("generation_limits", CLOUD_GENERATION_LIMITS)
    context = retrieve_generation_context(
        state["session"],
        query=action["query"],
        top_k=int(limits.get("targeted_rag_top_k") or limits.get("rag_top_k") or 5),
        max_content_chars=int(limits.get("max_chunk_chars") or CLOUD_GENERATION_LIMITS["max_chunk_chars"]),
        retrieval_metadata={
            "agent_action": ACTION_RETRIEVE,
            "obligation_id": action.get("obligation_id"),
        },
    )
    state["rag_context"] = _merge_context_items(state.get("rag_context", []), context)
    append_generation_event(
        state["session"],
        "coverage_agent_retrieval_completed",
        message="Coverage agent retrieved targeted source context.",
        payload={
            "query": action["query"],
            "obligation_id": action.get("obligation_id"),
            "context_count": len(context),
        },
    )
    return {
        "query": action["query"],
        "obligation_id": action.get("obligation_id"),
        "context_count": len(context),
    }


def _merge_repository_memory(state: TestGenerationState, *, query: str) -> None:
    memory = search_repository_memory(state["session"], query=query, limit=8)
    state["repository_memory"] = _merge_context_items(state.get("repository_memory", []), memory)


def _rebuild_evidence_and_obligations(state: TestGenerationState) -> None:
    session = state["session"]
    semantic_evidence = compile_semantic_evidence(
        objective=session.objective,
        generation_context=combined_generation_context(state),
        requirement_extraction=state.get("requirement_extraction", empty_requirement_extraction()),
    )
    coverage_obligations, coverage_metadata = build_coverage_obligations(semantic_evidence)
    state["semantic_evidence"] = semantic_evidence
    state["coverage_obligations"] = coverage_obligations
    state["coverage_metadata"] = coverage_metadata
    plan = state.get("generation_plan") or {}
    plan["coverage_obligations"] = coverage_obligations
    state["generation_plan"] = plan


def _revise_generation_plan_from_obligations(
    state: TestGenerationState,
    *,
    reason: str,
) -> dict[str, Any]:
    obligations = state.get("coverage_obligations") or []
    plan = state.get("generation_plan") or {}
    existing = plan.get("selected_scenarios") or []
    obligation_grouped = selected_scenarios_from_obligations(obligations)
    strategies = [
        _strategy_report("existing_plan", existing, obligations),
        _strategy_report("obligation_grouped", obligation_grouped, obligations),
    ]
    selected = min(
        strategies,
        key=lambda item: (
            item["uncovered_obligation_count"],
            item["mixed_metadata_count"],
            item["missing_section_path_count"],
            item["scenario_count"],
        ),
    )
    if selected["strategy"] == "obligation_grouped":
        plan["selected_scenarios"] = obligation_grouped
        plan["excluded_candidates"] = []
    plan["coverage_obligations"] = obligations
    plan.setdefault("termination", {})["coverage_agent_revision"] = reason
    state["generation_plan"] = plan
    return {
        "selected": selected,
        "rejected": [item for item in strategies if item["strategy"] != selected["strategy"]],
    }


def _strategy_report(
    name: str,
    scenarios: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
) -> dict[str, Any]:
    obligation_by_id = {str(item.get("obligation_id")): item for item in obligations}
    planned_ids = _planned_obligation_ids(scenarios)
    mixed_metadata = 0
    missing_section_path = 0
    for scenario in scenarios:
        if not scenario.get("section_path"):
            missing_section_path += 1
        scenario_obligations = [
            obligation_by_id[obligation_id]
            for obligation_id in _strings(scenario.get("covered_obligation_ids"))
            if obligation_id in obligation_by_id
        ]
        types = {str(item.get("scenario_type") or "") for item in scenario_obligations}
        polarities = {str(item.get("polarity") or "") for item in scenario_obligations}
        if len(types) > 1 or len(polarities) > 1:
            mixed_metadata += 1
    return {
        "strategy": name,
        "scenario_count": len(scenarios),
        "covered_obligation_count": len(planned_ids),
        "uncovered_obligation_count": len(set(obligation_by_id) - planned_ids),
        "mixed_metadata_count": mixed_metadata,
        "missing_section_path_count": missing_section_path,
    }


def _planned_obligation_ids(scenarios: list[dict[str, Any]]) -> set[str]:
    return {
        str(item)
        for scenario in scenarios
        if isinstance(scenario, dict)
        for item in scenario.get("covered_obligation_ids", [])
        if item
    }


def _query_for_obligation(obligation: dict[str, Any]) -> str:
    parts = [
        " ".join(_strings(obligation.get("requirement_ids"))),
        str(obligation.get("module_or_area") or ""),
        str(obligation.get("behavior") or ""),
        str(obligation.get("scenario_type") or ""),
        str(obligation.get("polarity") or ""),
    ]
    return " ".join(part for part in parts if part).strip()[:500]


def _project_has_rag_sources(state: TestGenerationState) -> bool:
    session = state["session"]
    return SpecChunk.objects.filter(specification__project=session.project).exists()


def _add_clarification_questions(state: TestGenerationState, observation: dict[str, Any]) -> None:
    plan = state.get("generation_plan") or {}
    existing = [str(item).strip() for item in plan.get("open_questions", []) if str(item).strip()]
    if not existing:
        existing = [
            "Which requirement, user flow, or business rule should the generated test coverage target?"
        ]
    plan["open_questions"] = existing
    state["generation_plan"] = plan
    state["clarification_questions"] = existing
    state["obligation_state_summary"] = observation["state_summary"]


def _merge_context_items(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*(existing or []), *(incoming or [])]:
        if not isinstance(item, dict):
            continue
        key = _context_key(item)
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output


def _context_key(item: dict[str, Any]) -> str:
    for key in ("chunk_id", "test_case_id", "record_id", "source_ref"):
        if item.get(key):
            return f"{key}:{item[key]}"
    return repr(sorted((str(key), str(value)) for key, value in item.items() if key != "score"))


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
