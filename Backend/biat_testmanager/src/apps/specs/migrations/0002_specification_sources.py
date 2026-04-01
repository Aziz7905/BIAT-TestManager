import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models
import apps.specs.models.specification_source


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("specs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpecificationSource",
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
                ("name", models.CharField(max_length=300)),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("plain_text", "Plain Text"),
                            ("csv", "CSV"),
                            ("xlsx", "XLSX"),
                            ("pdf", "PDF"),
                            ("docx", "DOCX"),
                            ("jira_issue", "Jira Issue"),
                            ("file_upload", "File Upload"),
                            ("url", "URL"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=apps.specs.models.specification_source.specification_source_upload_to,
                    ),
                ),
                ("raw_text", models.TextField(blank=True)),
                ("source_url", models.URLField(blank=True, null=True)),
                ("jira_issue_key", models.CharField(blank=True, max_length=100, null=True)),
                (
                    "parser_status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("parsing", "Parsing"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                            ("imported", "Imported"),
                        ],
                        default="uploaded",
                        max_length=20,
                    ),
                ),
                ("parser_error", models.TextField(blank=True)),
                ("source_metadata", models.JSONField(blank=True, default=dict)),
                ("column_mapping", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="specification_sources",
                        to="projects.project",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="uploaded_specification_sources",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "specs_specification_source",
                "ordering": ["project__name", "-created_at", "name"],
            },
        ),
        migrations.AddField(
            model_name="specification",
            name="external_reference",
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name="specification",
            name="source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="imported_specifications",
                to="specs.specificationsource",
            ),
        ),
        migrations.AddField(
            model_name="specification",
            name="source_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="specification",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("plain_text", "Plain Text"),
                    ("csv", "CSV"),
                    ("xlsx", "XLSX"),
                    ("pdf", "PDF"),
                    ("docx", "DOCX"),
                    ("jira_issue", "Jira Issue"),
                    ("file_upload", "File Upload"),
                    ("url", "URL"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="SpecificationSourceRecord",
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
                ("record_index", models.IntegerField()),
                ("external_reference", models.CharField(blank=True, max_length=120)),
                ("section_label", models.CharField(blank=True, max_length=200)),
                ("row_number", models.IntegerField(blank=True, null=True)),
                ("title", models.CharField(max_length=300)),
                ("content", models.TextField()),
                ("record_metadata", models.JSONField(blank=True, default=dict)),
                ("is_selected", models.BooleanField(default=True)),
                (
                    "import_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("imported", "Imported"),
                            ("skipped", "Skipped"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "linked_specification",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="source_record",
                        to="specs.specification",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="records",
                        to="specs.specificationsource",
                    ),
                ),
            ],
            options={
                "db_table": "specs_specification_source_record",
                "ordering": ["source__name", "record_index"],
                "unique_together": {("source", "record_index")},
            },
        ),
    ]
