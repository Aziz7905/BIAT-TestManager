from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import Team, TeamMembership, TeamMembershipRole, UserProfileRole
from apps.accounts.services.access import (
    can_manage_team_membership_record,
    can_manage_team_api_key,
    get_managed_team_ids_for_user,
)
from apps.accounts.services.memberships import (
    assign_user_to_team,
)
from apps.accounts.services.team_management import sync_manager_profile_with_team
from apps.accounts.services.validation import validate_manager_for_organization

User = get_user_model()


class TeamSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Team._meta.get_field("organization").remote_field.model.objects.all(),
        required=False,
    )
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    manager_name = serializers.SerializerMethodField()
    member_names = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    manager = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    ai_provider = serializers.PrimaryKeyRelatedField(
        queryset=Team._meta.get_field("ai_provider").remote_field.model.objects.all(),
        required=False,
        allow_null=True,
    )
    ai_provider_name = serializers.CharField(source="ai_provider.name", read_only=True)
    has_ai_api_key = serializers.SerializerMethodField()
    ai_api_key = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
    )
    ai_model = serializers.CharField(required=False, allow_blank=True)
    monthly_token_budget = serializers.IntegerField(required=False)
    jira_base_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    jira_project_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    github_org = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    github_repo = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    jenkins_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Team
        fields = [
            "id",
            "organization",
            "organization_name",
            "name",
            "manager",
            "manager_name",
            "member_names",
            "member_count",
            "ai_provider",
            "ai_provider_name",
            "ai_api_key",
            "has_ai_api_key",
            "ai_model",
            "monthly_token_budget",
            "tokens_used_this_month",
            "jira_base_url",
            "jira_project_key",
            "github_org",
            "github_repo",
            "jenkins_url",
            "created_at",
        ]
        read_only_fields = ["tokens_used_this_month", "created_at"]

    def get_manager_name(self, obj):
        if not obj.manager:
            return None
        return obj.manager.get_full_name().strip() or obj.manager.username

    def get_member_names(self, obj):
        memberships = obj.memberships.select_related("user").filter(is_active=True)
        member_names: list[str] = []

        for membership in memberships:
            full_name = membership.user.get_full_name().strip()
            member_names.append(full_name or membership.user.email or membership.user.username)

        return member_names

    def get_member_count(self, obj):
        return obj.memberships.filter(is_active=True).count()

    def get_has_ai_api_key(self, obj):
        return bool(obj.ai_api_key)

    def validate(self, attrs):
        request = self.context["request"]
        requester = request.user
        requester_profile = getattr(requester, "profile", None)
        requester_role = getattr(requester_profile, "role", None)

        organization = attrs.get("organization") or getattr(self.instance, "organization", None)
        manager_user = attrs.get("manager")

        if self.instance is None and organization is None:
            organization = getattr(requester_profile, "organization", None)
            if organization is not None:
                attrs["organization"] = organization

        if (
            requester_role == UserProfileRole.ORG_ADMIN
            and organization
            and requester_profile.organization_id != organization.id
        ):
            raise serializers.ValidationError(
                {"organization": "You can only manage teams in your organization."}
            )

        if requester_role == UserProfileRole.TEAM_MANAGER:
            if self.instance is None:
                raise serializers.ValidationError(
                    {"detail": "Team managers cannot create teams."}
                )
            managed_team_ids = get_managed_team_ids_for_user(requester)
            if self.instance.id not in managed_team_ids:
                raise serializers.ValidationError(
                    {"detail": "You can only manage your assigned teams."}
                )

            forbidden_fields = {
                field_name
                for field_name in attrs.keys()
                if field_name
                not in {
                    "ai_provider",
                    "ai_api_key",
                    "ai_model",
                    "monthly_token_budget",
                    "jira_base_url",
                    "jira_project_key",
                    "github_org",
                    "github_repo",
                    "jenkins_url",
                }
            }
            if forbidden_fields:
                raise serializers.ValidationError(
                    {
                        "detail": "Team managers can only update AI and integration settings."
                    }
                )

        if self.instance is None and manager_user is None:
            raise serializers.ValidationError(
                {"manager": "Manager is required when creating a team."}
            )

        validate_manager_for_organization(manager_user, organization)
        return attrs

    def create(self, validated_data):
        manager_user = validated_data.pop("manager", None)
        ai_api_key = validated_data.pop("ai_api_key", None)

        if not validated_data.get("ai_model"):
            validated_data.pop("ai_model", None)

        for field_name in [
            "jira_base_url",
            "jira_project_key",
            "github_org",
            "github_repo",
            "jenkins_url",
        ]:
            if not validated_data.get(field_name):
                validated_data[field_name] = None

        team = Team.objects.create(**validated_data)

        if manager_user:
            team.manager = manager_user

        if ai_api_key:
            team.ai_api_key = ai_api_key

        team.save()
        sync_manager_profile_with_team(manager_user, team)
        return team

    def update(self, instance, validated_data):
        request = self.context["request"]

        manager_user = validated_data.pop("manager", serializers.empty)
        ai_api_key = validated_data.pop("ai_api_key", serializers.empty)

        for attr, value in validated_data.items():
            if attr == "ai_model" and value == "":
                continue
            if attr in {
                "jira_base_url",
                "jira_project_key",
                "github_org",
                "github_repo",
                "jenkins_url",
            } and value == "":
                value = None
            setattr(instance, attr, value)

        if manager_user is not serializers.empty:
            instance.manager = manager_user

        if ai_api_key is not serializers.empty:
            if not can_manage_team_api_key(request.user, instance):
                raise serializers.ValidationError(
                    {"ai_api_key": "You do not have permission to update the AI API key."}
                )
            instance.ai_api_key = ai_api_key or None

        instance.save()

        sync_manager_profile_with_team(instance.manager, instance)

        return instance


class TeamMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    user_role = serializers.CharField(source="user.profile.role", read_only=True)

    class Meta:
        model = TeamMembership
        fields = [
            "id",
            "user_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "user_role",
            "role",
            "is_primary",
            "is_active",
            "joined_at",
        ]

    def get_full_name(self, obj):
        full_name = obj.user.get_full_name().strip()
        return full_name or obj.user.email or obj.user.username


class TeamMembershipCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.select_related("profile"))
    role = serializers.ChoiceField(choices=TeamMembershipRole.choices, required=False)
    is_primary = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        request = self.context["request"]
        team = self.context["team"]
        actor = request.user
        target_user = attrs["user"]
        target_profile = getattr(target_user, "profile", None)

        if not target_profile:
            raise serializers.ValidationError({"user": "Selected user does not have a profile."})

        if target_profile.organization_id != team.organization_id:
            raise serializers.ValidationError(
                {"user": "Selected user must belong to the same organization as the team."}
            )

        if target_profile.role not in {
            UserProfileRole.TEAM_MANAGER,
            UserProfileRole.TESTER,
            UserProfileRole.VIEWER,
        }:
            raise serializers.ValidationError(
                {"user": "Only team managers, testers, or viewers can be assigned to a team."}
            )

        desired_role = attrs.get("role") or {
            UserProfileRole.TEAM_MANAGER: TeamMembershipRole.MANAGER,
            UserProfileRole.TESTER: TeamMembershipRole.TESTER,
            UserProfileRole.VIEWER: TeamMembershipRole.VIEWER,
        }.get(target_profile.role)

        if desired_role is None:
            raise serializers.ValidationError(
                {"role": "A valid team role could not be inferred for this user."}
            )

        if TeamMembership.objects.filter(
            team=team,
            user=target_user,
            is_active=True,
        ).exists():
            raise serializers.ValidationError(
                {"user": "This user is already assigned to the selected team."}
            )

        actor_role = getattr(getattr(actor, "profile", None), "role", None)
        if actor_role == UserProfileRole.TEAM_MANAGER:
            raise serializers.ValidationError(
                {"detail": "Team managers cannot add members to teams."}
            )

        attrs["team"] = team
        attrs["desired_role"] = desired_role
        return attrs

    def create(self, validated_data):
        membership = assign_user_to_team(
            validated_data["user"],
            validated_data["team"],
            validated_data["desired_role"],
            is_primary=validated_data.get("is_primary", False),
        )
        return membership


class TeamMembershipUpdateSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=TeamMembershipRole.choices, required=False)
    is_primary = serializers.BooleanField(required=False)

    class Meta:
        model = TeamMembership
        fields = ["role", "is_primary"]

    def validate(self, attrs):
        request = self.context["request"]
        actor = request.user
        membership = self.instance
        target_profile = getattr(membership.user, "profile", None)

        if not can_manage_team_membership_record(actor, membership):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to manage this team member."}
            )

        if not target_profile:
            raise serializers.ValidationError(
                {"detail": "This membership is missing the linked user profile."}
            )

        desired_role = attrs.get("role", membership.role)
        actor_role = getattr(getattr(actor, "profile", None), "role", None)

        if actor_role == UserProfileRole.TEAM_MANAGER and desired_role not in {
            TeamMembershipRole.TESTER,
            TeamMembershipRole.VIEWER,
        }:
            raise serializers.ValidationError(
                {"role": "Team managers can only assign tester or viewer roles."}
            )

        if desired_role == TeamMembershipRole.MANAGER and target_profile.role == UserProfileRole.PLATFORM_OWNER:
            raise serializers.ValidationError(
                {"role": "Platform owners cannot be assigned as team members."}
            )

        attrs["desired_role"] = desired_role
        return attrs

    def update(self, instance, validated_data):
        desired_role = validated_data.get("desired_role", instance.role)
        make_primary = validated_data.get("is_primary", False)

        membership = assign_user_to_team(
            instance.user,
            instance.team,
            desired_role,
            is_primary=make_primary,
        )
        return membership
