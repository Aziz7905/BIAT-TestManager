from django.contrib import admin

from apps.automation.models import (
    AutomationScript,
    ExecutionCheckpoint,
    ExecutionEnvironment,
    ExecutionSchedule,
    ExecutionStep,
    TestArtifact,
    TestExecution,
    TestResult,
)


class ExecutionStepInline(admin.TabularInline):
    model = ExecutionStep
    extra = 0
    fields = (
        "step_index",
        "action",
        "status",
        "duration_ms",
        "executed_at",
    )
    readonly_fields = (
        "step_index",
        "executed_at",
    )
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class TestArtifactInline(admin.TabularInline):
    model = TestArtifact
    extra = 0
    fields = ("artifact_type", "storage_path", "created_at")
    readonly_fields = ("artifact_type", "storage_path", "created_at")
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class ExecutionCheckpointInline(admin.TabularInline):
    model = ExecutionCheckpoint
    extra = 0
    fields = ("checkpoint_key", "title", "status", "requested_at", "resolved_at")
    readonly_fields = ("checkpoint_key", "title", "status", "requested_at", "resolved_at")
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AutomationScript)
class AutomationScriptAdmin(admin.ModelAdmin):
    list_display = (
        "test_case",
        "framework",
        "language",
        "script_version",
        "generated_by",
        "is_active",
        "created_at",
    )
    list_filter = ("framework", "language", "generated_by", "is_active")
    list_select_related = True
    raw_id_fields = ("test_case", "test_case_revision")
    readonly_fields = ("script_version", "created_at")
    search_fields = (
        "test_case__title",
        "test_case__scenario__title",
        "test_case__scenario__section__suite__name",
    )


@admin.register(TestExecution)
class TestExecutionAdmin(admin.ModelAdmin):
    list_display = (
        "test_case",
        "status",
        "browser",
        "platform",
        "trigger_type",
        "triggered_by",
        "started_at",
        "ended_at",
    )
    list_filter = ("status", "browser", "platform", "trigger_type")
    list_select_related = True
    raw_id_fields = ("test_case", "script", "triggered_by", "run_case", "environment")
    readonly_fields = ("started_at", "ended_at", "celery_task_id", "attempt_number")
    search_fields = (
        "test_case__title",
        "test_case__scenario__title",
        "test_case__scenario__section__suite__name",
        "celery_task_id",
    )
    inlines = [ExecutionStepInline, ExecutionCheckpointInline, TestArtifactInline]


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = (
        "execution",
        "status",
        "duration_ms",
        "total_steps",
        "failed_steps",
        "created_at",
    )
    list_filter = ("status", "created_at")
    list_select_related = True
    raw_id_fields = ("execution",)
    readonly_fields = ("created_at",)
    search_fields = ("execution__test_case__title", "error_message")


@admin.register(ExecutionEnvironment)
class ExecutionEnvironmentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "team",
        "engine",
        "browser",
        "platform",
        "is_active",
        "max_parallelism",
    )
    list_filter = ("engine", "browser", "platform", "is_active")
    list_select_related = True
    raw_id_fields = ("team",)
    readonly_fields = ("created_at",)
    search_fields = ("name", "team__name")


@admin.register(ExecutionSchedule)
class ExecutionScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "suite",
        "browser",
        "platform",
        "is_active",
        "next_run_at",
    )
    list_filter = ("browser", "platform", "is_active")
    list_select_related = True
    raw_id_fields = ("project", "suite", "created_by")
    readonly_fields = ("next_run_at",)
    search_fields = ("name", "project__name", "suite__name")


@admin.register(ExecutionCheckpoint)
class ExecutionCheckpointAdmin(admin.ModelAdmin):
    list_display = (
        "checkpoint_key",
        "execution",
        "step",
        "status",
        "requested_at",
        "resolved_at",
        "resolved_by",
    )
    list_filter = ("status", "requested_at")
    list_select_related = True
    raw_id_fields = ("execution", "step", "resolved_by")
    readonly_fields = ("requested_at", "resolved_at")
    search_fields = ("checkpoint_key", "title", "execution__test_case__title")
