"""Live reports feed for admin + Flutter clients (§13.1).

`GET /api/v1/reports/stream` is a Server-Sent Events stream. Every
outbox row that lands via the relay's `PubSubDispatcher` fans out to
every open SSE subscriber as one `data:` frame. The client sees a
new-report event within milliseconds of the DB write committing.

We DON'T write our own SSE library — just the small subset we need
(`data: {json}\\n\\n` + periodic `:keepalive\\n\\n` comments to stop
proxies dropping the connection)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Final

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse

from fg_voice.obs.logging import get_logger
from fg_voice.persistence.broker import InProcessBroker, ReportEvent, SubscriberLagged

log = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["reports"])

# The broker is process-scoped. Wired at boot in main.py's lifespan;
# routes reach for it via `_broker_provider()` so tests can override
# the singleton without touching global state.
_broker_singleton: InProcessBroker | None = None

# How often to emit `:keepalive` when there are no events. Chosen
# below the 30s default proxy idle timeout (ALB, nginx) so an idle
# subscriber's connection doesn't get reset.
KEEPALIVE_INTERVAL_SEC: Final[float] = 15.0


def set_broker(broker: InProcessBroker | None) -> None:
    """Called by `main.py`'s lifespan at boot (with the real broker)
    and at shutdown (with `None`)."""
    global _broker_singleton
    _broker_singleton = broker


def _broker_provider() -> InProcessBroker | None:
    return _broker_singleton


@router.get("/reports/stream")
async def stream_reports(request: Request) -> Response:
    """Long-lived SSE connection. Closes cleanly when the client
    disconnects."""
    broker = _broker_provider()
    if broker is None:
        # Boot hasn't wired the broker yet, or the relay is disabled
        # in this deploy. Return an empty stream that immediately closes.
        return Response(status_code=503, content="reports stream not available")

    return StreamingResponse(
        _event_stream(request, broker),
        media_type="text/event-stream",
        # `X-Accel-Buffering: no` lets nginx flush frames immediately.
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _event_stream(request: Request, broker: InProcessBroker) -> AsyncIterator[bytes]:
    """The generator that produces SSE frames. Exits when the client
    disconnects OR the request scope is cancelled."""
    async with broker.subscribe() as queue:
        log.info("reports.stream.subscribed", subscribers=broker.subscriber_count)
        # Emit an initial hello so the client knows the stream is alive
        # before any events arrive.
        yield _sse_comment("connected")
        try:
            while True:
                if await request.is_disconnected():
                    log.info("reports.stream.client_disconnected")
                    return
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL_SEC)
                except TimeoutError:
                    yield _sse_comment("keepalive")
                    continue
                if isinstance(item, SubscriberLagged):
                    yield _sse_event(
                        "lagged",
                        {"note": "subscriber fell behind; some events were dropped"},
                    )
                    continue
                yield _sse_event(item.event_type, item.payload)
        finally:
            log.info(
                "reports.stream.unsubscribed",
                subscribers=max(0, broker.subscriber_count - 1),
            )


def _sse_event(event_type: str, payload: dict[str, object]) -> bytes:
    """SSE frame: `event:` + `data:` + trailing blank line. `event:` is
    optional in the spec but useful for client-side filtering."""
    body = json.dumps(payload, separators=(",", ":"), default=str)
    return f"event: {event_type}\ndata: {body}\n\n".encode()


def _sse_comment(text: str) -> bytes:
    """A line starting with `:` is a comment; used for keepalives so
    proxies see traffic without the client seeing a fake event."""
    return f": {text}\n\n".encode()


# Test-friendly re-exports so unit tests can bypass the FastAPI
# `Request` fixture when they only care about the generator behaviour.
__all__ = [
    "KEEPALIVE_INTERVAL_SEC",
    "_broker_provider",
    "_event_stream",
    "_sse_comment",
    "_sse_event",
    "router",
    "set_broker",
    "stream_reports",
]


# Unused import silencer for `ReportEvent` — importing here keeps the
# module-level typing hint explicit for readers even though the
# stream generator receives events via the broker queue.
_ = ReportEvent
