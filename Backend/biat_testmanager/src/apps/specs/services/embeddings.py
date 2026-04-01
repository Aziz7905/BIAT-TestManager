from dataclasses import dataclass
from time import perf_counter
import importlib.util
from threading import Lock

from django.conf import settings

from apps.specs.services.telemetry import ResourceMonitor


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _import_numpy():
    if not _module_available("numpy"):
        raise RuntimeError("numpy is required for local embeddings.")
    import numpy as np

    return np


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    model_name: str
    device: str
    batch_size: int
    normalized: bool
    duration_s: float
    metrics: dict[str, float]


class LocalEmbeddingService:
    def __init__(self):
        self.model_name = settings.SPEC_EMBEDDING_MODEL_NAME
        self.device_preference = settings.SPEC_EMBEDDING_DEVICE_PREFERENCE
        self.default_batch_size = settings.SPEC_EMBEDDING_BATCH_SIZE
        self.max_length = settings.SPEC_EMBEDDING_MAX_LENGTH
        self.normalize_embeddings = settings.SPEC_EMBEDDING_NORMALIZE
        self._models: dict[str, object] = {}
        self._lock = Lock()

    def _resolve_device(self) -> str:
        if self.device_preference == "cpu":
            return "cpu"

        if not _module_available("torch"):
            return "cpu"

        import torch

        if self.device_preference == "cuda" and torch.cuda.is_available():
            return "cuda"

        if self.device_preference == "auto" and torch.cuda.is_available():
            return "cuda"

        return "cpu"

    def _load_model(self, device: str):
        with self._lock:
            if device in self._models:
                return self._models[device]

            if not _module_available("sentence_transformers"):
                raise RuntimeError(
                    "sentence-transformers is not installed. Install project dependencies first."
                )

            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name, device=device)
            model.max_seq_length = self.max_length

            if device == "cuda" and hasattr(model, "half"):
                try:
                    model.half()
                except Exception:
                    pass

            self._models[device] = model
            return model

    def _clear_cuda_state(self):
        if not _module_available("torch"):
            return

        import torch

        self._models.pop("cuda", None)
        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

    @staticmethod
    def _is_cuda_oom(error: Exception) -> bool:
        message = str(error).lower()
        return "out of memory" in message or "cuda error" in message

    def _normalize(self, embeddings):
        np = _import_numpy()
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return embeddings / norms

    def embed_texts(
        self,
        texts: list[str],
        *,
        batch_size: int | None = None,
    ) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                embeddings=[],
                model_name=self.model_name,
                device="cpu",
                batch_size=batch_size or self.default_batch_size,
                normalized=self.normalize_embeddings,
                duration_s=0.0,
                metrics={},
            )

        device = self._resolve_device()
        attempted_batch_size = max(1, batch_size or self.default_batch_size)
        start_time = perf_counter()

        while True:
            monitor = ResourceMonitor(device=device)

            try:
                model = self._load_model(device)
                embeddings = model.encode(
                    texts,
                    batch_size=attempted_batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )

                if self.normalize_embeddings:
                    embeddings = self._normalize(embeddings)

                if hasattr(embeddings, "tolist"):
                    embeddings = embeddings.tolist()

                metrics = monitor.finish().as_dict()
                return EmbeddingResult(
                    embeddings=embeddings,
                    model_name=self.model_name,
                    device=device,
                    batch_size=attempted_batch_size,
                    normalized=self.normalize_embeddings,
                    duration_s=perf_counter() - start_time,
                    metrics=metrics,
                )
            except RuntimeError as error:
                if device == "cuda" and self._is_cuda_oom(error):
                    self._clear_cuda_state()
                    if attempted_batch_size > 1:
                        attempted_batch_size = max(1, attempted_batch_size // 2)
                        continue
                    device = "cpu"
                    attempted_batch_size = max(1, self.default_batch_size)
                    continue
                raise


_SERVICE: LocalEmbeddingService | None = None


def get_embedding_service() -> LocalEmbeddingService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LocalEmbeddingService()
    return _SERVICE

