import re


def normalize_part(value: str) -> str:
    normalized_value = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "", normalized_value)


def build_org_email(first_name: str, last_name: str, domain: str) -> str:
    local_part = f"{normalize_part(first_name)}.{normalize_part(last_name)}"
    return f"{local_part}@{domain.strip().lower()}"