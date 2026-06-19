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
    max_scenarios: int
    max_cases_per_scenario: int
    max_repairs_per_scenario: int = DEFAULT_MAX_REPAIRS_PER_SCENARIO
    max_agent_iterations: int = MAX_AGENT_ITERATIONS


def normalize_generation_plan(
    payload: Any,
    *,
    objective: str,
    limits: AgentLimits,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    candidates = _normalize_candidates(payload.get("candidate_pool"))
    selected = _normalize_selected(payload.get("selected_scenarios"), candidates, limits)
    selected_candidate_ids = {item["candidate_id"] for item in selected}
    excluded = _normalize_excluded(
        payload.get("excluded_candidates"),
        candidates,
        selected_candidate_ids,
    )
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "objective": str(payload.get("objective") or objective).strip(),
        "limits": {
            "max_scenarios": limits.max_scenarios,
            "max_cases_per_scenario": limits.max_cases_per_scenario,
            "max_repairs_per_scenario": limits.max_repairs_per_scenario,
            "max_agent_iterations": limits.max_agent_iterations,
        },
        "context_summary": _object(payload.get("context_summary")),
        "candidate_pool": candidates,
        "selected_scenarios": selected,
        "excluded_candidates": excluded,
        "scenario_budget": _object(payload.get("scenario_budget")),
        "assumptions": _strings(payload.get("assumptions")),
        "open_questions": _strings(payload.get("open_questions")),
        "termination": _object(payload.get("termination")) or {"reason": "planned"},
    }


def build_generation_plan_messages(
    *,
    objective: str,
    project_name: str,
    requirement_extraction: dict[str, Any],
    rag_context: list[dict[str, Any]],
    temporary_context: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
    generation_limits: dict[str, int],
) -> list[dict[str, str]]:
    context = {
        "project_name": project_name,
        "generation_contract": contract_for_prompt(),
        "requirement_extraction": requirement_extraction,
        "selected_or_rag_context": rag_context,
        "temporary_attachment_context": temporary_context,
        "repository_memory": repository_memory,
        "generation_limits": generation_limits,
    }
    return [
        {
            "role": "system",
            "content": (
                "Create BIAT's test-generation plan, not final test cases. First "
                "over-generate a candidate_pool larger than selected_scenarios when "
                "the source supports it. Then select the best scenarios under the "
                "limits. Keep candidate_pool and selected_scenarios distinct. For "
                "each candidate and selected scenario include a concise user_story "
                "that explains the user-visible value being tested. Non-functional "
                "candidates are allowed only when grounded by supplied sources. Do "
                "not block generation just because alternate outcomes are unspecified; "
                "generate reasonable positive, negative, and edge coverage and record "
                "assumptions. The final draft must map to the BIAT testing model "
                "contract included in context; use its field names and enum values "
                "exactly. Return open_questions with no selected_scenarios only when "
                "the objective is too empty or contradictory to identify any testable "
                "behavior. Return strict JSON."
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
                "draft_scenario_id as scenario.draft_id. Obey the intended_case_count "
                "and generation limits. Every step requires action and expected_outcome. "
                "Make the scenario description useful for repository review: include "
                "the user-visible journey, primary user story, and coverage purpose. "
                "Use only the exact draft keys and enum values in generation_contract. "
                "If the model contract and source text conflict, follow the contract "
                "and record the source ambiguity as an assumption or warning. Do not "
                "invent URLs, credentials, selectors, or business rules."
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
    limits: AgentLimits,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    candidate_by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    for index, item in enumerate(value if isinstance(value, list) else []):
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("candidate_id") or f"cand_{index + 1}").strip()
        title = str(item.get("title") or candidate_by_id.get(candidate_id, {}).get("title") or "").strip()
        if not title:
            continue
        intended_count = _bounded_int(
            item.get("intended_case_count"),
            default=limits.max_cases_per_scenario,
            minimum=1,
            maximum=limits.max_cases_per_scenario,
        )
        selected.append(
            {
                "draft_scenario_id": str(item.get("draft_scenario_id") or f"scenario_{index + 1}").strip(),
                "candidate_id": candidate_id,
                "title": title[:500],
                "category": str(item.get("category") or candidate_by_id.get(candidate_id, {}).get("category") or "functional").strip(),
                "priority": str(item.get("priority") or candidate_by_id.get(candidate_id, {}).get("priority") or "should_have").strip(),
                "intended_case_count": intended_count,
                "user_story": str(item.get("user_story") or candidate_by_id.get(candidate_id, {}).get("user_story") or "").strip(),
                "source_refs": item.get("source_refs")
                if isinstance(item.get("source_refs"), list)
                else candidate_by_id.get(candidate_id, {}).get("source_refs", []),
                "assumptions": _strings(item.get("assumptions")),
            }
        )
        if len(selected) >= limits.max_scenarios:
            break
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
                    "reason": "Not selected within the scenario budget.",
                }
            )
    return excluded


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (str(item).strip() for item in value) if item]


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
