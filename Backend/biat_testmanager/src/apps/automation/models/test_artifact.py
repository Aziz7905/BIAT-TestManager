import uuid

from django.db import models

from .choices import ArtifactType


class TestArtifact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(
        "automation.TestExecution",
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    artifact_type = models.CharField(
        max_length=20,
        choices=ArtifactType.choices,
        db_index=True,
    )
    storage_path = models.CharField(max_length=500)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "automation_test_artifact"
        ordering = ["execution", "artifact_type", "created_at"]

    def __str__(self) -> str:
        return f"{self.execution_id} / {self.artifact_type}"
