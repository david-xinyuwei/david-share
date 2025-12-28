#!/usr/bin/env python3
"""
BiomedParse 2D Visualization Script

Generate before/after comparison images for 2D fine-tuning results.
Shows GT (green), Before (orange), and After (cyan) overlays.

Usage:
    python visualize_2d.py \
        --test_dir /path/to/test \
        --test_mask_dir /path/to/test_mask \
        --checkpoint /path/to/best_model.pt \
        --output comparison.png

Author: Xinyu Wei
Date: 2025-12-28
"""

import os
import sys
import argparse
import numpy as np
import torch
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# Add BiomedParse to path
BIOMEDPARSE_ROOT = os.environ.get('BIOMEDPARSE_ROOT', '/path/to/BiomedParse')
sys.path.insert(0, BIOMEDPARSE_ROOT)

from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from inference_utils.inference import build_model


def build_biomedparse_model(checkpoint_path=None, device='cuda'):
    """Build BiomedParse model with optional custom checkpoint."""
    GlobalHydra.instance().clear()
    
    config_path = os.path.join(BIOMEDPARSE_ROOT, 'configs/model')
    initialize(config_path=config_path, version_base=None)
    cfg = compose(config_name='biomedparse')
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


def get_prompt_from_filename(fname):
    """Extract organ name from filename."""
    base = fname.replace('.png', '')
    parts = base.split('_')
    organ_parts = parts[1:]
    return ' '.join(organ_parts)


def predict_mask(model, image, prompt, device='cuda'):
    """Run inference and get predicted mask."""
    model.eval()
    
    # Prepare image tensor (keep 0-255!)
    img_tensor = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).to(device)
    
    with torch.no_grad():
        outputs = model.forward_2d(img_tensor, [prompt])
        pred = torch.sigmoid(outputs['pred_masks'])
        pred_binary = (pred > 0.5).float()
    
    return pred_binary.squeeze().cpu().numpy()


def compute_dice(pred, gt):
    """Compute Dice coefficient."""
    pred = pred.flatten()
    gt = gt.flatten()
    intersection = (pred * gt).sum()
    return (2. * intersection) / (pred.sum() + gt.sum() + 1e-6) * 100


def create_overlay(image, gt_mask, before_mask, after_mask, alpha=0.5):
    """
    Create overlay image with colored masks.
    
    Colors:
        - GT: Green
        - Before: Orange
        - After: Cyan
    """
    # Normalize image to 0-1 for display
    img_display = image.astype(np.float32) / 255.0
    
    # Create RGB overlay
    overlay = img_display.copy()
    
    # GT mask - Green
    gt_color = np.array([0, 1, 0])  # Green
    gt_region = gt_mask > 0.5
    for c in range(3):
        overlay[:, :, c] = np.where(gt_region, 
            overlay[:, :, c] * (1-alpha) + gt_color[c] * alpha,
            overlay[:, :, c])
    
    # Before mask - Orange
    before_color = np.array([1, 0.5, 0])  # Orange
    before_region = before_mask > 0.5
    for c in range(3):
        overlay[:, :, c] = np.where(before_region & ~gt_region,
            overlay[:, :, c] * (1-alpha) + before_color[c] * alpha,
            overlay[:, :, c])
    
    # After mask - Cyan
    after_color = np.array([0, 1, 1])  # Cyan
    after_region = after_mask > 0.5
    for c in range(3):
        overlay[:, :, c] = np.where(after_region & ~gt_region & ~before_region,
            overlay[:, :, c] * (1-alpha) + after_color[c] * alpha,
            overlay[:, :, c])
    
    return np.clip(overlay, 0, 1)


def main():
    parser = argparse.ArgumentParser(description='Generate 2D comparison visualization')
    parser.add_argument('--test_dir', type=str, required=True,
                        help='Path to test images directory')
    parser.add_argument('--test_mask_dir', type=str, required=True,
                        help='Path to test masks directory')
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='Path to fine-tuned checkpoint')
    parser.add_argument('--pretrained', type=str, default=None,
                        help='Path to pretrained checkpoint (for "before")')
    parser.add_argument('--output', type=str, default='comparison_2d.png',
                        help='Output image path')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device to use')
    args = parser.parse_args()
    
    device = torch.device(args.device if torch.cuda.is_available() else 'cpu')
    
    # Build models
    print("Loading fine-tuned model...")
    model_after = build_biomedparse_model(args.checkpoint, device)
    
    print("Loading pretrained model...")
    GlobalHydra.instance().clear()
    model_before = build_biomedparse_model(args.pretrained, device)
    
    # Get test samples
    test_files = sorted([f for f in os.listdir(args.test_dir) if f.endswith('.png')])
    print(f"Found {len(test_files)} test images")
    
    # Collect results
    results = []
    
    for fname in test_files:
        img_path = os.path.join(args.test_dir, fname)
        mask_path = os.path.join(args.test_mask_dir, fname.replace('.png', '_mask.png'))
        
        if not os.path.exists(mask_path):
            continue
        
        # Load image and mask
        img = np.array(Image.open(img_path).convert('RGB').resize((1024, 1024)))
        gt_mask = np.array(Image.open(mask_path).convert('L').resize((1024, 1024))) / 255.0
        
        # Get prompt
        prompt = get_prompt_from_filename(fname)
        
        # Predict
        pred_before = predict_mask(model_before, img.astype(np.float32), prompt, device)
        pred_after = predict_mask(model_after, img.astype(np.float32), prompt, device)
        
        # Resize predictions if needed
        if pred_before.shape != gt_mask.shape:
            from scipy.ndimage import zoom
            scale = (gt_mask.shape[0] / pred_before.shape[0], 
                     gt_mask.shape[1] / pred_before.shape[1])
            pred_before = zoom(pred_before, scale, order=0)
            pred_after = zoom(pred_after, scale, order=0)
        
        # Compute Dice scores
        dice_before = compute_dice(pred_before, gt_mask)
        dice_after = compute_dice(pred_after, gt_mask)
        
        results.append({
            'fname': fname,
            'prompt': prompt,
            'image': img,
            'gt_mask': gt_mask,
            'pred_before': pred_before,
            'pred_after': pred_after,
            'dice_before': dice_before,
            'dice_after': dice_after
        })
        
        print(f"  {fname}: {prompt} | Before: {dice_before:.1f}% | After: {dice_after:.1f}%")
    
    # Create visualization
    n_samples = len(results)
    fig, axes = plt.subplots(2, n_samples, figsize=(4 * n_samples, 8))
    
    if n_samples == 1:
        axes = axes.reshape(-1, 1)
    
    for i, res in enumerate(results):
        # Top row: Before
        overlay_before = create_overlay(res['image'], res['gt_mask'], 
                                        res['pred_before'], np.zeros_like(res['gt_mask']))
        axes[0, i].imshow(overlay_before)
        axes[0, i].set_title(f"{res['prompt']}\nBefore: {res['dice_before']:.1f}%")
        axes[0, i].axis('off')
        
        # Bottom row: After
        overlay_after = create_overlay(res['image'], res['gt_mask'],
                                       np.zeros_like(res['gt_mask']), res['pred_after'])
        axes[1, i].imshow(overlay_after)
        axes[1, i].set_title(f"After: {res['dice_after']:.1f}%")
        axes[1, i].axis('off')
    
    # Add legend
    legend_elements = [
        Patch(facecolor='green', alpha=0.5, label='Ground Truth'),
        Patch(facecolor='orange', alpha=0.5, label='Before Fine-tune'),
        Patch(facecolor='cyan', alpha=0.5, label='After Fine-tune')
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=12)
    
    plt.suptitle('BiomedParse 2D Fine-tuning Results', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(args.output, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n✓ Saved comparison image to: {args.output}")
    
    # Print summary
    avg_before = np.mean([r['dice_before'] for r in results])
    avg_after = np.mean([r['dice_after'] for r in results])
    print(f"\n=== Summary ===")
    print(f"Average Dice Before: {avg_before:.2f}%")
    print(f"Average Dice After: {avg_after:.2f}%")
    print(f"Improvement: +{avg_after - avg_before:.2f}%")


if __name__ == '__main__':
    main()
