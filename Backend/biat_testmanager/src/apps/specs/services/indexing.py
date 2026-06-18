import re

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q, QuerySet
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.specs.models import SpecChunk, SpecificationIndexStatus
from apps.specs.services.chunking import get_chunking_configuration, sync_specification_chunks
from apps.specs.services.embeddings import get_embedding_service
from apps.specs.services.embedding_models import get_or_create_default_embedding_model
from apps.specs.services.mlflow_tracking import MLflowRunLogger

_INDEXED_AT_UNSET = object()


def _base_chunk_queryset() -> QuerySet:
    return SpecChunk.objects.select_related(
        "embedding_model_config",
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


def _update_specification_index_state(
    specification,
    *,
    status: str,
    error_message: str = "",
    indexed_at=_INDEXED_AT_UNSET,
):
    update_fields: list[str] = []

    if specification.index_status != status:
        specification.index_status = status
        update_fields.append("index_status")

    if specification.index_error != error_message:
        specification.index_error = error_message
        update_fields.append("index_error")

    if indexed_at is not _INDEXED_AT_UNSET and specification.indexed_at != indexed_at:
        specification.indexed_at = indexed_at
        update_fields.append("indexed_at")

    if update_fields:
        specification.save(update_fields=[*update_fields, "updated_at"])


def _chunk_requires_reindex(chunk, embedding_model, *, force: bool = False) -> bool:
    return any(
        (
            force,
            chunk.embedding_vector is None,
            chunk.embedding_model != embedding_model.name,
            chunk.embedding_model_config_id != embedding_model.id,
            chunk.embedded_at is None,
        )
    )


def synchronize_specification_index(specification, *, force: bool = False):
    chunk_sync = sync_specification_chunks(specification)
    if not chunk_sync.chunks:
        _update_specification_index_state(
            specification,
            status=SpecificationIndexStatus.INDEXED,
            indexed_at=timezone.now(),
        )
        return []

    embedding_model = get_or_create_default_embedding_model()
    current_chunks = list(specification.chunks.order_by("chunk_index"))
    requires_reindex = chunk_sync.changed or any(
        _chunk_requires_reindex(chunk, embedding_model, force=force)
        for chunk in current_chunks
    )

    if not requires_reindex and specification.index_status == SpecificationIndexStatus.INDEXED:
        return current_chunks

    _update_specification_index_state(
        specification,
        status=SpecificationIndexStatus.PENDING,
    )
    return index_specification(
        specification,
        force=force or chunk_sync.changed,
        embedding_model=embedding_model,
    )


def index_specification(specification, *, force: bool = False, embedding_model=None):
    active_embedding_model = embedding_model or get_or_create_default_embedding_model()
    if active_embedding_model.dimensions != settings.SPEC_EMBEDDING_VECTOR_DIMENSIONS:
        message = (
            "Configured embedding dimensions do not match the pgvector column dimensions."
        )
        _update_specification_index_state(
            specification,
            status=SpecificationIndexStatus.FAILED,
            error_message=message,
        )
        raise ValueError(message)

    chunks = list(specification.chunks.order_by("chunk_index"))
    if not chunks:
        _update_specification_index_state(
            specification,
            status=SpecificationIndexStatus.INDEXED,
            indexed_at=timezone.now(),
        )
        return []

    pending_chunks = [
        chunk
        for chunk in chunks
        if _chunk_requires_reindex(
            chunk,
            active_embedding_model,
            force=force,
        )
    ]
    if not pending_chunks:
        _update_specification_index_state(
            specification,
            status=SpecificationIndexStatus.INDEXED,
            indexed_at=timezone.now(),
        )
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
        try:
            result = service.embed_texts(chunk_contents)

            timestamp = timezone.now()
            for chunk, embedding in zip(pending_chunks, result.embeddings, strict=True):
                chunk.embedding_vector = embedding
                chunk.embedding_model_config = active_embedding_model
                chunk.embedding_model = result.model_name
                chunk.embedded_at = timestamp

            SpecChunk.objects.bulk_update(
                pending_chunks,
                [
                    "embedding_vector",
                    "embedding_model_config",
                    "embedding_model",
                    "embedded_at",
                ],
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
        except Exception as error:
            _update_specification_index_state(
                specification,
                status=SpecificationIndexStatus.FAILED,
                error_message=str(error),
            )
            raise

    _update_specification_index_state(
        specification,
        status=SpecificationIndexStatus.INDEXED,
        indexed_at=timezone.now(),
    )

    return chunks


def reindex_specification_queryset(queryset: QuerySet, *, force: bool = False) -> int:
    indexed = 0
    for specification in queryset.iterator():
        synchronize_specification_index(specification, force=force)
        indexed += 1
    return indexed


def retrieve_similar_chunks(
    query: str,
    *,
    top_k: int = 5,
    project=None,
    specification=None,
    specifications=None,
    exclude_chunk_ids: list[str] | None = None,
):
    service = get_embedding_service()
    result = service.embed_texts([query], batch_size=1)
    query_embedding = result.embeddings[0]
    active_embedding_model = get_or_create_default_embedding_model()

    queryset = _base_chunk_queryset().filter(embedding_vector__isnull=False)
    queryset = queryset.filter(
        Q(embedding_model_config=active_embedding_model)
        | Q(
            embedding_model_config__isnull=True,
            embedding_model=active_embedding_model.name,
        )
    )
    if project is not None:
        queryset = queryset.filter(specification__project=project)
    if specification is not None:
        queryset = queryset.filter(specification=specification)
    if specifications is not None:
        queryset = queryset.filter(specification__in=specifications)
    if exclude_chunk_ids:
        queryset = queryset.exclude(pk__in=exclude_chunk_ids)

    return queryset.annotate(
        distance=CosineDistance("embedding_vector", query_embedding)
    ).order_by("distance", "chunk_index")[:top_k]


def full_text_retrieve_chunks(
    query: str,
    *,
    top_k: int = 5,
    project=None,
    specification=None,
    specifications=None,
):
    if not query.strip():
        return []

    queryset = _base_chunk_queryset()

    if project is not None:
        queryset = queryset.filter(specification__project=project)
    if specification is not None:
        queryset = queryset.filter(specification=specification)
    if specifications is not None:
        queryset = queryset.filter(specification__in=specifications)

    search_query = SearchQuery(query, config="simple", search_type="websearch")
    search_document = (
        SearchVector("content", weight="A", config="simple")
        + SearchVector("component_tag", weight="B", config="simple")
        + SearchVector("specification__title", weight="B", config="simple")
        + SearchVector("specification__external_reference", weight="B", config="simple")
    )

    try:
        return list(
            queryset.annotate(
                search_rank=SearchRank(
                    search_document,
                    search_query,
                    cover_density=True,
                )
            )
            .filter(search_rank__gt=0)
            .order_by("-search_rank", "specification__title", "chunk_index")[:top_k]
        )
    except Exception:
        return _fallback_keyword_retrieve_chunks(
            query,
            top_k=top_k,
            project=project,
            specification=specification,
            specifications=specifications,
        )


def keyword_retrieve_chunks(
    query: str,
    *,
    top_k: int = 5,
    project=None,
    specification=None,
    specifications=None,
):
    return full_text_retrieve_chunks(
        query,
        top_k=top_k,
        project=project,
        specification=specification,
        specifications=specifications,
    )


def hybrid_retrieve_chunks(
    query: str,
    *,
    top_k: int = 10,
    project=None,
    specification=None,
    specifications=None,
    vector_weight: float = 0.58,
    full_text_weight: float = 0.42,
):
    ranked_chunks: dict[str, object] = {}
    ranked_scores: dict[str, float] = {}

    full_text_chunks = list(
        full_text_retrieve_chunks(
            query,
            top_k=max(top_k * 2, top_k),
            project=project,
            specification=specification,
            specifications=specifications,
        )
    )
    _merge_ranked_chunks(
        ranked_chunks,
        ranked_scores,
        full_text_chunks,
        strategy="full_text",
        weight=full_text_weight,
    )

    try:
        vector_chunks = list(
            retrieve_similar_chunks(
                query,
                top_k=max(top_k * 2, top_k),
                project=project,
                specification=specification,
                specifications=specifications,
            )
        )
    except Exception:
        vector_chunks = []

    _merge_ranked_chunks(
        ranked_chunks,
        ranked_scores,
        vector_chunks,
        strategy="vector",
        weight=vector_weight,
    )

    if not ranked_chunks:
        fallback_chunks = _fallback_keyword_retrieve_chunks(
            query,
            top_k=top_k,
            project=project,
            specification=specification,
            specifications=specifications,
        )
        _merge_ranked_chunks(
            ranked_chunks,
            ranked_scores,
            fallback_chunks,
            strategy="keyword_fallback",
            weight=1.0,
        )

    ordered_ids = sorted(
        ranked_scores,
        key=lambda chunk_id: (
            -ranked_scores[chunk_id],
            ranked_chunks[chunk_id].specification.title,
            ranked_chunks[chunk_id].chunk_index,
        ),
    )
    results = [ranked_chunks[chunk_id] for chunk_id in ordered_ids[:top_k]]
    for chunk in results:
        chunk.retrieval_score = ranked_scores[str(chunk.id)]
        chunk.retrieval_strategy = "hybrid"
    return results


def _merge_ranked_chunks(
    ranked_chunks: dict[str, object],
    ranked_scores: dict[str, float],
    chunks: list[object],
    *,
    strategy: str,
    weight: float,
) -> None:
    for rank, chunk in enumerate(chunks, start=1):
        chunk_id = str(chunk.id)
        previous_sources = getattr(ranked_chunks.get(chunk_id), "retrieval_sources", set())
        if chunk_id not in ranked_chunks:
            ranked_chunks[chunk_id] = chunk
            ranked_scores[chunk_id] = 0.0
        elif getattr(chunk, "distance", None) is not None:
            ranked_chunks[chunk_id] = chunk

        ranked_scores[chunk_id] += weight / (60 + rank)
        existing_strategy = previous_sources or getattr(ranked_chunks[chunk_id], "retrieval_sources", set())
        if not isinstance(existing_strategy, set):
            existing_strategy = set(existing_strategy)
        existing_strategy.add(strategy)
        ranked_chunks[chunk_id].retrieval_sources = existing_strategy


def _fallback_keyword_retrieve_chunks(
    query: str,
    *,
    top_k: int = 5,
    project=None,
    specification=None,
    specifications=None,
):
    query_terms = _tokenize_query(query)
    queryset = _base_chunk_queryset()

    if project is not None:
        queryset = queryset.filter(specification__project=project)
    if specification is not None:
        queryset = queryset.filter(specification=specification)
    if specifications is not None:
        queryset = queryset.filter(specification__in=specifications)

    scored: list[tuple[int, object]] = []
    for chunk in queryset:
        content_terms = _tokenize_query(chunk.content)
        overlap = len(query_terms & content_terms)
        if overlap:
            scored.append((overlap, chunk))

    scored.sort(key=lambda item: (-item[0], item[1].chunk_index))
    return [chunk for _, chunk in scored[:top_k]]
