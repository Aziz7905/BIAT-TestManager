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

HEADER_SIGNAL_KEYS = {
    alias
    for aliases in STRUCTURED_FIELD_ALIASES.values()
    for alias in aliases
}

GENERIC_REFERENCE_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:[._/\-][A-Z0-9]+){1,}\b")

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
    first_other_value = next(
        (
            item["value"]
            for item in analysis["other_fields"]
            if item["value"]
        ),
        "",
    )
    if first_other_value:
        return first_other_value[:300]
    return fallback


def build_reference_from_analysis(analysis: dict) -> str:
    reference = analysis["structured_fields"].get("reference", "")
    if reference:
        return reference

    for candidate in [
        analysis["structured_fields"].get("title", ""),
        analysis["structured_fields"].get("description", ""),
        *[item["value"] for item in analysis["other_fields"]],
    ]:
        match = GENERIC_REFERENCE_RE.search(candidate or "")
        if match:
            return match.group(0)
    return ""


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
        if normalized_key.startswith("column_"):
            lines.append(item["value"])
        else:
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
    title_value = structured_fields.get("title", "")
    module_value = structured_fields.get("module", "")
    section_label = (
        structured_fields.get("section")
        or (module_value if module_value and module_value != title_value else "")
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


def _looks_numeric_like(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    candidate = normalized.replace(",", "").replace(".", "").replace("-", "").replace("/", "")
    return candidate.isdigit()


def _score_header_candidate(row_values: list[str]) -> float:
    non_empty_values = [value for value in row_values if value]
    if len(non_empty_values) < 2:
        return float("-inf")

    normalized_values = [slugify_label(value) for value in non_empty_values]
    alias_hits = sum(1 for value in normalized_values if value in HEADER_SIGNAL_KEYS)
    numeric_hits = sum(1 for value in non_empty_values if _looks_numeric_like(value))
    unique_ratio = len(set(normalized_values)) / max(len(normalized_values), 1)
    average_length = sum(len(value) for value in non_empty_values) / max(len(non_empty_values), 1)

    score = alias_hits * 4
    score += len(non_empty_values) * 0.6
    score += unique_ratio

    if average_length <= 40:
        score += 1
    elif average_length >= 90:
        score -= 2

    score -= numeric_hits * 1.5
    if any(len(value) > 140 for value in non_empty_values):
        score -= 2

    return score


def detect_tabular_header_row(tabular_rows: list[list[str]], *, scan_limit: int = 12) -> tuple[int, bool]:
    best_index = -1
    best_score = float("-inf")

    for index, row_values in enumerate(tabular_rows[:scan_limit]):
        score = _score_header_candidate(row_values)
        if score > best_score:
            best_index = index
            best_score = score

    if best_index >= 0 and best_score >= 4:
        return best_index, True

    for index, row_values in enumerate(tabular_rows):
        if any(row_values):
            return index, False

    return 0, False


def build_unique_headers(row_values: list[str]) -> list[str]:
    headers: list[str] = []
    seen: dict[str, int] = {}

    for index, value in enumerate(row_values):
        base_value = clean_text(value) or f"column_{index + 1}"
        normalized = slugify_label(base_value) or f"column_{index + 1}"
        duplicate_count = seen.get(normalized, 0)
        seen[normalized] = duplicate_count + 1

        if duplicate_count:
            headers.append(f"{base_value}_{duplicate_count + 1}")
        else:
            headers.append(base_value)

    return headers


def extend_headers(headers: list[str], required_length: int) -> list[str]:
    extended = list(headers)
    while len(extended) < required_length:
        extended.append(f"column_{len(extended) + 1}")
    return extended


def is_repeated_header_row(row_values: list[str], headers: list[str]) -> bool:
    row_keys = {slugify_label(value) for value in row_values if value}
    header_keys = {slugify_label(header) for header in headers if header}

    if len(row_keys) < 2 or len(header_keys) < 2:
        return False

    overlap = len(row_keys & header_keys) / max(len(row_keys), 1)
    return overlap >= 0.8


def extract_section_context(row_values: list[str]) -> str:
    non_empty_values = [value for value in row_values if value]
    if len(non_empty_values) != 1:
        return ""

    candidate = non_empty_values[0]
    if len(candidate) > 180:
        return ""
    if _looks_numeric_like(candidate):
        return ""
    if GENERIC_REFERENCE_RE.fullmatch(candidate):
        return ""
    if candidate.endswith((".", ";")):
        return ""
    if ":" in candidate and len(candidate.split()) > 6:
        return ""
    return candidate


def build_records_from_tabular_rows(
    tabular_rows: list[list[object]],
    *,
    fallback_title_prefix: str,
    default_section_label: str = "",
) -> tuple[list[ParsedSourceRecord], list[str], int | None, bool]:
    indexed_rows = [
        (index + 1, [clean_text(value) for value in row])
        for index, row in enumerate(tabular_rows)
    ]
    non_empty_rows = [
        (row_number, row_values)
        for row_number, row_values in indexed_rows
        if any(row_values)
    ]
    if not non_empty_rows:
        return [], [], None, False

    header_row_index, has_explicit_header = detect_tabular_header_row(
        [row_values for _, row_values in non_empty_rows]
    )

    if has_explicit_header:
        headers = build_unique_headers(non_empty_rows[header_row_index][1])
        data_rows = non_empty_rows[header_row_index + 1 :]
    else:
        max_width = max(len(row_values) for _, row_values in non_empty_rows)
        headers = [f"column_{index + 1}" for index in range(max_width)]
        data_rows = non_empty_rows[header_row_index:]

    records: list[ParsedSourceRecord] = []
    languages: set[str] = set()
    current_section_label = default_section_label

    for row_number, row_values in data_rows:
        if not any(row_values):
            continue

        effective_headers = extend_headers(headers, len(row_values))
        if has_explicit_header and is_repeated_header_row(row_values, effective_headers):
            continue

        inline_section_label = extract_section_context(row_values)
        if inline_section_label:
            current_section_label = inline_section_label
            continue

        row = {
            effective_headers[index]: row_values[index] if index < len(row_values) else ""
            for index in range(len(effective_headers))
        }

        record = build_record_from_row(
            row,
            fallback_title=f"{fallback_title_prefix} row {row_number}",
            default_section_label=current_section_label,
            row_number=row_number,
        )
        record.record_metadata.update(
            {
                "source_mode": "tabular_row",
                "tabular_header_row": non_empty_rows[header_row_index][0] if has_explicit_header else None,
                "has_explicit_header": has_explicit_header,
                "context_section_label": current_section_label,
            }
        )
        languages.add(record.record_metadata.get("language", "unknown"))
        records.append(record)

    visible_headers = [
        header
        for header in headers
        if header and not slugify_label(header).startswith("column_")
    ]
    return records, sorted(language for language in languages if language), visible_headers, (
        non_empty_rows[header_row_index][0] if has_explicit_header else None
    )
