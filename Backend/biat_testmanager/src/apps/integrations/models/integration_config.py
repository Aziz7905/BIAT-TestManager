import json
import uuid

from django.db import models
from django.db.models import Q
from encrypted_model_fields.fields import EncryptedTextField


class IntegrationConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.CASCADE,
        related_name="integration_configs",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="integration_configs",
        null=True,
        blank=True,
    )
    provider_slug = models.CharField(max_length=50)
    config_json_encrypted = EncryptedTextField(default="{}", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_integration_config"
        ordering = ["team__name", "provider_slug"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "provider_slug"],
                condition=Q(project__isnull=True),
                name="integrations_unique_team_provider_config",
            ),
            models.UniqueConstraint(
                fields=["team", "project", "provider_slug"],
                condition=Q(project__isnull=False),
                name="integrations_unique_project_provider_config",
            ),
        ]

    def __str__(self) -> str:
        target = self.project.name if self.project else self.team.name
        return f"{target} / {self.provider_slug}"

    @property
    def config_data(self) -> dict:
        if not self.config_json_encrypted:
            return {}
        try:
            parsed_value = json.loads(self.config_json_encrypted)
        except json.JSONDecodeError:
            return {}
        return parsed_value if isinstance(parsed_value, dict) else {}

    def set_config_data(self, payload: dict) -> None:
        self.config_json_encrypted = json.dumps(payload or {})
