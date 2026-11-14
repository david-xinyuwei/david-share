"""工程渲染图: the STEP solid itself rendered with a studio look, for every pre-generated render (offline, no model call).

The gpt-image render in render_cache/<id>/ is redrawn by an image model and never coincides with the STEP (pregen_render_cad.py
measures by how much). This tool runs static/engineering-render.mjs — the module the app also runs in the browser for live STEP
results — in headless Edge on cad_cache/<id>/model.glb: main-viewport materials, the workspace's 38° perspective direction framed
so the solid fills 74 % of the 16:9 frame, accumulated jittered frames with soft key / sky shadows, studio reflections, vignette
and AgX. The STEP outline + edges come from the same camera, so they lie on the picture without any fit.
Writes render_cache/<id>/engineering.png, engineering_lines.png (cyan on transparent) and engineering.json, which
GET /api/render/cache/<id> returns as `engineering`.
    python pregen_engineering.py [ids...] [--size 2048x1152] [--spp 256] [--out <dir>] [--no-install]
--out also writes <id>_engineering.png, <id>_engineering_cad.png (lines composited) and <id>_check.json there: silhouette IoU and
outline distance between the part area segmented from the render (as in pregen_render_cad.py) and the STEP mask, as evidence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
from scipy import ndimage

import pregen_render_cad as prc

LOAD = ("import { renderEngineering } from '%s/static/engineering-render.mjs';"
        "window.renderEngineering = renderEngineering; window.engReady = true;" % prc.HOST)


def serve(route):
    path = route.request.url[len(prc.HOST):].split("?")[0]
    if path == "/page.html":
        return route.fulfill(body=prc.PAGE, content_type="text/html")
    f = prc.BASE / path.lstrip("/") if path.startswith("/static/") else prc.CC / path[len("/cad/"):] if path.startswith("/cad/") else None
    if f is None or not f.is_file():
        return route.fulfill(status=404, body="")
    ctype = "text/javascript" if f.suffix in (".js", ".mjs") else "model/gltf-binary" if f.suffix == ".glb" else "application/octet-stream"
    return route.fulfill(status=200, body=f.read_bytes(), content_type=ctype)


def data(url: str) -> bytes:
    return base64.b64decode(url.split(",", 1)[1])


def check(beauty: Image.Image, mask: np.ndarray) -> dict:
    """Silhouette IoU and STEP-outline → segmented-outline distance (render px); segmentation as in pregen_render_cad.py."""
    area = prc.part_area(beauty)
    filled = ndimage.binary_fill_holes(mask)
    cad_o, seg_o = filled & ~ndimage.binary_erosion(filled), area & ~ndimage.binary_erosion(area)
    d = ndimage.distance_transform_edt(~seg_o)[cad_o]
    return {"iou_pct": round(prc.iou(mask, area) * 100, 1), "outline_median_px": round(float(np.median(d)), 1),
            "outline_p90_px": round(float(np.percentile(d, 90)), 1)}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")   # part names such as Ø / ⑪ are outside the GBK console code page
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--size", default="2048x1152")
    ap.add_argument("--spp", type=int, default=256)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--no-install", action="store_true")
    a = ap.parse_args()
    W, H = map(int, a.size.lower().split("x"))
    ids = a.ids or sorted(p.name for p in prc.RC.iterdir() if p.is_dir() and not p.name.startswith(".") and (prc.CC / p.name / "model.glb").is_file())
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
    failed, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)[:300]))
        page.route(f"{prc.HOST}/**", serve)
        page.goto(f"{prc.HOST}/page.html")
        page.wait_for_function("window.ready === true")
        page.add_script_tag(content=LOAD, type="module")
        page.wait_for_function("window.engReady === true", timeout=60000)
        for sid in ids:
            row = {"id": sid}
            try:
                parts = json.loads((prc.CC / sid / "parts.json").read_text(encoding="utf-8"))
                res = page.evaluate("([u, p, w, h, n]) => window.renderEngineering({ glb: u, parts: p, width: w, height: h, spp: n, debug: true })",
                                    [f"{prc.HOST}/cad/{sid}/model.glb", parts, W, H, a.spp])
                image, lines, mask_png = data(res.pop("image")), data(res.pop("lines")), data(res.pop("mask"))
                beauty = Image.open(io.BytesIO(image)).convert("RGB")
                mask = np.asarray(Image.open(io.BytesIO(mask_png)).convert("L")) > 127
                if beauty.size != (W, H) or mask.shape != (H, W):
                    raise ValueError(f"render {beauty.size}, mask {mask.shape[::-1]}, expected {(W, H)}")
                meta = {"method": "pregen_engineering.py → static/engineering-render.mjs in headless Edge: cad_cache/<id>/model.glb with the "
                                  "main-viewport materials, workspace perspective direction framed to fill the frame; STEP outline + edges "
                                  "drawn with the same camera, no fit",
                        "cad_source": f"cad_cache/{sid}/model.glb", "glb_sha256": hashlib.sha256((prc.CC / sid / "model.glb").read_bytes()).hexdigest(),
                        "image_model": None, "source": "pre_generated", **res, "rendered_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
                row.update({**check(beauty, mask), "spp": res["spp"], "render_s": round(res["render_ms"] / 1000, 1),
                            "zoom": round(res["camera"]["zoom"], 3), "unmatched_meshes": res["unmatched_meshes"]})
                if not a.no_install:
                    d = prc.RC / sid
                    prc.write(d / "engineering.png", image)
                    prc.write(d / "engineering_lines.png", lines)
                    prc.write(d / "engineering.json", json.dumps(meta, ensure_ascii=False, indent=1).encode("utf-8"))
                if a.out:
                    (a.out / f"{sid}_engineering.png").write_bytes(image)
                    Image.alpha_composite(beauty.convert("RGBA"), Image.open(io.BytesIO(lines)).convert("RGBA")).convert("RGB").save(a.out / f"{sid}_engineering_cad.png")
                    (a.out / f"{sid}_check.json").write_text(json.dumps({**row, "meta": meta}, ensure_ascii=False, indent=1), encoding="utf-8")
                row["ok"] = res["unmatched_meshes"] == 0
            except Exception as e:  # noqa: BLE001 — report and continue with the other scenarios
                row.update({"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"})
            if not row["ok"]:
                failed.append(sid)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        browser.close()
    if errors:
        print(json.dumps({"page_errors": errors[:5]}, ensure_ascii=False))
    return 1 if failed or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
