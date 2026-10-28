#!/usr/bin/env python3
"""Score labelled Kev records against any /v1/systemone endpoint (e.g. llama-server on the laptop) and time each request.

  python systemone_client.py --url http://127.0.0.1:8080/v1/systemone --data test_support.jsonl --out out/support
Writes <out>/rows.jsonl (answer, label, latency per record) and <out>/summary.json. Standard library only.
"""
import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path


def predicted(q, ans):
    if q["type"] == "choice":
        return ans["choice"]
    if q["type"] == "noul":
        return ans["noul"] >= 0.5
    probs = ans["probabilities"]
    return int(max(probs, key=lambda k: probs[k]))


def correct(q, pred):
    return pred == q["label"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--warmup", type=int, default=2, help="requests sent first and excluded from latency")
    a = ap.parse_args()
    recs = [json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.limit:
        recs = recs[:a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    def ask(rec):
        body = {"state": rec["state"], "questions": {qid: {k: v for k, v in q.items() if k != "label"}
                                                     for qid, q in rec["questions"].items()}}
        req = urllib.request.Request(a.url, data=json.dumps(body, ensure_ascii=False).encode(), method="POST",
                                     headers={"content-type": "application/json"})
        t = time.perf_counter()
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read())
        return data, (time.perf_counter() - t) * 1000

    for rec in recs[:a.warmup]:
        ask(rec)
    rows, lat, by_type, errors = [], [], {}, 0
    with (out / "rows.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for i, rec in enumerate(recs):
            try:
                data, ms = ask(rec)
            except Exception as e:  # noqa: BLE001 - one failed request is counted, not fatal
                errors += 1
                f.write(json.dumps({"i": i, "error": str(e)[:300]}) + "\n")
                continue
            lat.append(ms)
            row = {"i": i, "case": rec.get("_meta", {}).get("case"), "latency_ms": round(ms, 1),
                   "input_tokens": (data.get("usage") or {}).get("input_tokens"), "questions": {}}
            for qid, q in rec["questions"].items():
                ans = data["answers"][qid]
                pred = predicted(q, ans)
                ok = correct(q, pred)
                t = by_type.setdefault(q["type"], [0, 0])
                t[0] += ok
                t[1] += 1
                row["questions"][qid] = {"pred": pred, "label": q["label"], "ok": ok,
                                         "p": ans.get("probabilities", ans.get("noul"))}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    qs = sum(v[1] for v in by_type.values())
    lat_sorted = sorted(lat)
    summary = {"url": a.url, "data": a.data, "records": len(recs), "errors": errors, "questions": qs,
               "accuracy": round(sum(v[0] for v in by_type.values()) / qs, 4) if qs else None,
               "by_type": {k: round(v[0] / v[1], 4) for k, v in by_type.items()},
               "latency_ms": {"n": len(lat), "p50": round(statistics.median(lat), 1) if lat else None,
                              "p90": round(lat_sorted[int(0.9 * (len(lat) - 1))], 1) if lat else None,
                              "mean": round(statistics.fmean(lat), 1) if lat else None}}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
