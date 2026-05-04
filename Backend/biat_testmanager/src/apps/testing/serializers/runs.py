from rest_framework import serializers

from apps.projects.models import Project
from apps.testing.models import (
    TestCase,
    TestPlan,
    TestPlanStatus,
    TestRun,
    TestRunCase,
    TestRunCaseStatus,
    TestRunKind,
    TestRunStatus,
    TestRunTriggerType,
    TestSection,
    TestSuite,
)
from apps.testing.services.runs import (
    create_test_plan,
    create_test_run,
    expand_run_from_cases,
    expand_run_from_section,
    expand_run_from_suite,
)


# ---------------------------------------------------------------------------
# TestPlan
# ---------------------------------------------------------------------------

class TestPlanSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    run_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TestPlan
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "description",
            "status",
            "run_count",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "run_count",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name().strip() or obj.created_by.username

    def validate_project(self, project):
        from apps.testing.services.access import can_manage_test_design_for_project
        if not can_manage_test_design_for_project(self.context["request"].user, project):
            raise serializers.ValidationError(
                "You do not have permission to create plans for this project."
            )
        return project

    def create(self, validated_data):
        return create_test_plan(
            validated_data["project"],
            name=validated_data["name"],
            description=validated_data.get("description", ""),
            created_by=self.context["request"].user,
        )

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            if attr != "project":
                setattr(instance, attr, value)
        instance.save()
        return instance


# ---------------------------------------------------------------------------
# TestRun
# ---------------------------------------------------------------------------

class TestRunSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    run_case_count = serializers.IntegerField(read_only=True)
    passed_case_count = serializers.IntegerField(read_only=True)
    pass_rate = serializers.SerializerMethodField()

    class Meta:
        model = TestRun
        fields = [
            "id",
            "project",
            "project_name",
            "plan",
            "plan_name",
            "name",
            "status",
            "trigger_type",
            "run_kind",
            "run_case_count",
            "passed_case_count",
            "pass_rate",
            "created_by",
            "created_by_name",
            "created_at",
            "started_at",
            "ended_at",
        ]
        read_only_fields = [
            "id",
            "project_name",
            "plan_name",
            "run_kind",
            "run_case_count",
            "passed_case_count",
            "pass_rate",
            "created_by",
            "created_by_name",
            "created_at",
            "started_at",
            "ended_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name().strip() or obj.created_by.username

    def get_pass_rate(self, obj):
        passed = getattr(obj, "passed_case_count", None)
        total = getattr(obj, "run_case_count", None)
        if passed is None or total is None:
            return obj.get_pass_rate()
        from apps.testing.models.utils import calculate_pass_rate
        return calculate_pass_rate(total_count=total or 0, passed_count=passed or 0)

    def validate(self, attrs):
        request = self.context["request"]
        project = attrs.get("project") or getattr(self.instance, "project", None)
        from apps.testing.services.access import can_manage_test_design_for_project
        if project and not can_manage_test_design_for_project(request.user, project):
            raise serializers.ValidationError(
                {"project": "You do not have permission to create runs for this project."}
            )
        plan = attrs.get("plan")
        if plan and project and plan.project_id != project.id:
            raise serializers.ValidationError(
                {"plan": "Plan does not belong to the selected project."}
            )
        return attrs

    def create(self, validated_data):
        return create_test_run(
            validated_data["project"],
            name=validated_data["name"],
            created_by=self.context["request"].user,
            plan=validated_data.get("plan"),
            trigger_type=validated_data.get("trigger_type", TestRunTriggerType.MANUAL),
        )

    def update(self, instance, validated_data):
        allowed = {"name", "status"}
        for attr in allowed:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()
        return instance


# ---------------------------------------------------------------------------
# TestRun expand (POST action)
# ---------------------------------------------------------------------------

class TestRunExpandSerializer(serializers.Serializer):
    """
    Accepts one of: suite_id, section_id, or case_ids.
    Expands the run by creating TestRunCase records for all matching cases.
    """
    suite_id = serializers.UUIDField(required=False)
    section_id = serializers.UUIDField(required=False)
    case_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=False,
    )

    def validate(self, attrs):
        provided = [k for k in ("suite_id", "section_id", "case_ids") if attrs.get(k)]
        if len(provided) != 1:
            raise serializers.ValidationError(
                "Provide exactly one of: suite_id, section_id, or case_ids."
            )
        return attrs

    def expand(self, run: TestRun) -> list[TestRunCase]:
        base_index = run.run_cases.count()
        if suite_id := self.validated_data.get("suite_id"):
            suite = TestSuite.objects.get(pk=suite_id, project=run.project)
            return expand_run_from_suite(run, suite, base_order_index=base_index)
        if section_id := self.validated_data.get("section_id"):
            section = TestSection.objects.get(pk=section_id, suite__project=run.project)
            return expand_run_from_section(run, section, base_order_index=base_index)
        case_ids = self.validated_data["case_ids"]
        cases = list(
            TestCase.objects.filter(
                pk__in=case_ids,
                scenario__section__suite__project=run.project,
            ).order_by("scenario__order_index", "order_index")
        )
        return expand_run_from_cases(run, cases, base_order_index=base_index)


# ---------------------------------------------------------------------------
# TestRunCase
# ---------------------------------------------------------------------------

class TestRunCaseSerializer(serializers.ModelSerializer):
    run_name = serializers.CharField(source="run.name", read_only=True)
    test_case_title = serializers.CharField(source="test_case.title", read_only=True)
    test_case_automation_status = serializers.CharField(
        source="test_case.automation_status",
        read_only=True,
    )
    revision_version = serializers.IntegerField(
        source="test_case_revision.version_number",
        read_only=True,
    )
    assigned_to_name = serializers.SerializerMethodField()
    attempt_count = serializers.IntegerField(read_only=True)
    latest_execution = serializers.SerializerMethodField()

    class Meta:
        model = TestRunCase
        fields = [
            "id",
            "run",
            "run_name",
            "test_case",
            "test_case_title",
            "test_case_automation_status",
            "test_case_revision",
            "revision_version",
            "assigned_to",
            "assigned_to_name",
            "status",
            "order_index",
            "attempt_count",
            "latest_execution",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "run_name",
            "test_case_title",
            "test_case_automation_status",
            "revision_version",
            "assigned_to_name",
            "attempt_count",
            "latest_execution",
            "created_at",
            "updated_at",
        ]

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return None
        return obj.assigned_to.get_full_name().strip() or obj.assigned_to.username

    def get_latest_execution(self, obj):
        execution = (
            obj.executions.select_related("result", "triggered_by")
            .order_by("-attempt_number", "-started_at", "-id")
            .first()
        )
        if execution is None:
            return None

        result = getattr(execution, "result", None)
        triggered_by = execution.triggered_by
        triggered_by_name = None
        if triggered_by:
            triggered_by_name = (
                triggered_by.get_full_name().strip() or triggered_by.username
            )

        return {
            "id": str(execution.id),
            "status": execution.status,
            "browser": execution.browser,
            "attempt_number": execution.attempt_number,
            "started_at": execution.started_at,
            "ended_at": execution.ended_at,
            "duration_ms": execution.get_duration_ms(),
            "triggered_by_name": triggered_by_name,
            "has_browser_session": bool(execution.selenium_session_id),
            "result": {
                "status": result.status,
                "duration_ms": result.duration_ms,
                "total_steps": result.total_steps,
                "passed_steps": result.passed_steps,
                "failed_steps": result.failed_steps,
                "error_message": result.error_message or "",
            } if result else None,
        }

    def update(self, instance, validated_data):
        allowed = {"status", "assigned_to", "order_index"}
        for attr in allowed:
            if attr in validated_data:
                setattr(instance, attr, validated_data[attr])
        instance.save()
        return instance
