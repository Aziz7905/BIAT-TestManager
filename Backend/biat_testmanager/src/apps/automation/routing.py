from django.urls import path

from apps.automation.consumers import ExecutionStreamConsumer


websocket_urlpatterns = [
    path(
        "ws/executions/<uuid:execution_id>/",
        ExecutionStreamConsumer.as_asgi(),
    ),
]
