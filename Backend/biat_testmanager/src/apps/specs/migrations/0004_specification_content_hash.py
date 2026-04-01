from django.db import migrations, models
import hashlib
import re


def _normalize_spec_content(content: str) -> str:
    return re.sub(r"\s+", " ", (content or "").strip())


def populate_content_hash(apps, schema_editor):
    Specification = apps.get_model("specs", "Specification")

    for specification in Specification.objects.all().iterator():
        normalized = _normalize_spec_content(specification.content)
        specification.content_hash = hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()
        specification.save(update_fields=["content_hash"])


class Migration(migrations.Migration):
    dependencies = [
        ("specs", "0003_pgvector_embeddings"),
    ]

    operations = [
        migrations.AddField(
            model_name="specification",
            name="content_hash",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.RunPython(populate_content_hash, migrations.RunPython.noop),
    ]
