from __future__ import annotations

import json
from pathlib import Path

from apps.automation.services.artifacts import ensure_execution_artifact_directory


def get_execution_control_directory(execution) -> Path:
    return ensure_execution_artifact_directory(execution) / "control"


def ensure_execution_control_directory(execution) -> Path:
    control_directory = get_execution_control_directory(execution)
    control_directory.mkdir(parents=True, exist_ok=True)
    return control_directory


def get_checkpoint_resume_signal_path(execution, checkpoint_key: str) -> Path:
    return ensure_execution_control_directory(execution) / (
        f"checkpoint-{checkpoint_key}.resume.json"
    )


def get_execution_stop_signal_path(execution) -> Path:
    return ensure_execution_control_directory(execution) / "execution.stop"


def write_checkpoint_resume_signal(
    execution,
    checkpoint_key: str,
    payload: dict | None = None,
) -> Path:
    signal_path = get_checkpoint_resume_signal_path(execution, checkpoint_key)
    signal_path.write_text(json.dumps(payload or {}), encoding="utf-8")
    return signal_path


def write_execution_stop_signal(execution) -> Path:
    signal_path = get_execution_stop_signal_path(execution)
    signal_path.write_text("stop", encoding="utf-8")
    return signal_path
