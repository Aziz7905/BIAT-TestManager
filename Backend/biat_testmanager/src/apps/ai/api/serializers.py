from __future__ import annotations

from rest_framework import serializers

from apps.ai.models import (
    AIGenerationRetrievedContext,
    AIGenerationSession,
    AIGenerationSessionStatus,
    AIGenerationSourceType,
)
from apps.projects.access import get_project_queryset_for_actor
from apps.projects.models import Project
from apps.specs.models import Specification
from apps.specs.services.access import get_specification_queryset_for_actor
from apps.automation.models import ExecutionBrowser, ExecutionPlatform
from apps.testing.models import TestCase, TestSection, TestSuite
from apps.testing.services.access import can_manage_test_design_for_project
from apps.automation.services.access import can_trigger_test_execution


class AIGenerationRetrievedContextSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIGenerationRetrievedContext
        fields = [
            "id",
            "context_type",
            "object_id",
            "external_ref",
            "score",
            "metadata_json",
            "created_at",
        ]


class AIGenerationSessionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    retrieved_contexts = AIGenerationRetrievedContextSerializer(many=True, read_only=True)

    class Meta:
        model = AIGenerationSession
        fields = [
            "id",
            "team",
            "project",
            "created_by",
            "created_by_name",
            "target_suite",
            "target_section",
            "attached_specification",
            "status",
            "source_type",
            "objective",
            "source_refs",
            "jira_issue_key",
            "provider_name",
            "model_name",
            "purpose",
            "prompt_version",
            "schema_version",
            "draft_payload",
            "critic_report",
            "review_decisions",
            "saved_object_ids",
            "input_tokens",
            "output_tokens",
            "duration_ms",
            "error_message",
            "mlflow_run_id",
            "trace_id",
            "retrieved_contexts",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        full_name = obj.created_by.get_full_name().strip()
        return full_name or obj.created_by.email or obj.created_by.username


class AIGenerationSessionStartSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.select_related("team", "team__organization").all()
    )
    objective = serializers.CharField(trim_whitespace=True)
    source_type = serializers.ChoiceField(
        choices=AIGenerationSourceType.choices,
        required=False,
        default=AIGenerationSourceType.PROMPT,
    )
    target_suite = serializers.PrimaryKeyRelatedField(
        queryset=TestSuite.objects.select_related("project").all(),
        required=False,
        allow_null=True,
    )
    target_section = serializers.PrimaryKeyRelatedField(
        queryset=TestSection.objects.select_related("suite", "suite__project").all(),
        required=False,
        allow_null=True,
    )
    attached_specification = serializers.PrimaryKeyRelatedField(
        queryset=Specification.objects.select_related("project").all(),
        required=False,
        allow_null=True,
    )
    source_refs = serializers.JSONField(required=False, default=dict)
    jira_issue_key = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        project = attrs["project"]
        target_suite = attrs.get("target_suite")
        target_section = attrs.get("target_section")
        attached_specification = attrs.get("attached_specification")

        if not get_project_queryset_for_actor(request.user).filter(pk=project.pk).exists():
            raise serializers.ValidationError(
                {"project": "You do not have access to this project."}
            )
        if not can_manage_test_design_for_project(request.user, project):
            raise serializers.ValidationError(
                {"project": "You do not have permission to generate tests for this project."}
            )
        if target_suite is not None and target_suite.project_id != project.id:
            raise serializers.ValidationError(
                {"target_suite": "Target suite must belong to the selected project."}
            )
        if target_section is not None and target_section.suite.project_id != project.id:
            raise serializers.ValidationError(
                {"target_section": "Target section must belong to the selected project."}
            )
        if (
            target_suite is not None
            and target_section is not None
            and target_section.suite_id != target_suite.id
        ):
            raise serializers.ValidationError(
                {"target_section": "Target section must belong to the target suite."}
            )
        if attached_specification is not None:
            if attached_specification.project_id != project.id:
                raise serializers.ValidationError(
                    {
                        "attached_specification": (
                            "Attached specification must belong to the selected project."
                        )
                    }
                )
            if not get_specification_queryset_for_actor(request.user).filter(
                pk=attached_specification.pk
            ).exists():
                raise serializers.ValidationError(
                    {
                        "attached_specification": (
                            "You do not have access to this specification."
                        )
                    }
                )

        return attrs


class AIGenerationReviewSerializer(serializers.Serializer):
    review_decisions = serializers.JSONField()

    def validate_review_decisions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Review decisions must be a JSON object.")
        return value


class AIGenerationCommitSerializer(serializers.Serializer):
    create_as_approved = serializers.BooleanField(required=False, default=False)


class AIGenerationStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=AIGenerationSessionStatus.choices)


class AIAuthoringSessionStartSerializer(serializers.Serializer):
    test_case = serializers.PrimaryKeyRelatedField(
        queryset=TestCase.objects.select_related(
            "scenario",
            "scenario__section",
            "scenario__section__suite",
            "scenario__section__suite__project",
            "scenario__section__suite__project__team",
        ).all()
    )
    target_url = serializers.URLField()
    max_steps = serializers.IntegerField(required=False, min_value=2, max_value=12, default=12)
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
                {"test_case": "You do not have permission to author this test case."}
            )
        if attrs.get("browser") not in {ExecutionBrowser.CHROMIUM, ExecutionBrowser.CHROME}:
            raise serializers.ValidationError(
                {
                    "browser": (
                        "Playwright MCP authoring currently supports chromium/chrome. "
                        "Configure AI_PLAYWRIGHT_MCP_ARGS for other browser launch profiles later."
                    )
                }
            )
        return attrs
