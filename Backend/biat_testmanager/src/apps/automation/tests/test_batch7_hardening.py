from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.automation.tasks import enqueue_execution_task


class _FailingDelayTask:
    def __init__(self):
        self.called_eagerly = False

    def delay(self, execution_id):
        raise RuntimeError("broker unavailable")

    def __call__(self, _self, execution_id):
        self.called_eagerly = True
        return {"execution_id": execution_id, "status": "passed"}


class CeleryHardeningTests(SimpleTestCase):
    @override_settings(DEBUG=True, CELERY_TASK_ALWAYS_EAGER=False)
    def test_enqueue_execution_task_uses_dev_fallback_in_debug(self):
        task = _FailingDelayTask()

        with patch("apps.automation.tasks.run_test_execution_task", task):
            task_id = enqueue_execution_task("execution-id")

        self.assertIsNone(task_id)
        self.assertTrue(task.called_eagerly)

    @override_settings(DEBUG=False, CELERY_TASK_ALWAYS_EAGER=False)
    def test_enqueue_execution_task_raises_when_enqueue_fails_in_production(self):
        task = _FailingDelayTask()

        with patch("apps.automation.tasks.run_test_execution_task", task):
            with self.assertRaises(RuntimeError):
                enqueue_execution_task("execution-id")

        self.assertFalse(task.called_eagerly)
