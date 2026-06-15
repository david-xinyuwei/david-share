#!/usr/bin/env python3
"""
BiomedParse 3D Fine-tuning - Small Organs
v5: Use direct eval forward but enable gradients (patched model)
"""
import os, sys
# Assuming running from BiomedParse root
sys.path.append(os.getcwd())
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
import torch.nn.functional as F
import numpy as np
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra

# Monkey-patch forward_eval to allow gradients
def patch_model_for_training(model):
    """Patch model to enable gradients in eval mode"""
    original_forward_eval = model.forward_eval
    
    def forward_eval_with_grad(inputs, slice_batch_size=2):
        # Same as original but without torch.no_grad()
        import time
        t0 = time.time()
        
        image = inputs["image"] if "image" in inputs else None
        text = inputs["text"] if "text" in inputs else None
        
        if image is None:
            raise ValueError("Image is required input")
        
        if image.shape[0] > 1:
            raise ValueError("Batch size > 1 is not supported.")
        
        # pack RGB images with neighboring slices
        if image.shape[1] == 1:
            image = image.expand(3, -1, -1, -1)
        else:
            image1 = torch.cat((image[:, 1:2], image[:,:-1]), dim=1)
            image2 = torch.cat((image[:,1:], image[:,-2:-1]), dim=1)
            image = torch.cat((image, image1, image2), dim=0)
        image = image.transpose(0, 1)  # D, 3, H, W
        
        # Encode prompts (keep no_grad here for efficiency)
        with torch.no_grad():
            prompt_features = model.sem_seg_head.encode_prompts(text=text, eval=True)
            P = int(prompt_features["num_prompts"][0])
            prompt_features["grounding_tokens"] = prompt_features["grounding_tokens"].repeat(1, slice_batch_size, 1)
            prompt_features["class_emb"] = prompt_features["class_emb"].repeat(slice_batch_size, 1)
        
        n_slices = image.shape[0]
        start = 0
        pred_gmasks = None
        object_existence = None
        edge_masks = None
        
        while start < n_slices:
            end = min(start + slice_batch_size, n_slices)
            image_batch = (image[start:end] - model.pixel_mean.mean()) / model.pixel_std.mean()
            
            # Forward with gradients
            image_embedding = model.backbone(image_batch)
            
            if end-start < slice_batch_size:
                np_batch = (end-start) * P
                pf_batch = {
                    "grounding_tokens": prompt_features["grounding_tokens"][:,:np_batch],
                    "class_emb": prompt_features["class_emb"][:np_batch],
                    "num_prompts": prompt_features["num_prompts"],
                    "logit_scale": prompt_features["logit_scale"],
                }
            else:
                pf_batch = prompt_features
            
            outputs = model.sem_seg_head.forward(
                image_features=image_embedding, prompt_features=pf_batch
            )
            
            if model.edge_queries > 0:
                outputs["edge_masks"] = outputs["pred_gmasks"][:, -model.edge_queries:].mean(dim=1, keepdim=True)
                outputs["pred_gmasks"] = outputs["pred_gmasks"][:, :-model.edge_queries]
            else:
                outputs["edge_masks"] = None
            
            if model.convolute_outputs:
                outputs["pred_gmasks"] = model.convolution_procedure(image_batch, outputs["pred_gmasks"])
            else:
                outputs["pred_gmasks"] = outputs["pred_gmasks"].mean(dim=1, keepdim=True)
            
            if start == 0:
                pred_gmasks = outputs["pred_gmasks"]
                object_existence = outputs["object_existence"]
                if model.edge_queries > 0:
                    edge_masks = outputs["edge_masks"]
            else:
                pred_gmasks = torch.cat((pred_gmasks, outputs["pred_gmasks"]), dim=0)
                object_existence = torch.cat((object_existence, outputs["object_existence"]), dim=0)
                if model.edge_queries > 0:
                    edge_masks = torch.cat((edge_masks, outputs["edge_masks"]), dim=0)
            
            start += slice_batch_size
        
        pred_gmasks = pred_gmasks.view(n_slices, P, pred_gmasks.shape[-2], pred_gmasks.shape[-1])
        pred_gmasks = pred_gmasks.transpose(0, 1)
        object_existence = object_existence.view(n_slices, P).transpose(0, 1)
        
        if model.edge_queries > 0:
            edge_masks = edge_masks.view(n_slices, P, edge_masks.shape[-2], edge_masks.shape[-1])
            edge_masks = edge_masks.transpose(0, 1)
        
        outputs_final = {
            "pred_gmasks": pred_gmasks,
            "object_existence": object_existence,
        }
        if model.edge_queries > 0:
            outputs_final["edge_masks"] = edge_masks
        outputs_final["inference_time"] = time.time() - t0
        
        return {"predictions": outputs_final}
    
    model.forward_eval_with_grad = forward_eval_with_grad
    return model

# Config
NUM_EPOCHS = 100
LEARNING_RATE = 1e-5
SAVE_DIR = "output/finetune_3d"
# TODO: Update these paths to your dataset
IMG_PATH = "examples/imgs/CT_AMOS_amos_0018.npz"
GT_PATH = "examples/gts/CT_AMOS_amos_0018.npz"

TARGET_ORGANS = {
    11: "right adrenal gland",
    12: "left adrenal gland",
}

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
    print("BiomedParse 3D Fine-tuning - Small Organs v5")
    print("Using patched eval mode with gradients")
    print("="*60)
    
    # Load model
    print("\n[1/4] Loading 3D model...")
    GlobalHydra.instance().clear()
    initialize(config_path="configs/model", job_name="finetune3d", version_base=None)
    cfg = compose(config_name="biomedparse_3D")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    model.load_pretrained("biomedparse_v2.ckpt")
    model = model.to(device)
    model = patch_model_for_training(model)
    print("   Model loaded and patched!")
    
    # Load data
    print("\n[2/4] Loading data...")
    img_data = np.load(IMG_PATH, allow_pickle=True)
    gt_data = np.load(GT_PATH, allow_pickle=True)
    
    image = img_data["imgs"]
    gts = gt_data["gts"]
    text_prompts = img_data["text_prompts"].item()
    
    start_slice, end_slice = 15, 45
    image = image[start_slice:end_slice]
    gts = gts[start_slice:end_slice]
    
    print(f"   Volume shape: {image.shape}")
    print(f"   Input range: {image.min()}-{image.max()}")
    
    imgs = torch.from_numpy(image.astype(np.float32)).unsqueeze(0).to(device)
    
    gt_masks = {}
    organ_texts = {}
    for organ_id, organ_name in TARGET_ORGANS.items():
        gt = (gts == organ_id).astype(np.float32)
        gt_tensor = torch.from_numpy(gt)
        voxels = (gt > 0).sum()
        gt_masks[organ_name] = gt_tensor
        text = text_prompts.get(str(organ_id), organ_name)
        organ_texts[organ_name] = text
        print(f"   {organ_name}: {voxels} voxels")
    
    print(f"   Input shape: {imgs.shape}")
    
    # Evaluate original
    print("\n[3/4] Evaluating ORIGINAL model...")
    model.eval()
    orig_scores = {}
    with torch.no_grad():
        for organ_name, gt in gt_masks.items():
            gt = gt.to(device)
            text = organ_texts[organ_name]
            results = model({"image": imgs, "text": text}, mode="eval")
            pred = results["predictions"]["pred_gmasks"][0]
            
            if pred.shape != gt.shape:
                pred = F.interpolate(pred.unsqueeze(0).unsqueeze(0), 
                                    size=gt.shape, 
                                    mode="trilinear", 
                                    align_corners=False).squeeze()
            
            dice = compute_dice(pred, gt)
            orig_scores[organ_name] = dice
            print(f"   {organ_name}: {dice*100:.1f}%")
    
    orig_mean = np.mean(list(orig_scores.values())) * 100
    print(f"   Average: {orig_mean:.1f}%")
    
    # Fine-tune
    print(f"\n[4/4] Training for {NUM_EPOCHS} epochs...")
    
    for name, param in model.named_parameters():
        if "backbone" in name:
            param.requires_grad = False
        else:
            param.requires_grad = True
    
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"   Trainable params: {trainable/1e6:.1f}M / {total/1e6:.1f}M")
    
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=LEARNING_RATE, 
        weight_decay=0.01
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=NUM_EPOCHS)
    
    best_dice = orig_mean
    organ_list = list(TARGET_ORGANS.values())
    
    for epoch in range(NUM_EPOCHS):
        model.train()
        epoch_loss = 0
        
        for organ_name in organ_list:
            gt = gt_masks[organ_name].to(device)
            text = organ_texts[organ_name]
            
            optimizer.zero_grad()
            
            # Use patched forward with gradients
            results = model.forward_eval_with_grad({"image": imgs, "text": text})
            pred = results["predictions"]["pred_gmasks"][0]
            
            if pred.shape != gt.shape:
                pred = F.interpolate(pred.unsqueeze(0).unsqueeze(0), 
                                    size=gt.shape, 
                                    mode="trilinear", 
                                    align_corners=False).squeeze()
            
            loss = dice_loss(pred, gt)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
        
        scheduler.step()
        avg_loss = epoch_loss / len(organ_list)
        
        if (epoch + 1) % 10 == 0:
            model.eval()
            test_dices = []
            with torch.no_grad():
                for organ_name in organ_list:
                    gt = gt_masks[organ_name].to(device)
                    text = organ_texts[organ_name]
                    results = model({"image": imgs, "text": text}, mode="eval")
                    pred = results["predictions"]["pred_gmasks"][0]
                    
                    if pred.shape != gt.shape:
                        pred = F.interpolate(pred.unsqueeze(0).unsqueeze(0), 
                                            size=gt.shape, 
                                            mode="trilinear", 
                                            align_corners=False).squeeze()
                    
                    dice = compute_dice(pred, gt)
                    test_dices.append(dice)
            
            mean_dice = np.mean(test_dices) * 100
            print(f"   Epoch {epoch+1:3d}: Loss={avg_loss:.4f}, Dice={mean_dice:.1f}%")
            
            if mean_dice > best_dice:
                best_dice = mean_dice
                torch.save(model.state_dict(), f"{SAVE_DIR}/biomedparse_3d_adrenal_best.pt")
                print(f"   >>> New best: {best_dice:.1f}%")
    
    # Final
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    if os.path.exists(f"{SAVE_DIR}/biomedparse_3d_adrenal_best.pt"):
        model.load_state_dict(torch.load(f"{SAVE_DIR}/biomedparse_3d_adrenal_best.pt"))
    model.eval()
    
    print(f"\n{Organ:<25} {Before:>10} {After:>10} {Improve:>10}")
    print("-"*55)
    
    improvements = []
    final_scores = {}
    with torch.no_grad():
        for organ_name in organ_list:
            gt = gt_masks[organ_name].to(device)
            text = organ_texts[organ_name]
            results = model({"image": imgs, "text": text}, mode="eval")
            pred = results["predictions"]["pred_gmasks"][0]
            
            if pred.shape != gt.shape:
                pred = F.interpolate(pred.unsqueeze(0).unsqueeze(0), 
                                    size=gt.shape, 
                                    mode="trilinear", 
                                    align_corners=False).squeeze()
            
            new_dice = compute_dice(pred, gt) * 100
            old_dice = orig_scores[organ_name] * 100
            improve = new_dice - old_dice
            improvements.append(improve)
            final_scores[organ_name] = new_dice
            
            print(f"{organ_name:<25} {old_dice:>9.1f}% {new_dice:>9.1f}% {improve:>+9.1f}%")
    
    print("-"*55)
    avg_before = np.mean([orig_scores[n]*100 for n in organ_list])
    avg_after = np.mean([final_scores[n] for n in organ_list])
    avg_improve = np.mean(improvements)
    print(f"{Average:<25} {avg_before:>9.1f}% {avg_after:>9.1f}% {avg_improve:>+9.1f}%")
    print(f"\n✅ Best model saved to: {SAVE_DIR}/biomedparse_3d_adrenal_best.pt")

if __name__ == "__main__":
    main()
