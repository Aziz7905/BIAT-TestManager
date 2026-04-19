from django.conf import settings

from apps.specs.models import EmbeddingModel


def infer_embedding_provider(model_name: str) -> str:
    normalized_name = (model_name or "").strip()
    if not normalized_name:
        return "local"
    if (
        "\\" in normalized_name
        or ":" in normalized_name
        or normalized_name.startswith((".", "/"))
    ):
        return "local"
    if "/" in normalized_name:
        return normalized_name.split("/", maxsplit=1)[0]
    return "local"


def get_or_create_default_embedding_model() -> EmbeddingModel:
    defaults = {
        "provider": infer_embedding_provider(settings.SPEC_EMBEDDING_MODEL_NAME),
        "dimensions": settings.SPEC_EMBEDDING_VECTOR_DIMENSIONS,
        "normalize": settings.SPEC_EMBEDDING_NORMALIZE,
        "is_active": True,
    }
    embedding_model, _ = EmbeddingModel.objects.get_or_create(
        name=settings.SPEC_EMBEDDING_MODEL_NAME,
        defaults=defaults,
    )

    updated_fields: list[str] = []
    for field_name, expected_value in defaults.items():
        if getattr(embedding_model, field_name) != expected_value:
            setattr(embedding_model, field_name, expected_value)
            updated_fields.append(field_name)

    if updated_fields:
        embedding_model.save(update_fields=[*updated_fields, "updated_at"])

    return embedding_model
