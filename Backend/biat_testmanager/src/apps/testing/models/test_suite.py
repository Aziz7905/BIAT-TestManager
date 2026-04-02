import uuid

from django.conf import settings
from django.db import models

from .utils import calculate_pass_rate


class TestSuite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="test_suites",
    )
    specification = models.ForeignKey(
        "specs.Specification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="test_suites",
    )
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    folder_path = models.CharField(max_length=500, blank=True, default="")
    ai_generated = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_test_suites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "testing_test_suite"
        ordering = ["project__name", "folder_path", "name"]
        unique_together = [("project", "folder_path", "name")]

    def __str__(self) -> str:
        if self.folder_path:
            return f"{self.project.name} / {self.folder_path} / {self.name}"
        return f"{self.project.name} / {self.name}"

    def get_scenarios(self):
        return self.scenarios.order_by("order_index", "title")

    def get_total_cases(self) -> int:
        return self.scenarios.aggregate(total=models.Count("cases"))["total"] or 0

    def get_pass_rate(self) -> float:
        aggregates = self.scenarios.aggregate(
            total=models.Count("cases"),
            passed=models.Count(
                "cases",
                filter=models.Q(cases__status="passed"),
            ),
        )
        return calculate_pass_rate(
            total_count=aggregates["total"] or 0,
            passed_count=aggregates["passed"] or 0,
        )

