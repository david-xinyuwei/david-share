#!/usr/bin/env python3
"""
BiomedParse Inference Script - Generate comparison visualizations
Supports both 2D and 3D inference with original vs fine-tuned model comparison

Author: Xinyu Wei (Microsoft AI and Apps GBB)
Usage:
    # 2D comparison
    python inference.py --mode 2d \
        --image /path/to/image.png \
        --prompts "liver,spleen,kidney" \
        --original_ckpt biomedparse_v2.ckpt \
        --finetuned_ckpt finetuned_model.ckpt \
        --output_dir ./results

    # 3D comparison  
    python inference.py --mode 3d \
        --data_file /path/to/volume.npz \
        --original_ckpt biomedparse_v2.ckpt \
        --finetuned_ckpt finetuned_model.ckpt \
        --output_dir ./results
"""

import argparse
import os
import sys
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend


def setup_biomedparse_path(biomedparse_dir):
    """Add BiomedParse directory to Python path"""
    if biomedparse_dir not in sys.path:
        sys.path.insert(0, biomedparse_dir)
    parent_dir = os.path.dirname(biomedparse_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)


def load_model_v1(checkpoint_path, biomedparse_dir):
    """Load BiomedParse v1 model for 2D inference"""
    setup_biomedparse_path(biomedparse_dir)
    
    from modeling.BaseModel import BaseModel
    from modeling import build_model
    from utilities.distributed import init_distributed
    from utilities.arguments import load_opt_from_config_files
    
    config_path = os.path.join(biomedparse_dir, "configs/biomedparse_inference.yaml")
    opt = load_opt_from_config_files([config_path])
    opt = init_distributed(opt)
    
    model = BaseModel(opt, build_model(opt)).from_pretrained(checkpoint_path).eval().cuda()
    
    from utilities.constants import BIOMED_CLASSES
    with torch.no_grad():
        model.model.sem_seg_head.predictor.lang_encoder.get_text_embeddings(
            BIOMED_CLASSES + ["background"], is_eval=True
        )
    
    return model


def load_model_v2(checkpoint_path, biomedparse_dir):
    """Load BiomedParse v2 model for 3D inference"""
    setup_biomedparse_path(biomedparse_dir)
    
    import hydra
    from hydra import compose
    from hydra.core.global_hydra import GlobalHydra
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    GlobalHydra.instance().clear()
    config_path = os.path.join(biomedparse_dir, "configs/model")
    hydra.initialize(config_path=config_path, job_name="inference")
    cfg = compose(config_name="biomedparse_3D")
    
    model = hydra.utils.instantiate(cfg, _convert_="object")
    model.load_pretrained(checkpoint_path)
    model = model.to(device).eval()
    
    return model


def infer_2d_v1(model, image, prompts, biomedparse_dir):
    """Run 2D inference with v1 model"""
    setup_biomedparse_path(biomedparse_dir)
    from inference_utils.inference import interactive_infer_image
    pred_masks = interactive_infer_image(model, image, prompts)
    return pred_masks


def infer_3d_v2(model, npz_path, biomedparse_dir):
    """Run 3D inference with v2 model"""
    setup_biomedparse_path(biomedparse_dir)
    from utils import process_input, process_output
    from inference import postprocess, merge_multiclass_masks
    
    device = next(model.parameters()).device
    
    npz_data = np.load(npz_path, allow_pickle=True)
    imgs = npz_data["imgs"]
    text_prompts = npz_data["text_prompts"].item()
    
    ids = [int(k) for k in text_prompts.keys() if k != "instance_label"]
    ids.sort()
    text = "[SEP]".join([text_prompts[str(i)] for i in ids])
    
    imgs_processed, pad_width, padded_size, valid_axis = process_input(imgs, 512)
    imgs_processed = imgs_processed.to(device).int()
    
    input_tensor = {
        "image": imgs_processed.unsqueeze(0),
        "text": [text],
    }
    
    with torch.no_grad():
        output = model(input_tensor, mode="eval", slice_batch_size=4)
    
    mask_preds = output["predictions"]["pred_gmasks"]
    mask_preds = F.interpolate(mask_preds, size=(512, 512), mode="bicubic", 
                               align_corners=False, antialias=True)
    mask_preds = postprocess(mask_preds, output["predictions"]["object_existence"])
    mask_preds = merge_multiclass_masks(mask_preds, ids)
    mask_preds = process_output(mask_preds, pad_width, padded_size, valid_axis)
    
    return mask_preds, text_prompts, ids


def calculate_dice(pred, gt):
    """Calculate Dice coefficient"""
    pred_binary = (pred > 0.5).astype(np.float32)
    gt_binary = (gt > 0).astype(np.float32)
    
    intersection = np.sum(pred_binary * gt_binary)
    union = np.sum(pred_binary) + np.sum(gt_binary)
    
    if union == 0:
        return 1.0 if np.sum(gt_binary) == 0 else 0.0
    
    return 2.0 * intersection / union


def visualize_2d_comparison(image, gt_mask, pred_original, pred_finetuned, 
                            prompt, output_path):
    """Generate 2D comparison visualization"""
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    
    axes[0].imshow(image)
    axes[0].set_title("Input Image", fontsize=14)
    axes[0].axis('off')
    
    axes[1].imshow(image)
    if gt_mask is not None:
        axes[1].imshow(gt_mask, alpha=0.5, cmap='Reds')
    axes[1].set_title("Ground Truth", fontsize=14)
    axes[1].axis('off')
    
    dice_orig = calculate_dice(pred_original, gt_mask) if gt_mask is not None else 0
    axes[2].imshow(image)
    axes[2].imshow(pred_original > 0.5, alpha=0.5, cmap='Blues')
    axes[2].set_title(f"Original Model\nDice: {dice_orig:.2%}", fontsize=14)
    axes[2].axis('off')
    
    dice_ft = calculate_dice(pred_finetuned, gt_mask) if gt_mask is not None else 0
    axes[3].imshow(image)
    axes[3].imshow(pred_finetuned > 0.5, alpha=0.5, cmap='Greens')
    axes[3].set_title(f"Fine-tuned Model\nDice: {dice_ft:.2%}", fontsize=14)
    axes[3].axis('off')
    
    plt.suptitle(f"Segmentation Comparison: {prompt}", fontsize=16, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")
    print(f"   Original Dice: {dice_orig:.2%}, Fine-tuned Dice: {dice_ft:.2%}")
    
    return dice_orig, dice_ft


def visualize_3d_comparison(imgs, gt_masks, pred_original, pred_finetuned,
                            text_prompts, organ_ids, output_path, max_slices=8):
    """Generate 3D comparison visualization (selected slices)"""
    n_slices = min(max_slices, imgs.shape[0])
    slice_indices = np.linspace(0, imgs.shape[0] - 1, n_slices, dtype=int)
    
    n_organs = len(organ_ids)
    fig, axes = plt.subplots(n_organs, n_slices, figsize=(n_slices * 3, n_organs * 3))
    
    if n_organs == 1:
        axes = axes.reshape(1, -1)
    
    for row, organ_id in enumerate(organ_ids):
        organ_name = text_prompts.get(str(organ_id), f"Organ {organ_id}")
        
        for col, slice_idx in enumerate(slice_indices):
            ax = axes[row, col]
            img_slice = imgs[slice_idx]
            ax.imshow(img_slice, cmap='gray')
            
            if gt_masks is not None:
                gt_slice = (gt_masks[slice_idx] == organ_id).astype(np.float32)
                ax.contour(gt_slice, colors='yellow', linewidths=1, levels=[0.5])
            
            if pred_original is not None:
                pred_orig_slice = (pred_original[slice_idx] == organ_id).astype(np.float32)
                ax.contour(pred_orig_slice, colors='red', linewidths=1, levels=[0.5])
            
            if pred_finetuned is not None:
                pred_ft_slice = (pred_finetuned[slice_idx] == organ_id).astype(np.float32)
                ax.contour(pred_ft_slice, colors='green', linewidths=1, levels=[0.5])
            
            ax.axis('off')
            
            if col == 0:
                ax.set_ylabel(organ_name.replace("CT scan of ", ""), fontsize=10)
            if row == 0:
                ax.set_title(f"Slice {slice_idx}", fontsize=10)
    
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='yellow', linewidth=2, label='Ground Truth'),
        Line2D([0], [0], color='red', linewidth=2, label='Original Model'),
        Line2D([0], [0], color='green', linewidth=2, label='Fine-tuned Model'),
    ]
    fig.legend(handles=legend_elements, loc='upper center', ncol=3, fontsize=12,
               bbox_to_anchor=(0.5, 1.02))
    
    plt.suptitle("3D Segmentation Comparison", fontsize=16, fontweight='bold', y=1.05)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")


def visualize_dice_comparison(results, output_path):
    """Generate bar chart comparing Dice scores"""
    organs = list(results.keys())
    original_scores = [results[o]['original'] for o in organs]
    finetuned_scores = [results[o]['finetuned'] for o in organs]
    
    x = np.arange(len(organs))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width/2, [s * 100 for s in original_scores], width, 
                   label='Original Model', color='#ff6b6b', edgecolor='black')
    bars2 = ax.bar(x + width/2, [s * 100 for s in finetuned_scores], width,
                   label='Fine-tuned Model', color='#4ecdc4', edgecolor='black')
    
    ax.set_xlabel('Organ', fontsize=12)
    ax.set_ylabel('Dice Score (%)', fontsize=12)
    ax.set_title('Segmentation Performance: Original vs Fine-tuned', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([o.replace("CT scan of ", "").replace("the ", "") for o in organs], 
                       rotation=45, ha='right')
    ax.legend()
    ax.set_ylim(0, 100)
    ax.grid(axis='y', alpha=0.3)
    
    for bar in bars1:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    
    for bar in bars2:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}%', xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha='center', va='bottom', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="BiomedParse Inference & Comparison")
    parser.add_argument("--mode", type=str, choices=["2d", "3d"], required=True,
                        help="Inference mode: 2d or 3d")
    parser.add_argument("--biomedparse_dir", type=str, default=".",
                        help="Path to BiomedParse repository")
    parser.add_argument("--image", type=str, help="Path to 2D image (PNG)")
    parser.add_argument("--mask", type=str, help="Path to ground truth mask (optional)")
    parser.add_argument("--data_file", type=str, help="Path to 3D NPZ file")
    parser.add_argument("--prompts", type=str, help="Comma-separated text prompts for 2D")
    parser.add_argument("--original_ckpt", type=str, required=True,
                        help="Path to original model checkpoint")
    parser.add_argument("--finetuned_ckpt", type=str, required=True,
                        help="Path to fine-tuned model checkpoint")
    parser.add_argument("--output_dir", type=str, default="./results",
                        help="Output directory for visualizations")
    
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    if args.mode == "2d":
        if not args.image or not args.prompts:
            parser.error("2D mode requires --image and --prompts")
        
        prompts = [p.strip() for p in args.prompts.split(",")]
        print(f"Loading image: {args.image}")
        print(f"Prompts: {prompts}")
        
        image = Image.open(args.image).convert('RGB')
        gt_mask = None
        if args.mask:
            gt_mask = np.array(Image.open(args.mask).convert('L')) > 0
        
        print("Loading original model...")
        model_orig = load_model_v1(args.original_ckpt, args.biomedparse_dir)
        
        print("Loading fine-tuned model...")
        model_ft = load_model_v1(args.finetuned_ckpt, args.biomedparse_dir)
        
        results = {}
        for prompt in prompts:
            print(f"\nProcessing: {prompt}")
            pred_orig = infer_2d_v1(model_orig, image, [prompt], args.biomedparse_dir)[0]
            pred_ft = infer_2d_v1(model_ft, image, [prompt], args.biomedparse_dir)[0]
            
            output_path = os.path.join(args.output_dir, f"2d_comparison_{prompt.replace(' ', '_')}.png")
            dice_orig, dice_ft = visualize_2d_comparison(
                np.array(image), gt_mask, pred_orig, pred_ft, prompt, output_path
            )
            results[prompt] = {'original': dice_orig, 'finetuned': dice_ft}
        
        if len(results) > 1:
            chart_path = os.path.join(args.output_dir, "2d_dice_comparison.png")
            visualize_dice_comparison(results, chart_path)
    
    elif args.mode == "3d":
        if not args.data_file:
            parser.error("3D mode requires --data_file")
        
        print(f"Loading 3D volume: {args.data_file}")
        
        npz_data = np.load(args.data_file, allow_pickle=True)
        imgs = npz_data["imgs"]
        gts = npz_data.get("gts", None)
        text_prompts = npz_data["text_prompts"].item()
        
        organ_ids = [int(k) for k in text_prompts.keys() if k != "instance_label"]
        organ_ids.sort()
        
        print(f"Volume shape: {imgs.shape}")
        print(f"Organs: {[text_prompts[str(i)] for i in organ_ids]}")
        
        print("Loading original model...")
        model_orig = load_model_v2(args.original_ckpt, args.biomedparse_dir)
        
        print("Loading fine-tuned model...")
        model_ft = load_model_v2(args.finetuned_ckpt, args.biomedparse_dir)
        
        print("\nRunning inference with original model...")
        pred_orig, _, _ = infer_3d_v2(model_orig, args.data_file, args.biomedparse_dir)
        
        print("Running inference with fine-tuned model...")
        pred_ft, _, _ = infer_3d_v2(model_ft, args.data_file, args.biomedparse_dir)
        
        output_path = os.path.join(args.output_dir, "3d_comparison.png")
        visualize_3d_comparison(imgs, gts, pred_orig, pred_ft, text_prompts, 
                                organ_ids, output_path)
        
        if gts is not None:
            results = {}
            print("\nDice Scores:")
            for organ_id in organ_ids:
                organ_name = text_prompts[str(organ_id)]
                gt_organ = (gts == organ_id).astype(np.float32)
                pred_orig_organ = (pred_orig == organ_id).astype(np.float32)
                pred_ft_organ = (pred_ft == organ_id).astype(np.float32)
                
                dice_orig = calculate_dice(pred_orig_organ, gt_organ)
                dice_ft = calculate_dice(pred_ft_organ, gt_organ)
                
                results[organ_name] = {'original': dice_orig, 'finetuned': dice_ft}
                print(f"   {organ_name}: {dice_orig:.2%} -> {dice_ft:.2%}")
            
            chart_path = os.path.join(args.output_dir, "3d_dice_comparison.png")
            visualize_dice_comparison(results, chart_path)
    
    print(f"\nAll results saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
