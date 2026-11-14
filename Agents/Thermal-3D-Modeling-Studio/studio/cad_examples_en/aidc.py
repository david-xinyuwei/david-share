import cadquery as cq
import math

# AIDC GPU liquid-cooling cold plate — Track B reference script (scenario: base 110×90×3, micro-channel fins 0.3 wide / 3 high / 0.6 pitch, 2 mm cover, φ8 inlet and outlet at both ends of the short side)
P = {
    "baseL": 110.0, "baseW": 90.0, "baseT": 3.0, "coverT": 2.0, "cornerR": 4.0, "edgeChamfer": 0.5,
    "finW": 0.3, "finH": 3.0, "finPitch": 0.6, "finFieldL": 70.0, "finFieldW": 60.0, "finEquiv": 50,   # 100 real fins → 50 equivalent fins (pitch ×2, area scaled proportionally)
    "manifoldW": 10.0, "manifoldDepth": 2.5,                                                             # Manifold grooves on both sides of the fin field
    "portD": 8.0, "portWall": 1.0, "portLen": 18.0, "portBeadD": 10.0, "portInsert": 3.0,
    "lugW": 12.0, "lugL": 10.0, "holeD": 3.4, "cboreD": 6.0, "cboreDepth": 2.0,                         # 4×M3 counterbored mounting lugs
    "oringW": 1.5, "oringDepth": 1.0, "oringInset": 4.0,
    "seatPad": 60.0, "seatPadDepth": 0.2,                                                                # GPU contact pad on the bottom (polished area)
    "copperDensity": 8.96, "aluminumDensity": 2.70,
}
DENSITY = P["copperDensity"]
L, W, T, Tc = P["baseL"], P["baseW"], P["baseT"], P["coverT"]
fin_n = int(P["finEquiv"])
fin_pitch = P["finFieldW"] / fin_n            # Equivalent pitch (1.2 mm)
fin_w = P["finW"] * (fin_pitch / P["finPitch"])  # Equivalent fin width (0.6 mm), keeping the fin duty ratio
H_total = T + P["finH"] + Tc

# ---- Base: rounded rectangle + fin field + manifold grooves on both sides + counterbored lugs at the four corners + O-ring groove + bottom contact pad
base = cq.Workplane("XY").box(L, W, T).translate((0, 0, T / 2)).edges("|Z").fillet(P["cornerR"])
lug_pts = [(sx * (L / 2 + P["lugL"] / 2 - 2), sy * (W / 2 - P["lugW"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
lugs = cq.Workplane("XY").pushPoints(lug_pts).rect(P["lugL"] + 4, P["lugW"]).extrude(T)
lugs = lugs.edges("|Z").fillet(3.0)
base = base.union(lugs)
hole_pts = [(sx * (L / 2 + P["lugL"] / 2), sy * (W / 2 - P["lugW"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
base = base.faces(">Z").workplane().pushPoints(hole_pts).cboreHole(P["holeD"], P["cboreD"], P["cboreDepth"])
# Fin field (50 equivalent fins, arrayed along X, flow along Y)
fins = (cq.Workplane("XY").workplane(offset=T).rarray(fin_pitch, 1, fin_n, 1).rect(fin_w, P["finFieldL"]).extrude(P["finH"]))
fins = fins.translate((0, 0, 0))
# Manifold grooves: sunk manifoldDepth into the base at both ends (±Y) of the fin field to spread the coolant sideways
for sy in (-1, 1):
    base = base.cut(cq.Workplane("XY").workplane(offset=T - P["manifoldDepth"]).center(0, sy * (P["finFieldL"] / 2 + P["manifoldW"] / 2)).rect(P["finFieldW"] + 2, P["manifoldW"]).extrude(P["manifoldDepth"] + 0.1))
# O-ring groove (around the top face)
og_w, og_d, inset = P["oringW"], P["oringDepth"], P["oringInset"]
oring = cq.Workplane("XY").workplane(offset=T - og_d).rect(L - 2 * inset, W - 2 * inset).rect(L - 2 * inset - 2 * og_w, W - 2 * inset - 2 * og_w).extrude(og_d + 0.1)
try:
    oring = oring.edges("|Z").fillet(og_w)
except Exception:  # noqa: BLE001
    pass
base = base.cut(oring)
# GPU contact pad on the bottom: periphery sunk 0.2 mm, the central 60×60 kept as the polished contact face
pad_cut = cq.Workplane("XY").rect(L + 2, W + 2).rect(P["seatPad"], P["seatPad"]).extrude(P["seatPadDepth"]).translate((0, 0, -0.0))
base = base.cut(pad_cut)
# Inlet and outlet: both ends of the short side, entering the manifold grooves horizontally
port_z = T - P["manifoldDepth"] / 2 + P["finH"] / 2
ports = []
for sx in (-1, 1):
    x0 = sx * (L / 2 + P["portLen"] - P["portInsert"])
    direction = cq.Vector(-sx, 0, 0)
    body = cq.Solid.makeCylinder(P["portD"] / 2 + P["portWall"], P["portLen"], cq.Vector(x0, 0, port_z), direction)
    bead = cq.Solid.makeCylinder(P["portBeadD"] / 2, 2.5, cq.Vector(x0 - sx * 4, 0, port_z), direction)
    port = cq.Workplane("XY").newObject([body]).union(bead)
    port = port.cut(cq.Solid.makeCylinder(P["portD"] / 2, P["portLen"] + 2, cq.Vector(x0 + sx, 0, port_z), direction))
    try:
        port = port.faces(">X" if sx > 0 else "<X").chamfer(0.5)
    except Exception:  # noqa: BLE001
        pass
    ports.append(port)
    base = base.cut(cq.Solid.makeCylinder(P["portD"] / 2 + P["portWall"] + 0.05, P["portInsert"] + 0.1, cq.Vector(sx * (L / 2 + 0.1), 0, port_z), direction))
inlet, outlet = ports

# ---- Cover: same outline, central weight-saving recess, nameplate recess on top, chamfered edges; the cover cavity houses the fins
cover = cq.Workplane("XY").box(L, W, Tc).translate((0, 0, T + P["finH"] + Tc / 2)).edges("|Z").fillet(P["cornerR"])
cavity = cq.Workplane("XY").workplane(offset=T).rect(P["finFieldW"] + 2 * P["manifoldW"] + 6, P["finFieldL"] + 2 * P["manifoldW"]).extrude(P["finH"])
cover_skirt = cq.Workplane("XY").workplane(offset=T).rect(L - 2 * inset + og_w, W - 2 * inset + og_w).extrude(P["finH"]).edges("|Z").fillet(2.0)
cover = cover.union(cover_skirt).cut(cavity)
cover = cover.faces(">Z").workplane().rect(40, 14).cutBlind(-0.3)                                         # Nameplate recess
cover = cover.faces(">Z").workplane().pushPoints([(-30, 0), (30, 0)]).slot2D(18, 4).cutBlind(-0.4)         # Two weight-saving slots
try:
    cover = cover.faces(">Z").edges("not %CIRCLE").chamfer(P["edgeChamfer"])
except Exception:  # noqa: BLE001
    pass

result = base.union(fins).union(cover).union(inlet).union(outlet)

PARTS = {"Copper base plate": base, "Micro-channel fins (50 equivalent)": fins, "Top cover": cover, "Inlet fitting": inlet, "Outlet fitting": outlet}
MATERIALS = {"Copper base plate": "copper", "Micro-channel fins (50 equivalent)": "copper", "Top cover": "anodized", "Inlet fitting": "steel", "Outlet fitting": "steel"}
DENSITIES = {"Top cover": P["aluminumDensity"], "Inlet fitting": 7.90, "Outlet fitting": 7.90}
NAME = "GPU liquid-cooling cold plate"

real_fin_n = int(P["finFieldW"] / P["finPitch"])
real_area = real_fin_n * 2 * P["finH"] * P["finFieldL"] / 100  # cm²
METRICS = [
    {"label": "Fin equivalence", "value": f"{fin_n} fins ≙ {real_fin_n} fins", "unit": "", "note": f"Equivalent pitch {fin_pitch:.1f} mm / width {fin_w:.1f} mm, same duty ratio"},
    {"label": "Real fin heat-transfer area", "value": round(real_area, 1), "unit": "cm²", "note": f"{real_fin_n} fins × 2 faces × {P['finH']} × {P['finFieldL']} mm"},
    {"label": "Base 1-D thermal resistance (copper)", "value": round(P["baseT"] / 1000 / (400 * P["seatPad"] * P["seatPad"] / 1e6) * 1000, 3), "unit": "mK/W", "note": "t/(kA), A = 60×60 contact area, k = 400 W/m·K"},
    {"label": "Mounting holes", "value": "4 × M3 counterbored", "unit": "", "note": f"φ{P['holeD']} / φ{P['cboreD']}×{P['cboreDepth']}"},
]
