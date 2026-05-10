from __future__ import annotations

from apps.automation.models.choices import ArtifactType
from apps.automation.services.storage import build_artifact_download_url


def get_latest_execution_screenshot_url(execution) -> str | None:
    from apps.automation.models import TestArtifact

    latest_screenshot = (
        TestArtifact.objects.filter(
            execution=execution,
            artifact_type=ArtifactType.SCREENSHOT,
        )
        .order_by("-created_at")
        .first()
    )
    if latest_screenshot is None:
        return None
    return build_artifact_download_url(latest_screenshot)


def get_result_artifacts(result) -> dict:
    from apps.automation.models import TestArtifact

    artifacts = list(
        TestArtifact.objects.filter(execution=result.execution).order_by(
            "artifact_type",
            "created_at",
        )
    )
    structured = [
        {
            "id": artifact.id,
            "artifact_type": artifact.artifact_type,
            "storage_backend": artifact.storage_backend,
            "storage_key": artifact.storage_key,
            "download_url": build_artifact_download_url(artifact),
            "metadata_json": artifact.metadata_json,
            "created_at": artifact.created_at,
        }
        for artifact in artifacts
    ]
    stdout_artifact = _find_log_artifact(artifacts, "stdout", "stdout.log")
    stderr_artifact = _find_log_artifact(artifacts, "stderr", "stderr.log")
    return {
        "video_url": result.video_url,
        "artifacts_path": result.artifacts_path.url if result.artifacts_path else None,
        "stdout_log_url": build_artifact_download_url(stdout_artifact) if stdout_artifact else None,
        "stderr_log_url": build_artifact_download_url(stderr_artifact) if stderr_artifact else None,
        "latest_screenshot_url": get_latest_execution_screenshot_url(result.execution),
        "structured": structured,
    }


def _find_log_artifact(artifacts, label: str, file_name: str):
    for artifact in artifacts:
        if artifact.artifact_type != ArtifactType.LOG:
            continue
        if artifact.metadata_json.get("label") == label:
            return artifact
        if artifact.storage_key.endswith(f"/{file_name}"):
            return artifact
    return None
