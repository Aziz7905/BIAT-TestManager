import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Specification",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("title", models.CharField(max_length=300)),
                ("content", models.TextField()),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("jira_issue", "Jira Issue"),
                            ("file_upload", "File Upload"),
                            ("url", "URL"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                ("jira_issue_key", models.CharField(blank=True, max_length=100, null=True)),
                ("source_url", models.URLField(blank=True, null=True)),
                ("version", models.CharField(default="1.0", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="specifications",
                        to="projects.project",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_specifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "specs_specification",
                "ordering": ["project__name", "title", "-created_at"],
                "unique_together": {("project", "title", "version")},
            },
        ),
        migrations.CreateModel(
            name="SpecChunk",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("chunk_index", models.IntegerField()),
                (
                    "chunk_type",
                    models.CharField(
                        choices=[
                            ("functional_requirement", "Functional Requirement"),
                            ("acceptance_criteria", "Acceptance Criteria"),
                            ("user_story", "User Story"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=40,
                    ),
                ),
                ("component_tag", models.CharField(blank=True, max_length=100)),
                ("content", models.TextField()),
                ("embedding_vector", models.JSONField(blank=True, default=list)),
                ("token_count", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "specification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="specs.specification",
                    ),
                ),
            ],
            options={
                "db_table": "specs_spec_chunk",
                "ordering": ["specification__title", "chunk_index"],
                "unique_together": {("specification", "chunk_index")},
            },
        ),
    ]
