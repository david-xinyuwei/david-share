"""Show how results[].markdown of a saved retrieve answer is laid out, with every word masked.

Letters become "a", digits "9", CJK characters "字". Markdown marks, punctuation and line breaks stay,
and so does a short label in front of a colon at the start of a line (for example "Subject:").
"""
import argparse
import json
import pathlib
import re
import sys

RETRIEVAL = "application/vnd.ms-workiq.retrieval"
LABEL = re.compile(r"^(\W*)([A-Za-z][A-Za-z ]{1,18})(:)")


def mask(text):
    out = []
    for line in text.splitlines():
        m = LABEL.match(line)
        head, rest = (m.group(0), line[m.end():]) if m else ("", line)
        rest = re.sub(r"[A-Za-z]", "a", rest)
        rest = re.sub(r"\d", "9", rest)
        rest = re.sub(r"[\u3400-\u9fff]", "字", rest)
        out.append(head + rest)
    return "\n".join(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("record", help="a retrieve record from <out>/raw")
    ap.add_argument("--head", type=int, default=500, help="characters shown from the start of each markdown")
    ap.add_argument("--tail", type=int, default=160, help="characters shown from its end")
    a = ap.parse_args()
    rec = json.loads(pathlib.Path(a.record).read_text(encoding="utf-8"))
    body = ((rec.get("response") or {}).get("result") or {}).get("structuredContent", {}).get(RETRIEVAL) or {}
    for n, x in enumerate(body.get("results") or [], 1):
        md = x.get("markdown") or ""
        print(f"--- result {n}: {x.get('entityType')}, {len(md)} characters, {md.count(chr(10)) + 1} lines")
        print(mask(md[:a.head]))
        if len(md) > a.head + a.tail:
            print(f"   [... {len(md) - a.head - a.tail} characters ...]")
            print(mask(md[-a.tail:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
