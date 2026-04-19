from __future__ import annotations

import traceback

from django.db.models import Max
from django.utils import timezone

from apps.automation.models import (
    AutomationScript,
    ExecutionEnvironment,
    TestArtifact,
    TestExecution,
)
from apps.automation.models.choices import (
    ExecutionStatus,
    ExecutionTriggerType,
)
from apps.automation.services.engine import EngineResult, get_engine_for_execution
from apps.automation.services.playwright_runner import UnsupportedExecutionConfigurationError
from apps.automation.services.results import finalize_execution_result
from apps.automation.services.streaming import publish_execution_status_changed
from apps.automation.services.control import write_execution_stop_signal


class ExecutionQueueError(RuntimeError):
    pass


def select_execution_script(test_case, script=None, *, run_case=None):
    if script is not None:
        return script

    # Prefer a script pinned to the exact revision the run-case targets.
    if run_case is not None and run_case.test_case_revision_id:
        revision_script = (
            AutomationScript.objects.filter(
                test_case=test_case,
                test_case_revision=run_case.test_case_revision,
                is_active=True,
            )
            .order_by("-script_version", "-created_at")
            .first()
        )
        if revision_script is not None:
            return revision_script

    # Fall back to the latest active script for the test case.
    return (
        AutomationScript.objects.filter(
            test_case=test_case,
            is_active=True,
        )
        .order_by("-script_version", "-created_at")
        .first()
    )


def _next_attempt_number(run_case) -> int:
    if run_case is None:
        return 1
    existing = run_case.executions.aggregate(max_attempt=Max("attempt_number"))["max_attempt"]
    return (existing or 0) + 1


def resolve_execution_environment(*, test_case, browser: str, platform: str, script=None, environment=None):
    if environment is not None:
        return environment

    if script is None:
        return None

    return (
        ExecutionEnvironment.objects.filter(
            team_id=test_case.scenario.section.suite.project.team_id,
            is_active=True,
            engine=script.framework,
            browser=browser,
            platform=platform,
        )
        .order_by("-max_parallelism", "name")
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
    run_case=None,
    environment=None,
):
    from apps.testing.services.runs import get_or_create_adhoc_run_case

    resolved_run_case = run_case
    if resolved_run_case is None:
        resolved_run_case = get_or_create_adhoc_run_case(
            test_case, triggered_by=triggered_by
        )

    selected_script = select_execution_script(test_case, script, run_case=resolved_run_case)
    selected_environment = resolve_execution_environment(
        test_case=test_case,
        browser=browser,
        platform=platform,
        script=selected_script,
        environment=environment,
    )
    attempt_number = _next_attempt_number(resolved_run_case)
    execution = TestExecution.objects.create(
        test_case=test_case,
        run_case=resolved_run_case,
        environment=selected_environment,
        script=selected_script,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        status=ExecutionStatus.QUEUED,
        browser=browser,
        platform=platform,
        attempt_number=attempt_number,
    )
    publish_execution_status_changed(execution)
    return execution


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
    environment=None,
):
    execution = create_execution_record(
        test_case=test_case,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        browser=browser,
        platform=platform,
        script=script,
        environment=environment,
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


def _persist_engine_artifacts(execution, engine_result: EngineResult) -> None:
    from apps.automation.services.streaming import publish_execution_artifact_created

    artifacts = [
        TestArtifact.objects.create(
            execution=execution,
            artifact_type=artifact["type"],
            storage_path=artifact["path"],
            metadata_json=artifact.get("metadata") or {},
        )
        for artifact in engine_result.artifacts
        if artifact.get("path")
    ]
    for artifact in artifacts:
        publish_execution_artifact_created(artifact)


def run_execution(execution_id: str):
    from apps.testing.services.runs import acquire_run_case_lease, release_run_case_lease

    execution = TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "script",
        "environment",
        "run_case",
    ).get(pk=execution_id)

    if execution.status == ExecutionStatus.CANCELLED:
        return execution

    if execution.run_case_id:
        acquire_run_case_lease(execution.run_case, worker_id=f"exec-{str(execution_id)[:8]}")

    execution.status = ExecutionStatus.RUNNING
    execution.started_at = execution.started_at or timezone.now()
    execution.save(update_fields=["status", "started_at"])
    publish_execution_status_changed(execution)

    try:
        engine = get_engine_for_execution(execution)
        engine_result = engine.run(execution)
        duration_ms = execution.get_duration_ms() or 0
        steps = list(execution.steps.all())
        passed_steps = sum(step.status == "passed" for step in steps)
        failed_steps = sum(step.status == "failed" for step in steps)
        finalize_execution_result(
            execution,
            status=engine_result.status,
            duration_ms=duration_ms,
            total_steps=len(steps),
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            error_message=engine_result.error_message,
            stack_trace=engine_result.stack_trace,
        )
        _persist_engine_artifacts(execution, engine_result)
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
    finally:
        if execution.run_case_id:
            release_run_case_lease(execution.run_case)


def request_execution_pause(execution):
    execution = execution.pause()
    publish_execution_status_changed(execution)
    return execution


def request_execution_resume(execution):
    execution.resume()
    publish_execution_status_changed(execution)
    return queue_execution(execution)


def request_execution_stop(execution):
    execution = execution.stop()
    write_execution_stop_signal(execution)
    publish_execution_status_changed(execution)
    return execution


def activate_script(script) -> "AutomationScript":
    script.is_active = True
    script.save(update_fields=["is_active"])
    return script


def deactivate_script(script) -> "AutomationScript":
    script.is_active = False
    script.save(update_fields=["is_active"])
    return script
