from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core import signing

from apps.automation.services import (
    build_execution_snapshot,
    get_test_execution_queryset_for_actor,
    verify_execution_stream_ticket,
)
from apps.automation.services.grid import (
    get_node_vnc_url_for_session,
    get_session_vnc_websocket_url,
)
from apps.automation.services.streaming import get_execution_group_name


logger = logging.getLogger(__name__)


class ExecutionStreamConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        execution_id = self.scope["url_route"]["kwargs"]["execution_id"]
        query_string = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        ticket = (query_string.get("ticket") or [None])[0]
        if not ticket:
            await self.close(code=4403)
            return

        try:
            payload = verify_execution_stream_ticket(
                ticket,
                expected_execution_id=execution_id,
            )
        except signing.BadSignature:
            await self.close(code=4403)
            return

        snapshot = await self._load_snapshot(
            user_id=payload["user_id"],
            execution_id=execution_id,
        )
        if snapshot is None:
            await self.close(code=4403)
            return

        self.group_name = get_execution_group_name(execution_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "execution.snapshot",
                "execution_id": str(execution_id),
                "payload": snapshot,
            }
        )

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def execution_event(self, event):
        await self.send_json(event["event"])

    @database_sync_to_async
    def _load_snapshot(self, *, user_id, execution_id):
        user_model = get_user_model()
        user = user_model.objects.filter(pk=user_id).first()
        if user is None:
            return None

        execution = (
            get_test_execution_queryset_for_actor(user)
            .select_related("result")
            .prefetch_related("steps", "artifacts", "checkpoints")
            .filter(pk=execution_id)
            .first()
        )
        if execution is None:
            return None
        return build_execution_snapshot(execution)


class BrowserStreamConsumer(AsyncWebsocketConsumer):
    _novnc_ws = None
    _forward_task = None

    async def connect(self):
        import websockets as ws_lib

        execution_id = self.scope["url_route"]["kwargs"]["execution_id"]
        query_string = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        ticket = (query_string.get("ticket") or [None])[0]

        if not ticket:
            await self.close(code=4403)
            return

        try:
            payload = verify_execution_stream_ticket(
                ticket,
                expected_execution_id=execution_id,
            )
        except signing.BadSignature:
            await self.close(code=4403)
            return

        execution = await self._load_execution(
            user_id=payload["user_id"],
            execution_id=execution_id,
        )
        if execution is None:
            await self.close(code=4403)
            return

        if not execution.selenium_session_id:
            await self.close(code=4404)
            return

        ws_url = await sync_to_async(_get_browser_ws_url)(execution)
        if not ws_url:
            logger.warning(
                "Browser stream unavailable: no VNC websocket URL resolved.",
                extra={
                    "execution_id": str(execution.id),
                    "selenium_session_id": execution.selenium_session_id,
                },
            )
            await self.close(code=4503)
            return

        try:
            self._novnc_ws = await _connect_to_browser_stream(ws_lib, ws_url)
        except Exception:
            logger.warning(
                "Browser stream unavailable: unable to connect to Selenium VNC websocket.",
                extra={
                    "execution_id": str(execution.id),
                    "selenium_session_id": execution.selenium_session_id,
                    "browser_ws_url": ws_url,
                },
                exc_info=True,
            )
            await self.close(code=4503)
            return

        client_protocols = self.scope.get("subprotocols") or []
        await self.accept(subprotocol="binary" if "binary" in client_protocols else None)
        self._forward_task = asyncio.create_task(self._forward_from_novnc())

    async def disconnect(self, close_code):
        if self._forward_task:
            self._forward_task.cancel()
        if self._novnc_ws:
            await self._novnc_ws.close()

    async def receive(self, text_data=None, bytes_data=None):
        if self._novnc_ws is None:
            return
        try:
            if bytes_data:
                await self._novnc_ws.send(bytes_data)
            elif text_data:
                await self._novnc_ws.send(text_data.encode())
        except Exception:
            await self.close()

    async def _forward_from_novnc(self):
        try:
            async for message in self._novnc_ws:
                if isinstance(message, bytes):
                    await self.send(bytes_data=message)
                else:
                    await self.send(text_data=message)
        except Exception:
            pass
        finally:
            await self.close()

    @database_sync_to_async
    def _load_execution(self, *, user_id, execution_id):
        user_model = get_user_model()
        user = user_model.objects.filter(pk=user_id).first()
        if user is None:
            return None
        return (
            get_test_execution_queryset_for_actor(user)
            .filter(pk=execution_id)
            .first()
        )


async def _connect_to_browser_stream(ws_lib, ws_url: str):
    try:
        return await ws_lib.connect(
            ws_url,
            subprotocols=["binary"],
            open_timeout=5,
        )
    except Exception:
        return await ws_lib.connect(ws_url, open_timeout=5)


def _get_browser_ws_url(execution) -> str | None:
    """
    Returns a browser VNC websocket URL for the execution's browser session.
    Reads from Redis cache first (written when session_started fires), then
    falls back to a live Grid API lookup (works during active sessions).
    """
    from django.conf import settings
    import redis as redis_lib

    execution_id = str(execution.id)
    session_id = execution.selenium_session_id

    try:
        client = redis_lib.from_url(
            getattr(settings, "REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
        )
        cached_ws = client.get(f"biat:exec:{execution_id}:browser_ws_url")
        if cached_ws:
            return cached_ws
        cached = client.get(f"biat:exec:{execution_id}:vnc_url")
        if cached:
            return (
                cached.rstrip("/")
                .replace("http://", "ws://")
                .replace("https://", "wss://")
                + "/websockify"
            )
    except Exception:
        pass

    browser_ws_url = get_session_vnc_websocket_url(session_id)
    if browser_ws_url:
        return browser_ws_url

    vnc_url = get_node_vnc_url_for_session(session_id)
    if not vnc_url:
        return None
    return (
        vnc_url.rstrip("/")
        .replace("http://", "ws://")
        .replace("https://", "wss://")
        + "/websockify"
    )
