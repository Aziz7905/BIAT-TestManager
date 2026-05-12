from __future__ import annotations

from typing import Any

from apps.ai.models import AIGenerationContextType, AIGenerationRetrievedContext
from apps.specs.models import SpecChunk
from apps.specs.services.indexing import keyword_retrieve_chunks, retrieve_similar_chunks

MAX_CHUNK_CONTENT_CHARS = 1800


def retrieve_generation_context(session, *, top_k: int = 10) -> list[dict[str, Any]]:
    """Retrieve project-scoped specification chunks for a generation session."""
    query = session.objective
    project = session.project
    specification = session.attached_specification

    try:
        chunks = list(
            retrieve_similar_chunks(
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

    context: list[dict[str, Any]] = []
    for chunk in _dedupe_chunks(chunks):
        score = _score_chunk(chunk)
        context_item = _chunk_context_item(chunk, score=score)
        context.append(context_item)
        AIGenerationRetrievedContext.objects.create(
            session=session,
            context_type=AIGenerationContextType.SPEC_CHUNK,
            object_id=str(chunk.id),
            score=score,
            metadata_json={
                "specification_id": str(chunk.specification_id),
                "specification_title": chunk.specification.title,
                "chunk_index": chunk.chunk_index,
                "chunk_type": chunk.chunk_type,
                "component_tag": chunk.component_tag,
            },
        )

    return context


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
    distance = getattr(chunk, "distance", None)
    if distance is None:
        return None
    try:
        return max(0.0, 1.0 - float(distance))
    except (TypeError, ValueError):
        return None


def _chunk_context_item(chunk: SpecChunk, *, score: float | None) -> dict[str, Any]:
    return {
        "context_type": AIGenerationContextType.SPEC_CHUNK,
        "chunk_id": str(chunk.id),
        "specification_id": str(chunk.specification_id),
        "specification_title": chunk.specification.title,
        "chunk_index": chunk.chunk_index,
        "chunk_type": chunk.chunk_type,
        "component_tag": chunk.component_tag,
        "score": score,
        "content": chunk.content[:MAX_CHUNK_CONTENT_CHARS],
    }
