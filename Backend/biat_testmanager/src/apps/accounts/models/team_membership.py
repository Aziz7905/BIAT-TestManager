import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .choices import TeamMembershipRole
from .team import Team


class TeamMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="team_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=TeamMembershipRole.choices,
        default=TeamMembershipRole.VIEWER,
    )
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_team_membership"
        ordering = ["team__name", "user__first_name", "user__last_name"]
        unique_together = [("team", "user")]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_primary=True, is_active=True),
                name="accounts_unique_primary_active_team_membership",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} / {self.team.name}"

    def clean(self) -> None:
        super().clean()

        profile = getattr(self.user, "profile", None)
        if profile and profile.organization_id != self.team.organization_id:
            raise ValidationError(
                {"team": "Team membership must belong to the user's organization."}
            )
