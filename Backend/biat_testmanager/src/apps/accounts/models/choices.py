from django.db import models


class UserProfileRole(models.TextChoices):
    PLATFORM_OWNER = "platform_owner", "Platform Owner"
    ORG_ADMIN = "org_admin", "Org Admin"
    TEAM_MANAGER = "team_manager", "Team Manager"
    TESTER = "tester", "Tester"
    VIEWER = "viewer", "Viewer"


class TeamMembershipRole(models.TextChoices):
    MANAGER = "manager", "Manager"
    TESTER = "tester", "Tester"
    VIEWER = "viewer", "Viewer"


class NotificationProvider(models.TextChoices):
    NONE = "none", "None"
    SLACK = "slack", "Slack"
    TEAMS = "teams", "Microsoft Teams"
