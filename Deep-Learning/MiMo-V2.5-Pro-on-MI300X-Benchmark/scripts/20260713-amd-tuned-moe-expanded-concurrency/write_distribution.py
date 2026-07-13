#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node0-before", type=int, required=True)
    parser.add_argument("--node0-after", type=int, required=True)
    parser.add_argument("--node1-before", type=int, required=True)
    parser.add_argument("--node1-after", type=int, required=True)
    parser.add_argument("--expected-total", type=int, default=33)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = [
        ("node0", args.node0_before, args.node0_after, args.node0_after - args.node0_before),
        ("node1", args.node1_before, args.node1_after, args.node1_after - args.node1_before),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "worker\tbefore\tafter\tdelta\n"
        + "".join(f"{worker}\t{before}\t{after}\t{delta}\n" for worker, before, after, delta in rows),
        encoding="utf-8",
    )
    if any(delta <= 0 for _, _, _, delta in rows):
        raise SystemExit("Both workers must process requests")
    if sum(delta for _, _, _, delta in rows) != args.expected_total:
        raise SystemExit(
            f"Worker deltas must sum to {args.expected_total} (32 measured + 1 warmup)"
        )
    print(args.output)


if __name__ == "__main__":
    main()