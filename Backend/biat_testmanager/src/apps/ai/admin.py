from django.contrib import admin

from apps.ai.models import AIGenerationRetrievedContext, AIGenerationSession


@admin.register(AIGenerationSession)
class AIGenerationSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "created_by",
        "status",
        "provider_name",
        "model_name",
        "created_at",
    )
    list_filter = ("status", "source_type", "provider_name", "purpose")
    search_fields = ("objective", "jira_issue_key", "project__name", "team__name")
    readonly_fields = ("created_at", "updated_at", "started_at", "completed_at")


@admin.register(AIGenerationRetrievedContext)
class AIGenerationRetrievedContextAdmin(admin.ModelAdmin):
    list_display = ("session", "context_type", "object_id", "external_ref", "score")
    list_filter = ("context_type",)
    search_fields = ("object_id", "external_ref", "metadata_json")
