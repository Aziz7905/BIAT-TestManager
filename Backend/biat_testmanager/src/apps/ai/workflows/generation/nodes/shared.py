from __future__ import annotations

from apps.ai.models import AIGenerationSessionStatus
from apps.ai.workflows.generation.events import append_generation_event
from apps.ai.workflows.generation.plan import AgentLimits
from apps.ai.workflows.generation.state import CLOUD_GENERATION_LIMITS, TestGenerationState


GENERATED_SECTION_ID = "section_generated"
GENERATED_SECTION_NAME = "Generated scenarios"


class GenerationCancelled(Exception):
    """Raised internally when cooperative cancellation is observed."""


def combined_generation_context(state: TestGenerationState) -> list[dict]:
    return [*(state.get("rag_context") or []), *(state.get("temporary_context") or [])]


def agent_limits(state: TestGenerationState) -> AgentLimits:
    limits = state.get("generation_limits", CLOUD_GENERATION_LIMITS)
    return AgentLimits(
        max_scenarios=int(limits.get("max_scenarios_per_section") or 5),
        max_cases_per_scenario=int(limits.get("max_cases_per_scenario") or 5),
    )


def stop_if_cancelled(state: TestGenerationState) -> None:
    session = state["session"]
    session.refresh_from_db(fields=["status"])
    if session.status == AIGenerationSessionStatus.CANCELLED:
        state["agent_termination_reason"] = "cancelled"
        append_generation_event(
            session,
            "generation_cancelled",
            message="Generation stopped after cancellation was requested.",
        )
        raise GenerationCancelled()
