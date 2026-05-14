from __future__ import annotations

import json
from typing import Any

DESIGN_PROMPT_VERSION = "test_design_v1"


def build_test_design_messages(
    *,
    objective: str,
    project_name: str,
    target_suite_name: str | None,
    target_section_name: str | None,
    normalized_intent: dict[str, Any],
    requirement_extraction: dict[str, Any],
    rag_context: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
    generation_limits: dict[str, int],
    allowed_scenario_types: list[str],
    jira_issue_key: str = "",
) -> list[dict[str, str]]:
    context = {
        "project": project_name,
        "target_suite": target_suite_name,
        "target_section": target_section_name,
        "jira_issue_key": jira_issue_key,
        "normalized_intent": normalized_intent,
        "requirement_extraction": requirement_extraction,
        "rag_context": rag_context,
        "repository_memory": repository_memory,
        "generation_limits": generation_limits,
        "allowed_scenario_types": allowed_scenario_types,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are BIAT TestManager's AI test design workflow. Generate only "
                "reviewable test-design drafts. Drafts are not "
                "saved automatically; they must map cleanly to TestSuite, TestSection, "
                "nested child TestSection, TestScenario, TestCase, and TestCaseRevision. "
                "Use section.children when the test suite needs child sections.\n\n"
                "Use requirement_extraction as the main grounding object. Ground every "
                "case in extracted requirement facts, supplied requirement chunks, and "
                "repository memory. "
                "If context is missing, lower confidence and add open_questions. "
                "Avoid duplicates; when repository memory shows a similar case, add it "
                "to possible_duplicates instead of blindly creating the same test. "
                "Do not collapse a source bundle into only one happy path and one "
                "negative case. When requirement_extraction contains multiple business "
                "rules, validation rules, error conditions, update rules, generated "
                "outputs, or acceptance criteria, cover each concrete rule with a "
                "scenario or test case unless it is clearly a duplicate. "
                "Expected results must be concrete assertions, never vague phrases like "
                "'works correctly'. Every step must mention a concrete field, table, "
                "screen, API, job/process, output, file/report, message, validation "
                "rule, update rule, or business rule when those facts are available. "
                "Do not write generic steps such as 'Enter valid data', 'Enter invalid "
                "data', 'Submit the request', 'Generate facture', 'Verify the result', "
                "'Perform the action', or 'The application shows the expected state'.\n\n"
                "Choose scenario_type only from the allowed_scenario_types in context. "
                "For batch_job, data_processing, reporting, or integration requirements, "
                "produce backend/process-style steps: data setup, job/process/API "
                "execution, output/file/report validation, database/update verification, "
                "and edge/error validation. Use browser/UI steps only when the extracted "
                "requirement type or screens support a UI flow. Obey generation_limits. "
                "Generate positive, negative, and edge cases when the supplied context "
                "supports them.\n\n"
                "Return exactly one JSON object matching the provided schema."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Objective:\n{objective}\n\n"
                "Context JSON:\n"
                f"{json.dumps(context, ensure_ascii=True, default=str)}"
            ),
        },
    ]
