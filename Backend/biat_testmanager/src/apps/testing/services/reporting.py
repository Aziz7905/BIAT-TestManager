from __future__ import annotations

from datetime import datetime, time as datetime_time, timedelta

from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.automation.models import TestResult
from apps.automation.models.choices import TestResultStatus
from apps.testing.models import TestRun, TestRunCase
from apps.testing.models.choices import TestRunCaseStatus, TestRunStatus
from apps.testing.models.utils import calculate_pass_rate


TERMINAL_RUN_STATUSES = (
    TestRunStatus.PASSED,
    TestRunStatus.FAILED,
    TestRunStatus.CANCELLED,
)

FAILED_RUN_CASE_STATUSES = (
    TestRunCaseStatus.FAILED,
    TestRunCaseStatus.ERROR,
    TestRunCaseStatus.CANCELLED,
)


def build_project_quality_dashboard(
    project,
    *,
    recent_run_limit: int = 5,
) -> dict:
    """
    Build the dashboard overview for a single project's testing activity.

    This is the main dashboard read model used to power summary cards and the
    "recent runs" panel without forcing the frontend to stitch together several
    low-level list endpoints.
    """
    limited_recent_run_limit = max(1, min(recent_run_limit, 20))
    runs = TestRun.objects.filter(project=project)
    run_cases = TestRunCase.objects.filter(run__project=project)

    run_summary = runs.aggregate(
        total_runs=Count("id"),
        active_runs=Count(
            "id",
            filter=Q(status__in=[TestRunStatus.PENDING, TestRunStatus.RUNNING]),
        ),
        completed_runs=Count(
            "id",
            filter=Q(status__in=TERMINAL_RUN_STATUSES),
        ),
    )
    run_case_summary = run_cases.aggregate(
        total_run_cases=Count("id"),
        passed_run_cases=Count(
            "id",
            filter=Q(status=TestRunCaseStatus.PASSED),
        ),
        failed_run_cases=Count(
            "id",
            filter=Q(status__in=FAILED_RUN_CASE_STATUSES),
        ),
        skipped_run_cases=Count(
            "id",
            filter=Q(status=TestRunCaseStatus.SKIPPED),
        ),
        pending_run_cases=Count(
            "id",
            filter=Q(status=TestRunCaseStatus.PENDING),
        ),
        running_run_cases=Count(
            "id",
            filter=Q(status=TestRunCaseStatus.RUNNING),
        ),
    )

    recent_runs = list_project_recent_run_cards(project, limit=limited_recent_run_limit)

    total_run_cases = run_case_summary["total_run_cases"] or 0
    passed_run_cases = run_case_summary["passed_run_cases"] or 0
    failed_run_cases = run_case_summary["failed_run_cases"] or 0
    skipped_run_cases = run_case_summary["skipped_run_cases"] or 0
    pending_run_cases = run_case_summary["pending_run_cases"] or 0
    running_run_cases = run_case_summary["running_run_cases"] or 0

    return {
        "project": {
            "id": project.id,
            "name": project.name,
        },
        "summary": {
            "total_runs": run_summary["total_runs"] or 0,
            "active_runs": run_summary["active_runs"] or 0,
            "completed_runs": run_summary["completed_runs"] or 0,
            "total_run_cases": total_run_cases,
            "passed_run_cases": passed_run_cases,
            "failed_run_cases": failed_run_cases,
            "pass_rate": calculate_pass_rate(
                total_count=total_run_cases,
                passed_count=passed_run_cases,
            ),
        },
        "status_breakdown": {
            "pending": pending_run_cases,
            "running": running_run_cases,
            "passed": passed_run_cases,
            "failed": failed_run_cases,
            "skipped": skipped_run_cases,
        },
        "recent_runs": recent_runs,
    }


def list_project_recent_run_cards(project, *, limit: int = 5) -> list[dict]:
    """
    Return compact run cards for the dashboard's recent-runs panel.
    """
    limited = max(1, min(limit, 20))
    runs = (
        TestRun.objects.select_related("plan", "created_by")
        .filter(project=project)
        .annotate(
            run_case_count=Count("run_cases", distinct=True),
            passed_case_count=Count(
                "run_cases",
                filter=Q(run_cases__status=TestRunCaseStatus.PASSED),
                distinct=True,
            ),
            failed_case_count=Count(
                "run_cases",
                filter=Q(run_cases__status__in=FAILED_RUN_CASE_STATUSES),
                distinct=True,
            ),
        )
        .order_by("-created_at")[:limited]
    )

    cards: list[dict] = []
    for run in runs:
        total_cases = run.run_case_count or 0
        passed_cases = run.passed_case_count or 0
        cards.append(
            {
                "id": run.id,
                "name": run.name,
                "status": run.status,
                "trigger_type": run.trigger_type,
                "plan_name": run.plan.name if run.plan_id else None,
                "created_by_name": _display_user_name(run.created_by),
                "created_at": run.created_at,
                "started_at": run.started_at,
                "ended_at": run.ended_at,
                "run_case_count": total_cases,
                "passed_case_count": passed_cases,
                "failed_case_count": run.failed_case_count or 0,
                "pass_rate": calculate_pass_rate(
                    total_count=total_cases,
                    passed_count=passed_cases,
                ),
            }
        )
    return cards


def build_project_pass_rate_trend(
    project,
    *,
    days: int = 14,
) -> dict:
    """
    Build a day-by-day execution-result pass-rate trend for one project.
    """
    limited_days = max(1, min(days, 90))
    today = timezone.localdate()
    first_day = today - timedelta(days=limited_days - 1)
    since = timezone.make_aware(
        datetime.combine(first_day, datetime_time.min),
        timezone.get_current_timezone(),
    )
    result_rows = (
        TestResult.objects.filter(
            execution__run_case__run__project=project,
            created_at__gte=since,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(
            total_results=Count("id"),
            passed_results=Count(
                "id",
                filter=Q(status=TestResultStatus.PASSED),
            ),
            failed_results=Count(
                "id",
                filter=Q(status__in=[TestResultStatus.FAILED, TestResultStatus.ERROR]),
            ),
        )
        .order_by("day")
    )

    rows_by_day = {row["day"]: row for row in result_rows}
    points: list[dict] = []
    for offset in range(limited_days):
        day = today - timedelta(days=(limited_days - 1 - offset))
        row = rows_by_day.get(day, {})
        total_results = row.get("total_results", 0) or 0
        passed_results = row.get("passed_results", 0) or 0
        points.append(
            {
                "date": day,
                "total_results": total_results,
                "passed_results": passed_results,
                "failed_results": row.get("failed_results", 0) or 0,
                "pass_rate": calculate_pass_rate(
                    total_count=total_results,
                    passed_count=passed_results,
                ),
            }
        )

    return {
        "project": {
            "id": project.id,
            "name": project.name,
        },
        "days": limited_days,
        "points": points,
    }


def list_project_failure_hotspots(
    project,
    *,
    days: int = 30,
    limit: int = 10,
) -> dict:
    """
    Return the most failure-prone test cases for a project over a recent window.
    """
    limited_days = max(1, min(days, 180))
    limited = max(1, min(limit, 50))
    first_day = timezone.localdate() - timedelta(days=limited_days - 1)
    since = timezone.make_aware(
        datetime.combine(first_day, datetime_time.min),
        timezone.get_current_timezone(),
    )
    hotspots = (
        TestResult.objects.filter(
            execution__run_case__run__project=project,
            created_at__gte=since,
            status__in=[TestResultStatus.FAILED, TestResultStatus.ERROR],
        )
        .values(
            "execution__test_case_id",
            "execution__test_case__title",
            "execution__test_case__scenario__title",
            "execution__test_case__scenario__section__suite__name",
        )
        .annotate(
            failure_count=Count(
                "id",
                filter=Q(status=TestResultStatus.FAILED),
            ),
            error_count=Count(
                "id",
                filter=Q(status=TestResultStatus.ERROR),
            ),
            last_failure_at=Max("created_at"),
        )
        .order_by(
            "-failure_count",
            "-error_count",
            "-last_failure_at",
            "execution__test_case__title",
        )[:limited]
    )

    items = [
        {
            "test_case_id": row["execution__test_case_id"],
            "test_case_title": row["execution__test_case__title"],
            "scenario_title": row["execution__test_case__scenario__title"],
            "suite_name": row["execution__test_case__scenario__section__suite__name"],
            "failure_count": row["failure_count"] or 0,
            "error_count": row["error_count"] or 0,
            "last_failure_at": row["last_failure_at"],
        }
        for row in hotspots
    ]

    return {
        "project": {
            "id": project.id,
            "name": project.name,
        },
        "days": limited_days,
        "items": items,
    }


def _display_user_name(user) -> str | None:
    if user is None:
        return None
    full_name = user.get_full_name().strip()
    return full_name or user.username
