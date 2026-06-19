from __future__ import annotations

import json

from django.conf import settings
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


class UploadedFilesListField(serializers.ListField):
    """Accept repeated multipart file fields as a normal list of files."""

    def get_value(self, dictionary):
        request = self.root.context.get("request") if self.root else None
        uploaded_files = getattr(request, "FILES", None)
        if uploaded_files is not None:
            values = uploaded_files.getlist(self.field_name)
            if values:
                return values
        if hasattr(dictionary, "getlist"):
            values = dictionary.getlist(self.field_name)
            if values:
                return values
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        if isinstance(data, dict):
            data = list(data.values())
        elif data and not isinstance(data, (list, tuple)):
            data = [data]
        return super().to_internal_value(data)


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
    selected_specifications = serializers.PrimaryKeyRelatedField(
        queryset=Specification.objects.select_related("project").all(),
        required=False,
        many=True,
    )
    temporary_attachments = UploadedFilesListField(
        child=serializers.FileField(),
        required=False,
        write_only=True,
        allow_empty=True,
    )
    source_refs = serializers.JSONField(required=False, default=dict)
    jira_issue_key = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        project = attrs["project"]
        target_suite = attrs.get("target_suite")
        target_section = attrs.get("target_section")
        attached_specification = attrs.get("attached_specification")
        selected_specifications = attrs.get("selected_specifications") or []

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
        for specification in selected_specifications:
            if specification.project_id != project.id:
                raise serializers.ValidationError(
                    {
                        "selected_specifications": (
                            "Selected specifications must belong to the selected project."
                        )
                    }
                )
            if not get_specification_queryset_for_actor(request.user).filter(
                pk=specification.pk
            ).exists():
                raise serializers.ValidationError(
                    {
                        "selected_specifications": (
                            "You do not have access to one or more selected specifications."
                        )
                    }
                )

        return attrs

    def validate_source_refs(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("source_refs must be valid JSON.") from exc
        if not isinstance(value, dict):
            raise serializers.ValidationError("source_refs must be a JSON object.")
        return value


class AIGenerationReviewSerializer(serializers.Serializer):
    review_decisions = serializers.JSONField()

    def validate_review_decisions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Review decisions must be a JSON object.")
        return value


class AIGenerationClarifySerializer(serializers.Serializer):
    answers = serializers.CharField(trim_whitespace=True)


class AIGenerationRefineSerializer(serializers.Serializer):
    instruction = serializers.CharField(trim_whitespace=True)
    draft_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )


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
    # Per-session AI authoring knobs surfaced in the UI. Bounds come from
    # settings so the team manager (or env) can tighten/loosen without code
    # changes; serializer defaults fall back to the team default when omitted.
    max_steps = serializers.IntegerField(
        required=False,
        min_value=2,
        max_value=settings.AI_AUTHORING_MAX_STEPS_LIMIT,
        default=settings.AI_AUTHORING_DEFAULT_MAX_STEPS,
    )
    temperature = serializers.FloatField(
        required=False,
        min_value=0.0,
        max_value=1.0,
        default=settings.AI_AUTHORING_DEFAULT_TEMPERATURE,
    )
    max_tokens_per_step = serializers.IntegerField(
        required=False,
        min_value=50,
        max_value=settings.AI_AUTHORING_MAX_TOKENS_PER_STEP_LIMIT,
        default=settings.AI_AUTHORING_DEFAULT_MAX_TOKENS_PER_STEP,
    )
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
                        "AI browser authoring currently supports chromium/chrome. "
                        "Configure Selenoid browser capabilities for other launch profiles later."
                    )
                }
            )
        return attrs
