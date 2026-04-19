import uuid

from django.conf import settings
from django.db import models

from .choices import TestPlanStatus


class TestPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="test_plans",
    )
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=TestPlanStatus.choices,
        default=TestPlanStatus.DRAFT,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_test_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "testing_test_plan"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.name}"
