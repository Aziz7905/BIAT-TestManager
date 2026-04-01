import uuid

from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from .choices import SpecChunkType


class SpecChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    specification = models.ForeignKey(
        "specs.Specification",
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.IntegerField()
    chunk_type = models.CharField(
        max_length=40,
        choices=SpecChunkType.choices,
        default=SpecChunkType.OTHER,
    )
    component_tag = models.CharField(max_length=100, blank=True)
    content = models.TextField()
    embedding_vector = VectorField(
        dimensions=settings.SPEC_EMBEDDING_VECTOR_DIMENSIONS,
        null=True,
        blank=True,
    )
    embedding_model = models.CharField(max_length=200, blank=True)
    embedded_at = models.DateTimeField(null=True, blank=True)
    token_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "specs_spec_chunk"
        ordering = ["specification__title", "chunk_index"]
        unique_together = [("specification", "chunk_index")]
        indexes = [
            HnswIndex(
                name="spec_chunk_embedding_hnsw",
                fields=["embedding_vector"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.specification.title} / Chunk {self.chunk_index}"

    def similarity_search(self, query: str, top_k: int = 5):
        from apps.specs.services.indexing import retrieve_similar_chunks

        queryset = retrieve_similar_chunks(
            query,
            top_k=top_k,
            specification=self.specification,
            exclude_chunk_ids=[str(self.pk)],
        )
        return queryset
