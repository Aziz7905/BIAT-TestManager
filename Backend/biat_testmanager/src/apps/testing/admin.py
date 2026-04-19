from django.contrib import admin

from apps.testing.models import (
    TestCase,
    TestCaseRevision,
    TestPlan,
    TestRun,
    TestRunCase,
    TestScenario,
    TestSection,
    TestSuite,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 0
    fields = (
        "title",
        "design_status",
        "automation_status",
        "version",
        "order_index",
    )
    readonly_fields = ("version",)
    show_change_link = True
    raw_id_fields = ("scenario",)


class TestRunCaseInline(admin.TabularInline):
    model = TestRunCase
    extra = 0
    fields = ("test_case", "test_case_revision", "assigned_to", "status", "order_index", "attempt_count")
    readonly_fields = ("attempt_count", "test_case_revision")
    raw_id_fields = ("test_case", "assigned_to")
    show_change_link = True


# ---------------------------------------------------------------------------
# TestSuite
# ---------------------------------------------------------------------------

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
    raw_id_fields = ("project", "specification", "created_by")
    readonly_fields = ("created_at",)
    list_select_related = ("project", "specification", "created_by")


# ---------------------------------------------------------------------------
# TestSection
# ---------------------------------------------------------------------------

@admin.register(TestSection)
class TestSectionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "suite",
        "parent",
        "order_index",
        "created_at",
    )
    list_filter = ("suite__project__team",)
    search_fields = ("name", "suite__name", "suite__project__name")
    raw_id_fields = ("suite", "parent")
    readonly_fields = ("created_at",)
    list_select_related = ("suite", "suite__project", "parent")


# ---------------------------------------------------------------------------
# TestScenario
# ---------------------------------------------------------------------------

@admin.register(TestScenario)
class TestScenarioAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "section",
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
    search_fields = ("title", "section__name", "section__suite__name", "section__suite__project__name")
    raw_id_fields = ("section",)
    readonly_fields = ("created_at",)
    list_select_related = ("section", "section__suite")
    inlines = [TestCaseInline]


# ---------------------------------------------------------------------------
# TestCase
# ---------------------------------------------------------------------------

@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "scenario",
        "design_status",
        "automation_status",
        "version",
        "order_index",
        "updated_at",
    )
    list_filter = ("design_status", "automation_status", "ai_generated", "on_failure")
    search_fields = (
        "title",
        "scenario__title",
        "scenario__section__suite__name",
        "linked_specifications__title",
        "linked_specifications__external_reference",
    )
    raw_id_fields = ("scenario",)
    readonly_fields = ("version", "created_at", "updated_at")
    filter_horizontal = ("linked_specifications",)
    list_select_related = ("scenario", "scenario__section", "scenario__section__suite")


# ---------------------------------------------------------------------------
# TestCaseRevision — immutable, so all content fields are read-only
# ---------------------------------------------------------------------------

@admin.register(TestCaseRevision)
class TestCaseRevisionAdmin(admin.ModelAdmin):
    list_display = (
        "test_case",
        "version_number",
        "created_by",
        "created_at",
    )
    search_fields = (
        "test_case__title",
        "title",
    )
    raw_id_fields = ("test_case", "created_by")
    readonly_fields = (
        "test_case",
        "version_number",
        "title",
        "preconditions",
        "steps",
        "expected_result",
        "test_data",
        "source_snapshot_json",
        "created_by",
        "created_at",
    )
    filter_horizontal = ("linked_specifications",)
    list_select_related = ("test_case", "created_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# TestPlan
# ---------------------------------------------------------------------------

@admin.register(TestPlan)
class TestPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "project__team")
    search_fields = ("name", "project__name")
    raw_id_fields = ("project", "created_by")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("project", "created_by")


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------

@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "plan",
        "status",
        "trigger_type",
        "created_by",
        "started_at",
        "ended_at",
    )
    list_filter = ("status", "trigger_type", "project__team")
    search_fields = ("name", "project__name", "plan__name")
    raw_id_fields = ("project", "plan", "created_by")
    readonly_fields = ("created_at", "started_at", "ended_at")
    list_select_related = ("project", "plan", "created_by")
    inlines = [TestRunCaseInline]


# ---------------------------------------------------------------------------
# TestRunCase
# ---------------------------------------------------------------------------

@admin.register(TestRunCase)
class TestRunCaseAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "test_case",
        "status",
        "order_index",
        "attempt_count",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "run__project__team")
    search_fields = ("run__name", "test_case__title")
    raw_id_fields = ("run", "test_case", "test_case_revision", "assigned_to")
    readonly_fields = ("attempt_count", "leased_at", "leased_by", "created_at", "updated_at")
    list_select_related = ("run", "test_case", "assigned_to")
