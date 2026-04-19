import os

from channels.routing import ProtocolTypeRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'biat_testmanager.settings')

django_asgi_application = get_asgi_application()

from biat_testmanager.routing import application as websocket_application


application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": AllowedHostsOriginValidator(websocket_application),
    }
)
