"""Build the generic 14-inch notebook models used by the notebook-manufacturing scenes.

Two GLBs are produced (own procedural geometry, brand-neutral, free to use in customer material):
  static/assets/notebook/laptop14_open.glb    lid open 110° — context shell for the thermal-module / chassis scenes
  static/assets/notebook/laptop14_closed.glb  lid closed     — work-piece instances on the assembly line, units in packaging

    python assets/build_laptop.py

Geometry is modelled in mm (CadQuery, Z-up); OCCT's glTF writer keeps mm and rotates the root to Y-up, so in a
three.js scene with 1 unit = 1 mm the loaded scene needs no scaling. Orientation after loading (verified r160):
x = width (±156), y = up (base top at y = 12), z = depth with the palm rest at +z (front) and the hinge at −z.
Named nodes (OCCT emits one mesh per face, names are prefixed): base*, keys*, touchpad*, ports*, hinge_l*, hinge_r*,
lid*, screen*, feet*.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import cadquery as cq

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "static" / "assets" / "notebook"

# Proportions follow a 13.8" 3:2 premium ultraportable (Surface-Laptop-like): 301 × 220 footprint, wedge body
# 14.5 mm at the hinge tapering to ~9.5 mm at the palm-rest edge, 3:2 display with 5 mm bezels, large touchpad.
W, D, H_BASE = 301.0, 220.0, 14.5          # base footprint and rear thickness (mm)
LID_W, LID_D, LID_T = 301.0, 212.0, 4.2     # lid (A + B cover) footprint and thickness
SCREEN_W, SCREEN_H = 288.0, 192.0           # active area, 3:2
CORNER_R, EDGE_R = 7.0, 2.0
TAPER_DROP, TAPER_RUN = 5.0, 150.0          # underside wedge: drops 5 mm over the front 150 mm
HINGE_Y = D / 2 - 6.0                        # hinge axis (CadQuery +Y = rear)
KEY_PITCH, KEY_SIZE, KEY_H = 19.0, 16.4, 1.0
KEY_ROWS, KEY_COLS = 6, 14
KEY_AREA_W = KEY_COLS * KEY_PITCH            # 266 mm
KEY_CENTER_Y = 30.0                          # keyboard block centre (rear half of the deck)
TOUCHPAD_W, TOUCHPAD_D, TOUCHPAD_Y = 130.0, 88.0, -62.0


def rounded_slab(w: float, d: float, t: float, corner: float, edge: float) -> cq.Workplane:
    slab = cq.Workplane("XY").sketch().rect(w, d).vertices().fillet(corner).finalize().extrude(t)
    try:
        slab = slab.edges("|X or |Y").fillet(edge)   # soften the horizontal edges (unibody look)
    except Exception:  # noqa: BLE001
        pass
    return slab


def base() -> cq.Workplane:
    b = rounded_slab(W, D, H_BASE, CORNER_R, EDGE_R)
    # wedge underside: the body gets thinner towards the palm rest (front = -Y)
    wedge = (cq.Workplane("YZ").polyline([(-D / 2 - 1, -1), (-D / 2 - 1, TAPER_DROP), (-D / 2 + TAPER_RUN, -1)]).close()
             .extrude(W / 2 + 2, both=True))
    b = b.cut(wedge)
    # keyboard recess (1.6 mm deep) and touchpad recess (0.5 mm deep)
    b = b.faces(">Z").workplane().center(0, KEY_CENTER_Y).rect(KEY_AREA_W + 6, KEY_ROWS * KEY_PITCH + 6).cutBlind(-1.6)
    b = b.faces(">Z").workplane().center(0, TOUCHPAD_Y).rect(TOUCHPAD_W + 2, TOUCHPAD_D + 2).cutBlind(-0.5)
    # ports: left side USB-C ×2 + audio, right side a single magnetic charging connector
    for (y, w, h) in ((40, 9, 3.4), (56, 9, 3.4), (80, 6.5, 6.5)):
        b = b.cut(cq.Workplane("YZ").workplane(offset=-W / 2 - 1).center(-y + 40, H_BASE / 2 - 1).rect(w, h).extrude(12))
    b = b.cut(cq.Workplane("YZ").workplane(offset=W / 2 - 11).center(-40 + 40, H_BASE / 2 - 1).rect(14, 4.5).extrude(12))
    # vent slots on the rear face (thermal exhaust towards the hinge)
    for x in range(-120, 121, 8):
        b = b.cut(cq.Workplane("XZ").workplane(offset=-D / 2 - 1).center(x, H_BASE / 2).rect(5, 5).extrude(-12))
    return b


def keys() -> cq.Workplane:
    caps = cq.Workplane("XY").workplane(offset=H_BASE - 1.6)
    pts = []
    for r in range(KEY_ROWS):
        y = KEY_CENTER_Y + (r - (KEY_ROWS - 1) / 2) * KEY_PITCH
        if r == 0:   # bottom row: space bar in the middle, modifiers on the sides
            for c in (-6, -5, -4, 4, 5, 6):
                pts.append((c * KEY_PITCH, y))
            continue
        for c in range(KEY_COLS):
            pts.append(((c - (KEY_COLS - 1) / 2) * KEY_PITCH, y))
    caps = caps.pushPoints(pts).rect(KEY_SIZE, KEY_SIZE).extrude(KEY_H)
    space = cq.Workplane("XY").workplane(offset=H_BASE - 1.6).center(0, KEY_CENTER_Y - (KEY_ROWS - 1) / 2 * KEY_PITCH).rect(6 * KEY_PITCH + KEY_SIZE - KEY_PITCH, KEY_SIZE).extrude(KEY_H)
    caps = caps.union(space)
    try:
        caps = caps.edges("|Z").fillet(1.8)
    except Exception:  # noqa: BLE001
        pass
    return caps


def touchpad() -> cq.Workplane:
    return (cq.Workplane("XY").workplane(offset=H_BASE - 0.5).center(0, TOUCHPAD_Y)
            .sketch().rect(TOUCHPAD_W, TOUCHPAD_D).vertices().fillet(5).finalize().extrude(0.3))


def hinge(x: float) -> cq.Workplane:
    return cq.Workplane("YZ").workplane(offset=x - 22).center(HINGE_Y, H_BASE).circle(4.2).extrude(44)


def lid(open_deg: float) -> tuple[cq.Workplane, cq.Workplane]:
    """Lid + screen, modelled closed on top of the base then rotated open about the hinge axis."""
    body = rounded_slab(LID_W, LID_D, LID_T, CORNER_R, 1.6).translate((0, HINGE_Y - LID_D / 2, H_BASE))
    screen = (cq.Workplane("XY").workplane(offset=H_BASE - 0.3).center(0, HINGE_Y - LID_D / 2 + 2)
              .sketch().rect(SCREEN_W, SCREEN_H).vertices().fillet(3).finalize().extrude(0.6))   # 3:2 panel, ~5 mm bezels
    if open_deg:
        axis_start, axis_end = (-1, HINGE_Y, H_BASE), (1, HINGE_Y, H_BASE)
        body = body.rotate(axis_start, axis_end, -open_deg)
        screen = screen.rotate(axis_start, axis_end, -open_deg)
    return body, screen


def feet() -> cq.Workplane:
    return cq.Workplane("XY").pushPoints([(-120, -80), (120, -80), (-120, 80), (120, 80)]).rect(30, 8).extrude(-1.2)


def build(open_deg: float) -> cq.Assembly:
    alu = cq.Color(0.80, 0.80, 0.78, 1.0)      # "platinum" anodised aluminium
    dark = cq.Color(0.11, 0.11, 0.12, 1.0)
    assy = cq.Assembly(name="laptop14")
    assy.add(base(), name="base", color=alu)
    assy.add(keys(), name="keys", color=dark)
    assy.add(touchpad(), name="touchpad", color=cq.Color(0.86, 0.86, 0.85, 1.0))
    assy.add(hinge(-100), name="hinge_l", color=dark)
    assy.add(hinge(100), name="hinge_r", color=dark)
    lid_body, screen = lid(open_deg)
    assy.add(lid_body, name="lid", color=alu)
    assy.add(screen, name="screen", color=cq.Color(0.04, 0.05, 0.08, 1.0))
    assy.add(feet(), name="feet", color=dark)
    return assy


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, deg in (("laptop14_open.glb", 110.0), ("laptop14_closed.glb", 0.0)):
        out = OUT_DIR / name
        build(deg).export(str(out), exportType="GLTF", tolerance=0.4, angularTolerance=0.3)
        print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
    (OUT_DIR / "SOURCE.txt").write_text(
        "laptop14_open.glb / laptop14_closed.glb — generic 14-inch notebook, procedurally generated by assets/build_laptop.py (CadQuery / OCCT).\n"
        "Own asset, no third-party geometry; free to use in customer-facing material.\n"
        f"Base {W:.0f} × {D:.0f} mm, {H_BASE:.1f} mm at the hinge tapering to {H_BASE - TAPER_DROP:.1f} mm at the front; lid {LID_W:.0f} × {LID_D:.0f} × {LID_T:.1f} mm, 3:2 display {SCREEN_W:.0f} × {SCREEN_H:.0f}; open variant lid at 110°.\n"
        "glTF keeps mm; root node rotated to Y-up. In three.js (1 unit = 1 mm): x = width ±150, y = up (base top y = 14.5, open lid up to y ≈ 215),\n"
        "z = depth: palm rest / touchpad at +z (front, z ≈ +62), keyboard around z ≈ −30, hinge at z ≈ −104. No scaling needed.\n"
        "Nodes (prefix match, one mesh per face): base*, keys*, touchpad*, hinge_l*, hinge_r*, lid*, screen*, feet*.\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
