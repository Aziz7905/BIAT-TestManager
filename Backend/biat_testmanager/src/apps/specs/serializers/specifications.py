from rest_framework import serializers

from apps.projects.models import Project
from apps.specs.models import (
    SpecChunk,
    Specification,
    SpecificationSource,
    SpecificationSourceRecord,
    SpecificationSourceType,
)
from apps.specs.services import (
    build_spec_content_hash,
    can_create_specifications,
    can_manage_specification_record,
    can_manage_specification_source,
    can_manage_specification_source_record,
    find_duplicate_specification,
    import_selected_records,
    index_specification,
    infer_source_name,
    parse_specification_source,
    sync_specification_chunks,
)
from apps.testing.models import TestCase


class SpecChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecChunk
        fields = [
            "id",
            "chunk_index",
            "chunk_type",
            "component_tag",
            "content",
            "embedding_vector",
            "embedding_model",
            "embedded_at",
            "token_count",
            "created_at",
        ]


class LinkedTestCaseCompactSerializer(serializers.ModelSerializer):
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


class SpecificationSourceRecordSerializer(serializers.ModelSerializer):
    linked_specification_id = serializers.UUIDField(
        source="linked_specification.id",
        read_only=True,
    )
    linked_specification_title = serializers.CharField(
        source="linked_specification.title",
        read_only=True,
    )

    class Meta:
        model = SpecificationSourceRecord
        fields = [
            "id",
            "record_index",
            "external_reference",
            "section_label",
            "row_number",
            "title",
            "content",
            "record_metadata",
            "is_selected",
            "import_status",
            "error_message",
            "linked_specification_id",
            "linked_specification_title",
            "created_at",
            "updated_at",
        ]


class SpecificationSourceRecordUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecificationSourceRecord
        fields = ["title", "content", "is_selected", "external_reference", "section_label"]

    def validate(self, attrs):
        if not can_manage_specification_source_record(self.context["request"].user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this source record."}
            )
        return attrs


class SpecificationSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.select_related("team", "team__organization").all()
    )
    project_name = serializers.CharField(source="project.name", read_only=True)
    team = serializers.UUIDField(source="project.team.id", read_only=True)
    team_name = serializers.CharField(source="project.team.name", read_only=True)
    organization = serializers.UUIDField(
        source="project.team.organization.id",
        read_only=True,
    )
    organization_name = serializers.CharField(
        source="project.team.organization.name",
        read_only=True,
    )
    uploaded_by = serializers.IntegerField(source="uploaded_by.id", read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    source_id = serializers.UUIDField(source="source.id", read_only=True)
    source_name = serializers.CharField(source="source.name", read_only=True)
    source_record_id = serializers.SerializerMethodField()
    chunk_count = serializers.IntegerField(read_only=True)
    can_manage = serializers.SerializerMethodField()
    qtest_preview = serializers.SerializerMethodField()
    chunks = SpecChunkSerializer(many=True, read_only=True)
    linked_test_case_count = serializers.SerializerMethodField()
    linked_scenario_count = serializers.SerializerMethodField()
    linked_suite_count = serializers.SerializerMethodField()
    linked_test_cases = serializers.SerializerMethodField()
    coverage_status = serializers.SerializerMethodField()

    class Meta:
        model = Specification
        fields = [
            "id",
            "project",
            "project_name",
            "team",
            "team_name",
            "organization",
            "organization_name",
            "source_id",
            "source_name",
            "source_record_id",
            "title",
            "content",
            "source_type",
            "jira_issue_key",
            "source_url",
            "external_reference",
            "source_metadata",
            "version",
            "uploaded_by",
            "uploaded_by_name",
            "chunk_count",
            "can_manage",
            "qtest_preview",
            "chunks",
            "linked_test_case_count",
            "linked_scenario_count",
            "linked_suite_count",
            "linked_test_cases",
            "coverage_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uploaded_by",
            "uploaded_by_name",
            "source_id",
            "source_name",
            "source_record_id",
            "source_metadata",
            "chunk_count",
            "can_manage",
            "qtest_preview",
            "chunks",
            "linked_test_case_count",
            "linked_scenario_count",
            "linked_suite_count",
            "linked_test_cases",
            "coverage_status",
            "created_at",
            "updated_at",
        ]

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return None
        full_name = obj.uploaded_by.get_full_name().strip()
        return full_name or obj.uploaded_by.email or obj.uploaded_by.username

    def get_source_record_id(self, obj):
        try:
            record = obj.source_record
        except SpecificationSourceRecord.DoesNotExist:
            record = None
        return getattr(record, "id", None)

    def get_can_manage(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        return can_manage_specification_record(request.user, obj)

    def _get_structured_record_fields(self, obj) -> dict[str, str]:
        record_metadata = obj.source_metadata.get("record", {}) if obj.source_metadata else {}
        structured_fields = record_metadata.get("structured_fields", {})
        if isinstance(structured_fields, dict):
            return {
                str(key): str(value)
                for key, value in structured_fields.items()
                if value not in (None, "")
            }
        return {}

    def _get_linked_test_case_queryset(self, obj):
        prefetched_cases = getattr(obj, "_prefetched_objects_cache", {}).get("linked_test_cases")
        if prefetched_cases is not None:
            return prefetched_cases
        return obj.linked_test_cases.select_related("scenario", "scenario__suite").order_by(
            "scenario__suite__name",
            "scenario__title",
            "title",
        )

    def get_linked_test_case_count(self, obj):
        annotated_value = getattr(obj, "linked_test_case_count", None)
        if annotated_value is not None:
            return annotated_value
        return obj.linked_test_cases.count()

    def get_linked_scenario_count(self, obj):
        annotated_value = getattr(obj, "linked_scenario_count", None)
        if annotated_value is not None:
            return annotated_value
        return obj.linked_test_cases.values("scenario_id").distinct().count()

    def get_linked_suite_count(self, obj):
        annotated_value = getattr(obj, "linked_suite_count", None)
        if annotated_value is not None:
            return annotated_value
        return obj.linked_test_cases.values("scenario__suite_id").distinct().count()

    def get_linked_test_cases(self, obj):
        linked_test_cases = self._get_linked_test_case_queryset(obj)
        return LinkedTestCaseCompactSerializer(linked_test_cases, many=True).data

    def get_coverage_status(self, obj):
        if self.get_linked_test_case_count(obj) > 0:
            return "covered"
        return "uncovered"

    def get_qtest_preview(self, obj):
        try:
            record = obj.source_record
        except SpecificationSourceRecord.DoesNotExist:
            record = None
        structured_fields = self._get_structured_record_fields(obj)
        description = structured_fields.get("description") or obj.content
        if structured_fields.get("actor"):
            description = f"{description}\nActeur: {structured_fields['actor']}"
        if structured_fields.get("steps"):
            description = f"{description}\nEtapes: {structured_fields['steps']}"
        if structured_fields.get("acceptance_criteria"):
            description = (
                f"{description}\nCriteres d'acceptation: "
                f"{structured_fields['acceptance_criteria']}"
            )
        return {
            "module": structured_fields.get("module")
            or getattr(record, "section_label", "")
            or obj.project.name,
            "requirement_id": obj.external_reference
            or getattr(record, "external_reference", "")
            or structured_fields.get("reference", "")
            or obj.jira_issue_key
            or "",
            "summary": structured_fields.get("title") or obj.title,
            "description": description,
            "section": structured_fields.get("section")
            or getattr(record, "section_label", "")
            or obj.project.team.name,
            "preconditions": structured_fields.get("preconditions", ""),
            "expected_result": structured_fields.get(
                "expected_result",
                "To be generated during the test design layer.",
            ),
        }

    def validate(self, attrs):
        request = self.context["request"]
        project = attrs.get("project") or getattr(self.instance, "project", None)

        if project is None:
            raise serializers.ValidationError({"project": "Project is required."})

        if self.instance is None:
            if not can_create_specifications(request.user, project):
                raise serializers.ValidationError(
                    {
                        "project": "You do not have permission to create specifications for this project."
                    }
                )
        elif not can_manage_specification_record(request.user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this specification."}
            )

        source_type = attrs.get("source_type") or getattr(self.instance, "source_type", None)
        jira_issue_key = attrs.get(
            "jira_issue_key",
            getattr(self.instance, "jira_issue_key", None),
        )
        source_url = attrs.get("source_url", getattr(self.instance, "source_url", None))
        content = attrs.get("content", getattr(self.instance, "content", ""))

        if source_type == SpecificationSourceType.JIRA_ISSUE and not jira_issue_key:
            raise serializers.ValidationError(
                {
                    "jira_issue_key": "A Jira issue key is required when the source type is jira_issue."
                }
            )

        if source_type == SpecificationSourceType.URL and not source_url:
            raise serializers.ValidationError(
                {"source_url": "A source URL is required when the source type is url."}
            )

        duplicate = find_duplicate_specification(
            project=project,
            content=content,
            exclude_specification_id=getattr(self.instance, "id", None),
        )
        if duplicate is not None:
            raise serializers.ValidationError(
                {
                    "content": (
                        f"This specification already exists in the project as "
                        f"'{duplicate.title}'."
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        specification = Specification.objects.create(
            uploaded_by=self.context["request"].user,
            content_hash=build_spec_content_hash(validated_data["content"]),
            **validated_data,
        )
        sync_specification_chunks(specification)
        index_specification(specification, force=True)
        return specification

    def update(self, instance, validated_data):
        content_changed = "content" in validated_data

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if "content" in validated_data:
            instance.content_hash = build_spec_content_hash(instance.content)

        instance.save()

        if content_changed:
            sync_specification_chunks(instance)
            index_specification(instance, force=True)

        return instance


class SpecificationSourceListSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    team_name = serializers.CharField(source="project.team.name", read_only=True)
    organization_name = serializers.CharField(
        source="project.team.organization.name",
        read_only=True,
    )
    uploaded_by_name = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    record_count = serializers.IntegerField(read_only=True)
    selected_record_count = serializers.IntegerField(read_only=True)
    imported_record_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = SpecificationSource
        fields = [
            "id",
            "project",
            "project_name",
            "team_name",
            "organization_name",
            "name",
            "source_type",
            "file_name",
            "source_url",
            "jira_issue_key",
            "parser_status",
            "parser_error",
            "source_metadata",
            "column_mapping",
            "record_count",
            "selected_record_count",
            "imported_record_count",
            "uploaded_by_name",
            "can_manage",
            "created_at",
            "updated_at",
        ]

    def get_uploaded_by_name(self, obj):
        if not obj.uploaded_by:
            return None
        full_name = obj.uploaded_by.get_full_name().strip()
        return full_name or obj.uploaded_by.email or obj.uploaded_by.username

    def get_file_name(self, obj):
        if not obj.file:
            return None
        return obj.file.name.split("/")[-1]

    def get_can_manage(self, obj):
        request = self.context.get("request")
        if not request:
            return False
        return can_manage_specification_source(request.user, obj)


class SpecificationSourceDetailSerializer(SpecificationSourceListSerializer):
    raw_text = serializers.CharField(read_only=True)
    records = SpecificationSourceRecordSerializer(many=True, read_only=True)

    class Meta(SpecificationSourceListSerializer.Meta):
        fields = SpecificationSourceListSerializer.Meta.fields + [
            "raw_text",
            "records",
        ]


class SpecificationSourceCreateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    file = serializers.FileField(required=False, allow_null=True)
    raw_text = serializers.CharField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    jira_issue_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    auto_parse = serializers.BooleanField(required=False, default=True, write_only=True)
    auto_import = serializers.BooleanField(required=False, default=True, write_only=True)

    class Meta:
        model = SpecificationSource
        fields = [
            "project",
            "name",
            "source_type",
            "file",
            "raw_text",
            "source_url",
            "jira_issue_key",
            "auto_parse",
            "auto_import",
        ]

    def validate(self, attrs):
        project = attrs["project"]
        source_type = attrs["source_type"]
        actor = self.context["request"].user
        uploaded_file = attrs.get("file")
        raw_text = (attrs.get("raw_text") or "").strip()
        source_url = attrs.get("source_url")
        jira_issue_key = attrs.get("jira_issue_key")

        if not can_create_specifications(actor, project):
            raise serializers.ValidationError(
                {"project": "You do not have permission to import specifications for this project."}
            )

        file_required_types = {
            SpecificationSourceType.CSV,
            SpecificationSourceType.XLSX,
            SpecificationSourceType.PDF,
            SpecificationSourceType.DOCX,
            SpecificationSourceType.FILE_UPLOAD,
        }

        if source_type in file_required_types and uploaded_file is None:
            raise serializers.ValidationError({"file": "A file is required for this source type."})

        if source_type in {SpecificationSourceType.MANUAL, SpecificationSourceType.PLAIN_TEXT} and not raw_text:
            raise serializers.ValidationError({"raw_text": "Text content is required."})

        if source_type == SpecificationSourceType.JIRA_ISSUE and not jira_issue_key:
            raise serializers.ValidationError({"jira_issue_key": "A Jira issue key is required."})

        if source_type == SpecificationSourceType.URL and not source_url:
            raise serializers.ValidationError({"source_url": "A source URL is required."})

        return attrs

    def create(self, validated_data):
        auto_parse = validated_data.pop("auto_parse", True)
        auto_import = validated_data.pop("auto_import", True)
        name = (validated_data.get("name") or "").strip()
        uploaded_file = validated_data.get("file")
        inferred_name = infer_source_name(
            validated_data["source_type"],
            file_name=getattr(uploaded_file, "name", ""),
            jira_issue_key=validated_data.get("jira_issue_key") or "",
            source_url=validated_data.get("source_url") or "",
        )

        source = SpecificationSource.objects.create(
            uploaded_by=self.context["request"].user,
            name=name or inferred_name,
            **validated_data,
        )

        if auto_parse:
            parse_specification_source(source)
            if auto_import:
                import_selected_records(source, self.context["request"].user)

        return source


class SpecificationSourceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecificationSource
        fields = ["name", "raw_text", "source_url", "jira_issue_key"]

    def validate(self, attrs):
        if not can_manage_specification_source(self.context["request"].user, self.instance):
            raise serializers.ValidationError(
                {"detail": "You do not have permission to update this source."}
            )
        return attrs
