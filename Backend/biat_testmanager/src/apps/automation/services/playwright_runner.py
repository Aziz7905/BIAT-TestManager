from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from django.conf import settings
from django.utils import timezone

from apps.automation.models import AutomationFramework, AutomationLanguage, ExecutionStep
from apps.automation.models.choices import ExecutionStepStatus
from apps.automation.services.artifacts import (
    ensure_execution_artifact_directory,
    write_execution_text_artifact,
)
from apps.testing.models.utils import normalize_step_lines


class UnsupportedExecutionConfigurationError(RuntimeError):
    pass


def run_playwright_execution(execution) -> dict:
    script = execution.script
    if script is None:
        raise UnsupportedExecutionConfigurationError(
            "No automation script is linked to this execution."
        )

    if script.framework != AutomationFramework.PLAYWRIGHT:
        raise UnsupportedExecutionConfigurationError(
            "Only Playwright scripts are executable in v1."
        )

    if script.language != AutomationLanguage.PYTHON:
        raise UnsupportedExecutionConfigurationError(
            "Only Python Playwright scripts are executable in v1."
        )

    execution_steps = _ensure_execution_steps(execution)
    started_at = timezone.now()
    python_bin = getattr(settings, "AUTOMATION_PLAYWRIGHT_PYTHON_BIN", sys.executable)
    working_directory = getattr(settings, "AUTOMATION_PLAYWRIGHT_WORKDIR", str(settings.BASE_DIR))

    stdout = ""
    stderr = ""
    timed_out = False

    with tempfile.NamedTemporaryFile(
        suffix=".py",
        mode="w",
        encoding="utf-8",
        delete=False,
    ) as temp_script:
        temp_script.write(script.script_content)
        temp_path = temp_script.name

    try:
        _mark_step_started(execution_steps[0] if execution_steps else None)
        completed_process = subprocess.run(
            [python_bin, temp_path],
            capture_output=True,
            text=True,
            cwd=working_directory,
            timeout=max(int(execution.test_case.timeout_ms / 1000), 1),
            env=_build_execution_environment(execution),
            check=False,
        )
        stdout = completed_process.stdout or ""
        stderr = completed_process.stderr or ""
        return_code = completed_process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return_code = 1
        timed_out = True
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

    _write_execution_logs(execution, stdout, stderr)

    if return_code == 0:
        _mark_all_steps_passed(execution_steps, started_at)
        return {
            "status": "passed",
            "stdout": stdout,
            "stderr": stderr,
            "error_message": "",
            "stack_trace": "",
        }

    error_message = "Playwright execution timed out." if timed_out else "Playwright execution failed."
    stack_trace = stderr or stdout or error_message
    _mark_execution_failure(execution_steps, started_at, error_message, stack_trace)
    return {
        "status": "failed",
        "stdout": stdout,
        "stderr": stderr,
        "error_message": error_message,
        "stack_trace": stack_trace,
    }


def _ensure_execution_steps(execution):
    if execution.steps.exists():
        return list(execution.steps.order_by("step_index"))

    step_lines = normalize_step_lines(execution.test_case.steps)
    if not step_lines:
        step_lines = ["Run automation script"]

    execution_steps = []
    for index, step_line in enumerate(step_lines):
        execution_steps.append(
            ExecutionStep.objects.create(
                execution=execution,
                step_index=index,
                action=step_line[:255],
                target_element=step_line[:500],
                status=ExecutionStepStatus.PENDING,
            )
        )
    return execution_steps


def _build_execution_environment(execution) -> dict[str, str]:
    env = os.environ.copy()
    artifact_directory = ensure_execution_artifact_directory(execution)
    env["BIAT_EXECUTION_ID"] = str(execution.id)
    env["BIAT_TEST_CASE_ID"] = str(execution.test_case_id)
    env["BIAT_ARTIFACT_DIR"] = str(artifact_directory)
    return env


def _write_execution_logs(execution, stdout: str, stderr: str):
    write_execution_text_artifact(execution, "stdout.log", stdout)
    write_execution_text_artifact(execution, "stderr.log", stderr)


def _mark_step_started(step):
    if step is None:
        return
    step.status = ExecutionStepStatus.RUNNING
    step.executed_at = timezone.now()
    step.save(update_fields=["status", "executed_at"])


def _mark_all_steps_passed(execution_steps, started_at):
    finished_at = timezone.now()
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    per_step_duration = int(duration_ms / max(len(execution_steps), 1))

    for step in execution_steps:
        step.status = ExecutionStepStatus.PASSED
        step.executed_at = finished_at
        step.duration_ms = per_step_duration
        step.save(update_fields=["status", "executed_at", "duration_ms"])


def _mark_execution_failure(execution_steps, started_at, error_message: str, stack_trace: str):
    failed_at = timezone.now()
    for index, step in enumerate(execution_steps):
        if index == 0:
            step.status = ExecutionStepStatus.FAILED
            step.error_message = error_message
            step.stack_trace = stack_trace
            step.executed_at = failed_at
            step.duration_ms = int((failed_at - started_at).total_seconds() * 1000)
            step.save(
                update_fields=[
                    "status",
                    "error_message",
                    "stack_trace",
                    "executed_at",
                    "duration_ms",
                ]
            )
            continue

        step.status = ExecutionStepStatus.PENDING
        step.save(update_fields=["status"])
