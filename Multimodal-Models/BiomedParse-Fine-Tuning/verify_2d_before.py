import torch
import cv2
import numpy as np
import sys
import os

# Add src to path to find model
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from src.model.biomedparse import BiomedParseModel
except ImportError:
    # Try without src if in root
    sys.path.append(os.getcwd())
    from model.biomedparse import BiomedParseModel

# Initialize model
# Note: The model definition might require specific args. 
# Based on visualize_2d.py, it uses hydra. 
# But here we manually instantiate.
# We need to check __init__ args of BiomedParseModel.
# Assuming defaults or simple args work for now.
model = BiomedParseModel(
    lab_threshold=0.5,
    pixel_mean=[123.675, 116.280, 103.530],
    pixel_std=[58.395, 57.120, 57.375],
    device='cuda'
)
model.to('cuda')
model.eval()

# Load checkpoint
print("Loading checkpoint...")
checkpoint = torch.load('biomedparse_v2.ckpt', map_location='cpu')
state_dict = checkpoint['state_dict']

# Fix keys: strip "model." prefix
new_state_dict = {}
for k, v in state_dict.items():
    if k.startswith('model.'):
        new_key = k[6:] # Remove "model."
        new_state_dict[new_key] = v
    else:
        new_state_dict[k] = v

# Load state dict
try:
    missing, unexpected = model.load_state_dict(new_state_dict, strict=False)
    print(f"Missing keys: {len(missing)}")
    print(f"Unexpected keys: {len(unexpected)}")
    
    # Check if critical weights are missing
    critical_missing = [k for k in missing if 'backbone' in k or 'sem_seg_head' in k]
    if len(critical_missing) > 0:
        print(f"WARNING: {len(critical_missing)} critical keys are missing!")
        # print(f"Example missing: {critical_missing[:5]}")
    else:
        print("Critical weights loaded successfully.")

except Exception as e:
    print(f"Error loading state dict: {e}")
    sys.exit(1)

# Prepare input
image_path = 'slice025_left_kidney.png'
if not os.path.exists(image_path):
    print(f"Error: Image {image_path} not found.")
    sys.exit(1)

# Read image using cv2 directly
image = cv2.imread(image_path) # BGR
if image is None:
    print("Error: Failed to read image.")
    sys.exit(1)
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) # RGB

# Resize to 1024x1024 as per standard
image = cv2.resize(image, (1024, 1024))
image_tensor = torch.from_numpy(image.copy()).permute(2, 0, 1).cuda()

# Prepare prompts
prompts = ["left kidney"]

# Inference
print("Running inference...")
with torch.no_grad():
    # The model expects a list of dicts
    batched_inputs = [{
        "image": image_tensor,
        "height": 1024,
        "width": 1024,
        "prompts": prompts
    }]
    
    outputs = model(batched_inputs)

# Analyze output
pred_mask = outputs[0]['pred_masks'][0].cpu().numpy() # (H, W)
positive_pixels = np.sum(pred_mask > 0)
print(f"Positive pixels: {positive_pixels}")

if positive_pixels < 100:
    print("RESULT: Model predicts NOTHING (matches screenshot).")
else:
    print("RESULT: Model predicts SOMETHING (screenshot might be wrong).")

