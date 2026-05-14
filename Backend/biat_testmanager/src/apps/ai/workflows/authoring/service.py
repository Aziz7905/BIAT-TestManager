from __future__ import annotations

import json
import traceback
from typing import Any, Callable

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

MAX_AUTHORING_STEPS = 12


class AIAuthoringError(Exception):
    """Raised when an AI browser authoring session cannot be started or run."""


def start_browser_authoring_session(
    *,
    user,
    test_case,
    target_url: str,
    max_steps: int = MAX_AUTHORING_STEPS,
    browser: str = ExecutionBrowser.CHROMIUM,
    platform: str = ExecutionPlatform.DESKTOP,
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
        trigger_type=ExecutionTriggerType.MANUAL,
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
    max_steps: int = MAX_AUTHORING_STEPS,
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

            observation = tool.observe()
            decision = _next_browser_action(
                provider,
                goal=goal,
                observation=observation,
                trace=trace,
                max_steps=max_steps,
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
                return execution

            if action_name == "ask_user":
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
                return execution

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
        max_tokens=500,
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
    )


def _bounded_max_steps(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = MAX_AUTHORING_STEPS
    return max(2, min(parsed, MAX_AUTHORING_STEPS))


def _cache_session_if_available(execution: TestExecution, tool: BrowserAuthoringTool) -> None:
    session_id = tool.get_stream_session_id()
    if not session_id:
        return
    execution.selenium_session_id = session_id
    execution.save(update_fields=["selenium_session_id"])
    cache_browser_session_urls(str(execution.id), session_id)
    publish_execution_status_changed(execution)
