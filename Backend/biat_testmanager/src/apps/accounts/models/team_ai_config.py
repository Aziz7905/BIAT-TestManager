import uuid

from django.core.exceptions import ValidationError
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField

from .ai_provider import AIProvider
from .team import Team


class TeamAIConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.OneToOneField(
        Team,
        on_delete=models.CASCADE,
        related_name="ai_config",
    )
    provider = models.ForeignKey(
        AIProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_ai_configs",
    )
    api_key = EncryptedCharField(max_length=512, null=True, blank=True)
    monthly_budget = models.IntegerField(default=1000000)
    is_active = models.BooleanField(default=True)
    default_model_profile = models.ForeignKey(
        "accounts.ModelProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_team_ai_config"
        ordering = ["team__name"]

    def __str__(self) -> str:
        return f"AI config for {self.team.name}"

    def clean(self) -> None:
        super().clean()
        if (
            self.default_model_profile_id
            and self.default_model_profile.team_ai_config_id != self.id
        ):
            raise ValidationError(
                {
                    "default_model_profile": (
                        "Default model profile must belong to the same team AI config."
                    )
                }
            )
