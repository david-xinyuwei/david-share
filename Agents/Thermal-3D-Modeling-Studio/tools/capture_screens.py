"""Screenshots for the README and docs/RESULTS*.md, taken from the studio's pre-generated examples (no model call).

Start the studio first (docs/TESTING.md, "Browser check"), then:
    python tools/capture_screens.py http://127.0.0.1:8015 <out_dir> [--only module,features,gallery,render]   (default: module)

Signs in with PORTAL_USERNAME / PORTAL_PASSWORD from the environment. In the English and the Chinese UI it saves
  module    track-a-concept, track-b-brep-quad, track-b-cad-tab: the integrated module as GPT-6's concept scene, as the
            OCCT B-rep in the quad view, and the CAD tab with the STEP metrics
  features  feature-section, feature-isolate: a B-rep cut by a section plane (--section, default coldplate:y), and the cold
            plate's channel base plate shown alone
  gallery   gallery-<id>-gpt6, gallery-<id>-brep: each scenario's 3D viewport with GPT-6's page as written and with the B-rep
  render    render-tab: the render tab with the STEP outline over a saved render; needs studio/render_cache/module/
as <name>-<lang>.png, plus capture.json (browser, GPU, SHA-256 per file; a later run into the same directory adds to it).
Any POST to a model endpoint or any page error of the studio fails the run. An error thrown by GPT-6's own page, which the studio
reports as a scene that did not render, is recorded with that picture (scene_error) and in scene_errors instead.
The render tab only appears when the studio was started with AOAI_IMAGE_DEPLOYMENT set (no image call is made).
Needs Microsoft Edge and `pip install -r requirements-dev.txt`.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATHS = {"/api/generate", "/api/cad", "/api/render", "/api/concept", "/api/proposal"}
WAIT_MS = 180000
SMALL, TALL = {"width": 1600, "height": 900}, {"width": 1600, "height": 1200}
GPU_JS = ("() => { const gl = window.__renderer.getContext(); const ext = gl.getExtension('WEBGL_debug_renderer_info');"
          " return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'unknown'; }")
SCENE_SETTLED = ('n => document.querySelector("[data-geometry=concept]").getAttribute("aria-pressed") === "true" && ('
                 'document.querySelectorAll(".msg.assistant.error").length > n || '
                 '(s => s !== "" && !s.includes("B-rep"))(document.querySelector("#viewStatus").textContent.trim()))')
SAME_PARTS = ("names => document.querySelector('#viewStatus').textContent.includes('B-rep') && JSON.stringify("
              "[...document.querySelectorAll('#partList button')].map(b => b.textContent.trim())) === JSON.stringify(names)")


def scenario_groups() -> dict[str, str]:
    """Scenario id -> industry group (studio/scenarios.py). The studio lists the cards of one group at a time."""
    spec = importlib.util.spec_from_file_location("scenarios", ROOT / "studio" / "scenarios.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {s["id"]: module.industry_of(s) for s in module.SCENARIOS}


GROUP = scenario_groups()


def part_names(sid: str, lang: str) -> list[str]:
    parts = ROOT / "studio" / ("cad_cache" if lang == "zh" else "cad_cache_en") / sid / "parts.json"
    return [p["name"] for p in json.loads(parts.read_text(encoding="utf-8"))]


def open_scenario(page, sid: str, lang: str) -> list[str]:
    """Open a scenario card (loading its industry group first) and wait until its own pre-generated B-rep is on screen."""
    if not page.locator(f"[data-scenario='{sid}']").count():
        url = urlparse(page.url)
        page.goto(f"{url.scheme}://{url.netloc}/?lang={lang}&industry={GROUP[sid]}", wait_until="domcontentloaded")
        page.locator("#viewportBody.engineering").wait_for(timeout=WAIT_MS)
        page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WAIT_MS)
    names = part_names(sid, lang)
    # Clicking the scenario that is already open reloads the viewer iframe in place, which can crash the Playwright driver
    # (FrameManager.frameAttached assertion, 2026-11-14).
    if not page.evaluate(SAME_PARTS, names):
        page.evaluate("id => document.querySelector(`[data-scenario='${id}']`).click()", sid)
    page.wait_for_function(SAME_PARTS, arg=names, timeout=WAIT_MS)
    try:
        page.wait_for_function("n => (window.__aoReports || []).some(r => r.ao !== 'pending' && r.parts.includes(n))",
                               arg=names[0], timeout=30000)
    except Exception:  # noqa: BLE001 - ambient occlusion only shades the picture; its report is not required
        pass
    time.sleep(2)
    return names


def workspace_clip(page) -> dict:
    """Layout toolbar, side rail, 3D viewport and outliner: the solid together with the controls that set up the view."""
    viewer = page.locator("#viewer").bounding_box()
    toolbar = page.locator('[data-workspace-layout="original"]').bounding_box()
    outliner = page.locator("#partList").bounding_box()
    x, y = viewer["x"] - 44, toolbar["y"] - 12
    right = max(viewer["x"] + viewer["width"], outliner["x"] + outliner["width"]) + 8
    return {"x": x, "y": y, "width": right - x, "height": viewer["y"] + viewer["height"] - y}


def shoot(page, out: Path, record: dict, name: str, lang: str, scenario: str, shows: str, element=None, clip=None) -> None:
    path = out / f"{name}-{lang}.png"
    if element:
        page.locator(element).screenshot(path=str(path))
    else:
        page.screenshot(path=str(path), clip=clip)
    record["shots"].append({"file": path.name, "lang": lang, "scenario": scenario, "shows": shows, "viewport": page.viewport_size,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})


def module_shots(page, out: Path, record: dict, lang: str) -> None:
    page.set_viewport_size(SMALL)
    open_scenario(page, "module", lang)
    page.locator('[data-geometry="concept"]').click()
    page.wait_for_function('document.querySelector("[data-geometry=concept]").getAttribute("aria-pressed") === "true" && '
                           '!document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WAIT_MS)
    time.sleep(4)
    shoot(page, out, record, "track-a-concept", lang, "module", "GPT-6's three.js scene (Track A), recorded response, perspective view")
    page.locator('[data-geometry="brep"]').click()
    page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WAIT_MS)
    page.locator('[data-workspace-layout="quad"]').click()
    time.sleep(5)
    shoot(page, out, record, "track-b-brep-quad", lang, "module", "OCCT B-rep solid of the reference script (Track B), quad view")
    page.locator('[data-workspace-layout="single"]').click()
    page.locator('[data-tab="cad"]').click()
    time.sleep(4)
    shoot(page, out, record, "track-b-cad-tab", lang, "module", "CAD tab: STEP metrics computed by OCCT, STL preview, downloads")
    page.locator('[data-tab="view"]').click()


def feature_shots(page, out: Path, record: dict, lang: str, sections: list[str]) -> None:
    page.set_viewport_size(TALL)
    for spec in sections:
        sid, axis = spec.split(":")
        open_scenario(page, sid, lang)
        page.locator('[data-workspace-layout="quad"]').click()
        page.locator("#viewSection").select_option(axis)
        time.sleep(5)
        name = "feature-section" if len(sections) == 1 else f"feature-section-{sid}-{axis}"
        shoot(page, out, record, name, lang, sid, f"B-rep in the quad view, cut by the section plane normal to {axis.upper()}",
              clip=workspace_clip(page))
        page.locator("#viewSection").select_option("none")
    names = open_scenario(page, "coldplate", lang)
    page.locator('[data-workspace-layout="single"]').click()
    page.locator("#partList button").filter(has_text=names[0]).click()
    page.wait_for_function('!document.getElementById("viewIsolate").disabled', timeout=WAIT_MS)
    page.locator("#viewIsolate").click()
    page.wait_for_function('document.querySelectorAll("#partList input:checked").length === 1', timeout=WAIT_MS)
    time.sleep(4)
    shoot(page, out, record, "feature-isolate", lang, "coldplate", f"Cold plate B-rep with only one part shown: {names[0]}",
          clip=workspace_clip(page))
    page.locator("#viewShowAll").click()


def gallery_shots(page, out: Path, record: dict, lang: str, ids: list[str]) -> None:
    page.set_viewport_size(TALL)
    for sid in ids:
        open_scenario(page, sid, lang)
        page.locator('[data-workspace-layout="single"]').click()
        time.sleep(3)
        shoot(page, out, record, f"gallery-{sid}-brep", lang, sid, "3D viewport: OCCT B-rep solid of the reference script (Track B)",
              element="#viewer")
        errors_before = page.locator(".msg.assistant.error").count()
        page.locator('[data-geometry="concept"]').click()
        # The status line is empty until GPT-6's page has rendered; a page that does not expose the engineering-view interface
        # stays in its original layout with the layout buttons disabled (2026-11-14, notebook assembly line). When the page
        # itself throws, the studio reports "Code arrived, but the 3D scene did not render" and the status line stays empty.
        page.wait_for_function(SCENE_SETTLED, arg=errors_before, timeout=WAIT_MS)
        scene_error = None
        if page.locator(".msg.assistant.error").count() > errors_before:
            scene_error = page.locator(".msg.assistant.error").last.text_content().strip()[:600]
            time.sleep(8)
        else:
            # On render-ready the studio may switch the page into its engineering view; Original shows the page as written.
            # Click it whenever it is enabled (aria-pressed can still show the previous state) and wait for the view to leave.
            original = page.locator('[data-workspace-layout="original"]')
            if original.is_enabled():
                original.click()
            page.wait_for_function("() => !document.querySelector('#viewportBody').classList.contains('engineering')", timeout=WAIT_MS)
            page.frame_locator("#viewer").locator("#studio-workspace").wait_for(state="hidden", timeout=WAIT_MS)
            time.sleep(4)
        shoot(page, out, record, f"gallery-{sid}-gpt6", lang, sid, "3D viewport: GPT-6's three.js page as written (Track A, recorded response)",
              element="#viewer")
        record["shots"][-1]["status_line"] = page.locator("#viewStatus").text_content().strip()
        if scene_error:
            record["shots"][-1]["scene_error"] = scene_error
            record["scene_errors"].append({"scenario": sid, "lang": lang, "message": scene_error})


def render_shots(page, out: Path, record: dict, lang: str) -> None:
    page.set_viewport_size(TALL)
    open_scenario(page, "module", lang)
    page.locator('[data-tab="render"]').click()
    page.locator("#renderResult:not(.hidden)").wait_for(timeout=WAIT_MS)
    page.wait_for_function("() => { const i = document.querySelector('#renderImg'); return i.complete && i.naturalWidth > 0; }", timeout=WAIT_MS)
    if page.locator("#renderCadToggle").is_visible():
        page.locator("#renderCadToggle").click()
        page.wait_for_function("() => { const i = document.querySelector('#renderCadLines');"
                               " return !i.classList.contains('hidden') && i.complete && i.naturalWidth > 0; }", timeout=WAIT_MS)
    time.sleep(2)
    shoot(page, out, record, "render-tab", lang, "module", "Render tab: a saved gpt-image render of the module with the STEP outline overlaid")
    page.locator('[data-tab="view"]').click()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--only", default="module", help="comma-separated: module, features, gallery, render")
    ap.add_argument("--scenarios", default="", help="gallery scenario ids, comma-separated (default: every scenario card)")
    ap.add_argument("--langs", default="en,zh")
    ap.add_argument("--section", default="coldplate:y", help="scenario:axis pairs for the section shot, comma-separated")
    a = ap.parse_args()
    base, out, only = a.base_url.rstrip("/"), a.out_dir, set(a.only.split(","))
    if "render" in only and not (ROOT / "studio" / "render_cache" / "module" / "render.png").is_file():
        sys.exit("--only render needs a saved render in studio/render_cache/module/")
    out.mkdir(parents=True, exist_ok=True)
    record = {"url": base, "only": sorted(only), "started": datetime.now(timezone.utc).isoformat(timespec="seconds"), "shots": [],
              "model_calls": [], "page_errors": [], "scene_errors": [], "scene_page_errors": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport=SMALL, device_scale_factor=1)
        login = context.request.post(f"{base}/api/login", data={"username": os.environ.get("PORTAL_USERNAME", "studio"),
                                                               "password": os.environ["PORTAL_PASSWORD"]})
        if not login.ok:
            sys.exit(f"sign-in failed: HTTP {login.status}")
        page = context.new_page()
        page.on("pageerror", lambda e: record["page_errors"].append(str(e)[:200]))
        page.on("request", lambda r: record["model_calls"].append(r.url) if r.method == "POST" and urlparse(r.url).path in MODEL_PATHS else None)
        for lang in a.langs.split(","):
            page.set_viewport_size(SMALL)
            page.goto(f"{base}/?lang={lang}", wait_until="domcontentloaded")
            page.locator("#viewportBody.engineering").wait_for(timeout=WAIT_MS)
            page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WAIT_MS)
            if "gpu" not in record:
                record["gpu"] = page.frame_locator("#viewer").locator("body").evaluate(GPU_JS)
            if "module" in only:
                module_shots(page, out, record, lang)
            if "features" in only:
                feature_shots(page, out, record, lang, a.section.split(","))
            if "gallery" in only:
                ids = a.scenarios.split(",") if a.scenarios else page.evaluate(
                    "() => [...new Set([...document.querySelectorAll('[data-scenario]')].map(e => e.dataset.scenario))]")
                gallery_shots(page, out, record, lang, ids)
            if "render" in only:
                render_shots(page, out, record, lang)
        record["browser"] = f"Microsoft Edge {browser.version}, headless"
        browser.close()
    # Errors thrown by GPT-6's own page, which the studio reported as a failed scene, are a property of that recorded answer:
    # they stay with its picture (scene_errors) instead of failing the run. Any other page error still fails it.
    reported = [e["message"] for e in record["scene_errors"]]
    record["scene_page_errors"] = [e for e in record["page_errors"] if any(e in m for m in reported)]
    record["page_errors"] = [e for e in record["page_errors"] if not any(e in m for m in reported)]
    record["finished"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    saved = out / "capture.json"
    if saved.is_file():
        old = json.loads(saved.read_text(encoding="utf-8"))
        mine = {s["file"] for s in record["shots"]}
        record["shots"] = [s for s in old["shots"] if s["file"] not in mine] + record["shots"]
        record["runs"] = old.get("runs", []) + [{k: old[k] for k in ("only", "started", "finished") if k in old}]
        record["model_calls"] = old["model_calls"] + record["model_calls"]
        record["page_errors"] = old["page_errors"] + record["page_errors"]
        for key in ("scene_errors", "scene_page_errors"):
            record[key] = old.get(key, []) + record[key]
    saved.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: record.get(k) for k in ("gpu", "browser", "model_calls", "page_errors", "scene_errors")}, ensure_ascii=False))
    print(f"{len(record['shots'])} screenshots -> {out}")
    return 1 if record["model_calls"] or record["page_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
