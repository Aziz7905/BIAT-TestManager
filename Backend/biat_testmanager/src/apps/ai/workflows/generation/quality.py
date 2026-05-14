from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

VAGUE_STEP_PHRASES = [
    "enter valid data",
    "enter invalid data",
    "expected state",
    "submit the request",
    "generate facture",
    "perform the action",
    "verify the result",
    "system works correctly",
    "application shows the expected state",
]

PROCESS_REQUIREMENT_TYPES = {
    "batch_job",
    "data_processing",
    "integration",
    "reporting",
}

UI_ACTION_HINTS = {
    "click",
    "screen",
    "button",
    "form",
    "page",
    "browser",
    "field",
}

FACT_KEYS_FOR_GROUNDING = [
    "system_or_process_name",
    "business_entities",
    "source_entities",
    "target_entities",
    "screens",
    "apis",
    "files_or_reports",
    "fields",
    "filters",
    "grouping_rules",
    "sorting_rules",
    "calculations",
    "business_rules",
    "validation_rules",
    "update_rules",
    "generated_outputs",
    "notifications",
    "error_conditions",
    "acceptance_criteria",
]


@dataclass(frozen=True)
class DraftQualityResult:
    total_steps: int
    total_cases: int
    vague_steps: list[dict[str, Any]]
    grounded_step_count: int
    warnings: list[str]
    should_repair: bool


def evaluate_draft_quality(
    draft_payload: dict[str, Any],
    requirement_extraction: dict[str, Any],
    *,
    source_context_count: int = 0,
) -> DraftQualityResult:
    steps = list(_iter_steps(draft_payload))
    case_count = _count_cases(draft_payload)
    facts = _extract_fact_terms(requirement_extraction)
    meaningful_rule_count = _count_meaningful_rules(requirement_extraction)
    vague_steps = [
        step
        for step in steps
        if _has_vague_phrase(step.get("action", ""))
        or _has_vague_phrase(step.get("expected_outcome", ""))
    ]

    grounded_step_count = 0
    if facts:
        for step in steps:
            text = f"{step.get('action', '')} {step.get('expected_outcome', '')}".lower()
            if any(term in text for term in facts):
                grounded_step_count += 1

    warnings: list[str] = []
    if vague_steps:
        warnings.append(
            "Draft contains generic steps and needs human review."
        )
    if facts and steps and grounded_step_count < max(1, min(3, len(steps) // 3)):
        warnings.append(
            "Draft steps do not use enough extracted requirement facts."
        )
    if _is_process_requirement_with_ui_steps(requirement_extraction, steps):
        warnings.append(
            "Process-style requirements contain UI-style steps without extracted screens."
        )
    if (
        source_context_count >= 3
        and meaningful_rule_count >= 3
        and case_count < min(meaningful_rule_count, 4)
    ):
        warnings.append(
            "Draft appears too shallow for the number of extracted requirement rules."
        )

    should_repair = bool(vague_steps) or any(
        phrase in warning
        for warning in warnings
        for phrase in ("extracted requirement facts", "too shallow")
    )
    return DraftQualityResult(
        total_steps=len(steps),
        total_cases=case_count,
        vague_steps=vague_steps,
        grounded_step_count=grounded_step_count,
        warnings=warnings,
        should_repair=should_repair,
    )


def format_quality_repair_instruction(result: DraftQualityResult) -> str:
    vague_examples = [
        step.get("action", "")[:160]
        for step in result.vague_steps[:5]
        if step.get("action")
    ]
    return (
        "Replace vague steps with concrete steps using the extracted requirement facts. "
        "Every action and expected_outcome should mention concrete fields, entities, "
        "filters, jobs/processes, APIs, outputs, update rules, screens, messages, or "
        "business rules when they are available. Keep the same JSON schema and do not "
        f"add more than the configured limits. Vague examples: {vague_examples}"
    )


def _iter_steps(draft_payload: dict[str, Any]):
    for section in draft_payload.get("sections", []):
        yield from _iter_section_steps(section)


def _count_cases(draft_payload: dict[str, Any]) -> int:
    count = 0
    for section in draft_payload.get("sections", []):
        count += _count_section_cases(section)
    return count


def _count_section_cases(section: dict[str, Any]) -> int:
    count = 0
    for scenario in section.get("scenarios", []):
        count += len(scenario.get("cases", []))
    for child in section.get("children", []):
        if isinstance(child, dict):
            count += _count_section_cases(child)
    return count


def _iter_section_steps(section: dict[str, Any]):
    for scenario in section.get("scenarios", []):
        scenario_title = scenario.get("title", "")
        for case in scenario.get("cases", []):
            case_title = case.get("title", "")
            for step in case.get("steps", []):
                if not isinstance(step, dict):
                    continue
                yield {
                    **step,
                    "scenario_title": scenario_title,
                    "case_title": case_title,
                }
    for child in section.get("children", []):
        if isinstance(child, dict):
            yield from _iter_section_steps(child)


def _has_vague_phrase(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.lower()).strip()
    return any(phrase in normalized for phrase in VAGUE_STEP_PHRASES)


def _extract_fact_terms(extraction: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    for key in FACT_KEYS_FOR_GROUNDING:
        value = extraction.get(key)
        if key == "system_or_process_name" and isinstance(value, str):
            _add_terms(terms, value)
            continue
        _walk_fact_value(value, terms)
    return terms


def _count_meaningful_rules(extraction: dict[str, Any]) -> int:
    rule_keys = [
        "business_rules",
        "validation_rules",
        "update_rules",
        "generated_outputs",
        "error_conditions",
        "acceptance_criteria",
    ]
    count = 0
    for key in rule_keys:
        value = extraction.get(key)
        if isinstance(value, list):
            count += len([item for item in value if item])
    return count


def _walk_fact_value(value: Any, terms: set[str]) -> None:
    if isinstance(value, str):
        _add_terms(terms, value)
    elif isinstance(value, dict):
        for item in value.values():
            _walk_fact_value(item, terms)
    elif isinstance(value, list):
        for item in value:
            _walk_fact_value(item, terms)


def _add_terms(terms: set[str], value: str) -> None:
    cleaned = re.sub(r"\s+", " ", value.strip().lower())
    if len(cleaned) >= 4:
        terms.add(cleaned)
    for token in re.findall(r"[a-z0-9_.-]{4,}", cleaned):
        terms.add(token)


def _is_process_requirement_with_ui_steps(
    extraction: dict[str, Any],
    steps: list[dict[str, Any]],
) -> bool:
    requirement_type = extraction.get("requirement_type")
    if requirement_type not in PROCESS_REQUIREMENT_TYPES or extraction.get("screens"):
        return False
    for step in steps:
        text = f"{step.get('action', '')} {step.get('expected_outcome', '')}".lower()
        if any(hint in text for hint in UI_ACTION_HINTS):
            return True
    return False
