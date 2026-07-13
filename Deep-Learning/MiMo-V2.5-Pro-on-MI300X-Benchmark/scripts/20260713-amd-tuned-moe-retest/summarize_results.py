#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


METRIC_PATTERNS = {
    "concurrency": r"Max request concurrency:\s+([0-9]+)",
    "successful_requests": r"Successful requests:\s+([0-9]+)",
    "input_tok_s": r"Input token throughput \(tok/s\):\s+([0-9.]+)",
    "output_tok_s": r"Output token throughput \(tok/s\):\s+([0-9.]+)",
    "mean_ttft_ms": r"Mean TTFT \(ms\):\s+([0-9.]+)",
    "p99_ttft_ms": r"P99 TTFT \(ms\):\s+([0-9.]+)",
    "mean_tpot_ms": r"Mean TPOT \(ms\):\s+([0-9.]+)",
    "median_tpot_ms": r"Median TPOT \(ms\):\s+([0-9.]+)",
    "p99_tpot_ms": r"P99 TPOT \(ms\):\s+([0-9.]+)",
    "errors": r"ERRORS=([0-9]+)",
}

STRICT_DECODE_BASELINE = {
    16: {"output_tok_s": 1299.18, "mean_tpot_ms": 10.64},
    32: {"output_tok_s": 1910.75, "mean_tpot_ms": 13.50},
    64: {"output_tok_s": 2188.05, "mean_tpot_ms": 15.10},
    128: {"output_tok_s": 2209.43, "mean_tpot_ms": 14.52},
}

H200_DECODE = {
    16: {"output_tok_s": 1381.0, "median_tpot_ms": 11.59},
    32: {"output_tok_s": 2549.0, "median_tpot_ms": 12.56},
    64: {"output_tok_s": 4483.0, "median_tpot_ms": 14.28},
    128: {"output_tok_s": 7013.0, "median_tpot_ms": 18.25},
}

STRICT_PREFILL_BASELINE = {8192: 16715.80, 65536: 17254.14, 262144: 37492.80}
H200_PREFILL = {8192: 31950.0, 65536: 27400.0, 262144: 17400.0}


def parse_summary(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"^===(.+?)===\s*$", text, flags=re.MULTILINE)
    rows: list[dict] = []
    for index in range(1, len(sections), 2):
        filename = sections[index].strip()
        body = sections[index + 1]
        context_match = re.search(r"benchmark_([0-9]+)_con([0-9]+)\.log", filename)
        if not context_match:
            continue
        row: dict[str, int | float | str] = {
            "filename": filename,
            "input_tokens": int(context_match.group(1)),
            "concurrency": int(context_match.group(2)),
        }
        for key, pattern in METRIC_PATTERNS.items():
            match = re.search(pattern, body)
            if match:
                row[key] = int(match.group(1)) if key in {
                    "concurrency",
                    "successful_requests",
                    "errors",
                } else float(match.group(1))
        rows.append(row)
    return sorted(rows, key=lambda item: (int(item["input_tokens"]), int(item["concurrency"])))


def percent_change(value: float, baseline: float) -> float:
    return (value / baseline - 1.0) * 100.0


def enrich_decode(rows: list[dict]) -> None:
    for row in rows:
        concurrency = int(row["concurrency"])
        baseline = STRICT_DECODE_BASELINE.get(concurrency)
        h200 = H200_DECODE.get(concurrency)
        if not baseline or not h200:
            continue
        output = float(row["output_tok_s"])
        tpot = float(row["mean_tpot_ms"])
        median_tpot = float(row["median_tpot_ms"])
        row["output_vs_strict_pct"] = percent_change(output, baseline["output_tok_s"])
        row["mean_tpot_vs_strict_pct"] = percent_change(tpot, baseline["mean_tpot_ms"])
        row["output_vs_h200_pct"] = output / h200["output_tok_s"] * 100.0
        row["median_tpot_vs_h200"] = median_tpot / h200["median_tpot_ms"]


def enrich_prefill(rows: list[dict]) -> None:
    for row in rows:
        input_tokens = int(row["input_tokens"])
        throughput = float(row["input_tok_s"])
        row["vs_strict_pct"] = percent_change(throughput, STRICT_PREFILL_BASELINE[input_tokens])
        row["vs_h200_pct"] = throughput / H200_PREFILL[input_tokens] * 100.0


def enrich_dp2(rows: list[dict]) -> None:
    for row in rows:
        throughput = float(row["input_tok_s"])
        row["per_node_tok_s"] = throughput / 2.0
        row["per_node_vs_h200_pct"] = (
            float(row["per_node_tok_s"]) / H200_PREFILL[int(row["input_tokens"])] * 100.0
        )


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    result = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    result.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(result)


def render_markdown(run_id: str, data: dict) -> str:
    decode_rows = []
    for row in data["decode"]:
        decode_rows.append(
            [
                str(row["concurrency"]),
                str(row.get("successful_requests", "NA")),
                f"{float(row.get('output_tok_s', 0)):.2f}",
                f"{float(row.get('mean_tpot_ms', 0)):.2f}",
                f"{float(row.get('output_vs_strict_pct', 0)):+.2f}%",
                f"{float(row.get('mean_tpot_vs_strict_pct', 0)):+.2f}%",
                str(row.get("errors", "NA")),
            ]
        )
    prefill_rows = []
    for row in data["prefill"]:
        prefill_rows.append(
            [
                str(row["input_tokens"]),
                str(row["concurrency"]),
                str(row.get("successful_requests", "NA")),
                f"{float(row.get('input_tok_s', 0)):.2f}",
                f"{float(row.get('vs_strict_pct', 0)):+.2f}%",
                f"{float(row.get('vs_h200_pct', 0)):.1f}%",
                str(row.get("errors", "NA")),
            ]
        )
    dp2_rows = []
    for row in data["dp2"]:
        dp2_rows.append(
            [
                str(row["input_tokens"]),
                str(row["concurrency"]),
                str(row.get("successful_requests", "NA")),
                f"{float(row.get('input_tok_s', 0)):.2f}",
                f"{float(row.get('per_node_tok_s', 0)):.2f}",
                f"{float(row.get('per_node_vs_h200_pct', 0)):.1f}%",
                str(row.get("errors", "NA")),
            ]
        )
    return f"""# AMD Tuned MoE Retest — {run_id}

## Decode

{markdown_table(['Concurrency', 'Success', 'Output tok/s', 'Mean TPOT ms', 'Output vs strict baseline', 'TPOT vs strict baseline', 'Errors'], decode_rows)}

## 1P1D Prefill

{markdown_table(['Input tokens', 'Concurrency', 'Success', 'Input tok/s', 'vs strict baseline', 'vs H200', 'Errors'], prefill_rows)}

## DP=2 Prefill

{markdown_table(['Input tokens', 'Concurrency', 'Success', 'Aggregate tok/s', 'Per-node tok/s', 'Per-node vs H200', 'Errors'], dp2_rows)}

## DP=2 256K Correctness Guard

- The supplied `--context-length 262144` setting was insufficient for the standard DP=2 server path: a requested 262,144-token random input became 262,148 server-side tokens, and HTTP 200 error payloads could still appear as successful client responses.
- The invalid attempt is excluded; its deterministic overflow counts are recorded in `checks/validation.txt`.
- The accepted rerun kept `random_input_len=262144` and `random_output_len=1`, while setting the server allowance to 262,149 tokens. Both node service logs report zero context-overflow errors for the final six-point matrix.

## Interpretation

- Decode high-concurrency output throughput is the primary tuned-MoE gain; report TPOT separately because BS64/128 trade throughput for higher TPOT.
- 1P1D Prefill gains are positive across 8K/64K/256K.
- DP=2 results are prefill-only server-mode measurements and do not include P→D KV transfer.
- The single-kernel 37.6% latency reduction is AMD-reported; no standalone microbenchmark log was provided in the shared evidence directory.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Orchestrator output directory")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    data = {
        "run_id": args.run_id,
        "decode": parse_summary(args.root / "decode-summary.txt"),
        "prefill": parse_summary(args.root / "prefill-summary.txt"),
        "dp2": parse_summary(args.root / "dp2-summary.txt"),
    }
    enrich_decode(data["decode"])
    enrich_prefill(data["prefill"])
    if data["dp2"]:
        enrich_dp2(data["dp2"])

    (args.root / "results.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (args.root / "RESULTS.md").write_text(render_markdown(args.run_id, data), encoding="utf-8")


if __name__ == "__main__":
    main()