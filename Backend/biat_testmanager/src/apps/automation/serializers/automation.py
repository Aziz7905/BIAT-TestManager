from rest_framework import serializers

from apps.automation.models import (
    AutomationScript,
    AutomationScriptGeneratedBy,
    ExecutionCheckpoint,
    ExecutionBrowser,
    ExecutionEnvironment,
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
from apps.testing.models import TestCase, TestCaseRevision


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
            "test_case_revision",
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
    test_case_revision = serializers.PrimaryKeyRelatedField(
        queryset=TestCaseRevision.objects.select_related("test_case").all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = AutomationScript
        fields = [
            "test_case",
            "test_case_revision",
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

        test_case_revision = attrs.get(
            "test_case_revision",
            getattr(self.instance, "test_case_revision", None),
        )
        if test_case_revision is not None and test_case_revision.test_case_id != test_case.id:
            raise serializers.ValidationError(
                {"test_case_revision": "The selected revision must belong to the selected test case."}
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


class ExecutionCheckpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExecutionCheckpoint
        fields = [
            "id",
            "execution",
            "step",
            "checkpoint_key",
            "title",
            "instructions",
            "payload_json",
            "status",
            "requested_at",
            "resolved_at",
            "resolved_by",
        ]
        read_only_fields = fields


class ExecutionStreamTicketSerializer(serializers.Serializer):
    ticket = serializers.CharField()
    expires_in = serializers.IntegerField()
    websocket_path = serializers.CharField()
    browser_websocket_path = serializers.CharField()
    browser_view_url = serializers.CharField(required=False, allow_blank=True)
    browser_view_urls = serializers.ListField(
        child=serializers.CharField(),
        required=False,
    )


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
    has_browser_session = serializers.SerializerMethodField()

    class Meta:
        model = TestExecution
        fields = [
            "id",
            "test_case",
            "test_case_title",
            "scenario_id",
            "suite_id",
            "project_id",
            "run_case",
            "script",
            "environment",
            "attempt_number",
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
            "has_browser_session",
            "result",
        ]
        read_only_fields = [
            "run_case",
            "environment",
            "attempt_number",
            "status",
            "started_at",
            "ended_at",
            "duration_ms",
            "celery_task_id",
            "pause_requested",
            "has_browser_session",
            "result",
        ]

    def get_triggered_by_name(self, obj):
        if not obj.triggered_by:
            return None
        full_name = obj.triggered_by.get_full_name().strip()
        return full_name or obj.triggered_by.email or obj.triggered_by.username

    def get_duration_ms(self, obj):
        return obj.get_duration_ms()

    def get_has_browser_session(self, obj):
        return bool(obj.selenium_session_id)


class TestExecutionCreateSerializer(serializers.ModelSerializer):
    test_case = serializers.PrimaryKeyRelatedField(
        queryset=TestCase.objects.select_related(
            "scenario",
            "scenario__section",
            "scenario__section__suite",
            "scenario__section__suite__project",
        ).all()
    )
    script = serializers.PrimaryKeyRelatedField(
        queryset=AutomationScript.objects.select_related("test_case").all(),
        required=False,
        allow_null=True,
    )
    environment = serializers.PrimaryKeyRelatedField(
        queryset=ExecutionEnvironment.objects.select_related("team").all(),
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
            "environment",
            "trigger_type",
            "browser",
            "platform",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        test_case = attrs["test_case"]
        script = attrs.get("script")
        environment = attrs.get("environment")

        if not can_trigger_test_execution(request.user, test_case):
            raise serializers.ValidationError(
                {"test_case": "You do not have permission to execute this test case."}
            )

        if script is not None and script.test_case_id != test_case.id:
            raise serializers.ValidationError(
                {"script": "The selected script must belong to the selected test case."}
            )

        attrs.setdefault("trigger_type", ExecutionTriggerType.MANUAL)

        if environment is not None:
            attrs.setdefault("browser", environment.browser)
            attrs.setdefault("platform", environment.platform)
            if not environment.is_active:
                raise serializers.ValidationError(
                    {"environment": "The selected execution environment is inactive."}
                )
            if environment.team_id != test_case.scenario.section.suite.project.team_id:
                raise serializers.ValidationError(
                    {"environment": "The selected environment must belong to the test case team."}
                )
            if script is not None and environment.engine != script.framework:
                raise serializers.ValidationError(
                    {"environment": "The selected environment engine must match the script framework."}
                )
            if attrs["browser"] != environment.browser:
                raise serializers.ValidationError(
                    {"browser": "The selected browser must match the execution environment."}
                )
            if attrs["platform"] != environment.platform:
                raise serializers.ValidationError(
                    {"platform": "The selected platform must match the execution environment."}
                )
        else:
            attrs.setdefault("browser", ExecutionBrowser.CHROMIUM)
            attrs.setdefault("platform", ExecutionPlatform.DESKTOP)

        return attrs


class ManualBrowserExecutionCreateSerializer(serializers.Serializer):
    test_case = serializers.PrimaryKeyRelatedField(
        queryset=TestCase.objects.select_related(
            "scenario",
            "scenario__section",
            "scenario__section__suite",
            "scenario__section__suite__project",
        ).all()
    )
    target_url = serializers.URLField(required=False, allow_blank=True)
    browser = serializers.ChoiceField(
        choices=ExecutionBrowser.choices,
        required=False,
        default=ExecutionBrowser.CHROMIUM,
    )
    platform = serializers.ChoiceField(
        choices=ExecutionPlatform.choices,
        required=False,
        default=ExecutionPlatform.DESKTOP,
    )

    def validate(self, attrs):
        request = self.context["request"]
        test_case = attrs["test_case"]
        if not can_trigger_test_execution(request.user, test_case):
            raise serializers.ValidationError(
                {"test_case": "You do not have permission to execute this test case."}
            )
        return attrs


class ScheduleTriggerResponseSerializer(serializers.Serializer):
    """
    Lightweight read-only shape returned when a schedule is triggered manually.
    The schedule now produces a TestRun + TestRunCase records; executions are
    dispatched later when workers pick up run-cases.
    """
    run_id = serializers.UUIDField(source="id")
    name = serializers.CharField()
    status = serializers.CharField()
    trigger_type = serializers.CharField()
    project = serializers.UUIDField(source="project_id")
    run_case_count = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_run_case_count(self, obj):
        return obj.run_cases.count()


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
