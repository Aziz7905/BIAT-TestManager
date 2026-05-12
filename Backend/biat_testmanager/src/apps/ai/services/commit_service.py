from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.schemas import normalize_draft_payload
from apps.specs.models import Specification
from apps.testing.models import TestSection, TestSuite
from apps.testing.models.choices import (
    TestCaseAutomationStatus,
    TestCaseDesignStatus,
)
from apps.testing.services.repository import (
    create_test_case_with_revision,
    create_test_scenario,
    create_test_section,
    create_test_suite,
)


class AICommitError(ValueError):
    """Raised when a reviewed AI draft cannot be committed safely."""


@transaction.atomic
def commit_selected_drafts(
    *,
    session: AIGenerationSession,
    create_as_approved: bool = False,
) -> dict[str, Any]:
    """Save reviewed AI drafts into canonical BIAT repository models."""
    if session.status not in {
        AIGenerationSessionStatus.READY_FOR_REVIEW,
        AIGenerationSessionStatus.REVIEWING,
    }:
        raise AICommitError("Only reviewed AI generation sessions can be committed.")

    decisions = session.review_decisions or {}
    payload = decisions.get("draft_payload") or decisions.get("reviewed_draft") or session.draft_payload
    draft = normalize_draft_payload(payload)

    selected_case_ids = _id_set(decisions.get("selected_case_ids"))
    selected_scenario_ids = _id_set(decisions.get("selected_scenario_ids"))
    dropped_case_ids = _id_set(decisions.get("dropped_case_ids"))

    summary: dict[str, Any] = {
        "suite_ids": [],
        "section_ids": [],
        "scenario_ids": [],
        "case_ids": [],
        "revision_ids": [],
        "created_case_count": 0,
    }

    suite = _resolve_suite(session, draft["suite"])
    _append_unique(summary["suite_ids"], str(suite.id))

    design_status = (
        TestCaseDesignStatus.APPROVED
        if create_as_approved
        else TestCaseDesignStatus.DRAFT
    )

    for section_index, section_payload in enumerate(draft["sections"]):
        _commit_section_tree(
            session=session,
            suite=suite,
            section_payload=section_payload,
            summary=summary,
            design_status=design_status,
            selected_case_ids=selected_case_ids,
            selected_scenario_ids=selected_scenario_ids,
            dropped_case_ids=dropped_case_ids,
            parent_section=None,
            section_index=section_index,
        )

    if summary["created_case_count"] == 0:
        raise AICommitError("No selected test cases were found in the reviewed draft.")

    session.draft_payload = draft
    session.saved_object_ids = summary
    session.status = AIGenerationSessionStatus.SAVED
    session.completed_at = timezone.now()
    session.save(
        update_fields=[
            "draft_payload",
            "saved_object_ids",
            "status",
            "completed_at",
            "updated_at",
        ]
    )
    return summary


def _resolve_suite(session: AIGenerationSession, suite_payload: dict[str, Any]) -> TestSuite:
    if session.target_suite_id:
        return session.target_suite

    suite = TestSuite.objects.filter(
        project=session.project,
        folder_path="",
        name=suite_payload["name"],
    ).first()
    created_new = suite is None
    if created_new:
        suite = create_test_suite(
            session.project,
            name=suite_payload["name"],
            description=suite_payload["description"],
            specification=session.attached_specification,
            created_by=session.created_by,
        )
    if created_new and not suite.ai_generated:
        suite.ai_generated = True
        suite.save(update_fields=["ai_generated"])
    return suite


def _resolve_section(
    session: AIGenerationSession,
    suite: TestSuite,
    section_payload: dict[str, Any],
    *,
    parent_section: TestSection | None,
    order_index: int,
) -> TestSection:
    if session.target_section_id and parent_section is None:
        return session.target_section

    section = TestSection.objects.filter(
        suite=suite,
        parent=parent_section,
        name=section_payload["name"],
    ).first()
    if section is not None:
        return section
    return create_test_section(
        suite,
        name=section_payload["name"],
        parent=parent_section,
        order_index=section_payload.get("order_index", order_index),
    )


def _commit_section_tree(
    *,
    session: AIGenerationSession,
    suite: TestSuite,
    section_payload: dict[str, Any],
    summary: dict[str, Any],
    design_status: str,
    selected_case_ids: set[str],
    selected_scenario_ids: set[str],
    dropped_case_ids: set[str],
    parent_section: TestSection | None,
    section_index: int,
) -> None:
    if not _section_has_selected_cases(
        section_payload,
        selected_case_ids=selected_case_ids,
        selected_scenario_ids=selected_scenario_ids,
        dropped_case_ids=dropped_case_ids,
    ):
        return

    section = _resolve_section(
        session,
        suite,
        section_payload,
        parent_section=parent_section,
        order_index=section_index,
    )
    _append_unique(summary["section_ids"], str(section.id))

    for scenario_index, scenario_payload in enumerate(section_payload["scenarios"]):
        selected_cases = [
            case_payload
            for case_payload in scenario_payload["cases"]
            if _case_is_selected(
                case_payload,
                scenario_payload,
                selected_case_ids=selected_case_ids,
                selected_scenario_ids=selected_scenario_ids,
                dropped_case_ids=dropped_case_ids,
            )
        ]
        if not selected_cases:
            continue

        scenario = create_test_scenario(
            section,
            title=scenario_payload["title"],
            description=scenario_payload["description"],
            scenario_type=scenario_payload["scenario_type"],
            priority=scenario_payload["priority"],
            business_priority=scenario_payload["business_priority"],
            polarity=scenario_payload["polarity"],
            ai_generated=True,
            ai_confidence=scenario_payload["confidence"],
            order_index=scenario_payload.get("order_index", scenario_index),
        )
        summary["scenario_ids"].append(str(scenario.id))

        for case_index, case_payload in enumerate(selected_cases):
            linked_specifications = _resolve_linked_specifications(session, case_payload)
            test_case = create_test_case_with_revision(
                scenario=scenario,
                title=case_payload["title"],
                preconditions=case_payload["preconditions"],
                steps=case_payload["steps"],
                expected_result=case_payload["expected_result"],
                test_data=case_payload["test_data"],
                design_status=design_status,
                automation_status=TestCaseAutomationStatus.MANUAL,
                ai_generated=True,
                jira_issue_key=case_payload.get("jira_issue_key") or session.jira_issue_key or "",
                order_index=case_payload.get("order_index", case_index),
                linked_specifications=linked_specifications,
                created_by=session.created_by,
                source_snapshot_json={
                    "mutation_source": "ai_generation_commit",
                    "ai_generation_session_id": str(session.id),
                    "draft_case_id": case_payload["draft_id"],
                    "draft_scenario_id": scenario_payload["draft_id"],
                },
            )
            latest_revision = test_case.revisions.order_by("-version_number").first()
            summary["case_ids"].append(str(test_case.id))
            if latest_revision:
                summary["revision_ids"].append(str(latest_revision.id))
            summary["created_case_count"] += 1

    for child_index, child_payload in enumerate(section_payload.get("children", [])):
        _commit_section_tree(
            session=session,
            suite=suite,
            section_payload=child_payload,
            summary=summary,
            design_status=design_status,
            selected_case_ids=selected_case_ids,
            selected_scenario_ids=selected_scenario_ids,
            dropped_case_ids=dropped_case_ids,
            parent_section=section,
            section_index=child_index,
        )


def _resolve_linked_specifications(
    session: AIGenerationSession,
    case_payload: dict[str, Any],
) -> list[Specification]:
    linked_ids = set(case_payload.get("linked_spec_ids") or [])
    if session.attached_specification_id:
        linked_ids.add(str(session.attached_specification_id))
    if not linked_ids:
        return []
    return list(
        Specification.objects.filter(
            project=session.project,
            id__in=linked_ids,
        )
    )


def _case_is_selected(
    case_payload: dict[str, Any],
    scenario_payload: dict[str, Any],
    *,
    selected_case_ids: set[str],
    selected_scenario_ids: set[str],
    dropped_case_ids: set[str],
) -> bool:
    case_id = case_payload["draft_id"]
    scenario_id = scenario_payload["draft_id"]
    if case_id in dropped_case_ids:
        return False
    if selected_case_ids:
        return case_id in selected_case_ids
    if selected_scenario_ids:
        return scenario_id in selected_scenario_ids
    return case_payload.get("selected", True) is not False


def _section_has_selected_cases(
    section_payload: dict[str, Any],
    *,
    selected_case_ids: set[str],
    selected_scenario_ids: set[str],
    dropped_case_ids: set[str],
) -> bool:
    for scenario_payload in section_payload.get("scenarios", []):
        for case_payload in scenario_payload.get("cases", []):
            if _case_is_selected(
                case_payload,
                scenario_payload,
                selected_case_ids=selected_case_ids,
                selected_scenario_ids=selected_scenario_ids,
                dropped_case_ids=dropped_case_ids,
            ):
                return True
    return any(
        _section_has_selected_cases(
            child_payload,
            selected_case_ids=selected_case_ids,
            selected_scenario_ids=selected_scenario_ids,
            dropped_case_ids=dropped_case_ids,
        )
        for child_payload in section_payload.get("children", [])
    )


def _id_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if value}


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)
