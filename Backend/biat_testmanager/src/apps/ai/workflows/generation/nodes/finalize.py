from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.ai.models import AIGenerationSessionStatus
from apps.ai.workflows.generation.evidence import coverage_audit_for_draft
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
    coverage_audit = coverage_audit_for_draft(
        obligations=state.get("coverage_obligations") or (state.get("generation_plan") or {}).get("coverage_obligations", []),
        draft_payload=draft,
    )
    existing_report = session.critic_report if isinstance(session.critic_report, dict) else {}
    critic_report = {
        **existing_report,
        "prompt_version": CRITIC_PROMPT_VERSION,
        "extraction_prompt_version": EXTRACTION_PROMPT_VERSION,
        "quality_warnings": state.get("quality_warnings", []),
        "generation_plan": state.get("generation_plan") or {},
        "coverage_map": coverage_map,
        "coverage_audit": coverage_audit,
        "dedupe_report": {
            "duplicate_candidates": coverage_audit.get("duplicate_candidates", []),
        },
        "unsupported_claim_warnings": coverage_audit.get("unsupported_claim_warnings", []),
        "enum_alignment_warnings": coverage_audit.get("enum_alignment_warnings", []),
        "uncovered_obligations": coverage_audit.get("obligations_uncovered", []),
        "merged_obligations": (state.get("coverage_metadata") or {}).get("merged_obligations", []),
        "agent_actions": state.get("agent_actions", []),
        "agent_observations": state.get("agent_observations", []),
        "retrieval_attempts": state.get("retrieval_attempts", []),
        "obligation_state_summary": state.get("obligation_state_summary", {}),
        "selected_hierarchy_strategy": state.get("selected_hierarchy_strategy", {}),
        "rejected_hierarchy_strategies": state.get("rejected_hierarchy_strategies", []),
        "clarification_questions": state.get("clarification_questions", []),
        "agent_termination_reason": state.get("agent_termination_reason") or "finalized",
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
        for scenario in _iter_scenarios(draft)
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


def _iter_scenarios(draft: dict[str, Any]):
    for section in draft.get("sections", []):
        yield from _iter_section_scenarios(section)


def _iter_section_scenarios(section: dict[str, Any]):
    for scenario in section.get("scenarios", []):
        if isinstance(scenario, dict):
            yield scenario
    for child in section.get("children", []):
        if isinstance(child, dict):
            yield from _iter_section_scenarios(child)
