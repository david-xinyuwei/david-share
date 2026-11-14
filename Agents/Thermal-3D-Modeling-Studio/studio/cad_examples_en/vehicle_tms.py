import cadquery as cq
import math

# Vehicle thermal management system loops — Track B reference script: components and the pipe runs of three loops of an 800 V battery-electric SUV thermal system (system level 1:1); component centres and loop control points
# from the scenario example P: battery pack 2100×170×1320 (bottom cold plate), front e-drive (motor + reducer + inverter + oil cooler), integrated thermal module (manifold + nine-way valve +
# two e-pumps), chiller, micro-channel condenser + low-temperature radiator + twin fans, electric compressor, two electronic expansion valves, HVAC (evaporator + heater core), PTC.
# Pipes are hollow spline sweeps through the example loop control points: EPDM hoses for coolant, aluminium tubes for refrigerant. The car body is the GLB asset of the example and not part of the engineering solid.
# Coordinates: in the three.js example x is vehicle length (+x forward), y height, z width; T() in this script maps to CAD (x, -z, y), so the exported glTF shares the coordinate system of the example.
P = {
    "battery": [-150.0, 235.0, 0.0], "batterySize": [2100.0, 170.0, 1320.0], "edrive": [1300.0, 420.0, 0.0], "motorR": 145.0, "motorL": 390.0,
    "itm": [780.0, 400.0, -260.0], "itmSize": [400.0, 220.0, 460.0], "pump1": [650.0, 445.0, -390.0], "pump2": [870.0, 445.0, -390.0],
    "pumpR": 60.0, "pumpL": 100.0, "valve9": [770.0, 490.0, -160.0], "valveR": 85.0, "valveH": 100.0, "chiller": [800.0, 430.0, 250.0],
    "condenser": [2100.0, 700.0, 0.0], "ltr": [1980.0, 700.0, 0.0], "fan": [1870.0, 700.0, 0.0], "frontSize": [65.0, 620.0, 1250.0],
    "compressor": [1550.0, 550.0, -380.0], "compR": 90.0, "compL": 240.0, "exv1": [1140.0, 650.0, 380.0], "exv2": [1100.0, 390.0, 330.0],
    "exvR": 30.0, "exvL": 90.0, "hvac": [950.0, 800.0, 0.0], "hvacSize": [350.0, 260.0, 600.0], "ptc": [700.0, 740.0, 370.0],
    "batteryLoop": [[650, 445, -390], [450, 290, -570], [-1050, 290, -570], [-1050, 290, 570], [450, 290, 570], [800, 430, 250], [770, 490, -160]],
    "edriveLoop": [[870, 445, -390], [1300, 420, -240], [1470, 540, 300], [1900, 450, 550], [1980, 900, 550], [1980, 900, -550], [1900, 440, -550], [770, 490, -160]],
    "refLoop": [[1550, 550, -380], [2100, 480, -520], [2100, 950, -520], [2100, 950, 520], [1140, 650, 380], [950, 800, 230], [950, 850, -230], [1550, 700, -380]],
    "refBranch": [[1140, 650, 380], [1100, 390, 330], [800, 430, 250], [1050, 500, -500], [1550, 550, -380]],
    "hoseBattery": 9.0, "hoseEdrive": 10.0, "hoseWall": 2.0, "refR": 6.0, "refWall": 1.0,
    "aluminumDensity": 2.70, "steelDensity": 7.90, "brassDensity": 8.50, "copperDensity": 8.96, "polymerDensity": 1.40,
    "rubberDensity": 1.20, "cellDensity": 2.20,
    # Assumption: the parts below are envelope models (internal passages / fins / gears not modelled), with an equivalent density from their solid fraction
    "fill": {"lid": 0.15, "coldplate": 0.35, "core": 0.12, "reducer": 0.6, "inverter": 0.4, "manifold": 0.2, "chiller": 0.15},
}
EDGE_FINISH = 0   # Vehicle-level assembly: sub-millimetre automatic edge breaks are invisible; fillets modelled explicitly on each part are kept


def T(x, y, z):
    return cq.Vector(x, -z, y)


def box3(size, center, r=0.0):
    sx, sy, sz = size
    b = cq.Solid.makeBox(sx, sz, sy, T(*center) - cq.Vector(sx / 2, sz / 2, sy / 2))
    if r:
        try:
            b = cq.Workplane("XY").newObject([b]).edges("|Z").fillet(r).val()
        except Exception:  # noqa: BLE001
            pass
    return b


AX = {"x": cq.Vector(1, 0, 0), "y": cq.Vector(0, 0, 1), "z": cq.Vector(0, -1, 0)}


def cyl(r, length, center, axis):
    d = AX[axis]
    return cq.Solid.makeCylinder(r, length, T(*center) - d * (length / 2), d)


def pipe(pts, r, t, closed=False):   # Sweep a hollow round pipe along a spline through the control points; fall back to straight runs + spherical elbows on failure
    v = [T(*p) for p in pts]
    try:
        path = cq.Workplane("XY").spline([p.toTuple() for p in v], includeCurrent=False, periodic=closed)
        e = path.val()
        n = e.tangentAt(0)
        x = n.cross(cq.Vector(0, 0, 1))
        x = x if x.Length > 1e-6 else cq.Vector(1, 0, 0)
        s = cq.Workplane(cq.Plane(e.startPoint(), x, n)).circle(r).circle(r - t).sweep(path, transition="round").val()
        if s.isValid() and s.Volume() > 0:
            return s, e.Length()
    except Exception:  # noqa: BLE001
        pass
    seq = v + ([v[0]] if closed else [])
    outer, inner, total = [], [], 0.0
    for a, b in zip(seq, seq[1:]):
        d = b - a
        total += d.Length
        outer.append(cq.Solid.makeCylinder(r, d.Length, a, d.normalized()))
        inner.append(cq.Solid.makeCylinder(r - t, d.Length, a, d.normalized()))
    for p in seq[1:-1] if not closed else seq:
        outer.append(cq.Workplane("XY").sphere(r).translate(p).val())
        inner.append(cq.Workplane("XY").sphere(r - t).translate(p).val())
    return outer[0].fuse(*outer[1:]).cut(inner[0].fuse(*inner[1:])).clean(), total


def fuse(solids):
    return solids[0].fuse(*solids[1:]).clean() if len(solids) > 1 else solids[0]


PARTS, MATERIALS, DENSITIES = {}, {}, {}


def add(name, shapes, mat, dens):
    PARTS[name] = cq.Workplane("XY").newObject([cq.Compound.makeCompound(shapes) if isinstance(shapes, list) else shapes])
    MATERIALS[name] = mat
    DENSITIES[name] = dens


# ---- Battery pack: cast aluminium tray (floor 8 / wall 8, 12 mounting lugs) + composite lid + cold plate + 12 modules
bc, (bx, by, bz) = P["battery"], P["batterySize"]
y0 = bc[1] - by / 2
tray = box3([bx, by - 20, bz], [bc[0], y0 + (by - 20) / 2, 0], 40).cut(box3([bx - 16, by, bz - 16], [bc[0], y0 + 8 + by / 2, 0], 32))
for sx in range(6):
    for sz in (-1, 1):
        lug_c = [bc[0] - bx / 2 + 175 + sx * (bx - 350) / 5, y0 + by - 40, sz * (bz / 2 + 40)]
        tray = tray.fuse(box3([90, 20, 80], lug_c)).cut(cyl(7, 30, lug_c, "y"))
add("Battery pack tray (cast aluminium)", tray.clean(), "aluminumCast", P["aluminumDensity"])
F = P["fill"]
add("Battery pack lid", box3([bx, 20, bz], [bc[0], y0 + by - 10, 0], 40), "polymer", P["polymerDensity"] * F["lid"])
add("Battery cold plate", box3([bx - 100, 8, bz - 80], [bc[0], y0 + 12, 0], 20), "aluminum", P["aluminumDensity"] * F["coldplate"])
add("Battery modules ×12", [box3([640, 110, 300], [bc[0] + (k - 1) * 680, y0 + 16 + 55, (m - 1.5) * 320], 8) for k in range(3) for m in range(4)],
    "anodized", P["cellDensity"])

# ---- Front e-drive: motor (end cover + output shaft) + reducer + inverter + oil cooler
ec = P["edrive"]
R, Lm = P["motorR"], P["motorL"]
add("E-drive motor", fuse([cyl(R, Lm, ec, "z"), cyl(R + 5, 20, [ec[0], ec[1], Lm / 2 + 10], "z"), cyl(R + 5, 20, [ec[0], ec[1], -Lm / 2 - 10], "z"),
                     cyl(25, 60, [ec[0], ec[1], Lm / 2 + 50], "z")]), "aluminumCast", P["aluminumDensity"])
add("Reducer", box3([320, 300, 180], [ec[0] + 40, ec[1] - 20, -Lm / 2 - 20 - 90], 30), "aluminumCast", P["aluminumDensity"] * F["reducer"])
add("E-drive inverter", box3([380, 90, 300], [ec[0], ec[1] + R + 45, 0], 20), "anodized", P["aluminumDensity"] * F["inverter"])
add("E-drive oil cooler", box3([120, 70, 90], [ec[0] - R - 60, ec[1] - 50, 120], 6), "steel", P["steelDensity"])

# ---- Integrated thermal module: manifold (engineering plastic, 4 mounting lugs) + nine-way e-valve + two e-pumps
ic, (ix, iy, iz) = P["itm"], P["itmSize"]
man_top = P["pump1"][1] - P["pumpL"] / 2
man_c = [ic[0], (ic[1] - iy / 2 + man_top) / 2, ic[2]]
man = box3([ix, man_top - (ic[1] - iy / 2), iz], man_c, 15)
for sx in (-1, 1):
    for sz in (-1, 1):
        c = [ic[0] + sx * (ix / 2 + 15), ic[1] - iy / 2 + 10, ic[2] + sz * (iz / 2 - 40)]
        man = man.fuse(box3([40, 20, 50], c)).cut(cyl(5, 30, c, "y"))
add("Integrated module manifold", man.clean(), "polymer", P["polymerDensity"] * F["manifold"])
vc = P["valve9"]
vbase = man_top
valve = [cyl(70, vc[1] - P["valveH"] / 2 - vbase, [vc[0], (vbase + vc[1] - P["valveH"] / 2) / 2, vc[2]], "y"), cyl(P["valveR"], P["valveH"], vc, "y"),
         box3([120, 50, 90], [vc[0], vc[1] + P["valveH"] / 2 + 25, vc[2]], 8)]
valve += [cyl(12, 30, [vc[0] + math.cos(a) * (P["valveR"] + 12), vc[1] - 20, vc[2] + math.sin(a) * (P["valveR"] + 12)],
              "x" if abs(math.cos(a)) > 0.5 else "z") for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
add("Nine-way e-valve", fuse(valve), "polymerLight", P["polymerDensity"])
for k, key in enumerate(("pump1", "pump2")):
    pc = P[key]
    add(f"E-pump {k + 1}", fuse([cyl(P["pumpR"], P["pumpL"], pc, "y"), cyl(P["pumpR"] - 10, 25, [pc[0], pc[1] + P["pumpL"] / 2 + 12, pc[2]], "y"),
                                  cyl(P["pumpR"] + 8, 6, [pc[0], pc[1] - P["pumpL"] / 2 + 3, pc[2]], "y"), cyl(14, 50, [pc[0] + P["pumpR"] + 20, pc[1] - 5, pc[2]], "x")]),
        "aluminumCast", P["aluminumDensity"])

# ---- Chiller (brazed plate heat exchanger): core + 16 raised plates + end plates + 4 ports
cc = P["chiller"]
ch = [box3([180, 100, 140], cc)] + [box3([188, 104, 3], [cc[0], cc[1], cc[2] - 70 + i * 140 / 15]) for i in range(16)]
ch += [box3([200, 112, 10], [cc[0], cc[1], cc[2] + sz * 75]) for sz in (-1, 1)]
ch += [cyl(10, 25, [cc[0] + sx * 60, cc[1] + 62, cc[2] + sz * 40], "y") for sx in (-1, 1) for sz in (-1, 1)]
add("Chiller plate heat exchanger", fuse(ch), "steel", P["steelDensity"] * F["chiller"])

# ---- Front-end module: micro-channel condenser (40 flat tubes + fin strip + headers), low-temperature radiator (core + plastic tanks), fan shroud + twin fans
fs = P["frontSize"]
for key, depth, width, name in (("condenser", 16.0, 1200.0, "Micro-channel condenser"), ("ltr", 30.0, 1150.0, "Low-temperature radiator core")):
    fc = P[key]
    core = [box3([depth, 2, width], [fc[0], fc[1] - 292.5 + k * 15, 0]) for k in range(40)]
    core += [box3([depth - 2, 13, width], [fc[0], fc[1] - 285 + k * 15, 0]) for k in range(39)]
    if key == "condenser":
        core += [cyl(16, 640, [fc[0], fc[1], sz * (width / 2 + 16)], "y") for sz in (-1, 1)]
    add(name, core, "aluminum", P["aluminumDensity"] * F["core"])
lc = P["ltr"]
add("Low-temperature radiator tanks ×2", [fuse([box3([50, 640, 40], [lc[0], lc[1], sz * (1150 / 2 + 20)], 6), cyl(16, 40, [lc[0], lc[1] + sz * 200, sz * (1150 / 2 + 60)], "z")])
                         for sz in (-1, 1)], "polymer", P["polymerDensity"])
fc = P["fan"]
shroud = box3([20, fs[1], fs[2]], [fc[0] + 20, fc[1], 0], 30)
for sz in (-1, 1):
    shroud = shroud.cut(cyl(280, 40, [fc[0] + 20, fc[1], sz * 300], "x")).fuse(cyl(292, 60, [fc[0] + 10, fc[1], sz * 300], "x").cut(cyl(282, 70, [fc[0] + 10, fc[1], sz * 300], "x")))
add("Fan shroud", shroud.clean(), "polymer", P["polymerDensity"])
fans = []
for sz in (-1, 1):
    hub = T(fc[0] - 10, fc[1], sz * 300)
    f = cq.Solid.makeCylinder(70, 50, hub - cq.Vector(25, 0, 0), cq.Vector(1, 0, 0))
    for j in range(7):
        blade = (cq.Solid.makeBox(6, 90, 210, cq.Vector(-3, -45, 60)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 25)
                 .rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), j * 360 / 7).translate(hub))
        f = f.fuse(blade)
    fans.append(f.clean())
add("Cooling fans ×2 (7 blades)", fans, "polymer", P["polymerDensity"])

# ---- Electric compressor: scroll housing + controller + 3 mounting feet + suction and discharge ports
pc = P["compressor"]
comp = cq.Workplane("XY").newObject([cyl(P["compR"], P["compL"], pc, "x")]).edges("%CIRCLE").fillet(15).val()
comp = fuse([comp, box3([150, 60, 120], [pc[0], pc[1] + P["compR"] + 25, pc[2]], 10)]
            + [box3([40, 60, 170], [pc[0] + dx, pc[1] - P["compR"] + 10, pc[2]]) for dx in (-90, 0, 90)]
            + [cyl(sr, 45, [pc[0] + dx, pc[1] + 10, pc[2] + P["compR"] + 15], "z") for dx, sr in ((-70, 14), (70, 10))])
add("Electric compressor", comp, "aluminumCast", P["aluminumDensity"])

# ---- Two electronic expansion valves: brass body + copper tubes + coil
bodies, coils = [], []
for key in ("exv1", "exv2"):
    xc = P[key]
    bodies.append(fuse([cyl(18, 40, [xc[0], xc[1] - 25, xc[2]], "y")] + [cyl(6.35, 40, [xc[0] + sx * 36, xc[1] - 30, xc[2]], "x") for sx in (-1, 1)]))
    coils.append(cyl(P["exvR"], 50, [xc[0], xc[1] + 20, xc[2]], "y"))
add("Electronic expansion valves ×2, bodies and tubes", bodies, "brass", P["brassDensity"])
add("Electronic expansion valves ×2, coils", coils, "polymer", P["polymerDensity"])

# ---- HVAC: plastic housing (wall 3, outlet on top) + evaporator core + heater core; PTC heater
hc, hs = P["hvac"], P["hvacSize"]
case = box3(hs, hc, 20).cut(box3([hs[0] - 6, hs[1] - 6, hs[2] - 6], hc, 17)).cut(box3([200, 20, 400], [hc[0], hc[1] + hs[1] / 2, 0]))
add("HVAC housing (outlet on top)", case, "polymer", P["polymerDensity"])
add("Evaporator core", box3([60, 220, 520], [hc[0] - 80, hc[1], 0], 4), "aluminum", P["aluminumDensity"] * F["core"])
add("Heater core", box3([40, 180, 420], [hc[0] + 90, hc[1] - 10, 0], 4), "aluminum", P["aluminumDensity"] * F["core"])
tc = P["ptc"]
add("PTC heater", fuse([box3([160, 50, 180], tc, 8)] + [box3([150, 20, 4], [tc[0], tc[1] + 35, tc[2] - 70 + k * 20]) for k in range(8)]
                      + [cyl(10, 30, [tc[0] + sx * 95, tc[1], tc[2]], "x") for sx in (-1, 1)]), "aluminumCast", P["aluminumDensity"])

# ---- Pipes of the three loops
lens = {}
for key, name, r, t, mat, dens, closed in (("batteryLoop", "Battery coolant hoses (EPDM)", P["hoseBattery"], P["hoseWall"], "rubber", P["rubberDensity"], True),
                                          ("edriveLoop", "E-drive coolant hoses (EPDM)", P["hoseEdrive"], P["hoseWall"], "rubber", P["rubberDensity"], True),
                                          ("refLoop", "Refrigerant main line (aluminium)", P["refR"], P["refWall"], "aluminum", P["aluminumDensity"], True),
                                          ("refBranch", "Refrigerant chiller branch (aluminium)", P["refR"], P["refWall"], "aluminum", P["aluminumDensity"], False)):
    s, lens[key] = pipe(P[key], r, t, closed)
    add(name, s, mat, dens)

NAME = "800 V battery-electric SUV thermal management system"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

coolant_l = sum(math.pi * ((rr - P["hoseWall"]) / 1000) ** 2 * lens[k] / 1000 for k, rr in (("batteryLoop", P["hoseBattery"]), ("edriveLoop", P["hoseEdrive"]))) * 1000
METRICS = [
    {"label": "Battery loop pipe length", "value": round(lens["batteryLoop"] / 1000, 2), "unit": "m", "note": "Splines through the example loop control points, Ø18 EPDM"},
    {"label": "E-drive loop pipe length", "value": round(lens["edriveLoop"] / 1000, 2), "unit": "m", "note": "Ø20 EPDM"},
    {"label": "Total refrigerant line length", "value": round((lens["refLoop"] + lens["refBranch"]) / 1000, 2), "unit": "m", "note": "Main line + chiller branch, Ø12 aluminium tube"},
    {"label": "Coolant hose internal volume", "value": round(coolant_l, 2), "unit": "L", "note": "Hose sections of both coolant loops, excluding component cavities"},
    {"label": "Front-end module frontal area", "value": round(fs[1] * fs[2] / 1e6, 3), "unit": "m²", "note": "620 × 1,250 mm"},
    {"label": "Numbered components", "value": 15, "unit": "pcs", "note": "One per hotspot in the example (battery pack to fans)"},
]
