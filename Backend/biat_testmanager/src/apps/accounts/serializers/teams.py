from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import (
    AIProvider,
    ModelDeploymentMode,
    OrganizationRole,
    Team,
    TeamMembership,
    TeamMembershipRole,
)
from apps.accounts.services.access import (
    can_manage_team_membership_record,
    can_manage_team_api_key,
    get_managed_team_ids_for_user,
)
from apps.accounts.services.memberships import (
    assign_user_to_team,
)
from apps.accounts.services.roles import has_team_manager_role
from apps.accounts.services.team_ai import (
    UNSET,
    get_effective_ai_api_version,
    get_effective_ai_api_key,
    get_effective_ai_deployment_mode,
    get_effective_ai_endpoint_url,
    get_effective_ai_model,
    get_effective_ai_provider,
    get_effective_monthly_budget,
    update_team_ai_settings,
)
from apps.accounts.services.team_management import sync_manager_profile_with_team
from apps.accounts.services.validation import validate_manager_for_organization
from apps.integrations.services import (
    get_team_integration_values,
    update_team_integrations,
)

User = get_user_model()


class AIProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIProvider
        fields = ["id", "name", "provider_type", "base_url", "is_active"]


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
    # AI configuration is read/written through TeamAIConfig; these are
    # serializer-level fields, not Team model fields.
    ai_provider = serializers.PrimaryKeyRelatedField(
        queryset=AIProvider.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    ai_provider_name = serializers.SerializerMethodField()
    ai_provider_type = serializers.SerializerMethodField()
    ai_provider_base_url = serializers.SerializerMethodField()
    has_ai_api_key = serializers.SerializerMethodField()
    ai_api_key = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
    )
    ai_model = serializers.CharField(required=False, allow_blank=True)
    ai_endpoint_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ai_api_version = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ai_deployment_mode = serializers.ChoiceField(
        choices=ModelDeploymentMode.choices,
        required=False,
    )
    monthly_token_budget = serializers.IntegerField(required=False)

    # Integration configuration is read/written through IntegrationConfig.
    integrations = serializers.JSONField(required=False)

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
            "ai_provider_type",
            "ai_provider_base_url",
            "ai_api_key",
            "has_ai_api_key",
            "ai_model",
            "ai_endpoint_url",
            "ai_api_version",
            "ai_deployment_mode",
            "monthly_token_budget",
            "integrations",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def get_ai_provider_name(self, obj):
        provider = get_effective_ai_provider(obj)
        return provider.name if provider else None

    def get_ai_provider_type(self, obj):
        provider = get_effective_ai_provider(obj)
        return provider.provider_type if provider else None

    def get_ai_provider_base_url(self, obj):
        provider = get_effective_ai_provider(obj)
        return provider.base_url if provider else None

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
        return bool(get_effective_ai_api_key(obj))

    def to_representation(self, instance):
        payload = super().to_representation(instance)
        provider = get_effective_ai_provider(instance)
        payload["ai_provider"] = str(provider.id) if provider else None
        payload["ai_model"] = get_effective_ai_model(instance)
        payload["ai_endpoint_url"] = get_effective_ai_endpoint_url(instance)
        payload["ai_api_version"] = get_effective_ai_api_version(instance)
        payload["ai_deployment_mode"] = get_effective_ai_deployment_mode(instance)
        payload["monthly_token_budget"] = get_effective_monthly_budget(instance)

        payload["integrations"] = get_team_integration_values(instance)
        return payload

    def validate(self, attrs):
        request = self.context["request"]
        requester = request.user
        requester_profile = getattr(requester, "profile", None)
        requester_organization_role = getattr(
            requester_profile,
            "organization_role",
            None,
        )

        organization = attrs.get("organization") or getattr(self.instance, "organization", None)
        manager_user = attrs.get("manager")

        if self.instance is None and organization is None:
            organization = getattr(requester_profile, "organization", None)
            if organization is not None:
                attrs["organization"] = organization

        if (
            requester_organization_role == OrganizationRole.ORG_ADMIN
            and organization
            and requester_profile.organization_id != organization.id
        ):
            raise serializers.ValidationError(
                {"organization": "You can only manage teams in your organization."}
            )

        if requester_organization_role == OrganizationRole.MEMBER:
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
                    "ai_endpoint_url",
                    "ai_api_version",
                    "ai_deployment_mode",
                    "monthly_token_budget",
                    "integrations",
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
        ai_provider = validated_data.pop("ai_provider", None)
        ai_api_key = validated_data.pop("ai_api_key", None)
        ai_model = validated_data.pop("ai_model", None)
        ai_endpoint_url = validated_data.pop("ai_endpoint_url", None)
        ai_api_version = validated_data.pop("ai_api_version", None)
        ai_deployment_mode = validated_data.pop("ai_deployment_mode", None)
        monthly_token_budget = validated_data.pop("monthly_token_budget", None)
        integrations = validated_data.pop("integrations", None)

        team = Team.objects.create(**validated_data)
        update_fields: list[str] = []
        if manager_user:
            team.manager = manager_user
            update_fields.append("manager")
        if update_fields:
            team.save(update_fields=update_fields)

        update_team_ai_settings(
            team=team,
            provider=ai_provider,
            api_key=ai_api_key,
            endpoint_url=ai_endpoint_url,
            api_version=ai_api_version,
            model_name=ai_model or "gpt-4o-mini",
            deployment_mode=ai_deployment_mode or UNSET,
            monthly_budget=monthly_token_budget
            if isinstance(monthly_token_budget, int)
            else UNSET,
        )
        if integrations is not None:
            update_team_integrations(team=team, integrations=integrations)

        sync_manager_profile_with_team(manager_user, team)
        return team

    def update(self, instance, validated_data):
        request = self.context["request"]

        manager_user = validated_data.pop("manager", serializers.empty)
        ai_provider = validated_data.pop("ai_provider", serializers.empty)
        ai_api_key = validated_data.pop("ai_api_key", serializers.empty)
        ai_model = validated_data.pop("ai_model", serializers.empty)
        ai_endpoint_url = validated_data.pop("ai_endpoint_url", serializers.empty)
        ai_api_version = validated_data.pop("ai_api_version", serializers.empty)
        ai_deployment_mode = validated_data.pop("ai_deployment_mode", serializers.empty)
        monthly_token_budget = validated_data.pop("monthly_token_budget", serializers.empty)
        integrations = validated_data.pop("integrations", serializers.empty)

        has_ai_updates = any(
            value is not serializers.empty
            for value in [
                ai_provider,
                ai_api_key,
                ai_model,
                ai_endpoint_url,
                ai_api_version,
                ai_deployment_mode,
                monthly_token_budget,
            ]
        )
        if has_ai_updates and not can_manage_team_api_key(request.user, instance):
            raise serializers.ValidationError(
                {"ai_api_key": "You do not have permission to update the AI API key."}
            )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if manager_user is not serializers.empty:
            instance.manager = manager_user

        instance.save()

        if has_ai_updates:
            update_team_ai_settings(
                team=instance,
                provider=UNSET if ai_provider is serializers.empty else ai_provider,
                api_key=UNSET if ai_api_key is serializers.empty else ai_api_key,
                endpoint_url=(
                    UNSET if ai_endpoint_url is serializers.empty else ai_endpoint_url
                ),
                api_version=UNSET if ai_api_version is serializers.empty else ai_api_version,
                model_name=UNSET if ai_model is serializers.empty else ai_model,
                deployment_mode=(
                    UNSET
                    if ai_deployment_mode is serializers.empty
                    else ai_deployment_mode
                ),
                monthly_budget=(
                    monthly_token_budget
                    if monthly_token_budget is not serializers.empty
                    else UNSET
                ),
            )

        if integrations is not serializers.empty:
            update_team_integrations(
                team=instance,
                integrations=integrations,
            )

        sync_manager_profile_with_team(instance.manager, instance)

        return instance


class TeamMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source="user.email", read_only=True)
    user_role = serializers.SerializerMethodField()

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

    def get_user_role(self, obj):
        return getattr(obj.user.profile, "organization_role", None)


class TeamMembershipCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.select_related("profile"))
    role = serializers.ChoiceField(choices=TeamMembershipRole.choices, required=False)
    is_primary = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        team = self.context["team"]
        target_user = attrs["user"]
        target_profile = getattr(target_user, "profile", None)

        if not target_profile:
            raise serializers.ValidationError({"user": "Selected user does not have a profile."})

        if target_profile.organization_id != team.organization_id:
            raise serializers.ValidationError(
                {"user": "Selected user must belong to the same organization as the team."}
            )

        if target_profile.organization_role != OrganizationRole.MEMBER:
            raise serializers.ValidationError(
                {"user": "Only organization members can be assigned to a team."}
            )

        desired_role = attrs.get("role") or TeamMembershipRole.VIEWER

        if TeamMembership.objects.filter(
            team=team,
            user=target_user,
            is_active=True,
        ).exists():
            raise serializers.ValidationError(
                {"user": "This user is already assigned to the selected team."}
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
        actor_organization_role = getattr(
            getattr(actor, "profile", None),
            "organization_role",
            None,
        )
        team_manager_limited = (
            actor_organization_role == OrganizationRole.MEMBER
            and has_team_manager_role(actor, membership.team)
        )
        if team_manager_limited and desired_role not in {
            TeamMembershipRole.TESTER,
            TeamMembershipRole.VIEWER,
        }:
            raise serializers.ValidationError(
                {"role": "Team managers can only assign tester or viewer roles."}
            )

        if (
            desired_role == TeamMembershipRole.MANAGER
            and target_profile.organization_role == OrganizationRole.PLATFORM_OWNER
        ):
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
