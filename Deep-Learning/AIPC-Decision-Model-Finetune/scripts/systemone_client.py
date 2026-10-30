#!/usr/bin/env python3
"""Send a business request or score labelled records against a /v1/systemone endpoint.

  python systemone_client.py --url http://127.0.0.1:8080/v1/systemone --request request.json --out out/decision
  python systemone_client.py --url http://127.0.0.1:8080/v1/systemone --data test_support.jsonl --out out/support
Single requests write result.json without grading or warm-up. Batch scoring writes rows.jsonl and summary.json.
--concurrency N (default 1, one request at a time) keeps N requests in flight from a thread pool; each row's
latency_ms is still measured at the client from send to full answer, so it includes server-side queueing.
Standard library only.
"""
import argparse
import hashlib
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


def request_body(record):
    if "state" not in record or not isinstance(record.get("questions"), dict) or not record["questions"]:
        raise ValueError("A request needs state and at least one question")
    return {"state": record["state"],
            "questions": {question_id: {key: value for key, value in question.items() if key != "label"}
                          for question_id, question in record["questions"].items()}}


def ask(url, record):
    body = request_body(record)
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                                     headers={"content-type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        data = json.loads(response.read())
    return data, (time.perf_counter() - started) * 1000


def single_request(url, request_path, out):
    source = Path(request_path).read_bytes()
    body = request_body(json.loads(source.decode("utf-8-sig")))
    output = Path(out)
    output.mkdir(parents=True, exist_ok=False)
    response, elapsed_ms = ask(url, body)
    answers = response.get("answers", {})
    if not isinstance(answers, dict) or any(question_id not in answers for question_id in body["questions"]):
        raise ValueError("The endpoint did not return an answer for every requested question")
    for question_id, question in body["questions"].items():
        predicted(question, answers[question_id])
    result = {"captured_utc": datetime.now(timezone.utc).isoformat(), "url": url,
              "input_sha256": hashlib.sha256(source).hexdigest(), "request": body,
              "client_latency_ms": round(elapsed_ms, 1), "response": response}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


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
    inputs = ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--data", help="labelled JSONL records for batch scoring")
    inputs.add_argument("--request", help="one JSON business request; labels are not sent")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--warmup", type=int, default=2, help="requests sent first and excluded from latency")
    ap.add_argument("--concurrency", type=int, default=1, help="requests kept in flight at once (1 = sequential)")
    a = ap.parse_args()
    if a.concurrency < 1:
        ap.error("--concurrency must be at least 1")
    if a.request:
        single_request(a.url, a.request, a.out)
        return
    recs = [json.loads(l) for l in Path(a.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.limit:
        recs = recs[:a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    for rec in recs[:a.warmup]:
        ask(a.url, rec)

    def attempt(item):
        i, rec = item
        try:
            return i, rec, ask(a.url, rec), None
        except Exception as e:  # noqa: BLE001 - one failed request is counted, not fatal
            return i, rec, None, str(e)[:300]

    wall_started = time.perf_counter()
    if a.concurrency == 1:
        outcomes = map(attempt, enumerate(recs))
    else:
        pool = ThreadPoolExecutor(max_workers=a.concurrency)
        outcomes = pool.map(attempt, enumerate(recs))  # results come back in record order
    rows, lat, by_type, errors = [], [], {}, 0
    with (out / "rows.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for i, rec, answer, error in outcomes:
            if error is not None:
                errors += 1
                f.write(json.dumps({"i": i, "error": error}) + "\n")
                continue
            data, ms = answer
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
    wall_s = time.perf_counter() - wall_started
    if a.concurrency > 1:
        pool.shutdown()
    qs = sum(v[1] for v in by_type.values())
    lat_sorted = sorted(lat)
    summary = {"url": a.url, "data": a.data, "records": len(recs), "errors": errors, "questions": qs,
               "accuracy": round(sum(v[0] for v in by_type.values()) / qs, 4) if qs else None,
               "by_type": {k: round(v[0] / v[1], 4) for k, v in by_type.items()},
               "latency_ms": {"n": len(lat), "p50": round(statistics.median(lat), 1) if lat else None,
                              "p90": round(lat_sorted[int(0.9 * (len(lat) - 1))], 1) if lat else None,
                              "mean": round(statistics.fmean(lat), 1) if lat else None}}
    if a.concurrency > 1:  # sequential runs keep the historical summary shape
        summary["concurrency"] = a.concurrency
        summary["wall_seconds"] = round(wall_s, 1)  # warm-up excluded; all scored requests, send of the first to answer of the last
        summary["requests_per_second"] = round(len(lat) / wall_s, 3) if wall_s and lat else None
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
