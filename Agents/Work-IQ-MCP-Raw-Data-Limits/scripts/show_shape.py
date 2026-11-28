"""Print the structure of a saved record (key names, counts, lengths) without its text."""
import argparse
import json
import pathlib
import sys

from shape import shape


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("record", help="a file from <out>/raw")
    ap.add_argument("--meta", action="store_true", help="show result._meta as well")
    a = ap.parse_args()
    rec = json.loads(pathlib.Path(a.record).read_text(encoding="utf-8"))
    result = (rec.get("response") or {}).get("result") or {}
    print("isError:", result.get("isError"), "| HTTP", rec.get("http_status"), "|", rec.get("response_bytes"), "bytes |", rec.get("ms_to_last_byte"), "ms")
    print("content:", json.dumps(shape(result.get("content")), ensure_ascii=False)[:600])
    print("structuredContent:", json.dumps(shape(result.get("structuredContent")), ensure_ascii=False, indent=1))
    if a.meta:
        print("_meta:", json.dumps(result.get("_meta"), ensure_ascii=False)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
