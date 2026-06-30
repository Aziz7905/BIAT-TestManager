from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from apps.ai.models import AIGenerationSession
from apps.ai.providers.base import ChatResponse, LLMProvider
from apps.ai.workflows.generation.schemas import (
    LOCAL_MAX_STEPS_PER_CASE,
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
    context_plan: dict[str, bool]
    rag_context: list[dict[str, Any]]
    temporary_context: list[dict[str, Any]]
    temporary_inventory: list[dict[str, Any]]
    repository_memory: list[dict[str, Any]]
    semantic_evidence: list[dict[str, Any]]
    coverage_obligations: list[dict[str, Any]]
    coverage_metadata: dict[str, Any]
    generation_plan: dict[str, Any]
    draft_payload: dict[str, Any]
    repair_counts: dict[str, Any]
    clarification_required: bool
    agent_termination_reason: str
    agent_actions: list[dict[str, Any]]
    agent_observations: list[dict[str, Any]]
    retrieval_attempts: list[dict[str, Any]]
    obligation_state_summary: dict[str, int]
    selected_hierarchy_strategy: dict[str, Any]
    rejected_hierarchy_strategies: list[dict[str, Any]]
    clarification_questions: list[str]
    quality_warnings: list[str]
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
    "max_steps_per_case": MAX_STEPS_PER_CASE,
    "rag_top_k": 12,
    "max_chunk_chars": 1000,
    "extraction_max_tokens": 1200,
    "planning_max_tokens": 4096,
    "design_max_tokens": 4096,
    "repair_max_tokens": 3000,
    "critic_max_tokens": 1600,
    "json_retry_max_tokens": 8192,
    "max_agent_iterations": 80,
    "max_targeted_retrieval_attempts": 3,
    "targeted_rag_top_k": 5,
    "temporary_context_top_k": 40,
    "temporary_context_inventory_limit": 12,
}

LOCAL_GENERATION_LIMITS = {
    "max_steps_per_case": LOCAL_MAX_STEPS_PER_CASE,
    "rag_top_k": 5,
    "max_chunk_chars": 650,
    "extraction_max_tokens": 700,
    "planning_max_tokens": 1800,
    "design_max_tokens": 1800,
    "repair_max_tokens": 1400,
    "critic_max_tokens": 0,
    "json_retry_max_tokens": 2600,
    "num_ctx": 4096,
    "max_agent_iterations": 40,
    "max_targeted_retrieval_attempts": 1,
    "targeted_rag_top_k": 3,
    "temporary_context_top_k": 18,
    "temporary_context_inventory_limit": 8,
}
