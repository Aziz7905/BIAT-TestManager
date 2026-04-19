from __future__ import annotations

from typing import Any

from apps.automation.models.choices import (
    AutomationFramework,
    AutomationLanguage,
)


def validate_script_content(
    framework: str,
    language: str,
    script_content: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not script_content.strip():
        errors.append("Script content cannot be empty.")
        return _build_validation_result(errors, warnings)

    if framework in {AutomationFramework.PLAYWRIGHT, AutomationFramework.SELENIUM}:
        framework_label = "Playwright" if framework == AutomationFramework.PLAYWRIGHT else "Selenium"
        if language == AutomationLanguage.PYTHON:
            _validate_python_script(
                script_content,
                errors,
                warnings,
                framework_label=framework_label,
                module_hint=framework,
            )
        else:
            warnings.append(
                f"This script is stored successfully, but only Python {framework_label} scripts are executable in v1."
            )

    return _build_validation_result(errors, warnings)


def _validate_python_script(
    script_content: str,
    errors: list[str],
    warnings: list[str],
    *,
    framework_label: str,
    module_hint: str,
):
    try:
        compile(script_content, "<automation_script>", "exec")
    except SyntaxError as exc:
        errors.append(f"Python syntax error at line {exc.lineno}: {exc.msg}")
        return

    if module_hint not in script_content.lower():
        warnings.append(
            f"The script compiled successfully, but it does not appear to reference {framework_label} explicitly."
        )


def _build_validation_result(
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "is_valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }
