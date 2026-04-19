from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core import signing

from apps.automation.services import (
    build_execution_snapshot,
    get_test_execution_queryset_for_actor,
    verify_execution_stream_ticket,
)
from apps.automation.services.streaming import get_execution_group_name


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
