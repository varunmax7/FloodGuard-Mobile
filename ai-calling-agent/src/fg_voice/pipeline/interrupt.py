"""Barge-in coordinator (spec §7.4).

When `Flux.StartOfTurn` fires while agent audio is playing, three
things must happen immediately, in this order:

  1. Cancel the outstanding TTS / clip-playback task so no further
     frames enter the send buffer.
  2. Send a Twilio `clear` message so any frames Twilio has already
     buffered on their side are flushed.
  3. Drop anything still in our per-call outbound queue.

The order is intentional: cancelling the producer first prevents the
race where the clear message arrives, then a straggler frame from our
task refills the buffer.

This module is I/O-adjacent (it awaits a WebSocket send and cancels a
task) but has no knowledge of Deepgram, Pipecat, or Twilio auth — only
the primitives it needs, so it composes into any pipeline shape."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

from fg_voice.telephony.twilio_stream import build_clear

ClearSender = Callable[[str], Awaitable[None]]

# Minimum agent-audio duration before barge-in is allowed. Guards
# against echo triggering a false StartOfTurn on the leading frames
# of our own prompt (§7.4 rule 3). Kept small enough not to block a
# fast interrupter caller.
BARGE_IN_LOCKOUT_MS: Final[int] = 150


@dataclass(slots=True)
class InterruptController:
    """Per-call barge-in state. Instantiate at call start; call
    `track(task)` when a playback task is scheduled, and
    `on_start_of_turn()` when Flux says the caller started speaking."""

    stream_sid: str
    send_clear: ClearSender
    _playback_task: asyncio.Task[None] | None = None
    _playback_started_at: float | None = None
    _outbound_drain: Callable[[], None] | None = None
    _stats: BargeInStats = field(default_factory=lambda: BargeInStats())

    def track(
        self,
        task: asyncio.Task[None],
        drain_queue: Callable[[], None] | None = None,
    ) -> None:
        """Register the currently-playing task and (optionally) a
        callback that empties any local outbound queue."""
        self._playback_task = task
        self._playback_started_at = asyncio.get_event_loop().time()
        self._outbound_drain = drain_queue

    def release(self) -> None:
        """Called when playback finishes naturally — no barge-in
        happened, but we should stop tracking the task."""
        self._playback_task = None
        self._playback_started_at = None
        self._outbound_drain = None

    async def on_start_of_turn(self) -> BargeInResult:
        """Handle a Flux StartOfTurn event while the agent is speaking.
        Idempotent and safe to call when no playback is in flight."""
        if self._playback_task is None or self._playback_task.done():
            return BargeInResult(fired=False, reason="no_playback_in_flight")

        # Lockout guard: reject barge-in triggered by echo of our own
        # first frames. If it's before the lockout, mark it as false and
        # let the audio continue.
        if self._playback_started_at is not None:
            elapsed_ms = (asyncio.get_event_loop().time() - self._playback_started_at) * 1000
            if elapsed_ms < BARGE_IN_LOCKOUT_MS:
                self._stats.false_barge_ins += 1
                return BargeInResult(fired=False, reason="lockout")

        # 1. Cancel producer first.
        task = self._playback_task
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

        # 2. Twilio clear.
        with contextlib.suppress(Exception):
            await self.send_clear(build_clear(self.stream_sid))

        # 3. Drop local outbound queue.
        if self._outbound_drain is not None:
            with contextlib.suppress(Exception):
                self._outbound_drain()

        self._playback_task = None
        self._playback_started_at = None
        self._outbound_drain = None
        self._stats.fired += 1
        return BargeInResult(fired=True, reason=None)

    @property
    def stats(self) -> BargeInStats:
        return self._stats


@dataclass(slots=True, frozen=True)
class BargeInResult:
    fired: bool
    reason: str | None


@dataclass(slots=True)
class BargeInStats:
    fired: int = 0
    false_barge_ins: int = 0


__all__ = [
    "BARGE_IN_LOCKOUT_MS",
    "BargeInResult",
    "BargeInStats",
    "InterruptController",
]
