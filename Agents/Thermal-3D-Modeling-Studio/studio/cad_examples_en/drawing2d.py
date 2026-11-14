import cadquery as cq
import math

# 2D drawing / photo → 3D — Track B reference script: rebuilds the sample drawing EXV-DEMO-01 of the scenario (electronic expansion valve body assembly) item by item.
# Drawing callouts: body Ø32×60 (H62 brass), coil seat Ø28×35 (PA66), side tube Ø9.52 projecting 40 with its axis 22 above the body bottom,
# bottom tube Ø9.52 projecting 35 (TP2 copper), bore Ø14 (dashed), orifice Ø1.6. Dimensions not on the drawing are marked as assumptions in P.
P = {
    "bodyD": 32.0, "bodyH": 60.0, "upperD": 28.0, "upperH": 35.0,
    "capD": 20.0, "capH": 6.0,            # Assumption: the cap has no dimension on the drawing; Ø20×6 taken from the drawing proportions (same as the Track A example)
    "pipeD": 9.52, "pipeWall": 0.8, "sideL": 40.0, "sideZ": 22.0, "bottomL": 35.0,
    "boreD": 14.0, "boreBottom": 4.0, "boreTop": 56.0, "orificeD": 1.6,
    "sideSocket": 6.0,                    # Assumption: the side tube is brazed 6 mm into a socket in the body
    "bottomSocket": 2.5,                  # Assumption: the bottom tube socket is 2.5 mm deep, with a 1.5 mm long orifice above it
    "clearance": 0.03, "bodyChamfer": 0.8, "seatChamfer": 1.0,
    "brassDensity": 8.5, "copperDensity": 8.96, "plasticDensity": 1.4,
}
R = P["bodyD"] / 2
pr = P["pipeD"] / 2
pin = pr - P["pipeWall"]
x_sock = R - P["sideSocket"]

# ---- Valve body (H62 brass): Ø32×60 revolved body, chamfered outer edges top and bottom; Ø14 bore (z 4–56); side socket + inlet hole into the bore; bottom socket + Ø1.6 orifice
body = cq.Workplane("XY").circle(R).extrude(P["bodyH"])
body = body.faces(">Z").edges().chamfer(P["bodyChamfer"]).faces("<Z").edges().chamfer(P["bodyChamfer"])
body = body.cut(cq.Solid.makeCylinder(P["boreD"] / 2, P["boreTop"] - P["boreBottom"], cq.Vector(0, 0, P["boreBottom"])))
body = body.cut(cq.Solid.makeCylinder(pr + P["clearance"], P["sideSocket"] + 2, cq.Vector(x_sock, 0, P["sideZ"]), cq.Vector(1, 0, 0)))
body = body.cut(cq.Solid.makeCylinder(pin, x_sock - P["boreD"] / 2 + 1.0, cq.Vector(P["boreD"] / 2 - 0.5, 0, P["sideZ"]), cq.Vector(1, 0, 0)))
body = body.cut(cq.Solid.makeCylinder(pr + P["clearance"], P["bottomSocket"] + 1, cq.Vector(0, 0, -1)))
body = body.cut(cq.Solid.makeCylinder(P["orificeD"] / 2, P["boreBottom"] - P["bottomSocket"] + 1, cq.Vector(0, 0, P["bottomSocket"] - 0.5)))

# ---- Coil seat (PA66) Ø28×35 + cap Ø20×6, chamfered top edge
seat = cq.Workplane("XY").workplane(offset=P["bodyH"]).circle(P["upperD"] / 2).extrude(P["upperH"])
seat = seat.faces(">Z").edges().chamfer(P["seatChamfer"])
seat = seat.union(cq.Workplane("XY").workplane(offset=P["bodyH"] + P["upperH"]).circle(P["capD"] / 2).extrude(P["capH"]))

# ---- Tubes (TP2 copper Ø9.52×0.8): the side tube projects 40 beyond the body from the socket bottom; the bottom tube projects 35 down from the socket bottom
side = cq.Workplane("YZ").workplane(offset=x_sock).center(0, P["sideZ"]).circle(pr).circle(pin).extrude(R + P["sideL"] - x_sock)
bottom = cq.Workplane("XY").workplane(offset=-P["bottomL"]).circle(pr).circle(pin).extrude(P["bottomL"] + P["bottomSocket"])

PARTS = {"Valve body (H62 brass)": body, "Coil seat and cap (PA66)": seat, "Side tube (TP2 copper)": side, "Bottom tube (TP2 copper)": bottom}
MATERIALS = {"Valve body (H62 brass)": "brass", "Coil seat and cap (PA66)": "polymer", "Side tube (TP2 copper)": "copper", "Bottom tube (TP2 copper)": "copper"}
DENSITIES = {"Valve body (H62 brass)": P["brassDensity"], "Coil seat and cap (PA66)": P["plasticDensity"],
             "Side tube (TP2 copper)": P["copperDensity"], "Bottom tube (TP2 copper)": P["copperDensity"]}
NAME = "Electronic expansion valve body assembly (drawing EXV-DEMO-01)"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())   # Volume-weighted so the total mass equals the sum of the part masses
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

METRICS = [
    {"label": "Dimensions read from the drawing", "value": 10, "unit": "items", "note": "Ø32 / Ø28 / Ø9.52 / Ø14 / Ø1.6 / 60 / 35 / 35 / 40 / 22"},
    {"label": "Overall assembly height", "value": P["bottomL"] + P["bodyH"] + P["upperH"] + P["capH"], "unit": "mm", "note": "Bottom tube end to cap top: 35 + 60 + 35 + 6"},
    {"label": "Valve cavity volume", "value": round(math.pi * (P["boreD"] / 2) ** 2 * (P["boreTop"] - P["boreBottom"]) / 1000, 2), "unit": "cm³", "note": "Ø14 × 52 bore"},
    {"label": "Orifice flow area", "value": round(math.pi * (P["orificeD"] / 2) ** 2, 2), "unit": "mm²", "note": "Ø1.6"},
    {"label": "Tube inner diameter", "value": round(2 * pin, 2), "unit": "mm", "note": "Ø9.52 × 0.8 copper tube"},
    {"label": "Wall under the side socket", "value": round(x_sock - P["boreD"] / 2, 2), "unit": "mm", "note": "Margin from the 6 mm socket (assumed) to the Ø14 bore"},
]
