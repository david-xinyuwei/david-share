#!/usr/bin/env python3
"""
E4: Blender EEVEE vs Cycles — 光栅化 vs 光追 GPU 渲染对比
Author: 魏新宇 (Xinyu Wei)

验证内容：
  - 同一场景两种引擎渲染
  - EEVEE (光栅化) vs Cycles (Path Tracing) 的质量/速度差异
  - GPU 加速渲染

用法：在 A10 VM 上执行
  blender -b -P scripts/e4_blender_benchmark.py
"""

import bpy
import math
import time
import json
import os
import sys

# ============================================================
# 配置
# ============================================================
OUTPUT_DIR = "/root/rendering-experiments/results/e4_blender"
WIDTH = 1920
HEIGHT = 1080
CYCLES_SAMPLES = 256
EEVEE_SAMPLES = 64

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 1. 清空默认场景
# ============================================================
bpy.ops.wm.read_factory_settings(use_empty=True)

# ============================================================
# 2. 创建场景：球体（镜面/玻璃/漫反射）+ 地面 + 光源
# ============================================================

# --- 地面 ---
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = "Ground"
mat_ground = bpy.data.materials.new("GroundMat")
mat_ground.use_nodes = True
bsdf = mat_ground.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1.0)
bsdf.inputs["Roughness"].default_value = 0.8
ground.data.materials.append(mat_ground)

# --- 镜面球 ---
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(0, 0, 0.8))
sphere_mirror = bpy.context.active_object
sphere_mirror.name = "MirrorSphere"
mat_mirror = bpy.data.materials.new("MirrorMat")
mat_mirror.use_nodes = True
bsdf = mat_mirror.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.05
sphere_mirror.data.materials.append(mat_mirror)

# --- 红色漫反射球 ---
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(-1.5, -0.5, 0.5))
sphere_red = bpy.context.active_object
sphere_red.name = "RedSphere"
mat_red = bpy.data.materials.new("RedMat")
mat_red.use_nodes = True
bsdf = mat_red.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.9, 0.15, 0.15, 1.0)
bsdf.inputs["Roughness"].default_value = 0.4
sphere_red.data.materials.append(mat_red)

# --- 绿色球 ---
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(1.3, 0.8, 0.6))
sphere_green = bpy.context.active_object
sphere_green.name = "GreenSphere"
mat_green = bpy.data.materials.new("GreenMat")
mat_green.use_nodes = True
bsdf = mat_green.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.15, 0.8, 0.25, 1.0)
bsdf.inputs["Roughness"].default_value = 0.3
sphere_green.data.materials.append(mat_green)

# --- 玻璃球 ---
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.45, location=(0.8, -1.2, 0.45))
sphere_glass = bpy.context.active_object
sphere_glass.name = "GlassSphere"
mat_glass = bpy.data.materials.new("GlassMat")
mat_glass.use_nodes = True
bsdf = mat_glass.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 1.0, 1.0)
bsdf.inputs["Transmission"].default_value = 0.95
bsdf.inputs["Roughness"].default_value = 0.0
bsdf.inputs["IOR"].default_value = 1.45
sphere_glass.data.materials.append(mat_glass)

# --- 光源 ---
# 主光源（Area Light）
bpy.ops.object.light_add(type='AREA', location=(3, -2, 4))
key_light = bpy.context.active_object
key_light.name = "KeyLight"
key_light.data.energy = 200
key_light.data.size = 2.0

# 补光
bpy.ops.object.light_add(type='AREA', location=(-3, 2, 3))
fill_light = bpy.context.active_object
fill_light.name = "FillLight"
fill_light.data.energy = 80
fill_light.data.size = 3.0

# --- 摄像机 ---
bpy.ops.object.camera_add(location=(4, -4, 3))
camera = bpy.context.active_object
camera.name = "Camera"
camera.rotation_euler = (math.radians(60), 0, math.radians(45))
bpy.context.scene.camera = camera

# 设置分辨率
bpy.context.scene.render.resolution_x = WIDTH
bpy.context.scene.render.resolution_y = HEIGHT
bpy.context.scene.render.resolution_percentage = 100

print(f"场景创建完成: 5 物体 + 2 光源 + 1 摄像机")
print(f"分辨率: {WIDTH}x{HEIGHT}")

# ============================================================
# 3. EEVEE 渲染（光栅化引擎）
# ============================================================
print("\n" + "=" * 60)
print("渲染 1: EEVEE (光栅化)")
print("=" * 60)

bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.eevee.taa_render_samples = EEVEE_SAMPLES
bpy.context.scene.render.filepath = os.path.join(OUTPUT_DIR, "e4_eevee_render.png")
bpy.context.scene.render.image_settings.file_format = 'PNG'

t_start = time.time()
bpy.ops.render.render(write_still=True)
eevee_time = time.time() - t_start

print(f"  EEVEE 渲染完成: {eevee_time:.2f} 秒")
print(f"  输出: {bpy.context.scene.render.filepath}")

# ============================================================
# 4. Cycles 渲染（Path Tracing 引擎）
# ============================================================
print("\n" + "=" * 60)
print("渲染 2: Cycles (Path Tracing)")
print("=" * 60)

bpy.context.scene.render.engine = 'CYCLES'

# 尝试 GPU 渲染
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'CUDA'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = True
        print(f"  GPU 设备: {device.name} (type={device.type})")
    bpy.context.scene.cycles.device = 'GPU'
    print("  ✅ 使用 GPU 渲染")
except Exception as e:
    print(f"  ⚠️ GPU 不可用，回退 CPU: {e}")
    bpy.context.scene.cycles.device = 'CPU'

bpy.context.scene.cycles.samples = CYCLES_SAMPLES
bpy.context.scene.render.filepath = os.path.join(OUTPUT_DIR, "e4_cycles_render.png")

t_start = time.time()
bpy.ops.render.render(write_still=True)
cycles_time = time.time() - t_start

print(f"  Cycles 渲染完成: {cycles_time:.2f} 秒")
print(f"  输出: {bpy.context.scene.render.filepath}")

# ============================================================
# 5. 汇总
# ============================================================
results = {
    "experiment": "E4_blender_eevee_vs_cycles",
    "resolution": f"{WIDTH}x{HEIGHT}",
    "scene": "5 objects (mirror sphere, red sphere, green sphere, glass sphere, ground) + 2 area lights",
    "eevee": {
        "engine": "EEVEE (rasterization)",
        "samples": EEVEE_SAMPLES,
        "render_time_seconds": round(eevee_time, 2),
    },
    "cycles": {
        "engine": "Cycles (path tracing)",
        "samples": CYCLES_SAMPLES,
        "render_time_seconds": round(cycles_time, 2),
        "device": bpy.context.scene.cycles.device,
    },
    "speedup": round(cycles_time / eevee_time, 2) if eevee_time > 0 else 0,
    "key_differences": [
        "EEVEE: screen-space reflections (approximate)",
        "Cycles: physically-correct reflections (ray traced)",
        "EEVEE: no caustics, no true glass refraction",
        "Cycles: caustics, glass refraction, global illumination",
    ]
}

with open(os.path.join(OUTPUT_DIR, "e4_results.json"), 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}")
print(f"对比结果:")
print(f"  EEVEE (光栅化):   {eevee_time:8.2f} 秒 ({EEVEE_SAMPLES} samples)")
print(f"  Cycles (光追):    {cycles_time:8.2f} 秒 ({CYCLES_SAMPLES} samples)")
print(f"  速度比:           EEVEE {results['speedup']}x faster")
print(f"{'='*60}")
