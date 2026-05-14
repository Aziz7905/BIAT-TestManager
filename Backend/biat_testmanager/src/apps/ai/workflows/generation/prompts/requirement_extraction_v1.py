from __future__ import annotations

import json
from typing import Any

EXTRACTION_PROMPT_VERSION = "requirement_extraction_v1"

REQUIREMENT_TYPES = [
    "ui_flow",
    "batch_job",
    "api",
    "data_processing",
    "integration",
    "reporting",
    "security_access_control",
    "validation_rules",
    "unknown",
]

REQUIREMENT_EXTRACTION_FIELDS = [
    "actors",
    "business_entities",
    "source_entities",
    "target_entities",
    "screens",
    "apis",
    "files_or_reports",
    "fields",
    "filters",
    "grouping_rules",
    "sorting_rules",
    "calculations",
    "business_rules",
    "validation_rules",
    "update_rules",
    "generated_outputs",
    "notifications",
    "error_conditions",
    "acceptance_criteria",
    "test_data_hints",
    "open_questions",
]

REQUIREMENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["requirement_type", "system_or_process_name", *REQUIREMENT_EXTRACTION_FIELDS],
    "properties": {
        "requirement_type": {"enum": REQUIREMENT_TYPES},
        "system_or_process_name": {"type": "string"},
        **{
            field_name: {
                "type": "array",
                "items": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "object"},
                    ]
                },
            }
            for field_name in REQUIREMENT_EXTRACTION_FIELDS
        },
    },
}


def empty_requirement_extraction() -> dict[str, Any]:
    return {
        "requirement_type": "unknown",
        "system_or_process_name": "",
        **{field_name: [] for field_name in REQUIREMENT_EXTRACTION_FIELDS},
    }


def normalize_requirement_extraction(payload: Any) -> dict[str, Any]:
    extraction = empty_requirement_extraction()
    if not isinstance(payload, dict):
        return extraction

    requirement_type = str(payload.get("requirement_type") or "").strip()
    if requirement_type in REQUIREMENT_TYPES:
        extraction["requirement_type"] = requirement_type
    extraction["system_or_process_name"] = str(
        payload.get("system_or_process_name") or ""
    ).strip()
    for field_name in REQUIREMENT_EXTRACTION_FIELDS:
        value = payload.get(field_name)
        extraction[field_name] = value if isinstance(value, list) else []
    return extraction


def build_requirement_extraction_messages(
    *,
    objective: str,
    project_name: str,
    rag_context: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
) -> list[dict[str, str]]:
    context = {
        "project": project_name,
        "rag_context": rag_context,
        "repository_memory": repository_memory,
    }
    return [
        {
            "role": "system",
            "content": (
                "Extract concrete requirement facts for BIAT TestManager. This step is "
                "generic: infer facts only from the objective and supplied context. Do "
                "not invent application-specific names, tables, fields, screens, files, "
                "or business rules. Classify the requirement as one of the allowed "
                f"types: {', '.join(REQUIREMENT_TYPES)}.\n\n"
                "Preserve exact identifiers and domain terms from the context. Do not "
                "summarize away names of fields, tables, screens, APIs, jobs, reports, "
                "files, filters, output columns, update rules, counts, thresholds, or "
                "durations. If multiple requirement records are present, extract facts "
                "from all records instead of focusing only on the first one.\n\n"
                "Return strict JSON using the provided schema. Use arrays for all fact "
                "lists. Facts may be strings or small objects when a rule needs fields "
                "such as source, condition, value, or expected output."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Objective:\n{objective}\n\n"
                "Grounding context JSON:\n"
                f"{json.dumps(context, ensure_ascii=True, default=str)}"
            ),
        },
    ]
