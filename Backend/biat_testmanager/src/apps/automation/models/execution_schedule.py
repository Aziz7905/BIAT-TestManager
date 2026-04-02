import uuid

from django.conf import settings
from django.db import models

from apps.automation.models.choices import ExecutionBrowser, ExecutionPlatform


class ExecutionSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="execution_schedules",
    )
    suite = models.ForeignKey(
        "testing.TestSuite",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_schedules",
    )
    name = models.CharField(max_length=200)
    cron_expression = models.CharField(max_length=100)
    timezone = models.CharField(max_length=64, default="UTC")
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
    is_active = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_execution_schedules",
    )

    class Meta:
        db_table = "automation_execution_schedule"
        ordering = ["project__name", "name"]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.name}"

    def save(self, *args, **kwargs):
        if self.is_active:
            self.compute_next_run()
        else:
            self.next_run_at = None
        super().save(*args, **kwargs)

    def compute_next_run(self):
        from apps.automation.services.scheduling import compute_next_run_for_schedule

        self.next_run_at = compute_next_run_for_schedule(
            cron_expression=self.cron_expression,
            timezone_name=self.timezone,
        )
        return self.next_run_at

    def trigger_now(self):
        from apps.automation.services.scheduling import trigger_execution_schedule

        return trigger_execution_schedule(self)
