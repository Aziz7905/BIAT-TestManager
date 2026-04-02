from __future__ import annotations

from django.utils import timezone

from apps.automation.models import TestResult
from apps.automation.models.choices import TestResultStatus


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
    execution.status = status
    execution.ended_at = execution.ended_at or timezone.now()
    execution.save(update_fields=["status", "ended_at"])

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
    return result
