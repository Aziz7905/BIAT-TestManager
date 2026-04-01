from django.contrib import admin

from apps.accounts.models import AIProvider, Organization, Team, TeamMembership, UserProfile


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
    list_display = ("name", "organization", "manager", "ai_provider", "created_at")
    search_fields = (
        "name",
        "organization__name",
        "manager__first_name",
        "manager__last_name",
        "manager__email",
    )
    list_filter = ("ai_provider", "organization")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "organization",
        "team",
        "role",
        "notification_provider",
        "notifications_enabled",
        "created_at",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "team__name",
        "organization__name",
        "slack_user_id",
        "slack_username",
        "teams_user_id",
    )
    list_filter = (
        "role",
        "organization",
        "team",
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
