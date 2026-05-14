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


@shared_task(bind=True, name="ai.run_authoring_session")
def run_authoring_session_task(
    self,
    execution_id: str,
    target_url: str = "",
    max_steps: int = 12,
):
    return _run_authoring_session(
        execution_id,
        target_url=target_url,
        max_steps=max_steps,
    )


def _run_authoring_session(
    execution_id: str,
    *,
    target_url: str = "",
    max_steps: int = 12,
):
    execution = run_browser_authoring_session(
        execution_id,
        target_url=target_url,
        max_steps=max_steps,
    )
    return {
        "execution_id": str(execution.id),
        "status": execution.status,
    }


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


def enqueue_authoring_session_task(
    execution_id: str,
    *,
    target_url: str = "",
    max_steps: int = 12,
):
    if hasattr(run_authoring_session_task, "delay"):
        try:
            async_result = run_authoring_session_task.delay(
                execution_id,
                target_url,
                max_steps,
            )
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                _run_authoring_session(
                    execution_id,
                    target_url=target_url,
                    max_steps=max_steps,
                )
                return None
            raise RuntimeError("Unable to enqueue AI authoring session.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError("Celery is required to enqueue AI authoring sessions.") from _CELERY_IMPORT_ERROR

    _run_authoring_session(
        execution_id,
        target_url=target_url,
        max_steps=max_steps,
    )
    return None


def _can_run_eager_fallback() -> bool:
    return bool(settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER)
