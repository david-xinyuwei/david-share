"""Build (or check) outputs/gpt61-sol-20261003/README.md from the committed evidence in that folder.

Every number in the report is computed here from the published files; nothing is typed in by hand.
The 2026-09-26 GPT-6 Luna run is read only for the context table and is labelled as a different day.

    python scripts/build_gpt61_sol_report.py            # write README.md
    python scripts/build_gpt61_sol_report.py --check    # fail if README.md is stale or evidence is incomplete
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "outputs" / "gpt61-sol-20261003"
RUN = "20261003_114811"
PAIRED = "paired_gpt-6.1-sol_vs_gpt-6-luna_20261003_115838"
LUNA_DIR = ROOT / "outputs" / "gpt6-luna-20260926"
LUNA_RUN = "20260926_131212"
WITHHELD = {"PA01", "PA03"}
PLACEHOLDER_HOST = "YOUR-ENDPOINT.cognitiveservices.azure.com"
MODEL = "gpt-6.1-sol"
EFFORTS = ("low", "medium", "high")
ARM_ORDER = tuple(f"{MODEL}@{e}" for e in EFFORTS)
# file name, short label used in the probe table
PROBE_FILES = (("exact_answer_probe.json", "three efforts, 40k cap"),
               ("exact_answer_probe_astra_high.json", "GPT-6 Astra top-up, 40k cap"),
               ("exact_answer_probe_100k.json", "cap raised to 100k"))
NAMES = {"gpt-6.1-sol": "GPT-6.1 Sol", "gpt-6-luna": "GPT-6 Luna", "gpt-6-astra": "GPT-6 Astra"}
FILES = (("direct_{run}.metrics.jsonl", "every matrix request, numbers only"),
         ("raw_fulltext/direct_{run}.jsonl", "every matrix request with answer text"),
         ("{paired}.jsonl", "every interleaved A/B request"),
         ("{paired}.summary.json", "A/B statistics as printed above"),
         ("quality_opus46_{run}.jsonl", "judge scores (Claude Opus 4.6)"),
         ("exact_answer_probe*.json", "exact-answer probe records, one file per setting"),
         ("prompt_cache_check.metrics.jsonl", "prompt-cache check, every request"),
         ("prompt_cache_check.summary.json", "prompt-cache check, per-deployment summary"),
         ("deployment_verification.json", "deployments read back from Azure"),
         ("pricing.json", "list prices used for cost_usd"),
         ("models.json", "registry entries for the deployments in this folder"),
         ("provenance.json", "client, executed-source hashes, redaction record"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pct(xs: list[float], q: int) -> float:
    """Inclusive linear-interpolation percentile."""
    return statistics.quantiles(xs, n=100, method="inclusive")[q - 1]


def measured(records: list[dict]) -> list[dict]:
    return [r for r in records if not r.get("warmup") and not r.get("error")
            and r.get("status") == "completed" and not r.get("truncated")]


def arm_stats(records: list[dict]) -> dict[str, dict]:
    by = defaultdict(list)
    for r in measured(records):
        by[r["arm"]].append(r)
    out = {}
    for arm, rs in by.items():
        t = [r["ttft_ms"] for r in rs]
        e = [r["e2e_ms"] for r in rs]
        out[arm] = {"n": len(rs), "ttft": [statistics.median(t), pct(t, 90), pct(t, 95)],
                    "e2e": [statistics.median(e), pct(e, 90), pct(e, 95)],
                    "out": statistics.mean(r["completion_tokens"] for r in rs),
                    "reason": statistics.mean(r["reasoning_tokens"] for r in rs),
                    "usd_1k": 1000 * statistics.mean(r["cost_usd"] for r in rs)}
    return out


def quality(path: Path) -> dict[tuple, float]:
    rows = load_jsonl(path)
    if any(r.get("error") for r in rows):
        raise ValueError(f"{path.name}: judge errors present")
    return {(r["arm"], r["question_id"]): r["quality_mean"] for r in rows}


def probe_outcome(r: dict, cap: int) -> str:
    """Same classification the private summary used: exact / cutoff / refused / wrong / error."""
    if r.get("exact"):
        return "exact"
    if r.get("error"):
        return "error"
    usage = r.get("usage") or {}
    if r.get("status") == "incomplete" or (not (r.get("text") or "").strip() and usage.get("output", 0) >= cap):
        return "cutoff"  # the whole output budget went to reasoning; no answer was produced
    if "no invoice list" in (r.get("detail") or ""):
        return "refused"
    return "wrong"


def probe_files() -> list[tuple[str, str, dict]]:
    found = []
    for name, label_ in PROBE_FILES:
        path = RUN_DIR / name
        if path.is_file():
            found.append((name, label_, json.loads(path.read_text(encoding="utf-8"))))
    return found


def topup_sentence(probes) -> str:
    """One sentence per top-up file that is present, computed from its records."""
    parts = []
    by_name = {name: data for name, _, data in probes}
    hi = by_name.get(PROBE_FILES[2][0])
    if hi:
        rs = hi["records"]
        cap = int(hi["meta"]["max_output_tokens"])
        n_exact = sum(1 for r in rs if r["exact"])
        parts.append(f"With the cap raised to {cap:,} tokens `high` solved {n_exact}/{len(rs)}, and no run needed more "
                     f"than {max(r['usage']['output'] for r in rs):,} output tokens: the cut-off run was variance, not "
                     f"a budget wall (median ${statistics.median(r['usd'] for r in rs):.2f} per solve).")
    astra = by_name.get(PROBE_FILES[1][0])
    if astra:
        rs = astra["records"]
        parts.append(f"GPT-6 Astra `high` solved {sum(1 for r in rs if r['exact'])}/{len(rs)} at the 40,000 cap, "
                     f"median ${statistics.median(r['usd'] for r in rs):.2f} per solve.")
    return (" " + " ".join(parts)) if parts else ""


def validate(records, paired, q46, summary, probes, cache_rows, cache_summary) -> list[str]:
    problems = []
    if len(records) != 204:
        problems.append(f"expected 204 matrix records, found {len(records)}")
    counts = Counter(r["arm"] for r in measured(records))
    if sorted(counts) != sorted(ARM_ORDER) or set(counts.values()) != {51}:
        problems.append(f"expected 3 arms x 51 measured requests, found {dict(counts)}")
    if len(paired) != 204 or any(r.get("error") for r in paired):
        problems.append("expected 204 error-free interleaved requests")
    if len(q46) != 51 or {a for a, _ in q46} != set(ARM_ORDER):
        problems.append("judge: expected 51 scores over 3 arms")
    if summary["requests"] != 204 or summary["errors"] != 0 or set(summary["ttft"]) != {"low"}:
        problems.append("paired summary does not match the paired records (204 requests at `low`)")
    hosts = {r.get("endpoint_host") for r in records + paired}
    if hosts != {PLACEHOLDER_HOST}:
        problems.append(f"endpoint not redacted: {hosts}")
    if not probes or probes[0][0] != PROBE_FILES[0][0]:
        problems.append("exact_answer_probe.json (the 2026-10-03 three-effort probe) is missing")
    for name, _, data in probes:
        recs = data.get("records") or []
        if not recs or any(not r.get("usage") for r in recs if not r.get("error")):
            problems.append(f"{name}: records incomplete")
        if any(r.get("error") for r in recs):
            problems.append(f"{name}: {sum(1 for r in recs if r.get('error'))} probe request(s) errored")
    per_item = Counter(r["item"] for r in cache_rows if not r.get("error"))
    if len(per_item) != 6 or set(per_item.values()) != {4} or any(r.get("error") for r in cache_rows):
        problems.append(f"prompt-cache check: expected 6 items x 4 requests, found {dict(per_item)}")
    if set(cache_summary["deployments"]) != {MODEL}:
        problems.append("prompt-cache summary is not the gpt-6.1-sol run")
    return problems


def label(arm: str) -> str:
    model, effort = arm.split("@")
    return f"{NAMES.get(model, model)} `{effort}`"


def render() -> str:
    records = load_jsonl(RUN_DIR / f"direct_{RUN}.metrics.jsonl")
    paired = load_jsonl(RUN_DIR / f"{PAIRED}.jsonl")
    summary = json.loads((RUN_DIR / f"{PAIRED}.summary.json").read_text(encoding="utf-8"))
    q46 = quality(RUN_DIR / f"quality_opus46_{RUN}.jsonl")
    probes = probe_files()
    cache_rows = load_jsonl(RUN_DIR / "prompt_cache_check.metrics.jsonl")
    cache_summary = json.loads((RUN_DIR / "prompt_cache_check.summary.json").read_text(encoding="utf-8"))
    problems = validate(records, paired, q46, summary, probes, cache_rows, cache_summary)
    if problems:
        raise ValueError("evidence incomplete:\n  " + "\n  ".join(problems))
    prov = json.loads((RUN_DIR / "provenance.json").read_text(encoding="utf-8"))
    deploy = json.loads((RUN_DIR / "deployment_verification.json").read_text(encoding="utf-8"))["deployments"]
    prices = json.loads((RUN_DIR / "pricing.json").read_text(encoding="utf-8"))["models"]
    judge_rows = load_jsonl(RUN_DIR / f"quality_opus46_{RUN}.jsonl")
    judge_dep = sorted({r["judge_deployment"] for r in judge_rows})
    rubric = sorted({r["rubric_version"] for r in judge_rows})
    S = arm_stats(records)
    m46 = {a: statistics.mean(v for (x, _), v in q46.items() if x == a) for a in ARM_ORDER}
    luna_path = LUNA_DIR / f"direct_{LUNA_RUN}.metrics.jsonl"
    if not luna_path.is_file():
        raise ValueError(f"context run missing: {luna_path}")
    luna = arm_stats(load_jsonl(luna_path))
    luna_q = quality(LUNA_DIR / f"quality_opus46_{LUNA_RUN}.jsonl")
    luna_m46 = {a: statistics.mean(v for (x, _), v in luna_q.items() if x == a)
                for a in (f"gpt-6-luna@{e}" for e in ("none",) + EFFORTS)}
    tl, el = summary["ttft"]["low"], summary["e2e"]["low"]
    lo = S[f"{MODEL}@low"]
    cache = cache_summary["deployments"][MODEL]
    base = next(d for d in probes if d[0] == PROBE_FILES[0][0])[2]
    base_out = {e: Counter(probe_outcome(r, 40_000) for r in base["records"] if r["effort"] == e) for e in EFFORTS}

    L: list[str] = []
    w = L.append
    w("# GPT-6.1 Sol follow-up: where the bigger reasoning model earns its price")
    w("")
    w("2026-10-03 · Sweden Central · the same 17 assistant prompts, VM and resource as the "
      "[2026-09-26 GPT-6 Luna run](../gpt6-luna-20260926/README.md), plus an interleaved A/B against GPT-6 Luna, "
      "an exact-answer probe and a prompt-cache check.")
    w("")
    w("> Generated by [`scripts/build_gpt61_sol_report.py`](../../scripts/build_gpt61_sol_report.py) from the files in "
      "this folder. Do not edit by hand; `--check` fails if this page and the evidence disagree.")
    w("")
    w("## Summary")
    w("")
    w(f"- **On the assistant prompts GPT-6.1 Sol is slower and dearer than GPT-6 Luna, not better.** In {tl['pairs']} "
      f"back-to-back pairs at `low` (order alternated), GPT-6.1 Sol reached the first token in **{tl['a_p50']:.0f} ms "
      f"vs {tl['b_p50']:.0f} ms** for GPT-6 Luna (P50; ratio {tl['p50_ratio']:.2f}, 95% CI "
      f"{tl['p50_ratio_ci95'][0]:.2f}–{tl['p50_ratio_ci95'][1]:.2f}) and finished in {el['a_p50']:.0f} vs "
      f"{el['b_p50']:.0f} ms; it was faster in {tl['a_faster_pairs']}/{tl['pairs']} pairs. At list price its `low` arm "
      f"costs ${lo['usd_1k']:.2f} per 1,000 requests; GPT-6 Luna `none` cost ${luna['gpt-6-luna@none']['usd_1k']:.2f} "
      "on 2026-09-26.")
    lq = [luna_m46[f"gpt-6-luna@{e}"] for e in ("none",) + EFFORTS]
    w(f"- **Quality on these prompts is already saturated.** The Claude Opus 4.6 judge gave GPT-6.1 Sol "
      f"{m46[ARM_ORDER[0]]:.2f} / {m46[ARM_ORDER[1]]:.2f} / {m46[ARM_ORDER[2]]:.2f} out of 5 at `low` / `medium` / "
      f"`high`; GPT-6 Luna scored {min(lq):.2f}–{max(lq):.2f} on the same judge on 2026-09-26. Short assistant turns "
      "do not separate these models.")
    hx = base_out["high"]
    wrong = sum(c.get("wrong", 0) for c in base_out.values())
    w(f"- **Where it does earn its price: the exact-answer probe.** Asked to find the unique 9-of-24 invoice subset "
      f"that reconciles to a given total, GPT-6.1 Sol `high` returned the exact answer in {hx.get('exact', 0)}/3 runs "
      f"({hx.get('cutoff', 0)} spent the whole 40,000-token output cap reasoning and gave no answer), `medium` "
      f"{base_out['medium'].get('exact', 0)}/3, `low` {base_out['low'].get('exact', 0)}/3. Wrong answers: {wrong}; "
      "when it did not solve the task it declined." + topup_sentence(probes))
    w(f"- **Prompt caching behaves like the rest of the family.** Re-sending the same ~{cache['prompt_tokens_mean']:,.0f}"
      f"-token request hit the cache on {cache['repeat_requests_with_cache_hit']}/{cache['repeat_requests']} repeats and "
      f"cut steady-state cost by {cache['steady_state_saving_pct']:.0f}% at list price (cache read 0.1×, write 1.25×).")
    w("")
    w("## Setup")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Client | Linux VM in {prov['vm_metadata']['location']} ({prov['vm_metadata']['vmSize']}), same region as the "
      f"resource; median TCP connect {prov['network_rtt_ms']} ms (matrix) / {summary['network_rtt_ms']} ms (A/B) |")
    w("| API | Responses API, streaming, no tools, concurrency 1; system prompt and output caps identical to the "
      "2026-09-09 and 2026-09-26 runs |")
    w("| Prompts | `datasets/assistant_scenarios.jsonl` (17 prompts, 6 task families); executed copy SHA-256 "
      f"`{prov['source_sha256']['datasets/assistant_scenarios.jsonl'][:16]}…`, identical to both earlier runs |")
    w("| Matrix | 3 arms (GPT-6.1 Sol `low`, `medium`, `high`) × 17 prompts × (1 warm-up + 3 measured) = 204 requests; "
      "`none` is rejected by this model (HTTP 400, supported values low … max) |")
    w(f"| Interleaved A/B | {summary['a']} vs {summary['b']} at `low`: 17 prompts × (1 warm-up + 5 measured) pairs, "
      "the two requests of a pair sent back to back, first side alternated = 204 requests |")
    w("| Deployments | " + "; ".join(f"`{d['deployment']}` {d['model']} {d['version']} {d['sku']} {d['capacity']}"
                                     for d in deploy if d["format"] == "OpenAI") + " |")
    w("| Prices (USD / 1M, Global, list 2026-10-03) | " + " · ".join(
        f"{NAMES.get(m, m)} {p['input']:g} in / {p['cached']:g} cached / {p.get('cache_write', p['input']):g} "
        f"cache write / {p['output']:g} out" for m, p in prices.items()) + " |")
    w(f"| Judge | {', '.join(judge_dep)} on the same resource via the Anthropic Messages API, rubric "
      f"{', '.join(rubric)}, one iteration per prompt and arm (51 scores) |")
    w("")
    w("## Matrix")
    w("")
    w("Client-observed milliseconds over 51 measured requests per arm; cost is the per-request mean at list price. "
      "P90/P95 on 51 samples are descriptive, not a tail SLA.")
    w("")
    w("| Arm | TTFT P50 | TTFT P90 | TTFT P95 | E2E P50 | E2E P90 | E2E P95 | Output tok | Reasoning tok | USD / 1k | "
      "Judge (Opus 4.6) |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARM_ORDER:
        s = S[arm]
        w(f"| {label(arm)} | {s['ttft'][0]:.0f} | {s['ttft'][1]:.0f} | {s['ttft'][2]:.0f} | {s['e2e'][0]:.0f} | "
          f"{s['e2e'][1]:.0f} | {s['e2e'][2]:.0f} | {s['out']:.0f} | {s['reason']:.0f} | {s['usd_1k']:.3f} | "
          f"{m46[arm]:.2f} |")
    w("")
    w("Context, **not a same-session comparison**: the same prompts on GPT-6 Luna seven days earlier "
      "(2026-09-26, same VM and resource). The paired table below is the like-for-like speed comparison.")
    w("")
    w("| Arm (2026-09-26) | TTFT P50 | E2E P50 | Output tok | Reasoning tok | USD / 1k | Judge (Opus 4.6) |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for e in ("none",) + EFFORTS:
        arm = f"gpt-6-luna@{e}"
        s = luna[arm]
        w(f"| {label(arm)} | {s['ttft'][0]:.0f} | {s['e2e'][0]:.0f} | {s['out']:.0f} | {s['reason']:.0f} | "
          f"{s['usd_1k']:.3f} | {luna_m46[arm]:.2f} |")
    w("")
    w("## Interleaved A/B at `low`: GPT-6.1 Sol vs GPT-6 Luna")
    w("")
    w("Every GPT-6.1 Sol request has a GPT-6 Luna partner on the same prompt sent immediately before or after it. "
      "The P50 ratio CI resamples prompts, not requests; the sign tests count pairs and prompts where GPT-6.1 Sol "
      "was faster. `low` is the lowest effort both models accept.")
    w("")
    w("| Metric | GPT-6.1 Sol P50 | GPT-6 Luna P50 | Ratio | 95% CI | Sol faster, pairs | p | Sol faster, prompts | p | "
      "Median Δ, Sol first / Luna first |")
    w("|---|---:|---:|---:|---|---:|---:|---:|---:|---|")
    for metric, name in (("ttft", "TTFT"), ("e2e", "E2E")):
        v = summary[metric]["low"]
        o = v["by_order"]
        w(f"| {name} | {v['a_p50']:.0f} ms | {v['b_p50']:.0f} ms | {v['p50_ratio']:.2f} | "
          f"{v['p50_ratio_ci95'][0]:.2f}–{v['p50_ratio_ci95'][1]:.2f} | {v['a_faster_pairs']}/{v['pairs']} | "
          f"{v['pair_sign_p']:.2g} | {v['a_faster_prompts']}/{v['prompts']} | {v['prompt_sign_p']:.2g} | "
          f"{o['a_first']['median_diff_ms']:+.0f} / {o['b_first']['median_diff_ms']:+.0f} ms |")
    w("")
    w("Reading: the gap holds whichever model goes first and its CI excludes 1. A positive Δ means GPT-6 Luna was "
      "faster.")
    w("")
    w("## Exact-answer probe")
    w("")
    w("One task, repeated three times per setting: given 24 invoices and a target total, name the unique subset of "
      "9 whose amounts sum to it exactly (integer cents, no tools). `exact` = the returned list reconciles; `refused` "
      "= the model declined to produce a list; `cutoff` = the whole output cap went to reasoning and no answer came "
      "back. Each row is three requests, so read the counts as outcomes, not rates.")
    w("")
    w("| Model · effort | Run | Output cap | exact | refused | cutoff | wrong | Median E2E | Median output tok | "
      "Median USD / request |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for name, short, data in probes:
        cap = int((data.get("meta") or {}).get("max_output_tokens") or 40_000)
        groups = defaultdict(list)
        for r in data["records"]:
            groups[(r["model"], r["effort"])].append(r)
        for (model, effort), rs in sorted(groups.items(), key=lambda k: (k[0][0], EFFORTS.index(k[0][1])
                                                                       if k[0][1] in EFFORTS else 9)):
            c = Counter(probe_outcome(r, cap) for r in rs)
            w(f"| {label(f'{model}@{effort}')} | {short} | {cap:,} | {c.get('exact', 0)} | {c.get('refused', 0)} | "
              f"{c.get('cutoff', 0)} | {c.get('wrong', 0)} | {statistics.median(r['e2e_s'] for r in rs):.0f} s | "
              f"{statistics.median(r['usage']['output'] for r in rs):,.0f} | "
              f"{statistics.median(r['usd'] for r in rs):.3f} |")
    w("")
    spend = sum(r["usd"] for _, _, d in probes for r in d["records"] if r.get("usd"))
    w(f"All probe requests together cost ${spend:.2f} at list price. Records, including the returned text, are in "
      "the `exact_answer_probe*.json` files.")
    w("")
    w("## Prompt-cache check")
    w("")
    w("Six assistant prompts, each sent four times in a row with the same system prompt; `cached_tokens` is read from "
      "the usage block of every response. Costs are list price with the cache read and cache write rates above.")
    w("")
    per = defaultdict(lambda: {"prompt": 0, "hits": 0, "repeats": 0, "cached": 0})
    for r in cache_rows:
        e = per[r["item"]]
        e["prompt"] = r["prompt_tokens"]
        if r["repeat"] > 1:
            e["repeats"] += 1
            if r["cached_tokens"]:
                e["hits"] += 1
                e["cached"] = max(e["cached"], r["cached_tokens"])
    w("| Prompt | Prompt tokens | Repeats with a cache hit | Cached tokens on a hit |")
    w("|---|---:|---:|---:|")
    for item, e in sorted(per.items()):
        w(f"| {item} | {e['prompt']:,} | {e['hits']}/{e['repeats']} | {e['cached']:,} |")
    w("")
    w(f"Steady state (repeats only): ${cache['cost_per_1k_requests_steady_state_no_cache']:.2f} per 1,000 requests "
      f"without caching vs ${cache['cost_per_1k_requests_steady_state_with_cache']:.2f} with it, a saving of "
      f"{cache['steady_state_saving_pct']:.0f}%. The first request of each prompt already carried cached tokens "
      f"(mean {cache['first_request_cached_tokens_mean']:.0f}) because an earlier run had warmed the cache, so the "
      "write-billed first request of a cold prompt is not represented here. Prompts under 1,024 tokens are never "
      "cached by the service, which is why the hit counts split by prompt length.")
    w("")
    w("## Files")
    w("")
    w("| File | What it is | SHA-256 |")
    w("|---|---|---|")
    committed = prov["committed_sha256"]
    for pattern, what in FILES:
        name = pattern.format(run=RUN, paired=PAIRED)
        if "*" in name:
            for key in sorted(k for k in committed if k.startswith(name.split("*")[0]) and k.endswith(".json")):
                w(f"| `{key}` | {what} | `{committed[key][:16]}…` |")
            continue
        digest = committed.get(name)
        w(f"| `{name}` | {what} | `{digest[:16]}…` |" if digest else f"| `{name}` | {what} | – |")
    w("")
    red = prov["redaction"]
    w(f"Redaction: the endpoint host is replaced by `{red['endpoint_host']}` in every record; prompts "
      f"{', '.join(red['withheld_question_ids'])} keep their scores and hashes but their answer text and judge "
      "justification are withheld (see `outputs/public_redaction.json`). The exact-answer probe and the cache check "
      "carry no customer text. `provenance.json` lists the SHA-256 of every original file and of every committed "
      "file, and of the harness, judge and dataset as executed.")
    w("")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    target = RUN_DIR / "README.md"
    if args.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            print(f"STALE: {target.relative_to(ROOT)}")
            return 1
        print(f"VERIFIED: {target.relative_to(ROOT)}")
        return 0
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
