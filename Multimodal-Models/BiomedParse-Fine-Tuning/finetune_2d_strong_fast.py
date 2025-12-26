"""
BiomedParse v2 2D Multi-Organ Fine-tuning (Fast Version)
=========================================================
High-performance 2D medical image segmentation fine-tuning script.

Features:
- DataLoader with batch_size=8 and multi-worker loading
- Mixed precision training (FP16)
- Automatic best checkpoint saving
- Per-organ Dice evaluation

Author: Xinyu Wei (Microsoft AI and Apps GBB)
License: MIT
"""
import os
import sys
import json
import argparse

import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import autocast, GradScaler
from torch.utils.data import Dataset, DataLoader
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra


# ==================== Configuration ====================
def get_config():
    parser = argparse.ArgumentParser(description='BiomedParse 2D Fine-tuning')
    parser.add_argument('--biomedparse_dir', type=str, default='.',
                        help='Path to BiomedParse repository')
    parser.add_argument('--data_dir', type=str, required=True,
                        help='Path to training data directory')
    parser.add_argument('--output_dir', type=str, default='./output',
                        help='Path to save checkpoints')
    parser.add_argument('--checkpoint', type=str, default='biomedparse_v2.ckpt',
                        help='Path to pretrained checkpoint')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--lr', type=float, default=1e-5)
    parser.add_argument('--batch_size', type=int, default=8)
    parser.add_argument('--num_workers', type=int, default=4)
    parser.add_argument('--weight_decay', type=float, default=0.01)
    return parser.parse_args()


class MedSegDataset(Dataset):
    """Medical image segmentation dataset for 2D images.
    
    Expected data structure:
        data_dir/
        ├── train/           # Training images (PNG)
        ├── train_mask/      # Training masks (PNG, binary)
        ├── test/            # Test images
        ├── test_mask/       # Test masks
        ├── train.json       # Training annotations
        └── test.json        # Test annotations
    
    JSON format:
        {
            "annotations": [
                {
                    "file_name": "img_001.png",
                    "mask_file": "img_001.png",
                    "sentences": [{"sent": "CT scan of the liver"}]
                }
            ]
        }
    """
    
    def __init__(self, data_dir, split):
        json_path = os.path.join(data_dir, split + ".json")
        with open(json_path) as f:
            data = json.load(f)

        self.data = data["annotations"]
        self.img_dir = os.path.join(data_dir, split)
        self.mask_dir = os.path.join(data_dir, split + "_mask")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        ann = self.data[idx]

        # Load image
        img = Image.open(os.path.join(self.img_dir, ann["file_name"])).convert("RGB")
        img = np.array(img).astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))

        # Load mask
        mask = Image.open(os.path.join(self.mask_dir, ann["mask_file"])).convert("L")
        mask = np.array(mask).astype(np.float32) / 255.0

        # Get text prompt and organ name
        prompt = ann["sentences"][0]["sent"]
        organ = ann["file_name"].split("_")[-1].replace(".png", "")

        return torch.from_numpy(img), torch.from_numpy(mask), prompt, organ


def collate_fn(batch):
    """Custom collate function for DataLoader."""
    images = torch.stack([b[0] for b in batch])
    masks = torch.stack([b[1] for b in batch])
    prompts = [b[2] for b in batch]
    organs = [b[3] for b in batch]
    return images, masks, prompts, organs


def dice_loss(pred, target, smooth=1e-5):
    """Compute Dice loss for segmentation."""
    pred = torch.sigmoid(pred)
    bs = pred.shape[0]
    pred_flat = pred.view(bs, -1)
    target_flat = target.view(bs, -1)
    intersection = (pred_flat * target_flat).sum(dim=1)
    dice = (2 * intersection + smooth) / (pred_flat.sum(dim=1) + target_flat.sum(dim=1) + smooth)
    return 1 - dice.mean()


def bce_dice_loss(pred, target):
    """Combined BCE and Dice loss - standard for medical segmentation."""
    return F.binary_cross_entropy_with_logits(pred, target) + dice_loss(pred, target)


def dice_score(pred, gt):
    """Compute Dice score for evaluation."""
    intersection = (pred * gt).sum()
    return (2 * intersection + 1e-5) / (pred.sum() + gt.sum() + 1e-5)


def evaluate_model(model, data_loader, device):
    """Evaluate model and return per-organ Dice scores."""
    model.eval()
    dice_by_organ = {}

    with torch.no_grad():
        for images, masks, prompts, organs in data_loader:
            images = images.to(device)
            masks = masks.unsqueeze(1).to(device)

            for i in range(len(images)):
                with autocast():
                    output = model({"image": images[i:i+1], "text": [prompts[i]]}, mode="eval")
                    pred = output["predictions"]["pred_gmasks"]

                pred_resized = F.interpolate(pred, size=masks.shape[-2:], mode="bilinear", align_corners=False)
                pred_binary = (torch.sigmoid(pred_resized) > 0.5).float()
                dice = dice_score(pred_binary, masks[i:i+1]).item()

                organ = organs[i]
                if organ not in dice_by_organ:
                    dice_by_organ[organ] = []
                dice_by_organ[organ].append(dice)

    return dice_by_organ


def main():
    args = get_config()
    
    # Setup paths
    sys.path.insert(0, args.biomedparse_dir)
    os.chdir(args.biomedparse_dir)
    os.makedirs(args.output_dir, exist_ok=True)
    
    print("=" * 70)
    print("BiomedParse v2 2D Multi-Organ Fine-tuning")
    print("=" * 70)
    print(f"Data directory: {args.data_dir}")
    print(f"Output directory: {args.output_dir}")
    print(f"Epochs: {args.epochs}, LR: {args.lr}, Batch size: {args.batch_size}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load datasets
    print("\n[1/5] Loading datasets...")
    train_dataset = MedSegDataset(args.data_dir, "train")
    test_dataset = MedSegDataset(args.data_dir, "test")

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, collate_fn=collate_fn, pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.num_workers, collate_fn=collate_fn, pin_memory=True
    )

    print(f"   Train: {len(train_dataset)} samples, {len(train_loader)} batches")
    print(f"   Test: {len(test_dataset)} samples")

    # Load model
    print("\n[2/5] Loading BiomedParse 2D model...")
    GlobalHydra.instance().clear()
    initialize(config_path="configs/model", job_name="finetune_2d")
    cfg = compose(config_name="biomedparse")
    model = hydra.utils.instantiate(cfg, _convert_="object")

    # Load pretrained weights
    if os.path.exists(args.checkpoint):
        print(f"   Loading weights from {args.checkpoint}...")
        ckpt = torch.load(args.checkpoint, map_location="cpu")
        loaded = 0
        state_dict = model.state_dict()
        for k, v in ckpt.items():
            if k in state_dict and state_dict[k].shape == v.shape:
                state_dict[k] = v
                loaded += 1
        model.load_state_dict(state_dict)
        print(f"   Loaded {loaded}/{len(ckpt)} params")

    model = model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"   Parameters: {n_params:,}")

    # Evaluate original model
    print("\n[3/5] Evaluating ORIGINAL model...")
    orig_dice_by_organ = evaluate_model(model, test_loader, device)
    
    print("   Original Dice by organ:")
    for organ, dices in sorted(orig_dice_by_organ.items()):
        print(f"     {organ}: {np.mean(dices)*100:.2f}%")
    orig_overall = np.mean([d for dices in orig_dice_by_organ.values() for d in dices])
    print(f"   Overall: {orig_overall*100:.2f}%")

    # Training
    print("\n[4/5] Training...")
    model.train()
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler = GradScaler()

    print("-" * 70)
    best_loss = float("inf")

    for epoch in range(args.epochs):
        model.train()
        epoch_loss = 0.0
        n_samples = 0

        for images, masks, prompts, organs in train_loader:
            images = images.to(device)
            masks = masks.unsqueeze(1).to(device)

            optimizer.zero_grad()
            batch_loss = 0.0

            for i in range(len(images)):
                with autocast():
                    output = model({"image": images[i:i+1], "text": [prompts[i]]}, mode="train")
                    pred = output["predictions"]["pred_gmasks"]
                    pred_resized = F.interpolate(pred, size=masks.shape[-2:], mode="bilinear", align_corners=False)
                    loss = bce_dice_loss(pred_resized, masks[i:i+1]) / len(images)

                scaler.scale(loss).backward()
                batch_loss += loss.item() * len(images)

            scaler.step(optimizer)
            scaler.update()

            epoch_loss += batch_loss
            n_samples += len(images)

        scheduler.step()
        avg_loss = epoch_loss / n_samples

        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save(model.state_dict(), os.path.join(args.output_dir, "biomedparse_2d_best.pt"))

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1:3d}/{args.epochs}]: Loss = {avg_loss:.4f}")

    torch.save(model.state_dict(), os.path.join(args.output_dir, "biomedparse_2d_final.pt"))
    print("-" * 70)
    print(f"Training complete! Best loss: {best_loss:.4f}")

    # Final evaluation
    print("\n[5/5] Evaluating FINE-TUNED model...")
    ft_dice_by_organ = evaluate_model(model, test_loader, device)

    # Print comparison
    print("\n" + "=" * 70)
    print("FINAL RESULTS - Test Set")
    print("=" * 70)
    print(f"{'Organ':<20} {'Original':>12} {'Fine-tuned':>12} {'Delta':>12}")
    print("-" * 70)

    all_orig, all_ft = [], []
    for organ in sorted(orig_dice_by_organ.keys()):
        orig = np.mean(orig_dice_by_organ.get(organ, [0])) * 100
        ft = np.mean(ft_dice_by_organ.get(organ, [0])) * 100
        delta = ft - orig
        print(f"{organ:<20} {orig:>11.2f}% {ft:>11.2f}% {delta:>+11.2f}%")
        all_orig.extend(orig_dice_by_organ.get(organ, []))
        all_ft.extend(ft_dice_by_organ.get(organ, []))

    print("-" * 70)
    overall_orig = np.mean(all_orig) * 100
    overall_ft = np.mean(all_ft) * 100
    overall_delta = overall_ft - overall_orig
    print(f"{'OVERALL':<20} {overall_orig:>11.2f}% {overall_ft:>11.2f}% {overall_delta:>+11.2f}%")
    print("=" * 70)
    print(f"\nCheckpoints saved to: {args.output_dir}/")


if __name__ == "__main__":
    main()
