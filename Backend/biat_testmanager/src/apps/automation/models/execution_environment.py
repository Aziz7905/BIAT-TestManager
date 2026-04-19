import uuid

from django.db import models

from .choices import AutomationFramework, ExecutionBrowser, ExecutionPlatform


class ExecutionEnvironment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.CASCADE,
        related_name="execution_environments",
    )
    name = models.CharField(max_length=200)
    engine = models.CharField(
        max_length=20,
        choices=AutomationFramework.choices,
        default=AutomationFramework.PLAYWRIGHT,
    )
    browser = models.CharField(
        max_length=20,
        choices=ExecutionBrowser.choices,
        default=ExecutionBrowser.CHROMIUM,
    )
    platform = models.CharField(
        max_length=20,
        choices=ExecutionPlatform.choices,
        default=ExecutionPlatform.DESKTOP,
    )
    # Extra capabilities passed through to the engine (headless flag, viewport, etc.)
    capabilities_json = models.JSONField(default=dict, blank=True)
    max_parallelism = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "automation_execution_environment"
        ordering = ["team__name", "name"]
        unique_together = [("team", "name")]

    def __str__(self) -> str:
        return f"{self.team.name} / {self.name} ({self.engine} / {self.browser})"
