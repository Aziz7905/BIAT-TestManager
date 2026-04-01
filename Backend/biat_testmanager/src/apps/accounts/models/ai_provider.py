from django.db import models


class AIProvider(models.Model):
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=50)
    base_url = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "accounts_ai_provider"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name