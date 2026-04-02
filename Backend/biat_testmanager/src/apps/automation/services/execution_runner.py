from __future__ import annotations

import traceback

from django.utils import timezone

from apps.automation.models import AutomationScript, TestExecution
from apps.automation.models.choices import (
    ExecutionStatus,
    ExecutionTriggerType,
)
from apps.automation.services.playwright_runner import (
    UnsupportedExecutionConfigurationError,
    run_playwright_execution,
)
from apps.automation.services.results import finalize_execution_result


class ExecutionQueueError(RuntimeError):
    pass


def select_execution_script(test_case, script=None):
    if script is not None:
        return script

    return (
        AutomationScript.objects.filter(
            test_case=test_case,
            is_active=True,
        )
        .order_by("-script_version", "-created_at")
        .first()
    )


def create_execution_record(
    *,
    test_case,
    triggered_by,
    trigger_type: str = ExecutionTriggerType.MANUAL,
    browser: str,
    platform: str,
    script=None,
):
    selected_script = select_execution_script(test_case, script)
    return TestExecution.objects.create(
        test_case=test_case,
        script=selected_script,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        status=ExecutionStatus.QUEUED,
        browser=browser,
        platform=platform,
    )


def queue_execution(execution):
    from apps.automation.tasks import enqueue_execution_task

    task_identifier = enqueue_execution_task(str(execution.id))
    if task_identifier:
        execution.celery_task_id = task_identifier
        execution.save(update_fields=["celery_task_id"])
    return execution


def create_and_queue_execution(
    *,
    test_case,
    triggered_by,
    trigger_type: str = ExecutionTriggerType.MANUAL,
    browser: str,
    platform: str,
    script=None,
):
    execution = create_execution_record(
        test_case=test_case,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        browser=browser,
        platform=platform,
        script=script,
    )

    try:
        queue_execution(execution)
    except Exception as exc:
        finalize_execution_result(
            execution,
            status=ExecutionStatus.ERROR,
            duration_ms=0,
            total_steps=0,
            passed_steps=0,
            failed_steps=0,
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
        )
    return execution


def run_execution(execution_id: str):
    execution = TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__suite",
        "script",
    ).get(pk=execution_id)

    if execution.status == ExecutionStatus.CANCELLED:
        return execution

    execution.status = ExecutionStatus.RUNNING
    execution.started_at = execution.started_at or timezone.now()
    execution.save(update_fields=["status", "started_at"])

    try:
        runner_result = run_playwright_execution(execution)
        duration_ms = execution.get_duration_ms() or 0
        steps = list(execution.steps.all())
        passed_steps = sum(step.status == "passed" for step in steps)
        failed_steps = sum(step.status == "failed" for step in steps)
        finalize_execution_result(
            execution,
            status=runner_result["status"],
            duration_ms=duration_ms,
            total_steps=len(steps),
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            error_message=runner_result["error_message"],
            stack_trace=runner_result["stack_trace"],
        )
        return execution
    except UnsupportedExecutionConfigurationError as exc:
        finalize_execution_result(
            execution,
            status=ExecutionStatus.ERROR,
            duration_ms=execution.get_duration_ms() or 0,
            total_steps=execution.steps.count(),
            passed_steps=0,
            failed_steps=execution.steps.count(),
            error_message=str(exc),
            stack_trace="",
        )
        return execution
    except Exception as exc:  # pragma: no cover - defensive guard
        finalize_execution_result(
            execution,
            status=ExecutionStatus.ERROR,
            duration_ms=execution.get_duration_ms() or 0,
            total_steps=execution.steps.count(),
            passed_steps=0,
            failed_steps=execution.steps.count(),
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
        )
        return execution


def request_execution_pause(execution):
    return execution.pause()


def request_execution_resume(execution):
    execution.resume()
    return queue_execution(execution)


def request_execution_stop(execution):
    return execution.stop()
