import uuid

from django.apps import apps as django_apps
from django.db import models

from .choices import (
    TestCaseAutomationStatus,
    TestCaseOnFailureBehavior,
    TestCaseStatus,
)
from .utils import normalize_step_lines


class TestCase(models.Model):
    VERSIONED_FIELDS = (
        "title",
        "preconditions",
        "steps",
        "expected_result",
        "test_data",
        "on_failure",
        "timeout_ms",
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
    status = models.CharField(
        max_length=20,
        choices=TestCaseStatus.choices,
        default=TestCaseStatus.DRAFT,
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

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self._should_increment_version(update_fields):
            self.version += 1
            if update_fields is not None:
                updated_field_names = set(update_fields)
                updated_field_names.update({"version", "updated_at"})
                kwargs["update_fields"] = list(updated_field_names)
        super().save(*args, **kwargs)

    def _should_increment_version(self, update_fields) -> bool:
        if not self.pk:
            return False

        if update_fields is not None and not (set(update_fields) & set(self.VERSIONED_FIELDS)):
            return False

        current = type(self).objects.filter(pk=self.pk).values(*self.VERSIONED_FIELDS).first()
        if current is None:
            return False

        return any(
            current[field_name] != getattr(self, field_name)
            for field_name in self.VERSIONED_FIELDS
        )

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
                "version": self.version,
                "updated_at": self.updated_at,
            }
        ]
