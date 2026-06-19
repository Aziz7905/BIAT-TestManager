from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any

from django.db import models

from apps.testing.models import TestCase, TestScenario, TestSection, TestSuite

CONTRACT_VERSION = "biat_testing_generation_contract_v1"

MODEL_DRAFT_FIELDS: dict[type[models.Model], tuple[str, ...]] = {
    TestSuite: ("name", "description"),
    TestSection: ("name", "order_index"),
    TestScenario: (
        "title",
        "description",
        "scenario_type",
        "priority",
        "business_priority",
        "polarity",
        "ai_confidence",
        "order_index",
    ),
    TestCase: (
        "title",
        "preconditions",
        "steps",
        "expected_result",
        "test_data",
        "jira_issue_key",
        "order_index",
    ),
}

SCHEMA_FIELD_TO_MODEL_FIELD = {
    "confidence": "ai_confidence",
}


@lru_cache(maxsize=1)
def generation_contract() -> dict[str, Any]:
    """Return the BIAT testing model contract used by generation prompts."""
    return {
        "version": CONTRACT_VERSION,
        "draft_schema_version": "ai_generation_draft_v1",
        "models": {
            model.__name__: _model_contract(model, fields)
            for model, fields in MODEL_DRAFT_FIELDS.items()
        },
        "draft_shape": {
            "root": ["summary", "assumptions", "open_questions", "suite", "sections"],
            "suite": ["draft_id", "name", "description"],
            "section": ["draft_id", "name", "order_index", "scenarios", "children"],
            "scenario": [
                "draft_id",
                "title",
                "description",
                "scenario_type",
                "priority",
                "business_priority",
                "polarity",
                "confidence",
                "cases",
            ],
            "case": [
                "draft_id",
                "title",
                "preconditions",
                "steps",
                "expected_result",
                "test_data",
                "source_refs",
                "linked_spec_ids",
                "warnings",
                "coverage",
            ],
            "step": ["step_index", "action", "expected_outcome", "target", "test_data"],
        },
        "rules": [
            "Use only the exact enum values listed in this contract.",
            "Use draft keys exactly as listed; do not invent database field names or UI-only fields.",
            "Do not emit id, project, suite, section, scenario, created_at, updated_at, created_by, ai_generated, version, design_status, automation_status, on_failure, or timeout_ms.",
            "Represent executable test steps as objects with action and expected_outcome.",
            "When a source omits exact messages or alternate outcomes, generate reasonable assumptions instead of blocking.",
        ],
    }


def scenario_expansion_schema() -> dict[str, Any]:
    """JSON schema for one scenario expansion, aligned to the Django choices."""
    scenario_types = choice_values("TestScenario", "scenario_type")
    priorities = choice_values("TestScenario", "priority")
    business_priorities = choice_values("TestScenario", "business_priority")
    polarities = choice_values("TestScenario", "polarity")
    return {
        "type": "object",
        "required": ["scenario"],
        "additionalProperties": False,
        "properties": {
            "scenario": {
                "type": "object",
                "required": [
                    "draft_id",
                    "title",
                    "description",
                    "scenario_type",
                    "priority",
                    "polarity",
                    "cases",
                ],
                "additionalProperties": True,
                "properties": {
                    "draft_id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "scenario_type": {"enum": scenario_types},
                    "priority": {"enum": priorities},
                    "business_priority": {"enum": [None, *business_priorities]},
                    "polarity": {"enum": polarities},
                    "confidence": {"type": ["number", "null"]},
                    "possible_duplicates": {"type": "array"},
                    "cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "draft_id",
                                "title",
                                "preconditions",
                                "steps",
                                "expected_result",
                                "test_data",
                            ],
                            "additionalProperties": True,
                            "properties": {
                                "draft_id": {"type": "string"},
                                "title": {"type": "string"},
                                "preconditions": {"type": "string"},
                                "steps": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["action", "expected_outcome"],
                                        "additionalProperties": True,
                                        "properties": {
                                            "step_index": {"type": "integer"},
                                            "action": {"type": "string"},
                                            "expected_outcome": {"type": "string"},
                                            "target": {"type": "string"},
                                            "test_data": {"type": "object"},
                                            "validation_type": {"type": "string"},
                                            "notes": {"type": "string"},
                                        },
                                    },
                                },
                                "expected_result": {"type": "string"},
                                "test_data": {"type": "object"},
                                "linked_spec_ids": {"type": "array"},
                                "source_refs": {"type": "array"},
                                "warnings": {"type": "array"},
                                "coverage": {"type": "object"},
                            },
                        },
                    },
                },
            }
        },
    }


def choice_values(model_name: str, field_name: str) -> list[str]:
    model_contract = generation_contract()["models"][model_name]
    choices = model_contract["fields"][field_name].get("choices") or []
    return [item["value"] for item in choices]


def contract_for_prompt() -> dict[str, Any]:
    """Return a defensive copy so callers cannot mutate the cached contract."""
    return deepcopy(generation_contract())


def _model_contract(model: type[models.Model], field_names: tuple[str, ...]) -> dict[str, Any]:
    return {
        "db_table": model._meta.db_table,
        "fields": {
            field_name: _field_contract(model, field_name)
            for field_name in field_names
        },
    }


def _field_contract(model: type[models.Model], field_name: str) -> dict[str, Any]:
    field = model._meta.get_field(field_name)
    contract: dict[str, Any] = {
        "field_name": field.name,
        "draft_key": _draft_key(field.name),
        "type": _field_type(field),
        "required": _field_required(field),
    }
    if getattr(field, "max_length", None):
        contract["max_length"] = field.max_length
    if field.choices:
        contract["choices"] = [
            {"value": value, "label": label}
            for value, label in field.choices
        ]
    if field.has_default():
        default = field.default
        if not callable(default):
            contract["default"] = default
    return contract


def _draft_key(field_name: str) -> str:
    for draft_key, model_field in SCHEMA_FIELD_TO_MODEL_FIELD.items():
        if model_field == field_name:
            return draft_key
    return field_name


def _field_required(field: models.Field) -> bool:
    return not bool(getattr(field, "blank", False) or getattr(field, "null", False) or field.has_default())


def _field_type(field: models.Field) -> str:
    if isinstance(field, models.CharField):
        return "string"
    if isinstance(field, models.TextField):
        return "string"
    if isinstance(field, models.IntegerField):
        return "integer"
    if isinstance(field, models.FloatField):
        return "number"
    if isinstance(field, models.JSONField):
        return "json"
    return field.get_internal_type()
