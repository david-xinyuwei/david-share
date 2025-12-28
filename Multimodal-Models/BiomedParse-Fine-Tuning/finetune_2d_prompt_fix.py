#!/usr/bin/env python3
"""
BiomedParse 2D Fine-tuning Script

Fine-tune BiomedParse v2 on 2D CT slice data for custom organ segmentation.
Supports multiple organs with text prompts extracted from filenames.

Usage:
    python finetune_2d.py --data_dir /path/to/dataset --output_dir /path/to/output

Data Structure:
    dataset/
    ├── train/
    │   ├── slice001_left_kidney.png      # Filename = prompt
    │   └── ...
    ├── train_mask/
    │   ├── slice001_left_kidney_mask.png
    │   └── ...
    ├── test/
    └── test_mask/

Author: Xinyu Wei
Date: 2025-12-28
"""

import os
import sys
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast, GradScaler
from PIL import Image
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


class CT2DDataset(Dataset):
    """2D CT Dataset with text prompts extracted from filenames."""
    
    def __init__(self, img_dir, mask_dir, target_size=(1024, 1024)):
        """
        Args:
            img_dir: Directory containing input images
            mask_dir: Directory containing corresponding masks
            target_size: Target image size (H, W)
        """
        self.img_dir = img_dir
        self.mask_dir = mask_dir
        self.target_size = target_size
        
        # Get all image files
        self.samples = []
        for fname in sorted(os.listdir(img_dir)):
            if fname.endswith('.png'):
                # Extract organ name from filename
                # Example: slice001_left_kidney.png -> "left kidney"
                prompt = self._get_prompt_from_filename(fname)
                
                # Find corresponding mask
                mask_fname = fname.replace('.png', '_mask.png')
                if os.path.exists(os.path.join(mask_dir, mask_fname)):
                    self.samples.append({
                        'image': os.path.join(img_dir, fname),
                        'mask': os.path.join(mask_dir, mask_fname),
                        'prompt': prompt
                    })
        
        print(f"Loaded {len(self.samples)} samples")
    
    def _get_prompt_from_filename(self, fname):
        """Extract organ name from filename.
        
        CRITICAL: This must match the ground truth organ name exactly!
        
        Examples:
            slice001_left_kidney.png -> "left kidney"
            slice002_liver.png -> "liver"
            volume_right_adrenal_gland.png -> "right adrenal gland"
        """
        base = fname.replace('.png', '')
        parts = base.split('_')
        
        # Remove slice/volume prefix (first part)
        organ_parts = parts[1:]  # Skip "slice001" or "volume"
        
        # Join remaining parts with spaces
        prompt = ' '.join(organ_parts)
        return prompt
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        
        # Load image (keep 0-255 range!)
        img = Image.open(sample['image']).convert('RGB')
        img = img.resize(self.target_size, Image.BILINEAR)
        img = np.array(img, dtype=np.float32)  # DO NOT normalize to 0-1!
        
        # Load mask
        mask = Image.open(sample['mask']).convert('L')
        mask = mask.resize(self.target_size, Image.NEAREST)
        mask = np.array(mask, dtype=np.float32) / 255.0  # Mask should be 0-1
        
        # Convert to tensors
        img_tensor = torch.from_numpy(img).permute(2, 0, 1)  # [3, H, W]
        mask_tensor = torch.from_numpy(mask).unsqueeze(0)   # [1, H, W]
        
        return {
            'image': img_tensor,
            'mask': mask_tensor,
            'prompt': sample['prompt']
        }


def build_biomedparse_model(checkpoint_path=None, device='cuda'):
    """Build BiomedParse model with optional custom checkpoint."""
    
    # Clear Hydra global state (important for multiple calls!)
    GlobalHydra.instance().clear()
    
    # Initialize Hydra with BiomedParse config
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


def train_one_epoch(model, dataloader, optimizer, criterion, scaler, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0
    
    pbar = tqdm(dataloader, desc='Training')
    for batch in pbar:
        images = batch['image'].to(device)
        masks = batch['mask'].to(device)
        prompts = batch['prompt']
        
        optimizer.zero_grad()
        
        with autocast():
            # Forward pass
            outputs = model.forward_2d(images, prompts)
            pred_mask = torch.sigmoid(outputs['pred_masks'])
            
            # Compute loss
            loss = criterion(pred_mask, masks)
        
        # Backward pass
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        
        total_loss += loss.item()
        pbar.set_postfix({'loss': f'{loss.item():.4f}'})
    
    return total_loss / len(dataloader)


def evaluate(model, dataloader, device):
    """Evaluate model and compute Dice scores."""
    model.eval()
    dice_scores = []
    
    with torch.no_grad():
        for batch in tqdm(dataloader, desc='Evaluating'):
            images = batch['image'].to(device)
            masks = batch['mask'].to(device)
            prompts = batch['prompt']
            
            # Forward pass
            outputs = model.forward_2d(images, prompts)
            pred_mask = torch.sigmoid(outputs['pred_masks'])
            pred_binary = (pred_mask > 0.5).float()
            
            # Compute Dice
            for i in range(pred_binary.shape[0]):
                pred = pred_binary[i].view(-1)
                gt = masks[i].view(-1)
                intersection = (pred * gt).sum()
                dice = (2. * intersection) / (pred.sum() + gt.sum() + 1e-6)
                dice_scores.append(dice.item())
    
    return np.mean(dice_scores) * 100  # Return percentage


def main():
    parser = argparse.ArgumentParser(description='Fine-tune BiomedParse on 2D CT data')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Path to dataset directory')
    parser.add_argument('--output_dir', type=str, required=True,
                        help='Path to save checkpoints')
    parser.add_argument('--checkpoint', type=str, default=None,
                        help='Path to initial checkpoint (optional)')
    parser.add_argument('--epochs', type=int, default=30,
                        help='Number of training epochs')
    parser.add_argument('--lr', type=float, default=1e-5,
                        help='Learning rate')
    parser.add_argument('--batch_size', type=int, default=1,
                        help='Batch size (recommend 1 for different prompts)')
    parser.add_argument('--device', type=str, default='cuda',
                        help='Device to use')
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Setup device
    device = torch.device(args.device if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Build model
    print("Building model...")
    model = build_biomedparse_model(args.checkpoint, device)
    
    # Setup datasets
    print("Loading datasets...")
    train_dataset = CT2DDataset(
        img_dir=os.path.join(args.data_dir, 'train'),
        mask_dir=os.path.join(args.data_dir, 'train_mask')
    )
    test_dataset = CT2DDataset(
        img_dir=os.path.join(args.data_dir, 'test'),
        mask_dir=os.path.join(args.data_dir, 'test_mask')
    )
    
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size,
                              shuffle=True, num_workers=4)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size,
                             shuffle=False, num_workers=4)
    
    # Setup training
    criterion = DiceLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)
    scaler = GradScaler()
    
    # Training loop
    best_dice = 0
    print(f"\nStarting training for {args.epochs} epochs...")
    
    for epoch in range(1, args.epochs + 1):
        print(f"\n--- Epoch {epoch}/{args.epochs} ---")
        
        # Train
        train_loss = train_one_epoch(model, train_loader, optimizer, 
                                     criterion, scaler, device)
        print(f"Train Loss: {train_loss:.4f}")
        
        # Evaluate
        test_dice = evaluate(model, test_loader, device)
        print(f"Test Dice: {test_dice:.2f}%")
        
        # Save best model
        if test_dice > best_dice:
            best_dice = test_dice
            best_path = os.path.join(args.output_dir, 'best_model.pt')
            torch.save({
                'epoch': epoch,
                'model': model.state_dict(),
                'optimizer': optimizer.state_dict(),
                'dice': best_dice
            }, best_path)
            print(f"✓ New best model saved: {best_dice:.2f}%")
        
        # Update scheduler
        scheduler.step()
    
    print(f"\n=== Training Complete ===")
    print(f"Best Dice Score: {best_dice:.2f}%")
    print(f"Best model saved to: {os.path.join(args.output_dir, 'best_model.pt')}")


if __name__ == '__main__':
    main()
