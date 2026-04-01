import uuid

from django.db import models


class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    domain = models.CharField(max_length=255, unique=True)
    logo = models.ImageField(upload_to="organization_logos/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_organization"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name