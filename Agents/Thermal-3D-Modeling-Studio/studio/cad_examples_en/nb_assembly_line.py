import cadquery as cq
import math

# Notebook final-assembly line digital twin — Track B reference script: equipment layout solids of a 60 m U-shaped assembly line (option ①, one shift, 800 units, system level 1:1), placed as in the scenario example:
# conveyor long sides 26 m each, cross side 8 m, belt height 900; 14 stations 2,050 mm outside the belt (spaced evenly along the line); robot stations ③⑦⑬,
# AOI ⑧, test ⑨ (6 testers for option ①, 3 more positions reserved for option ②), burn-in rack ⑩ (5 levels), the rest manual stations (anti-fatigue mat + light frame + parts bins).
# The line-side store centre moves from z = 7,200 in the example out to 9,800 (the example shows it translucent; the original position overlaps the work area of station ⑪); 3 AGVs park in front of it.
# Coordinates: the three.js example is y-up; T() in this script maps to CAD (x, -z, y), so the exported glTF shares the coordinate system of the example.
P = {
    "leg": 26000.0, "span": 8000.0, "beltWidth": 1100.0, "beltHeight": 900.0, "beltThick": 220.0, "stationOffset": 2050.0,
    "table": [1900.0, 850.0, 1700.0], "agv": [1200.0, 450.0, 850.0], "unit": [301.0, 14.5, 220.0],
    "rack": [2300.0, 2500.0, 1800.0], "rackLevels": 5, "rackSlots": 240, "testers": 6, "testerSlots": 9,
    "warehouse": [7200.0, 2400.0, 2200.0], "warehouseZ": 9800.0, "agvZ": 8100.0,
    "categories": ["Manual", "Manual", "Robot", "Manual", "Manual", "Manual", "Robot", "AOI", "Test", "Burn-in", "Manual", "Manual", "Robot", "Manual"],
    "names": ["① Bottom case loading", "② Mainboard and cooling assembly", "③ Automatic screwdriving", "④ Battery and speakers", "⑤ Display and hinges", "⑥ Keyboard and closing", "⑦ Automatic screwdriving",
              "⑧ Cosmetic AOI", "⑨ Test", "⑩ Burn-in", "⑪ Software and final inspection", "⑫ Labelling and packing", "⑬ Boxing and palletising", "⑭ Finished goods off the line"],
    # Most equipment is modelled as envelope solids: an equivalent density (g/cm³) keeps each part mass at a realistic order of magnitude instead of the true material density
    "frameDensity": 0.20, "beltDensity": 0.18, "legDensity": 0.60, "stationDensity": 0.45, "robotDensity": 1.20, "toolDensity": 2.00,
    "aoiDensity": 1.00, "testerDensity": 0.45, "slotDensity": 0.07, "matDensity": 1.20, "binDensity": 0.12, "unitDensity": 1.35,
    "shelfDensity": 0.40, "crateDensity": 0.15, "agvDensity": 0.85, "loadDensity": 0.26, "wheelDensity": 1.20,
}
EDGE_FINISH = 0   # 28 m layout: sub-millimetre automatic edge breaks are invisible and only add faces and glb size
LEG, SPAN, BH = P["leg"], P["span"], P["beltHeight"]
path_len = 2 * LEG + SPAN


def T(x, y, z):
    return cq.Vector(x, -z, y)


def box3(size, center):
    sx, sy, sz = size
    return cq.Solid.makeBox(sx, sz, sy, T(*center) - cq.Vector(sx / 2, sz / 2, sy / 2))


def place(solids, deg, pos):
    return [s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), deg).translate(pos) for s in solids]


def fuse(solids):
    return solids[0].fuse(*solids[1:]).clean() if len(solids) > 1 else solids[0]


def wp(shapes):
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(shapes) if isinstance(shapes, list) else shapes])


def path_at(d):   # Same as pathAt() in the example: returns the belt centre point and the travel direction angle
    if d < LEG:
        return (-LEG / 2 + d, -SPAN / 2), 0.0
    if d < LEG + SPAN:
        return (LEG / 2, -SPAN / 2 + d - LEG), -90.0
    return (LEG / 2 - (d - LEG - SPAN), SPAN / 2), 180.0


# ---- U-shaped conveyor: aluminium frame + belt + legs
bw, bt = P["beltWidth"], P["beltThick"]
frame = fuse([box3([LEG + bw / 2, bt - 20, bw], [bw / 4, BH - 20 - (bt - 20) / 2, z]) for z in (-SPAN / 2, SPAN / 2)]
             + [box3([bw, bt - 20, SPAN], [LEG / 2, BH - 20 - (bt - 20) / 2, 0])])
belt = fuse([box3([LEG + bw / 2 - 50, 20, bw - 50], [bw / 4 - 25, BH - 10, z]) for z in (-SPAN / 2, SPAN / 2)]
            + [box3([bw - 50, 20, SPAN - bw + 50], [LEG / 2, BH - 10, 0])])
legs = [box3([180, BH - bt, 700], [x, (BH - bt) / 2, z]) for z in (-SPAN / 2, SPAN / 2) for x in range(-12000, 12001, 4000)]
legs += [box3([700, BH - bt, 180], [LEG / 2, (BH - bt) / 2, z]) for z in (-2000.0, 2000.0)]

# ---- 14 stations: workbench (aluminium profile, with lower shelf) + equipment by type
tw, th, td = P["table"]
stations, robots, tools, testers, reserved, slots, aoi, mats, bins, units = [], [], [], [], [], [], [], [], [], []
for i in range(14):
    d = 1100 + i * (path_len - 2200) / 13
    (px, pz), heading = path_at(d)
    if d < LEG:
        pos, rot = T(px, 0, pz - P["stationOffset"]), 180.0
    elif d < LEG + SPAN:
        pos, rot = T(px + P["stationOffset"], 0, pz), 90.0
    else:
        pos, rot = T(px, 0, pz + P["stationOffset"]), 0.0
    cat = P["categories"][i]
    body = [box3([tw - 100, 50, td - 100], [0, th + 25, 0]), box3([tw - 200, 20, td - 200], [0, 250, 0])]
    body += [box3([60, th, 60], [sx * (tw / 2 - 110), th / 2, sz * (td / 2 - 110)]) for sx in (-1, 1) for sz in (-1, 1)]
    if cat == "Manual":   # Light frame + parts bins + anti-fatigue mat (the operator stands on the side away from the belt)
        body += [box3([40, 1250, 40], [sx * (tw / 2 - 110), th + 50 + 625, -(td / 2 - 110)]) for sx in (-1, 1)]
        body += [box3([tw - 180, 40, 40], [0, th + 50 + 1250, -(td / 2 - 110)]), box3([1200, 30, 150], [0, th + 50 + 1215, -(td / 2 - 200)])]
        bins += place([box3([320, 120, 220], [k * 400, th + 110, -(td / 2 - 250)]) for k in (-1, 0, 1)], rot, pos)
        mats += place([box3([1600, 15, 600], [0, 7.5, td / 2 + 350])], rot, pos)
    elif cat == "Robot":
        robots += place([fuse([cq.Solid.makeCylinder(230, 220, T(0, th + 50, 0)), box3([230, 850, 230], [0, th + 270 + 420, 0]),
                               box3([850, 210, 230], [350, th + 270 + 830, 0])])], rot, pos)
        tools += place([box3([130, 260, 150], [730, th + 270 + 660, 0])], rot, pos)
    elif cat == "Test":
        for j in range(P["testerSlots"]):
            s = box3([480, 400, 360], [(j % 3 - 1) * 560, th + 250, (j // 3) * 470 - 470])
            (testers if j < P["testers"] else reserved).extend(place([s], rot, pos))
    elif cat == "Burn-in":
        rw, rh, rd = P["rack"]
        body += [box3([rw, 120, rd], [0, th + 50 + 60, 0])]
        body += [box3([rw, 65, rd], [0, 1050 + k * 350, 0]) for k in range(P["rackLevels"])]
        body += [box3([80, 1800, rd - 100], [sx * (rw / 2 - 40), 1800, 0]) for sx in (-1, 1)]
        slots += place([box3([270, 120, 600], [(j - 2.5) * 350, 1150 + k * 350, 0]) for k in range(P["rackLevels"]) for j in range(6)], rot, pos)
    else:   # AOI: back cabinet + cantilever camera
        aoi += place([fuse([box3([1600, 1200, 180], [0, 1450, -600]), box3([120, 120, 600], [0, 1900, -300]),
                            box3([450, 220, 450], [0, 1900, 0])])], rot, pos)
    stations.append(place([fuse(body)], rot, pos)[0])
    # Work in progress on the belt (closed notebooks), long side along the travel direction
    units.append(box3(P["unit"], [0, BH + P["unit"][1] / 2, 0]).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), heading).translate(T(px, 0, pz)))

# ---- Line-side store (racks + totes) and 3 AGVs
ww, wh, wd = P["warehouse"]
wz = P["warehouseZ"]
shelf = [box3([80, wh, 80], [-ww / 2 + 40 + k * (ww - 80) / 6, wh / 2, wz + sz * (wd / 2 - 40)]) for k in range(7) for sz in (-1, 1)]
shelf += [box3([ww, 40, wd], [0, y, wz]) for y in (600.0, 1400.0, wh - 20)]
crates = [box3([650, 550, 850], [(k - 3.5) * 820, 620 + 275, wz]) for k in range(8)]
agv_body, agv_load, wheels = [], [], []
for k in range(3):
    c = (-2400 + k * 2400, P["agvZ"])
    agv_body.append(fuse([box3(P["agv"], [c[0], P["agv"][1] / 2 + 30, c[1]])]))
    agv_load.append(box3([850, 350, 650], [c[0], P["agv"][1] + 30 + 175, c[1]]))
    wheels += [cq.Solid.makeCylinder(100, 100, T(c[0] + sx * 460, 100, c[1] + sz * 350 - 50), cq.Vector(0, -1, 0)) for sx in (-1, 1) for sz in (-1, 1)]

PARTS, MATERIALS, DENSITIES = {}, {}, {}


def add(name, w, mat, dens):
    PARTS[name] = w
    MATERIALS[name] = mat
    DENSITIES[name] = dens


add("U-shaped conveyor frame", wp(frame), "aluminum", P["frameDensity"])
add("Conveyor belt (PVC)", wp(belt), "rubber", P["beltDensity"])
add(f"Conveyor legs ×{len(legs)}", wp(legs), "aluminum", P["legDensity"])
for i, s in enumerate(stations):
    add(f"{P['names'][i]} station", wp(s), "aluminum", P["stationDensity"])
add("Six-axis robots ×3 (③⑦⑬)", wp(robots), "polymerLight", P["robotDensity"])
add("Robot end effectors ×3", wp(tools), "anodizedRed", P["toolDensity"])
add("⑧ AOI vision inspection machine", wp(aoi), "powderCoat", P["aoiDensity"])
add(f"⑨ Test benches ×{len(testers)} (option ①)", wp(testers), "anodizedBlue", P["testerDensity"])
add(f"⑨ Reserved test positions ×{len(reserved)} (used in option ②)", wp(reserved), "glass", 0.0)
add(f"⑩ Notebooks in burn-in (schematic, {len(slots)} / {P['rackSlots']} positions)", wp(slots), "anodizedBlue", P["slotDensity"])
add(f"Anti-fatigue mats ×{len(mats)}", wp(mats), "rubber", P["matDensity"])
add(f"Station parts bins ×{len(bins)}", wp(bins), "anodizedBlue", P["binDensity"])
add(f"Work in progress (closed notebooks) ×{len(units)}", wp(units), "aluminum", P["unitDensity"])
add("Line-side store racks", wp(fuse(shelf)), "powderCoat", P["shelfDensity"])
add(f"Line-side store totes ×{len(crates)}", wp(crates), "cardboard", P["crateDensity"])
add("Delivery AGVs ×3", wp(agv_body), "anodizedOrange", P["agvDensity"])
add("AGV totes ×3", wp(agv_load), "cardboard", P["loadDensity"])
add(f"AGV wheels ×{len(wheels)}", wp(wheels), "rubber", P["wheelDensity"])

NAME = "Notebook U-shaped final-assembly line (option ①, 800 units per shift)"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])
bb = result.val().BoundingBox()

METRICS = [
    {"label": "Total line length", "value": round(path_len / 1000, 1), "unit": "m", "note": "U shape: 26 + 8 + 26 m"},
    {"label": "Stations", "value": 14, "unit": "pcs", "note": "2,050 mm outside the belt"},
    {"label": "Six-axis robots", "value": len(robots), "unit": "units", "note": "③ ⑦ automatic screwdriving, ⑬ boxing and palletising"},
    {"label": "Test benches (option ①)", "value": f"{len(testers)} + reserved {len(reserved)}", "unit": "units", "note": "Option ② raises it to 9"},
    {"label": "Burn-in positions (option ①)", "value": P["rackSlots"], "unit": "positions", "note": f"Modelled as a {P['rackLevels']}-level rack with {len(slots)} units shown schematically"},
    {"label": "Equipment layout envelope", "value": f"{bb.xlen / 1000:.1f} × {bb.ylen / 1000:.1f}", "unit": "m", "note": "Including station work areas and the line-side store"},
]
