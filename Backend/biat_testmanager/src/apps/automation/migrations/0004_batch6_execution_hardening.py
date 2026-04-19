from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_team_ai_config"),
        ("automation", "0003_testexecution_run_case"),
        ("testing", "0006_batch5_plans_runs"),
    ]

    operations = [
        # ExecutionEnvironment
        migrations.CreateModel(
            name="ExecutionEnvironment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=200)),
                ("engine", models.CharField(
                    choices=[("playwright", "Playwright"), ("selenium", "Selenium")],
                    default="playwright",
                    max_length=20,
                )),
                ("browser", models.CharField(
                    choices=[
                        ("chromium", "Chromium"), ("firefox", "Firefox"),
                        ("webkit", "WebKit"), ("chrome", "Chrome"), ("edge", "Edge"),
                    ],
                    default="chromium",
                    max_length=20,
                )),
                ("platform", models.CharField(
                    choices=[("desktop", "Desktop"), ("mobile", "Mobile")],
                    default="desktop",
                    max_length=20,
                )),
                ("capabilities_json", models.JSONField(blank=True, default=dict)),
                ("max_parallelism", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("team", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="execution_environments",
                    to="accounts.team",
                )),
            ],
            options={
                "db_table": "automation_execution_environment",
                "ordering": ["team__name", "name"],
                "unique_together": {("team", "name")},
            },
        ),
        # TestArtifact
        migrations.CreateModel(
            name="TestArtifact",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("artifact_type", models.CharField(
                    choices=[
                        ("screenshot", "Screenshot"), ("video", "Video"),
                        ("log", "Log"), ("junit_xml", "JUnit XML"), ("trace", "Trace"),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ("storage_path", models.CharField(max_length=500)),
                ("metadata_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("execution", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="artifacts",
                    to="automation.testexecution",
                )),
            ],
            options={
                "db_table": "automation_test_artifact",
                "ordering": ["execution", "artifact_type", "created_at"],
            },
        ),
        # AutomationScript.test_case_revision
        migrations.AddField(
            model_name="automationscript",
            name="test_case_revision",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="scripts",
                to="testing.testcaserevision",
            ),
        ),
        # TestExecution.environment + attempt_number
        migrations.AddField(
            model_name="testexecution",
            name="environment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="executions",
                to="automation.executionenvironment",
            ),
        ),
        migrations.AddField(
            model_name="testexecution",
            name="attempt_number",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
