from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from apps.testing.models.choices import (
    BusinessPriority,
    TestPriority,
    TestScenarioPolarity,
    TestScenarioType,
)

EVIDENCE_TYPES = {
    "requirement",
    "user_story",
    "acceptance_criterion",
    "business_rule",
    "validation_rule",
    "nfr",
    "data_field",
    "api_contract",
    "screen_or_flow",
    "traceability_link",
    "unknown_context",
}

ID_RE = re.compile(
    r"\b(?:FR|REQ|BR|NFR|US|TS|TC|AC|API|RULE|STORY|CR|SR)[-_]?[A-Z0-9]*[-_]?\d+\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
NEGATIVE_RE = re.compile(
    r"\b(reject|invalid|missing|mismatch|duplicate|unauthori[sz]ed|forbid|prevent|"
    r"block|den(y|ied)|error|fail|insufficient|non[- ]?positive|not allowed)\b",
    re.IGNORECASE,
)
EDGE_RE = re.compile(
    r"\b(boundary|edge|retry|repeated|concurrent|idempotent|empty|none|zero|"
    r"minimum|maximum|min|max|timeout|partial)\b",
    re.IGNORECASE,
)
SECURITY_RE = re.compile(
    r"\b(security|authorization|authentication|session|credential|password|ssn|"
    r"access control|cross[- ]?customer|privilege|tls|cookie|sensitive)\b",
    re.IGNORECASE,
)
PERFORMANCE_RE = re.compile(
    r"\b(performance|load|response time|latency|throughput|p95|percentile|"
    r"availability|sla|seconds?)\b",
    re.IGNORECASE,
)
ACCESSIBILITY_RE = re.compile(
    r"\b(accessibility|a11y|keyboard|screen reader|contrast|focus order|aria)\b",
    re.IGNORECASE,
)


def compile_semantic_evidence(
    *,
    objective: str,
    generation_context: list[dict[str, Any]],
    requirement_extraction: dict[str, Any],
) -> list[dict[str, Any]]:
    """Normalize heterogeneous source context into source-backed evidence.

    This is intentionally format-agnostic: it uses generic record structure,
    identifiers, labels, and wording. It does not depend on workbook sheet names
    or client-specific templates.
    """
    evidence: list[dict[str, Any]] = []
    for index, item in enumerate(generation_context):
        content = _clean_text(item.get("content"))
        title = _clean_text(item.get("title") or item.get("specification_title"))
        if not content and not title:
            continue
        field_map = _field_map(content)
        spec_item = item.get("spec_item") if isinstance(item.get("spec_item"), dict) else {}
        text = "\n".join(part for part in (title, content) if part)
        ids = _ids(text)
        evidence_id = (
            _clean_text(spec_item.get("external_key"))
            or _primary_evidence_id(ids)
            or _synthetic_id(item, index)
        )
        evidence_type = _evidence_type_for_spec_item(spec_item) or _classify_evidence(text, field_map, evidence_id)
        statement = _statement_for(field_map, title=title, content=content)
        if not statement:
            continue
        related_ids = sorted(set(ids) - {evidence_id.upper()})
        evidence.append(
            {
                "evidence_id": evidence_id,
                "evidence_type": evidence_type,
                "statement": statement[:1200],
                "module": _clean_text(spec_item.get("module")) or _module_for(item, field_map),
                "feature": _clean_text(spec_item.get("feature")) or _feature_for(field_map),
                "related_ids": related_ids,
                "priority": _clean_text(spec_item.get("priority")) or _priority_for(field_map, text),
                "source_refs": [_source_ref(item)],
                "confidence": _confidence_for(evidence_type, ids, field_map),
                "assumptions": [],
            }
        )

    extracted = _evidence_from_requirement_extraction(requirement_extraction)
    evidence.extend(extracted)
    return _dedupe_evidence(evidence)


def build_coverage_obligations(
    semantic_evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Group source evidence into non-duplicate test-design obligations."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in semantic_evidence:
        if item.get("evidence_type") in {"traceability_link", "data_field", "unknown_context"}:
            continue
        key = _obligation_key(item)
        buckets[key].append(item)

    obligations: list[dict[str, Any]] = []
    merged: list[dict[str, Any]] = []
    for index, items in enumerate(buckets.values(), start=1):
        primary = _primary_obligation_evidence(items)
        text = " ".join(str(item.get("statement") or "") for item in items)
        scenario_type = _scenario_type_for(text, primary.get("evidence_type"))
        polarity = _polarity_for(text, scenario_type)
        module = _best_value([item.get("module") for item in items]) or "Generated Coverage"
        feature = _best_value([item.get("feature") for item in items])
        evidence_ids = sorted(
            {
                str(item.get("evidence_id") or "").upper()
                for item in items
                if item.get("evidence_id")
            }
        )
        requirement_ids = _requirement_ids_for(items)
        source_refs = _dedupe_json_refs(
            ref
            for item in items
            for ref in item.get("source_refs", [])
            if isinstance(ref, dict)
        )
        obligation_id = f"OBL-{index:04d}"
        if len(items) > 1:
            merged.append(
                {
                    "obligation_id": obligation_id,
                    "evidence_ids": evidence_ids,
                    "reason": "Related evidence describes the same test intent.",
                }
            )
        obligations.append(
            {
                "obligation_id": obligation_id,
                "behavior": _behavior_for(items),
                "module_or_area": module,
                "feature": feature,
                "scenario_hint": _scenario_hint(module, feature, scenario_type, polarity),
                "scenario_group_key": _scenario_group_key(
                    module,
                    feature,
                    scenario_type,
                    polarity,
                    items,
                ),
                "scenario_type": scenario_type,
                "polarity": polarity,
                "priority": _test_priority_for(items, scenario_type),
                "business_priority": _business_priority_for(items),
                "evidence_ids": evidence_ids,
                "requirement_ids": requirement_ids,
                "source_type": _source_type_for(items),
                "source_refs": source_refs,
                "expected_outcome": _expected_outcome_for(items),
                "assumptions": _assumptions_for(items),
            }
        )
    return obligations, {"merged_obligations": merged}


def selected_scenarios_from_obligations(
    obligations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obligation in obligations:
        grouped[str(obligation.get("scenario_group_key") or obligation["obligation_id"])].append(obligation)

    selected: list[dict[str, Any]] = []
    for index, group in enumerate(grouped.values(), start=1):
        first = group[0]
        title = _selected_scenario_title(group)
        selected.append(
            {
                "draft_scenario_id": f"scenario_{index}",
                "candidate_id": str(first.get("scenario_group_key") or first["obligation_id"]),
                "title": title,
                "category": first.get("scenario_type") or TestScenarioType.HAPPY_PATH,
                "scenario_type": first.get("scenario_type") or TestScenarioType.HAPPY_PATH,
                "priority": _max_test_priority(group),
                "business_priority": _max_business_priority(group),
                "polarity": first.get("polarity") or TestScenarioPolarity.POSITIVE,
                "section_path": _section_path_for(group),
                "intended_case_count": len(group),
                "user_story": _scenario_story(group),
                "covered_obligation_ids": [item["obligation_id"] for item in group],
                "evidence_ids": sorted(
                    {
                        evidence_id
                        for item in group
                        for evidence_id in item.get("evidence_ids", [])
                    }
                ),
                "requirement_ids": sorted(
                    {
                        requirement_id
                        for item in group
                        for requirement_id in item.get("requirement_ids", [])
                    }
                ),
                "source_type": _scenario_source_type(group),
                "source_refs": _dedupe_json_refs(
                    ref
                    for item in group
                    for ref in item.get("source_refs", [])
                    if isinstance(ref, dict)
                ),
                "assumptions": _strings(
                    assumption
                    for item in group
                    for assumption in item.get("assumptions", [])
                ),
            }
        )
    return selected


def coverage_audit_for_draft(
    *,
    obligations: list[dict[str, Any]],
    draft_payload: dict[str, Any],
) -> dict[str, Any]:
    covered: set[str] = set()
    duplicate_keys: dict[str, list[str]] = defaultdict(list)
    unsupported: list[dict[str, Any]] = []
    enum_warnings: list[dict[str, Any]] = []

    for scenario in _iter_scenarios(draft_payload):
        scenario_type = scenario.get("scenario_type")
        polarity = scenario.get("polarity")
        case_polarities: set[str] = set()
        for case in scenario.get("cases", []):
            coverage = case.get("coverage") if isinstance(case.get("coverage"), dict) else {}
            ids = [str(item) for item in coverage.get("obligation_ids") or [] if item]
            evidence_ids = [str(item) for item in coverage.get("evidence_ids") or [] if item]
            covered.update(ids)
            if not ids and not evidence_ids:
                unsupported.append(
                    {
                        "case_id": case.get("draft_id"),
                        "case_title": case.get("title"),
                        "reason": "Case has no evidence or obligation link.",
                    }
                )
            key = _case_duplicate_key(scenario, case, ids, evidence_ids)
            duplicate_keys[key].append(str(case.get("draft_id") or case.get("title") or "case"))
            if _case_looks_negative(case):
                case_polarities.add(TestScenarioPolarity.NEGATIVE)
            else:
                case_polarities.add(TestScenarioPolarity.POSITIVE)

        if len(case_polarities) > 1:
            enum_warnings.append(
                {
                    "scenario_id": scenario.get("draft_id"),
                    "scenario_title": scenario.get("title"),
                    "reason": "Scenario contains cases with mixed inferred polarity.",
                    "scenario_polarity": polarity,
                }
            )
        if scenario_type in {TestScenarioType.PERFORMANCE, TestScenarioType.SECURITY}:
            continue

    all_ids = {item["obligation_id"] for item in obligations}
    duplicate_cases = [
        {"key": key, "case_ids": ids}
        for key, ids in duplicate_keys.items()
        if len(ids) > 1
    ]
    return {
        "obligations_total": len(all_ids),
        "obligations_covered": len(covered & all_ids),
        "obligations_uncovered": sorted(all_ids - covered),
        "duplicate_candidates": duplicate_cases,
        "unsupported_claim_warnings": unsupported,
        "enum_alignment_warnings": enum_warnings,
    }


def requirement_like_ids(values: list[str]) -> list[str]:
    return sorted(
        {
            str(value).upper()
            for value in values
            if str(value).upper().startswith(("FR", "REQ", "NFR", "BR", "US", "API"))
        }
    )


def _field_map(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in content.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = _clean_text(key).lower().replace(" ", "_")
        value = _clean_text(value)
        if key and value:
            fields[key] = value
    return fields


def _ids(text: str) -> list[str]:
    return sorted({match.group(0).upper().replace("_", "-") for match in ID_RE.finditer(text or "")})


def _primary_evidence_id(ids: list[str]) -> str:
    return ids[0] if ids else ""


def _synthetic_id(item: dict[str, Any], index: int) -> str:
    seed = "|".join(
        str(item.get(key) or "")
        for key in ("fragment_id", "chunk_id", "title", "content")
    )
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"EV-{index + 1:04d}-{digest}".upper()


def _classify_evidence(text: str, field_map: dict[str, str], evidence_id: str) -> str:
    prefix = evidence_id.split("-", 1)[0].upper()
    keys = set(field_map)
    lowered = text.lower()
    if prefix == "US" or "user_story" in keys or "persona" in keys:
        return "user_story"
    if prefix == "BR" or "business_rule" in keys or "rationale" in keys:
        return "business_rule"
    if prefix == "NFR" or PERFORMANCE_RE.search(text):
        return "nfr"
    if prefix in {"TS", "TC", "AC"} or "expected_result" in keys or "test_steps" in keys:
        return "acceptance_criterion"
    if prefix == "API" or "endpoint" in keys or "api" in lowered:
        return "api_contract"
    if {"entity", "field"} <= keys or "logical_type" in keys:
        return "data_field"
    if "acceptance_criteria" in keys or "given" in lowered and "when" in lowered and "then" in lowered:
        return "acceptance_criterion"
    if "requirement" in keys or "shall" in lowered:
        return "requirement"
    if "related_fr_ids" in keys or "coverage_status" in keys:
        return "traceability_link"
    if NEGATIVE_RE.search(text):
        return "validation_rule"
    if "screen" in lowered or "page" in lowered or "flow" in lowered:
        return "screen_or_flow"
    return "unknown_context"


def _evidence_type_for_spec_item(spec_item: dict[str, Any]) -> str:
    item_type = str(spec_item.get("item_type") or "")
    mapping = {
        "requirement": "requirement",
        "acceptance_criterion": "acceptance_criterion",
        "business_rule": "business_rule",
        "validation_rule": "validation_rule",
        "user_story": "user_story",
        "nfr": "nfr",
        "test_case": "acceptance_criterion",
        "context": "unknown_context",
    }
    return mapping.get(item_type, "")


def _statement_for(field_map: dict[str, str], *, title: str, content: str) -> str:
    preferred = [
        "requirement",
        "business_rule",
        "user_story",
        "scenario",
        "acceptance_criteria",
        "expected_result",
        "validation_rule",
        "description",
    ]
    parts = [field_map[key] for key in preferred if field_map.get(key)]
    if parts:
        return " ".join(parts)
    return content or title


def _module_for(item: dict[str, Any], field_map: dict[str, str]) -> str:
    for key in ("module", "epic", "area", "component", "feature", "section"):
        if field_map.get(key):
            return field_map[key][:160]
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    return _clean_text(
        item.get("section_label")
        or provenance.get("sheet")
        or item.get("component_tag")
        or item.get("specification_title")
    )[:160]


def _feature_for(field_map: dict[str, str]) -> str:
    for key in ("story_id", "epic", "feature", "area", "scenario"):
        if field_map.get(key):
            return field_map[key][:160]
    return ""


def _priority_for(field_map: dict[str, str], text: str) -> str:
    raw = " ".join(
        field_map.get(key, "")
        for key in ("priority", "business_priority", "release", "coverage_status")
    )
    value = (raw or text).lower()
    if "must" in value or "critical" in value or "high" in value:
        return "high"
    if "could" in value or "low" in value:
        return "low"
    return "medium"


def _source_ref(item: dict[str, Any]) -> dict[str, Any]:
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    spec_item = item.get("spec_item") if isinstance(item.get("spec_item"), dict) else {}
    source_metadata = item.get("source_metadata") if isinstance(item.get("source_metadata"), dict) else {}
    item_metadata = spec_item.get("source_metadata") if isinstance(spec_item.get("source_metadata"), dict) else {}
    return {
        "context_type": item.get("context_type") or item.get("file_type") or "",
        "fragment_id": item.get("fragment_id") or "",
        "chunk_id": item.get("chunk_id") or "",
        "spec_item_id": spec_item.get("id") or "",
        "spec_item_external_key": spec_item.get("external_key") or "",
        "title": item.get("title") or item.get("specification_title") or "",
        "section_label": item.get("section_label") or "",
        "provenance": provenance
        or item_metadata.get("structure")
        or source_metadata.get("record", {}).get("structure", {})
        or {},
    }


def _confidence_for(evidence_type: str, ids: list[str], field_map: dict[str, str]) -> float:
    score = 0.45
    if evidence_type != "unknown_context":
        score += 0.2
    if ids:
        score += 0.2
    if field_map:
        score += 0.1
    return min(score, 0.95)


def _evidence_from_requirement_extraction(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(extraction, dict):
        return []
    module = _clean_text(extraction.get("system_or_process_name")) or "Extracted Requirements"
    evidence: list[dict[str, Any]] = []
    typed_fields = {
        "business_rules": "business_rule",
        "validation_rules": "validation_rule",
        "error_conditions": "validation_rule",
        "acceptance_criteria": "acceptance_criterion",
        "update_rules": "requirement",
        "generated_outputs": "requirement",
        "apis": "api_contract",
        "fields": "data_field",
        "screens": "screen_or_flow",
    }
    index = 0
    for field_name, evidence_type in typed_fields.items():
        values = extraction.get(field_name)
        if not isinstance(values, list):
            continue
        for value in values:
            statement = _clean_text(value if isinstance(value, str) else str(value))
            if not statement:
                continue
            index += 1
            ids = _ids(statement)
            evidence.append(
                {
                    "evidence_id": _primary_evidence_id(ids) or f"REQ-INF-{index:04d}",
                    "evidence_type": evidence_type,
                    "statement": statement[:1200],
                    "module": module,
                    "feature": "",
                    "related_ids": sorted(set(ids)),
                    "priority": "medium",
                    "source_refs": [{"context_type": "requirement_extraction", "field": field_name}],
                    "confidence": 0.7,
                    "assumptions": [],
                }
            )
    return evidence


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        key = str(item.get("evidence_id") or _normalize_key(item.get("statement"))).upper()
        if key not in merged:
            merged[key] = dict(item)
            continue
        existing = merged[key]
        existing["source_refs"] = _dedupe_json_refs(
            [*existing.get("source_refs", []), *item.get("source_refs", [])]
        )
        existing["related_ids"] = sorted(
            set(existing.get("related_ids", [])) | set(item.get("related_ids", []))
        )
        if len(str(item.get("statement") or "")) > len(str(existing.get("statement") or "")):
            existing["statement"] = item["statement"]
    return list(merged.values())


def _obligation_key(item: dict[str, Any]) -> str:
    ids = [str(value).upper() for value in item.get("related_ids", []) if value]
    ids.extend([str(item.get("evidence_id") or "").upper()])
    for value in ids:
        if value.startswith(("FR", "REQ", "NFR", "BR", "US", "API")):
            return value
    module = _normalize_key(item.get("module"))
    behavior = _normalize_key(item.get("statement"))
    return f"{module}:{behavior[:80]}"


def _primary_obligation_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
    order = [
        "requirement",
        "acceptance_criterion",
        "business_rule",
        "validation_rule",
        "nfr",
        "api_contract",
        "user_story",
    ]
    return sorted(
        items,
        key=lambda item: order.index(item.get("evidence_type"))
        if item.get("evidence_type") in order
        else len(order),
    )[0]


def _scenario_type_for(text: str, evidence_type: str | None) -> str:
    if evidence_type == "nfr" or PERFORMANCE_RE.search(text):
        return TestScenarioType.PERFORMANCE
    if SECURITY_RE.search(text):
        return TestScenarioType.SECURITY
    if ACCESSIBILITY_RE.search(text):
        return TestScenarioType.ACCESSIBILITY
    if EDGE_RE.search(text):
        return TestScenarioType.EDGE_CASE
    if NEGATIVE_RE.search(text) or evidence_type == "validation_rule":
        return TestScenarioType.ALTERNATIVE_FLOW
    return TestScenarioType.HAPPY_PATH


def _requirement_ids_for(items: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for item in items:
        values.append(str(item.get("evidence_id") or ""))
        values.extend(str(value) for value in item.get("related_ids", []) if value)
    requirement_ids = requirement_like_ids(values)
    if requirement_ids:
        return requirement_ids
    return [
        f"REQ-INF-{hashlib.sha1(str(item.get('evidence_id') or item.get('statement') or '').encode('utf-8', errors='ignore')).hexdigest()[:8].upper()}"
        for item in items
    ][:1]


def _source_type_for(items: list[dict[str, Any]]) -> str:
    types = {str(item.get("evidence_type") or "") for item in items}
    if types & {"requirement", "business_rule", "validation_rule", "nfr", "api_contract"}:
        return "explicit_requirement"
    if "acceptance_criterion" in types:
        return "acceptance_criterion"
    return "inferred_case"


def _scenario_source_type(group: list[dict[str, Any]]) -> str:
    values = {str(item.get("source_type") or "inferred_case") for item in group}
    if "explicit_requirement" in values:
        return "explicit_requirement"
    if "acceptance_criterion" in values:
        return "acceptance_criterion"
    return "inferred_case"


def _polarity_for(text: str, scenario_type: str) -> str:
    if scenario_type in {TestScenarioType.SECURITY}:
        return TestScenarioPolarity.NEGATIVE if NEGATIVE_RE.search(text) else TestScenarioPolarity.POSITIVE
    if NEGATIVE_RE.search(text):
        return TestScenarioPolarity.NEGATIVE
    return TestScenarioPolarity.POSITIVE


def _behavior_for(items: list[dict[str, Any]]) -> str:
    primary = _primary_obligation_evidence(items)
    return str(primary.get("statement") or "").strip()[:500]


def _expected_outcome_for(items: list[dict[str, Any]]) -> str:
    for item in items:
        statement = str(item.get("statement") or "").strip()
        if item.get("evidence_type") in {"acceptance_criterion", "validation_rule"} and statement:
            return statement[:500]
    return _behavior_for(items)


def _scenario_hint(module: str, feature: str, scenario_type: str, polarity: str) -> str:
    subject = feature or module or "Generated Coverage"
    if scenario_type == TestScenarioType.PERFORMANCE:
        return f"{subject} performance coverage"
    if scenario_type == TestScenarioType.SECURITY:
        return f"{subject} security coverage"
    if polarity == TestScenarioPolarity.NEGATIVE:
        return f"{subject} validation and rejection coverage"
    return f"{subject} successful behavior"


def _scenario_group_key(
    module: str,
    feature: str,
    scenario_type: str,
    polarity: str,
    items: list[dict[str, Any]],
) -> str:
    story = _first_related(items, "US")
    return ":".join(
        [
            _normalize_key(module),
            _normalize_key(feature or story),
            scenario_type,
            polarity,
        ]
    )


def _first_related(items: list[dict[str, Any]], prefix: str) -> str:
    for item in items:
        for value in [item.get("evidence_id"), *item.get("related_ids", [])]:
            candidate = str(value or "").upper()
            if candidate.startswith(prefix):
                return candidate
    return ""


def _test_priority_for(items: list[dict[str, Any]], scenario_type: str) -> str:
    if scenario_type == TestScenarioType.SECURITY:
        return TestPriority.CRITICAL
    priorities = {str(item.get("priority") or "").lower() for item in items}
    if priorities & {"critical", "high"}:
        return TestPriority.HIGH
    if "low" in priorities:
        return TestPriority.LOW
    return TestPriority.MEDIUM


def _business_priority_for(items: list[dict[str, Any]]) -> str:
    priorities = {str(item.get("priority") or "").lower() for item in items}
    if priorities & {"critical", "high", "must"}:
        return BusinessPriority.MUST_HAVE
    if "low" in priorities:
        return BusinessPriority.COULD_HAVE
    return BusinessPriority.SHOULD_HAVE


def _assumptions_for(items: list[dict[str, Any]]) -> list[str]:
    return _strings(
        assumption
        for item in items
        for assumption in item.get("assumptions", [])
    )


def _selected_scenario_title(group: list[dict[str, Any]]) -> str:
    first = group[0]
    hint = str(first.get("scenario_hint") or "").strip()
    return hint[:500] or str(first.get("behavior") or "Generated scenario")[:500]


def _max_test_priority(group: list[dict[str, Any]]) -> str:
    order = {
        TestPriority.CRITICAL: 4,
        TestPriority.HIGH: 3,
        TestPriority.MEDIUM: 2,
        TestPriority.LOW: 1,
    }
    return max((item.get("priority") or TestPriority.MEDIUM for item in group), key=lambda value: order.get(value, 0))


def _max_business_priority(group: list[dict[str, Any]]) -> str:
    order = {
        BusinessPriority.MUST_HAVE: 4,
        BusinessPriority.SHOULD_HAVE: 3,
        BusinessPriority.COULD_HAVE: 2,
        BusinessPriority.WONT_HAVE: 1,
    }
    return max(
        (item.get("business_priority") or BusinessPriority.SHOULD_HAVE for item in group),
        key=lambda value: order.get(value, 0),
    )


def _section_path_for(group: list[dict[str, Any]]) -> list[str]:
    module = _best_value([item.get("module_or_area") for item in group]) or "Generated Coverage"
    return [module[:300]]


def _scenario_story(group: list[dict[str, Any]]) -> str:
    behaviors = [str(item.get("behavior") or "").strip() for item in group]
    return " ".join(item for item in behaviors if item)[:1200]


def _iter_scenarios(draft_payload: dict[str, Any]):
    for section in draft_payload.get("sections", []):
        yield from _iter_section_scenarios(section)


def _iter_section_scenarios(section: dict[str, Any]):
    for scenario in section.get("scenarios", []):
        if isinstance(scenario, dict):
            yield scenario
    for child in section.get("children", []):
        if isinstance(child, dict):
            yield from _iter_section_scenarios(child)


def _case_duplicate_key(
    scenario: dict[str, Any],
    case: dict[str, Any],
    obligation_ids: list[str],
    evidence_ids: list[str],
) -> str:
    basis = obligation_ids or evidence_ids or [case.get("title", "")]
    return "|".join(
        [
            _normalize_key(scenario.get("title")),
            _normalize_key(case.get("expected_result")),
            ",".join(sorted(basis)),
        ]
    )


def _case_looks_negative(case: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(case.get("title") or ""),
            str(case.get("expected_result") or ""),
            str(case.get("preconditions") or ""),
        ]
    )
    return bool(NEGATIVE_RE.search(text))


def _best_value(values) -> str:
    cleaned = [str(value).strip() for value in values if str(value or "").strip()]
    if not cleaned:
        return ""
    return max(cleaned, key=len)


def _dedupe_json_refs(values) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for value in values:
        key = repr(sorted(value.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


def _strings(values) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        output.append(cleaned)
    return output


def _normalize_key(value: Any) -> str:
    words = WORD_RE.findall(str(value or "").lower())
    return "-".join(words[:16])


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"\s+", " ", value).strip()
