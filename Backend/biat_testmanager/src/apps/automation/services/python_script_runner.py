from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue

from django.conf import settings
from django.utils import timezone

from apps.automation.models import ExecutionStep, TestArtifact
from apps.automation.models.choices import (
    ArtifactType,
    AutomationFramework,
    AutomationLanguage,
    ExecutionStatus,
    ExecutionStepStatus,
)
from apps.automation.runtime import BIAT_EVENT_PREFIX
from apps.automation.services.browser_sessions import (
    cache_browser_session_urls,
    get_webdriver_url,
    resize_browser_window,
)
from apps.automation.services.checkpoints import create_pending_execution_checkpoint
from apps.automation.services.control import is_execution_stop_signaled
from apps.automation.services.streaming import (
    publish_execution_artifact_created,
    publish_execution_step_updated,
    publish_execution_status_changed,
)
from apps.automation.services.storage import (
    build_artifact_download_url,
    store_file_artifact,
    store_text_artifact,
)
from apps.testing.models.utils import normalize_step_lines


class UnsupportedExecutionConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunnerWorkspace:
    host_root: Path
    container_root: str
    script_path: str
    command: list[str]
    image: str


def run_containerized_automation_execution(
    execution,
    *,
    framework: str,
    framework_label: str,
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

    if script.language not in {AutomationLanguage.PYTHON, AutomationLanguage.JAVA}:
        raise UnsupportedExecutionConfigurationError(
            f"Only Python and Java {framework_label} scripts are executable."
        )
    if script.language == AutomationLanguage.JAVA and framework != AutomationFramework.SELENIUM:
        raise UnsupportedExecutionConfigurationError(
            "Only Selenium Java scripts are executable."
        )

    started_at = timezone.now()

    stdout = ""
    stderr = ""
    timed_out = False

    workspace = prepare_runner_workspace(execution)
    try:
        stdout, stderr, return_code, timed_out, runtime_events_seen = _run_container_with_live_events(
            execution=execution,
            workspace=workspace,
        )
    finally:
        shutil.rmtree(workspace.host_root, ignore_errors=True)

    log_artifacts = build_log_artifact_payloads(execution, stdout, stderr)
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


def prepare_runner_workspace(execution) -> RunnerWorkspace:
    workspace_parent = Path(settings.BASE_DIR).parent / ".runner_workspaces"
    workspace_parent.mkdir(parents=True, exist_ok=True)
    host_root = workspace_parent / f"biat-run-{execution.id}-{uuid.uuid4().hex}"
    host_root.mkdir(parents=True, exist_ok=False)
    container_root = "/workspace"
    (host_root / "artifacts").mkdir(parents=True, exist_ok=True)

    if execution.script.language == AutomationLanguage.PYTHON:
        _write_python_workspace(host_root, execution.script.script_content)
        return RunnerWorkspace(
            host_root=host_root,
            container_root=container_root,
            script_path=f"{container_root}/script.py",
            command=["python", f"{container_root}/script.py"],
            image=getattr(settings, "AUTOMATION_PYTHON_RUNNER_IMAGE"),
        )

    class_name = _extract_java_class_name(execution.script.script_content)
    _write_java_workspace(host_root, execution.script.script_content, class_name)
    return RunnerWorkspace(
        host_root=host_root,
        container_root=container_root,
        script_path=f"{container_root}/{class_name}.java",
        command=[
            "mvn",
            "-q",
            "compile",
            "exec:java",
            f"-Dexec.mainClass={class_name}",
        ],
        image=getattr(settings, "AUTOMATION_JAVA_RUNNER_IMAGE"),
    )


def _write_python_workspace(host_root: Path, script_content: str) -> None:
    (host_root / "script.py").write_text(script_content, encoding="utf-8")
    helper_dir = host_root / "apps" / "automation"
    helper_dir.mkdir(parents=True, exist_ok=True)
    (host_root / "apps" / "__init__.py").write_text("", encoding="utf-8")
    (helper_dir / "__init__.py").write_text("", encoding="utf-8")
    source_runtime = Path(settings.BASE_DIR) / "apps" / "automation" / "runtime.py"
    shutil.copyfile(source_runtime, helper_dir / "runtime.py")


def _write_java_workspace(host_root: Path, script_content: str, class_name: str) -> None:
    (host_root / f"{class_name}.java").write_text(script_content, encoding="utf-8")
    (host_root / "pom.xml").write_text(_java_runner_pom(), encoding="utf-8")
    (host_root / "BiatRuntime.java").write_text(_java_runtime_helper(), encoding="utf-8")


def _extract_java_class_name(script_content: str) -> str:
    match = re.search(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)", script_content)
    if not match:
        raise UnsupportedExecutionConfigurationError(
            "Selenium Java scripts must define one public class."
        )
    return match.group(1)


def _java_runner_pom() -> str:
    return """<project xmlns="http://maven.apache.org/POM/4.0.0"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>tn.biat</groupId>
  <artifactId>biat-runner-workspace</artifactId>
  <version>1.0.0</version>
  <dependencies>
    <dependency>
      <groupId>org.seleniumhq.selenium</groupId>
      <artifactId>selenium-java</artifactId>
      <version>4.25.0</version>
    </dependency>
  </dependencies>
  <build>
    <sourceDirectory>.</sourceDirectory>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.13.0</version>
        <configuration>
          <source>21</source>
          <target>21</target>
        </configuration>
      </plugin>
      <plugin>
        <groupId>org.codehaus.mojo</groupId>
        <artifactId>exec-maven-plugin</artifactId>
        <version>3.5.0</version>
      </plugin>
    </plugins>
  </build>
</project>
"""


def _java_runtime_helper() -> str:
    return r"""import java.util.concurrent.atomic.AtomicInteger;

public final class BiatRuntime {
    private static final AtomicInteger SEQ = new AtomicInteger(1);

    private BiatRuntime() {}

    public static String webdriverUrl() {
        return System.getenv("BIAT_WEBDRIVER_URL");
    }

    public static void event(String type, String jsonFields) {
        String suffix = (jsonFields == null || jsonFields.isBlank()) ? "" : "," + jsonFields;
        System.out.println("__BIAT_EVENT__{\"seq\":" + SEQ.getAndIncrement()
            + ",\"type\":\"" + type + "\"" + suffix + "}");
        System.out.flush();
    }

    public static void sessionStarted(String sessionId) {
        event("session_started", "\"session_id\":\"" + escape(sessionId) + "\"");
    }

    public static void stepStarted(int index, String action) {
        event("step_started", "\"step_index\":" + index + ",\"action\":\"" + escape(action) + "\"");
    }

    public static void stepPassed(int index) {
        event("step_passed", "\"step_index\":" + index);
    }

    public static void stepFailed(int index, String message) {
        event("step_failed", "\"step_index\":" + index + ",\"error_message\":\"" + escape(message) + "\"");
    }

    private static String escape(String value) {
        return value == null ? "" : value.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
"""


def build_execution_environment(
    execution,
    *,
    artifact_dir: str = "/workspace/artifacts",
) -> dict[str, str]:
    env = os.environ.copy()
    env["BIAT_EXECUTION_ID"] = str(execution.id)
    env["BIAT_TEST_CASE_ID"] = str(execution.test_case_id)
    env["BIAT_ARTIFACT_DIR"] = artifact_dir
    env["BIAT_AUTOMATION_FRAMEWORK"] = execution.script.framework if execution.script_id else ""
    env["BIAT_AUTOMATION_BROWSER"] = execution.browser
    env["BIAT_AUTOMATION_PLATFORM"] = execution.platform
    env["PYTHONUNBUFFERED"] = "1"
    python_path_segments = ["/workspace"]
    existing_python_path = env.get("PYTHONPATH")
    if existing_python_path:
        python_path_segments.append(existing_python_path)
    env["PYTHONPATH"] = os.pathsep.join(python_path_segments)

    if execution.environment_id:
        env["BIAT_EXECUTION_ENVIRONMENT_ID"] = str(execution.environment_id)
        env["BIAT_EXECUTION_ENGINE"] = execution.environment.engine

    webdriver_url = get_webdriver_url(for_runner=True)
    if webdriver_url:
        env["BIAT_WEBDRIVER_URL"] = webdriver_url
        # Browser-backend executions can be streamed through VNC, so default visible.
        # Execution environments can still override this with capabilities_json.headless.
        env.setdefault("BIAT_HEADLESS", "0")
        env.setdefault("BIAT_VIEWPORT_WIDTH", "1920")
        env.setdefault("BIAT_VIEWPORT_HEIGHT", "1080")
        env.setdefault("BIAT_BROWSER_WINDOW_SIZE", "1920,1080")

    env["BIAT_REDIS_URL"] = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    env["MINIO_ENDPOINT_URL"] = getattr(settings, "MINIO_RUNNER_ENDPOINT_URL", "")
    env["MINIO_ACCESS_KEY"] = getattr(settings, "MINIO_ACCESS_KEY", "")
    env["MINIO_SECRET_KEY"] = getattr(settings, "MINIO_SECRET_KEY", "")
    env["MINIO_BUCKET_NAME"] = getattr(settings, "MINIO_BUCKET_NAME", "")
    env["MINIO_REGION_NAME"] = getattr(settings, "MINIO_REGION_NAME", "us-east-1")

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


def build_log_artifact_payloads(execution, stdout: str, stderr: str) -> list[dict]:
    return [
        store_text_artifact(
            execution,
            name="stdout.log",
            content=stdout,
            artifact_type=ArtifactType.LOG,
            metadata={"label": "stdout"},
        ),
        store_text_artifact(
            execution,
            name="stderr.log",
            content=stderr,
            artifact_type=ArtifactType.LOG,
            metadata={"label": "stderr"},
        ),
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


def _run_container_with_live_events(
    *,
    execution,
    workspace: RunnerWorkspace,
) -> tuple[str, str, int, bool, bool]:
    import docker

    timeout_seconds = max(int(execution.test_case.timeout_ms / 1000), 1)
    started_monotonic = time.monotonic()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    timed_out = False
    runtime_events_seen = False
    last_seq = 0
    client = docker.from_env()
    container = client.containers.run(
        workspace.image,
        command=workspace.command,
        detach=True,
        environment=build_execution_environment(
            execution,
            artifact_dir=f"{workspace.container_root}/artifacts",
        ),
        volumes={
            str(workspace.host_root): {
                "bind": workspace.container_root,
                "mode": "rw",
            }
        },
        working_dir=workspace.container_root,
        network=getattr(settings, "AUTOMATION_RUNNER_DOCKER_NETWORK", ""),
        stdout=True,
        stderr=True,
    )
    line_queue: Queue[tuple[str, str | None]] = Queue()
    stop_requested = False

    log_thread = threading.Thread(
        target=_stream_container_logs_to_queue,
        args=(container, line_queue),
        daemon=True,
    )
    log_thread.start()

    try:
        while True:
            last_seq, runtime_events_seen = _drain_live_output(
                execution=execution,
                workspace=workspace,
                line_queue=line_queue,
                stdout_lines=stdout_lines,
                stderr_lines=stderr_lines,
                last_seq=last_seq,
                runtime_events_seen=runtime_events_seen,
            )

            container.reload()
            is_running = container.status == "running"
            if is_execution_stop_signaled(execution) and is_running:
                stop_requested = True
                container.stop(timeout=5)

            if (time.monotonic() - started_monotonic) > timeout_seconds and is_running:
                timed_out = True
                container.stop(timeout=5)

            if not is_running and not log_thread.is_alive() and line_queue.empty():
                break
            time.sleep(0.05)
    finally:
        try:
            container.reload()
            if container.status == "running":
                container.kill()
        except Exception:
            pass

    result = container.wait(timeout=10)
    try:
        container.remove(force=True)
    except Exception:
        pass

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
        int(result.get("StatusCode") or 0),
        timed_out,
        runtime_events_seen,
    )


def _stream_container_logs_to_queue(container, line_queue: Queue) -> None:
    try:
        for raw_line in container.logs(stream=True, follow=True):
            line = raw_line.decode("utf-8", errors="replace")
            line_queue.put(("stdout", line))
    finally:
        line_queue.put(("stdout", None))


def _drain_live_output(
    *,
    execution,
    workspace: RunnerWorkspace,
    line_queue: Queue,
    stdout_lines: list[str],
    stderr_lines: list[str],
    last_seq: int,
    runtime_events_seen: bool,
) -> tuple[int, bool]:
    while True:
        try:
            stream_name, line = line_queue.get_nowait()
        except Empty:
            break

        if line is None:
            continue

        if stream_name == "stdout":
            event = _parse_runner_event(line)
            if event is not None:
                event_seq = int(event.get("seq", 0))
                if event_seq > last_seq:
                    last_seq = event_seq
                    runtime_events_seen = True
                    _handle_runner_event(execution, event, workspace=workspace)
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


def _handle_runner_event(
    execution,
    event: dict,
    *,
    workspace: RunnerWorkspace,
) -> None:
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
        if event.get("type") in {"artifact_created", "step_passed", "step_failed"}:
            handler(execution, event, workspace=workspace)
        else:
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


def _handle_step_passed(
    execution,
    event: dict,
    *,
    workspace: RunnerWorkspace,
) -> None:
    screenshot_url = _store_step_screenshot_url(
        execution,
        workspace=workspace,
        step_index=event["step_index"],
        screenshot_path=event.get("screenshot_path"),
    )
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


def _handle_step_failed(
    execution,
    event: dict,
    *,
    workspace: RunnerWorkspace,
) -> None:
    screenshot_url = _store_step_screenshot_url(
        execution,
        workspace=workspace,
        step_index=event["step_index"],
        screenshot_path=event.get("screenshot_path"),
    )
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


def _handle_artifact_created(
    execution,
    event: dict,
    *,
    workspace: RunnerWorkspace,
) -> None:
    artifact_type = event.get("artifact_type", ArtifactType.LOG)
    storage_backend = event.get("storage_backend")
    storage_key = event.get("storage_key")
    metadata = event.get("metadata") or {}

    if not storage_key and event.get("path"):
        host_path = _container_artifact_path_to_host_path(
            workspace,
            event["path"],
        )
        if host_path and host_path.exists():
            stored = store_file_artifact(
                execution,
                local_path=host_path,
                artifact_type=artifact_type,
                metadata=metadata,
            )
            storage_backend = stored["storage_backend"]
            storage_key = stored["storage_key"]

    if not storage_key:
        return

    artifact = TestArtifact.objects.create(
        execution=execution,
        artifact_type=artifact_type,
        storage_backend=storage_backend or "minio",
        storage_key=storage_key,
        metadata_json=metadata,
    )
    publish_execution_artifact_created(artifact)


def _container_artifact_path_to_host_path(
    workspace: RunnerWorkspace,
    container_path: str,
) -> Path | None:
    container_root = workspace.container_root.rstrip("/")
    if not container_path.startswith(container_root + "/"):
        return None
    relative_path = container_path[len(container_root) + 1:]
    candidate = (workspace.host_root / relative_path).resolve()
    try:
        candidate.relative_to(workspace.host_root.resolve())
    except ValueError:
        return None
    return candidate


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


def _store_step_screenshot_url(
    execution,
    *,
    workspace: RunnerWorkspace,
    step_index: int,
    screenshot_path: str | None,
) -> str | None:
    if not screenshot_path:
        return None
    if screenshot_path.startswith(("http://", "https://")):
        return screenshot_path

    host_path = _container_artifact_path_to_host_path(workspace, screenshot_path)
    if host_path is None or not host_path.exists():
        return None

    stored = store_file_artifact(
        execution,
        local_path=host_path,
        artifact_type=ArtifactType.SCREENSHOT,
        metadata={"step_index": step_index},
    )
    artifact = TestArtifact.objects.create(
        execution=execution,
        artifact_type=ArtifactType.SCREENSHOT,
        storage_backend=stored["storage_backend"],
        storage_key=stored["storage_key"],
        metadata_json=stored["metadata"],
    )
    publish_execution_artifact_created(artifact)
    return build_artifact_download_url(artifact)


def _coerce_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
