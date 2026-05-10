from django.db import models


class IntegrationProvider(models.Model):
    """Reference table for supported external integration providers."""

    slug = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_integration_provider"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.slug
