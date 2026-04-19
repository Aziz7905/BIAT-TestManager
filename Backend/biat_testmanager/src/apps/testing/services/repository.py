#src/app/testing/services/repository.py
from __future__ import annotations

import copy
from copy import deepcopy
from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.testing.models import (
    TestCase,
    TestCaseRevision,
    TestScenario,
    TestSection,
    TestSuite,
)
from apps.testing.models.choices import (
    BusinessPriority,
    TestCaseDesignStatus,
    TestPriority,
    TestScenarioPolarity,
    TestScenarioType,
)

DEFAULT_TEST_SECTION_NAME = "General"
UNSET = object()


# ---------------------------------------------------------------------------
# Suite
# ---------------------------------------------------------------------------

@transaction.atomic
def create_test_suite(
    project,
    *,
    name: str,
    created_by=None,
    description: str = "",
    specification=None,
    folder_path: str = "",
) -> TestSuite:
    suite = TestSuite.objects.create(
        project=project,
        name=name,
        description=description,
        specification=specification,
        folder_path=folder_path,
        created_by=created_by,
    )
    get_or_create_default_section(suite)
    return suite


def get_or_create_default_section(suite) -> TestSection:
    default_section, _ = TestSection.objects.get_or_create(
        suite=suite,
        parent=None,
        name=DEFAULT_TEST_SECTION_NAME,
        defaults={"order_index": 0},
    )
    return default_section


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

def create_test_section(
    suite: TestSuite,
    *,
    name: str,
    parent: TestSection | None = None,
    order_index: int = 0,
) -> TestSection:
    return TestSection.objects.create(
        suite=suite,
        name=name,
        parent=parent,
        order_index=order_index,
    )


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

def create_test_scenario(
    section: TestSection,
    *,
    title: str,
    description: str = "",
    scenario_type: str = TestScenarioType.HAPPY_PATH,
    priority: str = TestPriority.MEDIUM,
    business_priority: str | None = None,
    polarity: str = TestScenarioPolarity.POSITIVE,
    ai_generated: bool = False,
    ai_confidence: float | None = None,
    order_index: int = 0,
) -> TestScenario:
    return TestScenario.objects.create(
        section=section,
        title=title,
        description=description,
        scenario_type=scenario_type,
        priority=priority,
        business_priority=business_priority,
        polarity=polarity,
        ai_generated=ai_generated,
        ai_confidence=ai_confidence,
        order_index=order_index,
    )


@transaction.atomic
def clone_test_scenario(scenario: TestScenario) -> TestScenario:
    """Clone a scenario and all its test cases into the same section."""
    cloned = TestScenario.objects.create(
        section=scenario.section,
        title=f"{scenario.title} Copy",
        description=scenario.description,
        scenario_type=scenario.scenario_type,
        priority=scenario.priority,
        business_priority=scenario.business_priority,
        polarity=scenario.polarity,
        ai_generated=scenario.ai_generated,
        ai_confidence=scenario.ai_confidence,
        order_index=scenario.order_index,
    )

    for case in scenario.cases.order_by("order_index", "title").prefetch_related(
        "linked_specifications"
    ):
        linked_specifications = list(case.linked_specifications.all())
        create_test_case_with_revision(
            scenario=cloned,
            title=case.title,
            preconditions=case.preconditions,
            steps=copy.deepcopy(case.steps),
            expected_result=case.expected_result,
            test_data=copy.deepcopy(case.test_data),
            design_status=case.design_status,
            automation_status=case.automation_status,
            ai_generated=case.ai_generated,
            jira_issue_key=case.jira_issue_key,
            on_failure=case.on_failure,
            timeout_ms=case.timeout_ms,
            order_index=case.order_index,
            linked_specifications=linked_specifications,
            source_snapshot_json={
                "cloned_from_case_id": str(case.id),
                "cloned_from_scenario_id": str(scenario.id),
            },
        )

    return cloned


@transaction.atomic
def clone_test_case(test_case: TestCase, *, created_by=None) -> TestCase:
    """Clone a case into the same scenario with a fresh revision history."""
    linked_specifications = list(test_case.linked_specifications.all())
    max_order_index = (
        TestCase.objects.filter(scenario=test_case.scenario).aggregate(
            max_order_index=Max("order_index")
        )["max_order_index"]
        or 0
    )

    return create_test_case_with_revision(
        scenario=test_case.scenario,
        title=f"{test_case.title} Copy",
        preconditions=test_case.preconditions,
        steps=copy.deepcopy(test_case.steps),
        expected_result=test_case.expected_result,
        test_data=copy.deepcopy(test_case.test_data),
        design_status=test_case.design_status,
        automation_status=test_case.automation_status,
        ai_generated=test_case.ai_generated,
        jira_issue_key=test_case.jira_issue_key,
        on_failure=test_case.on_failure,
        timeout_ms=test_case.timeout_ms,
        order_index=max_order_index + 1,
        linked_specifications=linked_specifications,
        created_by=created_by,
        source_snapshot_json={
            "cloned_from_case_id": str(test_case.id),
            "mutation_source": "api_clone",
        },
    )


# ---------------------------------------------------------------------------
# Design-status transitions
# ---------------------------------------------------------------------------

def approve_test_case(test_case: TestCase) -> TestCase:
    """Transition a test case to approved design status."""
    if test_case.design_status != TestCaseDesignStatus.APPROVED:
        test_case.design_status = TestCaseDesignStatus.APPROVED
        test_case.save(update_fields=["design_status", "updated_at"])
    return test_case


def archive_test_case(test_case: TestCase) -> TestCase:
    """Transition a test case to archived design status."""
    if test_case.design_status != TestCaseDesignStatus.ARCHIVED:
        test_case.design_status = TestCaseDesignStatus.ARCHIVED
        test_case.save(update_fields=["design_status", "updated_at"])
    return test_case


def build_case_source_snapshot(
    test_case: TestCase,
    *,
    linked_specifications: list[Any],
    extra_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = {
        "scenario_id": str(test_case.scenario_id),
        "section_id": str(test_case.scenario.section_id),
        "suite_id": str(test_case.scenario.section.suite_id),
        "project_id": str(test_case.scenario.section.suite.project_id),
        "design_status": test_case.design_status,
        "automation_status": test_case.automation_status,
        "on_failure": test_case.on_failure,
        "timeout_ms": test_case.timeout_ms,
        "linked_specification_ids": [str(specification.id) for specification in linked_specifications],
    }
    if extra_snapshot:
        snapshot.update(extra_snapshot)
    return snapshot


@transaction.atomic
def create_test_case_revision_snapshot(
    test_case: TestCase,
    *,
    created_by=None,
    linked_specifications: list[Any] | None = None,
    source_snapshot_json: dict[str, Any] | None = None,
) -> TestCaseRevision:
    resolved_linked_specifications = linked_specifications
    if resolved_linked_specifications is None:
        resolved_linked_specifications = list(test_case.linked_specifications.all())

    current_version = (
        test_case.revisions.aggregate(max_version=Max("version_number"))["max_version"] or 0
    )
    next_version = current_version + 1

    revision = TestCaseRevision.objects.create(
        test_case=test_case,
        version_number=next_version,
        title=test_case.title,
        preconditions=test_case.preconditions,
        steps=deepcopy(test_case.steps),
        expected_result=test_case.expected_result,
        test_data=deepcopy(test_case.test_data),
        created_by=created_by,
        source_snapshot_json=build_case_source_snapshot(
            test_case,
            linked_specifications=resolved_linked_specifications,
            extra_snapshot=source_snapshot_json,
        ),
    )
    if resolved_linked_specifications:
        revision.linked_specifications.set(resolved_linked_specifications)

    if test_case.version != next_version:
        type(test_case).objects.filter(pk=test_case.pk).update(version=next_version)
        test_case.version = next_version

    return revision


@transaction.atomic
def create_test_case_with_revision(
    *,
    scenario,
    linked_specifications: list[Any] | None = None,
    created_by=None,
    source_snapshot_json: dict[str, Any] | None = None,
    **case_fields,
) -> TestCase:
    test_case = TestCase.objects.create(scenario=scenario, **case_fields)
    if linked_specifications:
        test_case.linked_specifications.set(linked_specifications)

    create_test_case_revision_snapshot(
        test_case,
        created_by=created_by,
        linked_specifications=list(linked_specifications or []),
        source_snapshot_json=source_snapshot_json,
    )
    return test_case


@transaction.atomic
def update_test_case_with_revision(
    test_case: TestCase,
    *,
    linked_specifications=UNSET,
    created_by=None,
    source_snapshot_json: dict[str, Any] | None = None,
    **case_fields,
) -> TestCase:
    revision_fields_changed = any(
        field_name in case_fields
        and case_fields[field_name] != getattr(test_case, field_name)
        for field_name in TestCase.REVISION_FIELDS
    )

    linked_specifications_changed = False
    if linked_specifications is not UNSET:
        current_linked_ids = set(
            test_case.linked_specifications.values_list("id", flat=True)
        )
        next_linked_ids = {specification.id for specification in linked_specifications}
        linked_specifications_changed = current_linked_ids != next_linked_ids

    for attr, value in case_fields.items():
        setattr(test_case, attr, value)
    test_case.save()

    resolved_linked_specifications = None
    if linked_specifications is not UNSET:
        test_case.linked_specifications.set(linked_specifications)
        resolved_linked_specifications = list(linked_specifications)
    elif revision_fields_changed:
        resolved_linked_specifications = list(test_case.linked_specifications.all())

    if revision_fields_changed or linked_specifications_changed:
        create_test_case_revision_snapshot(
            test_case,
            created_by=created_by,
            linked_specifications=resolved_linked_specifications,
            source_snapshot_json=source_snapshot_json,
        )

    return test_case
