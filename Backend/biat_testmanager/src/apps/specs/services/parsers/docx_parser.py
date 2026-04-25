from dataclasses import dataclass, field
import re

from .base import ParsedSourceRecord, ParsedSourceResult, SpecificationSourceParseError, split_text_into_records


TOP_LEVEL_HEADING_RE = re.compile(r"^\d+\s*[/\-.:)]\s*")
REFERENCE_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:\.[A-Z0-9]+){2,}\b")
BULLET_PREFIX_RE = re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219\-\*\u00B7]+\s*")
HEADING_STYLE_RE = re.compile(r"heading\s*(\d+)?", re.IGNORECASE)


@dataclass
class _DocumentBlock:
    kind: str
    text: str = ""
    style_name: str = ""
    table_rows: list[str] = field(default_factory=list)


@dataclass
class _StructuredRecordDraft:
    parent_heading: str = ""
    subheading: str = ""
    body_lines: list[str] = field(default_factory=list)
    table_lines: list[str] = field(default_factory=list)


class DOCXSpecificationSourceParser:
    def parse(self, source):
        if not source.file:
            raise SpecificationSourceParseError("A DOCX file is required.")

        try:
            from docx import Document
        except ImportError as error:
            raise SpecificationSourceParseError(
                "DOCX parsing requires the python-docx package."
            ) from error

        document = Document(source.file)
        source.file.seek(0)

        blocks = list(_iter_document_blocks(document))
        paragraphs = [block.text for block in blocks if block.kind == "paragraph" and block.text]
        text = "\n\n".join(paragraphs)

        records = _build_structured_records(blocks, default_title=source.name)
        parse_strategy = "structured_docx"
        if not records:
            parse_strategy = "text_section"
            records = split_text_into_records(
                text,
                default_title=source.name,
                section_label="Document",
            )

        return ParsedSourceResult(
            records=records,
            source_metadata={
                "filename": source.file.name.split("/")[-1],
                "format": "docx",
                "paragraph_count": len(paragraphs),
                "table_count": sum(1 for block in blocks if block.kind == "table"),
                "latest_parse_strategy": parse_strategy,
            },
        )


def _iter_document_blocks(document):
    from docx.document import Document as DocumentObject
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    parent_elm = document.element.body if isinstance(document, DocumentObject) else document._element

    for child in parent_elm.iterchildren():
        if child.tag.endswith("}p"):
            paragraph = Paragraph(child, document)
            text = _clean_text(paragraph.text)
            if text:
                yield _DocumentBlock(
                    kind="paragraph",
                    text=text,
                    style_name=paragraph.style.name if paragraph.style is not None else "",
                )
        elif child.tag.endswith("}tbl"):
            table = Table(child, document)
            rows = _table_to_lines(table)
            if rows:
                yield _DocumentBlock(kind="table", table_rows=rows)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def _normalize_bullet(text: str) -> str:
    normalized = BULLET_PREFIX_RE.sub("", text).strip()
    return f"- {normalized}" if normalized else ""


def _looks_like_top_heading(text: str) -> bool:
    return bool(TOP_LEVEL_HEADING_RE.match(text))


def _extract_heading_level(style_name: str) -> int | None:
    normalized = (style_name or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"title", "titre"}:
        return 0
    match = HEADING_STYLE_RE.search(normalized)
    if match:
        return int(match.group(1) or 1)
    return None


def _looks_like_subheading(text: str, *, current_parent_heading: str) -> bool:
    if not current_parent_heading:
        return False
    if _looks_like_top_heading(text):
        return False
    if BULLET_PREFIX_RE.match(text):
        return False
    if len(text) > 90:
        return False
    if text.endswith((".", ";", ":")):
        return False

    words = [word for word in text.split() if word]
    if not words or len(words) > 4:
        return False

    has_uppercase_word = any(word.isupper() and len(word) > 1 for word in words)
    titleish = all(word[:1].isupper() or word.isupper() for word in words)
    return has_uppercase_word or titleish


def _classify_heading(text: str, style_name: str, *, current_parent_heading: str) -> str:
    heading_level = _extract_heading_level(style_name)
    if heading_level in {0, 1}:
        return "top"
    if heading_level and heading_level >= 2:
        return "sub" if current_parent_heading else "top"
    if _looks_like_top_heading(text):
        return "top"
    if _looks_like_subheading(text, current_parent_heading=current_parent_heading):
        return "sub"
    return ""


def _is_bullet_like(text: str, style_name: str) -> bool:
    if BULLET_PREFIX_RE.match(text):
        return True
    normalized_style = (style_name or "").strip().lower()
    return normalized_style.startswith("list")


def _table_to_lines(table) -> list[str]:
    rows: list[list[str]] = []
    for row in table.rows:
        values = [_clean_table_cell(cell.text) for cell in row.cells]
        values = [value for value in values if value]
        if not values:
            continue
        rows.append(values)

    if not rows:
        return []

    if all(len(row) == 1 for row in rows):
        return [row[0] for row in rows]

    if _looks_like_key_value_table(rows):
        return [
            row[0] if len(row) == 1 else f"{row[0]}: {row[1]}"
            for row in rows
        ]

    if _looks_like_header_table(rows):
        header_row = rows[0]
        body_rows = rows[1:]
        return [f"Columns: {' | '.join(header_row)}"] + [
            " | ".join(row)
            for row in body_rows
            if any(row)
        ]

    return [" | ".join(row) for row in rows]


def _clean_table_cell(value: str) -> str:
    text = _clean_text(value).strip("\"' ")
    markerless = re.sub(r"[=\-!_~|.\s]+", "", text)
    if not markerless:
        return ""
    return text


def _looks_like_key_value_table(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    two_column_rows = [row for row in rows if len(row) == 2]
    return len(two_column_rows) >= max(2, len(rows) - 1)


def _looks_like_header_table(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    header_width = len(rows[0])
    if header_width < 2:
        return False
    if not all(len(row) == header_width for row in rows[1:]):
        return False
    return all(len(cell) <= 40 for cell in rows[0])


def _extract_reference(*values: str) -> str:
    for value in values:
        match = REFERENCE_RE.search(value or "")
        if match:
            return match.group(0)
    return ""


def _make_record_title(parent_heading: str, subheading: str, fallback: str) -> str:
    return (subheading or parent_heading or fallback)[:300]


def _make_record_content(draft: _StructuredRecordDraft) -> str:
    lines: list[str] = []

    if draft.parent_heading and draft.subheading:
        lines.append(f"Contexte: {draft.parent_heading}")
        lines.append("")
    elif draft.parent_heading:
        lines.append(draft.parent_heading)
        lines.append("")

    lines.extend(draft.body_lines)

    if draft.table_lines:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append("Table:")
        lines.extend(f"- {line}" for line in draft.table_lines)

    return "\n".join(line for line in lines if line is not None).strip()


def _build_record_from_draft(
    draft: _StructuredRecordDraft,
    *,
    default_title: str,
    row_number: int,
) -> ParsedSourceRecord | None:
    if not draft.body_lines and not draft.table_lines:
        return None

    content = _make_record_content(draft)
    if not content:
        return None

    title = _make_record_title(draft.parent_heading, draft.subheading, default_title)
    section_label = draft.subheading or draft.parent_heading or "Document"

    return ParsedSourceRecord(
        title=title,
        content=content,
        external_reference=_extract_reference(draft.parent_heading, draft.subheading, title),
        section_label=section_label,
        row_number=row_number,
        record_metadata={
            "source_mode": "structured_docx",
            "parent_heading": draft.parent_heading,
            "subheading": draft.subheading,
            "table_row_count": len(draft.table_lines),
        },
    )


def _build_structured_records(blocks: list[_DocumentBlock], *, default_title: str) -> list[ParsedSourceRecord]:
    if not blocks:
        return []

    structured_document = any(
        block.kind == "table"
        or _looks_like_top_heading(block.text)
        or _extract_heading_level(block.style_name) is not None
        or _is_bullet_like(block.text, block.style_name)
        for block in blocks
    )
    if not structured_document:
        return []

    records: list[ParsedSourceRecord] = []
    current_parent_heading = ""
    current_draft = _StructuredRecordDraft()

    def flush_current_draft():
        nonlocal current_draft
        record = _build_record_from_draft(
            current_draft,
            default_title=default_title,
            row_number=len(records) + 1,
        )
        if record is not None:
            records.append(record)
        current_draft = _StructuredRecordDraft(parent_heading=current_parent_heading)

    for block in blocks:
        if block.kind == "paragraph":
            text = block.text
            heading_kind = _classify_heading(
                text,
                block.style_name,
                current_parent_heading=current_parent_heading,
            )
            if heading_kind == "top":
                flush_current_draft()
                current_parent_heading = text
                current_draft = _StructuredRecordDraft(parent_heading=current_parent_heading)
                continue

            if heading_kind == "sub":
                flush_current_draft()
                current_draft = _StructuredRecordDraft(
                    parent_heading=current_parent_heading,
                    subheading=text,
                )
                continue

            normalized_line = _normalize_bullet(text) if _is_bullet_like(text, block.style_name) else text
            if normalized_line:
                current_draft.body_lines.append(normalized_line)
            continue

        if block.kind == "table":
            current_draft.table_lines.extend(block.table_rows)

    flush_current_draft()
    return records
