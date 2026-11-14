import cadquery as cq
import math

# Notebook dual-fan thermal module — Track B reference script: cooling module assembly of a 14-inch thin-and-light notebook (system level), sizes and placement from the scenario example P:
# 0.6 mm copper vapour chamber 130×85 (semi-solid, 0.3 hollow) over CPU 40×30 and GPU 29×29; two φ6 sintered copper heat pipes flattened to 2.0 mm (section width keeps the perimeter);
# left and right fin stacks 60×10×9 each, 0.10 copper fins with 0.35 gaps (133 fins per stack, slotted where the heat pipes pass); two φ48×7 centrifugal fans (28 blades); 0.1 graphite sheet on the D-cover.
# Coordinates: the three.js example is y-up; T() in this script maps to CAD (x, -z, y), so the exported glTF shares the coordinate system of the example. The chassis is a GLB asset and not part of the solid.
P = {
    "vc": [130.0, 0.6, 85.0], "vcCenter": [0.0, 6.3, -42.5], "vcCavity": 0.3, "vcInset": 3.0, "vcCorner": 4.0,
    "cpu": [40.0, 1.8, 30.0], "gpu": [29.0, 1.8, 29.0], "cpuCenter": [-28.0, 5.0, -48.0], "gpuCenter": [30.0, 5.0, -48.0],
    "tim": 0.1, "bottom": 2.0,
    "finWidth": 60.0, "finDepth": 10.0, "finHeight": 9.0, "finThick": 0.1, "finGap": 0.35, "finZ": -95.0,
    "fanDiameter": 48.0, "fanHeight": 7.0, "fanX": 100.0, "fanZ": -65.0, "bladeCount": 28, "fanWall": 0.6, "fanPlate": 0.5,
    "inletD": 30.0, "outletW": 40.0,
    "hpDiameter": 6.0, "hpHeight": 2.0, "hpWall": 0.3, "hpY": 7.8,
    "hpPath": [[-42.0, -45.0], [-62.0, -58.0], [-66.0, -79.0], [-82.0, -91.0], [-120.0, -91.0]],
    "graphite": [280.0, 0.1, 180.0], "graphiteY": 2.0, "heightLimit": 9.0,
    "copperDensity": 8.96, "graphiteDensity": 2.1, "packageDensity": 2.0, "liquidMetalDensity": 6.44, "pasteDensity": 2.6,
    "aluminumDensity": 2.70, "polymerDensity": 1.40,
}


def T(x, y, z):
    return cq.Vector(x, -z, y)


def box3(size, center):   # Box in example coordinates (size = x, y, z)
    sx, sy, sz = size
    return cq.Solid.makeBox(sx, sz, sy, T(*center) - cq.Vector(sx / 2, sz / 2, sy / 2))


def wp(shape):
    return cq.Workplane("XY").newObject([shape])


cpu = wp(box3(P["cpu"], P["cpuCenter"]))
gpu = wp(box3(P["gpu"], P["gpuCenter"]))
top_y = P["cpuCenter"][1] + P["cpu"][1] / 2
tim_cpu = wp(box3([P["cpu"][0], P["tim"], P["cpu"][2]], [P["cpuCenter"][0], top_y + P["tim"] / 2, P["cpuCenter"][2]]))
tim_gpu = wp(box3([P["gpu"][0], P["tim"], P["gpu"][2]], [P["gpuCenter"][0], top_y + P["tim"] / 2, P["gpuCenter"][2]]))

# ---- Vapour chamber: rounded 0.6 shell, 0.3 hollow (0.15 top and bottom walls), 3 mm sealed rim
vx, vy, vz = P["vc"]
vcc = T(*P["vcCenter"])
vc = cq.Workplane("XY").workplane(offset=vcc.z - vy / 2).center(vcc.x, vcc.y).rect(vx, vz).extrude(vy).edges("|Z").fillet(P["vcCorner"])
cav = (cq.Workplane("XY").workplane(offset=vcc.z - P["vcCavity"] / 2).center(vcc.x, vcc.y)
       .rect(vx - 2 * P["vcInset"], vz - 2 * P["vcInset"]).extrude(P["vcCavity"]).edges("|Z").fillet(P["vcCorner"] - 1))
vc = vc.cut(cav)

# ---- Flattened heat pipes: planar spline through the example control points, offset in 2D into a strip and extruded 2.0; cavity offset inward 0.3, ends closed naturally
hp_w = (math.pi * P["hpDiameter"] - (math.pi - 2) * P["hpHeight"]) / 2
z_hp = P["hpY"] - P["hpHeight"] / 2
pipes, hp_len = [], 0.0
for s in (-1, 1):
    pts = [(-s * x, -z) for x, z in P["hpPath"]]     # hpPath is the left-hand path (x < 0); the right one is mirrored
    path = cq.Workplane("XY").workplane(offset=z_hp).spline(pts, includeCurrent=False)
    hp_len += path.val().Length()
    outer = cq.Workplane("XY").workplane(offset=z_hp).spline(pts, includeCurrent=False).offset2D(hp_w / 2).extrude(P["hpHeight"])
    inner = (cq.Workplane("XY").workplane(offset=z_hp + P["hpWall"]).spline(pts, includeCurrent=False)
             .offset2D(hp_w / 2 - P["hpWall"]).extrude(P["hpHeight"] - 2 * P["hpWall"]))
    pipes.append((outer, outer.cut(inner)))

# ---- Fin stacks: 133 copper fins of 0.10 per stack, 0.35 gaps; slotted where the heat pipes pass
fin_n = int(math.floor(P["finWidth"] / (P["finThick"] + P["finGap"])))
fins = []
for s, (outer, _) in zip((-1, 1), pipes):
    x0 = s * P["fanX"] - P["finWidth"] / 2 + P["finThick"] / 2
    solids = [box3([P["finThick"], P["finHeight"], P["finDepth"]], [x0 + i * (P["finThick"] + P["finGap"]), P["bottom"] + P["finHeight"] / 2, P["finZ"]])
              for i in range(fin_n)]
    fins.append(wp(cq.Compound.makeCompound(solids)).cut(outer))

# ---- Centrifugal fans: housing (side wall + top and bottom covers, one Ø30 intake each on top and bottom, outlet toward the fins) + impeller (back plate + hub + 28 blades)
R, fh = P["fanDiameter"] / 2, P["fanHeight"]
z0 = P["bottom"]
housings, rotors = [], []
for s in (-1, 1):
    fc = T(s * P["fanX"], 0, P["fanZ"])
    shell = cq.Workplane("XY").workplane(offset=z0).center(fc.x, fc.y).circle(R).circle(R - P["fanWall"]).extrude(fh)
    for zz in (z0, z0 + fh - P["fanPlate"]):
        shell = shell.union(cq.Workplane("XY").workplane(offset=zz).center(fc.x, fc.y).circle(R).circle(P["inletD"] / 2).extrude(P["fanPlate"]))
    shell = shell.cut(cq.Solid.makeBox(P["outletW"], R, fh - 2 * P["fanPlate"], cq.Vector(fc.x - P["outletW"] / 2, fc.y + R * 0.35, z0 + P["fanPlate"])))
    housings.append(shell)
    rotor = cq.Workplane("XY").workplane(offset=z0 + 1.5).center(fc.x, fc.y).circle(R - 3).extrude(0.4)
    rotor = rotor.union(cq.Workplane("XY").workplane(offset=z0 + 1.5).center(fc.x, fc.y).circle(7).extrude(4))
    for j in range(P["bladeCount"]):
        a = j / P["bladeCount"] * 2 * math.pi
        blade = (cq.Solid.makeBox(1.0, 13.0, 4.0, cq.Vector(-0.5, -6.5, 0)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), math.degrees(a + 0.4))
                 .translate(cq.Vector(fc.x + 15 * math.sin(a), fc.y - 15 * math.cos(a), z0 + 1.5)))
        rotor = rotor.union(blade)
    rotors.append(rotor)

# ---- Graphite sheet inside the D-cover (cut out at the fan intakes)
gx, gt, gz = P["graphite"]
graphite = cq.Workplane("XY").workplane(offset=P["graphiteY"]).rect(gx, gz).extrude(gt)
for s in (-1, 1):
    fc = T(s * P["fanX"], 0, P["fanZ"])
    graphite = graphite.cut(cq.Solid.makeCylinder(R, 1.0, cq.Vector(fc.x, fc.y, P["graphiteY"] - 0.5)))

PARTS = {"CPU package": cpu, "Discrete GPU package": gpu, "Liquid metal interface (CPU)": tim_cpu, "Thermal paste interface (GPU)": tim_gpu, "Copper vapour chamber": vc,
         "Left flattened heat pipe": pipes[0][1], "Right flattened heat pipe": pipes[1][1], f"Left copper fin stack ×{fin_n}": fins[0], f"Right copper fin stack ×{fin_n}": fins[1],
         "Left centrifugal fan housing": housings[0], "Left fan impeller (28 blades)": rotors[0], "Right centrifugal fan housing": housings[1], "Right fan impeller (28 blades)": rotors[1],
         "D-cover graphite sheet": graphite}
mats = ["pcb", "pcb", "steel", "polymerLight", "copper", "copper", "copper", "copper", "copper", "aluminumCast", "polymer",
        "aluminumCast", "polymer", "powderCoat"]
dens = [P["packageDensity"], P["packageDensity"], P["liquidMetalDensity"], P["pasteDensity"]] + [P["copperDensity"]] * 5 + \
       [P["aluminumDensity"], P["polymerDensity"], P["aluminumDensity"], P["polymerDensity"], P["graphiteDensity"]]
MATERIALS = dict(zip(PARTS, mats))
DENSITIES = dict(zip(PARTS, dens))
NAME = "Notebook dual-fan thermal module"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

METRICS = [
    {"label": "Fin count (both stacks)", "value": 2 * fin_n, "unit": "fins", "note": "Per stack 60 ÷ (0.10 + 0.35), rounded down"},
    {"label": "Flattened heat-pipe section width", "value": round(hp_w, 2), "unit": "mm", "note": "φ6 flattened to 2.0 mm, same perimeter"},
    {"label": "Heat-pipe centreline length", "value": round(hp_len, 1), "unit": "mm", "note": "Two pipes, splines through the example control points"},
    {"label": "Module stack height", "value": P["bottom"] + P["finHeight"] - P["graphiteY"], "unit": "mm", "note": f"D-cover inner face to the top of the fins / fans, limit {P['heightLimit']:g} mm"},
    {"label": "Vapour chamber / heat source area ratio", "value": round(vx * vz / (P["cpu"][0] * P["cpu"][2] + P["gpu"][0] * P["gpu"][2]), 2), "unit": "", "note": "130×85 vs CPU 40×30 + GPU 29×29"},
    {"label": "Fan blades", "value": f"{P['bladeCount']} × 2", "unit": "fins", "note": "φ48 × 7 centrifugal fans"},
]
