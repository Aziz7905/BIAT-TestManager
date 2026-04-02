from django.db import migrations, models


def backfill_case_specification_links(apps, schema_editor):
    TestCase = apps.get_model("testing", "TestCase")
    through_model = TestCase.linked_specifications.through

    for test_case in (
        TestCase.objects.select_related("scenario__suite__specification")
        .filter(scenario__suite__specification__isnull=False)
        .iterator()
    ):
        through_model.objects.get_or_create(
            testcase_id=test_case.id,
            specification_id=test_case.scenario.suite.specification_id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("specs", "0004_specification_content_hash"),
        ("testing", "0002_split_scenario_priority_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcase",
            name="linked_specifications",
            field=models.ManyToManyField(
                blank=True,
                related_name="linked_test_cases",
                to="specs.specification",
            ),
        ),
        migrations.RunPython(
            backfill_case_specification_links,
            migrations.RunPython.noop,
        ),
    ]
