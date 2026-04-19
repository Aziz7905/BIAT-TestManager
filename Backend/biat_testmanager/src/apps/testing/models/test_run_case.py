import uuid

from django.conf import settings
from django.db import models

from .choices import TestRunCaseStatus


class TestRunCase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        "testing.TestRun",
        on_delete=models.CASCADE,
        related_name="run_cases",
    )
    # test_case is kept for navigation; revision is the execution truth
    test_case = models.ForeignKey(
        "testing.TestCase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="run_cases",
    )
    test_case_revision = models.ForeignKey(
        "testing.TestCaseRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="run_cases",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_run_cases",
    )
    status = models.CharField(
        max_length=20,
        choices=TestRunCaseStatus.choices,
        default=TestRunCaseStatus.PENDING,
        db_index=True,
    )
    order_index = models.IntegerField(default=0)
    # Minimal dispatch lease - tracks which worker picked up this run-case
    # and how many attempts have been made. Not a full job queue.
    attempt_count = models.PositiveIntegerField(default=0)
    leased_at = models.DateTimeField(null=True, blank=True)
    leased_by = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "testing_test_run_case"
        ordering = ["run", "order_index"]

    def __str__(self) -> str:
        revision_label = (
            f"v{self.test_case_revision.version_number}"
            if self.test_case_revision_id
            else "no revision"
        )
        case_label = self.test_case.title if self.test_case_id else "deleted case"
        return f"{self.run.name} / {case_label} ({revision_label})"
