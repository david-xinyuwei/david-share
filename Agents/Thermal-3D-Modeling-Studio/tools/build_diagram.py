"""Render the two original figures (English and Chinese): the architecture and the test topology.

    python tools/build_diagram.py            # render images/{architecture,test-topology}-{en,zh}.png, update images/SOURCES.json
    python tools/build_diagram.py --check    # fail if an icon, an HTML source or a PNG differs from images/SOURCES.json

Icons come only from images/icons/ (Microsoft Azure architecture icons V25, unmodified) and must match the ledger by
SHA-256; every ledgered icon must be drawn in one of the figures. Each page is checked for missing icons, clipped text and
anything outside the canvas before a PNG is written. Needs Microsoft Edge and `pip install -r requirements-dev.txt`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "images" / "SOURCES.json"
W, H, SCALE = 1920, 1000, 1.5
FIGURES = {
    "architecture": "Components, who wrote them, and the request path of tracks A-D; not network detail or measured traffic",
    "test-topology": "Where each measured number in Results was produced: machine, code path, called component and what each clock "
                     "covers; not the deployed VM",
}
CHECK = """() => {
  const bad = [];
  document.querySelectorAll('img').forEach(i => { if (!i.complete || i.naturalWidth === 0) bad.push('icon missing: ' + i.src); });
  document.querySelectorAll('.card, .head, .track, .foot, .box, .bh, .clock').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1) bad.push('clipped: ' + e.textContent.trim().slice(0, 50));
    const r = e.getBoundingClientRect();
    if (r.left < 0 || r.top < 0 || r.right > %d || r.bottom > %d) bad.push('outside canvas: ' + e.textContent.trim().slice(0, 50));
  });
  document.querySelectorAll('[data-k]').forEach(e => { if (!e.textContent.trim()) bad.push('empty text: ' + e.dataset.k); });
  return bad; }""" % (W, H)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def source(name: str) -> Path:
    return ROOT / "tools" / f"{name}.html"


def check_icons(ledger: dict) -> list[str]:
    html = "".join(source(name).read_text(encoding="utf-8") for name in FIGURES)
    problems = []
    for icon in ledger["icons"]:
        p = ROOT / icon["file"]
        if not p.is_file() or sha(p.read_bytes()) != icon["sha256"]:
            problems.append(f"icon differs from the ledger: {icon['file']}")
        if Path(icon["file"]).name not in html:
            problems.append(f"ledgered icon not drawn: {icon['file']}")
    drawn = {part.split('"')[0] for part in html.split("../images/icons/")[1:]}
    problems += [f"icon not in the ledger: {name}" for name in sorted(drawn - {Path(i["file"]).name for i in ledger["icons"]})]
    return problems


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    problems = check_icons(ledger)
    figures = {f["file"]: f for f in ledger["images"] if f.get("kind") == "original explanatory diagram"}
    if a.check:
        for name in FIGURES:
            html_sha = sha(source(name).read_bytes())
            for lang in ("en", "zh"):
                rel = f"images/{name}-{lang}.png"
                entry, p = figures.get(rel), ROOT / rel
                if not entry or not p.is_file() or sha(p.read_bytes()) != entry["sha256"]:
                    problems.append(f"{rel} differs from the ledger")
                elif entry.get("source_sha256") != html_sha:
                    problems.append(f"{rel} was rendered from another version of tools/{name}.html")
        print("\n".join(problems) or "figures: icons, HTML sources and PNGs match images/SOURCES.json")
        return 1 if problems else 0
    if problems:
        print("\n".join(problems))
        return 1
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        for name, shows in FIGURES.items():
            html_sha = sha(source(name).read_bytes())
            for lang in ("en", "zh"):
                page.goto(source(name).as_uri() + f"?lang={lang}")
                page.wait_for_load_state("load")
                page.evaluate("document.fonts.ready")
                bad = page.evaluate(CHECK)
                if bad:
                    print(f"{name} {lang}: " + "; ".join(bad))
                    browser.close()
                    return 1
                rel = f"images/{name}-{lang}.png"
                page.screenshot(path=str(ROOT / rel))
                w, h = png_size(ROOT / rel)
                figures[rel] = {"file": rel, "sha256": sha((ROOT / rel).read_bytes()), "width": w, "height": h,
                                "kind": "original explanatory diagram", "generator": "tools/build_diagram.py",
                                "source": f"tools/{name}.html", "source_sha256": html_sha,
                                "renderer": f"Microsoft Edge headless via Playwright, {W}x{H} CSS px, device scale factor {SCALE}",
                                "shows": shows}
                print(f"{rel}: {w}x{h}")
        browser.close()
    ledger["images"] = [f for f in ledger["images"] if f.get("kind") != "original explanatory diagram"] + \
                       [figures[k] for k in sorted(figures)]
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
