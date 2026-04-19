from __future__ import annotations

from apps.automation.models import AutomationFramework
from apps.automation.services.python_script_runner import (
    UnsupportedExecutionConfigurationError,
    run_python_automation_execution,
)


def run_selenium_execution(execution) -> dict:
    return run_python_automation_execution(
        execution,
        framework=AutomationFramework.SELENIUM,
        framework_label="Selenium",
        python_bin_setting="AUTOMATION_SELENIUM_PYTHON_BIN",
        workdir_setting="AUTOMATION_SELENIUM_WORKDIR",
    )
