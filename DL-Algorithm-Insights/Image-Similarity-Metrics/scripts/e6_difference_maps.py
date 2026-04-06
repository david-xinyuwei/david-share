"""
E6: Visual Difference Maps — What does each metric "see"?
Generates side-by-side heatmaps showing MSE, SSIM, LPIPS spatial differences
between Teacher and Student images.

Author: Xinyu Wei
"""
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim
import lpips
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

print("=" * 70)
print("E6: VISUAL DIFFERENCE MAPS — WHAT EACH METRIC SEES")
print("=" * 70)

# Load images
teacher = np.array(Image.open("/home/azureuser/FINAL_teacher_40steps_cfg4.png").convert("RGB"))
student = np.array(Image.open("/home/azureuser/FINAL_shift_05_16steps_cfg4.png").convert("RGB"))
if student.shape != teacher.shape:
    student = np.array(Image.fromarray(student).resize((teacher.shape[1], teacher.shape[0])))
print(f"Teacher: {teacher.shape}, Student: {student.shape}")

# 1. MSE difference map (per-pixel squared error, averaged across channels)
mse_map = np.mean((teacher.astype(np.float32) - student.astype(np.float32)) ** 2, axis=2)
print(f"MSE map: shape={mse_map.shape}, range=[{mse_map.min():.1f}, {mse_map.max():.1f}]")

# 2. SSIM difference map (1 - local_ssim at each pixel)
_, ssim_full = ssim(teacher, student, channel_axis=2, data_range=255, full=True)
ssim_map = 1.0 - np.mean(ssim_full, axis=2)  # Convert to "difference" (higher = more different)
print(f"SSIM diff map: shape={ssim_map.shape}, range=[{ssim_map.min():.4f}, {ssim_map.max():.4f}]")

# 3. LPIPS spatial difference map
lpips_fn = lpips.LPIPS(net='vgg', spatial=True)
t_teacher = torch.from_numpy(teacher).permute(2,0,1).unsqueeze(0).float() / 127.5 - 1.0
t_student = torch.from_numpy(student).permute(2,0,1).unsqueeze(0).float() / 127.5 - 1.0
with torch.no_grad():
    lpips_spatial = lpips_fn(t_teacher, t_student)
lpips_map = lpips_spatial.squeeze().numpy()
# LPIPS spatial output is smaller due to VGG pooling, resize to match
lpips_map_resized = np.array(Image.fromarray(lpips_map).resize((teacher.shape[1], teacher.shape[0]), Image.BILINEAR))
print(f"LPIPS map: shape={lpips_map_resized.shape}, range=[{lpips_map_resized.min():.4f}, {lpips_map_resized.max():.4f}]")

# 4. Create visualization
fig, axes = plt.subplots(2, 3, figsize=(20, 14))
fig.suptitle('What Each Metric "Sees": Teacher (40-step) vs Student (16-step, shift=0.5)\n'
             'Virtual Try-On Output, 1024x1024, Qwen-Image-Edit on H100',
             fontsize=16, fontweight='bold')

# Row 1: Original images + absolute pixel difference
axes[0,0].imshow(teacher)
axes[0,0].set_title('Teacher (40 steps, CFG=4)', fontsize=13, fontweight='bold')
axes[0,0].axis('off')

axes[0,1].imshow(student)
axes[0,1].set_title('Student (16 steps, shift=0.5, CFG=4)', fontsize=13, fontweight='bold')
axes[0,1].axis('off')

# Absolute difference (amplified 5x for visibility)
abs_diff = np.clip(np.abs(teacher.astype(np.float32) - student.astype(np.float32)) * 5, 0, 255).astype(np.uint8)
axes[0,2].imshow(abs_diff)
axes[0,2].set_title('Pixel Difference (5x amplified)', fontsize=13, fontweight='bold')
axes[0,2].axis('off')

# Row 2: Three metric heatmaps
im1 = axes[1,0].imshow(mse_map, cmap='hot', interpolation='bilinear')
axes[1,0].set_title(f'MSE Map\n(per-pixel squared error)\nGlobal MSE = {np.mean(mse_map)/255**2:.6f}',
                     fontsize=12, fontweight='bold')
axes[1,0].axis('off')
plt.colorbar(im1, ax=axes[1,0], fraction=0.046)

im2 = axes[1,1].imshow(ssim_map, cmap='hot', interpolation='bilinear')
axes[1,1].set_title(f'SSIM Difference Map\n(1 - local SSIM, higher = more different)\nGlobal SSIM = {1-np.mean(ssim_map):.4f}',
                     fontsize=12, fontweight='bold')
axes[1,1].axis('off')
plt.colorbar(im2, ax=axes[1,1], fraction=0.046)

im3 = axes[1,2].imshow(lpips_map_resized, cmap='hot', interpolation='bilinear')
axes[1,2].set_title(f'LPIPS Spatial Map\n(VGG perceptual difference)\nGlobal LPIPS = {lpips_map_resized.mean():.4f}',
                     fontsize=12, fontweight='bold')
axes[1,2].axis('off')
plt.colorbar(im3, ax=axes[1,2], fraction=0.046)

plt.tight_layout()
outpath = '/home/azureuser/e6_difference_maps.png'
plt.savefig(outpath, dpi=150, bbox_inches='tight')
print(f"\nSaved: {outpath}")
print("=" * 70)
print("E6 COMPLETED — Visual difference maps generated!")
print("=" * 70)
