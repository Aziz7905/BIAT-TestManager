from __future__ import annotations

from typing import Any

from django.utils import timezone


MAX_GENERATION_EVENTS = 200


def append_generation_event(
    session,
    event_type: str,
    *,
    message: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a safe, user-visible generation progress event on the session."""
    critic_report = dict(session.critic_report or {})
    events = list(critic_report.get("events") or [])
    event = {
        "type": event_type,
        "message": message or event_type.replace("_", " "),
        "payload": payload or {},
        "created_at": timezone.now().isoformat(),
    }
    events.append(event)
    critic_report["events"] = events[-MAX_GENERATION_EVENTS:]
    session.critic_report = critic_report
    session.save(update_fields=["critic_report", "updated_at"])
    return event


def merge_generation_metadata(session, **values: Any) -> None:
    critic_report = dict(session.critic_report or {})
    critic_report.update({key: value for key, value in values.items() if value is not None})
    session.critic_report = critic_report
    session.save(update_fields=["critic_report", "updated_at"])
