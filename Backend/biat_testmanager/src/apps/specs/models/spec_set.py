import uuid

from django.db import models

from apps.projects.models import Project

from .choices import SpecSetType


class SpecSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="spec_sets",
    )
    source = models.ForeignKey(
        "specs.SpecificationSource",
        on_delete=models.CASCADE,
        related_name="spec_sets",
        null=True,
        blank=True,
    )
    set_key = models.CharField(max_length=240, db_index=True)
    set_type = models.CharField(
        max_length=40,
        choices=SpecSetType.choices,
        default=SpecSetType.MODULE,
        db_index=True,
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    items = models.ManyToManyField(
        "specs.SpecItem",
        related_name="spec_sets",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specs_spec_set"
        ordering = ["source__name", "set_type", "title"]
        unique_together = [("project", "source", "set_key")]
        indexes = [
            models.Index(fields=["project", "set_type"]),
            models.Index(fields=["source", "set_type"]),
        ]

    def __str__(self) -> str:
        return self.title
