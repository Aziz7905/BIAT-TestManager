import uuid

from django.conf import settings
from django.db import models

from .organization import Organization


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=200)

    # Display/cache pointer to the team's manager. Authority is granted by
    # TeamMembership(role="manager"), not by this field alone.
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_teams",
    )

    # AI configuration → see TeamAIConfig
    # Integration configuration → see IntegrationConfig

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_team"
        ordering = ["name"]
        unique_together = [("organization", "name")]

    def __str__(self) -> str:
        return f"{self.organization.name} / {self.name}"
