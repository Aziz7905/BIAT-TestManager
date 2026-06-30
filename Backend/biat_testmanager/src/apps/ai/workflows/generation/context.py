from __future__ import annotations

from typing import Any

from apps.ai.models import AIGenerationContextType, AIGenerationRetrievedContext
from apps.specs.models import SpecChunk, Specification, SpecificationSource
from apps.specs.services.indexing import (
    hybrid_retrieve_chunks,
    keyword_retrieve_chunks,
    retrieve_similar_chunks,
)

MAX_CHUNK_CONTENT_CHARS = 1800
MAX_SOURCE_BUNDLE_CHUNKS = 40


def retrieve_generation_context(
    session,
    *,
    query: str | None = None,
    top_k: int = 10,
    max_content_chars: int = MAX_CHUNK_CONTENT_CHARS,
    retrieval_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve project-scoped specification chunks for a generation session."""
    retrieval_query = str(query or session.objective or "").strip()
    project = session.project
    specifications = _resolve_selected_specifications(session)
    bundle_mode = len(specifications) > 1 or _source_scope_requested(session)

    chunks: list[SpecChunk] = []
    if specifications and bundle_mode:
        chunks = _retrieve_bundle_chunks(
            retrieval_query,
            specifications,
            max_chunks=max(top_k, min(MAX_SOURCE_BUNDLE_CHUNKS, len(specifications) * 2)),
        )
    elif specifications:
        for specification in specifications:
            chunks.extend(
                _retrieve_chunks_for_specification(
                    retrieval_query,
                    top_k=top_k,
                    project=project,
                    specification=specification,
                )
            )
    else:
        chunks = _retrieve_chunks_for_specification(
            retrieval_query,
            top_k=top_k,
            project=project,
            specification=None,
        )

    context: list[dict[str, Any]] = []
    chunk_limit = (
        max(top_k, min(MAX_SOURCE_BUNDLE_CHUNKS, len(specifications) * 2))
        if bundle_mode
        else top_k
    )
    for chunk in _dedupe_chunks(chunks)[:chunk_limit]:
        score = _score_chunk(chunk)
        context_item = _chunk_context_item(
            chunk,
            score=score,
            max_content_chars=max_content_chars,
        )
        context.append(context_item)
        AIGenerationRetrievedContext.objects.create(
            session=session,
            context_type=AIGenerationContextType.SPEC_CHUNK,
            object_id=str(chunk.id),
            score=score,
            metadata_json={
                **(retrieval_metadata or {}),
                "query": retrieval_query,
                "specification_id": str(chunk.specification_id),
                "specification_title": chunk.specification.title,
                "chunk_index": chunk.chunk_index,
                "chunk_type": chunk.chunk_type,
                "component_tag": chunk.component_tag,
                "retrieval_strategy": getattr(chunk, "retrieval_strategy", ""),
                "retrieval_sources": sorted(getattr(chunk, "retrieval_sources", set()) or []),
            },
        )

    return context


def _retrieve_bundle_chunks(
    query: str,
    specifications: list[Specification],
    *,
    max_chunks: int,
) -> list[SpecChunk]:
    coverage_seed = list(
        SpecChunk.objects.filter(specification__in=specifications)
        .select_related("specification", "specification__project")
        .order_by("specification__title", "chunk_index")
    )
    first_chunk_by_spec: dict[str, SpecChunk] = {}
    for chunk in coverage_seed:
        first_chunk_by_spec.setdefault(str(chunk.specification_id), chunk)

    ranked_chunks = list(
        hybrid_retrieve_chunks(
            query,
            top_k=max_chunks,
            specifications=specifications,
        )
    )
    chunks = _dedupe_chunks([*first_chunk_by_spec.values(), *ranked_chunks])
    if chunks:
        return chunks[:max_chunks]

    return [
        chunk
        for specification in specifications
        for chunk in specification.chunks.select_related("specification").order_by("chunk_index")
    ][:max_chunks]


def _retrieve_chunks_for_specification(
    query: str,
    *,
    top_k: int,
    project,
    specification,
) -> list[SpecChunk]:
    try:
        chunks = list(
            hybrid_retrieve_chunks(
                query,
                top_k=top_k,
                project=project,
                specification=specification,
            )
        )
    except Exception:
        chunks = list(
            keyword_retrieve_chunks(
                query,
                top_k=top_k,
                project=project,
                specification=specification,
            )
        )
    if not chunks:
        chunks = list(
            keyword_retrieve_chunks(
                query,
                top_k=top_k,
                project=project,
                specification=specification,
            )
        )
    return chunks


def _resolve_selected_specifications(session) -> list[Specification]:
    project = session.project
    source_refs = session.source_refs if isinstance(session.source_refs, dict) else {}
    spec_ids = _list_refs(source_refs, "specification_ids")
    spec_ids += _list_refs(source_refs, "selected_specification_ids")
    source_ids = _list_refs(source_refs, "specification_source_ids")
    source_ids += _list_refs(source_refs, "source_ids")
    for key in ("specification_source_id", "specification_source"):
        value = source_refs.get(key)
        if value:
            source_ids.append(str(value))

    if session.attached_specification_id:
        spec_ids.append(str(session.attached_specification_id))

    specifications_by_id: dict[str, Specification] = {}
    if spec_ids:
        for specification in Specification.objects.filter(
            project=project,
            pk__in=spec_ids,
        ).select_related("project", "source"):
            specifications_by_id[str(specification.id)] = specification

    if source_ids:
        valid_source_ids = SpecificationSource.objects.filter(
            project=project,
            pk__in=source_ids,
        ).values_list("id", flat=True)
        for specification in Specification.objects.filter(
            project=project,
            source_id__in=list(valid_source_ids),
        ).select_related("project", "source"):
            specifications_by_id[str(specification.id)] = specification

    return list(specifications_by_id.values())


def _source_scope_requested(session) -> bool:
    source_refs = session.source_refs if isinstance(session.source_refs, dict) else {}
    return any(
        source_refs.get(key)
        for key in (
            "specification_source_id",
            "specification_source",
            "specification_source_ids",
            "source_ids",
        )
    )


def _list_refs(source_refs: dict[str, Any], key: str) -> list[str]:
    value = source_refs.get(key)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _dedupe_chunks(chunks: list[SpecChunk]) -> list[SpecChunk]:
    seen: set[str] = set()
    deduped: list[SpecChunk] = []
    for chunk in chunks:
        chunk_id = str(chunk.id)
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        deduped.append(chunk)
    return deduped


def _score_chunk(chunk: SpecChunk) -> float | None:
    retrieval_score = getattr(chunk, "retrieval_score", None)
    if retrieval_score is not None:
        try:
            return float(retrieval_score)
        except (TypeError, ValueError):
            pass

    search_rank = getattr(chunk, "search_rank", None)
    if search_rank is not None:
        try:
            return float(search_rank)
        except (TypeError, ValueError):
            pass

    distance = getattr(chunk, "distance", None)
    if distance is None:
        return None
    try:
        return max(0.0, 1.0 - float(distance))
    except (TypeError, ValueError):
        return None


def _chunk_context_item(
    chunk: SpecChunk,
    *,
    score: float | None,
    max_content_chars: int,
) -> dict[str, Any]:
    spec_item = _spec_item_context(chunk)
    return {
        "context_type": AIGenerationContextType.SPEC_CHUNK,
        "chunk_id": str(chunk.id),
        "specification_id": str(chunk.specification_id),
        "specification_title": chunk.specification.title,
        "specification_external_reference": chunk.specification.external_reference or "",
        "chunk_index": chunk.chunk_index,
        "chunk_type": chunk.chunk_type,
        "component_tag": chunk.component_tag,
        "score": score,
        "retrieval_strategy": getattr(chunk, "retrieval_strategy", ""),
        "retrieval_sources": sorted(getattr(chunk, "retrieval_sources", set()) or []),
        "content": chunk.content[:max_content_chars],
        "spec_item": spec_item,
        "source_metadata": chunk.specification.source_metadata or {},
    }


def _spec_item_context(chunk: SpecChunk) -> dict[str, Any]:
    try:
        item = chunk.specification.spec_item
    except Exception:
        return {}
    return {
        "id": str(item.id),
        "external_key": item.external_key,
        "item_type": item.item_type,
        "title": item.title,
        "module": item.module,
        "feature": item.feature,
        "priority": item.priority,
        "status": item.status,
        "parent_external_key": item.parent_external_key,
        "source_metadata": item.source_metadata or {},
    }
