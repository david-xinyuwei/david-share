import cadquery as cq
import math

# 热管理集成模块 —— 轨 B 参考脚本（场景需求：歧管 260×160×60 内两条 φ16 水路；五通电子水阀 φ60×70 铝壳；电子水泵 φ70×90 铝壳带出水口；
# 板式换热器 120×80×60 不锈钢 20 层；两个 φ16 快插接头）
P = {
    "manL": 260.0, "manW": 160.0, "manH": 60.0, "manR": 6.0, "wall": 4.0, "channelD": 16.0, "channelY": [-40.0, 40.0],
    "valveD": 60.0, "valveH": 70.0, "valveX": -70.0, "valveY": -20.0, "valveWall": 2.5, "valveFlangeD": 72.0, "valveFlangeT": 4.0, "valveBoltN": 4, "valveBoltD": 5.5,
    "pumpD": 70.0, "pumpH": 90.0, "pumpX": 60.0, "pumpY": 30.0, "pumpOutletD": 18.0, "pumpOutletLen": 35.0, "pumpWall": 3.0,
    "chillerL": 120.0, "chillerW": 80.0, "chillerH": 60.0, "chillerX": 60.0, "chillerY": -45.0, "plateN": 20, "plateT": 0.6,
    "quickD": 16.0, "quickWall": 1.2, "quickLen": 34.0, "quickBeadD": 20.0,
    "lugW": 18.0, "lugL": 16.0, "holeD": 8.4, "cboreD": 14.0, "cboreDepth": 6.0,     # 4×M8 沉孔安装耳
    "chamfer": 0.8, "polymerDensity": 1.40, "aluminumDensity": 2.70, "steelDensity": 7.90,
}
DENSITY = P["polymerDensity"]
L, W, H = P["manL"], P["manW"], P["manH"]

# ---- 歧管本体（工程塑料）：圆角长方体，内部两条 φ16 主水路（贯通），顶部多处安装座，四角 M8 沉孔耳，侧面加强筋
man = cq.Workplane("XY").box(L, W, H).translate((0, 0, H / 2)).edges("|Z").fillet(P["manR"])
try:
    man = man.faces(">Z").edges("not %CIRCLE").chamfer(P["chamfer"])
except Exception:  # noqa: BLE001
    pass
lug_pts = [(sx * (L / 2 + P["lugL"] / 2 - 3), sy * (W / 2 - P["lugW"] / 2 - 10)) for sx in (-1, 1) for sy in (-1, 1)]
lugs = cq.Workplane("XY").pushPoints(lug_pts).rect(P["lugL"] + 6, P["lugW"]).extrude(14).edges("|Z").fillet(4.0)
man = man.union(lugs)
hole_pts = [(sx * (L / 2 + P["lugL"] / 2), sy * (W / 2 - P["lugW"] / 2 - 10)) for sx in (-1, 1) for sy in (-1, 1)]
man = man.faces(">Z[-2]").workplane(centerOption="ProjectedOrigin").pushPoints(hole_pts).cboreHole(P["holeD"], P["cboreD"], P["cboreDepth"])
for y in P["channelY"]:   # 两条贯通主水路
    man = man.cut(cq.Solid.makeCylinder(P["channelD"] / 2, L + 2, cq.Vector(-L / 2 - 1, y, H / 2), cq.Vector(1, 0, 0)))
# 竖向支路：水路 → 顶面安装座（阀、泵、chiller 各一）
for x, y in ((P["valveX"], P["valveY"]), (P["pumpX"], P["pumpY"]), (P["chillerX"], P["chillerY"])):
    yc = min(P["channelY"], key=lambda c: abs(c - y))
    man = man.cut(cq.Solid.makeCylinder(6.0, H / 2 + 1, cq.Vector(x, yc, H / 2), cq.Vector(0, 0, 1)))
# 侧面加强筋（减重 + 刚度），两长边各 5 条
ribs = cq.Workplane("XZ").workplane(offset=-W / 2 - 0.0).pushPoints([(x, H / 2) for x in (-100, -50, 0, 50, 100)]).rect(6, H - 12).extrude(-3)
ribs2 = cq.Workplane("XZ").workplane(offset=W / 2).pushPoints([(x, H / 2) for x in (-100, -50, 0, 50, 100)]).rect(6, H - 12).extrude(3)
man = man.union(ribs).union(ribs2)
man = man.faces(">Z").workplane(centerOption="ProjectedOrigin").center(-20, 60).rect(50, 16).cutBlind(-0.3)   # 铭牌凹区

# ---- 五通电子水阀（铝壳）：圆柱壳 + 底部法兰 + 4×M5 孔 + 顶部电机座 + 侧面 4 个接口凸台
vx, vy = P["valveX"], P["valveY"]
valve = cq.Workplane("XY").workplane(offset=H).center(vx, vy).circle(P["valveD"] / 2).extrude(P["valveH"])
vflange = cq.Workplane("XY").workplane(offset=H).center(vx, vy).circle(P["valveFlangeD"] / 2).extrude(P["valveFlangeT"])
vmotor = cq.Workplane("XY").workplane(offset=H + P["valveH"]).center(vx, vy).rect(44, 36).extrude(22).edges("|Z").fillet(6)
valve = valve.union(vflange).union(vmotor)
for k in range(4):   # 侧向接口凸台（五通：4 侧 + 1 底）
    ang = math.radians(90 * k + 45)
    valve = valve.union(cq.Solid.makeCylinder(10.0, 14.0, cq.Vector(vx + math.cos(ang) * P["valveD"] / 2, vy + math.sin(ang) * P["valveD"] / 2, H + 32), cq.Vector(math.cos(ang), math.sin(ang), 0)))
    valve = valve.cut(cq.Solid.makeCylinder(6.5, 20.0, cq.Vector(vx + math.cos(ang) * (P["valveD"] / 2 - 5), vy + math.sin(ang) * (P["valveD"] / 2 - 5), H + 32), cq.Vector(math.cos(ang), math.sin(ang), 0)))
valve = valve.cut(cq.Solid.makeCylinder(P["valveD"] / 2 - P["valveWall"], P["valveH"] - 2 * P["valveWall"], cq.Vector(vx, vy, H + P["valveWall"]), cq.Vector(0, 0, 1)))  # 真实壁厚内腔
valve = valve.faces("<Z").workplane(centerOption="ProjectedOrigin").center(vx, -vy).polarArray(P["valveFlangeD"] / 2 - 4, 0, 360, P["valveBoltN"]).hole(P["valveBoltD"], P["valveFlangeT"] + 1)
try:
    valve = valve.faces(">Z").edges("not %CIRCLE").chamfer(1.0)
except Exception:  # noqa: BLE001
    pass

# ---- 电子水泵（铝壳带出水口）：泵壳 φ70×90 + 顶部电机段差 + 侧向出水口 + 底部法兰
px, py = P["pumpX"], P["pumpY"]
pump = cq.Workplane("XY").workplane(offset=H).center(px, py).circle(P["pumpD"] / 2).extrude(P["pumpH"] * 0.55)
pump_motor = cq.Workplane("XY").workplane(offset=H + P["pumpH"] * 0.55).center(px, py).circle(P["pumpD"] / 2 - 6).extrude(P["pumpH"] * 0.45)
pump_flange = cq.Workplane("XY").workplane(offset=H).center(px, py).circle(P["pumpD"] / 2 + 6).extrude(4)
pump = pump.union(pump_motor).union(pump_flange)
outlet = cq.Solid.makeCylinder(P["pumpOutletD"] / 2 + P["pumpWall"], P["pumpOutletLen"], cq.Vector(px + P["pumpD"] / 2 - 4, py, H + 22), cq.Vector(1, 0, 0))
pump = pump.union(outlet)
pump = pump.cut(cq.Solid.makeCylinder(P["pumpOutletD"] / 2, P["pumpOutletLen"] + 2, cq.Vector(px + P["pumpD"] / 2 - 5, py, H + 22), cq.Vector(1, 0, 0)))
pump = pump.cut(cq.Solid.makeCylinder(P["pumpD"] / 2 - P["pumpWall"], P["pumpH"] * 0.55 - 2 * P["pumpWall"], cq.Vector(px, py, H + P["pumpWall"]), cq.Vector(0, 0, 1)))  # 泵腔
pump = pump.faces("<Z").workplane(centerOption="ProjectedOrigin").center(px, -py).polarArray(P["pumpD"] / 2 + 2, 45, 360, 4).hole(5.5, 5)
try:
    pump = pump.faces(">Z").edges().fillet(3.0)
except Exception:  # noqa: BLE001
    pass
# 泵顶散热筋
pump = pump.union(cq.Workplane("XY").workplane(offset=H + P["pumpH"] - 18).center(px, py).polarArray(P["pumpD"] / 2 - 6, 0, 360, 12).rect(3, 8).extrude(18))

# ---- 板式换热器 Chiller（不锈钢）：120×80×60，20 层板片在壳内（简化为 20 块薄板 compound），4 个接口，顶部铭牌
cx, cy = P["chillerX"], P["chillerY"]
chiller = cq.Workplane("XY").workplane(offset=H).center(cx, cy).rect(P["chillerL"], P["chillerW"]).extrude(P["chillerH"]).edges("|Z").fillet(4.0)
chiller = chiller.cut(cq.Workplane("XY").workplane(offset=H + 3).center(cx, cy).rect(P["chillerL"] - 6, P["chillerW"] - 6).extrude(P["chillerH"] - 6))
for dx, dy in ((-45, -30), (45, -30), (-45, 30), (45, 30)):    # 4 个接口短管
    chiller = chiller.union(cq.Solid.makeCylinder(9.0, 12.0, cq.Vector(cx + dx, cy + dy, H + P["chillerH"] - 0.5), cq.Vector(0, 0, 1)))
    chiller = chiller.cut(cq.Solid.makeCylinder(6.0, 16.0, cq.Vector(cx + dx, cy + dy, H + P["chillerH"] - 4), cq.Vector(0, 0, 1)))
try:
    chiller = chiller.faces(">Z").edges("not %CIRCLE").chamfer(P["chamfer"])
except Exception:  # noqa: BLE001
    pass
plate_pitch = (P["chillerH"] - 10) / P["plateN"]
plates = cq.Workplane("XY").newObject([cq.Compound.makeCompound([
    cq.Solid.makeBox(P["chillerL"] - 14, P["chillerW"] - 14, P["plateT"], cq.Vector(cx - (P["chillerL"] - 14) / 2, cy - (P["chillerW"] - 14) / 2, H + 5 + i * plate_pitch)) for i in range(P["plateN"])])])

# ---- 两个 φ16 快插接头（铝）：插入歧管两端主水路
quicks = []
for sx, y in ((-1, P["channelY"][0]), (1, P["channelY"][1])):
    x0 = sx * (L / 2 - 3)
    direction = cq.Vector(sx, 0, 0)
    body = cq.Solid.makeCylinder(P["quickD"] / 2 + P["quickWall"], P["quickLen"], cq.Vector(x0, y, H / 2), direction)
    bead = cq.Solid.makeCylinder(P["quickBeadD"] / 2, 3.0, cq.Vector(x0 + sx * 8, y, H / 2), direction)
    q = cq.Workplane("XY").newObject([body]).union(bead)
    q = q.cut(cq.Solid.makeCylinder(P["quickD"] / 2, P["quickLen"] + 2, cq.Vector(x0 - sx, y, H / 2), direction))
    try:
        q = q.faces(">X" if sx > 0 else "<X").chamfer(0.6)
    except Exception:  # noqa: BLE001
        pass
    quicks.append(q)
quick_a, quick_b = quicks

result = man.union(valve).union(pump).union(chiller).union(plates).union(quick_a).union(quick_b)

PARTS = {"歧管本体": man, "五通电子水阀": valve, "电子水泵": pump, "板式换热器壳体": chiller, "换热板片 × 20": plates, "快插接头 A": quick_a, "快插接头 B": quick_b}
MATERIALS = {"歧管本体": "polymer", "五通电子水阀": "aluminumCast", "电子水泵": "aluminumCast", "板式换热器壳体": "steel", "换热板片 × 20": "steel", "快插接头 A": "aluminum", "快插接头 B": "aluminum"}
DENSITIES = {"五通电子水阀": P["aluminumDensity"], "电子水泵": P["aluminumDensity"], "板式换热器壳体": P["steelDensity"], "换热板片 × 20": P["steelDensity"], "快插接头 A": P["aluminumDensity"], "快插接头 B": P["aluminumDensity"]}
NAME = "热管理集成模块"

METRICS = [
    {"label": "部件数量", "value": 7, "unit": "", "note": "歧管 / 阀 / 泵 / 板换壳 / 板片组 / 2 接头"},
    {"label": "主水路", "value": f"2 × φ{P['channelD']:g} × {L:g}", "unit": "mm", "note": "贯通歧管，3 条竖向支路到阀 / 泵 / 板换"},
    {"label": "安装孔", "value": "4 × M8 沉孔", "unit": "", "note": f"φ{P['holeD']} / φ{P['cboreD']}×{P['cboreDepth']}"},
    {"label": "板片", "value": f"{P['plateN']} × {P['plateT']}", "unit": "mm", "note": "不锈钢板片，层距 " + f"{plate_pitch:.1f} mm"},
]
