#!/usr/bin/env python3
"""
3D BiomedParse Fine-tuning: Before vs After Comparison
Shows Input | GT | Before (Original) | After (Fine-tuned)
"""
import os, sys
# Assuming running from BiomedParse root
sys.path.append(os.getcwd())
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra

device = torch.device("cuda")

def load_model(checkpoint_path=None):
    """Load 3D model, optionally with fine-tuned weights"""
    GlobalHydra.instance().clear()
    job_name = "ft" if checkpoint_path else "orig"
    initialize(config_path="configs/model", job_name=job_name, version_base=None)
    cfg = compose(config_name="biomedparse_3D")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    model.load_pretrained("biomedparse_v2.ckpt")
    
    if checkpoint_path:
        ckpt = torch.load(checkpoint_path, map_location="cuda")
        model.load_state_dict(ckpt)
        print(f"Loaded fine-tuned: {checkpoint_path}")
    
    return model.to(device).eval()

def predict_3d(model, imgs_tensor, text):
    """Run 3D inference - imgs_tensor should be (1, D, H, W) NOT normalized"""
    with torch.no_grad(), torch.amp.autocast("cuda"):
        results = model({"image": imgs_tensor, "text": text}, mode="eval")
        pred = results["predictions"]["pred_gmasks"][0]
        pred_resized = F.interpolate(
            pred.unsqueeze(0).unsqueeze(0),
            size=(imgs_tensor.shape[1], 512, 512),
            mode="trilinear",
            align_corners=False
        ).squeeze()
        pred_mask = (torch.sigmoid(pred_resized) > 0.5).cpu().numpy()
    return pred_mask

def compute_dice(pred, gt):
    intersection = np.logical_and(pred, gt).sum()
    total = pred.sum() + gt.sum()
    return 2 * intersection / total if total > 0 else 1.0

def main():
    # os.chdir("/root/BiomedParse") # Removed for portability
    
    print("Loading 3D data...")
    # TODO: Update these paths to your dataset
    img_data = np.load("examples/imgs/CT_AMOS_amos_0018.npz", allow_pickle=True)
    gt_data = np.load("examples/gts/CT_AMOS_amos_0018.npz", allow_pickle=True)
    
    image_full = img_data["imgs"]
    gts_full = gt_data["gts"]
    text_prompts = img_data["text_prompts"].item()
    
    # Use same slice range as fine-tuning script
    start_slice, end_slice = 15, 45
    image = image_full[start_slice:end_slice]
    gts = gts_full[start_slice:end_slice]
    
    # NO normalization - keep original range!
    imgs_tensor = torch.from_numpy(image.astype(np.float32)).unsqueeze(0).to(device)
    print(f"Volume shape: {image.shape}, range: {image.min():.0f}-{image.max():.0f}")
    
    # Adrenal glands - what we fine-tuned on
    organs = {
        "Left Adrenal Gland": (11, text_prompts.get("11", "Left Adrenal Gland")),
        "Right Adrenal Gland": (12, text_prompts.get("12", "Right Adrenal Gland")),
    }
    
    print("\nLoading original model...")
    model_orig = load_model()
    
    print("\nLoading fine-tuned model...")
    # Update this path to your fine-tuned model
    # Found at: /root/finetune_output/biomedparse_3d_adrenal_best.pt
    model_ft = load_model("/root/finetune_output/biomedparse_3d_adrenal_best.pt")
    
    # Create figure
    fig, axes = plt.subplots(2, 4, figsize=(16, 9))
    
    for row, (organ_name, (organ_id, text)) in enumerate(organs.items()):
        print(f"\n{organ_name} (ID={organ_id}, text='{text}')...")
        
        # Get GT for this organ
        gt_vol = (gts == organ_id).astype(np.uint8)
        slice_counts = gt_vol.sum(axis=(1, 2))
        best_slice = np.argmax(slice_counts)
        print(f"  Best slice: {best_slice} (global {best_slice+start_slice}), {slice_counts[best_slice]} GT pixels")
        
        # Run both models
        print("  Original model...")
        pred_orig = predict_3d(model_orig, imgs_tensor, text)
        dice_orig = compute_dice(pred_orig, gt_vol) * 100
        
        print("  Fine-tuned model...")
        pred_ft = predict_3d(model_ft, imgs_tensor, text)
        dice_ft = compute_dice(pred_ft, gt_vol) * 100
        
        improvement = dice_ft - dice_orig
        print(f"  Dice: {dice_orig:.1f}% -> {dice_ft:.1f}% (Δ{improvement:+.1f}%)")
        
        # Get slices for visualization
        img_slice = image[best_slice]
        gt_slice = gt_vol[best_slice]
        pred_orig_slice = pred_orig[best_slice]
        pred_ft_slice = pred_ft[best_slice]
        
        # Normalize image for display only
        img_disp = (img_slice - img_slice.min()) / (img_slice.max() - img_slice.min() + 1e-8)
        img_rgb = np.stack([img_disp]*3, axis=-1)
        
        # Col 0: Input image
        axes[row, 0].imshow(img_disp, cmap="gray")
        axes[row, 0].set_title(f"Input (slice {best_slice+start_slice})", fontsize=11)
        axes[row, 0].axis("off")
        
        # Col 1: Ground Truth (green overlay)
        gt_ov = img_rgb.copy()
        gt_ov[gt_slice > 0] = [0, 1, 0]
        axes[row, 1].imshow(gt_ov)
        axes[row, 1].set_title(f"GT: {organ_name}", fontsize=11)
        axes[row, 1].axis("off")
        
        # Col 2: Before (Original model)
        # Green=correct, Red=FP, Orange=missed
        ov_before = img_rgb.copy()
        correct = (pred_orig_slice > 0) & (gt_slice > 0)
        fp = (pred_orig_slice > 0) & (gt_slice == 0)
        missed = (pred_orig_slice == 0) & (gt_slice > 0)
        ov_before[correct] = [0, 0.8, 0]   # Green
        ov_before[fp] = [1, 0, 0]          # Red
        ov_before[missed] = [1, 0.5, 0]    # Orange
        axes[row, 2].imshow(ov_before)
        axes[row, 2].set_title(f"Before: {dice_orig:.1f}%", fontsize=12, color="red", fontweight="bold")
        axes[row, 2].axis("off")
        
        # Col 3: After (Fine-tuned model)
        ov_after = img_rgb.copy()
        correct = (pred_ft_slice > 0) & (gt_slice > 0)
        fp = (pred_ft_slice > 0) & (gt_slice == 0)
        missed = (pred_ft_slice == 0) & (gt_slice > 0)
        ov_after[correct] = [0, 0.8, 0]
        ov_after[fp] = [1, 0, 0]
        ov_after[missed] = [1, 0.5, 0]
        axes[row, 3].imshow(ov_after)
        axes[row, 3].set_title(f"After: {dice_ft:.1f}%", fontsize=12, color="green", fontweight="bold")
        axes[row, 3].axis("off")
    
    plt.suptitle("3D BiomedParse Fine-tuning: Adrenal Glands\nGreen=Correct, Red=False Positive, Orange=Missed", 
                 fontsize=14, color="white")
    plt.tight_layout()
    plt.savefig("3d_finetune_comparison_v4.png", dpi=150, bbox_inches="tight", facecolor="black")
    print("\n✅ Saved: 3d_finetune_comparison_v4.png")

if __name__ == "__main__":
    main()
