"""Commit a passed AI authoring trace as a Selenium ``AutomationScript`` row.

Pipeline: authoring trace (ExecutionStep) -> Selenium Python script (translator)
-> AutomationScript row (this module).

The result is an active, AI-generated AutomationScript pinned to the same
TestCaseRevision the agent was working against. Any previously active script
for the same (test_case, framework, language) tuple is deactivated so the
regression pipeline picks up the new one.
"""

from __future__ import annotations

from django.db import transaction

from apps.ai.workflows.authoring.service import AIAuthoringError
from apps.ai.workflows.authoring.translator import render_selenium_python
from apps.automation.models import AutomationScript, ExecutionStep, TestExecution
from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
    AutomationScriptGeneratedBy,
    ExecutionStatus,
    ExecutionStepStatus,
    ExecutionTriggerType,
)
from apps.testing.services.access import can_manage_test_case_record


@transaction.atomic
def commit_authoring_trace_as_selenium_script(
    *,
    execution: TestExecution,
    user,
) -> AutomationScript:
    """Create an AutomationScript from this AI authoring execution.

    Constraints:
      - Execution must be an AI authoring run.
      - Execution must have ended in PASSED state.
      - At least one PASSED step must be present.
      - Caller must have permission to manage the target test case.

    Side effects:
      - Any prior active Selenium/Python AutomationScript on the same TestCase
        is deactivated.
      - The new AutomationScript is created with ``is_active=True`` and
        ``generated_by=AI``.
    """
    if execution.trigger_type != ExecutionTriggerType.AI_AUTHORING:
        raise AIAuthoringError(
            "This execution is not an AI authoring session; "
            "use the regression script editor instead."
        )

    # Re-fetch with the FK chain we need for permission + revision lookup.
    execution = TestExecution.objects.select_related(
        "test_case",
        "test_case__scenario",
        "test_case__scenario__section",
        "test_case__scenario__section__suite",
        "test_case__scenario__section__suite__project",
    ).get(pk=execution.pk)
    test_case = execution.test_case

    if not can_manage_test_case_record(user, test_case):
        raise AIAuthoringError(
            "You do not have permission to save this authoring trace as a script."
        )

    if execution.status != ExecutionStatus.PASSED:
        raise AIAuthoringError(
            "Only PASSED AI authoring traces can be saved as a Selenium script."
        )

    passed_steps = list(
        ExecutionStep.objects.filter(
            execution=execution,
            status=ExecutionStepStatus.PASSED,
        ).order_by("step_index")
    )
    if not passed_steps:
        raise AIAuthoringError("This authoring trace has no passed steps to translate.")

    target_url = _extract_target_url(passed_steps)
    script_content = render_selenium_python(
        test_case_title=test_case.title,
        target_url=target_url,
        steps=passed_steps,
    )

    revision = (
        test_case.revisions.order_by("-version_number", "-created_at").first()
    )

    existing_script = (
        AutomationScript.objects.filter(
            test_case=test_case,
            test_case_revision=revision,
            framework=AutomationFramework.SELENIUM,
            language=AutomationLanguage.PYTHON,
            generated_by=AutomationScriptGeneratedBy.AI,
            script_content=script_content,
        )
        .order_by("-script_version", "-created_at")
        .first()
    )
    if existing_script is not None:
        if not existing_script.is_active:
            existing_script.is_active = True
            existing_script.save(update_fields=["is_active"])
        return existing_script

    # AutomationScript.save() handles script_version assignment and
    # deactivation of prior active scripts for the same (test_case, framework,
    # language) tuple. We just create with is_active=True.
    return AutomationScript.objects.create(
        test_case=test_case,
        test_case_revision=revision,
        framework=AutomationFramework.SELENIUM,
        language=AutomationLanguage.PYTHON,
        script_content=script_content,
        generated_by=AutomationScriptGeneratedBy.AI,
        is_active=True,
    )


def _extract_target_url(steps: list[ExecutionStep]) -> str:
    """Pull the navigate target URL out of the recorded trace, if any."""
    for step in steps:
        if (step.action or "").strip().lower() == "navigate":
            return (step.target_element or "").strip()
    return ""


__all__ = ["commit_authoring_trace_as_selenium_script"]
