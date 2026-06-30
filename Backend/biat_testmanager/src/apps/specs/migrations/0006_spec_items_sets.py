from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
        ("specs", "0005_embeddingmodel_specification_index_error_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SpecItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("external_key", models.CharField(blank=True, db_index=True, max_length=160)),
                (
                    "item_type",
                    models.CharField(
                        choices=[
                            ("requirement", "Requirement"),
                            ("acceptance_criterion", "Acceptance Criterion"),
                            ("business_rule", "Business Rule"),
                            ("validation_rule", "Validation Rule"),
                            ("user_story", "User Story"),
                            ("nfr", "Non-Functional Requirement"),
                            ("test_case", "Test Case"),
                            ("test_data", "Test Data"),
                            ("context", "Context"),
                            ("other", "Other"),
                        ],
                        db_index=True,
                        default="requirement",
                        max_length=40,
                    ),
                ),
                ("title", models.CharField(max_length=300)),
                ("content", models.TextField()),
                ("module", models.CharField(blank=True, max_length=200)),
                ("feature", models.CharField(blank=True, max_length=200)),
                ("priority", models.CharField(blank=True, max_length=80)),
                ("status", models.CharField(blank=True, max_length=80)),
                ("parent_external_key", models.CharField(blank=True, max_length=160)),
                ("source_metadata", models.JSONField(blank=True, default=dict)),
                ("extra_fields", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="spec_items", to="projects.project"),
                ),
                (
                    "source",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="spec_items", to="specs.specificationsource"),
                ),
                (
                    "source_record",
                    models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="spec_item", to="specs.specificationsourcerecord"),
                ),
                (
                    "specification",
                    models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="spec_item", to="specs.specification"),
                ),
            ],
            options={
                "db_table": "specs_spec_item",
                "ordering": ["source__name", "module", "feature", "external_key", "title"],
            },
        ),
        migrations.CreateModel(
            name="SpecSet",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("set_key", models.CharField(db_index=True, max_length=240)),
                (
                    "set_type",
                    models.CharField(
                        choices=[
                            ("source", "Source"),
                            ("sheet", "Sheet"),
                            ("module", "Module"),
                            ("feature", "Feature"),
                            ("user_journey", "User Journey"),
                            ("requirement_family", "Requirement Family"),
                            ("context", "Context"),
                        ],
                        db_index=True,
                        default="module",
                        max_length=40,
                    ),
                ),
                ("title", models.CharField(max_length=300)),
                ("description", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "items",
                    models.ManyToManyField(blank=True, related_name="spec_sets", to="specs.specitem"),
                ),
                (
                    "project",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="spec_sets", to="projects.project"),
                ),
                (
                    "source",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="spec_sets", to="specs.specificationsource"),
                ),
            ],
            options={
                "db_table": "specs_spec_set",
                "ordering": ["source__name", "set_type", "title"],
                "unique_together": {("project", "source", "set_key")},
            },
        ),
        migrations.AddIndex(
            model_name="specitem",
            index=models.Index(fields=["project", "item_type"], name="specs_spec__project_335118_idx"),
        ),
        migrations.AddIndex(
            model_name="specitem",
            index=models.Index(fields=["project", "external_key"], name="specs_spec__project_ed9c5c_idx"),
        ),
        migrations.AddIndex(
            model_name="specitem",
            index=models.Index(fields=["source", "module", "feature"], name="specs_spec__source__e7d750_idx"),
        ),
        migrations.AddIndex(
            model_name="specset",
            index=models.Index(fields=["project", "set_type"], name="specs_spec__project_9cab56_idx"),
        ),
        migrations.AddIndex(
            model_name="specset",
            index=models.Index(fields=["source", "set_type"], name="specs_spec__source__973a64_idx"),
        ),
    ]
