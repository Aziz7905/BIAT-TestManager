import uuid

from django.conf import settings
from django.db import models


class RepositoryBinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="repository_bindings",
    )
    provider_slug = models.CharField(max_length=50)
    repo_identifier = models.CharField(max_length=255)
    default_branch = models.CharField(max_length=150, default="main")
    metadata_json = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_repository_bindings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_repository_binding"
        ordering = ["project__name", "provider_slug", "repo_identifier"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "provider_slug", "repo_identifier"],
                name="integrations_unique_project_repository_binding",
            ),
        ]
        indexes = [
            models.Index(
                fields=["provider_slug", "repo_identifier"],
                name="int_repo_provider_idx",
            ),
            models.Index(
                fields=["project", "is_active"],
                name="int_repo_project_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.provider_slug}:{self.repo_identifier}"
