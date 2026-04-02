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


COMMON_TITLE_KEYS = [
    "title",
    "titre",
    "summary",
    "resume",
    "name",
    "nom",
    "intitule",
    "requirement",
    "exigence",
    "requirement_title",
    "titre_exigence",
    "story",
    "user_story",
    "histoire_utilisateur",
    "scenario",
    "scenarion",
    "feature",
    "fonctionnalite",
]
COMMON_REFERENCE_KEYS = [
    "id",
    "identifiant",
    "key",
    "reference",
    "requirement_id",
    "story_id",
    "ticket",
    "ticket_id",
    "issue_key",
    "qtest_id",
    "code",
]

STRUCTURED_FIELD_ALIASES = {
    "reference": COMMON_REFERENCE_KEYS
    + [
        "requirement_code",
        "requirement_ref",
        "reference_exigence",
    ],
    "title": COMMON_TITLE_KEYS
    + [
        "test_name",
        "nom_du_test",
        "nom_test",
    ],
    "type": [
        "type",
        "category",
        "categorie",
        "type_exigence",
        "type_requirement",
    ],
    "description": [
        "description",
        "details",
        "detail",
        "requirement_description",
        "description_exigence",
        "description_requirement",
    ],
    "actor": [
        "actor",
        "acteur",
        "role",
        "utilisateur",
        "persona",
    ],
    "preconditions": [
        "precondition",
        "preconditions",
        "condition_prealable",
        "conditions_prealables",
        "prerequisite",
        "prerequisites",
    ],
    "steps": [
        "step",
        "steps",
        "etape",
        "etapes",
        "procedure",
        "actions",
        "test_steps",
    ],
    "expected_result": [
        "expected_result",
        "expected_results",
        "resultat_attendu",
        "resultats_attendus",
        "expected_outcome",
        "outcome",
    ],
    "priority": [
        "priority",
        "priorite",
        "severity",
        "importance",
    ],
    "version": [
        "version",
        "revision",
        "release",
    ],
    "acceptance_criteria": [
        "acceptance_criteria",
        "acceptance_criterion",
        "critere_acceptation",
        "criteres_acceptation",
        "critere_d_acceptation",
        "criteres_d_acceptation",
    ],
    "module": [
        "module",
        "feature",
        "fonctionnalite",
        "component",
        "composant",
        "composante",
    ],
    "section": [
        "section",
        "rubrique",
        "sheet",
        "feuille",
        "onglet",
    ],
    "url": [
        "url",
        "link",
        "lien",
        "reference_url",
        "url_de_reference",
        "lien_de_reference",
        "documentation_url",
    ],
}

DISPLAY_LABELS = {
    "reference": "ID",
    "title": "Titre",
    "type": "Type",
    "description": "Description",
    "actor": "Acteur",
    "preconditions": "Precondition",
    "steps": "Steps",
    "expected_result": "Expected Result",
    "priority": "Priorite",
    "version": "Version",
    "acceptance_criteria": "Criteres d'acceptation",
    "module": "Module",
    "section": "Section",
    "url": "URL de reference",
}

PREFERRED_CONTENT_ORDER = [
    "reference",
    "title",
    "type",
    "description",
    "actor",
    "preconditions",
    "steps",
    "expected_result",
    "acceptance_criteria",
    "priority",
    "version",
    "url",
]

FRENCH_FIELD_KEYS = {
    "titre",
    "nom",
    "exigence",
    "acteur",
    "priorite",
    "etape",
    "etapes",
    "rubrique",
    "feuille",
    "lien",
    "condition_prealable",
    "conditions_prealables",
    "resultat_attendu",
    "resultats_attendus",
    "critere_acceptation",
    "criteres_acceptation",
}


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def slugify_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")


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


def analyze_row_structure(row: dict) -> dict:
    cleaned_items: list[dict[str, str]] = []
    for key, value in row.items():
        original_key = clean_text(key)
        cleaned_value = clean_text(value)
        if not original_key:
            continue
        cleaned_items.append(
            {
                "original_key": original_key,
                "normalized_key": slugify_label(original_key),
                "value": cleaned_value,
            }
        )

    structured_fields: dict[str, str] = {}
    field_labels: dict[str, str] = {}
    used_keys: set[str] = set()

    for canonical_name, aliases in STRUCTURED_FIELD_ALIASES.items():
        for item in cleaned_items:
            if item["normalized_key"] in aliases and item["value"]:
                structured_fields[canonical_name] = item["value"]
                field_labels[canonical_name] = item["original_key"]
                used_keys.add(item["normalized_key"])
                break

    other_fields = [
        {
            "key": item["original_key"],
            "value": item["value"],
        }
        for item in cleaned_items
        if item["value"] and item["normalized_key"] not in used_keys
    ]

    normalized_keys = {item["normalized_key"] for item in cleaned_items}
    if normalized_keys & FRENCH_FIELD_KEYS:
        language = "fr"
    elif normalized_keys:
        language = "en"
    else:
        language = "unknown"

    return {
        "structured_fields": structured_fields,
        "field_labels": field_labels,
        "other_fields": other_fields,
        "language": language,
    }


def build_title_from_analysis(analysis: dict, fallback: str) -> str:
    structured_fields = analysis["structured_fields"]
    title = structured_fields.get("title") or structured_fields.get("description", "")
    if title:
        if structured_fields.get("reference") and title == structured_fields["reference"]:
            return fallback
        return title[:300]
    return fallback


def build_reference_from_analysis(analysis: dict) -> str:
    return analysis["structured_fields"].get("reference", "")


def row_to_content(row: dict, ignore_keys: list[str] | None = None) -> str:
    ignored = {slugify_label(key) for key in (ignore_keys or [])}
    analysis = analyze_row_structure(row)
    structured_fields = analysis["structured_fields"]
    field_labels = analysis["field_labels"]
    lines: list[str] = []

    for canonical_name in PREFERRED_CONTENT_ORDER:
        if canonical_name in ignored:
            continue
        value = structured_fields.get(canonical_name)
        if not value:
            continue
        label = field_labels.get(canonical_name) or DISPLAY_LABELS[canonical_name]
        lines.append(f"{label}: {value}")

    for item in analysis["other_fields"]:
        normalized_key = slugify_label(item["key"])
        if normalized_key in ignored:
            continue
        lines.append(f"{item['key']}: {item['value']}")

    return "\n".join(lines)


def build_record_from_row(
    row: dict,
    *,
    fallback_title: str,
    default_section_label: str = "",
    row_number: int | None = None,
) -> ParsedSourceRecord:
    analysis = analyze_row_structure(row)
    structured_fields = analysis["structured_fields"]
    section_label = (
        structured_fields.get("section")
        or structured_fields.get("module")
        or default_section_label
    )

    return ParsedSourceRecord(
        title=build_title_from_analysis(analysis, fallback_title),
        content=row_to_content(row, ignore_keys=["title", "summary", "name"]),
        external_reference=build_reference_from_analysis(analysis),
        section_label=section_label,
        row_number=row_number,
        record_metadata={
            "raw_row": row,
            **analysis,
        },
    )


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
