# Generated manually for integration provider normalization.

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_PROVIDERS = {
    "jira": "Jira",
    "github": "GitHub",
    "jenkins": "Jenkins",
}

PROVIDER_MODEL_NAMES = [
    "IntegrationConfig",
    "UserIntegrationCredential",
    "RepositoryBinding",
    "IntegrationActionLog",
    "ExternalIssueLink",
    "WebhookEvent",
]


def seed_integration_providers(apps, schema_editor):
    IntegrationProvider = apps.get_model("integrations", "IntegrationProvider")

    discovered_slugs = set(DEFAULT_PROVIDERS)
    for model_name in PROVIDER_MODEL_NAMES:
        Model = apps.get_model("integrations", model_name)
        discovered_slugs.update(
            slug
            for slug in Model.objects.exclude(provider_slug="").values_list(
                "provider_slug",
                flat=True,
            )
            if slug
        )

    for slug in sorted(discovered_slugs):
        IntegrationProvider.objects.update_or_create(
            slug=slug,
            defaults={
                "name": DEFAULT_PROVIDERS.get(slug, slug.replace("_", " ").title()),
                "is_active": True,
            },
        )


def populate_provider_foreign_keys(apps, schema_editor):
    for model_name in PROVIDER_MODEL_NAMES:
        Model = apps.get_model("integrations", model_name)
        for row in Model.objects.all().only("id", "provider_slug").iterator():
            row.provider_id = row.provider_slug
            row.save(update_fields=["provider"])


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0002_repositorybinding_integrationactionlog_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationProvider",
            fields=[
                ("slug", models.CharField(max_length=50, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "integrations_integration_provider",
                "ordering": ["name"],
            },
        ),
        migrations.RemoveConstraint(
            model_name="integrationconfig",
            name="integrations_unique_team_provider_config",
        ),
        migrations.RemoveConstraint(
            model_name="integrationconfig",
            name="integrations_unique_project_provider_config",
        ),
        migrations.RemoveConstraint(
            model_name="repositorybinding",
            name="integrations_unique_project_repository_binding",
        ),
        migrations.RemoveConstraint(
            model_name="webhookevent",
            name="integrations_unique_provider_webhook_external_id",
        ),
        migrations.RemoveConstraint(
            model_name="externalissuelink",
            name="integrations_unique_external_issue_link",
        ),
        migrations.RemoveIndex(
            model_name="repositorybinding",
            name="int_repo_provider_idx",
        ),
        migrations.RemoveIndex(
            model_name="webhookevent",
            name="int_webhook_provider_idx",
        ),
        migrations.RemoveIndex(
            model_name="integrationactionlog",
            name="int_action_provider_idx",
        ),
        migrations.RemoveIndex(
            model_name="externalissuelink",
            name="int_issue_project_idx",
        ),
        migrations.AlterUniqueTogether(
            name="userintegrationcredential",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="integrationconfig",
            name="provider",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="configs",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AddField(
            model_name="userintegrationcredential",
            name="provider",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="user_credentials",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AddField(
            model_name="repositorybinding",
            name="provider",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="repository_bindings",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AddField(
            model_name="integrationactionlog",
            name="provider",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="action_logs",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AddField(
            model_name="externalissuelink",
            name="provider",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="external_issue_links",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="provider",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="webhook_events",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.RunPython(seed_integration_providers, migrations.RunPython.noop),
        migrations.RunPython(populate_provider_foreign_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="integrationconfig",
            name="provider",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="configs",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AlterField(
            model_name="userintegrationcredential",
            name="provider",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="user_credentials",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AlterField(
            model_name="repositorybinding",
            name="provider",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="repository_bindings",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AlterField(
            model_name="integrationactionlog",
            name="provider",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="action_logs",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AlterField(
            model_name="externalissuelink",
            name="provider",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="external_issue_links",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.AlterField(
            model_name="webhookevent",
            name="provider",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="webhook_events",
                to="integrations.integrationprovider",
            ),
        ),
        migrations.RemoveField(
            model_name="integrationconfig",
            name="provider_slug",
        ),
        migrations.RemoveField(
            model_name="userintegrationcredential",
            name="provider_slug",
        ),
        migrations.RemoveField(
            model_name="repositorybinding",
            name="provider_slug",
        ),
        migrations.RemoveField(
            model_name="integrationactionlog",
            name="provider_slug",
        ),
        migrations.RemoveField(
            model_name="externalissuelink",
            name="provider_slug",
        ),
        migrations.RemoveField(
            model_name="webhookevent",
            name="provider_slug",
        ),
        migrations.AlterModelOptions(
            name="integrationconfig",
            options={"ordering": ["team__name", "provider"]},
        ),
        migrations.AlterModelOptions(
            name="userintegrationcredential",
            options={"ordering": ["user_profile__user__username", "provider"]},
        ),
        migrations.AlterModelOptions(
            name="repositorybinding",
            options={"ordering": ["project__name", "provider", "repo_identifier"]},
        ),
        migrations.AlterModelOptions(
            name="externalissuelink",
            options={"ordering": ["project__name", "provider", "external_key"]},
        ),
        migrations.AlterUniqueTogether(
            name="userintegrationcredential",
            unique_together={("user_profile", "provider")},
        ),
        migrations.AddConstraint(
            model_name="integrationconfig",
            constraint=models.UniqueConstraint(
                condition=models.Q(("project__isnull", True)),
                fields=("team", "provider"),
                name="integrations_unique_team_provider_config",
            ),
        ),
        migrations.AddConstraint(
            model_name="integrationconfig",
            constraint=models.UniqueConstraint(
                condition=models.Q(("project__isnull", False)),
                fields=("team", "project", "provider"),
                name="integrations_unique_project_provider_config",
            ),
        ),
        migrations.AddIndex(
            model_name="repositorybinding",
            index=models.Index(fields=["provider", "repo_identifier"], name="int_repo_provider_idx"),
        ),
        migrations.AddConstraint(
            model_name="repositorybinding",
            constraint=models.UniqueConstraint(
                fields=("project", "provider", "repo_identifier"),
                name="integrations_unique_project_repository_binding",
            ),
        ),
        migrations.AddConstraint(
            model_name="webhookevent",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_id__isnull", False), models.Q(("external_id", ""), _negated=True)),
                fields=("provider", "external_id"),
                name="integrations_unique_provider_webhook_external_id",
            ),
        ),
        migrations.AddIndex(
            model_name="webhookevent",
            index=models.Index(fields=["provider", "event_type", "status"], name="int_webhook_provider_idx"),
        ),
        migrations.AddIndex(
            model_name="integrationactionlog",
            index=models.Index(fields=["provider", "action_type", "status"], name="int_action_provider_idx"),
        ),
        migrations.AddIndex(
            model_name="externalissuelink",
            index=models.Index(fields=["project", "provider", "external_key"], name="int_issue_project_idx"),
        ),
        migrations.AddConstraint(
            model_name="externalissuelink",
            constraint=models.UniqueConstraint(
                fields=("project", "provider", "external_key", "content_type", "object_id"),
                name="integrations_unique_external_issue_link",
            ),
        ),
    ]
