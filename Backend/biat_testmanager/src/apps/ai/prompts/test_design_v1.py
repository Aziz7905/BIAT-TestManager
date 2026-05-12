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
    rag_context: list[dict[str, Any]],
    repository_memory: list[dict[str, Any]],
    jira_issue_key: str = "",
) -> list[dict[str, str]]:
    context = {
        "project": project_name,
        "target_suite": target_suite_name,
        "target_section": target_section_name,
        "jira_issue_key": jira_issue_key,
        "normalized_intent": normalized_intent,
        "rag_context": rag_context,
        "repository_memory": repository_memory,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are BIAT TestManager's AI test design workflow. Generate only "
                "reviewable test-design drafts for a web application. Drafts are not "
                "saved automatically; they must map cleanly to TestSuite, TestSection, "
                "nested child TestSection, TestScenario, TestCase, and TestCaseRevision. "
                "Use section.children when the test suite needs child sections.\n\n"
                "Ground every case in the provided requirements and repository memory. "
                "If context is missing, lower confidence and add open_questions. "
                "Avoid duplicates; when repository memory shows a similar case, add it "
                "to possible_duplicates instead of blindly creating the same test. "
                "Expected results must be concrete assertions, never vague phrases like "
                "'works correctly'. Generate positive, negative, and edge cases when "
                "the supplied context supports them.\n\n"
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
