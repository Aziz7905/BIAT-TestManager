import uuid

from django.conf import settings
from django.db import models

from .choices import TestRunStatus, TestRunTriggerType


class TestRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        "testing.TestPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="test_runs",
    )
    name = models.CharField(max_length=300)
    status = models.CharField(
        max_length=20,
        choices=TestRunStatus.choices,
        default=TestRunStatus.PENDING,
        db_index=True,
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TestRunTriggerType.choices,
        default=TestRunTriggerType.MANUAL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_test_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "testing_test_run"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.name}"

    def get_pass_rate(self) -> float:
        from apps.testing.models.utils import calculate_pass_rate
        from apps.testing.models.choices import TestRunCaseStatus

        aggregates = self.run_cases.aggregate(
            total=models.Count("id"),
            passed=models.Count(
                "id",
                filter=models.Q(status=TestRunCaseStatus.PASSED),
            ),
        )
        return calculate_pass_rate(
            total_count=aggregates["total"] or 0,
            passed_count=aggregates["passed"] or 0,
        )
