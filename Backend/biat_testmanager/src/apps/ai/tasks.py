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

from apps.ai.services.test_generation_workflow import run_test_generation_workflow


@shared_task(bind=True, name="ai.run_generation_session")
def run_generation_session_task(self, session_id: str):
    result = run_test_generation_workflow(session_id)
    session = result["session"]
    return {
        "session_id": str(session.id),
        "status": session.status,
    }


def enqueue_generation_session_task(session_id: str):
    if hasattr(run_generation_session_task, "delay"):
        try:
            async_result = run_generation_session_task.delay(session_id)
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                run_generation_session_task(None, session_id)
                return None
            raise RuntimeError("Unable to enqueue AI generation session.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError("Celery is required to enqueue AI generation sessions.") from _CELERY_IMPORT_ERROR

    run_generation_session_task(None, session_id)
    return None


def _can_run_eager_fallback() -> bool:
    return bool(settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER)
