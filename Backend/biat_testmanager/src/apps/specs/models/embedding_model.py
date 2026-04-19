import uuid

from django.db import models


class EmbeddingModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    provider = models.CharField(max_length=120, blank=True)
    dimensions = models.PositiveIntegerField()
    normalize = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specs_embedding_model"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
