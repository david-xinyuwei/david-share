import cadquery as cq
import math

# Magnesium die-cast A-cover (display lid) — Track B reference script (scenario: 312×217, R8, main wall 0.8, flange 6.5 high and 1.0 thick, ribs 0.8×2.0 at 45 pitch,
# 3 φ4.5×3.5 bosses at each hinge area, 10 mm antenna clearance zone at the top with a PC+GF insert, 3 wide adhesive groove). Both mould halves are conceptual outlines for exploded and closed views.
P = {
    "L": 312.0, "W": 217.0, "R": 8.0, "wall": 0.8, "flangeH": 6.5, "flangeT": 1.0, "draft": 1.0,
    "ribW": 0.8, "ribH": 2.0, "ribPitch": 45.0,
    "bossD": 4.5, "bossH": 3.5, "bossHoleD": 1.6, "bossN": 3, "bossPitch": 14.0, "hingeInset": 28.0,
    "antennaW": 10.0, "glueW": 3.0, "glueDepth": 0.3,
    "moldClear": 40.0, "coreH": 30.0, "cavityH": 36.0, "gateW": 60.0, "gateT": 1.2, "overflowN": 4, "overflowD": 8.0,
    "mgDensity": 1.81, "pcDensity": 1.35, "steelDensity": 7.85,
}
DENSITY = P["mgDensity"]
L, W, R, t = P["L"], P["W"], P["R"], P["wall"]
fh, ft = P["flangeH"], P["flangeT"]

# ---- A-cover body: top plate + flange all round (real wall thickness), extruded from the outline and then shelled
outer = cq.Workplane("XY").rect(L, W).extrude(fh + t).edges("|Z").fillet(R)
shell = outer.faces("<Z").shell(-t)                       # Shell open downward: top plate thickness t, flange thickness t (the 1.0 flange is thickened afterwards)
# Flange thickened to 1.0 (0.2 mm added all round on the inside)
inner_ring = (cq.Workplane("XY").rect(L - 2 * t, W - 2 * t).rect(L - 2 * ft, W - 2 * ft).extrude(fh))
try:
    inner_ring = inner_ring.edges("|Z").fillet(R - t)
except Exception:  # noqa: BLE001
    pass
cover = shell.union(inner_ring)
# Fillet on the outer top edge (A-surface look)
try:
    cover = cover.faces(">Z").edges().fillet(1.2)
except Exception:  # noqa: BLE001
    pass
# Inner rib grid: several ribs along X and Y, 2.0 high, 0.8 wide, from the inside of the top plate downward
nx = int((L - 40) // P["ribPitch"]); ny = int((W - 40) // P["ribPitch"])
xs = [(i - (nx - 1) / 2) * P["ribPitch"] for i in range(nx)]
ys = [(j - (ny - 1) / 2) * P["ribPitch"] for j in range(ny)]
ribs = cq.Workplane("XY").workplane(offset=fh - P["ribH"]).pushPoints([(x, 0) for x in xs]).rect(P["ribW"], W - 2 * ft - 4).extrude(P["ribH"] + 0.05)
ribs = ribs.union(cq.Workplane("XY").workplane(offset=fh - P["ribH"]).pushPoints([(0, y) for y in ys]).rect(L - 2 * ft - 4, P["ribW"]).extrude(P["ribH"] + 0.05))
cover = cover.union(ribs)
# Two hinge mounting areas: 3 φ4.5×3.5 bosses each (with φ1.6 blind holes), on the hinge-side long edge (-Y)
boss_pts = [(sx * (L / 2 - P["hingeInset"]) + (k - 1) * P["bossPitch"] * sx, -W / 2 + 14) for sx in (-1, 1) for k in range(P["bossN"])]
bosses = cq.Workplane("XY").workplane(offset=fh - P["bossH"]).pushPoints(boss_pts).circle(P["bossD"] / 2).extrude(P["bossH"] + 0.05)
bosses = bosses.cut(cq.Workplane("XY").workplane(offset=fh - P["bossH"] - 0.1).pushPoints(boss_pts).circle(P["bossHoleD"] / 2).extrude(P["bossH"] - 0.6))
cover = cover.union(bosses)
# Antenna clearance zone: a 10 mm strip at the top without magnesium, filled by a PC+GF insert (long edge opposite the hinges, +Y)
antenna_cut = cq.Workplane("XY").workplane(offset=fh - 0.05).center(0, W / 2 - P["antennaW"] / 2 - 2).rect(L - 2 * R - 10, P["antennaW"]).extrude(t + 1)
cover = cover.cut(antenna_cut)
insert = cq.Workplane("XY").workplane(offset=fh).center(0, W / 2 - P["antennaW"] / 2 - 2).rect(L - 2 * R - 10, P["antennaW"]).extrude(t)
try:
    insert = insert.edges("|Z").fillet(1.0)
except Exception:  # noqa: BLE001
    pass
# Display adhesive groove: 3 mm wide, 0.3 deep around the flange top (shell opening) (cut into the flange end face, in practice a step on the inside of the flange)
glue = cq.Workplane("XY").rect(L - 2 * ft, W - 2 * ft).rect(L - 2 * ft - 2 * P["glueW"], W - 2 * ft - 2 * P["glueW"]).extrude(P["glueDepth"])
cover = cover.cut(glue)

# ---- Mould concept: moving half (core, carrying the shape of the shell interior) and fixed half (cavity). Closed: fixed half on top, moving half below, parting plane at the flange top z=0.
mL, mW = L + 2 * P["moldClear"], W + 2 * P["moldClear"]
core = cq.Workplane("XY").rect(mL, mW).extrude(-P["coreH"]).edges("|Z").fillet(6)
core = core.union(cq.Workplane("XY").rect(L - 2 * ft, W - 2 * ft).extrude(fh - t).edges("|Z").fillet(R - ft))   # Core boss = shell interior
core = core.faces("<Z").workplane().pushPoints([(sx * (mL / 2 - 18), sy * (mW / 2 - 18)) for sx in (-1, 1) for sy in (-1, 1)]).hole(12.0)   # Guide pin holes
cavity = cq.Workplane("XY").workplane(offset=fh + t).rect(mL, mW).extrude(P["cavityH"]).edges("|Z").fillet(6)
cavity = cavity.cut(cq.Workplane("XY").rect(L, W).extrude(fh + t + 0.01).edges("|Z").fillet(R))                   # Cavity = shell exterior
cavity = cavity.union(cq.Workplane("XY").workplane(offset=fh + t).pushPoints([(sx * (mL / 2 - 18), sy * (mW / 2 - 18)) for sx in (-1, 1) for sy in (-1, 1)]).circle(5.9).extrude(-P["coreH"] * 0.6))  # Guide pins
# Fan gate (hinge-side long edge -Y) and 4 overflows on the opposite side: cut into the parting face of the fixed half
gate = cq.Workplane("XY").workplane(offset=fh + t - P["gateT"]).center(0, -W / 2 - 14).rect(P["gateW"], 28).extrude(P["gateT"] + 0.05)
cavity = cavity.cut(gate)
cavity = cavity.cut(cq.Workplane("XY").workplane(offset=fh + t - 3).pushPoints([((k - 1.5) * 70, W / 2 + 10) for k in range(P["overflowN"])]).circle(P["overflowD"] / 2).extrude(3.05))
try:
    cavity = cavity.faces(">Z").edges("not %CIRCLE").chamfer(2.0)
    core = core.faces("<Z").edges("not %CIRCLE").chamfer(2.0)
except Exception:  # noqa: BLE001
    pass

result = cover.union(insert).union(core).union(cavity)

PARTS = {"Magnesium A-cover": cover, "Antenna zone PC+GF insert": insert, "Moving half (core)": core, "Fixed half (cavity)": cavity}
MATERIALS = {"Magnesium A-cover": "aluminumCast", "Antenna zone PC+GF insert": "polymerLight", "Moving half (core)": "steelDark", "Fixed half (cavity)": "steelDark"}
DENSITIES = {"Antenna zone PC+GF insert": P["pcDensity"], "Moving half (core)": P["steelDensity"], "Fixed half (cavity)": P["steelDensity"]}
NAME = "Magnesium A-cover and die-casting mould"

proj_area_cm2 = L * W / 100
clamp_kN = 60.0 * (L * W) / 1000 * 1.2
METRICS = [
    {"label": "Projected area", "value": round(proj_area_cm2, 1), "unit": "cm²", "note": "Outline 312 × 217"},
    {"label": "Clamping force estimate", "value": round(clamp_kN / 9.80665, 0), "unit": "t", "note": "60 MPa specific pressure × projected area × safety factor 1.2"},
    {"label": "Ribs", "value": f"{nx} longitudinal + {ny} transverse", "unit": "ribs", "note": f"{P['ribW']} × {P['ribH']} mm, pitch {P['ribPitch']:g}"},
    {"label": "Screw bosses", "value": f"{2 * P['bossN']} × φ{P['bossD']}×{P['bossH']}", "unit": "mm", "note": "3 at each hinge area, M2 blind holes"},
    {"label": "Mould envelope", "value": f"{mL:g} × {mW:g} × {P['coreH'] + P['cavityH'] + fh + t:g}", "unit": "mm", "note": "Closed height of moving + fixed half (concept)"},
]
