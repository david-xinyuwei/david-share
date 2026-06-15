#!/usr/bin/env python3
"""
Evaluate v2 predictions: focus on category accuracy + multi-label detail/co tags F1.
Now both gold and pred use semantic strings, so F1 is meaningful.
"""
import argparse
import json
import re
import statistics
from pathlib import Path


def extract_json(text):
    if text is None:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def get_gt(rec):
    try:
        return json.loads(rec["messages"][-1]["content"])
    except Exception:
        return None


def prf(pred_set, gold_set):
    if not pred_set and not gold_set:
        return 1.0, 1.0, 1.0
    if not pred_set:
        return 0.0, 0.0, 0.0
    if not gold_set:
        return 0.0, 1.0, 0.0
    tp = len(pred_set & gold_set)
    p = tp / len(pred_set)
    r = tp / len(gold_set)
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-json", required=True)
    ap.add_argument("--predictions", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    val = json.loads(Path(args.val_json).read_text())
    preds = [json.loads(l) for l in Path(args.predictions).read_text().splitlines() if l.strip()]
    by_idx = {p["index"]: p for p in preds}

    n = len(val)
    schema_ok = 0
    cat_correct = 0
    detail_p, detail_r, detail_f = [], [], []
    co_p, co_r, co_f = [], [], []
    latencies = []
    out_tokens = []
    err = 0

    cat_confusion = []  # (gold, pred)

    for i, rec in enumerate(val):
        gt = get_gt(rec)
        p = by_idx.get(i)
        if not p or "error" in p:
            err += 1
            continue
        latencies.append(p.get("latency_ms", 0))
        if p.get("output_tokens"):
            out_tokens.append(p["output_tokens"])
        pj = extract_json(p.get("prediction"))
        if pj is None:
            continue
        schema_ok += 1
        gcat = str(gt.get("category", "")).lower()
        pcat = str(pj.get("category", "")).lower()
        if gcat == pcat:
            cat_correct += 1
        cat_confusion.append((gcat, pcat))
        gd = set(map(str.lower, gt.get("detail_tags") or []))
        pd_ = set(map(str.lower, pj.get("detail_tags") or []))
        a, b, c = prf(pd_, gd)
        detail_p.append(a); detail_r.append(b); detail_f.append(c)
        gco = set(map(str.lower, gt.get("co_garments") or []))
        pco = set(map(str.lower, pj.get("co_garments") or []))
        a, b, c = prf(pco, gco)
        co_p.append(a); co_r.append(b); co_f.append(c)

    summary = {
        "n_total": n,
        "n_inference_errors": err,
        "schema_validity": round(schema_ok / max(1, n - err), 4),
        "category_accuracy": round(cat_correct / max(1, schema_ok), 4) if schema_ok else 0.0,
        "detail_tags_precision": round(statistics.mean(detail_p), 4) if detail_p else 0.0,
        "detail_tags_recall": round(statistics.mean(detail_r), 4) if detail_p else 0.0,
        "detail_tags_f1": round(statistics.mean(detail_f), 4) if detail_p else 0.0,
        "co_garments_precision": round(statistics.mean(co_p), 4) if co_p else 0.0,
        "co_garments_recall": round(statistics.mean(co_r), 4) if co_p else 0.0,
        "co_garments_f1": round(statistics.mean(co_f), 4) if co_p else 0.0,
        "latency_p50_ms": round(statistics.median(latencies), 1) if latencies else 0,
        "latency_p95_ms": round(sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)], 1) if latencies else 0,
        "latency_mean_ms": round(statistics.mean(latencies), 1) if latencies else 0,
        "output_tokens_mean": round(statistics.mean(out_tokens), 1) if out_tokens else 0,
        "category_confusion_first_15": cat_confusion[:15],
    }
    Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
