"""
BiomedParse 3D STRONG Fine-tuning v3
====================================
基于 finetune_3d_proper.py 的工作版本
100 epochs, 更多器官
"""
import os
import sys
sys.path.insert(0, "/root/BiomedParse")

import torch
import torch.nn.functional as F
import numpy as np
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.cuda.amp import GradScaler
import gc

os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.chdir("/root/BiomedParse")

# Config
NUM_EPOCHS = 100
LEARNING_RATE = 1e-5
WEIGHT_DECAY = 0.01

def dice_loss(pred, target, smooth=1e-5):
    pred = torch.sigmoid(pred)
    intersection = (pred * target).sum()
    return 1 - (2 * intersection + smooth) / (pred.sum() + target.sum() + smooth)

def bce_dice_loss(pred, target):
    bce = F.binary_cross_entropy_with_logits(pred, target)
    dice = dice_loss(pred, target)
    return bce + dice

def dice_score(pred, target, smooth=1e-5):
    pred_binary = (torch.sigmoid(pred) > 0.5).float()
    intersection = (pred_binary * target).sum()
    return (2 * intersection + smooth) / (pred_binary.sum() + target.sum() + smooth)

def main():
    print("=" * 70)
    print("BiomedParse 3D STRONG Fine-tuning v3")
    print("=" * 70, flush=True)

    device = torch.device("cuda")
    print(f"GPU: {torch.cuda.get_device_name(0)}", flush=True)

    # Load CT_AMOS data
    print("\n[1/5] Loading CT_AMOS dataset...")
    img_data = np.load("examples/imgs/CT_AMOS_amos_0018.npz", allow_pickle=True)
    gt_data = np.load("examples/gts/CT_AMOS_amos_0018.npz", allow_pickle=True)

    image = img_data["imgs"]  # (63, 512, 512)
    gts = gt_data["gts"]       # (63, 512, 512)
    text_prompts = img_data["text_prompts"].item()

    # Use slices 20-36 (16 slices where organs exist)
    start_slice = 20
    num_slices = 16
    image = image[start_slice:start_slice+num_slices]
    gts = gts[start_slice:start_slice+num_slices]
    print(f"   Volume: {image.shape} (slices {start_slice}-{start_slice+num_slices-1})")

    # Use organs 1-6 (spleen, kidneys, gallbladder, esophagus, liver)
    organ_ids = [1, 2, 3, 4, 5, 6]
    num_organs = len(organ_ids)
    text = "[SEP]".join([text_prompts[str(i)] for i in organ_ids])
    print(f"   Organs: {num_organs}")
    for oid in organ_ids:
        print(f"     {oid}: {text_prompts[str(oid)][:40]}...")

    # Create GT masks
    gt_masks = []
    for oid in organ_ids:
        mask = (gts == oid).astype(np.float32)
        gt_masks.append(mask)
        print(f"     Organ {oid}: {mask.sum():.0f} pixels")

    # Prepare tensors
    image_norm = (image - image.min()) / (image.max() - image.min() + 1e-8)
    imgs = torch.from_numpy(image_norm).unsqueeze(0).float().to(device)  # [1, D, H, W]
    gt_tensor = torch.from_numpy(np.stack(gt_masks)).float().to(device)   # [num_organs, D, H, W]
    print(f"   Image tensor: {imgs.shape}")
    print(f"   GT tensor: {gt_tensor.shape}", flush=True)

    # Load model
    print("\n[2/5] Loading BiomedParse 3D model...")
    GlobalHydra.instance().clear()
    initialize(config_path="configs/model", job_name="finetune_3d")
    cfg = compose(config_name="biomedparse_3D")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    model.load_pretrained("biomedparse_v2.ckpt")
    model = model.to(device)

    n_params = sum(p.numel() for p in model.parameters())
    print(f"   Parameters: {n_params:,}", flush=True)

    # Evaluate original model
    print("\n[3/5] Evaluating ORIGINAL model...")
    model.eval()
    with torch.no_grad(), torch.amp.autocast("cuda"):
        results = model({"image": imgs, "text": text}, mode="eval")
        pred_masks = results["predictions"]["pred_gmasks"][:num_organs]

    gt_resized = F.interpolate(gt_tensor.unsqueeze(0), size=pred_masks.shape[-3:], mode="nearest").squeeze(0)
    
    orig_dice = {}
    for i, oid in enumerate(organ_ids):
        d = dice_score(pred_masks[i:i+1], gt_resized[i:i+1]).item()
        orig_dice[oid] = d
        print(f"   Organ {oid}: {d*100:.2f}%")
    orig_overall = np.mean(list(orig_dice.values()))
    print(f"   Overall: {orig_overall*100:.2f}%", flush=True)

    # Training
    print("\n[4/5] Training...")
    model.train()
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
    scaler = GradScaler()

    print(f"   Epochs: {NUM_EPOCHS}")
    print(f"   LR: {LEARNING_RATE}")
    print("-" * 70, flush=True)

    best_loss = float("inf")
    gt_resized = None

    for epoch in range(NUM_EPOCHS):
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
                torch.save(model.state_dict(), "/root/finetune_output/biomedparse_3d_strong_best.pt")

            if (epoch + 1) % 10 == 0 or epoch == 0:
                print(f"Epoch [{epoch+1:3d}/{NUM_EPOCHS}]: Loss = {loss.item():.4f}", flush=True)

        except RuntimeError as e:
            if "out of memory" in str(e):
                print(f"OOM at epoch {epoch+1}, clearing cache...")
                gc.collect()
                torch.cuda.empty_cache()
            else:
                raise e

    torch.save(model.state_dict(), "/root/finetune_output/biomedparse_3d_strong_final.pt")
    print("-" * 70)
    print(f"Training complete! Best loss: {best_loss:.4f}", flush=True)

    # Final evaluation
    print("\n[5/5] Evaluating FINE-TUNED model...")
    model.eval()
    with torch.no_grad(), torch.amp.autocast("cuda"):
        results = model({"image": imgs, "text": text}, mode="eval")
        pred_masks = results["predictions"]["pred_gmasks"][:num_organs]

    gt_eval = F.interpolate(gt_tensor.unsqueeze(0), size=pred_masks.shape[-3:], mode="nearest").squeeze(0)

    print("\n" + "=" * 70)
    print("FINAL RESULTS")
    print("=" * 70)
    print(f"{Organ:<8} {Original:>12} {Fine-tuned:>12} {Delta:>12}")
    print("-" * 70)

    ft_dices = []
    for i, oid in enumerate(organ_ids):
        o = orig_dice[oid] * 100
        f = dice_score(pred_masks[i:i+1], gt_eval[i:i+1]).item() * 100
        ft_dices.append(f/100)
        d = f - o
        print(f"Organ {oid:<3} {o:>11.2f}% {f:>11.2f}% {d:>+11.2f}%")

    print("-" * 70)
    ft_overall = np.mean(ft_dices)
    delta = (ft_overall - orig_overall) * 100
    print(f"{OVERALL:<8} {orig_overall*100:>11.2f}% {ft_overall*100:>11.2f}% {delta:>+11.2f}%")
    print("=" * 70, flush=True)

if __name__ == "__main__":
    main()
