from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aigenerationsession",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("generating", "Generating"),
                    ("clarification_required", "Clarification Required"),
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
    ]
