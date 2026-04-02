from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.automation.models.choices import ExecutionTriggerType
from apps.automation.services.execution_runner import create_and_queue_execution


def compute_next_run_for_schedule(
    *,
    cron_expression: str,
    timezone_name: str,
    from_datetime: datetime | None = None,
):
    try:
        from croniter import croniter
    except ModuleNotFoundError:
        return _compute_basic_next_run(
            cron_expression=cron_expression,
            timezone_name=timezone_name,
            from_datetime=from_datetime,
        )

    try:
        zone = ZoneInfo(timezone_name)
        base_datetime = from_datetime or timezone.now()
        localized_datetime = base_datetime.astimezone(zone)
        iterator = croniter(cron_expression, localized_datetime)
        next_run = iterator.get_next(datetime)
    except Exception:
        return None

    if timezone.is_naive(next_run):
        return timezone.make_aware(next_run, zone)
    return next_run.astimezone(zone)


def _compute_basic_next_run(
    *,
    cron_expression: str,
    timezone_name: str,
    from_datetime: datetime | None = None,
):
    parts = cron_expression.split()
    if len(parts) != 5:
        return None

    minute_part, hour_part, day_part, month_part, weekday_part = parts
    if any(part != "*" for part in [day_part, month_part, weekday_part]):
        return None

    try:
        minute = int(minute_part)
        hour = int(hour_part)
        zone = ZoneInfo(timezone_name)
    except Exception:
        return None

    base_datetime = (from_datetime or timezone.now()).astimezone(zone)
    next_run = base_datetime.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )
    if next_run <= base_datetime:
        next_run = next_run + timedelta(days=1)

    return next_run


def trigger_execution_schedule(schedule):
    test_cases = _get_schedule_test_cases(schedule)
    executions = []
    for test_case in test_cases:
        executions.append(
            create_and_queue_execution(
                test_case=test_case,
                triggered_by=schedule.created_by,
                trigger_type=ExecutionTriggerType.SCHEDULED,
                browser=schedule.browser,
                platform=schedule.platform,
            )
        )
    return executions


def _get_schedule_test_cases(schedule):
    from apps.testing.models import TestCase

    if schedule.suite_id:
        return list(
            TestCase.objects.select_related(
                "scenario",
                "scenario__suite",
            ).filter(
                scenario__suite=schedule.suite,
            ).order_by(
                "scenario__order_index",
                "scenario__title",
                "order_index",
                "title",
            )
        )

    return list(
        TestCase.objects.select_related(
            "scenario",
            "scenario__suite",
        ).filter(
            scenario__suite__project=schedule.project,
        ).order_by(
            "scenario__suite__folder_path",
            "scenario__suite__name",
            "scenario__order_index",
            "scenario__title",
            "order_index",
            "title",
        )
    )
