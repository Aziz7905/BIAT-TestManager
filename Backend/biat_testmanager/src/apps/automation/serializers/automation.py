from rest_framework import serializers

from apps.automation.models import (
    AutomationScript,
    AutomationScriptGeneratedBy,
    ExecutionBrowser,
    ExecutionPlatform,
    ExecutionSchedule,
    ExecutionStep,
    ExecutionTriggerType,
    TestExecution,
    TestResult,
)
from apps.automation.services import (
    can_manage_automation_for_project,
    can_manage_automation_script_record,
    can_manage_execution_schedule_record,
    can_manage_test_execution_record,
    can_trigger_test_execution,
    get_result_artifacts,
    validate_script_content,
)
from apps.testing.models import TestCase


class AutomationScriptSerializer(serializers.ModelSerializer):
    test_case_title = serializers.CharField(source="test_case.title", read_only=True)
    scenario_id = serializers.UUIDField(source="test_case.scenario.id", read_only=True)
    suite_id = serializers.UUIDField(
        source="test_case.scenario.suite.id",
        read_only=True,
    )
    project_id = serializers.UUIDField(
        source="test_case.scenario.suite.project.id",
        read_only=True,
    )

    class Meta:
        model = AutomationScript
        fields = [
            "id",
            "test_case",
            "test_case_title",
            "scenario_id",
            "suite_id",
            "project_id",
            "framework",
            "language",
            "script_content",
            "script_version",
            "generated_by",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "script_version",
            "created_at",
        ]


class AutomationScriptDetailSerializer(AutomationScriptSerializer):
    validation = serializers.SerializerMethodField()
    history_versions = serializers.SerializerMethodField()
    diff_with_previous = serializers.SerializerMethodField()

    class Meta(AutomationScriptSerializer.Meta):
        fields = AutomationScriptSerializer.Meta.fields + [
            "validation",
            "history_versions",
            "diff_with_previous",
        ]

    def get_validation(self, obj):
        return obj.validate_syntax()

    def get_history_versions(self, obj):
        return [script.script_version for script in obj.get_history()]

    def get_diff_with_previous(self, obj):
        return obj.diff_with_previous()


class AutomationScriptWriteSerializer(serializers.ModelSerializer):
    generated_by = serializers.ChoiceField(
        choices=AutomationScriptGeneratedBy.choices,
        required=False,
    )

    class Meta:
        model = AutomationScript
        fields = [
            "test_case",
            "framework",
            "language",
            "script_content",
            "generated_by",
            "is_active",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        test_case = attrs.get("test_case", getattr(self.instance, "test_case", None))
        if test_case is None:
            raise serializers.ValidationError({"test_case": "Test case is required."})

        if self.instance is None and not can_trigger_test_execution(request.user, test_case):
            raise serializers.ValidationError(
                {"test_case": "You do not have permission to add scripts to this test case."}
            )

        if self.instance is not None and not can_manage_automation_script_record(
            request.user,
            self.instance,
        ):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this automation script."}
            )

        if (
            self.instance is not None
            and attrs.get("test_case") is not None
            and attrs["test_case"].id != self.instance.test_case_id
            and not can_trigger_test_execution(request.user, attrs["test_case"])
        ):
            raise serializers.ValidationError(
                {"test_case": "You do not have permission to move this script to the selected test case."}
            )

        validation_result = validate_script_content(
            framework=attrs.get("framework", getattr(self.instance, "framework", "")),
            language=attrs.get("language", getattr(self.instance, "language", "")),
            script_content=attrs.get(
                "script_content",
                getattr(self.instance, "script_content", ""),
            ),
        )
        if not validation_result["is_valid"]:
            raise serializers.ValidationError(
                {"script_content": validation_result["errors"]}
            )

        return attrs


class ExecutionStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutionStep
        fields = [
            "id",
            "execution",
            "step_index",
            "action",
            "target_element",
            "selector_used",
            "input_value",
            "screenshot_url",
            "status",
            "error_message",
            "stack_trace",
            "duration_ms",
            "executed_at",
        ]


class TestResultSerializer(serializers.ModelSerializer):
    artifacts = serializers.SerializerMethodField()

    class Meta:
        model = TestResult
        fields = [
            "id",
            "execution",
            "status",
            "duration_ms",
            "total_steps",
            "passed_steps",
            "failed_steps",
            "error_message",
            "stack_trace",
            "junit_xml",
            "video_url",
            "artifacts_path",
            "artifacts",
            "ai_failure_analysis",
            "issues_count",
            "created_at",
        ]

    def get_artifacts(self, obj):
        return get_result_artifacts(obj)


class TestExecutionSerializer(serializers.ModelSerializer):
    test_case_title = serializers.CharField(source="test_case.title", read_only=True)
    scenario_id = serializers.UUIDField(source="test_case.scenario.id", read_only=True)
    suite_id = serializers.UUIDField(
        source="test_case.scenario.suite.id",
        read_only=True,
    )
    project_id = serializers.UUIDField(
        source="test_case.scenario.suite.project.id",
        read_only=True,
    )
    triggered_by_name = serializers.SerializerMethodField()
    result = TestResultSerializer(read_only=True)
    duration_ms = serializers.SerializerMethodField()

    class Meta:
        model = TestExecution
        fields = [
            "id",
            "test_case",
            "test_case_title",
            "scenario_id",
            "suite_id",
            "project_id",
            "script",
            "triggered_by",
            "triggered_by_name",
            "trigger_type",
            "status",
            "browser",
            "platform",
            "started_at",
            "ended_at",
            "duration_ms",
            "celery_task_id",
            "pause_requested",
            "agent_run",
            "result",
        ]
        read_only_fields = [
            "status",
            "started_at",
            "ended_at",
            "duration_ms",
            "celery_task_id",
            "pause_requested",
            "result",
        ]

    def get_triggered_by_name(self, obj):
        if not obj.triggered_by:
            return None
        full_name = obj.triggered_by.get_full_name().strip()
        return full_name or obj.triggered_by.email or obj.triggered_by.username

    def get_duration_ms(self, obj):
        return obj.get_duration_ms()


class TestExecutionCreateSerializer(serializers.ModelSerializer):
    test_case = serializers.PrimaryKeyRelatedField(
        queryset=TestCase.objects.select_related("scenario", "scenario__suite", "scenario__suite__project").all()
    )
    script = serializers.PrimaryKeyRelatedField(
        queryset=AutomationScript.objects.select_related("test_case").all(),
        required=False,
        allow_null=True,
    )
    trigger_type = serializers.ChoiceField(
        choices=ExecutionTriggerType.choices,
        required=False,
    )
    browser = serializers.ChoiceField(choices=ExecutionBrowser.choices, required=False)
    platform = serializers.ChoiceField(choices=ExecutionPlatform.choices, required=False)

    class Meta:
        model = TestExecution
        fields = [
            "test_case",
            "script",
            "trigger_type",
            "browser",
            "platform",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        test_case = attrs["test_case"]
        script = attrs.get("script")

        if not can_trigger_test_execution(request.user, test_case):
            raise serializers.ValidationError(
                {"test_case": "You do not have permission to execute this test case."}
            )

        if script is not None and script.test_case_id != test_case.id:
            raise serializers.ValidationError(
                {"script": "The selected script must belong to the selected test case."}
            )

        return attrs


class ExecutionScheduleSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    suite_name = serializers.CharField(source="suite.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionSchedule
        fields = [
            "id",
            "project",
            "project_name",
            "suite",
            "suite_name",
            "name",
            "cron_expression",
            "timezone",
            "browser",
            "platform",
            "is_active",
            "next_run_at",
            "created_by",
            "created_by_name",
        ]
        read_only_fields = ["next_run_at", "created_by", "created_by_name"]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username

    def validate(self, attrs):
        request = self.context["request"]
        project = attrs.get("project", getattr(self.instance, "project", None))
        suite = attrs.get("suite", getattr(self.instance, "suite", None))

        if project is None:
            raise serializers.ValidationError({"project": "Project is required."})

        if self.instance is None and not can_manage_automation_for_project(
            request.user,
            project,
        ):
            raise serializers.ValidationError(
                {"project": "You do not have permission to manage schedules for this project."}
            )

        if self.instance is not None and not can_manage_execution_schedule_record(
            request.user,
            self.instance,
        ):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this schedule."}
            )

        if suite is not None and suite.project_id != project.id:
            raise serializers.ValidationError(
                {"suite": "The selected suite must belong to the selected project."}
            )

        return attrs
