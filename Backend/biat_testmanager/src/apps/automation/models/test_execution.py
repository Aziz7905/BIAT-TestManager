import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.automation.models.choices import (
    ExecutionBrowser,
    ExecutionPlatform,
    ExecutionStatus,
    ExecutionTriggerType,
)


class TestExecution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test_case = models.ForeignKey(
        "testing.TestCase",
        on_delete=models.CASCADE,
        related_name="executions",
    )
    script = models.ForeignKey(
        "automation.AutomationScript",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executions",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_test_executions",
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=ExecutionTriggerType.choices,
        default=ExecutionTriggerType.MANUAL,
    )
    status = models.CharField(
        max_length=20,
        choices=ExecutionStatus.choices,
        default=ExecutionStatus.QUEUED,
        db_index=True,
    )
    browser = models.CharField(
        max_length=20,
        choices=ExecutionBrowser.choices,
        default=ExecutionBrowser.CHROMIUM,
    )
    platform = models.CharField(
        max_length=20,
        choices=ExecutionPlatform.choices,
        default=ExecutionPlatform.DESKTOP,
    )
    run_case = models.ForeignKey(
        "testing.TestRunCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executions",
    )
    environment = models.ForeignKey(
        "automation.ExecutionEnvironment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executions",
    )
    # Attempt number within the run-case (1 = first attempt, 2 = first retry, …)
    attempt_number = models.PositiveIntegerField(default=1)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    selenium_session_id = models.CharField(max_length=255, null=True, blank=True)
    pause_requested = models.BooleanField(default=False)

    class Meta:
        db_table = "automation_test_execution"
        ordering = ["-started_at", "-id"]

    def __str__(self) -> str:
        return f"{self.test_case.title} / {self.status}"

    def pause(self):
        if self.status == ExecutionStatus.RUNNING:
            self.pause_requested = True
            self.status = ExecutionStatus.PAUSED
            self.save(update_fields=["pause_requested", "status"])
        return self

    def resume(self):
        if self.status == ExecutionStatus.PAUSED:
            self.pause_requested = False
            self.status = ExecutionStatus.QUEUED
            self.save(update_fields=["pause_requested", "status"])
        return self

    def stop(self):
        if self.status in {
            ExecutionStatus.QUEUED,
            ExecutionStatus.RUNNING,
            ExecutionStatus.PAUSED,
        }:
            self.pause_requested = True
            self.status = ExecutionStatus.CANCELLED
            if self.ended_at is None:
                self.ended_at = timezone.now()
            self.save(update_fields=["pause_requested", "status", "ended_at"])
        return self

    def get_duration_ms(self):
        if self.started_at is None:
            return None

        finished_at = self.ended_at or timezone.now()
        duration = finished_at - self.started_at
        return int(duration.total_seconds() * 1000)
