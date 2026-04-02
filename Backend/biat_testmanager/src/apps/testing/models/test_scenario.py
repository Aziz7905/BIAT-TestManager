import copy
import uuid

from django.db import models, transaction

from .choices import (
    BusinessPriority,
    TestPriority,
    TestScenarioPolarity,
    TestScenarioType,
)
from .utils import calculate_pass_rate


class TestScenario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    suite = models.ForeignKey(
        "testing.TestSuite",
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
        ordering = ["suite__name", "order_index", "title"]

    def __str__(self) -> str:
        return f"{self.suite.name} / {self.title}"

    def get_cases(self):
        return self.cases.order_by("order_index", "title")

    def get_pass_rate(self) -> float:
        aggregates = self.cases.aggregate(
            total=models.Count("id"),
            passed=models.Count("id", filter=models.Q(status="passed")),
        )
        return calculate_pass_rate(
            total_count=aggregates["total"] or 0,
            passed_count=aggregates["passed"] or 0,
        )

    @transaction.atomic
    def clone(self):
        cloned_scenario = TestScenario.objects.create(
            suite=self.suite,
            title=f"{self.title} Copy",
            description=self.description,
            scenario_type=self.scenario_type,
            priority=self.priority,
            business_priority=self.business_priority,
            polarity=self.polarity,
            ai_generated=self.ai_generated,
            ai_confidence=self.ai_confidence,
            order_index=self.order_index,
        )

        for case in self.get_cases().prefetch_related("linked_specifications"):
            linked_specifications = list(case.linked_specifications.all())
            case.pk = None
            case.scenario = cloned_scenario
            case.steps = copy.deepcopy(case.steps)
            case.test_data = copy.deepcopy(case.test_data)
            case.version = 1
            case.save()
            case.linked_specifications.set(linked_specifications)

        return cloned_scenario
