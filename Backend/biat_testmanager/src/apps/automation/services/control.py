from __future__ import annotations

import json

import redis as redis_lib
from django.conf import settings

_STOP_TTL = 3600
_CHECKPOINT_TTL = 3600


class ExecutionControlUnavailable(RuntimeError):
    pass


def _get_redis_client() -> redis_lib.Redis:
    url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    return redis_lib.from_url(url, decode_responses=True)


def _stop_key(execution_id: str) -> str:
    return f"biat:exec:{execution_id}:stop"


def _checkpoint_key(execution_id: str, checkpoint_key: str) -> str:
    return f"biat:exec:{execution_id}:ckpt:{checkpoint_key}"


def write_execution_stop_signal(execution) -> None:
    try:
        _get_redis_client().set(_stop_key(str(execution.id)), "1", ex=_STOP_TTL)
    except redis_lib.RedisError as exc:
        raise ExecutionControlUnavailable(
            "Execution control channel is unavailable."
        ) from exc


def is_execution_stop_signaled(execution) -> bool:
    try:
        return bool(_get_redis_client().get(_stop_key(str(execution.id))))
    except redis_lib.RedisError:
        return False


def write_checkpoint_resume_signal(
    execution,
    checkpoint_key: str,
    payload: dict | None = None,
) -> None:
    try:
        _get_redis_client().set(
            _checkpoint_key(str(execution.id), checkpoint_key),
            json.dumps(payload or {}),
            ex=_CHECKPOINT_TTL,
        )
    except redis_lib.RedisError as exc:
        raise ExecutionControlUnavailable(
            "Execution control channel is unavailable."
        ) from exc


def read_and_clear_checkpoint_resume_signal(
    execution_id: str,
    checkpoint_key: str,
) -> dict | None:
    try:
        value = _get_redis_client().getdel(
            _checkpoint_key(execution_id, checkpoint_key)
        )
    except redis_lib.RedisError as exc:
        raise ExecutionControlUnavailable(
            "Execution control channel is unavailable."
        ) from exc
    if value is None:
        return None
    return json.loads(value)
