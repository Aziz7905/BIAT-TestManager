from django.db import migrations, models


def backfill_run_kind(apps, schema_editor):
    TestRun = apps.get_model("testing", "TestRun")
    # Ad-hoc internal runs created by get_or_create_adhoc_run_case
    TestRun.objects.filter(name__startswith="Ad-hoc -").update(run_kind="system_generated")
    # Plan-linked runs are planned regression runs
    TestRun.objects.filter(plan__isnull=False).exclude(run_kind="system_generated").update(
        run_kind="planned"
    )
    # Everything else is a user-created standalone run
    TestRun.objects.filter(plan__isnull=True).exclude(run_kind="system_generated").update(
        run_kind="standalone"
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("testing", "0007_batch6_run_case_lease_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="testrun",
            name="run_kind",
            field=models.CharField(
                choices=[
                    ("planned", "Planned"),
                    ("standalone", "Standalone"),
                    ("system_generated", "System Generated"),
                ],
                db_index=True,
                default="planned",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_run_kind, noop_reverse),
    ]
