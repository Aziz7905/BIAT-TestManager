from __future__ import annotations

from typing import Any

from apps.testing.models.choices import TestScenarioType

FIXED_GENERATION_EVAL_DATASETS: list[dict[str, Any]] = [
    {
        "dataset_id": "auth_registration_minimal",
        "requirements": [
            {
                "requirement_id": "FR-AUTH-001",
                "category": TestScenarioType.HAPPY_PATH,
                "behavior": "Customer registration accepts complete unique customer data.",
            },
            {
                "requirement_id": "FR-AUTH-002",
                "category": TestScenarioType.ALTERNATIVE_FLOW,
                "behavior": "Customer registration rejects missing mandatory fields.",
            },
            {
                "requirement_id": "FR-AUTH-003",
                "category": TestScenarioType.ALTERNATIVE_FLOW,
                "behavior": "Customer registration rejects duplicate usernames.",
            },
        ],
        "expected": {
            "requirement_ids": ["FR-AUTH-001", "FR-AUTH-002", "FR-AUTH-003"],
            "categories_by_requirement": {
                "FR-AUTH-001": TestScenarioType.HAPPY_PATH,
                "FR-AUTH-002": TestScenarioType.ALTERNATIVE_FLOW,
                "FR-AUTH-003": TestScenarioType.ALTERNATIVE_FLOW,
            },
        },
    },
    {
        "dataset_id": "security_performance_minimal",
        "requirements": [
            {
                "requirement_id": "FR-SEC-001",
                "category": TestScenarioType.SECURITY,
                "behavior": "A customer cannot view another customer's account.",
            },
            {
                "requirement_id": "NFR-PERF-001",
                "category": TestScenarioType.PERFORMANCE,
                "behavior": "Authenticated pages meet the stated response-time target.",
            },
        ],
        "expected": {
            "requirement_ids": ["FR-SEC-001", "NFR-PERF-001"],
            "categories_by_requirement": {
                "FR-SEC-001": TestScenarioType.SECURITY,
                "NFR-PERF-001": TestScenarioType.PERFORMANCE,
            },
        },
    },
]


def evaluate_generation_draft(
    *,
    dataset: dict[str, Any],
    draft_payload: dict[str, Any],
) -> dict[str, float]:
    expected_ids = set(dataset.get("expected", {}).get("requirement_ids") or [])
    categories_by_requirement = dataset.get("expected", {}).get("categories_by_requirement") or {}
    cases = list(_iter_cases(draft_payload))
    scenario_count = max(1, len(list(_iter_scenarios(draft_payload))))
    case_count = max(1, len(cases))
    covered_ids = {
        requirement_id
        for _scenario, case in cases
        for requirement_id in _case_requirement_ids(case)
    }
    traceable_cases = [
        case for _scenario, case in cases if _case_requirement_ids(case)
    ]
    duplicate_count = _duplicate_count(cases)
    atomic_cases = [
        case for _scenario, case in cases if _is_atomic(case)
    ]
    classified = 0
    classifiable = 0
    for scenario, case in cases:
        for requirement_id in _case_requirement_ids(case):
            expected_category = categories_by_requirement.get(requirement_id)
            if not expected_category:
                continue
            classifiable += 1
            if scenario.get("scenario_type") == expected_category:
                classified += 1
    unsupported_assumption_count = sum(
        1
        for _scenario, case in cases
        if _has_unsupported_assumption(case)
    )
    schema_valid_cases = [
        case for _scenario, case in cases if _has_required_case_shape(case)
    ]
    quality_expected_cases = [
        case for _scenario, case in cases if _has_quality_expected_result(case)
    ]
    return {
        "requirement_coverage": _ratio(len(covered_ids & expected_ids), len(expected_ids)),
        "duplicate_rate": _ratio(duplicate_count, case_count),
        "traceability_rate": _ratio(len(traceable_cases), case_count),
        "atomicity": _ratio(len(atomic_cases), case_count),
        "classification_accuracy": _ratio(classified, classifiable),
        "unsupported_assumption_rate": _ratio(unsupported_assumption_count, case_count),
        "schema_valid_output_rate": _ratio(len(schema_valid_cases), case_count),
        "expected_result_quality": _ratio(len(quality_expected_cases), case_count),
        "cases_per_scenario": round(len(cases) / scenario_count, 4),
    }


def compare_generation_eval_runs(
    *,
    before: dict[str, float],
    after: dict[str, float],
) -> dict[str, float]:
    keys = sorted(set(before) | set(after))
    return {key: round(float(after.get(key, 0.0)) - float(before.get(key, 0.0)), 4) for key in keys}


def run_fixed_generation_evals(
    *,
    drafts_by_dataset: dict[str, dict[str, Any]],
    baseline_by_dataset: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for dataset in FIXED_GENERATION_EVAL_DATASETS:
        dataset_id = dataset["dataset_id"]
        draft = drafts_by_dataset.get(dataset_id) or {}
        after = evaluate_generation_draft(dataset=dataset, draft_payload=draft)
        result = {"after": after}
        if baseline_by_dataset and baseline_by_dataset.get(dataset_id):
            before = evaluate_generation_draft(
                dataset=dataset,
                draft_payload=baseline_by_dataset[dataset_id],
            )
            result["before"] = before
            result["delta"] = compare_generation_eval_runs(before=before, after=after)
        results[dataset_id] = result
    return results


def _iter_scenarios(draft: dict[str, Any]):
    for section in draft.get("sections", []):
        yield from _iter_section_scenarios(section)


def _iter_section_scenarios(section: dict[str, Any]):
    for scenario in section.get("scenarios", []):
        if isinstance(scenario, dict):
            yield scenario
    for child in section.get("children", []):
        if isinstance(child, dict):
            yield from _iter_section_scenarios(child)


def _iter_cases(draft: dict[str, Any]):
    for scenario in _iter_scenarios(draft):
        for case in scenario.get("cases", []):
            if isinstance(case, dict):
                yield scenario, case


def _case_requirement_ids(case: dict[str, Any]) -> list[str]:
    coverage = case.get("coverage") if isinstance(case.get("coverage"), dict) else {}
    return [str(item) for item in coverage.get("requirement_ids", []) if item]


def _duplicate_count(cases: list[tuple[dict[str, Any], dict[str, Any]]]) -> int:
    seen: set[str] = set()
    duplicates = 0
    for _scenario, case in cases:
        key = " ".join(
            str(case.get(field) or "").strip().lower()
            for field in ("title", "expected_result")
        )
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def _is_atomic(case: dict[str, Any]) -> bool:
    text = f"{case.get('title', '')} {case.get('expected_result', '')}".lower()
    return not any(phrase in text for phrase in (" and then ", " as well as ", " also "))


def _has_unsupported_assumption(case: dict[str, Any]) -> bool:
    coverage = case.get("coverage") if isinstance(case.get("coverage"), dict) else {}
    text = " ".join(str(item) for item in coverage.get("assumptions", []) + case.get("warnings", []))
    return "assume" in text.lower()


def _has_required_case_shape(case: dict[str, Any]) -> bool:
    if not str(case.get("preconditions") or "").strip():
        return False
    if not isinstance(case.get("test_data"), dict):
        return False
    if not str(case.get("expected_result") or "").strip():
        return False
    steps = case.get("steps")
    return isinstance(steps, list) and bool(steps)


def _has_quality_expected_result(case: dict[str, Any]) -> bool:
    expected = str(case.get("expected_result") or "").strip().lower()
    if len(expected) < 12:
        return False
    vague = ("works correctly", "expected result", "expected state", "properly")
    return not any(phrase in expected for phrase in vague)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 1.0
    return round(numerator / denominator, 4)
