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

from apps.automation.services.execution_runner import run_execution
from apps.automation.services.checkpoints import expire_stale_execution_checkpoints
from apps.automation.services.manual_browser import run_manual_browser_session


@shared_task(bind=True, name="automation.run_test_execution")
def run_test_execution_task(self, execution_id: str):
    execution = run_execution(execution_id)
    return {
        "execution_id": str(execution.id),
        "status": execution.status,
    }


@shared_task(name="automation.expire_stale_execution_checkpoints")
def expire_stale_execution_checkpoints_task():
    expired_count = expire_stale_execution_checkpoints()
    return {
        "expired_checkpoints": expired_count,
    }


@shared_task(bind=True, name="automation.run_manual_browser_session")
def run_manual_browser_session_task(self, execution_id: str, target_url: str = ""):
    execution = run_manual_browser_session(execution_id, target_url=target_url)
    return {
        "execution_id": str(execution.id),
        "status": execution.status,
    }


def enqueue_execution_task(execution_id: str):
    if hasattr(run_test_execution_task, "delay"):
        try:
            async_result = run_test_execution_task.delay(execution_id)
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                run_test_execution_task(None, execution_id)
                return None
            raise RuntimeError("Unable to enqueue execution task.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError("Celery is required to enqueue execution tasks.") from _CELERY_IMPORT_ERROR

    run_test_execution_task(None, execution_id)
    return None


def enqueue_manual_browser_session_task(execution_id: str, *, target_url: str = ""):
    if hasattr(run_manual_browser_session_task, "delay"):
        try:
            async_result = run_manual_browser_session_task.delay(execution_id, target_url)
            return getattr(async_result, "id", None)
        except Exception as exc:
            if _can_run_eager_fallback():
                run_manual_browser_session_task(None, execution_id, target_url)
                return None
            raise RuntimeError("Unable to enqueue manual browser session.") from exc

    if not _can_run_eager_fallback():
        raise RuntimeError("Celery is required to enqueue manual browser sessions.") from _CELERY_IMPORT_ERROR

    run_manual_browser_session_task(None, execution_id, target_url)
    return None


def _can_run_eager_fallback() -> bool:
    return bool(settings.DEBUG or settings.CELERY_TASK_ALWAYS_EAGER)
