from __future__ import annotations

from urllib.parse import urljoin
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


def get_execution_artifact_url(execution, file_name: str) -> str:
    media_url = settings.MEDIA_URL.rstrip("/") + "/"
    relative_path = f"automation_artifacts/{execution.id}/{file_name}"
    return urljoin(media_url, relative_path)


def get_latest_execution_screenshot_url(execution) -> str | None:
    artifact_directory = get_execution_artifact_directory(execution)
    if not artifact_directory.exists():
        return None

    screenshot_candidates = [
        path
        for path in artifact_directory.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    if not screenshot_candidates:
        return None

    latest_screenshot = max(screenshot_candidates, key=lambda path: path.stat().st_mtime)
    return get_execution_artifact_url(execution, latest_screenshot.name)


def get_result_artifacts(result) -> dict:
    from apps.automation.models import TestArtifact

    structured = list(
        TestArtifact.objects.filter(execution=result.execution).values(
            "id", "artifact_type", "storage_path", "metadata_json", "created_at"
        ).order_by("artifact_type", "created_at")
    )
    return {
        "video_url": result.video_url,
        "artifacts_path": result.artifacts_path.url if result.artifacts_path else None,
        "stdout_log_url": get_execution_artifact_url(result.execution, "stdout.log"),
        "stderr_log_url": get_execution_artifact_url(result.execution, "stderr.log"),
        "latest_screenshot_url": get_latest_execution_screenshot_url(result.execution),
        "structured": structured,
    }
