from django.contrib import admin

from apps.integrations.models import (
    ExternalIssueLink,
    IntegrationActionLog,
    IntegrationConfig,
    RepositoryBinding,
    UserIntegrationCredential,
    WebhookEvent,
)


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = ("provider_slug", "team", "project", "is_active", "updated_at")
    search_fields = ("provider_slug", "team__name", "project__name")
    list_filter = ("provider_slug", "is_active")


@admin.register(UserIntegrationCredential)
class UserIntegrationCredentialAdmin(admin.ModelAdmin):
    list_display = ("user_profile", "provider_slug", "is_active", "updated_at")
    search_fields = ("user_profile__user__username", "provider_slug")
    list_filter = ("provider_slug", "is_active")


@admin.register(RepositoryBinding)
class RepositoryBindingAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "provider_slug",
        "repo_identifier",
        "default_branch",
        "is_active",
        "updated_at",
    )
    search_fields = ("project__name", "provider_slug", "repo_identifier")
    list_filter = ("provider_slug", "is_active")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        "provider_slug",
        "event_type",
        "external_id",
        "project",
        "status",
        "received_at",
    )
    search_fields = ("provider_slug", "event_type", "external_id", "project__name")
    list_filter = ("provider_slug", "event_type", "status")


@admin.register(ExternalIssueLink)
class ExternalIssueLinkAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "provider_slug",
        "external_key",
        "content_type",
        "object_id",
        "is_active",
    )
    search_fields = ("project__name", "provider_slug", "external_key", "object_id")
    list_filter = ("provider_slug", "is_active", "content_type")


@admin.register(IntegrationActionLog)
class IntegrationActionLogAdmin(admin.ModelAdmin):
    list_display = (
        "provider_slug",
        "action_type",
        "project",
        "actor_user",
        "status",
        "created_at",
    )
    search_fields = ("provider_slug", "action_type", "project__name", "actor_user__username")
    list_filter = ("provider_slug", "action_type", "status")
