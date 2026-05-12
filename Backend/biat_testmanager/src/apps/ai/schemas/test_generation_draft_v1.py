from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

from apps.testing.models.choices import (
    BusinessPriority,
    TestPriority,
    TestScenarioPolarity,
    TestScenarioType,
)

SCHEMA_VERSION = "ai_generation_draft_v1"

ALLOWED_SCENARIO_TYPES = {value for value, _ in TestScenarioType.choices}
ALLOWED_PRIORITIES = {value for value, _ in TestPriority.choices}
ALLOWED_BUSINESS_PRIORITIES = {value for value, _ in BusinessPriority.choices}
ALLOWED_POLARITIES = {value for value, _ in TestScenarioPolarity.choices}

DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "suite", "sections"],
    "properties": {
        "summary": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "suite": {
            "type": "object",
            "required": ["name", "description"],
            "properties": {
                "draft_id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
        },
        "sections": {
            "type": "array",
            "items": {"$ref": "#/$defs/section"},
        },
    },
    "$defs": {
        "section": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "draft_id": {"type": "string"},
                "name": {"type": "string"},
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": [
                            "title",
                            "description",
                            "scenario_type",
                            "priority",
                            "polarity",
                            "cases",
                        ],
                        "properties": {
                            "draft_id": {"type": "string"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "scenario_type": {
                                "enum": sorted(ALLOWED_SCENARIO_TYPES),
                            },
                            "priority": {"enum": sorted(ALLOWED_PRIORITIES)},
                            "business_priority": {
                                "enum": [None, *sorted(ALLOWED_BUSINESS_PRIORITIES)],
                            },
                            "polarity": {"enum": sorted(ALLOWED_POLARITIES)},
                            "confidence": {"type": "number"},
                            "possible_duplicates": {"type": "array"},
                            "cases": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": [
                                        "title",
                                        "preconditions",
                                        "steps",
                                        "expected_result",
                                        "test_data",
                                    ],
                                    "properties": {
                                        "draft_id": {"type": "string"},
                                        "title": {"type": "string"},
                                        "preconditions": {"type": "string"},
                                        "steps": {"type": "array"},
                                        "expected_result": {"type": "string"},
                                        "test_data": {"type": "object"},
                                        "linked_spec_ids": {"type": "array"},
                                        "possible_duplicates": {"type": "array"},
                                    },
                                },
                            },
                        },
                    },
                },
                "children": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/section"},
                },
            },
        },
    },
}


class DraftValidationError(ValueError):
    """Raised when an AI generation draft cannot map to BIAT test models."""


def normalize_draft_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a generated draft into BIAT's canonical draft shape."""
    if not isinstance(payload, dict):
        raise DraftValidationError("Draft payload must be a JSON object.")

    draft = deepcopy(payload)
    if "sections" not in draft and isinstance(draft.get("scenarios"), list):
        draft["sections"] = [
            {
                "draft_id": _draft_id(),
                "name": "Generated scenarios",
                "scenarios": draft.pop("scenarios"),
            }
        ]

    summary = _clean_string(draft.get("summary") or draft.get("objective_summary"))
    if not summary:
        raise DraftValidationError("Draft summary is required.")

    suite = draft.get("suite")
    if not isinstance(suite, dict):
        suite = {"name": "AI Generated Test Suite", "description": summary}
    suite = _normalize_suite(suite, summary=summary)

    raw_sections = draft.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections:
        raise DraftValidationError("Draft must include at least one section.")

    sections = [
        _normalize_section(section, section_index=index)
        for index, section in enumerate(raw_sections)
    ]
    if not any(_section_has_scenarios(section) for section in sections):
        raise DraftValidationError("Draft must include at least one scenario.")

    return {
        "schema_version": SCHEMA_VERSION,
        "summary": summary,
        "assumptions": _string_list(draft.get("assumptions")),
        "open_questions": _string_list(draft.get("open_questions")),
        "coverage_summary": _json_object(draft.get("coverage_summary")),
        "possible_duplicates": _json_list(draft.get("possible_duplicates")),
        "suite": suite,
        "sections": sections,
    }


def _normalize_suite(raw: dict[str, Any], *, summary: str) -> dict[str, Any]:
    name = _clean_string(raw.get("name")) or "AI Generated Test Suite"
    return {
        "draft_id": _clean_string(raw.get("draft_id")) or _draft_id(),
        "name": name[:300],
        "description": _clean_string(raw.get("description")) or summary,
    }


def _normalize_section(raw: Any, *, section_index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DraftValidationError("Every section must be a JSON object.")

    name = _clean_string(raw.get("name")) or "General"
    raw_scenarios = raw.get("scenarios", [])
    if not isinstance(raw_scenarios, list):
        raise DraftValidationError(f"Section '{name}' scenarios must be a list.")
    raw_children = raw.get("children", [])
    if not isinstance(raw_children, list):
        raise DraftValidationError(f"Section '{name}' children must be a list.")
    if not raw_scenarios and not raw_children:
        raise DraftValidationError(
            f"Section '{name}' must include scenarios or child sections."
        )

    return {
        "draft_id": _clean_string(raw.get("draft_id")) or _draft_id(),
        "name": name[:300],
        "order_index": _integer(raw.get("order_index"), section_index),
        "scenarios": [
            _normalize_scenario(scenario, scenario_index=index)
            for index, scenario in enumerate(raw_scenarios)
        ],
        "children": [
            _normalize_section(child, section_index=index)
            for index, child in enumerate(raw_children)
        ],
    }


def _normalize_scenario(raw: Any, *, scenario_index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DraftValidationError("Every scenario must be a JSON object.")

    title = _clean_string(raw.get("title"))
    if not title:
        raise DraftValidationError("Every scenario must include a title.")

    scenario_type = _choice(
        raw.get("scenario_type"),
        allowed=ALLOWED_SCENARIO_TYPES,
        default=TestScenarioType.HAPPY_PATH,
        field_name="scenario_type",
    )
    priority = _choice(
        raw.get("priority"),
        allowed=ALLOWED_PRIORITIES,
        default=TestPriority.MEDIUM,
        field_name="priority",
    )
    business_priority = _nullable_choice(
        raw.get("business_priority"),
        allowed=ALLOWED_BUSINESS_PRIORITIES,
        field_name="business_priority",
    )
    polarity = _choice(
        raw.get("polarity"),
        allowed=ALLOWED_POLARITIES,
        default=TestScenarioPolarity.POSITIVE,
        field_name="polarity",
    )

    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise DraftValidationError(f"Scenario '{title}' must include at least one case.")

    return {
        "draft_id": _clean_string(raw.get("draft_id")) or _draft_id(),
        "title": title[:500],
        "description": _clean_string(raw.get("description")),
        "scenario_type": scenario_type,
        "priority": priority,
        "business_priority": business_priority,
        "polarity": polarity,
        "confidence": _confidence(raw.get("confidence")),
        "possible_duplicates": _json_list(raw.get("possible_duplicates")),
        "order_index": _integer(raw.get("order_index"), scenario_index),
        "cases": [
            _normalize_case(case, case_index=index)
            for index, case in enumerate(raw_cases)
        ],
    }


def _normalize_case(raw: Any, *, case_index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DraftValidationError("Every test case must be a JSON object.")

    title = _clean_string(raw.get("title"))
    if not title:
        raise DraftValidationError("Every test case must include a title.")

    steps = _normalize_steps(raw.get("steps"))
    expected_result = _clean_string(raw.get("expected_result"))
    if not expected_result and steps:
        expected_result = steps[-1]["expected_outcome"]
    if not expected_result:
        raise DraftValidationError(f"Test case '{title}' must include an expected result.")

    return {
        "draft_id": _clean_string(raw.get("draft_id")) or _draft_id(),
        "title": title[:500],
        "preconditions": _clean_string(raw.get("preconditions")),
        "steps": steps,
        "expected_result": expected_result,
        "test_data": _json_object(raw.get("test_data")),
        "linked_spec_ids": _string_list(raw.get("linked_spec_ids")),
        "possible_duplicates": _json_list(raw.get("possible_duplicates")),
        "order_index": _integer(raw.get("order_index"), case_index),
        "jira_issue_key": _clean_string(raw.get("jira_issue_key")),
    }


def _section_has_scenarios(section: dict[str, Any]) -> bool:
    if section.get("scenarios"):
        return True
    return any(_section_has_scenarios(child) for child in section.get("children", []))


def _normalize_steps(raw_steps: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list) or not raw_steps:
        raise DraftValidationError("Every test case must include at least one step.")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise DraftValidationError("Every test step must be a JSON object.")
        action = _clean_string(raw.get("action") or raw.get("step") or raw.get("description"))
        expected = _clean_string(
            raw.get("expected_outcome")
            or raw.get("expected")
            or raw.get("expected_result")
        )
        if not action:
            raise DraftValidationError("Every test step must include an action.")
        if not expected:
            expected = "The application shows the expected state for this step."
        normalized.append(
            {
                "step_index": _integer(raw.get("step_index") or raw.get("order"), index),
                "action": action,
                "expected_outcome": expected,
            }
        )
    return normalized


def _draft_id() -> str:
    return str(uuid.uuid4())


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    return [item for item in (_clean_string(item) for item in value) if item]


def _json_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _confidence(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, parsed))


def _choice(value: Any, *, allowed: set[str], default: str, field_name: str) -> str:
    cleaned = _clean_string(value) or default
    if cleaned not in allowed:
        raise DraftValidationError(f"Invalid {field_name}: {cleaned}.")
    return cleaned


def _nullable_choice(value: Any, *, allowed: set[str], field_name: str) -> str | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None
    if cleaned not in allowed:
        raise DraftValidationError(f"Invalid {field_name}: {cleaned}.")
    return cleaned
