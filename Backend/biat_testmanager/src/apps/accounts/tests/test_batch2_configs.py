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
from apps.accounts.services.team_ai import sync_team_ai_config_from_legacy
from apps.integrations.models import IntegrationConfig, UserIntegrationCredential
from apps.integrations.services import (
    get_team_integration_values,
    sync_team_integrations_from_legacy,
)

User = get_user_model()


class Batch2ConfigTests(TestCase):
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

    def test_legacy_team_ai_and_integration_settings_can_backfill_new_models(self):
        team = Team.objects.create(
            organization=self.organization,
            name="Quality",
            manager=self.team_manager,
            ai_provider=self.provider,
            ai_api_key="groq-secret",
            ai_model="llama-3.3-70b-versatile",
            monthly_token_budget=250000,
            jira_base_url="https://jira.example.com",
            jira_project_key="BANK",
            github_org="biat",
            github_repo="test-manager",
            jenkins_url="https://jenkins.example.com",
        )

        ai_config = sync_team_ai_config_from_legacy(team)
        sync_team_integrations_from_legacy(team)
        integration_values = get_team_integration_values(team)

        self.assertEqual(ai_config.provider, self.provider)
        self.assertEqual(ai_config.api_key, "groq-secret")
        self.assertEqual(ai_config.monthly_budget, 250000)
        self.assertEqual(
            ai_config.default_model_profile.model_name,
            "llama-3.3-70b-versatile",
        )
        self.assertEqual(
            integration_values["jira_base_url"],
            "https://jira.example.com",
        )
        self.assertEqual(integration_values["github_org"], "biat")
        self.assertEqual(
            IntegrationConfig.objects.filter(team=team).count(),
            3,
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
                "monthly_token_budget": 500000,
                "jira_base_url": "https://jira.biat.tn",
                "jira_project_key": "QABANK",
                "github_org": "biat-org",
                "github_repo": "qa-platform",
                "jenkins_url": "https://jenkins.biat.tn",
            },
            context={"request": request},
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        team = serializer.save()
        payload = TeamSerializer(team, context={"request": request}).data

        ai_config = TeamAIConfig.objects.get(team=team)
        self.assertEqual(ai_config.provider, self.provider)
        self.assertEqual(ai_config.api_key, "configured-secret")
        self.assertEqual(ai_config.monthly_budget, 500000)
        self.assertEqual(
            ai_config.default_model_profile.model_name,
            "llama-3.3-70b-versatile",
        )
        self.assertEqual(payload["ai_provider"], str(self.provider.id))
        self.assertEqual(payload["ai_model"], "llama-3.3-70b-versatile")
        self.assertEqual(payload["jira_project_key"], "QABANK")

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
            provider_slug="jira",
        )
        github_credential = UserIntegrationCredential.objects.get(
            user_profile=self.team_manager_profile,
            provider_slug="github",
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
