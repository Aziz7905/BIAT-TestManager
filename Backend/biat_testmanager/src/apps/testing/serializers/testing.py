from rest_framework import serializers

from apps.projects.models import Project
from apps.specs.models import Specification
from apps.testing.models import (
    BusinessPriority,
    TestCase,
    TestCaseAutomationStatus,
    TestCaseOnFailureBehavior,
    TestCaseStatus,
    TestPriority,
    TestScenario,
    TestScenarioPolarity,
    TestScenarioType,
    TestSuite,
)
from apps.testing.models.utils import calculate_pass_rate
from apps.testing.services import (
    can_create_test_case,
    can_create_test_scenario,
    can_create_test_suite,
    can_manage_test_case_record,
    can_manage_test_scenario_record,
    can_manage_test_suite_record,
)


class LinkedSpecificationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specification
        fields = ["id", "title", "external_reference", "source_type"]


class LinkedTestCasePreviewSerializer(serializers.ModelSerializer):
    scenario_id = serializers.UUIDField(source="scenario.id", read_only=True)
    scenario_title = serializers.CharField(source="scenario.title", read_only=True)
    suite_id = serializers.UUIDField(source="scenario.suite.id", read_only=True)
    suite_name = serializers.CharField(source="scenario.suite.name", read_only=True)

    class Meta:
        model = TestCase
        fields = [
            "id",
            "title",
            "status",
            "automation_status",
            "version",
            "scenario_id",
            "scenario_title",
            "suite_id",
            "suite_name",
        ]


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


class TestSuiteSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.select_related("team", "team__organization").all()
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    specification = serializers.PrimaryKeyRelatedField(
        queryset=Specification.objects.select_related("project").all(),
        required=False,
        allow_null=True,
    )
    specification_title = serializers.CharField(source="specification.title", read_only=True)
    created_by = serializers.IntegerField(source="created_by.id", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    scenario_count = serializers.SerializerMethodField()
    total_case_count = serializers.SerializerMethodField()
    pass_rate = serializers.SerializerMethodField()
    linked_specification_count = serializers.SerializerMethodField()
    linked_specifications = serializers.SerializerMethodField()

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
            "scenario_count",
            "total_case_count",
            "pass_rate",
            "linked_specification_count",
            "linked_specifications",
            "created_at",
        ]
        read_only_fields = [
            "created_by",
            "created_by_name",
            "scenario_count",
            "total_case_count",
            "pass_rate",
            "linked_specification_count",
            "linked_specifications",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username

    def get_scenario_count(self, obj):
        return _get_annotated_value(obj, "scenario_count", obj.scenarios.count())

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
        scenarios = list(obj.scenarios.all())
        cases = [test_case for scenario in scenarios for test_case in scenario.cases.all()]
        return _get_linked_specifications_from_cases(cases)

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
        return TestSuite.objects.create(
            created_by=self.context["request"].user,
            **validated_data,
        )


class TestScenarioSerializer(serializers.ModelSerializer):
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

    def validate(self, attrs):
        request = self.context["request"]
        suite = self.context["suite"]

        if self.instance is None:
            if not can_create_test_scenario(request.user, suite):
                raise serializers.ValidationError(
                    {"detail": "You do not have permission to create scenarios in this suite."}
                )
        elif not can_manage_test_scenario_record(request.user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this scenario."}
            )

        return attrs

    def create(self, validated_data):
        return TestScenario.objects.create(
            suite=self.context["suite"],
            **validated_data,
        )


class TestCaseSerializer(serializers.ModelSerializer):
    scenario_id = serializers.UUIDField(source="scenario.id", read_only=True)
    scenario_title = serializers.CharField(source="scenario.title", read_only=True)
    suite_id = serializers.UUIDField(source="scenario.suite.id", read_only=True)
    suite_name = serializers.CharField(source="scenario.suite.name", read_only=True)
    project_id = serializers.UUIDField(source="scenario.suite.project.id", read_only=True)
    latest_result_status = serializers.SerializerMethodField()
    gherkin_preview = serializers.SerializerMethodField()
    version_history = serializers.SerializerMethodField()
    linked_specifications = LinkedSpecificationSummarySerializer(many=True, read_only=True)
    linked_specification_ids = serializers.SerializerMethodField()

    class Meta:
        model = TestCase
        fields = [
            "id",
            "scenario_id",
            "scenario_title",
            "suite_id",
            "suite_name",
            "project_id",
            "title",
            "preconditions",
            "steps",
            "expected_result",
            "test_data",
            "status",
            "automation_status",
            "ai_generated",
            "jira_issue_key",
            "version",
            "on_failure",
            "timeout_ms",
            "order_index",
            "linked_specifications",
            "linked_specification_ids",
            "latest_result_status",
            "gherkin_preview",
            "version_history",
            "created_at",
            "updated_at",
        ]

    def get_latest_result_status(self, obj):
        latest_result = obj.get_latest_result()
        return getattr(latest_result, "status", None)

    def get_gherkin_preview(self, obj):
        return obj.to_gherkin()

    def get_version_history(self, obj):
        return obj.get_version_history()

    def get_linked_specification_ids(self, obj):
        return [str(specification.id) for specification in obj.linked_specifications.all()]


class TestCaseWriteSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=TestCaseStatus.choices)
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
        test_case = TestCase.objects.create(
            scenario=self.context["scenario"],
            **validated_data,
        )
        if linked_specifications:
            test_case.linked_specifications.set(linked_specifications)
        return test_case

    def update(self, instance, validated_data):
        linked_specifications = validated_data.pop("linked_specifications", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if linked_specifications is not None:
            instance.linked_specifications.set(linked_specifications)

        return instance
