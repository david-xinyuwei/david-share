import cadquery as cq
import math

# AIDC CDU 液冷分配单元 —— 轨 B 参考脚本：1.2 MW 列级 CDU + 8 个 150 kW 液冷机柜的设备与管路实体（系统级 1:1），摆放取自场景示例 P：
# CDU 1100×2100×950（开放框架，便于查看内部）：钎焊板换 380×800×340（18 片）、两台变频电子水泵（N+1）、过滤器、膨胀 / 补液罐、
# 一次侧比例调节阀、温压流传感器；二次侧供 / 回液主管（高 380 / 1,500，位于机柜后方 z = 680）；8 个机柜间距 760，
# 每柜 8 层服务器托盘（每盘 2 块铜冷板）、后部供回液分歧管、支路隔离电子水阀。CDU 内管路按示例回路控制点做样条扫掠（空心管）。
# 坐标：示例 three.js 为 y 向上，本脚本 T() 映射为 CAD 的 (x, -z, y)，导出 glTF 后与示例同一坐标系。
P = {
    "racks": 8, "rackW": 600.0, "rackH": 1900.0, "rackD": 850.0, "pitch": 760.0, "rackStart": 1600.0,
    "cduW": 1100.0, "cduH": 2100.0, "cduD": 950.0, "hx": [380.0, 800.0, 340.0], "hxPos": [-220.0, 1200.0, 0.0], "hxPlates": 18,
    "pumpR": 125.0, "pumpL": 280.0, "pumpX": 230.0, "pumpY": 300.0, "tankR": 110.0, "tankH": 420.0, "tankPos": [270.0, 1600.0, -50.0],
    "filterR": 85.0, "filterH": 280.0, "filterPos": [400.0, 620.0, 220.0], "valveR": 70.0, "valveL": 120.0, "pvalvePos": [-620.0, 1150.0, 0.0],
    "sensorR": 35.0, "sensorH": 90.0, "sensorPos": [670.0, 850.0, 680.0], "facilityPos": [-1000.0, 800.0, 0.0],
    "plate": [430.0, 24.0, 390.0], "plateCount": 8, "plateStep": 180.0, "plateBase": 300.0,
    "supplyY": 380.0, "returnY": 1500.0, "headerZ": 680.0, "headerR": 45.0, "branchR": 18.0, "primaryR": 40.0, "wall": 3.0,
    "steelDensity": 7.90, "aluminumDensity": 2.70, "copperDensity": 8.96, "glassDensity": 2.5, "polymerDensity": 1.4,
    "cduFrameMass": 280.0, "rackMass": 140.0,   # 假设：框架 / 空机柜典型自重 kg（实体为实心简化件，按此折算等效密度）
    "fill": {"hx": 0.25, "pump": 0.6, "filter": 0.3, "tank": 0.25},   # 假设：外形包络件的实体占比（内腔未建模）
}
EDGE_FINISH = 0   # 7 m 级系统布置：亚毫米自动倒钝看不见；各部件显式建模的圆角保留
H, BR = P["headerR"], P["branchR"]
end_x = P["rackStart"] + (P["racks"] - 1) * P["pitch"]


def T(x, y, z):
    return cq.Vector(x, -z, y)


def box3(size, center):
    sx, sy, sz = size
    return cq.Solid.makeBox(sx, sz, sy, T(*center) - cq.Vector(sx / 2, sz / 2, sy / 2))


AX = {"x": cq.Vector(1, 0, 0), "y": cq.Vector(0, 0, 1), "z": cq.Vector(0, -1, 0)}


def cyl(r, length, center, axis):
    d = AX[axis]
    return cq.Solid.makeCylinder(r, length, T(*center) - d * (length / 2), d)


def tube(r, t, length, center, axis):
    return cyl(r, length, center, axis).cut(cyl(r - t, length + 2, center, axis))


def pipe(pts, r, t, closed=False):   # 沿控制点样条扫掠空心圆管；失败时退回直段 + 球形弯头
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


def wp(shapes):
    return cq.Workplane("XY").newObject([cq.Compound.makeCompound(shapes) if isinstance(shapes, list) else shapes])


def fuse(solids):
    return solids[0].fuse(*solids[1:]).clean()


PARTS, MATERIALS, DENSITIES = {}, {}, {}


def add(name, shapes, mat, dens):
    PARTS[name] = wp(shapes)
    MATERIALS[name] = mat
    DENSITIES[name] = dens


# ---- CDU 开放式框架：4 立柱 + 顶板 + 底座 + 中层横梁
W, Hc, D = P["cduW"], P["cduH"], P["cduD"]
frame = [box3([60, Hc, 60], [sx * (W / 2 - 30), Hc / 2, sz * (D / 2 - 30)]) for sx in (-1, 1) for sz in (-1, 1)]
frame += [box3([W, 40, D], [0, Hc - 20, 0]), box3([W, 100, D], [0, 50, 0])]
frame += [box3([W - 120, 50, 50], [0, 1000, sz * (D / 2 - 30)]) for sz in (-1, 1)]
frame = fuse(frame)
add("CDU 机柜框架（侧板未建模，便于查看内部）", frame, "powderCoat", P["cduFrameMass"] * 1e6 / frame.Volume())

# ---- 钎焊板式换热器：芯体 + 18 片外凸板片 + 前后压板 + 4 个法兰接口（前：一次侧，后：二次侧）
hx, hc = P["hx"], P["hxPos"]
plates = [box3([hx[0] + 8, hx[1], 4], [hc[0], hc[1], -hx[2] / 2 + i * hx[2] / (P["hxPlates"] - 1)]) for i in range(P["hxPlates"])]
hxs = [box3(hx, hc)] + plates + [box3([hx[0] + 30, hx[1] + 40, 20], [hc[0], hc[1], sz * (hx[2] / 2 + 10)]) for sz in (-1, 1)]
for y, sz in ((1100.0, -1), (1500.0, -1), (950.0, 1), (1400.0, 1)):
    hxs += [cyl(P["primaryR"] + 4, 45, [hc[0], y, sz * (hx[2] / 2 + 42)], "z"), cyl(75, 14, [hc[0], y, sz * (hx[2] / 2 + 27)], "z")]
add("钓焊板式换热器（18 片）", fuse(hxs), "steel", P["steelDensity"] * P["fill"]["hx"])

# ---- 两台变频电子水泵（N+1）：泵壳 + 电机 + 底座 + 顶部出口
motors, skids = [], []
for k, sx in enumerate((-1, 1)):
    x = sx * P["pumpX"]
    casing = [cyl(P["pumpR"], P["pumpL"], [x, P["pumpY"], 0], "z"), cyl(P["pumpR"] + 12, 18, [x, P["pumpY"], -P["pumpL"] / 2 + 9], "z"),
              cyl(50, 60, [x, P["pumpY"] + P["pumpR"] + 25, 40], "y"), cyl(46, 50, [x, P["pumpY"], P["pumpL"] / 2 + 20], "z")]
    add(f"变频电子水泵 {k + 1}（{'运行' if k == 0 else '备用'}）泵壳", fuse(casing), "steel", P["steelDensity"] * P["fill"]["pump"])
    motors.append(cyl(P["pumpR"] - 20, 170, [x, P["pumpY"], -P["pumpL"] / 2 - 85], "z"))
    skids.append(box3([260, 75, 480], [x, 100 + 37.5, -60]))
add("水泵电机 ×2", motors, "anodizedBlue", P["steelDensity"] * 0.6)
add("水泵底座 ×2", skids, "steelDark", P["steelDensity"])

# ---- 一次侧比例调节阀、过滤器、膨胀 / 补液罐、传感器、设施水接口
pv = P["pvalvePos"]
add("一次侧电子比例调节阀", fuse([cyl(P["valveR"], P["valveL"], pv, "y"), cyl(P["valveR"] + 15, 14, [pv[0], pv[1] - P["valveL"] / 2, pv[2]], "y"),
                                 cyl(P["valveR"] + 15, 14, [pv[0], pv[1] + P["valveL"] / 2, pv[2]], "y")]), "steel", P["steelDensity"])
actuators = [box3([110, 130, 100], [pv[0], pv[1] + P["valveL"] / 2 + 70, pv[2]])]
fp = P["filterPos"]
flt = cq.Workplane("XY").newObject([cyl(P["filterR"], P["filterH"], fp, "y")]).faces(">Z").edges().fillet(25)
flt = flt.union(cyl(P["filterR"] + 12, 16, [fp[0], fp[1] + P["filterH"] / 2 - 40, fp[2]], "y"))
add("二次侧过滤器", flt.val(), "steel", P["steelDensity"] * P["fill"]["filter"])
tp = P["tankPos"]
tank = cq.Workplane("XY").newObject([cyl(P["tankR"], P["tankH"], tp, "y")]).edges("%CIRCLE").fillet(40)
tank = tank.union(cyl(30, 40, [tp[0], tp[1] + P["tankH"] / 2 + 15, tp[2]], "y"))
add("膨胀 / 补液罐", tank.val(), "aluminum", P["aluminumDensity"] * P["fill"]["tank"])
add("液位视窗", cyl(12, 260, [tp[0] + P["tankR"] + 14, tp[1], tp[2]], "y"), "glass", P["glassDensity"])
sp = P["sensorPos"]
add("供回液温压流传感器 ×3", [cyl(P["sensorR"], P["sensorH"], [sp[0], sp[1] + i * 110, sp[2] - 60], "z") for i in range(3)], "anodizedBlue", P["polymerDensity"])
add("传感器支架", box3([40, 1320, 40], [sp[0], 960, sp[2] - 125]), "steelDark", P["steelDensity"])
fc = P["facilityPos"]
add("一次侧设施水接口", fuse([box3([260, 450, 300], fc), cyl(P["primaryR"] + 4, 60, [fc[0] - 160, 700, 0], "x"), cyl(75, 14, [fc[0] - 137, 700, 0], "x")]),
    "steel", P["steelDensity"])

# ---- 管路：一次侧闭环、CDU 内二次侧（回液 → 板换 → 泵 → 过滤器 → 供液）、两根主管、机柜支管与分歧管
pipes_len = {}
prim, pipes_len["primary"] = pipe([[-1000, 700, 0], [-620, 700, 0], [-620, 1150, 0], [-220, 1100, -190], [-220, 1500, -190], [-1000, 1500, -190]],
                                  P["primaryR"], P["wall"], closed=True)
add("一次侧设施水回路管", prim, "steel", P["steelDensity"])
inner = []
for key, pts in (("return_in", [[640, P["returnY"], P["headerZ"]], [-220, 1400, 190], [-220, 950, 190]]),
                 ("pump1", [[-220, 950, 190], [-230, 600, 100], [-230, 300, 160], [400, 400, 220], [400, 620, 220]]),
                 ("pump2", [[-220, 950, 190], [230, 600, 100], [230, 300, 160], [400, 400, 220], [400, 620, 220]]),
                 ("supply_out", [[400, 620, 220], [560, 470, 470], [640, P["supplyY"], P["headerZ"]]])):
    s, pipes_len[key] = pipe(pts, H, P["wall"])
    inner.append(s)
add("CDU 内二次侧管路 ×4", inner, "steel", P["steelDensity"])
hdr_len = end_x + 80 - 620
for name, y in (("二次侧供液主管", P["supplyY"]), ("二次侧回液主管", P["returnY"])):
    c = [(620 + end_x + 80) / 2, y, P["headerZ"]]
    add(name, fuse([tube(H, P["wall"], hdr_len, c, "x"), cyl(H + 5, 10, [end_x + 85, y, P["headerZ"]], "x")]), "steel", P["steelDensity"])

# ---- 8 个机柜：框架 + 侧板 + 8 层服务器托盘（每盘 2 块铜冷板）+ 后部分歧管 + 支管 + 支路隔离阀
rw, rh, rd = P["rackW"], P["rackH"], P["rackD"]
trays, coldplates, manifolds, branches, valves, valves5 = [], [], [], [], [], []
for i in range(P["racks"]):
    x = P["rackStart"] + i * P["pitch"]
    rack = [box3([40, rh, 40], [x + sx * (rw / 2 - 20), rh / 2, sz * (rd / 2 - 20)]) for sx in (-1, 1) for sz in (-1, 1)]
    rack += [box3([rw, 20, rd], [x, rh - 10, 0]), box3([rw, 60, rd], [x, 30, 0])]
    rack += [box3([2, rh - 80, rd - 80], [x + sx * (rw / 2 - 1), rh / 2, 0]) for sx in (-1, 1)]
    rack = fuse(rack)
    add(f"机柜 {i + 1}" + ("（漏液隔离演示）" if i == 4 else ""), rack, "powderCoat", P["rackMass"] * 1e6 / rack.Volume())
    for j in range(P["plateCount"]):
        y = P["plateBase"] + j * P["plateStep"]
        trays.append(box3(P["plate"], [x, y, 0]))
        coldplates += [box3([110, 8, 110], [x + sx * 100, y + 16, -40]) for sx in (-1, 1)]
    top = P["plateBase"] + (P["plateCount"] - 1) * P["plateStep"] + 80
    manifolds += [tube(BR, 2.0, top - 250, [x - 80, (top + 250) / 2, 260], "y"), tube(BR, 2.0, top - 250, [x + 80, (top + 250) / 2, 340], "y")]
    branches += [tube(BR, 2.0, P["headerZ"] - 260, [x - 80, P["supplyY"], (P["headerZ"] + 260) / 2], "z"),
                 tube(BR, 2.0, P["headerZ"] - 340, [x + 80, P["returnY"], (P["headerZ"] + 340) / 2], "z")]
    for xx, y in ((x - 80, P["supplyY"]), (x + 80, P["returnY"])):
        (valves5 if i == 4 else valves).append(cyl(P["valveR"] * 0.55, P["valveL"] * 0.65, [xx, y, P["headerZ"] - 145], "z"))
        actuators.append(box3([70, 80, 60], [xx, y + P["valveR"] * 0.55 + 40, P["headerZ"] - 145]))
add(f"服务器托盘 ×{len(trays)}", trays, "aluminum", P["aluminumDensity"] / 3)
add(f"GPU 铜冷板 ×{len(coldplates)}", coldplates, "copper", P["copperDensity"])
add(f"机柜供回液分歧管 ×{len(manifolds)}", manifolds, "steel", P["steelDensity"])
add(f"机柜供回液支管 ×{len(branches)}", branches, "steel", P["steelDensity"])
add(f"支路隔离电子水阀 ×{len(valves)}", valves, "steel", P["steelDensity"])
add("机柜 5 支路隔离电子水阀 ×2", valves5, "steel", P["steelDensity"])
add(f"电动执行器 ×{len(actuators)}", actuators, "anodizedBlue", P["polymerDensity"])

NAME = "AIDC 列级 CDU 与 8 机柜液冷系统"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

ri = (H - P["wall"]) / 1000
secondary_m = (2 * hdr_len + sum(v for k, v in pipes_len.items() if k != "primary")) / 1000
rack_m = P["racks"] * (2 * (top - 250) + (P["headerZ"] - 260) + (P["headerZ"] - 340)) / 1000
fill_l = (math.pi * ri ** 2 * secondary_m + math.pi * ((BR - 2) / 1000) ** 2 * rack_m) * 1000
METRICS = [
    {"label": "液冷机柜", "value": P["racks"], "unit": "个", "note": "每柜 8 层服务器托盘"},
    {"label": "GPU 铜冷板", "value": len(coldplates), "unit": "块", "note": "每盘 2 块（示意）"},
    {"label": "供 / 回液主管长度", "value": round(hdr_len / 1000, 2), "unit": "m", "note": "各一根，DN90 × 3"},
    {"label": "二次侧管路充液量", "value": round(fill_l, 1), "unit": "L", "note": "主管 + CDU 内管路 + 机柜支管与分歧管，不含板换与冷板"},
    {"label": "机柜列长度", "value": round((end_x + rw / 2 - (P["rackStart"] - rw / 2)) / 1000, 2), "unit": "m", "note": f"间距 {P['pitch']:g} mm"},
    {"label": "CDU 外形", "value": f"{W:g} × {D:g} × {Hc:g}", "unit": "mm", "note": "宽 × 深 × 高"},
]
