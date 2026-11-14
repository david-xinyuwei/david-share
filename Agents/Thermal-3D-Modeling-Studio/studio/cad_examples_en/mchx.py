import cadquery as cq
import math

# Micro-channel heat exchanger core — Track B reference script (scenario: 24 flat tubes 16×1.3 × 300 long, tube pitch 8; φ20 headers at both ends; φ12 inlet and outlet on the same side; fins simplified to straight fins)
P = {
    "tubeN": 24, "tubeW": 16.0, "tubeT": 1.3, "tubeLen": 300.0, "tubePitch": 8.0, "tubeWall": 0.35, "tubeChannels": 8,   # Flat tubes: real wall thickness + 8 micro-channels
    "headerD": 20.0, "headerWall": 1.2, "headerExtra": 12.0,                                                             # Headers extend 12 mm beyond the tube stack at each end
    "portD": 12.0, "portWall": 1.0, "portLen": 30.0, "portInsert": 3.0,
    "finPerGap": 12, "finT": 0.4, "finEquivNote": "Real fin pitch 1.2 mm → about 240 fins per gap, modelled as 12 equivalent fins (0.4 mm thick), area scaled proportionally",
    "bracketT": 2.0, "bracketW": 25.0, "bracketH": 30.0, "bracketHoleD": 6.6,                                            # Mounting brackets at both ends + M6 holes
    "aluminumDensity": 2.70,
}
DENSITY = P["aluminumDensity"]
n, w, t, L, pitch = int(P["tubeN"]), P["tubeW"], P["tubeT"], P["tubeLen"], P["tubePitch"]
stack = (n - 1) * pitch                    # Tube stack height (arrayed along Z)
zs = [(i - (n - 1) / 2) * pitch for i in range(n)]
hd, hw = P["headerD"], P["headerWall"]
header_len = stack + t + 2 * P["headerExtra"]

# ---- Flat tubes (24, 300 long along X, 16×1.3 section with 8 micro-channel holes): build one, then rarray
ch_w = (w - 2 * P["tubeWall"] - (P["tubeChannels"] - 1) * P["tubeWall"]) / P["tubeChannels"]
ch_h = t - 2 * P["tubeWall"]
one_tube = cq.Workplane("YZ").rect(w, t).extrude(L).translate((-L / 2, 0, 0))
try:
    one_tube = one_tube.edges("|X").fillet(t / 2 - 0.05)                                   # Rounded tube edges
except Exception:  # noqa: BLE001
    pass
channels = (cq.Workplane("YZ").rarray(ch_w + P["tubeWall"], 1, P["tubeChannels"], 1).rect(ch_w, ch_h).extrude(L + 2).translate((-L / 2 - 1, 0, 0)))
one_tube = one_tube.cut(channels)
tubes = cq.Workplane("XY").newObject([one_tube.val().moved(cq.Location(cq.Vector(0, 0, z))) for z in zs])

# ---- Fins: 12 equivalent straight fins per tube gap (0.4 thick, 16 wide, height = gap pitch - t), evenly spaced along X
gap = pitch - t
fin_list = []
fin_pitch_x = L / P["finPerGap"]
for i in range(n - 1):
    zc = (zs[i] + zs[i + 1]) / 2
    for k in range(P["finPerGap"]):
        x = -L / 2 + fin_pitch_x * (k + 0.5)
        fin_list.append(cq.Solid.makeBox(P["finT"], w, gap, cq.Vector(x - P["finT"] / 2, -w / 2, zc - gap / 2)))
fins = cq.Workplane("XY").newObject([cq.Compound.makeCompound(fin_list)])

# ---- Headers (both ends, along Z), real wall thickness, end caps, tube slots
def header(x_center: float, with_ports: bool) -> cq.Workplane:
    h = cq.Workplane("XY").workplane(offset=-header_len / 2).center(x_center, 0).circle(hd / 2).circle(hd / 2 - hw).extrude(header_len)
    cap_bot = cq.Workplane("XY").workplane(offset=-header_len / 2 - 1.5).center(x_center, 0).circle(hd / 2).extrude(1.5)
    cap_top = cq.Workplane("XY").workplane(offset=header_len / 2).center(x_center, 0).circle(hd / 2).extrude(1.5)
    h = h.union(cap_bot).union(cap_top)
    try:
        h = h.faces(">Z").edges().fillet(1.2)
        h = h.faces("<Z").edges().fillet(1.2)
    except Exception:  # noqa: BLE001
        pass
    # Tube slots through the header wall facing the tube stack
    sign = -1 if x_center > 0 else 1
    for z in zs:
        h = h.cut(cq.Solid.makeBox(hw + 1, w + 0.1, t + 0.1, cq.Vector(x_center + sign * (hd / 2) - (hw + 1) / 2 - sign * 0.5, -(w + 0.1) / 2, z - (t + 0.1) / 2)))
    # Internal baffle: splits the header into two passes (typical 2-pass layout)
    h = h.union(cq.Workplane("XY").workplane(offset=zs[n // 2] - pitch / 2 - 0.5).center(x_center, 0).circle(hd / 2 - hw + 0.05).extrude(1.0))
    if with_ports:
        for z, direction in ((zs[2], 1), (zs[-3], 1)):
            h = h.cut(cq.Solid.makeCylinder(P["portD"] / 2 + P["portWall"] + 0.05, hd / 2 + 1, cq.Vector(x_center, 0, z), cq.Vector(0, 1, 0)))
    return h
header_in = header(-L / 2 - hd / 2 + 0.5, True)     # Inlet and outlet both on this side
header_out = header(L / 2 + hd / 2 - 0.5, False)

# ---- Inlet and outlet fittings: φ12 aluminium tube, real wall thickness, chamfered end, inserted 3 mm into the header
ports = []
for z in (zs[2], zs[-3]):
    y0 = hd / 2 - P["portInsert"]
    port = cq.Workplane("XZ").workplane(offset=-y0).center(-L / 2 - hd / 2 + 0.5, z).circle(P["portD"] / 2 + P["portWall"]).circle(P["portD"] / 2).extrude(-P["portLen"])
    try:
        port = port.faces(">Y").chamfer(0.5)
    except Exception:  # noqa: BLE001
        pass
    ports.append(port)
port_in, port_out = ports

# ---- Mounting brackets at both ends (L-shaped sheet metal, M6 holes), welded to the outside of the headers
brackets = []
for x_center in (-L / 2 - hd / 2 + 0.5, L / 2 + hd / 2 - 0.5):
    sign = -1 if x_center < 0 else 1
    br = cq.Workplane("XY").workplane(offset=header_len / 2 - P["bracketH"]).center(x_center + sign * (hd / 2 + P["bracketT"] / 2), 0).rect(P["bracketT"], P["bracketW"]).extrude(P["bracketH"] + 6)
    foot = cq.Workplane("XY").workplane(offset=header_len / 2 + 6 - P["bracketT"]).center(x_center + sign * (hd / 2 + 8), 0).rect(16, P["bracketW"]).extrude(P["bracketT"])
    br = br.union(foot)
    br = br.faces(">Z").workplane().center(x_center + sign * (hd / 2 + 10), 0).hole(P["bracketHoleD"])
    try:
        br = br.edges("|Z").fillet(1.5)
    except Exception:  # noqa: BLE001
        pass
    brackets.append(br)
bracket_l, bracket_r = brackets

# `.val()` would take only the first of the 24 tubes: collect every solid on each stack so result == union of PARTS (rule 9).
def _solids(wp):
    return [v for v in wp.vals() if isinstance(v, cq.Shape)]
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound(
    _solids(tubes) + _solids(fins) + _solids(header_in) + _solids(header_out) + _solids(port_in) + _solids(port_out) + _solids(bracket_l) + _solids(bracket_r))])

PARTS = {"Aluminium flat tubes × 24": tubes, "Straight fins (equivalent)": fins, "Inlet-side header": header_in, "Outlet-side header": header_out,
         "Inlet fitting": port_in, "Outlet fitting": port_out, "Mounting bracket (left)": bracket_l, "Mounting bracket (right)": bracket_r}
MATERIALS = {"Aluminium flat tubes × 24": "aluminum", "Straight fins (equivalent)": "aluminumCast", "Inlet-side header": "aluminum", "Outlet-side header": "aluminum",
             "Inlet fitting": "aluminum", "Outlet fitting": "aluminum", "Mounting bracket (left)": "powderCoat", "Mounting bracket (right)": "powderCoat"}
DENSITIES = {"Mounting bracket (left)": 7.90, "Mounting bracket (right)": 7.90}
NAME = "Micro-channel heat exchanger core"

tube_area = n * 2 * (w + t) * L / 100
real_fins = (n - 1) * int(L / 1.2)
fin_area = real_fins * 2 * w * gap / 100
METRICS = [
    {"label": "Flat tube outer area", "value": round(tube_area, 1), "unit": "cm²", "note": f"{n} tubes × perimeter × {L} mm"},
    {"label": "Fin area (real)", "value": round(fin_area, 1), "unit": "cm²", "note": f"{real_fins} fins × 2 faces (1.2 mm pitch)"},
    {"label": "Total heat-transfer area", "value": round(tube_area + fin_area, 1), "unit": "cm²", "note": "Tubes + fins"},
    {"label": "Fin equivalence", "value": f"{P['finPerGap']} ≙ {int(L / 1.2)} fins/gap", "unit": "", "note": P["finEquivNote"]},
]
