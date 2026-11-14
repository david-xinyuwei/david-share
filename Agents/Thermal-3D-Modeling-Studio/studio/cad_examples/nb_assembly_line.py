import cadquery as cq
import math

# 笔记本总装产线数字孪生 —— 轨 B 参考脚本：60 m U 形总装线的设备布置实体（方案①单班 800 台，系统级 1:1），摆放取自场景示例：
# 输送带两条长边各 26 m、横边 8 m、带面高 900；14 个工位沿带外侧 2,050 mm 布置（间距按线长均分）；机器人工位 ③⑦⑬、
# AOI ⑧、测试 ⑨（方案① 6 台，另留 3 个方案② 机位）、老化架 ⑩（5 层）、其余为人工工位（防疲劳地垫 + 灯架 + 物料盒）。
# 线边仓中心由示例的 z = 7,200 外移到 9,800（示例为半透明示意，原位置与 ⑪ 工位操作区重叠）；3 台 AGV 停在仓前。
# 坐标：示例 three.js 为 y 向上，本脚本 T() 映射为 CAD 的 (x, -z, y)，导出 glTF 后与示例同一坐标系。
P = {
    "leg": 26000.0, "span": 8000.0, "beltWidth": 1100.0, "beltHeight": 900.0, "beltThick": 220.0, "stationOffset": 2050.0,
    "table": [1900.0, 850.0, 1700.0], "agv": [1200.0, 450.0, 850.0], "unit": [301.0, 14.5, 220.0],
    "rack": [2300.0, 2500.0, 1800.0], "rackLevels": 5, "rackSlots": 240, "testers": 6, "testerSlots": 9,
    "warehouse": [7200.0, 2400.0, 2200.0], "warehouseZ": 9800.0, "agvZ": 8100.0,
    "categories": ["人工", "人工", "机器人", "人工", "人工", "人工", "机器人", "AOI", "测试", "老化", "人工", "人工", "机器人", "人工"],
    "names": ["① 底壳上线", "② 主板与散热装配", "③ 自动锁螺钉", "④ 电池与扬声器", "⑤ 屏幕与转轴", "⑥ 键盘与合盖", "⑦ 自动锁螺钉",
              "⑧ 外观 AOI", "⑨ 测试", "⑩ 老化", "⑪ 软件与终检", "⑫ 贴标与包装", "⑬ 装箱码垛", "⑭ 成品下线"],
    # 设备多为外形包络实体：取等效密度（g/cm³），使各部件质量接近实物量级，而不是材料真密度
    "frameDensity": 0.20, "beltDensity": 0.18, "legDensity": 0.60, "stationDensity": 0.45, "robotDensity": 1.20, "toolDensity": 2.00,
    "aoiDensity": 1.00, "testerDensity": 0.45, "slotDensity": 0.07, "matDensity": 1.20, "binDensity": 0.12, "unitDensity": 1.35,
    "shelfDensity": 0.40, "crateDensity": 0.15, "agvDensity": 0.85, "loadDensity": 0.26, "wheelDensity": 1.20,
}
EDGE_FINISH = 0   # 28 m 级布置：亚毫米自动倒钝看不见，只增加面数与 glb 体积
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


def path_at(d):   # 与示例 pathAt() 相同：返回带面中心点与行进方向角
    if d < LEG:
        return (-LEG / 2 + d, -SPAN / 2), 0.0
    if d < LEG + SPAN:
        return (LEG / 2, -SPAN / 2 + d - LEG), -90.0
    return (LEG / 2 - (d - LEG - SPAN), SPAN / 2), 180.0


# ---- U 形输送线：铝机架 + 带面 + 支腿
bw, bt = P["beltWidth"], P["beltThick"]
frame = fuse([box3([LEG + bw / 2, bt - 20, bw], [bw / 4, BH - 20 - (bt - 20) / 2, z]) for z in (-SPAN / 2, SPAN / 2)]
             + [box3([bw, bt - 20, SPAN], [LEG / 2, BH - 20 - (bt - 20) / 2, 0])])
belt = fuse([box3([LEG + bw / 2 - 50, 20, bw - 50], [bw / 4 - 25, BH - 10, z]) for z in (-SPAN / 2, SPAN / 2)]
            + [box3([bw - 50, 20, SPAN - bw + 50], [LEG / 2, BH - 10, 0])])
legs = [box3([180, BH - bt, 700], [x, (BH - bt) / 2, z]) for z in (-SPAN / 2, SPAN / 2) for x in range(-12000, 12001, 4000)]
legs += [box3([700, BH - bt, 180], [LEG / 2, (BH - bt) / 2, z]) for z in (-2000.0, 2000.0)]

# ---- 14 个工位：工作台（铝型材，含下层板）+ 按类别的设备
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
    if cat == "人工":   # 灯架 + 物料盒 + 防疲劳地垫（操作员站在远离输送带一侧）
        body += [box3([40, 1250, 40], [sx * (tw / 2 - 110), th + 50 + 625, -(td / 2 - 110)]) for sx in (-1, 1)]
        body += [box3([tw - 180, 40, 40], [0, th + 50 + 1250, -(td / 2 - 110)]), box3([1200, 30, 150], [0, th + 50 + 1215, -(td / 2 - 200)])]
        bins += place([box3([320, 120, 220], [k * 400, th + 110, -(td / 2 - 250)]) for k in (-1, 0, 1)], rot, pos)
        mats += place([box3([1600, 15, 600], [0, 7.5, td / 2 + 350])], rot, pos)
    elif cat == "机器人":
        robots += place([fuse([cq.Solid.makeCylinder(230, 220, T(0, th + 50, 0)), box3([230, 850, 230], [0, th + 270 + 420, 0]),
                               box3([850, 210, 230], [350, th + 270 + 830, 0])])], rot, pos)
        tools += place([box3([130, 260, 150], [730, th + 270 + 660, 0])], rot, pos)
    elif cat == "测试":
        for j in range(P["testerSlots"]):
            s = box3([480, 400, 360], [(j % 3 - 1) * 560, th + 250, (j // 3) * 470 - 470])
            (testers if j < P["testers"] else reserved).extend(place([s], rot, pos))
    elif cat == "老化":
        rw, rh, rd = P["rack"]
        body += [box3([rw, 120, rd], [0, th + 50 + 60, 0])]
        body += [box3([rw, 65, rd], [0, 1050 + k * 350, 0]) for k in range(P["rackLevels"])]
        body += [box3([80, 1800, rd - 100], [sx * (rw / 2 - 40), 1800, 0]) for sx in (-1, 1)]
        slots += place([box3([270, 120, 600], [(j - 2.5) * 350, 1150 + k * 350, 0]) for k in range(P["rackLevels"]) for j in range(6)], rot, pos)
    else:   # AOI：背板机柜 + 悬臂相机
        aoi += place([fuse([box3([1600, 1200, 180], [0, 1450, -600]), box3([120, 120, 600], [0, 1900, -300]),
                            box3([450, 220, 450], [0, 1900, 0])])], rot, pos)
    stations.append(place([fuse(body)], rot, pos)[0])
    # 输送带上的在制品（合盖整机），长边沿行进方向
    units.append(box3(P["unit"], [0, BH + P["unit"][1] / 2, 0]).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), heading).translate(T(px, 0, pz)))

# ---- 线边仓（货架 + 料箱）与 3 台 AGV
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


add("U 形输送线机架", wp(frame), "aluminum", P["frameDensity"])
add("输送带面（PVC）", wp(belt), "rubber", P["beltDensity"])
add(f"输送线支腿 ×{len(legs)}", wp(legs), "aluminum", P["legDensity"])
for i, s in enumerate(stations):
    add(f"{P['names'][i]} 工位", wp(s), "aluminum", P["stationDensity"])
add("六轴机器人 ×3（③⑦⑬）", wp(robots), "polymerLight", P["robotDensity"])
add("机器人末端执行器 ×3", wp(tools), "anodizedRed", P["toolDensity"])
add("⑧ AOI 视觉检测机", wp(aoi), "powderCoat", P["aoiDensity"])
add(f"⑨ 测试机台 ×{len(testers)}（方案①）", wp(testers), "anodizedBlue", P["testerDensity"])
add(f"⑨ 预留测试机位 ×{len(reserved)}（方案②启用）", wp(reserved), "glass", 0.0)
add(f"⑩ 老化中整机（示意 {len(slots)} / {P['rackSlots']} 台位）", wp(slots), "anodizedBlue", P["slotDensity"])
add(f"防疲劳地垫 ×{len(mats)}", wp(mats), "rubber", P["matDensity"])
add(f"工位物料盒 ×{len(bins)}", wp(bins), "anodizedBlue", P["binDensity"])
add(f"在制品（合盖整机）×{len(units)}", wp(units), "aluminum", P["unitDensity"])
add("线边仓货架", wp(fuse(shelf)), "powderCoat", P["shelfDensity"])
add(f"线边仓料箱 ×{len(crates)}", wp(crates), "cardboard", P["crateDensity"])
add("配送 AGV ×3", wp(agv_body), "anodizedOrange", P["agvDensity"])
add("AGV 载料箱 ×3", wp(agv_load), "cardboard", P["loadDensity"])
add(f"AGV 车轮 ×{len(wheels)}", wp(wheels), "rubber", P["wheelDensity"])

NAME = "笔记本总装 U 形产线（方案① 单班 800 台）"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])
bb = result.val().BoundingBox()

METRICS = [
    {"label": "线体总长", "value": round(path_len / 1000, 1), "unit": "m", "note": "U 形：26 + 8 + 26 m"},
    {"label": "工位数", "value": 14, "unit": "个", "note": "沿带外侧 2,050 mm 布置"},
    {"label": "六轴机器人", "value": len(robots), "unit": "台", "note": "③ ⑦ 自动锁螺钉、⑬ 装箱码垛"},
    {"label": "测试机台（方案①）", "value": f"{len(testers)} + 预留 {len(reserved)}", "unit": "台", "note": "方案② 增至 9 台"},
    {"label": "老化台位（方案①）", "value": P["rackSlots"], "unit": "台位", "note": f"实体为 {P['rackLevels']} 层架，架上 {len(slots)} 台为示意"},
    {"label": "设备布置包络", "value": f"{bb.xlen / 1000:.1f} × {bb.ylen / 1000:.1f}", "unit": "m", "note": "含工位操作区与线边仓"},
]
