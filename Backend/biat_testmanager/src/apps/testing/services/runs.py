"""
Services for TestPlan, TestRun, and TestRunCase lifecycle management.

Authority model: plan/run management requires project owner or editor role.
Expansion: suites and sections are expanded into run-cases that each pin the
latest available TestCaseRevision at the moment the run is created.
Compatibility shim: one-off executions triggered directly from TestCase still
work — get_or_create_adhoc_run_case auto-creates a lightweight run and run-case
so every TestExecution always has a revision-safe reference.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.testing.models import (
    TestCase,
    TestPlan,
    TestPlanStatus,
    TestRun,
    TestRunCase,
    TestRunCaseStatus,
    TestRunStatus,
    TestRunTriggerType,
)


# ---------------------------------------------------------------------------
# Plan helpers
# ---------------------------------------------------------------------------

def create_test_plan(project, *, name: str, created_by=None, description: str = "") -> TestPlan:
    return TestPlan.objects.create(
        project=project,
        name=name,
        description=description,
        status=TestPlanStatus.DRAFT,
        created_by=created_by,
    )


def archive_test_plan(plan: TestPlan) -> TestPlan:
    plan.status = TestPlanStatus.ARCHIVED
    plan.save(update_fields=["status", "updated_at"])
    return plan


# ---------------------------------------------------------------------------
# Run helpers
# ---------------------------------------------------------------------------

def create_test_run(
    project,
    *,
    name: str,
    created_by=None,
    plan: TestPlan | None = None,
    trigger_type: str = TestRunTriggerType.MANUAL,
) -> TestRun:
    return TestRun.objects.create(
        project=project,
        plan=plan,
        name=name,
        status=TestRunStatus.PENDING,
        trigger_type=trigger_type,
        created_by=created_by,
    )


def start_test_run(run: TestRun) -> TestRun:
    if run.status == TestRunStatus.PENDING:
        run.status = TestRunStatus.RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])
    return run


def _resolve_final_run_status(run: TestRun) -> str:
    """Derive the run's terminal status from its run-case outcomes."""
    statuses = set(run.run_cases.values_list("status", flat=True))
    if not statuses:
        return TestRunStatus.CANCELLED
    if TestRunCaseStatus.FAILED in statuses or TestRunCaseStatus.ERROR in statuses:
        return TestRunStatus.FAILED
    pending = {TestRunCaseStatus.PENDING, TestRunCaseStatus.RUNNING}
    if statuses & pending:
        return TestRunStatus.RUNNING
    return TestRunStatus.PASSED


def close_test_run(run: TestRun) -> TestRun:
    """Mark the run as finished based on its run-case outcomes."""
    final_status = _resolve_final_run_status(run)
    if final_status in {TestRunStatus.PASSED, TestRunStatus.FAILED, TestRunStatus.CANCELLED}:
        run.status = final_status
        run.ended_at = timezone.now()
        run.save(update_fields=["status", "ended_at"])
    return run


# ---------------------------------------------------------------------------
# Run-case creation helpers
# ---------------------------------------------------------------------------

def _latest_revision_for_case(test_case: TestCase):
    return (
        test_case.revisions.order_by("-version_number", "-created_at").first()
    )


def _build_run_case(run: TestRun, test_case: TestCase, *, order_index: int = 0) -> TestRunCase:
    revision = _latest_revision_for_case(test_case)
    return TestRunCase(
        run=run,
        test_case=test_case,
        test_case_revision=revision,
        status=TestRunCaseStatus.PENDING,
        order_index=order_index,
    )


@transaction.atomic
def expand_run_from_cases(
    run: TestRun,
    test_cases,
    *,
    base_order_index: int = 0,
) -> list[TestRunCase]:
    """Create TestRunCase records for an explicit list of TestCase instances."""
    cases = list(test_cases)
    if not cases:
        return []

    run_cases = [
        _build_run_case(run, case, order_index=base_order_index + i)
        for i, case in enumerate(cases)
    ]
    TestRunCase.objects.bulk_create(run_cases)
    return run_cases


@transaction.atomic
def expand_run_from_section(run: TestRun, section, *, base_order_index: int = 0) -> list[TestRunCase]:
    """Expand approved cases under a section into run-cases.

    Only cases with design_status=approved are included. Draft and archived
    cases are excluded — a draft is not ready to execute, and an archived
    case should not appear in new runs.
    """
    from apps.testing.models.choices import TestCaseDesignStatus
    cases = list(
        TestCase.objects.filter(
            scenario__section=section,
            design_status=TestCaseDesignStatus.APPROVED,
        ).select_related("scenario").order_by("scenario__order_index", "order_index", "title")
    )
    return expand_run_from_cases(run, cases, base_order_index=base_order_index)


@transaction.atomic
def expand_run_from_suite(run: TestRun, suite, *, base_order_index: int = 0) -> list[TestRunCase]:
    """Expand approved cases under every section in a suite into run-cases.

    Only cases with design_status=approved are included. Draft and archived
    cases are excluded — a draft is not ready to execute, and an archived
    case should not appear in new runs.
    """
    from apps.testing.models.choices import TestCaseDesignStatus
    cases = list(
        TestCase.objects.filter(
            scenario__section__suite=suite,
            design_status=TestCaseDesignStatus.APPROVED,
        ).select_related(
            "scenario",
            "scenario__section",
        ).order_by(
            "scenario__section__order_index",
            "scenario__order_index",
            "order_index",
            "title",
        )
    )
    return expand_run_from_cases(run, cases, base_order_index=base_order_index)


# ---------------------------------------------------------------------------
# Compatibility shim — one-off execution entrypoint
# ---------------------------------------------------------------------------

def get_or_create_adhoc_run_case(test_case: TestCase, *, triggered_by=None) -> TestRunCase:
    """
    Return an existing pending ad-hoc run-case for this test_case, or create
    a new lightweight TestRun + TestRunCase so that every TestExecution always
    has a revision-safe reference.

    Callers that want a proper named run should use create_test_run +
    expand_run_from_cases instead.
    """
    existing = (
        TestRunCase.objects.filter(
            test_case=test_case,
            status=TestRunCaseStatus.PENDING,
            run__trigger_type=TestRunTriggerType.MANUAL,
            run__status=TestRunStatus.PENDING,
        )
        .select_related("run")
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        return existing

    with transaction.atomic():
        run = create_test_run(
            test_case.scenario.section.suite.project,
            name=f"Ad-hoc - {test_case.title[:200]}",
            created_by=triggered_by,
            trigger_type=TestRunTriggerType.MANUAL,
        )
        run_case = _build_run_case(run, test_case)
        run_case.save()

    return run_case


# ---------------------------------------------------------------------------
# Lease helpers — called by execution workers to track dispatch state
# ---------------------------------------------------------------------------

def acquire_run_case_lease(run_case: TestRunCase, worker_id: str) -> TestRunCase:
    """
    Mark the run-case as leased by a worker.  Increments attempt_count and
    records who picked it up.  Intentionally lightweight — not a distributed
    lock; callers should handle idempotency at the task level.
    """
    from django.db.models import F

    TestRunCase.objects.filter(pk=run_case.pk).update(
        attempt_count=F("attempt_count") + 1,
        leased_at=timezone.now(),
        leased_by=worker_id[:200],
    )
    run_case.refresh_from_db(fields=["attempt_count", "leased_at", "leased_by", "status"])
    if run_case.status == TestRunCaseStatus.PENDING:
        run_case.status = TestRunCaseStatus.RUNNING
        run_case.save(update_fields=["status", "updated_at"])
    start_test_run(run_case.run)
    return run_case


def release_run_case_lease(run_case: TestRunCase) -> TestRunCase:
    """Clear the lease once the worker has finished (pass, fail, or error)."""
    run_case.leased_at = None
    run_case.leased_by = ""
    run_case.save(update_fields=["leased_at", "leased_by", "updated_at"])
    return run_case


# ---------------------------------------------------------------------------
# Status sync helper (called after execution result is written)
# ---------------------------------------------------------------------------

def sync_run_case_status_from_execution(run_case: TestRunCase, execution_status: str) -> TestRunCase:
    """
    Map a TestExecution terminal status back onto the TestRunCase status.
    Only updates if the run-case is still in a non-terminal state.
    """
    terminal_states = {
        TestRunCaseStatus.PASSED,
        TestRunCaseStatus.FAILED,
        TestRunCaseStatus.SKIPPED,
        TestRunCaseStatus.ERROR,
        TestRunCaseStatus.CANCELLED,
    }
    if run_case.status in terminal_states:
        return run_case

    status_map = {
        "passed": TestRunCaseStatus.PASSED,
        "failed": TestRunCaseStatus.FAILED,
        "error": TestRunCaseStatus.ERROR,
        "cancelled": TestRunCaseStatus.CANCELLED,
    }
    mapped = status_map.get(execution_status)
    if mapped is not None:
        run_case.status = mapped
        run_case.save(update_fields=["status", "updated_at"])
        close_test_run(run_case.run)

    return run_case
