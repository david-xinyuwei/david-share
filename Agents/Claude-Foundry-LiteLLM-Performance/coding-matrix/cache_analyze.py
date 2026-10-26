"""Summarise cache_results.jsonl: tokens written / read per turn, cost per conversation, cold vs warm latency.

Only the last attempt of each request counts (a 429 attempt is resent and kept apart).
Numbers are means over repetitions; latency uses medians.
"""
import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from pricing import PRICES


def read_rows(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    last = {}
    for row in rows:  # keep the final attempt of every (model, scenario, repetition, nonce, turn)
        last[(row["model"], row["scenario"], row["repetition"], row["nonce"], row["turn"])] = row
    throttled = sum(1 for r in rows if r.get("http_status") == 429)
    return list(last.values()), rows, throttled


def tokens(row):
    u = row.get("usage") or {}
    created = u.get("cache_creation") or {}
    return {"input": u.get("input_tokens") or 0, "write": u.get("cache_creation_input_tokens") or 0,
            "write_1h": created.get("ephemeral_1h_input_tokens") or 0,
            "read": u.get("cache_read_input_tokens") or 0, "output": u.get("output_tokens") or 0}


def no_cache_cost(model, t):
    """What the same request would cost with nothing cached: every prompt token at the input price."""
    price = PRICES[model]
    return ((t["input"] + t["write"] + t["read"]) * price["input"] + t["output"] * price["output"]) / 1e6


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def summarize(rows):
    turns = defaultdict(list)
    for row in rows:
        turns[(row["model"], row["scenario"], row["turn"])].append(row)
    per_turn = []
    for (model, scenario, turn), group in sorted(turns.items()):
        ok = [r for r in group if r.get("http_status") == 200]
        toks = [tokens(r) for r in ok]
        mean = {k: (sum(t[k] for t in toks) / len(toks) if toks else None) for k in
                ("input", "write", "write_1h", "read", "output")}
        prompt = (mean["input"] + mean["write"] + mean["read"]) if toks else None
        per_turn.append({
            "model": model, "scenario": scenario, "turn": turn, "n": len(group), "ok": len(ok),
            "statuses": sorted({f"{r.get('status')}/{r.get('http_status')}" for r in group}),
            "errors": sorted({json.dumps(r.get("error_body"))[:300] for r in group if r.get("http_status") not in (200, None)}),
            "effort": group[0].get("effort"), "message_effort": group[0].get("message_effort"), "mode": group[0].get("mode"),
            "tokens_mean": mean, "prompt_tokens_mean": prompt,
            "read_share": (mean["read"] / prompt) if prompt else None,
            "cost_mean_usd": (sum(r.get("cost_usd") or 0 for r in ok) / len(ok)) if ok else None,
            "no_cache_cost_mean_usd": (sum(no_cache_cost(model, t) for t in toks) / len(toks)) if toks else None,
            "first_event_p50_s": median([(r.get("timing") or {}).get("first_event") for r in ok]),
            "first_text_p50_s": median([(r.get("timing") or {}).get("first_text") for r in ok]),
        })
    conversations = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get("http_status") == 200:
            conversations[(row["model"], row["scenario"])][row["repetition"]].append(row)
    sessions = []
    for (model, scenario), reps in sorted(conversations.items()):
        costs = [sum(r.get("cost_usd") or 0 for r in rs) for rs in reps.values()]
        plain = [sum(no_cache_cost(model, tokens(r)) for r in rs) for rs in reps.values()]
        sessions.append({"model": model, "scenario": scenario, "repetitions": len(reps),
                         "requests": statistics.mean(len(rs) for rs in reps.values()),
                         "cost_mean_usd": statistics.mean(costs), "same_tokens_no_cache_usd": statistics.mean(plain),
                         "saving_vs_no_cache": 1 - statistics.mean(costs) / statistics.mean(plain) if plain and statistics.mean(plain) else None})
    pairs = []
    by_pair = defaultdict(dict)
    for row in rows:
        if row["scenario"].startswith("ttft_") and row.get("http_status") == 200:
            _, side, size = row["scenario"].split("_")
            by_pair[(row["model"], size, row["repetition"], row["nonce"])][side] = row
    grouped = defaultdict(lambda: {"cold": [], "warm": []})
    for (model, size, _, _), sides in by_pair.items():
        if len(sides) == 2:  # a pair counts only when both requests succeeded
            grouped[(model, size)]["cold"].append(sides["cold"])
            grouped[(model, size)]["warm"].append(sides["warm"])
    for (model, scenario), g in sorted(grouped.items()):
        def stat(rs, key):
            return median([(r.get("timing") or {}).get(key) for r in rs])
        pairs.append({"model": model, "scenario": scenario, "pairs": len(g["cold"]),
                      "prompt_tokens": statistics.mean(sum(tokens(r)[k] for k in ("input", "write", "read")) for r in g["cold"]),
                      "cold_read_mean": statistics.mean(tokens(r)["read"] for r in g["cold"]),
                      "warm_read_mean": statistics.mean(tokens(r)["read"] for r in g["warm"]),
                      "cold_first_event_p50_s": stat(g["cold"], "first_event"),
                      "warm_first_event_p50_s": stat(g["warm"], "first_event"),
                      "cold_first_text_p50_s": stat(g["cold"], "first_text"),
                      "warm_first_text_p50_s": stat(g["warm"], "first_text"),
                      "cold_cost_mean_usd": statistics.mean(r.get("cost_usd") or 0 for r in g["cold"]),
                      "warm_cost_mean_usd": statistics.mean(r.get("cost_usd") or 0 for r in g["warm"])})
    return per_turn, sessions, pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--check", action="store_true", help="recompute and compare with cache_facts.json; write nothing")
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    rows, all_rows, throttled = read_rows(run_dir / "cache_results.jsonl")
    per_turn, sessions, pairs = summarize(rows)
    facts = {"run": run_dir.name, "requests_sent": len(all_rows), "throttled_attempts": throttled,
             "cost_total_usd": sum(r.get("cost_usd") or 0 for r in all_rows),
             "context": json.loads((run_dir / "context.json").read_text(encoding="utf-8")),
             "per_turn": per_turn, "sessions": sessions, "ttft_pairs": pairs}
    if args.check:
        saved = json.loads((run_dir / "cache_facts.json").read_text(encoding="utf-8"))
        if saved != json.loads(json.dumps(facts)):
            sys.exit(f"cache_facts.json in {run_dir} differs from a fresh analysis of cache_results.jsonl")
        print(json.dumps({"status": "PASS", "run": facts["run"], "requests_sent": facts["requests_sent"]}))
        return
    (run_dir / "cache_facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8", newline="\n")
    for t in per_turn:
        m = t["tokens_mean"]
        print(f"{t['model'][7:]:10s} {t['scenario']:24s} t{t['turn']} ok={t['ok']}/{t['n']} "
              f"in={m['input'] or 0:7.0f} write={m['write'] or 0:7.0f} read={m['read'] or 0:7.0f} "
              f"out={m['output'] or 0:6.0f} read%={100 * (t['read_share'] or 0):5.1f} "
              f"$={t['cost_mean_usd'] or 0:.4f} {'' if t['ok'] == t['n'] else t['statuses']} {t['errors'] or ''}")
    for s in sessions:
        print(f"SESSION {s['model'][7:]:10s} {s['scenario']:24s} ${s['cost_mean_usd']:.4f} vs ${s['same_tokens_no_cache_usd']:.4f} "
              f"saving={100 * (s['saving_vs_no_cache'] or 0):.0f}%")
    for p in pairs:
        print(f"PAIR {p['model'][7:]:10s} {p['scenario']:18s} n={p['pairs']} prompt={p['prompt_tokens']:.0f} "
              f"first_event {p['cold_first_event_p50_s']}->{p['warm_first_event_p50_s']} "
              f"first_text {p['cold_first_text_p50_s']}->{p['warm_first_text_p50_s']}")


if __name__ == "__main__":
    main()
