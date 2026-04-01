from django.contrib import admin

from apps.specs.models import (
    SpecChunk,
    Specification,
    SpecificationSource,
    SpecificationSourceRecord,
)


class SpecChunkInline(admin.TabularInline):
    model = SpecChunk
    extra = 0
    fields = (
        "chunk_index",
        "chunk_type",
        "component_tag",
        "embedding_model",
        "embedded_at",
        "token_count",
        "content",
    )
    readonly_fields = ("embedding_model", "embedded_at", "token_count")


class SpecificationSourceRecordInline(admin.TabularInline):
    model = SpecificationSourceRecord
    extra = 0
    fields = (
        "record_index",
        "title",
        "external_reference",
        "section_label",
        "row_number",
        "is_selected",
        "import_status",
        "linked_specification",
    )
    readonly_fields = ("import_status", "linked_specification")


@admin.register(Specification)
class SpecificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "project",
        "source_type",
        "version",
        "uploaded_by",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "title",
        "project__name",
        "project__team__name",
        "project__team__organization__name",
        "jira_issue_key",
        "source_url",
    )
    list_filter = (
        "source_type",
        "project__team__organization",
        "project__team",
        "project",
    )
    inlines = [SpecChunkInline]


@admin.register(SpecificationSource)
class SpecificationSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "project",
        "source_type",
        "parser_status",
        "uploaded_by",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "name",
        "project__name",
        "project__team__name",
        "project__team__organization__name",
        "jira_issue_key",
        "source_url",
    )
    list_filter = (
        "source_type",
        "parser_status",
        "project__team__organization",
        "project__team",
        "project",
    )
    inlines = [SpecificationSourceRecordInline]


@admin.register(SpecChunk)
class SpecChunkAdmin(admin.ModelAdmin):
    list_display = (
        "specification",
        "chunk_index",
        "chunk_type",
        "component_tag",
        "embedding_model",
        "embedded_at",
        "token_count",
        "created_at",
    )
    search_fields = (
        "specification__title",
        "component_tag",
        "content",
    )
    list_filter = (
        "chunk_type",
        "embedding_model",
        "specification__project__team__organization",
        "specification__project__team",
        "specification__project",
    )


@admin.register(SpecificationSourceRecord)
class SpecificationSourceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "record_index",
        "title",
        "external_reference",
        "section_label",
        "import_status",
        "linked_specification",
    )
    search_fields = (
        "source__name",
        "title",
        "external_reference",
        "section_label",
        "content",
    )
    list_filter = (
        "import_status",
        "is_selected",
        "source__project__team__organization",
        "source__project__team",
        "source__project",
    )
