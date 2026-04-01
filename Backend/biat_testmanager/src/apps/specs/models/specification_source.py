import uuid

from django.conf import settings
from django.db import models

from apps.projects.models import Project

from .choices import SpecificationSourceParserStatus, SpecificationSourceType


def specification_source_upload_to(instance, filename: str) -> str:
    project_id = instance.project_id or "unassigned"
    return f"spec_sources/{project_id}/{filename}"


class SpecificationSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="specification_sources",
    )
    name = models.CharField(max_length=300)
    source_type = models.CharField(
        max_length=20,
        choices=SpecificationSourceType.choices,
    )
    file = models.FileField(
        upload_to=specification_source_upload_to,
        null=True,
        blank=True,
    )
    raw_text = models.TextField(blank=True)
    source_url = models.URLField(blank=True, null=True)
    jira_issue_key = models.CharField(max_length=100, blank=True, null=True)
    parser_status = models.CharField(
        max_length=20,
        choices=SpecificationSourceParserStatus.choices,
        default=SpecificationSourceParserStatus.UPLOADED,
    )
    parser_error = models.TextField(blank=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    column_mapping = models.JSONField(default=dict, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_specification_sources",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specs_specification_source"
        ordering = ["project__name", "-created_at", "name"]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.name}"

