import cadquery as cq
import math

# EV battery cold plate — Track B reference script (written to CAD_PROMPT rules 9–15, used by tests/test_cad.py and as the prompt few-shot)
P = {
    "plateLength": 320, "plateWidth": 180, "plateThickness": 12, "minimumWall": 1.5,
    "channelRuns": 6, "channelWidth": 10, "channelDepth": 6, "channelPitch": 25, "channelTurnX": 135,
    "coverThickness": 3.0,            # Top cover thickness (channel depth 6 + 3 for each cover = 12)
    "cornerRadius": 6.0, "edgeChamfer": 0.8,
    "lugWidth": 22, "lugLength": 18, "lugHoleDia": 6.6, "cboreDia": 11.0, "cboreDepth": 6.0,   # M6 counterbored mounting lugs
    "oringWidth": 2.4, "oringDepth": 1.8, "oringInset": 6.0,
    "portOD": 12.0, "portID": 8.0, "portLength": 26.0, "portBeadOD": 13.5, "portInsert": 4.0,
    "slotLength": 60, "slotWidth": 8, "slotDepth": 0.6,
    "aluminumDensity": 2.70,
}
DENSITY = P["aluminumDensity"]
L, W, T = P["plateLength"], P["plateWidth"], P["plateThickness"]
n, w, d, pitch, tx = int(P["channelRuns"]), P["channelWidth"], P["channelDepth"], P["channelPitch"], P["channelTurnX"]
cover = P["coverThickness"]
r = pitch / 2
ys = [(i - (n - 1) / 2) * pitch for i in range(n)]
assert cover >= P["minimumWall"] and pitch - w >= P["minimumWall"]

# ---- Channel tool body (6 straights + 5 half-round bends + 2 inlet leads), one union, then one cut
tools = []
for i, y in enumerate(ys):
    xmin = -L / 2 if i in (0, n - 1) else -tx
    tools.append(cq.Solid.makeBox(tx - xmin, w, d, cq.Vector(xmin, y - w / 2, -d / 2)))
half_turn = (cq.Workplane("XZ").polyline([(r - w / 2, -d / 2), (r + w / 2, -d / 2), (r + w / 2, d / 2), (r - w / 2, d / 2)]).close()
             .revolve(180, (0, 0), (0, 1)))
for i in range(n - 1):
    right = i % 2 == 0
    turn = half_turn.rotate((0, 0, 0), (0, 0, 1), -90 if right else 90).translate((tx if right else -tx, (ys[i] + ys[i + 1]) / 2, 0))
    tools.append(turn.val())
channel_tool = cq.Workplane("XY").newObject([tools[0]])
for tl in tools[1:]:
    channel_tool = channel_tool.union(tl)

# ---- Channel base plate (lower 2/3): real rounded outline + channel cavity + counterbored lugs at the four corners + O-ring seal groove
base_t = T - cover
base = cq.Workplane("XY").box(L, W, base_t).translate((0, 0, -cover / 2))
base = base.edges("|Z").fillet(P["cornerRadius"])
# Mounting lugs at the four corners (same thickness as the base, projecting outward), M6 counterbored
lug_pts = [(sx * (L / 2 + P["lugLength"] / 2 - 4), sy * (W / 2 - P["lugWidth"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
lugs = (cq.Workplane("XY").pushPoints(lug_pts).rect(P["lugLength"] + 8, P["lugWidth"]).extrude(base_t).translate((0, 0, -base_t / 2 - cover / 2)))
lugs = lugs.edges("|Z").fillet(min(4.0, P["lugWidth"] / 2 - 0.5))
base = base.union(lugs)
hole_pts = [(sx * (L / 2 + P["lugLength"] / 2), sy * (W / 2 - P["lugWidth"] / 2)) for sx in (-1, 1) for sy in (-1, 1)]
base = base.faces(">Z").workplane().pushPoints(hole_pts).cboreHole(P["lugHoleDia"], P["cboreDia"], P["cboreDepth"])
# Channel cavity: d down from the base top face (the full channel depth is in the base; the cover is flat)
channel_cavity = channel_tool.translate((0, 0, (T / 2 - cover) - d / 2 + 0.0))  # cavity top flush with base top
base = base.cut(channel_cavity)
# O-ring groove: around the base top face, outside the channel area
og_w, og_d, inset = P["oringWidth"], P["oringDepth"], P["oringInset"]
ring_outer = cq.Workplane("XY").rect(L - 2 * inset, W - 2 * inset).extrude(og_d)
ring_inner = cq.Workplane("XY").rect(L - 2 * inset - 2 * og_w, W - 2 * inset - 2 * og_w).extrude(og_d)
oring_groove = ring_outer.cut(ring_inner).edges("|Z").fillet(og_w).translate((0, 0, T / 2 - cover - og_d))
base = base.cut(oring_groove)


def soft_chamfer(wp, selector, size):
    """Chamfer the straight outer edges of one face; OCCT refuses chamfers that run into fillet tangencies, so fall back
    to a smaller size and finally to no chamfer rather than failing the whole part (prompt rule 11)."""
    for s in (size, size / 2, size / 4):
        try:
            return wp.faces(selector).edges("not %CIRCLE").chamfer(s)
        except Exception:  # noqa: BLE001 — geometric failure only; the solid itself is already valid
            continue
    return wp


base = soft_chamfer(base, "<Z", P["edgeChamfer"])

# ---- Top cover: same outline, weight-saving slots (obround), nameplate recess, chamfered edges
lid = cq.Workplane("XY").box(L, W, cover).translate((0, 0, T / 2 - cover / 2))
lid = lid.edges("|Z").fillet(P["cornerRadius"])
lid = (lid.faces(">Z").workplane().pushPoints([(-L / 4, W / 2 - 18), (L / 4, W / 2 - 18), (-L / 4, -W / 2 + 18), (L / 4, -W / 2 + 18)])
       .slot2D(P["slotLength"], P["slotWidth"]).cutBlind(-P["slotDepth"]))
lid = lid.faces(">Z").workplane().center(0, 0).rect(70, 24).cutBlind(-0.3)          # Nameplate recess
lid = soft_chamfer(lid, ">Z", P["edgeChamfer"])

# ---- Inlet and outlet fittings: two diameters (body + sealing collar) + end chamfer + real through-bore, inserted portInsert mm into the base
ports = []
for y in (ys[0], ys[-1]):
    x0 = -L / 2 - P["portLength"] + P["portInsert"]
    body = cq.Solid.makeCylinder(P["portOD"] / 2, P["portLength"], cq.Vector(x0, y, 0), cq.Vector(1, 0, 0))
    bead = cq.Solid.makeCylinder(P["portBeadOD"] / 2, 3.0, cq.Vector(x0 + 6, y, 0), cq.Vector(1, 0, 0))
    port = cq.Workplane("XY").newObject([body]).union(bead)
    try:
        port = port.faces("<X").chamfer(0.6)
    except Exception:  # noqa: BLE001
        pass
    bore = cq.Solid.makeCylinder(P["portID"] / 2, P["portLength"] + 2, cq.Vector(x0 - 1, y, 0), cq.Vector(1, 0, 0))
    ports.append(port.cut(bore))
    base = base.cut(cq.Solid.makeCylinder(P["portOD"] / 2 + 0.05, P["portInsert"] + 0.1, cq.Vector(-L / 2 - 0.1, y, 0), cq.Vector(1, 0, 0)))

inlet, outlet = ports
result = base.union(lid).union(inlet).union(outlet)

PARTS = {"Channel base plate": base, "Top cover": lid, "Inlet fitting": inlet, "Outlet fitting": outlet}
MATERIALS = {"Channel base plate": "aluminum", "Top cover": "anodized", "Inlet fitting": "steel", "Outlet fitting": "steel"}
DENSITIES = {"Inlet fitting": 7.90, "Outlet fitting": 7.90}
NAME = "EV battery cold plate"

channel_len = n * (tx + L / 2) + (n - 1) * math.pi * r
METRICS = [
    {"label": "Channel centreline length", "value": round(channel_len, 1), "unit": "mm", "note": "6 straights + 5 half-round bends + inlet leads"},
    {"label": "Channel wetted area", "value": round(2 * (w + d) * channel_len / 100, 1), "unit": "cm²", "note": "Rectangular section perimeter × centreline length"},
    {"label": "Mounting holes", "value": "4 × M6 counterbored", "unit": "", "note": f"φ{P['lugHoleDia']} through / φ{P['cboreDia']}×{P['cboreDepth']} counterbore"},
]
