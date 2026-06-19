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
MAX_SECTIONS = 5
MAX_SCENARIOS_PER_SECTION = 8
MAX_CASES_PER_SCENARIO = 6
MAX_STEPS_PER_CASE = 12

LOCAL_MAX_SECTIONS = 2
LOCAL_MAX_SCENARIOS_PER_SECTION = 3
LOCAL_MAX_CASES_PER_SCENARIO = 2
LOCAL_MAX_STEPS_PER_CASE = 6

ALLOWED_SCENARIO_TYPES = {value for value, _ in TestScenarioType.choices}
ALLOWED_PRIORITIES = {value for value, _ in TestPriority.choices}
ALLOWED_BUSINESS_PRIORITIES = {value for value, _ in BusinessPriority.choices}
ALLOWED_POLARITIES = {value for value, _ in TestScenarioPolarity.choices}

PRIORITY_ALIASES = {}
BUSINESS_PRIORITY_ALIASES = {}
POLARITY_ALIASES = {}


def _normalize_choice_key(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _choice_aliases(choices: Any) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for value, label in choices.choices:
        aliases[_normalize_choice_key(value)] = str(value)
        aliases[_normalize_choice_key(label)] = str(value)
    return aliases


SCENARIO_TYPE_ALIASES = {
    **_choice_aliases(TestScenarioType),
    "acceptance": TestScenarioType.HAPPY_PATH,
    "acceptance_test": TestScenarioType.HAPPY_PATH,
    "acceptance_testing": TestScenarioType.HAPPY_PATH,
    "functional": TestScenarioType.HAPPY_PATH,
    "functional_test": TestScenarioType.HAPPY_PATH,
    "functional_testing": TestScenarioType.HAPPY_PATH,
    "positive": TestScenarioType.HAPPY_PATH,
    "positive_case": TestScenarioType.HAPPY_PATH,
    "success": TestScenarioType.HAPPY_PATH,
    "success_case": TestScenarioType.HAPPY_PATH,
    "smoke": TestScenarioType.HAPPY_PATH,
    "smoke_test": TestScenarioType.HAPPY_PATH,
    "regression": TestScenarioType.HAPPY_PATH,
    "regression_test": TestScenarioType.HAPPY_PATH,
    "business_rule": TestScenarioType.ALTERNATIVE_FLOW,
    "business_rules": TestScenarioType.ALTERNATIVE_FLOW,
    "validation": TestScenarioType.ALTERNATIVE_FLOW,
    "validation_rule": TestScenarioType.ALTERNATIVE_FLOW,
    "validation_rules": TestScenarioType.ALTERNATIVE_FLOW,
    "alternate": TestScenarioType.ALTERNATIVE_FLOW,
    "alternate_flow": TestScenarioType.ALTERNATIVE_FLOW,
    "alternative": TestScenarioType.ALTERNATIVE_FLOW,
    "error_case": TestScenarioType.EDGE_CASE
    if TestScenarioType.EDGE_CASE in ALLOWED_SCENARIO_TYPES
    else TestScenarioType.ALTERNATIVE_FLOW,
    "error_handling": TestScenarioType.EDGE_CASE
    if TestScenarioType.EDGE_CASE in ALLOWED_SCENARIO_TYPES
    else TestScenarioType.ALTERNATIVE_FLOW,
    "failure_case": TestScenarioType.EDGE_CASE
    if TestScenarioType.EDGE_CASE in ALLOWED_SCENARIO_TYPES
    else TestScenarioType.ALTERNATIVE_FLOW,
    "negative": TestScenarioType.ALTERNATIVE_FLOW
    if TestScenarioType.ALTERNATIVE_FLOW in ALLOWED_SCENARIO_TYPES
    else TestScenarioType.EDGE_CASE,
    "negative_case": TestScenarioType.ALTERNATIVE_FLOW
    if TestScenarioType.ALTERNATIVE_FLOW in ALLOWED_SCENARIO_TYPES
    else TestScenarioType.EDGE_CASE,
    "boundary": TestScenarioType.EDGE_CASE,
    "boundary_case": TestScenarioType.EDGE_CASE,
    "edge": TestScenarioType.EDGE_CASE,
    "edge_cases": TestScenarioType.EDGE_CASE,
    "non_functional": TestScenarioType.PERFORMANCE,
    "nonfunctional": TestScenarioType.PERFORMANCE,
    "load": TestScenarioType.PERFORMANCE,
    "load_test": TestScenarioType.PERFORMANCE,
    "performance_test": TestScenarioType.PERFORMANCE,
    "security_test": TestScenarioType.SECURITY,
    "access_control": TestScenarioType.SECURITY,
    "authorization": TestScenarioType.SECURITY,
    "authentication": TestScenarioType.SECURITY,
    "accessibility_test": TestScenarioType.ACCESSIBILITY,
    "a11y": TestScenarioType.ACCESSIBILITY,
}
PRIORITY_ALIASES = _choice_aliases(TestPriority)
BUSINESS_PRIORITY_ALIASES = {
    **_choice_aliases(BusinessPriority),
    "critical": BusinessPriority.MUST_HAVE,
    "high": BusinessPriority.MUST_HAVE,
    "medium": BusinessPriority.SHOULD_HAVE,
    "normal": BusinessPriority.SHOULD_HAVE,
    "standard": BusinessPriority.SHOULD_HAVE,
    "low": BusinessPriority.COULD_HAVE,
    "minor": BusinessPriority.COULD_HAVE,
}
POLARITY_ALIASES = _choice_aliases(TestScenarioPolarity)

DRAFT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "suite", "sections"],
    "properties": {
        "summary": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "requirement_extraction": {"type": "object"},
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
                                        "steps": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["action", "expected_outcome"],
                                                "properties": {
                                                    "step_index": {"type": "integer"},
                                                    "action": {"type": "string"},
                                                    "expected_outcome": {"type": "string"},
                                                    "target": {"type": "string"},
                                                    "test_data": {"type": "object"},
                                                    "validation_type": {"type": "string"},
                                                    "notes": {"type": "string"},
                                                },
                                            },
                                        },
                                        "expected_result": {"type": "string"},
                                        "test_data": {"type": "object"},
                                        "linked_spec_ids": {"type": "array"},
                                        "source_refs": {"type": "array"},
                                        "warnings": {"type": "array"},
                                        "coverage": {"type": "object"},
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
    if len(raw_sections) > MAX_SECTIONS:
        raise DraftValidationError(
            f"Draft cannot include more than {MAX_SECTIONS} root sections."
        )

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
        "requirement_extraction": _json_object(draft.get("requirement_extraction")),
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
    if len(raw_scenarios) > MAX_SCENARIOS_PER_SECTION:
        raise DraftValidationError(
            f"Section '{name}' cannot include more than "
            f"{MAX_SCENARIOS_PER_SECTION} scenarios."
        )
    raw_children = raw.get("children", [])
    if not isinstance(raw_children, list):
        raise DraftValidationError(f"Section '{name}' children must be a list.")
    if len(raw_children) > MAX_SECTIONS:
        raise DraftValidationError(
            f"Section '{name}' cannot include more than {MAX_SECTIONS} child sections."
        )
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

    scenario_type = _scenario_type_choice(
        raw.get("scenario_type"),
        allowed=ALLOWED_SCENARIO_TYPES,
        default=TestScenarioType.HAPPY_PATH,
        field_name="scenario_type",
    )
    priority = _choice(
        raw.get("priority"),
        allowed=ALLOWED_PRIORITIES,
        aliases=PRIORITY_ALIASES,
        default=TestPriority.MEDIUM,
        field_name="priority",
    )
    business_priority = _nullable_choice(
        raw.get("business_priority"),
        allowed=ALLOWED_BUSINESS_PRIORITIES,
        aliases=BUSINESS_PRIORITY_ALIASES,
        field_name="business_priority",
    )
    polarity = _choice(
        raw.get("polarity"),
        allowed=ALLOWED_POLARITIES,
        aliases=POLARITY_ALIASES,
        default=TestScenarioPolarity.POSITIVE,
        field_name="polarity",
    )

    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise DraftValidationError(f"Scenario '{title}' must include at least one case.")
    if len(raw_cases) > MAX_CASES_PER_SCENARIO:
        raise DraftValidationError(
            f"Scenario '{title}' cannot include more than "
            f"{MAX_CASES_PER_SCENARIO} test cases."
        )

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
        "source_refs": _json_list(raw.get("source_refs")),
        "warnings": _string_list(raw.get("warnings")),
        "coverage": _json_object(raw.get("coverage")),
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
    if len(raw_steps) > MAX_STEPS_PER_CASE:
        raise DraftValidationError(
            f"A test case cannot include more than {MAX_STEPS_PER_CASE} steps."
        )

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
            raise DraftValidationError("Every test step must include an expected outcome.")
        step = {
            "step_index": index + 1,
            "action": action,
            "expected_outcome": expected,
        }
        for optional_field in ("target", "validation_type", "notes"):
            optional_value = _clean_string(raw.get(optional_field))
            if optional_value:
                step[optional_field] = optional_value
        test_data = _json_object(raw.get("test_data"))
        if test_data:
            step["test_data"] = test_data
        normalized.append(step)
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


def _choice(
    value: Any,
    *,
    allowed: set[str],
    aliases: dict[str, str] | None = None,
    default: str,
    field_name: str,
) -> str:
    cleaned = _clean_string(value) or default
    cleaned = (aliases or {}).get(_choice_key(cleaned), cleaned)
    if cleaned not in allowed:
        raise DraftValidationError(f"Invalid {field_name}: {cleaned}.")
    return cleaned


def _scenario_type_choice(
    value: Any,
    *,
    allowed: set[str],
    default: str,
    field_name: str,
) -> str:
    cleaned = _choice_key(value) or default
    cleaned = str(SCENARIO_TYPE_ALIASES.get(cleaned, cleaned))
    if cleaned not in allowed:
        raise DraftValidationError(f"Invalid {field_name}: {cleaned}.")
    return cleaned


def _choice_key(value: Any) -> str:
    return _normalize_choice_key(value)


def _nullable_choice(
    value: Any,
    *,
    allowed: set[str],
    aliases: dict[str, str] | None = None,
    field_name: str,
) -> str | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None
    cleaned = (aliases or {}).get(_choice_key(cleaned), cleaned)
    if cleaned not in allowed:
        raise DraftValidationError(f"Invalid {field_name}: {cleaned}.")
    return cleaned
