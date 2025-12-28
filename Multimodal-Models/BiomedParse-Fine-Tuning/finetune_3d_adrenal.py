#!/usr/bin/env python3
"""
BiomedParse 3D Fine-tuning Script

Fine-tune BiomedParse v2 on 3D CT volumetric data for small organ segmentation.
Uses 3D mode with volumetric consistency for organs like adrenal glands.

Usage:
    python finetune_3d.py --data_path /path/to/volume.npz --output_dir /path/to/output

Data Format (NPZ):
    - 'volume': CT volume array [D, H, W], 0-255 range
    - 'left_adrenal_gland': Binary mask [D, H, W]
    - 'right_adrenal_gland': Binary mask [D, H, W]

Author: Xinyu Wei
Date: 2025-12-28
"""

import os
import sys
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.cuda.amp import autocast, GradScaler
from tqdm import tqdm

# Add BiomedParse to path
BIOMEDPARSE_ROOT = os.environ.get('BIOMEDPARSE_ROOT', '/path/to/BiomedParse')
sys.path.insert(0, BIOMEDPARSE_ROOT)

from hydra import initialize, compose
from hydra.core.global_hydra import GlobalHydra
from inference_utils.inference import build_model


class DiceLoss(nn.Module):
    """Dice Loss for binary segmentation."""
    
    def __init__(self, smooth=1e-6):
        super().__init__()
        self.smooth = smooth

    def forward(self, pred, target):
        pred = pred.view(-1)
        target = target.view(-1)
        intersection = (pred * target).sum()
        return 1 - (2. * intersection + self.smooth) / \
               (pred.sum() + target.sum() + self.smooth)


def build_biomedparse_model_3d(checkpoint_path=None, device='cuda'):
    """Build BiomedParse 3D model with optional custom checkpoint."""
    
    # Clear Hydra global state
    GlobalHydra.instance().clear()
    
    # Initialize Hydra with 3D config
    config_path = os.path.join(BIOMEDPARSE_ROOT, 'configs/model')
    initialize(config_path=config_path, version_base=None)
    cfg = compose(config_name='biomedparse_3D')  # 3D config!
    cfg_dict = {
        'STROKE_SAMPLER': {'MAX_CANDIDATE': 1},
        'MODEL': {
            'BACKBONE_DIM': 768,
            'IMAGE_ENCODER': {'PRETRAINED': True}
        }
    }
    
    # Build model
    model = build_model(cfg, cfg_dict)
    
    # Load checkpoint
    if checkpoint_path and os.path.exists(checkpoint_path):
        print(f"Loading checkpoint: {checkpoint_path}")
        state = torch.load(checkpoint_path, map_location='cpu')
        if 'model' in state:
            model.load_state_dict(state['model'], strict=False)
        else:
            model.load_state_dict(state, strict=False)
    else:
        # Load default pretrained model
        default_ckpt = os.path.join(BIOMEDPARSE_ROOT, 'biomedparse_v2.ckpt')
        if os.path.exists(default_ckpt):
            print(f"Loading pretrained model: {default_ckpt}")
            state = torch.load(default_ckpt, map_location='cpu')
            model.load_state_dict(state['model'], strict=False)
    
    return model.to(device)


def load_3d_data(data_path, target_size=128):
    """
    Load 3D volumetric data from NPZ file.
    
    Expected keys:
        - 'volume': CT volume [D, H, W]
        - 'left_<organ>': Left organ mask [D, H, W]
        - 'right_<organ>': Right organ mask [D, H, W]
    
    Returns:
        dict with volume and masks
    """
    data = np.load(data_path)
    
    volume = data['volume']
    print(f"Volume shape: {volume.shape}, range: [{volume.min()}, {volume.max()}]")
    
    # Find mask keys
    masks = {}
    for key in data.files:
        if key != 'volume' and 'mask' not in key.lower():
            masks[key.replace('_', ' ')] = data[key]
            print(f"  Mask '{key}': shape {data[key].shape}")
    
    return {
        'volume': volume,
        'masks': masks
    }


def resize_3d_volume(volume, target_size):
    """Resize 3D volume to target size using trilinear interpolation."""
    from scipy.ndimage import zoom
    
    D, H, W = volume.shape
    scale = (target_size / D, target_size / H, target_size / W)
    
    # Use order=1 for trilinear (volume) or order=0 for nearest (masks)
    resized = zoom(volume, scale, order=1)
    return resized


def compute_dice_3d(pred, gt):
    """Compute Dice coefficient for 3D volumes."""
    pred = pred.flatten()
    gt = gt.flatten()
    intersection = (pred * gt).sum()
    return (2. * intersection) / (pred.sum() + gt.sum() + 1e-6) * 100


def train_3d(model, volume, masks, output_dir, 
             epochs=100, lr=1e-5, target_size=128, device='cuda'):
    """
    Train 3D model on volumetric data.
    
    Args:
        model: BiomedParse 3D model
        volume: CT volume [D, H, W]
        masks: Dict of organ name -> binary mask
        output_dir: Directory to save checkpoints
        epochs: Number of training epochs
        lr: Learning rate
        target_size: Target volume size
        device: Device to use
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare volume tensor
    # Keep 0-255 range! Do NOT normalize to 0-1!
    vol_resized = resize_3d_volume(volume.astype(np.float32), target_size)
    vol_tensor = torch.from_numpy(vol_resized).unsqueeze(0).to(device)  # [1, D, H, W]
    
    # Prepare mask tensors
    mask_tensors = {}
    for organ, mask in masks.items():
        mask_resized = resize_3d_volume(mask.astype(np.float32), target_size)
        mask_resized = (mask_resized > 0.5).astype(np.float32)
        mask_tensors[organ] = torch.from_numpy(mask_resized).unsqueeze(0).to(device)
    
    # Setup training
    criterion = DiceLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)
    scaler = GradScaler()
    
    # Training loop
    best_dice = 0
    organ_list = list(masks.keys())
    
    print(f"\nStarting 3D training for {epochs} epochs...")
    print(f"Organs: {organ_list}")
    
    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0
        
        # Train on each organ
        for organ in organ_list:
            optimizer.zero_grad()
            
            with autocast():
                # Forward pass (3D mode)
                outputs = model.forward_3d(vol_tensor, [organ])
                pred_mask = torch.sigmoid(outputs['pred_masks'])
                
                # Compute loss
                loss = criterion(pred_mask, mask_tensors[organ])
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            epoch_loss += loss.item()
        
        scheduler.step()
        avg_loss = epoch_loss / len(organ_list)
        
        # Evaluate every 10 epochs
        if epoch % 10 == 0 or epoch == 1:
            model.eval()
            dice_scores = []
            
            with torch.no_grad():
                for organ in organ_list:
                    outputs = model.forward_3d(vol_tensor, [organ])
                    pred = (torch.sigmoid(outputs['pred_masks']) > 0.5).float()
                    dice = compute_dice_3d(
                        pred.cpu().numpy(),
                        mask_tensors[organ].cpu().numpy()
                    )
                    dice_scores.append(dice)
                    print(f"  {organ}: {dice:.2f}%")
            
            avg_dice = np.mean(dice_scores)
            print(f"Epoch {epoch}/{epochs} | Loss: {avg_loss:.4f} | Avg Dice: {avg_dice:.2f}%")
            
            # Save best model
            if avg_dice > best_dice:
                best_dice = avg_dice
                best_path = os.path.join(output_dir, 'best_model_3d.pt')
                torch.save({
                    'epoch': epoch,
                    'model': model.state_dict(),
                    'dice': best_dice
                }, best_path)
                print(f"✓ New best model: {best_dice:.2f}%")
    
    print(f"\n=== 3D Training Complete ===")
    print(f"Best Dice Score: {best_dice:.2f}%")
    
    return best_dice


def main():
    parser = argparse.ArgumentParser(description='Fine-tune BiomedParse on 3D CT data')
    parser.add_argument('--data_path', type=str, required=True,
                        help='Path to NPZ file with volume and masks')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Path to save checkpoints')
    parser.add_argument('--checkpoint', type=str, default=None,
                        help='Path to initial checkpoint (optional)')
    parser.add_argument('--epochs', type=int, default=100,
                        help='Number of training epochs')
    parser.add_argument('--lr', type=float, default=1e-5,
                        help='Learning rate')
    parser.add_argument('--target_size', type=int, default=128,
                        help='Target volume size (D=H=W)')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device to use')
    args = parser.parse_args()
    
    # Setup device
    device = torch.device(args.device if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Load data
    print(f"Loading data from: {args.data_path}")
    data = load_3d_data(args.data_path, args.target_size)
    
    # Build model
    print("Building 3D model...")
    model = build_biomedparse_model_3d(args.checkpoint, device)
    
    # Train
    train_3d(
        model=model,
        volume=data['volume'],
        masks=data['masks'],
        output_dir=args.output_dir,
        epochs=args.epochs,
        lr=args.lr,
        target_size=args.target_size,
        device=device
    )


if __name__ == '__main__':
    main()
