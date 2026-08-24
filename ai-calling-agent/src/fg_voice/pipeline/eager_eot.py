"""Eager end-of-turn coordinator — spec §9.2 speculative extraction.

Deepgram Flux emits `EagerEndOfTurn` when it *thinks* the caller has
stopped talking but isn't fully sure yet. Waiting for the definitive
`EndOfTurn` adds ~200-400 ms of dead time. Starting extraction
speculatively on the eager event and committing/discarding based on
what happens next cuts that dead time to zero when the speculation
was right, and costs one wasted extractor call when it wasn't.

The Flux event sequence is one of:

  (a) StartOfTurn → EagerEndOfTurn → EndOfTurn
      → speculation was correct; commit
  (b) StartOfTurn → EagerEndOfTurn → TurnResumed → ... → EndOfTurn
      → speculation was wrong; cancel + wait for real EndOfTurn
  (c) StartOfTurn → EndOfTurn (no eager event)
      → normal path; extract on EndOfTurn

This module owns the state machine and the extractor-call
scheduling. It does NOT own:
- The extractor itself (`extraction/keyword_rules.py` or the LLM).
- The Deepgram WS transport (yet to be built).
- The prompt / TTS side (agent's response after extraction commits).

Design:

- One coordinator instance per turn — reset when a `StartOfTurn`
  event arrives (or externally, if the caller cancels).
- Extractor calls are async — the coordinator hands out
  `asyncio.Task` handles it can `.cancel()` on `TurnResumed`.
- Speculation results are cached under the transcript hash;
  if `EndOfTurn` arrives with the same transcript, we reuse the
  speculative result without a second extractor call.
- If `EndOfTurn` arrives with a DIFFERENT transcript (extra words
  captured after the eager event), we discard the speculation and
  re-extract on the final transcript.

All state is per-turn — a fresh coordinator (or a `.reset()`) on
each `StartOfTurn`. The runner owns coordinator lifecycle.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

from fg_voice.obs.logging import get_logger
from fg_voice.pipeline.stt_flux import FluxEvent, FluxEventKind

log = get_logger(__name__)


# `Coroutine[Any, Any, T]` (not `Awaitable[T]`) so `asyncio.create_task`
# accepts the return value — `create_task` narrows Awaitable → Coroutine.
# PEP 695 alias so `ExtractorFn[R]` parameterises cleanly.
type ExtractorFn[ExtractionT] = Callable[[str], Coroutine[Any, Any, ExtractionT]]


@dataclass(slots=True)
class _Speculation[ExtractionT]:
    """One speculative extraction in flight. `transcript` is the
    exact string handed to the extractor so we can decide whether
    a final EndOfTurn's transcript matches (reuse result) or differs
    (cancel + re-run)."""

    transcript: str
    task: asyncio.Task[ExtractionT]


@dataclass(slots=True)
class EagerEotCoordinator[ExtractionT]:
    """Per-turn state machine for eager EOT speculation.

    Instantiate once per turn (or call `.reset()` at StartOfTurn).
    Feed Flux events via `handle_event(evt)`; the return value tells
    the caller what to do next:

    - `AsyncNoop` / None → nothing to do (event was informational).
    - `AsyncCommit(result)` → the extractor produced a final result
      (either speculatively, or on the final EndOfTurn) and the
      caller can advance the graph.
    - `AsyncCancelled` → a speculation was cancelled; the caller
      may want to swallow a mid-flight backchannel.

    The extractor is caller-supplied so this module has zero
    dependency on `extraction/` — testable with a stub."""

    extractor: ExtractorFn[ExtractionT]
    _speculation: _Speculation[ExtractionT] | None = field(default=None, init=False)
    # Metrics (for observability + tests). Counts persist across
    # multiple turns if the caller doesn't reset — that's a feature
    # for aggregate stats.
    stats: EagerEotStats = field(default_factory=lambda: EagerEotStats(), init=False)

    def reset(self) -> None:
        """Called on `StartOfTurn`. Cancels any in-flight speculation
        from a prior half-completed turn (shouldn't happen under
        normal flow but the safety cost is one .cancel() call)."""
        if self._speculation is not None:
            self._speculation.task.cancel()
            self._speculation = None

    async def handle_event(self, event: FluxEvent) -> ExtractionT | None:
        """Process one Flux event. Returns the extraction result
        when the turn commits (via speculation or the final
        EndOfTurn), or None on informational events."""
        match event.kind:
            case FluxEventKind.START_OF_TURN:
                # Clear any lingering state before the new turn.
                self.reset()
                return None

            case FluxEventKind.EAGER_END_OF_TURN:
                # Start speculating on this transcript. Any transcript
                # is fair game — the extractor is stateless and cheap
                # enough that a wasted call costs less than the
                # latency saved when speculation is correct.
                transcript = (event.transcript or "").strip()
                if not transcript:
                    # No content to speculate on — the eager event
                    # was likely a very short pause on a filler word.
                    return None
                self._speculation = _Speculation(
                    transcript=transcript,
                    task=asyncio.create_task(self.extractor(transcript)),
                )
                self.stats.speculations_started += 1
                log.info(
                    "eager_eot.speculation_started",
                    transcript_len=len(transcript),
                )
                return None

            case FluxEventKind.TURN_RESUMED:
                # Caller kept talking — cancel the speculation. The
                # extractor call was wasted; the real EndOfTurn will
                # arrive with a longer transcript that supersedes it.
                if self._speculation is not None:
                    self._speculation.task.cancel()
                    self._speculation = None
                    self.stats.speculations_cancelled += 1
                    log.info("eager_eot.speculation_cancelled")
                return None

            case FluxEventKind.END_OF_TURN:
                transcript = (event.transcript or "").strip()
                # Case (a): speculation was correct — the final
                # transcript matches what we speculated on. Reuse.
                if self._speculation is not None and self._speculation.transcript == transcript:
                    task = self._speculation.task
                    self._speculation = None
                    try:
                        result = await task
                    except asyncio.CancelledError:
                        # Race: speculation was cancelled between
                        # the match check and the await. Fall
                        # through to the fresh-extraction path.
                        pass
                    else:
                        self.stats.speculations_reused += 1
                        log.info("eager_eot.speculation_reused")
                        return result

                # Case (b) / (c): no matching speculation. If we had
                # one for a shorter transcript, drop it — the final
                # transcript is longer / different and superseded it.
                if self._speculation is not None:
                    self._speculation.task.cancel()
                    self._speculation = None
                    self.stats.speculations_discarded += 1

                # Run a fresh extraction on the final transcript.
                # An empty transcript still hits the extractor —
                # some extractors want to see empty input (returns
                # "unclear" / low-confidence result).
                self.stats.final_extractions += 1
                return await self.extractor(transcript)

            case _:
                # StartOfTurn / TurnInfo / Metadata / etc — nothing
                # for the coordinator to do. The runner may observe
                # them for other reasons (barge-in, telemetry).
                return None


@dataclass(slots=True)
class EagerEotStats:
    """Per-coordinator counters. Useful for /metrics + eval:
    speculation_hit_rate = reused / started."""

    speculations_started: int = 0
    speculations_reused: int = 0
    speculations_cancelled: int = 0
    speculations_discarded: int = 0
    final_extractions: int = 0

    def hit_rate(self) -> float | None:
        """Fraction of speculations that were reused (the actual
        latency saving). Returns None if no speculation happened —
        avoids divide-by-zero + a misleading 0.0."""
        if self.speculations_started == 0:
            return None
        return self.speculations_reused / self.speculations_started


__all__ = [
    "EagerEotCoordinator",
    "EagerEotStats",
    "ExtractorFn",
]
