from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from apps.specs.services.embeddings import LocalEmbeddingService


class LocalEmbeddingServiceTests(SimpleTestCase):
    def test_resolve_model_source_falls_back_to_huggingface_models_directory(self):
        project_root = Path(settings.BASE_DIR).resolve().parent
        fallback_dir = project_root / "HuggingFace_models" / "BAAI__bge-m3"

        self.assertTrue(fallback_dir.exists())

        with override_settings(
            BASE_DIR=settings.BASE_DIR,
            SPEC_EMBEDDING_MODEL_NAME=str(project_root / "models" / "BAAI__bge-m3"),
            SPEC_EMBEDDING_LOCAL_FILES_ONLY=True,
        ):
            service = LocalEmbeddingService()

            self.assertEqual(service._resolve_model_source(), str(fallback_dir))
