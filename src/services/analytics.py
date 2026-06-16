from __future__ import annotations

from src.storage.db import log_event


def track(session_id: str | None, event_name: str, **payload) -> None:
    log_event(session_id, event_name, payload)
