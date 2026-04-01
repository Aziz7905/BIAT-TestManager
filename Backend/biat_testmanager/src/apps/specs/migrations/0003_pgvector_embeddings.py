from django.db import migrations, models
from pgvector.django import HnswIndex, VectorExtension, VectorField


class Migration(migrations.Migration):
    dependencies = [
        ("specs", "0002_specification_sources"),
    ]

    operations = [
        VectorExtension(),
        migrations.RemoveField(
            model_name="specchunk",
            name="embedding_vector",
        ),
        migrations.AddField(
            model_name="specchunk",
            name="embedding_vector",
            field=VectorField(
                dimensions=1024,
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="specchunk",
            name="embedding_model",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="specchunk",
            name="embedded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="specchunk",
            index=HnswIndex(
                name="spec_chunk_embedding_hnsw",
                fields=["embedding_vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
