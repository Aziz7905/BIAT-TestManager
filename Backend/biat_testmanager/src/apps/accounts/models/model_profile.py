import uuid
from decimal import Decimal

from django.db import models
from django.db.models import Q

from .team_ai_config import TeamAIConfig


class ModelProfilePurpose(models.TextChoices):
    DEFAULT = "default", "Default"
    TEST_DESIGN = "test_design", "Test Design"
    REVIEW = "review", "Review"
    EXECUTION = "execution", "Execution"


class ModelDeploymentMode(models.TextChoices):
    CLOUD = "cloud", "Cloud"
    LOCAL = "local", "Local"
    HYBRID = "hybrid", "Hybrid"


class ModelProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_ai_config = models.ForeignKey(
        TeamAIConfig,
        on_delete=models.CASCADE,
        related_name="model_profiles",
    )
    slug = models.SlugField(max_length=100)
    purpose = models.CharField(
        max_length=30,
        choices=ModelProfilePurpose.choices,
        default=ModelProfilePurpose.DEFAULT,
    )
    model_name = models.CharField(max_length=150)
    temperature = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.10"),
    )
    max_tokens = models.PositiveIntegerField(default=4096)
    deployment_mode = models.CharField(
        max_length=20,
        choices=ModelDeploymentMode.choices,
        default=ModelDeploymentMode.CLOUD,
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_model_profile"
        ordering = ["team_ai_config__team__name", "slug"]
        unique_together = [("team_ai_config", "slug")]
        constraints = [
            models.UniqueConstraint(
                fields=["team_ai_config"],
                condition=Q(is_default=True),
                name="accounts_unique_default_model_profile_per_team_ai_config",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.team_ai_config.team.name} / {self.slug}"
