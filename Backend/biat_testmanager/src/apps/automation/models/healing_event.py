import uuid

from django.db import models

from apps.automation.models.choices import (
    HealingDetectionMethod,
    HealingEventStatus,
)


class HealingEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(
        "automation.TestExecution",
        on_delete=models.CASCADE,
        related_name="healing_events",
    )
    step = models.ForeignKey(
        "automation.ExecutionStep",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="healing_events",
    )
    original_selector = models.CharField(max_length=1000)
    healed_selector = models.CharField(max_length=1000)
    detection_method = models.CharField(
        max_length=30,
        choices=HealingDetectionMethod.choices,
    )
    confidence_score = models.FloatField()
    reason = models.TextField()
    approved_automatically = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=HealingEventStatus.choices,
    )
    screenshot_before_url = models.URLField(null=True, blank=True)
    screenshot_after_url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "automation_healing_event"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.execution_id} / {self.status}"

    def apply_fix(self):
        self.status = HealingEventStatus.APPLIED
        self.save(update_fields=["status"])
        return self

    def rollback(self):
        self.status = HealingEventStatus.REJECTED
        self.save(update_fields=["status"])
        return self

    def to_audit_log(self) -> dict:
        return {
            "execution_id": str(self.execution_id),
            "step_id": str(self.step_id) if self.step_id else None,
            "original_selector": self.original_selector,
            "healed_selector": self.healed_selector,
            "detection_method": self.detection_method,
            "confidence_score": self.confidence_score,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }
