import os

from celery import Celery


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "biat_testmanager.settings")

app = Celery("biat_testmanager")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
