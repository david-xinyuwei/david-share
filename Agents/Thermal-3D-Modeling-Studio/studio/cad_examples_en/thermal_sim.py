import cadquery as cq
import math

# AI-assisted simulation estimate — Track B reference script: the estimated battery cold plate solid + the coolant solid in the channels (split into 6 passes, part names carrying the inlet and outlet temperatures from the 1-D model).
# Geometry and operating point from the scenario example P: 320×180×12, 6 serpentine passes in series 10×6, heated wall 1.5, pass pitch 28, Ø12 inlet and outlet on the same short side;
# 50% glycol 8 L/min, 25 °C inlet, 2 kW spread over the top face. METRICS port calculate() from the example formula by formula (lumped / 1-D model, not CFD).
P = {
    "L": 320.0, "W": 180.0, "H": 12.0, "n": 6, "cw": 10.0, "ch": 6.0, "wall": 1.5, "pitch": 28.0, "endX": 130.0,
    "portD": 12.0, "portOuterD": 16.0, "portLength": 18.0,
    "corner": 6.0, "bossL": 24.0, "bossW": 26.0, "bossH": 20.0, "beadD": 17.5,   # Assumption: fillets and brazed fitting-block sizes
    "flow": 8.0, "Tin": 25.0, "heat": 2000.0,
    "rho": 1069.0, "cp": 3280.0, "mu": 0.0034, "k": 0.38, "Pr": 29.0,
    "alK": 200.0, "criticalRe": 2300.0, "laminarNu": 4.0, "dbC": 0.023, "dbRe": 0.8, "dbPr": 0.4,
    "laminarF": 64.0, "blasiusC": 0.316, "blasiusE": -0.25, "bendK": 1.5, "portK": 1.5,
    "alDensity": 2.70, "coolantDensity": 1.069,
}
n = int(P["n"])
L, W, H, cw, ch = P["L"], P["W"], P["H"], P["cw"], P["ch"]
r = P["pitch"] / 2
tx = P["endX"]
lead = L / 2 - tx

# ---- 1-D thermal-flow estimate (same formulas as calculate() on the example page)
path_mm = n * 2 * tx + (n - 1) * math.pi * r + 2 * lead
Q = P["flow"] / 60000
A = cw * ch * 1e-6
per = 2 * (cw + ch) / 1000
Dh = 4 * A / per
Lm = path_mm / 1000
rise = P["heat"] / (P["rho"] * Q * P["cp"])
v = Q / A
Re = P["rho"] * v * Dh / P["mu"]
Nu = P["laminarNu"] if Re < P["criticalRe"] else P["dbC"] * Re ** P["dbRe"] * P["Pr"] ** P["dbPr"]
h = Nu * P["k"] / Dh
flux = P["heat"] / (per * Lm)
wall_rise = flux / h + flux * (P["wall"] / 1000) / P["alK"]
fric = P["laminarF"] / Re if Re < P["criticalRe"] else P["blasiusC"] * Re ** P["blasiusE"]
dyn = P["rho"] * v * v / 2
v_port = Q / (math.pi * (P["portD"] / 1000) ** 2 / 4)
dp = (fric * Lm / Dh * dyn + (n - 1) * P["bendK"] * dyn + P["portK"] * P["rho"] * v_port ** 2 / 2) / 1000
T_out = P["Tin"] + rise
T_max = T_out + wall_rise

# ---- Channel geometry: 1.5 cover on top, channels milled 6 deep into the base top face; z = 0 is the cold plate bottom
base_t = H - P["wall"]
zc = base_t - ch / 2
ys = [(i - (n - 1) / 2) * P["pitch"] for i in range(n)]
half_turn = (cq.Workplane("XZ").polyline([(r - cw / 2, -ch / 2), (r + cw / 2, -ch / 2), (r + cw / 2, ch / 2), (r - cw / 2, ch / 2)]).close()
             .revolve(180, (0, 0), (0, 1)))
x_edge = -L / 2
port_x0 = x_edge - P["bossL"]
fluid, seg_len = [], []
for i, y in enumerate(ys):
    xmin = x_edge if i in (0, n - 1) else -tx
    f = cq.Workplane("XY").newObject([cq.Solid.makeBox(tx - xmin, cw, ch, cq.Vector(xmin, y - cw / 2, zc - ch / 2))])
    length = tx - xmin
    if i < n - 1:
        right = i % 2 == 0
        f = f.union(half_turn.rotate((0, 0, 0), (0, 0, 1), -90 if right else 90).translate((tx if right else -tx, (y + ys[i + 1]) / 2, zc)))
        length += math.pi * r
    if i in (0, n - 1):   # 10×6 transition slot in the fitting block + Ø12 hole + tube bore
        f = f.union(cq.Solid.makeBox(6.0, cw, ch, cq.Vector(x_edge - 6.0, y - cw / 2, zc - ch / 2)))
        f = f.union(cq.Solid.makeCylinder(P["portD"] / 2, P["bossL"] - 6.0 + P["portLength"], cq.Vector(port_x0 - P["portLength"], y, zc), cq.Vector(1, 0, 0)))
    fluid.append(f)
    seg_len.append(length)

# ---- Cold plate base (aluminium, milled channels) and cover (heated face)
base = cq.Workplane("XY").rect(L, W).extrude(base_t).edges("|Z").fillet(P["corner"])
for f in fluid:
    base = base.cut(f)
lid = cq.Workplane("XY").workplane(offset=base_t).rect(L, W).extrude(P["wall"]).edges("|Z").fillet(P["corner"])

# ---- Inlet and outlet fitting blocks (brazed to the short side) and Ø16/Ø12 tubes (with retaining beads)
bosses, tubes = [], []
for y in (ys[0], ys[-1]):
    b = cq.Workplane("XY").newObject([cq.Solid.makeBox(P["bossL"], P["bossW"], P["bossH"], cq.Vector(port_x0, y - P["bossW"] / 2, zc - P["bossH"] / 2))])
    try:
        b = b.edges("|X").fillet(3.0)
    except Exception:  # noqa: BLE001
        pass
    b = b.cut(cq.Solid.makeBox(6.2, cw, ch, cq.Vector(x_edge - 6.0, y - cw / 2, zc - ch / 2)))
    b = b.cut(cq.Solid.makeCylinder(P["portD"] / 2, P["bossL"] - 5.9, cq.Vector(port_x0 - 0.1, y, zc), cq.Vector(1, 0, 0)))
    bosses.append(b)
    t = cq.Workplane("XY").newObject([cq.Solid.makeCylinder(P["portOuterD"] / 2, P["portLength"], cq.Vector(port_x0 - P["portLength"], y, zc), cq.Vector(1, 0, 0))])
    t = t.union(cq.Solid.makeCylinder(P["beadD"] / 2, 2.5, cq.Vector(port_x0 - P["portLength"] + 4.0, y, zc), cq.Vector(1, 0, 0)))
    t = t.cut(cq.Solid.makeCylinder(P["portD"] / 2, P["portLength"] + 1, cq.Vector(port_x0 - P["portLength"] - 0.5, y, zc), cq.Vector(1, 0, 0)))
    tubes.append(t)

PARTS = {"Cold plate base (milled channels)": base, "Cover (1.5 mm heated face)": lid, "Inlet fitting block": bosses[0], "Outlet fitting block": bosses[1],
         "Inlet tube Ø16/Ø12": tubes[0], "Outlet tube Ø16/Ø12": tubes[1]}
MATERIALS = {k: "aluminum" for k in PARTS}
s0 = 0.0
for i, f in enumerate(fluid):
    t0, t1 = P["Tin"] + rise * s0 / path_mm, P["Tin"] + rise * (s0 + seg_len[i]) / path_mm
    name = f"Coolant · pass {i + 1} · {t0:.1f}→{t1:.1f} °C"
    PARTS[name] = f
    MATERIALS[name] = "coolant"
    s0 += seg_len[i]
DENSITIES = {k: (P["coolantDensity"] if MATERIALS[k] == "coolant" else P["alDensity"]) for k in PARTS}
NAME = "Battery cold plate thermal-flow estimate model"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())   # Volume-weighted so the total mass equals the sum of the part masses
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

note = "1-D model, same formulas as calculate() on the example page (default operating point)"
METRICS = [
    {"label": "Outlet temperature", "value": f"{T_out:.2f}", "unit": "°C", "note": note},
    {"label": "Maximum wall temperature", "value": f"{T_max:.2f}", "unit": "°C", "note": note},
    {"label": "Total pressure drop", "value": f"{dp:.2f}", "unit": "kPa", "note": note},
    {"label": "Reynolds number", "value": f"{Re:.0f}", "unit": "", "note": note},
    {"label": "Convective heat-transfer coefficient", "value": f"{h:.1f}", "unit": "W/(m²·K)", "note": note},
    {"label": "Total flow path length", "value": f"{Lm:.3f}", "unit": "m", "note": note},
]
