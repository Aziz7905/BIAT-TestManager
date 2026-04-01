from datetime import datetime, timezone
import re

from django.conf import settings
from django.db.models import QuerySet
from pgvector.django import CosineDistance

from apps.specs.models import SpecChunk
from apps.specs.services.chunking import get_chunking_configuration
from apps.specs.services.embeddings import get_embedding_service
from apps.specs.services.mlflow_tracking import MLflowRunLogger


def _base_chunk_queryset() -> QuerySet:
    return SpecChunk.objects.select_related(
        "specification",
        "specification__project",
        "specification__project__team",
        "specification__project__team__organization",
    )


def _tokenize_query(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]+", query.lower())
        if len(token) > 2
    }


def index_specification(specification, *, force: bool = False):
    chunks = list(specification.chunks.order_by("chunk_index"))
    if not chunks:
        return []

    pending_chunks = [
        chunk
        for chunk in chunks
        if force
        or chunk.embedding_vector is None
        or chunk.embedding_model != settings.SPEC_EMBEDDING_MODEL_NAME
    ]
    if not pending_chunks:
        return chunks

    service = get_embedding_service()
    chunk_contents = [chunk.content for chunk in pending_chunks]
    chunk_config = get_chunking_configuration()

    with MLflowRunLogger(
        "spec_chunk_indexing",
        params={
            "model_name": service.model_name,
            "batch_size_requested": service.default_batch_size,
            "chunk_count": len(pending_chunks),
            "chunking_strategy": chunk_config["strategy"],
            "chunk_max_chars": chunk_config["max_chars"],
            "chunk_overlap_chars": chunk_config["overlap_chars"],
            "source_type": specification.source_type,
            "project_id": str(specification.project_id),
            "specification_id": str(specification.id),
        },
        tags={
            "pipeline": "spec_indexing",
        },
    ) as tracker:
        result = service.embed_texts(chunk_contents)

        timestamp = datetime.now(timezone.utc)
        for chunk, embedding in zip(pending_chunks, result.embeddings, strict=True):
            chunk.embedding_vector = embedding
            chunk.embedding_model = result.model_name
            chunk.embedded_at = timestamp

        SpecChunk.objects.bulk_update(
            pending_chunks,
            ["embedding_vector", "embedding_model", "embedded_at"],
        )

        tracker.log_params(
            {
                "resolved_device": result.device,
                "resolved_batch_size": result.batch_size,
                "normalized_embeddings": result.normalized,
                "vector_dimensions": settings.SPEC_EMBEDDING_VECTOR_DIMENSIONS,
            }
        )
        tracker.log_metrics(
            {
                "processing_time_s": result.duration_s,
                **result.metrics,
            }
        )
        tracker.log_dict(
            {
                "chunk_ids": [str(chunk.id) for chunk in pending_chunks],
                "chunk_lengths": [len(chunk.content) for chunk in pending_chunks],
            },
            "indexing_chunks.json",
        )

    return chunks


def reindex_specification_queryset(queryset: QuerySet, *, force: bool = False) -> int:
    indexed = 0
    for specification in queryset.iterator():
        index_specification(specification, force=force)
        indexed += 1
    return indexed


def retrieve_similar_chunks(
    query: str,
    *,
    top_k: int = 5,
    project=None,
    specification=None,
    exclude_chunk_ids: list[str] | None = None,
):
    service = get_embedding_service()
    result = service.embed_texts([query], batch_size=1)
    query_embedding = result.embeddings[0]

    queryset = _base_chunk_queryset().filter(embedding_vector__isnull=False)
    if project is not None:
        queryset = queryset.filter(specification__project=project)
    if specification is not None:
        queryset = queryset.filter(specification=specification)
    if exclude_chunk_ids:
        queryset = queryset.exclude(pk__in=exclude_chunk_ids)

    return queryset.annotate(
        distance=CosineDistance("embedding_vector", query_embedding)
    ).order_by("distance", "chunk_index")[:top_k]


def keyword_retrieve_chunks(
    query: str,
    *,
    top_k: int = 5,
    project=None,
    specification=None,
):
    query_terms = _tokenize_query(query)
    queryset = _base_chunk_queryset()

    if project is not None:
        queryset = queryset.filter(specification__project=project)
    if specification is not None:
        queryset = queryset.filter(specification=specification)

    scored: list[tuple[int, object]] = []
    for chunk in queryset:
        content_terms = _tokenize_query(chunk.content)
        overlap = len(query_terms & content_terms)
        if overlap:
            scored.append((overlap, chunk))

    scored.sort(key=lambda item: (-item[0], item[1].chunk_index))
    return [chunk for _, chunk in scored[:top_k]]
