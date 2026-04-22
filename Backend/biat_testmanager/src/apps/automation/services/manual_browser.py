from __future__ import annotations

import time
import traceback

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.automation.models import ExecutionStep, TestExecution
from apps.automation.models.choices import (
    ExecutionBrowser,
    ExecutionPlatform,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionTriggerType,
)
from apps.automation.services.control import is_execution_stop_signaled
from apps.automation.services.grid import cache_browser_session_urls
from apps.automation.services.results import finalize_execution_result
from apps.automation.services.streaming import (
    publish_execution_status_changed,
    publish_execution_step_updated,
)


def create_and_queue_manual_browser_execution(
    *,
    test_case,
    triggered_by,
    target_url: str = "",
    browser: str = ExecutionBrowser.CHROMIUM,
    platform: str = ExecutionPlatform.DESKTOP,
):
    from apps.automation.tasks import enqueue_manual_browser_session_task
    from apps.testing.services.runs import get_or_create_adhoc_run_case

    run_case = get_or_create_adhoc_run_case(test_case, triggered_by=triggered_by)
    attempt_number = (
        run_case.executions.aggregate(max_attempt=Max("attempt_number"))["max_attempt"] or 0
    ) + 1
    execution = TestExecution.objects.create(
        test_case=test_case,
        run_case=run_case,
        script=None,
        environment=None,
        triggered_by=triggered_by,
        trigger_type=ExecutionTriggerType.MANUAL,
        status=ExecutionStatus.QUEUED,
        browser=browser,
        platform=platform,
        attempt_number=attempt_number,
    )
    publish_execution_status_changed(execution)

    try:
        task_identifier = enqueue_manual_browser_session_task(
            str(execution.id),
            target_url=target_url,
        )
        if task_identifier:
            execution.celery_task_id = task_identifier
            execution.save(update_fields=["celery_task_id"])
    except Exception as exc:
        finalize_execution_result(
            execution,
            status=ExecutionStatus.ERROR,
            duration_ms=0,
            total_steps=0,
            passed_steps=0,
            failed_steps=0,
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
        )
    return execution


def run_manual_browser_session(execution_id: str, *, target_url: str = ""):
    execution = TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "run_case",
    ).get(pk=execution_id)

    if execution.status == ExecutionStatus.CANCELLED:
        return execution

    execution.status = ExecutionStatus.RUNNING
    execution.started_at = execution.started_at or timezone.now()
    execution.save(update_fields=["status", "started_at"])
    publish_execution_status_changed(execution)

    step = ExecutionStep.objects.create(
        execution=execution,
        step_index=0,
        action="Manual browser session",
        target_element=target_url or "about:blank",
        status=ExecutionStepStatus.RUNNING,
        executed_at=timezone.now(),
    )
    publish_execution_step_updated(step)

    driver = None
    try:
        driver = _build_driver(execution.browser)
        execution.selenium_session_id = driver.session_id
        execution.save(update_fields=["selenium_session_id"])
        cache_browser_session_urls(str(execution.id), driver.session_id)
        publish_execution_status_changed(execution)

        if target_url:
            driver.get(target_url)

        timeout_seconds = int(
            getattr(settings, "MANUAL_BROWSER_SESSION_TIMEOUT_SECONDS", 1800)
        )
        deadline = time.monotonic() + max(timeout_seconds, 30)
        while time.monotonic() < deadline:
            execution.refresh_from_db(fields=["status"])
            if execution.status == ExecutionStatus.CANCELLED:
                break
            if is_execution_stop_signaled(execution):
                execution.stop()
                break
            time.sleep(0.5)

        execution.refresh_from_db(fields=["status"])
        step.status = ExecutionStepStatus.PASSED
        step.duration_ms = execution.get_duration_ms()
        step.save(update_fields=["status", "duration_ms"])
        publish_execution_step_updated(step)
        finalize_execution_result(
            execution,
            status=ExecutionStatus.CANCELLED,
            duration_ms=execution.get_duration_ms() or 0,
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
            error_message="",
            stack_trace="",
        )
    except Exception as exc:
        step.status = ExecutionStepStatus.FAILED
        step.error_message = str(exc)
        step.stack_trace = traceback.format_exc()
        step.save(update_fields=["status", "error_message", "stack_trace"])
        publish_execution_step_updated(step)
        finalize_execution_result(
            execution,
            status=ExecutionStatus.ERROR,
            duration_ms=execution.get_duration_ms() or 0,
            total_steps=1,
            passed_steps=0,
            failed_steps=1,
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
        )
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass

    return execution


def _build_driver(browser: str):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions

    grid_url = getattr(settings, "SELENIUM_GRID_HUB_URL", "")
    if not grid_url:
        raise RuntimeError("SELENIUM_GRID_HUB_URL is required for manual browser sessions.")
    if browser not in {ExecutionBrowser.CHROMIUM, ExecutionBrowser.CHROME}:
        raise RuntimeError("Manual browser sessions currently support Chrome/Grid only.")

    options = ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    return webdriver.Remote(command_executor=grid_url, options=options)
