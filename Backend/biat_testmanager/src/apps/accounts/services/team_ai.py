from __future__ import annotations

from decimal import Decimal

from apps.accounts.models import AIProvider, ModelProfile, Team, TeamAIConfig

DEFAULT_MODEL_PROFILE_SLUG = "default"
UNSET = object()


def get_or_create_team_ai_config(team: Team) -> TeamAIConfig:
    config, _ = TeamAIConfig.objects.get_or_create(
        team=team,
        defaults={
            "provider": team.ai_provider,
            "api_key": team.ai_api_key,
            "monthly_budget": team.monthly_token_budget,
        },
    )
    return config


def sync_team_ai_config_from_legacy(team: Team) -> TeamAIConfig:
    config = get_or_create_team_ai_config(team)

    update_fields: list[str] = []
    if config.provider_id is None and team.ai_provider_id is not None:
        config.provider = team.ai_provider
        update_fields.append("provider")

    if not config.api_key and team.ai_api_key:
        config.api_key = team.ai_api_key
        update_fields.append("api_key")

    if config.monthly_budget == 100000 and team.monthly_token_budget != 100000:
        config.monthly_budget = team.monthly_token_budget
        update_fields.append("monthly_budget")

    if update_fields:
        config.save(update_fields=update_fields)

    ensure_default_model_profile(
        config,
        model_name=team.ai_model or "gpt-4o-mini",
    )
    return config


def ensure_default_model_profile(
    team_ai_config: TeamAIConfig,
    *,
    model_name: str,
    deployment_mode: str = "cloud",
) -> ModelProfile:
    default_profile = team_ai_config.default_model_profile
    if default_profile:
        update_fields: list[str] = []
        if default_profile.model_name != model_name:
            default_profile.model_name = model_name
            update_fields.append("model_name")
        if update_fields:
            default_profile.save(update_fields=update_fields)
        return default_profile

    profile, created = ModelProfile.objects.get_or_create(
        team_ai_config=team_ai_config,
        slug=DEFAULT_MODEL_PROFILE_SLUG,
        defaults={
            "purpose": "default",
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
    model_name: str | None | object = UNSET,
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
    elif team.ai_model:
        effective_model_name = team.ai_model

    if effective_model_name:
        ensure_default_model_profile(config, model_name=effective_model_name)

    return config


def get_effective_ai_provider(team: Team):
    ai_config = getattr(team, "ai_config", None)
    if ai_config and ai_config.provider_id:
        return ai_config.provider
    return team.ai_provider


def get_effective_ai_api_key(team: Team) -> str | None:
    ai_config = getattr(team, "ai_config", None)
    if ai_config and ai_config.api_key:
        return ai_config.api_key
    return team.ai_api_key


def get_effective_ai_model(team: Team) -> str:
    ai_config = getattr(team, "ai_config", None)
    if ai_config and ai_config.default_model_profile_id:
        return ai_config.default_model_profile.model_name
    return team.ai_model


def get_effective_monthly_budget(team: Team) -> int:
    ai_config = getattr(team, "ai_config", None)
    if ai_config:
        return ai_config.monthly_budget
    return team.monthly_token_budget
