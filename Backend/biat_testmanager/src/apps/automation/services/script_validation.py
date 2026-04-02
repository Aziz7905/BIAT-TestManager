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

    if framework == AutomationFramework.PLAYWRIGHT and language == AutomationLanguage.PYTHON:
        _validate_python_script(script_content, errors, warnings)
    elif framework == AutomationFramework.PLAYWRIGHT:
        warnings.append(
            "This script is stored successfully, but only Python Playwright scripts are executable in v1."
        )
    elif framework == AutomationFramework.SELENIUM:
        warnings.append(
            "Selenium scripts are stored for future compatibility and are not executable in v1."
        )

    return _build_validation_result(errors, warnings)


def _validate_python_script(
    script_content: str,
    errors: list[str],
    warnings: list[str],
):
    try:
        compile(script_content, "<automation_script>", "exec")
    except SyntaxError as exc:
        errors.append(f"Python syntax error at line {exc.lineno}: {exc.msg}")
        return

    if "playwright" not in script_content.lower():
        warnings.append(
            "The script compiled successfully, but it does not appear to reference Playwright explicitly."
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
