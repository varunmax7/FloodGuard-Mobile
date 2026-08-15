"""Node handlers: the glue between `graph.py` (pure data) and
`extraction/` (pure functions).

Every function here is stateless and does no I/O. Given an
`ExtractorId` and a caller utterance, dispatch to the concrete
extractor and produce a `SlotValue` shaped for `CallState.set_slot`.

Kept in its own module (per §6 repo layout) so a future refactor —
e.g. swapping keyword rules for the LLM extractor in P4 — does not
churn `graph.py`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final

from fg_voice.conversation.graph import ExtractorId
from fg_voice.conversation.state import Slot, SlotSource, SlotValue
from fg_voice.extraction import keyword_rules
from fg_voice.extraction.normalize import depth_to_cm
from fg_voice.extraction.schemas import (
    ConfirmationExtraction,
    DepthExtraction,
    FreeTextExtraction,
    HazardTypeExtraction,
    IntentExtraction,
    SeverityExtraction,
)

# Every categorical extractor emits an "unclear" sentinel when the
# caller's utterance didn't classify. The graph treats that as "no
# fill" and the reprompt ladder advances the attempt counter.
UNCLEAR: Final[str] = "unclear"


def run_extractor(
    extractor: ExtractorId,
    utterance: str,
    source: SlotSource = "asr",
) -> SlotValue | None:
    """Run the extractor named by `extractor` and shape the result as
    a SlotValue. Returns None when the utterance was empty or the
    extraction was "unclear" — the runner treats both as "no fill"
    and advances the reprompt ladder."""
    if extractor is ExtractorId.NONE:
        return None
    if not utterance.strip():
        return None

    if extractor is ExtractorId.INTENT:
        return _from_categorical(keyword_rules.extract_intent(utterance), source)
    if extractor is ExtractorId.HAZARD_TYPE:
        return _from_categorical(keyword_rules.extract_hazard_type(utterance), source)
    if extractor is ExtractorId.SEVERITY:
        return _from_categorical(keyword_rules.extract_severity(utterance), source)
    if extractor is ExtractorId.CONFIRMATION:
        return _from_categorical(keyword_rules.extract_confirmation(utterance), source)
    if extractor is ExtractorId.DEPTH:
        return _from_depth(keyword_rules.extract_depth(utterance), source)
    if extractor is ExtractorId.DESCRIPTION or extractor is ExtractorId.LOCATION:
        return _from_free_text(keyword_rules.extract_free_text(utterance), source)

    # Exhaustiveness: if a new ExtractorId is added, mypy strict on
    # this file will flag the missing branch — but only if the caller
    # passes the new variant. Guard at runtime too.
    raise NotImplementedError(f"no dispatch for extractor {extractor!r}")


def slot_for(extractor: ExtractorId) -> Slot | None:
    """Which slot the given extractor targets. `None` for NONE and for
    LOCATION (which the RAG resolver rewrites in P4)."""
    return _EXTRACTOR_TO_SLOT.get(extractor)


def dtmf_slot_value(
    slot: Slot,
    canonical_value: str,
) -> SlotValue:
    """Build a SlotValue from a DTMF-driven digit->value mapping.
    Confidence is 1.0 because the caller explicitly pressed the key —
    there is no ASR uncertainty to model."""
    value: str | int = (
        depth_to_cm(canonical_value)  # type: ignore[arg-type]
        if slot is Slot.WATER_DEPTH_CM
        else canonical_value
    )
    return SlotValue(
        value=value,
        confidence=1.0,
        source="dtmf",
        raw_transcript=None,
        captured_at=datetime.now(UTC),
    )


# ─── Internal ────────────────────────────────────────────────────────


_EXTRACTOR_TO_SLOT: Final[dict[ExtractorId, Slot]] = {
    ExtractorId.INTENT: Slot.INTENT,
    ExtractorId.HAZARD_TYPE: Slot.HAZARD_TYPE,
    ExtractorId.SEVERITY: Slot.SEVERITY,
    ExtractorId.DEPTH: Slot.WATER_DEPTH_CM,
    ExtractorId.CONFIRMATION: Slot.CONFIRMATION,
    ExtractorId.DESCRIPTION: Slot.DESCRIPTION,
    ExtractorId.LOCATION: Slot.LOCATION,
}


def _from_categorical(
    extraction: IntentExtraction
    | HazardTypeExtraction
    | SeverityExtraction
    | ConfirmationExtraction,
    source: SlotSource,
) -> SlotValue | None:
    if extraction.value == UNCLEAR:
        return None
    return SlotValue(
        value=extraction.value,
        confidence=extraction.confidence,
        source=source,
        raw_transcript=extraction.evidence or None,
    )


def _from_depth(extraction: DepthExtraction, source: SlotSource) -> SlotValue | None:
    if extraction.value == UNCLEAR:
        return None
    return SlotValue(
        value=depth_to_cm(extraction.value),
        confidence=extraction.confidence,
        source=source,
        raw_transcript=extraction.evidence or None,
    )


def _from_free_text(extraction: FreeTextExtraction | None, source: SlotSource) -> SlotValue | None:
    if extraction is None:
        return None
    return SlotValue(
        value=extraction.value,
        confidence=extraction.confidence,
        source=source,
        raw_transcript=extraction.evidence or None,
    )


__all__ = ["UNCLEAR", "dtmf_slot_value", "run_extractor", "slot_for"]
