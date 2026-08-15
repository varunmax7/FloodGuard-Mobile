"""Deepgram Flux event dataclasses + JSON-frame parser.

Flux is a streaming STT model with explicit turn-taking events on top
of the usual transcripts (§9.2). This module owns three things and
nothing else:

  1. A closed set of typed events (`StartOfTurn`, `EagerEndOfTurn`,
     `TurnResumed`, `EndOfTurn`, `TurnInfo`, `Metadata`).
  2. `parse_event(raw)` — bytes/str/dict → typed event, or raises.
  3. `FluxAction` — what the runner should do in response to each
     event, encoded as an enum so the runner is trivially unit-testable
     without a real Flux connection.

The live WebSocket client that speaks the wire protocol lands
separately once we have a Deepgram key on the CI runner; keeping the
event model isolated means we can unit-test all downstream code today."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FluxEventKind(StrEnum):
    """The event names Deepgram emits on the Flux stream."""

    START_OF_TURN = "StartOfTurn"
    TURN_INFO = "TurnInfo"
    EAGER_END_OF_TURN = "EagerEndOfTurn"
    TURN_RESUMED = "TurnResumed"
    END_OF_TURN = "EndOfTurn"
    METADATA = "Metadata"


class FluxAction(StrEnum):
    """How the runner reacts to a Flux event. Kept as a small enum so
    the mapping is a single lookup table and easy to test."""

    BARGE_IN = "barge_in"  # StartOfTurn while agent speaks
    UPDATE_TRANSCRIPT_DRAFT = "update_draft"  # TurnInfo — observability only
    SPECULATE = "speculate"  # EagerEndOfTurn — begin speculative extraction
    CANCEL_SPECULATION = "cancel_speculation"  # TurnResumed
    COMMIT_TURN = "commit_turn"  # EndOfTurn — backchannel + real pipeline
    NOOP = "noop"  # Metadata / anything advisory


@dataclass(frozen=True, slots=True)
class FluxEvent:
    """Base type. Kept intentionally minimal — the runner only reaches
    for `.transcript` on the two events that carry it."""

    kind: FluxEventKind
    transcript: str | None = None
    confidence: float | None = None
    raw: dict[str, Any] | None = None


class FluxProtocolError(ValueError):
    """Raised when the wire frame doesn't parse as a known Flux event."""


_ACTION_MAP: dict[FluxEventKind, FluxAction] = {
    FluxEventKind.START_OF_TURN: FluxAction.BARGE_IN,
    FluxEventKind.TURN_INFO: FluxAction.UPDATE_TRANSCRIPT_DRAFT,
    FluxEventKind.EAGER_END_OF_TURN: FluxAction.SPECULATE,
    FluxEventKind.TURN_RESUMED: FluxAction.CANCEL_SPECULATION,
    FluxEventKind.END_OF_TURN: FluxAction.COMMIT_TURN,
    FluxEventKind.METADATA: FluxAction.NOOP,
}


def action_for(event: FluxEvent) -> FluxAction:
    return _ACTION_MAP[event.kind]


def parse_event(raw: bytes | str | dict[str, Any]) -> FluxEvent:
    """Parse one Flux wire frame. Accepts bytes (as delivered by the
    WS client), str (as delivered by mock harnesses), or a pre-parsed
    dict (used by unit tests)."""
    if isinstance(raw, (bytes, bytearray)):
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise FluxProtocolError(f"invalid JSON frame: {exc}") from exc
    elif isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FluxProtocolError(f"invalid JSON frame: {exc}") from exc
    elif isinstance(raw, dict):
        payload = raw
    else:
        raise FluxProtocolError(f"unsupported frame type: {type(raw).__name__}")

    kind_str = payload.get("type") or payload.get("event")
    if not isinstance(kind_str, str):
        raise FluxProtocolError("Flux frame missing `type` field")
    try:
        kind = FluxEventKind(kind_str)
    except ValueError as exc:
        raise FluxProtocolError(f"unknown Flux event kind: {kind_str!r}") from exc

    transcript = payload.get("transcript")
    if transcript is not None and not isinstance(transcript, str):
        raise FluxProtocolError("`transcript` must be a string when present")
    confidence = payload.get("confidence")
    if confidence is not None and not isinstance(confidence, (int, float)):
        raise FluxProtocolError("`confidence` must be a number when present")

    return FluxEvent(
        kind=kind,
        transcript=transcript,
        confidence=float(confidence) if confidence is not None else None,
        raw=payload,
    )


__all__ = [
    "FluxAction",
    "FluxEvent",
    "FluxEventKind",
    "FluxProtocolError",
    "action_for",
    "parse_event",
]
