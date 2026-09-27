#!/usr/bin/env python3
"""Project and parse `python -m sglang.bench_serving` output.

The parser is vendor-neutral: the same bench_serving client prints the same
result block on ROCm and CUDA builds of SGLang.

    python tools/bench_log.py project RAW.log -o evidence/raw/NAME.txt
    python tools/bench_log.py parse evidence/raw/NAME.txt

`project` keeps the workload arguments and the "Serving Benchmark Result"
block of every run in a log and drops everything else (model paths, dataset
paths, hosts, warnings). It fails closed when a kept line still looks like a
filesystem path, an IPv4 address other than 0.0.0.0, or a user@host string.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KEPT_ARGS = (
    "dataset_name",
    "num_prompts",
    "random_input_len",
    "random_output_len",
    "random_range_ratio",
    "max_concurrency",
    "request_rate",
    "warmup_requests",
    "flush_cache",
    "seed",
    "tokenize_prompt",
    "pd_separated",
    "fake_prefill",
)
BLOCK_START = "============ Serving Benchmark Result ============"
BLOCK_END = "=================================================="
ARGS_LINE = re.compile(r"^(?:benchmark_args=)?Namespace\((?P<body>.*)\)\s*$")
PRIVATE_SHAPES = (
    re.compile(r"(?<![\w.:])/[A-Za-z_][\w.-]*/"),  # any absolute POSIX path with at least one directory
    re.compile(r"\b[A-Za-z]:[\\/]"),  # Windows drive path
    re.compile(r"\\\\[\w.-]+\\"),  # UNC path
    re.compile(r"\b(?!0\.0\.0\.0\b)(?:\d{1,3}\.){3}\d{1,3}\b"),  # IPv4 other than 0.0.0.0
    re.compile(r"\b[0-9a-f]{0,4}(?::[0-9a-f]{0,4}){2,7}\b", re.I),  # IPv6
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\b"),  # user@host or e-mail
)

METRICS = {
    "Max request concurrency": "max_request_concurrency",
    "Successful requests": "successful_requests",
    "Benchmark duration (s)": "duration_s",
    "Total input tokens": "total_input_tokens",
    "Total generated tokens": "total_generated_tokens",
    "Request throughput (req/s)": "request_throughput",
    "Input token throughput (tok/s)": "input_tok_s",
    "Output token throughput (tok/s)": "output_tok_s",
    "Concurrency": "observed_concurrency",
    "Mean E2E Latency (ms)": "mean_e2e_ms",
    "Mean TTFT (ms)": "mean_ttft_ms",
    "Median TTFT (ms)": "median_ttft_ms",
    "P99 TTFT (ms)": "p99_ttft_ms",
    "Mean TPOT (ms)": "mean_tpot_ms",
    "Median TPOT (ms)": "median_tpot_ms",
    "P99 TPOT (ms)": "p99_tpot_ms",
}


class ProjectionError(ValueError):
    pass


def _parse_namespace(body: str) -> dict[str, str]:
    found = {}
    for key in KEPT_ARGS:
        m = re.search(rf"(?:^|, ){key}=('[^']*'|[^,]*)", body)
        if m:
            found[key] = m.group(1).strip("'")
    return found


def project(text: str) -> str:
    """Return the public projection of one raw bench_serving log."""
    lines = text.splitlines()
    runs, pending_args, i = [], None, 0
    while i < len(lines):
        line = lines[i]
        m = ARGS_LINE.match(line)
        if m:
            pending_args = _parse_namespace(m.group("body"))
        elif line.strip() == BLOCK_START:
            block = [BLOCK_START]
            i += 1
            while i < len(lines) and lines[i].strip() != BLOCK_END:
                block.append(lines[i].rstrip())
                i += 1
            if i == len(lines):
                raise ProjectionError("result block is not terminated")
            block.append(BLOCK_END)
            if not pending_args:
                raise ProjectionError("result block has no preceding Namespace(...) arguments")
            runs.append((pending_args, block))
            pending_args = None
        i += 1
    if not runs:
        raise ProjectionError("no Serving Benchmark Result block found")
    out = []
    for args, block in runs:
        out.append("# args: " + " ".join(f"{k}={v}" for k, v in sorted(args.items())))
        out.extend(block)
        out.append("")
    projected = "\n".join(out)
    for number, kept in enumerate(projected.splitlines(), 1):
        for shape in PRIVATE_SHAPES:
            if shape.search(kept):
                raise ProjectionError(f"private-looking content kept on line {number}: {kept!r}")
    return projected


def _number(value: str):
    value = value.strip()
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse(text: str) -> list[dict]:
    """Parse a projected (or raw) log into one dict per run."""
    runs, current = [], None
    for line in text.splitlines():
        if line.startswith("# args: "):
            current = {"args": {}, "metrics": {}}
            for pair in line[len("# args: "):].split():
                key, _, value = pair.partition("=")
                current["args"][key] = _number(value)
            continue
        if current is None:
            continue
        if line.strip() == BLOCK_END:
            runs.append(current)
            current = None
            continue
        label, sep, value = line.partition(":")
        if sep and label.strip() in METRICS:
            current["metrics"][METRICS[label.strip()]] = _number(value)
    if not runs:
        raise ValueError("no parsed runs")
    return runs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("project", help="keep workload args and result blocks only")
    p1.add_argument("raw", type=Path)
    p1.add_argument("-o", "--output", type=Path, required=True)
    p2 = sub.add_parser("parse", help="print parsed runs as JSON")
    p2.add_argument("projected", type=Path, nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "project":
        text = args.raw.read_text(encoding="utf-8", errors="replace")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(project(text), encoding="utf-8", newline="\n")
        print(f"wrote {args.output}")
        return 0
    runs = []
    for path in args.projected:
        for run in parse(path.read_text(encoding="utf-8")):
            run["source"] = path.name
            runs.append(run)
    json.dump(runs, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
