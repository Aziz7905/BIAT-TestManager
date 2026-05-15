from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Any, Callable

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.providers.base import LLMProvider, parse_json_content
from apps.ai.providers.brain import get_team_brain
from apps.ai.workflows.authoring.browser_tools import (
    BrowserAuthoringTool,
    build_browser_authoring_tool,
)
from apps.ai.workflows.authoring.prompts import build_browser_next_action_messages
from apps.ai.workflows.authoring.schemas import (
    ALLOWED_BROWSER_ACTIONS,
    BROWSER_ACTION_SCHEMA,
)
from apps.automation.models import ExecutionStep, TestExecution
from apps.automation.models.choices import (
    ExecutionBrowser,
    ExecutionPlatform,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionTriggerType,
)
from apps.automation.services.access import can_trigger_test_execution
from apps.automation.services.browser_sessions import cache_browser_session_urls
from apps.automation.services.results import finalize_execution_result
from apps.automation.services.streaming import (
    publish_execution_status_changed,
    publish_execution_step_updated,
)

logger = logging.getLogger(__name__)

PAUSE_POLL_INTERVAL_SECONDS = 2


class AIAuthoringError(Exception):
    """Raised when an AI browser authoring session cannot be started or run."""


def start_browser_authoring_session(
    *,
    user,
    test_case,
    target_url: str,
    max_steps: int | None = None,
    browser: str = ExecutionBrowser.CHROMIUM,
    platform: str = ExecutionPlatform.DESKTOP,
    temperature: float | None = None,
    max_tokens_per_step: int | None = None,
) -> TestExecution:
    if not can_trigger_test_execution(user, test_case):
        raise AIAuthoringError("You do not have permission to author this test case.")
    if not target_url:
        raise AIAuthoringError("A target URL is required for AI browser authoring.")

    # Resolve early so configuration errors fail before creating a queued session.
    get_team_brain(
        test_case.scenario.section.suite.project.team,
        purpose=ModelProfilePurpose.EXECUTION,
    )

    from apps.ai.tasks import enqueue_authoring_session_task
    from apps.testing.services.runs import get_or_create_adhoc_run_case

    run_case = get_or_create_adhoc_run_case(test_case, triggered_by=user)
    attempt_number = (
        run_case.executions.aggregate(max_attempt=Max("attempt_number"))["max_attempt"] or 0
    ) + 1
    execution = TestExecution.objects.create(
        test_case=test_case,
        run_case=run_case,
        script=None,
        environment=None,
        triggered_by=user,
        trigger_type=ExecutionTriggerType.AI_AUTHORING,
        status=ExecutionStatus.QUEUED,
        browser=browser,
        platform=platform,
        attempt_number=attempt_number,
        stream_enabled=True,
    )
    publish_execution_status_changed(execution)

    try:
        task_identifier = enqueue_authoring_session_task(
            str(execution.id),
            target_url=target_url,
            max_steps=_bounded_max_steps(max_steps),
            temperature=_bounded_temperature(temperature),
            max_tokens_per_step=_bounded_max_tokens(max_tokens_per_step),
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


def run_browser_authoring_session(
    execution_id: str,
    *,
    target_url: str,
    max_steps: int | None = None,
    temperature: float | None = None,
    max_tokens_per_step: int | None = None,
    browser_tool_factory: Callable[[str], BrowserAuthoringTool] = build_browser_authoring_tool,
    provider: LLMProvider | None = None,
) -> TestExecution:
    execution = TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "test_case__scenario__section__suite__project",
        "test_case__scenario__section__suite__project__team",
    ).get(pk=execution_id)

    if execution.status == ExecutionStatus.CANCELLED:
        return execution

    max_steps = _bounded_max_steps(max_steps)
    temperature = _bounded_temperature(temperature)
    max_tokens_per_step = _bounded_max_tokens(max_tokens_per_step)
    provider = provider or get_team_brain(
        execution.test_case.scenario.section.suite.project.team,
        purpose=ModelProfilePurpose.EXECUTION,
    )
    tool = browser_tool_factory(execution.browser)
    passed_steps = 0
    failed_steps = 0
    trace: list[dict[str, Any]] = []

    execution.status = ExecutionStatus.RUNNING
    execution.started_at = execution.started_at or timezone.now()
    execution.save(update_fields=["status", "started_at"])
    publish_execution_status_changed(execution)

    try:
        tool.start()
        _cache_session_if_available(execution, tool)
        if target_url:
            result = tool.execute(
                {"action": "navigate", "url": target_url, "reason": "Open target URL."},
                {},
            )
            step = _record_step(
                execution,
                index=1,
                action_name="navigate",
                target=target_url,
                selector="",
                value="",
                status=ExecutionStepStatus.PASSED,
                duration_ms=None,
            )
            publish_execution_step_updated(step)
            trace.append({"action": "navigate", "target": target_url, **result})
            passed_steps += 1

        goal = _test_case_goal(execution.test_case)
        for step_number in range(2, max_steps + 1):
            execution.refresh_from_db(fields=["status", "pause_requested"])
            if execution.status == ExecutionStatus.CANCELLED:
                return execution

            # Pause means the user wants to drive the same Selenoid browser via
            # noVNC. Keep the tool alive, do NOT call tool.close(); poll until
            # the user resumes or cancels. On resume we observe a fresh DOM so
            # the agent sees whatever the user changed during take-over.
            if execution.pause_requested or execution.status == ExecutionStatus.PAUSED:
                _wait_until_resumed(execution)
                if execution.status == ExecutionStatus.CANCELLED:
                    return execution

            observation = tool.observe()
            decision = _next_browser_action(
                provider,
                goal=goal,
                observation=observation,
                trace=trace,
                max_steps=max_steps,
                temperature=temperature,
                max_tokens_per_step=max_tokens_per_step,
            )
            action_name = decision.get("action")
            if action_name == "stop":
                status = ExecutionStatus.PASSED if decision.get("success", True) else ExecutionStatus.FAILED
                finalize_execution_result(
                    execution,
                    status=status,
                    duration_ms=execution.get_duration_ms() or 0,
                    total_steps=passed_steps + failed_steps,
                    passed_steps=passed_steps,
                    failed_steps=failed_steps,
                    error_message="" if status == ExecutionStatus.PASSED else decision.get("message", ""),
                )
                if status == ExecutionStatus.PASSED:
                    _auto_commit_authoring_script(execution)
                return execution

            if action_name == "ask_user":
                # Agent itself decided it needs the human. Same end state as a
                # user-initiated pause: keep tool alive, poll for resume.
                execution.status = ExecutionStatus.PAUSED
                execution.pause_requested = True
                execution.save(update_fields=["status", "pause_requested"])
                publish_execution_status_changed(execution)
                _record_step(
                    execution,
                    index=step_number,
                    action_name="ask_user",
                    target=decision.get("message") or decision.get("reason") or "Manual input required",
                    selector="",
                    value="",
                    status=ExecutionStepStatus.PENDING,
                )
                _wait_until_resumed(execution)
                if execution.status == ExecutionStatus.CANCELLED:
                    return execution
                # Fall through to the next loop iteration; observe() picks up
                # whatever state the user left the browser in.
                continue

            try:
                result = tool.execute(decision, observation)
                step = _record_step(
                    execution,
                    index=step_number,
                    action_name=str(action_name),
                    target=(
                        result.get("target")
                        or decision.get("element_ref")
                        or decision.get("ref")
                        or decision.get("element_id")
                        or decision.get("selector")
                        or ""
                    ),
                    selector=decision.get("selector") or decision.get("element_ref") or decision.get("ref") or "",
                    value=decision.get("value") or decision.get("assertion") or "",
                    status=ExecutionStepStatus.PASSED,
                    duration_ms=result.get("duration_ms"),
                    target_attrs=result.get("target_attrs") or {},
                )
                passed_steps += 1
                trace.append({**decision, **result})
            except Exception as exc:
                failed_steps += 1
                step = _record_step(
                    execution,
                    index=step_number,
                    action_name=str(action_name),
                    target=(
                        decision.get("element_ref")
                        or decision.get("ref")
                        or decision.get("element_id")
                        or decision.get("selector")
                        or ""
                    ),
                    selector=decision.get("selector") or decision.get("element_ref") or decision.get("ref") or "",
                    value=decision.get("value") or decision.get("assertion") or "",
                    status=ExecutionStepStatus.FAILED,
                    error_message=str(exc),
                    stack_trace=traceback.format_exc(),
                )
                publish_execution_step_updated(step)
                finalize_execution_result(
                    execution,
                    status=ExecutionStatus.FAILED,
                    duration_ms=execution.get_duration_ms() or 0,
                    total_steps=passed_steps + failed_steps,
                    passed_steps=passed_steps,
                    failed_steps=failed_steps,
                    error_message=str(exc),
                    stack_trace=traceback.format_exc(),
                )
                return execution
            publish_execution_step_updated(step)

        finalize_execution_result(
            execution,
            status=ExecutionStatus.FAILED,
            duration_ms=execution.get_duration_ms() or 0,
            total_steps=passed_steps + failed_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            error_message="AI authoring reached the maximum step count before stopping.",
        )
    except Exception as exc:
        finalize_execution_result(
            execution,
            status=ExecutionStatus.ERROR,
            duration_ms=execution.get_duration_ms() or 0,
            total_steps=passed_steps + failed_steps,
            passed_steps=passed_steps,
            failed_steps=failed_steps,
            error_message=str(exc),
            stack_trace=traceback.format_exc(),
        )
    finally:
        tool.close()

    execution.refresh_from_db()
    return execution


def _next_browser_action(
    provider: LLMProvider,
    *,
    goal: dict[str, Any],
    observation: dict[str, Any],
    trace: list[dict[str, Any]],
    max_steps: int,
    temperature: float,
    max_tokens_per_step: int,
) -> dict[str, Any]:
    messages = [
        {
            "role": "system",
            "content": (
                "Return only one valid JSON object. Do not wrap it in markdown. "
                f"The object must match this schema: {json.dumps(BROWSER_ACTION_SCHEMA, ensure_ascii=True)}"
            ),
        },
        *build_browser_next_action_messages(
            goal=goal,
            observation=observation,
            trace=trace,
            max_steps=max_steps,
        ),
    ]
    response = provider.chat(
        messages,
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens_per_step,
    )
    decision = parse_json_content(response.content)
    action_name = decision.get("action")
    if action_name not in ALLOWED_BROWSER_ACTIONS:
        raise AIAuthoringError(f"Unsupported browser action returned by AI: {action_name}.")
    return decision


def _test_case_goal(test_case) -> dict[str, Any]:
    revision = test_case.revisions.order_by("-version_number", "-created_at").first()
    source = revision or test_case
    return {
        "test_case_id": str(test_case.id),
        "title": source.title,
        "preconditions": source.preconditions,
        "steps": source.steps,
        "expected_result": source.expected_result,
        "test_data": source.test_data,
    }


def _record_step(
    execution: TestExecution,
    *,
    index: int,
    action_name: str,
    target: str,
    selector: str,
    value: str,
    status: str,
    duration_ms: int | None = None,
    error_message: str = "",
    stack_trace: str = "",
    target_attrs: dict[str, Any] | None = None,
) -> ExecutionStep:
    return ExecutionStep.objects.create(
        execution=execution,
        step_index=index,
        action=action_name[:255],
        target_element=(target or "")[:500],
        selector_used=(selector or "")[:1000],
        input_value=(value or "")[:1000],
        status=status,
        error_message=error_message or None,
        stack_trace=stack_trace or None,
        duration_ms=duration_ms,
        executed_at=timezone.now(),
        target_attrs=target_attrs or {},
    )


def _auto_commit_authoring_script(execution: TestExecution) -> None:
    if execution.triggered_by_id is None:
        logger.warning(
            "Skipping AI authoring script auto-save for execution %s without triggered_by.",
            execution.id,
        )
        return

    try:
        from apps.ai.workflows.authoring.commit_script import (
            commit_authoring_trace_as_selenium_script,
        )

        script = commit_authoring_trace_as_selenium_script(
            execution=execution,
            user=execution.triggered_by,
        )
        logger.info(
            "Auto-saved AI authoring Selenium script %s for execution %s.",
            script.id,
            execution.id,
        )
    except Exception:
        logger.exception(
            "Failed to auto-save AI authoring Selenium script for execution %s.",
            execution.id,
        )


def _wait_until_resumed(execution: TestExecution) -> None:
    """Block the authoring loop while the user drives the Selenoid browser.

    The tool stays alive — user has full noVNC keyboard/mouse over the same
    browser session. Returns when ``pause_requested`` is cleared (resume) or
    when ``status`` becomes CANCELLED. On resume we transition status back to
    RUNNING and publish so the frontend updates.

    Trade-off: holds a gevent slot on the ai_agent queue. Acceptable at the
    default 20-session cap; a future V2 swaps to session-reattachment so a
    paused session frees its slot.
    """
    if execution.status != ExecutionStatus.PAUSED:
        execution.status = ExecutionStatus.PAUSED
        execution.save(update_fields=["status"])
    publish_execution_status_changed(execution)

    while True:
        time.sleep(PAUSE_POLL_INTERVAL_SECONDS)
        execution.refresh_from_db(fields=["status", "pause_requested"])
        if execution.status == ExecutionStatus.CANCELLED:
            return
        if not execution.pause_requested:
            execution.status = ExecutionStatus.RUNNING
            execution.save(update_fields=["status"])
            publish_execution_status_changed(execution)
            return


def _bounded_max_steps(value: int | None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = settings.AI_AUTHORING_DEFAULT_MAX_STEPS
    return max(2, min(parsed, settings.AI_AUTHORING_MAX_STEPS_LIMIT))


def _bounded_temperature(value: float | None) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = settings.AI_AUTHORING_DEFAULT_TEMPERATURE
    return max(0.0, min(parsed, 1.0))


def _bounded_max_tokens(value: int | None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = settings.AI_AUTHORING_DEFAULT_MAX_TOKENS_PER_STEP
    return max(50, min(parsed, settings.AI_AUTHORING_MAX_TOKENS_PER_STEP_LIMIT))


def _cache_session_if_available(execution: TestExecution, tool: BrowserAuthoringTool) -> None:
    session_id = tool.get_stream_session_id()
    if not session_id:
        return
    execution.selenium_session_id = session_id
    execution.save(update_fields=["selenium_session_id"])
    cache_browser_session_urls(str(execution.id), session_id)
    publish_execution_status_changed(execution)
