from __future__ import annotations

import json
from typing import Any

from apps.ai.workflows.generation.contracts import contract_for_prompt
from apps.ai.workflows.generation.events import append_generation_event
from apps.ai.workflows.generation.nodes._llm import (
    accumulate_usage,
    call_llm_json,
    limit_value,
)
from apps.ai.workflows.generation.nodes.shared import (
    GENERATED_SECTION_ID,
    GENERATED_SECTION_NAME,
    agent_limits,
    combined_generation_context,
    stop_if_cancelled,
)
from apps.ai.workflows.generation.plan import (
    AgentLimits,
    SCENARIO_EXPANSION_SCHEMA,
    build_scenario_expansion_messages,
)
from apps.ai.workflows.generation.prompts import empty_requirement_extraction
from apps.ai.workflows.generation.quality import (
    evaluate_draft_quality,
    format_quality_repair_instruction,
)
from apps.ai.workflows.generation.schemas import (
    ALLOWED_SCENARIO_TYPES,
    SCHEMA_VERSION,
    normalize_draft_payload,
)
from apps.ai.workflows.generation.state import (
    CLOUD_GENERATION_LIMITS,
    TestGenerationState,
)


def scenario_expand_loop(state: TestGenerationState) -> TestGenerationState:
    plan = state.get("generation_plan") or {}
    draft = empty_draft(state["session"], plan)
    limits = agent_limits(state)
    repair_counts: dict[str, Any] = {}
    termination_reason = "completed"
    selected = plan.get("selected_scenarios") or []
    for iteration, scenario_plan in enumerate(selected):
        stop_if_cancelled(state)
        if iteration >= limits.max_agent_iterations:
            termination_reason = "agent_iteration_limit_reached"
            break
        append_generation_event(
            state["session"],
            "scenario_expansion_started",
            message=f"Expanding scenario: {scenario_plan.get('title', 'Untitled scenario')}",
            payload={"scenario_index": iteration + 1},
        )
        scenario, scenario_counts = _generate_scenario_with_repairs(
            state,
            scenario_plan=scenario_plan,
            limits=limits,
        )
        repair_counts[scenario_plan.get("draft_scenario_id") or scenario.get("draft_id")] = scenario_counts
        if scenario_counts.get("termination_reason") != "completed":
            termination_reason = scenario_counts["termination_reason"]
        draft["sections"][0]["scenarios"].append(scenario)
        _persist_progressive_draft(state["session"], draft)
        append_generation_event(
            state["session"],
            "scenario_expansion_completed",
            message=(
                f"Generated {len(scenario.get('cases', []))} cases for "
                f"{scenario.get('title', 'Untitled scenario')}."
            ),
            payload={"scenario_id": scenario.get("draft_id")},
        )
    state["draft_payload"] = normalize_draft_payload(draft)
    state["repair_counts"] = repair_counts
    state["agent_termination_reason"] = termination_reason
    return state


def empty_draft(session, plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": plan.get("objective") or session.objective,
        "assumptions": plan.get("assumptions", []),
        "open_questions": plan.get("open_questions", []),
        "suite": {
            "draft_id": session.target_suite_id or "suite_generated",
            "name": session.target_suite.name
            if session.target_suite
            else plan.get("objective") or "AI Generated Test Suite",
            "description": _build_suite_description(plan, session.objective),
        },
        "sections": [
            {
                "draft_id": session.target_section_id or GENERATED_SECTION_ID,
                "name": session.target_section.name
                if session.target_section
                else GENERATED_SECTION_NAME,
                "order_index": 0,
                "scenarios": [],
                "children": [],
            }
        ],
    }


def _build_suite_description(plan: dict[str, Any], objective: str) -> str:
    parts = [_clean_text(objective)]
    for selected in plan.get("selected_scenarios", []):
        if isinstance(selected, dict):
            story = _clean_text(selected.get("user_story"))
            if story:
                parts.append(story)
    return "\n\n".join(part for part in parts if part).strip()


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _generate_scenario_with_repairs(
    state: TestGenerationState,
    *,
    scenario_plan: dict[str, Any],
    limits: AgentLimits,
) -> tuple[dict[str, Any], dict[str, Any]]:
    counts = {
        "schema_repair_attempts": 0,
        "quality_repair_attempts": 0,
        "termination_reason": "completed",
    }
    scenario_payload = _call_scenario_expander(state, scenario_plan)
    if isinstance(scenario_payload, dict):
        scenario_payload = scenario_payload.get("scenario", scenario_payload)
    for _attempt in range(limits.max_repairs_per_scenario + 1):
        try:
            scenario_payload = _normalize_single_scenario(
                state,
                scenario_plan,
                scenario_payload,
            )
            quality = evaluate_draft_quality(
                _draft_for_single_scenario(state, scenario_payload),
                state.get("requirement_extraction", empty_requirement_extraction()),
                source_context_count=len(combined_generation_context(state)),
            )
            if not quality.should_repair:
                return scenario_payload, counts
            counts["quality_repair_attempts"] += 1
            scenario_payload = _repair_scenario_payload(
                state,
                scenario_plan=scenario_plan,
                scenario_payload=scenario_payload,
                instruction=format_quality_repair_instruction(quality),
            )
            scenario_payload = _normalize_single_scenario(
                state,
                scenario_plan,
                scenario_payload,
            )
        except Exception as exc:
            if counts["schema_repair_attempts"] >= limits.max_repairs_per_scenario:
                counts["termination_reason"] = "schema_repair_limit_reached"
                raise
            counts["schema_repair_attempts"] += 1
            scenario_payload = _repair_scenario_payload(
                state,
                scenario_plan=scenario_plan,
                scenario_payload=scenario_payload,
                instruction=(
                    "Repair this single scenario JSON so it maps to BIAT's draft schema. "
                    f"Validation error: {exc}"
                ),
            )
    return scenario_payload, counts


def _call_scenario_expander(
    state: TestGenerationState,
    scenario_plan: dict[str, Any],
) -> dict[str, Any]:
    session = state["session"]
    messages = build_scenario_expansion_messages(
        objective=session.objective,
        project_name=session.project.name,
        plan=state.get("generation_plan", {}),
        selected_scenario=scenario_plan,
        requirement_extraction=state.get(
            "requirement_extraction",
            empty_requirement_extraction(),
        ),
        rag_context=state.get("rag_context", []),
        temporary_context=state.get("temporary_context", []),
        repository_memory=state.get("repository_memory", []),
        generation_limits=state.get("generation_limits", CLOUD_GENERATION_LIMITS),
        allowed_scenario_types=sorted(ALLOWED_SCENARIO_TYPES),
    )
    result = call_llm_json(
        state["provider"],
        messages=messages,
        schema=SCENARIO_EXPANSION_SCHEMA,
        max_tokens=limit_value(state, "design_max_tokens"),
        retry_max_tokens=limit_value(state, "json_retry_max_tokens"),
        num_ctx=limit_value(state, "num_ctx"),
    )
    accumulate_usage(state, result)
    return result.payload


def _repair_scenario_payload(
    state: TestGenerationState,
    *,
    scenario_plan: dict[str, Any],
    scenario_payload: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": instruction},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "generation_contract": contract_for_prompt(),
                    "selected_scenario": scenario_plan,
                    "scenario": scenario_payload,
                    "generation_limits": state.get(
                        "generation_limits",
                        CLOUD_GENERATION_LIMITS,
                    ),
                },
                ensure_ascii=True,
                default=str,
            ),
        },
    ]
    result = call_llm_json(
        state["provider"],
        messages=messages,
        schema=SCENARIO_EXPANSION_SCHEMA,
        max_tokens=limit_value(state, "repair_max_tokens"),
        retry_max_tokens=limit_value(state, "json_retry_max_tokens"),
        num_ctx=limit_value(state, "num_ctx"),
    )
    accumulate_usage(state, result)
    if isinstance(result.payload, dict):
        return result.payload.get("scenario", result.payload)
    return {}


def _normalize_single_scenario(
    state: TestGenerationState,
    scenario_plan: dict[str, Any],
    scenario_payload: dict[str, Any],
) -> dict[str, Any]:
    scenario_payload = dict(scenario_payload or {})
    scenario_payload["draft_id"] = scenario_plan["draft_scenario_id"]
    scenario_payload.setdefault("title", scenario_plan["title"])
    scenario_payload.setdefault("business_priority", scenario_plan.get("priority"))
    source_refs = scenario_plan.get("source_refs") or []
    for case in scenario_payload.get("cases") or []:
        if isinstance(case, dict) and not case.get("source_refs"):
            case["source_refs"] = source_refs
    draft = _draft_for_single_scenario(state, scenario_payload)
    normalized = normalize_draft_payload(draft)
    return normalized["sections"][0]["scenarios"][0]


def _draft_for_single_scenario(
    state: TestGenerationState,
    scenario_payload: dict[str, Any],
) -> dict[str, Any]:
    session = state["session"]
    plan = state.get("generation_plan") or {}
    return {
        "summary": plan.get("objective") or session.objective,
        "suite": {
            "draft_id": "suite_temp",
            "name": "Scenario expansion",
            "description": "",
        },
        "sections": [
            {
                "draft_id": "section_temp",
                "name": GENERATED_SECTION_NAME,
                "scenarios": [scenario_payload],
            }
        ],
    }


def _persist_progressive_draft(session, draft: dict[str, Any]) -> None:
    session.draft_payload = draft
    session.save(update_fields=["draft_payload", "updated_at"])
