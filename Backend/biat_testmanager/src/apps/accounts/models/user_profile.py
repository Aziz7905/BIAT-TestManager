import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField

from .choices import (
    NotificationProvider,
    OrganizationRole,
)
from .organization import Organization
from .team import Team
from .utils import build_org_email


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="user_profiles",
    )

    primary_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
    )

    organization_role = models.CharField(
        max_length=30,
        choices=OrganizationRole.choices,
        default=OrganizationRole.MEMBER,
    )

    jira_token = EncryptedCharField(max_length=512, null=True, blank=True)
    github_token = EncryptedCharField(max_length=512, null=True, blank=True)

    notification_provider = models.CharField(
        max_length=20,
        choices=NotificationProvider.choices,
        default=NotificationProvider.NONE,
    )
    slack_user_id = models.CharField(max_length=100, null=True, blank=True)
    slack_username = models.CharField(max_length=100, null=True, blank=True)
    teams_user_id = models.CharField(max_length=100, null=True, blank=True)
    notifications_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_user_profile"
        ordering = ["user__first_name", "user__last_name"]

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.username

    def clean(self) -> None:
        super().clean()

        if (
            self.primary_team
            and self.primary_team.organization_id != self.organization_id
        ):
            raise ValidationError("Team must belong to the same organization.")

        if not self.user.first_name or not self.user.last_name:
            raise ValidationError(
                {"user": "User must have both first name and last name."}
            )

        if not self.organization.domain:
            raise ValidationError(
                {"organization": "Organization must have a valid domain."}
            )

        expected_email = build_org_email(
            self.user.first_name,
            self.user.last_name,
            self.organization.domain,
        )

        if self.user.email and self.user.email.lower() != expected_email:
            raise ValidationError({"user": f"Email must be exactly: {expected_email}"})

    @property
    def team(self):
        return self.primary_team

    @team.setter
    def team(self, value) -> None:
        self.primary_team = value

    @property
    def team_id(self):
        return self.primary_team_id

    @team_id.setter
    def team_id(self, value) -> None:
        self.primary_team_id = value
