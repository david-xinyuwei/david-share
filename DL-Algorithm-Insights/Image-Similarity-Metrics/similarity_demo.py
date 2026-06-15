"""
Image Similarity Metrics Demo — SSIM vs LPIPS

Demonstrates the difference between structural (SSIM) and perceptual (LPIPS)
image similarity metrics using synthetic image distortions.

Requirements:
    pip install torch torchvision lpips scikit-image Pillow matplotlib numpy

Usage:
    python similarity_demo.py                    # Run all demos
    python similarity_demo.py --demo shift       # Run specific demo
    python similarity_demo.py --save-images      # Save comparison images

Author: Xinyu Wei (魏新宇)
"""

import argparse
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from skimage.metrics import structural_similarity as ssim
import torch
import lpips
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def create_test_image(size=(256, 256), seed=42):
    """Create a synthetic test image with geometric shapes and textures."""
    np.random.seed(seed)
    img = Image.new('RGB', size, (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(size[1]):
        r = int(200 + 55 * y / size[1])
        g = int(220 - 40 * y / size[1])
        b = int(255 - 80 * y / size[1])
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))

    # Geometric shapes
    draw.rectangle([30, 30, 100, 100], fill=(220, 50, 50), outline=(180, 30, 30), width=2)
    draw.ellipse([130, 40, 220, 130], fill=(50, 150, 220), outline=(30, 120, 200), width=2)
    draw.polygon([(60, 150), (120, 230), (10, 230)], fill=(50, 200, 50), outline=(30, 160, 30))

    # Texture pattern
    for i in range(0, size[0], 8):
        for j in range(150, size[1], 8):
            if (i + j) % 16 == 0:
                c = np.random.randint(180, 230)
                draw.rectangle([i, j, i + 4, j + 4], fill=(c, c, c))

    return img


def apply_distortions(img):
    """Apply various distortions to test image."""
    arr = np.array(img)

    distortions = {}

    # 1. Pixel shift (1px right) — SSIM sensitive, LPIPS insensitive
    shifted = np.roll(arr, 1, axis=1)
    distortions['1px_shift'] = Image.fromarray(shifted)

    # 2. Gaussian blur — both detect, different sensitivity
    distortions['blur_slight'] = img.filter(ImageFilter.GaussianBlur(radius=1.5))
    distortions['blur_heavy'] = img.filter(ImageFilter.GaussianBlur(radius=4.0))

    # 3. Brightness change — SSIM very sensitive, LPIPS less so
    bright = np.clip(arr.astype(np.int16) + 30, 0, 255).astype(np.uint8)
    distortions['brightness+30'] = Image.fromarray(bright)

    # 4. Gaussian noise — both detect
    noise = np.random.normal(0, 15, arr.shape).astype(np.int16)
    noisy = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    distortions['noise_σ15'] = Image.fromarray(noisy)

    # 5. Color shift — change hue
    color_shifted = arr.copy()
    color_shifted[:, :, 0] = np.clip(arr[:, :, 0].astype(np.int16) + 40, 0, 255)
    color_shifted[:, :, 2] = np.clip(arr[:, :, 2].astype(np.int16) - 40, 0, 255)
    distortions['color_shift'] = Image.fromarray(color_shifted)

    # 6. JPEG compression artifacts
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=10)
    buf.seek(0)
    distortions['jpeg_q10'] = Image.open(buf).copy()

    # 7. Local change (small region replaced)
    local = arr.copy()
    local[100:140, 100:140] = [255, 0, 0]  # Red patch
    distortions['local_patch'] = Image.fromarray(local)

    return distortions


def compute_ssim(img1, img2):
    """Compute SSIM between two PIL images."""
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    # Ensure same size
    if arr1.shape != arr2.shape:
        img2 = img2.resize(img1.size, Image.LANCZOS)
        arr2 = np.array(img2)
    score = ssim(arr1, arr2, channel_axis=2, data_range=255)
    return score


def compute_lpips(img1, img2, loss_fn):
    """Compute LPIPS between two PIL images."""
    def to_tensor(img):
        arr = np.array(img).astype(np.float32) / 255.0
        # LPIPS expects [-1, 1] range
        arr = arr * 2.0 - 1.0
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
        return tensor

    t1 = to_tensor(img1)
    t2 = to_tensor(img2)

    # Ensure same size
    if t1.shape != t2.shape:
        t2 = torch.nn.functional.interpolate(t2, size=t1.shape[2:], mode='bilinear')

    with torch.no_grad():
        score = loss_fn(t1, t2)
    return score.item()


def run_comparison(save_images=False, output_dir='images'):
    """Run full SSIM vs LPIPS comparison on all distortions."""
    print("=" * 70)
    print("  Image Similarity Metrics Demo — SSIM vs LPIPS")
    print("=" * 70)

    # Create test image
    print("\n[1/3] Creating test image...")
    original = create_test_image()

    # Apply distortions
    print("[2/3] Applying 7 types of distortions...")
    distortions = apply_distortions(original)

    # Initialize LPIPS (VGG backbone)
    print("[3/3] Loading LPIPS model (VGG, first run downloads ~60MB)...")
    loss_fn = lpips.LPIPS(net='vgg', verbose=False)

    # Compute metrics
    print("\n" + "-" * 70)
    print(f"{'Distortion':<20} {'SSIM':>8} {'LPIPS':>8}  Interpretation")
    print("-" * 70)

    results = {}
    for name, distorted in distortions.items():
        s = compute_ssim(original, distorted)
        l = compute_lpips(original, distorted, loss_fn)
        results[name] = {'ssim': s, 'lpips': l}

        # Interpretation
        if s > 0.95 and l < 0.05:
            interp = "Both agree: nearly identical"
        elif s < 0.85 and l > 0.15:
            interp = "Both agree: clearly different"
        elif s < 0.90 and l < 0.05:
            interp = "⚡ SSIM says different, LPIPS says same!"
        elif s > 0.90 and l > 0.10:
            interp = "⚡ SSIM says same, LPIPS says different!"
        else:
            interp = "Moderate difference"

        print(f"{name:<20} {s:>8.4f} {l:>8.4f}  {interp}")

    print("-" * 70)

    # Key insight
    print("\n📊 Key Takeaways:")
    print("  • 1px shift:    SSIM drops significantly, LPIPS barely changes")
    print("                  → SSIM is pixel-aligned, LPIPS is perception-aligned")
    print("  • Brightness:   SSIM drops a lot, LPIPS changes moderately")
    print("                  → SSIM treats brightness change as structural damage")
    print("  • Heavy blur:   Both detect it, but LPIPS penalizes more")
    print("                  → Blur destroys texture details that VGG captures")
    print("  • JPEG q=10:    Both penalize, LPIPS especially harsh")
    print("                  → Block artifacts are perceptually very obvious")

    # SSIM direction reminder
    print("\n⚠️  Score Direction Reminder:")
    print("  SSIM:  1.0 = identical, 0.0 = completely different  (higher = more similar)")
    print("  LPIPS: 0.0 = identical, 1.0 = completely different  (lower  = more similar)")

    if save_images:
        save_comparison_grid(original, distortions, results, output_dir)

    return results


def save_comparison_grid(original, distortions, results, output_dir):
    """Save a comparison grid image showing all distortions with scores."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    n = len(distortions) + 1  # +1 for original
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(16, 4 * rows))
    axes = axes.flatten()

    # Plot original
    axes[0].imshow(np.array(original))
    axes[0].set_title('Original\nSSIM=1.000 / LPIPS=0.000', fontsize=10, fontweight='bold')
    axes[0].axis('off')

    # Plot distortions
    for idx, (name, img) in enumerate(distortions.items(), 1):
        axes[idx].imshow(np.array(img))
        s = results[name]['ssim']
        l = results[name]['lpips']
        axes[idx].set_title(f'{name}\nSSIM={s:.3f} / LPIPS={l:.3f}', fontsize=10)
        axes[idx].axis('off')

    # Hide unused subplots
    for idx in range(n, len(axes)):
        axes[idx].axis('off')

    plt.suptitle('SSIM vs LPIPS — Same Distortion, Different Scores', fontsize=14, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(output_dir, 'comparison_grid.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n✅ Comparison grid saved to: {path}")


def demo_shift():
    """Focused demo: Why 1px shift breaks SSIM but not LPIPS."""
    print("\n🔬 Demo: 1px Pixel Shift")
    print("   This shows the fundamental difference between SSIM and LPIPS.\n")

    img = create_test_image()
    arr = np.array(img)
    shifted = Image.fromarray(np.roll(arr, 1, axis=1))

    loss_fn = lpips.LPIPS(net='vgg', verbose=False)

    s = compute_ssim(img, shifted)
    l = compute_lpips(img, shifted, loss_fn)

    print(f"   Original vs 1px-shifted:")
    print(f"   SSIM  = {s:.4f}  (dropped from 1.0 — 'something changed!')")
    print(f"   LPIPS = {l:.4f}  (barely moved — 'looks the same to me')")
    print(f"\n   → SSIM is a 'pixel ruler': if pixels don't line up, score drops.")
    print(f"   → LPIPS is an 'art critic': if it looks the same, score stays low.")


def demo_blur_vs_noise():
    """Demo: Blur and noise affect metrics differently."""
    print("\n🔬 Demo: Blur vs Noise")
    print("   Same 'amount' of change, very different perceptual impact.\n")

    img = create_test_image()
    blurred = img.filter(ImageFilter.GaussianBlur(radius=2.0))

    arr = np.array(img)
    noise = np.random.normal(0, 20, arr.shape).astype(np.int16)
    noisy = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))

    loss_fn = lpips.LPIPS(net='vgg', verbose=False)

    s_blur = compute_ssim(img, blurred)
    l_blur = compute_lpips(img, blurred, loss_fn)
    s_noise = compute_ssim(img, noisy)
    l_noise = compute_lpips(img, noisy, loss_fn)

    print(f"   {'Distortion':<15} {'SSIM':>8} {'LPIPS':>8}")
    print(f"   {'Blur r=2.0':<15} {s_blur:>8.4f} {l_blur:>8.4f}")
    print(f"   {'Noise σ=20':<15} {s_noise:>8.4f} {l_noise:>8.4f}")
    print(f"\n   → Blur is perceptually worse (higher LPIPS) even if SSIM is similar")
    print(f"   → Because blur destroys texture details that human eyes notice")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SSIM vs LPIPS comparison demo')
    parser.add_argument('--demo', choices=['all', 'shift', 'blur'],
                        default='all', help='Which demo to run')
    parser.add_argument('--save-images', action='store_true',
                        help='Save comparison grid image')
    parser.add_argument('--output-dir', default='images',
                        help='Directory to save images')
    args = parser.parse_args()

    if args.demo == 'shift':
        demo_shift()
    elif args.demo == 'blur':
        demo_blur_vs_noise()
    else:
        run_comparison(save_images=args.save_images, output_dir=args.output_dir)
        print("\n" + "=" * 70)
        print("  Run individual demos:")
        print("    python similarity_demo.py --demo shift")
        print("    python similarity_demo.py --demo blur")
        print("    python similarity_demo.py --save-images")
        print("=" * 70)
