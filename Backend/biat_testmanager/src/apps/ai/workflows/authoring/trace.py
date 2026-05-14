from __future__ import annotations

from typing import Any

from apps.ai.workflows.authoring.service import AIAuthoringError
from apps.automation.models import ExecutionStep, TestExecution
from apps.automation.models.choices import ExecutionStepStatus
from apps.testing.models.choices import TestCaseDesignStatus
from apps.testing.services import update_test_case_with_revision
from apps.testing.services.access import can_manage_test_case_record


def save_authoring_trace_as_draft_steps(*, execution: TestExecution, user) -> dict[str, Any]:
    execution = TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "test_case__scenario__section__suite__project",
    ).get(pk=execution.pk)
    test_case = execution.test_case
    if not can_manage_test_case_record(user, test_case):
        raise AIAuthoringError("You do not have permission to save this authoring trace.")

    trace_steps = list(
        ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.PASSED,
        ).order_by("step_index")
    )
    if not trace_steps:
        raise AIAuthoringError("This authoring session has no passed steps to save.")

    case_steps = [_trace_step_to_case_step(step) for step in trace_steps]
    updated = update_test_case_with_revision(
        test_case,
        steps=case_steps,
        design_status=TestCaseDesignStatus.DRAFT,
        created_by=user,
        source_snapshot_json={
            "mutation_source": "ai_browser_authoring_trace",
            "authoring_execution_id": str(execution.id),
        },
    )
    latest_revision = updated.revisions.order_by("-version_number", "-created_at").first()
    return {
        "test_case_id": str(updated.id),
        "revision_id": str(latest_revision.id) if latest_revision else None,
        "version": updated.version,
        "step_count": len(case_steps),
        "steps": case_steps,
    }


def _trace_step_to_case_step(step: ExecutionStep) -> dict[str, str]:
    target = step.target_element or "current page"
    if step.action == "navigate":
        return {
            "step": f"Open {target}.",
            "outcome": "The target page is loaded.",
        }
    if step.action == "fill":
        return {
            "step": f"Fill {target} with {step.input_value or 'the required value'}.",
            "outcome": f"{target} contains the entered value.",
        }
    if step.action == "click":
        return {
            "step": f"Click {target}.",
            "outcome": "The application accepts the action and advances to the next state.",
        }
    if step.action == "select":
        return {
            "step": f"Select {step.input_value or 'the required option'} in {target}.",
            "outcome": f"{target} shows the selected option.",
        }
    if step.action == "assert_text":
        return {
            "step": f"Verify text {step.input_value or target} is visible.",
            "outcome": "The expected text is present on the page.",
        }
    if step.action == "assert_visible":
        return {
            "step": f"Verify {target} is visible.",
            "outcome": f"{target} is visible.",
        }
    return {
        "step": f"{step.action} {target}.",
        "outcome": "The browser action completes successfully.",
    }
