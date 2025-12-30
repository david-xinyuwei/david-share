import os
import sys
import torch
import torch.nn.functional as F
import numpy as np
import cv2
import hydra
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra

# Add current directory to path
sys.path.append(os.getcwd())

device = torch.device("cuda")

def load_model_correctly():
    GlobalHydra.instance().clear()
    # Initialize hydra with config path
    # Assuming configs are in configs/model relative to root
    initialize(config_path="configs/model", job_name="verify_before", version_base=None)
    cfg = compose(config_name="biomedparse")
    model = hydra.utils.instantiate(cfg, _convert_="object")
    
    print("Loading checkpoint: biomedparse_v2.ckpt")
    checkpoint = torch.load("biomedparse_v2.ckpt", map_location="cpu")
    
    # Check if state_dict is in checkpoint
    if 'state_dict' in checkpoint:
        state_dict = checkpoint['state_dict']
    else:
        state_dict = checkpoint
        
    # Fix keys: strip "model." prefix
    new_state_dict = {}
    for k, v in state_dict.items():
        if k.startswith('model.'):
            new_key = k[6:] # Remove "model."
            new_state_dict[new_key] = v
        else:
            new_state_dict[k] = v
            
    # Load state dict
    missing, unexpected = model.load_state_dict(new_state_dict, strict=False)
    print(f"Missing keys: {len(missing)}")
    print(f"Unexpected keys: {len(unexpected)}")
    
    # Check critical keys
    critical_missing = [k for k in missing if 'backbone' in k or 'sem_seg_head' in k]
    if len(critical_missing) > 0:
        print(f"WARNING: {len(critical_missing)} critical keys are missing!")
    else:
        print("Critical weights loaded successfully.")
        
    return model.to(device).eval()

def predict(model, img_tensor, text):
    with torch.no_grad(), torch.amp.autocast("cuda"):
        # Model expects inputs dict and mode
        results = model({"image": img_tensor, "text": text}, mode="eval")
        # Output structure might vary, checking visualize_2d.py
        # pred = results["predictions"]["pred_gmasks"][0]
        # But let's print keys to be sure if it fails
        return results

def main():
    # Load model
    try:
        model = load_model_correctly()
    except Exception as e:
        print(f"Failed to load model: {e}")
        sys.exit(1)
        
    # Load image
    image_path = 'slice025_left_kidney.png'
    if not os.path.exists(image_path):
        print(f"Image {image_path} not found.")
        sys.exit(1)
        
    image = cv2.imread(image_path)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = cv2.resize(image, (1024, 1024))
    
    # Normalize? visualize_2d.py doesn't show normalization in predict, 
    # but the model config might handle it. 
    # visualize_2d.py passes tensor.
    # Let's assume 0-255 input is expected if model handles mean/std.
    # But wait, visualize_2d.py imports PIL and converts to tensor?
    # visualize_2d.py: img_tensor = torch.from_numpy(img).permute(2,0,1).float().cuda()
    # It doesn't divide by 255.
    
    image_tensor = torch.from_numpy(image).permute(2, 0, 1).float().cuda()
    image_tensor = image_tensor.unsqueeze(0) # Add batch dim? 
    # visualize_2d.py: pred_resized = F.interpolate(pred.unsqueeze(0), size=img_tensor.shape[-2:], ...)
    # It seems visualize_2d.py passes (C, H, W) or (B, C, H, W)?
    # visualize_2d.py: results = model({"image": img_tensor, ...})
    # Usually models expect (B, C, H, W).
    # Let's try adding batch dim.
    
    text = ["left kidney"]
    
    print("Running inference...")
    try:
        results = predict(model, image_tensor, text)
        
        # Extract mask
        # visualize_2d.py: pred = results["predictions"]["pred_gmasks"][0]
        if "predictions" in results and "pred_gmasks" in results["predictions"]:
            pred = results["predictions"]["pred_gmasks"][0]
            # pred is likely logits
            pred_mask = (torch.sigmoid(pred) > 0.5).float().cpu().numpy()
            # Check dimensions
            if len(pred_mask.shape) == 3:
                pred_mask = pred_mask[0] # Take first class/channel
            
            positive_pixels = np.sum(pred_mask > 0)
            print(f"Positive pixels: {positive_pixels}")
            
            if positive_pixels < 100:
                print("RESULT: Model predicts NOTHING (matches screenshot).")
            else:
                print("RESULT: Model predicts SOMETHING (screenshot might be wrong).")
        else:
            print("Unexpected output structure:", results.keys())
            
    except Exception as e:
        print(f"Inference failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
