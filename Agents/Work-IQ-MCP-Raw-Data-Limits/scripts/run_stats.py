"""Count the calls of a run from its saved records: how many, over which time, how fast, which status codes, any throttling."""
import argparse
import collections
import datetime
import json
import pathlib
import re
import sys

THROTTLED = re.compile(r"\b429\b|too many requests|throttl", re.I)


def reports_throttling(result):
    """True when a tool result reports throttling: a fetch result with status 429, or an error text that names it.
    Only error texts are read, never the content of a successful answer."""
    texts = [c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text"] if result.get("isError") else []
    structured = result.get("structuredContent")
    for x in (structured.get("results") if isinstance(structured, dict) and isinstance(structured.get("results"), list) else []):
        if isinstance(x, dict):
            if x.get("statusCode") == 429:
                return True
            if x.get("error"):
                texts.append(json.dumps(x["error"], ensure_ascii=False))
    return any(THROTTLED.search(t) for t in texts)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", help="evidence folder of the run")
    ap.add_argument("--json", help="write the numbers to this file")
    a = ap.parse_args()
    calls, header_names = [], collections.Counter()
    for f in sorted((pathlib.Path(a.out) / "raw").glob("*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if not rec.get("sent_utc") or rec.get("tool") in (None, "(tools/list)"):
            continue
        header_names.update(rec.get("headers") or {})
        result = (rec.get("response") or {}).get("result") or {}
        calls.append({"t": datetime.datetime.fromisoformat(rec["sent_utc"].replace("Z", "+00:00")), "tool": rec["tool"], "http": rec.get("http_status"),
                      "ms": rec.get("ms_to_last_byte") or rec.get("ms_to_headers"), "bytes": rec.get("response_bytes"),
                      "is_error": bool(result.get("isError")) or "error" in (rec.get("response") or {}),
                      "throttled": reports_throttling(result),
                      "retry_after": (rec.get("headers") or {}).get("retry-after")})
    calls.sort(key=lambda c: c["t"])
    if not calls:
        print("no tools/call records")
        return 1
    busiest, j = 0, 0
    for i, c in enumerate(calls):  # largest number of calls inside any 60 seconds
        while c["t"] - calls[j]["t"] > datetime.timedelta(seconds=60):
            j += 1
        busiest = max(busiest, i - j + 1)
    per_tool = {}
    for tool in sorted({c["tool"] for c in calls}):
        ms = sorted(c["ms"] for c in calls if c["tool"] == tool and c["ms"] is not None)
        per_tool[tool] = {"calls": sum(c["tool"] == tool for c in calls), "tool_errors": sum(c["tool"] == tool and c["is_error"] for c in calls),
                          "ms_median": ms[len(ms) // 2] if ms else None, "ms_max": ms[-1] if ms else None,
                          "largest_answer_bytes": max(c["bytes"] or 0 for c in calls if c["tool"] == tool)}
    stats = {"tools_call_records": len(calls), "first_utc": calls[0]["t"].isoformat(), "last_utc": calls[-1]["t"].isoformat(),
             "minutes": round((calls[-1]["t"] - calls[0]["t"]).total_seconds() / 60, 1),
             "http_status": dict(collections.Counter(str(c["http"]) for c in calls)),
             "http_429": sum(c["http"] == 429 for c in calls), "answers_with_retry_after_header": sum(c["retry_after"] is not None for c in calls),
             "tool_results_that_report_throttling": sum(c["throttled"] for c in calls),
             "most_calls_in_60_seconds": busiest, "per_tool": per_tool, "response_headers_recorded": sorted(header_names)}
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
