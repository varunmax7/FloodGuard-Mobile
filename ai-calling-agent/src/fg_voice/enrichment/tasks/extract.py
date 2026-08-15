"""Task 3a (§11): deep extraction over the full call context.

This is the LLM boundary. The design:

- `LLMExtractor` is a Protocol that the flow depends on. Real
  implementations (OpenAI / Bedrock / vLLM) live under `extraction/`
  and get injected at wire-time in `main.py`.
- The default shipped here is `NoOpExtractor` — returns no revised
  slots so the row stays whatever the in-call extractor produced. This
  keeps the P6 flow runnable end-to-end without an API key configured.

Design invariant (CLAUDE.md #1): the extractor NEVER decides the next
node and NEVER produces caller-facing text. Its output here is a
`RevisedSlots` dict — a set of *proposed* slot overrides. `persist`
reconciles them against the stored values (only overwrite if
confidence is higher).

We deliberately do not put this under `extraction/` — that package is
the *in-call* extractor (keyword rules + normalisers, no LLM). The
LLM-based deep pass runs post-call and is a distinct concern; keeping
it under `enrichment/tasks/` makes the split obvious in imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from fg_voice.enrichment.models import EnrichmentContext


@dataclass(slots=True, frozen=True)
class RevisedSlots:
    """One deep-extract result. Each entry is a proposed override for
    a slot; the flow's persist step reconciles against stored values.
    `confidence` is the extractor's self-reported score in [0, 1]."""

    values: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    notes: str = ""


class LLMExtractor(Protocol):
    """Bounded LLM call: transcript in, structured output out. See
    CLAUDE.md invariant #1 — this must NEVER produce free-form
    caller-facing prose, and must NEVER route the conversation."""

    async def extract(self, snapshot_description: str | None) -> RevisedSlots: ...


@dataclass(slots=True)
class NoOpExtractor:
    """Default. Returns an empty RevisedSlots. Ships so the flow can
    run end-to-end without an LLM configured; a real deploy swaps this
    for `extraction.llm.OpenAiExtractor` (lands with the LLM adapter)."""

    async def extract(self, snapshot_description: str | None) -> RevisedSlots:
        return RevisedSlots()


async def deep_extract(ctx: EnrichmentContext, *, extractor: LLMExtractor) -> None:
    """Run the extractor over the raw description and stash proposed
    slot revisions on the accumulator. `persist` reconciles."""
    revised = await extractor.extract(ctx.snapshot.description)
    if revised.values:
        ctx.result.revised_slots.update(revised.values)
        ctx.result.notes.append(
            f"deep_extract proposed {sorted(revised.values.keys())} at conf={revised.confidence:.2f}"
        )


__all__ = ["LLMExtractor", "NoOpExtractor", "RevisedSlots", "deep_extract"]
