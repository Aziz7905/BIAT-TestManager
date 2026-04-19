from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0001_initial"),
        ("testing", "0005_testsection_fix_null_unique_constraint"),
    ]

    operations = [
        migrations.CreateModel(
            name="TestPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=300)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(
                    choices=[("draft", "Draft"), ("active", "Active"), ("archived", "Archived")],
                    db_index=True,
                    default="draft",
                    max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="test_plans",
                    to="projects.project",
                )),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_test_plans",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "testing_test_plan", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TestRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=300)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("running", "Running"),
                        ("passed", "Passed"),
                        ("failed", "Failed"),
                        ("cancelled", "Cancelled"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=20,
                )),
                ("trigger_type", models.CharField(
                    choices=[
                        ("manual", "Manual"),
                        ("ci_cd", "CI/CD"),
                        ("scheduled", "Scheduled"),
                        ("webhook", "Webhook"),
                    ],
                    default="manual",
                    max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("plan", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="runs",
                    to="testing.testplan",
                )),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="test_runs",
                    to="projects.project",
                )),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="created_test_runs",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "testing_test_run", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TestRunCase",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("running", "Running"),
                        ("passed", "Passed"),
                        ("failed", "Failed"),
                        ("skipped", "Skipped"),
                        ("error", "Error"),
                        ("cancelled", "Cancelled"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=20,
                )),
                ("order_index", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("run", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="run_cases",
                    to="testing.testrun",
                )),
                ("test_case", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="run_cases",
                    to="testing.testcase",
                )),
                ("test_case_revision", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="run_cases",
                    to="testing.testcaserevision",
                )),
                ("assigned_to", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="assigned_run_cases",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "testing_test_run_case", "ordering": ["run", "order_index"]},
        ),
    ]
