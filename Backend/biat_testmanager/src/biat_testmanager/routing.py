from channels.routing import URLRouter

from apps.automation.routing import websocket_urlpatterns as automation_websocket_urlpatterns


websocket_urlpatterns = [
    *automation_websocket_urlpatterns,
]

application = URLRouter(websocket_urlpatterns)
