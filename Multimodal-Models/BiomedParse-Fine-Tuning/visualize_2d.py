#!/usr/bin/env python3
"""2D BiomedParse Fine-tuning - Final Comparison with correct left/right kidney"""
import os, sys
# Assuming running from BiomedParse root
sys.path.append(os.getcwd())
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra

device = torch.device("cuda")

def load_model(checkpoint=None):
    GlobalHydra.instance().clear()
    name = "ft" if checkpoint else "orig"
    initialize(config_path="configs/model", job_name=f"compare_{name}", version_base=None)
    cfg = compose(config_name="biomedparse")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    ckpt = torch.load("biomedparse_v2.ckpt", map_location="cpu", weights_only=True)
    if 'state_dict' in ckpt:
        ckpt = ckpt['state_dict']
    
    # Fix keys: strip "model." prefix
    new_state_dict = {}
    for k, v in ckpt.items():
        if k.startswith('model.'):
            new_key = k[6:] # Remove "model."
            new_state_dict[new_key] = v
        else:
            new_state_dict[k] = v
            
    # Load state dict with strict=False to ignore extra keys
    model.load_state_dict(new_state_dict, strict=False)
    if checkpoint and os.path.exists(checkpoint):
        ft_state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(ft_state)
    return model.to(device).eval()

def predict(model, img_tensor, text):
    with torch.no_grad(), torch.amp.autocast("cuda"):
        results = model({"image": img_tensor, "text": text}, mode="eval")
        pred = results["predictions"]["pred_gmasks"][0]
        pred_resized = F.interpolate(pred.unsqueeze(0), size=img_tensor.shape[-2:], mode="bilinear", align_corners=False)
        pred_mask = (torch.sigmoid(pred_resized) > 0.5).squeeze().cpu().numpy()
    return pred_mask

def compute_dice(pred, gt):
    intersection = np.logical_and(pred, gt).sum()
    total = pred.sum() + gt.sum()
    return 2 * intersection / total if total > 0 else 1.0

def overlay_mask(img, mask, color, alpha=0.5):
    img_norm = img.astype(np.float32) / 255.0
    result = img_norm.copy()
    result[mask] = alpha * np.array(color) + (1-alpha) * result[mask]
    return np.clip(result, 0, 1)

def get_organ_prompt(fname):
    # slice025_left_kidney.png -> "left kidney"
    base = fname.replace(".png", "")
    parts = base.split("_")[1:]  # remove slice number
    return " ".join(parts)

def main():
    # os.chdir("/root/BiomedParse") # Removed for portability
    output_dir = "images"
    os.makedirs(output_dir, exist_ok=True)

    print("Loading models...")
    model_orig = load_model()
    # Update this path to your fine-tuned model
    # Default: output/finetune_2d/biomedparse_2d_correct_best.pt
    ft_path = "output/finetune_2d/biomedparse_2d_correct_best.pt"
    if not os.path.exists(ft_path):
        print(f"⚠️ Warning: Fine-tuned model not found at {ft_path}")
        print("Please update the path in visualize_2d.py or run finetune_2d.py first.")
        model_ft = model_orig # Fallback to compare same model (or exit)
    else:
        model_ft = load_model(ft_path)

    # TODO: Update these paths to your dataset
    test_dir = "biomedparse_datasets/ct_2d_data/test"
    mask_dir = "biomedparse_datasets/ct_2d_data/test_mask"
    test_files = sorted([f for f in os.listdir(test_dir) if f.endswith(".png")])[:6]

    fig, axes = plt.subplots(len(test_files), 4, figsize=(14, 3.5*len(test_files)))
    col_titles = ["Input", "Ground Truth", "Before (Original)", "After (Fine-tuned)"]

    for i, fname in enumerate(test_files):
        img = np.array(Image.open(f"{test_dir}/{fname}"))
        mask_fname = fname.replace(".png", "_mask.png")
        gt = np.array(Image.open(f"{mask_dir}/{mask_fname}")) > 127
        organ = get_organ_prompt(fname)

        img_tensor = torch.from_numpy(img.astype(np.float32)).permute(2, 0, 1).unsqueeze(0).to(device)

        pred_orig = predict(model_orig, img_tensor, organ)
        pred_ft = predict(model_ft, img_tensor, organ)

        dice_orig = compute_dice(pred_orig, gt) * 100
        dice_ft = compute_dice(pred_ft, gt) * 100
        improvement = dice_ft - dice_orig

        print(f"{fname}: '{organ}' -> {dice_orig:.1f}% -> {dice_ft:.1f}% (+{improvement:.1f}%)")

        # Column 0: Input
        axes[i, 0].imshow(img)
        if i == 0: axes[i, 0].set_title(col_titles[0], fontsize=13, fontweight="bold", pad=10)
        axes[i, 0].set_ylabel(organ.title(), fontsize=10)
        axes[i, 0].axis("off")

        # Column 1: Ground Truth (green)
        axes[i, 1].imshow(overlay_mask(img, gt, [0, 1, 0], 0.5))
        if i == 0: axes[i, 1].set_title(col_titles[1], fontsize=13, fontweight="bold", pad=10)
        axes[i, 1].axis("off")

        # Column 2: Before (orange)
        axes[i, 2].imshow(overlay_mask(img, pred_orig, [1, 0.5, 0], 0.5))
        if i == 0: axes[i, 2].set_title(col_titles[2], fontsize=13, fontweight="bold", pad=10)
        axes[i, 2].text(0.5, -0.02, f"Dice: {dice_orig:.1f}%", transform=axes[i,2].transAxes,
                        ha="center", va="top", fontsize=10, color="red", fontweight="bold")
        axes[i, 2].axis("off")

        # Column 3: After (cyan)
        axes[i, 3].imshow(overlay_mask(img, pred_ft, [0, 0.8, 1], 0.5))
        if i == 0: axes[i, 3].set_title(col_titles[3], fontsize=13, fontweight="bold", pad=10)
        axes[i, 3].text(0.5, -0.02, f"Dice: {dice_ft:.1f}% (+{improvement:.1f}%)", 
                        transform=axes[i,3].transAxes, ha="center", va="top", fontsize=10, color="green", fontweight="bold")
        axes[i, 3].axis("off")

    fig.suptitle("2D BiomedParse Fine-tuning: CT Organ Segmentation\n(GT=Green, Before=Orange, After=Cyan)", 
                 fontsize=14, fontweight="bold", y=0.995)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    output_path = f"{output_dir}/biomedparse_2d_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"\n✅ Saved: {output_path}")

if __name__ == "__main__":
    main()
