import uuid

from django.conf import settings
from django.db import models

from .choices import IntegrationActionStatus


class IntegrationActionLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.SET_NULL,
        related_name="integration_action_logs",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        related_name="integration_action_logs",
        null=True,
        blank=True,
    )
    provider_slug = models.CharField(max_length=50)
    action_type = models.CharField(max_length=100)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="integration_action_logs",
        null=True,
        blank=True,
    )
    request_json = models.JSONField(default=dict, blank=True)
    response_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=IntegrationActionStatus.choices,
        default=IntegrationActionStatus.PENDING,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integrations_integration_action_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["provider_slug", "action_type", "status"],
                name="int_action_provider_idx",
            ),
            models.Index(
                fields=["project", "created_at"],
                name="int_action_project_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider_slug} / {self.action_type} / {self.status}"
