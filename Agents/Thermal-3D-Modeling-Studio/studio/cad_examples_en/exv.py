import cadquery as cq
import math

# Electronic expansion valve body — Track B reference script (sizes from the scenario: brass body φ32×60, φ9.52 copper tubes, φ28×35 coil assembly, φ1.6 orifice)
P = {
    "bodyOD": 32.0, "bodyH": 60.0, "boreD": 14.0, "boreDepth": 44.0,          # Valve body and main cavity
    "seatD": 1.6, "seatLen": 4.0,                                               # Orifice
    "tubeOD": 9.52, "tubeWall": 0.8, "inletLen": 40.0, "inletZ": 22.0, "outletLen": 35.0, "tubeInsert": 6.0,
    "coilD": 28.0, "coilH": 35.0, "coilWall": 1.6, "coilNeckD": 20.0, "coilNeckH": 4.0,   # Stepper-motor coil assembly (plastic housing)
    "needleD": 6.0, "needleLen": 46.0, "needleTipLen": 5.0,                    # Needle valve spool
    "flangeD": 36.0, "flangeT": 3.0, "boltD": 3.4, "boltPitchR": 15.0, "boltN": 4,  # Flange on top of the body + 4×M3 mounting holes
    "oringW": 1.8, "oringDepth": 1.2, "oringD": 24.0,                           # Top sealing groove
    "hexW": 27.0, "hexH": 8.0,                                                  # Hex wrench flats on the lower body
    "chamfer": 0.6, "fillet": 1.5,
    "brassDensity": 8.50, "copperDensity": 8.96, "steelDensity": 7.90, "polymerDensity": 1.40,
}
DENSITY = P["brassDensity"]
D, H, bore = P["bodyOD"], P["bodyH"], P["boreD"]

# ---- Valve body: cylinder + top flange + bottom hex; cavity, orifice, side inlet hole, top O-ring groove, 4 M3 holes
body = cq.Workplane("XY").circle(D / 2).extrude(H)
flange = cq.Workplane("XY").workplane(offset=H - P["flangeT"]).circle(P["flangeD"] / 2).extrude(P["flangeT"])
hexpart = cq.Workplane("XY").workplane(offset=10.0).polygon(6, P["hexW"] / math.cos(math.pi / 6)).extrude(P["hexH"])
body = body.union(flange).union(hexpart)
body = body.faces(">Z").workplane().hole(bore, P["boreDepth"])                               # Main cavity (from the top down)
seat = cq.Solid.makeCylinder(P["seatD"] / 2, P["seatLen"] + 0.2, cq.Vector(0, 0, H - P["boreDepth"] - P["seatLen"] - 0.1), cq.Vector(0, 0, 1))
body = body.cut(seat)                                                                      # Orifice connecting the cavity to the bottom outlet
outlet_bore = cq.Solid.makeCylinder(P["tubeOD"] / 2 - P["tubeWall"], H - P["boreDepth"] - P["seatLen"] + 0.1, cq.Vector(0, 0, -0.1), cq.Vector(0, 0, 1))
body = body.cut(outlet_bore)
# Side inlet: tube socket (φ tube OD) + hole into the cavity
inlet_socket = cq.Solid.makeCylinder(P["tubeOD"] / 2 + 0.05, P["tubeInsert"] + 0.1, cq.Vector(D / 2 - P["tubeInsert"], 0, P["inletZ"]), cq.Vector(1, 0, 0))
inlet_pass = cq.Solid.makeCylinder(P["tubeOD"] / 2 - P["tubeWall"], D / 2, cq.Vector(0, 0, P["inletZ"]), cq.Vector(1, 0, 0))
body = body.cut(inlet_socket).cut(inlet_pass)
# Bottom outlet tube socket
outlet_socket = cq.Solid.makeCylinder(P["tubeOD"] / 2 + 0.05, P["tubeInsert"] + 0.1, cq.Vector(0, 0, -0.1), cq.Vector(0, 0, 1))
body = body.cut(outlet_socket)
# Top O-ring groove + 4×M3 mounting holes (on the flange)
oring = (cq.Workplane("XY").workplane(offset=H - P["oringDepth"]).circle(P["oringD"] / 2 + P["oringW"] / 2).circle(P["oringD"] / 2 - P["oringW"] / 2).extrude(P["oringDepth"] + 0.1))
body = body.cut(oring)
body = body.faces(">Z").workplane().polarArray(P["boltPitchR"], 0, 360, P["boltN"]).hole(P["boltD"])
try:
    body = body.faces(">Z").edges("%CIRCLE").edges(cq.selectors.RadiusNthSelector(-1)).chamfer(P["chamfer"])   # Chamfer on the flange outer edge
except Exception:  # noqa: BLE001 — chamfer is cosmetic; the solid stays valid without it
    pass
try:
    body = body.faces("<Z").chamfer(P["chamfer"])
except Exception:  # noqa: BLE001
    pass

# ---- Copper tubes: real wall thickness, chamfered ends
inlet = cq.Workplane("YZ").workplane(offset=D / 2 - P["tubeInsert"]).center(0, P["inletZ"]).circle(P["tubeOD"] / 2).circle(P["tubeOD"] / 2 - P["tubeWall"]).extrude(P["inletLen"])
outlet = cq.Workplane("XY").workplane(offset=-P["outletLen"] + P["tubeInsert"]).circle(P["tubeOD"] / 2).circle(P["tubeOD"] / 2 - P["tubeWall"]).extrude(P["outletLen"])
try:
    inlet = inlet.faces(">X").chamfer(0.4)
    outlet = outlet.faces("<Z").chamfer(0.4)
except Exception:  # noqa: BLE001
    pass

# ---- Coil assembly housing: φ28×35 plastic shell, necked down to sit in the flange, rounded top, wiring boss on the side
coil = cq.Workplane("XY").workplane(offset=H).circle(P["coilD"] / 2).extrude(P["coilH"])
coil = coil.faces(">Z").edges().fillet(P["fillet"] * 2)
connector = cq.Workplane("XY").workplane(offset=H + 8).center(P["coilD"] / 2 + 3, 0).rect(10, 8).extrude(10)
coil = coil.union(connector)
coil_cavity = cq.Workplane("XY").workplane(offset=H + P["coilWall"]).circle(P["coilD"] / 2 - P["coilWall"]).extrude(P["coilH"] - 2 * P["coilWall"])
coil = coil.cut(coil_cavity)                                                               # Real wall thickness, coil cavity visible in a section
neck = cq.Workplane("XY").workplane(offset=H - P["coilNeckH"]).circle(P["coilNeckD"] / 2).circle(P["coilNeckD"] / 2 - 1.2).extrude(P["coilNeckH"])
coil = coil.union(neck)

# ---- Coil (copper): ring winding inside the housing
winding = (cq.Workplane("XY").workplane(offset=H + P["coilWall"] + 2).circle(P["coilD"] / 2 - P["coilWall"] - 0.5).circle(P["needleD"] / 2 + 2.5).extrude(P["coilH"] - 2 * P["coilWall"] - 6))

# ---- Needle valve spool (stainless steel): stem + conical tip, centred in the cavity
needle_rod = cq.Solid.makeCylinder(P["needleD"] / 2, P["needleLen"], cq.Vector(0, 0, H - P["boreDepth"] + P["needleTipLen"]), cq.Vector(0, 0, 1))
needle_tip = cq.Solid.makeCone(0.6, P["needleD"] / 2, P["needleTipLen"], cq.Vector(0, 0, H - P["boreDepth"]), cq.Vector(0, 0, 1))
needle = cq.Workplane("XY").newObject([needle_rod]).union(needle_tip)

result = body.union(inlet).union(outlet).union(coil).union(winding).union(needle)

PARTS = {"Brass valve body": body, "Inlet copper tube": inlet, "Outlet copper tube": outlet, "Coil assembly housing": coil, "Stator coil": winding, "Needle valve spool": needle}
MATERIALS = {"Brass valve body": "brass", "Inlet copper tube": "copper", "Outlet copper tube": "copper", "Coil assembly housing": "polymer", "Stator coil": "copperWire", "Needle valve spool": "steel"}
DENSITIES = {"Inlet copper tube": P["copperDensity"], "Outlet copper tube": P["copperDensity"], "Coil assembly housing": P["polymerDensity"], "Stator coil": P["copperDensity"], "Needle valve spool": P["steelDensity"]}
NAME = "Electronic expansion valve"

tube_len = P["inletLen"] + P["outletLen"]
METRICS = [
    {"label": "Overall valve height", "value": round(H + P["coilH"] + P["outletLen"] - P["tubeInsert"], 1), "unit": "mm", "note": "Outlet tube end to coil top"},
    {"label": "Total copper tube length", "value": round(tube_len, 1), "unit": "mm", "note": "Inlet + outlet"},
    {"label": "Orifice", "value": f"φ{P['seatD']}", "unit": "mm", "note": "Needle cone + orifice, visible in a section"},
    {"label": "Mounting holes", "value": f"{P['boltN']} × M3", "unit": "", "note": f"Flange φ{P['flangeD']}, hole φ{P['boltD']}"},
]
