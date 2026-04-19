#src/app/testing/models/test_scenario.py
import uuid

from django.db import models

from .choices import (
    BusinessPriority,
    TestPriority,
    TestScenarioPolarity,
    TestScenarioType,
)
from .utils import calculate_pass_rate


class TestScenario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        "testing.TestSection",
        on_delete=models.CASCADE,
        related_name="scenarios",
    )
    title = models.CharField(max_length=500)
    description = models.TextField()
    scenario_type = models.CharField(
        max_length=30,
        choices=TestScenarioType.choices,
        default=TestScenarioType.HAPPY_PATH,
    )
    priority = models.CharField(
        max_length=20,
        choices=TestPriority.choices,
        default=TestPriority.MEDIUM,
    )
    business_priority = models.CharField(
        max_length=20,
        choices=BusinessPriority.choices,
        null=True,
        blank=True,
    )
    polarity = models.CharField(
        max_length=20,
        choices=TestScenarioPolarity.choices,
        default=TestScenarioPolarity.POSITIVE,
    )
    ai_generated = models.BooleanField(default=False)
    ai_confidence = models.FloatField(null=True, blank=True)
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "testing_test_scenario"
        ordering = ["section__suite__name", "section__order_index", "order_index", "title"]

    def __str__(self) -> str:
        return f"{self.section.suite.name} / {self.title}"

    @property
    def suite(self):
        return self.section.suite

    @property
    def suite_id(self):
        return self.section.suite_id

    def get_cases(self):
        return self.cases.order_by("order_index", "title")

    def get_pass_rate(self) -> float:
        # Batch 4 keeps this intentionally simple: a case counts as passed when it
        # has at least one passing execution result linked to it.
        aggregates = self.cases.aggregate(
            total=models.Count("id", distinct=True),
            passed=models.Count(
                "id",
                filter=models.Q(executions__result__status="passed"),
                distinct=True,
            ),
        )
        return calculate_pass_rate(
            total_count=aggregates["total"] or 0,
            passed_count=aggregates["passed"] or 0,
        )

