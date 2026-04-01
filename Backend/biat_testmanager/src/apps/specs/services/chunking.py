from dataclasses import dataclass
import re

from django.conf import settings

from apps.specs.models import SpecChunk, SpecChunkType


@dataclass
class ChunkDraft:
    chunk_index: int
    chunk_type: str
    component_tag: str
    content: str
    token_count: int


def get_chunking_configuration() -> dict[str, int | str]:
    return {
        "strategy": settings.SPEC_CHUNK_STRATEGY,
        "max_chars": settings.SPEC_CHUNK_MAX_CHARS,
        "overlap_chars": settings.SPEC_CHUNK_OVERLAP_CHARS,
    }


def estimate_token_count(content: str) -> int:
    return max(1, len(content.split()))


def infer_chunk_type(content: str) -> str:
    lowered = content.lower()

    if any(phrase in lowered for phrase in ["as a ", "i want ", "so that "]):
        return SpecChunkType.USER_STORY

    if any(
        phrase in lowered
        for phrase in ["acceptance criteria", "given ", "when ", "then ", "scenario:"]
    ):
        return SpecChunkType.ACCEPTANCE_CRITERIA

    if any(phrase in lowered for phrase in ["shall ", "must ", "should ", "requirement"]):
        return SpecChunkType.FUNCTIONAL_REQUIREMENT

    return SpecChunkType.OTHER


def infer_component_tag(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return ""

    first_line = lines[0].lstrip("#").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", first_line).strip("-")
    return normalized[:100]


def split_into_sections(content: str) -> list[str]:
    if not content.strip():
        return []

    sections = [section.strip() for section in re.split(r"\n\s*\n", content) if section.strip()]
    return sections or [content.strip()]


def split_section_by_sentences(section: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if len(section) <= max_chars:
        return [section.strip()]

    sentences = [
        segment.strip()
        for segment in re.split(r"(?<=[.!?])\s+", section)
        if segment.strip()
    ]
    if not sentences:
        return [section.strip()]

    windows: list[str] = []
    current_sentences: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence) + (1 if current_sentences else 0)
        if current_sentences and current_length + sentence_length > max_chars:
            window = " ".join(current_sentences).strip()
            windows.append(window)

            overlap_sentences: list[str] = []
            overlap_length = 0
            for existing in reversed(current_sentences):
                candidate_length = len(existing) + (1 if overlap_sentences else 0)
                if overlap_length + candidate_length > overlap_chars:
                    break
                overlap_sentences.insert(0, existing)
                overlap_length += candidate_length

            current_sentences = overlap_sentences[:]
            current_length = len(" ".join(current_sentences))

        current_sentences.append(sentence)
        current_length = len(" ".join(current_sentences))

    if current_sentences:
        windows.append(" ".join(current_sentences).strip())

    return [window for window in windows if window]


def build_chunks_from_content(content: str) -> list[ChunkDraft]:
    config = get_chunking_configuration()
    sections = split_into_sections(content)
    drafts: list[ChunkDraft] = []

    for section in sections:
        for part in split_section_by_sentences(
            section,
            max_chars=int(config["max_chars"]),
            overlap_chars=int(config["overlap_chars"]),
        ):
            drafts.append(
                ChunkDraft(
                    chunk_index=len(drafts),
                    chunk_type=infer_chunk_type(part),
                    component_tag=infer_component_tag(part),
                    content=part,
                    token_count=estimate_token_count(part),
                )
            )

    return drafts


def sync_specification_chunks(specification):
    drafts = build_chunks_from_content(specification.content)

    specification.chunks.all().delete()

    SpecChunk.objects.bulk_create(
        [
            SpecChunk(
                specification=specification,
                chunk_index=draft.chunk_index,
                chunk_type=draft.chunk_type,
                component_tag=draft.component_tag,
                content=draft.content,
                token_count=draft.token_count,
            )
            for draft in drafts
        ]
    )

    return drafts
