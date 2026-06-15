"""
FID (Fréchet Inception Distance) Demo

Demonstrates FID's strengths and limitations through three experiments:
1. Engine alignment: paired images with small perturbations (FID vs SSIM)
2. Model capability: unpaired image sets of different quality (FID shines)
3. Sample sensitivity: FID variance across different sample sizes

Requirements:
    pip install torch torchvision scipy numpy Pillow matplotlib scikit-image

Usage:
    python fid_demo.py                     # Run all experiments
    python fid_demo.py --experiment 1      # Run specific experiment (1/2/3)
    python fid_demo.py --save-images       # Save visualization images

Author: Xinyu Wei (魏新宇)
"""

import argparse
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import torch
import torchvision.transforms as transforms
from torchvision.models import inception_v3, Inception_V3_Weights
from scipy import linalg
from skimage.metrics import structural_similarity as ssim
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# ─── FID Core Implementation ─────────────────────────────────────────

def get_inception_model(device='cpu'):
    """Load InceptionV3 model for feature extraction (pool3 layer, 2048-d)."""
    model = inception_v3(weights=Inception_V3_Weights.DEFAULT)
    # Remove the final classification layer — we want pool3 features (2048-d)
    model.fc = torch.nn.Identity()
    model.eval()
    return model.to(device)


def extract_features(images_np, model, device='cpu', batch_size=32):
    """
    Extract 2048-d Inception features from a list of numpy images.

    Args:
        images_np: list of numpy arrays (H, W, 3), values in [0, 255]
        model: InceptionV3 model with fc replaced by Identity
        device: 'cpu' or 'cuda'
        batch_size: batch size for inference

    Returns:
        numpy array of shape (N, 2048)
    """
    preprocess = transforms.Compose([
        transforms.Resize((299, 299)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    all_features = []
    for i in range(0, len(images_np), batch_size):
        batch_imgs = images_np[i:i + batch_size]
        batch_tensors = torch.stack([
            preprocess(Image.fromarray(img)) for img in batch_imgs
        ]).to(device)

        with torch.no_grad():
            features = model(batch_tensors)

        all_features.append(features.cpu().numpy())

    return np.concatenate(all_features, axis=0)


def compute_fid(features_real, features_gen):
    """
    Compute FID between two sets of Inception features.

    FID = ||μ₁ - μ₂||² + Tr(Σ₁ + Σ₂ - 2√(Σ₁Σ₂))

    Args:
        features_real: numpy array (N1, 2048) — reference set
        features_gen: numpy array (N2, 2048) — generated set

    Returns:
        FID score (float, lower = more similar distributions)
    """
    mu1 = np.mean(features_real, axis=0)
    mu2 = np.mean(features_gen, axis=0)
    sigma1 = np.cov(features_real, rowvar=False)
    sigma2 = np.cov(features_gen, rowvar=False)

    # Mean difference
    diff = mu1 - mu2
    mean_term = np.dot(diff, diff)

    # Matrix square root via eigendecomposition (more stable than scipy sqrtm)
    # covmean = sqrt(sigma1 @ sigma2)
    covmean, _ = linalg.sqrtm(sigma1 @ sigma2, disp=False)

    # Numerical stability: remove imaginary components from rounding errors
    if np.iscomplexobj(covmean):
        covmean = covmean.real

    trace_term = np.trace(sigma1 + sigma2 - 2 * covmean)

    return float(mean_term + trace_term)


# ─── Image Generation Utilities ───────────────────────────────────────

def generate_varied_images(n, size=(256, 256), quality='high', seed=42):
    """
    Generate a set of synthetic images with controlled quality/diversity.

    Args:
        n: number of images to generate
        size: image dimensions
        quality: 'high' (clean shapes) or 'low' (noisy, distorted)
        seed: random seed for reproducibility

    Returns:
        list of numpy arrays (H, W, 3)
    """
    np.random.seed(seed)
    images = []

    for i in range(n):
        img = Image.new('RGB', size, (240, 240, 240))
        draw = ImageDraw.Draw(img)

        # Background gradient (varies per image)
        base_r = np.random.randint(180, 255)
        base_g = np.random.randint(180, 255)
        base_b = np.random.randint(200, 255)
        for y in range(size[1]):
            r = int(base_r + (255 - base_r) * y / size[1])
            g = int(base_g - 40 * y / size[1])
            b = int(base_b - 60 * y / size[1])
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))

        # Random geometric shapes
        n_shapes = np.random.randint(3, 7)
        for _ in range(n_shapes):
            shape_type = np.random.choice(['rect', 'ellipse', 'polygon'])
            color = tuple(np.random.randint(30, 230, 3).tolist())
            x1, y1 = np.random.randint(10, size[0] - 80), np.random.randint(10, size[1] - 80)
            x2, y2 = x1 + np.random.randint(30, 80), y1 + np.random.randint(30, 80)

            if shape_type == 'rect':
                draw.rectangle([x1, y1, x2, y2], fill=color, outline=tuple(max(0, c - 40) for c in color), width=2)
            elif shape_type == 'ellipse':
                draw.ellipse([x1, y1, x2, y2], fill=color, outline=tuple(max(0, c - 40) for c in color), width=2)
            else:
                pts = [(x1, y2), ((x1 + x2) // 2, y1), (x2, y2)]
                draw.polygon(pts, fill=color, outline=tuple(max(0, c - 40) for c in color))

        # Quality degradation for 'low' quality
        if quality == 'low':
            # Add noise
            arr = np.array(img).astype(np.float32)
            noise = np.random.normal(0, 30, arr.shape)
            arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            # Add blur
            if np.random.random() > 0.5:
                img = img.filter(ImageFilter.GaussianBlur(radius=2))

        images.append(np.array(img))

    return images


def add_perturbation(images_np, perturbation_type='slight_noise', intensity=1.0):
    """Add controlled perturbation to a set of images (simulating engine differences)."""
    perturbed = []
    for img in images_np:
        arr = img.astype(np.float32)
        if perturbation_type == 'slight_noise':
            noise = np.random.normal(0, 3 * intensity, arr.shape)
            arr = np.clip(arr + noise, 0, 255)
        elif perturbation_type == 'color_shift':
            arr[:, :, 0] = np.clip(arr[:, :, 0] + 5 * intensity, 0, 255)  # Slight red shift
            arr[:, :, 2] = np.clip(arr[:, :, 2] - 3 * intensity, 0, 255)
        elif perturbation_type == 'blur':
            pil_img = Image.fromarray(arr.astype(np.uint8))
            pil_img = pil_img.filter(ImageFilter.GaussianBlur(radius=0.5 * intensity))
            arr = np.array(pil_img).astype(np.float32)
        elif perturbation_type == 'heavy_noise':
            noise = np.random.normal(0, 25 * intensity, arr.shape)
            arr = np.clip(arr + noise, 0, 255)
        perturbed.append(arr.astype(np.uint8))
    return perturbed


# ─── Experiment 1: Engine Alignment (FID vs SSIM on paired images) ────

def experiment_1_engine_alignment(model, device, save_images=False, image_dir='images'):
    """
    Scenario: Same inputs through two inference engines with minor numerical diffs.
    Shows that SSIM handles this well (per-image) while FID also works but is overkill.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Engine Alignment — Paired Image Comparison")
    print("Scenario: Same model, two engines, slight numerical differences")
    print("=" * 70)

    n_images = 100
    reference_images = generate_varied_images(n_images, seed=42)

    perturbations = [
        ('identical', 'none', 0),
        ('slight_noise', 'slight_noise', 1.0),
        ('color_shift', 'color_shift', 1.0),
        ('slight_blur', 'blur', 1.0),
        ('heavy_noise', 'heavy_noise', 1.0),
    ]

    results = []
    print(f"\nReference set: {n_images} images (256×256)")
    print(f"{'Perturbation':<18} {'FID':>10} {'Avg SSIM':>10} {'Avg LPIPS*':>12}  Interpretation")
    print("-" * 80)

    for name, ptype, intensity in perturbations:
        if ptype == 'none':
            perturbed_images = [img.copy() for img in reference_images]
        else:
            perturbed_images = add_perturbation(reference_images, ptype, intensity)

        # Compute FID (distribution-level)
        feat_ref = extract_features(reference_images, model, device)
        feat_per = extract_features(perturbed_images, model, device)
        fid_score = compute_fid(feat_ref, feat_per)

        # Compute average SSIM (image-level, paired)
        ssim_scores = []
        for ref, per in zip(reference_images, perturbed_images):
            s = ssim(ref, per, channel_axis=2, data_range=255)
            ssim_scores.append(s)
        avg_ssim = np.mean(ssim_scores)

        interp = ""
        if fid_score < 1:
            interp = "Identical distributions"
        elif fid_score < 10:
            interp = "Very similar (engine-level diff)"
        elif fid_score < 50:
            interp = "Noticeable difference"
        else:
            interp = "Significant difference"

        print(f"{name:<18} {fid_score:>10.2f} {avg_ssim:>10.4f} {'N/A':>12}  {interp}")
        results.append((name, fid_score, avg_ssim))

    print("\n* LPIPS omitted here (see similarity_demo.py for LPIPS experiments)")
    print("\nKey takeaway: For paired images (same input → two outputs),")
    print("SSIM gives per-image answers. FID gives one batch-level number.")
    print("Both detect the same trends, but SSIM is more informative here.")

    if save_images:
        _save_experiment1_chart(results, image_dir)

    return results


def _save_experiment1_chart(results, image_dir):
    """Save a dual-axis chart comparing FID and SSIM across perturbations."""
    names = [r[0] for r in results]
    fids = [r[1] for r in results]
    ssims = [r[2] for r in results]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    x = np.arange(len(names))
    width = 0.35

    bars1 = ax1.bar(x - width / 2, fids, width, label='FID (lower=better)', color='#0078D4', alpha=0.8)
    ax1.set_ylabel('FID Score', color='#0078D4')
    ax1.tick_params(axis='y', labelcolor='#0078D4')

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, ssims, width, label='SSIM (higher=better)', color='#FF8C00', alpha=0.8)
    ax2.set_ylabel('SSIM Score', color='#FF8C00')
    ax2.set_ylim(0, 1.05)
    ax2.tick_params(axis='y', labelcolor='#FF8C00')

    ax1.set_xticks(x)
    ax1.set_xticklabels(names, rotation=15, ha='right')
    ax1.set_title('Experiment 1: FID vs SSIM on Paired Images (Engine Alignment)')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    os.makedirs(image_dir, exist_ok=True)
    path = os.path.join(image_dir, 'fid_experiment1_engine_alignment.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n📊 Chart saved: {path}")


# ─── Experiment 2: Model Capability (FID's killer scenario) ──────────

def experiment_2_model_capability(model, device, save_images=False, image_dir='images'):
    """
    Scenario: Two different models generate images from different prompts.
    No paired relationship — SSIM cannot be used, FID is the only option.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Model Capability — Unpaired Distribution Comparison")
    print("Scenario: Different models, no paired images, compare overall quality")
    print("=" * 70)

    n_images = 100

    # "Reference": high-quality diverse images (ground truth distribution)
    real_images = generate_varied_images(n_images, quality='high', seed=100)

    # "Good model": similar quality and diversity to reference
    good_model_images = generate_varied_images(n_images, quality='high', seed=200)

    # "Bad model": noisy, blurry, less diverse
    bad_model_images = generate_varied_images(n_images, quality='low', seed=300)

    # "Collapsed model": same image repeated (mode collapse)
    single_image = generate_varied_images(1, quality='high', seed=400)
    collapsed_images = [single_image[0].copy() for _ in range(n_images)]

    comparisons = [
        ('Good model', good_model_images),
        ('Bad model', bad_model_images),
        ('Collapsed model', collapsed_images),
    ]

    print(f"\nReference: {n_images} high-quality synthetic images")
    print(f"{'Model':<20} {'FID':>10} {'Can use SSIM?':>15}  Interpretation")
    print("-" * 70)

    results = []
    feat_real = extract_features(real_images, model, device)

    for name, gen_images in comparisons:
        feat_gen = extract_features(gen_images, model, device)
        fid_score = compute_fid(feat_real, feat_gen)

        can_ssim = "NO (unpaired)"
        if fid_score < 30:
            interp = "Good generation quality"
        elif fid_score < 100:
            interp = "Noticeable quality gap"
        else:
            interp = "Poor quality or mode collapse"

        print(f"{name:<20} {fid_score:>10.2f} {can_ssim:>15}  {interp}")
        results.append((name, fid_score))

    print("\nKey takeaway: When images are UNPAIRED (different models, different prompts),")
    print("SSIM/LPIPS cannot be used. FID is the standard metric for this scenario.")
    print("Notice how mode collapse produces the highest FID — FID captures diversity.")

    if save_images:
        _save_experiment2_chart(results, image_dir)
        _save_experiment2_samples(real_images, good_model_images, bad_model_images,
                                 collapsed_images, image_dir)

    return results


def _save_experiment2_chart(results, image_dir):
    """Save FID comparison bar chart."""
    names = [r[0] for r in results]
    fids = [r[1] for r in results]

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ['#107C10', '#FF8C00', '#D13438']
    bars = ax.bar(names, fids, color=colors, alpha=0.85, edgecolor='gray')

    for bar, fid in zip(bars, fids):
        ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + 2,
                f'{fid:.1f}', ha='center', va='bottom', fontweight='bold')

    ax.set_ylabel('FID Score (lower = better)')
    ax.set_title('Experiment 2: FID Compares Unpaired Image Sets\n(SSIM cannot be used here)')
    ax.axhline(y=30, color='gray', linestyle='--', alpha=0.5, label='Good threshold')
    ax.legend()

    plt.tight_layout()
    os.makedirs(image_dir, exist_ok=True)
    path = os.path.join(image_dir, 'fid_experiment2_model_capability.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n📊 Chart saved: {path}")


def _save_experiment2_samples(real, good, bad, collapsed, image_dir):
    """Save sample images from each set for visual comparison."""
    fig, axes = plt.subplots(4, 5, figsize=(15, 12))
    sets = [('Reference (Real)', real), ('Good Model', good),
            ('Bad Model', bad), ('Collapsed Model', collapsed)]

    for row, (title, imgs) in enumerate(sets):
        axes[row, 0].set_ylabel(title, fontsize=12, fontweight='bold', rotation=0,
                                labelpad=100, ha='right', va='center')
        for col in range(5):
            axes[row, col].imshow(imgs[col])
            axes[row, col].axis('off')

    plt.suptitle('Sample Images from Each Set', fontsize=14, fontweight='bold')
    plt.tight_layout()
    path = os.path.join(image_dir, 'fid_experiment2_samples.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 Samples saved: {path}")


# ─── Experiment 3: Sample Size Sensitivity ────────────────────────────

def experiment_3_sample_sensitivity(model, device, save_images=False, image_dir='images'):
    """
    Scenario: Same distribution, but different sample sizes.
    Shows FID variance increases dramatically with smaller samples.
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Sample Size Sensitivity")
    print("Scenario: Same distributions, different sample sizes → FID variance")
    print("=" * 70)

    # Generate a large pool and subsample
    pool_size = 500
    pool_a = generate_varied_images(pool_size, quality='high', seed=1000)
    pool_b = generate_varied_images(pool_size, quality='high', seed=2000)

    sample_sizes = [10, 25, 50, 100, 200, 500]
    n_trials = 5  # Repeat each size multiple times to show variance

    print(f"\nTwo pools of {pool_size} images each (same quality, different seeds)")
    print(f"{'Sample Size':>12} {'FID (trials)':>50} {'Mean':>8} {'Std':>8}")
    print("-" * 90)

    results = []
    for n in sample_sizes:
        fids = []
        for trial in range(n_trials):
            # Random subsample
            idx_a = np.random.choice(pool_size, n, replace=False)
            idx_b = np.random.choice(pool_size, n, replace=False)
            subset_a = [pool_a[i] for i in idx_a]
            subset_b = [pool_b[i] for i in idx_b]

            feat_a = extract_features(subset_a, model, device)
            feat_b = extract_features(subset_b, model, device)

            # Need at least n > 2048 for stable covariance; add regularization for small n
            if n < 2048:
                # Regularize covariance for small sample sizes
                eps = 1e-6
                feat_a_cov = np.cov(feat_a, rowvar=False) + eps * np.eye(feat_a.shape[1])
                feat_b_cov = np.cov(feat_b, rowvar=False) + eps * np.eye(feat_b.shape[1])

                mu1, mu2 = np.mean(feat_a, axis=0), np.mean(feat_b, axis=0)
                diff = mu1 - mu2
                covmean, _ = linalg.sqrtm(feat_a_cov @ feat_b_cov, disp=False)
                if np.iscomplexobj(covmean):
                    covmean = covmean.real
                fid = float(np.dot(diff, diff) + np.trace(feat_a_cov + feat_b_cov - 2 * covmean))
            else:
                fid = compute_fid(feat_a, feat_b)

            fids.append(fid)

        fid_str = ", ".join(f"{f:.1f}" for f in fids)
        mean_fid = np.mean(fids)
        std_fid = np.std(fids)
        print(f"{n:>12} [{fid_str:>46}] {mean_fid:>8.1f} {std_fid:>8.1f}")
        results.append((n, fids, mean_fid, std_fid))

    print("\nKey takeaway: With 10-50 samples, FID fluctuates wildly between trials.")
    print("The official recommendation is ≥ 50,000 samples for stable FID.")
    print("With 50 samples (common in practice), treat FID as a rough indicator, not a precise metric.")

    if save_images:
        _save_experiment3_chart(results, image_dir)

    return results


def _save_experiment3_chart(results, image_dir):
    """Save sample size vs FID variance chart."""
    sizes = [r[0] for r in results]
    means = [r[2] for r in results]
    stds = [r[3] for r in results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: FID mean with error bars
    ax1.errorbar(sizes, means, yerr=stds, fmt='o-', color='#0078D4',
                 ecolor='#D13438', capsize=5, linewidth=2, markersize=8)
    ax1.set_xlabel('Sample Size')
    ax1.set_ylabel('FID Score')
    ax1.set_title('FID vs Sample Size\n(error bars = std across 5 trials)')
    ax1.set_xscale('log')
    ax1.grid(True, alpha=0.3)

    # Right: FID standard deviation
    ax2.bar([str(s) for s in sizes], stds, color='#D13438', alpha=0.8)
    ax2.set_xlabel('Sample Size')
    ax2.set_ylabel('FID Standard Deviation')
    ax2.set_title('FID Variance Decreases with More Samples')

    plt.tight_layout()
    os.makedirs(image_dir, exist_ok=True)
    path = os.path.join(image_dir, 'fid_experiment3_sample_sensitivity.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n📊 Chart saved: {path}")


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='FID Demo — Three Experiments')
    parser.add_argument('--experiment', type=int, choices=[1, 2, 3], default=None,
                        help='Run specific experiment (1/2/3). Default: run all')
    parser.add_argument('--save-images', action='store_true',
                        help='Save visualization charts to images/')
    parser.add_argument('--device', type=str, default='cpu',
                        help='Device: cpu or cuda (default: cpu)')
    parser.add_argument('--image-dir', type=str, default='images',
                        help='Directory for saving images (default: images/)')
    args = parser.parse_args()

    print("=" * 70)
    print("FID (Fréchet Inception Distance) Demo")
    print("=" * 70)
    print(f"Device: {args.device}")
    print("Loading InceptionV3 model...")

    model = get_inception_model(args.device)
    print("Model loaded.\n")

    experiments = {
        1: experiment_1_engine_alignment,
        2: experiment_2_model_capability,
        3: experiment_3_sample_sensitivity,
    }

    if args.experiment:
        experiments[args.experiment](model, args.device, args.save_images, args.image_dir)
    else:
        for exp_num, exp_func in experiments.items():
            exp_func(model, args.device, args.save_images, args.image_dir)

    print("\n" + "=" * 70)
    print("SUMMARY: When to Use Which Metric")
    print("=" * 70)
    print("""
┌─────────────────────────────────────────────────────────────────────┐
│  Question                              │  Metric    │  Min Samples │
├─────────────────────────────────────────┼────────────┼──────────────┤
│  "Are these two images the same?"      │  SSIM      │  1 pair      │
│  "Do they look the same to humans?"    │  LPIPS     │  1 pair      │
│  "Is this model as good as that one?"  │  FID       │  50+ (≥50K   │
│                                        │            │  recommended)│
│  "Does the output match the prompt?"   │  CLIP Score│  1 pair      │
└─────────────────────────────────────────┴────────────┴──────────────┘
""")


if __name__ == '__main__':
    main()
