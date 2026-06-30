from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from apps.ai.workflows.generation.evidence import requirement_like_ids
from apps.testing.models.choices import TestScenarioPolarity, TestScenarioType

ALLOWED_SCENARIO_TYPES = {
    TestScenarioType.HAPPY_PATH,
    TestScenarioType.ALTERNATIVE_FLOW,
    TestScenarioType.EDGE_CASE,
    TestScenarioType.SECURITY,
    TestScenarioType.PERFORMANCE,
    TestScenarioType.ACCESSIBILITY,
}
ALLOWED_SOURCE_TYPES = {
    "explicit_requirement",
    "acceptance_criterion",
    "inferred_case",
}
VAGUE_EXPECTED_PATTERNS = [
    r"\bworks correctly\b",
    r"\bexpected result\b",
    r"\bexpected state\b",
    r"\bproperly\b",
    r"\bsuccessfully\b$",
    r"\bverify the result\b",
]
COMBINED_OBJECTIVE_RE = re.compile(
    r"\b(and|then|as well as)\b.+\b(and|then|also)\b",
    re.IGNORECASE,
)
NON_FUNCTIONAL_RE = re.compile(
    r"\b(performance|latency|response time|throughput|availability|p95|percentile|load)\b",
    re.IGNORECASE,
)
MEASUREMENT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(ms|s|sec|seconds?|%|percent|rps|tps)\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


@dataclass(frozen=True)
class GuardrailViolation:
    code: str
    message: str
    severity: str = "error"
    repairable: bool = True
    case_id: str = ""


@dataclass(frozen=True)
class GuardrailResult:
    violations: list[GuardrailViolation]

    @property
    def should_repair(self) -> bool:
        return any(item.severity == "error" and item.repairable for item in self.violations)

    @property
    def should_reject(self) -> bool:
        return any(item.severity == "error" and not item.repairable for item in self.violations)

    @property
    def warnings(self) -> list[str]:
        return [item.message for item in self.violations if item.severity == "warning"]


def validate_scenario_guardrails(
    *,
    scenario_payload: dict[str, Any],
    scenario_plan: dict[str, Any],
    coverage_obligations: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]] | None = None,
) -> GuardrailResult:
    obligation_by_id = {
        str(item.get("obligation_id")): item
        for item in coverage_obligations
        if item.get("obligation_id")
    }
    planned_obligation_ids = [
        str(item)
        for item in scenario_plan.get("covered_obligation_ids", [])
        if item
    ]
    planned_requirements = requirement_like_ids(
        [
            *scenario_plan.get("requirement_ids", []),
            *scenario_plan.get("evidence_ids", []),
            *[
                req
                for obligation_id in planned_obligation_ids
                for req in obligation_by_id.get(obligation_id, {}).get("requirement_ids", [])
            ],
        ]
    )
    planned_source_type = str(scenario_plan.get("source_type") or "inferred_case")
    allowed_text = _supported_text(planned_obligation_ids, obligation_by_id)
    violations: list[GuardrailViolation] = []

    scenario_type = str(scenario_payload.get("scenario_type") or "")
    planned_scenario_type = str(scenario_plan.get("scenario_type") or "")
    if scenario_type not in ALLOWED_SCENARIO_TYPES:
        violations.append(
            GuardrailViolation(
                "incorrect_category",
                f"Scenario category '{scenario_type}' is not allowed.",
            )
        )
    elif planned_scenario_type and scenario_type != planned_scenario_type:
        violations.append(
            GuardrailViolation(
                "incorrect_category",
                f"Scenario category '{scenario_type}' does not match planned category '{planned_scenario_type}'.",
            )
        )
    if planned_source_type not in ALLOWED_SOURCE_TYPES:
        violations.append(
            GuardrailViolation(
                "incorrect_source_type",
                f"Source type '{planned_source_type}' is not allowed.",
            )
        )

    cases = scenario_payload.get("cases") if isinstance(scenario_payload.get("cases"), list) else []
    seen_case_texts: list[tuple[str, str]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("draft_id") or f"case_{index + 1}")
        coverage = case.get("coverage") if isinstance(case.get("coverage"), dict) else {}
        coverage_requirements = requirement_like_ids(
            [
                *coverage.get("requirement_ids", []),
                *coverage.get("evidence_ids", []),
            ]
        )
        if not coverage_requirements:
            coverage_requirements = planned_requirements
            coverage["requirement_ids"] = planned_requirements
            case["coverage"] = coverage
        if not coverage_requirements:
            violations.append(
                GuardrailViolation(
                    "missing_requirement_references",
                    "Every generated case must reference at least one requirement-like ID.",
                    case_id=case_id,
                )
            )

        source_type = str(coverage.get("source_type") or planned_source_type)
        coverage["source_type"] = source_type
        if source_type == "inferred_case":
            coverage["inferred"] = True
        if source_type not in ALLOWED_SOURCE_TYPES:
            violations.append(
                GuardrailViolation(
                    "incorrect_source_type",
                    f"Case source type '{source_type}' is not allowed.",
                    case_id=case_id,
                )
            )

        missing_fields = _missing_case_fields(case)
        if missing_fields:
            violations.append(
                GuardrailViolation(
                    "missing_case_detail",
                    f"Case is missing required detail: {', '.join(missing_fields)}.",
                    case_id=case_id,
                )
            )

        expected = str(case.get("expected_result") or "")
        if _is_vague_expected(expected):
            violations.append(
                GuardrailViolation(
                    "vague_expected_result",
                    "Expected result must be clear and verifiable.",
                    case_id=case_id,
                )
            )

        title = str(case.get("title") or "")
        if _looks_combined(title) or _looks_combined(expected):
            violations.append(
                GuardrailViolation(
                    "combined_non_atomic_objective",
                    "Case appears to combine multiple primary behaviors.",
                    case_id=case_id,
                )
            )

        assumption_text = " ".join(
            str(value)
            for value in [
                *case.get("warnings", []),
                *coverage.get("assumptions", []),
            ]
        )
        if "assume" in assumption_text.lower() and not _is_supported(assumption_text, allowed_text):
            violations.append(
                GuardrailViolation(
                    "unsupported_assumption",
                    "Case contains an assumption not supported by source evidence.",
                    case_id=case_id,
                )
            )

        if scenario_type == TestScenarioType.PERFORMANCE or NON_FUNCTIONAL_RE.search(title + " " + expected):
            threshold_text = title + " " + expected + " " + _steps_text(case)
            if not MEASUREMENT_RE.search(threshold_text):
                violations.append(
                    GuardrailViolation(
                        "unmeasurable_non_functional_requirement",
                        "Non-functional case lacks a measurable source-backed assertion.",
                        case_id=case_id,
                    )
                )
            elif _invented_measurement(threshold_text, allowed_text):
                violations.append(
                    GuardrailViolation(
                        "unsupported_assumption",
                        "Case appears to invent a performance threshold not present in source evidence.",
                        case_id=case_id,
                    )
                )

        duplicate_key = _case_semantic_text(case)
        for previous_id, previous_text in seen_case_texts:
            if _similarity(previous_text, duplicate_key) >= 0.82:
                violations.append(
                    GuardrailViolation(
                        "duplicate_or_near_duplicate_case",
                        f"Case is near-duplicate of {previous_id}.",
                        case_id=case_id,
                    )
                )
                break
        seen_case_texts.append((case_id, duplicate_key))

    for memory in repository_memory or []:
        memory_text = " ".join(
            str(memory.get(key) or "")
            for key in ("title", "scenario_title", "section_name", "suite_name")
        )
        for case in cases:
            if not isinstance(case, dict):
                continue
            if _similarity(memory_text, _case_semantic_text(case)) >= 0.86:
                violations.append(
                    GuardrailViolation(
                        "duplicate_or_near_duplicate_case",
                        "Case appears already covered by repository memory.",
                        case_id=str(case.get("draft_id") or ""),
                    )
                )

    if planned_obligation_ids:
        covered = {
            str(item)
            for case in cases
            if isinstance(case, dict)
            for item in (case.get("coverage") or {}).get("obligation_ids", [])
        }
        missing = sorted(set(planned_obligation_ids) - covered)
        if missing:
            violations.append(
                GuardrailViolation(
                    "uncovered_requirements",
                    f"Scenario did not cover planned obligations: {', '.join(missing)}.",
                )
            )

    return GuardrailResult(violations=violations)


def format_guardrail_repair_instruction(result: GuardrailResult) -> str:
    details = [
        {
            "code": item.code,
            "message": item.message,
            "case_id": item.case_id,
        }
        for item in result.violations
        if item.severity == "error" and item.repairable
    ]
    return (
        "Repair the scenario JSON to satisfy BIAT deterministic generation guardrails. "
        "Keep only source-supported behavior. Ensure one primary behavior per case, "
        "coverage.requirement_ids/evidence_ids/source_type on every case, clear "
        "preconditions, steps, test_data, and verifiable expected_result. Do not invent "
        f"unsupported assumptions or performance thresholds. Violations: {details}"
    )


def _missing_case_fields(case: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("title", "preconditions", "expected_result"):
        if not str(case.get(field) or "").strip():
            missing.append(field)
    if not isinstance(case.get("test_data"), dict):
        missing.append("test_data")
    steps = case.get("steps")
    if not isinstance(steps, list) or not steps:
        missing.append("steps")
    else:
        for step in steps:
            if not isinstance(step, dict):
                missing.append("steps")
                break
            if not str(step.get("action") or "").strip() or not str(step.get("expected_outcome") or "").strip():
                missing.append("steps")
                break
    return sorted(set(missing))


def _is_vague_expected(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.lower()).strip()
    if len(normalized) < 12:
        return True
    return any(re.search(pattern, normalized) for pattern in VAGUE_EXPECTED_PATTERNS)


def _looks_combined(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value.lower()).strip()
    return bool(COMBINED_OBJECTIVE_RE.search(normalized))


def _supported_text(
    planned_obligation_ids: list[str],
    obligation_by_id: dict[str, dict[str, Any]],
) -> str:
    return " ".join(
        str(obligation_by_id.get(obligation_id, {}).get(key) or "")
        for obligation_id in planned_obligation_ids
        for key in ("behavior", "expected_outcome")
    ).lower()


def _is_supported(value: str, supported_text: str) -> bool:
    tokens = _tokens(value)
    if not tokens:
        return True
    supported = _tokens(supported_text)
    return len(tokens & supported) / max(len(tokens), 1) >= 0.45


def _invented_measurement(value: str, supported_text: str) -> bool:
    generated = {match.group(0).lower() for match in MEASUREMENT_RE.finditer(value)}
    if not generated:
        return False
    supported = supported_text.lower()
    return any(item not in supported for item in generated)


def _steps_text(case: dict[str, Any]) -> str:
    return " ".join(
        f"{step.get('action', '')} {step.get('expected_outcome', '')}"
        for step in case.get("steps", [])
        if isinstance(step, dict)
    )


def _case_semantic_text(case: dict[str, Any]) -> str:
    return " ".join(
        [
            str(case.get("title") or ""),
            str(case.get("preconditions") or ""),
            str(case.get("expected_result") or ""),
            _steps_text(case),
        ]
    )


def _similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(value or "")
        if len(token) > 2
    }
