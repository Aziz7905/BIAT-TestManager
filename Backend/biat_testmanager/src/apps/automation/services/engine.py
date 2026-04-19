"""
ExecutionEngine contract and registered adapters.

Both Playwright and Selenium implement the same EngineResult shape so that
scheduling, result persistence, and artifact handling are engine-agnostic.

Adding a new engine:
1. Create a class with a `framework` class attribute and a `run(execution)` method.
2. Register it in _ENGINE_REGISTRY below.
3. Add the framework choice to AutomationFramework if it does not exist yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from apps.automation.models.choices import AutomationFramework


# ---------------------------------------------------------------------------
# Shared result contract
# ---------------------------------------------------------------------------

@dataclass
class EngineResult:
    status: str                             # passed | failed | error | cancelled
    error_message: str = ""
    stack_trace: str = ""
    artifacts: list[dict] = field(default_factory=list)
    # Each artifact dict: {"type": ArtifactType value, "path": str, "metadata": dict}


# ---------------------------------------------------------------------------
# Protocol — both engines must satisfy this shape
# ---------------------------------------------------------------------------

@runtime_checkable
class ExecutionEngine(Protocol):
    framework: str

    def run(self, execution) -> EngineResult: ...


# ---------------------------------------------------------------------------
# Playwright adapter
# ---------------------------------------------------------------------------

class PlaywrightExecutionEngine:
    framework = AutomationFramework.PLAYWRIGHT

    def run(self, execution) -> EngineResult:
        from apps.automation.services.playwright_runner import (
            UnsupportedExecutionConfigurationError,
            run_playwright_execution,
        )

        try:
            raw = run_playwright_execution(execution)
            return EngineResult(
                status=raw["status"],
                error_message=raw.get("error_message") or "",
                stack_trace=raw.get("stack_trace") or "",
                artifacts=raw.get("artifacts") or [],
            )
        except UnsupportedExecutionConfigurationError:
            raise
        except Exception as exc:
            import traceback
            return EngineResult(
                status="error",
                error_message=str(exc),
                stack_trace=traceback.format_exc(),
            )


# ---------------------------------------------------------------------------
# Selenium adapter (stub — same contract, not yet implemented)
# ---------------------------------------------------------------------------

class SeleniumExecutionEngine:
    framework = AutomationFramework.SELENIUM

    def run(self, execution) -> EngineResult:
        from apps.automation.services.selenium_runner import (
            UnsupportedExecutionConfigurationError,
            run_selenium_execution,
        )

        try:
            raw = run_selenium_execution(execution)
            return EngineResult(
                status=raw["status"],
                error_message=raw.get("error_message") or "",
                stack_trace=raw.get("stack_trace") or "",
                artifacts=raw.get("artifacts") or [],
            )
        except UnsupportedExecutionConfigurationError:
            raise
        except Exception as exc:
            import traceback

            return EngineResult(
                status="error",
                error_message=str(exc),
                stack_trace=traceback.format_exc(),
            )


# ---------------------------------------------------------------------------
# Registry and selector
# ---------------------------------------------------------------------------

_ENGINE_REGISTRY: dict[str, ExecutionEngine] = {
    AutomationFramework.PLAYWRIGHT: PlaywrightExecutionEngine(),
    AutomationFramework.SELENIUM: SeleniumExecutionEngine(),
}


def get_engine_for_execution(execution) -> ExecutionEngine:
    """
    Select the engine based on the script's framework, falling back to the
    environment engine if no script is attached.
    """
    from apps.automation.services.playwright_runner import (
        UnsupportedExecutionConfigurationError,
    )

    framework = None
    if execution.script_id:
        framework = execution.script.framework
    elif execution.environment_id:
        framework = execution.environment.engine

    engine = _ENGINE_REGISTRY.get(framework)
    if engine is None:
        raise UnsupportedExecutionConfigurationError(
            f"No engine registered for framework: {framework!r}"
        )
    return engine
