"""Pre-generate the 轨 C render (gpt-image photoreal image of the 3D view) of each scenario, through the live page.

Runs on a workstation with Edge on the real GPU (the VM has no browser); the files land in the local render_cache/ and ship with
the next deploy.ps1. The portal account comes from PORTAL_USERNAME / PORTAL_PASSWORD in the environment:
    python pregen_render.py               # scenarios without render_cache/<id>/
    python pregen_render.py --force aps   # redo these
`--browser swiftshader` (software WebGL, Linux) remains for a host without a GPU; it needs > 300 s for the MCHX fin pack.
It signs in with the portal account, opens each scenario card as a visitor would (the pre-generated B-rep
solid becomes the main view) and presses「开始渲染」with fixed settings. The page itself exports the WebGL snapshot and calls
/api/render, so each scenario costs exactly one gpt-image call, made the way a live click makes it. The request and its SSE
`done` event are copied inside the page and saved as render_cache/<id>/{render.png, snapshot.png, meta.json}.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
OUT = BASE / "render_cache"
SITE = os.environ.get("STUDIO_SITE", "http://127.0.0.1:3005")   # override with --site
# Copies the /api/render request body and the complete SSE reply; what the page sends and receives is unchanged.
TEE = """(() => {
  const orig = window.fetch.bind(window);
  window.__renderCalls = [];
  window.fetch = async (input, init) => {
    const res = await orig(input, init);
    const url = typeof input === 'string' ? input : input.url;
    if (url.split('?')[0].endsWith('/api/render') && init && init.method === 'POST' && res.body) {
      const [a, b] = res.body.tee();
      window.__renderCalls.push({ request: init.body, response: new Response(b).text() });
      return new Response(a, { status: res.status, statusText: res.statusText, headers: res.headers });
    }
    return res;
  };
})();"""
DROP = ("image", "ok", "source", "key_source", "endpoint_host")   # image is saved as a file; the rest is per-request plumbing


def env_value(text: str, key: str) -> str:
    m = re.search(rf"^{key}=(.*)$", text, re.M)
    if not m:
        raise SystemExit(f"{key} missing in .env")
    return m.group(1).strip()


def sse_events(text: str):
    for block in text.split("\n\n"):
        event = data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                data = line[6:]
        if event and data:
            yield event, json.loads(data)


def png_bytes(data_url: str) -> bytes:
    if not isinstance(data_url, str) or not data_url.startswith("data:image/png;base64,"):
        raise ValueError("not a PNG data URL")
    raw = base64.b64decode(data_url.split(",", 1)[1], validate=True)
    if not raw.startswith(b"\x89PNG"):
        raise ValueError("not a PNG")
    return raw


def _clear_readonly(func, path, _exc_info):
    os.chmod(path, stat.S_IWRITE)   # OneDrive marks synced folders read-only, and Windows then refuses to remove them
    func(path)


def save(sid: str, done: dict, request: dict, view: str, site: str, browser: str) -> dict:
    render, snapshot = png_bytes(done["image"]), png_bytes(request["image"])
    meta = {k: v for k, v in done.items() if k not in DROP}
    meta.update({"scenario_id": sid, "origin": "live /api/render call made by pregen_render.py through the page", "view": view,
                 "site": site, "snapshot_browser": browser, "summary_sent": (request.get("summary") or "")[:600],
                 "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(), "render_sha256": hashlib.sha256(render).hexdigest(),
                 "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    staging = OUT / f".{sid}.building"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    (staging / "render.png").write_bytes(render)
    (staging / "snapshot.png").write_bytes(snapshot)
    (staging / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    dest = OUT / sid
    if dest.exists():
        shutil.rmtree(dest, onerror=_clear_readonly)
    staging.rename(dest)   # the server only lists a directory whose render.png and meta.json both exist
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--style", default="studio")
    ap.add_argument("--size", default="2048x1152")
    ap.add_argument("--quality", default="max")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--browser", choices=("swiftshader", "msedge"), default="msedge")
    a = ap.parse_args()
    if os.environ.get("PORTAL_USERNAME") and os.environ.get("PORTAL_PASSWORD"):
        user, password = os.environ["PORTAL_USERNAME"], os.environ["PORTAL_PASSWORD"]
    else:
        env = (BASE / ".env").read_text(encoding="utf-8")
        user, password = env_value(env, "PORTAL_USERNAME"), env_value(env, "PORTAL_PASSWORD")
    done_ids, failed = [], []
    with sync_playwright() as p:
        browser = (p.chromium.launch(channel="msedge", headless=True) if a.browser == "msedge" else
                   p.chromium.launch(headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"]))
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_init_script(TEE)
        page = ctx.new_page()
        page.set_default_timeout(300000)   # software WebGL on the VM loads the larger B-rep assemblies slowly
        if not ctx.request.post(f"{a.site}/api/login", data={"username": user, "password": password}).ok:
            raise SystemExit("portal sign-in failed")
        me = ctx.request.get(f"{a.site}/api/me").json()
        if not me.get("image_deployment"):
            raise SystemExit("the server has no image deployment (AOAI_IMAGE_DEPLOYMENT)")
        data = ctx.request.get(f"{a.site}/api/scenarios").json()
        scenarios = {s["id"]: s for s in data["scenarios"]}
        labels = {i["id"]: i["label"] for i in data.get("industries", [])}
        todo = [sid for sid in (a.ids or list(scenarios)) if sid in scenarios
                and (a.force or not all((OUT / sid / n).is_file() for n in ("render.png", "meta.json")))]
        print(json.dumps({"todo": todo, "image_deployment": me["image_deployment"], "style": a.style, "size": a.size,
                          "quality": a.quality, "browser": a.browser}), flush=True)
        page.goto(f"{a.site}/?lang=zh&render_cache=0", wait_until="domcontentloaded")   # no stored render: the live render path
        page.wait_for_selector(".scenario")
        for sid in todo:
            t0 = time.time()
            try:
                label = labels.get(scenarios[sid].get("industry") or "thermal")
                if label and not page.locator("#industryTabs button.active").inner_text().startswith(label):
                    page.locator("#industryTabs button").filter(has_text=label).first.click(force=True)
                    page.wait_for_timeout(600)
                page.locator(f'.scenario[data-scenario="{sid}"]').click(force=True)
                if sid in (me.get("cad_cached") or []):
                    page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")')
                page.wait_for_function('!document.querySelector("#btnRender").disabled')
                view = page.locator("#viewStatus").inner_text()
                page.locator("#tabRender").click(force=True)
                page.select_option("#renderStyle", a.style)
                page.select_option("#renderSize", a.size)
                page.select_option("#renderQuality", a.quality)
                page.select_option("#renderBase", "snapshot")
                page.fill("#renderInstruction", "")
                for attempt in range(a.retries + 1):
                    n0 = page.evaluate("() => window.__renderCalls.length")
                    page.locator("#renderGo").click(force=True)
                    page.wait_for_function(f"() => window.__renderCalls.length > {n0}")
                    call = page.evaluate("async () => { const c = window.__renderCalls.at(-1); return { request: c.request, response: await c.response }; }")
                    events = dict(sse_events(call["response"]))
                    if "done" in events:
                        break
                    message = (events.get("error") or {}).get("message", "stream ended without a result")
                    if attempt < a.retries and re.search(r"429|rate.?limit", message, re.I):
                        print(json.dumps({"id": sid, "retry_after_s": 65, "error": message[:160]}), flush=True)
                        page.wait_for_function('!document.querySelector("#renderGo").disabled')
                        time.sleep(65)   # the image deployment allows 2 requests per minute
                        page.select_option("#renderBase", "snapshot")
                        continue
                    raise RuntimeError(message[:300])
                meta = save(sid, events["done"], json.loads(call["request"]), view, a.site, a.browser)
                page.wait_for_function('!document.querySelector("#renderGo").disabled')
                done_ids.append(sid)
                print(json.dumps({"id": sid, "ok": True, "t_s": round(time.time() - t0, 1), "latency_s": meta.get("latency_s"),
                                  "size": meta.get("size"), "quality": meta.get("quality"), "model": meta.get("model"),
                                  "tokens": (meta.get("usage") or {}).get("total_tokens"), "view": view}, ensure_ascii=False), flush=True)
            except Exception as e:  # noqa: BLE001 — record and continue with the other scenarios
                failed.append(sid)
                print(json.dumps({"id": sid, "ok": False, "t_s": round(time.time() - t0, 1), "error": str(e)[:300]}, ensure_ascii=False), flush=True)
        browser.close()
    print(json.dumps({"done": done_ids, "failed": failed}), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
