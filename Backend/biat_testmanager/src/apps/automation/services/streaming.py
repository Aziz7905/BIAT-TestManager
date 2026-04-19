from __future__ import annotations

import logging
import time
from urllib.parse import urlencode
import json

from asgiref.sync import async_to_sync
from django.core import signing
from rest_framework.renderers import JSONRenderer


EXECUTION_STREAM_TICKET_SALT = "execution-stream-ticket"
EXECUTION_STREAM_TICKET_TTL_SECONDS = 120
EXECUTION_GROUP_PREFIX = "execution."
logger = logging.getLogger(__name__)


def get_execution_group_name(execution_id) -> str:
    return f"{EXECUTION_GROUP_PREFIX}{execution_id}"


def normalize_json_payload(data):
    return json.loads(JSONRenderer().render(data))


def issue_execution_stream_ticket(execution, user) -> dict:
    expires_at = int(time.time()) + EXECUTION_STREAM_TICKET_TTL_SECONDS
    payload = {
        "execution_id": str(execution.id),
        "user_id": user.id,
        "exp": expires_at,
    }
    ticket = signing.dumps(payload, salt=EXECUTION_STREAM_TICKET_SALT)
    query = urlencode({"ticket": ticket})
    return {
        "ticket": ticket,
        "expires_in": EXECUTION_STREAM_TICKET_TTL_SECONDS,
        "websocket_path": f"/ws/executions/{execution.id}/?{query}",
    }


def verify_execution_stream_ticket(ticket: str, *, expected_execution_id=None) -> dict:
    payload = signing.loads(ticket, salt=EXECUTION_STREAM_TICKET_SALT)
    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise signing.SignatureExpired("Execution stream ticket expired.")

    execution_id = payload.get("execution_id")
    if expected_execution_id is not None and str(execution_id) != str(expected_execution_id):
        raise signing.BadSignature("Execution stream ticket does not match the requested execution.")

    return payload


def serialize_execution_checkpoint(checkpoint) -> dict:
    return {
        "id": str(checkpoint.id),
        "execution": str(checkpoint.execution_id),
        "step": str(checkpoint.step_id) if checkpoint.step_id else None,
        "checkpoint_key": checkpoint.checkpoint_key,
        "title": checkpoint.title,
        "instructions": checkpoint.instructions,
        "payload_json": checkpoint.payload_json,
        "status": checkpoint.status,
        "requested_at": checkpoint.requested_at.isoformat().replace("+00:00", "Z"),
        "resolved_at": (
            checkpoint.resolved_at.isoformat().replace("+00:00", "Z")
            if checkpoint.resolved_at
            else None
        ),
        "resolved_by": checkpoint.resolved_by_id,
    }


def serialize_test_artifact(artifact) -> dict:
    return {
        "id": str(artifact.id),
        "execution": str(artifact.execution_id),
        "artifact_type": artifact.artifact_type,
        "storage_path": artifact.storage_path,
        "metadata_json": artifact.metadata_json,
        "created_at": artifact.created_at.isoformat().replace("+00:00", "Z"),
    }


def build_execution_snapshot(execution) -> dict:
    from apps.automation.serializers import (
        ExecutionStepSerializer,
        TestExecutionSerializer,
        TestResultSerializer,
    )

    execution_data = TestExecutionSerializer(execution).data
    steps = ExecutionStepSerializer(execution.steps.order_by("step_index"), many=True).data
    result = TestResultSerializer(execution.result).data if hasattr(execution, "result") else None
    pending_checkpoints = [
        serialize_execution_checkpoint(checkpoint)
        for checkpoint in execution.checkpoints.filter(status="pending").order_by("requested_at")
    ]
    artifacts = [
        serialize_test_artifact(artifact)
        for artifact in execution.artifacts.order_by("artifact_type", "created_at")
    ]
    return normalize_json_payload(
        {
        "execution": execution_data,
        "steps": steps,
        "pending_checkpoints": pending_checkpoints,
        "result": result,
        "artifacts": artifacts,
        }
    )


def publish_execution_event(execution_id, event_type: str, payload: dict) -> None:
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            get_execution_group_name(execution_id),
            {
                "type": "execution_event",
                "event": {
                    "type": event_type,
                    "execution_id": str(execution_id),
                    "emitted_at": int(time.time()),
                    "payload": payload,
                },
            },
        )
    except Exception:
        logger.warning(
            "Unable to publish execution stream event.",
            extra={"execution_id": str(execution_id), "event_type": event_type},
            exc_info=True,
        )


def publish_execution_snapshot(execution) -> None:
    publish_execution_event(
        execution.id,
        "execution.snapshot",
        build_execution_snapshot(execution),
    )


def publish_execution_status_changed(execution) -> None:
    from apps.automation.serializers import TestExecutionSerializer

    publish_execution_event(
        execution.id,
        "execution.status_changed",
        normalize_json_payload(TestExecutionSerializer(execution).data),
    )


def publish_execution_step_updated(step) -> None:
    from apps.automation.serializers import ExecutionStepSerializer

    publish_execution_event(
        step.execution_id,
        "execution.step_updated",
        normalize_json_payload(ExecutionStepSerializer(step).data),
    )


def publish_execution_result_ready(result) -> None:
    from apps.automation.serializers import TestResultSerializer

    publish_execution_event(
        result.execution_id,
        "execution.result_ready",
        normalize_json_payload(TestResultSerializer(result).data),
    )


def publish_execution_artifact_created(artifact) -> None:
    publish_execution_event(
        artifact.execution_id,
        "execution.artifact_created",
        serialize_test_artifact(artifact),
    )
