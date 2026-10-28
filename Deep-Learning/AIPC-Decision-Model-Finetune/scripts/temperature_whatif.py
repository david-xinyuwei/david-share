"""Re-score saved kev.benchmark rows at other softmax temperatures, without re-running the model.

kev rows store the logits already divided by the serving temperature (p == softmax(logits)), plus
inference_temperature, so the raw logits are logits * inference_temperature and p(T') = softmax(raw / T').
Argmax (accuracy) never changes; Brier and ECE do.
Usage: python temperature_whatif.py --rows a/rows.json b/rows.json --temps 1.26 2.351 [--out whatif.json]
Standard library only.
"""
import argparse
import json
import math
import sys


def softmax(xs):
    m = max(xs)
    e = [math.exp(x - m) for x in xs]
    s = sum(e)
    return [x / s for x in e]


def score(rows, temp):
    brier, n, bins = 0.0, 0, [[0, 0.0, 0] for _ in range(10)]  # count, confidence sum, correct
    for r in rows:
        raw = [float(x) * float(r["inference_temperature"]) for x in r["logits"]]
        p = softmax([x / temp for x in raw])
        label = int(r["label"])
        pred = max(range(len(p)), key=lambda j: p[j])
        brier += sum((x - (1.0 if j == label else 0.0)) ** 2 for j, x in enumerate(p))
        conf = p[pred]
        b = bins[min(int(conf * 10), 9)]
        b[0] += 1
        b[1] += conf
        b[2] += pred == label
        n += 1
    ece = sum(abs(b[1] - b[2]) for b in bins if b[0]) / n
    acc = sum(b[2] for b in bins) / n
    return {"n": n, "acc": round(acc, 4), "brier": round(brier / n, 4), "ece_10bin": round(ece, 4)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="+", required=True)
    ap.add_argument("--temps", nargs="+", type=float, required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--variant", default="clean", help="score only rows of this variant (kev's headline metrics use 'clean'); '' = all")
    a = ap.parse_args()
    out = {}
    for path in a.rows:
        rows = [r for r in json.load(open(path, encoding="utf-8")) if not a.variant or r.get("variant", "clean") == a.variant]
        served = rows[0].get("inference_temperature")
        out[path] = {"served_temperature": served, "at": {str(t): score(rows, t) for t in a.temps}}
        print(path, json.dumps(out[path], ensure_ascii=False))
    if a.out:
        json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
