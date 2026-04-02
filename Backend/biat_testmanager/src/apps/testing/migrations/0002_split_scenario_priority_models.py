from django.db import migrations, models


BUSINESS_PRIORITY_VALUES = {"must_have", "should_have", "could_have"}


def split_scenario_priorities(apps, schema_editor):
    TestScenario = apps.get_model("testing", "TestScenario")

    for scenario in TestScenario.objects.all().iterator():
        updates = {}

        if scenario.scenario_type == "negative":
            updates["scenario_type"] = "alternative_flow"

        if scenario.priority in BUSINESS_PRIORITY_VALUES:
            updates["business_priority"] = scenario.priority
            updates["priority"] = "medium"
        elif scenario.business_priority in BUSINESS_PRIORITY_VALUES:
            updates["business_priority"] = scenario.business_priority
        else:
            updates["business_priority"] = None

        if updates:
            TestScenario.objects.filter(pk=scenario.pk).update(**updates)


class Migration(migrations.Migration):
    dependencies = [
        ("testing", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="testscenario",
            name="business_priority",
            field=models.CharField(
                blank=True,
                choices=[
                    ("must_have", "Must Have"),
                    ("should_have", "Should Have"),
                    ("could_have", "Could Have"),
                    ("wont_have", "Won't Have"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.RunPython(split_scenario_priorities, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="testscenario",
            name="priority",
            field=models.CharField(
                choices=[
                    ("critical", "Critical"),
                    ("high", "High"),
                    ("medium", "Medium"),
                    ("low", "Low"),
                ],
                default="medium",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="testscenario",
            name="scenario_type",
            field=models.CharField(
                choices=[
                    ("happy_path", "Happy Path"),
                    ("alternative_flow", "Alternative Flow"),
                    ("edge_case", "Edge Case"),
                    ("security", "Security"),
                    ("performance", "Performance"),
                    ("accessibility", "Accessibility"),
                ],
                default="happy_path",
                max_length=30,
            ),
        ),
    ]
