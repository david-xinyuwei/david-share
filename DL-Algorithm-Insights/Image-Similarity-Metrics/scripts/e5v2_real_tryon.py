"""
E5v2: Real SHEIN Try-On Image — Metric Blind Spot + Teacher vs Student
Uses actual diffusion model output images from SHEIN virtual try-on experiments.

Author: Xinyu Wei
"""
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image, ImageFilter
from skimage.metrics import structural_similarity as ssim
import lpips
import json, os

print("=" * 70)
print("E5v2: REAL SHEIN TRY-ON — METRICS ON PRODUCTION IMAGES")
print("=" * 70)

# Load LPIPS
lpips_fn = lpips.LPIPS(net='vgg')

def to_lpips(img_np):
    return torch.from_numpy(img_np).permute(2,0,1).unsqueeze(0).float() / 127.5 - 1.0

def to_mse(img_np):
    return torch.from_numpy(img_np).permute(2,0,1).unsqueeze(0).float() / 255.0

def compute_all(a_np, b_np, label):
    mse_v = F.mse_loss(to_mse(a_np), to_mse(b_np)).item()
    ssim_v = ssim(a_np, b_np, channel_axis=2, data_range=255)
    with torch.no_grad():
        lpips_v = lpips_fn(to_lpips(a_np), to_lpips(b_np)).item()
    print(f"  {label:40s}  MSE={mse_v:.6f}  SSIM={ssim_v:.4f}  LPIPS={lpips_v:.4f}")
    return {"label": label, "MSE": round(mse_v, 6), "SSIM": round(ssim_v, 4), "LPIPS": round(lpips_v, 4)}

# ============================================================
# Part 1: Teacher vs Student (real diffusion outputs)
# ============================================================
print("\n--- Part 1: Teacher (40-step) vs Student (various configs) ---")
print(f"  {'Comparison':40s}  {'MSE':>10s}  {'SSIM':>6s}  {'LPIPS':>6s}")
print(f"  {'-'*40}  {'-'*10}  {'-'*6}  {'-'*6}")

results = []
teacher = np.array(Image.open("/home/azureuser/FINAL_teacher_40steps_cfg4.png").convert("RGB"))

# Teacher vs itself
results.append(compute_all(teacher, teacher, "Teacher vs Teacher (baseline)"))

# Teacher vs different student configs
for name, path in [
    ("Student shift=0.5, 16step, CFG=4", "/home/azureuser/FINAL_shift_05_16steps_cfg4.png"),
    ("Student shift=1.0, 16step, CFG=4", "/home/azureuser/FINAL_shift_10_16steps_cfg4.png"),
    ("Student shift=1.1, 16step, CFG=4", "/home/azureuser/FINAL_shift_11_16steps_cfg4.png"),
    ("Student shift=0.5, 16step, CFG=1", "/home/azureuser/FINAL_shift_05_16steps_cfg1.png"),
    ("Student shift=1.0, 16step, CFG=1", "/home/azureuser/FINAL_shift_10_16steps_cfg1.png"),
]:
    if os.path.exists(path):
        student = np.array(Image.open(path).convert("RGB"))
        # Resize if needed
        if student.shape != teacher.shape:
            student = np.array(Image.fromarray(student).resize((teacher.shape[1], teacher.shape[0])))
        results.append(compute_all(teacher, student, name))

# ============================================================
# Part 2: Distortion blind spots on real try-on image
# ============================================================
print("\n--- Part 2: Distortion Blind Spots on Teacher Image ---")
print(f"  {'Distortion':40s}  {'MSE':>10s}  {'SSIM':>6s}  {'LPIPS':>6s}")
print(f"  {'-'*40}  {'-'*10}  {'-'*6}  {'-'*6}")

img_pil = Image.fromarray(teacher)

# D1: 1px shift
shifted = np.zeros_like(teacher)
shifted[:, 1:, :] = teacher[:, :-1, :]
shifted[:, 0, :] = teacher[:, 0, :]
results.append(compute_all(teacher, shifted, "D1: 1px horizontal shift"))

# D2: Slight blur
blurred = np.array(img_pil.filter(ImageFilter.GaussianBlur(radius=1)))
results.append(compute_all(teacher, blurred, "D2: Gaussian blur sigma=1"))

# D3: Heavy blur
blurred_h = np.array(img_pil.filter(ImageFilter.GaussianBlur(radius=3)))
results.append(compute_all(teacher, blurred_h, "D3: Gaussian blur sigma=3"))

# D4: Brightness +30
bright = np.clip(teacher.astype(np.int16) + 30, 0, 255).astype(np.uint8)
results.append(compute_all(teacher, bright, "D4: Brightness +30"))

# D5: Noise sigma=15
np.random.seed(42)
noisy = np.clip(teacher.astype(np.float32) + np.random.randn(*teacher.shape) * 15, 0, 255).astype(np.uint8)
results.append(compute_all(teacher, noisy, "D5: Gaussian noise sigma=15"))

# D6: Color shift
color_s = teacher.copy()
color_s[:,:,0] = np.clip(teacher[:,:,0].astype(np.int16) + 20, 0, 255).astype(np.uint8)
color_s[:,:,2] = np.clip(teacher[:,:,2].astype(np.int16) - 20, 0, 255).astype(np.uint8)
results.append(compute_all(teacher, color_s, "D6: Color shift R+20 B-20"))

# D7: JPEG q=10
from io import BytesIO
buf = BytesIO()
img_pil.save(buf, format='JPEG', quality=10)
buf.seek(0)
jpeg = np.array(Image.open(buf).convert("RGB"))
if jpeg.shape != teacher.shape:
    jpeg = np.array(Image.fromarray(jpeg).resize((teacher.shape[1], teacher.shape[0])))
results.append(compute_all(teacher, jpeg, "D7: JPEG compression q=10"))

# Save
with open("/home/azureuser/e5v2_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\nImage used: FINAL_teacher_40steps_cfg4.png ({teacher.shape})")
print(f"Results saved to /home/azureuser/e5v2_results.json")
print("=" * 70)
print("E5v2 COMPLETED — Real SHEIN try-on images verified!")
print("=" * 70)
