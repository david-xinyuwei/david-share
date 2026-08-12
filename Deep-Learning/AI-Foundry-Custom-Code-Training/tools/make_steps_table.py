"""Render the README steady-state table directly from evidence/training-metrics.jsonl.

Generating the table instead of hand-transcribing it keeps the three sides of the data
triangle identical: source log -> evidence file -> README claim. The summary lines below
the table are the aggregate figures the README quotes in prose.

    python tools/make_steps_table.py --metrics evidence/training-metrics.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# tqdm's `s/it` is a running average and drops frames; verl's own `perf/time_per_step`
# is the per-step wall time and is emitted on every step line.
COLUMNS = [
    ("step", "Step", lambda v: str(v)),
    ("perf/time_per_step", "s/step", lambda v: f"{v:.2f}"),
    ("global_seqlen/mean", "`global_seqlen/mean`", lambda v: f"{v:,.0f}".replace(",", " ")),
    ("global_seqlen/minmax_diff", "rank imbalance", lambda v: f"{v:,.0f}".replace(",", " ")),
    ("actor/entropy", "`actor/entropy`", lambda v: f"{v:.4f}"),
    ("critic/score/mean", "`critic/score/mean`", lambda v: f"{v:.4f}"),
    ("actor/kl_loss", "`actor/kl_loss`", lambda v: f"{v:.4f}"),
    ("actor/grad_norm", "`actor/grad_norm`", lambda v: f"{v:.4f}"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, type=Path)
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.metrics.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    print("| " + " | ".join(header for _, header, _ in COLUMNS) + " |")
    print("|" + "|".join(["---"] * len(COLUMNS)) + "|")
    for row in rows:
        cells = [fmt(row[key]) if key in row else "—" for key, _, fmt in COLUMNS]
        print("| " + " | ".join(cells) + " |")

    print()
    print(f"STEPS={len(rows)}")

    seconds = [row["perf/time_per_step"] for row in rows if "perf/time_per_step" in row]
    if seconds:
        mean = sum(seconds) / len(seconds)
        print(f"SECONDS_PER_STEP_MEAN={mean:.2f}")
        print(f"SECONDS_PER_STEP_MIN={min(seconds):.2f}")
        print(f"SECONDS_PER_STEP_MAX={max(seconds):.2f}")
        print(f"SECONDS_PER_STEP_SPREAD_PCT={(max(seconds) - min(seconds)) / mean * 100:.2f}")

        # Step 14 also runs the final validation pass, so quote the steady state separately.
        steady = [
            row["perf/time_per_step"]
            for row in rows
            if "perf/time_per_step" in row and row["step"] != max(r["step"] for r in rows)
        ]
        if steady:
            steady_mean = sum(steady) / len(steady)
            print(f"STEADY_MEAN={steady_mean:.2f}")
            print(f"STEADY_MIN={min(steady):.2f}")
            print(f"STEADY_MAX={max(steady):.2f}")
            print(
                "STEADY_SPREAD_PCT="
                f"{(max(steady) - min(steady)) / steady_mean * 100:.2f}"
            )

    imbalance = [
        row["global_seqlen/minmax_diff"] / row["global_seqlen/mean"]
        for row in rows
        if "global_seqlen/minmax_diff" in row and row.get("global_seqlen/mean")
    ]
    if imbalance:
        print(f"RANK_IMBALANCE_MAX_PCT={max(imbalance) * 100:.2f}")

    for key in ("perf/max_memory_reserved_gb", "perf/max_memory_allocated_gb", "perf/mfu/actor"):
        values = [row[key] for row in rows if key in row]
        if values:
            print(f"{key}=min {min(values):.4f} max {max(values):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
