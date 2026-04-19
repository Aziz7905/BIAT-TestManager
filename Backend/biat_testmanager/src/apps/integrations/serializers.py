from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from apps.integrations.models import (
    ExternalIssueLink,
    IntegrationActionLog,
    IntegrationConfig,
    RepositoryBinding,
    UserIntegrationCredential,
    WebhookEvent,
)
from apps.integrations.services import (
    configure_project_integration,
    configure_team_integration,
    create_repository_binding_for_project,
    link_external_issue_to_object,
    store_user_integration_credential,
    update_repository_binding,
)

SENSITIVE_CONFIG_KEYS = {"api_key", "password", "secret", "token", "webhook_secret"}


class IntegrationConfigSerializer(serializers.ModelSerializer):
    config_data = serializers.SerializerMethodField()
    team_name = serializers.CharField(source="team.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = IntegrationConfig
        fields = [
            "id",
            "team",
            "team_name",
            "project",
            "project_name",
            "provider_slug",
            "config_data",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_config_data(self, obj):
        return {
            key: "********" if key in SENSITIVE_CONFIG_KEYS else value
            for key, value in obj.config_data.items()
        }


class IntegrationConfigWriteSerializer(serializers.Serializer):
    config_data = serializers.JSONField(default=dict)
    is_active = serializers.BooleanField(default=True)

    def save(self, **kwargs):
        request = self.context["request"]
        provider_slug = self.context["provider_slug"]
        config_data = self._preserve_redacted_secrets(
            self.validated_data.get("config_data") or {}
        )
        is_active = self.validated_data.get("is_active", True)

        if team := self.context.get("team"):
            return configure_team_integration(
                actor=request.user,
                team=team,
                provider_slug=provider_slug,
                config_data=config_data,
                is_active=is_active,
            )

        return configure_project_integration(
            actor=request.user,
            project=self.context["project"],
            provider_slug=provider_slug,
            config_data=config_data,
            is_active=is_active,
        )

    def _preserve_redacted_secrets(self, config_data: dict) -> dict:
        existing = self._get_existing_config()
        if existing is None:
            return config_data

        existing_data = existing.config_data
        merged_data = config_data.copy()
        for key in SENSITIVE_CONFIG_KEYS:
            if merged_data.get(key) == "********" and existing_data.get(key):
                merged_data[key] = existing_data[key]
        return merged_data

    def _get_existing_config(self):
        provider_slug = self.context["provider_slug"]
        if team := self.context.get("team"):
            return IntegrationConfig.objects.filter(
                team=team,
                project=None,
                provider_slug=provider_slug,
            ).first()
        return IntegrationConfig.objects.filter(
            project=self.context["project"],
            provider_slug=provider_slug,
        ).first()


class UserIntegrationCredentialSerializer(serializers.ModelSerializer):
    has_credential = serializers.SerializerMethodField()

    class Meta:
        model = UserIntegrationCredential
        fields = [
            "id",
            "provider_slug",
            "has_credential",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_has_credential(self, obj):
        return bool(obj.credential_data)


class UserIntegrationCredentialWriteSerializer(serializers.Serializer):
    credential_data = serializers.JSONField(default=dict)
    is_active = serializers.BooleanField(default=True)

    def save(self, **kwargs):
        request = self.context["request"]
        return store_user_integration_credential(
            profile=request.user.profile,
            provider_slug=self.context["provider_slug"],
            credential_data=self.validated_data.get("credential_data") or {},
            is_active=self.validated_data.get("is_active", True),
        )


class RepositoryBindingSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = RepositoryBinding
        fields = [
            "id",
            "project",
            "project_name",
            "provider_slug",
            "repo_identifier",
            "default_branch",
            "metadata_json",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "project_name",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name().strip() or obj.created_by.username

    def create(self, validated_data):
        return create_repository_binding_for_project(
            actor=self.context["request"].user,
            project=self.context["project"],
            provider_slug=validated_data["provider_slug"],
            repo_identifier=validated_data["repo_identifier"],
            default_branch=validated_data.get("default_branch", "main"),
            metadata_json=validated_data.get("metadata_json") or {},
        )

    def update(self, instance, validated_data):
        return update_repository_binding(
            actor=self.context["request"].user,
            binding=instance,
            default_branch=validated_data.get("default_branch"),
            metadata_json=validated_data.get("metadata_json"),
            is_active=validated_data.get("is_active"),
        )


class WebhookEventListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    repository = serializers.CharField(
        source="repository_binding.repo_identifier",
        read_only=True,
    )

    class Meta:
        model = WebhookEvent
        fields = [
            "id",
            "project",
            "project_name",
            "repository",
            "provider_slug",
            "event_type",
            "external_id",
            "status",
            "received_at",
            "processed_at",
        ]


class WebhookEventDetailSerializer(WebhookEventListSerializer):
    class Meta(WebhookEventListSerializer.Meta):
        fields = WebhookEventListSerializer.Meta.fields + [
            "payload_json",
            "headers_json",
            "error_message",
        ]


class ExternalIssueLinkSerializer(serializers.ModelSerializer):
    target_type = serializers.SerializerMethodField(read_only=True)
    target_type_input = serializers.CharField(write_only=True)
    object_id = serializers.CharField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ExternalIssueLink
        fields = [
            "id",
            "project",
            "provider_slug",
            "external_key",
            "external_url",
            "target_type",
            "target_type_input",
            "object_id",
            "metadata_json",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "target_type",
            "is_active",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def get_target_type(self, obj):
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name().strip() or obj.created_by.username

    def validate(self, attrs):
        target_type = attrs.pop("target_type_input")
        attrs["content_object"] = self._resolve_content_object(
            target_type=target_type,
            object_id=attrs["object_id"],
        )
        return attrs

    def create(self, validated_data):
        content_object = validated_data.pop("content_object")
        return link_external_issue_to_object(
            actor=self.context["request"].user,
            project=self.context["project"],
            provider_slug=validated_data["provider_slug"],
            external_key=validated_data["external_key"],
            external_url=validated_data.get("external_url", ""),
            content_object=content_object,
            metadata_json=validated_data.get("metadata_json") or {},
        )

    def _resolve_content_object(self, *, target_type: str, object_id: str):
        if "." not in target_type:
            raise serializers.ValidationError(
                {"target_type_input": "Use the format app_label.model."}
            )
        app_label, model = target_type.split(".", 1)
        try:
            content_type = ContentType.objects.get(
                app_label=app_label,
                model=model.lower(),
            )
        except ContentType.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"target_type_input": "Unknown target type."}
            ) from exc

        try:
            target = content_type.get_object_for_this_type(pk=object_id)
        except ObjectDoesNotExist as exc:
            raise serializers.ValidationError({"object_id": "Target object was not found."})
        if target is None:
            raise serializers.ValidationError({"object_id": "Target object was not found."})
        return target


class IntegrationActionLogSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    actor_username = serializers.CharField(source="actor_user.username", read_only=True)

    class Meta:
        model = IntegrationActionLog
        fields = [
            "id",
            "team",
            "team_name",
            "project",
            "project_name",
            "provider_slug",
            "action_type",
            "actor_user",
            "actor_username",
            "status",
            "error_message",
            "created_at",
            "completed_at",
        ]
