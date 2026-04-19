from __future__ import annotations

from apps.automation.models import AutomationFramework
from apps.automation.services.python_script_runner import (
    UnsupportedExecutionConfigurationError,
    run_python_automation_execution,
)


def run_playwright_execution(execution) -> dict:
    return run_python_automation_execution(
        execution,
        framework=AutomationFramework.PLAYWRIGHT,
        framework_label="Playwright",
        python_bin_setting="AUTOMATION_PLAYWRIGHT_PYTHON_BIN",
        workdir_setting="AUTOMATION_PLAYWRIGHT_WORKDIR",
    )
