from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("automation", "0002_cleanup_execution_metadata"),
        ("testing", "0006_batch5_plans_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="testexecution",
            name="run_case",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="executions",
                to="testing.testruncase",
            ),
        ),
    ]
