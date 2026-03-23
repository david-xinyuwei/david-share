"""
E7: One Example to Rule Them All — Four Modifications × Three Metrics
Generates a visual grid showing original image, 4 distortions, and 3 metric scores.
Uses real virtual try-on images from SHEIN project.

Author: Xinyu Wei
"""
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from skimage.metrics import structural_similarity as ssim
import lpips
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

print("=" * 70)
print("E7: ONE EXAMPLE — FOUR MODIFICATIONS × THREE METRICS")
print("=" * 70)

# Load real try-on image
img_pil = Image.open("/home/azureuser/FINAL_teacher_40steps_cfg4.png").convert("RGB")
# Crop center 512x512 for cleaner visualization
w, h = img_pil.size
left = (w - 512) // 2
top = (h - 512) // 2
img_pil = img_pil.crop((left, top, left + 512, top + 512))
orig = np.array(img_pil)
print(f"Image: {orig.shape}")

# Setup LPIPS
lpips_fn = lpips.LPIPS(net='vgg')

def to_lpips(x):
    return torch.from_numpy(x).permute(2,0,1).unsqueeze(0).float() / 127.5 - 1.0

def to_mse(x):
    return torch.from_numpy(x).permute(2,0,1).unsqueeze(0).float() / 255.0

def compute(a, b):
    mse_v = F.mse_loss(to_mse(a), to_mse(b)).item()
    ssim_v = ssim(a, b, channel_axis=2, data_range=255)
    with torch.no_grad():
        lpips_v = lpips_fn(to_lpips(a), to_lpips(b)).item()
    return mse_v, ssim_v, lpips_v

# Create 4 modifications
mods = {}

# M1: Brightness +30
bright = np.clip(orig.astype(np.int16) + 30, 0, 255).astype(np.uint8)
mods["Brightness +30\n(Screen brighter)"] = bright

# M2: Slight blur sigma=1.5
blurred = np.array(img_pil.filter(ImageFilter.GaussianBlur(radius=1.5)))
mods["Slight Blur sigma=1.5\n(Lens out of focus)"] = blurred

# M3: 1px shift
shifted = np.zeros_like(orig)
shifted[:, 1:, :] = orig[:, :-1, :]
shifted[:, 0, :] = orig[:, 0, :]
mods["1px Horizontal Shift\n(Imperceptible)"] = shifted

# M4: Color shift R+20 B-20
color_s = orig.copy()
color_s[:,:,0] = np.clip(orig[:,:,0].astype(np.int16) + 20, 0, 255).astype(np.uint8)
color_s[:,:,2] = np.clip(orig[:,:,2].astype(np.int16) - 20, 0, 255).astype(np.uint8)
mods["Color Shift R+20 B-20\n(Warm tone shift)"] = color_s

# Compute metrics
results = {}
for name, img in mods.items():
    mse_v, ssim_v, lpips_v = compute(orig, img)
    results[name] = (mse_v, ssim_v, lpips_v)
    print(f"  {name.split(chr(10))[0]:30s}  MSE={mse_v:.6f}  SSIM={ssim_v:.4f}  LPIPS={lpips_v:.4f}")

# Create visualization
fig, axes = plt.subplots(2, 5, figsize=(28, 12))
fig.suptitle('One Example: How Different Metrics React to the Same Modifications\n'
             'Real Virtual Try-On Image (512x512 center crop), H100 GPU',
             fontsize=18, fontweight='bold', y=0.98)

# Row 1: Images
axes[0, 0].imshow(orig)
axes[0, 0].set_title('Original\n(Reference)', fontsize=13, fontweight='bold', color='#107C10')
axes[0, 0].axis('off')

colors_map = {'Brightness': '#FF8C00', 'Slight Blur': '#800080', '1px': '#0078D4', 'Color': '#DC143C'}
for idx, (name, img) in enumerate(mods.items()):
    ax = axes[0, idx + 1]
    ax.imshow(img)
    short = name.split('\n')[0]
    color = '#333'
    for k, c in colors_map.items():
        if k in short:
            color = c
            break
    ax.set_title(name, fontsize=11, fontweight='bold', color=color)
    ax.axis('off')

# Row 2: Difference images (amplified 10x)
axes[1, 0].text(0.5, 0.5, 'Pixel Difference\n(10x amplified)\n\nBrighter = \nMore different',
                transform=axes[1,0].transAxes, ha='center', va='center',
                fontsize=13, fontweight='bold', color='#555')
axes[1, 0].axis('off')

for idx, (name, img) in enumerate(mods.items()):
    ax = axes[1, idx + 1]
    diff = np.clip(np.abs(orig.astype(np.float32) - img.astype(np.float32)) * 10, 0, 255).astype(np.uint8)
    ax.imshow(diff)

    mse_v, ssim_v, lpips_v = results[name]

    # Color code: green = good, red = bad/fooled
    def score_color(val, metric):
        if metric == 'MSE':
            return '#DC143C' if val > 0.01 else ('#FF8C00' if val > 0.003 else '#107C10')
        elif metric == 'SSIM':
            return '#107C10' if val > 0.9 else ('#FF8C00' if val > 0.5 else '#DC143C')
        else:  # LPIPS
            return '#107C10' if val < 0.05 else ('#FF8C00' if val < 0.2 else '#DC143C')

    txt = f"MSE: {mse_v:.4f}\nSSIM: {ssim_v:.3f}\nLPIPS: {lpips_v:.3f}"
    mc = score_color(mse_v, 'MSE')
    sc = score_color(ssim_v, 'SSIM')
    lc = score_color(lpips_v, 'LPIPS')

    ax.text(0.02, 0.98, f"MSE:  {mse_v:.4f}", transform=ax.transAxes,
            fontsize=12, fontweight='bold', color=mc, va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))
    ax.text(0.02, 0.85, f"SSIM: {ssim_v:.3f}", transform=ax.transAxes,
            fontsize=12, fontweight='bold', color=sc, va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))
    ax.text(0.02, 0.72, f"LPIPS:{lpips_v:.3f}", transform=ax.transAxes,
            fontsize=12, fontweight='bold', color=lc, va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))

    # Mark which metric is "fooled"
    short = name.split('\n')[0]
    if 'Brightness' in short:
        ax.text(0.98, 0.02, 'MSE over-reacts!', transform=ax.transAxes,
                fontsize=11, fontweight='bold', color='white', ha='right',
                bbox=dict(boxstyle='round', facecolor='#DC143C', alpha=0.9))
    elif 'Blur' in short:
        ax.text(0.98, 0.02, 'MSE misses it!', transform=ax.transAxes,
                fontsize=11, fontweight='bold', color='white', ha='right',
                bbox=dict(boxstyle='round', facecolor='#DC143C', alpha=0.9))
    elif '1px' in short:
        ax.text(0.98, 0.02, 'SSIM over-reacts!', transform=ax.transAxes,
                fontsize=11, fontweight='bold', color='white', ha='right',
                bbox=dict(boxstyle='round', facecolor='#DC143C', alpha=0.9))
    elif 'Color' in short:
        ax.text(0.98, 0.02, 'SSIM is fooled!', transform=ax.transAxes,
                fontsize=11, fontweight='bold', color='white', ha='right',
                bbox=dict(boxstyle='round', facecolor='#DC143C', alpha=0.9))

    ax.axis('off')

plt.tight_layout(rect=[0, 0, 1, 0.95])
outpath = '/home/azureuser/e7_one_example.png'
plt.savefig(outpath, dpi=150, bbox_inches='tight')
print(f"\nSaved: {outpath}")
print("=" * 70)
