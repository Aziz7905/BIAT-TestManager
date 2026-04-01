from rest_framework import serializers

from apps.accounts.models import NotificationProvider, TeamMembership, UserProfile
from apps.accounts.services.notifications import (
    clear_notification_identifiers,
    normalize_notification_provider,
)
from apps.accounts.services.user_identity import update_user_identity_from_name


class TeamMembershipSummarySerializer(serializers.ModelSerializer):
    team = serializers.UUIDField(source="team.id", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    organization = serializers.UUIDField(source="team.organization.id", read_only=True)
    organization_name = serializers.CharField(
        source="team.organization.name",
        read_only=True,
    )

    class Meta:
        model = TeamMembership
        fields = [
            "id",
            "team",
            "team_name",
            "organization",
            "organization_name",
            "role",
            "is_primary",
            "is_active",
            "joined_at",
        ]


class UserProfileSerializer(serializers.ModelSerializer):
    organization = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    team = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()
    team_memberships = serializers.SerializerMethodField()

    def _get_active_memberships(self, obj):
        memberships = obj.user.team_memberships.select_related(
            "team",
            "team__organization",
        ).filter(is_active=True)
        return list(memberships)

    def _get_primary_membership(self, obj):
        memberships = self._get_active_memberships(obj)
        return next(
            (membership for membership in memberships if membership.is_primary),
            memberships[0] if memberships else None,
        )

    def get_team(self, obj):
        primary_membership = self._get_primary_membership(obj)
        if primary_membership:
            return str(primary_membership.team_id)
        if obj.team_id:
            return str(obj.team_id)
        return None

    def get_team_name(self, obj):
        primary_membership = self._get_primary_membership(obj)
        if primary_membership:
            return primary_membership.team.name
        if obj.team:
            return obj.team.name
        return None

    def get_team_memberships(self, obj):
        memberships = self._get_active_memberships(obj)
        return TeamMembershipSummarySerializer(memberships, many=True).data

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "organization",
            "organization_name",
            "team",
            "team_name",
            "team_memberships",
            "role",
            "notification_provider",
            "notifications_enabled",
            "created_at",
        ]


class MyProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    team = serializers.SerializerMethodField()
    team_name = serializers.SerializerMethodField()
    team_memberships = serializers.SerializerMethodField()
    has_jira_token = serializers.SerializerMethodField()
    has_github_token = serializers.SerializerMethodField()
    has_slack_user = serializers.SerializerMethodField()
    has_teams_user = serializers.SerializerMethodField()

    def _get_active_memberships(self, obj):
        memberships = obj.user.team_memberships.select_related(
            "team",
            "team__organization",
        ).filter(is_active=True)
        return list(memberships)

    def _get_primary_membership(self, obj):
        memberships = self._get_active_memberships(obj)
        return next(
            (membership for membership in memberships if membership.is_primary),
            memberships[0] if memberships else None,
        )

    def get_team_name(self, obj):
        primary_membership = self._get_primary_membership(obj)
        if primary_membership:
            return primary_membership.team.name
        if obj.team:
            return obj.team.name
        return None

    def get_team(self, obj):
        primary_membership = self._get_primary_membership(obj)
        if primary_membership:
            return str(primary_membership.team_id)
        if obj.team_id:
            return str(obj.team_id)
        return None

    def get_team_memberships(self, obj):
        memberships = self._get_active_memberships(obj)
        return TeamMembershipSummarySerializer(memberships, many=True).data

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "organization",
            "organization_name",
            "team",
            "team_name",
            "team_memberships",
            "role",
            "has_jira_token",
            "has_github_token",
            "notification_provider",
            "notifications_enabled",
            "slack_user_id",
            "slack_username",
            "teams_user_id",
            "has_slack_user",
            "has_teams_user",
            "created_at",
        ]

    def get_has_jira_token(self, obj):
        return bool(obj.jira_token)

    def get_has_github_token(self, obj):
        return bool(obj.github_token)

    def get_has_slack_user(self, obj):
        return bool(obj.slack_user_id)

    def get_has_teams_user(self, obj):
        return bool(obj.teams_user_id)


class UpdateMyProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    jira_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    github_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    notification_provider = serializers.ChoiceField(
        choices=NotificationProvider.choices,
        required=False,
    )
    slack_user_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )
    slack_username = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )
    teams_user_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=100,
    )
    notifications_enabled = serializers.BooleanField(required=False)

    def update(self, instance, validated_data):
        user = instance.user

        first_name = validated_data.get("first_name", user.first_name)
        last_name = validated_data.get("last_name", user.last_name)

        update_user_identity_from_name(
            user=user,
            organization=instance.organization,
            first_name=first_name,
            last_name=last_name,
        )

        if "jira_token" in validated_data:
            instance.jira_token = validated_data["jira_token"] or None

        if "github_token" in validated_data:
            instance.github_token = validated_data["github_token"] or None

        if "notification_provider" in validated_data:
            provider = normalize_notification_provider(
                validated_data["notification_provider"]
            )
            instance.notification_provider = provider
            if provider == NotificationProvider.NONE:
                clear_notification_identifiers(instance)

        if "slack_user_id" in validated_data:
            instance.slack_user_id = validated_data["slack_user_id"] or None

        if "slack_username" in validated_data:
            instance.slack_username = validated_data["slack_username"] or None

        if "teams_user_id" in validated_data:
            instance.teams_user_id = validated_data["teams_user_id"] or None

        if "notifications_enabled" in validated_data:
            instance.notifications_enabled = validated_data["notifications_enabled"]

        instance.save()
        return instance
