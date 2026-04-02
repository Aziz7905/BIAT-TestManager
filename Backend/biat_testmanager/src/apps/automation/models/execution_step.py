import uuid

from django.db import models

from apps.automation.models.choices import ExecutionStepStatus


class ExecutionStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(
        "automation.TestExecution",
        on_delete=models.CASCADE,
        related_name="steps",
    )
    step_index = models.IntegerField()
    action = models.CharField(max_length=255)
    target_element = models.CharField(max_length=500)
    selector_used = models.CharField(max_length=1000, null=True, blank=True)
    input_value = models.CharField(max_length=1000, null=True, blank=True)
    screenshot_url = models.URLField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=ExecutionStepStatus.choices,
        default=ExecutionStepStatus.PENDING,
    )
    error_message = models.TextField(null=True, blank=True)
    stack_trace = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "automation_execution_step"
        ordering = ["execution__started_at", "step_index"]
        unique_together = [("execution", "step_index")]

    def __str__(self) -> str:
        return f"{self.execution_id} / step {self.step_index}"

    def get_screenshot(self):
        return self.screenshot_url

    def get_dom_snapshot(self):
        return None
