from __future__ import annotations

import re
from typing import Any

from apps.ai.models import AIGenerationContextType, AIGenerationRetrievedContext
from apps.testing.models import TestCase


def search_repository_memory(session, *, limit: int = 8) -> list[dict[str, Any]]:
    """Find similar existing tests so generation can avoid duplicates."""
    query_terms = _tokenize(session.objective)
    if not query_terms:
        return []

    queryset = (
        TestCase.objects.select_related(
            "scenario",
            "scenario__section",
            "scenario__section__suite",
        )
        .filter(scenario__section__suite__project=session.project)
        .order_by("-updated_at", "title")[:250]
    )

    scored: list[tuple[float, TestCase, str]] = []
    for test_case in queryset:
        searchable = " ".join(
            [
                test_case.title,
                test_case.expected_result,
                test_case.preconditions,
                test_case.scenario.title,
                test_case.scenario.section.name,
                test_case.scenario.section.suite.name,
            ]
        )
        terms = _tokenize(searchable)
        overlap = query_terms & terms
        if not overlap:
            continue
        score = len(overlap) / max(len(query_terms), 1)
        scored.append((score, test_case, ", ".join(sorted(overlap)[:8])))

    scored.sort(key=lambda item: (-item[0], item[1].title.lower()))
    results = [
        _case_context_item(test_case, score=score, reason=reason)
        for score, test_case, reason in scored[:limit]
    ]
    for item in results:
        AIGenerationRetrievedContext.objects.create(
            session=session,
            context_type=AIGenerationContextType.TEST_CASE,
            object_id=item["test_case_id"],
            score=item["score"],
            metadata_json={
                "title": item["title"],
                "scenario_id": item["scenario_id"],
                "scenario_title": item["scenario_title"],
                "section_id": item["section_id"],
                "suite_id": item["suite_id"],
                "similarity_reason": item["similarity_reason"],
            },
        )

    return results


def _case_context_item(test_case: TestCase, *, score: float, reason: str) -> dict[str, Any]:
    scenario = test_case.scenario
    section = scenario.section
    suite = section.suite
    return {
        "context_type": AIGenerationContextType.TEST_CASE,
        "test_case_id": str(test_case.id),
        "title": test_case.title,
        "scenario_id": str(scenario.id),
        "scenario_title": scenario.title,
        "section_id": str(section.id),
        "section_name": section.name,
        "suite_id": str(suite.id),
        "suite_name": suite.name,
        "design_status": test_case.design_status,
        "automation_status": test_case.automation_status,
        "score": round(score, 4),
        "similarity_reason": f"Shared terms: {reason}",
    }


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", (text or "").lower())
        if len(token) > 2
    }
