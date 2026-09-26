"""Render README.md from one benchmark run directory. The README is generated output; edit this file, not the README.

    python render.py runs/us-matrix-20260925            # write README.md + images/
    python render.py runs/us-matrix-20260925 --check    # exit 1 if README.md differs from a fresh render
"""
import argparse
import hashlib
import json
import shutil
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
README = HERE / "README.md"
IMAGES = HERE / "images"
PRICING = json.loads((HERE / "pricing.json").read_text(encoding="utf-8"))
sys.path.insert(0, str(HERE))
import robustness  # noqa: E402  (same folder; compares against earlier Sweden Central runs)

# Display order and labels. A group missing from the run is simply not rendered.
GROUP_ORDER = [
    ("mai-image-2.6", "MAI-Image-2.6", "MAI-Image-2.6", None),
    ("gpt-image-2-low", "GPT-Image-2 · low", "gpt-image-2", "low"),
    ("gpt-image-2-medium", "GPT-Image-2 · medium", "gpt-image-2", "medium"),
    ("gpt-image-2-high", "GPT-Image-2 · high", "gpt-image-2", "high"),
    ("gpt-image-2.5-flare-auto", "GPT-Image-2.5 Flare · auto", "gpt-image-2.5-flare", "auto"),
    ("gpt-image-2.5-flare-low", "GPT-Image-2.5 Flare · low", "gpt-image-2.5-flare", "low"),
    ("gpt-image-2.5-flare-medium", "GPT-Image-2.5 Flare · medium", "gpt-image-2.5-flare", "medium"),
    ("gpt-image-2.5-flare-high", "GPT-Image-2.5 Flare · high", "gpt-image-2.5-flare", "high"),
    ("gpt-image-2.5-sunburst-auto", "GPT-Image-2.5 Sunburst · auto", "gpt-image-2.5-sunburst", "auto"),
    ("gpt-image-2.5-sunburst-low", "GPT-Image-2.5 Sunburst · low", "gpt-image-2.5-sunburst", "low"),
    ("gpt-image-2.5-sunburst-medium", "GPT-Image-2.5 Sunburst · medium", "gpt-image-2.5-sunburst", "medium"),
    ("gpt-image-2.5-sunburst-high", "GPT-Image-2.5 Sunburst · high", "gpt-image-2.5-sunburst", "high"),
]


def load_run(run_dir):
    results = json.loads((run_dir / "5way_v2_results.json").read_text(encoding="utf-8"))
    if results.get("state") != "COMPLETED":
        raise SystemExit(f"Run state is {results.get('state')!r}, not COMPLETED; refusing to render a partial run.")
    prompts = load_prompts(run_dir)
    raw = [r for r in results["raw_data"] if r.get("ok")]
    failed = [r for r in results["raw_data"] if not r.get("ok")]
    return results, prompts, raw, failed


def load_prompts(run_dir):
    import csv
    path = next(iter(sorted((run_dir / "source").glob("prompts*.csv"))), None)
    if path is None:
        raise SystemExit("No source/prompts*.csv frozen beside the run.")
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    return {i + 1: row for i, row in enumerate(rows)}


def tokens(record):
    info = record.get("token_info") or {}
    if "output_image_tokens" in info:
        return info.get("input_tokens"), info.get("output_image_tokens")
    usage = info.get("usage") or {}
    return usage.get("num_input_text_tokens"), info.get("num_output_tokens") or usage.get("num_output_tokens")


def cost_usd(model, tin, tout):
    price = PRICING.get(model)
    if not price or not price.get("verified") or tin is None or tout is None:
        return None
    return tin / 1e6 * price["input_text"] + tout / 1e6 * price["output_image"]


def echoed_tiers(records):
    """For quality=auto the service picks a tier per request and echoes it; return e.g. 'low ×12, medium ×5'."""
    counts = {}
    for r in records:
        q = (r.get("token_info") or {}).get("service_quality") or "not echoed"
        counts[q] = counts.get(q, 0) + 1
    return ", ".join(f"{q} ×{n}" for q, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def verify_and_copy_images(run_dir, raw):
    """Every formal image is stored once, in images/. The run record carries each image's SHA-256; the bytes are
    read from the run directory when present (fresh run) or from images/ (published tree), and must match."""
    IMAGES.mkdir(exist_ok=True)
    copied = {}
    for r in raw:
        src = run_dir / r["image"]
        dst = IMAGES / f"{r['group']}-r{r['round']}-p{r['prompt_idx']:02d}.png"
        if src.is_file():
            data = src.read_bytes()
        elif dst.is_file():
            data = dst.read_bytes()
        else:
            raise SystemExit(f"image missing: neither {src} nor {dst} exists")
        digest = hashlib.sha256(data).hexdigest()
        if digest != r["image_sha256"]:
            raise SystemExit(f"SHA-256 mismatch for {r['image']}: record says {r['image_sha256'][:12]}, file is {digest[:12]}")
        if not dst.is_file() or dst.read_bytes() != data:
            shutil.copyfile(src, dst)
        copied[(r["group"], r["round"], r["prompt_idx"])] = dst.relative_to(HERE).as_posix()
    return copied


def fmt(x, nd=2):
    return "—" if x is None else f"{x:,.{nd}f}"


def pct(values, p):
    """Percentile with linear interpolation between order statistics (numpy default / Excel PERCENTILE.INC).
    On 34 samples P90 sits between the 30th and 31st sorted value; P95 between the 32nd and 33rd. Descriptive, not
    a tail-latency guarantee."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def render(run_dir):
    results, prompts, raw, failed = load_run(run_dir)
    cfg = results["config"]
    images = verify_and_copy_images(run_dir, raw)
    present = [g for g in GROUP_ORDER if any(r["group"] == g[0] for r in raw)]
    by_group = {g[0]: [r for r in raw if r["group"] == g[0]] for g in present}
    n_prompts = len(prompts)
    rounds = cfg.get("rounds", 2)
    run_name = run_dir.name

    out = []
    w = out.append
    w("# MAI-Image-2.6 vs GPT-Image-2 vs GPT-Image-2.5 — US-region deployments, one client, one session")
    w("")
    w(f"{len(present)} configurations · {n_prompts} prompts · {rounds} rounds · {len(raw)} images · "
      f"resources: East US (MAI) / East US 2 (GPT) · client: {cfg.get('client_location', 'unspecified')}")
    w("")
    w("Every configuration received the same prompts verbatim, from the same client, in one session, "
      "interleaved so no model got a warmer or quieter minute than another. Timings are wall-clock seconds "
      "from HTTP request to full response body — what a user waits, not model-only inference.")
    w("")

    # ---- summary table: latency percentiles ----
    w("## Results")
    w("")
    w("Seconds per image, wall-clock from HTTP request to full response. P50 is the median; P90 / P95 are the values "
      "below which 90% / 95% of this run's requests finished (linear interpolation; descriptive on ≈34 samples per "
      "configuration, not a tail-latency guarantee).")
    w("")
    w("| Configuration | Images | P50 s | P90 s | P95 s | Mean s | Min–max s | Output tokens / image | USD / image (P50) |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for gid, label, model, tier in present:
        rs = by_group[gid]
        times = [r["time"] for r in rs]
        outs = [tokens(r)[1] for r in rs]
        ins = [tokens(r)[0] for r in rs]
        costs = [cost_usd(model, i, o) for i, o in zip(ins, outs)]
        out_tok = f"{outs[0]:,}" if len(set(outs)) == 1 else f"{min(outs):,}–{max(outs):,}"
        cost = fmt(pct(costs, 50), 4) if all(c is not None for c in costs) else "price unverified"
        w(f"| {label} | {len(rs)} | {fmt(pct(times, 50))} | {fmt(pct(times, 90))} | {fmt(pct(times, 95))} | "
          f"{fmt(statistics.mean(times))} | {fmt(min(times))}–{fmt(max(times))} | {out_tok} | {cost} |")
    w("")
    if failed:
        w(f"{len(failed)} request(s) did not return an image after retries and are excluded from the table above; "
          f"see `attempts.jsonl` in the run directory.")
        w("")
    unverified = sorted({g[2] for g in present if not (PRICING.get(g[2]) or {}).get("verified")})
    if unverified:
        w(f"Cost is shown only for models whose price was verified on a recorded date (see Cost). "
          f"Unverified: {', '.join(unverified)}. Token counts are exact API-reported values regardless.")
        w("")
    auto_groups = [g for g in present if g[3] == "auto"]
    if auto_groups:
        w("`auto` is not a fixed tier: the service chooses a tier per request and echoes the one it used. "
          "Tiers echoed in this run — " + "; ".join(f"{g[1]}: {echoed_tiers(by_group[g[0]])}" for g in auto_groups) +
          ". The token column for `auto` therefore shows the observed range, and its cost is per-image actuals, not a tier price.")
        w("")

    # ---- cost ----
    w("## Cost")
    w("")
    w("Cost per image = input text tokens × input price + output image tokens × output price, using the exact token counts "
      "each API returned for each request. No rounding to a tier price: `auto` and any variance are costed as billed.")
    w("")
    w("| Configuration | Images | Output tokens P50 / P90 | USD / image P50 | USD / image P90 | USD / image P95 | USD / image mean | USD / 1,000 images (mean) | vs MAI-Image-2.6 | Run spend (USD) |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    mai_per_image = None
    if "mai-image-2.6" in by_group:
        mai_costs = [cost_usd("MAI-Image-2.6", *tokens(r)) for r in by_group["mai-image-2.6"]]
        if all(c is not None for c in mai_costs):
            mai_per_image = statistics.mean(mai_costs)
    run_total = 0.0
    run_total_complete = True
    for gid, label, model, tier in present:
        rs = by_group[gid]
        costs = [cost_usd(model, *tokens(r)) for r in rs]
        outs = [tokens(r)[1] for r in rs if tokens(r)[1] is not None]
        tok_pcts = f"{pct(outs, 50):,.0f} / {pct(outs, 90):,.0f}" if outs else "—"
        if all(c is not None for c in costs) and costs:
            per = statistics.mean(costs)
            spend = sum(costs)
            run_total += spend
            ratio = f"{per / mai_per_image:.2f}×" if mai_per_image else "—"
            w(f"| {label} | {len(rs)} | {tok_pcts} | {pct(costs, 50):,.4f} | {pct(costs, 90):,.4f} | {pct(costs, 95):,.4f} | "
              f"{per:,.4f} | {per * 1000:,.2f} | {ratio} | {spend:,.2f} |")
        else:
            run_total_complete = False
            w(f"| {label} | {len(rs)} | {tok_pcts} | price unverified | — | — | — | — | — | — |")
    warm = results.get("warmup", [])
    warm_cost = 0.0
    for wu in warm:
        g = next((x for x in GROUP_ORDER if x[0] == wu["group"]), None)
        c = cost_usd(g[2], *tokens(wu)) if g and wu.get("ok") else None
        if c is not None:
            warm_cost += c
    w("")
    total_line = f"**Model charges for this run: ${run_total:,.2f}** for {len(raw)} formal images"
    if warm_cost:
        total_line += f", plus ${warm_cost:,.2f} for {sum(1 for wu in warm if wu.get('ok'))} warm-up images"
    total_line += "." if run_total_complete else " (groups with unverified prices excluded)."
    w(total_line + " Excludes the client machine, storage of the archive, and any Azure resource fixed fees (none: GlobalStandard image deployments bill per token only).")
    w("")
    w("**Where each price comes from.** `list` = the public Azure pricing page on the date shown; `invoice` = actual charge on "
      "our own Azure subscription (Cost Management, PreTaxCost ÷ billed tokens) because the model was not yet on the public page.")
    w("")
    w("| Model | Input text USD / 1M | Output image USD / 1M | Source | Verified |")
    w("|---|---:|---:|---|---|")
    for model in dict.fromkeys(g[2] for g in present):
        p = PRICING.get(model) or {}
        w(f"| {model} | {fmt(p.get('input_text'))} | {fmt(p.get('output_image'))} | {p.get('source_kind', '—')} | {p.get('verified') or 'not verified'} |")
    w("")
    w("Prices are Global deployment, pay-as-you-go, USD, before any negotiated discount. Read the ratio column, not the "
      "absolute dollars: a tier that returns more output tokens costs proportionally more on every model. For fixed tiers "
      "P50 = P90 = P95 = mean because every image bills the same token count; the percentiles only spread for `auto`, "
      "where the service picks the tier per request.")
    w("")

    # ---- robustness vs earlier runs ----
    rob = robustness.compare(run_dir)
    w("## Robustness against earlier runs")
    w("")
    w("Same runner family, same 11 repo prompts (matched by prompt SHA-256; the 6 newer prompts have no earlier counterpart), "
      "same 1024×1024 and 2-round interleaving — but Sweden Central resources, a different day and a different client. "
      "So the question is not whether the seconds match (they should not), but whether the **billing tokens are identical**, "
      "whether the **ordering of configurations** holds, and whether **round 1 and round 2 agree** inside this run.")
    w("")
    w("| Configuration | Tokens identical | P50 s this run / earlier | P90 s this run / earlier | P50 ratio (shared prompts) | Per-prompt ratio P25–P75 | R1 / R2 P50 s | Earlier run |")
    w("|---|:---:|---:|---:|---:|---:|---:|---|")
    for r in rob["groups"]:
        label = next((g[1] for g in GROUP_ORDER if g[0] == r["group"]), r["group"])
        if not r.get("ref_run"):
            w(f"| {label} | — | {fmt(r['us_median_s'])} / — | {fmt(r['us_p90_s'])} / — | — | — | {fmt(r['us_r1_median_s'], 1)} / {fmt(r['us_r2_median_s'], 1)} | no earlier run |")
            continue
        pp = r.get("per_prompt_ratio_p25_p75")
        w(f"| {label} | {'yes' if r['tokens_identical'] else '**NO**'} | {fmt(r['us_median_s'])} / {fmt(r['ref_median_s'])} | "
          f"{fmt(r['us_p90_s'])} / {fmt(r['ref_p90_s'])} | {fmt(r['median_ratio_shared'])}× | {f'{pp[0]:.2f}–{pp[1]:.2f}' if pp else '—'} | "
          f"{fmt(r['us_r1_median_s'], 1)} / {fmt(r['us_r2_median_s'], 1)} | `{r['ref_run']}` ({rob['references'][r['ref_run']]['date']}) |")
    w("")
    autos = [r for r in rob["groups"] if r.get("us_auto_echo")]
    if autos:
        w("`auto` tier choices, this run vs earlier: " + "; ".join(
            f"{next((g[1] for g in GROUP_ORDER if g[0] == r['group']), r['group'])} — now {r['us_auto_echo']}, earlier {r['ref_auto_echo']}"
            for r in autos) + ". For `auto`, 'tokens identical' means: the same echoed tier billed the same token count in both runs.")
        w("")
    o = rob["ordering"]
    w(f"Latency ordering (fastest → slowest) identical to the earlier runs: **{'yes' if o['identical'] else 'no'}**.")
    w("")
    w("- this run: " + " < ".join(o["us"]))
    w("- earlier: " + " < ".join(o["reference"]))
    w("")
    w("Earlier runs used (each is a published run record in the same repository; SHA-256 of the file as read): " + "; ".join(
        f"`{name}` ({spec['date']}, {spec['region']}; `{spec['published_path']}`, SHA-256 `{spec['sha256'][:12]}…`)"
        for name, spec in rob["references"].items()) + ".")
    w("")

    # ---- per-prompt image grid ----
    w("## Images")
    w("")
    w("Round 1 outputs. Each row is one prompt; each column is one configuration. Click any image for full size.")
    w("")
    for idx in sorted(prompts):
        p = prompts[idx]
        w(f"### {p.get('prompt_id', f'P{idx:02d}')} · {p.get('scenario', '')}")
        w("")
        w(f"> {p['prompt']}")
        w("")
        w("| " + " | ".join(g[1] for g in present) + " |")
        w("|" + "---|" * len(present))
        cells = []
        for gid, *_ in present:
            path = images.get((gid, 1, idx))
            rec = next((r for r in by_group[gid] if r["round"] == 1 and r["prompt_idx"] == idx), None)
            if path and rec:
                cells.append(f'<a href="{path}"><img src="{path}" width="160"></a><br>{rec["time"]:.1f} s')
            else:
                cells.append("—")
        w("| " + " | ".join(cells) + " |")
        w("")

    # ---- method ----
    w("## Method")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Run | `{run_name}`, {results.get('started_at_utc', '')[:10]} |")
    w(f"| Client | {cfg.get('client_location', 'unspecified')} |")
    loc_file = run_dir / "CLIENT-LOCATION.json"
    if loc_file.is_file():
        loc = json.loads(loc_file.read_text(encoding="utf-8"))
        for model, res in loc.get("resources", {}).items():
            w(f"| Resource · {model} | {res} |")
        if loc.get("note"):
            w(f"| Region caveat | {loc['note']} |")
    for gc in cfg.get("group_configurations", []):
        parts = [f"{gc['model']} {gc.get('model_version') or ''}".strip()]
        for key, label in (("deployment_sku", ""), ("deployment_region", ""), ("api_version", "api-version "),
                           ("auth", ""), ("request_timeout_seconds", "timeout ")):
            if gc.get(key) not in (None, ""):
                parts.append(f"{label}{gc[key]}" + (" s" if key == "request_timeout_seconds" else ""))
        if gc.get("request_rate_limit_per_minute"):
            parts.append(f"{gc['request_rate_limit_per_minute']} req/min")
        w(f"| {gc['id']} | {' · '.join(parts)} |")
    w(f"| Resolution | {cfg.get('resolution', '1024x1024')} PNG, one image per request |")
    w(f"| Pacing | {cfg.get('inter_call_wait', 5)} s between calls; "
      f"{cfg['rate_pacing']['max_requests']} requests per {cfg['rate_pacing']['window_seconds']} s per deployment |")
    w(f"| Order | round 1 forward, round 2 reversed: {' → '.join(cfg['round_order']['1'][:3])} … |")
    w(f"| Prompts | `source/prompts.csv`, SHA-256 `{cfg.get('prompts_sha256', '')[:16]}…` |")
    w(f"| Runner | `source/benchmark_5way_v2.py`, SHA-256 `{results.get('script_sha256', '')[:16]}…` |")
    for rev in results.get("runner_revisions", []):
        w(f"| Runner revised mid-run | {rev['at_utc'][:16]}Z, `{rev['from_sha256'][:12]}` → `{rev['to_sha256'][:12]}` after "
          f"{rev['ok_before']} ok / {rev['failed_before']} failed samples: {rev['reason']} "
          f"Previous source kept as `source/benchmark_5way_v2.pre-revision-{rev['from_sha256'][:12]}.py`; "
          f"failed samples were re-run, not patched. |")
    attempts_file = run_dir / "attempts.jsonl"
    if attempts_file.is_file():
        bad = {}
        for line in attempts_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            a = json.loads(line)
            if a.get("phase") == "formal" and not a.get("ok"):
                bad[a.get("http_status")] = bad.get(a.get("http_status"), 0) + 1
        if bad:
            desc = ", ".join(f"HTTP {k}: {v}" for k, v in sorted(bad.items(), key=lambda kv: str(kv[0])))
            w(f"| Failed attempts | {sum(bad.values())} of {sum(1 for l in attempts_file.read_text(encoding='utf-8').splitlines() if l.strip())} "
              f"logged requests failed ({desc}); each affected sample was retried until it returned an image, and only the "
              f"successful attempt's latency is reported. Every request is in `attempts.jsonl`. |")
    w("")
    w("**What this does not show.** One client, one day, concurrency 1: these are typical latencies, not P95 under load. "
      "GlobalStandard deployments do not pin the physical GPU region. No image-quality score is computed; the images are "
      "shown so a reader can judge for the scenario they care about. GPT tiers are not calibrated to MAI's single tier — "
      "compare on output tokens per image, which is what each provider bills.")
    w("")
    w("## Reproduce")
    w("")
    w("```")
    w("pip install -r requirements.txt")
    w(f"python render.py runs/{run_name} --check   # re-renders from the frozen run and diffs against README.md")
    w("```")
    w("")
    w("To measure again, use the test pack in `testpack/` with your own deployments; see `testpack/README.md`.")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--check", action="store_true", help="exit 1 if README.md is not byte-identical to a fresh render")
    a = ap.parse_args()
    text = render(a.run_dir)
    if a.check:
        current = README.read_text(encoding="utf-8") if README.is_file() else ""
        if current != text:
            print("CHECK FAIL: README.md differs from a fresh render")
            return 1
        print(f"CHECK PASS: README.md matches run {a.run_dir.name}; {sum(1 for _ in IMAGES.glob('*.png'))} images verified")
        return 0
    README.write_text(text, encoding="utf-8")
    print(f"WROTE {README} ({len(text):,} bytes) from {a.run_dir.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
