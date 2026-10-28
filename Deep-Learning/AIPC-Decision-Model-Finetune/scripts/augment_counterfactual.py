"""Counterfactual records: the same customer text with one device/context field changed so that a label changes.

Contoso's labels come from its policy code and depend on structured fields that the customer text never states
(warranty plan, purchase age, region, battery cycles; network, enterprise management, battery level). The field-flip
pairs of the first test sets showed that the first fine-tune mostly gave both records of a pair the same answer, i.e. it
did not use those fields. This script
  * adds such variants of TRAIN cases to a second training file (train_cf.jsonl = train.jsonl + variants), and
  * builds variant-only evaluation sets from the dev, test and out-of-distribution cases (never from train),
so that rule-following can be trained and measured with more than the few dozen pairs of the first test sets.
The product line is never changed (customers name their laptop in the text). No API calls: the generated texts are
reused unchanged and the labels are recomputed by the policy code.

  python augment_counterfactual.py --root data/contoso --out data/contoso/final [--per-case 2] [--per-case-train 3] [--seed 11]
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
from vendor_policy import PLAN_DAYS, REGIONS, WORKLOADS, record_of  # noqa: E402

FIELDS = {"support": ("warranty_plan", "days_since_purchase", "region", "battery_cycles"),
          "assistant": ("network", "enterprise_managed", "battery")}


def mutate(case, field, rng):
    v = json.loads(json.dumps(case))
    if case["workload"] == "support":
        d = v["device"]
        if field == "warranty_plan":
            d[field] = rng.choice([p for p in PLAN_DAYS if p != d[field]])
        elif field == "days_since_purchase":
            d[field] = max(3, rng.choice((365, 730, 1095)) + rng.randint(-60, 60)) if rng.random() < 0.6 else rng.randint(3, 1400)
        elif field == "region":
            d[field] = rng.choice([r for r in REGIONS if r != d[field]])
        elif field == "battery_cycles":
            d[field] = max(10, 500 + rng.randint(-120, 120)) if rng.random() < 0.6 else rng.randint(10, 990)
    else:
        x = v["context"]
        if field == "network":
            x[field] = rng.choice([n for n in ("wifi", "metered", "offline") if n != x[field]])
        elif field == "enterprise_managed":
            x[field] = not x[field]
        elif field == "battery":
            if rng.random() < 0.8:
                x["power_source"], x["battery_pct"] = "battery", max(1, min(100, 20 + rng.randint(-10, 10)) if rng.random() < 0.6 else rng.randint(1, 100))
            else:
                x["power_source"], x["battery_pct"] = "ac", 100
    return v


def variants(case, per_case, rng):
    labels = WORKLOADS[case["workload"]]["labels"]
    base = labels(case)
    out, seen = [], set()
    for _ in range(40):
        if len(out) >= per_case:
            break
        field = rng.choice(FIELDS[case["workload"]])
        v = mutate(case, field, rng)
        new = labels(v)
        key = json.dumps(v.get("device") or v.get("context"), sort_keys=True)  # distinct field values, outcomes may repeat
        if new != base and key not in seen and v != case:
            seen.add(key)
            out.append((field, v))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-case", type=int, default=2, help="label-changing variants per dev/test/OOD case")
    ap.add_argument("--per-case-train", type=int, default=3, help="label-changing variants per training case")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--splits", default="70,10,10,10", help="must match the build step")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out)
    cuts = [int(x) for x in a.splits.split(",")]
    files = {"train_cf.jsonl": read_jsonl(out / "train.jsonl")}
    report = {}
    for w in ("support", "assistant"):
        for tag, splits in (("g1", None), ("ood", "ood")):
            cases = read_jsonl(root / f"{w}.{tag}.cases.jsonl")
            texts = {t["id"]: t for t in read_jsonl(root / f"{w}.{tag}.texts.jsonl")}
            for c in cases:
                t = texts.get(c["id"])
                if t is None:
                    continue
                split = splits or split_of(c["id"], cuts)
                target = {"train": "train_cf.jsonl", "dev": f"dev_cf_{w}.jsonl", "test": f"test_cf_{w}.jsonl",
                          "ood": f"ood_cf_{w}.jsonl"}.get(split)
                if target is None:  # calibration cases stay as they are
                    continue
                rng = random.Random(a.seed * 1_000_003 + int(hashlib.sha256(c["id"].encode()).hexdigest()[:8], 16))
                for k, (field, v) in enumerate(variants(c, a.per_case_train if split == "train" else a.per_case, rng)):
                    meta = {"source": f"contoso-{w}", "group": c["id"], "case": f"{c['id']}-cf{k}", "lang": c["lang"],
                            "generator": t["generator"], "pair_field": field, "aug": "cf"}
                    files.setdefault(target, []).append({**record_of(v, t["text"]), "_meta": meta})
                    if split in ("test", "ood"):
                        files.setdefault(f"policy_{target}", []).append({**record_of(v, t["text"], with_policy=True), "_meta": meta})
                    report.setdefault(target, Counter())[field] += 1
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, rows in files.items():
        write_jsonl(out / name, rows)
        manifest[name] = {"records": len(rows), "questions": sum(len(r["questions"]) for r in rows),
                          "sha256": hashlib.sha256((out / name).read_bytes()).hexdigest()}
    manifest_path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(json.dumps({"records": {k: v["records"] for k, v in manifest.items() if "cf" in k},
                      "changed_field": {k: dict(v) for k, v in report.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
