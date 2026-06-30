from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from apps.specs.models import SpecificationSourceType
from apps.specs.services.parsers.registry import get_parser_for_source


MAX_TEMP_ATTACHMENT_CONTENT_CHARS = 1800


@dataclass(frozen=True)
class TemporaryAttachmentContext:
    attachment_id: str
    filename: str
    file_type: str
    fragments: list[dict[str, Any]]
    source_metadata: dict[str, Any]


def extract_temporary_attachment_context(uploaded_file) -> TemporaryAttachmentContext:
    """Extract session-scoped context without creating specs records or indexes."""
    filename = uploaded_file.name.split("/")[-1]
    source_type = _source_type_for_filename(filename)
    source = SimpleNamespace(
        name=filename,
        raw_text="",
        file=uploaded_file,
        source_type=source_type,
    )
    parser = get_parser_for_source(source)
    content_hash = _uploaded_file_hash(uploaded_file)
    parsed = parser.parse(source)
    attachment_id = f"temp_{content_hash[:16]}"
    fragments = []
    for index, record in enumerate(parsed.records):
        metadata = record.record_metadata or {}
        structure = metadata.get("structure") if isinstance(metadata.get("structure"), dict) else {}
        fragments.append(
            {
                "attachment_id": attachment_id,
                "fragment_id": f"{attachment_id}:fragment:{index + 1}",
                "filename": filename,
                "file_type": source_type,
                "title": record.title,
                "content": record.content[:MAX_TEMP_ATTACHMENT_CONTENT_CHARS],
                "external_reference": record.external_reference,
                "section_label": record.section_label,
                "row_number": record.row_number,
                "provenance": {
                    "filename": filename,
                    "file_type": source_type,
                    "sheet": structure.get("container") or record.section_label or "",
                    "cell_range": structure.get("source_range") or "",
                    "region_id": structure.get("region_id") or "",
                    "row_number": record.row_number,
                },
            }
        )
    return TemporaryAttachmentContext(
        attachment_id=attachment_id,
        filename=filename,
        file_type=source_type,
        fragments=fragments,
        source_metadata=parsed.source_metadata,
    )


def _source_type_for_filename(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return SpecificationSourceType.CSV
    if lowered.endswith(".xlsx"):
        return SpecificationSourceType.XLSX
    if lowered.endswith(".pdf"):
        return SpecificationSourceType.PDF
    if lowered.endswith(".docx"):
        return SpecificationSourceType.DOCX
    if lowered.endswith(".txt"):
        return SpecificationSourceType.PLAIN_TEXT
    return SpecificationSourceType.FILE_UPLOAD


def _uploaded_file_hash(uploaded_file) -> str:
    digest = hashlib.sha256()
    digest.update((uploaded_file.name or "").encode("utf-8", errors="ignore"))
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()
