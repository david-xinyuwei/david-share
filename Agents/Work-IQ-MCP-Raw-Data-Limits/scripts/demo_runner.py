"""Call Work IQ MCP tools through the Interactive Demo page and record each exchange.

The request is typed into the page's "Edit as JSON" box and sent with its "Call tool" button.
A recorder installed in the page (js/fetch_recorder.js) keeps the request body, HTTP status, selected
headers, timing and the unmodified response stream of every request the page sends to the MCP endpoint.
The Authorization header is never read or stored.
"""
import json
import pathlib
import time

import edge_cdp as ec

DEMO_HOST = "interactivedemo.microsoft.com"
JS_DIR = pathlib.Path(__file__).resolve().parent / "js"

UI_CALL_JS = r"""(async (tool, argsText) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const col = () => document.querySelector('[data-testid="workiq-remote-detail-column"]');
  const editor = () => col() && col().querySelector('textarea[aria-label="Tool arguments as JSON"]');
  const item = document.querySelector(`[data-testid="tool-item-${tool}"]`);
  if (!item) return {ok: false, why: 'no tool named ' + tool + ' in the page'};
  item.click();
  await sleep(500);
  if (!editor()) {
    const sw = col().querySelector('input[role="switch"]');
    if (!sw) return {ok: false, why: 'no "Edit as JSON" switch'};
    sw.click();
    await sleep(500);
  }
  if (!editor()) return {ok: false, why: 'no JSON editor'};
  // React keeps its own copy of the value: set it through the native setter, then tell React with an input event.
  Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(editor(), argsText);
  editor().dispatchEvent(new Event('input', {bubbles: true}));
  await sleep(400);
  const shown = editor().value;
  if (shown !== argsText) return {ok: false, why: 'the page did not take the JSON', shown};
  const btn = [...col().querySelectorAll('button')].find(b => /^Call tool$/i.test(b.innerText.trim()));
  if (!btn) return {ok: false, why: 'no "Call tool" button'};
  if (btn.disabled) return {ok: false, why: '"Call tool" is disabled'};
  btn.click();
  return {ok: true};
})(%s, %s)"""

# Index and state of the newest recorded request whose JSON-RPC method is %s, at or after log position %d.
FIND_JS = r"""((method, from) => {
  const log = window.__mcpLog || [];
  for (let i = log.length - 1; i >= from; i--) {
    const e = log[i];
    if (e.body && e.body.includes('"method":"' + method + '"')) {
      return {i, done: e.done, status: e.status === undefined ? null : e.status, chars: e.chunks.reduce((n, c) => n + c.length, 0),
              tail: e.chunks.join('').slice(-300), networkError: e.networkError || null};
    }
  }
  return null;
})(%s, %d)"""
TAKE_JS = r"""(i => {
  const e = window.__mcpLog[i];
  return {sentUtc: e.sentUtc, requestText: e.body, status: e.status === undefined ? null : e.status, headers: e.headers || {},
          msToHeaders: e.msToHeaders === undefined ? null : e.msToHeaders, msToLastByte: e.msToLastByte === undefined ? null : e.msToLastByte,
          streamEnd: e.streamEnd || null, networkError: e.networkError || null, done: e.done, responseText: e.chunks.join('')};
})(%d)"""


def parse_reply(text):
    """Return the JSON-RPC message of an MCP reply sent as plain JSON or as a text/event-stream body; None while incomplete."""
    text = (text or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    last = None
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                last = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                pass
    return last


class Session:
    def __init__(self, port=ec.DEFAULT_PORT):
        if not ec.version(port):
            raise SystemExit(f"EDGE_NOT_RUNNING on port {port}: run scripts/edge_cdp.py start first")
        t = ec.find(port, DEMO_HOST)
        if not t:
            raise SystemExit("NO_DEMO_PAGE: start the automation Edge on the Interactive Demo first")
        self.c = ec.page(port, t["id"])
        recorder = (JS_DIR / "fetch_recorder.js").read_text(encoding="utf-8")
        self.c.send("Page.enable")
        ec.wake(self.c)
        self.c.send("Page.addScriptToEvaluateOnNewDocument", {"source": recorder})  # survives a reload
        self.recorder = self.js(recorder)

    def close(self):
        self.c.close()

    def js(self, expr, timeout=120):
        r = self.c.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, timeout=timeout)
        if "exceptionDetails" in r:
            d = r["exceptionDetails"]
            raise RuntimeError("JS: " + str(d.get("exception", {}).get("description") or d.get("text")))
        return r.get("result", {}).get("value")

    def account(self):
        return self.js("(document.querySelector('[data-testid=\"workiq-account-name\"]') || {}).innerText || ''")

    def _log_size(self):
        return self.js("(window.__mcpLog || []).length") or 0

    def _wait(self, method, start, timeout):
        """Wait until a recorded request with this JSON-RPC method holds a complete reply (or its stream ended)."""
        end, seen = time.time() + timeout, None
        while time.time() < end:
            time.sleep(0.4)
            try:
                seen = self.js(FIND_JS % (json.dumps(method), start))
            except Exception:
                continue  # the page is reloading
            if not seen:
                continue
            if seen["networkError"] or seen["done"]:
                return self._take(seen["i"])
            # The server may keep the event stream open after its answer: a stream that ends in a complete message is finished.
            if seen["chars"] and seen["tail"].rstrip().endswith("}"):
                rec = self._take(seen["i"])
                if rec["response"] is not None:
                    return rec
        return self._take(seen["i"]) if seen else None

    def _take(self, index):
        e = self.js(TAKE_JS % index, timeout=300)
        rec = {"sent_utc": e["sentUtc"], "http_status": e["status"], "headers": e["headers"],
               "ms_to_headers": e["msToHeaders"], "ms_to_last_byte": e["msToLastByte"],
               "stream_end": e["streamEnd"], "network_error": e["networkError"],
               "response_bytes": len(e["responseText"].encode("utf-8")),
               "request_text": e["requestText"], "response_text": e["responseText"]}
        try:
            rec["request"] = json.loads(e["requestText"] or "null")
        except json.JSONDecodeError:
            rec["request"] = None
        rec["response"] = parse_reply(e["responseText"])
        return rec

    def reload_and_list_tools(self, timeout=90):
        """Reload the page and return the tools/list exchange it makes right after sign-in."""
        self.c.send("Page.reload")
        return self._wait("tools/list", 0, timeout)

    def call(self, tool, arguments, timeout=300):
        """Send one tools/call through the page; return the record."""
        args_text = json.dumps(arguments, ensure_ascii=False, indent=2)
        ec.wake(self.c)  # Edge freezes the timers of a covered window; the page needs them to send the call
        start = self._log_size()
        try:
            ui = self.js(UI_CALL_JS % (json.dumps(tool), json.dumps(args_text)), timeout=60)
        except TimeoutError:
            return {"tool": tool, "arguments": arguments, "ui_error": "the page did not react within 60 s (timers frozen: is the Edge window covered or the screen locked?)"}
        if not ui or not ui.get("ok"):
            return {"tool": tool, "arguments": arguments, "ui_error": (ui or {}).get("why", "no answer from the page")}
        rec = self._wait("tools/call", start, timeout)
        if rec is None:
            return {"tool": tool, "arguments": arguments, "ui_error": f"no tools/call recorded within {timeout} s"}
        sent = (rec.get("request") or {}).get("params", {})
        rec["tool"], rec["arguments"] = tool, arguments
        rec["sent_as_typed"] = sent.get("name") == tool and sent.get("arguments") == arguments
        return rec


def save(record, folder, case):
    folder = pathlib.Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{case}.json"
    path.write_text(json.dumps(dict(record, case=case), ensure_ascii=False, indent=1), encoding="utf-8")
    return path
