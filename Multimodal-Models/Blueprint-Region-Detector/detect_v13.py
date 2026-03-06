#!/usr/bin/env python3
"""
Blueprint Region Detector v13 — Cross-Style CLI
SAM 2.1 + Auto-Tuned Flood Fill + Image-Statistics-Guided Parameters

Usage:
  python detect_v13.py input.png -o output/ -m sam2.1_hiera_large.pt

Features:
    - Estimates blueprint style from image statistics (gray-fill / line-enclosed)
    - Applies style-guided parameter presets per image
  - SAM 2.1 for texture/structure detection
  - Auto-tuned Flood Fill for wall-enclosed room detection
  - Building outline filtering + aggressive NMS

Author: Xinyu Wei
"""
import argparse
import cv2
import numpy as np
import torch
import json
import time
import os


def parse_args():
    p = argparse.ArgumentParser(description="Blueprint Region Detector v13 (Cross-Style)")
    p.add_argument("input", help="Input image path (PNG/JPG)")
    p.add_argument("-o", "--output", default=".", help="Output directory")
    p.add_argument("-m", "--model", default="checkpoints/sam2.1_hiera_large.pt",
                   help="SAM 2.1 checkpoint path")
    p.add_argument("--config", default="configs/sam2.1/sam2.1_hiera_l.yaml",
                   help="SAM 2.1 config path")
    p.add_argument("--max-size", type=int, default=2000,
                   help="Max image dimension for processing")
    p.add_argument("--sam-points", type=int, default=64)
    p.add_argument("--show-style", action="store_true",
                   help="Print detailed style analysis")
    return p.parse_args()


# ============================================================
# Stage 0: Style Estimation (from image statistics)
# ============================================================
def detect_style(gray):
    """Analyze grayscale image to detect blueprint style."""
    h, w = gray.shape
    total = h * w

    dark = np.sum(gray < 50) / total
    mid_gray = np.sum((gray >= 80) & (gray <= 185)) / total
    white = np.sum(gray > 230) / total

    # Wall thickness from adaptive threshold
    adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 5)
    wall_pct = np.sum(adapt > 0) / total
    thickness = "thick" if wall_pct > 0.08 else ("medium" if wall_pct > 0.05 else "thin")

    if mid_gray > 0.05:
        style = "gray_fill"
    else:
        style = "line_enclosed"

    return {
        "style": style,
        "wall_thickness": thickness,
        "mid_gray_pct": round(mid_gray * 100, 1),
        "dark_pct": round(dark * 100, 1),
        "white_pct": round(white * 100, 1),
        "wall_pct": round(wall_pct * 100, 1),
    }


# ============================================================
# Stage 1: Parameter Selection
# ============================================================
def get_params(style_info):
    """Select detection parameters based on style."""
    style = style_info["style"]

    if style == "gray_fill":
        return {
            "sam_min_ratio": 0.0005,
            "sam_max_ratio": 0.15,
            "sam_max_aspect": 5.0,
            "sam_inside_thresh": 0.5,
            "flood_min_ratio": 0.003,
            "flood_max_ratio": 0.10,
            "flood_max_aspect": 4,
            "nms_iou": 0.30,
            "nms_contain": 0.55,
        }
    else:
        return {
            "sam_min_ratio": 0.001,
            "sam_max_ratio": 0.10,
            "sam_max_aspect": 4.0,
            "sam_inside_thresh": 0.7,
            "flood_min_ratio": 0.005,
            "flood_max_ratio": 0.10,
            "flood_max_aspect": 4,
            "nms_iou": 0.25,
            "nms_contain": 0.50,
        }


# ============================================================
# Stage 2: Building Outline Detection
# ============================================================
def find_building_outline(gray):
    """Find the largest dark-bordered region = building footprint."""
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    k_size = max(7, min(h, w) // 200)
    kernel = np.ones((k_size, k_size), np.uint8)
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=3)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bcnt = max(contours, key=cv2.contourArea)
    bmask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(bmask, [bcnt], -1, 255, -1)
    bbox = cv2.boundingRect(bcnt)
    return bmask, bbox


# ============================================================
# Stage 3a: SAM 2.1 Detection
# ============================================================
def sam_detect(img_r, gray, bmask, img_area, mask_generator, params):
    """Run SAM 2.1 and filter segments."""
    rh, rw = gray.shape
    rgb = cv2.cvtColor(img_r, cv2.COLOR_BGR2RGB)

    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        masks = mask_generator.generate(rgb)

    p = params
    rooms = []
    for m in masks:
        a = m["area"]
        r = a / img_area
        bbox = m["bbox"]
        x, y, bw, bh = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
        asp = max(bw, bh) / (min(bw, bh) + 1)
        seg = m["segmentation"]
        cx, cy = x + bw // 2, y + bh // 2

        if r > p["sam_max_ratio"] or r < p["sam_min_ratio"] or asp >= p["sam_max_aspect"]:
            continue
        if bmask[min(cy, rh - 1), min(cx, rw - 1)] == 0:
            continue
        if np.sum((seg > 0) & (bmask > 0)) / max(np.sum(seg > 0), 1) < p["sam_inside_thresh"]:
            continue
        rooms.append((x, y, bw, bh, a))

    return rooms, len(masks)


# ============================================================
# Stage 3b: Auto-Tuned Flood Fill
# ============================================================
def flood_fill_detect(gray, bmask, img_area, params):
    """Try multiple morphology parameter combos, pick best."""
    best = []
    best_score = -1
    p = params

    for dk in [3, 5, 7]:
        for di in [1, 2, 3]:
            for ci in [2, 3, 4, 5]:
                adapt = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 25, 5)
                walls = cv2.dilate(adapt, np.ones((dk, dk), np.uint8), iterations=di)
                walls = cv2.morphologyEx(walls, cv2.MORPH_CLOSE,
                                          np.ones((3, 3), np.uint8), iterations=ci)
                rm = cv2.bitwise_and(cv2.bitwise_not(walls), bmask)
                rm = cv2.erode(rm, np.ones((3, 3), np.uint8), iterations=1)

                nl, _, stats, _ = cv2.connectedComponentsWithStats(rm, connectivity=4)
                rooms = []
                for i in range(1, nl):
                    a = stats[i, cv2.CC_STAT_AREA]
                    r = a / img_area
                    if r < p["flood_min_ratio"] or r > p["flood_max_ratio"]:
                        continue
                    bx = int(stats[i, 0])
                    by = int(stats[i, 1])
                    bw = int(stats[i, 2])
                    bh = int(stats[i, 3])
                    asp = max(bw, bh) / (min(bw, bh) + 1)
                    if asp >= p["flood_max_aspect"]:
                        continue
                    rooms.append((bx, by, bw, bh, a))

                n = len(rooms)
                score = n if 8 <= n <= 25 else max(0, n - abs(n - 15) * 2)
                if score > best_score:
                    best_score = score
                    best = rooms

    return best


# ============================================================
# Stage 4: Merge + NMS
# ============================================================
def merge_and_nms(sam_rooms, flood_rooms, params, building_bbox):
    """Merge SAM + Flood Fill, NMS, boundary filter."""
    p = params
    bx0, by0, bbw, bbh = building_bbox

    all_rooms = sam_rooms + flood_rooms
    all_rooms.sort(key=lambda e: e[4], reverse=True)

    keep = []
    for e in all_rooms:
        dup = False
        for k in keep:
            ix1, iy1 = max(e[0], k[0]), max(e[1], k[1])
            ix2, iy2 = min(e[0] + e[2], k[0] + k[2]), min(e[1] + e[3], k[1] + k[3])
            if ix2 > ix1 and iy2 > iy1:
                inter = (ix2 - ix1) * (iy2 - iy1)
                union = e[2] * e[3] + k[2] * k[3] - inter
                iou = inter / union if union > 0 else 0
                smaller = min(e[2] * e[3], k[2] * k[3])
                contain = inter / smaller if smaller > 0 else 0
                if iou > p["nms_iou"] or contain > p["nms_contain"]:
                    dup = True
                    break
        if not dup:
            keep.append(e)

    # Boundary filter
    margin = 20
    final = []
    for x, y, bw, bh, a in keep:
        cx, cy = x + bw // 2, y + bh // 2
        if bx0 - margin <= cx <= bx0 + bbw + margin and by0 - margin <= cy <= by0 + bbh + margin:
            final.append((x, y, bw, bh, a))

    return final


# ============================================================
# Drawing + Output
# ============================================================
def draw_results(img, entities):
    result = img.copy()
    for e in entities:
        cv2.rectangle(result, (e["x"], e["y"]),
                       (e["x"] + e["w"], e["y"] + e["h"]), (0, 255, 0), 2)
        cv2.circle(result, (e["cx"], e["cy"]), 5, (0, 0, 255), -1)
    return result


# ============================================================
# Main
# ============================================================
def main():
    args = parse_args()

    # Load image
    img = cv2.imread(args.input)
    if img is None:
        raise FileNotFoundError(f"Cannot read: {args.input}")
    h, w = img.shape[:2]
    scale = min(args.max_size / max(h, w), 1.0)
    img_r = cv2.resize(img, (int(w * scale), int(h * scale))) if scale < 1 else img
    rh, rw = img_r.shape[:2]
    img_area = rh * rw
    gray = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"

    print(f"🚀 Blueprint Region Detector v13")
    print(f"   Device: {device} ({gpu_name})")
    print(f"   Input: {args.input}")
    print(f"   Size: {w}x{h} -> {rw}x{rh} (scale={scale:.2f})")

    t0 = time.time()

    # Stage 0: Style estimation
    style = detect_style(gray)
    print(f"   Style: {style['style']} (gray={style['mid_gray_pct']}%, walls={style['wall_pct']}%)")
    if args.show_style:
        print(f"   Detail: {json.dumps(style, indent=2)}")

    # Stage 1: Parameters
    params = get_params(style)

    # Stage 2: Building outline
    bmask, building_bbox = find_building_outline(gray)

    # Stage 3a: SAM 2.1
    print(f"   [SAM 2.1] Segmenting...")
    from sam2.build_sam import build_sam2
    from sam2.automatic_mask_generator import SAM2AutomaticMaskGenerator

    sam2 = build_sam2(args.config, args.model, device=device, apply_postprocessing=False)
    mg = SAM2AutomaticMaskGenerator(
        sam2,
        points_per_side=args.sam_points,
        points_per_batch=32,
        pred_iou_thresh=0.70,
        stability_score_thresh=0.85,
        crop_n_layers=1,
        crop_n_points_downscale_factor=2,
        min_mask_region_area=80,
    )
    sam_rooms, total_masks = sam_detect(img_r, gray, bmask, img_area, mg, params)
    print(f"   [SAM 2.1] {total_masks} masks -> {len(sam_rooms)} entities")

    # Stage 3b: Flood Fill
    print(f"   [Flood Fill] Auto-tuning...")
    flood_rooms = flood_fill_detect(gray, bmask, img_area, params)
    print(f"   [Flood Fill] {len(flood_rooms)} entities")

    # Stage 4: Merge + NMS
    final_tuples = merge_and_nms(sam_rooms, flood_rooms, params, building_bbox)

    # Scale back to original coords
    entities = []
    for x, y, bw, bh, a in final_tuples:
        entities.append({
            "x": int(x / scale), "y": int(y / scale),
            "w": int(bw / scale), "h": int(bh / scale),
            "cx": int((x + bw // 2) / scale),
            "cy": int((y + bh // 2) / scale),
            "area": int(a / scale ** 2),
        })

    elapsed = time.time() - t0
    print(f"\n📊 Total: {len(entities)} entities (SAM:{len(sam_rooms)} + Flood:{len(flood_rooms)}) in {elapsed:.1f}s")

    # Save
    os.makedirs(args.output, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.input))[0]
    out_img = os.path.join(args.output, f"{base}_v13.png")
    out_json = os.path.join(args.output, f"{base}_v13.json")

    result = draw_results(img, entities)
    cv2.imwrite(out_img, result)
    print(f"   ✅ Saved: {out_img}")

    with open(out_json, "w") as f:
        json.dump({"style": style, "entities": entities, "stats": {
            "total": len(entities), "sam": len(sam_rooms),
            "flood": len(flood_rooms), "time_sec": round(elapsed, 1)
        }}, f, indent=2)
    print(f"   ✅ Saved: {out_json}")


if __name__ == "__main__":
    main()
