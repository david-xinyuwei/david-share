#!/usr/bin/env python3
"""
BiomedParse 3D Visualization Script

Generate before/after comparison images for 3D fine-tuning results.
Shows volumetric segmentation with multi-slice visualization.

Usage:
    python visualize_3d.py \
        --data_path /path/to/volume.npz \
        --checkpoint /path/to/best_model_3d.pt \
        --output comparison_3d.png

Color Scheme:
    - Green: True Positive (correctly segmented)
    - Red: False Positive (over-segmentation)
    - Orange: False Negative (missed region)

Author: Xinyu Wei
Date: 2025-12-28
"""

import os
import sys
import argparse
import numpy as np
import torch
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from scipy.ndimage import zoom

# Add BiomedParse to path
BIOMEDPARSE_ROOT = os.environ.get('BIOMEDPARSE_ROOT', '/path/to/BiomedParse')
sys.path.insert(0, BIOMEDPARSE_ROOT)

from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from inference_utils.inference import build_model


def build_biomedparse_model_3d(checkpoint_path=None, device='cuda'):
    """Build BiomedParse 3D model."""
    GlobalHydra.instance().clear()
    
    config_path = os.path.join(BIOMEDPARSE_ROOT, 'configs/model')
    initialize(config_path=config_path, version_base=None)
    cfg = compose(config_name='biomedparse_3D')
    cfg_dict = {
        'STROKE_SAMPLER': {'MAX_CANDIDATE': 1},
        'MODEL': {
            'BACKBONE_DIM': 768,
            'IMAGE_ENCODER': {'PRETRAINED': True}
        }
    }
    
    model = build_model(cfg, cfg_dict)
    
    if checkpoint_path and os.path.exists(checkpoint_path):
        state = torch.load(checkpoint_path, map_location='cpu')
        if 'model' in state:
            model.load_state_dict(state['model'], strict=False)
        else:
            model.load_state_dict(state, strict=False)
    
    return model.to(device)


def resize_3d_volume(volume, target_size, order=1):
    """Resize 3D volume."""
    D, H, W = volume.shape
    scale = (target_size / D, target_size / H, target_size / W)
    return zoom(volume, scale, order=order)


def compute_dice_3d(pred, gt):
    """Compute 3D Dice coefficient."""
    pred = pred.flatten()
    gt = gt.flatten()
    intersection = (pred * gt).sum()
    return (2. * intersection) / (pred.sum() + gt.sum() + 1e-6) * 100


def predict_3d(model, volume, prompt, device='cuda', target_size=128):
    """Run 3D inference."""
    model.eval()
    
    # Resize and prepare volume
    vol_resized = resize_3d_volume(volume.astype(np.float32), target_size)
    vol_tensor = torch.from_numpy(vol_resized).unsqueeze(0).to(device)
    
    with torch.no_grad():
        outputs = model.forward_3d(vol_tensor, [prompt])
        pred = torch.sigmoid(outputs['pred_masks'])
        pred_binary = (pred > 0.5).float()
    
    return pred_binary.squeeze().cpu().numpy()


def create_3d_overlay(slice_img, gt_mask, pred_mask, alpha=0.4):
    """
    Create overlay for a single slice with TP/FP/FN coloring.
    
    Colors:
        - Green: True Positive
        - Red: False Positive  
        - Orange: False Negative
    """
    # Normalize image
    img_norm = (slice_img - slice_img.min()) / (slice_img.max() - slice_img.min() + 1e-6)
    overlay = np.stack([img_norm, img_norm, img_norm], axis=-1)
    
    gt_bool = gt_mask > 0.5
    pred_bool = pred_mask > 0.5
    
    # True Positive - Green
    tp = gt_bool & pred_bool
    overlay[tp] = overlay[tp] * (1-alpha) + np.array([0, 1, 0]) * alpha
    
    # False Positive - Red
    fp = ~gt_bool & pred_bool
    overlay[fp] = overlay[fp] * (1-alpha) + np.array([1, 0, 0]) * alpha
    
    # False Negative - Orange
    fn = gt_bool & ~pred_bool
    overlay[fn] = overlay[fn] * (1-alpha) + np.array([1, 0.6, 0]) * alpha
    
    return np.clip(overlay, 0, 1)


def main():
    parser = argparse.ArgumentParser(description='Generate 3D comparison visualization')
    parser.add_argument('--data_path', type=str, required=True,
                        help='Path to NPZ file with volume and masks')
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='Path to fine-tuned checkpoint')
    parser.add_argument('--pretrained', type=str, default=None,
                        help='Path to pretrained checkpoint (for "before")')
    parser.add_argument('--output', type=str, default='comparison_3d.png',
                        help='Output image path')
    parser.add_argument('--target_size', type=int, default=128,
                        help='Target volume size')
    parser.add_argument('--n_slices', type=int, default=6,
                        help='Number of slices to display')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device to use')
    args = parser.parse_args()
    
    device = torch.device(args.device if torch.cuda.is_available() else 'cpu')
    
    # Load data
    print(f"Loading data from: {args.data_path}")
    data = np.load(args.data_path)
    volume = data['volume']
    
    # Find organ masks
    organs = []
    for key in data.files:
        if key != 'volume':
            organs.append({
                'name': key.replace('_', ' '),
                'mask': data[key]
            })
    
    print(f"Volume shape: {volume.shape}")
    print(f"Organs: {[o['name'] for o in organs]}")
    
    # Build models
    print("Loading fine-tuned model...")
    model_after = build_biomedparse_model_3d(args.checkpoint, device)
    
    print("Loading pretrained model...")
    GlobalHydra.instance().clear()
    model_before = build_biomedparse_model_3d(args.pretrained, device)
    
    # Resize volume and masks
    vol_resized = resize_3d_volume(volume, args.target_size, order=1)
    
    results = []
    for organ in organs:
        mask_resized = resize_3d_volume(organ['mask'], args.target_size, order=0)
        mask_resized = (mask_resized > 0.5).astype(np.float32)
        
        # Predict
        pred_before = predict_3d(model_before, volume, organ['name'], device, args.target_size)
        pred_after = predict_3d(model_after, volume, organ['name'], device, args.target_size)
        
        # Compute Dice
        dice_before = compute_dice_3d(pred_before, mask_resized)
        dice_after = compute_dice_3d(pred_after, mask_resized)
        
        results.append({
            'name': organ['name'],
            'gt_mask': mask_resized,
            'pred_before': pred_before,
            'pred_after': pred_after,
            'dice_before': dice_before,
            'dice_after': dice_after
        })
        
        print(f"  {organ['name']}: Before {dice_before:.1f}% -> After {dice_after:.1f}%")
    
    # Select slices with organ presence
    all_masks = np.stack([r['gt_mask'] for r in results]).sum(axis=0)
    slice_presence = all_masks.sum(axis=(1, 2))
    valid_slices = np.where(slice_presence > 0)[0]
    
    if len(valid_slices) >= args.n_slices:
        # Sample evenly
        indices = np.linspace(0, len(valid_slices)-1, args.n_slices, dtype=int)
        selected_slices = valid_slices[indices]
    else:
        selected_slices = valid_slices
    
    # Create visualization
    n_organs = len(results)
    n_slices = len(selected_slices)
    
    fig, axes = plt.subplots(n_organs * 2, n_slices, figsize=(3 * n_slices, 4 * n_organs))
    
    if n_organs == 1:
        axes = axes.reshape(2, -1)
    
    for org_idx, res in enumerate(results):
        for slice_idx, z in enumerate(selected_slices):
            # Get slice data
            slice_img = vol_resized[z]
            gt_slice = res['gt_mask'][z]
            before_slice = res['pred_before'][z]
            after_slice = res['pred_after'][z]
            
            # Before (top rows)
            row_before = org_idx * 2
            overlay_before = create_3d_overlay(slice_img, gt_slice, before_slice)
            axes[row_before, slice_idx].imshow(overlay_before)
            axes[row_before, slice_idx].axis('off')
            
            if slice_idx == 0:
                axes[row_before, slice_idx].set_ylabel(
                    f"{res['name']}\nBefore: {res['dice_before']:.1f}%",
                    fontsize=10
                )
            
            if org_idx == 0:
                axes[row_before, slice_idx].set_title(f"z={z}", fontsize=10)
            
            # After (bottom rows)
            row_after = org_idx * 2 + 1
            overlay_after = create_3d_overlay(slice_img, gt_slice, after_slice)
            axes[row_after, slice_idx].imshow(overlay_after)
            axes[row_after, slice_idx].axis('off')
            
            if slice_idx == 0:
                axes[row_after, slice_idx].set_ylabel(
                    f"After: {res['dice_after']:.1f}%",
                    fontsize=10
                )
    
    # Add legend
    legend_elements = [
        Patch(facecolor='green', alpha=0.5, label='True Positive'),
        Patch(facecolor='red', alpha=0.5, label='False Positive'),
        Patch(facecolor='orange', alpha=0.5, label='False Negative (Missed)')
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=10)
    
    plt.suptitle('BiomedParse 3D Fine-tuning Results', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(args.output, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n✓ Saved comparison image to: {args.output}")
    
    # Print summary
    print(f"\n=== Summary ===")
    for res in results:
        improvement = res['dice_after'] - res['dice_before']
        print(f"{res['name']}: {res['dice_before']:.1f}% -> {res['dice_after']:.1f}% (+{improvement:.1f}%)")
    
    avg_before = np.mean([r['dice_before'] for r in results])
    avg_after = np.mean([r['dice_after'] for r in results])
    print(f"\nAverage: {avg_before:.1f}% -> {avg_after:.1f}% (+{avg_after - avg_before:.1f}%)")


if __name__ == '__main__':
    main()
