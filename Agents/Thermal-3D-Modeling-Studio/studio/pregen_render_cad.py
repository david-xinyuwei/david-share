"""渲染图 vs CAD: fit the STEP solid's outline and edges onto each pre-generated render (offline, no model call).

Every render in render_cache/<id>/ was made by the image model from snapshot.png, a picture of the STEP solid
(cad_cache/<id>/model.glb) in the workspace perspective view. This tool
 1. re-renders that CAD view with the same glTF and the workspace's own framing code (frameCamera / modelViews from
    static/viewer-workspace.mjs, 38° camera, the snapshot's pixel size): a silhouette mask and the visible edges;
 2. finds the part's area in the render: pixels with fine-scale gradient energy above the studio backdrop's noise,
    closed and hole-filled (soft shadows have no fine gradient; floor reflections do and are counted);
 3. places the CAD view on the render with ONE uniform scale and a shift that maximise the silhouette IoU — the image
    model re-frames its 16:9 output, so the framing has to be found, but no stretch or rotation is allowed: wherever
    the CAD lines miss the picture, the render departs from the STEP;
 4. writes render_cache/<id>/cad_lines.png (cyan lines on transparent, render pixels) and cad_overlay.json.
GET /api/render/cache/<id> returns both as `cad_overlay`; the 渲染图 tab shows them under「与 CAD 叠放」.
Runs on a workstation with Edge (Playwright), numpy, scipy and Pillow:
    python pregen_render_cad.py [ids...] [--sheets <dir>]   # --sheets also saves stretch / fit / free-fit comparison panels
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from scipy import ndimage, optimize

BASE = Path(__file__).resolve().parent
RC, CC = BASE / "render_cache", BASE / "cad_cache"
K = 2   # CAD views drawn at K × the snapshot size
D = 4   # the fit runs on the render downsampled by D
HOST = "http://cad.local"
PAGE = """<!DOCTYPE html><html><head>
<script type="importmap">{"imports":{"three":"%(h)s/static/vendor/three/three.module.js","three/addons/":"%(h)s/static/vendor/three/jsm/"}}</script>
</head><body style="margin:0;background:#000"><script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { frameCamera, modelViews } from '%(h)s/static/viewer-workspace.mjs';
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1); renderer.setClearColor(0x000000, 1);
document.body.appendChild(renderer.domElement);
window.cadViews = async (url, W, H, k) => {
  const root = (await new GLTFLoader().loadAsync(url)).scene; root.updateMatrixWorld(true);
  // The workspace's single perspective view: Box3.setFromObject(model, true), a 38° camera, frameCamera(); B-rep is Y-up.
  const bounds = new THREE.Box3().setFromObject(root, true);
  const camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 20000);
  const v = modelViews(THREE, new THREE.Vector3(0, 1, 0));
  frameCamera(THREE, camera, bounds, W, H, v.directions.perspective, v.up);
  renderer.setSize(W * k, H * k, false);
  const meshes = []; root.traverse(o => { if (o.isMesh) meshes.push(o); });
  const scene = new THREE.Scene(); scene.add(root);
  for (const m of meshes) m.material = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
  renderer.render(scene, camera);
  const mask = renderer.domElement.toDataURL('image/png');
  // Edges per part: OCCT writes one mesh per B-rep face, so weld a part's faces before taking 28° creases.
  const byParent = new Map();
  for (const m of meshes) { const p = m.parent || root; if (!byParent.has(p)) byParent.set(p, []); byParent.get(p).push(m); }
  const lines = new THREE.Group(), lineMat = new THREE.LineBasicMaterial({ color: 0xffffff });
  for (const group of byParent.values()) {
    const geoms = group.map(m => { let g = new THREE.BufferGeometry(); g.setAttribute('position', m.geometry.attributes.position.clone());
      if (m.geometry.index) { g.setIndex(m.geometry.index.clone()); g = g.toNonIndexed(); } g.applyMatrix4(m.matrixWorld); return g; });
    lines.add(new THREE.LineSegments(new THREE.EdgesGeometry(mergeVertices(mergeGeometries(geoms, false), 1e-3), 28), lineMat));
  }
  const occluder = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2 });
  for (const m of meshes) m.material = occluder;
  scene.add(lines);
  renderer.render(scene, camera);
  return { mask, edges: renderer.domElement.toDataURL('image/png') };
};
window.ready = true;
</script></body></html>""" % {"h": HOST}


def png(data_url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1])))


def part_area(rgb: Image.Image) -> np.ndarray:
    """Part area in a studio render: fine gradient energy above the backdrop noise (from the image border), closed and filled."""
    g = ndimage.gaussian_filter(np.asarray(rgb.convert("L"), np.float32), 1.2)
    mag = np.hypot(ndimage.sobel(g, 1), ndimage.sobel(g, 0))
    b = max(8, int(0.03 * min(mag.shape)))
    border = np.concatenate([mag[:b].ravel(), mag[-b:].ravel(), mag[:, :b].ravel(), mag[:, -b:].ravel()])
    m = ndimage.binary_closing(mag > max(np.percentile(border, 95) * 2.0, 6.0), structure=np.ones((3, 3)), iterations=6)
    m = ndimage.binary_opening(ndimage.binary_fill_holes(m), structure=np.ones((3, 3)), iterations=2)
    lab, n = ndimage.label(m)
    if not n:
        return m
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    return np.isin(lab, 1 + np.flatnonzero(sizes >= 0.002 * m.size))


def warp(cad: np.ndarray, sx: float, sy: float, tx: float, ty: float, shape) -> np.ndarray:
    """CAD mask drawn at K × snapshot px → render px with x_r = sx · x_s + tx, y_r = sy · y_s + ty."""
    return ndimage.affine_transform(cad.astype(np.float32), np.diag([K / sy, K / sx]), offset=[-K * ty / sy, -K * tx / sx],
                                    output_shape=shape, order=1) > 0.5


def iou(a: np.ndarray, b: np.ndarray) -> float:
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def best_fit(cad, area_small, x0, aniso: bool):
    """Maximise IoU on the downsampled part area; x = (sx, sy, tx, ty) in full render px. Uniform: sx = sy."""
    def cost(x):
        sx, sy, tx, ty = x if aniso else (x[0], x[0], x[1], x[2])
        return 1.0 if min(sx, sy) <= 0 else -iou(warp(cad, sx / D, sy / D, tx / D, ty / D, area_small.shape), area_small)
    start = np.array(list(x0) if aniso else [x0[0], x0[2], x0[3]], float)
    best = None
    for jitter in (0.0, 0.08, -0.08):
        s = start.copy()
        s[: 2 if aniso else 1] *= 1 + jitter
        step = np.array([0.06 * s[0]] * (2 if aniso else 1) + [40.0, 40.0])
        r = optimize.minimize(cost, s, method="Nelder-Mead",
                              options={"xatol": 0.2, "fatol": 1e-4, "maxiter": 3000, "initial_simplex": np.vstack([s, np.diag(step) + s])})
        if best is None or r.fun < best.fun:
            best = r
    return best.x if aniso else np.array([best.x[0], best.x[0], best.x[1], best.x[2]])


def lines_layer(lines: np.ndarray, sx, sy, tx, ty, shape) -> np.ndarray:
    pts = np.argwhere(lines)[:, ::-1].astype(np.float64) / K
    m = np.round(np.column_stack([pts[:, 0] * sx + tx, pts[:, 1] * sy + ty])).astype(int)
    ok = (m[:, 0] >= 0) & (m[:, 0] < shape[1]) & (m[:, 1] >= 0) & (m[:, 1] < shape[0])
    layer = np.zeros(shape, bool)
    layer[m[ok, 1], m[ok, 0]] = True
    return ndimage.binary_dilation(layer, iterations=1)


def write(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    if path.exists():
        os.chmod(path, stat.S_IWRITE)   # OneDrive may mark synced files read-only; os.replace then fails on Windows
    os.replace(tmp, path)


def sheet(rend, area, cad, lines, fits: dict, path: Path) -> None:
    panels = []
    for title, x in fits.items():
        cm = warp(cad, *x, area.shape)
        out = np.asarray(rend, np.float32).copy()
        out[area & ~cm] = out[area & ~cm] * 0.45 + np.array([255, 140, 40]) * 0.55   # render only
        out[cm & ~area] = out[cm & ~area] * 0.45 + np.array([40, 110, 255]) * 0.55   # CAD only
        out[lines_layer(lines, *x, area.shape)] = [0, 229, 255]
        im = Image.fromarray(out.clip(0, 255).astype(np.uint8))
        im.thumbnail((760, 430))
        ImageDraw.Draw(im).rectangle([0, 0, im.size[0], 22], fill=(255, 255, 255))
        ImageDraw.Draw(im).text((6, 5), f"{title} | IoU {iou(cm, area) * 100:.1f}%", fill=(0, 0, 0))
        panels.append(im)
    s = Image.new("RGB", (sum(p.size[0] for p in panels) + 8 * (len(panels) - 1), panels[0].size[1]), "white")
    for i, p in enumerate(panels):
        s.paste(p, (i * (panels[0].size[0] + 8), 0))
    s.save(path)


def run(sid: str, page, sheets: Path | None) -> dict:
    d = RC / sid
    snap, rend = Image.open(d / "snapshot.png").convert("RGB"), Image.open(d / "render.png").convert("RGB")
    (W, H), (Rw, Rh) = snap.size, rend.size
    views = page.evaluate("([u, w, h, k]) => window.cadViews(u, w, h, k)", [f"{HOST}/cad/{sid}/model.glb", W, H, K])
    cad = np.asarray(png(views["mask"]).convert("L")) > 127
    lines = (np.asarray(png(views["edges"]).convert("L")) > 127) | (cad & ~ndimage.binary_erosion(cad))
    area = part_area(rend)
    small = np.asarray(Image.fromarray((area * 255).astype(np.uint8)).resize((Rw // D, Rh // D), Image.BILINEAR)) > 127
    s_fit, s_fill = min(Rw / W, Rh / H), max(Rw / W, Rh / H)
    framings = {"stretch": (Rw / W, Rh / H, 0.0, 0.0), "fit": (s_fit, s_fit, (Rw - W * s_fit) / 2, (Rh - H * s_fit) / 2),
                "fill": (s_fill, s_fill, (Rw - W * s_fill) / 2, (Rh - H * s_fill) / 2)}
    framing_iou = {k: iou(warp(cad, *v, area.shape), area) for k, v in framings.items()}
    uni = best_fit(cad, small, framings[max(framing_iou, key=framing_iou.get)], aniso=False)
    free = best_fit(cad, small, uni, aniso=True)
    uni_iou, free_iou = iou(warp(cad, *uni, area.shape), area), iou(warp(cad, *free, area.shape), area)
    layer = lines_layer(lines, *uni, area.shape)
    rgba = np.zeros((*layer.shape, 4), np.uint8)
    rgba[layer] = (0, 229, 255, 255)
    buf = io.BytesIO()
    Image.fromarray(rgba).save(buf, format="PNG", optimize=True)
    write(d / "cad_lines.png", buf.getvalue())
    info = {"fit": "uniform", "scale": round(float(uni[0]), 4), "shift_px": [round(float(uni[2]), 1), round(float(uni[3]), 1)],
            "iou_pct": round(uni_iou * 100, 1), "free_x_over_y": round(float(free[0] / free[1]), 3), "free_iou_pct": round(free_iou * 100, 1),
            "framing_iou_pct": {k: round(v * 100, 1) for k, v in framing_iou.items()},
            "snapshot_px": [W, H], "render_px": [Rw, Rh], "cad_source": f"cad_cache/{sid}/model.glb",
            "method": "pregen_render_cad.py: CAD view re-rendered with the workspace camera; render part area from fine-scale "
                      "gradient energy (floor reflections included); uniform scale + shift maximising silhouette IoU",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    write(d / "cad_overlay.json", json.dumps(info, ensure_ascii=False, indent=1).encode("utf-8"))
    if sheets:
        sheets.mkdir(parents=True, exist_ok=True)
        sheet(rend, area, cad, lines, {"stretch": framings["stretch"], f"uniform s={uni[0]:.3f}": uni,
                                       f"free x/y={free[0] / free[1]:.3f}": free}, sheets / f"{sid}.png")
    return {"id": sid, **{k: info[k] for k in ("scale", "iou_pct", "free_x_over_y", "free_iou_pct", "framing_iou_pct")}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--sheets", type=Path)
    a = ap.parse_args()
    ids = a.ids or sorted(p.name for p in RC.iterdir() if p.is_dir() and not p.name.startswith(".")
                          and (p / "snapshot.png").is_file() and (CC / p.name / "model.glb").is_file())
    failed = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page()

        def serve(route):
            path = route.request.url[len(HOST):].split("?")[0]
            if path == "/page.html":
                return route.fulfill(body=PAGE, content_type="text/html")
            f = BASE / path.lstrip("/") if path.startswith("/static/") else CC / path[len("/cad/"):] if path.startswith("/cad/") else None
            if f is None or not f.is_file():
                return route.fulfill(status=404, body="")
            ctype = "text/javascript" if f.suffix in (".js", ".mjs") else "model/gltf-binary" if f.suffix == ".glb" else "application/octet-stream"
            return route.fulfill(status=200, body=f.read_bytes(), content_type=ctype)

        page.route(f"{HOST}/**", serve)
        page.goto(f"{HOST}/page.html")
        page.wait_for_function("window.ready === true")
        for sid in ids:
            try:
                print(json.dumps(run(sid, page, a.sheets), ensure_ascii=False), flush=True)
            except Exception as e:  # noqa: BLE001 — report and continue with the other scenarios
                failed.append(sid)
                print(json.dumps({"id": sid, "error": f"{type(e).__name__}: {str(e)[:300]}"}, ensure_ascii=False), flush=True)
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
