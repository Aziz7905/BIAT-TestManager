# Generated for BIAT Step 4A AI generation foundation.

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0007_ai_provider_configuration"),
        ("projects", "0001_initial"),
        ("specs", "0005_embeddingmodel_specification_index_error_and_more"),
        ("testing", "0008_testrun_run_kind"),
    ]

    operations = [
        migrations.CreateModel(
            name="AIGenerationSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("generating", "Generating"),
                            ("ready_for_review", "Ready For Review"),
                            ("reviewing", "Reviewing"),
                            ("saved", "Saved"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=30,
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("prompt", "Prompt"),
                            ("specification", "Specification"),
                            ("jira", "Jira"),
                            ("manual", "Manual"),
                            ("mixed", "Mixed"),
                        ],
                        default="prompt",
                        max_length=30,
                    ),
                ),
                ("objective", models.TextField()),
                ("source_refs", models.JSONField(blank=True, default=dict)),
                ("jira_issue_key", models.CharField(blank=True, max_length=100)),
                ("provider_name", models.CharField(blank=True, max_length=100)),
                ("model_name", models.CharField(blank=True, max_length=150)),
                ("purpose", models.CharField(blank=True, default="test_design", max_length=30)),
                ("prompt_version", models.CharField(blank=True, max_length=80)),
                ("schema_version", models.CharField(blank=True, max_length=80)),
                ("draft_payload", models.JSONField(blank=True, default=dict)),
                ("critic_report", models.JSONField(blank=True, default=dict)),
                ("review_decisions", models.JSONField(blank=True, default=dict)),
                ("saved_object_ids", models.JSONField(blank=True, default=dict)),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("duration_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("mlflow_run_id", models.CharField(blank=True, max_length=255)),
                ("trace_id", models.CharField(blank=True, max_length=255)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "attached_specification",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_generation_sessions",
                        to="specs.specification",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_generation_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_generation_sessions",
                        to="projects.project",
                    ),
                ),
                (
                    "target_section",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_generation_sessions",
                        to="testing.testsection",
                    ),
                ),
                (
                    "target_suite",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_generation_sessions",
                        to="testing.testsuite",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ai_generation_sessions",
                        to="accounts.team",
                    ),
                ),
            ],
            options={
                "db_table": "ai_generation_session",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AIGenerationRetrievedContext",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "context_type",
                    models.CharField(
                        choices=[
                            ("spec_chunk", "Spec Chunk"),
                            ("test_suite", "Test Suite"),
                            ("test_scenario", "Test Scenario"),
                            ("test_case", "Test Case"),
                            ("repository_memory", "Repository Memory"),
                            ("jira", "Jira"),
                            ("github", "Github"),
                            ("prompt", "Prompt"),
                        ],
                        max_length=40,
                    ),
                ),
                ("object_id", models.CharField(blank=True, max_length=64)),
                ("external_ref", models.CharField(blank=True, max_length=255)),
                ("score", models.FloatField(blank=True, null=True)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retrieved_contexts",
                        to="ai.aigenerationsession",
                    ),
                ),
            ],
            options={
                "db_table": "ai_generation_retrieved_context",
                "ordering": ["session_id", "context_type", "-score", "created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="aigenerationsession",
            index=models.Index(fields=["team", "status"], name="ai_gen_team_status_idx"),
        ),
        migrations.AddIndex(
            model_name="aigenerationsession",
            index=models.Index(fields=["project", "created_at"], name="ai_gen_project_created_idx"),
        ),
        migrations.AddIndex(
            model_name="aigenerationretrievedcontext",
            index=models.Index(fields=["session", "context_type"], name="ai_ctx_session_type_idx"),
        ),
        migrations.AddIndex(
            model_name="aigenerationretrievedcontext",
            index=models.Index(fields=["context_type", "object_id"], name="ai_ctx_object_idx"),
        ),
    ]
