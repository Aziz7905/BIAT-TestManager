from django.db import transaction

from apps.specs.models import (
    Specification,
    SpecificationSource,
    SpecificationSourceParserStatus,
    SpecificationSourceRecord,
    SpecificationSourceRecordStatus,
)
from apps.specs.services.deduplication import build_spec_content_hash, find_duplicate_specification
from apps.specs.services.indexing import synchronize_specification_index
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


def _build_record_defaults(source: SpecificationSource, parsed_record, index: int) -> dict:
    return {
        "external_reference": parsed_record.external_reference,
        "section_label": parsed_record.section_label,
        "row_number": parsed_record.row_number,
        "title": parsed_record.title[:300] or f"{source.name} record {index + 1}",
        "content": parsed_record.content,
        "record_metadata": parsed_record.record_metadata,
        "is_selected": parsed_record.is_selected,
    }


def _record_has_manual_changes(record: SpecificationSourceRecord, parsed_defaults: dict) -> bool:
    return any(
        (
            record.title != parsed_defaults["title"],
            record.content != parsed_defaults["content"],
            record.external_reference != parsed_defaults["external_reference"],
            record.section_label != parsed_defaults["section_label"],
            record.row_number != parsed_defaults["row_number"],
            record.record_metadata != parsed_defaults["record_metadata"],
            record.is_selected != parsed_defaults["is_selected"],
        )
    ) and record.updated_at > record.created_at


def _should_preserve_record(
    record: SpecificationSourceRecord,
    parsed_defaults: dict | None = None,
) -> bool:
    if record.linked_specification_id is not None:
        return True
    if record.import_status != SpecificationSourceRecordStatus.PENDING:
        return True
    if parsed_defaults is not None:
        return _record_has_manual_changes(record, parsed_defaults)
    return record.updated_at > record.created_at


def _build_preserved_record_metadata(
    existing_metadata: dict,
    *,
    parsed_defaults: dict | None = None,
    reconciliation_status: str,
) -> dict:
    metadata = dict(existing_metadata or {})
    metadata["_reconciliation_status"] = reconciliation_status
    if parsed_defaults is not None:
        metadata["_latest_parse_snapshot"] = {
            "external_reference": parsed_defaults["external_reference"],
            "section_label": parsed_defaults["section_label"],
            "row_number": parsed_defaults["row_number"],
            "title": parsed_defaults["title"],
            "content": parsed_defaults["content"],
            "record_metadata": parsed_defaults["record_metadata"],
            "is_selected": parsed_defaults["is_selected"],
        }
    return metadata


@transaction.atomic
def parse_specification_source(source: SpecificationSource):
    source.parser_status = SpecificationSourceParserStatus.PARSING
    source.parser_error = ""
    source.save(update_fields=["parser_status", "parser_error", "updated_at"])

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

    existing_records = {
        record.record_index: record
        for record in source.records.select_related("linked_specification")
    }
    records_to_create: list[SpecificationSourceRecord] = []
    records_to_update: list[SpecificationSourceRecord] = []
    records_to_delete: list[str] = []

    for index, parsed_record in enumerate(parsed.records):
        parsed_defaults = _build_record_defaults(source, parsed_record, index)
        existing_record = existing_records.pop(index, None)

        if existing_record is None:
            records_to_create.append(
                SpecificationSourceRecord(
                    source=source,
                    record_index=index,
                    **parsed_defaults,
                )
            )
            continue

        if _should_preserve_record(existing_record, parsed_defaults):
            preserved_metadata = _build_preserved_record_metadata(
                existing_record.record_metadata,
                parsed_defaults=parsed_defaults,
                reconciliation_status="preserved_curated_record",
            )
            if existing_record.record_metadata != preserved_metadata:
                existing_record.record_metadata = preserved_metadata
                records_to_update.append(existing_record)
            continue

        for field_name, field_value in parsed_defaults.items():
            setattr(existing_record, field_name, field_value)
        if existing_record.error_message:
            existing_record.error_message = ""
        records_to_update.append(existing_record)

    for stale_record in existing_records.values():
        if _should_preserve_record(stale_record):
            preserved_metadata = _build_preserved_record_metadata(
                stale_record.record_metadata,
                reconciliation_status="missing_from_latest_parse",
            )
            update_required = False

            if stale_record.record_metadata != preserved_metadata:
                stale_record.record_metadata = preserved_metadata
                update_required = True

            if (
                stale_record.import_status == SpecificationSourceRecordStatus.PENDING
                and stale_record.is_selected
            ):
                stale_record.is_selected = False
                update_required = True

            if update_required:
                records_to_update.append(stale_record)
            continue

        records_to_delete.append(str(stale_record.id))

    if records_to_delete:
        SpecificationSourceRecord.objects.filter(pk__in=records_to_delete).delete()

    if records_to_create:
        SpecificationSourceRecord.objects.bulk_create(records_to_create)

    if records_to_update:
        SpecificationSourceRecord.objects.bulk_update(
            records_to_update,
            [
                "external_reference",
                "section_label",
                "row_number",
                "title",
                "content",
                "record_metadata",
                "is_selected",
                "error_message",
            ],
        )

    source.source_metadata = {
        **parsed.source_metadata,
        "latest_parse_record_count": len(parsed.records),
    }
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
        synchronize_specification_index(specification, force=True)

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
