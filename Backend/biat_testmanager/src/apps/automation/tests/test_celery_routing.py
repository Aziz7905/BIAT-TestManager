"""Verify each Celery task lands on the queue mapped in settings.

Roadmap Step 1: three queues — ai_agent, regression, interactive — with explicit
routing rules. This test guards against future task renames or routing
regressions.
"""
from django.conf import settings
from django.test import TestCase


EXPECTED_QUEUES = {"ai_agent", "regression", "interactive"}

EXPECTED_ROUTES = {
    "automation.run_test_execution": "regression",
    "automation.run_manual_browser_session": "interactive",
    "automation.expire_stale_execution_checkpoints": "regression",
}


class CeleryRoutingTests(TestCase):
    def test_three_queues_declared(self):
        names = {q.name for q in settings.CELERY_TASK_QUEUES}
        self.assertEqual(names, EXPECTED_QUEUES)

    def test_default_queue_is_regression(self):
        self.assertEqual(settings.CELERY_TASK_DEFAULT_QUEUE, "regression")

    def test_each_known_task_routes_to_its_workload_queue(self):
        for task_name, expected_queue in EXPECTED_ROUTES.items():
            with self.subTest(task=task_name):
                route = settings.CELERY_TASK_ROUTES.get(task_name)
                self.assertIsNotNone(route, f"{task_name} has no explicit route")
                self.assertEqual(route.get("queue"), expected_queue)

    def test_routes_only_use_declared_queues(self):
        for task_name, route in settings.CELERY_TASK_ROUTES.items():
            with self.subTest(task=task_name):
                self.assertIn(route["queue"], EXPECTED_QUEUES)
