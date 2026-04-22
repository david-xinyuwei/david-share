#!/usr/bin/env python3
"""
E2: Software Ray Tracer — 从零实现光线追踪渲染
Author: 魏新宇 (Xinyu Wei)

验证内容：
  - Ray-Sphere 求交（解二次方程）
  - Ray-Triangle 求交（Möller-Trumbore 算法）
  - 反射光线（递归追踪）
  - 阴影光线
  - 同一场景与 E1 光栅化器对比

输出：渲染图（含反射+阴影）+ 无反射版本（用于对比 E1）
"""

import argparse
import json
import math
import time
import numpy as np
from PIL import Image

# ============================================================
# 1. 数学工具
# ============================================================

def normalize(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v

def reflect(incident, normal):
    """反射方向"""
    return incident - 2 * np.dot(incident, normal) * normal

# ============================================================
# 2. 场景对象
# ============================================================

class Sphere:
    def __init__(self, center, radius, color, reflectivity=0.0):
        self.center = np.array(center, dtype=np.float64)
        self.radius = radius
        self.color = np.array(color, dtype=np.float64)
        self.reflectivity = reflectivity

    def intersect(self, ray_origin, ray_dir):
        """
        Ray-Sphere 求交 — 解二次方程
        来源：Wikipedia Ray tracing (graphics) #Example
        ||origin + t*dir - center||² = r²
        → t² + 2(v·d)t + (v²-r²) = 0
        """
        v = ray_origin - self.center
        a = np.dot(ray_dir, ray_dir)
        b = 2.0 * np.dot(v, ray_dir)
        c = np.dot(v, v) - self.radius ** 2
        discriminant = b * b - 4 * a * c

        if discriminant < 0:
            return None

        sqrt_disc = math.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)

        if t1 > 0.001:
            return t1
        if t2 > 0.001:
            return t2
        return None

    def normal_at(self, point):
        return normalize(point - self.center)


class Triangle:
    def __init__(self, v0, v1, v2, color, reflectivity=0.0):
        self.v0 = np.array(v0, dtype=np.float64)
        self.v1 = np.array(v1, dtype=np.float64)
        self.v2 = np.array(v2, dtype=np.float64)
        self.color = np.array(color, dtype=np.float64)
        self.reflectivity = reflectivity
        edge1 = self.v1 - self.v0
        edge2 = self.v2 - self.v0
        self.face_normal = normalize(np.cross(edge1, edge2))

    def intersect(self, ray_origin, ray_dir):
        """
        Möller-Trumbore Ray-Triangle 求交算法
        来源：Möller & Trumbore, 1997
        """
        EPSILON = 1e-8
        edge1 = self.v1 - self.v0
        edge2 = self.v2 - self.v0
        h = np.cross(ray_dir, edge2)
        a = np.dot(edge1, h)

        if -EPSILON < a < EPSILON:
            return None  # 光线平行于三角形

        f = 1.0 / a
        s = ray_origin - self.v0
        u = f * np.dot(s, h)

        if u < 0.0 or u > 1.0:
            return None

        q = np.cross(s, edge1)
        v = f * np.dot(ray_dir, q)

        if v < 0.0 or u + v > 1.0:
            return None

        t = f * np.dot(edge2, q)

        if t > EPSILON:
            return t
        return None

    def normal_at(self, point):
        return self.face_normal


class Plane:
    """无限平面（用于地面）"""
    def __init__(self, point, normal, color, reflectivity=0.0):
        self.point = np.array(point, dtype=np.float64)
        self.normal_vec = normalize(np.array(normal, dtype=np.float64))
        self.color = np.array(color, dtype=np.float64)
        self.reflectivity = reflectivity

    def intersect(self, ray_origin, ray_dir):
        denom = np.dot(self.normal_vec, ray_dir)
        if abs(denom) < 1e-8:
            return None
        t = np.dot(self.point - ray_origin, self.normal_vec) / denom
        if t > 0.001:
            return t
        return None

    def normal_at(self, point):
        return self.normal_vec


# ============================================================
# 3. 创建与 E1 相同的场景
# ============================================================

def create_scene_matching_e1():
    """创建和 E1 光栅化器相同的场景（立方体 + 地面）"""
    objects = []

    # 立方体（用三角形构成）
    s = 0.5
    rot_y = 35.0
    rot_x = 20.0
    a_y = math.radians(rot_y)
    a_x = math.radians(rot_x)

    # 旋转矩阵
    def rotate(v):
        # Y rotation
        x1 = v[0] * math.cos(a_y) + v[2] * math.sin(a_y)
        y1 = v[1]
        z1 = -v[0] * math.sin(a_y) + v[2] * math.cos(a_y)
        # X rotation
        x2 = x1
        y2 = y1 * math.cos(a_x) - z1 * math.sin(a_x)
        z2 = y1 * math.sin(a_x) + z1 * math.cos(a_x)
        return np.array([x2, y2, z2])

    verts = [
        rotate(np.array([-s, -s, -s])), rotate(np.array([s, -s, -s])),
        rotate(np.array([s, s, -s])),   rotate(np.array([-s, s, -s])),
        rotate(np.array([-s, -s, s])),  rotate(np.array([s, -s, s])),
        rotate(np.array([s, s, s])),    rotate(np.array([-s, s, s])),
    ]

    faces = [
        (4,5,6, [0.2,0.4,0.9]), (4,6,7, [0.2,0.4,0.9]),  # front
        (1,0,3, [0.9,0.2,0.2]), (1,3,2, [0.9,0.2,0.2]),  # back
        (5,1,2, [0.2,0.8,0.3]), (5,2,6, [0.2,0.8,0.3]),  # right
        (0,4,7, [0.9,0.9,0.2]), (0,7,3, [0.9,0.9,0.2]),  # left
        (3,7,6, [0.7,0.3,0.8]), (3,6,2, [0.7,0.3,0.8]),  # top
        (0,1,5, [0.2,0.8,0.8]), (0,5,4, [0.2,0.8,0.8]),  # bottom
    ]

    for i0, i1, i2, col in faces:
        objects.append(Triangle(verts[i0], verts[i1], verts[i2], col))

    # 地面
    objects.append(Plane([0, -0.6, 0], [0, 1, 0], [0.6, 0.6, 0.6], reflectivity=0.2))

    return objects

def create_scene_showcase():
    """展示光追优势的场景：球体 + 反射 + 阴影"""
    objects = []

    # 镜面球
    objects.append(Sphere([0.0, 0.0, -1.5], 0.5, [0.9, 0.9, 0.9], reflectivity=0.8))
    # 红球
    objects.append(Sphere([-1.2, -0.2, -1.0], 0.4, [0.9, 0.2, 0.2], reflectivity=0.1))
    # 绿球
    objects.append(Sphere([1.0, -0.3, -0.8], 0.3, [0.2, 0.8, 0.3], reflectivity=0.1))
    # 蓝球（后方）
    objects.append(Sphere([0.3, 0.3, -3.0], 0.6, [0.2, 0.4, 0.9], reflectivity=0.3))

    # 地面
    objects.append(Plane([0, -0.6, 0], [0, 1, 0], [0.7, 0.7, 0.7], reflectivity=0.15))

    return objects

# ============================================================
# 4. 光线追踪核心
# ============================================================

def trace_ray(ray_origin, ray_dir, objects, lights, depth=0, max_depth=3):
    """
    递归光线追踪
    - 找最近交点
    - Lambert 漫反射 + Phong 高光
    - 阴影光线
    - 反射光线（递归）
    """
    if depth > max_depth:
        return np.array([0.05, 0.05, 0.08])  # 背景色

    # 找最近交点
    closest_t = float('inf')
    closest_obj = None

    for obj in objects:
        t = obj.intersect(ray_origin, ray_dir)
        if t is not None and t < closest_t:
            closest_t = t
            closest_obj = obj

    if closest_obj is None:
        return np.array([0.05, 0.05, 0.08])  # 背景

    # 交点和法线
    hit_point = ray_origin + closest_t * ray_dir
    normal = closest_obj.normal_at(hit_point)

    # 确保法线朝向光线
    if np.dot(normal, ray_dir) > 0:
        normal = -normal

    color = np.zeros(3)

    for light_pos, light_color, light_intensity in lights:
        # 光照方向
        to_light = light_pos - hit_point
        light_dist = np.linalg.norm(to_light)
        light_dir = to_light / light_dist

        # 阴影光线：检查是否被遮挡
        shadow_origin = hit_point + normal * 0.001
        in_shadow = False
        for obj in objects:
            t = obj.intersect(shadow_origin, light_dir)
            if t is not None and t < light_dist:
                in_shadow = True
                break

        if not in_shadow:
            # Lambert 漫反射
            diffuse = max(0, np.dot(normal, light_dir))
            color += closest_obj.color * light_color * diffuse * light_intensity

            # Phong 高光
            half_vec = normalize(light_dir - ray_dir)
            specular = max(0, np.dot(normal, half_vec)) ** 32
            color += light_color * specular * 0.3 * light_intensity

    # 环境光
    color += closest_obj.color * 0.1

    # 反射
    if closest_obj.reflectivity > 0 and depth < max_depth:
        reflect_dir = reflect(ray_dir, normal)
        reflect_origin = hit_point + normal * 0.001
        reflect_color = trace_ray(reflect_origin, reflect_dir, objects, lights,
                                  depth + 1, max_depth)
        color = color * (1 - closest_obj.reflectivity) + \
                reflect_color * closest_obj.reflectivity

    return np.clip(color, 0, 1)

# ============================================================
# 5. 渲染
# ============================================================

def render(width, height, objects, lights, fov=60.0, max_depth=3):
    """逐像素光线追踪渲染"""
    aspect = width / height
    fov_rad = math.radians(fov)
    tan_half = math.tan(fov_rad / 2)

    eye = np.array([0.0, 1.0, 3.5])
    framebuffer = np.zeros((height, width, 3), dtype=np.float64)

    for y in range(height):
        for x in range(width):
            # 像素 → NDC → 光线方向
            ndc_x = (2.0 * (x + 0.5) / width - 1.0) * aspect * tan_half
            ndc_y = (1.0 - 2.0 * (y + 0.5) / height) * tan_half
            ray_dir = normalize(np.array([ndc_x, ndc_y, -1.0]))

            framebuffer[y, x] = trace_ray(eye, ray_dir, objects, lights,
                                          max_depth=max_depth)

        if y % 50 == 0:
            print(f"    渲染进度: {y}/{height} ({100*y/height:.0f}%)")

    return framebuffer

# ============================================================
# 6. 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="E2: Software Ray Tracer")
    parser.add_argument("--width", type=int, default=640, help="Image width")
    parser.add_argument("--height", type=int, default=480, help="Image height")
    parser.add_argument("--output-dir", type=str, default="results/e2_raytracer")
    parser.add_argument("--scene", choices=["match_e1", "showcase"], default="showcase",
                        help="Scene: match_e1 (same as E1) or showcase (reflections+shadows)")
    parser.add_argument("--max-depth", type=int, default=3, help="Max reflection bounces")
    args = parser.parse_args()

    W, H = args.width, args.height
    out = args.output_dir

    print("=" * 60)
    print("E2: Software Ray Tracer — 光线追踪渲染")
    print("=" * 60)

    # 光源
    lights = [
        (np.array([2.0, 3.0, 2.0]),  np.array([1.0, 1.0, 1.0]),  0.8),  # 主光源
        (np.array([-2.0, 2.0, 3.0]), np.array([0.6, 0.6, 0.8]),  0.4),  # 补光
    ]

    # --- 场景 1: 展示场景（反射 + 阴影）---
    if args.scene == "showcase":
        print("\n[Scene: Showcase] 球体 + 镜面反射 + 阴影")
        objects = create_scene_showcase()
        print(f"  对象数: {len(objects)}")

        t_start = time.time()
        fb = render(W, H, objects, lights, max_depth=args.max_depth)
        render_time = time.time() - t_start

        img = Image.fromarray((fb * 255).astype(np.uint8))
        img.save(f"{out}/e2_showcase_render.png")
        print(f"\n  ✅ 渲染完成: {out}/e2_showcase_render.png")
        print(f"  耗时: {render_time:.2f} 秒")
        print(f"  光线数: {W * H} primary + reflections (depth={args.max_depth})")

    # --- 场景 2: 匹配 E1 场景 ---
    if args.scene == "match_e1":
        print("\n[Scene: match_e1] 与 E1 相同的立方体+地面")
        objects = create_scene_matching_e1()

        # 无反射版本（公平对比 E1）
        for obj in objects:
            obj.reflectivity = 0.0

        t_start = time.time()
        fb = render(W, H, objects, lights, max_depth=0)
        render_time = time.time() - t_start

        img = Image.fromarray((fb * 255).astype(np.uint8))
        img.save(f"{out}/e2_match_e1_render.png")
        print(f"\n  ✅ 渲染完成: {out}/e2_match_e1_render.png")
        print(f"  耗时: {render_time:.2f} 秒 (无反射, depth=0)")

    # --- 汇总 ---
    results = {
        "experiment": "E2_software_ray_tracer",
        "resolution": f"{W}x{H}",
        "scene": args.scene,
        "max_depth": args.max_depth,
        "render_time_seconds": round(render_time, 2),
        "primary_rays": W * H,
        "algorithm_components": [
            "Ray-Sphere intersection (quadratic equation)",
            "Ray-Triangle intersection (Moller-Trumbore)",
            "Shadow rays (occlusion test)",
            "Reflection rays (recursive, up to max_depth bounces)",
            "Lambert diffuse + Phong specular shading"
        ]
    }

    with open(f"{out}/e2_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"渲染统计:")
    print(f"  分辨率:     {W}×{H}")
    print(f"  主光线数:   {W*H:,}")
    print(f"  最大反射:   {args.max_depth} 次")
    print(f"  渲染时间:   {render_time:.2f} 秒")
    print(f"  每像素耗时: {render_time/(W*H)*1e6:.1f} µs")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
