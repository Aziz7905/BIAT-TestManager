from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.accounts.models import (
    AIProvider,
    Organization,
    OrganizationRole,
    Team,
    TeamAIConfig,
    UserProfile,
)
from apps.accounts.serializers.profiles import MyProfileSerializer, UpdateMyProfileSerializer
from apps.accounts.serializers.teams import TeamSerializer
from apps.ai.providers.base import LLMProviderNotConfiguredError
from apps.ai.providers.factory import get_llm_provider
from apps.ai.providers.ollama import OllamaProvider
from apps.ai.providers.openai_compatible import OpenAICompatibleProvider
from apps.integrations.models import IntegrationConfig, UserIntegrationCredential

User = get_user_model()


class Batch2ConfigTests(TestCase):
    """AI config, integration config, and personal credentials live separately."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.organization = Organization.objects.create(
            name="BIAT",
            domain="biat.tn",
        )
        self.provider = AIProvider.objects.create(
            name="Groq",
            provider_type="groq",
            is_active=True,
        )

        self.org_admin = User.objects.create_user(
            username="org.admin",
            password="Pass1234!",
            email="org.admin@biat.tn",
            first_name="Org",
            last_name="Admin",
        )
        UserProfile.objects.create(
            user=self.org_admin,
            organization=self.organization,
            organization_role=OrganizationRole.ORG_ADMIN,
        )

        self.team_manager = User.objects.create_user(
            username="team.manager",
            password="Pass1234!",
            email="team.manager@biat.tn",
            first_name="Team",
            last_name="Manager",
        )
        self.team_manager_profile = UserProfile.objects.create(
            user=self.team_manager,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )

    def test_team_serializer_persists_new_ai_and_integration_config_tables(self):
        request = self.factory.post("/api/accounts/teams/")
        request.user = self.org_admin

        serializer = TeamSerializer(
            data={
                "organization": str(self.organization.id),
                "name": "Platform QA",
                "manager": self.team_manager.id,
                "ai_provider": self.provider.id,
                "ai_api_key": "configured-secret",
                "ai_model": "llama-3.3-70b-versatile",
                "ai_endpoint_url": "https://api.groq.com/openai/v1",
                "ai_deployment_mode": "cloud",
                "monthly_token_budget": 500000,
                "integrations": {
                    "jira": {
                        "base_url": "https://jira.biat.tn",
                        "project_key": "QABANK",
                    },
                    "github": {
                        "org": "biat-org",
                        "repo": "qa-platform",
                    },
                    "jenkins": {"url": "https://jenkins.biat.tn"},
                },
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        team = serializer.save()
        payload = TeamSerializer(team, context={"request": request}).data

        ai_config = TeamAIConfig.objects.get(team=team)
        self.assertEqual(ai_config.provider, self.provider)
        self.assertEqual(ai_config.api_key, "configured-secret")
        self.assertEqual(ai_config.endpoint_url, "https://api.groq.com/openai/v1")
        self.assertEqual(ai_config.monthly_budget, 500000)
        self.assertEqual(
            ai_config.default_model_profile.model_name,
            "llama-3.3-70b-versatile",
        )
        self.assertEqual(ai_config.default_model_profile.deployment_mode, "cloud")
        self.assertEqual(payload["ai_provider"], str(self.provider.id))
        self.assertEqual(payload["ai_provider_type"], "groq")
        self.assertEqual(payload["ai_model"], "llama-3.3-70b-versatile")
        self.assertEqual(payload["ai_endpoint_url"], "https://api.groq.com/openai/v1")
        self.assertEqual(payload["ai_deployment_mode"], "cloud")
        self.assertEqual(payload["integrations"]["jira"]["project_key"], "QABANK")
        self.assertTrue(payload["has_ai_api_key"])

        # Three IntegrationConfig rows: jira, github, jenkins
        self.assertEqual(IntegrationConfig.objects.filter(team=team).count(), 3)

    def test_team_response_omits_deprecated_token_counter(self):
        request = self.factory.get("/api/accounts/teams/")
        request.user = self.org_admin

        serializer = TeamSerializer(
            data={
                "organization": str(self.organization.id),
                "name": "Platform QA",
                "manager": self.team_manager.id,
                "ai_provider": self.provider.id,
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        team = serializer.save()

        payload = TeamSerializer(team, context={"request": request}).data
        self.assertNotIn("tokens_used_this_month", payload)

    def test_llm_factory_returns_openai_compatible_provider_for_groq(self):
        team = Team.objects.create(
            organization=self.organization,
            name="AI QA",
            manager=self.team_manager,
        )
        serializer = TeamSerializer(
            team,
            data={
                "ai_provider": self.provider.id,
                "ai_api_key": "groq-secret",
                "ai_model": "llama-3.3-70b-versatile",
                "ai_deployment_mode": "cloud",
            },
            partial=True,
            context={"request": self.factory.patch("/api/accounts/teams/")},
        )
        serializer.context["request"].user = self.org_admin
        self.assertTrue(serializer.is_valid(), serializer.errors)
        team = serializer.save()

        provider = get_llm_provider(team)

        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.name, "groq")
        self.assertEqual(provider.model_name, "llama-3.3-70b-versatile")

    def test_llm_factory_allows_ollama_without_api_key(self):
        ollama = AIProvider.objects.create(
            name="Ollama",
            provider_type="ollama",
            base_url="http://localhost:11434",
            is_active=True,
        )
        team = Team.objects.create(
            organization=self.organization,
            name="Local AI QA",
            manager=self.team_manager,
        )
        request = self.factory.patch("/api/accounts/teams/")
        request.user = self.org_admin
        serializer = TeamSerializer(
            team,
            data={
                "ai_provider": ollama.id,
                "ai_model": "gemma3:12b",
                "ai_endpoint_url": "http://localhost:11434",
                "ai_deployment_mode": "local",
            },
            partial=True,
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        team = serializer.save()

        provider = get_llm_provider(team)

        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.model_name, "gemma3:12b")

    def test_llm_factory_rejects_cloud_provider_without_api_key(self):
        team = Team.objects.create(
            organization=self.organization,
            name="Missing Key QA",
            manager=self.team_manager,
        )
        request = self.factory.patch("/api/accounts/teams/")
        request.user = self.org_admin
        serializer = TeamSerializer(
            team,
            data={
                "ai_provider": self.provider.id,
                "ai_model": "llama-3.3-70b-versatile",
                "ai_deployment_mode": "cloud",
            },
            partial=True,
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        team = serializer.save()

        with self.assertRaises(LLMProviderNotConfiguredError):
            get_llm_provider(team)

    def test_profile_updates_store_personal_tokens_in_user_credentials(self):
        serializer = UpdateMyProfileSerializer(
            self.team_manager_profile,
            data={
                "jira_token": "jira-personal-token",
                "github_token": "github-personal-token",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        payload = MyProfileSerializer(self.team_manager_profile).data

        jira_credential = UserIntegrationCredential.objects.get(
            user_profile=self.team_manager_profile,
            provider_id="jira",
        )
        github_credential = UserIntegrationCredential.objects.get(
            user_profile=self.team_manager_profile,
            provider_id="github",
        )

        self.assertEqual(
            jira_credential.credential_data["token"],
            "jira-personal-token",
        )
        self.assertEqual(
            github_credential.credential_data["token"],
            "github-personal-token",
        )
        self.assertTrue(payload["has_jira_token"])
        self.assertTrue(payload["has_github_token"])
