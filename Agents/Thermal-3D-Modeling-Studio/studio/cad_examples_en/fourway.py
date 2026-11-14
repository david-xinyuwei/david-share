import cadquery as cq
import math

# Four-way reversing valve — Track B reference script (scenario: copper barrel φ34×110, wall 3; tube D on top, tubes E/S/C below at 22 pitch; pilot solenoid valve φ14×45 + two φ3 capillaries)
P = {
    "bodyOD": 34.0, "bodyLen": 110.0, "wall": 3.0,
    "tubeOD": 12.7, "tubeWall": 0.9, "tubeLen": 32.0, "tubeInsert": 3.0, "lowerPitch": 22.0,
    "capT": 3.0, "capFillet": 2.5,                                            # End caps at both ends (filleted)
    "slideLen": 54.0, "slideOD": 26.0, "slideBore": 10.0,                    # Internal slide (main spool), visible in a section
    "pistonOD": 27.6, "pistonT": 4.0,                                         # Pistons at both ends
    "pilotD": 14.0, "pilotLen": 45.0, "pilotOffsetY": 24.0, "pilotZ": 6.0,   # Pilot solenoid valve
    "capD": 3.0, "capWall": 0.5,                                              # Capillary tubes
    "bracketT": 1.5, "bracketW": 14.0, "bracketH": 20.0, "bracketHoleD": 4.5,  # Mounting bracket + M4 holes
    "chamfer": 0.5, "copperDensity": 8.96, "steelDensity": 7.90, "brassDensity": 8.50,
}
DENSITY = P["copperDensity"]
R, L, t = P["bodyOD"] / 2, P["bodyLen"], P["wall"]

# ---- Main valve body: copper barrel along X, end caps, real wall thickness
shell = cq.Workplane("YZ").circle(R).circle(R - t).extrude(L).translate((-L / 2, 0, 0))
cap_l = cq.Workplane("YZ").circle(R).extrude(P["capT"]).translate((-L / 2 - P["capT"], 0, 0))
cap_r = cq.Workplane("YZ").circle(R).extrude(P["capT"]).translate((L / 2, 0, 0))
body = shell.union(cap_l).union(cap_r)
try:
    body = body.faces("<X").edges().fillet(P["capFillet"])
    body = body.faces(">X").edges().fillet(P["capFillet"])
except Exception:  # noqa: BLE001 — cosmetic
    pass
# Four tube sockets: D at top centre, E/S/C evenly spaced on the bottom
ports = [(0.0, 1), (-P["lowerPitch"], -1), (0.0, -1), (P["lowerPitch"], -1)]
for x, s in ports:
    body = body.cut(cq.Solid.makeCylinder(P["tubeOD"] / 2 + 0.05, R + 1, cq.Vector(x, 0, 0), cq.Vector(0, 0, s)))

# ---- Four tubes (real wall thickness, chamfered ends): inserted tubeInsert into the body
tubes = []
for x, s in ports:
    z0 = s * (R - P["tubeInsert"])
    tube = cq.Workplane("XY").workplane(offset=z0 if s > 0 else z0 - P["tubeLen"]).center(x, 0).circle(P["tubeOD"] / 2).circle(P["tubeOD"] / 2 - P["tubeWall"]).extrude(P["tubeLen"])
    try:
        tube = tube.faces(">Z" if s > 0 else "<Z").chamfer(0.4)
    except Exception:  # noqa: BLE001
        pass
    tubes.append(tube)
tube_d, tube_e, tube_s, tube_c = tubes

# ---- Internal slide (main spool, plastic/brass) and end pistons: the reversing mechanism is visible in a section
slide = cq.Workplane("YZ").circle(P["slideOD"] / 2).extrude(P["slideLen"]).translate((-P["slideLen"] / 2 + 8, 0, 0))
slide = slide.cut(cq.Workplane("YZ").circle(P["slideBore"] / 2).extrude(P["slideLen"] + 2).translate((-P["slideLen"] / 2 + 7, 0, 0)))
slide = slide.cut(cq.Solid.makeBox(P["lowerPitch"] * 1.6, P["slideOD"], P["slideOD"] / 2, cq.Vector(-P["lowerPitch"] * 0.8 + 8, -P["slideOD"] / 2, -P["slideOD"] / 2)))  # U-shaped passage underneath (connects E-S or S-C)
piston_l = cq.Workplane("YZ").circle(P["pistonOD"] / 2).extrude(P["pistonT"]).translate((-L / 2 + 6, 0, 0))
piston_r = cq.Workplane("YZ").circle(P["pistonOD"] / 2).extrude(P["pistonT"]).translate((L / 2 - 6 - P["pistonT"], 0, 0))
rod = cq.Workplane("YZ").circle(2.0).extrude(L - 12 - 2 * P["pistonT"]).translate((-L / 2 + 6 + P["pistonT"], 0, 0))
piston_assy = piston_l.union(piston_r).union(rod)

# ---- Pilot solenoid valve: φ14×45 cylinder + stepped coil section on top + wiring boss, seated on a bracket on the side of the body
py_, pz = P["pilotOffsetY"], P["pilotZ"]
pilot = cq.Workplane("YZ").center(py_, pz).circle(P["pilotD"] / 2).extrude(P["pilotLen"]).translate((-P["pilotLen"] / 2, 0, 0))
pilot_coil = cq.Workplane("YZ").center(py_, pz).circle(P["pilotD"] / 2 + 2.0).extrude(18).translate((-9, 0, 0))
pilot_conn = cq.Workplane("XY").workplane(offset=pz + P["pilotD"] / 2 - 1).center(0, py_).rect(8, 6).extrude(6)
pilot = pilot.union(pilot_coil).union(pilot_conn)
try:
    pilot = pilot.faces("<X").chamfer(P["chamfer"])
    pilot = pilot.faces(">X").chamfer(P["chamfer"])
except Exception:  # noqa: BLE001
    pass
pilot_seat = cq.Workplane("XY").workplane(offset=pz - 3).center(0, (py_ + R - 4) / 2).rect(16, py_ - R + 6).extrude(6)  # Seat connecting the body and the pilot valve

# ---- Two φ3 capillaries: from both ends of the pilot valve to the end caps of the main body. Three straight runs + two spherical elbows (sweeping a polyline gives an empty shape in OCCT,
# straight runs + makeSphere elbows are robust; the capillaries are solid, a 0.5 mm wall on φ3 means nothing in a STEP)
def seg(p0, p1):
    v = cq.Vector(*p1) - cq.Vector(*p0)
    return cq.Solid.makeCylinder(P["capD"] / 2, v.Length, cq.Vector(*p0), v.normalized())
def capillary(x_end: float) -> cq.Workplane:
    sign = 1 if x_end > 0 else -1
    a = (sign * (P["pilotLen"] / 2 - 2), py_, pz)
    b = (sign * (P["pilotLen"] / 2 + 10), py_, pz)
    c = (sign * (P["pilotLen"] / 2 + 10), R * 0.55, R * 0.55)
    d = (x_end, R * 0.55, R * 0.55)
    wp = cq.Workplane("XY").newObject([seg(a, b)]).union(seg(b, c)).union(seg(c, d))
    for corner in (b, c):
        wp = wp.union(cq.Solid.makeSphere(P["capD"] / 2, cq.Vector(*corner)))
    return wp
cap_left = capillary(-L / 2 - P["capT"] + 1)
cap_right = capillary(L / 2 + P["capT"] - 1)

# ---- Mounting bracket: L-shaped sheet metal with 2×M4 holes, welded under the body
bracket = cq.Workplane("XY").workplane(offset=-R - P["bracketH"]).rect(P["bracketW"] * 3, P["bracketT"]).extrude(P["bracketH"] + 2).translate((0, R * 0.0, 0))
foot = cq.Workplane("XY").workplane(offset=-R - P["bracketH"]).center(0, -P["bracketW"] / 2 + P["bracketT"] / 2).rect(P["bracketW"] * 3, P["bracketW"]).extrude(P["bracketT"])
bracket = bracket.union(foot)
bracket = bracket.faces("<Z").workplane().pushPoints([(-P["bracketW"], 0), (P["bracketW"], 0)]).hole(P["bracketHoleD"])
try:
    bracket = bracket.edges("|Z").fillet(1.0)
except Exception:  # noqa: BLE001
    pass

result = body.union(tube_d).union(tube_e).union(tube_s).union(tube_c).union(slide).union(piston_assy).union(pilot).union(pilot_seat).union(cap_left).union(cap_right).union(bracket)

PARTS = {"Main body (copper barrel + end caps)": body, "High-pressure inlet tube D": tube_d, "Tube E": tube_e, "Tube S": tube_s, "Tube C": tube_c,
         "Main slide spool": slide, "Piston assembly": piston_assy, "Pilot solenoid valve": pilot, "Pilot valve seat": pilot_seat, "Capillary (left)": cap_left, "Capillary (right)": cap_right, "Mounting bracket": bracket}
MATERIALS = {"Main body (copper barrel + end caps)": "copper", "High-pressure inlet tube D": "copper", "Tube E": "copper", "Tube S": "copper", "Tube C": "copper",
             "Main slide spool": "polymerLight", "Piston assembly": "steel", "Pilot solenoid valve": "powderCoat", "Pilot valve seat": "steelDark", "Capillary (left)": "copper", "Capillary (right)": "copper", "Mounting bracket": "powderCoat"}
DENSITIES = {"Main slide spool": 1.40, "Piston assembly": P["steelDensity"], "Pilot solenoid valve": P["steelDensity"], "Pilot valve seat": P["steelDensity"], "Mounting bracket": P["steelDensity"]}
NAME = "Four-way reversing valve"

shell_vol = math.pi * (R ** 2 - (R - t) ** 2) * L + 2 * math.pi * R ** 2 * P["capT"]
METRICS = [
    {"label": "Main body copper (wall 3.0)", "value": round(shell_vol * P["copperDensity"] / 1e6, 3), "unit": "kg", "note": "Barrel + both end caps"},
    {"label": "Wall reduced to 2.2 mm", "value": round((math.pi * (R ** 2 - (R - 2.2) ** 2) * L + 2 * math.pi * R ** 2 * P["capT"]) * P["copperDensity"] / 1e6, 3), "unit": "kg", "note": "Same OD, copper down " + f"{(1 - (R ** 2 - (R - 2.2) ** 2) / (R ** 2 - (R - t) ** 2)) * 100:.0f}%"},
    {"label": "Stainless steel 2.0 mm", "value": round((math.pi * (R ** 2 - (R - 2.0) ** 2) * L + 2 * math.pi * R ** 2 * P["capT"]) * P["steelDensity"] / 1e6, 3), "unit": "kg", "note": "Material cost CNY 20,000/t vs copper CNY 75,000/t"},
    {"label": "Tubes", "value": "4 × φ12.7", "unit": "mm", "note": "D on top / E·S·C below, 22 pitch"},
]
