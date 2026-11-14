import cadquery as cq
import math

# Packaging and container loading optimisation — Track B reference script: the four loading levels of option ① (standard pallets in the container): retail box → shipping carton → pallet → 40 ft high-cube container.
# Layouts ported formula by formula from planar() / compute(0) in the scenario example: carton = 5 retail boxes stacked along the 62 mm side + 10 mm clearance per side + 5 mm board; the pallet layer
# takes the better of two orientations, layers limited by 1,800 mm stack height and 1,000 kg per pallet; pallets are not stacked in the container. METRICS use the same formulas as the page.
# The container is a cut-away (no roof or near side wall, so the cargo shows); an opened carton stands outside the doors: 5 retail boxes, the top one open to show the notebook and the pulp cushions.
P = {
    "retail": [355.0, 245.0, 62.0], "perCarton": 5, "gap": 10.0, "board": 5.0, "boardDensity": 0.75, "gross": 2.4,
    "pallet": [1200.0, 1000.0, 150.0], "maxHeight": 1800.0, "maxLoad": 1000.0, "palletMass": 22.0,
    "container": [12032.0, 2352.0, 2698.0], "carbon": 1200.0, "pulp": 0.18, "retailMass": 0.26,
    "deck": 25.0, "runnerWidth": 90.0, "laptop": [301.0, 220.0, 14.5], "laptopMass": 1.3,
    "shell": 2.0, "corrPitch": 278.0, "corrDepth": 36.0, "floorT": 28.0, "wallZone": 43.0, "endZone": 80.0, "under": 150.0,
    "doorT": 50.0, "steelDensity": 7.85, "woodDensity": 0.55, "floorDensity": 0.70, "paperDensity": 0.70, "pulpDensity": 0.25,
    "tare": 3900.0,   # Assumption: typical tare weight of a 40 ft high-cube in kg; structural parts are simplified solids, with an equivalent density derived from the tare weight
}
r = P["retail"]
e = P["gap"] + P["board"]
c = [r[0] + 2 * e, r[1] + 2 * e, r[2] * P["perCarton"] + 2 * e]
CW, CD, CH = P["container"]


def planar(area, box):   # Of the two horizontal orientations take the one with more pieces (same as planar() on the page; a tie takes the first)
    opts = [(d, math.floor(area[0] / d[0]), math.floor(area[1] / d[1])) for d in ((box[0], box[1]), (box[1], box[0]))]
    return max(opts, key=lambda o: o[1] * o[2])


cardboard = 2 * (c[0] * c[1] + c[0] * c[2] + c[1] * c[2]) / 1e6 * P["boardDensity"]
layer = planar(P["pallet"], c)
case_mass = P["perCarton"] * P["gross"] + cardboard
layers = min(math.floor((P["maxHeight"] - P["pallet"][2]) / c[2]),
             math.floor((P["maxLoad"] - P["palletMass"]) / (layer[1] * layer[2] * case_mass)))
per_pallet = layer[1] * layer[2] * layers * P["perCarton"]
packing = planar(P["container"], P["pallet"])
total = packing[1] * packing[2] * per_pallet
util = total * r[0] * r[1] * r[2] / (CW * CD * CH) * 100
material = (cardboard / P["perCarton"] + P["pulp"] + P["retailMass"] + P["palletMass"] / per_pallet) * 1000


def B(x, y, z, dx, dy, dz):
    return cq.Solid.makeBox(dx, dy, dz, cq.Vector(x, y, z))


def comp(solids):
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(solids)])


# ---- Pallets and cartons: container coordinates x 0…12032 (door end +X), y ±1176, floor at z = 0
(pdx, pdy), pnx, pny = packing
(cdx, cdy), cnx, cny = layer
pallets, cartons = [], []
for i in range(pnx):
    for j in range(pny):
        px, py = (CW - pnx * pdx) / 2 + i * pdx, -pny * pdy / 2 + j * pdy
        deck, run = P["deck"], P["runnerWidth"]
        for k in range(7):     # 7 deck boards (perpendicular to the stringers)
            pallets.append(B(px + k * (pdx - 120) / 6, py, P["pallet"][2] - deck, 120, pdy, deck))
        for yy in (0, (pdy - run) / 2, pdy - run):   # 3 stringers
            pallets.append(B(px, py + yy, deck, pdx, run, P["pallet"][2] - 2 * deck))
        for xx in (0, (pdx - 140) / 2, pdx - 140):   # 3 bottom boards
            pallets.append(B(px + xx, py, 0, 140, pdy, deck))
        ox, oy = px + (pdx - cnx * cdx) / 2, py + (pdy - cny * cdy) / 2
        for L in range(layers):
            for a in range(cnx):
                for b in range(cny):     # Each carton is inset 1 mm all round so the seams show
                    cartons.append(B(ox + a * cdx + 1, oy + b * cdy + 1, P["pallet"][2] + L * c[2] + 1, cdx - 2, cdy - 2, c[2] - 2))

# ---- 40 ft high-cube (cut-away): corrugated far side wall, front wall, corner posts, top and bottom side rails, floor cross members, door frame; wooden floor; both doors open 90°
t, zd, wz, ez, un = P["shell"], P["corrDepth"], P["wallZone"], P["endZone"], P["under"]
top = CH + 48


def zigzag(n_len, base, sign):
    pts, k, p = [], 0, P["corrPitch"]
    while k * p < n_len:
        for u, s in ((0, 0), (102, 0), (137, 1), (243, 1)):
            if k * p + u < n_len:
                pts.append((k * p + u, base + sign * s * zd))
        k += 1
    pts.append((n_len, base))
    return pts


def corrugated(n_len, base, sign):
    outer = zigzag(n_len, base, sign)
    inner = [(x, y + sign * t) for x, y in outer]
    return cq.Workplane("XY").polyline(outer + inner[::-1]).close()


far = corrugated(CW, CD / 2, 1).extrude(top - 110).val().translate(cq.Vector(0, 0, 10))
front = corrugated(CD, 0, 1).extrude(top - 100).val().rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 90).translate(cq.Vector(0, -CD / 2, 0))
frame = [far, front]
for x0 in (-ez, CW):
    for y0 in (-CD / 2 - wz, CD / 2):
        frame.append(B(x0, y0, -un, ez, wz, top + un))                    # Corner posts
for y0 in (-CD / 2 - wz, CD / 2):
    frame.append(B(0, y0, -un, CW, wz, 160))                               # Bottom side rails
frame.append(B(0, CD / 2, top - 100, CW, wz, 100))                         # Far top side rail
frame.append(B(-ez, -CD / 2, top - 100, ez, CD, 100))                      # Front top rail
frame.append(B(-ez, -CD / 2, -un, ez, CD, un))                             # Front bottom rail
frame.append(B(CW, -CD / 2, top - 150, ez, CD, 150))                       # Door header
frame.append(B(CW, -CD / 2, -un, ez, CD, un))                              # Door sill
for k in range(24):                                                        # Floor cross members
    frame.append(B(k * (CW - 60) / 23, -CD / 2, -un + 10, 60, CD, un - P["floorT"] - 10))
floor = comp([B(0, -CD / 2, -P["floorT"], CW, CD, P["floorT"])])
doors, bars = [], []
for sy in (-1, 1):   # Door leaves swing 90° about the outer hinges to stand outside along +X; locking bars on the outer face
    y_in = sy * (CD / 2 + wz)
    doors.append(B(CW + ez, y_in if sy < 0 else y_in - P["doorT"], 0, CD / 2 + wz, P["doorT"], top - 160))
    for f in (0.35, 0.75):
        bars.append(cq.Solid.makeCylinder(14, top - 200, cq.Vector(CW + ez + f * (CD / 2 + wz), y_in + sy * 16, 20)))

# ---- Single carton cut-away outside the doors: opened carton (no top, no front panel) + 5 retail boxes, the top one open with the notebook and the pulp cushions
gx, gy, gz = CW + ez + CD / 2 + wz + 900, 0.0, -un
bd = P["board"]
open_carton = [B(gx, gy - c[1] / 2, gz, c[0], c[1], bd), B(gx + bd, gy + c[1] / 2 - bd, gz + bd, c[0] - 2 * bd, bd, c[2] - bd),
               B(gx, gy - c[1] / 2, gz + bd, bd, c[1], c[2] - bd), B(gx + c[0] - bd, gy - c[1] / 2, gz + bd, bd, c[1], c[2] - bd)]
bx, by = gx + e, gy - r[1] / 2
closed = [B(bx, by, gz + e + k * r[2], r[0], r[1], r[2]) for k in range(P["perCarton"] - 1)]
z5 = gz + e + (P["perCarton"] - 1) * r[2]
tray = cq.Workplane("XY").newObject([B(bx, by, z5, r[0], r[1], r[2] - 8)]).faces(">Z").shell(-1.5)
lid = (cq.Workplane("XY").newObject([B(0, -r[1], 0, r[0], r[1], 8)]).faces("<Z").shell(-1.5)   # Hinged at the rear top edge, lid open 105°
       .rotate((0, 0, 0), (1, 0, 0), -105).translate((bx, by + r[1], z5 + r[2] - 8)))
lap = P["laptop"]
pad = 1.5
cush = [B(bx + pad, by + pad, z5 + pad, r[0] - 2 * pad, r[1] - 2 * pad, 10)]
side_w = (r[0] - 2 * pad - lap[0]) / 2
cush += [B(bx + pad, by + pad, z5 + pad + 10, side_w, r[1] - 2 * pad, 30), B(bx + r[0] - pad - side_w, by + pad, z5 + pad + 10, side_w, r[1] - 2 * pad, 30)]
laptop = cq.Workplane("XY").newObject([B(bx + pad + side_w, gy - lap[1] / 2, z5 + pad + 10, lap[0], lap[1], lap[2])]).edges("|Z").fillet(8.0)

PARTS = {"Container structure (40 ft high-cube, cut-away)": comp(frame), "Container doors ×2 (open 90°)": comp(doors), "Door locking bars ×4": comp(bars), "Wooden floor": floor,
         f"Wooden pallets ×{pnx * pny}": comp(pallets), f"Corrugated cartons ×{len(cartons)} ({P['perCarton']} units each, with contents)": comp(cartons),
         "Opened carton (single-carton cut-away)": comp(open_carton), f"Retail boxes ×{len(closed)} (sealed, with notebook)": comp(closed), "Retail box (open)": tray.union(lid),
         "Moulded pulp cushions": comp(cush), "Notebook (closed)": laptop}
MATERIALS = dict(zip(PARTS, ["powderCoat", "powderCoat", "steel", "wood", "wood", "cardboard", "cardboard", "polymerLight",
                             "polymerLight", "cardboard", "aluminum"]))
vols = {k: w.val().Volume() for k, w in PARTS.items()}
names = list(PARTS)
steel_eq = (P["tare"] - vols[names[3]] * P["floorDensity"] / 1e6) * 1e6 / (vols[names[0]] + vols[names[1]] + vols[names[2]])
DENSITIES = dict(zip(names, [steel_eq, steel_eq, steel_eq, P["floorDensity"], P["palletMass"] * pnx * pny * 1e6 / vols[names[4]],
                             case_mass * len(cartons) * 1e6 / vols[names[5]],          # Cartons and retail boxes use their packed mass
                             P["boardDensity"] / P["board"], P["gross"] * len(closed) * 1e6 / vols[names[7]],
                             P["paperDensity"], P["pulpDensity"], P["laptopMass"] * 1e6 / vols[names[10]]]))
NAME = "Notebook packaging and 40 ft high-cube loading (option ①, standard pallets)"
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

METRICS = [
    {"label": "Units per carton", "value": str(P["perCarton"]), "unit": "units", "note": "Assumes retail boxes stacked on their shortest side"},
    {"label": "Units per pallet", "value": str(per_pallet), "unit": "units", "note": "Assumes full regular layers; the weight limit includes the pallet"},
    {"label": "Units per container", "value": str(total), "unit": "units", "note": "Assumes pallets are not stacked, lashing space not deducted"},
    {"label": "Container volume utilisation (%)", "value": f"{util:.2f}", "unit": "%", "note": "Based on the total envelope volume of the retail boxes"},
    {"label": "Packaging mass per unit (g)", "value": f"{material:.1f}", "unit": "g", "note": "Assumes board at 0.75 kg/m², overlaps and accessories not counted"},
    {"label": "Sea freight emissions per unit (kg CO₂e)", "value": f"{P['carbon'] / total:.3f}", "unit": "kg CO₂e", "note": "Assumes 1,200 kg CO₂e per container for the whole trip, shared equally"},
]
