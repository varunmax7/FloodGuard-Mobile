"""LLM-driven caller persona simulator. Drives an LLM caller against the
agent over the real WebSocket. Personas defined in spec §18.5.
Implemented in P8."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all-personas", action="store_true")
    parser.add_argument("--persona", default=None)
    args = parser.parse_args()
    print(f"simulate_call: persona={args.persona} all={args.all_personas}")
    print("  → not implemented yet; wired in P8.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
