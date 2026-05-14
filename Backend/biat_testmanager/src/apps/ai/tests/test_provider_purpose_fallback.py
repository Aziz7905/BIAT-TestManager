from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import (
    AIProvider,
    ModelProfile,
    ModelProfilePurpose,
    Organization,
    Team,
    TeamAIConfig,
)
from apps.ai.providers.base import LLMProviderNotConfiguredError
from apps.ai.providers.brain import get_team_brain


class ProviderPurposeFallbackTests(TestCase):
    """Per-purpose ModelProfile resolution with default fallback.

    Simple mode: one default profile powers every purpose.
    Advanced mode: per-purpose profiles override the default; missing purposes
    fall back to the default profile cleanly.
    """

    def setUp(self):
        self.organization = Organization.objects.create(
            name="BIAT",
            domain="biat.tn",
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="AI QA",
        )
        self.provider = AIProvider.objects.create(
            name="Groq",
            provider_type="groq",
            base_url="https://api.groq.com/openai/v1",
            is_active=True,
        )

    def _make_config(self, *, is_active: bool = True) -> TeamAIConfig:
        return TeamAIConfig.objects.create(
            team=self.team,
            provider=self.provider,
            api_key="test-key",
            is_active=is_active,
        )

    def _make_profile(
        self,
        config: TeamAIConfig,
        *,
        slug: str,
        purpose: str,
        model_name: str,
        is_default: bool = False,
    ) -> ModelProfile:
        return ModelProfile.objects.create(
            team_ai_config=config,
            slug=slug,
            purpose=purpose,
            model_name=model_name,
            temperature=Decimal("0.10"),
            max_tokens=4096,
            deployment_mode="cloud",
            is_default=is_default,
        )

    def test_simple_mode_single_default_profile_serves_every_purpose(self):
        config = self._make_config()
        profile = self._make_profile(
            config,
            slug="default",
            purpose=ModelProfilePurpose.DEFAULT,
            model_name="llama-3.3-70b-versatile",
            is_default=True,
        )
        config.default_model_profile = profile
        config.save(update_fields=["default_model_profile"])

        for purpose in (
            ModelProfilePurpose.DEFAULT,
            ModelProfilePurpose.TEST_DESIGN,
            ModelProfilePurpose.REVIEW,
            ModelProfilePurpose.EXECUTION,
        ):
            with self.subTest(purpose=purpose):
                resolved = get_team_brain(self.team, purpose=purpose)
                self.assertEqual(resolved.model_name, "llama-3.3-70b-versatile")

    def test_purpose_specific_profile_overrides_default(self):
        config = self._make_config()
        default_profile = self._make_profile(
            config,
            slug="default",
            purpose=ModelProfilePurpose.DEFAULT,
            model_name="llama-3.3-70b-versatile",
            is_default=True,
        )
        config.default_model_profile = default_profile
        config.save(update_fields=["default_model_profile"])

        self._make_profile(
            config,
            slug="test-design-pro",
            purpose=ModelProfilePurpose.TEST_DESIGN,
            model_name="gemini-2.5-pro",
        )

        design = get_team_brain(self.team, purpose=ModelProfilePurpose.TEST_DESIGN)
        self.assertEqual(design.model_name, "gemini-2.5-pro")

        # Purposes without an override fall back to the default profile.
        for purpose in (
            ModelProfilePurpose.DEFAULT,
            ModelProfilePurpose.REVIEW,
            ModelProfilePurpose.EXECUTION,
        ):
            with self.subTest(purpose=purpose):
                resolved = get_team_brain(self.team, purpose=purpose)
                self.assertEqual(resolved.model_name, "llama-3.3-70b-versatile")

    def test_team_without_config_raises_not_configured(self):
        with self.assertRaises(LLMProviderNotConfiguredError):
            get_team_brain(self.team)

    def test_disabled_config_raises_not_configured(self):
        config = self._make_config(is_active=False)
        self._make_profile(
            config,
            slug="default",
            purpose=ModelProfilePurpose.DEFAULT,
            model_name="llama-3.3-70b-versatile",
            is_default=True,
        )
        with self.assertRaises(LLMProviderNotConfiguredError):
            get_team_brain(self.team, purpose=ModelProfilePurpose.TEST_DESIGN)
