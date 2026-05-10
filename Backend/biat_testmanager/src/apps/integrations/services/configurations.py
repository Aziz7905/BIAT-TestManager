"""IntegrationConfig + UserIntegrationCredential are the single sources of truth."""
from __future__ import annotations

import json

from apps.accounts.models import Team, UserProfile
from apps.integrations.models import IntegrationConfig, UserIntegrationCredential

JIRA_PROVIDER = "jira"
GITHUB_PROVIDER = "github"
JENKINS_PROVIDER = "jenkins"


def _get_or_create_team_integration(team: Team, provider_key: str) -> IntegrationConfig:
    config, _ = IntegrationConfig.objects.get_or_create(
        team=team,
        project=None,
        provider_id=provider_key,
        defaults={"config_json_encrypted": "{}"},
    )
    return config


def _upsert_team_integration_payload(
    *,
    team: Team,
    provider_key: str,
    payload: dict,
) -> IntegrationConfig:
    config, _ = IntegrationConfig.objects.update_or_create(
        team=team,
        project=None,
        provider_id=provider_key,
        defaults={
            "config_json_encrypted": json.dumps(payload or {}),
            "is_active": bool(payload),
        },
    )
    return config


def _merge_provider_payload(
    *,
    team: Team,
    provider_key: str,
    values: dict,
    allowed_keys: tuple[str, ...],
) -> None:
    config = _get_or_create_team_integration(team, provider_key)
    payload = config.config_data
    changed = False

    for key in allowed_keys:
        if key not in values:
            continue
        changed = True
        if values[key]:
            payload[key] = values[key]
        else:
            payload.pop(key, None)

    if changed:
        _upsert_team_integration_payload(
            team=team,
            provider_key=provider_key,
            payload=payload,
        )


def update_team_integrations(*, team: Team, integrations: dict | None) -> None:
    """Persist the nested Team API integration payload into IntegrationConfig."""
    integrations = integrations or {}

    jira = integrations.get(JIRA_PROVIDER)
    github = integrations.get(GITHUB_PROVIDER)
    jenkins = integrations.get(JENKINS_PROVIDER)

    if isinstance(jira, dict):
        _merge_provider_payload(
            team=team,
            provider_key=JIRA_PROVIDER,
            values=jira,
            allowed_keys=("base_url", "project_key"),
        )
    if isinstance(github, dict):
        _merge_provider_payload(
            team=team,
            provider_key=GITHUB_PROVIDER,
            values=github,
            allowed_keys=("org", "repo"),
        )
    if isinstance(jenkins, dict):
        _merge_provider_payload(
            team=team,
            provider_key=JENKINS_PROVIDER,
            values=jenkins,
            allowed_keys=("url",),
        )


def get_team_integration_values(team: Team) -> dict[str, dict[str, str | None]]:
    """Read all integration values for a team as a nested provider payload."""
    values = {
        JIRA_PROVIDER: {"base_url": None, "project_key": None},
        GITHUB_PROVIDER: {"org": None, "repo": None},
        JENKINS_PROVIDER: {"url": None},
    }

    related_manager = getattr(team, "integration_configs", None)
    configs = related_manager.all() if related_manager is not None else []

    for config in configs:
        payload = config.config_data
        if config.provider_id == JIRA_PROVIDER:
            values[JIRA_PROVIDER]["base_url"] = (
                payload.get("base_url") or values[JIRA_PROVIDER]["base_url"]
            )
            values[JIRA_PROVIDER]["project_key"] = (
                payload.get("project_key") or values[JIRA_PROVIDER]["project_key"]
            )
        elif config.provider_id == GITHUB_PROVIDER:
            values[GITHUB_PROVIDER]["org"] = payload.get("org") or values[GITHUB_PROVIDER]["org"]
            values[GITHUB_PROVIDER]["repo"] = payload.get("repo") or values[GITHUB_PROVIDER]["repo"]
        elif config.provider_id == JENKINS_PROVIDER:
            values[JENKINS_PROVIDER]["url"] = payload.get("url") or values[JENKINS_PROVIDER]["url"]

    return values


def update_user_integration_token(
    profile: UserProfile,
    provider_key: str,
    token: str | None,
) -> None:
    existing = UserIntegrationCredential.objects.filter(
        user_profile=profile,
        provider_id=provider_key,
    ).first()
    payload = existing.credential_data if existing else {}
    if token:
        payload["token"] = token
    else:
        payload.pop("token", None)

    UserIntegrationCredential.objects.update_or_create(
        user_profile=profile,
        provider_id=provider_key,
        defaults={
            "credential_json_encrypted": json.dumps(payload),
            "is_active": bool(payload),
        },
    )


def get_user_integration_token(profile: UserProfile, provider_key: str) -> str | None:
    credential = (
        profile.integration_credentials.filter(
            provider_id=provider_key,
            is_active=True,
        )
        .first()
    )
    if credential:
        return credential.credential_data.get("token")
    return None
