from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from django.db import transaction

from apps.specs.models import SpecItem, SpecItemType, SpecSet, SpecSetType


KNOWN_FIELD_KEYS = {
    "external_id",
    "external_key",
    "title",
    "name",
    "summary",
    "module",
    "feature",
    "section",
    "description",
    "acceptance_criteria",
    "business_rule",
    "validation_rule",
    "user_story",
    "priority",
    "status",
    "type",
    "parent_external_id",
    "preconditions",
    "steps",
    "expected_result",
    "test_data",
    "linked_requirement_key",
}

ITEM_TYPE_BY_RECORD_TYPE = {
    "requirement": SpecItemType.REQUIREMENT,
    "test_case": SpecItemType.TEST_CASE,
    "test_data": SpecItemType.TEST_DATA,
    "context": SpecItemType.CONTEXT,
}

ITEM_TYPE_BY_FIELD = {
    "acceptance_criteria": SpecItemType.ACCEPTANCE_CRITERION,
    "business_rule": SpecItemType.BUSINESS_RULE,
    "validation_rule": SpecItemType.VALIDATION_RULE,
    "user_story": SpecItemType.USER_STORY,
}


def import_record_to_spec_item(record, specification) -> SpecItem:
    fields = _labelled_fields(record.content)
    review = (record.record_metadata or {}).get("review") or {}
    record_type = str(review.get("record_type") or "").strip()
    item_type = _item_type_for(record_type, fields)
    external_key = _first_value(fields, "external_id", "external_key") or record.external_reference or ""
    title = _first_value(fields, "title", "name", "summary") or record.title
    module = _first_value(fields, "module") or record.section_label or ""
    feature = _first_value(fields, "feature", "section")
    priority = _first_value(fields, "priority")
    status = _first_value(fields, "status")
    parent_external_key = _first_value(fields, "parent_external_id")

    item, _created = SpecItem.objects.update_or_create(
        source_record=record,
        defaults={
            "project": record.source.project,
            "source": record.source,
            "specification": specification,
            "external_key": external_key[:160],
            "item_type": item_type,
            "title": title[:300] or f"{record.source.name} record {record.record_index + 1}",
            "content": record.content,
            "module": module[:200],
            "feature": feature[:200],
            "priority": priority[:80],
            "status": status[:80],
            "parent_external_key": parent_external_key[:160],
            "source_metadata": _source_metadata_for(record),
            "extra_fields": _extra_fields(fields),
        },
    )
    return item


@transaction.atomic
def sync_spec_sets_for_source(source) -> list[SpecSet]:
    items = list(source.spec_items.order_by("module", "feature", "external_key", "title"))
    managed_qs = source.spec_sets.filter(metadata__managed_by="spec_item_sync")
    active_keys: set[str] = set()
    sets: list[SpecSet] = []

    if items:
        source_set = _upsert_set(
            source=source,
            set_key=f"source:{source.id}",
            set_type=SpecSetType.SOURCE,
            title=source.name,
            description=f"All imported specification items from {source.name}.",
            items=items,
            metadata={"source_id": str(source.id)},
        )
        active_keys.add(source_set.set_key)
        sets.append(source_set)

    for sheet, group_items in _group_by_sheet(items).items():
        spec_set = _upsert_set(
            source=source,
            set_key=f"sheet:{_key(sheet)}",
            set_type=SpecSetType.SHEET,
            title=sheet,
            description=f"Specification items from sheet or section {sheet}.",
            items=group_items,
            metadata={"sheet": sheet},
        )
        active_keys.add(spec_set.set_key)
        sets.append(spec_set)

    for group_key, group_items in _group_by_module_feature(items).items():
        module, feature = group_key
        title = " / ".join(part for part in (module, feature) if part)
        if not title:
            continue
        spec_set = _upsert_set(
            source=source,
            set_key=f"module:{_key(module)}:feature:{_key(feature)}",
            set_type=SpecSetType.FEATURE if feature else SpecSetType.MODULE,
            title=title,
            description=_set_description(group_items),
            items=group_items,
            metadata={"module": module, "feature": feature},
        )
        active_keys.add(spec_set.set_key)
        sets.append(spec_set)

    if active_keys:
        managed_qs.exclude(set_key__in=active_keys).delete()
    else:
        managed_qs.delete()
    return sets


def _upsert_set(
    *,
    source,
    set_key: str,
    set_type: str,
    title: str,
    description: str,
    items: list[SpecItem],
    metadata: dict[str, Any],
) -> SpecSet:
    spec_set, _created = SpecSet.objects.update_or_create(
        project=source.project,
        source=source,
        set_key=set_key[:240],
        defaults={
            "set_type": set_type,
            "title": title[:300],
            "description": description[:2000],
            "metadata": {"managed_by": "spec_item_sync", **metadata},
        },
    )
    spec_set.items.set(items)
    return spec_set


def _labelled_fields(content: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = defaultdict(list)
    for line in (content or "").splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        key = _field_key(label)
        cleaned = " ".join(value.split()).strip()
        if key and cleaned:
            fields[key].append(cleaned)
    return dict(fields)


def _field_key(label: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (label or "").strip().lower()).strip("_")
    aliases = {
        "id": "external_id",
        "external_reference": "external_id",
        "requirement_id": "external_id",
        "key": "external_key",
        "requirement": "description",
        "requirement_text": "description",
        "summary": "summary",
        "acceptance_criterion": "acceptance_criteria",
        "ac": "acceptance_criteria",
        "business_rules": "business_rule",
        "validation_rules": "validation_rule",
        "parent_id": "parent_external_id",
        "parent_key": "parent_external_id",
        "linked_requirement": "linked_requirement_key",
    }
    return aliases.get(normalized, normalized)


def _first_value(fields: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = fields.get(key) or []
        if values:
            return values[0]
    return ""


def _item_type_for(record_type: str, fields: dict[str, list[str]]) -> str:
    if record_type in ITEM_TYPE_BY_RECORD_TYPE:
        return ITEM_TYPE_BY_RECORD_TYPE[record_type]
    for key, item_type in ITEM_TYPE_BY_FIELD.items():
        if fields.get(key):
            return item_type
    return SpecItemType.REQUIREMENT


def _extra_fields(fields: dict[str, list[str]]) -> dict[str, Any]:
    return {
        key: values[0] if len(values) == 1 else values
        for key, values in fields.items()
        if key not in KNOWN_FIELD_KEYS
    }


def _source_metadata_for(record) -> dict[str, Any]:
    metadata = record.record_metadata or {}
    structure = metadata.get("structure") if isinstance(metadata.get("structure"), dict) else {}
    return {
        "source_record_id": str(record.id),
        "record_index": record.record_index,
        "section_label": record.section_label,
        "row_number": record.row_number,
        "structure": structure,
        "review": metadata.get("review") or {},
    }


def _group_by_sheet(items: list[SpecItem]) -> dict[str, list[SpecItem]]:
    grouped: dict[str, list[SpecItem]] = defaultdict(list)
    for item in items:
        structure = (item.source_metadata or {}).get("structure") or {}
        sheet = str(structure.get("container") or item.module or item.source.name).strip()
        grouped[sheet].append(item)
    return dict(grouped)


def _group_by_module_feature(items: list[SpecItem]) -> dict[tuple[str, str], list[SpecItem]]:
    grouped: dict[tuple[str, str], list[SpecItem]] = defaultdict(list)
    for item in items:
        module = (item.module or "").strip()
        feature = (item.feature or "").strip()
        if not module and not feature:
            continue
        grouped[(module, feature)].append(item)
    return dict(grouped)


def _set_description(items: list[SpecItem]) -> str:
    examples = [item.title for item in items[:5] if item.title]
    if not examples:
        return ""
    suffix = "" if len(items) <= 5 else f" and {len(items) - 5} more"
    return "Includes " + ", ".join(examples) + suffix + "."


def _key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return cleaned or "general"
