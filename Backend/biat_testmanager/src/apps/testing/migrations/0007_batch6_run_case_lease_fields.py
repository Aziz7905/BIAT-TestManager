from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("testing", "0006_batch5_plans_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="testruncase",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="testruncase",
            name="leased_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="testruncase",
            name="leased_by",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
