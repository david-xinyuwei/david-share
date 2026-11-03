#!/usr/bin/env python3
"""Diagnose saved model probabilities without fitting a deployable temperature or deciding whether to retrain.

Restore raw logits using each row's inference_temperature. Report served accuracy/ECE, source-stratified
case-group bootstrap intervals, and the lowest in-sample ECE found on the finite 0.5..4.0 grid.
That grid result is neither a global optimum nor a bound on what calibration can fix. Threshold statistics
are descriptive results on these same rows, not an independently accepted deployment policy.
Usage: python scripts/calibration_boundary.py --runs 验证结果/微调评测_<time>/runs --out 验证结果/校准边界_<time>
Standard library only.
"""
import argparse
import hashlib
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


def bootstrap(prepared, temp, groups, seed=1, reps=1000):
    if len(groups) != len(prepared) or not prepared:
        raise ValueError("Bootstrap requires one source/group identity per question")
    clusters = {}
    for index, (source, group) in enumerate(groups):
        clusters.setdefault(source, {}).setdefault(group, []).append(index)
    strata = [list(source_groups.values()) for source_groups in clusters.values()]
    scores = []
    for raw, label, _ in prepared:
        probabilities = softmax([value / temp for value in raw])
        prediction = max(range(len(probabilities)), key=probabilities.__getitem__)
        scores.append((probabilities[prediction], prediction == label))
    rng = random.Random(seed)
    accs, eces = [], []
    for _ in range(reps):
        indices = [index for grouped in strata for _ in grouped
                   for index in grouped[rng.randrange(len(grouped))]]
        bins = [[0.0, 0] for _ in range(10)]
        correct = 0
        for index in indices:
            confidence, matched = scores[index]
            bucket = bins[min(int(confidence * 10), 9)]
            bucket[0] += confidence
            bucket[1] += matched
            correct += matched
        accs.append(correct / len(indices))
        eces.append(sum(abs(confidence - matched) for confidence, matched in bins) / len(indices))
    accs.sort()
    eces.sort()
    lo, hi = int(0.025 * reps), int(0.975 * reps) - 1
    return {"acc_95": [round(accs[lo], 4), round(accs[hi], 4)], "ece_95": [round(eces[lo], 4), round(eces[hi], 4)]}


def analyse(path, data_path=None):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = [r for r in rows if r.get("variant", "clean") == "clean"]
    if data_path is not None:
        records = [json.loads(line) for line in Path(data_path).read_text(encoding="utf-8").splitlines() if line.strip()]
        expected = {(index, question_id) for index, record in enumerate(records)
                    for question_id in record["questions"]}
        observed = set()
        for row in rows:
            record_index = int(row["id"].rsplit("/", 1)[-1])
            identity = (record_index, row["question"])
            if identity not in expected or identity in observed:
                raise ValueError(f"Calibration question coverage mismatch: {row['id']}/{row['question']}")
            observed.add(identity)
            question = records[record_index]["questions"][row["question"]]
            label = json.dumps(question["label"]) if isinstance(question["label"], bool) else str(question["label"])
            if row["type"] != question["type"] or str(row["keys"][row["label"]]) != label:
                raise ValueError(f"Calibration input/label mismatch: {row['id']}/{row['question']}")
        if observed != expected:
            raise ValueError(f"Calibration question coverage mismatch: {len(expected - observed)} missing questions")
        groups = [(row["source"], records[int(row["id"].rsplit("/", 1)[-1])]["_meta"]["group"]) for row in rows]
        group_origin = "input data _meta.group"
    else:
        groups = [(row["source"], row["group"]) for row in rows]
        group_origin = "recorded source/group"
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
        "ece_decrease_on_grid": round(at_served["ece"] - sweep[str(best_ece_t)]["ece"], 4),
        "bootstrap_95_at_served": bootstrap(prepared, t_served, groups),
        "bootstrap_method": {"unit": "source-stratified original-case groups", "group_origin": group_origin,
                     "groups": len(set(groups)), "samples": 1000, "seed": 1},
        "temperature_search": {"minimum": min(GRID), "maximum": max(GRID), "points": len(GRID),
                       "objective": "in-sample ECE", "global_bound": False,
                       "best_at_grid_boundary": best_ece_t in (min(GRID), max(GRID))},
        "input_hashes": {"rows_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                 "data_sha256": hashlib.sha256(Path(data_path).read_bytes()).hexdigest() if data_path else None},
        "by_type_at_served": by_type,
        "coverage_at_served": coverage(prepared, t_served),
        "sweep_ece": {t: round(sweep[t]["ece"], 4) for t in ("0.5", "0.75", "1.0", "1.25", "1.5", "2.0", "2.5", "3.0", "4.0")},
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="验证结果/微调评测_<time>/runs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", type=Path, default=Path(__file__).resolve().parents[1] / "data/contoso/final",
                    help="input JSONL directory supplying original case groups")
    ap.add_argument("--sets", nargs="+", default=["test_support", "test_assistant", "ood_support", "ood_assistant"])
    ap.add_argument("--recipes", nargs="+", default=["ft", "ftcf"])
    ap.add_argument("--sizes", nargs="+", choices=["0.8b", "4b"],
                    help="model sizes to require; defaults to supported size directories under --runs")
    a = ap.parse_args()
    runs, out = Path(a.runs), Path(a.out)
    if not runs.is_dir():
        ap.error(f"Calibration runs directory is missing: {runs}")
    if out.exists():
        ap.error(f"Calibration output already exists: {out}")
    sizes = a.sizes or sorted(path.name for path in runs.iterdir()
                             if path.is_dir() and path.name in ("0.8b", "4b"))
    if not sizes:
        ap.error("No calibration model runs found; specify --sizes and provide their results")
    requested = [(f"{size}/{recipe}/{dataset}", runs / size / f"{recipe}-{dataset}" / "rows.json", dataset)
                 for size in sizes for recipe in a.recipes for dataset in a.sets]
    missing = [key for key, path, dataset in requested if not path.is_file()]
    if missing:
        ap.error("Missing calibration runs: " + ", ".join(missing))
    result = {}
    for key, path, dataset in requested:
        result[key] = analyse(path, a.data / f"{dataset}.jsonl")
        entry = result[key]
        print(f"{key:28} n={entry['rows']:4} acc={entry['accuracy']:.3f} [{entry['bootstrap_95_at_served']['acc_95'][0]:.3f},{entry['bootstrap_95_at_served']['acc_95'][1]:.3f}]"
              f"  ECE T=1 {entry['at_T1']['ece']:.3f} -> served T={entry['served_T']} {entry['at_served']['ece']:.3f} [{entry['bootstrap_95_at_served']['ece_95'][0]:.3f},{entry['bootstrap_95_at_served']['ece_95'][1]:.3f}]"
              f" -> grid best T={entry['best_T_for_ece_in_sample']} {entry['ece_at_best_T']:.3f} (in-sample decrease {entry['ece_decrease_on_grid']:+.3f})"
              f"  cov@0.9={entry['coverage_at_served']['0.9']['coverage']:.2f} acc@0.9={entry['coverage_at_served']['0.9']['accuracy_accepted']}")
    out.mkdir(parents=True, exist_ok=False)
    (out / "calibration_boundary.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", out / "calibration_boundary.json")


if __name__ == "__main__":
    main()
