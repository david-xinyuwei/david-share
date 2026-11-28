"""From the saved summary of the retrieve stage: which fields does results[].markdown carry per result type,
how long is each, and what does the service write into truncationInfo."""
import argparse
import collections
import json
import pathlib
import sys


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", help="evidence folder of the run")
    ap.add_argument("--json", help="write the table to this file as JSON")
    a = ap.parse_args()
    rows = json.loads((pathlib.Path(a.out) / "summary" / "retrieve.json").read_text(encoding="utf-8"))
    per_type = collections.defaultdict(lambda: {"results": 0, "markdown_chars": [], "fields": collections.defaultdict(list), "truncationInfo": collections.Counter()})
    for row in rows:
        res = row.get("result")
        if not isinstance(res, dict) or "markdown_fields_each" not in res:
            continue
        for kind, chars, fields in zip(res["entityType_each"], res["markdown_chars_each"], res["markdown_fields_each"]):
            t = per_type[kind]
            t["results"] += 1
            t["markdown_chars"].append(chars)
            t["truncationInfo"][fields.get("truncationInfo", "(no truncationInfo field)")] += 1
            for name, size in fields.items():
                if name != "truncationInfo":
                    t["fields"][name].append(size)
    table = {}
    for kind, t in sorted(per_type.items()):
        table[kind] = {"results": t["results"], "markdown_chars_min": min(t["markdown_chars"]), "markdown_chars_max": max(t["markdown_chars"]),
                       "truncationInfo": dict(t["truncationInfo"]),
                       "fields": {name: {"in_results": len(sizes), "chars_min": min(sizes), "chars_max": max(sizes)} for name, sizes in sorted(t["fields"].items())}}
        print(f"== {kind}: {t['results']} results, markdown {min(t['markdown_chars']):,} to {max(t['markdown_chars']):,} characters")
        print("   truncationInfo:", dict(t["truncationInfo"]))
        for name, sizes in sorted(t["fields"].items(), key=lambda kv: -max(kv[1])):
            print(f"   {name:<24} in {len(sizes):>2} results, {min(sizes):>6,} to {max(sizes):>6,} characters")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
