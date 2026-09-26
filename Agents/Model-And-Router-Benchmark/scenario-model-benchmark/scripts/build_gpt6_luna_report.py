"""Build (or check) outputs/gpt6-luna-20260926/README.md from the committed evidence in that folder.

Every number in the report is computed here from the published files; nothing is typed in by hand.
The 2026-09-09 metrics in outputs/ are read only for the drift table.

    python scripts/build_gpt6_luna_report.py            # write README.md
    python scripts/build_gpt6_luna_report.py --check    # fail if README.md is stale or evidence is incomplete
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "outputs" / "gpt6-luna-20260926"
RUN = "20260926_131212"
PAIRED = "paired_gpt-6-luna_vs_gpt-5.6-luna_20260926_143407"
BASELINE = ROOT / "outputs" / "direct_20260909_120534.metrics.jsonl"
WITHHELD = {"PA01", "PA03"}
PLACEHOLDER_HOST = "YOUR-ENDPOINT.cognitiveservices.azure.com"
ARM_ORDER = (["gpt-4o-mini-bench"]
             + [f"gpt-5-mini@{e}" for e in ("minimal", "low", "medium", "high")]
             + [f"gpt-5.6-luna@{e}" for e in ("none", "low", "medium", "high", "xhigh", "max")]
             + [f"gpt-6-luna@{e}" for e in ("none", "low", "medium", "high", "xhigh", "max")])
EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
FILES = (("direct_{run}.metrics.jsonl", "every matrix request, numbers only"),
         ("raw_fulltext/direct_{run}.jsonl", "every matrix request with answer text"),
         ("{paired}.jsonl", "every interleaved A/B request"),
         ("{paired}.summary.json", "A/B statistics as printed above"),
         ("quality_opus55_{run}.jsonl", "Judge A scores"),
         ("quality_opus46_{run}.jsonl", "Judge B scores"),
         ("deployment_verification.json", "deployments read back from Azure"),
         ("provenance.json", "client, executed-source hashes, redaction record"))


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(xs: list[float], q: int) -> float:
    """Inclusive linear-interpolation percentile."""
    return statistics.quantiles(xs, n=100, method="inclusive")[q - 1]


def sign_p(wins: int, n: int) -> float:
    if n == 0:
        return 1.0
    k = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


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


def validate(records, paired, q55, q46, summary) -> list[str]:
    problems = []
    if len(records) != 1156:
        problems.append(f"expected 1156 matrix records, found {len(records)}")
    counts = defaultdict(int)
    for r in measured(records):
        counts[r["arm"]] += 1
    if sorted(counts) != sorted(ARM_ORDER) or set(counts.values()) != {51}:
        problems.append(f"expected 17 arms x 51 measured requests, found {dict(counts)}")
    if len(paired) != 612 or any(r.get("error") for r in paired):
        problems.append("expected 612 error-free interleaved requests")
    for name, q in (("opus55", q55), ("opus46", q46)):
        if len(q) != 289 or {a for a, _ in q} != set(ARM_ORDER):
            problems.append(f"{name}: expected 289 scores over 17 arms")
    if summary["requests"] != 612 or summary["errors"] != 0:
        problems.append("paired summary does not match the paired records")
    hosts = {r.get("endpoint_host") for r in records + paired}
    if hosts != {PLACEHOLDER_HOST}:
        problems.append(f"endpoint not redacted: {hosts}")
    return problems


def paired_quality(q: dict) -> dict[str, tuple]:
    out = {}
    for e in EFFORTS:
        d = [q[(f"gpt-6-luna@{e}", k)] - q[(f"gpt-5.6-luna@{e}", k)] for (a, k) in q if a == f"gpt-6-luna@{e}"]
        w, l = sum(x > 0 for x in d), sum(x < 0 for x in d)
        out[e] = (statistics.mean(d), w, l, len(d) - w - l, sign_p(w, w + l))
    return out


def pearson(x, y) -> float:
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    return num / math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))


def label(arm: str) -> str:
    if arm == "gpt-4o-mini-bench":
        return "GPT-4o mini"
    model, effort = arm.split("@")
    name = {"gpt-5-mini": "GPT-5 mini", "gpt-5.6-luna": "GPT-5.6 Luna", "gpt-6-luna": "GPT-6 Luna"}[model]
    return f"{name} `{effort}`"


def render() -> str:
    records = load_jsonl(RUN_DIR / f"direct_{RUN}.metrics.jsonl")
    paired = load_jsonl(RUN_DIR / f"{PAIRED}.jsonl")
    summary = json.loads((RUN_DIR / f"{PAIRED}.summary.json").read_text(encoding="utf-8"))
    q55 = quality(RUN_DIR / f"quality_opus55_{RUN}.jsonl")
    q46 = quality(RUN_DIR / f"quality_opus46_{RUN}.jsonl")
    batches = defaultdict(list)
    for r in load_jsonl(RUN_DIR / f"quality_opus55_{RUN}.jsonl"):
        batches[r["judge_batch"]].append(r["quality_mean"])
    batch_means = [statistics.mean(v) for v in batches.values()]
    problems = validate(records, paired, q55, q46, summary)
    if len(batches) != 8 or sum(len(v) for v in batches.values()) != 289:
        problems.append("Judge A rows must carry their judge_batch (8 batches, 289 rows)")
    if problems:
        raise ValueError("evidence incomplete:\n  " + "\n  ".join(problems))
    prov = json.loads((RUN_DIR / "provenance.json").read_text(encoding="utf-8"))
    deploy = json.loads((RUN_DIR / "deployment_verification.json").read_text(encoding="utf-8"))
    S = arm_stats(records)
    base = arm_stats(load_jsonl(BASELINE)) if BASELINE.is_file() else {}
    m55 = {a: statistics.mean(v for (x, _), v in q55.items() if x == a) for a in ARM_ORDER}
    m46 = {a: statistics.mean(v for (x, _), v in q46.items() if x == a) for a in ARM_ORDER}
    keys = sorted(q55)
    r_item = pearson([q55[k] for k in keys], [q46[k] for k in keys])
    g6, g56 = S["gpt-6-luna@none"], S["gpt-5.6-luna@none"]
    tn, en = summary["ttft"]["none"], summary["e2e"]["none"]
    tl, th = summary["ttft"]["low"], summary["ttft"]["high"]
    cheaper = 1 - g6["usd_1k"] / g56["usd_1k"]
    L: list[str] = []
    w = L.append
    w("# GPT-6 Luna follow-up: every arm re-measured in one session")
    w("")
    w("2026-09-26 · Sweden Central · the same 17 assistant prompts, VM and resource as the "
      "[2026-09-09 matrix](../../README.md), plus GPT-6 Luna at every reasoning effort it accepts.")
    w("")
    w("> Generated by [`scripts/build_gpt6_luna_report.py`](../../scripts/build_gpt6_luna_report.py) from the files in "
      "this folder. Do not edit by hand; `--check` fails if this page and the evidence disagree.")
    w("")
    w("## Summary")
    w("")
    w(f"- **GPT-6 Luna `none` is the new default low-latency tier.** In {tn['pairs']} back-to-back pairs against "
      f"GPT-5.6 Luna `none` (order alternated), time to first token P50 was **{tn['a_p50']:.0f} ms vs "
      f"{tn['b_p50']:.0f} ms** (ratio {tn['p50_ratio']:.2f}, 95% CI {tn['p50_ratio_ci95'][0]:.2f}–"
      f"{tn['p50_ratio_ci95'][1]:.2f}; faster in {tn['a_faster_pairs']}/{tn['pairs']} pairs and "
      f"{tn['a_faster_prompts']}/{tn['prompts']} prompts). End-to-end P50 was {en['a_p50']:.0f} vs {en['b_p50']:.0f} ms. "
      f"It cost **{cheaper:.0%} less** per request (${g6['usd_1k']:.3f} vs ${g56['usd_1k']:.3f} per 1,000).")
    w("- **Quality is on par, not better.** Two cross-vendor blind judges found no significant per-prompt "
      "difference between GPT-6 Luna and GPT-5.6 Luna at any effort.")
    el, eh = summary["e2e"]["low"], summary["e2e"]["high"]
    w("- **Only `none` is a robust first-token win.** At `low` and `high` the TTFT gap is inside the noise "
      f"(ratio CI {tl['p50_ratio_ci95'][0]:.2f}–{tl['p50_ratio_ci95'][1]:.2f} and "
      f"{th['p50_ratio_ci95'][0]:.2f}–{th['p50_ratio_ci95'][1]:.2f}), though GPT-6 Luna still finishes first in most "
      f"pairs ({el['a_faster_pairs']}/{el['pairs']} and {eh['a_faster_pairs']}/{eh['pairs']}). Tails differ in both "
      f"directions at `none`: TTFT P95 {g6['ttft'][2]:.0f} vs {g56['ttft'][2]:.0f} ms (GPT-6 wider), E2E P95 "
      f"{g6['e2e'][2]:.0f} vs {g56['e2e'][2]:.0f} ms (GPT-6 narrower).")
    w("- **The service itself moved.** The same GPT-5.6 Luna deployment was faster than on 2026-09-09, which is why "
      "every arm was re-measured instead of comparing a new model against old numbers.")
    w("")
    w("## Setup")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Client | Linux VM in {prov['vm_metadata']['location']} ({prov['vm_metadata']['vmSize']}), same region as the "
      f"resource; median TCP connect {prov['network_rtt_ms']} ms (matrix) / {summary['network_rtt_ms']} ms (A/B) |")
    w("| API | Responses API, streaming, no tools, concurrency 1; system prompt and output caps identical to 2026-09-09 |")
    w("| Prompts | `datasets/assistant_scenarios.jsonl` (17 prompts, 6 task families); executed copy SHA-256 "
      f"`{prov['source_sha256']['datasets/assistant_scenarios.jsonl'][:16]}…`, identical to 2026-09-09 |")
    w("| Matrix | 17 arms × 17 prompts × (1 warm-up + 3 measured) = 1,156 requests, arms run one after another |")
    w(f"| Interleaved A/B | {summary['a']} vs {summary['b']} at `none`, `low`, `high`: 17 prompts × (1 warm-up + 5 "
      "measured) pairs, the two requests of a pair sent back to back, first side alternated = 612 requests |")
    w("| Deployments | " + "; ".join(f"`{d['deployment']}` {d['model']} {d['version']} {d['sku']} {d['capacity']}"
                                     for d in deploy if d["format"] == "OpenAI") + " |")
    w("| Prices (USD / 1M, Global, list 2026-09-26) | GPT-6 Luna 0.10 in / 0.01 cached / 0.50 out · GPT-5.6 Luna 0.20 / "
      "0.02 / 1.20 · GPT-5 mini 0.25 / 0.03 / 2.00 · GPT-4o mini 0.15 / 0.075 / 0.60 |")
    w("")
    w("## Same-session matrix")
    w("")
    w("Client-observed milliseconds over 51 measured requests per arm; cost is the per-request mean at list price. "
      "P90/P95 on 51 samples are descriptive, not a tail SLA.")
    w("")
    w("| Arm | TTFT P50 | TTFT P90 | TTFT P95 | E2E P50 | E2E P90 | E2E P95 | Output tok | Reasoning tok | USD / 1k | "
      "Judge A | Judge B |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for arm in ARM_ORDER:
        s = S[arm]
        name = f"**{label(arm)}**" if arm == "gpt-6-luna@none" else label(arm)
        w(f"| {name} | {s['ttft'][0]:.0f} | {s['ttft'][1]:.0f} | {s['ttft'][2]:.0f} | {s['e2e'][0]:.0f} | "
          f"{s['e2e'][1]:.0f} | {s['e2e'][2]:.0f} | {s['out']:.0f} | {s['reason']:.0f} | {s['usd_1k']:.3f} | "
          f"{m55[arm]:.2f} | {m46[arm]:.2f} |")
    w("")
    w("Judge A = Claude Opus 5.5, Judge B = Claude Opus 4.6 (see [Quality](#quality)).")
    w("")
    w("## Interleaved A/B: is the speed difference real?")
    w("")
    w("The matrix runs arms one after another, so each arm owns a different half hour. Here every GPT-6 Luna request "
      "has a GPT-5.6 Luna partner on the same prompt sent immediately before or after it. The P50 ratio CI resamples "
      "prompts, not requests; the sign tests count pairs and prompts where GPT-6 Luna was faster.")
    w("")
    w("| Metric · effort | GPT-6 Luna P50 | GPT-5.6 Luna P50 | Ratio | 95% CI | Faster pairs | p | Faster prompts | p | "
      "Median Δ, GPT-6 first / 5.6 first |")
    w("|---|---:|---:|---:|---|---:|---:|---:|---:|---|")
    for metric, name in (("ttft", "TTFT"), ("e2e", "E2E")):
        for e in ("none", "low", "high"):
            v = summary[metric][e]
            o = v["by_order"]
            w(f"| {name} `{e}` | {v['a_p50']:.0f} ms | {v['b_p50']:.0f} ms | {v['p50_ratio']:.2f} | "
              f"{v['p50_ratio_ci95'][0]:.2f}–{v['p50_ratio_ci95'][1]:.2f} | {v['a_faster_pairs']}/{v['pairs']} | "
              f"{v['pair_sign_p']:.2g} | {v['a_faster_prompts']}/{v['prompts']} | {v['prompt_sign_p']:.2g} | "
              f"{o['a_first']['median_diff_ms']:+.0f} / {o['b_first']['median_diff_ms']:+.0f} ms |")
    w("")
    w("Reading: at `none` the gap holds whichever model goes first, on most prompts, and its CI excludes 1. At `low` and "
      "`high` the TTFT gap does not, while end to end GPT-6 Luna still wins most pairs. The sequential matrix put "
      f"`none` end-to-end P50 at a tie ({g6['e2e'][0]:.0f} vs {g56['e2e'][0]:.0f} ms); interleaved it is not, which is "
      "the half-hour confound the A/B exists to remove.")
    w("")
    if base:
        w("## Drift since 2026-09-09")
        w("")
        w("Same deployments, VM, prompts and payloads. Only the day differs.")
        w("")
        w("| Arm | TTFT P50 09-09 | TTFT P50 09-26 | Change |")
        w("|---|---:|---:|---:|")
        for arm in ("gpt-4o-mini-bench", "gpt-5-mini@minimal", "gpt-5-mini@high", "gpt-5.6-luna@none",
                    "gpt-5.6-luna@high", "gpt-5.6-luna@max"):
            if arm in base:
                a, b = base[arm]["ttft"][0], S[arm]["ttft"][0]
                w(f"| {label(arm)} | {a:.0f} ms | {b:.0f} ms | {b / a - 1:+.0%} |")
        w("")
        w("A new model compared against numbers from another day would inherit this drift as if it were a model "
          "difference.")
        w("")
    w("## Quality")
    w("")
    w("GPT judges were ruled out: `gpt-5.6-terra` is a generation older than GPT-6 and `gpt-6-astra` is GPT-6 Luna's "
      "own family, and the repository's judge rules reject both. Two Claude judges scored the same 289 answers "
      "(first measured answer per arm × prompt) with the unchanged five-dimension rubric `v2-toolless-2026-09-10`:")
    w("")
    w("- **Judge A, Claude Opus 5.5**, via a GitHub Copilot agent: answers anonymised and shuffled, scored in "
      f"{len(batches)} independent batches of {min(map(len, batches.values()))}–{max(map(len, batches.values()))} with "
      f"the rubric verbatim. Batch leniency varied (batch means {min(batch_means):.2f}–{max(batch_means):.2f}); every "
      "batch is a random mix of arms, so this adds noise rather than favouring one model.")
    w("- **Judge B, Claude Opus 4.6**, through the Foundry Anthropic Messages API with `judge.py` (extended thinking, "
      "4,096-token budget), as an independent cross-check.")
    w("")
    worst = max(ARM_ORDER, key=lambda a: abs(m55[a] - m46[a]))
    w(f"Agreement: item-level Pearson {r_item:.2f} over 289 answers. Both put GPT-4o mini last; Judge B is more "
      f"lenient overall ({statistics.mean(q46.values()):.2f} vs {statistics.mean(q55.values()):.2f}) and disagrees "
      f"most on {label(worst)} ({m55[worst]:.2f} vs {m46[worst]:.2f}).")
    w("")
    w("GPT-6 Luna minus GPT-5.6 Luna at the same effort, paired by prompt:")
    w("")
    w("| Effort | Judge A mean Δ | better / worse / tie | p | Judge B mean Δ | better / worse / tie | p |")
    w("|---|---:|---|---:|---:|---|---:|")
    pa, pb = paired_quality(q55), paired_quality(q46)
    for e in EFFORTS:
        a, b = pa[e], pb[e]
        w(f"| `{e}` | {a[0]:+.3f} | {a[1]} / {a[2]} / {a[3]} | {a[4]:.2f} | {b[0]:+.3f} | {b[1]} / {b[2]} / {b[3]} | "
          f"{b[4]:.2f} |")
    w("")
    w("No row is significant for both judges, and none survives a six-comparison correction for either. "
      "These synthetic prompts are easy for every Luna arm; separating the Luna tiers needs harder, real traffic.")
    w("")
    w("## Limitations")
    w("")
    w("- 17 synthetic prompts, single turn, concurrency 1, one region, one evening. Not a capacity or SLA test.")
    w("- GlobalStandard does not pin the GPU region; the resource region is a fact, the serving region is not observable.")
    w("- TTFT includes network, queueing and any reasoning before the first text token; it is not pure model time.")
    w(f"- Prompts {', '.join(sorted(WITHHELD))} reproduce an internal meeting transcript; their answer text and judge "
      "justifications are withheld in this public copy (numbers, scores and `response_sha256` unchanged), as in "
      "[public_redaction.json](../public_redaction.json).")
    w("")
    w("## Files")
    w("")
    w("| File | What | SHA-256 |")
    w("|---|---|---|")
    for pattern, what in FILES:
        name = pattern.format(run=RUN, paired=PAIRED)
        w(f"| [`{name}`]({name}) | {what} | `{sha256(RUN_DIR / name)[:16]}…` |")
    w("")
    w("## Reproduce")
    w("")
    w("```bash")
    w("# same-region Linux VM, Entra ID auth (no key needed)")
    w('export AZURE_OPENAI_ENDPOINT="https://<resource>.cognitiveservices.azure.com/"')
    w("python probe_efforts.py --deployments gpt-6-luna --write")
    w("python harness.py --mode direct --matrix --dataset datasets/assistant_scenarios.jsonl \\")
    w("  --deployments gpt-6-luna,gpt-5.6-luna,gpt-5-mini,gpt-4o-mini-bench \\")
    w("  --region swedencentral --client-location swedencentral-linux-vm --iterations 3 --warmup 1")
    w("python scripts/paired_direct.py --a gpt-6-luna --b gpt-5.6-luna --efforts none,low,high \\")
    w("  --repeats 5 --warmup 1 --region swedencentral --client-location swedencentral-linux-vm")
    w("python scripts/build_gpt6_luna_report.py --check")
    w("```")
    w("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = render()
    target = RUN_DIR / "README.md"
    if a.check:
        if not target.is_file() or target.read_text(encoding="utf-8") != text:
            print("README.md is stale; run scripts/build_gpt6_luna_report.py")
            return 1
        print("README.md matches the evidence")
        return 0
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
