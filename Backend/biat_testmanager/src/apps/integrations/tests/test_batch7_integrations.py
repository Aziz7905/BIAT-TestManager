import hashlib
import hmac
import json

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import (
    Organization,
    OrganizationRole,
    Team,
    UserProfile,
)
from apps.integrations.models import (
    ExternalIssueLink,
    IntegrationActionLog,
    IntegrationActionStatus,
    IntegrationConfig,
    RepositoryBinding,
    UserIntegrationCredential,
    WebhookEvent,
)
from apps.integrations.services import (
    configure_project_integration,
    create_repository_binding_for_project,
    link_external_issue_to_object,
    process_webhook_event,
    record_integration_action_result,
    store_user_integration_credential,
)
from apps.projects.models import Project, ProjectMember, ProjectMemberRole

User = get_user_model()


def _signed_json_body(payload: dict, secret: str) -> tuple[bytes, str]:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return body, f"sha256={digest}"


class Batch7IntegrationSetupMixin:
    def setUp(self):
        self.organization = Organization.objects.create(
            name="BIAT",
            domain="biat.tn",
        )
        self.team = Team.objects.create(
            organization=self.organization,
            name="QA Platform",
        )
        self.admin = User.objects.create_user(
            username="integration.admin",
            password="Pass1234!",
            email="integration.admin@biat.tn",
        )
        UserProfile.objects.create(
            user=self.admin,
            organization=self.organization,
            organization_role=OrganizationRole.ORG_ADMIN,
        )
        self.viewer = User.objects.create_user(
            username="integration.viewer",
            password="Pass1234!",
            email="integration.viewer@biat.tn",
        )
        UserProfile.objects.create(
            user=self.viewer,
            organization=self.organization,
            organization_role=OrganizationRole.MEMBER,
        )
        self.project = Project.objects.create(
            team=self.team,
            name="Digital Banking",
            created_by=self.admin,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.admin,
            role=ProjectMemberRole.OWNER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMemberRole.VIEWER,
        )


class Batch7IntegrationModelTests(Batch7IntegrationSetupMixin, TestCase):
    def test_repository_binding_is_unique_per_project_provider_and_repo(self):
        RepositoryBinding.objects.create(
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
            created_by=self.admin,
        )

        with self.assertRaises(IntegrityError):
            RepositoryBinding.objects.create(
                project=self.project,
                provider_slug="github",
                repo_identifier="biat/test-manager",
                created_by=self.admin,
            )

    def test_external_issue_link_targets_project_object(self):
        link = link_external_issue_to_object(
            actor=self.admin,
            project=self.project,
            provider_slug="jira",
            external_key="BANK-123",
            content_object=self.project,
            metadata_json={"source": "manual"},
        )

        self.assertEqual(link.project_id, self.project.id)
        self.assertEqual(link.content_object, self.project)
        self.assertEqual(link.metadata_json["source"], "manual")


class Batch7IntegrationServiceTests(Batch7IntegrationSetupMixin, TestCase):
    def test_configure_project_integration_creates_project_override(self):
        config = configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="jira",
            config_data={"base_url": "https://jira.biat.tn", "project_key": "BANK"},
        )

        self.assertEqual(config.team_id, self.team.id)
        self.assertEqual(config.project_id, self.project.id)
        self.assertEqual(config.config_data["project_key"], "BANK")

    def test_configure_project_integration_overwrites_existing_record(self):
        first = configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={"org": "biat", "repo": "old"},
        )
        second = configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={"org": "biat", "repo": "new"},
        )

        self.assertEqual(first.id, second.id)
        self.assertEqual(second.config_data["repo"], "new")
        self.assertEqual(
            IntegrationConfig.objects.filter(
                project=self.project,
                provider_slug="github",
            ).count(),
            1,
        )

    def test_store_user_integration_credential_keeps_payload_encrypted_in_model(self):
        credential = store_user_integration_credential(
            profile=self.admin.profile,
            provider_slug="github",
            credential_data={"token": "ghp_test"},
        )

        self.assertEqual(credential.credential_data["token"], "ghp_test")
        self.assertTrue(
            UserIntegrationCredential.objects.filter(
                user_profile=self.admin.profile,
                provider_slug="github",
                is_active=True,
            ).exists()
        )

    def test_viewer_cannot_create_repository_binding(self):
        with self.assertRaises(PermissionDenied):
            create_repository_binding_for_project(
                actor=self.viewer,
                project=self.project,
                provider_slug="github",
                repo_identifier="biat/test-manager",
            )

    def test_duplicate_repository_binding_returns_validation_error(self):
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )

        with self.assertRaises(ValidationError):
            create_repository_binding_for_project(
                actor=self.admin,
                project=self.project,
                provider_slug="github",
                repo_identifier="biat/test-manager",
            )

    def test_process_github_webhook_attaches_matching_repository_binding(self):
        binding = create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )

        event, created = process_webhook_event(
            provider_slug="github",
            event_type="push",
            external_id="delivery-1",
            payload_json={"repository": {"full_name": "biat/test-manager"}},
        )

        self.assertTrue(created)
        self.assertEqual(event.repository_binding_id, binding.id)
        self.assertEqual(event.project_id, self.project.id)

    def test_process_webhook_event_is_idempotent_by_external_id(self):
        first, created = process_webhook_event(
            provider_slug="github",
            event_type="push",
            external_id="delivery-2",
            payload_json={},
        )
        second, duplicate_created = process_webhook_event(
            provider_slug="github",
            event_type="push",
            external_id="delivery-2",
            payload_json={},
        )

        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first.id, second.id)
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_record_integration_action_result_is_append_only_audit(self):
        log = record_integration_action_result(
            provider_slug="jira",
            action_type="update_issue",
            status=IntegrationActionStatus.SUCCESS,
            actor_user=self.admin,
            project=self.project,
            request_json={"issue": "BANK-1"},
            response_json={"status": 204},
        )

        self.assertEqual(log.project_id, self.project.id)
        self.assertEqual(log.team_id, self.team.id)
        self.assertIsNotNone(log.completed_at)
        self.assertEqual(IntegrationActionLog.objects.count(), 1)


class Batch7IntegrationAPITests(Batch7IntegrationSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_configure_project_integration_via_api(self):
        response = self.client.put(
            f"/api/integrations/projects/{self.project.id}/jira/config/",
            {
                "config_data": {
                    "base_url": "https://jira.biat.tn",
                    "project_key": "BANK",
                },
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["provider_slug"], "jira")
        self.assertEqual(response.data["config_data"]["project_key"], "BANK")
        self.assertTrue(
            IntegrationConfig.objects.filter(
                project=self.project,
                provider_slug="jira",
            ).exists()
        )

    def test_project_integration_response_redacts_webhook_secret(self):
        response = self.client.put(
            f"/api/integrations/projects/{self.project.id}/github/config/",
            {
                "config_data": {
                    "org": "biat",
                    "repo": "test-manager",
                    "webhook_secret": "do-not-return",
                },
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["config_data"]["webhook_secret"], "********")

    def test_project_integration_update_preserves_redacted_webhook_secret(self):
        configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={
                "org": "biat",
                "repo": "test-manager",
                "webhook_secret": "original-secret",
            },
        )

        response = self.client.put(
            f"/api/integrations/projects/{self.project.id}/github/config/",
            {
                "config_data": {
                    "org": "biat",
                    "repo": "renamed",
                    "webhook_secret": "********",
                },
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        config = IntegrationConfig.objects.get(
            project=self.project,
            provider_slug="github",
        )
        self.assertEqual(config.config_data["repo"], "renamed")
        self.assertEqual(config.config_data["webhook_secret"], "original-secret")

    def test_store_personal_credential_via_api_without_returning_secret(self):
        response = self.client.put(
            "/api/integrations/me/credentials/github/",
            {"credential_data": {"token": "ghp_test"}, "is_active": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_credential"])
        self.assertNotIn("credential_data", response.data)

    def test_create_repository_binding_via_api(self):
        response = self.client.post(
            f"/api/integrations/projects/{self.project.id}/repository-bindings/",
            {
                "provider_slug": "github",
                "repo_identifier": "biat/test-manager",
                "default_branch": "main",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["repo_identifier"], "biat/test-manager")

    def test_viewer_cannot_create_repository_binding_via_api(self):
        self.client.force_authenticate(self.viewer)

        response = self.client.post(
            f"/api/integrations/projects/{self.project.id}/repository-bindings/",
            {
                "provider_slug": "github",
                "repo_identifier": "biat/forbidden",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_webhook_ingest_via_api_is_durable_without_authentication(self):
        secret = "github-webhook-secret"
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )
        configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={
                "org": "biat",
                "repo": "test-manager",
                "webhook_secret": secret,
            },
        )
        payload = {"repository": {"full_name": "biat/test-manager"}}
        body, signature = _signed_json_body(payload, secret)
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/integrations/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="delivery-api-1",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["event_type"], "push")
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_webhook_ingest_rejects_missing_signature(self):
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )
        configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={"webhook_secret": "github-webhook-secret"},
        )
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/integrations/webhooks/github/",
            {"repository": {"full_name": "biat/test-manager"}},
            format="json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="delivery-api-missing-sig",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_webhook_ingest_rejects_invalid_signature(self):
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )
        configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={"webhook_secret": "github-webhook-secret"},
        )
        payload = {"repository": {"full_name": "biat/test-manager"}}
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/integrations/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="delivery-api-invalid-sig",
            HTTP_X_HUB_SIGNATURE_256="sha256=bad",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_webhook_ingest_rejects_unmatched_repository(self):
        secret = "github-webhook-secret"
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )
        configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={"webhook_secret": secret},
        )
        payload = {"repository": {"full_name": "biat/unknown"}}
        body, signature = _signed_json_body(payload, secret)
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/integrations/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="delivery-api-unknown-repo",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_webhook_ingest_duplicate_signed_delivery_is_idempotent(self):
        secret = "github-webhook-secret"
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )
        configure_project_integration(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            config_data={"webhook_secret": secret},
        )
        payload = {"repository": {"full_name": "biat/test-manager"}}
        body, signature = _signed_json_body(payload, secret)
        self.client.force_authenticate(user=None)

        first = self.client.post(
            "/api/integrations/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="delivery-api-duplicate",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )
        second = self.client.post(
            "/api/integrations/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_GITHUB_EVENT="push",
            HTTP_X_GITHUB_DELIVERY="delivery-api-duplicate",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_repository_binding_list_is_paginated(self):
        create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )

        response = self.client.get(
            f"/api/integrations/projects/{self.project.id}/repository-bindings/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 1)

    def test_repository_binding_detail_is_not_paginated(self):
        binding = create_repository_binding_for_project(
            actor=self.admin,
            project=self.project,
            provider_slug="github",
            repo_identifier="biat/test-manager",
        )

        response = self.client.get(f"/api/integrations/repository-bindings/{binding.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("results", response.data)
        self.assertEqual(response.data["id"], str(binding.id))

    def test_link_external_issue_to_project_via_api(self):
        response = self.client.post(
            f"/api/integrations/projects/{self.project.id}/external-issue-links/",
            {
                "provider_slug": "jira",
                "external_key": "BANK-42",
                "target_type_input": "projects.project",
                "object_id": str(self.project.id),
                "metadata_json": {"reason": "manual triage"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["external_key"], "BANK-42")
        self.assertEqual(ExternalIssueLink.objects.count(), 1)
