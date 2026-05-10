from django.contrib import admin

from apps.integrations.models import (
    ExternalIssueLink,
    IntegrationActionLog,
    IntegrationConfig,
    IntegrationProvider,
    RepositoryBinding,
    UserIntegrationCredential,
    WebhookEvent,
)


@admin.register(IntegrationProvider)
class IntegrationProviderAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "is_active", "updated_at")
    search_fields = ("slug", "name")
    list_filter = ("is_active",)


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "team", "project", "is_active", "updated_at")
    search_fields = ("provider__slug", "provider__name", "team__name", "project__name")
    list_filter = ("provider", "is_active")


@admin.register(UserIntegrationCredential)
class UserIntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ("user_profile", "provider", "is_active", "updated_at")
    search_fields = ("user_profile__user__username", "provider__slug", "provider__name")
    list_filter = ("provider", "is_active")


@admin.register(RepositoryBinding)
class RepositoryBindingAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "provider",
        "repo_identifier",
        "default_branch",
        "is_active",
        "updated_at",
    )
    search_fields = ("project__name", "provider__slug", "provider__name", "repo_identifier")
    list_filter = ("provider", "is_active")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "event_type",
        "external_id",
        "project",
        "status",
        "received_at",
    )
    search_fields = ("provider__slug", "provider__name", "event_type", "external_id", "project__name")
    list_filter = ("provider", "event_type", "status")


@admin.register(ExternalIssueLink)
class ExternalIssueLinkAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "provider",
        "external_key",
        "content_type",
        "object_id",
        "is_active",
    )
    search_fields = ("project__name", "provider__slug", "provider__name", "external_key", "object_id")
    list_filter = ("provider", "is_active", "content_type")


@admin.register(IntegrationActionLog)
class IntegrationActionLogAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "action_type",
        "project",
        "actor_user",
        "status",
        "created_at",
    )
    search_fields = ("provider__slug", "provider__name", "action_type", "project__name", "actor_user__username")
    list_filter = ("provider", "action_type", "status")
