#!/usr/bin/env python3
"""Convert a raw Agent console log into public-safe structured lifecycle events."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_local_recovery import sanitize_agent_log, write_jsonl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--workload",
        choices=("checkpoint_contract", "translator_batch"),
        default="checkpoint_contract",
    )
    args = parser.parse_args()
    events = sanitize_agent_log(args.input, args.workload)
    if not events:
        parser.error("input log contains no recognized LRA lifecycle events")
    write_jsonl(args.output, events)
    print(f"wrote {len(events)} sanitized events to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
