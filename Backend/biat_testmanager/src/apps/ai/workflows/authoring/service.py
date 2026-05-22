from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Callable

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import ModelProfilePurpose
from apps.ai.providers.base import LLMProvider, LLMProviderResponseError
from apps.ai.providers.brain import get_team_brain
from apps.ai.workflows.authoring.browser_tools import (
    BrowserAuthoringTool,
    build_browser_authoring_tool,
)
from apps.ai.workflows.authoring.blockers import detect_blocker
from apps.ai.workflows.authoring.prompts import build_browser_next_action_messages
from apps.ai.workflows.authoring.schemas import (
    ALLOWED_BROWSER_TOOLS,
    BROWSER_ACTION_SCHEMA,
)
from apps.ai.workflows.authoring.success import evaluate_success
from apps.ai.workflows.authoring.trace_utils import (
    best_selector_for_trace,
    describe_target,
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
        logger.exception(
            "AI authoring session %s errored before it could finish cleanly.",
            execution.id,
        )
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
    invalid_decision_count = 0
    trace: list[dict[str, Any]] = []

    execution.status = ExecutionStatus.RUNNING
    execution.started_at = execution.started_at or timezone.now()
    execution.save(update_fields=["status", "started_at"])
    publish_execution_status_changed(execution)

    try:
        tool.start()
        _cache_session_if_available(execution, tool)
        next_step_index = 1
        if target_url:
            result = tool.execute(
                {"tool": "browser_navigate", "url": target_url, "reason": "Open target URL."},
                {},
            )
            step = _record_result_step(
                execution,
                index=next_step_index,
                decision={"tool": "browser_navigate", "url": target_url},
                result=result,
                status=ExecutionStepStatus.PASSED,
            )
            publish_execution_step_updated(step)
            trace.append({"tool": "browser_navigate", **result})
            passed_steps += 1
            next_step_index += 1

        goal = _test_case_goal(execution.test_case)
        while next_step_index <= max_steps:
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
            blocker = detect_blocker(observation)
            if blocker.blocked:
                execution.status = ExecutionStatus.PAUSED
                execution.pause_requested = True
                execution.save(update_fields=["status", "pause_requested"])
                publish_execution_status_changed(execution)
                step = _record_step(
                    execution,
                    index=next_step_index,
                    action_name="ask_user",
                    target=blocker.message,
                    selector="",
                    value=", ".join(blocker.evidence),
                    status=ExecutionStepStatus.PENDING,
                )
                publish_execution_step_updated(step)
                next_step_index += 1
                _wait_until_resumed(execution)
                if execution.status == ExecutionStatus.CANCELLED:
                    return execution
                continue

            success = evaluate_success(goal=goal, observation=observation, trace=trace)
            if success.satisfied:
                step = _record_success_step(execution, next_step_index, success)
                publish_execution_step_updated(step)
                passed_steps += 1
                finalize_execution_result(
                    execution,
                    status=ExecutionStatus.PASSED,
                    duration_ms=execution.get_duration_ms() or 0,
                    total_steps=passed_steps + failed_steps,
                    passed_steps=passed_steps,
                    failed_steps=failed_steps,
                )
                _auto_commit_authoring_script(execution)
                return execution

            try:
                decision = _next_browser_action(
                    provider,
                    goal=goal,
                    observation=observation,
                    trace=trace,
                    max_steps=max_steps,
                    temperature=temperature,
                    max_tokens_per_step=max_tokens_per_step,
                )
            except (AIAuthoringError, LLMProviderResponseError) as exc:
                invalid_decision_count += 1
                trace.append(
                    {
                        "tool": "invalid_tool_call",
                        "status": "rejected",
                        "error": str(exc),
                        "reason": "Provider response could not be used as a BIAT browser tool call.",
                    }
                )
                if invalid_decision_count >= 3:
                    failed_steps += 1
                    step = _record_step(
                        execution,
                        index=next_step_index,
                        action_name="invalid_tool_call",
                        target="provider response",
                        selector="",
                        value="",
                        status=ExecutionStepStatus.FAILED,
                        error_message=str(exc),
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
                    )
                    return execution
                continue

            decision = _normalize_browser_decision(decision, observation)
            tool_name = str(decision.get("tool") or "")
            validation_error = (
                _decision_validation_error(decision, observation)
                or _repeated_fill_error(decision, trace)
            )
            if validation_error:
                invalid_decision_count += 1
                trace.append(
                    {
                        "tool": tool_name or "invalid_tool_call",
                        "status": "rejected",
                        "error": validation_error,
                        "reason": decision.get("reason") or "",
                        "decision": _safe_trace_decision(decision),
                    }
                )
                if invalid_decision_count >= 3:
                    failed_steps += 1
                    step = _record_step(
                        execution,
                        index=next_step_index,
                        action_name=_canonical_action_for_tool(tool_name) or "invalid_tool_call",
                        target=decision.get("element")
                        or decision.get("target")
                        or tool_name
                        or "invalid tool call",
                        selector="",
                        value=_decision_value(decision),
                        status=ExecutionStepStatus.FAILED,
                        error_message=validation_error,
                    )
                    publish_execution_step_updated(step)
                    finalize_execution_result(
                        execution,
                        status=ExecutionStatus.FAILED,
                        duration_ms=execution.get_duration_ms() or 0,
                        total_steps=passed_steps + failed_steps,
                        passed_steps=passed_steps,
                        failed_steps=failed_steps,
                        error_message=validation_error,
                    )
                    return execution
                continue
            invalid_decision_count = 0
            if tool_name == "browser_finish":
                success = evaluate_success(
                    goal=goal,
                    observation=observation,
                    trace=trace,
                    success_evidence=decision.get("success_evidence") or [],
                )
                if not success.satisfied:
                    failed_steps += 1
                    step = _record_step(
                        execution,
                        index=next_step_index,
                        action_name="finish",
                        target=decision.get("reason") or "Finish requested before success was verified.",
                        selector="",
                        value="; ".join(decision.get("success_evidence") or []),
                        status=ExecutionStepStatus.FAILED,
                        error_message=success.reason,
                    )
                    publish_execution_step_updated(step)
                    finalize_execution_result(
                        execution,
                        status=ExecutionStatus.FAILED,
                        duration_ms=execution.get_duration_ms() or 0,
                        total_steps=passed_steps + failed_steps,
                        passed_steps=passed_steps,
                        failed_steps=failed_steps,
                        error_message=success.reason,
                    )
                    return execution
                step = _record_success_step(execution, next_step_index, success)
                publish_execution_step_updated(step)
                passed_steps += 1
                finalize_execution_result(
                    execution,
                    status=ExecutionStatus.PASSED,
                    duration_ms=execution.get_duration_ms() or 0,
                    total_steps=passed_steps + failed_steps,
                    passed_steps=passed_steps,
                    failed_steps=failed_steps,
                )
                _auto_commit_authoring_script(execution)
                return execution

            if tool_name == "browser_ask_user":
                # Agent itself decided it needs the human. Same end state as a
                # user-initiated pause: keep tool alive, poll for resume.
                execution.status = ExecutionStatus.PAUSED
                execution.pause_requested = True
                execution.save(update_fields=["status", "pause_requested"])
                publish_execution_status_changed(execution)
                _record_step(
                    execution,
                    index=next_step_index,
                    action_name="ask_user",
                    target=decision.get("message") or decision.get("reason") or "Manual input required",
                    selector="",
                    value="",
                    status=ExecutionStepStatus.PENDING,
                )
                next_step_index += 1
                _wait_until_resumed(execution)
                if execution.status == ExecutionStatus.CANCELLED:
                    return execution
                # Fall through to the next loop iteration; observe() picks up
                # whatever state the user left the browser in.
                continue

            try:
                result = tool.execute(decision, observation)
                if result.get("action") == "fill_form":
                    field_results = result.get("field_results") or []
                    for field_result in field_results:
                        field_status = (
                            ExecutionStepStatus.PASSED
                            if field_result.get("status") == "passed"
                            else ExecutionStepStatus.FAILED
                        )
                        step = _record_result_step(
                            execution,
                            index=next_step_index,
                            decision=field_result.get("field") or decision,
                            result=field_result,
                            status=field_status,
                            error_message=field_result.get("message") if field_status == ExecutionStepStatus.FAILED else "",
                        )
                        publish_execution_step_updated(step)
                        if field_status == ExecutionStepStatus.PASSED:
                            passed_steps += 1
                        else:
                            failed_steps += 1
                        next_step_index += 1
                    if result.get("status") != "passed":
                        finalize_execution_result(
                            execution,
                            status=ExecutionStatus.FAILED,
                            duration_ms=execution.get_duration_ms() or 0,
                            total_steps=passed_steps + failed_steps,
                            passed_steps=passed_steps,
                            failed_steps=failed_steps,
                            error_message=result.get("message") or "browser_fill_form failed.",
                        )
                        return execution
                elif result.get("blocked"):
                    execution.status = ExecutionStatus.PAUSED
                    execution.pause_requested = True
                    execution.save(update_fields=["status", "pause_requested"])
                    publish_execution_status_changed(execution)
                    step = _record_step(
                        execution,
                        index=next_step_index,
                        action_name="ask_user",
                        target=result.get("message") or "Manual input required",
                        selector="",
                        value=", ".join(result.get("evidence") or []),
                        status=ExecutionStepStatus.PENDING,
                    )
                    publish_execution_step_updated(step)
                    next_step_index += 1
                    _wait_until_resumed(execution)
                    if execution.status == ExecutionStatus.CANCELLED:
                        return execution
                    continue
                else:
                    step = _record_result_step(
                        execution,
                        index=next_step_index,
                        decision=decision,
                        result=result,
                        status=ExecutionStepStatus.PASSED,
                    )
                    publish_execution_step_updated(step)
                    passed_steps += 1
                    next_step_index += 1

                trace.append({**decision, **result})
                post_observation = tool.observe()
                success = evaluate_success(goal=goal, observation=post_observation, trace=trace)
                if success.satisfied:
                    step = _record_success_step(execution, next_step_index, success)
                    publish_execution_step_updated(step)
                    passed_steps += 1
                    finalize_execution_result(
                        execution,
                        status=ExecutionStatus.PASSED,
                        duration_ms=execution.get_duration_ms() or 0,
                        total_steps=passed_steps + failed_steps,
                        passed_steps=passed_steps,
                        failed_steps=failed_steps,
                    )
                    _auto_commit_authoring_script(execution)
                    return execution
            except Exception as exc:
                failed_steps += 1
                target_attrs = getattr(exc, "target_attrs", {}) or {}
                raw_target = (
                    getattr(exc, "target_ref", "")
                    or decision.get("target")
                    or decision.get("element")
                    or decision.get("element_ref")
                    or decision.get("ref")
                    or decision.get("element_id")
                    or decision.get("selector")
                    or ""
                )
                step = _record_step(
                    execution,
                    index=next_step_index,
                    action_name=_canonical_action_for_tool(tool_name),
                    target=describe_target(target_attrs, fallback=str(raw_target)),
                    selector=best_selector_for_trace(
                        target_attrs,
                        fallback_ref=(
                            decision.get("target")
                            or decision.get("selector")
                            or decision.get("element_ref")
                            or decision.get("ref")
                            or ""
                        ),
                    ),
                    value=_decision_value(decision),
                    status=ExecutionStepStatus.FAILED,
                    error_message=str(exc),
                    stack_trace=traceback.format_exc(),
                    target_attrs=target_attrs,
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

    try:
        execution.refresh_from_db()
    except TestExecution.DoesNotExist:
        logger.warning(
            "AI authoring execution %s disappeared before the task completed.",
            execution.id,
        )
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
    messages = build_browser_next_action_messages(
        goal=goal,
        observation=observation,
        trace=trace,
        max_steps=max_steps,
    )
    decision = provider.chat_json(
        messages,
        BROWSER_ACTION_SCHEMA,
        temperature=temperature,
        max_tokens=max_tokens_per_step,
    )
    tool_name = decision.get("tool")
    if tool_name not in ALLOWED_BROWSER_TOOLS:
        raise AIAuthoringError(f"Unsupported browser tool returned by AI: {tool_name}.")
    return decision


def _normalize_browser_decision(
    decision: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Repair harmless field-placement mistakes before validation.

    The model still has to obey the V2 tool contract. This only handles common
    shape slips that are unambiguous, such as using ``text`` where a fill tool
    expects ``value`` or putting visible text in ``target`` for text checks.
    """
    normalized = dict(decision)
    tool_name = str(normalized.get("tool") or "")

    if tool_name in {
        "browser_click",
        "browser_fill",
        "browser_type",
        "browser_select_option",
        "browser_verify_element_visible",
        "browser_verify_value",
    }:
        normalized = _normalize_decision_target(normalized, observation)

    if tool_name in {"browser_fill", "browser_type"}:
        if normalized.get("value") is None and normalized.get("text") is not None:
            normalized["value"] = normalized.get("text")

    if tool_name == "browser_fill_form":
        normalized = _normalize_fill_form_decision(normalized, observation)

    if tool_name == "browser_verify_text_visible" and not _has_text_argument(normalized):
        refs = _observation_refs(observation)
        for key in ("text", "value", "target", "element"):
            candidate = str(normalized.get(key) or "").strip()
            if _looks_like_verification_text(candidate, refs):
                normalized["text"] = candidate
                break

    return normalized


def _decision_validation_error(
    decision: dict[str, Any],
    observation: dict[str, Any],
) -> str:
    tool_name = str(decision.get("tool") or "")
    refs = _observation_refs(observation)

    if tool_name == "browser_navigate" and not str(decision.get("url") or "").strip():
        return "browser_navigate requires a non-empty url."

    if tool_name in {
        "browser_click",
        "browser_fill",
        "browser_type",
        "browser_select_option",
        "browser_verify_element_visible",
        "browser_verify_value",
    }:
        target = str(decision.get("target") or "").strip()
        if not refs:
            return (
                f"{tool_name} needs an interactive element, but the latest "
                "browser observation contains no element refs. Use browser_wait_for "
                "or browser_ask_user."
            )
        if not target:
            return f"{tool_name} requires a target ref from the latest browser_snapshot."
        if target not in refs:
            return f"{tool_name} target {target!r} is not present in the latest browser_snapshot."

    if tool_name in {"browser_fill", "browser_type"} and decision.get("value") is None:
        return f"{tool_name} requires a value."

    if tool_name == "browser_fill_form":
        fields = decision.get("fields")
        if not isinstance(fields, list) or not fields:
            return "browser_fill_form requires a non-empty fields array."
        if not refs:
            return (
                "browser_fill_form needs interactive elements, but the latest "
                "browser observation contains no element refs. Use browser_wait_for "
                "or browser_ask_user."
            )
        for index, field in enumerate(fields, start=1):
            if not isinstance(field, dict):
                return f"browser_fill_form field {index} must be an object."
            target = str(field.get("target") or "").strip()
            if not target:
                return f"browser_fill_form field {index} requires a target ref."
            if target not in refs:
                return (
                    f"browser_fill_form field {index} target {target!r} is not present "
                    "in the latest browser_snapshot."
                )
            if field.get("value") is None:
                return f"browser_fill_form field {index} requires a value."

    if tool_name == "browser_select_option":
        values = decision.get("values")
        has_values = isinstance(values, list) and bool(values)
        if not has_values and decision.get("value") is None:
            return "browser_select_option requires values or value."

    if tool_name == "browser_press_key" and not str(
        decision.get("key") or decision.get("value") or ""
    ).strip():
        return "browser_press_key requires key."

    if tool_name == "browser_wait_for":
        has_condition = any(
            decision.get(key) is not None for key in ("text", "textGone", "urlContains", "time")
        )
        if not has_condition:
            return "browser_wait_for requires text, textGone, urlContains, or time."

    if tool_name == "browser_verify_text_visible" and not _has_text_argument(decision):
        return "browser_verify_text_visible requires a non-empty text value."
    if tool_name == "browser_verify_text_visible":
        expected_text = str(
            decision.get("text")
            or decision.get("assertion")
            or decision.get("value")
            or ""
        ).strip()
        if expected_text and not _text_visible_in_observation(expected_text, observation):
            return (
                f"browser_verify_text_visible cannot assert {expected_text!r} because "
                "that text is not visible in the current browser_snapshot. Choose a "
                "visible text from the snapshot, wait for it, or use browser_finish "
                "with actual visible success evidence."
            )

    if tool_name == "browser_verify_value" and decision.get("value") is None:
        return "browser_verify_value requires value."

    if tool_name == "browser_ask_user" and not str(
        decision.get("message") or decision.get("reason") or ""
    ).strip():
        return "browser_ask_user requires message or reason."

    return ""


def _text_visible_in_observation(text: str, observation: dict[str, Any]) -> bool:
    expected = str(text or "").strip().lower()
    if not expected:
        return False
    haystack_parts = [observation.get("visible_text_summary") or ""]
    for element in observation.get("interactive_elements") or []:
        if not isinstance(element, dict):
            continue
        haystack_parts.extend(
            [
                str(element.get("role") or ""),
                str(element.get("name") or ""),
                str(element.get("value") or ""),
                str(element.get("line") or ""),
            ]
        )
    return expected in " ".join(haystack_parts).lower()


def _repeated_fill_error(decision: dict[str, Any], trace: list[dict[str, Any]]) -> str:
    tool_name = str(decision.get("tool") or "")
    if tool_name not in {"browser_fill", "browser_type", "browser_fill_form"}:
        return ""

    requested = _fill_signatures_from_decision(decision)
    if not requested:
        return ""

    previous = _successful_fill_signatures(trace)
    duplicates = requested.intersection(previous)
    if not duplicates:
        return ""

    labels = ", ".join(sorted(target for target, _value in duplicates))
    return (
        f"{tool_name} repeats fields already filled with the same values: {labels}. "
        "Choose the next transition action such as browser_click, browser_wait_for, "
        "or a verification tool instead of filling the same fields again."
    )


def _fill_signatures_from_decision(decision: dict[str, Any]) -> set[tuple[str, str]]:
    tool_name = str(decision.get("tool") or "")
    signatures: set[tuple[str, str]] = set()
    if tool_name in {"browser_fill", "browser_type"}:
        target = str(decision.get("target") or "").strip()
        value = str(decision.get("value") or "").strip()
        if target and value:
            signatures.add((target, value))
        return signatures

    if tool_name == "browser_fill_form":
        for field in decision.get("fields") or []:
            if not isinstance(field, dict):
                continue
            target = str(field.get("target") or "").strip()
            value = str(field.get("value") or "").strip()
            if target and value:
                signatures.add((target, value))
    return signatures


def _successful_fill_signatures(trace: list[dict[str, Any]]) -> set[tuple[str, str]]:
    signatures: set[tuple[str, str]] = set()
    for event in trace:
        if not isinstance(event, dict):
            continue
        if str(event.get("status") or "").lower() != "passed":
            continue
        action = str(event.get("action") or event.get("tool") or "").lower()
        if action in {"fill", "browser_fill", "browser_type"}:
            target = str(event.get("target") or "").strip()
            value = str(event.get("value") or "").strip()
            if target and value:
                signatures.add((target, value))
        if action in {"fill_form", "browser_fill_form"}:
            signatures.update(_fill_signatures_from_event_fields(event.get("fields")))
            field_results = event.get("field_results")
            if isinstance(field_results, list):
                for result in field_results:
                    if not isinstance(result, dict):
                        continue
                    signatures.update(_fill_signatures_from_event_fields([result.get("field")]))
    return signatures


def _fill_signatures_from_event_fields(fields: Any) -> set[tuple[str, str]]:
    signatures: set[tuple[str, str]] = set()
    if not isinstance(fields, list):
        return signatures
    for field in fields:
        if not isinstance(field, dict):
            continue
        target = str(field.get("target") or "").strip()
        value = str(field.get("value") or "").strip()
        if target and value:
            signatures.add((target, value))
    return signatures


def _normalize_decision_target(
    decision: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    target = str(decision.get("target") or "").strip()
    if target in _observation_refs(observation):
        return decision

    hint = (
        target
        or str(decision.get("element") or "").strip()
        or str(decision.get("selector") or "").strip()
        or str(decision.get("element_ref") or "").strip()
        or str(decision.get("ref") or "").strip()
    )
    ref = _ref_for_hint(hint, observation)
    if not ref:
        return decision

    normalized = dict(decision)
    normalized["target"] = ref
    normalized.setdefault("element", hint)
    return normalized


def _normalize_fill_form_decision(
    decision: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(decision)
    fields = normalized.get("fields")

    if isinstance(fields, dict):
        fields = [
            {"element": str(key), "target": str(key), "value": value}
            for key, value in fields.items()
        ]

    normalized_fields: list[dict[str, Any]] = []
    for field in fields or []:
        if not isinstance(field, dict):
            continue
        normalized_field = dict(field)
        target = str(normalized_field.get("target") or "").strip()
        if target not in _observation_refs(observation):
            hint = (
                target
                or str(normalized_field.get("element") or "").strip()
                or str(normalized_field.get("name") or "").strip()
            )
            ref = _ref_for_hint(hint, observation)
            if ref:
                normalized_field["target"] = ref
        normalized_fields.append(normalized_field)

    normalized["fields"] = normalized_fields
    return normalized


def _generic_key_hints(key: str) -> tuple[str, ...]:
    hints = {
        "username": ("username", "user", "login"),
        "user": ("username", "user", "login"),
        "login": ("username", "user", "login"),
        "password": ("password", "passwd", "pwd"),
        "pwd": ("password", "passwd", "pwd"),
        "email": ("email", "mail"),
        "firstname": ("firstname", "first", "given"),
        "lastname": ("lastname", "last", "family", "surname"),
        "phone": ("phone", "mobile", "telephone"),
        "name": ("name",),
    }
    return hints.get(key, (key,))


def _ref_for_hint(hint: str, observation: dict[str, Any]) -> str:
    normalized_hint = _compact_token(hint)
    if not normalized_hint:
        return ""

    best_ref = ""
    best_score = 0
    for element in _interactive_elements(observation):
        ref = _element_ref(element)
        if not ref:
            continue
        search_text = _compact_token(_element_search_text(element))
        if not search_text:
            continue
        score = 0
        if normalized_hint == ref:
            score += 100
        if normalized_hint == search_text:
            score += 50
        if normalized_hint in search_text:
            score += 20
        if search_text in normalized_hint:
            score += 10
        for hint_token in _generic_key_hints(normalized_hint):
            if hint_token and hint_token in search_text:
                score += 8
        if score > best_score:
            best_ref = ref
            best_score = score
    return best_ref if best_score >= 8 else ""


def _interactive_elements(observation: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        element
        for element in observation.get("interactive_elements") or []
        if isinstance(element, dict)
    ]


def _element_ref(element: dict[str, Any]) -> str:
    return str(element.get("ref") or element.get("id") or "").strip()


def _element_search_text(element: dict[str, Any]) -> str:
    attrs = element.get("target_attrs") if isinstance(element.get("target_attrs"), dict) else {}
    parts = [
        element.get("role") or "",
        element.get("name") or "",
        element.get("placeholder") or "",
        element.get("line") or "",
        attrs.get("type") or "",
        attrs.get("id") or "",
        attrs.get("name") or "",
        attrs.get("aria_label") or "",
        attrs.get("placeholder") or "",
        attrs.get("text") or "",
    ]
    return " ".join(str(part) for part in parts if part)


def _compact_token(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _observation_refs(observation: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for element in observation.get("interactive_elements") or []:
        if not isinstance(element, dict):
            continue
        ref = str(element.get("ref") or element.get("id") or "").strip()
        if ref:
            refs.add(ref)
    return refs


def _has_text_argument(decision: dict[str, Any]) -> bool:
    return bool(
        str(
            decision.get("text")
            or decision.get("assertion")
            or decision.get("value")
            or ""
        ).strip()
    )


def _looks_like_verification_text(candidate: str, refs: set[str]) -> bool:
    if not candidate:
        return False
    if candidate in refs:
        return False
    if candidate.lower() in {"body", "current page", "page", "screen", "document"}:
        return False
    return any(ch.isalpha() for ch in candidate)


def _safe_trace_decision(decision: dict[str, Any]) -> dict[str, Any]:
    safe = dict(decision)
    if "fields" in safe and isinstance(safe["fields"], list):
        safe["fields"] = [
            {**field, "value": "***"} if isinstance(field, dict) and "value" in field else field
            for field in safe["fields"]
        ]
    if "value" in safe:
        safe["value"] = "***"
    return safe


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


def _record_result_step(
    execution: TestExecution,
    *,
    index: int,
    decision: dict[str, Any],
    result: dict[str, Any],
    status: str,
    error_message: str = "",
    stack_trace: str = "",
) -> ExecutionStep:
    target_attrs = result.get("target_attrs") or {}
    raw_target = (
        result.get("target")
        or decision.get("target")
        or decision.get("element")
        or decision.get("element_ref")
        or decision.get("ref")
        or decision.get("element_id")
        or decision.get("selector")
        or ""
    )
    fallback_ref = (
        decision.get("target")
        or decision.get("selector")
        or decision.get("element_ref")
        or decision.get("ref")
        or ""
    )
    return _record_step(
        execution,
        index=index,
        action_name=_canonical_action_for_tool(
            str(decision.get("tool") or result.get("action") or "")
        ),
        target=describe_target(target_attrs, fallback=str(raw_target)),
        selector=best_selector_for_trace(target_attrs, fallback_ref=str(fallback_ref or "")),
        value=_decision_value(decision),
        status=status,
        duration_ms=result.get("duration_ms"),
        error_message=error_message,
        stack_trace=stack_trace,
        target_attrs=target_attrs,
    )


def _record_success_step(
    execution: TestExecution,
    index: int,
    success,
) -> ExecutionStep:
    evidence = ", ".join(success.evidence) or success.reason or "Objective satisfied"
    url_evidence = _url_contains_evidence(success.evidence)
    if url_evidence:
        return _record_step(
            execution,
            index=index,
            action_name="assert_url",
            target=f"URL contains {url_evidence}",
            selector="",
            value=url_evidence,
            status=ExecutionStepStatus.PASSED,
        )
    return _record_step(
        execution,
        index=index,
        action_name="assert_text",
        target=evidence,
        selector="",
        value=evidence,
        status=ExecutionStepStatus.PASSED,
    )


def _url_contains_evidence(evidence_items) -> str:
    for item in evidence_items or []:
        text = str(item or "").strip()
        prefix = "url contains:"
        if text.lower().startswith(prefix):
            return text[len(prefix) :].strip()
    return ""


def _canonical_action_for_tool(tool_name: str) -> str:
    mapping = {
        "browser_navigate": "navigate",
        "browser_click": "click",
        "browser_type": "fill",
        "browser_fill": "fill",
        "browser_fill_form": "fill",
        "browser_select_option": "select",
        "browser_press_key": "press_key",
        "browser_wait_for": "wait",
        "browser_verify_text_visible": "assert_text",
        "browser_verify_element_visible": "assert_visible",
        "browser_verify_value": "assert_value",
        "browser_console_messages": "console_messages",
        "browser_take_screenshot": "screenshot",
        "browser_detect_blocker": "detect_blocker",
        "browser_snapshot": "snapshot",
        "browser_finish": "finish",
        "browser_ask_user": "ask_user",
        "navigate": "navigate",
        "click": "click",
        "fill": "fill",
        "select": "select",
        "wait": "wait",
        "assert_text": "assert_text",
        "assert_url": "assert_url",
        "assert_visible": "assert_visible",
        "assert_value": "assert_value",
        "press_key": "press_key",
    }
    return mapping.get(tool_name, tool_name or "step")


def _decision_value(decision: dict[str, Any]) -> str:
    if decision.get("value") is not None:
        return str(decision.get("value"))
    if decision.get("text") is not None:
        return str(decision.get("text"))
    if decision.get("key") is not None:
        return str(decision.get("key"))
    values = decision.get("values")
    if isinstance(values, list):
        return ", ".join(str(value) for value in values)
    if decision.get("urlContains") is not None:
        return str(decision.get("urlContains"))
    if decision.get("textGone") is not None:
        return str(decision.get("textGone"))
    if decision.get("time") is not None:
        return str(decision.get("time"))
    return ""


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
