from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from apps.ai.models import AIGenerationSession
from apps.ai.providers.base import ChatResponse, LLMProvider
from apps.ai.workflows.generation.schemas import (
    LOCAL_MAX_CASES_PER_SCENARIO,
    LOCAL_MAX_SCENARIOS_PER_SECTION,
    LOCAL_MAX_SECTIONS,
    LOCAL_MAX_STEPS_PER_CASE,
    MAX_CASES_PER_SCENARIO,
    MAX_SCENARIOS_PER_SECTION,
    MAX_SECTIONS,
    MAX_STEPS_PER_CASE,
)


class TestGenerationState(TypedDict, total=False):
    session_id: str
    session: AIGenerationSession
    provider: LLMProvider
    provider_name: str
    model_name: str
    normalized_intent: dict[str, Any]
    requirement_extraction: dict[str, Any]
    generation_limits: dict[str, int]
    rag_context: list[dict[str, Any]]
    repository_memory: list[dict[str, Any]]
    raw_draft_payload: dict[str, Any]
    draft_payload: dict[str, Any]
    critic_report: dict[str, Any]
    validation_error: str
    quality_warnings: list[str]
    quality_repair_instruction: str
    input_tokens: int
    output_tokens: int
    duration_ms: int
    mlflow_run_id: str


@dataclass
class LLMJSONResult:
    payload: dict[str, Any]
    response: ChatResponse
    duration_ms: int


CLOUD_GENERATION_LIMITS = {
    "max_sections": MAX_SECTIONS,
    "max_scenarios_per_section": MAX_SCENARIOS_PER_SECTION,
    "max_cases_per_scenario": MAX_CASES_PER_SCENARIO,
    "max_steps_per_case": MAX_STEPS_PER_CASE,
    "rag_top_k": 12,
    "max_chunk_chars": 1000,
    "extraction_max_tokens": 1200,
    "design_max_tokens": 4096,
    "repair_max_tokens": 3000,
    "critic_max_tokens": 1600,
}

LOCAL_GENERATION_LIMITS = {
    "max_sections": LOCAL_MAX_SECTIONS,
    "max_scenarios_per_section": LOCAL_MAX_SCENARIOS_PER_SECTION,
    "max_cases_per_scenario": LOCAL_MAX_CASES_PER_SCENARIO,
    "max_steps_per_case": LOCAL_MAX_STEPS_PER_CASE,
    "rag_top_k": 5,
    "max_chunk_chars": 650,
    "extraction_max_tokens": 700,
    "design_max_tokens": 1800,
    "repair_max_tokens": 1400,
    "critic_max_tokens": 0,
    "num_ctx": 4096,
}
