"""Send one Work IQ MCP tool call through the Interactive Demo page and save the network record.

Examples:
  python scripts/call_once.py --list-tools --case tools_list --out results/raw
  python scripts/call_once.py --tool fetch --args-file cases/fetch_me.json --case fetch_me --out results/raw
The console shows structure and sizes only; the full answer is in the saved file.
"""
import argparse
import json
import pathlib
import sys

import demo_runner as dr
from shape import shape, tool_result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tool")
    ap.add_argument("--args-file", help="JSON file with the tool arguments")
    ap.add_argument("--list-tools", action="store_true", help="reload the page and record its tools/list exchange")
    ap.add_argument("--case", required=True, help="name of the saved record")
    ap.add_argument("--out", required=True, help="folder for the record")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    s = dr.Session()
    try:
        print("account shown by the page:", s.account() or "(none: Demo mode?)")
        if a.list_tools:
            rec = s.reload_and_list_tools()
            if rec is None:
                print("NO tools/list seen after the reload")
                return 2
            rec["tool"], rec["arguments"] = "(tools/list)", {}
        else:
            args = json.loads(pathlib.Path(a.args_file).read_text(encoding="utf-8"))
            print(f"tools/call {a.tool} {json.dumps(args, ensure_ascii=False)}")
            rec = s.call(a.tool, args, a.timeout)
    finally:
        s.close()

    path = dr.save(rec, a.out, a.case)
    if "ui_error" in rec:
        print("UI_ERROR:", rec["ui_error"])
        print("saved", path)
        return 3
    print(f"HTTP {rec.get('http_status')}  headers after {rec.get('ms_to_headers')} ms, last byte after {rec.get('ms_to_last_byte')} ms  "
          f"{rec.get('response_bytes')} bytes  request-id {rec.get('headers', {}).get('request-id', '')}  "
          f"sent as typed: {rec.get('sent_as_typed')}")
    if a.list_tools:
        tools = (rec.get("response") or {}).get("result", {}).get("tools", [])
        print(len(tools), "tools:", ", ".join(t["name"] for t in tools))
    else:
        is_error, texts, structured = tool_result(rec.get("response"))
        print("isError:", is_error, "| text parts:", [len(t) for t in texts], "chars")
        if is_error:
            for t in texts:
                print("  error text:", t[:600])
        if structured is not None:
            print("structuredContent:", json.dumps(shape(structured), ensure_ascii=False)[:1500])
    print("saved", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
