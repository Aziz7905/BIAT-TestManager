from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.ai.models import AIGenerationSessionStatus
from apps.ai.workflows.generation.events import append_generation_event
from apps.ai.workflows.generation.nodes.expansion import empty_draft
from apps.ai.workflows.generation.prompts import CRITIC_PROMPT_VERSION, EXTRACTION_PROMPT_VERSION
from apps.ai.workflows.generation.state import TestGenerationState


def finalize_generation(state: TestGenerationState) -> TestGenerationState:
    session = state["session"]
    if session.status == AIGenerationSessionStatus.CANCELLED:
        return state
    draft = state.get("draft_payload") or empty_draft(session, state.get("generation_plan") or {})
    coverage_map = _build_coverage_map(state.get("generation_plan") or {}, draft)
    existing_report = session.critic_report if isinstance(session.critic_report, dict) else {}
    critic_report = {
        **existing_report,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "extraction_prompt_version": EXTRACTION_PROMPT_VERSION,
        "quality_warnings": state.get("quality_warnings", []),
        "generation_plan": state.get("generation_plan") or {},
        "coverage_map": coverage_map,
        "repair_counts": state.get("repair_counts") or {},
        "termination": {
            "reason": state.get("agent_termination_reason") or "finalized",
            "max_attempts": (state.get("generation_plan") or {}).get("limits") or {},
        },
    }
    session.status = AIGenerationSessionStatus.READY_FOR_REVIEW
    session.draft_payload = draft
    session.critic_report = critic_report
    session.input_tokens = int(state.get("input_tokens") or 0)
    session.output_tokens = int(state.get("output_tokens") or 0)
    session.duration_ms = int(state.get("duration_ms") or 0)
    session.mlflow_run_id = state.get("mlflow_run_id", "")
    session.completed_at = timezone.now()
    session.error_message = ""
    session.save(
        update_fields=[
            "status",
            "draft_payload",
            "critic_report",
            "input_tokens",
            "output_tokens",
            "duration_ms",
            "mlflow_run_id",
            "completed_at",
            "error_message",
            "updated_at",
        ]
    )
    append_generation_event(
        session,
        "generation_completed",
        message="Generation completed and is ready for review.",
        payload=coverage_map,
    )
    return state


def _build_coverage_map(plan: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    produced = {
        scenario.get("draft_id")
        for section in draft.get("sections", [])
        for scenario in section.get("scenarios", [])
        if isinstance(scenario, dict)
    }
    planned = {
        scenario.get("draft_scenario_id")
        for scenario in plan.get("selected_scenarios", [])
        if isinstance(scenario, dict)
    }
    return {
        "planned_scenario_count": len(planned),
        "produced_scenario_count": len(produced),
        "uncovered_scenario_ids": sorted(planned - produced),
        "excluded_candidate_count": len(plan.get("excluded_candidates") or []),
    }
