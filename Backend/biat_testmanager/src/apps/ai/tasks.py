from django.conf import settings

_CELERY_IMPORT_ERROR = None

try:
    from celery import shared_task
except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific fallback
    _CELERY_IMPORT_ERROR = exc

    def shared_task(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from apps.ai.models import AIGenerationSession
from apps.ai.workflows.authoring.service import run_browser_authoring_session
from apps.ai.workflows.generation.refine import run_draft_refinement
from apps.ai.workflows.generation.service import (
    mark_generation_failed,
    run_test_generation_workflow,
)


@shared_task(bind=True, name="ai.run_generation_session")
def run_generation_session_task(self, session_id: str):
    return _run_generation_session(session_id)


def _run_generation_session(session_id: str):
    try:
        result = run_test_generation_workflow(session_id)
        session = result["session"]
    except Exception as exc:
        mark_generation_failed(session_id, str(exc))
        session = AIGenerationSession.objects.filter(pk=session_id).first()
        return {
            "session_id": session_id,
            "status": session.status if session else "failed",
            "error_message": str(exc),
        }
    return {
        "session_id": str(session.id),
        "status": session.status,
    }


@shared_task(bind=True, name="ai.run_generation_refine")
def run_generation_refine_task(self, session_id: str, instruction: str = "", draft_ids=None):
    return _run_generation_refine(session_id, instruction, draft_ids)


def _run_generation_refine(session_id: str, instruction: str = "", draft_ids=None):
    session = run_draft_refinement(session_id, instruction, list(draft_ids or []))
    return {
        "session_id": str(session.id),
        "status": session.status,
    }


@shared_task(bind=True, name="ai.run_authoring_session")
def run_authoring_session_task(
    self,
    execution_id: str,
    target_url: str = "",
    max_steps: int | None = None,
    temperature: float | None = None,
    max_tokens_per_step: int | None = None,
):
    return _run_authoring_session(
        execution_id,
        target_url=target_url,
        max_steps=max_steps,
        temperature=temperature,
        max_tokens_per_step=max_tokens_per_step,
    )


def _run_authoring_session(
    execution_id: str,
    *,
    target_url: str = "",
    max_steps: int | None = None,
    temperature: float | None = None,
    max_tokens_per_step: int | None = None,
):
    execution = run_browser_authoring_session(
        execution_id,
        target_url=target_url,
        max_steps=max_steps,
        temperature=temperature,
        max_tokens_per_step=max_tokens_per_step,
    )
    return _execution_task_payload(execution)


def _execution_task_payload(execution):
    payload = {
        "execution_id": str(execution.id),
        "status": execution.status,
    }

    try:
        result = execution.result
    except Exception:
        result = None
    if result and result.error_message:
        payload["error_message"] = result.error_message[:1000]

    failed_step = (
        execution.steps.filter(status="failed")
        .order_by("step_index")
        .first()
    )
    if failed_step is not None:
        payload["failed_step"] = {
            "step_index": failed_step.step_index,
            "action": failed_step.action,
            "target": failed_step.target_element,
            "selector": failed_step.selector_used,
            "error_message": (failed_step.error_message or "")[:1000],
        }

    return payload


def enqueue_generation_session_task(session_id: str):
    if hasattr(run_generation_session_task, "delay"):
        try:
            async_result = run_generation_session_task.delay(session_id)
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                _run_generation_session(session_id)
                return None
            raise RuntimeError("Unable to enqueue AI generation session.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError("Celery is required to enqueue AI generation sessions.") from _CELERY_IMPORT_ERROR

    _run_generation_session(session_id)
    return None


def enqueue_generation_refine_task(session_id: str, instruction: str = "", draft_ids=None):
    draft_ids = list(draft_ids or [])
    if hasattr(run_generation_refine_task, "delay"):
        try:
            async_result = run_generation_refine_task.delay(session_id, instruction, draft_ids)
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                _run_generation_refine(session_id, instruction, draft_ids)
                return None
            raise RuntimeError("Unable to enqueue AI draft refinement.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError(
            "Celery is required to enqueue AI draft refinements."
        ) from _CELERY_IMPORT_ERROR

    _run_generation_refine(session_id, instruction, draft_ids)
    return None


def enqueue_authoring_session_task(
    execution_id: str,
    *,
    target_url: str = "",
    max_steps: int | None = None,
    temperature: float | None = None,
    max_tokens_per_step: int | None = None,
):
    if hasattr(run_authoring_session_task, "delay"):
        try:
            async_result = run_authoring_session_task.delay(
                execution_id,
                target_url,
                max_steps,
                temperature,
                max_tokens_per_step,
            )
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                _run_authoring_session(
                    execution_id,
                    target_url=target_url,
                    max_steps=max_steps,
                    temperature=temperature,
                    max_tokens_per_step=max_tokens_per_step,
                )
                return None
            raise RuntimeError("Unable to enqueue AI authoring session.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError("Celery is required to enqueue AI authoring sessions.") from _CELERY_IMPORT_ERROR

    _run_authoring_session(
        execution_id,
        target_url=target_url,
        max_steps=max_steps,
        temperature=temperature,
        max_tokens_per_step=max_tokens_per_step,
    )
    return None


def _can_run_eager_fallback() -> bool:
    return bool(settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER)
