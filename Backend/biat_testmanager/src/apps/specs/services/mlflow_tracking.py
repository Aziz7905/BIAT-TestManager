from contextlib import AbstractContextManager
import importlib.util
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class MLflowRunLogger(AbstractContextManager):
    def __init__(
        self,
        run_name: str,
        *,
        params: dict | None = None,
        tags: dict | None = None,
    ):
        self.run_name = run_name
        self.params = params or {}
        self.tags = tags or {}
        self._mlflow = None
        self._run = None

    @property
    def enabled(self) -> bool:
        return importlib.util.find_spec("mlflow") is not None

    def __enter__(self):
        if not self.enabled:
            return self

        try:
            import mlflow

            self._mlflow = mlflow
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            experiment = mlflow.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)
            if experiment is None:
                experiment_id = mlflow.create_experiment(
                    settings.MLFLOW_EXPERIMENT_NAME,
                    artifact_location=settings.MLFLOW_ARTIFACT_ROOT,
                )
                mlflow.set_experiment(experiment_id=experiment_id)
            else:
                mlflow.set_experiment(experiment_name=settings.MLFLOW_EXPERIMENT_NAME)
            self._run = mlflow.start_run(run_name=self.run_name)
            if self.tags:
                self._mlflow.set_tags(self.tags)
            if self.params:
                self._mlflow.log_params(self.params)
        except Exception as exc:
            logger.warning("MLflow run setup failed: %s", exc, exc_info=True)
            self._mlflow = None
            self._run = None
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._mlflow and self._run:
            try:
                if exc_value is not None:
                    self.log_param("status", "failed")
                    self.log_error(str(exc_value))
                self._mlflow.end_run()
            except Exception as exc:
                logger.warning("MLflow run close failed: %s", exc, exc_info=True)
        return False

    def log_param(self, key: str, value):
        if self._mlflow:
            try:
                self._mlflow.log_param(key, value)
            except Exception as exc:
                logger.debug("MLflow log_param failed for %s: %s", key, exc, exc_info=True)

    def log_params(self, values: dict):
        if self._mlflow and values:
            try:
                self._mlflow.log_params(values)
            except Exception as exc:
                logger.debug("MLflow log_params failed: %s", exc, exc_info=True)

    def log_metrics(self, values: dict[str, float]):
        if self._mlflow and values:
            try:
                self._mlflow.log_metrics(values)
            except Exception as exc:
                logger.debug("MLflow log_metrics failed: %s", exc, exc_info=True)

    def log_dict(self, artifact: dict, artifact_file: str):
        if self._mlflow:
            try:
                self._mlflow.log_dict(artifact, artifact_file)
            except Exception as exc:
                logger.debug("MLflow log_dict failed for %s: %s", artifact_file, exc, exc_info=True)

    def log_text(self, text: str, artifact_file: str):
        if self._mlflow:
            try:
                self._mlflow.log_text(text, artifact_file)
            except Exception as exc:
                logger.debug("MLflow log_text failed for %s: %s", artifact_file, exc, exc_info=True)

    def log_error(self, message: str):
        if self._mlflow:
            try:
                self._mlflow.log_text(message, "errors.txt")
            except Exception as exc:
                logger.debug("MLflow log_error failed: %s", exc, exc_info=True)
