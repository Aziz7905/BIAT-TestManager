#src/app/testing/models/test_suite.py
import uuid

from django.apps import apps as django_apps
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

    @property
    def scenarios(self):
        scenario_model = django_apps.get_model("testing", "TestScenario")
        return scenario_model.objects.filter(section__suite=self)

    def get_scenarios(self):
        return self.scenarios.select_related("section").order_by(
            "section__order_index",
            "order_index",
            "title",
        )

    def get_total_cases(self) -> int:
        return (
            self.sections.aggregate(total=models.Count("scenarios__cases", distinct=True))["total"]
            or 0
        )

    def get_pass_rate(self) -> float:
        # Batch 4 keeps this intentionally simple: a case counts as passed when it
        # has at least one passing execution result linked to it.
        aggregates = self.sections.aggregate(
            total=models.Count("scenarios__cases", distinct=True),
            passed=models.Count(
                "scenarios__cases",
                filter=models.Q(
                    scenarios__cases__executions__result__status="passed",
                ),
                distinct=True,
            ),
        )
        return calculate_pass_rate(
            total_count=aggregates["total"] or 0,
            passed_count=aggregates["passed"] or 0,
        )
