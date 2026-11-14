import cadquery as cq
import math

# 整车热管理系统回路 —— 轨 B 参考脚本：800 V 纯电 SUV 热管理系统的部件与三条回路管路实体（系统级 1:1），部件中心与回路控制点
# 取自场景示例 P：电池包 2100×170×1320（底部液冷板）、前电驱（电机 + 减速器 + 逆变器 + 油冷器）、热管理集成模块（歧管 + 九通阀 +
# 两台电子水泵）、chiller、微通道冷凝器 + 低温散热器 + 双风扇、电动压缩机、两个电子膨胀阀、HVAC（蒸发器 + 暖风芯体）、PTC。
# 管路按示例回路控制点做样条扫掠空心管：冷却液为 EPDM 软管，冷媒为铝管。车身外壳是示例的 GLB 素材，不纳入工程实体。
# 坐标：示例 three.js 为 x 车长（+x 车头）、y 高度、z 车宽，本脚本 T() 映射为 CAD 的 (x, -z, y)，导出 glTF 后与示例同一坐标系。
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
    # 假设：以下部件按外形包络建模（内部流道 / 翅片 / 齿轮未建模），按实体占比折算等效密度
    "fill": {"lid": 0.15, "coldplate": 0.35, "core": 0.12, "reducer": 0.6, "inverter": 0.4, "manifold": 0.2, "chiller": 0.15},
}
EDGE_FINISH = 0   # 整车级装配：亚毫米自动倒钝看不见；各部件显式建模的圆角保留


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


def fuse(solids):
    return solids[0].fuse(*solids[1:]).clean() if len(solids) > 1 else solids[0]


PARTS, MATERIALS, DENSITIES = {}, {}, {}


def add(name, shapes, mat, dens):
    PARTS[name] = cq.Workplane("XY").newObject([cq.Compound.makeCompound(shapes) if isinstance(shapes, list) else shapes])
    MATERIALS[name] = mat
    DENSITIES[name] = dens


# ---- 电池包：铸铝托盘（底 8 / 壁 8，12 个安装耳）+ 复合材料上盖 + 液冷板 + 12 个模组
bc, (bx, by, bz) = P["battery"], P["batterySize"]
y0 = bc[1] - by / 2
tray = box3([bx, by - 20, bz], [bc[0], y0 + (by - 20) / 2, 0], 40).cut(box3([bx - 16, by, bz - 16], [bc[0], y0 + 8 + by / 2, 0], 32))
for sx in range(6):
    for sz in (-1, 1):
        lug_c = [bc[0] - bx / 2 + 175 + sx * (bx - 350) / 5, y0 + by - 40, sz * (bz / 2 + 40)]
        tray = tray.fuse(box3([90, 20, 80], lug_c)).cut(cyl(7, 30, lug_c, "y"))
add("电池包托盘（铸铝）", tray.clean(), "aluminumCast", P["aluminumDensity"])
F = P["fill"]
add("电池包上盖", box3([bx, 20, bz], [bc[0], y0 + by - 10, 0], 40), "polymer", P["polymerDensity"] * F["lid"])
add("电池液冷板", box3([bx - 100, 8, bz - 80], [bc[0], y0 + 12, 0], 20), "aluminum", P["aluminumDensity"] * F["coldplate"])
add("电池模组 ×12", [box3([640, 110, 300], [bc[0] + (k - 1) * 680, y0 + 16 + 55, (m - 1.5) * 320], 8) for k in range(3) for m in range(4)],
    "anodized", P["cellDensity"])

# ---- 前电驱：电机（端盖 + 输出轴）+ 减速器 + 逆变器 + 油冷器
ec = P["edrive"]
R, Lm = P["motorR"], P["motorL"]
add("电驱电机", fuse([cyl(R, Lm, ec, "z"), cyl(R + 5, 20, [ec[0], ec[1], Lm / 2 + 10], "z"), cyl(R + 5, 20, [ec[0], ec[1], -Lm / 2 - 10], "z"),
                     cyl(25, 60, [ec[0], ec[1], Lm / 2 + 50], "z")]), "aluminumCast", P["aluminumDensity"])
add("减速器", box3([320, 300, 180], [ec[0] + 40, ec[1] - 20, -Lm / 2 - 20 - 90], 30), "aluminumCast", P["aluminumDensity"] * F["reducer"])
add("电驱逆变器", box3([380, 90, 300], [ec[0], ec[1] + R + 45, 0], 20), "anodized", P["aluminumDensity"] * F["inverter"])
add("电驱油冷器", box3([120, 70, 90], [ec[0] - R - 60, ec[1] - 50, 120], 6), "steel", P["steelDensity"])

# ---- 热管理集成模块：歧管（工程塑料，4 个安装耳）+ 九通电子水阀 + 两台电子水泵
ic, (ix, iy, iz) = P["itm"], P["itmSize"]
man_top = P["pump1"][1] - P["pumpL"] / 2
man_c = [ic[0], (ic[1] - iy / 2 + man_top) / 2, ic[2]]
man = box3([ix, man_top - (ic[1] - iy / 2), iz], man_c, 15)
for sx in (-1, 1):
    for sz in (-1, 1):
        c = [ic[0] + sx * (ix / 2 + 15), ic[1] - iy / 2 + 10, ic[2] + sz * (iz / 2 - 40)]
        man = man.fuse(box3([40, 20, 50], c)).cut(cyl(5, 30, c, "y"))
add("集成模块歧管", man.clean(), "polymer", P["polymerDensity"] * F["manifold"])
vc = P["valve9"]
vbase = man_top
valve = [cyl(70, vc[1] - P["valveH"] / 2 - vbase, [vc[0], (vbase + vc[1] - P["valveH"] / 2) / 2, vc[2]], "y"), cyl(P["valveR"], P["valveH"], vc, "y"),
         box3([120, 50, 90], [vc[0], vc[1] + P["valveH"] / 2 + 25, vc[2]], 8)]
valve += [cyl(12, 30, [vc[0] + math.cos(a) * (P["valveR"] + 12), vc[1] - 20, vc[2] + math.sin(a) * (P["valveR"] + 12)],
              "x" if abs(math.cos(a)) > 0.5 else "z") for a in (0, math.pi / 2, math.pi, 1.5 * math.pi)]
add("九通电子水阀", fuse(valve), "polymerLight", P["polymerDensity"])
for k, key in enumerate(("pump1", "pump2")):
    pc = P[key]
    add(f"电子水泵 {k + 1}", fuse([cyl(P["pumpR"], P["pumpL"], pc, "y"), cyl(P["pumpR"] - 10, 25, [pc[0], pc[1] + P["pumpL"] / 2 + 12, pc[2]], "y"),
                                  cyl(P["pumpR"] + 8, 6, [pc[0], pc[1] - P["pumpL"] / 2 + 3, pc[2]], "y"), cyl(14, 50, [pc[0] + P["pumpR"] + 20, pc[1] - 5, pc[2]], "x")]),
        "aluminumCast", P["aluminumDensity"])

# ---- Chiller（钎焊板式换热器）：芯体 + 16 片外凸板片 + 端板 + 4 个接口
cc = P["chiller"]
ch = [box3([180, 100, 140], cc)] + [box3([188, 104, 3], [cc[0], cc[1], cc[2] - 70 + i * 140 / 15]) for i in range(16)]
ch += [box3([200, 112, 10], [cc[0], cc[1], cc[2] + sz * 75]) for sz in (-1, 1)]
ch += [cyl(10, 25, [cc[0] + sx * 60, cc[1] + 62, cc[2] + sz * 40], "y") for sx in (-1, 1) for sz in (-1, 1)]
add("Chiller 板式换热器", fuse(ch), "steel", P["steelDensity"] * F["chiller"])

# ---- 前端模块：微通道冷凝器（40 扁管 + 翅片带 + 集流管）、低温散热器（芯体 + 塑料水室）、护风罩 + 双风扇
fs = P["frontSize"]
for key, depth, width, name in (("condenser", 16.0, 1200.0, "微通道冷凝器"), ("ltr", 30.0, 1150.0, "低温散热器芯体")):
    fc = P[key]
    core = [box3([depth, 2, width], [fc[0], fc[1] - 292.5 + k * 15, 0]) for k in range(40)]
    core += [box3([depth - 2, 13, width], [fc[0], fc[1] - 285 + k * 15, 0]) for k in range(39)]
    if key == "condenser":
        core += [cyl(16, 640, [fc[0], fc[1], sz * (width / 2 + 16)], "y") for sz in (-1, 1)]
    add(name, core, "aluminum", P["aluminumDensity"] * F["core"])
lc = P["ltr"]
add("低温散热器水室 ×2", [fuse([box3([50, 640, 40], [lc[0], lc[1], sz * (1150 / 2 + 20)], 6), cyl(16, 40, [lc[0], lc[1] + sz * 200, sz * (1150 / 2 + 60)], "z")])
                         for sz in (-1, 1)], "polymer", P["polymerDensity"])
fc = P["fan"]
shroud = box3([20, fs[1], fs[2]], [fc[0] + 20, fc[1], 0], 30)
for sz in (-1, 1):
    shroud = shroud.cut(cyl(280, 40, [fc[0] + 20, fc[1], sz * 300], "x")).fuse(cyl(292, 60, [fc[0] + 10, fc[1], sz * 300], "x").cut(cyl(282, 70, [fc[0] + 10, fc[1], sz * 300], "x")))
add("风扇护风罩", shroud.clean(), "polymer", P["polymerDensity"])
fans = []
for sz in (-1, 1):
    hub = T(fc[0] - 10, fc[1], sz * 300)
    f = cq.Solid.makeCylinder(70, 50, hub - cq.Vector(25, 0, 0), cq.Vector(1, 0, 0))
    for j in range(7):
        blade = (cq.Solid.makeBox(6, 90, 210, cq.Vector(-3, -45, 60)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 25)
                 .rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), j * 360 / 7).translate(hub))
        f = f.fuse(blade)
    fans.append(f.clean())
add("冷却风扇 ×2（7 叶）", fans, "polymer", P["polymerDensity"])

# ---- 电动压缩机：涡旋壳体 + 控制器 + 3 个安装脚 + 吸排气口
pc = P["compressor"]
comp = cq.Workplane("XY").newObject([cyl(P["compR"], P["compL"], pc, "x")]).edges("%CIRCLE").fillet(15).val()
comp = fuse([comp, box3([150, 60, 120], [pc[0], pc[1] + P["compR"] + 25, pc[2]], 10)]
            + [box3([40, 60, 170], [pc[0] + dx, pc[1] - P["compR"] + 10, pc[2]]) for dx in (-90, 0, 90)]
            + [cyl(sr, 45, [pc[0] + dx, pc[1] + 10, pc[2] + P["compR"] + 15], "z") for dx, sr in ((-70, 14), (70, 10))])
add("电动压缩机", comp, "aluminumCast", P["aluminumDensity"])

# ---- 两个电子膨胀阀：黄铜阀体 + 铜接管 + 线圈
bodies, coils = [], []
for key in ("exv1", "exv2"):
    xc = P[key]
    bodies.append(fuse([cyl(18, 40, [xc[0], xc[1] - 25, xc[2]], "y")] + [cyl(6.35, 40, [xc[0] + sx * 36, xc[1] - 30, xc[2]], "x") for sx in (-1, 1)]))
    coils.append(cyl(P["exvR"], 50, [xc[0], xc[1] + 20, xc[2]], "y"))
add("电子膨胀阀 ×2 阀体与接管", bodies, "brass", P["brassDensity"])
add("电子膨胀阀 ×2 线圈", coils, "polymer", P["polymerDensity"])

# ---- HVAC：塑料壳体（壁厚 3，顶部出风口）+ 蒸发器芯体 + 暖风芯体；PTC 加热器
hc, hs = P["hvac"], P["hvacSize"]
case = box3(hs, hc, 20).cut(box3([hs[0] - 6, hs[1] - 6, hs[2] - 6], hc, 17)).cut(box3([200, 20, 400], [hc[0], hc[1] + hs[1] / 2, 0]))
add("HVAC 壳体（顶部出风口）", case, "polymer", P["polymerDensity"])
add("蒸发器芯体", box3([60, 220, 520], [hc[0] - 80, hc[1], 0], 4), "aluminum", P["aluminumDensity"] * F["core"])
add("暖风芯体", box3([40, 180, 420], [hc[0] + 90, hc[1] - 10, 0], 4), "aluminum", P["aluminumDensity"] * F["core"])
tc = P["ptc"]
add("PTC 加热器", fuse([box3([160, 50, 180], tc, 8)] + [box3([150, 20, 4], [tc[0], tc[1] + 35, tc[2] - 70 + k * 20]) for k in range(8)]
                      + [cyl(10, 30, [tc[0] + sx * 95, tc[1], tc[2]], "x") for sx in (-1, 1)]), "aluminumCast", P["aluminumDensity"])

# ---- 三条回路管路
lens = {}
for key, name, r, t, mat, dens, closed in (("batteryLoop", "电池冷却液管路（EPDM）", P["hoseBattery"], P["hoseWall"], "rubber", P["rubberDensity"], True),
                                          ("edriveLoop", "电驱冷却液管路（EPDM）", P["hoseEdrive"], P["hoseWall"], "rubber", P["rubberDensity"], True),
                                          ("refLoop", "冷媒主干管路（铝）", P["refR"], P["refWall"], "aluminum", P["aluminumDensity"], True),
                                          ("refBranch", "冷媒 chiller 支路（铝）", P["refR"], P["refWall"], "aluminum", P["aluminumDensity"], False)):
    s, lens[key] = pipe(P[key], r, t, closed)
    add(name, s, mat, dens)

NAME = "800 V 纯电 SUV 整车热管理系统"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

coolant_l = sum(math.pi * ((rr - P["hoseWall"]) / 1000) ** 2 * lens[k] / 1000 for k, rr in (("batteryLoop", P["hoseBattery"]), ("edriveLoop", P["hoseEdrive"]))) * 1000
METRICS = [
    {"label": "电池回路管长", "value": round(lens["batteryLoop"] / 1000, 2), "unit": "m", "note": "按示例回路控制点样条，Ø18 EPDM"},
    {"label": "电驱回路管长", "value": round(lens["edriveLoop"] / 1000, 2), "unit": "m", "note": "Ø20 EPDM"},
    {"label": "冷媒管路总长", "value": round((lens["refLoop"] + lens["refBranch"]) / 1000, 2), "unit": "m", "note": "主干 + chiller 支路，Ø12 铝管"},
    {"label": "冷却液管内容积", "value": round(coolant_l, 2), "unit": "L", "note": "两条冷却液回路的软管部分，不含部件内腔"},
    {"label": "前端模块迎风面积", "value": round(fs[1] * fs[2] / 1e6, 3), "unit": "m²", "note": "620 × 1,250 mm"},
    {"label": "编号部件", "value": 15, "unit": "个", "note": "与示例热点一一对应（电池包至风扇）"},
]
