"""Print the tools of a recorded tools/list exchange: name, parameters, and the limits their descriptions state."""
import argparse
import json
import pathlib
import re
import sys

LIMIT_WORDS = re.compile(r"[^.;]*\b(\d[\d,.]*\s?(MB|KB|GB|bytes|items|results|messages|characters|chars)|\$top|\$skip|limit|cap(ped)?|maximum|max\b|at most|up to|truncat|page|nextLink)[^.;]*[.;]?", re.I)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("record", help="raw record of tools/list (call_once.py --list-tools)")
    ap.add_argument("--tools", nargs="*", help="only these tools")
    ap.add_argument("--full", action="store_true", help="print whole descriptions")
    ap.add_argument("--save", help="write the tools array (service schema, no tenant data, no request ID) to this file")
    a = ap.parse_args()

    rec = json.loads(pathlib.Path(a.record).read_text(encoding="utf-8"))
    tools = rec["response"]["result"]["tools"]
    print(f"{len(tools)} tools, recorded {rec['sent_utc']}, request-id {rec['headers'].get('request-id')}")
    for t in tools:
        if a.tools and t["name"] not in a.tools:
            continue
        props = t.get("inputSchema", {}).get("properties", {})
        required = t.get("inputSchema", {}).get("required", [])
        print(f"\n== {t['name']}  ({len(t.get('description', ''))} chars of description)")
        if a.full:
            print(t.get("description", ""))
        for name, p in props.items():
            kind = p.get("type")
            extra = f" default={p['default']!r}" if "default" in p else ""
            star = "*" if name in required else ""
            print(f"  - {name}{star}: {kind}{extra} | {p.get('description', '')[: (2000 if a.full else 260)]}")
        text = t.get("description", "") + " " + " ".join(p.get("description", "") for p in props.values())
        hits = sorted({m.group(0).strip() for m in LIMIT_WORDS.finditer(text)})
        for h in hits:
            print("  limit wording:", h[:300])
    if a.save:
        out = pathlib.Path(a.save)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"recorded_utc": rec["sent_utc"], "tools": tools}, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8", newline="\n")
        print("\nsaved", out)


if __name__ == "__main__":
    main()
