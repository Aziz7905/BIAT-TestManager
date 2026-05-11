"""TeamAIConfig is the single source of truth for team-level AI configuration.

The deprecated `Team.ai_provider`, `Team.ai_api_key`, `Team.ai_model`,
`Team.monthly_token_budget`, `Team.tokens_used_this_month` fields were removed
in roadmap Step 2. All AI configuration now lives in `TeamAIConfig` +
`ModelProfile`.
"""
from __future__ import annotations

from decimal import Decimal

from apps.accounts.models import (
    AIProvider,
    ModelDeploymentMode,
    ModelProfile,
    ModelProfilePurpose,
    Team,
    TeamAIConfig,
)

DEFAULT_MODEL_PROFILE_SLUG = "default"
DEFAULT_MODEL_NAME = "gpt-4o-mini"
DEFAULT_MONTHLY_BUDGET = 1000000
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"
UNSET = object()

CLOUD_PROVIDER_TYPES = {"openai", "azure_openai", "anthropic", "groq"}
LOCAL_PROVIDER_TYPES = {"ollama"}


def infer_deployment_mode(provider: AIProvider | None) -> str:
    if provider and provider.provider_type in LOCAL_PROVIDER_TYPES:
        return ModelDeploymentMode.LOCAL
    return ModelDeploymentMode.CLOUD


def get_or_create_team_ai_config(team: Team) -> TeamAIConfig:
    config, _ = TeamAIConfig.objects.get_or_create(team=team)
    return config


def ensure_default_model_profile(
    team_ai_config: TeamAIConfig,
    *,
    model_name: str,
    deployment_mode: str = ModelDeploymentMode.CLOUD,
) -> ModelProfile:
    default_profile = team_ai_config.default_model_profile
    if default_profile:
        update_fields: list[str] = []
        if default_profile.model_name != model_name:
            default_profile.model_name = model_name
            update_fields.append("model_name")
        if default_profile.deployment_mode != deployment_mode:
            default_profile.deployment_mode = deployment_mode
            update_fields.append("deployment_mode")
        if update_fields:
            default_profile.save(update_fields=update_fields)
        return default_profile

    profile, created = ModelProfile.objects.get_or_create(
        team_ai_config=team_ai_config,
        slug=DEFAULT_MODEL_PROFILE_SLUG,
        defaults={
            "purpose": ModelProfilePurpose.DEFAULT,
            "model_name": model_name,
            "temperature": Decimal("0.10"),
            "max_tokens": 4096,
            "deployment_mode": deployment_mode,
            "is_default": True,
        },
    )

    update_fields: list[str] = []
    if not created and profile.model_name != model_name:
        profile.model_name = model_name
        update_fields.append("model_name")
    if not created and profile.deployment_mode != deployment_mode:
        profile.deployment_mode = deployment_mode
        update_fields.append("deployment_mode")
    if not profile.is_default:
        profile.is_default = True
        update_fields.append("is_default")
    if update_fields:
        profile.save(update_fields=update_fields)

    if team_ai_config.default_model_profile_id != profile.id:
        team_ai_config.default_model_profile = profile
        team_ai_config.save(update_fields=["default_model_profile"])
    return profile


def update_team_ai_settings(
    *,
    team: Team,
    provider: AIProvider | None | object = UNSET,
    api_key: str | None | object = UNSET,
    endpoint_url: str | None | object = UNSET,
    api_version: str | None | object = UNSET,
    model_name: str | None | object = UNSET,
    deployment_mode: str | None | object = UNSET,
    monthly_budget: int | None | object = UNSET,
) -> TeamAIConfig:
    config = get_or_create_team_ai_config(team)
    update_fields: list[str] = []

    if provider is not UNSET:
        if config.provider_id != getattr(provider, "id", None):
            config.provider = provider
            update_fields.append("provider")

    if api_key is not UNSET and config.api_key != api_key:
        config.api_key = api_key or None
        update_fields.append("api_key")

    if endpoint_url is not UNSET:
        next_endpoint_url = (endpoint_url or "").strip()
        if config.endpoint_url != next_endpoint_url:
            config.endpoint_url = next_endpoint_url
            update_fields.append("endpoint_url")

    if api_version is not UNSET:
        next_api_version = (api_version or "").strip()
        if config.api_version != next_api_version:
            config.api_version = next_api_version
            update_fields.append("api_version")

    if isinstance(monthly_budget, int) and config.monthly_budget != monthly_budget:
        config.monthly_budget = monthly_budget
        update_fields.append("monthly_budget")

    if update_fields:
        config.save(update_fields=update_fields)

    effective_model_name = None
    if isinstance(model_name, str) and model_name.strip():
        effective_model_name = model_name.strip()
    elif config.default_model_profile:
        effective_model_name = config.default_model_profile.model_name

    if effective_model_name:
        if isinstance(deployment_mode, str) and deployment_mode:
            effective_deployment_mode = deployment_mode
        elif provider is not UNSET:
            effective_deployment_mode = infer_deployment_mode(config.provider)
        elif config.default_model_profile:
            effective_deployment_mode = config.default_model_profile.deployment_mode
        else:
            effective_deployment_mode = infer_deployment_mode(config.provider)

        ensure_default_model_profile(
            config,
            model_name=effective_model_name,
            deployment_mode=effective_deployment_mode,
        )

    return config


def get_effective_ai_provider(team: Team):
    ai_config = getattr(team, "ai_config", None)
    if ai_config:
        return ai_config.provider
    return None


def get_effective_ai_api_key(team: Team) -> str | None:
    ai_config = getattr(team, "ai_config", None)
    if ai_config:
        return ai_config.api_key
    return None


def get_effective_ai_model(team: Team) -> str:
    ai_config = getattr(team, "ai_config", None)
    if ai_config and ai_config.default_model_profile_id:
        return ai_config.default_model_profile.model_name
    return DEFAULT_MODEL_NAME


def get_effective_ai_endpoint_url(team: Team) -> str:
    ai_config = getattr(team, "ai_config", None)
    if ai_config and ai_config.endpoint_url:
        return ai_config.endpoint_url
    provider = get_effective_ai_provider(team)
    if provider and provider.provider_type == "ollama":
        return DEFAULT_OLLAMA_ENDPOINT
    return ""


def get_effective_ai_api_version(team: Team) -> str:
    ai_config = getattr(team, "ai_config", None)
    if ai_config:
        return ai_config.api_version
    return ""


def get_effective_ai_deployment_mode(team: Team) -> str:
    ai_config = getattr(team, "ai_config", None)
    if ai_config and ai_config.default_model_profile_id:
        return ai_config.default_model_profile.deployment_mode
    return infer_deployment_mode(get_effective_ai_provider(team))


def get_effective_monthly_budget(team: Team) -> int:
    ai_config = getattr(team, "ai_config", None)
    if ai_config:
        return ai_config.monthly_budget
    return DEFAULT_MONTHLY_BUDGET
