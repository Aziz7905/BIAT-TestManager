from __future__ import annotations

import json

from apps.accounts.models import Team, UserProfile
from apps.integrations.models import IntegrationConfig, UserIntegrationCredential

JIRA_PROVIDER = "jira"
GITHUB_PROVIDER = "github"
JENKINS_PROVIDER = "jenkins"


def _get_or_create_team_integration(team: Team, provider_slug: str) -> IntegrationConfig:
    config, _ = IntegrationConfig.objects.get_or_create(
        team=team,
        project=None,
        provider_slug=provider_slug,
        defaults={"config_json_encrypted": "{}"},
    )
    return config


def _upsert_team_integration_payload(
    *,
    team: Team,
    provider_slug: str,
    payload: dict,
) -> IntegrationConfig:
    config, _ = IntegrationConfig.objects.update_or_create(
        team=team,
        project=None,
        provider_slug=provider_slug,
        defaults={
            "config_json_encrypted": json.dumps(payload or {}),
            "is_active": bool(payload),
        },
    )
    return config


def sync_team_integrations_from_legacy(team: Team) -> None:
    jira_payload = {}
    if team.jira_base_url:
        jira_payload["base_url"] = team.jira_base_url
    if team.jira_project_key:
        jira_payload["project_key"] = team.jira_project_key
    if jira_payload:
        jira_config = _get_or_create_team_integration(team, JIRA_PROVIDER)
        if not jira_config.config_data:
            jira_config.set_config_data(jira_payload)
            jira_config.save(update_fields=["config_json_encrypted", "updated_at"])

    github_payload = {}
    if team.github_org:
        github_payload["org"] = team.github_org
    if team.github_repo:
        github_payload["repo"] = team.github_repo
    if github_payload:
        github_config = _get_or_create_team_integration(team, GITHUB_PROVIDER)
        if not github_config.config_data:
            github_config.set_config_data(github_payload)
            github_config.save(update_fields=["config_json_encrypted", "updated_at"])

    if team.jenkins_url:
        jenkins_config = _get_or_create_team_integration(team, JENKINS_PROVIDER)
        if not jenkins_config.config_data:
            jenkins_config.set_config_data({"url": team.jenkins_url})
            jenkins_config.save(update_fields=["config_json_encrypted", "updated_at"])


def update_team_integrations(
    *,
    team: Team,
    jira_base_url=...,
    jira_project_key=...,
    github_org=...,
    github_repo=...,
    jenkins_url=...,
) -> None:
    if jira_base_url is not ... or jira_project_key is not ...:
        config = _get_or_create_team_integration(team, JIRA_PROVIDER)
        payload = config.config_data
        if jira_base_url is not ...:
            if jira_base_url:
                payload["base_url"] = jira_base_url
            else:
                payload.pop("base_url", None)
        if jira_project_key is not ...:
            if jira_project_key:
                payload["project_key"] = jira_project_key
            else:
                payload.pop("project_key", None)
        _upsert_team_integration_payload(
            team=team,
            provider_slug=JIRA_PROVIDER,
            payload=payload,
        )

    if github_org is not ... or github_repo is not ...:
        config = _get_or_create_team_integration(team, GITHUB_PROVIDER)
        payload = config.config_data
        if github_org is not ...:
            if github_org:
                payload["org"] = github_org
            else:
                payload.pop("org", None)
        if github_repo is not ...:
            if github_repo:
                payload["repo"] = github_repo
            else:
                payload.pop("repo", None)
        _upsert_team_integration_payload(
            team=team,
            provider_slug=GITHUB_PROVIDER,
            payload=payload,
        )

    if jenkins_url is not ...:
        config = _get_or_create_team_integration(team, JENKINS_PROVIDER)
        payload = config.config_data
        if jenkins_url:
            payload["url"] = jenkins_url
        else:
            payload.pop("url", None)
        _upsert_team_integration_payload(
            team=team,
            provider_slug=JENKINS_PROVIDER,
            payload=payload,
        )


def get_team_integration_values(team: Team) -> dict[str, str | None]:
    values = {
        "jira_base_url": team.jira_base_url,
        "jira_project_key": team.jira_project_key,
        "github_org": team.github_org,
        "github_repo": team.github_repo,
        "jenkins_url": team.jenkins_url,
    }

    related_manager = getattr(team, "integration_configs", None)
    configs = related_manager.all() if related_manager is not None else []

    for config in configs:
        payload = config.config_data
        if config.provider_slug == JIRA_PROVIDER:
            values["jira_base_url"] = payload.get("base_url") or values["jira_base_url"]
            values["jira_project_key"] = payload.get("project_key") or values["jira_project_key"]
        elif config.provider_slug == GITHUB_PROVIDER:
            values["github_org"] = payload.get("org") or values["github_org"]
            values["github_repo"] = payload.get("repo") or values["github_repo"]
        elif config.provider_slug == JENKINS_PROVIDER:
            values["jenkins_url"] = payload.get("url") or values["jenkins_url"]

    return values


def sync_user_credentials_from_legacy(profile: UserProfile) -> None:
    if profile.jira_token:
        credential, _ = UserIntegrationCredential.objects.get_or_create(
            user_profile=profile,
            provider_slug=JIRA_PROVIDER,
            defaults={"credential_json_encrypted": "{}"},
        )
        if not credential.credential_data:
            credential.set_credential_data({"token": profile.jira_token})
            credential.save(update_fields=["credential_json_encrypted", "updated_at"])

    if profile.github_token:
        credential, _ = UserIntegrationCredential.objects.get_or_create(
            user_profile=profile,
            provider_slug=GITHUB_PROVIDER,
            defaults={"credential_json_encrypted": "{}"},
        )
        if not credential.credential_data:
            credential.set_credential_data({"token": profile.github_token})
            credential.save(update_fields=["credential_json_encrypted", "updated_at"])


def update_user_integration_token(
    profile: UserProfile,
    provider_slug: str,
    token: str | None,
) -> None:
    existing = UserIntegrationCredential.objects.filter(
        user_profile=profile,
        provider_slug=provider_slug,
    ).first()
    payload = existing.credential_data if existing else {}
    if token:
        payload["token"] = token
    else:
        payload.pop("token", None)

    UserIntegrationCredential.objects.update_or_create(
        user_profile=profile,
        provider_slug=provider_slug,
        defaults={
            "credential_json_encrypted": json.dumps(payload),
            "is_active": bool(payload),
        },
    )


def get_user_integration_token(profile: UserProfile, provider_slug: str) -> str | None:
    credential = next(
        (
            item
            for item in profile.integration_credentials.filter(
                provider_slug=provider_slug,
                is_active=True,
            )[:1]
        ),
        None,
    )
    if credential:
        return credential.credential_data.get("token")

    if provider_slug == JIRA_PROVIDER:
        return profile.jira_token
    if provider_slug == GITHUB_PROVIDER:
        return profile.github_token
    return None
