from unittest.mock import patch

from django.test import SimpleTestCase

from apps.specs.services.embeddings import LocalEmbeddingService
from apps.specs.services.mlflow_tracking import MLflowRunLogger


class SpecsHardeningTests(SimpleTestCase):
    def test_mlflow_unavailable_does_not_fail_workflow(self):
        with patch(
            "apps.specs.services.mlflow_tracking.importlib.util.find_spec",
            return_value=None,
        ):
            with MLflowRunLogger("spec-index") as logger:
                logger.log_param("specification_id", "spec-1")
                logger.log_metrics({"chunks": 3.0})

    def test_embedding_cuda_oom_detection_still_matches_cuda_failures(self):
        service = LocalEmbeddingService()

        self.assertTrue(service._is_cuda_oom(RuntimeError("CUDA error: out of memory")))
        self.assertFalse(service._is_cuda_oom(RuntimeError("model file missing")))
