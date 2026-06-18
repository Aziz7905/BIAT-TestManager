from django.db import transaction
from django.db.models import Max

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
from apps.specs.services.parsers.base import SpecificationSourceParseError, clean_text


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


def _record_fatal_validation_errors(record: SpecificationSourceRecord) -> list[str]:
    validation = (record.record_metadata or {}).get("validation") or {}
    fatal_errors = validation.get("fatal_errors") or []
    return [str(error) for error in fatal_errors if str(error).strip()]


def _record_review(record: SpecificationSourceRecord) -> dict:
    return (record.record_metadata or {}).get("review") or {}


def _record_needs_unconfirmed_mapping(record: SpecificationSourceRecord) -> bool:
    review = _record_review(record)
    return bool(review.get("needs_mapping")) and not review.get("confirmed")


@transaction.atomic
def import_selected_records(source: SpecificationSource, actor):
    imported_specifications: list[Specification] = []

    selected_records = source.records.select_for_update().filter(
        is_selected=True,
        linked_specification__isnull=True,
    )

    for record in selected_records:
        if _record_needs_unconfirmed_mapping(record):
            continue

        fatal_errors = _record_fatal_validation_errors(record)
        if fatal_errors:
            record.import_status = SpecificationSourceRecordStatus.FAILED
            record.error_message = " ".join(fatal_errors)
            record.save(
                update_fields=[
                    "import_status",
                    "error_message",
                    "updated_at",
                ]
            )
            continue

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


@transaction.atomic
def delete_selected_records(source: SpecificationSource) -> int:
    selected_records = source.records.select_for_update().filter(is_selected=True)
    deleted_count = selected_records.count()
    if deleted_count:
        selected_records.delete()
    return deleted_count


# Canonical mapping targets. This is a fixed target *schema* the user maps onto;
# it is not used to guess meaning. Order also drives content rendering.
MAPPING_FIELD_ORDER = [
    "external_id",
    "title",
    "module",
    "section",
    "description",
    "preconditions",
    "steps",
    "expected_result",
    "acceptance_criteria",
    "priority",
]
MAPPING_FIELD_LABELS = {
    "external_id": "ID",
    "title": "Title",
    "module": "Module",
    "section": "Section",
    "description": "Description",
    "preconditions": "Preconditions",
    "steps": "Steps",
    "expected_result": "Expected Result",
    "acceptance_criteria": "Acceptance Criteria",
    "priority": "Priority",
}
MAPPABLE_RECORD_TYPES = {"requirement", "test_case", "test_data", "context", "ignore"}
TABLE_RECORD_TYPES = {"requirement", "test_case", "test_data"}
EMPTY_REGION_MESSAGE = "Region has no readable content."


def _content_validation(content: str) -> dict:
    return {
        "fatal_errors": [] if clean_text(content) else [EMPTY_REGION_MESSAGE],
        "warnings": [],
    }


def _apply_mapping_to_row(cells: list[dict], column_mapping: dict[str, str]) -> dict:
    """Project one structural row onto the canonical schema using the user's mapping.

    Mapped columns are reordered into the canonical schema; every other populated
    column is preserved verbatim as an extra "label: value" line — never dropped.
    """
    mapped: dict[str, str] = {}
    extras: list[tuple[str, str]] = []

    for cell in cells:
        value = cell.get("displayed_value") or cell.get("raw_value") or ""
        if not value:
            continue
        label = cell.get("header_candidate") or f"Column {cell.get('column_letter', '')}".strip()
        target = column_mapping.get(label)
        if target in MAPPING_FIELD_LABELS:
            mapped.setdefault(target, value)
        else:
            extras.append((label, value))

    lines = [
        f"{MAPPING_FIELD_LABELS[field]}: {mapped[field]}"
        for field in MAPPING_FIELD_ORDER
        if mapped.get(field)
    ]
    lines.extend(f"{label}: {value}" for label, value in extras)

    return {
        "content": "\n".join(lines),
        "external_reference": mapped.get("external_id", ""),
        "title": mapped.get("title", ""),
        "section_label": mapped.get("section") or mapped.get("module") or "",
    }


def _confirm_record_mapping(
    record: SpecificationSourceRecord,
    *,
    record_type: str,
    column_mapping: dict[str, str],
) -> None:
    metadata = dict(record.record_metadata or {})
    review = dict(metadata.get("review") or {})
    review.update(
        {
            "confirmed": True,
            "record_type": record_type,
            "column_mapping": column_mapping,
        }
    )
    metadata["review"] = review

    if record_type == "ignore":
        record.is_selected = False
        record.record_metadata = metadata
        return

    record.is_selected = True
    cells = ((metadata.get("structure") or {}).get("row") or {}).get("cells") or []
    if cells:
        projection = _apply_mapping_to_row(cells, column_mapping)
        record.content = projection["content"] or record.content
        record.external_reference = projection["external_reference"][:120]
        if projection["title"]:
            record.title = projection["title"][:300]
        if projection["section_label"]:
            record.section_label = projection["section_label"][:200]

    validation = dict(metadata.get("validation") or {})
    validation["fatal_errors"] = [] if clean_text(record.content) else [EMPTY_REGION_MESSAGE]
    metadata["validation"] = validation
    record.record_metadata = metadata


def _record_structure(record: SpecificationSourceRecord) -> dict:
    return (record.record_metadata or {}).get("structure") or {}


def _region_base(structure: dict) -> dict:
    return {
        "region_id": structure.get("region_id"),
        "container": structure.get("container") or "",
        "source_range": structure.get("source_range") or "",
        "header_candidates": structure.get("header_candidates") or [],
    }


def _save_in_place(records: list[SpecificationSourceRecord], record_type: str, column_mapping: dict[str, str]) -> None:
    for record in records:
        _confirm_record_mapping(record, record_type=record_type, column_mapping=column_mapping)
        record.save(
            update_fields=[
                "title",
                "content",
                "external_reference",
                "section_label",
                "is_selected",
                "record_metadata",
                "updated_at",
            ]
        )


def _labelled_cells(grid_row: list[dict], header_values: list[str], has_header: bool) -> list[dict]:
    cells = []
    for position, cell in enumerate(grid_row):
        value = cell.get("displayed_value") or cell.get("raw_value") or ""
        if not (value or cell.get("formula")):
            continue
        label = (
            header_values[position]
            if has_header and position < len(header_values) and header_values[position]
            else f"Column {cell.get('column_letter') or ''}".strip()
        )
        cells.append({**cell, "header_candidate": label})
    return cells


def _is_repeated_header_row(cells: list[dict], header_values: list[str]) -> bool:
    if not header_values:
        return False
    row_values = {cell.get("displayed_value") or cell.get("raw_value") or "" for cell in cells}
    return {value for value in row_values if value} == {value for value in header_values if value}


def _table_row_record(
    source: SpecificationSource,
    base: dict,
    cells: list[dict],
    row_number,
    record_type: str,
    column_mapping: dict[str, str],
    index: int,
) -> SpecificationSourceRecord:
    projection = _apply_mapping_to_row(cells, column_mapping)
    content = projection["content"]
    return SpecificationSourceRecord(
        source=source,
        record_index=index,
        external_reference=projection["external_reference"][:120],
        section_label=(projection["section_label"] or base["container"])[:200],
        row_number=row_number,
        title=(projection["title"] or f"{base['container']} row {row_number}")[:300],
        content=content,
        is_selected=True,
        record_metadata={
            "source_mode": "structural_table_row",
            "structure": {**base, "row": {"row_number": row_number, "cells": cells}},
            "review": {
                "needs_mapping": False,
                "confirmed": True,
                "record_type": record_type,
                "column_mapping": column_mapping,
            },
            "validation": _content_validation(content),
        },
    )


def _promote_to_table(
    source: SpecificationSource,
    context_record: SpecificationSourceRecord,
    *,
    record_type: str,
    column_mapping: dict[str, str],
    start_index: int,
) -> list[SpecificationSourceRecord]:
    structure = _record_structure(context_record)
    base = _region_base(structure)
    base["structural_type"] = "table"
    header_candidates = base["header_candidates"]
    header_values = header_candidates[0]["values"] if header_candidates else []
    has_header = bool(header_values)
    data_rows = (structure.get("grid") or [])[1:] if has_header else (structure.get("grid") or [])

    records: list[SpecificationSourceRecord] = []
    index = start_index
    for grid_row in data_rows:
        cells = _labelled_cells(grid_row, header_values, has_header)
        if not cells or _is_repeated_header_row(cells, header_values):
            continue
        row_number = grid_row[0].get("row") if grid_row else None
        records.append(
            _table_row_record(source, base, cells, row_number, record_type, column_mapping, index)
        )
        index += 1
    return records


def _demote_to_context(
    source: SpecificationSource,
    region_records: list[SpecificationSourceRecord],
    *,
    start_index: int,
) -> list[SpecificationSourceRecord]:
    ordered = sorted(region_records, key=lambda record: record.row_number or 0)
    content = "\n\n".join(record.content for record in ordered if record.content)
    structure = _record_structure(ordered[0])
    base = _region_base(structure)
    base["structural_type"] = "key_value_block"

    # Reconstruct a grid (header row + data rows) so the region can be promoted again.
    grid: list[list[dict]] = []
    if base["header_candidates"]:
        grid.append(
            [
                {"column": position + 1, "column_letter": "", "displayed_value": value, "raw_value": value, "formula": "", "merged": False, "row": None, "coordinate": ""}
                for position, value in enumerate(base["header_candidates"][0]["values"])
            ]
        )
    for record in ordered:
        cells = (_record_structure(record).get("row") or {}).get("cells") or []
        if cells:
            grid.append(cells)
    base["grid"] = grid

    title = next((line.strip() for line in content.splitlines() if line.strip()), "") or f"{base['container']} context"
    return [
        SpecificationSourceRecord(
            source=source,
            record_index=start_index,
            external_reference="",
            section_label=base["container"][:200],
            row_number=ordered[0].row_number,
            title=title[:300],
            content=content,
            is_selected=True,
            record_metadata={
                "source_mode": "structural_region",
                "structure": base,
                "review": {"needs_mapping": False, "confirmed": True, "record_type": "context", "column_mapping": {}},
                "validation": _content_validation(content),
            },
        )
    ]


@transaction.atomic
def apply_region_mapping(
    source: SpecificationSource,
    *,
    region_id: str,
    record_type: str,
    column_mapping: dict[str, str],
) -> list[SpecificationSourceRecord]:
    """Confirm — and if needed re-type — a structural region across its records.

    Promoting a key/value region to a table re-splits it into per-row records;
    demoting a table collapses it to one context record. Re-mapping a region
    that already has the target granularity is applied in place.
    """
    if record_type not in MAPPABLE_RECORD_TYPES:
        raise ValueError(f"Unsupported record type: {record_type}")

    column_mapping = {str(key): str(value) for key, value in (column_mapping or {}).items() if value}

    region_records = [
        record
        for record in source.records.select_for_update().filter(linked_specification__isnull=True)
        if _record_structure(record).get("region_id") == region_id
    ]
    if not region_records:
        return []

    is_table_materialized = any(_record_structure(record).get("row") for record in region_records)
    table_target = record_type in TABLE_RECORD_TYPES

    # Ignore, or any change that keeps the current granularity, is applied in place.
    if record_type == "ignore" or (table_target == is_table_materialized):
        _save_in_place(region_records, record_type, column_mapping)
        return region_records

    # Granularity change: re-materialize the region's records from the grid.
    next_index = (source.records.aggregate(value=Max("record_index"))["value"] or -1) + 1
    if table_target:
        new_records = _promote_to_table(
            source,
            region_records[0],
            record_type=record_type,
            column_mapping=column_mapping,
            start_index=next_index,
        )
    else:
        new_records = _demote_to_context(source, region_records, start_index=next_index)

    SpecificationSourceRecord.objects.filter(pk__in=[record.pk for record in region_records]).delete()
    if new_records:
        SpecificationSourceRecord.objects.bulk_create(new_records)
    return new_records
