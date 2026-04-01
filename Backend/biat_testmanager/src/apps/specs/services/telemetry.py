from dataclasses import dataclass
from time import perf_counter
import importlib.util
import os


def _import_optional(module_name: str):
    if importlib.util.find_spec(module_name) is None:
        return None
    return __import__(module_name)


@dataclass
class ResourceMetrics:
    duration_s: float
    system_cpu_percent: float | None
    process_cpu_percent: float | None
    process_ram_mb: float | None
    system_ram_percent: float | None
    gpu_memory_allocated_mb: float | None
    gpu_memory_reserved_mb: float | None
    gpu_memory_peak_allocated_mb: float | None
    gpu_memory_peak_reserved_mb: float | None
    gpu_memory_used_mb: float | None
    gpu_memory_total_mb: float | None

    def as_dict(self) -> dict[str, float]:
        return {
            key: value
            for key, value in self.__dict__.items()
            if value is not None
        }


class ResourceMonitor:
    def __init__(self, device: str | None = None):
        self.device = device or "cpu"
        self.started_at = perf_counter()
        self._psutil = _import_optional("psutil")
        self._torch = _import_optional("torch")
        self._pynvml = _import_optional("pynvml")
        self._process = self._psutil.Process(os.getpid()) if self._psutil else None
        self._gpu_peak_allocated = None
        self._gpu_peak_reserved = None
        self._gpu_used = None
        self._gpu_total = None

        if self._psutil:
            self._psutil.cpu_percent(interval=None)
            self._process.cpu_percent(interval=None)

        if self._torch and self.device == "cuda" and self._torch.cuda.is_available():
            try:
                self._torch.cuda.reset_peak_memory_stats()
            except Exception:
                pass

    def sample(self) -> None:
        if self._torch and self.device == "cuda" and self._torch.cuda.is_available():
            allocated = self._torch.cuda.memory_allocated() / (1024 * 1024)
            reserved = self._torch.cuda.memory_reserved() / (1024 * 1024)
            peak_allocated = self._torch.cuda.max_memory_allocated() / (1024 * 1024)
            peak_reserved = self._torch.cuda.max_memory_reserved() / (1024 * 1024)

            self._gpu_peak_allocated = max(
                self._gpu_peak_allocated or 0.0,
                peak_allocated,
                allocated,
            )
            self._gpu_peak_reserved = max(
                self._gpu_peak_reserved or 0.0,
                peak_reserved,
                reserved,
            )

        if self._pynvml and self.device == "cuda":
            try:
                self._pynvml.nvmlInit()
                handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
                info = self._pynvml.nvmlDeviceGetMemoryInfo(handle)
                self._gpu_used = info.used / (1024 * 1024)
                self._gpu_total = info.total / (1024 * 1024)
                self._pynvml.nvmlShutdown()
            except Exception:
                pass

    def finish(self) -> ResourceMetrics:
        self.sample()

        system_cpu_percent = self._psutil.cpu_percent(interval=None) if self._psutil else None
        process_cpu_percent = self._process.cpu_percent(interval=None) if self._process else None
        process_ram_mb = (
            self._process.memory_info().rss / (1024 * 1024)
            if self._process
            else None
        )
        system_ram_percent = self._psutil.virtual_memory().percent if self._psutil else None

        allocated = None
        reserved = None
        if self._torch and self.device == "cuda" and self._torch.cuda.is_available():
            allocated = self._torch.cuda.memory_allocated() / (1024 * 1024)
            reserved = self._torch.cuda.memory_reserved() / (1024 * 1024)

        return ResourceMetrics(
            duration_s=perf_counter() - self.started_at,
            system_cpu_percent=system_cpu_percent,
            process_cpu_percent=process_cpu_percent,
            process_ram_mb=process_ram_mb,
            system_ram_percent=system_ram_percent,
            gpu_memory_allocated_mb=allocated,
            gpu_memory_reserved_mb=reserved,
            gpu_memory_peak_allocated_mb=self._gpu_peak_allocated,
            gpu_memory_peak_reserved_mb=self._gpu_peak_reserved,
            gpu_memory_used_mb=self._gpu_used,
            gpu_memory_total_mb=self._gpu_total,
        )

