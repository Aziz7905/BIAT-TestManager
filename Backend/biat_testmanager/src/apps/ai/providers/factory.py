from __future__ import annotations

from decimal import Decimal

from apps.accounts.models import ModelProfilePurpose, Team, TeamAIConfig
from apps.accounts.services.team_ai import DEFAULT_MODEL_NAME, DEFAULT_OLLAMA_ENDPOINT

from .anthropic import AnthropicProvider
from .azure_openai import AzureOpenAIProvider
from .base import LLMProvider, LLMProviderNotConfiguredError
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider

DEFAULT_PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
}


def _temperature_as_float(value: Decimal | float | int | str) -> float:
    return float(value)


def _get_config(team: Team) -> TeamAIConfig:
    config = getattr(team, "ai_config", None)
    if config is not None:
        return config
    try:
        return TeamAIConfig.objects.select_related(
            "provider",
            "default_model_profile",
        ).get(team=team)
    except TeamAIConfig.DoesNotExist as exc:
        raise LLMProviderNotConfiguredError("This team has no AI configuration.") from exc


def _select_model_profile(config: TeamAIConfig, purpose: str):
    if purpose and purpose != ModelProfilePurpose.DEFAULT:
        profile = (
            config.model_profiles.filter(purpose=purpose)
            .order_by("-is_default", "slug")
            .first()
        )
        if profile:
            return profile
    if config.default_model_profile_id:
        return config.default_model_profile
    return config.model_profiles.filter(is_default=True).first()


def get_llm_provider(
    team: Team,
    *,
    purpose: str = ModelProfilePurpose.DEFAULT,
) -> LLMProvider:
    config = _get_config(team)
    if not config.is_active:
        raise LLMProviderNotConfiguredError("This team's AI configuration is disabled.")
    if not config.provider_id:
        raise LLMProviderNotConfiguredError("Choose an AI provider before using AI features.")

    provider = config.provider
    provider_type = provider.provider_type
    profile = _select_model_profile(config, purpose)
    model_name = profile.model_name if profile else DEFAULT_MODEL_NAME
    temperature = _temperature_as_float(profile.temperature if profile else Decimal("0.10"))
    max_tokens = int(profile.max_tokens if profile else 4096)

    if provider_type == "ollama":
        return OllamaProvider(
            endpoint=config.endpoint_url or provider.base_url or DEFAULT_OLLAMA_ENDPOINT,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    api_key = config.api_key
    if not api_key:
        raise LLMProviderNotConfiguredError("This AI provider needs an API key.")

    if provider_type in {"openai", "groq"}:
        return OpenAICompatibleProvider(
            name=provider_type,
            api_key=api_key,
            model_name=model_name,
            base_url=provider.base_url or DEFAULT_PROVIDER_BASE_URLS[provider_type],
            temperature=temperature,
            max_tokens=max_tokens,
            token_parameter="max_completion_tokens"
            if provider_type == "groq"
            else "max_tokens",
        )

    if provider_type == "azure_openai":
        if not config.endpoint_url:
            raise LLMProviderNotConfiguredError("Azure OpenAI needs an endpoint URL.")
        if not config.api_version:
            raise LLMProviderNotConfiguredError("Azure OpenAI needs an API version.")
        return AzureOpenAIProvider(
            api_key=api_key,
            endpoint=config.endpoint_url,
            api_version=config.api_version,
            deployment_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider_type == "anthropic":
        return AnthropicProvider(
            api_key=api_key,
            model_name=model_name,
            base_url=provider.base_url or DEFAULT_PROVIDER_BASE_URLS["anthropic"],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider_type == "gemini":
        return GeminiProvider(
            api_key=api_key,
            model_name=model_name,
            base_url=provider.base_url or DEFAULT_PROVIDER_BASE_URLS["gemini"],
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise LLMProviderNotConfiguredError(f"Unsupported AI provider: {provider_type}.")
