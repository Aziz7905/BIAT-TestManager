from __future__ import annotations

import logging

from django.utils import timezone

from apps.automation.models import TestResult
from apps.automation.models.choices import TestResultStatus
from apps.automation.services.checkpoints import cancel_pending_execution_checkpoints
from apps.automation.services.streaming import (
    publish_execution_result_ready,
    publish_execution_status_changed,
)


logger = logging.getLogger(__name__)


EXECUTION_STATUS_TO_RESULT_STATUS = {
    "passed": TestResultStatus.PASSED,
    "failed": TestResultStatus.FAILED,
    "cancelled": TestResultStatus.SKIPPED,
    "error": TestResultStatus.ERROR,
}


def finalize_execution_result(
    execution,
    *,
    status: str,
    duration_ms: int,
    total_steps: int,
    passed_steps: int,
    failed_steps: int,
    error_message: str = "",
    stack_trace: str = "",
    junit_xml: str = "",
    video_url: str | None = None,
    issues_count: int = 0,
):
    ended_at = execution.ended_at or timezone.now()
    execution.status = status
    execution.ended_at = ended_at
    updated = execution.__class__.objects.filter(pk=execution.pk).update(
        status=status,
        ended_at=ended_at,
    )
    if not updated:
        logger.warning(
            "Skipping result finalization for missing execution %s. "
            "Original status=%s error=%s",
            execution.pk,
            status,
            error_message,
        )
        return None

    cancel_pending_execution_checkpoints(execution)
    publish_execution_status_changed(execution)

    result_status = EXECUTION_STATUS_TO_RESULT_STATUS.get(
        status,
        TestResultStatus.ERROR,
    )

    result, _ = TestResult.objects.update_or_create(
        execution=execution,
        defaults={
            "status": result_status,
            "duration_ms": duration_ms,
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "error_message": error_message or None,
            "stack_trace": stack_trace or None,
            "junit_xml": junit_xml or None,
            "video_url": video_url,
            "issues_count": issues_count,
        },
    )

    if execution.run_case_id:
        from apps.testing.services.runs import sync_run_case_status_from_execution
        sync_run_case_status_from_execution(execution.run_case, status)

    publish_execution_result_ready(result)
    return result
