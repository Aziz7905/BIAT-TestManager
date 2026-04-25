from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from queue import Empty, Queue

from django.conf import settings
from django.utils import timezone

from apps.automation.models import ExecutionStep, TestArtifact
from apps.automation.models.choices import (
    ArtifactType,
    AutomationLanguage,
    ExecutionStatus,
    ExecutionStepStatus,
)
from apps.automation.runtime import BIAT_EVENT_PREFIX
from apps.automation.services.artifacts import (
    ensure_execution_artifact_directory,
    get_execution_artifact_directory,
    get_execution_artifact_url,
    write_execution_text_artifact,
)
from apps.automation.services.checkpoints import create_pending_execution_checkpoint
from apps.automation.services.control import is_execution_stop_signaled
from apps.automation.services.grid import cache_browser_session_urls, resize_browser_window
from apps.automation.services.streaming import (
    publish_execution_artifact_created,
    publish_execution_step_updated,
    publish_execution_status_changed,
)
from apps.testing.models.utils import normalize_step_lines


class UnsupportedExecutionConfigurationError(RuntimeError):
    pass


def run_python_automation_execution(
    execution,
    *,
    framework: str,
    framework_label: str,
    python_bin_setting: str,
    workdir_setting: str,
) -> dict:
    script = execution.script
    if script is None:
        raise UnsupportedExecutionConfigurationError(
            "No automation script is linked to this execution."
        )

    if script.framework != framework:
        raise UnsupportedExecutionConfigurationError(
            f"Only {framework_label} scripts are executable in v1."
        )

    if script.language != AutomationLanguage.PYTHON:
        raise UnsupportedExecutionConfigurationError(
            f"Only Python {framework_label} scripts are executable in v1."
        )

    started_at = timezone.now()
    python_bin = getattr(settings, python_bin_setting, sys.executable)
    working_directory = getattr(settings, workdir_setting, str(settings.BASE_DIR))

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
        stdout, stderr, return_code, timed_out, runtime_events_seen = _run_process_with_live_events(
            execution=execution,
            python_bin=python_bin,
            temp_path=temp_path,
            working_directory=working_directory,
        )
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass

    write_execution_logs(execution, stdout, stderr)
    log_artifacts = build_log_artifact_payloads(execution)
    execution.refresh_from_db(fields=["status"])

    if execution.status == ExecutionStatus.CANCELLED:
        finalize_runtime_steps(execution, success=False)
        return {
            "status": "cancelled",
            "stdout": stdout,
            "stderr": stderr,
            "error_message": "Execution cancelled.",
            "stack_trace": "",
            "artifacts": log_artifacts,
        }

    if return_code == 0:
        if runtime_events_seen:
            finalize_runtime_steps(execution, success=True)
            failed_step = (
                execution.steps.filter(status=ExecutionStepStatus.FAILED)
                .order_by("step_index")
                .first()
            )
            if failed_step is not None:
                return {
                    "status": "failed",
                    "stdout": stdout,
                    "stderr": stderr,
                    "error_message": failed_step.error_message or f"Step {failed_step.step_index} failed.",
                    "stack_trace": failed_step.stack_trace or "",
                    "artifacts": log_artifacts,
                }
        else:
            execution_steps = ensure_execution_steps(execution)
            mark_all_steps_passed(execution_steps, started_at)
        return {
            "status": "passed",
            "stdout": stdout,
            "stderr": stderr,
            "error_message": "",
            "stack_trace": "",
            "artifacts": log_artifacts,
        }

    error_message = (
        f"{framework_label} execution timed out."
        if timed_out
        else f"{framework_label} execution failed."
    )
    stack_trace = stderr or stdout or error_message
    if runtime_events_seen:
        finalize_runtime_steps(
            execution,
            success=False,
            error_message=error_message,
            stack_trace=stack_trace,
        )
    else:
        execution_steps = ensure_execution_steps(execution)
        mark_execution_failure(execution_steps, started_at, error_message, stack_trace)
    return {
        "status": "failed",
        "stdout": stdout,
        "stderr": stderr,
        "error_message": error_message,
        "stack_trace": stack_trace,
        "artifacts": log_artifacts,
    }


def ensure_execution_steps(execution):
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


def build_execution_environment(execution) -> dict[str, str]:
    env = os.environ.copy()
    artifact_directory = ensure_execution_artifact_directory(execution)
    env["BIAT_EXECUTION_ID"] = str(execution.id)
    env["BIAT_TEST_CASE_ID"] = str(execution.test_case_id)
    env["BIAT_ARTIFACT_DIR"] = str(artifact_directory)
    env["BIAT_AUTOMATION_FRAMEWORK"] = execution.script.framework if execution.script_id else ""
    env["BIAT_AUTOMATION_BROWSER"] = execution.browser
    env["BIAT_AUTOMATION_PLATFORM"] = execution.platform
    env["PYTHONUNBUFFERED"] = "1"
    python_path_segments = [str(settings.BASE_DIR)]
    existing_python_path = env.get("PYTHONPATH")
    if existing_python_path:
        python_path_segments.append(existing_python_path)
    env["PYTHONPATH"] = os.pathsep.join(python_path_segments)

    if execution.environment_id:
        env["BIAT_EXECUTION_ENVIRONMENT_ID"] = str(execution.environment_id)
        env["BIAT_EXECUTION_ENGINE"] = execution.environment.engine

    grid_url = getattr(settings, "SELENIUM_GRID_HUB_URL", "")
    if grid_url:
        env["BIAT_SELENIUM_GRID_URL"] = grid_url
        # Grid executions are streamed through VNC, so default to a visible browser.
        # Execution environments can still override this with capabilities_json.headless.
        env.setdefault("BIAT_HEADLESS", "0")
        env.setdefault("BIAT_VIEWPORT_WIDTH", "1920")
        env.setdefault("BIAT_VIEWPORT_HEIGHT", "1080")
        env.setdefault("BIAT_BROWSER_WINDOW_SIZE", "1920,1080")

    env["BIAT_REDIS_URL"] = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")

    if execution.environment_id and execution.environment.capabilities_json:
        caps = execution.environment.capabilities_json
        if "headless" in caps:
            env["BIAT_HEADLESS"] = "1" if caps["headless"] else "0"
        if "viewport_width" in caps:
            env["BIAT_VIEWPORT_WIDTH"] = str(caps["viewport_width"])
        if "viewport_height" in caps:
            env["BIAT_VIEWPORT_HEIGHT"] = str(caps["viewport_height"])
        env["BIAT_EXEC_CAPABILITIES"] = json.dumps(caps)

    return env


def write_execution_logs(execution, stdout: str, stderr: str):
    write_execution_text_artifact(execution, "stdout.log", stdout)
    write_execution_text_artifact(execution, "stderr.log", stderr)


def build_log_artifact_payloads(execution) -> list[dict]:
    artifact_directory = ensure_execution_artifact_directory(execution)
    return [
        {
            "type": ArtifactType.LOG,
            "path": str((artifact_directory / "stdout.log").resolve()),
            "metadata": {"label": "stdout"},
        },
        {
            "type": ArtifactType.LOG,
            "path": str((artifact_directory / "stderr.log").resolve()),
            "metadata": {"label": "stderr"},
        },
    ]


def mark_all_steps_passed(execution_steps, started_at):
    finished_at = timezone.now()
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    per_step_duration = int(duration_ms / max(len(execution_steps), 1))

    for step in execution_steps:
        step.status = ExecutionStepStatus.PASSED
        step.executed_at = finished_at
        step.duration_ms = per_step_duration
        step.save(update_fields=["status", "executed_at", "duration_ms"])


def mark_execution_failure(execution_steps, started_at, error_message: str, stack_trace: str):
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


def finalize_runtime_steps(
    execution,
    *,
    success: bool,
    error_message: str = "",
    stack_trace: str = "",
):
    now = timezone.now()
    running_steps = execution.steps.filter(status=ExecutionStepStatus.RUNNING)
    for step in running_steps:
        step.status = ExecutionStepStatus.PASSED if success else ExecutionStepStatus.FAILED
        step.executed_at = now
        if not success:
            step.error_message = step.error_message or error_message
            step.stack_trace = step.stack_trace or stack_trace
        step.save(
            update_fields=[
                "status",
                "executed_at",
                "error_message",
                "stack_trace",
            ]
        )
        publish_execution_step_updated(step)


def _run_process_with_live_events(
    *,
    execution,
    python_bin: str,
    temp_path: str,
    working_directory: str,
) -> tuple[str, str, int, bool, bool]:
    timeout_seconds = max(int(execution.test_case.timeout_ms / 1000), 1)
    started_monotonic = time.monotonic()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    timed_out = False
    runtime_events_seen = False
    last_seq = 0
    process = subprocess.Popen(
        [python_bin, temp_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=working_directory,
        env=build_execution_environment(execution),
        bufsize=1,
    )
    line_queue: Queue[tuple[str, str | None]] = Queue()
    closed_streams: set[str] = set()
    stop_requested = False

    stdout_thread = threading.Thread(
        target=_stream_lines_to_queue,
        args=("stdout", process.stdout, line_queue),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_stream_lines_to_queue,
        args=("stderr", process.stderr, line_queue),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    try:
        while True:
            last_seq, runtime_events_seen = _drain_live_output(
                execution=execution,
                line_queue=line_queue,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                closed_streams=closed_streams,
                last_seq=last_seq,
                runtime_events_seen=runtime_events_seen,
            )

            if is_execution_stop_signaled(execution) and process.poll() is None:
                stop_requested = True
                process.terminate()

            if (time.monotonic() - started_monotonic) > timeout_seconds and process.poll() is None:
                timed_out = True
                process.terminate()

            if (
                process.poll() is not None
                and closed_streams == {"stdout", "stderr"}
                and line_queue.empty()
            ):
                break
            time.sleep(0.05)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)

    execution.refresh_from_db(fields=["status"])
    if stop_requested or execution.status == ExecutionStatus.CANCELLED:
        return (
            "".join(stdout_lines),
            "".join(stderr_lines),
            130,
            False,
            runtime_events_seen,
        )
    return (
        "".join(stdout_lines),
        "".join(stderr_lines),
        process.returncode or 0,
        timed_out,
        runtime_events_seen,
    )


def _stream_lines_to_queue(stream_name: str, stream, line_queue: Queue) -> None:
    try:
        if stream is None:
            return
        for line in iter(stream.readline, ""):
            line_queue.put((stream_name, line))
    finally:
        if stream is not None:
            stream.close()
        line_queue.put((stream_name, None))


def _drain_live_output(
    *,
    execution,
    line_queue: Queue,
    stdout_lines: list[str],
    stderr_lines: list[str],
    closed_streams: set[str],
    last_seq: int,
    runtime_events_seen: bool,
) -> tuple[int, bool]:
    while True:
        try:
            stream_name, line = line_queue.get_nowait()
        except Empty:
            break

        if line is None:
            closed_streams.add(stream_name)
            continue

        if stream_name == "stdout":
            event = _parse_runner_event(line)
            if event is not None:
                event_seq = int(event.get("seq", 0))
                if event_seq > last_seq:
                    last_seq = event_seq
                    runtime_events_seen = True
                    _handle_runner_event(execution, event)
                continue
            stdout_lines.append(line)
            continue

        stderr_lines.append(line)

    return last_seq, runtime_events_seen


def _parse_runner_event(line: str) -> dict | None:
    if not line.startswith(BIAT_EVENT_PREFIX):
        return None

    payload = line[len(BIAT_EVENT_PREFIX):].strip()
    if not payload:
        return None

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _handle_runner_event(execution, event: dict) -> None:
    handlers = {
        "session_started": _handle_session_started,
        "step_started": _handle_step_started,
        "step_passed": _handle_step_passed,
        "step_failed": _handle_step_failed,
        "artifact_created": _handle_artifact_created,
        "checkpoint_requested": _handle_checkpoint_requested,
    }
    handler = handlers.get(event.get("type"))
    if handler:
        handler(execution, event)


def _handle_session_started(execution, event: dict) -> None:
    session_id = event.get("session_id", "")
    if not session_id:
        return
    viewport_width = _coerce_positive_int(event.get("viewport_width"), 1920)
    viewport_height = _coerce_positive_int(event.get("viewport_height"), 1080)
    resize_browser_window(
        session_id,
        width=viewport_width,
        height=viewport_height,
    )
    execution.selenium_session_id = session_id
    execution.save(update_fields=["selenium_session_id"])

    cache_browser_session_urls(str(execution.id), session_id)
    publish_execution_status_changed(execution)


def _handle_step_started(execution, event: dict) -> None:
    step = _upsert_execution_step(
        execution,
        step_index=event["step_index"],
        defaults={
            "action": event.get("action") or f"Step {event['step_index']}",
            "target_element": event.get("target_element") or "",
            "selector_used": event.get("selector_used") or None,
            "input_value": event.get("input_value") or None,
            "status": ExecutionStepStatus.RUNNING,
            "executed_at": timezone.now(),
            "error_message": None,
            "stack_trace": None,
        },
    )
    publish_execution_step_updated(step)


def _handle_step_passed(execution, event: dict) -> None:
    screenshot_url = _coerce_artifact_url(execution, event.get("screenshot_path"))
    step = _upsert_execution_step(
        execution,
        step_index=event["step_index"],
        defaults={
            "status": ExecutionStepStatus.PASSED,
            "duration_ms": event.get("duration_ms"),
            "executed_at": timezone.now(),
            "screenshot_url": screenshot_url,
        },
    )
    publish_execution_step_updated(step)


def _handle_step_failed(execution, event: dict) -> None:
    screenshot_url = _coerce_artifact_url(execution, event.get("screenshot_path"))
    step = _upsert_execution_step(
        execution,
        step_index=event["step_index"],
        defaults={
            "status": ExecutionStepStatus.FAILED,
            "duration_ms": event.get("duration_ms"),
            "executed_at": timezone.now(),
            "error_message": event.get("error_message") or "Execution step failed.",
            "stack_trace": event.get("stack_trace") or "",
            "screenshot_url": screenshot_url,
        },
    )
    publish_execution_step_updated(step)


def _handle_artifact_created(execution, event: dict) -> None:
    artifact = TestArtifact.objects.create(
        execution=execution,
        artifact_type=event.get("artifact_type", ArtifactType.LOG),
        storage_path=event.get("path", ""),
        metadata_json=event.get("metadata") or {},
    )
    publish_execution_artifact_created(artifact)


def _handle_checkpoint_requested(execution, event: dict) -> None:
    step = None
    step_index = event.get("step_index")
    if step_index is not None:
        step = execution.steps.filter(step_index=step_index).first()
    create_pending_execution_checkpoint(
        execution,
        checkpoint_key=event.get("checkpoint_key") or f"checkpoint-{event.get('seq', 0)}",
        title=event.get("title") or "Human action required",
        instructions=event.get("instructions") or "",
        payload_json=event.get("payload") or {},
        step=step,
    )


def _upsert_execution_step(execution, *, step_index: int, defaults: dict):
    step, _ = ExecutionStep.objects.get_or_create(
        execution=execution,
        step_index=step_index,
        defaults={
            "action": defaults.get("action") or f"Step {step_index}",
            "target_element": defaults.get("target_element") or "",
            "status": defaults.get("status", ExecutionStepStatus.PENDING),
        },
    )
    update_fields: list[str] = []
    for field_name in [
        "action",
        "target_element",
        "selector_used",
        "input_value",
        "status",
        "error_message",
        "stack_trace",
        "duration_ms",
        "executed_at",
        "screenshot_url",
    ]:
        if field_name not in defaults:
            continue
        value = defaults[field_name]
        if value is None and field_name in {"action", "target_element"}:
            continue
        if getattr(step, field_name) != value:
            setattr(step, field_name, value)
            update_fields.append(field_name)

    if update_fields:
        step.save(update_fields=update_fields)
    return step


def _coerce_artifact_url(execution, screenshot_path: str | None) -> str | None:
    if not screenshot_path:
        return None

    artifact_directory = get_execution_artifact_directory(execution).resolve()
    candidate = os.path.abspath(screenshot_path)
    try:
        relative_path = os.path.relpath(candidate, artifact_directory)
    except ValueError:
        return screenshot_path

    file_name = relative_path.replace("\\", "/")
    return get_execution_artifact_url(execution, file_name)


def _coerce_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
