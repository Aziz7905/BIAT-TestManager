try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ModuleNotFoundError:  # pragma: no cover - fallback until Celery is installed
    celery_app = None
    __all__ = ()
