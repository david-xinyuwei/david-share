#!/usr/bin/env python3
"""Measure where temperature calibration stops helping and retraining starts, from saved kev.benchmark rows.

kev rows keep the logits already divided by the served temperature plus `inference_temperature`, so for any other
temperature T the probabilities are softmax(logits * T_served / T). Argmax never changes, so accuracy is invariant;
Brier, ECE, NLL and threshold coverage do change. For each model x test set this script reports:
  - accuracy (constant in T) and the 95% bootstrap interval of accuracy (what a retrain has to beat);
  - ECE / Brier at T = 1 (no calibration), at the served T, and at the best T for this very set (an in-sample optimum,
    i.e. the most a single scalar temperature could ever remove) -> the residual ECE is what calibration cannot fix;
  - the 95% bootstrap interval of ECE at the served T (the noise floor a "drift" must exceed to mean anything);
  - ECE per question type at the served T;
  - the automation trade-off at the served T: coverage and accuracy of the accepted part at confidence thresholds.
Usage: python scripts/calibration_boundary.py --runs 验证结果/微调评测_<time>/runs --out 验证结果/校准边界_<time>
Standard library only.
"""
import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

GRID = [round(0.5 + 0.05 * i, 2) for i in range(71)]  # 0.50 .. 4.00
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def softmax(xs):
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = sum(e)
    return [x / s for x in e]


def prepare(rows):
    """Raw logits, label index, question type per row."""
    out = []
    for r in rows:
        t_served = float(r["inference_temperature"])
        raw = [float(x) * t_served for x in r["logits"]]
        out.append((raw, int(r["label"]), r["type"]))
    return out, t_served


def metrics(prepared, temp, idx=None):
    idx = range(len(prepared)) if idx is None else idx
    bins = [[0, 0.0, 0] for _ in range(10)]
    brier = nll = 0.0
    correct = n = 0
    for i in idx:
        raw, label, _ = prepared[i]
        p = softmax([x / temp for x in raw])
        pred = max(range(len(p)), key=lambda j: p[j])
        correct += pred == label
        brier += sum((x - (1.0 if j == label else 0.0)) ** 2 for j, x in enumerate(p))
        nll += -math.log(max(p[label], 1e-12))
        b = bins[min(int(p[pred] * 10), 9)]
        b[0] += 1
        b[1] += p[pred]
        b[2] += pred == label
        n += 1
    ece = sum(abs(b[1] - b[2]) for b in bins if b[0]) / n
    return {"n": n, "acc": correct / n, "ece": ece, "brier": brier / n, "nll": nll / n}


def coverage(prepared, temp):
    rows = []
    for raw, label, _ in prepared:
        p = softmax([x / temp for x in raw])
        pred = max(range(len(p)), key=lambda j: p[j])
        rows.append((p[pred], pred == label))
    out = {}
    for th in THRESHOLDS:
        accepted = [ok for conf, ok in rows if conf >= th]
        out[str(th)] = {"coverage": round(len(accepted) / len(rows), 4),
                        "accuracy_accepted": round(sum(accepted) / len(accepted), 4) if accepted else None}
    return out


def bootstrap(prepared, temp, seed=1, reps=1000):
    rng = random.Random(seed)
    n = len(prepared)
    accs, eces = [], []
    for _ in range(reps):
        idx = [rng.randrange(n) for _ in range(n)]
        m = metrics(prepared, temp, idx)
        accs.append(m["acc"])
        eces.append(m["ece"])
    accs.sort()
    eces.sort()
    lo, hi = int(0.025 * reps), int(0.975 * reps) - 1
    return {"acc_95": [round(accs[lo], 4), round(accs[hi], 4)], "ece_95": [round(eces[lo], 4), round(eces[hi], 4)]}


def analyse(path):
    rows = json.load(open(path, encoding="utf-8"))
    rows = [r for r in rows if r.get("variant", "clean") == "clean"]
    prepared, t_served = prepare(rows)
    sweep = {str(t): metrics(prepared, t) for t in GRID}
    best_ece_t = min(GRID, key=lambda t: sweep[str(t)]["ece"])
    best_nll_t = min(GRID, key=lambda t: sweep[str(t)]["nll"])
    at_served = metrics(prepared, t_served)
    by_type = {}
    for qtype in sorted({q[2] for q in prepared}):
        idx = [i for i, q in enumerate(prepared) if q[2] == qtype]
        by_type[qtype] = {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics(prepared, t_served, idx).items()}
    return {
        "rows": len(prepared), "served_T": round(t_served, 4),
        "accuracy": round(at_served["acc"], 4),
        "at_T1": {k: round(v, 4) for k, v in metrics(prepared, 1.0).items() if k in ("ece", "brier", "nll")},
        "at_served": {k: round(v, 4) for k, v in at_served.items() if k in ("ece", "brier", "nll")},
        "best_T_for_ece_in_sample": best_ece_t, "ece_at_best_T": round(sweep[str(best_ece_t)]["ece"], 4),
        "best_T_for_nll_in_sample": best_nll_t, "ece_at_nll_T": round(sweep[str(best_nll_t)]["ece"], 4),
        "ece_removable_by_any_T": round(at_served["ece"] - sweep[str(best_ece_t)]["ece"], 4),
        "bootstrap_95_at_served": bootstrap(prepared, t_served),
        "by_type_at_served": by_type,
        "coverage_at_served": coverage(prepared, t_served),
        "sweep_ece": {t: round(sweep[t]["ece"], 4) for t in ("0.5", "0.75", "1.0", "1.25", "1.5", "2.0", "2.5", "3.0", "4.0")},
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="验证结果/微调评测_<time>/runs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sets", nargs="+", default=["test_support", "test_assistant", "ood_support", "ood_assistant"])
    ap.add_argument("--recipes", nargs="+", default=["ft", "ftcf"])
    a = ap.parse_args()
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    result = {}
    for size in sorted(p.name for p in runs.iterdir() if p.is_dir()):
        for recipe in a.recipes:
            for s in a.sets:
                path = runs / size / f"{recipe}-{s}" / "rows.json"
                if path.is_file():
                    key = f"{size}/{recipe}/{s}"
                    result[key] = analyse(path)
                    r = result[key]
                    print(f"{key:28} n={r['rows']:4} acc={r['accuracy']:.3f} [{r['bootstrap_95_at_served']['acc_95'][0]:.3f},{r['bootstrap_95_at_served']['acc_95'][1]:.3f}]"
                          f"  ECE T=1 {r['at_T1']['ece']:.3f} -> served T={r['served_T']} {r['at_served']['ece']:.3f} [{r['bootstrap_95_at_served']['ece_95'][0]:.3f},{r['bootstrap_95_at_served']['ece_95'][1]:.3f}]"
                          f" -> best T={r['best_T_for_ece_in_sample']} {r['ece_at_best_T']:.3f} (removable {r['ece_removable_by_any_T']:+.3f})"
                          f"  cov@0.9={r['coverage_at_served']['0.9']['coverage']:.2f} acc@0.9={r['coverage_at_served']['0.9']['accuracy_accepted']}")
    (out / "calibration_boundary.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out / "calibration_boundary.json")


if __name__ == "__main__":
    main()
