"""Interleaved A/B latency test: two direct deployments, the same prompt, back to back.

The main matrix runs arm after arm, so each arm owns a different half hour. On
2026-09-26 the same gpt-5.6-luna deployment measured 28% faster TTFT than on
2026-09-09, so time of day is a real confounder: a sequential run cannot tell a
faster model from a quieter half hour. Here every measured request to A has a
partner request to B on the same prompt, sent immediately before or after it,
and the side that goes first alternates, so drift and ordering cancel inside
each pair.

Requests are built by harness.run_one, so payload, streaming, TTFT definition
and output cap are identical to the matrix run.

    python scripts/paired_direct.py --a gpt-6-luna --b gpt-5.6-luna \
        --efforts none,low,high --repeats 5 --warmup 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def p50(xs):
    return statistics.median(xs) if xs else None


def sign_test_p(wins: int, n: int) -> float:
    """Two-sided exact binomial sign test against p=0.5."""
    if n == 0:
        return 1.0
    k = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def cluster_boot_ratio(by_prompt: dict, metric: str, B: int = 4000, seed: int = 7):
    """95% CI of P50(A)/P50(B), resampling prompts (not requests) with replacement."""
    rng = random.Random(seed)
    prompts = sorted(by_prompt)
    if not prompts:
        return None, None
    out = []
    for _ in range(B):
        a, b = [], []
        for q in rng.choices(prompts, k=len(prompts)):
            for pair in by_prompt[q]:
                a.append(pair["a"][metric])
                b.append(pair["b"][metric])
        out.append(p50(a) / p50(b))
    out.sort()
    return out[int(0.025 * B)], out[int(0.975 * B)]


def summarize(records: list[dict], metric: str = "ttft_ms") -> dict:
    """Per effort: both sides' P50/P90, per-pair and per-prompt win counts, order split, CI of the P50 ratio."""
    pairs = defaultdict(dict)
    for r in records:
        if r.get("warmup") or r.get("error") or r.get(metric) is None:
            continue
        pairs[(r["effort"], r["pair_id"])][r["side"]] = r
    by_effort = defaultdict(lambda: defaultdict(list))
    for (effort, _pid), sides in pairs.items():
        if "a" in sides and "b" in sides:
            by_effort[effort][sides["a"]["question_id"]].append(sides)
    result = {}
    for effort, by_prompt in by_effort.items():
        flat = [p for ps in by_prompt.values() for p in ps]
        a = sorted(p["a"][metric] for p in flat)
        b = sorted(p["b"][metric] for p in flat)
        diffs = [p["a"][metric] - p["b"][metric] for p in flat]
        pair_wins = sum(1 for d in diffs if d < 0)
        prompt_d = {q: p50([p["a"][metric] - p["b"][metric] for p in ps]) for q, ps in by_prompt.items()}
        prompt_wins = sum(1 for d in prompt_d.values() if d < 0)
        order = {}
        for first in ("a", "b"):
            sub = [p["a"][metric] - p["b"][metric] for p in flat if p["a"]["first"] == first]
            order[f"{first}_first"] = {"n": len(sub), "median_diff_ms": p50(sub),
                                       "a_faster": sum(1 for d in sub if d < 0)}
        lo, hi = cluster_boot_ratio(by_prompt, metric)
        q90 = lambda xs: statistics.quantiles(xs, n=10, method="inclusive")[8] if len(xs) >= 2 else None
        result[effort] = {
            "pairs": len(flat), "prompts": len(by_prompt),
            "a_p50": p50(a), "b_p50": p50(b), "a_p90": q90(a), "b_p90": q90(b),
            "p50_ratio": p50(a) / p50(b), "p50_ratio_ci95": [lo, hi],
            "median_pair_diff_ms": p50(diffs),
            "a_faster_pairs": pair_wins, "pair_sign_p": sign_test_p(pair_wins, len(diffs)),
            "a_faster_prompts": prompt_wins, "prompt_sign_p": sign_test_p(prompt_wins, len(prompt_d)),
            "by_order": order,
        }
    return result


def main() -> int:
    import harness

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--a", required=True, help="deployment A (the candidate)")
    ap.add_argument("--b", required=True, help="deployment B (the baseline)")
    ap.add_argument("--efforts", default="none", help="comma-separated; '-' = do not send")
    ap.add_argument("--dataset", default=str(next(iter(sorted((ROOT / "datasets").glob("*_scenarios.jsonl"))),
                                                  ROOT / "datasets" / "assistant_scenarios.jsonl")),
                    help="default: the single datasets/*_scenarios.jsonl (the 17 assistant prompts)")
    ap.add_argument("--repeats", type=int, default=5, help="measured pairs per prompt per effort")
    ap.add_argument("--warmup", type=int, default=1, help="warm-up pairs per prompt per effort")
    ap.add_argument("--region", required=True)
    ap.add_argument("--client-location", default="unknown", dest="client_location")
    ap.add_argument("--allow-remote-client", action="store_true", dest="allow_remote_client")
    args = ap.parse_args()

    dataset = harness.load_jsonl(Path(args.dataset))
    efforts = [None if e.strip() == "-" else e.strip() for e in args.efforts.split(",") if e.strip()]
    built = harness.build_client()
    # the working harness returns (client, endpoint); the published copy returns the client only
    client, endpoint = built if isinstance(built, tuple) else (built, os.environ.get("AZURE_OPENAI_ENDPOINT", ""))
    host = urlparse(endpoint).netloc or endpoint
    rtt = harness.measure_rtt(host)
    print(f"endpoint={host} rtt={rtt}ms client={args.client_location}")
    remote_ms = getattr(harness, "REMOTE_CLIENT_RTT_MS", 50)
    if rtt is not None and rtt >= remote_ms and not args.allow_remote_client:
        raise SystemExit(f"Refusing to measure at {rtt}ms TCP connect; run from a same-region VM.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = harness.OUTPUT_DIR / f"paired_{args.a}_vs_{args.b}_{stamp}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    total = len(efforts) * len(dataset) * (args.repeats + args.warmup) * 2
    print(f"{len(efforts)} efforts x {len(dataset)} prompts x {args.repeats}+{args.warmup} pairs x 2 = {total} requests")
    print(f"writing {out}")

    records, done, pair_id = [], 0, 0
    with out.open("w", encoding="utf-8") as fh:
        for effort in efforts:
            # Rounds outermost: each prompt's repeats are spread across the whole
            # effort block instead of bunched into one minute.
            for rnd in range(args.warmup + args.repeats):
                warm = rnd < args.warmup
                for idx, item in enumerate(dataset):
                    pair_id += 1
                    first = "a" if (rnd + idx) % 2 == 0 else "b"
                    order = [("a", args.a), ("b", args.b)] if first == "a" else [("b", args.b), ("a", args.a)]
                    cap = int(item.get("max_output_tokens", 512)) + harness.REASONING_HEADROOM_UNIFORM
                    for side, dep in order:
                        m = harness.run_one(client, dep, item, cap, effort)
                        done += 1
                        rec = {"run_id": stamp, "pair_id": pair_id, "round": rnd, "warmup": warm,
                               "effort": effort or "-", "side": side, "first": first, "deployment": dep,
                               "question_id": item["id"], "scenario": item.get("scenario"),
                               "region": args.region, "client_location": args.client_location,
                               "endpoint_host": host, "network_rtt_ms": rtt,
                               "started_at_utc": datetime.now(timezone.utc).isoformat()}
                        rec.update({k: m[k] for k in ("ttft_ms", "e2e_ms", "decode_ms", "prompt_tokens",
                                                       "completion_tokens", "reasoning_tokens", "cached_tokens",
                                                       "status", "truncated", "model_actually_served", "error")})
                        rec["response_sha256"] = hashlib.sha256(
                            (m.get("response_text") or "").encode("utf-8")).hexdigest()
                        records.append(rec)
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                        tag = "WU" if warm else "  "
                        print(f"{tag} [{done}/{total}] {effort or '-':6} {item['id']:6} {side}:{dep:16} "
                              f"TTFT={m['ttft_ms'] or 0:7.0f}ms e2e={m['e2e_ms']:7.0f}ms"
                              + (f"  ERR {m['error'][:60]}" if m["error"] else ""))

    errors = sum(1 for r in records if r["error"])
    summary = {"run_id": stamp, "a": args.a, "b": args.b, "requests": len(records), "errors": errors,
               "network_rtt_ms": rtt, "ttft": summarize(records, "ttft_ms"), "e2e": summarize(records, "e2e_ms")}
    spath = out.with_suffix(".summary.json")
    spath.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nerrors={errors}  summary → {spath}")
    for metric in ("ttft", "e2e"):
        for effort, s in summary[metric].items():
            lo, hi = s["p50_ratio_ci95"]
            print(f"{metric:4} {effort:6} P50 A={s['a_p50']:6.0f} B={s['b_p50']:6.0f} ratio={s['p50_ratio']:.2f} "
                  f"[{lo:.2f},{hi:.2f}]  A faster pairs {s['a_faster_pairs']}/{s['pairs']} (p={s['pair_sign_p']:.2g})  "
                  f"prompts {s['a_faster_prompts']}/{s['prompts']} (p={s['prompt_sign_p']:.2g})")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
