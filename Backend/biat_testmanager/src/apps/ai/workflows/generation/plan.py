from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from apps.ai.workflows.generation.contracts import (
    contract_for_prompt,
    scenario_expansion_schema,
)

PLAN_SCHEMA_VERSION = "ai_generation_plan_v1"
MAX_AGENT_ITERATIONS = 80
DEFAULT_MAX_REPAIRS_PER_SCENARIO = 2

PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "objective",
        "candidate_pool",
        "selected_scenarios",
        "excluded_candidates",
        "scenario_budget",
        "assumptions",
        "open_questions",
    ],
    "properties": {
        "objective": {"type": "string"},
        "candidate_pool": {"type": "array", "items": {"type": "object"}},
        "selected_scenarios": {"type": "array", "items": {"type": "object"}},
        "excluded_candidates": {"type": "array", "items": {"type": "object"}},
        "scenario_budget": {"type": "object"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
    },
}

SCENARIO_EXPANSION_SCHEMA = scenario_expansion_schema()


@dataclass(frozen=True)
class AgentLimits:
    max_repairs_per_scenario: int = DEFAULT_MAX_REPAIRS_PER_SCENARIO
    max_agent_iterations: int = MAX_AGENT_ITERATIONS


def normalize_generation_plan(
    payload: Any,
    *,
    objective: str,
    limits: AgentLimits,
    coverage_obligations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from apps.ai.workflows.generation.evidence import selected_scenarios_from_obligations

    if not isinstance(payload, dict):
        payload = {}
    candidates = _normalize_candidates(payload.get("candidate_pool"))
    obligation_selected = selected_scenarios_from_obligations(coverage_obligations or [])
    selected = _normalize_selected(
        payload.get("selected_scenarios"),
        candidates,
        obligation_selected=obligation_selected,
    )
    if not selected:
        selected = obligation_selected
    selected_candidate_ids = {item["candidate_id"] for item in selected}
    excluded = _normalize_excluded(
        payload.get("excluded_candidates"),
        candidates,
        selected_candidate_ids,
    )
    open_questions = [] if selected else _strings(payload.get("open_questions"))
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "objective": str(payload.get("objective") or objective).strip(),
        "limits": {
            "max_repairs_per_scenario": limits.max_repairs_per_scenario,
            "max_agent_iterations": limits.max_agent_iterations,
        },
        "context_summary": _object(payload.get("context_summary")),
        "candidate_pool": candidates,
        "selected_scenarios": selected,
        "coverage_obligations": coverage_obligations or [],
        "excluded_candidates": excluded,
        "scenario_budget": _object(payload.get("scenario_budget")),
        "assumptions": _strings(payload.get("assumptions")),
        "open_questions": open_questions,
        "termination": _object(payload.get("termination")) or {"reason": "planned"},
    }


def build_generation_plan_messages(
    *,
    objective: str,
    project_name: str,
    requirement_extraction: dict[str, Any],
    rag_context: list[dict[str, Any]],
    temporary_context: list[dict[str, Any]],
    temporary_inventory: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
    generation_limits: dict[str, int],
    semantic_evidence: list[dict[str, Any]] | None = None,
    coverage_obligations: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    context = {
        "project_name": project_name,
        "generation_contract": contract_for_prompt(),
        "requirement_extraction": requirement_extraction,
        "context_template": {
            "structured_requirements": coverage_obligations or [],
            "existing_generated_test_cases": repository_memory,
            "allowed_test_categories": [
                "happy_path",
                "alternative_flow",
                "edge_case",
                "security",
                "performance",
                "accessibility",
            ],
            "source_types": [
                "explicit_requirement",
                "acceptance_criterion",
                "inferred_case",
            ],
            "generation_rules": [
                "One primary behavior per test case.",
                "Every case must reference at least one requirement-like ID.",
                "Do not invent unsupported behavior.",
                "Mark inferred cases explicitly with coverage.source_type='inferred_case' and coverage.inferred=true.",
                "Do not invent performance thresholds.",
                "Avoid generating cases already covered by existing_generated_test_cases.",
                "Generated cases are draft candidates; do not emit persistence lifecycle fields.",
                "Expected results must be clear and verifiable.",
            ],
        },
        "selected_or_rag_context": rag_context,
        "temporary_attachment_context": temporary_context,
        "temporary_attachment_inventory": temporary_inventory or [],
        "repository_memory": repository_memory,
        "semantic_evidence": semantic_evidence or [],
        "coverage_obligations": coverage_obligations or [],
        "generation_limits": generation_limits,
    }
    return [
        {
            "role": "system",
            "content": (
                "Create BIAT's test-generation plan, not final test cases. Plan from "
                "coverage_obligations, not from arbitrary record counts. Do not use a "
                "fixed scenario target or cap; selected_scenarios should contain every "
                "distinct behavior group justified by evidence, constrained only by "
                "the operational iteration limits in context. Each selected scenario "
                "must include section_path, scenario_type, polarity, priority, "
                "business_priority, covered_obligation_ids, evidence_ids, "
                "requirement_ids, source_type, and intended_case_count. Keep scenarios homogeneous: do not mix positive "
                "and negative obligations or functional/security/performance/"
                "accessibility obligations in one scenario. Non-functional candidates "
                "are allowed only when grounded by supplied sources. The final draft "
                "must map to the BIAT testing model contract included in context; use "
                "its field names and enum values exactly. Return open_questions with "
                "no selected_scenarios only when the objective is too empty or "
                "contradictory to identify any testable behavior. Return strict JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Objective:\n{objective}\n\n"
                "Planning context JSON:\n"
                f"{json.dumps(context, ensure_ascii=True, default=str)}"
            ),
        },
    ]


def build_scenario_expansion_messages(
    *,
    objective: str,
    project_name: str,
    plan: dict[str, Any],
    selected_scenario: dict[str, Any],
    requirement_extraction: dict[str, Any],
    rag_context: list[dict[str, Any]],
    temporary_context: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
    generation_limits: dict[str, int],
    allowed_scenario_types: list[str],
) -> list[dict[str, str]]:
    context = {
        "project_name": project_name,
        "generation_contract": contract_for_prompt(),
        "context_template": {
            "structured_requirements": plan.get("coverage_obligations", []),
            "existing_generated_test_cases": repository_memory,
            "allowed_test_categories": allowed_scenario_types,
            "selected_source_type": selected_scenario.get("source_type"),
            "selected_requirement_ids": selected_scenario.get("requirement_ids", []),
            "rules": [
                "One primary behavior per test case.",
                "Every case must include coverage.requirement_ids and coverage.evidence_ids.",
                "Use coverage.source_type as explicit_requirement, acceptance_criterion, or inferred_case.",
                "If coverage.source_type is inferred_case, set coverage.inferred=true.",
                "Do not invent unsupported behavior or performance thresholds.",
                "Avoid duplicates from existing_generated_test_cases.",
                "Use clear, verifiable expected results.",
            ],
        },
        "plan": plan,
        "selected_scenario": selected_scenario,
        "requirement_extraction": requirement_extraction,
        "selected_or_rag_context": rag_context,
        "temporary_attachment_context": temporary_context,
        "repository_memory": repository_memory,
        "generation_limits": generation_limits,
        "allowed_scenario_types": allowed_scenario_types,
    }
    return [
        {
            "role": "system",
            "content": (
                "Expand exactly one planned BIAT scenario into reviewable test cases. "
                "Return one JSON object with key scenario. Use the selected scenario's "
                "draft_scenario_id as scenario.draft_id. Generate cases only for the "
                "selected scenario's covered_obligation_ids. Every generated case must "
                "include coverage.obligation_ids, coverage.requirement_ids, "
                "coverage.evidence_ids, coverage.source_type, and source_refs when "
                "available. Every step requires action and "
                "expected_outcome. "
                "Make the scenario description useful for repository review: include "
                "the user-visible journey, primary user story, and coverage purpose. "
                "Use only the exact draft keys and enum values in generation_contract. "
                "If the model contract and source text conflict, follow the contract "
                "and record the source ambiguity as an assumption or warning. Do not "
                "invent URLs, credentials, selectors, performance thresholds, or "
                "business rules."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Objective:\n{objective}\n\n"
                "Scenario expansion context JSON:\n"
                f"{json.dumps(context, ensure_ascii=True, default=str)}"
            ),
        },
    ]


def _normalize_candidates(value: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(value if isinstance(value, list) else []):
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or f"cand_{index + 1}").strip()
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        candidates.append(
            {
                "candidate_id": candidate_id,
                "title": title[:500],
                "category": str(item.get("category") or "functional").strip(),
                "priority": str(item.get("priority") or "should_have").strip(),
                "user_story": str(item.get("user_story") or "").strip(),
                "source_refs": item.get("source_refs")
                if isinstance(item.get("source_refs"), list)
                else [],
                "assumptions": _strings(item.get("assumptions")),
            }
        )
    return candidates


def _normalize_selected(
    value: Any,
    candidates: list[dict[str, Any]],
    *,
    obligation_selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    fallback_by_index = {
        index: item for index, item in enumerate(obligation_selected)
    }
    for index, item in enumerate(value if isinstance(value, list) else []):
        if not isinstance(item, dict):
            continue
        fallback = fallback_by_index.get(index, {})
        candidate_id = str(item.get("candidate_id") or f"cand_{index + 1}").strip()
        title = str(item.get("title") or candidate_by_id.get(candidate_id, {}).get("title") or "").strip()
        if not title:
            continue
        intended_count = _positive_int(
            item.get("intended_case_count"),
            default=int(fallback.get("intended_case_count") or 1),
        )
        selected.append(
            {
                "draft_scenario_id": str(item.get("draft_scenario_id") or f"scenario_{index + 1}").strip(),
                "candidate_id": candidate_id,
                "title": title[:500],
                "category": str(item.get("category") or item.get("scenario_type") or candidate_by_id.get(candidate_id, {}).get("category") or fallback.get("category") or "functional").strip(),
                "scenario_type": str(item.get("scenario_type") or fallback.get("scenario_type") or item.get("category") or "happy_path").strip(),
                "priority": str(item.get("priority") or candidate_by_id.get(candidate_id, {}).get("priority") or "should_have").strip(),
                "business_priority": item.get("business_priority") or fallback.get("business_priority"),
                "polarity": str(item.get("polarity") or fallback.get("polarity") or "positive").strip(),
                "section_path": item.get("section_path") if isinstance(item.get("section_path"), list) else fallback.get("section_path", []),
                "intended_case_count": intended_count,
                "user_story": str(item.get("user_story") or candidate_by_id.get(candidate_id, {}).get("user_story") or "").strip(),
                "covered_obligation_ids": item.get("covered_obligation_ids")
                if isinstance(item.get("covered_obligation_ids"), list)
                else fallback.get("covered_obligation_ids", []),
                "evidence_ids": item.get("evidence_ids")
                if isinstance(item.get("evidence_ids"), list)
                else fallback.get("evidence_ids", []),
                "requirement_ids": item.get("requirement_ids")
                if isinstance(item.get("requirement_ids"), list)
                else fallback.get("requirement_ids", []),
                "source_type": item.get("source_type") or fallback.get("source_type", "inferred_case"),
                "source_refs": item.get("source_refs")
                if isinstance(item.get("source_refs"), list)
                else fallback.get("source_refs", candidate_by_id.get(candidate_id, {}).get("source_refs", [])),
                "assumptions": _strings(item.get("assumptions")),
            }
        )
    return selected


def _normalize_excluded(
    value: Any,
    candidates: list[dict[str, Any]],
    selected_candidate_ids: set[str],
) -> list[dict[str, Any]]:
    excluded: list[dict[str, Any]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        excluded.append(
            {
                "candidate_id": candidate_id,
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    excluded_ids = {item["candidate_id"] for item in excluded}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        if candidate_id not in selected_candidate_ids and candidate_id not in excluded_ids:
            excluded.append(
                {
                    "candidate_id": candidate_id,
                    "reason": "Not selected because another planned scenario covers this evidence.",
                }
            )
    return excluded


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(1, parsed)


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (str(item).strip() for item in value) if item]


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
