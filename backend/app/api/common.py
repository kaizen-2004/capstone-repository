from __future__ import annotations

from fastapi import Request

from ..modules.event_engine import EventEngine


def event_engine(request: Request) -> EventEngine:
    return request.app.state.event_engine
