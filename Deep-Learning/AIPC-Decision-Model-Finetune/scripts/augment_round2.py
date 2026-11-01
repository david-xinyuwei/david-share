"""Second-round training augmentation: more region flips and more onsite_repair positives for the TRAIN split only.

Why: the first fine-tunes answered "change one field, the answer must follow" questions worst on the region field
(0.8B FT-cf 36.2%) and almost never answered "onsite eligible = yes" (186 of 2,174 support training records, 8.6%).
Both are policy outcomes that depend on fields the customer text never states, so they can be taught only through
counterfactual variants. This script adds, to train_cf.jsonl, for support training cases only:
  * region variants: the same text with a different region, whenever that changes a label (default 2 per case), and
  * onsite variants: plan -> Premium Care 3Y, region -> one of the onsite regions, purchase age inside the plan,
    whenever that turns the queue into onsite_repair (default 1 per eligible case).
No API calls: texts are reused unchanged and labels are recomputed by vendor_policy. dev/test/ood/calib are untouched,
so every evaluation set keeps its meaning. Output: train_cf2.jsonl + manifest entry + a JSON report on stdout.

  python augment_round2.py --root data/contoso --out data/contoso/final [--region-per-case 2] [--onsite-per-case 1] [--seed 23]
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_vendor_data import read_jsonl, split_of, write_jsonl  # noqa: E402
from vendor_policy import ONSITE_REGIONS, PLAN_DAYS, REGIONS, WORKLOADS, record_of  # noqa: E402

LABELS = WORKLOADS["support"]["labels"]


def clone(case):
    return json.loads(json.dumps(case))


def region_variants(case, per_case, rng):
    base = LABELS(case)
    out = []
    for region in rng.sample([r for r in REGIONS if r != case["device"]["region"]], len(REGIONS) - 1):
        v = clone(case)
        v["device"]["region"] = region
        if LABELS(v) != base:
            out.append(("region", v))
        if len(out) >= per_case:
            break
    return out


def onsite_variants(case, per_case, rng):
    """Make the case onsite-eligible: Premium Care 3Y, an onsite region, purchase age within the plan. Keep only
    variants whose queue becomes onsite_repair (the policy still routes safety, battery-program, claim and invoice
    cases elsewhere), and only when that differs from the original labels."""
    base = LABELS(case)
    out, seen = [], set()
    for _ in range(12):
        if len(out) >= per_case:
            break
        v = clone(case)
        d = v["device"]
        d["warranty_plan"] = "Premium Care 3Y"
        d["region"] = rng.choice(sorted(ONSITE_REGIONS))
        if d["days_since_purchase"] > PLAN_DAYS["Premium Care 3Y"]:
            d["days_since_purchase"] = rng.randint(30, PLAN_DAYS["Premium Care 3Y"] - 30)
        key = json.dumps(d, sort_keys=True)
        new = LABELS(v)
        if new["queue"] == "onsite_repair" and new != base and key not in seen:
            seen.add(key)
            out.append(("onsite", v))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--region-per-case", type=int, default=2)
    ap.add_argument("--onsite-per-case", type=int, default=1)
    ap.add_argument("--seed", type=int, default=23)
    ap.add_argument("--splits", default="70,10,10,10", help="must match the build step")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    cuts = [int(x) for x in a.splits.split(",")]
    base_rows = read_jsonl(out / "train_cf.jsonl")
    cases = read_jsonl(root / "support.g1.cases.jsonl")
    texts = {t["id"]: t for t in read_jsonl(root / "support.g1.texts.jsonl")}
    added, report = [], {"region": Counter(), "onsite": Counter()}
    for c in cases:
        t = texts.get(c["id"])
        if t is None or split_of(c["id"], cuts) != "train":
            continue
        rng = random.Random(a.seed * 1_000_003 + int(hashlib.sha256(c["id"].encode()).hexdigest()[:8], 16))
        variants = region_variants(c, a.region_per_case, rng) + onsite_variants(c, a.onsite_per_case, rng)
        for k, (kind, v) in enumerate(variants):
            meta = {"source": "contoso-support", "group": c["id"], "case": f"{c['id']}-r2{kind}{k}", "lang": c["lang"],
                    "generator": t["generator"], "pair_field": "region" if kind == "region" else "warranty_plan+region", "aug": f"r2-{kind}"}
            added.append({**record_of(v, t["text"]), "_meta": meta})
            report[kind][LABELS(v)["queue"]] += 1
    rows = base_rows + added
    name = "train_cf2.jsonl"
    write_jsonl(out / name, rows)
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[name] = {"records": len(rows), "questions": sum(len(r["questions"]) for r in rows),
                      "sha256": hashlib.sha256((out / name).read_bytes()).hexdigest(),
                      "derived_from": "train_cf.jsonl", "added": len(added), "seed": a.seed,
                      "region_per_case": a.region_per_case, "onsite_per_case": a.onsite_per_case}
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    onsite_total = sum(1 for r in rows if r["_meta"]["source"] == "contoso-support" and r["questions"]["queue"]["label"] == "onsite_repair")
    region_total = sum(1 for r in rows if r["_meta"].get("pair_field") in ("region", "warranty_plan+region"))
    print(json.dumps({"base": len(base_rows), "added": len(added), "total": len(rows),
                      "added_by_kind_and_queue": {k: dict(v) for k, v in report.items()},
                      "support_onsite_repair_records": onsite_total, "region_touching_variants": region_total}, ensure_ascii=False))


if __name__ == "__main__":
    main()
