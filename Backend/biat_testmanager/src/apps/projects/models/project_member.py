import uuid

from django.conf import settings
from django.db import models


class ProjectMemberRole(models.TextChoices):
    OWNER = "owner", "Owner"
    EDITOR = "editor", "Editor"
    VIEWER = "viewer", "Viewer"


class ProjectMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=ProjectMemberRole.choices,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "projects_project_member"
        ordering = ["project__name", "user__first_name", "user__last_name"]
        unique_together = [("project", "user")]

    def __str__(self) -> str:
        return f"{self.project.name} / {self.user.get_full_name() or self.user.username}"

    def has_permission(self, action: str) -> bool:
        if self.role == ProjectMemberRole.OWNER:
            return True

        if self.role == ProjectMemberRole.EDITOR:
            return action in {
                "view",
                "edit",
                "create_suite",
                "create_specification",
                "run_tests",
            }

        return action == "view"

