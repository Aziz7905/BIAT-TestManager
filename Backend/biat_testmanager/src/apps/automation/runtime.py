from __future__ import annotations

import itertools
import json
import os
import time
import uuid
from pathlib import Path


BIAT_EVENT_PREFIX = "__BIAT_EVENT__"
_SEQ = itertools.count(1)


def _emit_event(event_type: str, **payload) -> None:
    event = {
        "seq": next(_SEQ),
        "type": event_type,
    }
    event.update(payload)
    print(f"{BIAT_EVENT_PREFIX}{json.dumps(event)}", flush=True)


def _artifact_dir() -> Path:
    value = os.environ.get("BIAT_ARTIFACT_DIR")
    if not value:
        raise RuntimeError("BIAT_ARTIFACT_DIR is not configured for this execution.")
    return Path(value)


def _control_dir() -> Path:
    return _artifact_dir() / "control"


def _absolute_artifact_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((_artifact_dir() / candidate).resolve())


def report_step_started(
    *,
    step_index: int,
    action: str,
    target_element: str | None = None,
    selector_used: str | None = None,
    input_value: str | None = None,
) -> None:
    _emit_event(
        "step_started",
        step_index=step_index,
        action=action,
        target_element=target_element,
        selector_used=selector_used,
        input_value=input_value,
    )


def report_step_passed(
    *,
    step_index: int,
    duration_ms: int | None = None,
    screenshot_path: str | None = None,
) -> None:
    _emit_event(
        "step_passed",
        step_index=step_index,
        duration_ms=duration_ms,
        screenshot_path=_absolute_artifact_path(screenshot_path) if screenshot_path else None,
    )


def report_step_failed(
    *,
    step_index: int,
    error_message: str,
    stack_trace: str | None = None,
    duration_ms: int | None = None,
    screenshot_path: str | None = None,
) -> None:
    _emit_event(
        "step_failed",
        step_index=step_index,
        error_message=error_message,
        stack_trace=stack_trace,
        duration_ms=duration_ms,
        screenshot_path=_absolute_artifact_path(screenshot_path) if screenshot_path else None,
    )


def artifact_created(
    *,
    artifact_type: str,
    path: str,
    metadata: dict | None = None,
) -> None:
    _emit_event(
        "artifact_created",
        artifact_type=artifact_type,
        path=_absolute_artifact_path(path),
        metadata=metadata or {},
    )


def require_human_action(
    *,
    title: str,
    instructions: str,
    step_index: int | None = None,
    payload: dict | None = None,
    checkpoint_key: str | None = None,
    poll_interval_seconds: float = 0.25,
) -> dict:
    checkpoint_key = checkpoint_key or uuid.uuid4().hex
    _emit_event(
        "checkpoint_requested",
        checkpoint_key=checkpoint_key,
        step_index=step_index,
        title=title,
        instructions=instructions,
        payload=payload or {},
    )

    control_directory = _control_dir()
    resume_path = control_directory / f"checkpoint-{checkpoint_key}.resume.json"
    stop_path = control_directory / "execution.stop"

    while True:
        if stop_path.exists():
            raise SystemExit(130)

        if resume_path.exists():
            try:
                raw_payload = resume_path.read_text(encoding="utf-8").strip()
                return json.loads(raw_payload) if raw_payload else {}
            finally:
                try:
                    resume_path.unlink()
                except FileNotFoundError:
                    pass

        time.sleep(poll_interval_seconds)
