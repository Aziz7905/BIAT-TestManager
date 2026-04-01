from contextlib import AbstractContextManager
import importlib.util

from django.conf import settings


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
            mlflow.set_tags(self.tags)
        if self.params:
            mlflow.log_params(self.params)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self._mlflow and self._run:
            if exc_value is not None:
                self.log_param("status", "failed")
                self.log_error(str(exc_value))
            self._mlflow.end_run()
        return False

    def log_param(self, key: str, value):
        if self._mlflow:
            self._mlflow.log_param(key, value)

    def log_params(self, values: dict):
        if self._mlflow and values:
            self._mlflow.log_params(values)

    def log_metrics(self, values: dict[str, float]):
        if self._mlflow and values:
            self._mlflow.log_metrics(values)

    def log_dict(self, artifact: dict, artifact_file: str):
        if self._mlflow:
            self._mlflow.log_dict(artifact, artifact_file)

    def log_text(self, text: str, artifact_file: str):
        if self._mlflow:
            self._mlflow.log_text(text, artifact_file)

    def log_error(self, message: str):
        if self._mlflow:
            self._mlflow.log_text(message, "errors.txt")
