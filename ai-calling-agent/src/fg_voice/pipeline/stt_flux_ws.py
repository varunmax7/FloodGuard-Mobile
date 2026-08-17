"""Deepgram Flux WebSocket transport — spec §9.2.

The event dataclasses + parser live in `stt_flux.py`; this module owns
the wire connection and the send/receive coroutines. Kept separate so
downstream code (runner, eager EOT, tests) can be unit-tested against
the parsed event stream without a Deepgram key on the CI runner.

Wire shape (per Deepgram Flux docs):

- URL: `wss://api.deepgram.com/v2/listen?<params>`  (Flux endpoint;
  path may evolve — the constant is centralised here so a doc-update
  is a one-line change).
- Auth: `Authorization: Token <api_key>` header on the WS handshake.
- Client → server: raw PCM/μ-law audio bytes framed however (Twilio's
  20 ms μ-law works directly; encoding+sample_rate declared in URL
  params).
- Server → client: JSON events, one per WS message, matching the
  `FluxEventKind` set parsed by `stt_flux.parse_event`.

Design notes:

- **Async iterator interface.** `FluxClient.events()` yields typed
  `FluxEvent`s so the runner can `async for` naturally.
- **Send is a separate coroutine.** `FluxClient.send_audio(chunk)` is
  called from the media WS handler as each Twilio frame arrives. The
  underlying WS is full-duplex; asyncio's `websockets` library handles
  the interleaving safely.
- **Reconnect / retry is the caller's job.** A dropped Flux WS is
  fatal for the current turn; the runner catches `FluxTransportError`
  and either reconnects or degrades to Twilio Gather. Keeping retry
  out of this module makes the seam testable — a fake `FluxClient`
  can be a scripted iterator with zero WS code.
- **Config injection (§9.2).** Per-node `eot_threshold` /
  `eot_timeout_ms` can be updated mid-call via
  `send_config({"eot_threshold": 0.8, ...})`. Deepgram accepts a
  control frame with `{"type": "Configure", "config": {...}}`. Wire
  shape confirmed against docs at implementation time; the constant
  is defined here so a spec change is a one-line edit.

**Import-layer note.** `pipeline/` sits below `conversation/` per the
layered contract — the runner may reach down here, but this module
must not import from conversation. That's why `build_url` takes plain
config values rather than a `Settings` object; the caller assembles
them from `Settings`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Final, Protocol
from urllib.parse import urlencode

from fg_voice.obs.logging import get_logger
from fg_voice.pipeline.stt_flux import FluxEvent, FluxProtocolError, parse_event

log = get_logger(__name__)


# Base URL is centralised so a doc-update is a one-line change. Path
# component here matches Deepgram's Flux endpoint at the time of the
# spec write-up; keep this in sync with §4 of the Deepgram docs.
FLUX_WSS_BASE: Final[str] = "wss://api.deepgram.com/v2/listen"

# Default connect timeout for the WS handshake. Anything longer than a
# few seconds means Deepgram is down or the region is unreachable — we
# want to fail fast to the fallback path, not stall the caller.
DEFAULT_CONNECT_TIMEOUT_SEC: Final[float] = 3.0


class FluxTransportError(RuntimeError):
    """Raised when the Flux WS fails at the transport layer — handshake
    rejected, unexpected close, IO error mid-stream. The runner treats
    this as fatal for the current turn and either reconnects or falls
    back to Twilio Gather."""


@dataclass(frozen=True, slots=True)
class FluxConfig:
    """Bundled connection parameters. Kept as a plain dataclass so tests
    can construct one without a full `Settings` object."""

    api_key: str
    model: str = "flux-general-en"
    encoding: str = "mulaw"
    sample_rate: int = 8000
    eot_threshold: float = 0.7
    eager_eot_threshold: float = 0.55
    eot_timeout_ms: int = 1200
    keyterms: tuple[str, ...] = ()

    def to_url_params(self) -> dict[str, str]:
        """Flatten to a dict suitable for URL-encoding. Deepgram accepts
        `keyterm` as a repeated param — we emit it comma-joined here and
        the URL builder repeats the key. Empty tuple → no `keyterm` at
        all (Deepgram treats absence as "no bias")."""
        params: dict[str, str] = {
            "model": self.model,
            "encoding": self.encoding,
            "sample_rate": str(self.sample_rate),
            "eot_threshold": f"{self.eot_threshold:.2f}",
            "eager_eot_threshold": f"{self.eager_eot_threshold:.2f}",
            "eot_timeout_ms": str(self.eot_timeout_ms),
        }
        return params


def build_url(config: FluxConfig, *, base: str = FLUX_WSS_BASE) -> str:
    """Assemble the full WSS URL from `config`. Keyterms are appended
    as repeated `keyterm=<term>` params (Deepgram's documented shape),
    URL-encoded so terms with spaces survive."""
    base_params = list(config.to_url_params().items())
    # Repeat `keyterm=` for each term, in order. `doseq=True` on
    # urlencode would work if we pre-shaped as `{"keyterm": [...]}`;
    # a simple manual pass makes the ordering explicit for tests.
    keyterm_pairs = [("keyterm", term) for term in config.keyterms]
    query = urlencode(base_params + keyterm_pairs, doseq=False)
    return f"{base}?{query}"


class WebSocketLike(Protocol):
    """Minimal WS surface the client needs. Matches the interface
    exposed by `websockets.asyncio.client.ClientConnection`, but
    typed as a Protocol so a scripted test double can substitute
    without importing the websockets library."""

    async def send(self, message: str | bytes) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class WebSocketConnector(Protocol):
    """Factory: (url, headers) → open WS. Injected so tests can pass a
    fake and production passes a `websockets.asyncio.client.connect`
    wrapper. Kept behind a Protocol so this module has no hard import
    on the `websockets` package."""

    async def __call__(
        self, url: str, *, headers: dict[str, str], timeout_sec: float
    ) -> WebSocketLike: ...


async def default_connector(
    url: str,
    *,
    headers: dict[str, str],
    timeout_sec: float,
) -> WebSocketLike:
    """Real WS opener using the `websockets` library. Imported lazily
    so the test suite can substitute a fake without pulling websockets
    into its import graph."""
    from websockets.asyncio.client import connect

    connection = await asyncio.wait_for(
        connect(url, additional_headers=headers),
        timeout=timeout_sec,
    )
    return connection  # type: ignore[return-value]


@dataclass(slots=True)
class FluxClient:
    """One-per-call Flux WS client.

    Lifecycle:

        client = FluxClient(config=..., connector=default_connector)
        await client.connect()

        # Producer side (from the Twilio media handler):
        await client.send_audio(pcm_or_ulaw_bytes)

        # Consumer side (from the runner):
        async for event in client.events():
            ...

        await client.close()

    The two sides are independent asyncio tasks — the client owns no
    dispatch of its own. `events()` terminates when the server closes
    the WS or `close()` is called locally.
    """

    config: FluxConfig
    connector: WebSocketConnector
    connect_timeout_sec: float = DEFAULT_CONNECT_TIMEOUT_SEC
    _ws: WebSocketLike | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)

    async def connect(self) -> None:
        """Open the Flux WS. Raises `FluxTransportError` on any handshake
        failure (bad key, unreachable region, timeout)."""
        if self._ws is not None:
            raise FluxTransportError("Flux client already connected")
        url = build_url(self.config)
        headers = {"Authorization": f"Token {self.config.api_key}"}
        try:
            self._ws = await self.connector(
                url, headers=headers, timeout_sec=self.connect_timeout_sec
            )
        except TimeoutError as exc:
            raise FluxTransportError(
                f"Flux WS connect timed out after {self.connect_timeout_sec}s"
            ) from exc
        except Exception as exc:
            raise FluxTransportError(f"Flux WS connect failed: {exc}") from exc
        log.info(
            "flux.ws.connected",
            model=self.config.model,
            sample_rate=self.config.sample_rate,
            keyterm_count=len(self.config.keyterms),
        )

    async def send_audio(self, chunk: bytes) -> None:
        """Push one audio frame to Flux. Chunk size is up to the caller —
        Twilio's native 20 ms μ-law frames work directly. Silently
        no-ops if the client hasn't been connected yet (caller may
        buffer while we handshake)."""
        if self._ws is None:
            log.warning("flux.ws.send_before_connect", bytes=len(chunk))
            return
        if self._closed:
            return
        try:
            await self._ws.send(chunk)
        except Exception as exc:
            raise FluxTransportError(f"Flux WS send failed: {exc}") from exc

    async def send_config(self, updates: dict[str, Any]) -> None:
        """Update per-node EOT knobs mid-call (§9.2). Sends a Configure
        control frame with the partial update. Silently no-ops when the
        client is closed or not yet connected."""
        if self._ws is None or self._closed:
            return
        frame = json.dumps({"type": "Configure", "config": updates})
        try:
            await self._ws.send(frame)
        except Exception as exc:
            raise FluxTransportError(f"Flux WS configure failed: {exc}") from exc
        log.debug("flux.ws.reconfigured", updates=list(updates.keys()))

    async def events(self) -> AsyncIterator[FluxEvent]:
        """Async iterator over parsed Flux events. Terminates when the
        server closes the WS. Malformed frames are logged and skipped
        — a single bad frame shouldn't kill the turn."""
        if self._ws is None:
            raise FluxTransportError("Flux client not connected")
        while not self._closed:
            try:
                raw = await self._ws.recv()
            except Exception as exc:
                # ConnectionClosed is normal at end-of-call; treat other
                # errors as transport failures.
                name = type(exc).__name__
                if "ConnectionClosed" in name:
                    log.info("flux.ws.closed_by_server")
                    return
                raise FluxTransportError(f"Flux WS recv failed: {exc}") from exc
            try:
                event = parse_event(raw)
            except FluxProtocolError as exc:
                log.warning("flux.ws.bad_frame", error=str(exc))
                continue
            yield event

    async def close(self) -> None:
        """Idempotent close. Safe to call multiple times."""
        if self._closed:
            return
        self._closed = True
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close(code=1000, reason="normal")
            self._ws = None
        log.info("flux.ws.closed_local")


__all__ = [
    "DEFAULT_CONNECT_TIMEOUT_SEC",
    "FLUX_WSS_BASE",
    "FluxClient",
    "FluxConfig",
    "FluxTransportError",
    "WebSocketConnector",
    "WebSocketLike",
    "build_url",
    "default_connector",
]
