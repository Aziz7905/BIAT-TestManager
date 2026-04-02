try:
    from celery import shared_task
except ModuleNotFoundError:  # pragma: no cover - fallback for environments without Celery installed yet
    def shared_task(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

from apps.automation.services.execution_runner import run_execution


@shared_task(bind=True, name="automation.run_test_execution")
def run_test_execution_task(self, execution_id: str):
    execution = run_execution(execution_id)
    return {
        "execution_id": str(execution.id),
        "status": execution.status,
    }


def enqueue_execution_task(execution_id: str):
    if hasattr(run_test_execution_task, "delay"):
        async_result = run_test_execution_task.delay(execution_id)
        return getattr(async_result, "id", None)

    run_test_execution_task(None, execution_id)
    return None
