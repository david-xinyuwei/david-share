import cadquery as cq
import math

# 笔记本双风扇散热模组 —— 轨 B 参考脚本：14 英寸轻薄本散热模组装配（系统级），尺寸与摆放取自场景示例 P：
# 0.6 mm 铜均热板 130×85（半实心，中空 0.3）覆盖 CPU 40×30 与 GPU 29×29；两根 φ6 烧结铜热管压扁至 2.0 mm（截面宽按周长守恒）；
# 左右翅片组各 60×10×9，铜片 0.10 厚、间隙 0.35（每组 133 片，热管穿片处开槽）；两台 φ48×7 离心风扇（28 叶）；D 壳石墨片 0.1。
# 坐标：示例 three.js 为 y 向上，本脚本 T() 映射为 CAD 的 (x, -z, y)，导出 glTF 后与示例同一坐标系。机身为 GLB 素材，不纳入实体。
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


def box3(size, center):   # 示例坐标下的长方体（size = x, y, z）
    sx, sy, sz = size
    return cq.Solid.makeBox(sx, sz, sy, T(*center) - cq.Vector(sx / 2, sz / 2, sy / 2))


def wp(shape):
    return cq.Workplane("XY").newObject([shape])


cpu = wp(box3(P["cpu"], P["cpuCenter"]))
gpu = wp(box3(P["gpu"], P["gpuCenter"]))
top_y = P["cpuCenter"][1] + P["cpu"][1] / 2
tim_cpu = wp(box3([P["cpu"][0], P["tim"], P["cpu"][2]], [P["cpuCenter"][0], top_y + P["tim"] / 2, P["cpuCenter"][2]]))
tim_gpu = wp(box3([P["gpu"][0], P["tim"], P["gpu"][2]], [P["gpuCenter"][0], top_y + P["tim"] / 2, P["gpuCenter"][2]]))

# ---- 均热板：圆角外壳 0.6，中空 0.3（上下壁各 0.15），四周 3 mm 封边
vx, vy, vz = P["vc"]
vcc = T(*P["vcCenter"])
vc = cq.Workplane("XY").workplane(offset=vcc.z - vy / 2).center(vcc.x, vcc.y).rect(vx, vz).extrude(vy).edges("|Z").fillet(P["vcCorner"])
cav = (cq.Workplane("XY").workplane(offset=vcc.z - P["vcCavity"] / 2).center(vcc.x, vcc.y)
       .rect(vx - 2 * P["vcInset"], vz - 2 * P["vcInset"]).extrude(P["vcCavity"]).edges("|Z").fillet(P["vcCorner"] - 1))
vc = vc.cut(cav)

# ---- 压扁热管：沿示例控制点做平面样条，2D 等距成带状后拉伸 2.0；内腔等距缩 0.3，端部自然封口
hp_w = (math.pi * P["hpDiameter"] - (math.pi - 2) * P["hpHeight"]) / 2
z_hp = P["hpY"] - P["hpHeight"] / 2
pipes, hp_len = [], 0.0
for s in (-1, 1):
    pts = [(-s * x, -z) for x, z in P["hpPath"]]     # hpPath 为左侧路径（x < 0），右侧镜像
    path = cq.Workplane("XY").workplane(offset=z_hp).spline(pts, includeCurrent=False)
    hp_len += path.val().Length()
    outer = cq.Workplane("XY").workplane(offset=z_hp).spline(pts, includeCurrent=False).offset2D(hp_w / 2).extrude(P["hpHeight"])
    inner = (cq.Workplane("XY").workplane(offset=z_hp + P["hpWall"]).spline(pts, includeCurrent=False)
             .offset2D(hp_w / 2 - P["hpWall"]).extrude(P["hpHeight"] - 2 * P["hpWall"]))
    pipes.append((outer, outer.cut(inner)))

# ---- 翅片组：每组 133 片 0.10 铜片，间隙 0.35；热管穿过处开槽
fin_n = int(math.floor(P["finWidth"] / (P["finThick"] + P["finGap"])))
fins = []
for s, (outer, _) in zip((-1, 1), pipes):
    x0 = s * P["fanX"] - P["finWidth"] / 2 + P["finThick"] / 2
    solids = [box3([P["finThick"], P["finHeight"], P["finDepth"]], [x0 + i * (P["finThick"] + P["finGap"]), P["bottom"] + P["finHeight"] / 2, P["finZ"]])
              for i in range(fin_n)]
    fins.append(wp(cq.Compound.makeCompound(solids)).cut(outer))

# ---- 离心风扇：壳体（侧壁 + 上下盖板，上下各一 Ø30 进风口，朝翅片一侧开出风口）+ 叶轮（后盘 + 轮毂 + 28 叶）
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

# ---- D 壳内侧石墨片（风扇进风处开孔）
gx, gt, gz = P["graphite"]
graphite = cq.Workplane("XY").workplane(offset=P["graphiteY"]).rect(gx, gz).extrude(gt)
for s in (-1, 1):
    fc = T(s * P["fanX"], 0, P["fanZ"])
    graphite = graphite.cut(cq.Solid.makeCylinder(R, 1.0, cq.Vector(fc.x, fc.y, P["graphiteY"] - 0.5)))

PARTS = {"CPU 封装": cpu, "独显 GPU 封装": gpu, "液态金属界面（CPU）": tim_cpu, "导热膏界面（GPU）": tim_gpu, "铜均热板": vc,
         "左压扁热管": pipes[0][1], "右压扁热管": pipes[1][1], f"左铜翅片组 ×{fin_n}": fins[0], f"右铜翅片组 ×{fin_n}": fins[1],
         "左离心风扇壳体": housings[0], "左风扇叶轮（28 叶）": rotors[0], "右离心风扇壳体": housings[1], "右风扇叶轮（28 叶）": rotors[1],
         "D 壳石墨片": graphite}
mats = ["pcb", "pcb", "steel", "polymerLight", "copper", "copper", "copper", "copper", "copper", "aluminumCast", "polymer",
        "aluminumCast", "polymer", "powderCoat"]
dens = [P["packageDensity"], P["packageDensity"], P["liquidMetalDensity"], P["pasteDensity"]] + [P["copperDensity"]] * 5 + \
       [P["aluminumDensity"], P["polymerDensity"], P["aluminumDensity"], P["polymerDensity"], P["graphiteDensity"]]
MATERIALS = dict(zip(PARTS, mats))
DENSITIES = dict(zip(PARTS, dens))
NAME = "笔记本双风扇散热模组"
vols = {k: w.val().Volume() for k, w in PARTS.items()}
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

METRICS = [
    {"label": "翅片数量（两组）", "value": 2 * fin_n, "unit": "片", "note": "每组 60 ÷ (0.10 + 0.35) 取整"},
    {"label": "热管压扁截面宽", "value": round(hp_w, 2), "unit": "mm", "note": "φ6 压扁至 2.0 mm，周长守恒"},
    {"label": "热管中心线总长", "value": round(hp_len, 1), "unit": "mm", "note": "两根，按示例控制点样条"},
    {"label": "模组堆叠高度", "value": P["bottom"] + P["finHeight"] - P["graphiteY"], "unit": "mm", "note": f"D 壳内表面至翅片 / 风扇顶，限高 {P['heightLimit']:g} mm"},
    {"label": "均热板 / 热源面积比", "value": round(vx * vz / (P["cpu"][0] * P["cpu"][2] + P["gpu"][0] * P["gpu"][2]), 2), "unit": "", "note": "130×85 对 CPU 40×30 + GPU 29×29"},
    {"label": "风扇叶片", "value": f"{P['bladeCount']} × 2", "unit": "片", "note": "φ48 × 7 离心风扇"},
]
