"""IntegrationResolverService verifies act_as_user vs act_as_app routing."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Organization, OrganizationRole, Team, UserProfile
from apps.integrations.models import IntegrationConfig, UserIntegrationCredential
from apps.integrations.services import resolve_integration_credentials

User = get_user_model()


class IntegrationResolverTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="BIAT", domain="biat.tn")
        self.team = Team.objects.create(organization=self.org, name="QA")
        self.user = User.objects.create_user(
            username="aziz",
            password="Pass1234!", 
            email="aziz@biat.tn",
            first_name="Aziz",
            last_name="B",
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            organization_role=OrganizationRole.MEMBER,
        )

    def _make_team_config(self, payload):
        config = IntegrationConfig.objects.create(
            team=self.team,
            project=None,
            provider_id="jira",
        )
        config.set_config_data(payload)
        config.save(update_fields=["config_json_encrypted"])
        return config

    def _make_user_credential(self, payload):
        cred = UserIntegrationCredential.objects.create(
            user_profile=self.profile,
            provider_id="jira",
        )
        cred.set_credential_data(payload)
        cred.save(update_fields=["credential_json_encrypted"])
        return cred

    def test_act_as_app_returns_team_config(self):
        team_config = self._make_team_config({"base_url": "https://jira.biat.tn"})
        self._make_user_credential({"token": "user-personal"})

        bundle = resolve_integration_credentials(
            provider="jira",
            team=self.team,
            actor_user=self.user,
            mode="act_as_app",
        )
        self.assertIsNotNone(bundle.config)
        self.assertEqual(bundle.config.id, team_config.id)
        self.assertIsNone(bundle.credential)
        self.assertTrue(bundle.has_credentials)

    def test_act_as_user_returns_user_credential(self):
        self._make_team_config({"base_url": "https://jira.biat.tn"})
        user_cred = self._make_user_credential({"token": "user-personal"})

        bundle = resolve_integration_credentials(
            provider="jira",
            team=self.team,
            actor_user=self.user,
            mode="act_as_user",
        )
        self.assertEqual(bundle.credential.id, user_cred.id)
        self.assertIsNone(bundle.config)

    def test_act_as_user_without_credential_does_not_silently_fall_back(self):
        self._make_team_config({"base_url": "https://jira.biat.tn"})

        bundle = resolve_integration_credentials(
            provider="jira",
            team=self.team,
            actor_user=self.user,
            mode="act_as_user",
        )
        self.assertIsNone(bundle.credential)
        self.assertIsNone(bundle.config)
        self.assertFalse(bundle.has_credentials)

    def test_act_as_user_falls_back_when_explicitly_allowed(self):
        team_config = self._make_team_config({"base_url": "https://jira.biat.tn"})

        bundle = resolve_integration_credentials(
            provider="jira",
            team=self.team,
            actor_user=self.user,
            mode="act_as_user",
            allow_app_fallback=True,
        )
        self.assertIsNone(bundle.credential)
        self.assertEqual(bundle.config.id, team_config.id)
        self.assertTrue(bundle.has_credentials)
