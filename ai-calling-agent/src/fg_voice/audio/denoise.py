"""Noise-suppression seam — spec §9.1 step 2.

The audio path is:

    μ-law → PCM16 → [denoise?] → frontend (DC/HPF/AGC/gate) → STT

Denoise is optional and pluggable. This module defines the seam
(`Denoiser` protocol) and ships a NoOp default so the audio path
runs end-to-end without an external denoiser wired.

Two production implementations were considered:

- **Krisp** — commercial SaaS-style SDK, best objective quality
  on 8 kHz telephony, licensed per-concurrent-call. Requires a
  Krisp license key and their SDK binary. Concrete impl will land
  as `KrispDenoiser` once ops confirms the license.

- **rnnoise** — open-source RNN model, GPL-3 licensed C code with
  Python bindings (`rnnoise-python`). Free but the bindings are
  a manual C++ build and the model is trained for 48 kHz — needs
  a resample loop to work on 8 kHz phone audio, which negates
  much of the quality win.

Neither ships in this commit. What we DO ship:

1. The `Denoiser` Protocol — one method, `process_pcm16(bytes) ->
   bytes`. Stateful per-call (Krisp's RNN carries state; rnnoise
   likewise). Instance-per-call, same lifecycle as `AudioFrontend`.
2. `NoOpDenoiser` — passthrough. Ships so the pipeline runs on any
   deploy without a license or C++ build.
3. `chain_denoiser_into_frontend(frontend, denoiser)` — wires the
   denoiser as a pre-frontend step. Not applied automatically to
   AudioFrontend to keep that module dep-free.

Latency budget note: Krisp adds ~5-10 ms per 20 ms frame on
current hardware. rnnoise ~2-3 ms. Either fits comfortably in the
turn budget (§5). But if the frame budget starts squeezing, the
denoiser is the first thing to drop — measurable-quality-win test
first, then decide.

Wiring at boot lives in `main.py`; a `DENOISE_PROVIDER` config
selects the implementation, defaults to `none`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from fg_voice.obs.logging import get_logger

log = get_logger(__name__)


@runtime_checkable
class Denoiser(Protocol):
    """One noise-suppression pass over a PCM16 frame.

    - Input: PCM16 bytes (little-endian int16, 8 kHz mono, typically
      160 samples / 320 bytes per Twilio frame).
    - Output: PCM16 bytes of the same shape.

    Implementations are stateful per call — the RNN or Krisp session
    carries information across frames — so instantiate once per call
    session and share across frames in-order.
    """

    def process_pcm16(self, pcm16: bytes) -> bytes: ...


@dataclass(slots=True)
class NoOpDenoiser:
    """Passthrough denoiser. Ships as the safe default so the
    pipeline runs end-to-end on any deploy without a licensed
    denoiser or C++ build. Zero latency, zero quality change.

    A `denoise_provider=none` deploy uses this; production replaces
    it with `KrispDenoiser` when the license is provisioned."""

    def process_pcm16(self, pcm16: bytes) -> bytes:
        return pcm16


@dataclass(slots=True)
class ChainedDenoiseFrontend:
    """Composes a `Denoiser` + `AudioFrontend` into one per-frame
    call. Kept as a separate class rather than shoved into
    `AudioFrontend` so the frontend module stays dependency-free and
    unit-testable in isolation.

    Usage in main.py:

        denoiser = _build_denoiser(settings)  # NoOp or Krisp
        frontend = AudioFrontend()
        pipeline = ChainedDenoiseFrontend(denoiser, frontend)
        clean_pcm16 = pipeline.process_pcm16(raw_pcm16_bytes)
    """

    denoiser: Denoiser
    # Typed as Any so this module has no import dep on frontend.py;
    # runtime is `AudioFrontend`. Kept intentionally structural.
    frontend: object  # AudioFrontend — kept object to avoid the import cycle risk

    def process_pcm16(self, pcm16: bytes) -> object:
        """Denoise first, then frontend. Returns the frontend's
        output shape (int16 numpy array). Caller-facing type is
        `object` to keep this module's imports minimal."""
        cleaned = self.denoiser.process_pcm16(pcm16)
        # We know structurally the frontend has this method — it's
        # the whole point of the seam. Runtime attribute access
        # rather than a static import keeps this module light.
        return self.frontend.process_pcm16(cleaned)  # type: ignore[attr-defined]


def build_denoiser(provider: str) -> Denoiser:
    """Factory. `provider` matches `Settings.denoise_provider`
    (`none` / `krisp` / `rnnoise`). Unknown providers fall back to
    NoOp with a loud warning — safer than crashing the boot for a
    typo in an ops env var that affects perception quality but not
    call-completion capability."""
    if provider == "none":
        return NoOpDenoiser()
    if provider == "krisp":
        # KrispDenoiser lands in a follow-up commit alongside the
        # license wiring. Falling back to NoOp keeps the pipeline
        # up when someone flips the flag before the impl ships.
        log.warning(
            "audio.denoise.provider_not_implemented",
            provider=provider,
            note="Krisp integration not yet built; using NoOpDenoiser",
        )
        return NoOpDenoiser()
    if provider == "rnnoise":
        log.warning(
            "audio.denoise.provider_not_implemented",
            provider=provider,
            note="rnnoise integration not yet built; using NoOpDenoiser",
        )
        return NoOpDenoiser()
    log.warning("audio.denoise.unknown_provider", provider=provider)
    return NoOpDenoiser()


__all__ = [
    "ChainedDenoiseFrontend",
    "Denoiser",
    "NoOpDenoiser",
    "build_denoiser",
]
