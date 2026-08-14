"""Latency budget assertion — replays a fixed 8-turn conversation N times
and fails if p50/p95 exceed the spec §5 budget. Wired into CI as a
blocking gate from P4 onward."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calls", type=int, default=200)
    parser.add_argument("--turns", type=int, default=8)
    args = parser.parse_args()
    print(f"bench_latency: calls={args.calls} turns={args.turns}")
    print("  → not implemented yet; wired in P4 once the full pipeline lands.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
