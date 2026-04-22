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


def _absolute_artifact_path(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str((_artifact_dir() / candidate).resolve())


def _get_redis_client():
    import redis as redis_lib
    url = os.environ.get("BIAT_REDIS_URL", "redis://localhost:6379/0")
    return redis_lib.from_url(url, decode_responses=True)


def _stop_key() -> str:
    execution_id = os.environ.get("BIAT_EXECUTION_ID", "")
    return f"biat:exec:{execution_id}:stop"


def _checkpoint_resume_key(checkpoint_key: str) -> str:
    execution_id = os.environ.get("BIAT_EXECUTION_ID", "")
    return f"biat:exec:{execution_id}:ckpt:{checkpoint_key}"


def report_session_started(*, session_id: str) -> None:
    _emit_event("session_started", session_id=session_id)


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

    stop_key = _stop_key()
    resume_key = _checkpoint_resume_key(checkpoint_key)
    client = _get_redis_client()

    while True:
        try:
            if client.get(stop_key):
                raise SystemExit(130)

            raw_payload = client.getdel(resume_key)
        except SystemExit:
            raise
        except Exception as exc:
            raise RuntimeError(
                "Execution control channel is unavailable while waiting for checkpoint resume."
            ) from exc
        if raw_payload is not None:
            return json.loads(raw_payload) if raw_payload else {}

        time.sleep(poll_interval_seconds)
