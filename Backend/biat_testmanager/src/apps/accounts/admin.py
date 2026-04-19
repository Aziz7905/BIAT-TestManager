from django.contrib import admin

from apps.accounts.models import (
    AIProvider,
    ModelProfile,
    Organization,
    Team,
    TeamAIConfig,
    TeamMembership,
    TeamMembershipRole,
    UserProfile,
)
from apps.accounts.services.team_ai import get_effective_ai_provider


@admin.register(AIProvider)
class AIProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_type", "is_active")
    search_fields = ("name", "provider_type")
    list_filter = ("is_active", "provider_type")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "created_at")
    search_fields = ("name", "domain")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "legacy_manager",
        "membership_managers",
        "resolved_ai_provider",
        "created_at",
    )
    search_fields = (
        "name",
        "organization__name",
        "manager__first_name",
        "manager__last_name",
        "manager__email",
    )
    list_filter = ("organization",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("organization", "manager")
            .prefetch_related("memberships__user")
        )

    @admin.display(description="Manager pointer (legacy)")
    def legacy_manager(self, obj):
        return obj.manager

    @admin.display(description="Membership managers")
    def membership_managers(self, obj):
        managers = [
            membership.user.get_full_name().strip()
            or membership.user.email
            or membership.user.username
            for membership in obj.memberships.all()
            if membership.is_active and membership.role == TeamMembershipRole.MANAGER
        ]
        return ", ".join(managers) or "-"

    @admin.display(description="AI Provider")
    def resolved_ai_provider(self, obj):
        provider = get_effective_ai_provider(obj)
        return getattr(provider, "name", None)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "organization",
        "primary_team",
        "organization_role",
        "notification_provider",
        "notifications_enabled",
        "created_at",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "primary_team__name",
        "organization__name",
        "slack_user_id",
        "slack_username",
        "teams_user_id",
    )
    list_filter = (
        "organization_role",
        "organization",
        "primary_team",
        "notification_provider",
        "notifications_enabled",
    )

@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "team",
        "role",
        "is_primary",
        "is_active",
        "joined_at",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "team__name",
        "team__organization__name",
    )
    list_filter = (
        "role",
        "is_primary",
        "is_active",
        "team__organization",
    )


@admin.register(TeamAIConfig)
class TeamAIConfigAdmin(admin.ModelAdmin):
    list_display = (
        "team",
        "provider",
        "default_model_profile",
        "monthly_budget",
        "is_active",
        "updated_at",
    )
    search_fields = ("team__name", "provider__name")
    list_filter = ("is_active", "provider")


@admin.register(ModelProfile)
class ModelProfileAdmin(admin.ModelAdmin):
    list_display = (
        "slug",
        "team_ai_config",
        "purpose",
        "model_name",
        "deployment_mode",
        "is_default",
    )
    search_fields = ("slug", "model_name", "team_ai_config__team__name")
    list_filter = ("purpose", "deployment_mode", "is_default")
