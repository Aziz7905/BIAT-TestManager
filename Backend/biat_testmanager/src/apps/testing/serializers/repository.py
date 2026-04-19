from __future__ import annotations

from rest_framework import serializers

from apps.testing.models import TestScenario, TestSection, TestSuite

from .reporting import RecentRunCardSerializer


class RepositorySummarySerializer(serializers.Serializer):
    suite_count = serializers.IntegerField(required=False)
    section_count = serializers.IntegerField(required=False)
    child_section_count = serializers.IntegerField(required=False)
    scenario_count = serializers.IntegerField(required=False)
    case_count = serializers.IntegerField(required=False)
    approved_case_count = serializers.IntegerField(required=False)
    automated_case_count = serializers.IntegerField(required=False)
    draft_case_count = serializers.IntegerField(required=False)
    in_review_case_count = serializers.IntegerField(required=False)
    archived_case_count = serializers.IntegerField(required=False)
    manual_case_count = serializers.IntegerField(required=False)


class RepositoryCountsSerializer(serializers.Serializer):
    section_count = serializers.IntegerField(required=False)
    child_section_count = serializers.IntegerField(required=False)
    scenario_count = serializers.IntegerField(required=False)
    case_count = serializers.IntegerField(required=False)
    approved_case_count = serializers.IntegerField(required=False)
    automated_case_count = serializers.IntegerField(required=False)


class RepositoryExecutionSnapshotSerializer(serializers.Serializer):
    last_execution_at = serializers.DateTimeField(allow_null=True)
    recent_execution_count = serializers.IntegerField()
    recent_pass_rate = serializers.FloatField()


class LinkedSpecificationSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    external_reference = serializers.CharField(allow_null=True)
    source_type = serializers.CharField()


class RepositoryTreeScenarioSerializer(serializers.ModelSerializer):
    case_count = serializers.IntegerField()
    approved_case_count = serializers.IntegerField()
    automated_case_count = serializers.IntegerField()

    class Meta:
        model = TestScenario
        fields = [
            "id",
            "title",
            "scenario_type",
            "priority",
            "order_index",
            "case_count",
            "approved_case_count",
            "automated_case_count",
        ]


class RepositoryTreeSectionSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()
    scenarios = serializers.SerializerMethodField()

    class Meta:
        model = TestSection
        fields = [
            "id",
            "name",
            "parent_id",
            "order_index",
            "counts",
            "children",
            "scenarios",
        ]

    def get_counts(self, obj) -> dict:
        return {
            "child_section_count": getattr(obj, "child_section_count", 0) or 0,
            "scenario_count": getattr(obj, "scenario_count", 0) or 0,
            "case_count": getattr(obj, "case_count", 0) or 0,
        }

    def get_children(self, obj):
        children_map = self.context.get("children_map", {})
        children = children_map.get(obj.id, [])
        return RepositoryTreeSectionSerializer(children, many=True, context=self.context).data

    def get_scenarios(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("scenarios")
        scenarios = prefetched if prefetched is not None else obj.scenarios.all()
        ordered_scenarios = sorted(scenarios, key=lambda value: (value.order_index, value.title))
        return RepositoryTreeScenarioSerializer(ordered_scenarios, many=True).data


class RepositoryTreeSuiteSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()

    class Meta:
        model = TestSuite
        fields = [
            "id",
            "name",
            "folder_path",
            "counts",
            "sections",
        ]

    def get_counts(self, obj) -> dict:
        return {
            "section_count": getattr(obj, "section_count", 0) or 0,
            "scenario_count": getattr(obj, "scenario_count", 0) or 0,
            "case_count": getattr(obj, "case_count", 0) or 0,
        }

    def get_sections(self, obj):
        prefetched = getattr(obj, "_prefetched_objects_cache", {}).get("sections")
        all_sections = list(prefetched) if prefetched is not None else list(
            obj.sections.all().order_by("order_index", "name")
        )

        children_map: dict = {}
        for section in all_sections:
            children_map.setdefault(section.parent_id, []).append(section)

        root_sections = sorted(
            children_map.get(None, []),
            key=lambda value: (value.order_index, value.name),
        )
        context = {**self.context, "children_map": children_map}
        return RepositoryTreeSectionSerializer(root_sections, many=True, context=context).data


class ProjectRepositoryTreeSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    project_name = serializers.CharField()
    summary = RepositorySummarySerializer()
    suites = RepositoryTreeSuiteSerializer(many=True)


class RepositoryProjectSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    team_name = serializers.CharField(required=False)
    organization_name = serializers.CharField(required=False)


class RepositoryContextSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    project_name = serializers.CharField()
    suite_id = serializers.UUIDField(required=False, allow_null=True)
    suite_name = serializers.CharField(required=False, allow_null=True)
    section_id = serializers.UUIDField(required=False, allow_null=True)
    section_name = serializers.CharField(required=False, allow_null=True)
    scenario_id = serializers.UUIDField(required=False, allow_null=True)
    scenario_title = serializers.CharField(required=False, allow_null=True)
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    parent_name = serializers.CharField(required=False, allow_null=True)


class RepositorySuitePreviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    folder_path = serializers.CharField()
    counts = RepositoryCountsSerializer()


class RepositorySectionPreviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    counts = RepositoryCountsSerializer()


class RepositoryScenarioPreviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    priority = serializers.CharField()
    scenario_type = serializers.CharField(required=False)
    counts = RepositoryCountsSerializer()


class RepositoryCaseSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    design_status = serializers.CharField()
    automation_status = serializers.CharField()
    version = serializers.IntegerField()
    order_index = serializers.IntegerField()
    latest_result_status = serializers.CharField(allow_null=True)
    has_active_script = serializers.BooleanField()


class ProjectRepositoryOverviewSerializer(serializers.Serializer):
    project = RepositoryProjectSerializer()
    summary = RepositorySummarySerializer()
    recent_activity = RepositoryExecutionSnapshotSerializer()
    top_suites = RepositorySuitePreviewSerializer(many=True)
    recent_runs = RecentRunCardSerializer(many=True)


class TestSuiteOverviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    folder_path = serializers.CharField()
    context = RepositoryContextSerializer()
    specification = LinkedSpecificationSummarySerializer(allow_null=True)
    created_by_name = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    counts = RepositorySummarySerializer()
    recent_activity = RepositoryExecutionSnapshotSerializer()
    linked_specifications = LinkedSpecificationSummarySerializer(many=True)
    sections = RepositorySectionPreviewSerializer(many=True)


class TestSectionOverviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    context = RepositoryContextSerializer()
    counts = RepositorySummarySerializer()
    recent_activity = RepositoryExecutionSnapshotSerializer()
    linked_specifications = LinkedSpecificationSummarySerializer(many=True)
    child_sections = RepositorySectionPreviewSerializer(many=True)
    scenarios = RepositoryScenarioPreviewSerializer(many=True)


class TestScenarioOverviewSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    description = serializers.CharField()
    scenario_type = serializers.CharField()
    priority = serializers.CharField()
    business_priority = serializers.CharField(allow_null=True)
    polarity = serializers.CharField()
    context = RepositoryContextSerializer()
    coverage = RepositorySummarySerializer()
    execution_snapshot = RepositoryExecutionSnapshotSerializer()
    linked_specifications = LinkedSpecificationSummarySerializer(many=True)
    cases = RepositoryCaseSummarySerializer(many=True)


class TestCaseDesignSerializer(serializers.Serializer):
    preconditions = serializers.CharField()
    steps = serializers.ListField(child=serializers.JSONField())
    expected_result = serializers.CharField()
    test_data = serializers.JSONField()
    design_status = serializers.CharField()
    automation_status = serializers.CharField()
    jira_issue_key = serializers.CharField(allow_null=True)
    on_failure = serializers.CharField()
    timeout_ms = serializers.IntegerField()
    version = serializers.IntegerField()
    current_revision_id = serializers.UUIDField(allow_null=True)
    linked_specifications = LinkedSpecificationSummarySerializer(many=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class RepositoryLatestExecutionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    started_at = serializers.DateTimeField(allow_null=True)
    ended_at = serializers.DateTimeField(allow_null=True)
    duration_ms = serializers.IntegerField(allow_null=True)
    browser = serializers.CharField()
    platform = serializers.CharField()
    framework = serializers.CharField(allow_null=True)
    artifact_count = serializers.IntegerField()


class TestCaseAutomationSerializer(serializers.Serializer):
    has_active_script = serializers.BooleanField()
    active_script_count = serializers.IntegerField()
    runnable_frameworks = serializers.ListField(child=serializers.CharField())
    latest_execution = RepositoryLatestExecutionSerializer(allow_null=True)
    artifact_count = serializers.IntegerField()
    last_artifact_at = serializers.DateTimeField(allow_null=True)


class RepositoryVersionHistorySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    version_number = serializers.IntegerField()
    created_by = serializers.IntegerField(allow_null=True)
    created_by_name = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


class RepositoryRecentResultSerializer(serializers.Serializer):
    execution_id = serializers.UUIDField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    duration_ms = serializers.IntegerField()


class TestCaseHistorySerializer(serializers.Serializer):
    version_history = RepositoryVersionHistorySerializer(many=True)
    recent_results = RepositoryRecentResultSerializer(many=True)


class TestCaseWorkspaceSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    context = RepositoryContextSerializer()
    design = TestCaseDesignSerializer()
    automation = TestCaseAutomationSerializer()
    history = TestCaseHistorySerializer()
