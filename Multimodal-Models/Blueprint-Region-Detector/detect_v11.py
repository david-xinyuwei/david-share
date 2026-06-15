#!/usr/bin/env python3
"""
Two-Stage Entity Detector v11
- Stricter filtering: aspect ratio check, solidity check
- Lighter morphological cleanup
- Better text rejection

Author: Xinyu Wei
"""
import argparse
import json
import time
import os
import cv2
import numpy as np
import torch
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator


def parse_args():
    p = argparse.ArgumentParser(description="Two-Stage Entity Detector v11")
    p.add_argument("input", help="Input image path")
    p.add_argument("-o", "--output", default=".", help="Output directory")
    p.add_argument("-m", "--model", default="sam_vit_b.pth", help="SAM model path")
    p.add_argument("--model-type", default="vit_b", choices=["vit_b", "vit_h", "vit_l"])
    p.add_argument("--max-size", type=int, default=4000)
    # SAM parameters
    p.add_argument("--sam-points", type=int, default=48)
    p.add_argument("--sam-iou", type=float, default=0.80)
    p.add_argument("--sam-stability", type=float, default=0.85)
    p.add_argument("--sam-crop-layers", type=int, default=1)
    # Stage 1 filtering
    p.add_argument("--s1-min-area", type=int, default=500)
    p.add_argument("--s1-max-area", type=int, default=50000)
    p.add_argument("--s1-min-rect", type=float, default=0.5)
    p.add_argument("--s1-max-gray", type=int, default=210)
    p.add_argument("--s1-min-dim", type=int, default=20)
    # Stage 2 filtering (CC)
    p.add_argument("--s2-gray-lo", type=int, default=50)
    p.add_argument("--s2-gray-hi", type=int, default=180)
    p.add_argument("--s2-min-area", type=int, default=800)
    p.add_argument("--s2-max-area", type=int, default=30000)
    p.add_argument("--s2-min-dim", type=int, default=25)
    p.add_argument("--s2-max-aspect", type=float, default=4.0)
    p.add_argument("--s2-min-rect", type=float, default=0.30)
    p.add_argument("--s2-max-rect", type=float, default=0.5)
    # v11: Gray fill detection (lighter filtering)
    p.add_argument("--fill-gray-lo", type=int, default=100, help="Gray low")
    p.add_argument("--fill-gray-hi", type=int, default=185, help="Gray high")
    p.add_argument("--fill-min-area", type=int, default=100, help="Min area in resized img")
    p.add_argument("--fill-max-aspect", type=float, default=3.0, help="Max aspect ratio")
    p.add_argument("--fill-min-solidity", type=float, default=0.4, help="Min solidity")
    # NMS & Drawing
    p.add_argument("--nms-thresh", type=float, default=0.3)
    p.add_argument("--dot-radius", type=int, default=0, help="0=auto")
    return p.parse_args()


def load_and_resize(path, max_size):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Cannot read: {path}")
    h, w = img.shape[:2]
    scale = min(max_size / max(h, w), 1.0)
    if scale < 1.0:
        resized = cv2.resize(img, (int(w * scale), int(h * scale)))
    else:
        resized = img
        scale = 1.0
    return img, resized, scale


def find_best_gray_region(gray_img, bbox, args):
    """
    Find the largest valid gray filled region within bbox.
    Apply filtering to reject text while keeping filled shapes.
    """
    x, y, w, h = bbox
    gray_roi = gray_img[y:y+h, x:x+w]
    
    # Create mask for gray fill pixels
    gray_fill = ((gray_roi >= args.fill_gray_lo) & (gray_roi <= args.fill_gray_hi)).astype(np.uint8) * 255
    
    # Light morphological cleanup (3x3 kernel, 1 iteration)
    kernel = np.ones((3, 3), np.uint8)
    gray_fill = cv2.morphologyEx(gray_fill, cv2.MORPH_OPEN, kernel, iterations=1)
    gray_fill = cv2.morphologyEx(gray_fill, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    contours, _ = cv2.findContours(gray_fill, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return x + w // 2, y + h // 2, None
    
    best_contour = None
    best_area = 0
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < args.fill_min_area:
            continue
        
        rx, ry, rw, rh = cv2.boundingRect(cnt)
        
        # Aspect ratio check
        aspect = max(rw, rh) / (min(rw, rh) + 1)
        if aspect > args.fill_max_aspect:
            continue
        
        # Solidity check
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area > 0:
            solidity = area / hull_area
            if solidity < args.fill_min_solidity:
                continue
        
        if area > best_area:
            best_area = area
            best_contour = cnt
    
    if best_contour is None:
        return x + w // 2, y + h // 2, None
    
    # Calculate centroid using moments
    M = cv2.moments(best_contour)
    if M["m00"] > 0:
        cx_local = int(M["m10"] / M["m00"])
        cy_local = int(M["m01"] / M["m00"])
    else:
        rx, ry, rw, rh = cv2.boundingRect(best_contour)
        cx_local = rx + rw // 2
        cy_local = ry + rh // 2
    
    rx, ry, rw, rh = cv2.boundingRect(best_contour)
    
    cx = x + cx_local
    cy = y + cy_local
    tight_bbox = (x + rx, y + ry, rw, rh)
    
    return cx, cy, tight_bbox


def stage1_sam(img_resized, gray, args):
    """Stage 1: SAM for solid filled shapes"""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam = sam_model_registry[args.model_type](checkpoint=args.model)
    sam.to(device)

    generator = SamAutomaticMaskGenerator(
        sam,
        points_per_side=args.sam_points,
        pred_iou_thresh=args.sam_iou,
        stability_score_thresh=args.sam_stability,
        min_mask_region_area=args.s1_min_area,
        crop_n_layers=args.sam_crop_layers,
    )

    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    print("   [Stage 1] SAM segmenting...")
    t0 = time.time()
    masks = generator.generate(img_rgb)
    print(f"   [Stage 1] {len(masks)} segments in {time.time()-t0:.1f}s")

    entities = []
    skipped = {"no_gray": 0, "small": 0, "filtered": 0}
    
    for mask in masks:
        seg = mask["segmentation"].astype(np.uint8)
        contours, _ = cv2.findContours(seg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        cnt = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(cnt)
        if not (args.s1_min_area <= area <= args.s1_max_area):
            skipped["filtered"] += 1
            continue

        x, y, bw, bh = cv2.boundingRect(cnt)
        rect_area = bw * bh
        if rect_area == 0 or bw < args.s1_min_dim or bh < args.s1_min_dim:
            skipped["small"] += 1
            continue

        rectangularity = area / rect_area
        if rectangularity < args.s1_min_rect:
            skipped["filtered"] += 1
            continue

        # v11: Find best gray region
        cx, cy, tight_bbox = find_best_gray_region(gray, (x, y, bw, bh), args)
        
        if tight_bbox is None:
            skipped["no_gray"] += 1
            continue
            
        tx, ty, tw, th = tight_bbox
        
        if tw < args.s1_min_dim or th < args.s1_min_dim:
            skipped["small"] += 1
            continue

        roi = gray[y:y+bh, x:x+bw]
        mean_gray = np.mean(roi)

        entities.append({
            "x": tx, "y": ty, "w": tw, "h": th,
            "cx": cx, "cy": cy,
            "area": int(area),
            "rect": round(rectangularity, 3),
            "gray": int(mean_gray),
            "source": "SAM"
        })

    print(f"   [Stage 1] Filtered: {len(entities)} shapes (skipped: no_gray={skipped['no_gray']}, small={skipped['small']}, filtered={skipped['filtered']})")
    return entities


def stage2_cc(gray, sam_entities, args):
    """Stage 2: Connected components for L/U/T shapes"""
    print("   [Stage 2] Connected component analysis...")
    h_r, w_r = gray.shape[:2]

    mask = ((gray > args.s2_gray_lo) & (gray < args.s2_gray_hi)).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    print(f"   [Stage 2] Found {num_labels-1} connected regions")

    sam_mask = np.zeros((h_r, w_r), dtype=np.uint8)
    for e in sam_entities:
        cv2.rectangle(sam_mask, (e["x"], e["y"]), (e["x"]+e["w"], e["y"]+e["h"]), 255, -1)

    entities = []
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if not (args.s2_min_area <= area <= args.s2_max_area):
            continue
        if bw < args.s2_min_dim or bh < args.s2_min_dim:
            continue

        aspect = max(bw, bh) / (min(bw, bh) + 1)
        if aspect > args.s2_max_aspect:
            continue

        bbox_area = bw * bh
        overlap = np.sum(sam_mask[y:y+bh, x:x+bw] > 0) / bbox_area if bbox_area > 0 else 0
        if overlap > 0.5:
            continue

        component_mask = (labels == i).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        cnt = max(contours, key=cv2.contourArea)
        cnt_area = cv2.contourArea(cnt)
        rectangularity = cnt_area / bbox_area if bbox_area > 0 else 0
        if not (args.s2_min_rect <= rectangularity < args.s2_max_rect):
            continue

        roi = gray[y:y+bh, x:x+bw]
        mean_gray = np.mean(roi)

        # v11: Find best gray region
        cx, cy, tight_bbox = find_best_gray_region(gray, (x, y, bw, bh), args)
        
        if tight_bbox is None:
            continue
            
        tx, ty, tw, th = tight_bbox
        
        if tw < args.s2_min_dim or th < args.s2_min_dim:
            continue

        entities.append({
            "x": tx, "y": ty, "w": tw, "h": th,
            "cx": cx, "cy": cy,
            "area": int(cnt_area),
            "rect": round(rectangularity, 3),
            "gray": int(mean_gray),
            "source": "CC"
        })

    print(f"   [Stage 2] Added: {len(entities)} complex shapes")
    return entities


def nms(entities, iou_thresh):
    def iou(a, b):
        x1, y1 = max(a["x"], b["x"]), max(a["y"], b["y"])
        x2, y2 = min(a["x"]+a["w"], b["x"]+b["w"]), min(a["y"]+a["h"], b["y"]+b["h"])
        if x2 <= x1 or y2 <= y1:
            return 0
        inter = (x2-x1) * (y2-y1)
        return inter / (a["w"]*a["h"] + b["w"]*b["h"] - inter)

    entities.sort(key=lambda e: (e["source"] == "SAM", e["area"]), reverse=True)
    keep = []
    for e in entities:
        if all(iou(e, k) <= iou_thresh for k in keep):
            keep.append(e)
    return keep


def scale_entities(entities, scale):
    return [{
        "x": int(e["x"] / scale), "y": int(e["y"] / scale),
        "w": int(e["w"] / scale), "h": int(e["h"] / scale),
        "cx": int(e["cx"] / scale), "cy": int(e["cy"] / scale),
        "area": int(e["area"] / scale**2),
        "rect": e["rect"], "gray": e["gray"], "source": e["source"]
    } for e in entities]


def draw_results(img, entities, dot_radius):
    result = img.copy()
    for e in entities:
        x, y, w, h = e["x"], e["y"], e["w"], e["h"]
        cx, cy = e["cx"], e["cy"]
        color = (0, 255, 0) if e["source"] == "SAM" else (0, 165, 255)
        thickness = 3 if e["source"] == "SAM" else 2
        cv2.rectangle(result, (x, y), (x+w, y+h), color, thickness)
        cv2.circle(result, (cx, cy), dot_radius, (0, 0, 255), -1)
    return result


def main():
    args = parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu_name = torch.cuda.get_device_name(0) if device == "cuda" else "CPU"

    print(f"🚀 Two-Stage Entity Detector v11 (Strict Filtering)")
    print(f"   Device: {device} ({gpu_name})")
    print(f"   Gray fill: {args.fill_gray_lo}-{args.fill_gray_hi}, min_area={args.fill_min_area}")
    print(f"   Max aspect: {args.fill_max_aspect}, min solidity: {args.fill_min_solidity}")

    img_orig, img_resized, scale = load_and_resize(args.input, args.max_size)
    h, w = img_orig.shape[:2]
    h_r, w_r = img_resized.shape[:2]
    print(f"   Input: {args.input}")
    print(f"   Size: {w}x{h} -> {w_r}x{h_r} (scale={scale:.2f})")

    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

    sam_entities = stage1_sam(img_resized, gray, args)
    cc_entities = stage2_cc(gray, sam_entities, args)

    all_entities = sam_entities + cc_entities
    final_entities = nms(all_entities, args.nms_thresh)
    final_entities = scale_entities(final_entities, scale)

    sam_count = sum(1 for e in final_entities if e["source"] == "SAM")
    cc_count = sum(1 for e in final_entities if e["source"] == "CC")
    print(f"\n�� Total: {len(final_entities)} entities (SAM: {sam_count}, CC: {cc_count})")

    os.makedirs(args.output, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.input))[0]
    out_img = os.path.join(args.output, f"{base}_v11.png")
    out_json = os.path.join(args.output, f"{base}_v11.json")

    result_img = draw_results(img_orig, final_entities, args.dot_radius)
    cv2.imwrite(out_img, result_img)
    print(f"   ✅ Saved: {out_img}")

    with open(out_json, "w") as f:
        json.dump(final_entities, f, indent=2)
    print(f"   ✅ Saved: {out_json}")


if __name__ == "__main__":
    main()
