from __future__ import annotations

import re
from typing import Any

SelectorCandidate = tuple[str, str]

_VOLATILE_ID_PATTERNS = (
    re.compile(r"^__"),
    re.compile(r"^mui-\d+"),
    re.compile(r"^chakra-"),
    re.compile(r"^react-aria-\d+"),
    re.compile(r"^radix-"),
    re.compile(r"^[A-Za-z]?:r[0-9a-z]+"),
    re.compile(r"^[a-f0-9]{8,}-[a-f0-9]{4,}"),
)

_PASSWORD_TOKENS = ("password", "passwd", "pwd", "passcode", "secret", "token")


def attr(attrs: dict[str, Any] | None, *keys: str) -> str:
    attrs = attrs or {}
    for key in keys:
        value = attrs.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return ""


def normalize_space(value: str) -> str:
    return " ".join(str(value or "").split())


def field_name(value: str) -> str:
    value = normalize_space(value)
    if not value:
        return ""
    if "[" in value and value.endswith("]"):
        value = value.rsplit("[", 1)[-1].rstrip("]")
    return normalize_space(value.replace("_", " ").replace("-", " "))


def describe_target(attrs: dict[str, Any] | None, *, fallback: str = "") -> str:
    attrs = attrs or {}
    label = (
        attr(attrs, "placeholder")
        or attr(attrs, "aria_label", "aria-label")
        or normalize_space(attr(attrs, "text"))
        or field_name(attr(attrs, "name"))
        or field_name(attr(attrs, "id"))
        or attr(attrs, "role")
    )
    if label:
        return label

    tag = attr(attrs, "tag")
    input_type = attr(attrs, "type")
    if tag and input_type:
        return f"{input_type} {tag}"
    if tag:
        return tag
    return fallback or "current page"


def selector_candidates(
    attrs: dict[str, Any] | None,
    *,
    include_weak: bool = True,
) -> list[SelectorCandidate]:
    attrs = attrs or {}
    strong: list[SelectorCandidate] = []
    weak: list[SelectorCandidate] = []

    def add(target: list[SelectorCandidate], by: str, value: str) -> None:
        value = (value or "").strip()
        if value:
            target.append((by, value))

    data_attrs = (
        ("data_testid", "data-testid"),
        ("data-testid", "data-testid"),
        ("data_test_id", "data-test-id"),
        ("data-test-id", "data-test-id"),
        ("data_test", "data-test"),
        ("data-test", "data-test"),
        ("data_qa", "data-qa"),
        ("data-qa", "data-qa"),
        ("data_cy", "data-cy"),
        ("data-cy", "data-cy"),
    )
    for key, html_attr in data_attrs:
        value = attr(attrs, key)
        if value:
            add(strong, "By.CSS_SELECTOR", f'[{html_attr}="{escape_attr(value)}"]')

    element_id = attr(attrs, "id")
    if element_id and is_stable_id(element_id):
        add(strong, "By.ID", element_id)

    name = attr(attrs, "name")
    if name:
        add(strong, "By.NAME", name)

    aria_label = attr(attrs, "aria_label", "aria-label")
    if aria_label:
        add(strong, "By.CSS_SELECTOR", f'[aria-label="{escape_attr(aria_label)}"]')

    tag = attr(attrs, "tag").lower()
    placeholder = attr(attrs, "placeholder")
    if placeholder and tag in {"input", "textarea"}:
        add(strong, "By.CSS_SELECTOR", f'{tag}[placeholder="{escape_attr(placeholder)}"]')
    elif placeholder:
        add(strong, "By.CSS_SELECTOR", f'[placeholder="{escape_attr(placeholder)}"]')

    text = normalize_space(attr(attrs, "text"))
    input_type = attr(attrs, "type").lower()
    if text and tag == "input" and input_type in {"submit", "button", "reset"}:
        add(
            strong,
            "By.CSS_SELECTOR",
            f'input[type="{escape_attr(input_type)}"][value="{escape_attr(text)}"]',
        )

    if text and tag in {"button", "a", "summary", "label"}:
        add(strong, "By.XPATH", f"//{tag}[normalize-space()={xpath_str(text)}]")

    role = attr(attrs, "role")
    role_name = text or aria_label
    if role and role_name:
        add(
            strong,
            "By.XPATH",
            f"//*[@role={xpath_str(role)} and normalize-space()={xpath_str(role_name)}]",
        )
        add(
            strong,
            "By.XPATH",
            f"//*[@role={xpath_str(role)} and @aria-label={xpath_str(role_name)}]",
        )

    if tag == "input" and input_type:
        add(weak, "By.CSS_SELECTOR", f'input[type="{escape_attr(input_type)}"]')
    if tag:
        add(weak, "By.TAG_NAME", tag)

    strong = dedupe_candidates(strong)
    if strong or not include_weak:
        return strong

    weak = dedupe_candidates(weak)
    if weak:
        return weak
    return [("By.TAG_NAME", "body")]


def best_selector_for_trace(attrs: dict[str, Any] | None, *, fallback_ref: str = "") -> str:
    candidates = selector_candidates(attrs, include_weak=False)
    if candidates:
        return format_selector(candidates[0])
    fallback_ref = (fallback_ref or "").strip()
    if fallback_ref:
        if fallback_ref.isdigit():
            return f"data-biat-ref={fallback_ref}"
        return fallback_ref
    weak_candidates = selector_candidates(attrs, include_weak=True)
    return format_selector(weak_candidates[0]) if weak_candidates else ""


def format_selector(candidate: SelectorCandidate) -> str:
    by, value = candidate
    return f"{by}={value}"


def is_password_like(
    *,
    attrs: dict[str, Any] | None = None,
    action: str = "",
    target: str = "",
    value: str = "",
) -> bool:
    attrs = attrs or {}
    haystack = " ".join(
        [
            action,
            target,
            value,
            attr(attrs, "type"),
            attr(attrs, "id"),
            attr(attrs, "name"),
            attr(attrs, "placeholder"),
            attr(attrs, "aria_label", "aria-label"),
            attr(attrs, "role"),
        ]
    ).lower()
    return any(token in haystack for token in _PASSWORD_TOKENS)


def display_input_value(
    *,
    action: str,
    value: str | None,
    attrs: dict[str, Any] | None = None,
    target: str = "",
) -> str:
    value = value or ""
    if not value:
        return ""
    if is_password_like(attrs=attrs, action=action, target=target, value=value):
        return "********"
    return value


def display_summary(
    *,
    action: str,
    target: str,
    input_value: str = "",
    attrs: dict[str, Any] | None = None,
) -> str:
    action = (action or "").strip().lower()
    target = target or describe_target(attrs, fallback="current page")
    safe_value = display_input_value(
        action=action,
        value=input_value,
        attrs=attrs,
        target=target,
    )
    if action == "navigate":
        return f"Navigate to {target}"
    if action == "fill":
        return f"Fill {target} = {safe_value}" if safe_value else f"Fill {target}"
    if action == "click":
        return f"Click {target}"
    if action == "select":
        return f"Select {safe_value} in {target}" if safe_value else f"Select {target}"
    if action == "assert_text":
        expected = safe_value or target
        return f'Assert text "{expected}"'
    if action == "assert_url":
        expected = safe_value or target
        return f'Assert URL contains "{expected}"'
    if action == "assert_visible":
        return f"Assert {target} is visible"
    if action == "wait":
        return f"Wait for {safe_value or target}"
    return f"{action or 'step'} {target}".strip()


def is_stable_id(value: str) -> bool:
    if not value:
        return False
    return not any(pattern.match(value) for pattern in _VOLATILE_ID_PATTERNS)


def escape_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def xpath_str(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    chunks = ["'" + part + "'" for part in parts]
    return "concat(" + ", \"'\", ".join(chunks) + ")"


def dedupe_candidates(candidates: list[SelectorCandidate]) -> list[SelectorCandidate]:
    seen: set[SelectorCandidate] = set()
    deduped: list[SelectorCandidate] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped
