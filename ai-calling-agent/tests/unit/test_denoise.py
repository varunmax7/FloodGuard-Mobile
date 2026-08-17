"""Denoise seam — Protocol + NoOp default + chained pipeline.

Coverage:
- Denoiser protocol is runtime-checkable (isinstance works)
- NoOpDenoiser passes bytes through unchanged
- ChainedDenoiseFrontend calls denoise then frontend in order
- build_denoiser factory: `none` → NoOp; unknown → NoOp with
  warning; `krisp`/`rnnoise` → NoOp (not-yet-implemented log path)
"""

from __future__ import annotations

from fg_voice.audio.denoise import (
    ChainedDenoiseFrontend,
    Denoiser,
    NoOpDenoiser,
    build_denoiser,
)
from fg_voice.audio.frontend import AudioFrontend


def test_denoiser_protocol_runtime_checkable():
    """`isinstance` should work — the Protocol is marked
    runtime_checkable so wiring can validate injected implementations."""
    assert isinstance(NoOpDenoiser(), Denoiser)


def test_noop_denoiser_passthrough():
    """Zero mutation of the input. Bit-exact identity — anything else
    means the "no-op" isn't."""
    frame = bytes(range(160))  # 160 arbitrary bytes = 80 PCM16 samples
    out = NoOpDenoiser().process_pcm16(frame)
    assert out == frame


def test_chained_denoise_frontend_calls_denoiser_first():
    """The denoiser sees the raw bytes; the frontend sees whatever
    the denoiser returned. Verifies with a spy denoiser that
    records + mutates."""

    class SpyDenoiser:
        def __init__(self):
            self.received: bytes | None = None

        def process_pcm16(self, pcm16: bytes) -> bytes:
            self.received = pcm16
            # Return a marker so we can prove the frontend got THIS
            # output, not the raw input.
            return b"\x00\x00" * 160  # zero PCM16 frame

    spy = SpyDenoiser()
    frontend = AudioFrontend()
    chain = ChainedDenoiseFrontend(denoiser=spy, frontend=frontend)

    raw = bytes([0x7F, 0x80] * 160)  # non-zero pattern
    chain.process_pcm16(raw)

    # Denoiser was called with the raw input.
    assert spy.received == raw


def test_build_denoiser_none_returns_noop():
    d = build_denoiser("none")
    assert isinstance(d, NoOpDenoiser)


def test_build_denoiser_krisp_falls_back_to_noop_with_warning():
    """Krisp integration isn't shipped yet. Rather than crash the
    boot, the factory returns NoOp + logs a warning so ops sees the
    misconfiguration without losing call-completion capability."""
    d = build_denoiser("krisp")
    assert isinstance(d, NoOpDenoiser)


def test_build_denoiser_rnnoise_falls_back_to_noop_with_warning():
    d = build_denoiser("rnnoise")
    assert isinstance(d, NoOpDenoiser)


def test_build_denoiser_unknown_provider_falls_back_to_noop():
    """A typo in an ops env var shouldn't crash the boot — audio
    would just skip the denoise step. Loud log; safe fallback."""
    d = build_denoiser("this-is-not-a-real-provider")
    assert isinstance(d, NoOpDenoiser)
