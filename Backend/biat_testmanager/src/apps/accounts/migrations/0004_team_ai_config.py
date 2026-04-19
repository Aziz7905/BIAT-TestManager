import decimal
import uuid

import django.db.models.deletion
import encrypted_model_fields.fields
from django.db import migrations, models


def forwards(apps, schema_editor):
    ModelProfile = apps.get_model("accounts", "ModelProfile")
    Team = apps.get_model("accounts", "Team")
    TeamAIConfig = apps.get_model("accounts", "TeamAIConfig")

    for team in Team.objects.all().iterator():
        config, _ = TeamAIConfig.objects.get_or_create(
            team_id=team.id,
            defaults={
                "provider_id": team.ai_provider_id,
                "api_key": team.ai_api_key,
                "monthly_budget": team.monthly_token_budget,
                "is_active": True,
            },
        )

        update_fields = []
        if config.provider_id is None and team.ai_provider_id is not None:
            config.provider_id = team.ai_provider_id
            update_fields.append("provider")
        if not config.api_key and team.ai_api_key:
            config.api_key = team.ai_api_key
            update_fields.append("api_key")
        if config.monthly_budget == 100000 and team.monthly_token_budget != 100000:
            config.monthly_budget = team.monthly_token_budget
            update_fields.append("monthly_budget")
        if update_fields:
            config.save(update_fields=update_fields)

        model_name = (team.ai_model or "").strip() or "gpt-4o-mini"
        profile, _ = ModelProfile.objects.get_or_create(
            team_ai_config_id=config.id,
            slug="default",
            defaults={
                "purpose": "default",
                "model_name": model_name,
                "temperature": decimal.Decimal("0.10"),
                "max_tokens": 4096,
                "deployment_mode": "cloud",
                "is_default": True,
            },
        )
        profile_updates = []
        if profile.model_name != model_name:
            profile.model_name = model_name
            profile_updates.append("model_name")
        if not profile.is_default:
            profile.is_default = True
            profile_updates.append("is_default")
        if profile_updates:
            profile.save(update_fields=profile_updates)

        if config.default_model_profile_id != profile.id:
            config.default_model_profile_id = profile.id
            config.save(update_fields=["default_model_profile"])


def backwards(apps, schema_editor):
    TeamAIConfig = apps.get_model("accounts", "TeamAIConfig")
    TeamAIConfig.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_userprofile_org_role"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeamAIConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("api_key", encrypted_model_fields.fields.EncryptedCharField(blank=True, max_length=512, null=True)),
                ("monthly_budget", models.IntegerField(default=100000)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="team_ai_configs", to="accounts.aiprovider")),
                ("team", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ai_config", to="accounts.team")),
            ],
            options={
                "db_table": "accounts_team_ai_config",
                "ordering": ["team__name"],
            },
        ),
        migrations.CreateModel(
            name="ModelProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("slug", models.SlugField(max_length=100)),
                ("purpose", models.CharField(choices=[("default", "Default"), ("test_design", "Test Design"), ("review", "Review"), ("execution", "Execution")], default="default", max_length=30)),
                ("model_name", models.CharField(max_length=150)),
                ("temperature", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.10"), max_digits=4)),
                ("max_tokens", models.PositiveIntegerField(default=4096)),
                ("deployment_mode", models.CharField(choices=[("cloud", "Cloud"), ("local", "Local"), ("hybrid", "Hybrid")], default="cloud", max_length=20)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("team_ai_config", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="model_profiles", to="accounts.teamaiconfig")),
            ],
            options={
                "db_table": "accounts_model_profile",
                "ordering": ["team_ai_config__team__name", "slug"],
                "unique_together": {("team_ai_config", "slug")},
            },
        ),
        migrations.AddConstraint(
            model_name="modelprofile",
            constraint=models.UniqueConstraint(condition=models.Q(is_default=True), fields=("team_ai_config",), name="accounts_unique_default_model_profile_per_team_ai_config"),
        ),
        migrations.AddField(
            model_name="teamaiconfig",
            name="default_model_profile",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="accounts.modelprofile"),
        ),
        migrations.RunPython(forwards, backwards),
    ]
