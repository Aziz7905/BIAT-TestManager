from django.urls import path

from apps.automation.consumers import BrowserStreamConsumer, ExecutionStreamConsumer


websocket_urlpatterns = [
    path(
        "ws/executions/<uuid:execution_id>/",
        ExecutionStreamConsumer.as_asgi(),
    ),
    path(
        "ws/executions/<uuid:execution_id>/browser-stream/",
        BrowserStreamConsumer.as_asgi(),
    ),
]
