import uuid

from django.conf import settings
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField

from .ai_provider import AIProvider
from .organization import Organization


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    name = models.CharField(max_length=200)

    # Compatibility assignment pointer. Team authority is granted by
    # TeamMembership(role="manager"), not by this field alone.
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_teams",
    )

    ai_provider = models.ForeignKey(
        AIProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )
    ai_api_key = EncryptedCharField(max_length=512, null=True, blank=True)
    ai_model = models.CharField(max_length=100, default="gpt-4o-mini")

    monthly_token_budget = models.IntegerField(default=100000)
    tokens_used_this_month = models.IntegerField(default=0)

    jira_base_url = models.URLField(null=True, blank=True)
    jira_project_key = models.CharField(max_length=100, null=True, blank=True)
    github_org = models.CharField(max_length=150, null=True, blank=True)
    github_repo = models.CharField(max_length=150, null=True, blank=True)
    jenkins_url = models.URLField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_team"
        ordering = ["name"]
        unique_together = [("organization", "name")]

    def __str__(self) -> str:
        return f"{self.organization.name} / {self.name}"
