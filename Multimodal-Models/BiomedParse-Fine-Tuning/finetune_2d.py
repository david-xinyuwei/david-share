#!/usr/bin/env python3
"""
BiomedParse 2D Fine-tuning - CORRECT VERSION
Key: Input stays 0-255, NO /255 normalization!
"""
import os, sys
# Assuming running from BiomedParse root
sys.path.append(os.getcwd())
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
from PIL import Image
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra

# Config
NUM_EPOCHS = 100
LEARNING_RATE = 1e-5
SAVE_DIR = "output/finetune_2d"

class CTDataset(Dataset):
    def __init__(self, img_dir, mask_dir):
        self.img_dir = img_dir
        self.mask_dir = mask_dir
        self.files = sorted([f for f in os.listdir(img_dir) if f.endswith(".png")])
        
    def __len__(self):
        return len(self.files)
    
    def __getitem__(self, idx):
        fname = self.files[idx]
        img = np.array(Image.open(f"{self.img_dir}/{fname}")).astype(np.float32)
        mask_fname = fname.replace(".png", "_mask.png")
        mask = np.array(Image.open(f"{self.mask_dir}/{mask_fname}")).astype(np.float32) / 255.0
        # Extract full organ name: slice025_left_kidney.png -> "left kidney"
        base = fname.replace(".png", "")
        parts = base.split("_")[1:]  # remove slice number
        organ = " ".join(parts)
        img = torch.from_numpy(img).permute(2, 0, 1)
        mask = torch.from_numpy(mask).unsqueeze(0)
        return img, mask, organ

def dice_loss(pred, target):
    smooth = 1.0
    pred = torch.sigmoid(pred)
    intersection = (pred * target).sum()
    union = pred.sum() + target.sum()
    dice = (2 * intersection + smooth) / (union + smooth)
    return 1 - dice

def compute_dice(pred, target):
    pred_bin = (torch.sigmoid(pred) > 0.5).float()
    intersection = (pred_bin * target).sum()
    total = pred_bin.sum() + target.sum()
    if total == 0:
        return 1.0
    return (2 * intersection / total).item()

def main():
    device = torch.device("cuda")
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    print("="*60)
    print("BiomedParse 2D Fine-tuning - CORRECT (0-255 input)")
    print("="*60)
    
    # Load model
    print("\n[1/4] Loading model...")
    GlobalHydra.instance().clear()
    initialize(config_path="configs/model", job_name="finetune2d", version_base=None)
    cfg = compose(config_name="biomedparse")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    
    ckpt = torch.load("biomedparse_v2.ckpt", map_location="cpu", weights_only=True)
    state_dict = model.state_dict()
    loaded = 0
    for k, v in ckpt.items():
        if k in state_dict and state_dict[k].shape == v.shape:
            state_dict[k] = v
            loaded += 1
    model.load_state_dict(state_dict)
    model = model.to(device)
    print(f"   Loaded {loaded}/{len(ckpt)} params")
    
    # Data - batch_size=1 to avoid text mismatch
    print("\n[2/4] Loading data...")
    # TODO: Update this path to your dataset
    data_root = "biomedparse_datasets/ct_2d_data"
    train_ds = CTDataset(f"{data_root}/train", f"{data_root}/train_mask")
    test_ds = CTDataset(f"{data_root}/test", f"{data_root}/test_mask")
    
    train_loader = DataLoader(train_ds, batch_size=1, shuffle=True, num_workers=2)
    test_loader = DataLoader(test_ds, batch_size=1, shuffle=False)
    
    print(f"   Train: {len(train_ds)}, Test: {len(test_ds)}")
    
    sample_img, _, _ = train_ds[0]
    print(f"   Sample input range: {sample_img.min():.0f} - {sample_img.max():.0f}")
    
    # Evaluate original
    print("\n[3/4] Evaluating ORIGINAL model...")
    model.eval()
    orig_dices = []
    with torch.no_grad():
        for img, mask, organ in test_loader:
            img, mask = img.to(device), mask.to(device)
            with torch.amp.autocast("cuda"):
                results = model({"image": img, "text": organ[0]}, mode="eval")
                pred = results["predictions"]["pred_gmasks"][0]
                pred_resized = F.interpolate(pred.unsqueeze(0), size=mask.shape[-2:], mode="bilinear", align_corners=False)
            dice = compute_dice(pred_resized, mask)
            orig_dices.append(dice)
    orig_mean = np.mean(orig_dices) * 100
    print(f"   Original Dice: {orig_mean:.2f}%")
    
    # Train
    print(f"\n[4/4] Training for {NUM_EPOCHS} epochs...")
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
    scaler = torch.amp.GradScaler("cuda")
    
    best_dice = 0
    for epoch in range(NUM_EPOCHS):
        model.train()
        epoch_loss = 0
        for img, mask, organ in train_loader:
            img, mask = img.to(device), mask.to(device)
            
            if epoch == 0 and epoch_loss == 0:
                print(f"\n[DEBUG] Real 2D Input Tensor Shape: {img.shape}")
                print(f"[DEBUG] Real 2D Input Tensor Range: {img.min().item()} - {img.max().item()}")

            optimizer.zero_grad()
            with torch.amp.autocast("cuda"):
                results = model({"image": img, "text": organ[0]}, mode="train")
                pred = results["predictions"]["pred_gmasks"]
                pred_resized = F.interpolate(pred, size=mask.shape[-2:], mode="bilinear", align_corners=False)
                loss = dice_loss(pred_resized, mask)
            
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            epoch_loss += loss.item()
        
        scheduler.step()
        avg_loss = epoch_loss / len(train_loader)
        
        if (epoch + 1) % 10 == 0:
            model.eval()
            test_dices = []
            with torch.no_grad():
                for img, mask, organ in test_loader:
                    img, mask = img.to(device), mask.to(device)
                    with torch.amp.autocast("cuda"):
                        results = model({"image": img, "text": organ[0]}, mode="eval")
                        pred = results["predictions"]["pred_gmasks"][0]
                        pred_resized = F.interpolate(pred.unsqueeze(0), size=mask.shape[-2:], mode="bilinear", align_corners=False)
                    dice = compute_dice(pred_resized, mask)
                    test_dices.append(dice)
            test_mean = np.mean(test_dices) * 100
            print(f"Epoch {epoch+1:3d}: Loss={avg_loss:.4f}, Dice={test_mean:.2f}%")
            
            if test_mean > best_dice:
                best_dice = test_mean
                torch.save(model.state_dict(), f"{SAVE_DIR}/biomedparse_2d_correct_best.pt")
                print(f"         -> New best!")
        else:
            print(f"Epoch {epoch+1:3d}: Loss={avg_loss:.4f}")
    
    torch.save(model.state_dict(), f"{SAVE_DIR}/biomedparse_2d_correct_final.pt")
    
    print("\n" + "="*60)
    print(f"DONE! Original: {orig_mean:.2f}% -> Best: {best_dice:.2f}%")
    print(f"Improvement: +{best_dice - orig_mean:.2f}%")
    print("="*60)

if __name__ == "__main__":
    main()
