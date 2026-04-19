import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ExternalIssueLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="external_issue_links",
    )
    provider_slug = models.CharField(max_length=50)
    external_key = models.CharField(max_length=100)
    external_url = models.URLField(blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=64)
    content_object = GenericForeignKey("content_type", "object_id")
    metadata_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_external_issue_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_external_issue_link"
        ordering = ["project__name", "provider_slug", "external_key"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "project",
                    "provider_slug",
                    "external_key",
                    "content_type",
                    "object_id",
                ],
                name="integrations_unique_external_issue_link",
            ),
        ]
        indexes = [
            models.Index(
                fields=["project", "provider_slug", "external_key"],
                name="int_issue_project_idx",
            ),
            models.Index(
                fields=["content_type", "object_id"],
                name="int_issue_target_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.provider_slug}:{self.external_key}"
