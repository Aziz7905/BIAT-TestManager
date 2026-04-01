from dataclasses import dataclass, field
import re


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


COMMON_TITLE_KEYS = [
    "title",
    "summary",
    "name",
    "requirement",
    "requirement_title",
    "story",
    "user_story",
    "scenario",
    "feature",
]
COMMON_REFERENCE_KEYS = [
    "id",
    "key",
    "requirement_id",
    "story_id",
    "ticket",
    "ticket_id",
    "issue_key",
    "qtest_id",
]


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def slugify_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def pick_first_value(row: dict, candidate_keys: list[str]) -> str:
    normalized = {
        slugify_label(str(key)): clean_text(value)
        for key, value in row.items()
        if clean_text(key)
    }
    for key in candidate_keys:
        value = normalized.get(key)
        if value:
            return value
    return ""


def build_title_from_row(row: dict, fallback: str) -> str:
    title = pick_first_value(row, COMMON_TITLE_KEYS)
    return title or fallback


def build_reference_from_row(row: dict) -> str:
    return pick_first_value(row, COMMON_REFERENCE_KEYS)


def row_to_content(row: dict, ignore_keys: list[str] | None = None) -> str:
    ignored = {slugify_label(key) for key in (ignore_keys or [])}
    lines = []

    for key, value in row.items():
        normalized_key = slugify_label(str(key))
        cleaned_value = clean_text(value)
        if not normalized_key or normalized_key in ignored or not cleaned_value:
            continue
        lines.append(f"{key}: {cleaned_value}")

    return "\n".join(lines)


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

