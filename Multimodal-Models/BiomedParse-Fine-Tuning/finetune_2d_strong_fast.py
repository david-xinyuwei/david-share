"""
BiomedParse v2 2D STRONG Fine-tuning (FAST VERSION)
====================================================
- DataLoader with batch_size=8
- num_workers=4
- Gradient accumulation
- 目标: 3-5x speedup
"""
import os, sys, gc, json
sys.path.insert(0, "/root/BiomedParse")
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

os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.chdir("/root/BiomedParse")

# ==================== Config ====================
NUM_EPOCHS = 100
LEARNING_RATE = 1e-5
WEIGHT_DECAY = 0.01
BATCH_SIZE = 8  # 提高并发
NUM_WORKERS = 4
DATA_DIR = "/root/BiomedParse/biomedparse_datasets/strong_2d_data"

class MedSegDataset(Dataset):
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
        
        img = Image.open(os.path.join(self.img_dir, ann["file_name"])).convert("RGB")
        img = np.array(img).astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        
        mask = Image.open(os.path.join(self.mask_dir, ann["mask_file"])).convert("L")
        mask = np.array(mask).astype(np.float32) / 255.0
        
        prompt = ann["sentences"][0]["sent"]
        organ = ann["file_name"].split("_")[-1].replace(".png", "")
        
        return torch.from_numpy(img), torch.from_numpy(mask), prompt, organ

def collate_fn(batch):
    images = torch.stack([b[0] for b in batch])
    masks = torch.stack([b[1] for b in batch])
    prompts = [b[2] for b in batch]
    organs = [b[3] for b in batch]
    return images, masks, prompts, organs

def dice_loss(pred, target, smooth=1e-5):
    pred = torch.sigmoid(pred)
    # Per-sample dice then mean
    bs = pred.shape[0]
    pred_flat = pred.view(bs, -1)
    target_flat = target.view(bs, -1)
    intersection = (pred_flat * target_flat).sum(dim=1)
    dice = (2 * intersection + smooth) / (pred_flat.sum(dim=1) + target_flat.sum(dim=1) + smooth)
    return 1 - dice.mean()

def bce_dice_loss(pred, target):
    return F.binary_cross_entropy_with_logits(pred, target) + dice_loss(pred, target)

def dice_score(pred, gt):
    intersection = (pred * gt).sum()
    return (2 * intersection + 1e-5) / (pred.sum() + gt.sum() + 1e-5)

def main():
    print("=" * 70)
    print("BiomedParse v2 2D STRONG Fine-tuning (FAST)")
    print("=" * 70)

    device = torch.device("cuda")

    # Load datasets with DataLoader
    print("\n[1/5] Loading datasets...")
    train_dataset = MedSegDataset(DATA_DIR, "train")
    test_dataset = MedSegDataset(DATA_DIR, "test")
    
    train_loader = DataLoader(
        train_dataset, 
        batch_size=BATCH_SIZE, 
        shuffle=True, 
        num_workers=NUM_WORKERS,
        collate_fn=collate_fn,
        pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, 
        batch_size=BATCH_SIZE, 
        shuffle=False, 
        num_workers=NUM_WORKERS,
        collate_fn=collate_fn,
        pin_memory=True
    )

    print(f"   Train: {len(train_dataset)} samples, {len(train_loader)} batches")
    print(f"   Test: {len(test_dataset)} samples, {len(test_loader)} batches")
    print(f"   Batch size: {BATCH_SIZE}")

    # Load model
    print("\n[2/5] Loading BiomedParse 2D model...")
    GlobalHydra.instance().clear()
    initialize(config_path="configs/model", job_name="ft2d_strong_fast")
    cfg = compose(config_name="biomedparse")
    model = hydra.utils.instantiate(cfg, _convert_="object")

    # Load pretrained weights
    ckpt_path = "/root/BiomedParse/biomedparse_v2.ckpt"
    if os.path.exists(ckpt_path):
        print("   Loading weights from biomedparse_v2.ckpt...")
        ckpt = torch.load(ckpt_path, map_location="cpu")
        loaded = 0
        state_dict = model.state_dict()
        for k, v in ckpt.items():
            if k in state_dict and state_dict[k].shape == v.shape:
                state_dict[k] = v
                loaded += 1
        model.load_state_dict(state_dict)
        print(f"   Loaded {loaded}/{len(ckpt)} params")

    model = model.cuda()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"   Parameters: {n_params:,}")

    # Evaluate original model
    print("\n[3/5] Evaluating ORIGINAL model on test set...")
    model.eval()
    orig_dice_by_organ = {}

    with torch.no_grad():
        for images, masks, prompts, organs in test_loader:
            images = images.to(device)
            masks = masks.unsqueeze(1).to(device)
            
            # Process one at a time for eval (model expects single text)
            for i in range(len(images)):
                with autocast():
                    output = model({"image": images[i:i+1], "text": [prompts[i]]}, mode="eval")
                    pred = output["predictions"]["pred_gmasks"]
                
                pred_resized = F.interpolate(pred, size=masks.shape[-2:], mode="bilinear", align_corners=False)
                pred_binary = (torch.sigmoid(pred_resized) > 0.5).float()
                dice = dice_score(pred_binary, masks[i:i+1]).item()
                
                organ = organs[i]
                if organ not in orig_dice_by_organ:
                    orig_dice_by_organ[organ] = []
                orig_dice_by_organ[organ].append(dice)

    print("   Original Dice by organ:")
    for organ, dices in sorted(orig_dice_by_organ.items()):
        print(f"     {organ}: {np.mean(dices)*100:.2f}%")
    orig_overall = np.mean([d for dices in orig_dice_by_organ.values() for d in dices])
    print(f"   Overall: {orig_overall*100:.2f}%")

    # Training setup
    print("\n[4/5] Starting training...")
    model.train()
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
    scaler = GradScaler()

    print(f"   Epochs: {NUM_EPOCHS}")
    print(f"   LR: {LEARNING_RATE}")
    print(f"   Batch size: {BATCH_SIZE}")
    print(f"   Batches per epoch: {len(train_loader)}")
    print("-" * 70)

    best_loss = float("inf")

    for epoch in range(NUM_EPOCHS):
        model.train()
        epoch_loss = 0.0
        n_samples = 0

        for images, masks, prompts, organs in train_loader:
            images = images.to(device)
            masks = masks.unsqueeze(1).to(device)
            
            optimizer.zero_grad()
            batch_loss = 0.0
            
            # Process samples in batch (model handles single text, so loop)
            for i in range(len(images)):
                with autocast():
                    output = model({"image": images[i:i+1], "text": [prompts[i]]}, mode="train")
                    pred = output["predictions"]["pred_gmasks"]
                    pred_resized = F.interpolate(pred, size=masks.shape[-2:], mode="bilinear", align_corners=False)
                    loss = bce_dice_loss(pred_resized, masks[i:i+1]) / len(images)  # Normalize
                
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
            torch.save(model.state_dict(), "/root/finetune_output/biomedparse_2d_strong_best.pt")

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1:3d}/{NUM_EPOCHS}]: Loss = {avg_loss:.4f}")

    torch.save(model.state_dict(), "/root/finetune_output/biomedparse_2d_strong_final.pt")
    print("-" * 70)
    print(f"Training complete! Best loss: {best_loss:.4f}")

    # Final evaluation
    print("\n[5/5] Evaluating FINE-TUNED model on test set...")
    model.eval()
    ft_dice_by_organ = {}

    with torch.no_grad():
        for images, masks, prompts, organs in test_loader:
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
                if organ not in ft_dice_by_organ:
                    ft_dice_by_organ[organ] = []
                ft_dice_by_organ[organ].append(dice)

    # Print comparison
    print("\n" + "=" * 70)
    print("FINAL RESULTS - Test Set")
    print("=" * 70)
    print(f"{Organ:<20} {Original:>12} {Fine-tuned:>12} {Delta:>12}")
    print("-" * 70)

    all_orig = []
    all_ft = []
    all_organs = sorted(set(organs for _, _, _, organs_batch in test_loader for organs in organs_batch))

    for organ in all_organs:
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
    print(f"{OVERALL:<20} {overall_orig:>11.2f}% {overall_ft:>11.2f}% {overall_delta:>+11.2f}%")
    print("=" * 70)

if __name__ == "__main__":
    main()
