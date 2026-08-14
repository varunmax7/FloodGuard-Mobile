"""Renders every `prerender: true` prompt in conversation/prompts.yaml
into 8 kHz μ-law and writes them to prompts/audio_bank/{locale}/.

Runs at build time and on demand. Implemented in P2 — this stub exists
so `make render-bank` and the CI docker build never fail from a missing
file, and so anyone reading the Makefile can find the entry point."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the prerendered TTS audio bank.")
    parser.add_argument("--locale", default="en-IN")
    args = parser.parse_args()

    print(f"render_audio_bank: locale={args.locale}")
    print("  → not implemented yet; wired in P2 once conversation/prompts.yaml lands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
