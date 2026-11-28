"""Print the summaries of a run as one compact line per call."""
import argparse
import json
import pathlib
import sys


def brief(row):
    if "check" in row:
        return f"  CHECK {row['check']}: {row['value']}"
    if "ui_error" in row:
        return f"{row['case']:<34} UI_ERROR {row['ui_error']}"
    res = row.get("result")
    if isinstance(res, list):
        if len(res) > 3:
            codes = sorted({str(x.get("statusCode")) for x in res})
            parts = [f"{len(res)} results, statusCode {'/'.join(codes)}"]
        else:
            parts = []
            for x in res:
                p = f"status {x.get('statusCode')}"
                if "count" in x:
                    p += f", {x['count']} items"
                if "nextLink" in x:
                    p += ", nextLink(" + ",".join(f"{k}={v}" for k, v in x["nextLink"].items() if k in ("$top", "$skip", "$skiptoken")) + ")"
                if "error" in x:
                    p += f", error {json.dumps(x['error'], ensure_ascii=False)[:260]}"
                for k in x:
                    if k not in ("statusCode", "count", "nextLink", "error"):
                        p += f", {k}={str(x[k])[:160]}"
                parts.append(p)
        result = " | ".join(parts)
    elif isinstance(res, dict) and "markdown_chars_each" in res:  # a retrieve answer
        kinds = {}
        for kind in res["entityType_each"]:
            kinds[kind] = kinds.get(kind, 0) + 1
        result = (f"{res['results']} results, markdown chars {res['markdown_chars_each']} (total {res['markdown_chars_total']}), "
                  f"types {kinds}, encrypted {res['encrypted_each'].count(True)}, months {res['months']}, stopped {res['stoppedReason']}, "
                  f"searchMetadata({res.get('searchMetadata_is')}) {json.dumps(res['searchMetadata'], ensure_ascii=False)}"
                  + (f", other keys {res['other_keys']}" if res["other_keys"] else "")
                  + (f", structuredContent also has {res['structuredContent_other_keys']}" if res.get("structuredContent_other_keys") else ""))
    else:
        result = json.dumps(res, ensure_ascii=False)[:420] if res is not None else ""
    text = (" TEXT " + " ".join(row.get("text", []))[:420]) if row.get("text") else ""
    head = (" BODY " + row["body_head"][:200]) if row.get("body_head") else ""
    return (f"{row['case']:<34} HTTP {row.get('http_status')} {row.get('ms')} ms {row.get('response_bytes')} B "
            f"err={row.get('is_error')} typed={row.get('sent_as_typed')} :: {result}{text}{head}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", help="evidence folder of the run")
    ap.add_argument("stages", nargs="+")
    a = ap.parse_args()
    for stage in a.stages:
        rows = json.loads((pathlib.Path(a.out) / "summary" / f"{stage}.json").read_text(encoding="utf-8"))
        print(f"== {stage}: {sum('case' in r for r in rows)} calls")
        for row in rows:
            print(brief(row))


if __name__ == "__main__":
    main()
