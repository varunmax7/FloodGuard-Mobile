"""/ws/media — the Twilio Media Streams WebSocket endpoint.

In P1 this is an echo bot: play a short greeting, then loop every
inbound frame back to the caller. P2 replaces the handler body with
the Pipecat pipeline; the socket-level plumbing stays here."""

from __future__ import annotations

import asyncio
import math
import struct

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from fg_voice.audio.codec import (
    TWILIO_FRAME_BYTES_ULAW,
    TWILIO_SAMPLE_RATE_HZ,
    pcm16_to_ulaw,
)
from fg_voice.obs.logging import get_logger
from fg_voice.telephony.twilio_stream import (
    MediaEvent,
    StartEvent,
    StopEvent,
    UnknownEventError,
    build_clear,
    build_mark,
    build_media,
    envelope_kind,
    parse_inbound,
)

log = get_logger(__name__)
router = APIRouter(tags=["media"])


def _generate_beep_pcm16(freq_hz: int = 660, duration_ms: int = 400) -> bytes:
    """A short synthetic beep as the P1 greeting. Real prompts land in P2."""
    n = TWILIO_SAMPLE_RATE_HZ * duration_ms // 1000
    amp = 12_000  # -8 dBFS-ish, comfortably below clipping
    samples: bytes = b"".join(
        struct.pack("<h", int(amp * math.sin(2 * math.pi * freq_hz * i / TWILIO_SAMPLE_RATE_HZ)))
        for i in range(n)
    )
    return samples


_GREETING_ULAW: bytes = pcm16_to_ulaw(_generate_beep_pcm16())


async def _send_ulaw_paced(
    ws: WebSocket, stream_sid: str, ulaw: bytes, frame_ms: int = 20
) -> None:
    """Send μ-law bytes as 20 ms frames, paced in real time. Twilio does
    not require pacing, but pacing prevents us from flooding their
    buffer and enables clean barge-in interruption later."""
    for i in range(0, len(ulaw), TWILIO_FRAME_BYTES_ULAW):
        frame = ulaw[i : i + TWILIO_FRAME_BYTES_ULAW]
        if not frame:
            continue
        await ws.send_text(build_media(stream_sid, frame))
        await asyncio.sleep(frame_ms / 1000)


@router.websocket("/ws/media")
async def media_ws(ws: WebSocket) -> None:
    """Echo bot: greeting → echo caller's audio 1:1."""
    await ws.accept(subprotocol="audio.twilio.com")
    stream_sid: str | None = None
    frames_in = 0
    frames_out = 0

    try:
        while True:
            raw = await ws.receive_text()
            try:
                evt = parse_inbound(raw)
            except UnknownEventError:
                log.debug("media.unknown_event", kind=envelope_kind(raw))
                continue

            if isinstance(evt, StartEvent):
                stream_sid = evt.stream_sid
                log.info(
                    "media.start",
                    stream_sid=stream_sid,
                    call_sid=evt.call_sid,
                    encoding=evt.media_format_encoding,
                    sample_rate=evt.media_format_sample_rate,
                    params=list(evt.custom_parameters.keys()),
                )
                # Play the greeting, then send a mark so we can time the
                # end of the prompt when Twilio ACKs it.
                await _send_ulaw_paced(ws, stream_sid, _GREETING_ULAW)
                await ws.send_text(build_mark(stream_sid, "greeting_end"))

            elif isinstance(evt, MediaEvent):
                if stream_sid is None:
                    continue  # media before start; ignore
                frames_in += 1
                frames_out += 1
                # Echo the caller's frame verbatim. No pacing sleep here:
                # inbound frames already arrive at 20 ms cadence, so
                # forwarding preserves timing without extra latency.
                await ws.send_text(build_media(stream_sid, evt.payload))

            elif isinstance(evt, StopEvent):
                log.info(
                    "media.stop",
                    stream_sid=stream_sid,
                    frames_in=frames_in,
                    frames_out=frames_out,
                )
                break

            # DtmfEvent / MarkEvent are ignored by the P1 echo bot; P2
            # wires them into the conversation DAG.

    except WebSocketDisconnect:
        log.info(
            "media.disconnect",
            stream_sid=stream_sid,
            frames_in=frames_in,
            frames_out=frames_out,
        )
    finally:
        if stream_sid is not None:
            try:
                # A trailing `clear` on close prevents any queued audio
                # from continuing to play if Twilio holds the leg open
                # briefly after our WS closes.
                await ws.send_text(build_clear(stream_sid))
            except Exception:
                pass  # noqa: S110 — WS already gone; best-effort close
