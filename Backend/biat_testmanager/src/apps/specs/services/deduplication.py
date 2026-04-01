import hashlib
import re

from apps.specs.models import Specification


def normalize_spec_content(content: str) -> str:
    normalized = re.sub(r"\s+", " ", (content or "").strip())
    return normalized


def build_spec_content_hash(content: str) -> str:
    normalized = normalize_spec_content(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def find_duplicate_specification(*, project, content: str, exclude_specification_id=None):
    content_hash = build_spec_content_hash(content)
    queryset = Specification.objects.filter(
        project=project,
        content_hash=content_hash,
    )
    if exclude_specification_id is not None:
        queryset = queryset.exclude(pk=exclude_specification_id)
    return queryset.first()
