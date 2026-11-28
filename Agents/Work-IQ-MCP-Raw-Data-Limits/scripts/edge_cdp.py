"""Drive a separate Microsoft Edge automation profile over the Chrome DevTools Protocol (CDP).

The profile is a folder of its own, so the Edge windows you work in are not touched.
Needs: Windows, Microsoft Edge, Python 3.11+, `pip install websocket-client`.
"""
import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import websocket

EDGE_PATHS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
DEFAULT_PORT = 9351
DEFAULT_PROFILE = pathlib.Path(os.environ.get("LOCALAPPDATA", ".")) / "EdgeAutomation" / "workiq-demo"
LOGIN_HOSTS = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com")
_LOCAL = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 127.0.0.1 never goes through a proxy


def _get(port, path):
    with _LOCAL.open(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return json.load(r)


def version(port):
    try:
        return _get(port, "/json/version")
    except Exception:
        return None


def targets(port):
    return [t for t in _get(port, "/json/list") if t.get("type") == "page"]


class CDP:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=10)
        self.ws.settimeout(1.0)
        self.n = 0
        self.events = []

    def send(self, method, params=None, timeout=60):
        self.n += 1
        mid = self.n
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if m.get("id") == mid:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})
            if "method" in m:
                self.events.append(m)
        raise TimeoutError(method)

    def pump(self, seconds):
        """Collect CDP events for a while and hand them over."""
        end = time.time() + seconds
        while time.time() < end:
            try:
                m = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
            if "method" in m:
                self.events.append(m)
        ev, self.events = self.events, []
        return ev

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def page(port, tid):
    return CDP(f"ws://127.0.0.1:{port}/devtools/page/{tid}")


def start(port=DEFAULT_PORT, profile=DEFAULT_PROFILE, url="about:blank"):
    """Start the automation Edge if nothing listens on the port; return /json/version."""
    v = version(port)
    if v:
        return v
    edge = next((p for p in EDGE_PATHS if os.path.exists(p)), None)
    if not edge:
        raise SystemExit("EDGE_NOT_FOUND")
    pathlib.Path(profile).mkdir(parents=True, exist_ok=True)
    # A covered or minimized window, or a locked screen, makes Edge slow down and then freeze the timers of the page.
    subprocess.Popen([edge, f"--user-data-dir={profile}", f"--remote-debugging-port={port}",
                      "--no-first-run", "--no-default-browser-check", "--window-size=1500,1000",
                      "--disable-background-timer-throttling", "--disable-backgrounding-occluded-windows",
                      "--disable-renderer-backgrounding", "--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling", url])
    for _ in range(60):
        time.sleep(1)
        v = version(port)
        if v:
            return v
    raise SystemExit("EDGE_NOT_LISTENING")


def evaluate(port, tid, expr, await_promise=False, timeout=180):
    """Run JavaScript in the page and return its JSON value; raise on a JavaScript exception."""
    c = page(port, tid)
    try:
        r = c.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                        "awaitPromise": await_promise}, timeout=timeout)
    finally:
        c.close()
    if "exceptionDetails" in r:
        d = r["exceptionDetails"]
        raise RuntimeError("JS: " + str(d.get("exception", {}).get("description") or d.get("text")))
    return r.get("result", {}).get("value")


def wake(c):
    """Tell a page that it is active and focused, so that its timers run while the window is covered or the screen is locked."""
    done = []
    for method, params in (("Page.setWebLifecycleState", {"state": "active"}), ("Emulation.setFocusEmulationEnabled", {"enabled": True})):
        try:
            c.send(method, params, timeout=10)
            done.append(method)
        except Exception as e:
            done.append(f"{method} failed: {e}")
    return done


def screenshot(port, tid, path, full=False):
    c = page(port, tid)
    try:
        c.send("Page.bringToFront")
        r = c.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": bool(full)})
    finally:
        c.close()
    data = base64.b64decode(r["data"])
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(data)
    return len(data)


def find(port, part):
    """Page whose host contains `part`; only then a page whose URL does (a sign-in URL carries the caller's host as redirect_uri)."""
    pages = targets(port)
    by_host = next((t for t in pages if part in (urllib.parse.urlparse(t.get("url", "")).hostname or "")), None)
    return by_host or next((t for t in pages if part in t.get("url", "")), None)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start", help="start the automation Edge and open a URL")
    s.add_argument("--url", default="about:blank")
    s.add_argument("--profile", default=str(DEFAULT_PROFILE))
    sub.add_parser("targets", help="list the open pages")
    e = sub.add_parser("eval", help="run a JavaScript file in a page")
    e.add_argument("--match", required=True, help="part of the page URL")
    e.add_argument("--file", required=True)
    e.add_argument("--await", dest="await_promise", action="store_true")
    e.add_argument("--arg", help="value that replaces __ARG__ in the file, passed as a JSON string")
    e.add_argument("--out")
    h = sub.add_parser("shot", help="save a PNG of a page")
    h.add_argument("--match", required=True)
    h.add_argument("--out", required=True)
    h.add_argument("--full", action="store_true")
    w = sub.add_parser("wake", help="unfreeze a page whose window is covered, and time two 300 ms timers in it")
    w.add_argument("--match", required=True)
    n = sub.add_parser("open", help="open a URL in a new tab")
    n.add_argument("--url", required=True)
    sub.add_parser("close", help="close the automation Edge")
    a = ap.parse_args()

    if a.cmd == "start":
        v = start(a.port, a.profile, a.url)
        print("EDGE", v.get("Browser"), "port", a.port, "profile", a.profile)
        return 0
    if not version(a.port):
        print("EDGE_NOT_RUNNING on port", a.port)
        return 2
    if a.cmd == "targets":
        for t in targets(a.port):
            print(t["id"], "|", t.get("url", "")[:140], "|", t.get("title", "")[:60])
        return 0
    if a.cmd == "open":
        b = CDP(version(a.port)["webSocketDebuggerUrl"])
        try:
            print(b.send("Target.createTarget", {"url": a.url})["targetId"])
        finally:
            b.close()
        return 0
    if a.cmd == "close":
        b = CDP(version(a.port)["webSocketDebuggerUrl"])
        try:
            b.send("Browser.close")
        except Exception:
            pass
        print("EDGE_CLOSED")
        return 0
    t = find(a.port, a.match)
    if not t:
        print("NO_PAGE matching", a.match)
        return 3
    if a.cmd == "shot":
        print("PNG", a.out, screenshot(a.port, t["id"], a.out, a.full), "bytes")
        return 0
    if a.cmd == "wake":
        c = page(a.port, t["id"])
        try:
            print("sent:", wake(c))
            probe = (pathlib.Path(__file__).resolve().parent / "js" / "timer_probe.js").read_text(encoding="utf-8")
            r = c.send("Runtime.evaluate", {"expression": probe, "returnByValue": True, "awaitPromise": True}, timeout=30)
            print(json.dumps(r.get("result", {}).get("value"), ensure_ascii=False))
        except TimeoutError:
            print("TIMERS_FROZEN: two 300 ms timers did not finish within 30 s")
            return 4
        finally:
            c.close()
        return 0
    expr = pathlib.Path(a.file).read_text(encoding="utf-8")
    if a.arg is not None:
        expr = expr.replace("__ARG__", json.dumps(a.arg))
    value = evaluate(a.port, t["id"], expr, a.await_promise)
    text = json.dumps(value, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
        print("saved", a.out, len(text), "chars")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
