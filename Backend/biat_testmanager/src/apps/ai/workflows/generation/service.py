from __future__ import annotations

from django.utils import timezone

from apps.ai.models import AIGenerationSession, AIGenerationSessionStatus
from apps.ai.workflows.generation.prompts import DESIGN_PROMPT_VERSION
from apps.ai.workflows.generation.schemas import SCHEMA_VERSION
from apps.ai.workflows.generation.state import TestGenerationState
from apps.specs.services.mlflow_tracking import MLflowRunLogger


def run_test_generation_workflow(session_id: str) -> TestGenerationState:
    from apps.ai.workflows.generation.graph import run_test_generation_graph

    state: TestGenerationState = {"session_id": session_id}
    with MLflowRunLogger(
        "ai_test_generation",
        params={
            "session_id": session_id,
            "schema_version": SCHEMA_VERSION,
            "prompt_version": DESIGN_PROMPT_VERSION,
        },
        tags={"pipeline": "ai_test_generation"},
    ) as tracker:
        if getattr(tracker, "_run", None):
            state["mlflow_run_id"] = tracker._run.info.run_id
        try:
            result = run_test_generation_graph(state)
            tracker.log_params(
                {
                    "provider": result.get("provider_name", ""),
                    "model": result.get("model_name", ""),
                }
            )
            tracker.log_metrics(
                {
                    "input_tokens": float(result.get("input_tokens") or 0),
                    "output_tokens": float(result.get("output_tokens") or 0),
                    "duration_ms": float(result.get("duration_ms") or 0),
                    "retrieved_chunk_count": float(len(result.get("rag_context") or [])),
                    "repository_memory_count": float(len(result.get("repository_memory") or [])),
                }
            )
            tracker.log_dict(result.get("draft_payload", {}), "draft_payload.json")
            tracker.log_dict(result.get("critic_report", {}), "critic_report.json")
            return result
        except Exception as exc:
            mark_generation_failed(session_id, str(exc), state=state)
            raise


def mark_generation_failed(
    session_id: str,
    message: str,
    *,
    state: TestGenerationState | None = None,
) -> None:
    update_fields = ["status", "error_message", "completed_at", "updated_at"]
    session = AIGenerationSession.objects.filter(pk=session_id).first()
    if session is None:
        return
    session.status = AIGenerationSessionStatus.FAILED
    session.error_message = message[:5000]
    session.completed_at = timezone.now()
    if state:
        session.input_tokens = int(state.get("input_tokens") or session.input_tokens)
        session.output_tokens = int(state.get("output_tokens") or session.output_tokens)
        session.duration_ms = int(state.get("duration_ms") or session.duration_ms or 0)
        session.mlflow_run_id = state.get("mlflow_run_id", session.mlflow_run_id)
        update_fields.extend(
            ["input_tokens", "output_tokens", "duration_ms", "mlflow_run_id"]
        )
    session.save(update_fields=update_fields)
