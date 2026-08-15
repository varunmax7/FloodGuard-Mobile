"""ASGI entrypoint. Wires the FastAPI app together — routes come from
the per-phase modules; the lifespan hook starts + stops the outbox
relay background task."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from fg_voice import __version__
from fg_voice.api import routes_reports
from fg_voice.api.routes_gather import router as gather_router
from fg_voice.api.routes_health import router as health_router
from fg_voice.api.routes_media import router as media_router
from fg_voice.api.routes_reports import router as reports_router
from fg_voice.api.routes_voice import router as voice_router
from fg_voice.config import get_settings
from fg_voice.obs.logging import configure_logging, get_logger
from fg_voice.persistence.alerts import (
    AlertBackend,
    AlertDispatcher,
    LogAlertBackend,
    WebhookAlertBackend,
)
from fg_voice.persistence.broker import InProcessBroker
from fg_voice.persistence.csv_projector import CsvProjectorDispatcher
from fg_voice.persistence.dispatchers import ChainDispatcher, PubSubDispatcher
from fg_voice.persistence.relay import Dispatcher, LogDispatcher, OutboxRelay

log = get_logger(__name__)

# Bound to the FastAPI `app.state` at lifespan entry; kept as
# module-level references so tests can peek at the running relay.
_relay_task: asyncio.Task[None] | None = None
_shutdown_event: asyncio.Event | None = None
_broker: InProcessBroker | None = None

# Graceful shutdown budget for the relay — enough for one final poll
# to finish, not so long that the ASGI server stalls on SIGTERM.
_RELAY_SHUTDOWN_TIMEOUT_SEC = 5.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _relay_task, _shutdown_event, _broker

    settings = get_settings()
    configure_logging(settings.fg_log_level, service="fg_voice")
    settings.require_production_secrets()
    log.info(
        "fg_voice.starting",
        version=__version__,
        env=settings.fg_env,
        region=settings.fg_region,
        agent_version=settings.fg_agent_version,
        runner_mode=settings.runner_mode,
        relay_enabled=settings.relay_enabled,
    )
    if not settings.admin_api_key.get_secret_value():
        # `require_production_secrets` already refuses to boot in
        # production without the key, so this branch is only hit in
        # dev/staging. Warn loudly so an operator doesn't accidentally
        # expose /reports to the internet.
        log.warning(
            "fg_voice.admin_auth_disabled",
            note="ADMIN_API_KEY is empty; /api/v1/reports* are unauthenticated",
        )

    # Clear any leftover state from a previous lifespan entry so a
    # re-entry (mostly tests) doesn't inherit stale task references.
    app.state.relay_task = None
    app.state.relay = None
    app.state.broker = None

    if settings.relay_enabled:
        _broker = InProcessBroker()
        routes_reports.set_broker(_broker)
        # PubSubDispatcher fans events into the SSE broker for live
        # consumers. CsvProjectorDispatcher optionally lands a row in
        # a shared CSV file (§12.3 fast path). Composed via
        # ChainDispatcher so both run per event; if either raises the
        # relay bumps retry_count and re-attempts.
        dispatchers: list[Dispatcher] = [PubSubDispatcher(broker=_broker)]
        if settings.csv_enabled:
            dispatchers.append(
                CsvProjectorDispatcher(
                    path=settings.csv_path,
                    agent_version=settings.fg_agent_version,
                )
            )
        if settings.alerts_enabled:
            backends: list[AlertBackend] = [LogAlertBackend()]
            if settings.alert_webhook_url:
                backends.append(
                    WebhookAlertBackend(
                        url=settings.alert_webhook_url,
                        timeout_sec=settings.alert_webhook_timeout_sec,
                    )
                )
            dispatchers.append(AlertDispatcher(backends=backends))
        dispatcher: Dispatcher = (
            dispatchers[0] if len(dispatchers) == 1 else ChainDispatcher(dispatchers)
        )
        relay = OutboxRelay(
            dispatcher=dispatcher,
            poll_interval_sec=settings.relay_poll_interval_sec,
        )
        _shutdown_event = asyncio.Event()
        _relay_task = asyncio.create_task(relay.run(_shutdown_event), name="fg_voice.outbox_relay")
        # Keep for observability + testability.
        app.state.broker = _broker
        app.state.relay = relay
        app.state.relay_task = _relay_task
        # LogDispatcher isn't wired in the chain today because the
        # relay-side logs already record dispatched entries; adding
        # log-in-chain would double-log every event.
        _ = LogDispatcher  # keep the import warm so the linter is quiet

    try:
        yield
    finally:
        if _shutdown_event is not None and _relay_task is not None:
            log.info("fg_voice.stopping.relay")
            _shutdown_event.set()
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(_relay_task, timeout=_RELAY_SHUTDOWN_TIMEOUT_SEC)
            if not _relay_task.done():
                _relay_task.cancel()
                with contextlib.suppress(BaseException):
                    await _relay_task
            _relay_task = None
            _shutdown_event = None
            app.state.relay_task = None
            app.state.relay = None
        routes_reports.set_broker(None)
        app.state.broker = None
        _broker = None
        log.info("fg_voice.stopping")


app = FastAPI(
    title="FloodGuard Voice Agent",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if get_settings().fg_env != "production" else None,
    redoc_url=None,
)

app.include_router(health_router)
app.include_router(voice_router)
app.include_router(media_router)
app.include_router(gather_router)
app.include_router(reports_router)
