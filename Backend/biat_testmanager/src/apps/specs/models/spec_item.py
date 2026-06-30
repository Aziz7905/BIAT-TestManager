import uuid

from django.db import models

from apps.projects.models import Project

from .choices import SpecItemType


class SpecItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="spec_items",
    )
    source = models.ForeignKey(
        "specs.SpecificationSource",
        on_delete=models.CASCADE,
        related_name="spec_items",
        null=True,
        blank=True,
    )
    source_record = models.OneToOneField(
        "specs.SpecificationSourceRecord",
        on_delete=models.SET_NULL,
        related_name="spec_item",
        null=True,
        blank=True,
    )
    specification = models.OneToOneField(
        "specs.Specification",
        on_delete=models.SET_NULL,
        related_name="spec_item",
        null=True,
        blank=True,
    )
    external_key = models.CharField(max_length=160, blank=True, db_index=True)
    item_type = models.CharField(
        max_length=40,
        choices=SpecItemType.choices,
        default=SpecItemType.REQUIREMENT,
        db_index=True,
    )
    title = models.CharField(max_length=300)
    content = models.TextField()
    module = models.CharField(max_length=200, blank=True)
    feature = models.CharField(max_length=200, blank=True)
    priority = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=80, blank=True)
    parent_external_key = models.CharField(max_length=160, blank=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    extra_fields = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specs_spec_item"
        ordering = ["source__name", "module", "feature", "external_key", "title"]
        indexes = [
            models.Index(fields=["project", "item_type"]),
            models.Index(fields=["project", "external_key"]),
            models.Index(fields=["source", "module", "feature"]),
        ]

    def __str__(self) -> str:
        key = f"{self.external_key} " if self.external_key else ""
        return f"{key}{self.title}"
