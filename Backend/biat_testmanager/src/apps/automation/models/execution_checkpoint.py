import uuid

from django.conf import settings
from django.db import models

from apps.automation.models.choices import ExecutionCheckpointStatus


class ExecutionCheckpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(
        "automation.TestExecution",
        on_delete=models.CASCADE,
        related_name="checkpoints",
    )
    step = models.ForeignKey(
        "automation.ExecutionStep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkpoints",
    )
    checkpoint_key = models.CharField(max_length=120)
    title = models.CharField(max_length=255)
    instructions = models.TextField()
    payload_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ExecutionCheckpointStatus.choices,
        default=ExecutionCheckpointStatus.PENDING,
        db_index=True,
    )
    requested_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_execution_checkpoints",
    )

    class Meta:
        db_table = "automation_execution_checkpoint"
        ordering = ["requested_at", "checkpoint_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["execution", "checkpoint_key"],
                name="automation_unique_execution_checkpoint_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.execution_id} / {self.checkpoint_key} / {self.status}"
