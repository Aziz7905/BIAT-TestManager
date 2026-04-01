import uuid

from django.apps import apps as django_apps
from django.conf import settings
from django.db import models

from apps.accounts.models import Team


class ProjectStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="projects",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.ACTIVE,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects_project"
        ordering = ["name"]
        unique_together = [("team", "name")]

    def __str__(self) -> str:
        return f"{self.team.name} / {self.name}"

    def get_members(self):
        return self.members.select_related("user").order_by("joined_at")

    def get_specs(self):
        try:
            specification_model = django_apps.get_model("specs", "Specification")
        except LookupError:
            return []
        return specification_model.objects.filter(project=self)

    def get_stats(self):
        specs = self.get_specs()
        suites = self.get_active_suites()

        return {
            "members_count": self.get_members().count(),
            "specifications_count": specs.count() if hasattr(specs, "count") else len(specs),
            "active_suites_count": suites.count() if hasattr(suites, "count") else len(suites),
        }

    def get_active_suites(self):
        try:
            suite_model = django_apps.get_model("testing", "TestSuite")
        except LookupError:
            return []
        return suite_model.objects.filter(project=self)

