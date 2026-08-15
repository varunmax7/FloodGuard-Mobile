"""Backchannel picker: plays a short "Okay." / "Got it." clip on
`EndOfTurn` to mask the pause while the extractor and next-prompt
selection run (§8.4 step 5).

The audio comes from the pre-rendered bank under `backchannel_<i>`.
Selection is round-robin per call so consecutive turns don't sound
identical, and per-call so simultaneous calls don't unmask each other
in load tests."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from dataclasses import dataclass, field

from fg_voice.audio.bank import AudioBank, Clip


@dataclass(slots=True)
class BackchannelPicker:
    """Per-call rotating picker. Instantiate once at call start and
    call `.next(bank)` on every `EndOfTurn`."""

    _cycle: Iterator[int] | None = field(default=None, init=False, repr=False)

    def _rebuild(self, bank: AudioBank) -> Iterator[int]:
        indices = sorted(
            int(pid.rsplit("_", 1)[1]) for pid in bank.ids() if pid.startswith("backchannel_")
        )
        if not indices:
            return iter([])
        return itertools.cycle(indices)

    def next(self, bank: AudioBank) -> Clip | None:
        """Return the next backchannel clip, or None if the bank has
        no backchannel variants (dev bank rendered without them)."""
        if self._cycle is None:
            self._cycle = self._rebuild(bank)
        try:
            idx = next(self._cycle)
        except StopIteration:
            return None
        return bank.get(f"backchannel_{idx}")


__all__ = ["BackchannelPicker"]
