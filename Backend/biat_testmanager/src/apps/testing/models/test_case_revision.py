import uuid

from django.conf import settings
from django.db import models


class TestCaseRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    test_case = models.ForeignKey(
        "testing.TestCase",
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    linked_specifications = models.ManyToManyField(
        "specs.Specification",
        blank=True,
        related_name="linked_test_case_revisions",
    )
    version_number = models.IntegerField()
    title = models.CharField(max_length=500)
    preconditions = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)
    expected_result = models.TextField()
    test_data = models.JSONField(default=dict, blank=True)
    source_snapshot_json = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_test_case_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "testing_test_case_revision"
        ordering = ["-version_number", "-created_at"]
        unique_together = [("test_case", "version_number")]

    def __str__(self) -> str:
        return f"{self.test_case.title} / v{self.version_number}"
