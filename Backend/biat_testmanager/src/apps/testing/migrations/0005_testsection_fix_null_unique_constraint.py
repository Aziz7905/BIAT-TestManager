from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """
    Replace unique_together on TestSection with two partial UniqueConstraints.

    PostgreSQL does not enforce uniqueness on NULL values in a standard
    unique_together constraint, so (suite, NULL, "General") could be inserted
    multiple times — breaking get_or_create_default_section race-safety.

    Two partial constraints enforce the correct semantics:
    - root sections (parent IS NULL): unique by (suite, name)
    - child sections (parent IS NOT NULL): unique by (suite, parent, name)
    """

    dependencies = [
        ("testing", "0004_batch4_repository_redesign"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="testsection",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="testsection",
            constraint=models.UniqueConstraint(
                fields=["suite", "name"],
                condition=Q(parent__isnull=True),
                name="unique_root_section_per_suite",
            ),
        ),
        migrations.AddConstraint(
            model_name="testsection",
            constraint=models.UniqueConstraint(
                fields=["suite", "parent", "name"],
                condition=Q(parent__isnull=False),
                name="unique_child_section_per_parent",
            ),
        ),
    ]
