from django.contrib import admin

from apps.testing.models import TestCase, TestScenario, TestSuite


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 0
    fields = (
        "title",
        "status",
        "automation_status",
        "version",
        "order_index",
    )
    readonly_fields = ("version",)
    show_change_link = True


@admin.register(TestSuite)
class TestSuiteAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "specification",
        "folder_path",
        "ai_generated",
        "created_by",
        "created_at",
    )
    list_filter = ("project__team", "ai_generated", "created_at")
    search_fields = ("name", "project__name", "specification__title")


@admin.register(TestScenario)
class TestScenarioAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "suite",
        "scenario_type",
        "priority",
        "business_priority",
        "polarity",
        "order_index",
        "ai_generated",
        "created_at",
    )
    list_filter = (
        "scenario_type",
        "priority",
        "business_priority",
        "polarity",
        "ai_generated",
    )
    search_fields = ("title", "suite__name", "suite__project__name")
    inlines = [TestCaseInline]


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "scenario",
        "status",
        "automation_status",
        "version",
        "order_index",
        "updated_at",
    )
    list_filter = ("status", "automation_status", "ai_generated", "on_failure")
    search_fields = (
        "title",
        "scenario__title",
        "scenario__suite__name",
        "linked_specifications__title",
        "linked_specifications__external_reference",
    )
    filter_horizontal = ("linked_specifications",)
