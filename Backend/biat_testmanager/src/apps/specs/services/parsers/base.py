from dataclasses import dataclass, field
import re
import unicodedata


class SpecificationSourceParseError(Exception):
    pass


@dataclass
class ParsedSourceRecord:
    title: str
    content: str
    external_reference: str = ""
    section_label: str = ""
    row_number: int | None = None
    record_metadata: dict = field(default_factory=dict)
    is_selected: bool = True


@dataclass
class ParsedSourceResult:
    records: list[ParsedSourceRecord]
    source_metadata: dict = field(default_factory=dict)
    column_mapping: dict = field(default_factory=dict)


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def slugify_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


def split_text_into_records(
    text: str,
    *,
    default_title: str,
    section_label: str = "",
) -> list[ParsedSourceRecord]:
    normalized = text.strip()
    if not normalized:
        return []

    sections = [section.strip() for section in re.split(r"\n\s*\n", normalized) if section.strip()]
    if not sections:
        sections = [normalized]

    records: list[ParsedSourceRecord] = []
    for index, section in enumerate(sections):
        first_line = next((line.strip() for line in section.splitlines() if line.strip()), "")
        title = first_line[:300] if first_line else f"{default_title} {index + 1}"
        records.append(
            ParsedSourceRecord(
                title=title or default_title,
                content=section,
                section_label=section_label,
                row_number=index + 1,
                record_metadata={"source_mode": "text_section"},
            )
        )
    return records
