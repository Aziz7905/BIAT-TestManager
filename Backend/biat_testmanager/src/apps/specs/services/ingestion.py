from django.db import transaction

from apps.specs.models import (
    Specification,
    SpecificationSource,
    SpecificationSourceParserStatus,
    SpecificationSourceRecord,
    SpecificationSourceRecordStatus,
)
from apps.specs.services.chunking import sync_specification_chunks
from apps.specs.services.deduplication import build_spec_content_hash, find_duplicate_specification
from apps.specs.services.indexing import index_specification
from apps.specs.services.parsers import get_parser_for_source
from apps.specs.services.parsers.base import SpecificationSourceParseError


def infer_source_name(source_type: str, *, file_name: str = "", jira_issue_key: str = "", source_url: str = "") -> str:
    if file_name:
        return file_name.split("/")[-1]

    if jira_issue_key:
        return jira_issue_key

    if source_url:
        return source_url

    return source_type.replace("_", " ").title()


@transaction.atomic
def parse_specification_source(source: SpecificationSource):
    source.parser_status = SpecificationSourceParserStatus.PARSING
    source.parser_error = ""
    source.save(update_fields=["parser_status", "parser_error", "updated_at"])

    source.records.all().delete()

    parser = get_parser_for_source(source)

    try:
        parsed = parser.parse(source)
    except SpecificationSourceParseError as error:
        source.parser_status = SpecificationSourceParserStatus.FAILED
        source.parser_error = str(error)
        source.save(
            update_fields=[
                "parser_status",
                "parser_error",
                "updated_at",
            ]
        )
        return source

    SpecificationSourceRecord.objects.bulk_create(
        [
            SpecificationSourceRecord(
                source=source,
                record_index=index,
                external_reference=record.external_reference,
                section_label=record.section_label,
                row_number=record.row_number,
                title=record.title[:300] or f"{source.name} record {index + 1}",
                content=record.content,
                record_metadata=record.record_metadata,
                is_selected=record.is_selected,
            )
            for index, record in enumerate(parsed.records)
        ]
    )

    source.source_metadata = parsed.source_metadata
    source.column_mapping = parsed.column_mapping
    source.parser_status = SpecificationSourceParserStatus.READY
    source.parser_error = ""
    source.save(
        update_fields=[
            "source_metadata",
            "column_mapping",
            "parser_status",
            "parser_error",
            "updated_at",
        ]
    )
    return source


def _build_unique_title(project, desired_title: str, version: str) -> str:
    base_title = desired_title[:300] or "Imported Specification"
    candidate = base_title
    suffix = 2

    while Specification.objects.filter(project=project, title=candidate, version=version).exists():
        trimmed_base = base_title[: max(0, 295 - len(str(suffix)))]
        candidate = f"{trimmed_base} ({suffix})"
        suffix += 1

    return candidate


@transaction.atomic
def import_selected_records(source: SpecificationSource, actor):
    imported_specifications: list[Specification] = []

    selected_records = source.records.select_for_update().filter(
        is_selected=True,
        linked_specification__isnull=True,
    )

    for record in selected_records:
        version = "1.0"
        duplicate = find_duplicate_specification(
            project=source.project,
            content=record.content,
        )
        if duplicate is not None:
            record.import_status = SpecificationSourceRecordStatus.SKIPPED
            record.error_message = (
                f"Duplicate specification detected: {duplicate.title} ({duplicate.id})."
            )
            record.save(
                update_fields=[
                    "import_status",
                    "error_message",
                    "updated_at",
                ]
            )
            continue

        title = _build_unique_title(source.project, record.title, version)

        specification = Specification.objects.create(
            project=source.project,
            source=source,
            title=title,
            content=record.content,
            source_type=source.source_type,
            jira_issue_key=source.jira_issue_key,
            source_url=source.source_url,
            external_reference=record.external_reference or None,
            source_metadata={
                "source": source.source_metadata,
                "record": record.record_metadata,
                "section_label": record.section_label,
                "row_number": record.row_number,
            },
            content_hash=build_spec_content_hash(record.content),
            version=version,
            uploaded_by=actor,
        )
        sync_specification_chunks(specification)
        index_specification(specification, force=True)

        record.linked_specification = specification
        record.import_status = SpecificationSourceRecordStatus.IMPORTED
        record.error_message = ""
        record.save(
            update_fields=[
                "linked_specification",
                "import_status",
                "error_message",
                "updated_at",
            ]
        )

        imported_specifications.append(specification)

    source.parser_status = (
        SpecificationSourceParserStatus.IMPORTED
        if source.records.filter(
            is_selected=True,
            import_status=SpecificationSourceRecordStatus.PENDING,
        ).count()
        == 0
        else SpecificationSourceParserStatus.READY
    )
    source.save(update_fields=["parser_status", "updated_at"])

    return imported_specifications
