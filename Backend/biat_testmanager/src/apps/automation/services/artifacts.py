from __future__ import annotations

from pathlib import Path

from django.conf import settings


def get_execution_artifact_directory(execution) -> Path:
    artifact_root = Path(settings.AUTOMATION_ARTIFACTS_ROOT)
    return artifact_root / str(execution.id)


def ensure_execution_artifact_directory(execution) -> Path:
    artifact_directory = get_execution_artifact_directory(execution)
    artifact_directory.mkdir(parents=True, exist_ok=True)
    return artifact_directory


def write_execution_text_artifact(execution, name: str, content: str) -> Path:
    artifact_directory = ensure_execution_artifact_directory(execution)
    target_path = artifact_directory / name
    target_path.write_text(content, encoding="utf-8")
    return target_path


def get_result_artifacts(result) -> dict:
    return {
        "video_url": result.video_url,
        "artifacts_path": result.artifacts_path.url if result.artifacts_path else None,
    }
