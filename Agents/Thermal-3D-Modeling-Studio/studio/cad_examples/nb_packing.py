import cadquery as cq
import math

# 包装与集装箱装载优化 —— 轨 B 参考脚本：方案①（标准托盘装柜）的四级装载实体：彩盒 → 外箱 → 托盘 → 40 尺高柜。
# 排布逐式移植自场景示例 planar() / compute(0)：外箱 = 5 只彩盒沿 62 mm 方向叠放 + 每边 10 mm 间隙 + 5 mm 板厚；托盘层
# 取两种朝向的最大排布，层数受堆高 1,800 mm 与单托 1,000 kg 约束；托盘在柜内单层不堆码。METRICS 与页面同式。
# 集装箱为剖视建模（不建顶板与近侧侧板，露出货物）；柜门外另摆一只剖开外箱：5 只彩盒，最上一只打开露出整机与纸浆缓冲。
P = {
    "retail": [355.0, 245.0, 62.0], "perCarton": 5, "gap": 10.0, "board": 5.0, "boardDensity": 0.75, "gross": 2.4,
    "pallet": [1200.0, 1000.0, 150.0], "maxHeight": 1800.0, "maxLoad": 1000.0, "palletMass": 22.0,
    "container": [12032.0, 2352.0, 2698.0], "carbon": 1200.0, "pulp": 0.18, "retailMass": 0.26,
    "deck": 25.0, "runnerWidth": 90.0, "laptop": [301.0, 220.0, 14.5], "laptopMass": 1.3,
    "shell": 2.0, "corrPitch": 278.0, "corrDepth": 36.0, "floorT": 28.0, "wallZone": 43.0, "endZone": 80.0, "under": 150.0,
    "doorT": 50.0, "steelDensity": 7.85, "woodDensity": 0.55, "floorDensity": 0.70, "paperDensity": 0.70, "pulpDensity": 0.25,
    "tare": 3900.0,   # 假设：40 尺高柜典型自重 kg；结构件为实心简化件，按自重折算等效密度
}
r = P["retail"]
e = P["gap"] + P["board"]
c = [r[0] + 2 * e, r[1] + 2 * e, r[2] * P["perCarton"] + 2 * e]
CW, CD, CH = P["container"]


def planar(area, box):   # 两种水平朝向取件数最多者（与页面 planar() 相同，平局取第一种）
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


# ---- 托盘与外箱：柜内坐标 x 0…12032（门端 +X），y ±1176，地板面 z = 0
(pdx, pdy), pnx, pny = packing
(cdx, cdy), cnx, cny = layer
pallets, cartons = [], []
for i in range(pnx):
    for j in range(pny):
        px, py = (CW - pnx * pdx) / 2 + i * pdx, -pny * pdy / 2 + j * pdy
        deck, run = P["deck"], P["runnerWidth"]
        for k in range(7):     # 面板 7 块（垂直于纵梁）
            pallets.append(B(px + k * (pdx - 120) / 6, py, P["pallet"][2] - deck, 120, pdy, deck))
        for yy in (0, (pdy - run) / 2, pdy - run):   # 3 根纵梁
            pallets.append(B(px, py + yy, deck, pdx, run, P["pallet"][2] - 2 * deck))
        for xx in (0, (pdx - 140) / 2, pdx - 140):   # 底板 3 块
            pallets.append(B(px + xx, py, 0, 140, pdy, deck))
        ox, oy = px + (pdx - cnx * cdx) / 2, py + (pdy - cny * cdy) / 2
        for L in range(layers):
            for a in range(cnx):
                for b in range(cny):     # 每只外箱四周各让 1 mm，露出箱缝
                    cartons.append(B(ox + a * cdx + 1, oy + b * cdy + 1, P["pallet"][2] + L * c[2] + 1, cdx - 2, cdy - 2, c[2] - 2))

# ---- 40 尺高柜（剖视）：瓦楞远侧侧板、前端墙、角柱、上下边梁、底横梁、门框；木地板；两扇门打开 90°
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
        frame.append(B(x0, y0, -un, ez, wz, top + un))                    # 角柱
for y0 in (-CD / 2 - wz, CD / 2):
    frame.append(B(0, y0, -un, CW, wz, 160))                               # 下边梁
frame.append(B(0, CD / 2, top - 100, CW, wz, 100))                         # 远侧上边梁
frame.append(B(-ez, -CD / 2, top - 100, ez, CD, 100))                      # 前端上横梁
frame.append(B(-ez, -CD / 2, -un, ez, CD, un))                             # 前端下横梁
frame.append(B(CW, -CD / 2, top - 150, ez, CD, 150))                       # 门楣
frame.append(B(CW, -CD / 2, -un, ez, CD, un))                              # 门槛
for k in range(24):                                                        # 底横梁
    frame.append(B(k * (CW - 60) / 23, -CD / 2, -un + 10, 60, CD, un - P["floorT"] - 10))
floor = comp([B(0, -CD / 2, -P["floorT"], CW, CD, P["floorT"])])
doors, bars = [], []
for sy in (-1, 1):   # 门扇绕外侧铰链转 90° 到柜外，沿 +X 伸出；锁杆在门外表面
    y_in = sy * (CD / 2 + wz)
    doors.append(B(CW + ez, y_in if sy < 0 else y_in - P["doorT"], 0, CD / 2 + wz, P["doorT"], top - 160))
    for f in (0.35, 0.75):
        bars.append(cq.Solid.makeCylinder(14, top - 200, cq.Vector(CW + ez + f * (CD / 2 + wz), y_in + sy * 16, 20)))

# ---- 柜门外的单箱剖视：剖开外箱（去顶、去前板）+ 5 只彩盒，最上一只打开，内有整机与纸浆缓冲
gx, gy, gz = CW + ez + CD / 2 + wz + 900, 0.0, -un
bd = P["board"]
open_carton = [B(gx, gy - c[1] / 2, gz, c[0], c[1], bd), B(gx + bd, gy + c[1] / 2 - bd, gz + bd, c[0] - 2 * bd, bd, c[2] - bd),
               B(gx, gy - c[1] / 2, gz + bd, bd, c[1], c[2] - bd), B(gx + c[0] - bd, gy - c[1] / 2, gz + bd, bd, c[1], c[2] - bd)]
bx, by = gx + e, gy - r[1] / 2
closed = [B(bx, by, gz + e + k * r[2], r[0], r[1], r[2]) for k in range(P["perCarton"] - 1)]
z5 = gz + e + (P["perCarton"] - 1) * r[2]
tray = cq.Workplane("XY").newObject([B(bx, by, z5, r[0], r[1], r[2] - 8)]).faces(">Z").shell(-1.5)
lid = (cq.Workplane("XY").newObject([B(0, -r[1], 0, r[0], r[1], 8)]).faces("<Z").shell(-1.5)   # 铰链在后上沿，开盖 105°
       .rotate((0, 0, 0), (1, 0, 0), -105).translate((bx, by + r[1], z5 + r[2] - 8)))
lap = P["laptop"]
pad = 1.5
cush = [B(bx + pad, by + pad, z5 + pad, r[0] - 2 * pad, r[1] - 2 * pad, 10)]
side_w = (r[0] - 2 * pad - lap[0]) / 2
cush += [B(bx + pad, by + pad, z5 + pad + 10, side_w, r[1] - 2 * pad, 30), B(bx + r[0] - pad - side_w, by + pad, z5 + pad + 10, side_w, r[1] - 2 * pad, 30)]
laptop = cq.Workplane("XY").newObject([B(bx + pad + side_w, gy - lap[1] / 2, z5 + pad + 10, lap[0], lap[1], lap[2])]).edges("|Z").fillet(8.0)

PARTS = {"集装箱结构（40 尺高柜，剖视）": comp(frame), "柜门 ×2（开启 90°）": comp(doors), "门锁杆 ×4": comp(bars), "木地板": floor,
         f"木托盘 ×{pnx * pny}": comp(pallets), f"瓦楞外箱 ×{len(cartons)}（每箱 {P['perCarton']} 台，含货）": comp(cartons),
         "剖开外箱（单箱剖视）": comp(open_carton), f"彩盒 ×{len(closed)}（封口，含整机）": comp(closed), "彩盒（打开）": tray.union(lid),
         "纸浆模塑缓冲": comp(cush), "笔记本整机（合盖）": laptop}
MATERIALS = dict(zip(PARTS, ["powderCoat", "powderCoat", "steel", "wood", "wood", "cardboard", "cardboard", "polymerLight",
                             "polymerLight", "cardboard", "aluminum"]))
vols = {k: w.val().Volume() for k, w in PARTS.items()}
names = list(PARTS)
steel_eq = (P["tare"] - vols[names[3]] * P["floorDensity"] / 1e6) * 1e6 / (vols[names[0]] + vols[names[1]] + vols[names[2]])
DENSITIES = dict(zip(names, [steel_eq, steel_eq, steel_eq, P["floorDensity"], P["palletMass"] * pnx * pny * 1e6 / vols[names[4]],
                             case_mass * len(cartons) * 1e6 / vols[names[5]],          # 外箱与彩盒按含货质量折算
                             P["boardDensity"] / P["board"], P["gross"] * len(closed) * 1e6 / vols[names[7]],
                             P["paperDensity"], P["pulpDensity"], P["laptopMass"] * 1e6 / vols[names[10]]]))
NAME = "笔记本包装与 40 尺高柜装载（方案① 标准托盘）"
DENSITY = sum(vols[k] * DENSITIES[k] for k in PARTS) / sum(vols.values())
result = cq.Workplane("XY").newObject([cq.Compound.makeCompound([w.val() for w in PARTS.values()])])

METRICS = [
    {"label": "每箱台数", "value": str(P["perCarton"]), "unit": "台", "note": "假设彩盒最短边堆叠"},
    {"label": "每托盘台数", "value": str(per_pallet), "unit": "台", "note": "假设规则整层，限重含托盘"},
    {"label": "每柜总台数", "value": str(total), "unit": "台", "note": "假设托盘不堆码，未扣绑扎空间"},
    {"label": "集装箱容积利用率(%)", "value": f"{util:.2f}", "unit": "%", "note": "假设按彩盒包络总体积计算"},
    {"label": "每台包装材料质量(g)", "value": f"{material:.1f}", "unit": "g", "note": "假设纸板0.75kg/m²，不计搭接辅材"},
    {"label": "每台海运碳排放(kg CO₂e)", "value": f"{P['carbon'] / total:.3f}", "unit": "kg CO₂e", "note": "假设全程每柜1200kg CO₂e均摊"},
]
