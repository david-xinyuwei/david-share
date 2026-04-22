#!/usr/bin/env python3
"""
E3: Rasterization vs Ray Tracing — 像素级对比
Author: 魏新宇 (Xinyu Wei)

验证内容：
  - 同一场景：E1 光栅化 vs E2 光追的像素级差异
  - 量化指标：MSE, SSIM, histogram 分布
  - 生成差异热力图

输入：E1 和 E2 的渲染结果（必须同分辨率）
输出：差异图 + 指标 JSON
"""

import argparse
import json
import numpy as np
from PIL import Image

def compute_mse(img1, img2):
    """均方误差"""
    return np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)

def compute_ssim(img1, img2, window_size=7):
    """
    简化版 SSIM（不依赖 skimage）
    来源：Wang et al., "Image Quality Assessment", IEEE TIP 2004
    """
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)

    # 逐通道计算
    ssim_channels = []
    for c in range(img1.shape[2]):
        ch1 = img1[:, :, c]
        ch2 = img2[:, :, c]

        mu1 = np.mean(ch1)
        mu2 = np.mean(ch2)
        sigma1_sq = np.var(ch1)
        sigma2_sq = np.var(ch2)
        sigma12 = np.mean((ch1 - mu1) * (ch2 - mu2))

        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1 ** 2 + mu2 ** 2 + C1) * (sigma1_sq + sigma2_sq + C2)

        ssim_channels.append(numerator / denominator)

    return np.mean(ssim_channels)

def generate_diff_heatmap(img1, img2, output_path):
    """生成差异热力图"""
    diff = np.abs(img1.astype(np.float64) - img2.astype(np.float64))
    diff_gray = np.mean(diff, axis=2)

    # 归一化到 0-255
    if diff_gray.max() > 0:
        diff_normalized = (diff_gray / diff_gray.max() * 255).astype(np.uint8)
    else:
        diff_normalized = np.zeros_like(diff_gray, dtype=np.uint8)

    # 伪彩色热力图（冷色=相似，暖色=差异大）
    h, w = diff_normalized.shape
    heatmap = np.zeros((h, w, 3), dtype=np.uint8)

    for y in range(h):
        for x in range(w):
            v = diff_normalized[y, x] / 255.0
            if v < 0.25:
                heatmap[y, x] = [0, int(v * 4 * 255), 255]  # 蓝→青
            elif v < 0.5:
                heatmap[y, x] = [0, 255, int((0.5 - v) * 4 * 255)]  # 青→绿
            elif v < 0.75:
                heatmap[y, x] = [int((v - 0.5) * 4 * 255), 255, 0]  # 绿→黄
            else:
                heatmap[y, x] = [255, int((1.0 - v) * 4 * 255), 0]  # 黄→红

    Image.fromarray(heatmap).save(output_path)
    print(f"  saved: {output_path}")
    return diff_gray

def generate_side_by_side(img1, img2, diff_heatmap, labels, output_path):
    """生成三图并排对比"""
    h, w = img1.shape[:2]
    gap = 10
    canvas_w = w * 3 + gap * 2
    canvas_h = h + 40  # 底部留空间写标签

    canvas = np.full((canvas_h, canvas_w, 3), 30, dtype=np.uint8)  # 深色背景

    canvas[0:h, 0:w] = img1
    canvas[0:h, w + gap:2 * w + gap] = img2
    canvas[0:h, 2 * w + 2 * gap:3 * w + 2 * gap] = diff_heatmap

    Image.fromarray(canvas).save(output_path)
    print(f"  saved: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="E3: Rasterization vs Ray Tracing Comparison")
    parser.add_argument("--img1", required=True, help="E1 rasterizer output")
    parser.add_argument("--img2", required=True, help="E2 ray tracer output")
    parser.add_argument("--output-dir", default="results/e3_comparison")
    parser.add_argument("--label1", default="Rasterization (E1)")
    parser.add_argument("--label2", default="Ray Tracing (E2)")
    args = parser.parse_args()

    import os
    os.makedirs(args.output_dir, exist_ok=True)

    print("=" * 60)
    print("E3: Rasterization vs Ray Tracing — 像素级对比")
    print("=" * 60)

    # 加载图片
    img1 = np.array(Image.open(args.img1).convert('RGB'))
    img2 = np.array(Image.open(args.img2).convert('RGB'))

    print(f"  {args.label1}: {img1.shape}")
    print(f"  {args.label2}: {img2.shape}")

    # 尺寸检查
    if img1.shape != img2.shape:
        print(f"  ⚠️ 尺寸不匹配！ resize img2 to match img1")
        img2_pil = Image.fromarray(img2).resize((img1.shape[1], img1.shape[0]), Image.LANCZOS)
        img2 = np.array(img2_pil)
        print(f"  resized {args.label2}: {img2.shape}")

    # 计算指标
    mse = compute_mse(img1, img2)
    ssim = compute_ssim(img1, img2)

    print(f"\n  MSE:  {mse:.2f} (lower = more similar, 0 = identical)")
    print(f"  SSIM: {ssim:.4f} (higher = more similar, 1.0 = identical)")

    # 差异热力图
    print(f"\n  生成差异热力图...")
    diff_gray = generate_diff_heatmap(img1, img2, f"{args.output_dir}/e3_diff_heatmap.png")

    # 加载热力图用于并排
    heatmap = np.array(Image.open(f"{args.output_dir}/e3_diff_heatmap.png"))

    # 三图并排
    generate_side_by_side(img1, img2, heatmap,
                         [args.label1, args.label2, "Difference"],
                         f"{args.output_dir}/e3_comparison.png")

    # 差异统计
    total_pixels = img1.shape[0] * img1.shape[1]
    identical = np.sum(np.all(img1 == img2, axis=2))
    near_identical = np.sum(diff_gray < 5)   # 差异 < 5
    moderate = np.sum((diff_gray >= 5) & (diff_gray < 30))
    large = np.sum(diff_gray >= 30)

    print(f"\n  像素差异分布:")
    print(f"    完全相同:     {identical:,} ({100*identical/total_pixels:.1f}%)")
    print(f"    近似相同(<5): {near_identical:,} ({100*near_identical/total_pixels:.1f}%)")
    print(f"    中等差异:     {moderate:,} ({100*moderate/total_pixels:.1f}%)")
    print(f"    大差异(>30):  {large:,} ({100*large/total_pixels:.1f}%)")

    # 保存结果
    results = {
        "experiment": "E3_rasterization_vs_raytracing_comparison",
        "img1": args.img1,
        "img2": args.img2,
        "resolution": f"{img1.shape[1]}x{img1.shape[0]}",
        "metrics": {
            "MSE": round(mse, 2),
            "SSIM": round(ssim, 4),
        },
        "pixel_distribution": {
            "identical": int(identical),
            "near_identical_lt5": int(near_identical),
            "moderate_5_30": int(moderate),
            "large_gt30": int(large),
            "total_pixels": int(total_pixels),
        },
        "interpretation": (
            "E1 (rasterization) and E2 (ray tracing) render the same scene. "
            "Differences come from: (1) lighting model - E2 has shadow rays and "
            "multi-light support, (2) shading interpolation - E1 uses flat triangle "
            "normals while E2 computes per-pixel normals, (3) anti-aliasing differences."
        )
    }

    with open(f"{args.output_dir}/e3_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"结论:")
    if ssim > 0.9:
        print(f"  SSIM={ssim:.4f} > 0.9: 两种方法渲染结果高度一致")
    elif ssim > 0.7:
        print(f"  SSIM={ssim:.4f}: 中等差异——光影效果不同但几何一致")
    else:
        print(f"  SSIM={ssim:.4f}: 较大差异——光追提供了光栅化无法模拟的效果")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
