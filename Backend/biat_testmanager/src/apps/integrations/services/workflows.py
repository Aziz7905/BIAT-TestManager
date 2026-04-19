from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Team, UserProfile
from apps.integrations.access import (
    can_manage_project_integrations,
    can_manage_team_integrations,
)
from apps.integrations.models import (
    ExternalIssueLink,
    IntegrationActionLog,
    IntegrationActionStatus,
    IntegrationConfig,
    RepositoryBinding,
    UserIntegrationCredential,
    WebhookEvent,
)
from apps.projects.models import Project

User = get_user_model()

GENERIC_SIGNATURE_HEADER = "X-BIAT-Signature-256"


def configure_team_integration(
    *,
    actor: User,
    team: Team,
    provider_slug: str,
    config_data: dict[str, Any],
    is_active: bool = True,
) -> IntegrationConfig:
    """Configure shared integration settings for a team."""
    if not can_manage_team_integrations(actor, team):
        raise PermissionDenied("You do not have permission to manage this team's integrations.")

    serialized_config = json.dumps(config_data or {})
    config, _ = IntegrationConfig.objects.update_or_create(
        team=team,
        project=None,
        provider_slug=provider_slug,
        defaults={
            "config_json_encrypted": serialized_config,
            "is_active": bool(is_active and config_data),
        },
    )
    return config


def configure_project_integration(
    *,
    actor: User,
    project: Project,
    provider_slug: str,
    config_data: dict[str, Any],
    is_active: bool = True,
) -> IntegrationConfig:
    """Configure project-level integration settings that override team defaults."""
    if not can_manage_project_integrations(actor, project):
        raise PermissionDenied("You do not have permission to manage this project's integrations.")

    serialized_config = json.dumps(config_data or {})
    config, _ = IntegrationConfig.objects.update_or_create(
        team=project.team,
        project=project,
        provider_slug=provider_slug,
        defaults={
            "config_json_encrypted": serialized_config,
            "is_active": bool(is_active and config_data),
        },
    )
    return config


def store_user_integration_credential(
    *,
    profile: UserProfile,
    provider_slug: str,
    credential_data: dict[str, Any],
    is_active: bool = True,
) -> UserIntegrationCredential:
    """Store an acting-as-user credential without exposing its encrypted payload."""
    serialized_credential = json.dumps(credential_data or {})
    credential, _ = UserIntegrationCredential.objects.update_or_create(
        user_profile=profile,
        provider_slug=provider_slug,
        defaults={
            "credential_json_encrypted": serialized_credential,
            "is_active": bool(is_active and credential_data),
        },
    )
    return credential


def create_repository_binding_for_project(
    *,
    actor: User,
    project: Project,
    provider_slug: str,
    repo_identifier: str,
    default_branch: str = "main",
    metadata_json: dict[str, Any] | None = None,
) -> RepositoryBinding:
    """Bind a project to a source repository so webhooks can be scoped."""
    if not can_manage_project_integrations(actor, project):
        raise PermissionDenied("You do not have permission to bind repositories for this project.")

    try:
        return RepositoryBinding.objects.create(
            project=project,
            provider_slug=provider_slug,
            repo_identifier=repo_identifier.strip(),
            default_branch=(default_branch or "main").strip(),
            metadata_json=metadata_json or {},
            created_by=actor,
        )
    except IntegrityError as exc:
        raise ValidationError(
            {"repo_identifier": "This repository is already bound to the project."}
        ) from exc


def update_repository_binding(
    *,
    actor: User,
    binding: RepositoryBinding,
    default_branch: str | None = None,
    metadata_json: dict[str, Any] | None = None,
    is_active: bool | None = None,
) -> RepositoryBinding:
    """Update a repository binding without changing its project identity."""
    if not can_manage_project_integrations(actor, binding.project):
        raise PermissionDenied("You do not have permission to update this repository binding.")

    update_fields = ["updated_at"]
    if default_branch is not None:
        binding.default_branch = default_branch.strip() or "main"
        update_fields.append("default_branch")
    if metadata_json is not None:
        binding.metadata_json = metadata_json
        update_fields.append("metadata_json")
    if is_active is not None:
        binding.is_active = is_active
        update_fields.append("is_active")
    binding.save(update_fields=update_fields)
    return binding


def process_webhook_event(
    *,
    provider_slug: str,
    event_type: str,
    external_id: str | None,
    payload_json: dict[str, Any],
    headers_json: dict[str, Any] | None = None,
    repository_binding: RepositoryBinding | None = None,
) -> tuple[WebhookEvent, bool]:
    """Persist a webhook delivery and attach it to a repository binding when possible."""
    if external_id:
        existing = WebhookEvent.objects.filter(
            provider_slug=provider_slug,
            external_id=external_id,
        ).first()
        if existing:
            return existing, False

    binding = repository_binding or _find_repository_binding(provider_slug, payload_json)
    try:
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                repository_binding=binding,
                project=binding.project if binding else None,
                provider_slug=provider_slug,
                event_type=event_type,
                external_id=external_id or None,
                payload_json=payload_json,
                headers_json=headers_json or {},
            )
    except IntegrityError:
        event = WebhookEvent.objects.get(
            provider_slug=provider_slug,
            external_id=external_id,
        )
        return event, False

    return event, True


def verify_webhook_signature(
    *,
    provider_slug: str,
    payload_json: dict[str, Any],
    raw_body: bytes,
    headers,
) -> RepositoryBinding:
    """Verify a webhook HMAC signature and return the matched repository binding."""
    binding = _find_repository_binding(provider_slug, payload_json)
    if binding is None:
        raise PermissionDenied("Webhook repository binding was not found.")

    secret = _get_webhook_secret(
        provider_slug=provider_slug,
        project=binding.project,
    )
    if not secret:
        raise PermissionDenied("Webhook secret is not configured.")

    signature = _get_signature_header(provider_slug, headers)
    if not signature:
        raise PermissionDenied("Webhook signature is missing.")

    if not _is_valid_hmac_signature(
        secret=secret,
        raw_body=raw_body,
        signature=signature,
    ):
        raise PermissionDenied("Webhook signature is invalid.")

    return binding


def mark_webhook_event_processed(event: WebhookEvent) -> WebhookEvent:
    """Mark durable webhook storage as processed once downstream work succeeds."""
    event.status = "processed"
    event.processed_at = timezone.now()
    event.save(update_fields=["status", "processed_at"])
    return event


def link_external_issue_to_object(
    *,
    actor: User,
    project: Project,
    provider_slug: str,
    external_key: str,
    content_object: object,
    external_url: str = "",
    metadata_json: dict[str, Any] | None = None,
) -> ExternalIssueLink:
    """Link a Jira/GitHub issue to a project-owned domain object."""
    if not can_manage_project_integrations(actor, project):
        raise PermissionDenied("You do not have permission to link external issues for this project.")

    object_project = _resolve_project_for_content_object(content_object)
    if object_project is None or object_project.id != project.id:
        raise ValidationError({"object_id": "The target object does not belong to this project."})

    content_type = ContentType.objects.get_for_model(content_object)
    try:
        return ExternalIssueLink.objects.create(
            project=project,
            provider_slug=provider_slug,
            external_key=external_key.strip(),
            external_url=external_url or "",
            content_type=content_type,
            object_id=str(content_object.pk),
            metadata_json=metadata_json or {},
            created_by=actor,
        )
    except IntegrityError as exc:
        raise ValidationError(
            {"external_key": "This external issue is already linked to the target object."}
        ) from exc


def record_integration_action_result(
    *,
    provider_slug: str,
    action_type: str,
    status: str,
    actor_user: User | None = None,
    team: Team | None = None,
    project: Project | None = None,
    request_json: dict[str, Any] | None = None,
    response_json: dict[str, Any] | None = None,
    error_message: str = "",
) -> IntegrationActionLog:
    """Append an audit record for an external integration operation."""
    completed_at = timezone.now() if status != IntegrationActionStatus.PENDING else None
    return IntegrationActionLog.objects.create(
        team=team or (project.team if project else None),
        project=project,
        provider_slug=provider_slug,
        action_type=action_type,
        actor_user=actor_user,
        request_json=request_json or {},
        response_json=response_json or {},
        status=status,
        error_message=error_message,
        completed_at=completed_at,
    )


def _find_repository_binding(
    provider_slug: str,
    payload_json: dict[str, Any],
) -> RepositoryBinding | None:
    repo_identifier = _extract_repo_identifier(provider_slug, payload_json)
    if not repo_identifier:
        return None
    return RepositoryBinding.objects.select_related("project", "project__team").filter(
        provider_slug=provider_slug,
        repo_identifier=repo_identifier,
        is_active=True,
    ).first()


def _get_webhook_secret(*, provider_slug: str, project: Project) -> str:
    project_config = IntegrationConfig.objects.filter(
        provider_slug=provider_slug,
        is_active=True,
        project=project,
    ).first()
    if project_config:
        secret = project_config.config_data.get("webhook_secret")
        if secret:
            return str(secret)

    team_config = IntegrationConfig.objects.filter(
        provider_slug=provider_slug,
        is_active=True,
        team=project.team,
        project__isnull=True,
    ).first()
    if team_config:
        secret = team_config.config_data.get("webhook_secret")
        if secret:
            return str(secret)
    return ""


def _get_signature_header(provider_slug: str, headers) -> str:
    if provider_slug == "github":
        return str(headers.get("X-Hub-Signature-256") or "")
    return str(headers.get(GENERIC_SIGNATURE_HEADER) or "")


def _is_valid_hmac_signature(*, secret: str, raw_body: bytes, signature: str) -> bool:
    expected_digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    expected_signature = f"sha256={expected_digest}"
    normalized_signature = signature.strip()
    if not normalized_signature.startswith("sha256="):
        normalized_signature = f"sha256={normalized_signature}"
    return hmac.compare_digest(expected_signature, normalized_signature)


def _extract_repo_identifier(
    provider_slug: str,
    payload_json: dict[str, Any],
) -> str:
    if provider_slug == "github":
        repository = payload_json.get("repository") or {}
        return str(repository.get("full_name") or "").strip()
    if provider_slug == "jenkins":
        return str(
            payload_json.get("job_name")
            or payload_json.get("repository")
            or payload_json.get("repo_identifier")
            or ""
        ).strip()
    return str(payload_json.get("repo_identifier") or "").strip()


def _resolve_project_for_content_object(content_object) -> Project | None:
    if isinstance(content_object, Project):
        return content_object

    project = getattr(content_object, "project", None)
    if isinstance(project, Project):
        return project

    suite = getattr(content_object, "suite", None)
    if suite is not None:
        return getattr(suite, "project", None)

    section = getattr(content_object, "section", None)
    if section is not None:
        suite = getattr(section, "suite", None)
        return getattr(suite, "project", None)

    scenario = getattr(content_object, "scenario", None)
    if scenario is not None:
        section = getattr(scenario, "section", None)
        suite = getattr(section, "suite", None)
        return getattr(suite, "project", None)

    test_case = getattr(content_object, "test_case", None)
    if test_case is not None:
        scenario = getattr(test_case, "scenario", None)
        section = getattr(scenario, "section", None)
        suite = getattr(section, "suite", None)
        return getattr(suite, "project", None)

    run = getattr(content_object, "run", None)
    if run is not None:
        return getattr(run, "project", None)

    run_case = getattr(content_object, "run_case", None)
    if run_case is not None:
        run = getattr(run_case, "run", None)
        if run is not None:
            return getattr(run, "project", None)

    return None
