from django.contrib import admin

from apps.projects.models import Project, ProjectMember


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_select_related = ("team", "team__organization", "created_by")
    list_display = (
        "name",
        "team",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "team__name",
        "team__organization__name",
        "created_by__first_name",
        "created_by__last_name",
        "created_by__email",
    )
    list_filter = ("status", "team__organization", "team")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_select_related = ("project", "project__team", "user")
    list_display = (
        "project",
        "user",
        "role",
        "joined_at",
    )
    search_fields = (
        "project__name",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    list_filter = ("role", "project__team__organization", "project__team")
    readonly_fields = ("joined_at",)
