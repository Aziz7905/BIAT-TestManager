import uuid

from django.db import models
from django.db.models import Q

from .choices import WebhookEventStatus


class WebhookEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository_binding = models.ForeignKey(
        "integrations.RepositoryBinding",
        on_delete=models.SET_NULL,
        related_name="webhook_events",
        null=True,
        blank=True,
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        related_name="webhook_events",
        null=True,
        blank=True,
    )
    provider_slug = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    external_id = models.CharField(max_length=150, null=True, blank=True)
    payload_json = models.JSONField(default=dict, blank=True)
    headers_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=WebhookEventStatus.choices,
        default=WebhookEventStatus.RECEIVED,
    )
    error_message = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integrations_webhook_event"
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider_slug", "external_id"],
                condition=Q(external_id__isnull=False) & ~Q(external_id=""),
                name="integrations_unique_provider_webhook_external_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=["provider_slug", "event_type", "status"],
                name="int_webhook_provider_idx",
            ),
            models.Index(
                fields=["project", "received_at"],
                name="int_webhook_project_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.provider_slug} / {self.event_type} / {self.external_id or self.id}"
