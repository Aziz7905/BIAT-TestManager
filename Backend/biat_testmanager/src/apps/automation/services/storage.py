from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from urllib.parse import urljoin

from django.conf import settings

from apps.automation.models.choices import ArtifactStorageBackend


def store_text_artifact(
    execution,
    *,
    name: str,
    content: str,
    artifact_type: str,
    metadata: dict | None = None,
) -> dict:
    temp_dir = _staging_directory(execution)
    try:
        local_path = temp_dir / name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(content, encoding="utf-8")
        return store_file_artifact(
            execution,
            local_path=local_path,
            artifact_type=artifact_type,
            object_name=name,
            metadata=metadata,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def store_file_artifact(
    execution,
    *,
    local_path: str | Path,
    artifact_type: str,
    object_name: str | None = None,
    metadata: dict | None = None,
) -> dict:
    local_path = Path(local_path)
    object_name = object_name or local_path.name
    storage_key = build_artifact_storage_key(
        execution,
        artifact_type=artifact_type,
        object_name=object_name,
    )
    _upload_to_minio(local_path, storage_key)

    return {
        "type": artifact_type,
        "storage_backend": ArtifactStorageBackend.MINIO,
        "storage_key": storage_key,
        "metadata": metadata or {},
    }


def build_artifact_storage_key(
    execution,
    *,
    artifact_type: str,
    object_name: str,
) -> str:
    project_id = execution.test_case.scenario.section.suite.project_id
    safe_name = object_name.replace("\\", "/").lstrip("/")
    return (
        f"projects/{project_id}/executions/{execution.id}/"
        f"{artifact_type}/{safe_name}"
    )


def _upload_to_minio(local_path: Path, storage_key: str) -> None:
    client = _minio_client()
    client.upload_file(
        str(local_path),
        getattr(settings, "MINIO_BUCKET_NAME", "biat-artifacts"),
        storage_key,
    )


def build_artifact_download_url(artifact, *, expires_in: int = 3600) -> str | None:
    if not artifact.storage_key:
        return None
    if artifact.storage_backend == ArtifactStorageBackend.MINIO:
        return build_minio_download_url(artifact.storage_key, expires_in=expires_in)
    if artifact.storage_backend == ArtifactStorageBackend.LOCAL:
        return urljoin(settings.MEDIA_URL.rstrip("/") + "/", artifact.storage_key)
    return None


def build_minio_download_url(storage_key: str, *, expires_in: int = 3600) -> str | None:
    if not storage_key:
        return None
    try:
        client = _minio_client()
    except ImportError:
        return None
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": getattr(settings, "MINIO_BUCKET_NAME", "biat-artifacts"),
            "Key": storage_key,
        },
        ExpiresIn=expires_in,
    )


def _minio_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=getattr(settings, "MINIO_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=getattr(settings, "MINIO_ACCESS_KEY", "biat"),
        aws_secret_access_key=getattr(settings, "MINIO_SECRET_KEY", "biat-secret"),
        region_name=getattr(settings, "MINIO_REGION_NAME", "us-east-1"),
    )


def _staging_directory(execution) -> Path:
    staging_parent = Path(settings.BASE_DIR).parent / ".runner_workspaces" / "artifact-staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    staging_dir = staging_parent / f"{execution.id}-{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=True, exist_ok=False)
    return staging_dir
