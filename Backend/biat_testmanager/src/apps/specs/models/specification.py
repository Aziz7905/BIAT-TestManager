import uuid

from django.apps import apps as django_apps
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.projects.models import Project

from .choices import SpecificationSourceType


class Specification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="specifications",
    )
    source = models.ForeignKey(
        "specs.SpecificationSource",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_specifications",
    )
    title = models.CharField(max_length=300)
    content = models.TextField()
    source_type = models.CharField(
        max_length=20,
        choices=SpecificationSourceType.choices,
        default=SpecificationSourceType.MANUAL,
    )
    jira_issue_key = models.CharField(max_length=100, blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    external_reference = models.CharField(max_length=120, blank=True, null=True)
    source_metadata = models.JSONField(default=dict, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    version = models.CharField(max_length=50, default="1.0")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_specifications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "specs_specification"
        ordering = ["project__name", "title", "-created_at"]
        unique_together = [("project", "title", "version")]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.title}"

    def chunk_for_rag(self):
        return self.chunks.order_by("chunk_index")

    def get_embeddings(self):
        return [
            chunk.embedding_vector
            for chunk in self.chunks.order_by("chunk_index")
            if chunk.embedding_vector is not None
        ]

    def get_test_suites(self):
        try:
            suite_model = django_apps.get_model("testing", "TestSuite")
        except LookupError:
            return []
        return suite_model.objects.filter(
            Q(specification=self) |
            Q(scenarios__cases__linked_specifications=self)
        ).distinct()
