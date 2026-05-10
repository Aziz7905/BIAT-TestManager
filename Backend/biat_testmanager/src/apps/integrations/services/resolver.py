"""Integration credential resolver.

The seam every AI agent (and any other service that calls Jira/GitHub/Jenkins)
must go through. The agent declares its mode and the resolver returns the
right credentials — never read `Team.*` or `UserProfile.*` directly.

See docs/PLATFORM.md hard rules 12 and 13.

Mode semantics:
    "act_as_user" — the operation should be attributed to a specific user
                    (e.g., a tester clicking "create Jira bug from this run").
                    Resolver returns the user's `UserIntegrationCredential`.
                    Falls back to app credentials only when explicitly allowed
                    by the IntegrationConfig.

    "act_as_app"  — the operation runs on behalf of the platform/team
                    (webhook reactions, scheduled syncs, AI agent operations).
                    Resolver returns the team-level `IntegrationConfig`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from apps.accounts.models import Team
from apps.integrations.models import IntegrationConfig, UserIntegrationCredential

IntegrationResolutionMode = Literal["act_as_user", "act_as_app"]


@dataclass(frozen=True)
class IntegrationCredentialBundle:
    """The result of resolving credentials for a given integration call.

    `config` is the team/project-level IntegrationConfig (the platform's bot
    settings). `credential` is the user's personal credential when resolved
    in `act_as_user` mode. Either may be None depending on the mode and what
    is configured.
    """

    provider: str
    mode: IntegrationResolutionMode
    config: IntegrationConfig | None
    credential: UserIntegrationCredential | None

    @property
    def has_credentials(self) -> bool:
        if self.credential and self.credential.credential_data:
            return True
        if self.config and self.config.config_data:
            return True
        return False


def _select_team_config(
    *,
    team: Team,
    project,
    provider_key: str,
) -> IntegrationConfig | None:
    queryset = IntegrationConfig.objects.filter(
        team=team,
        provider_id=provider_key,
        is_active=True,
    )
    # Prefer project-scoped config when a project is provided
    if project is not None:
        project_config = queryset.filter(project=project).first()
        if project_config:
            return project_config
    return queryset.filter(project__isnull=True).first()


def _select_user_credential(
    *,
    actor_user,
    provider_key: str,
) -> UserIntegrationCredential | None:
    if actor_user is None:
        return None
    profile = getattr(actor_user, "profile", None)
    if profile is None:
        return None
    return UserIntegrationCredential.objects.filter(
        user_profile=profile,
        provider_id=provider_key,
        is_active=True,
    ).first()


def resolve_integration_credentials(
    *,
    provider: str,
    team: Team,
    project=None,
    actor_user=None,
    mode: IntegrationResolutionMode = "act_as_app",
    allow_app_fallback: bool = False,
) -> IntegrationCredentialBundle:
    """Resolve the credentials to use for a given integration call.

    `mode` decides which credential takes precedence:

    - `act_as_app`  → team/project IntegrationConfig.
    - `act_as_user` → actor_user's UserIntegrationCredential. If not present,
                      the resolver falls back to the app credential ONLY when
                      `allow_app_fallback=True` (defaults to False so calls
                      that need user attribution fail loudly instead of
                      silently posting as the bot).
    """
    provider_key = provider
    config = _select_team_config(team=team, project=project, provider_key=provider_key)

    if mode == "act_as_app":
        return IntegrationCredentialBundle(
            provider=provider_key,
            mode="act_as_app",
            config=config,
            credential=None,
        )

    credential = _select_user_credential(
        actor_user=actor_user,
        provider_key=provider_key,
    )
    if credential is None and not allow_app_fallback:
        return IntegrationCredentialBundle(
            provider=provider_key,
            mode="act_as_user",
            config=None,
            credential=None,
        )

    return IntegrationCredentialBundle(
        provider=provider_key,
        mode="act_as_user",
        config=config if credential is None else None,
        credential=credential,
    )
