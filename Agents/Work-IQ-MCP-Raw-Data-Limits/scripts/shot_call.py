"""Send one tool call through the Interactive Demo page and save a screenshot of the page showing request and response.

Use it for calls whose answer holds no private content (an error text, a count of IDs).
"""
import argparse
import json
import pathlib
import sys
import time

import demo_runner as dr
import edge_cdp as ec

SCROLL_JS = r"""(() => {
  const col = document.querySelector('[data-testid="workiq-remote-detail-column"]');
  if (!col) return 'no detail column';
  const head = [...col.querySelectorAll('h1,h2,h3,h4,div,span')].find(e => e.children.length === 0 && /^Request$/.test((e.innerText || '').trim()));
  if (head) head.scrollIntoView({block: 'start'});
  return head ? 'scrolled to Request' : 'no Request heading';
})()"""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tool", required=True)
    ap.add_argument("--args-file", required=True, help="JSON file with the tool arguments")
    ap.add_argument("--png", required=True, help="screenshot to write")
    ap.add_argument("--case", help="also save the network record under this name")
    ap.add_argument("--out", help="folder for the network record")
    ap.add_argument("--wait", type=float, default=2.0, help="seconds between the answer and the screenshot")
    ap.add_argument("--height", type=int, default=1900, help="height of the page in CSS pixels while the screenshot is taken")
    ap.add_argument("--no-call", action="store_true", help="send nothing: take the screenshot of the page as it is")
    ap.add_argument("--redact", nargs="*", default=[r"AAMk[A-Za-z0-9_\-=]{20,}", r"\b01[A-Z0-9]{30,}\b", r"19:[A-Za-z0-9_\-@.]{20,}",
                                                    r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}", r'(?<=W/\\")[^\\"]{16,}'],
                    help="regular expressions of the strings to cover in the public copy (default: mail, drive item and chat IDs, "
                         "every GUID, which covers the user's object ID and the request IDs of the service, and ETags)")
    a = ap.parse_args()
    args = json.loads(pathlib.Path(a.args_file).read_text(encoding="utf-8"))
    s = dr.Session()
    rec = None
    try:
        if not a.no_call:
            rec = s.call(a.tool, args)
            if "ui_error" in rec:
                print("UI_ERROR:", rec["ui_error"])
                return 3
            time.sleep(a.wait)
        # The page keeps request and response in a column that scrolls inside the window: a taller window shows both.
        s.c.send("Emulation.setDeviceMetricsOverride", {"width": 1500, "height": a.height, "deviceScaleFactor": 1.25, "mobile": False})
        time.sleep(1.0)
        print(s.js(SCROLL_JS))
        time.sleep(0.5)
        rects = s.js((dr.JS_DIR / "redact_rects.js").read_text(encoding="utf-8").replace("__ARG__", json.dumps(a.redact)))
        shot = s.c.send("Page.captureScreenshot", {"format": "png"})
        s.c.send("Emulation.clearDeviceMetricsOverride")
    finally:
        s.close()
    import base64
    png = pathlib.Path(a.png)
    png.parent.mkdir(parents=True, exist_ok=True)
    png.write_bytes(base64.b64decode(shot["data"]))
    png.with_suffix(".rects.json").write_text(json.dumps(rects, indent=1), encoding="utf-8")
    print("strings to cover in the public copy:", len(rects.get("rects", [])))
    if rec and a.case and a.out:
        dr.save(rec, a.out, a.case)
    if rec:
        print(f"HTTP {rec['http_status']}  {rec['response_bytes']} bytes  request-id {rec['headers'].get('request-id')}  sent as typed: {rec['sent_as_typed']}")
    print("PNG", png, png.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
