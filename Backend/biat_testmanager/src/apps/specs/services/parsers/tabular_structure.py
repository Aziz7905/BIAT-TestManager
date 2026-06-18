"""Format-agnostic structural extraction for tabular specification sources.

This module performs *faithful* structural extraction only. It detects the
layout of a 2D grid (tables, key/value blocks, lists, text) using general
shape signals — empty-row/column boundaries, populated rectangles, row-width
consistency, and a structural header *candidate*. It never tries to understand
business meaning: there is no classification into requirement/test-case tables,
no confidence scoring, no field-alias matching, and no language detection.

Both the XLSX and CSV parsers build a grid of :class:`GridCell` and feed it
through :func:`segment_regions` + :func:`build_records_for_region`. Assigning
business meaning to a region (requirement vs. test case, which column is the
external id, ...) is the user's job, done later via the review/mapping flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .base import ParsedSourceRecord, clean_text, slugify_label

# Structural region types describe *layout*, not business meaning.
STRUCTURAL_TABLE = "table"
STRUCTURAL_KEY_VALUE = "key_value_block"
STRUCTURAL_LIST = "list"
STRUCTURAL_TEXT = "text_block"
STRUCTURAL_UNKNOWN = "unknown"

MAX_HEADER_LABEL_CHARS = 60


@dataclass(frozen=True)
class GridCell:
    """A single cell, preserving its source coordinates and raw content."""

    row: int
    column: int
    coordinate: str
    raw_value: str
    displayed_value: str = ""
    formula: str = ""
    merged: bool = False
    hidden_row: bool = False
    hidden_column: bool = False

    @property
    def is_hidden(self) -> bool:
        return self.hidden_row or self.hidden_column

    @property
    def value(self) -> str:
        """Readable value used for structure detection and content building.

        Hidden cells are treated as empty for layout purposes but their raw
        value is still preserved on the dataclass for faithful inspection.
        """
        if self.is_hidden:
            return ""
        return self.displayed_value or self.raw_value


@dataclass
class StructuralRegion:
    region_id: str
    container: str
    cells: list[list[GridCell]] = field(default_factory=list)

    @property
    def rows(self) -> list[list[str]]:
        return [[cell.value for cell in row] for row in self.cells]

    @property
    def source_range(self) -> str:
        start = self.cells[0][0].coordinate
        end = self.cells[-1][-1].coordinate
        return start if start == end else f"{start}:{end}"


def column_to_letter(column: int) -> str:
    """Convert a 1-based column index to its spreadsheet letter (1 -> A)."""
    letters = ""
    while column > 0:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters or "A"


def trim_empty_grid(grid: list[list[GridCell]]) -> list[list[GridCell]]:
    """Drop trailing/leading empty rows and columns from a grid."""
    if not grid:
        return []

    non_empty_rows = [
        index for index, row in enumerate(grid) if any(cell.value for cell in row)
    ]
    if not non_empty_rows:
        return []

    width = max(len(row) for row in grid)
    non_empty_columns = [
        index
        for index in range(width)
        if any(index < len(row) and row[index].value for row in grid)
    ]
    if not non_empty_columns:
        return []

    row_start, row_end = min(non_empty_rows), max(non_empty_rows)
    column_start, column_end = min(non_empty_columns), max(non_empty_columns)
    return [row[column_start : column_end + 1] for row in grid[row_start : row_end + 1]]


def segment_regions(grid: list[list[GridCell]], *, container: str) -> list[StructuralRegion]:
    """Split a grid into populated rectangles separated by empty rows/columns."""
    regions: list[StructuralRegion] = []

    row_groups = _contiguous_groups(
        [index for index, row in enumerate(grid) if any(cell.value for cell in row)]
    )
    for row_group in row_groups:
        row_cells = [grid[index] for index in row_group]
        width = max((len(row) for row in row_cells), default=0)
        column_groups = _contiguous_groups(
            [
                index
                for index in range(width)
                if any(index < len(row) and row[index].value for row in row_cells)
            ]
        )
        for column_group in column_groups:
            region_cells = [
                [row[index] for index in column_group if index < len(row)]
                for row in row_cells
            ]
            region_cells = [row for row in region_cells if any(cell.value for cell in row)]
            if not region_cells:
                continue
            start = region_cells[0][0].coordinate
            end = region_cells[-1][-1].coordinate
            source_range = start if start == end else f"{start}:{end}"
            regions.append(
                StructuralRegion(
                    region_id=f"{container}!{source_range}",
                    container=container,
                    cells=region_cells,
                )
            )

    return regions


def detect_header_candidates(region: StructuralRegion) -> list[dict]:
    """Return structural header candidates (0 or 1) for a region.

    A row is a header *candidate* — not an authoritative header — when it looks
    like a row of labels: at least two non-empty cells, all short, all distinct,
    and none purely numeric. This is structural only; the user confirms which
    columns mean what during mapping.
    """
    for local_index, row in enumerate(region.cells):
        values = [cell.value for cell in row]
        if not _is_header_candidate(values):
            continue
        return [
            {
                "local_index": local_index,
                "row": row[0].row,
                "values": values,
                "coordinates": [cell.coordinate for cell in row],
            }
        ]
    return []


def classify_structure(region: StructuralRegion, header_candidates: list[dict]) -> str:
    """Classify a region by *shape* only — never by business meaning."""
    rows = region.rows
    populated_rows = [row for row in rows if any(row)]
    row_count = len(populated_rows)
    column_count = max((len(row) for row in rows), default=0)

    if row_count == 0 or column_count == 0:
        return STRUCTURAL_UNKNOWN

    if column_count == 1:
        return STRUCTURAL_TEXT if row_count == 1 else STRUCTURAL_LIST

    widths = [sum(1 for value in row if value) for row in populated_rows]
    width_consistency = _modal_share(widths)
    has_header = bool(header_candidates)

    # A two-column region is structurally indistinguishable between a real
    # two-column table (id | requirement) and a key/value block (scope | text):
    # both are N rows of paired cells. There is no reliable shape signal to tell
    # them apart, so we default to a key/value block, which is non-destructive
    # (one faithful "key: value" record). Guessing "table" is destructive — it
    # splits rows under a false header and cannot be cleanly undone. The user
    # can re-type a region when they genuinely need per-row table records.
    if column_count == 2 and _is_key_value_block(widths, row_count):
        return STRUCTURAL_KEY_VALUE

    if row_count >= 2 and (has_header or width_consistency >= 0.6):
        return STRUCTURAL_TABLE

    return STRUCTURAL_TEXT if row_count == 1 else STRUCTURAL_UNKNOWN


def _is_key_value_block(widths: list[int], row_count: int) -> bool:
    two_cell_share = sum(1 for width in widths if width == 2) / row_count
    return two_cell_share >= 0.6


def build_records_for_region(region: StructuralRegion) -> tuple[list[ParsedSourceRecord], dict]:
    """Produce faithful review candidates for a region (no semantic labels)."""
    header_candidates = detect_header_candidates(region)
    structural_type = classify_structure(region, header_candidates)

    region_metadata = {
        "region_id": region.region_id,
        "container": region.container,
        "structural_type": structural_type,
        "source_range": region.source_range,
        "header_candidates": [
            {"row": candidate["row"], "values": candidate["values"]}
            for candidate in header_candidates
        ],
    }

    structure_base = {
        "region_id": region.region_id,
        "container": region.container,
        "structural_type": structural_type,
        "source_range": region.source_range,
        "header_candidates": region_metadata["header_candidates"],
    }

    if structural_type == STRUCTURAL_TABLE:
        records = _build_table_records(region, header_candidates, structure_base)
    else:
        records = [_build_context_record(region, structural_type, structure_base)]

    return records, region_metadata


def _build_table_records(
    region: StructuralRegion,
    header_candidates: list[dict],
    structure_base: dict,
) -> list[ParsedSourceRecord]:
    header = header_candidates[0] if header_candidates else None
    header_values = header["values"] if header else []
    header_local_index = header["local_index"] if header else -1

    records: list[ParsedSourceRecord] = []
    for local_index, row in enumerate(region.cells):
        if local_index <= header_local_index:
            continue
        values = [cell.value for cell in row]
        if not any(values):
            continue
        if header_values and _is_repeated_header(values, header_values):
            continue

        content = _row_to_content(row, header_values)
        row_number = row[0].row
        structure = dict(structure_base)
        structure["row"] = {
            "row_number": row_number,
            "source_range": _cells_range(row),
            "cells": [
                {
                    "coordinate": cell.coordinate,
                    "column": cell.column,
                    "column_letter": column_to_letter(cell.column),
                    "raw_value": cell.raw_value,
                    "displayed_value": cell.displayed_value or cell.raw_value,
                    "formula": cell.formula,
                    "merged": cell.merged,
                    "header_candidate": _label_for_column(header_values, index, cell.column),
                }
                for index, cell in enumerate(row)
                if cell.value or cell.raw_value or cell.formula
            ],
        }

        records.append(
            ParsedSourceRecord(
                title=f"{region.container} row {row_number}",
                content=content,
                external_reference="",
                section_label=region.container,
                row_number=row_number,
                is_selected=False,
                record_metadata={
                    "source_mode": "structural_table_row",
                    "structure": structure,
                    "review": _review_block(needs_mapping=True),
                    "validation": _validation_for(content),
                },
            )
        )

    return records


def _build_context_record(
    region: StructuralRegion,
    structural_type: str,
    structure_base: dict,
) -> ParsedSourceRecord:
    content = _region_to_content(region, structural_type)
    title = _context_title(content, structural_type, region.source_range)
    structure = dict(structure_base)
    # Keep the full grid so the region can later be re-typed into a per-row table.
    structure["grid"] = serialize_grid(region)
    return ParsedSourceRecord(
        title=title,
        content=content,
        external_reference="",
        section_label=region.container,
        row_number=region.cells[0][0].row,
        is_selected=bool(content),
        record_metadata={
            "source_mode": "structural_region",
            "structure": structure,
            "review": _review_block(
                needs_mapping=False,
                confirmed=True,
                record_type="context",
            ),
            "validation": _validation_for(content),
        },
    )


def serialize_grid(region: StructuralRegion) -> list[list[dict]]:
    return [
        [
            {
                "coordinate": cell.coordinate,
                "row": cell.row,
                "column": cell.column,
                "column_letter": column_to_letter(cell.column),
                "raw_value": cell.raw_value,
                "displayed_value": cell.displayed_value or cell.raw_value,
                "formula": cell.formula,
                "merged": cell.merged,
            }
            for cell in row
        ]
        for row in region.cells
    ]


def _review_block(
    *,
    needs_mapping: bool,
    confirmed: bool = False,
    record_type: str | None = None,
) -> dict:
    return {
        "needs_mapping": needs_mapping,
        "confirmed": confirmed,
        "record_type": record_type,
        "column_mapping": {},
    }


def _validation_for(content: str) -> dict:
    fatal_errors = [] if clean_text(content) else ["Region has no readable content."]
    return {"fatal_errors": fatal_errors, "warnings": []}


def _row_to_content(row: list[GridCell], header_values: list[str]) -> str:
    lines: list[str] = []
    for index, cell in enumerate(row):
        value = cell.value
        if not value:
            continue
        label = _label_for_column(header_values, index, cell.column)
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def _label_for_column(header_values: list[str], index: int, column: int) -> str:
    if header_values and index < len(header_values) and header_values[index]:
        return header_values[index]
    return f"Column {column_to_letter(column)}"


def _region_to_content(region: StructuralRegion, structural_type: str) -> str:
    lines: list[str] = []
    for row in region.cells:
        values = [cell.value for cell in row if cell.value]
        if not values:
            continue
        if structural_type == STRUCTURAL_KEY_VALUE and len(values) == 2:
            lines.append(f"{values[0]}: {values[1]}")
        else:
            lines.append(" | ".join(values))
    return "\n".join(lines)


def _context_title(content: str, structural_type: str, source_range: str) -> str:
    first_line = next((line.strip() for line in content.splitlines() if line.strip()), "")
    if first_line:
        return first_line[:300]
    return f"{structural_type.replace('_', ' ').title()} {source_range}"


def _cells_range(row: list[GridCell]) -> str:
    non_empty = [cell for cell in row if cell.value] or row
    start = non_empty[0].coordinate
    end = non_empty[-1].coordinate
    return start if start == end else f"{start}:{end}"


def _is_header_candidate(values: list[str]) -> bool:
    non_empty = [value for value in values if value]
    if len(non_empty) < 2:
        return False
    if any(len(value) > MAX_HEADER_LABEL_CHARS for value in non_empty):
        return False
    if any(_is_numeric(value) for value in non_empty):
        return False
    slugs = [slugify_label(value) for value in non_empty]
    return len(set(slugs)) == len(slugs)


def _is_repeated_header(values: list[str], header_values: list[str]) -> bool:
    row_slugs = {slugify_label(value) for value in values if value}
    header_slugs = {slugify_label(value) for value in header_values if value}
    if len(row_slugs) < 2 or len(header_slugs) < 2:
        return False
    overlap = len(row_slugs & header_slugs) / max(len(row_slugs), 1)
    return overlap >= 0.8


def _is_numeric(value: str) -> bool:
    candidate = clean_text(value).replace(",", "").replace(".", "").replace("-", "").replace("/", "").replace(" ", "")
    return bool(candidate) and candidate.isdigit()


def _modal_share(widths: list[int]) -> float:
    if not widths:
        return 0.0
    most_common = max(widths.count(width) for width in set(widths))
    return most_common / len(widths)


def _contiguous_groups(indexes: list[int]) -> list[list[int]]:
    if not indexes:
        return []
    groups = [[indexes[0]]]
    for index in indexes[1:]:
        if index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    return groups
