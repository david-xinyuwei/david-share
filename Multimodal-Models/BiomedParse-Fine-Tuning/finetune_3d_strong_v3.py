"""
BiomedParse v2 3D Multi-Organ Fine-tuning
==========================================
Fine-tune BiomedParse 3D model on CT/MRI volume data.

Features:
- Supports NPZ format 3D volumes (CT_AMOS style)
- Multi-organ segmentation with [SEP] token
- Mixed precision training
- Automatic OOM recovery

Author: Xinyu Wei (Microsoft AI and Apps GBB)
License: MIT
"""
import os
import sys
import gc
import argparse

import torch
import torch.nn.functional as F
import numpy as np
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import GradScaler


def get_config():
    parser = argparse.ArgumentParser(description='BiomedParse 3D Fine-tuning')
    parser.add_argument('--biomedparse_dir', type=str, default='.',
                        help='Path to BiomedParse repository')
    parser.add_argument('--data_file', type=str, required=True,
                        help='Path to NPZ data file (e.g., CT_AMOS_amos_0018.npz)')
    parser.add_argument('--gt_file', type=str, default=None,
                        help='Path to ground truth NPZ file (if separate from data)')
    parser.add_argument('--output_dir', type=str, default='./output',
                        help='Path to save checkpoints')
    parser.add_argument('--checkpoint', type=str, default='biomedparse_v2.ckpt',
                        help='Path to pretrained checkpoint')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--lr', type=float, default=1e-5)
    parser.add_argument('--weight_decay', type=float, default=0.01)
    parser.add_argument('--start_slice', type=int, default=20,
                        help='Starting slice index')
    parser.add_argument('--num_slices', type=int, default=16,
                        help='Number of slices to use')
    parser.add_argument('--organ_ids', type=str, default='1,2,3,4,5,6',
                        help='Comma-separated organ IDs to segment')
    return parser.parse_args()


def dice_loss(pred, target, smooth=1e-5):
    """Compute Dice loss."""
    pred = torch.sigmoid(pred)
    intersection = (pred * target).sum()
    return 1 - (2 * intersection + smooth) / (pred.sum() + target.sum() + smooth)


def bce_dice_loss(pred, target):
    """Combined BCE and Dice loss."""
    bce = F.binary_cross_entropy_with_logits(pred, target)
    dice = dice_loss(pred, target)
    return bce + dice


def dice_score(pred, target, smooth=1e-5):
    """Compute Dice score for evaluation."""
    pred_binary = (torch.sigmoid(pred) > 0.5).float()
    intersection = (pred_binary * target).sum()
    return (2 * intersection + smooth) / (pred_binary.sum() + target.sum() + smooth)


def main():
    args = get_config()
    
    # Setup paths
    sys.path.insert(0, args.biomedparse_dir)
    os.chdir(args.biomedparse_dir)
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Environment settings for memory efficiency
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    
    print("=" * 70)
    print("BiomedParse v2 3D Multi-Organ Fine-tuning")
    print("=" * 70)
    print(f"Data file: {args.data_file}")
    print(f"Output directory: {args.output_dir}")
    print(f"Epochs: {args.epochs}, LR: {args.lr}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # Load 3D volume data
    print("\n[1/5] Loading 3D volume data...")
    img_data = np.load(args.data_file, allow_pickle=True)
    
    # Handle different NPZ structures
    if 'imgs' in img_data:
        image = img_data["imgs"]
    elif 'image' in img_data:
        image = img_data["image"]
    else:
        raise KeyError(f"NPZ file must contain 'imgs' or 'image' key. Found: {list(img_data.keys())}")
    
    # Load ground truth
    if args.gt_file:
        gt_data = np.load(args.gt_file, allow_pickle=True)
        gts = gt_data["gts"]
    elif 'gts' in img_data:
        gts = img_data["gts"]
    else:
        raise KeyError("Ground truth not found. Provide --gt_file or ensure 'gts' in data file.")
    
    # Load text prompts
    if 'text_prompts' in img_data:
        text_prompts = img_data["text_prompts"].item()
    else:
        # Default prompts for common organs
        text_prompts = {
            "1": "CT scan of spleen",
            "2": "CT scan of right kidney", 
            "3": "CT scan of left kidney",
            "4": "CT scan of gallbladder",
            "5": "CT scan of esophagus",
            "6": "CT scan of liver"
        }
        print("   Warning: Using default text prompts")

    # Select slices
    image = image[args.start_slice:args.start_slice + args.num_slices]
    gts = gts[args.start_slice:args.start_slice + args.num_slices]
    print(f"   Volume shape: {image.shape} (slices {args.start_slice}-{args.start_slice + args.num_slices - 1})")

    # Parse organ IDs
    organ_ids = [int(x) for x in args.organ_ids.split(',')]
    num_organs = len(organ_ids)
    
    # Build text prompt with [SEP] tokens
    text = "[SEP]".join([text_prompts[str(i)] for i in organ_ids])
    print(f"   Organs: {num_organs}")
    for oid in organ_ids:
        prompt_text = text_prompts.get(str(oid), f"Organ {oid}")
        print(f"     {oid}: {prompt_text[:50]}...")

    # Create GT masks
    gt_masks = []
    for oid in organ_ids:
        mask = (gts == oid).astype(np.float32)
        gt_masks.append(mask)
        pixel_count = mask.sum()
        print(f"     Organ {oid}: {pixel_count:.0f} pixels")

    # Prepare tensors
    image_norm = (image - image.min()) / (image.max() - image.min() + 1e-8)
    imgs = torch.from_numpy(image_norm).unsqueeze(0).float().to(device)
    gt_tensor = torch.from_numpy(np.stack(gt_masks)).float().to(device)
    print(f"   Image tensor: {imgs.shape}")
    print(f"   GT tensor: {gt_tensor.shape}")

    # Load model
    print("\n[2/5] Loading BiomedParse 3D model...")
    GlobalHydra.instance().clear()
    initialize(config_path="configs/model", job_name="finetune_3d")
    cfg = compose(config_name="biomedparse_3D")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    model.load_pretrained(args.checkpoint)
    model = model.to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"   Parameters: {n_params:,}")

    # Evaluate original model
    print("\n[3/5] Evaluating ORIGINAL model...")
    model.eval()
    with torch.no_grad(), torch.amp.autocast("cuda"):
        results = model({"image": imgs, "text": text}, mode="eval")
        pred_masks = results["predictions"]["pred_gmasks"][:num_organs]

    gt_resized = F.interpolate(
        gt_tensor.unsqueeze(0), 
        size=pred_masks.shape[-3:], 
        mode="nearest"
    ).squeeze(0)

    orig_dice = {}
    for i, oid in enumerate(organ_ids):
        d = dice_score(pred_masks[i:i+1], gt_resized[i:i+1]).item()
        orig_dice[oid] = d
        print(f"   Organ {oid}: {d*100:.2f}%")
    orig_overall = np.mean(list(orig_dice.values()))
    print(f"   Overall: {orig_overall*100:.2f}%")

    # Training
    print("\n[4/5] Training...")
    model.train()
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs)
    scaler = GradScaler()

    print(f"   Epochs: {args.epochs}")
    print(f"   LR: {args.lr}")
    print("-" * 70)

    best_loss = float("inf")
    gt_resized = None

    for epoch in range(args.epochs):
        optimizer.zero_grad(set_to_none=True)

        try:
            with torch.amp.autocast("cuda"):
                results = model.forward_train(
                    {"image": imgs, "text": text},
                    slice_batch_size=2
                )
                pred_masks = results["predictions"]["pred_gmasks"][:num_organs]

                if gt_resized is None or pred_masks.shape[-2:] != gt_resized.shape[-2:]:
                    gt_resized = F.interpolate(
                        gt_tensor.unsqueeze(0),
                        size=pred_masks.shape[-3:],
                        mode="nearest"
                    ).squeeze(0)

                loss = bce_dice_loss(pred_masks, gt_resized)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            if loss.item() < best_loss:
                best_loss = loss.item()
                torch.save(model.state_dict(), os.path.join(args.output_dir, "biomedparse_3d_best.pt"))

            if (epoch + 1) % 10 == 0 or epoch == 0:
                print(f"Epoch [{epoch+1:3d}/{args.epochs}]: Loss = {loss.item():.4f}")

        except RuntimeError as e:
            if "out of memory" in str(e):
                print(f"OOM at epoch {epoch+1}, clearing cache...")
                gc.collect()
                torch.cuda.empty_cache()
            else:
                raise e

    torch.save(model.state_dict(), os.path.join(args.output_dir, "biomedparse_3d_final.pt"))
    print("-" * 70)
    print(f"Training complete! Best loss: {best_loss:.4f}")

    # Final evaluation
    print("\n[5/5] Evaluating FINE-TUNED model...")
    model.eval()
    with torch.no_grad(), torch.amp.autocast("cuda"):
        results = model({"image": imgs, "text": text}, mode="eval")
        pred_masks = results["predictions"]["pred_gmasks"][:num_organs]

    gt_eval = F.interpolate(
        gt_tensor.unsqueeze(0), 
        size=pred_masks.shape[-3:], 
        mode="nearest"
    ).squeeze(0)

    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"{'Organ':<12} {'Original':>12} {'Fine-tuned':>12} {'Delta':>12}")
    print("-" * 70)

    ft_dices = []
    for i, oid in enumerate(organ_ids):
        o = orig_dice[oid] * 100
        f = dice_score(pred_masks[i:i+1], gt_eval[i:i+1]).item() * 100
        ft_dices.append(f / 100)
        d = f - o
        print(f"Organ {oid:<6} {o:>11.2f}% {f:>11.2f}% {d:>+11.2f}%")

    print("-" * 70)
    ft_overall = np.mean(ft_dices)
    delta = (ft_overall - orig_overall) * 100
    print(f"{'OVERALL':<12} {orig_overall*100:>11.2f}% {ft_overall*100:>11.2f}% {delta:>+11.2f}%")
    print("=" * 70)
    print(f"\nCheckpoints saved to: {args.output_dir}/")


if __name__ == "__main__":
    main()
