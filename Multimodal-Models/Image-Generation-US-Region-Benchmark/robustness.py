"""Robustness of the US run against earlier Sweden Central runs of the same runner family.

    python robustness.py runs/<tag>            # print the comparison
    python robustness.py runs/<tag> --json out # also write machine-readable results

Three checks, all on the 11 repo prompts that both runs share (matched by prompt SHA-256, never by index):
  1. Tokens per image: must be identical for fixed tiers (196 / 1,756 / 7,024 / 1,024). Billing, not latency —
     if this drifts the price tables in both reports are wrong.
  2. Latency: median ratio US/earlier, and the per-prompt sign agreement (does the same prompt take longer in
     both runs?). Different region, date, client and network, so a ratio != 1 is expected; what matters is
     whether the ORDERING of configurations and the tier gaps hold.
  3. Within-run stability: round 1 vs round 2 medians in the US run (the reverse-order design's own check).
Reads the reference locally when readable, else the published byte-identical copy over HTTPS.
"""
import argparse, hashlib, json, statistics, sys, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
HERE = Path(__file__).resolve().parent
# Where the earlier runs live (MAI-Image-2.6 Test/runs). Override when this file runs from a copy.
PROJECT = Path(os.environ.get("USB_REFERENCE_ROOT") or HERE.parent)
REFS = json.loads((HERE / "references.json").read_text(encoding="utf-8"))
_cache = {}


def load_reference(run_name):
    if run_name in _cache:
        return _cache[run_name]
    spec = REFS["runs"][run_name]
    pin = spec.get("sha256")  # SHA-256 of the published copy; the README cites exactly this file
    local = PROJECT / spec["path"]
    doc, source = None, None
    try:
        b = local.read_bytes()
        if (not b.startswith(b"version https://git-lfs") and len(b) > 1000
                and (pin is None or hashlib.sha256(b).hexdigest() == pin)):
            doc, source = json.loads(b), f"local {spec['path']}"
    except OSError:
        pass
    if doc is None:
        with urllib.request.urlopen(spec["media_url"], timeout=120) as r:
            b = r.read()
        got = hashlib.sha256(b).hexdigest()
        if pin and got != pin:
            raise SystemExit(f"reference {run_name}: published copy sha256 {got[:12]} != pinned {pin[:12]}; "
                             f"re-pin deliberately if the published run was legitimately updated")
        doc, source = json.loads(b), "published copy (media.githubusercontent.com)"
    _cache[run_name] = (doc, source, hashlib.sha256(b).hexdigest())
    return _cache[run_name]


def out_tokens(rec):
    info = rec.get("token_info") or {}
    if "output_image_tokens" in info:
        return info.get("output_image_tokens")
    return info.get("num_output_tokens") or (info.get("usage") or {}).get("num_output_tokens")


def by_prompt(records):
    """{prompt_sha256: [records...]} for ok records."""
    d = {}
    for r in records:
        if r.get("ok") and r.get("prompt_sha256"):
            d.setdefault(r["prompt_sha256"], []).append(r)
    return d


def med(xs):
    return statistics.median(xs) if xs else None


def pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def compare(run_dir):
    us = json.loads((run_dir / "5way_v2_results.json").read_text(encoding="utf-8"))
    us_raw = [r for r in us["raw_data"] if r.get("ok")]
    report = {"run": run_dir.name, "state": us.get("state"), "samples": len(us_raw), "groups": [], "references": {}}
    rows = []
    for gid in us["config"]["groups"]:
        m = REFS["group_map"].get(gid)
        us_recs = [r for r in us_raw if r["group"] == gid]
        if not us_recs:
            continue
        row = {"group": gid, "us_n": len(us_recs), "us_median_s": med([r["time"] for r in us_recs]),
               "us_p90_s": pct([r["time"] for r in us_recs], 90),
               "us_r1_median_s": med([r["time"] for r in us_recs if r["round"] == 1]),
               "us_r2_median_s": med([r["time"] for r in us_recs if r["round"] == 2]),
               "us_tokens": sorted({out_tokens(r) for r in us_recs})}
        if m:
            ref_doc, source, sha = load_reference(m["run"])
            spec = REFS["runs"][m["run"]]
            # location-independent citation: the path inside the public repo, taken from the raw-media URL
            published = spec["media_url"].split("/master/", 1)[-1] if "/master/" in spec["media_url"] else spec["path"]
            report["references"][m["run"]] = {"source": source, "published_path": published, "sha256": sha,
                                               **{k: v for k, v in spec.items() if k != "media_url"}}
            ref_recs = [r for r in ref_doc["raw_data"] if r.get("ok") and r["group"] == m["group"]]
            us_bp, ref_bp = by_prompt(us_recs), by_prompt(ref_recs)
            shared = sorted(set(us_bp) & set(ref_bp))
            pairs = [(med([r["time"] for r in us_bp[s]]), med([r["time"] for r in ref_bp[s]])) for s in shared]
            if gid.endswith("-auto"):
                # auto varies by design; the billing invariant is "same echoed tier -> same token count"
                def tier_tokens(recs):
                    d = {}
                    for r in recs:
                        d.setdefault((r.get("token_info") or {}).get("service_quality") or "?", set()).add(out_tokens(r))
                    return d
                ut, rt = tier_tokens(us_recs), tier_tokens(ref_recs)
                tokens_ok = all(ut[q] <= rt.get(q, set()) or rt.get(q) is None for q in ut)
            else:
                tokens_ok = sorted({out_tokens(r) for r in us_recs}) == sorted({out_tokens(r) for r in ref_recs})
            row.update({
                "ref_run": m["run"], "ref_n": len(ref_recs), "ref_median_s": med([r["time"] for r in ref_recs]),
                "ref_p90_s": pct([r["time"] for r in ref_recs], 90),
                "ref_tokens": sorted({out_tokens(r) for r in ref_recs}),
                "shared_prompts": len(shared),
                "tokens_identical": tokens_ok,
                "median_ratio_shared": (med([u for u, _ in pairs]) / med([v for _, v in pairs])) if pairs and med([v for _, v in pairs]) else None,
                "per_prompt_ratio_p25_p75": (sorted(u / v for u, v in pairs)[len(pairs) // 4], sorted(u / v for u, v in pairs)[(3 * len(pairs)) // 4]) if len(pairs) >= 4 else None,
            })
            if gid.endswith("-auto"):
                def echo(recs):
                    c = {}
                    for r in recs:
                        q = (r.get("token_info") or {}).get("service_quality") or "?"
                        c[q] = c.get(q, 0) + 1
                    return c
                row["us_auto_echo"], row["ref_auto_echo"] = echo(us_recs), echo(ref_recs)
        rows.append(row)
    report["groups"] = rows

    # ordering check: rank configurations by median latency in both runs, over groups that have a reference
    ranked = [r for r in rows if r.get("ref_median_s") and r["us_median_s"]]
    us_rank = [r["group"] for r in sorted(ranked, key=lambda r: r["us_median_s"])]
    ref_rank = [r["group"] for r in sorted(ranked, key=lambda r: r["ref_median_s"])]
    report["ordering"] = {"us": us_rank, "reference": ref_rank, "identical": us_rank == ref_rank}
    return report


def print_report(rep):
    print(f"run={rep['run']} state={rep['state']} ok_samples={rep['samples']}")
    print(f"\n{'group':<30} {'US n':>4} {'US med':>7} {'ref med':>8} {'ratio':>6} {'p25-p75':>12} {'tok=':>5} {'r1/r2 med':>12} {'ref run'}")
    for r in rep["groups"]:
        ratio = f"{r['median_ratio_shared']:.2f}" if r.get("median_ratio_shared") else "  -"
        pp = f"{r['per_prompt_ratio_p25_p75'][0]:.2f}-{r['per_prompt_ratio_p25_p75'][1]:.2f}" if r.get("per_prompt_ratio_p25_p75") else "-"
        tok = "yes" if r.get("tokens_identical") else ("NO" if "tokens_identical" in r else "-")
        r12 = f"{r['us_r1_median_s'] or 0:.1f}/{r['us_r2_median_s'] or 0:.1f}" if r["us_r2_median_s"] else f"{r['us_r1_median_s'] or 0:.1f}/-"
        print(f"{r['group']:<30} {r['us_n']:>4} {r['us_median_s']:>7.1f} {r.get('ref_median_s') or 0:>8.1f} {ratio:>6} {pp:>12} {tok:>5} {r12:>12} {r.get('ref_run', '-')}")
        if r.get("us_auto_echo"):
            print(f"{'':<30} auto echo US={r['us_auto_echo']}  ref={r['ref_auto_echo']}")
    print(f"\nlatency ordering identical: {rep['ordering']['identical']}")
    print(f"  US : {' < '.join(rep['ordering']['us'])}")
    print(f"  ref: {' < '.join(rep['ordering']['reference'])}")
    for name, spec in rep["references"].items():
        print(f"ref {name}: {spec['source']} sha256={spec['sha256'][:12]} ({spec['date']}, {spec['region']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    rep = compare(a.run_dir.resolve())
    print_report(rep)
    if a.json:
        a.json.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"WROTE {a.json}")
