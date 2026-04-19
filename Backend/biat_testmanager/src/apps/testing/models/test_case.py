#src/app/testing/models/test_case.py
import uuid

from django.apps import apps as django_apps
from django.db import models

from .choices import (
    TestCaseAutomationStatus,
    TestCaseDesignStatus,
    TestCaseOnFailureBehavior,
)
from .utils import normalize_step_lines


class TestCase(models.Model):
    REVISION_FIELDS = (
        "title",
        "preconditions",
        "steps",
        "expected_result",
        "test_data",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(
        "testing.TestScenario",
        on_delete=models.CASCADE,
        related_name="cases",
    )
    linked_specifications = models.ManyToManyField(
        "specs.Specification",
        blank=True,
        related_name="linked_test_cases",
    )
    title = models.CharField(max_length=500)
    preconditions = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)
    expected_result = models.TextField()
    test_data = models.JSONField(default=dict, blank=True)
    design_status = models.CharField(
        max_length=20,
        choices=TestCaseDesignStatus.choices,
        default=TestCaseDesignStatus.DRAFT,
        db_index=True,
    )
    automation_status = models.CharField(
        max_length=20,
        choices=TestCaseAutomationStatus.choices,
        default=TestCaseAutomationStatus.MANUAL,
    )
    ai_generated = models.BooleanField(default=False)
    jira_issue_key = models.CharField(max_length=100, blank=True, null=True)
    version = models.IntegerField(default=1)
    on_failure = models.CharField(
        max_length=30,
        choices=TestCaseOnFailureBehavior.choices,
        default=TestCaseOnFailureBehavior.FAIL_BUT_CONTINUE,
    )
    timeout_ms = models.IntegerField(default=120000)
    order_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "testing_test_case"
        ordering = ["scenario__title", "order_index", "title"]

    def __str__(self) -> str:
        return f"{self.scenario.title} / {self.title}"

    @property
    def status(self) -> str:
        return self.design_status

    @status.setter
    def status(self, value: str) -> None:
        self.design_status = value

    def get_latest_result(self):
        try:
            result_model = django_apps.get_model("automation", "TestResult")
        except LookupError:
            return None

        return result_model.objects.filter(
            execution__test_case=self
        ).select_related("execution").order_by("-created_at").first()

    def to_gherkin(self) -> str:
        lines = [
            f"Feature: {self.scenario.suite.name}",
            f"  Scenario: {self.title}",
        ]

        preconditions = [line.strip() for line in self.preconditions.splitlines() if line.strip()]
        for index, precondition in enumerate(preconditions):
            keyword = "Given" if index == 0 else "And"
            lines.append(f"    {keyword} {precondition}")

        for index, step in enumerate(normalize_step_lines(self.steps)):
            keyword = "When" if index == 0 else "And"
            lines.append(f"    {keyword} {step}")

        if self.expected_result.strip():
            lines.append(f"    Then {self.expected_result.strip()}")

        return "\n".join(lines)

    def get_version_history(self):
        return [
            {
                "id": str(revision.id),
                "version": revision.version_number,
                "created_at": revision.created_at,
                "created_by": revision.created_by_id,
            }
            for revision in self.revisions.select_related("created_by").order_by(
                "-version_number",
                "-created_at",
            )
        ]
