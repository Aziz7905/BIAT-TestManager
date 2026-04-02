from django.contrib import admin

from apps.automation.models import (
    AutomationScript,
    ExecutionSchedule,
    ExecutionStep,
    HealingEvent,
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
    readonly_fields = ("executed_at",)
    show_change_link = True


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
    search_fields = (
        "test_case__title",
        "test_case__scenario__title",
        "test_case__scenario__suite__name",
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
    search_fields = (
        "test_case__title",
        "test_case__scenario__title",
        "test_case__scenario__suite__name",
        "celery_task_id",
    )
    inlines = [ExecutionStepInline]


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
    search_fields = ("execution__test_case__title", "error_message")


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
    search_fields = ("name", "project__name", "suite__name")


@admin.register(HealingEvent)
class HealingEventAdmin(admin.ModelAdmin):
    list_display = (
        "execution",
        "step",
        "detection_method",
        "confidence_score",
        "status",
        "created_at",
    )
    list_filter = ("detection_method", "status", "approved_automatically")
    search_fields = ("execution__test_case__title", "original_selector", "healed_selector")
