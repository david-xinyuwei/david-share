#!/usr/bin/env python3
"""Prove that event summaries vary with materially different inputs."""

from __future__ import annotations

from pathlib import Path

from lra_resilience.events import summarize_event_file


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    invocation = summarize_event_file(ROOT / "tests" / "fixtures" / "invocations.jsonl")
    responses = summarize_event_file(ROOT / "tests" / "fixtures" / "responses.jsonl")
    if invocation == responses:
        print("FAIL: materially different event streams produced identical summaries")
        return 1
    if invocation["phases"] != [1, 2] or not invocation["recovery_observed"]:
        print("FAIL: invocation fixture did not preserve phase/recovery semantics")
        return 1
    if responses["output_indexes"] != [0, 1] or not responses["in_progress_reset_observed"]:
        print("FAIL: responses fixture did not preserve output/reset semantics")
        return 1
    print("PASS: differential summaries changed with protocol-level input")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
