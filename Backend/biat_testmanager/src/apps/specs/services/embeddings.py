from dataclasses import dataclass
from time import perf_counter
import importlib.util
import logging
from pathlib import Path
from threading import Lock

from django.conf import settings

from apps.specs.services.telemetry import ResourceMonitor

logger = logging.getLogger(__name__)


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
        self.local_files_only = settings.SPEC_EMBEDDING_LOCAL_FILES_ONLY
        self.device_preference = settings.SPEC_EMBEDDING_DEVICE_PREFERENCE
        self.default_batch_size = settings.SPEC_EMBEDDING_BATCH_SIZE
        self.max_length = settings.SPEC_EMBEDDING_MAX_LENGTH
        self.normalize_embeddings = settings.SPEC_EMBEDDING_NORMALIZE
        self._models: dict[str, object] = {}
        self._lock = Lock()

    def _resolve_model_source(self) -> str:
        if not self.local_files_only:
            return self.model_name

        configured_path = Path(self.model_name)
        if configured_path.exists():
            return str(configured_path)

        source_basename = configured_path.name or self.model_name.replace("/", "__")
        normalized_basename = self.model_name.replace("/", "__").replace("\\", "__")
        project_root = Path(settings.BASE_DIR).resolve().parent
        candidate_roots = (
            project_root / "HuggingFace_models",
            project_root / "models",
            Path(settings.BASE_DIR).resolve() / "HuggingFace_models",
            Path(settings.BASE_DIR).resolve() / "models",
        )

        for root in candidate_roots:
            for folder_name in (source_basename, normalized_basename):
                candidate = root / folder_name
                if candidate.exists():
                    return str(candidate)

        return self.model_name

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

            model = SentenceTransformer(
                self._resolve_model_source(),
                device=device,
                local_files_only=self.local_files_only,
            )
            model.max_seq_length = self.max_length

            if device == "cuda" and hasattr(model, "half"):
                try:
                    model.half()
                except Exception:  # pragma: no cover - hardware/library specific
                    logger.debug("Could not switch embedding model to half precision.", exc_info=True)

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
            except Exception:  # pragma: no cover - hardware/library specific
                logger.warning("Failed to clear CUDA embedding cache.", exc_info=True)

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
