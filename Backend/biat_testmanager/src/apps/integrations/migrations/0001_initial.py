import json
import uuid

import django.db.models.deletion
import encrypted_model_fields.fields
from django.db import migrations, models


def forwards(apps, schema_editor):
    IntegrationConfig = apps.get_model("integrations", "IntegrationConfig")
    UserIntegrationCredential = apps.get_model("integrations", "UserIntegrationCredential")
    Team = apps.get_model("accounts", "Team")
    UserProfile = apps.get_model("accounts", "UserProfile")

    for team in Team.objects.all().iterator():
        if team.jira_base_url or team.jira_project_key:
            config, _ = IntegrationConfig.objects.get_or_create(
                team_id=team.id,
                project_id=None,
                provider_slug="jira",
                defaults={"config_json_encrypted": "{}"},
            )
            if config.config_json_encrypted in {"", "{}"}:
                payload = {}
                if team.jira_base_url:
                    payload["base_url"] = team.jira_base_url
                if team.jira_project_key:
                    payload["project_key"] = team.jira_project_key
                config.config_json_encrypted = json.dumps(payload)
                config.save(update_fields=["config_json_encrypted", "updated_at"])

        if team.github_org or team.github_repo:
            config, _ = IntegrationConfig.objects.get_or_create(
                team_id=team.id,
                project_id=None,
                provider_slug="github",
                defaults={"config_json_encrypted": "{}"},
            )
            if config.config_json_encrypted in {"", "{}"}:
                payload = {}
                if team.github_org:
                    payload["org"] = team.github_org
                if team.github_repo:
                    payload["repo"] = team.github_repo
                config.config_json_encrypted = json.dumps(payload)
                config.save(update_fields=["config_json_encrypted", "updated_at"])

        if team.jenkins_url:
            config, _ = IntegrationConfig.objects.get_or_create(
                team_id=team.id,
                project_id=None,
                provider_slug="jenkins",
                defaults={"config_json_encrypted": "{}"},
            )
            if config.config_json_encrypted in {"", "{}"}:
                config.config_json_encrypted = json.dumps({"url": team.jenkins_url})
                config.save(update_fields=["config_json_encrypted", "updated_at"])

    for profile in UserProfile.objects.all().iterator():
        if profile.jira_token:
            credential, _ = UserIntegrationCredential.objects.get_or_create(
                user_profile_id=profile.id,
                provider_slug="jira",
                defaults={"credential_json_encrypted": "{}"},
            )
            if credential.credential_json_encrypted in {"", "{}"}:
                credential.credential_json_encrypted = json.dumps({"token": profile.jira_token})
                credential.save(update_fields=["credential_json_encrypted", "updated_at"])

        if profile.github_token:
            credential, _ = UserIntegrationCredential.objects.get_or_create(
                user_profile_id=profile.id,
                provider_slug="github",
                defaults={"credential_json_encrypted": "{}"},
            )
            if credential.credential_json_encrypted in {"", "{}"}:
                credential.credential_json_encrypted = json.dumps({"token": profile.github_token})
                credential.save(update_fields=["credential_json_encrypted", "updated_at"])


def backwards(apps, schema_editor):
    IntegrationConfig = apps.get_model("integrations", "IntegrationConfig")
    UserIntegrationCredential = apps.get_model("integrations", "UserIntegrationCredential")
    IntegrationConfig.objects.all().delete()
    UserIntegrationCredential.objects.all().delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0004_team_ai_config"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_slug", models.CharField(max_length=50)),
                ("config_json_encrypted", encrypted_model_fields.fields.EncryptedTextField(blank=True, default="{}")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="integration_configs", to="projects.project")),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integration_configs", to="accounts.team")),
            ],
            options={
                "db_table": "integrations_integration_config",
                "ordering": ["team__name", "provider_slug"],
            },
        ),
        migrations.CreateModel(
            name="UserIntegrationCredential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider_slug", models.CharField(max_length=50)),
                ("credential_json_encrypted", encrypted_model_fields.fields.EncryptedTextField(blank=True, default="{}")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user_profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="integration_credentials", to="accounts.userprofile")),
            ],
            options={
                "db_table": "integrations_user_integration_credential",
                "ordering": ["user_profile__user__username", "provider_slug"],
                "unique_together": {("user_profile", "provider_slug")},
            },
        ),
        migrations.AddConstraint(
            model_name="integrationconfig",
            constraint=models.UniqueConstraint(condition=models.Q(project__isnull=True), fields=("team", "provider_slug"), name="integrations_unique_team_provider_config"),
        ),
        migrations.AddConstraint(
            model_name="integrationconfig",
            constraint=models.UniqueConstraint(condition=models.Q(project__isnull=False), fields=("team", "project", "provider_slug"), name="integrations_unique_project_provider_config"),
        ),
        migrations.RunPython(forwards, backwards),
    ]
