"""Per-question parity between a PyTorch kev.benchmark run and a llama.cpp /v1/systemone run on the same data file.

Usage: python parity.py --torch rows.json --engine rows.jsonl --out parity.json
kev rows.json: one row per question, id "custom/<record index>", keys, p (aligned with keys), label (index).
engine rows.jsonl (systemone_client.py): one row per record with "i" and questions{name: {pred, label, ok, p}};
p is a dict over the same keys for choice/score and P(true) for noul.
Reports prediction agreement, accuracy of both sides and the probability gap (total variation distance).
Standard library only.
"""
import argparse
import json
from collections import defaultdict


def engine_probs(kind, keys, p):
    if kind == "noul":
        return [1.0 - float(p), float(p)]
    return [float(p[k]) for k in keys]


def argmax(xs):
    return max(range(len(xs)), key=lambda j: xs[j])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--torch", required=True)
    ap.add_argument("--engine", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    torch_rows = json.load(open(a.torch, encoding="utf-8"))
    engine = {}
    with open(a.engine, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                engine[int(r["i"])] = r

    stats = defaultdict(lambda: {"n": 0, "agree": 0, "torch_ok": 0, "engine_ok": 0, "only_torch_ok": 0,
                                 "only_engine_ok": 0, "tvd_sum": 0.0, "tvd_max": 0.0})
    missing = 0
    flips = []
    for row in torch_rows:
        i = int(str(row["id"]).rsplit("/", 1)[-1])
        q = engine.get(i, {}).get("questions", {}).get(row["question"])
        if q is None or "p" not in q:
            missing += 1
            continue
        keys, pt = row["keys"], [float(x) for x in row["p"]]
        pe = engine_probs(row["type"], keys, q["p"])
        label = int(row["label"])
        at, ae = argmax(pt), argmax(pe)
        tvd = 0.5 * sum(abs(x - y) for x, y in zip(pt, pe))
        for name in ("all", row["type"]):
            s = stats[name]
            s["n"] += 1
            s["agree"] += at == ae
            s["torch_ok"] += at == label
            s["engine_ok"] += ae == label
            s["only_torch_ok"] += (at == label) and (ae != label)
            s["only_engine_ok"] += (ae == label) and (at != label)
            s["tvd_sum"] += tvd
            s["tvd_max"] = max(s["tvd_max"], tvd)
        if at != ae:
            flips.append({"i": i, "question": row["question"], "torch": keys[at], "engine": keys[ae],
                          "label": keys[label], "torch_p": round(pt[at], 4), "engine_p": round(pe[ae], 4),
                          "tvd": round(tvd, 4)})

    out = {"torch": a.torch, "engine": a.engine, "missing": missing, "by_type": {}}
    for name, s in stats.items():
        n = s["n"] or 1
        # 6 decimals so that a report rounding to 0.1% does not round twice
        out["by_type"][name] = {
            "n": s["n"], "agree_count": s["agree"], "agreement": round(s["agree"] / n, 6),
            "torch_acc": round(s["torch_ok"] / n, 6), "engine_acc": round(s["engine_ok"] / n, 6),
            "only_torch_correct": s["only_torch_ok"], "only_engine_correct": s["only_engine_ok"],
            "mean_tvd": round(s["tvd_sum"] / n, 6), "max_tvd": round(s["tvd_max"], 6)}
    out["flips"] = sorted(flips, key=lambda x: -x["tvd"])
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({"missing": missing, **{k: v for k, v in out["by_type"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
