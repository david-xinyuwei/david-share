#!/usr/bin/env python3
"""
E1: Software Rasterizer — 从零实现 3D→2D 渲染管线
Author: 魏新宇 (Xinyu Wei)

验证内容：
  - 5 步坐标变换（Model → Camera → Projection → Clip → Viewport）
  - 三角形光栅化（Edge Function）
  - Z-Buffer 深度排序
  - 简单 Lambert 着色

输出：每步中间结果可视化 + 最终渲染图 + Z-Buffer 深度图
"""

import argparse
import json
import math
import time
import numpy as np
from PIL import Image

# ============================================================
# 1. 数学工具：4×4 齐次矩阵
# ============================================================

def normalize(v):
    """向量归一化"""
    n = np.linalg.norm(v)
    return v / n if n > 0 else v

def translation_matrix(tx, ty, tz):
    """平移矩阵"""
    return np.array([
        [1, 0, 0, tx],
        [0, 1, 0, ty],
        [0, 0, 1, tz],
        [0, 0, 0, 1]
    ], dtype=np.float64)

def rotation_y_matrix(angle_deg):
    """绕 Y 轴旋转矩阵"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([
        [c,  0, s, 0],
        [0,  1, 0, 0],
        [-s, 0, c, 0],
        [0,  0, 0, 1]
    ], dtype=np.float64)

def rotation_x_matrix(angle_deg):
    """绕 X 轴旋转矩阵"""
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([
        [1, 0,  0, 0],
        [0, c, -s, 0],
        [0, s,  c, 0],
        [0, 0,  0, 1]
    ], dtype=np.float64)

def scale_matrix(sx, sy, sz):
    """缩放矩阵"""
    return np.array([
        [sx, 0,  0,  0],
        [0,  sy, 0,  0],
        [0,  0,  sz, 0],
        [0,  0,  0,  1]
    ], dtype=np.float64)

def look_at_matrix(eye, target, up):
    """
    摄像机 LookAt 矩阵
    eye: 摄像机位置
    target: 看向的点
    up: 上方向向量
    """
    f = normalize(target - eye)      # forward
    r = normalize(np.cross(f, up))   # right
    u = np.cross(r, f)               # true up

    return np.array([
        [r[0],  r[1],  r[2],  -np.dot(r, eye)],
        [u[0],  u[1],  u[2],  -np.dot(u, eye)],
        [-f[0], -f[1], -f[2], np.dot(f, eye)],
        [0,     0,     0,     1]
    ], dtype=np.float64)

def perspective_matrix(fov_deg, aspect, near, far):
    """
    透视投影矩阵
    fov_deg: 垂直视角（度）
    aspect: 宽高比
    near/far: 近/远裁剪面
    """
    f = 1.0 / math.tan(math.radians(fov_deg) / 2.0)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), (2 * far * near) / (near - far)],
        [0, 0, -1, 0]
    ], dtype=np.float64)

# ============================================================
# 2. 场景定义：彩色立方体 + 地面
# ============================================================

def create_cube(size=1.0):
    """创建立方体的三角形网格，返回 (vertices, triangles, colors)"""
    s = size / 2.0
    # 8 个顶点
    verts = np.array([
        [-s, -s, -s], [s, -s, -s], [s, s, -s], [-s, s, -s],  # back face
        [-s, -s,  s], [s, -s,  s], [s, s,  s], [-s, s,  s],  # front face
    ], dtype=np.float64)

    # 12 个三角形（每面 2 个）+ 颜色
    faces = [
        # front (z+) — 蓝色
        ([4,5,6], [0.2, 0.4, 0.9]), ([4,6,7], [0.2, 0.4, 0.9]),
        # back (z-) — 红色
        ([1,0,3], [0.9, 0.2, 0.2]), ([1,3,2], [0.9, 0.2, 0.2]),
        # right (x+) — 绿色
        ([5,1,2], [0.2, 0.8, 0.3]), ([5,2,6], [0.2, 0.8, 0.3]),
        # left (x-) — 黄色
        ([0,4,7], [0.9, 0.9, 0.2]), ([0,7,3], [0.9, 0.9, 0.2]),
        # top (y+) — 紫色
        ([3,7,6], [0.7, 0.3, 0.8]), ([3,6,2], [0.7, 0.3, 0.8]),
        # bottom (y-) — 青色
        ([0,1,5], [0.2, 0.8, 0.8]), ([0,5,4], [0.2, 0.8, 0.8]),
    ]

    triangles = [f[0] for f in faces]
    colors = [f[1] for f in faces]
    return verts, triangles, colors

def create_ground(size=3.0, y=-0.5):
    """地面（2 个三角形）"""
    s = size
    verts = np.array([
        [-s, y, -s], [s, y, -s], [s, y, s], [-s, y, s]
    ], dtype=np.float64)
    triangles = [[0,1,2], [0,2,3]]
    colors = [[0.6, 0.6, 0.6], [0.5, 0.5, 0.5]]
    return verts, triangles, colors

# ============================================================
# 3. 管线各阶段
# ============================================================

def apply_transform(vertices, matrix):
    """对顶点应用 4×4 矩阵变换"""
    n = len(vertices)
    homogeneous = np.hstack([vertices, np.ones((n, 1))])  # Nx4
    transformed = (matrix @ homogeneous.T).T               # Nx4
    return transformed

def perspective_divide(clip_coords):
    """透视除法：齐次坐标 → NDC"""
    w = clip_coords[:, 3:4]
    w = np.where(np.abs(w) < 1e-10, 1e-10, w)  # 避免除零
    ndc = clip_coords[:, :3] / w
    return ndc

def viewport_transform(ndc, width, height):
    """NDC [-1,1] → 屏幕像素坐标"""
    screen = np.zeros_like(ndc)
    screen[:, 0] = (ndc[:, 0] + 1.0) * 0.5 * width
    screen[:, 1] = (1.0 - ndc[:, 1]) * 0.5 * height  # y 翻转
    screen[:, 2] = ndc[:, 2]  # 保留深度
    return screen

# ============================================================
# 4. 光栅化核心：Edge Function + Z-Buffer
# ============================================================

def edge_function(a, b, c):
    """Edge function：判断点 c 在边 ab 的哪一侧"""
    return (c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0])

def rasterize_triangle(v0, v1, v2, color, light_dir, normal,
                       framebuffer, zbuffer, width, height):
    """
    光栅化一个三角形
    v0, v1, v2: 屏幕空间坐标 (x, y, z_depth)
    color: RGB [0,1]
    """
    # Bounding box 优化
    min_x = max(0, int(min(v0[0], v1[0], v2[0])))
    max_x = min(width - 1, int(max(v0[0], v1[0], v2[0])) + 1)
    min_y = max(0, int(min(v0[1], v1[1], v2[1])))
    max_y = min(height - 1, int(max(v0[1], v1[1], v2[1])) + 1)

    area = edge_function(v0, v1, v2)
    if abs(area) < 1e-10:
        return  # 退化三角形

    # Lambert 着色
    n = normalize(normal)
    intensity = max(0.15, np.dot(n, -light_dir))  # ambient = 0.15

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            p = [x + 0.5, y + 0.5]

            w0 = edge_function(v1, v2, p)
            w1 = edge_function(v2, v0, p)
            w2 = edge_function(v0, v1, p)

            if (w0 >= 0 and w1 >= 0 and w2 >= 0) or \
               (w0 <= 0 and w1 <= 0 and w2 <= 0):
                # 重心坐标插值深度
                w0 /= area
                w1 /= area
                w2 /= area
                depth = w0 * v0[2] + w1 * v1[2] + w2 * v2[2]

                # Z-Buffer 测试
                if depth < zbuffer[y, x]:
                    zbuffer[y, x] = depth
                    r = int(min(255, color[0] * intensity * 255))
                    g = int(min(255, color[1] * intensity * 255))
                    b = int(min(255, color[2] * intensity * 255))
                    framebuffer[y, x] = [r, g, b]

# ============================================================
# 5. 可视化中间步骤
# ============================================================

def visualize_vertices_2d(vertices, width, height, filename, title=""):
    """将顶点投影到 2D 并画点"""
    img = Image.new('RGB', (width, height), (20, 20, 30))
    pixels = img.load()
    for v in vertices:
        x, y = int(v[0]), int(v[1])
        if 0 <= x < width and 0 <= y < height:
            # 画 3×3 的点
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        pixels[nx, ny] = (255, 200, 50)
    img.save(filename)
    print(f"  saved: {filename} ({title})")

def save_zbuffer_image(zbuffer, filename):
    """Z-Buffer 可视化为灰度图"""
    valid = zbuffer[zbuffer < 1e9]
    if len(valid) == 0:
        return
    zmin, zmax = valid.min(), valid.max()
    if zmax - zmin < 1e-10:
        zmax = zmin + 1
    normalized = np.clip((zbuffer - zmin) / (zmax - zmin), 0, 1)
    normalized[zbuffer >= 1e9] = 1.0  # 背景白色
    gray = (normalized * 255).astype(np.uint8)
    img = Image.fromarray(gray, mode='L')
    img.save(filename)
    print(f"  saved: {filename} (Z-Buffer depth map)")

# ============================================================
# 6. 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="E1: Software Rasterizer")
    parser.add_argument("--width", type=int, default=640, help="Image width")
    parser.add_argument("--height", type=int, default=480, help="Image height")
    parser.add_argument("--output-dir", type=str, default="results/e1_rasterizer")
    parser.add_argument("--rotate-y", type=float, default=35.0, help="Y-axis rotation (degrees)")
    parser.add_argument("--rotate-x", type=float, default=20.0, help="X-axis rotation (degrees)")
    args = parser.parse_args()

    W, H = args.width, args.height
    out = args.output_dir

    print("=" * 60)
    print("E1: Software Rasterizer — 3D→2D 渲染管线")
    print("=" * 60)

    # --- 场景 ---
    cube_v, cube_t, cube_c = create_cube(1.0)
    ground_v, ground_t, ground_c = create_ground(3.0, -0.6)

    # 合并场景
    all_verts = np.vstack([cube_v, ground_v])
    all_tris = cube_t + [[i + len(cube_v) for i in t] for t in ground_t]
    all_colors = cube_c + ground_c

    print(f"  场景: {len(all_verts)} 顶点, {len(all_tris)} 三角形")

    # --- Step 1: Model Transform ---
    print("\n[Step 1] Model Transform (旋转 + 缩放)")
    t_start = time.time()
    model_mat = rotation_y_matrix(args.rotate_y) @ rotation_x_matrix(args.rotate_x)
    model_coords = apply_transform(all_verts, model_mat)
    t1 = time.time() - t_start
    print(f"  耗时: {t1*1000:.2f} ms")

    # --- Step 2: Camera Transform ---
    print("\n[Step 2] Camera Transform (LookAt)")
    t_start = time.time()
    eye = np.array([0.0, 1.0, 3.5])
    target = np.array([0.0, 0.0, 0.0])
    up = np.array([0.0, 1.0, 0.0])
    view_mat = look_at_matrix(eye, target, up)
    camera_coords = apply_transform(model_coords[:, :3], view_mat)
    t2 = time.time() - t_start
    print(f"  摄像机位置: eye={eye}, target={target}")
    print(f"  耗时: {t2*1000:.2f} ms")

    # --- Step 3: Perspective Projection ---
    print("\n[Step 3] Perspective Projection")
    t_start = time.time()
    fov = 60.0
    aspect = W / H
    near, far = 0.1, 100.0
    proj_mat = perspective_matrix(fov, aspect, near, far)
    clip_coords = (proj_mat @ camera_coords.T).T
    ndc_coords = perspective_divide(clip_coords)
    t3 = time.time() - t_start
    print(f"  FOV={fov}°, aspect={aspect:.2f}, near={near}, far={far}")
    print(f"  耗时: {t3*1000:.2f} ms")

    # --- Step 4: Viewport Transform ---
    print("\n[Step 4] Viewport Transform (NDC → pixels)")
    t_start = time.time()
    screen_coords = viewport_transform(ndc_coords, W, H)
    t4 = time.time() - t_start
    print(f"  屏幕尺寸: {W}×{H}")
    print(f"  耗时: {t4*1000:.2f} ms")

    # 保存中间步骤可视化
    visualize_vertices_2d(screen_coords, W, H,
                         f"{out}/step4_vertices_projected.png",
                         "投影后的顶点位置")

    # --- Step 5: Rasterization + Z-Buffer ---
    print("\n[Step 5] Rasterization (Edge Function + Z-Buffer + Lambert)")
    t_start = time.time()
    framebuffer = np.full((H, W, 3), [20, 20, 30], dtype=np.uint8)  # 深色背景
    zbuffer = np.full((H, W), 1e10, dtype=np.float64)

    light_dir = normalize(np.array([0.5, -0.8, -0.6]))  # 光照方向

    for i, (tri, color) in enumerate(zip(all_tris, all_colors)):
        v0 = screen_coords[tri[0]]
        v1 = screen_coords[tri[1]]
        v2 = screen_coords[tri[2]]

        # 计算世界空间法线（用于着色）
        world_v0 = model_coords[tri[0], :3]
        world_v1 = model_coords[tri[1], :3]
        world_v2 = model_coords[tri[2], :3]
        edge1 = world_v1 - world_v0
        edge2 = world_v2 - world_v0
        normal = np.cross(edge1, edge2)

        rasterize_triangle(v0, v1, v2, color, light_dir, normal,
                          framebuffer, zbuffer, W, H)

    t5 = time.time() - t_start
    print(f"  光栅化 {len(all_tris)} 三角形")
    print(f"  耗时: {t5*1000:.2f} ms")

    # --- 保存结果 ---
    final_img = Image.fromarray(framebuffer)
    final_img.save(f"{out}/e1_final_render.png")
    print(f"\n  ✅ 最终渲染: {out}/e1_final_render.png")

    save_zbuffer_image(zbuffer, f"{out}/e1_zbuffer.png")

    # --- 汇总 ---
    total_ms = (t1 + t2 + t3 + t4 + t5) * 1000
    results = {
        "experiment": "E1_software_rasterizer",
        "resolution": f"{W}x{H}",
        "vertices": len(all_verts),
        "triangles": len(all_tris),
        "timing_ms": {
            "model_transform": round(t1 * 1000, 2),
            "camera_transform": round(t2 * 1000, 2),
            "projection": round(t3 * 1000, 2),
            "viewport": round(t4 * 1000, 2),
            "rasterization": round(t5 * 1000, 2),
            "total": round(total_ms, 2),
        },
        "pipeline_steps": [
            "Model Transform (4x4 matrix: rotation + scale)",
            "Camera Transform (LookAt matrix)",
            "Perspective Projection (frustum → NDC)",
            "Viewport Transform (NDC → screen pixels)",
            "Rasterization (Edge Function + Z-Buffer + Lambert shading)"
        ]
    }

    with open(f"{out}/e1_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"总耗时: {total_ms:.2f} ms")
    print(f"  Step 1 Model Transform:    {t1*1000:8.2f} ms")
    print(f"  Step 2 Camera Transform:   {t2*1000:8.2f} ms")
    print(f"  Step 3 Projection:         {t3*1000:8.2f} ms")
    print(f"  Step 4 Viewport:           {t4*1000:8.2f} ms")
    print(f"  Step 5 Rasterization:      {t5*1000:8.2f} ms")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
