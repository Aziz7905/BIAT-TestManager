from django.db import models


class OrganizationRole(models.TextChoices):
    PLATFORM_OWNER = "platform_owner", "Platform Owner"
    ORG_ADMIN = "org_admin", "Org Admin"
    MEMBER = "member", "Member"


class TeamMembershipRole(models.TextChoices):
    MANAGER = "manager", "Manager"
    TESTER = "tester", "Tester"
    VIEWER = "viewer", "Viewer"


class NotificationProvider(models.TextChoices):
    NONE = "none", "None"
    SLACK = "slack", "Slack"
    TEAMS = "teams", "Microsoft Teams"
