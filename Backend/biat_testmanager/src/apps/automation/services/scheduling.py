from __future__ import annotations

from datetime import datetime, timedelta
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from apps.automation.models.choices import ExecutionTriggerType
from apps.testing.models import TestRunTriggerType

logger = logging.getLogger(__name__)


def compute_next_run_for_schedule(
    *,
    cron_expression: str,
    timezone_name: str,
    from_datetime: datetime | None = None,
):
    try:
        from croniter import CroniterBadCronError, CroniterBadDateError, croniter
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
    except (
        CroniterBadCronError,
        CroniterBadDateError,
        ValueError,
        ZoneInfoNotFoundError,
    ) as exc:
        logger.warning(
            "Invalid execution schedule: cron=%s timezone=%s error=%s",
            cron_expression,
            timezone_name,
            exc,
        )
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
        logger.warning("Invalid basic cron expression: %s", cron_expression)
        return None

    minute_part, hour_part, day_part, month_part, weekday_part = parts
    if any(part != "*" for part in [day_part, month_part, weekday_part]):
        return None

    try:
        minute = int(minute_part)
        hour = int(hour_part)
        zone = ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        logger.warning(
            "Invalid basic execution schedule: cron=%s timezone=%s error=%s",
            cron_expression,
            timezone_name,
            exc,
        )
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
    """
    Create a TestRun + TestRunCase records for the schedule's scope, then
    return the run. Execution dispatch happens downstream (Celery task or
    manual trigger). The scheduler no longer bypasses the run layer.
    """
    from apps.testing.services.runs import (
        create_test_run,
        expand_run_from_suite,
    )
    from apps.testing.models import TestSuite

    run = create_test_run(
        schedule.project,
        name=f"Scheduled - {schedule.name}",
        created_by=schedule.created_by,
        trigger_type=TestRunTriggerType.SCHEDULED,
    )

    if schedule.suite_id:
        expand_run_from_suite(run, schedule.suite)
    else:
        for suite in TestSuite.objects.filter(project=schedule.project):
            expand_run_from_suite(run, suite)

    return run
