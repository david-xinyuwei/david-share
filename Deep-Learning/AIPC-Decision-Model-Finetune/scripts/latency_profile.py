#!/usr/bin/env python3
"""Latency and input-token medians per block of consecutive requests in an engine rows.jsonl, to spot windows where
other work on the laptop slowed the server down.  python scripts/latency_profile.py <rows.jsonl> [--block 20]"""
import argparse
import json
import statistics
import sys
from pathlib import Path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("rows")
    ap.add_argument("--block", type=int, default=20)
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.rows).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if "latency_ms" in r]
    print(f"n={len(rows)} p50={statistics.median(r['latency_ms'] for r in rows):.0f} ms")
    for i in range(0, len(rows), a.block):
        b = rows[i:i + a.block]
        tok = [r["input_tokens"] for r in b if r.get("input_tokens")]
        print(f"{i:4d}-{i + len(b) - 1:4d}  p50 {statistics.median(r['latency_ms'] for r in b):6.0f} ms"
              f"  min {min(r['latency_ms'] for r in b):6.0f}  tokens p50 {statistics.median(tok) if tok else '—'}")


if __name__ == "__main__":
    main()
