from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.automation.models import ExecutionCheckpoint
from apps.automation.models.choices import ExecutionCheckpointStatus, ExecutionStatus
from apps.automation.services.control import (
    write_checkpoint_resume_signal,
    write_execution_stop_signal,
)
from apps.automation.services.streaming import (
    publish_execution_event,
    publish_execution_status_changed,
    serialize_execution_checkpoint,
)


def create_pending_execution_checkpoint(
    execution,
    *,
    checkpoint_key: str,
    title: str,
    instructions: str,
    payload_json: dict | None = None,
    step=None,
):
    checkpoint, created = ExecutionCheckpoint.objects.get_or_create(
        execution=execution,
        checkpoint_key=checkpoint_key,
        defaults={
            "step": step,
            "title": title,
            "instructions": instructions,
            "payload_json": payload_json or {},
            "status": ExecutionCheckpointStatus.PENDING,
        },
    )
    if not created:
        return checkpoint

    execution.pause_requested = True
    execution.status = ExecutionStatus.PAUSED
    execution.save(update_fields=["pause_requested", "status"])
    publish_execution_status_changed(execution)
    publish_execution_event(
        execution.id,
        "execution.checkpoint_requested",
        serialize_execution_checkpoint(checkpoint),
    )
    return checkpoint


@transaction.atomic
def resume_execution_checkpoint(checkpoint, *, resolved_by, payload_json: dict | None = None):
    checkpoint = ExecutionCheckpoint.objects.select_for_update().select_related(
        "execution"
    ).get(pk=checkpoint.pk)
    if checkpoint.status != ExecutionCheckpointStatus.PENDING:
        return checkpoint

    now = timezone.now()
    checkpoint.status = ExecutionCheckpointStatus.RESOLVED
    checkpoint.resolved_at = now
    checkpoint.resolved_by = resolved_by
    if payload_json:
        merged_payload = dict(checkpoint.payload_json)
        merged_payload.update(payload_json)
        checkpoint.payload_json = merged_payload
    checkpoint.save(
        update_fields=["status", "resolved_at", "resolved_by", "payload_json"]
    )

    execution = checkpoint.execution
    execution.pause_requested = False
    if execution.status == ExecutionStatus.PAUSED:
        execution.status = ExecutionStatus.RUNNING
    execution.save(update_fields=["pause_requested", "status"])

    signal_payload = {
        "resolved_by": getattr(resolved_by, "id", None),
        "resolved_at": now.isoformat().replace("+00:00", "Z"),
        "payload_json": payload_json or {},
    }
    write_checkpoint_resume_signal(execution, checkpoint.checkpoint_key, signal_payload)

    publish_execution_status_changed(execution)
    publish_execution_event(
        execution.id,
        "execution.checkpoint_resolved",
        serialize_execution_checkpoint(checkpoint),
    )
    publish_execution_event(
        execution.id,
        "execution.control_ack",
        {
            "action": "checkpoint_resume",
            "checkpoint_id": str(checkpoint.id),
            "status": execution.status,
        },
    )
    return checkpoint


def cancel_pending_execution_checkpoints(execution):
    pending_checkpoints = list(
        execution.checkpoints.filter(status=ExecutionCheckpointStatus.PENDING)
    )
    if not pending_checkpoints:
        return 0

    now = timezone.now()
    for checkpoint in pending_checkpoints:
        checkpoint.status = ExecutionCheckpointStatus.CANCELLED
        checkpoint.resolved_at = now
        checkpoint.save(update_fields=["status", "resolved_at"])
    return len(pending_checkpoints)


def expire_stale_execution_checkpoints(*, max_age: timedelta | None = None) -> int:
    from apps.automation.services.results import finalize_execution_result

    cutoff = timezone.now() - (max_age or timedelta(minutes=60))
    expired_count = 0
    stale_checkpoints = list(
        ExecutionCheckpoint.objects.select_related("execution").filter(
            status=ExecutionCheckpointStatus.PENDING,
            requested_at__lt=cutoff,
        )
    )
    for checkpoint in stale_checkpoints:
        checkpoint.status = ExecutionCheckpointStatus.EXPIRED
        checkpoint.resolved_at = timezone.now()
        checkpoint.save(update_fields=["status", "resolved_at"])
        expired_count += 1

        execution = checkpoint.execution
        publish_execution_event(
            execution.id,
            "execution.checkpoint_expired",
            serialize_execution_checkpoint(checkpoint),
        )

        if execution.status == ExecutionStatus.PAUSED:
            write_execution_stop_signal(execution)
            steps = list(execution.steps.all())
            finalize_execution_result(
                execution,
                status=ExecutionStatus.ERROR,
                duration_ms=execution.get_duration_ms() or 0,
                total_steps=len(steps),
                passed_steps=sum(step.status == "passed" for step in steps),
                failed_steps=sum(step.status == "failed" for step in steps),
                error_message="Execution checkpoint timed out.",
                stack_trace="Execution checkpoint expired before a tester resumed the run.",
            )

    return expired_count
