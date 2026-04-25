from rest_framework import serializers

from apps.projects.models import Project
from apps.specs.models import Specification
from apps.testing.models import (
    BusinessPriority,
    TestCase,
    TestCaseAutomationStatus,
    TestCaseDesignStatus,
    TestCaseOnFailureBehavior,
    TestCaseRevision,
    TestPriority,
    TestScenario,
    TestScenarioPolarity,
    TestScenarioType,
    TestSection,
    TestSuite,
)
from apps.testing.models.choices import (
    LEGACY_TEST_CASE_STATUS_TO_DESIGN_STATUS,
    map_legacy_test_case_status_to_design_status,
)
from apps.testing.models.utils import calculate_pass_rate
from apps.testing.services import (
    UNSET,
    can_create_test_case,
    can_create_test_scenario,
    can_create_test_section,
    can_create_test_suite,
    can_manage_test_case_record,
    can_manage_test_scenario_record,
    can_manage_test_section_record,
    can_manage_test_suite_record,
    create_test_case_with_revision,
    create_test_scenario,
    create_test_section,
    create_test_suite,
    get_or_create_default_section,
    update_test_case_with_revision,
)


class LinkedSpecificationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        fields = ["id", "title", "external_reference", "source_type"]


def _get_annotated_value(obj, field_name, fallback):
    value = getattr(obj, field_name, None)
    if value is None:
        return fallback
    return value


def _get_linked_specifications_from_cases(cases):
    unique_specifications: dict[str, Specification] = {}
    for test_case in cases:
        for specification in test_case.linked_specifications.all():
            unique_specifications[str(specification.id)] = specification

    ordered_specifications = sorted(
        unique_specifications.values(),
        key=lambda specification: (
            specification.external_reference or "",
            specification.title,
        ),
    )
    return LinkedSpecificationSummarySerializer(ordered_specifications, many=True).data


def _get_section_queryset(suite):
    prefetched_sections = getattr(suite, "_prefetched_objects_cache", {}).get("sections")
    if prefetched_sections is not None:
        return list(prefetched_sections)
    return list(suite.sections.all().order_by("order_index", "name"))


class TestCaseRevisionSummarySerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseRevision
        fields = [
            "id",
            "version_number",
            "created_by",
            "created_by_name",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username


class TestCaseRevisionSerializer(serializers.ModelSerializer):
    linked_specifications = LinkedSpecificationSummarySerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TestCaseRevision
        fields = [
            "id",
            "test_case",
            "version_number",
            "title",
            "preconditions",
            "steps",
            "expected_result",
            "test_data",
            "source_snapshot_json",
            "linked_specifications",
            "created_by",
            "created_by_name",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username


class LinkedTestCasePreviewSerializer(serializers.ModelSerializer):
    scenario_id = serializers.UUIDField(source="scenario.id", read_only=True)
    scenario_title = serializers.CharField(source="scenario.title", read_only=True)
    section_id = serializers.UUIDField(source="scenario.section.id", read_only=True)
    section_name = serializers.CharField(source="scenario.section.name", read_only=True)
    suite_id = serializers.UUIDField(source="scenario.suite.id", read_only=True)
    suite_name = serializers.CharField(source="scenario.suite.name", read_only=True)
    design_status = serializers.CharField(read_only=True)
    status = serializers.CharField(source="design_status", read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "title",
            "design_status",
            "status",
            "automation_status",
            "version",
            "scenario_id",
            "scenario_title",
            "section_id",
            "section_name",
            "suite_id",
            "suite_name",
        ]


class TestCaseSummarySerializer(serializers.ModelSerializer):
    scenario_id = serializers.UUIDField(source="scenario.id", read_only=True)
    scenario_title = serializers.CharField(source="scenario.title", read_only=True)
    section_id = serializers.UUIDField(source="scenario.section.id", read_only=True)
    section_name = serializers.CharField(source="scenario.section.name", read_only=True)
    suite_id = serializers.UUIDField(source="scenario.suite.id", read_only=True)
    suite_name = serializers.CharField(source="scenario.suite.name", read_only=True)
    project_id = serializers.UUIDField(source="scenario.suite.project.id", read_only=True)
    current_revision_id = serializers.SerializerMethodField()
    design_status = serializers.CharField(read_only=True)
    status = serializers.CharField(source="design_status", read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "scenario_id",
            "scenario_title",
            "section_id",
            "section_name",
            "suite_id",
            "suite_name",
            "project_id",
            "title",
            "design_status",
            "status",
            "automation_status",
            "version",
            "current_revision_id",
            "on_failure",
            "timeout_ms",
            "order_index",
            "created_at",
            "updated_at",
        ]

    def get_current_revision_id(self, obj):
        prefetched_revisions = getattr(obj, "_prefetched_objects_cache", {}).get("revisions")
        if prefetched_revisions:
            return str(prefetched_revisions[0].id) if prefetched_revisions else None
        latest = obj.revisions.order_by("-version_number", "-created_at").first()
        return str(latest.id) if latest else None


class TestCaseSerializer(serializers.ModelSerializer):
    scenario_id = serializers.UUIDField(source="scenario.id", read_only=True)
    scenario_title = serializers.CharField(source="scenario.title", read_only=True)
    section_id = serializers.UUIDField(source="scenario.section.id", read_only=True)
    section_name = serializers.CharField(source="scenario.section.name", read_only=True)
    suite_id = serializers.UUIDField(source="scenario.suite.id", read_only=True)
    suite_name = serializers.CharField(source="scenario.suite.name", read_only=True)
    project_id = serializers.UUIDField(source="scenario.suite.project.id", read_only=True)
    current_revision_id = serializers.SerializerMethodField()
    latest_result_status = serializers.SerializerMethodField()
    version_history = serializers.SerializerMethodField()
    linked_specifications = LinkedSpecificationSummarySerializer(many=True, read_only=True)
    linked_specification_ids = serializers.SerializerMethodField()
    design_status = serializers.CharField(read_only=True)
    status = serializers.CharField(source="design_status", read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "scenario_id",
            "scenario_title",
            "section_id",
            "section_name",
            "suite_id",
            "suite_name",
            "project_id",
            "title",
            "preconditions",
            "steps",
            "expected_result",
            "test_data",
            "design_status",
            "status",
            "automation_status",
            "ai_generated",
            "jira_issue_key",
            "version",
            "current_revision_id",
            "on_failure",
            "timeout_ms",
            "order_index",
            "linked_specifications",
            "linked_specification_ids",
            "latest_result_status",
            "version_history",
            "created_at",
            "updated_at",
        ]

    def _get_latest_revision(self, obj):
        prefetched_revisions = getattr(obj, "_prefetched_objects_cache", {}).get("revisions")
        if prefetched_revisions:
            return prefetched_revisions[0]
        return obj.revisions.order_by("-version_number", "-created_at").first()

    def get_current_revision_id(self, obj):
        latest_revision = self._get_latest_revision(obj)
        return str(latest_revision.id) if latest_revision else None

    def get_latest_result_status(self, obj):
        latest_result = obj.get_latest_result()
        return getattr(latest_result, "status", None)

    def get_version_history(self, obj):
        revisions = getattr(obj, "_prefetched_objects_cache", {}).get("revisions")
        if revisions is not None:
            return TestCaseRevisionSummarySerializer(revisions, many=True).data
        return obj.get_version_history()

    def get_linked_specification_ids(self, obj):
        return [str(specification.id) for specification in obj.linked_specifications.all()]


class TestCaseWriteSerializer(serializers.ModelSerializer):
    design_status = serializers.ChoiceField(
        choices=TestCaseDesignStatus.choices,
        required=False,
    )
    status = serializers.CharField(required=False, write_only=True)
    automation_status = serializers.ChoiceField(choices=TestCaseAutomationStatus.choices)
    on_failure = serializers.ChoiceField(choices=TestCaseOnFailureBehavior.choices)
    linked_specification_ids = serializers.PrimaryKeyRelatedField(
        queryset=Specification.objects.select_related("project").all(),
        many=True,
        required=False,
        source="linked_specifications",
        write_only=True,
    )

    class Meta:
        model = TestCase
        fields = [
            "title",
            "preconditions",
            "steps",
            "expected_result",
            "test_data",
            "design_status",
            "status",
            "automation_status",
            "ai_generated",
            "jira_issue_key",
            "on_failure",
            "timeout_ms",
            "order_index",
            "linked_specification_ids",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        scenario = self.context["scenario"]
        linked_specifications = attrs.get("linked_specifications")
        legacy_status = attrs.pop("status", None)

        if legacy_status is not None:
            if legacy_status not in LEGACY_TEST_CASE_STATUS_TO_DESIGN_STATUS:
                raise serializers.ValidationError(
                    {"status": "Unknown test case design status."}
                )
            if "design_status" not in attrs:
                attrs["design_status"] = map_legacy_test_case_status_to_design_status(
                    legacy_status
                )

        if self.instance is None and "design_status" not in attrs:
            attrs["design_status"] = TestCaseDesignStatus.DRAFT

        if self.instance is None:
            if not can_create_test_case(request.user, scenario):
                raise serializers.ValidationError(
                    {"detail": "You do not have permission to create test cases in this scenario."}
                )
        elif not can_manage_test_case_record(request.user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this test case."}
            )

        if linked_specifications is not None:
            project_id = scenario.suite.project_id
            invalid_specification = next(
                (
                    specification
                    for specification in linked_specifications
                    if specification.project_id != project_id
                ),
                None,
            )
            if invalid_specification is not None:
                raise serializers.ValidationError(
                    {
                        "linked_specification_ids": (
                            "Every linked specification must belong to the same project "
                            "as the test case."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        linked_specifications = validated_data.pop("linked_specifications", [])
        return create_test_case_with_revision(
            scenario=self.context["scenario"],
            linked_specifications=list(linked_specifications),
            created_by=self.context["request"].user,
            source_snapshot_json={"mutation_source": "api_create"},
            **validated_data,
        )

    def update(self, instance, validated_data):
        linked_specifications = validated_data.pop("linked_specifications", None)
        return update_test_case_with_revision(
            instance,
            linked_specifications=linked_specifications if linked_specifications is not None else UNSET,
            created_by=self.context["request"].user,
            source_snapshot_json={"mutation_source": "api_update"},
            **validated_data,
        )


class TestSectionSerializer(serializers.ModelSerializer):
    suite_id = serializers.UUIDField(source="suite.id", read_only=True)
    suite_name = serializers.CharField(source="suite.name", read_only=True)
    project_id = serializers.UUIDField(source="suite.project.id", read_only=True)
    parent_id = serializers.UUIDField(source="parent.id", read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    scenario_count = serializers.SerializerMethodField()
    total_case_count = serializers.SerializerMethodField()
    linked_specification_count = serializers.SerializerMethodField()

    class Meta:
        model = TestSection
        fields = [
            "id",
            "suite_id",
            "suite_name",
            "project_id",
            "parent_id",
            "parent_name",
            "name",
            "order_index",
            "scenario_count",
            "total_case_count",
            "linked_specification_count",
            "created_at",
        ]

    def get_scenario_count(self, obj):
        return _get_annotated_value(obj, "scenario_count", obj.scenarios.count())

    def get_total_case_count(self, obj):
        return _get_annotated_value(obj, "total_case_count", obj.get_total_cases())

    def get_linked_specification_count(self, obj):
        fallback = len(
            _get_linked_specifications_from_cases(
                [test_case for scenario in obj.scenarios.all() for test_case in scenario.cases.all()]
            )
        )
        return _get_annotated_value(obj, "linked_specification_count", fallback)


class TestSectionWriteSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=TestSection.objects.select_related("suite").all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = TestSection
        fields = ["name", "parent", "order_index"]

    def validate(self, attrs):
        request = self.context["request"]
        suite = self.context["suite"]
        parent = attrs.get("parent", getattr(self.instance, "parent", None))

        if self.instance is None:
            if not can_create_test_section(request.user, suite):
                raise serializers.ValidationError(
                    {"detail": "You do not have permission to create sections in this suite."}
                )
        elif not can_manage_test_section_record(request.user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this section."}
            )

        if parent is not None and parent.suite_id != suite.id:
            raise serializers.ValidationError(
                {"parent": "Parent section must belong to the same suite."}
            )
        return attrs

    def create(self, validated_data):
        return create_test_section(
            self.context["suite"],
            name=validated_data["name"],
            parent=validated_data.get("parent"),
            order_index=validated_data.get("order_index", 0),
        )


class TestScenarioSerializer(serializers.ModelSerializer):
    section_id = serializers.UUIDField(source="section.id", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    suite_id = serializers.UUIDField(source="suite.id", read_only=True)
    suite_name = serializers.CharField(source="suite.name", read_only=True)
    project_id = serializers.UUIDField(source="suite.project.id", read_only=True)
    specification_id = serializers.UUIDField(source="suite.specification.id", read_only=True)
    case_count = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()
    linked_specification_count = serializers.SerializerMethodField()
    linked_specifications = serializers.SerializerMethodField()

    class Meta:
        model = TestScenario
        fields = [
            "id",
            "section_id",
            "section_name",
            "suite_id",
            "suite_name",
            "project_id",
            "specification_id",
            "title",
            "description",
            "scenario_type",
            "priority",
            "business_priority",
            "polarity",
            "ai_generated",
            "ai_confidence",
            "order_index",
            "case_count",
            "pass_rate",
            "linked_specification_count",
            "linked_specifications",
            "created_at",
        ]

    def get_case_count(self, obj):
        return _get_annotated_value(obj, "case_count", obj.cases.count())

    def get_pass_rate(self, obj):
        case_count = getattr(obj, "case_count", None)
        passed_case_count = getattr(obj, "passed_case_count", None)
        if case_count is not None and passed_case_count is not None:
            return calculate_pass_rate(
                total_count=case_count,
                passed_count=passed_case_count,
            )
        return obj.get_pass_rate()

    def get_linked_specification_count(self, obj):
        fallback = len(self.get_linked_specifications(obj))
        return _get_annotated_value(obj, "linked_specification_count", fallback)

    def get_linked_specifications(self, obj):
        return _get_linked_specifications_from_cases(obj.cases.all())


class TestScenarioWriteSerializer(serializers.ModelSerializer):
    scenario_type = serializers.ChoiceField(choices=TestScenarioType.choices)
    priority = serializers.ChoiceField(choices=TestPriority.choices)
    business_priority = serializers.ChoiceField(
        choices=BusinessPriority.choices,
        required=False,
        allow_null=True,
    )
    polarity = serializers.ChoiceField(choices=TestScenarioPolarity.choices)

    class Meta:
        model = TestScenario
        fields = [
            "title",
            "description",
            "scenario_type",
            "priority",
            "business_priority",
            "polarity",
            "ai_generated",
            "ai_confidence",
            "order_index",
        ]

    def _get_target_section(self):
        section = self.context.get("section")
        if section is not None:
            return section
        suite = self.context["suite"]
        return get_or_create_default_section(suite)

    def validate(self, attrs):
        request = self.context["request"]
        section = self._get_target_section()

        if self.instance is None:
            if not can_create_test_scenario(request.user, section):
                raise serializers.ValidationError(
                    {"detail": "You do not have permission to create scenarios in this section."}
                )
        elif not can_manage_test_scenario_record(request.user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this scenario."}
            )

        return attrs

    def create(self, validated_data):
        section = self._get_target_section()
        return create_test_scenario(section, **validated_data)


class TestSuiteWriteSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.select_related("team", "team__organization").all()
    )
    specification = serializers.PrimaryKeyRelatedField(
        queryset=Specification.objects.select_related("project").all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = TestSuite
        fields = ["project", "name", "description", "folder_path", "specification", "ai_generated"]

    def validate(self, attrs):
        request = self.context["request"]
        project = attrs.get("project") or getattr(self.instance, "project", None)
        specification = attrs.get("specification", getattr(self.instance, "specification", None))

        if project is None:
            raise serializers.ValidationError({"project": "Project is required."})

        if specification is not None and specification.project_id != project.id:
            raise serializers.ValidationError(
                {"specification": "Specification must belong to the selected project."}
            )

        if self.instance is None:
            if not can_create_test_suite(request.user, project):
                raise serializers.ValidationError(
                    {"project": "You do not have permission to create test suites for this project."}
                )
        elif not can_manage_test_suite_record(request.user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this test suite."}
            )

        return attrs

    def create(self, validated_data):
        return create_test_suite(
            validated_data.pop("project"),
            name=validated_data.pop("name"),
            created_by=self.context["request"].user,
            **validated_data,
        )

    def update(self, instance, validated_data):
        validated_data.pop("project", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TestSuiteSummarySerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    specification_title = serializers.CharField(source="specification.title", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    section_count = serializers.SerializerMethodField()
    scenario_count = serializers.SerializerMethodField()
    total_case_count = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()
    linked_specification_count = serializers.SerializerMethodField()

    class Meta:
        model = TestSuite
        fields = [
            "id",
            "project",
            "project_name",
            "specification",
            "specification_title",
            "name",
            "description",
            "folder_path",
            "ai_generated",
            "created_by",
            "created_by_name",
            "section_count",
            "scenario_count",
            "total_case_count",
            "pass_rate",
            "linked_specification_count",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username

    def get_section_count(self, obj):
        return _get_annotated_value(obj, "section_count", obj.sections.count())

    def get_scenario_count(self, obj):
        return _get_annotated_value(obj, "scenario_count", obj.get_scenarios().count())

    def get_total_case_count(self, obj):
        return _get_annotated_value(obj, "total_case_count", obj.get_total_cases())

    def get_pass_rate(self, obj):
        total_case_count = getattr(obj, "total_case_count", None)
        passed_case_count = getattr(obj, "passed_case_count", None)
        if total_case_count is not None and passed_case_count is not None:
            return calculate_pass_rate(
                total_count=total_case_count,
                passed_count=passed_case_count,
            )
        return obj.get_pass_rate()

    def get_linked_specification_count(self, obj):
        return _get_annotated_value(
            obj,
            "linked_specification_count",
            obj.sections.aggregate(
                total=__import__("django.db.models", fromlist=["Count"]).Count(
                    "scenarios__cases__linked_specifications", distinct=True
                )
            )["total"] or 0,
        )


class TestSuiteSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    specification = serializers.PrimaryKeyRelatedField(read_only=True)
    specification_title = serializers.CharField(source="specification.title", read_only=True)
    created_by = serializers.IntegerField(source="created_by.id", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    default_section_id = serializers.SerializerMethodField()
    section_count = serializers.SerializerMethodField()
    scenario_count = serializers.SerializerMethodField()
    total_case_count = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()
    linked_specification_count = serializers.SerializerMethodField()
    linked_specifications = serializers.SerializerMethodField()
    sections = TestSectionSerializer(many=True, read_only=True)

    class Meta:
        model = TestSuite
        fields = [
            "id",
            "project",
            "project_name",
            "specification",
            "specification_title",
            "name",
            "description",
            "folder_path",
            "ai_generated",
            "created_by",
            "created_by_name",
            "default_section_id",
            "section_count",
            "scenario_count",
            "total_case_count",
            "pass_rate",
            "linked_specification_count",
            "linked_specifications",
            "sections",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username

    def get_default_section_id(self, obj):
        default_section = next(
            (section for section in _get_section_queryset(obj) if section.parent_id is None),
            None,
        )
        return str(default_section.id) if default_section else None

    def get_section_count(self, obj):
        return _get_annotated_value(obj, "section_count", obj.sections.count())

    def get_scenario_count(self, obj):
        return _get_annotated_value(obj, "scenario_count", obj.get_scenarios().count())

    def get_total_case_count(self, obj):
        return _get_annotated_value(obj, "total_case_count", obj.get_total_cases())

    def get_pass_rate(self, obj):
        total_case_count = getattr(obj, "total_case_count", None)
        passed_case_count = getattr(obj, "passed_case_count", None)
        if total_case_count is not None and passed_case_count is not None:
            return calculate_pass_rate(
                total_count=total_case_count,
                passed_count=passed_case_count,
            )
        return obj.get_pass_rate()

    def get_linked_specification_count(self, obj):
        fallback = len(self.get_linked_specifications(obj))
        return _get_annotated_value(obj, "linked_specification_count", fallback)

    def get_linked_specifications(self, obj):
        sections = _get_section_queryset(obj)
        cases = [
            test_case
            for section in sections
            for scenario in section.scenarios.all()
            for test_case in scenario.cases.all()
        ]
        return _get_linked_specifications_from_cases(cases)
