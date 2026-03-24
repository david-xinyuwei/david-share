# Image Similarity Metrics — MSE, SSIM, LPIPS, FID & CLIP Score

> **Five ways to compare images — pixel difference, structural matching, AI perception, statistical distribution, and semantic alignment.**

## What Is It?

Imagine you bought a piece of clothing online, and the seller used AI to generate a photo of "you wearing this outfit." Now the seller wants to upgrade the AI engine for faster generation, but worries the new engine might produce "lower quality" images. How do you judge? Manually comparing thousands of images is too slow, so we need **automated image quality metrics**.

The five metrics below do exactly this. Each independently answers "how similar are these two images (or two batches)?" but from completely different angles:

| | MSE | SSIM | LPIPS | FID | CLIP Score |
|---|---|---|---|---|---|
| **Approach** | Element-wise squared diff | Sliding window stats (2004) | VGG deep features (2018) | Inception feature dist. (2017) | CLIP cosine distance |
| **Compares** | Raw numerical diff | Luminance+Contrast+Structure | Multi-layer visual features | Feature distribution distance | Text-image semantic alignment |
| **Granularity** | Per-pixel/element | Per-image paired | Per-image paired | **Batch-level** (set vs set) | Per-image (text-image) |
| **Score direction** | **Low=similar** | **High=similar** (1.0=identical) | **Low=similar** (0.0=identical) | **Low=better** | **High=better** |
| **Needs neural net?** | ❌ Pure math | ❌ Pure math | ✅ VGG-16 | ✅ InceptionV3 | ✅ CLIP |

### Relationship Between Metrics

These five metrics are **independently implemented** (SSIM's formula contains no MSE, LPIPS doesn't call SSIM, FID doesn't call LPIPS), but they exist on an **abstraction spectrum from concrete to abstract**:

```
Pixel(MSE) → Structural(SSIM) → Perceptual(LPIPS) → Distribution(FID) → Semantic(CLIP)
  Concrete                                                                   Abstract
```

They are not hierarchically nested (higher levels don't depend on lower levels). They are five independent observation angles on the same question, but these angles have a progression from surface-level to deep-level — like a blood test, CT scan, and MRI: each independent, but progressing from surface to depth.

### Cross-Space Applicability (Core Decision Constraint)

Before looking at this chart, understand one key background: images exist in different "forms" inside a computer.

- **Pixel Space [H×W×3]**: The RGB image you see. Each pixel has 3 numbers (Red/Green/Blue, each 0-255), giving 256³ = 16.7 million possible colors.
- **Latent Space [h×w×4]**: A compressed "summary" after passing through a VAE encoder. Spatial dimensions shrink 8x (1024×1024 → 128×128), channels become 4. Humans can't interpret it, but it preserves the image's core information. Diffusion model training and inference happen in this space.
- **Velocity Field [h×w×4]**: The model's predicted "direction and speed from noise to image." Same shape as latent. The fine-tuning loss compares predicted velocity against ground truth velocity.

Here's the key: LPIPS, FID, and CLIP's backbone networks (VGG/Inception/CLIP) **only accept 3-channel RGB images**. Feed them a 4-channel latent tensor, and their first convolution layer crashes — channel count mismatch. MSE, being pure math, doesn't care about channel count and works everywhere.

The chart below makes this crystal clear:

![Cross-Space Applicability](images/cross_space_applicability.png)

**This chart determines which metrics can be used at each stage of Diffusion model development** — not a preference, but a hard physical-space constraint (see the "Cross-Space Applicability" section below for details).

### One Example That Explains All Metrics

The image below shows the same real diffusion model image generation image with four different modifications, evaluated by MSE, SSIM, and LPIPS. Each metric reacts completely differently — this is why you need to combine them, not rely on just one:


| Modification | Human Perception | MSE | SSIM | LPIPS | Who Got Fooled? |
|-------------|-----------------|:---:|:----:|:-----:|----------------|
| Brightness +30 | Can't tell | **0.0138**(⬆️) | 0.922 | 0.029 | MSE over-reacts |
| Slight blur | Obviously blurry | 0.0009 | 0.853 | **0.329**(⬆️) | MSE misses it |
| 1px shift | Can't tell | 0.0019 | **0.803**(⬇️) | 0.055 | SSIM over-reacts |
| Color shift R+20 | Noticeable | 0.0041 | **0.939**(⬆️) | 0.141 | SSIM is fooled |

**Conclusion**: Every metric has blind spots. MSE alone is fooled by brightness, SSIM alone is fooled by color shifts. **Combine them to avoid being fooled.**

## Why It Matters

In diffusion model inference optimization, we constantly face this question: **"I changed the engine/precision/compiler — did the output quality degrade?"**

Without objective metrics, you'd need humans to compare thousands of image pairs. SSIM and LPIPS automate this:

- **SSIM** → Quick engineering check: "Did my code change introduce pixel-level differences?"
- **LPIPS** → Quality assurance: "Does the output still look good to human eyes?"

**Real-world example (diffusion model image generation Benchmark)**:
- Compared 4 inference configurations (diffusers eager/compile × vLLM eager/compile)
- Each produced 50 generation images from identical inputs
- SSIM measured: are the outputs pixel-consistent across engines?
- Result: diffusers eager vs compile SSIM ≈ 0.93 (excellent — compile doesn't degrade quality)
- Cross-engine SSIM ≈ 0.91 (after correcting for resolution mismatch)

---

## Running on Azure

The included demo runs on **any machine with Python** (CPU only, ~30 seconds). No GPU or Azure subscription required to learn and experiment.

In production, we used these metrics to evaluate diffusion model inference quality on Azure GPU VMs:

| Item | Details |
|---|---|
| **SKU** | [Standard_NC80adis_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | 1× NVIDIA H100 NVL 94 GB |
| **Workload** | diffusion model image generation inference (50 samples × 4 engine configs) |
| **Role of SSIM/LPIPS** | Automated quality gate — compare outputs across engines without human review |

### Why Azure GPU VMs for Quality Evaluation

- **Diffusion model inference** generates the images; SSIM/LPIPS **measure** the quality
- Running inference on cloud GPUs (H100/A100) lets you benchmark at scale: 50–200 samples per config
- Pay-as-you-go: spin up, run inference + quality comparison, shut down
- The metrics themselves are lightweight — SSIM is pure math, LPIPS needs only a small VGG model

### What We Validated on Azure

| Comparison | SSIM | Conclusion |
|---|:---:|---|
| Same engine, eager vs `torch.compile` | ~0.93 | Compile does not degrade quality |
| Cross-engine, same resolution | ~0.91 | Minor numerical differences, acceptable |
| Cross-engine, resolution mismatch | ~0.88 | Resize artifacts lower score — fix resolution first |

These numbers gave us confidence to recommend `torch.compile` and alternative engines for production deployment on Azure.

---

## How It Works

Above, we used a chart and a table to see the big picture: "who can work where" and "what role each plays." Now let's open each one up and understand **how it computes internally**. We go from simplest to most complex:

1. **MSE** — Simplest, pure math, one-line formula
2. **SSIM** — One step beyond MSE, uses sliding windows to examine local structure
3. **LPIPS** — Lets a neural network simulate human visual judgment
4. **FID** — Doesn't look at individual images, compares statistical distributions of batches

### MSE — The All-Space Player

MSE (Mean Squared Error) is the most fundamental metric:

> **MSE = (1/n) × Σ(yᵢ - ŷᵢ)²**

Computes the squared difference for each element, then averages. Squaring penalizes large errors more heavily (a difference of 10 contributes 100, a difference of 1 contributes just 1).

**MSE's Core Role in Diffusion Models**:

During training, the model predicts noise or velocity, with the loss:

> **L = E[||ε_θ(xₜ, t) - ε||²]**

This is not an arbitrary choice — it's a **mathematical necessity derived from the variational lower bound (ELBO)**: maximizing the log-likelihood variational lower bound → minimizing per-step KL divergence → under Gaussian noise assumption → reduces exactly to MSE.

**Why not MAE (L1 Loss)?**

| | MSE (L2) | MAE (L1) |
|---|---------|---------|
| Gradient | Larger gradients for large errors, faster convergence | Constant gradient, slow convergence on large errors |
| Generation quality | Smoother, better detail | Can produce blur |
| Theory | Directly derived from ELBO | No variational inference support |

**MSE's unique advantage — works in all spaces**: MSE is pure math (element-wise squared difference), agnostic to input format. This makes it the only metric that works in all spaces (see Cross-Space Applicability below).

MSE is simple but has blind spots — it only measures how much the numbers differ, but "large numerical difference" does NOT mean "looks different." Example: uniformly brightening an image by 30 gives a high MSE (every pixel differs by 30), but humans can barely tell; conversely, slight blur gives a low MSE (pixel values change little), but humans clearly see the blur. SSIM and LPIPS address this: one examines structure mathematically, the other simulates human vision with a neural network. The diagram below compares their computation pipelines:

![SSIM vs LPIPS Pipeline](images/ssim_vs_lpips_pipeline.png)

### SSIM — The Mathematical Ruler

SSIM computes similarity across three dimensions:

> **SSIM(x, y) = l(x,y)ᵅ · c(x,y)ᵝ · s(x,y)ᵞ**

Where:

| Component | Formula | Meaning |
|:---------:|---------|--------|
| **l** (Luminance) | l(x,y) = (2μxμy + C₁) / (μx² + μy² + C₁) | Are the average brightnesses similar? |
| **c** (Contrast) | c(x,y) = (2σxσy + C₂) / (σx² + σy² + C₂) | Are the contrast ranges similar? |
| **s** (Structure) | s(x,y) = (σxy + C₃) / (σxσy + C₃) | Are the structural patterns similar? |

Constants C₁, C₂, C₃ prevent division by zero. Typically α = β = γ = 1.

**Key property**: SSIM operates on sliding windows (default 7×7 or 11×11), computing local statistics then averaging. This makes it more perceptual than MSE (which is purely pixel-wise), but still fundamentally **pixel-aligned** — a 1-pixel shift can significantly drop the score.

### LPIPS — The AI Art Critic

LPIPS feeds both images through a pretrained VGG-16 network and compares their deep features:

```mermaid
flowchart LR
    A["Image A"] --> VGG["VGG-16"]
    B["Image B"] --> VGG
    VGG --> L1["Layer 1: Edges"]
    VGG --> L2["Layer 2: Textures"]
    VGG --> L3["Layer 3: Shapes"]
    VGG --> L4["Layer 4: Parts"]
    VGG --> L5["Layer 5: Semantics"]
    L1 --> W["Weighted Sum"]
    L2 --> W
    L3 --> W
    L4 --> W
    L5 --> W
    W --> S["LPIPS Score"]

    style A fill:#e8f4ff,stroke:#0078D4
    style B fill:#e8f4ff,stroke:#0078D4
    style S fill:#e8ffe8,stroke:#107C10
```

Each VGG layer captures different levels of visual information:

| Layer | Captures | Example |
|:-----:|----------|---------|
| 1 | Edges, lines | "There's an edge here" |
| 2 | Textures, patterns | "This is a checkered pattern" |
| 3 | Local shapes | "This is a sleeve" |
| 4 | Object parts | "This is a T-shirt" |
| 5 | Semantic meaning | "A person wearing a T-shirt" |

The linear weights w₁ … w₅ (stored as `lin0.weight` through `lin4.weight`) are **learned** by training on human perceptual judgments — this is why LPIPS correlates better with human perception than SSIM.

In practice, these weights sometimes appear in diffusion model checkpoints when the training code uses LPIPS as a loss function and doesn't filter out the loss network weights during checkpoint saving. They are harmless — ignored during inference.

### VGG-16 — The Feature Extractor

VGG-16 (Visual Geometry Group, Oxford, 2014) is a classic CNN with 16 layers. Though no longer used for image classification (superseded by ResNet, ViT, etc.), its intermediate features are remarkably good at representing visual content. That's why LPIPS uses it as a "feature extractor" — like repurposing a retired detective's investigative instincts.

### FID — The Distribution Statistician

FID (Fréchet Inception Distance) takes a fundamentally different approach from SSIM and LPIPS. Instead of comparing two individual images, it compares two **sets** of images by measuring how similar their statistical distributions are in a learned feature space.

**How FID Works**:

1. Feed both image sets through InceptionV3 (a pretrained CNN), extracting 2048-dimensional features from the pool3 layer
2. Compute the mean vector (μ) and covariance matrix (Σ) of features for each set
3. Calculate the Fréchet distance between the two multivariate Gaussians:

> **FID = ||μ₁ - μ₂||² + Tr(Σ₁ + Σ₂ - 2√(Σ₁Σ₂))**

The first term measures how different the "average" images are. The second term measures how different the "variety" of images is (covariance captures diversity, style consistency, color distribution, etc.).

**Why FID exists (what SSIM/LPIPS cannot do)**:

| Scenario | SSIM/LPIPS | FID |
|----------|:----------:|:---:|
| "Are these two outputs from the same input identical?" | ✅ | Overkill |
| "Is Model A as good as Model B overall?" | ❌ (no paired images) | ✅ |
| "Did my model collapse to generating one image repeatedly?" | ❌ | ✅ |
| "Is this GAN training converging?" | ❌ | ✅ |

SSIM and LPIPS require **paired** images (image A₁ vs image B₁). FID compares **unpaired sets** — you just need two batches of images, no correspondence required.

**FID's limitations**:
- Requires **large sample sizes** for stable estimates (official recommendation: ≥ 50,000 images; in practice, ≥ 100 is a minimum)
- Uses InceptionV3 (2015) as the feature extractor — may not capture modern visual features well
- A single FID number doesn't tell you **which** images are good or bad
- Sensitive to image resolution and preprocessing (always resize to 299×299 consistently)

**What FID actually is — formula, model, or library?**

FID is often misunderstood as "a model" or "a library." It's actually three distinct layers:

| Layer | What It Is | Specifics |
|-------|-----------|----------|
| **Formula** | A mathematical distance metric | Fréchet Distance between two multivariate Gaussians |
| **Feature extractor** | A pretrained CNN model | InceptionV3 (Google 2015, trained on ImageNet) |
| **Implementation** | Various libraries/scripts | pytorch-fid, clean-fid, torchmetrics, or hand-written |

InceptionV3 only extracts features ("looks at images and outputs 2048 numbers"). The FID score itself is computed by a simple statistical formula on those features — the core calculation is ~5 lines of code:

```python
diff = mu1 - mu2
covmean = scipy.linalg.sqrtm(sigma1 @ sigma2)
fid = diff @ diff + np.trace(sigma1 + sigma2 - 2 * covmean)
```

Common FID libraries:

| Library | Install | Notes |
|---------|---------|-------|
| **pytorch-fid** | `pip install pytorch-fid` | Most popular, CLI tool |
| **clean-fid** | `pip install clean-fid` | Fixes resize inconsistencies in original implementation |
| **torchmetrics** | `pip install torchmetrics` | Unified metrics library, includes FID |
| **Hand-written** | torch + scipy | Like our `fid_demo.py` — full control, ~30 lines of core code |

**Is FID fair? — Fairness concerns**:

FID measures "how similar to the reference set," but **"similar to reference" ≠ "good."** Key fairness pitfalls:

| Concern | Explanation | Impact |
|---------|-------------|--------|
| **Inception bias** | InceptionV3 was trained on ImageNet (natural photos) | Features may be poor for fashion, medical, artistic images |
| **Reference set = ground truth** | FID only measures distance to reference, not intrinsic quality | If reference set is biased, FID inherits the bias |
| **Rewards memorization** | Perfectly copying the training set → FID ≈ 0 | That's overfitting, not quality! |
| **Sample size asymmetry** | Model A with 100 samples vs Model B with 10,000 → incomparable | Must use equal sample sizes |
| **Preprocessing differences** | Different resize methods to 299×299 affect scores | Two papers' FID numbers may not be comparable |
| **Insensitive to mode dropping** | Model drops 10% of categories but remaining 90% is great → FID may look fine | Cannot detect "partial omission" |

**FID fairness self-check**:

- [ ] Are reference and generated sets the **same sample size**? (≥100, ideally ≥50K)
- [ ] Is the **preprocessing identical** on both sides? (resize method, normalization)
- [ ] Does the reference set **represent your domain**? (ImageNet ≠ fashion generation)
- [ ] Are you **cross-validating** with other metrics? (SSIM + LPIPS + human review)

**Bottom line**: FID is a good **screening tool** ("is training converging?"), not a **judge** ("which model is best"). For fair evaluation, always combine FID with per-image metrics and human review.

---

## Cross-Space Applicability — The Core Decision Constraint

This is the most critical constraint when choosing metrics — **not a preference, but a hard physical-space limitation**:

| Metric | Pixel Space [H×W×3] | Latent Space [h×w×4] | Velocity Field [h×w×4] | Reason |
|--------|:---:|:---:|:---:|--------|
| **MSE** | ✅ | ✅ | ✅ | Pure math, works on any tensor |
| **SSIM** | ✅ | ⚠️ Computable but meaningless | ⚠️ Computable but meaningless | "Luminance/Contrast/Structure" designed for pixels; latent mean ≠ "luminance" |
| **LPIPS** | ✅ | ❌ | ❌ | VGG-16 only accepts 3-channel RGB input; latent is 4/16 channels with range [-3,3] |
| **FID** | ✅ | ❌ | ❌ | InceptionV3 only accepts 3-channel 299×299 RGB input |
| **CLIP Score** | ✅ | ❌ | ❌ | CLIP visual encoder only accepts 3-channel 224×224 RGB input |

**This table directly determines the loss/metric choice at each stage of Diffusion model development**:

| Stage | Working Space | Available Metrics |
|-------|--------------|-------------------|
| Fine-tuning (LoRA) | Latent/Velocity | MSE only (the only all-space player) |
| Distillation | Pixel space* | LPIPS (needs VAE decode to pixel space) |
| Inference quality evaluation | Pixel space | SSIM + LPIPS + FID (complementary) |
| Text-image alignment | Pixel space | CLIP Score |

*Distillation can use LPIPS because it adds a VAE decode step to convert latent back to RGB. But decode is expensive (memory + compute), making distillation more costly than regular fine-tuning.

**Supplementary metrics for velocity fields**:

In velocity space, Cosine Similarity complements MSE:
- MSE measures velocity **magnitude difference**
- Cosine Similarity measures velocity **directional consistency** (ignoring magnitude)
- Edge case: velocity direction correct but magnitude off by 10x → MSE spikes but Cosine ≈ 1

## Cross-Space Verification Experiments (H100 GPU, Real generation Images)

Validated every conclusion in the cross-space applicability table on Azure H100 NVL (NC40ads_H100_v5) with real diffusion model image generation images. Scripts: `cross_space_experiment.py` + `e5_blind_spots.py`.

### E1: LPIPS on 4-Channel Latent — Crash

```
[PIXEL]  LPIPS score: 0.6928  ✅ Works
[LATENT] Feeding [1, 4, 32, 32] to LPIPS...
[LATENT] CRASHED! ✅
Error: RuntimeError: size of tensor a (4) must match size of tensor b (3)
```

**Verdict**: VGG-16 Conv1 only accepts 3-channel input. 4-channel latent crashes immediately. Hard constraint, not preference.

### E2: SSIM on Latent — Computable but Meaningless

```
[PIXEL]  SSIM(cloth, model):          0.1608  (meaningful)
[LATENT] SSIM(lat_cloth, lat_model):  0.1221  (computable but meaningless)
[LATENT] SSIM(lat_cloth, +noise):     0.1376
[PIXEL]  SSIM(cloth, +noise):         0.2962
```

**Verdict**: SSIM's "luminance/contrast/structure" have no physical meaning in latent space. Noise response patterns differ completely from pixel space.

### E3: MSE Works in All Spaces

```
[PIXEL]    MSE(cloth, model):  0.165405  ✅
[LATENT]   MSE(lat_c, lat_m):  0.065193  ✅
[VELOCITY] MSE(vel_a, vel_b):  0.010035  ✅
```

**Verdict**: MSE is pure math — works on any tensor regardless of channel count or semantics.

### E4: Cosine vs MSE Complementarity

| Scenario | MSE | Cosine | Interpretation |
|----------|:---:|:------:|----------------|
| Identical velocity | 0.000000 | 1.0000 | Baseline |
| **Same direction, 10x magnitude** | **82.19** | **1.0000** | MSE explodes 8190x, Cosine unchanged! |
| Opposite direction | 4.059 | -1.0000 | Both detect |
| Slight perturbation | 0.010 | 0.9951 | Realistic scenario |

**Verdict**: MSE catches magnitude errors, Cosine catches direction errors. Together = complete velocity field quality assessment.

### E5: Real Image Blind Spot Comparison (H100, Real generation 256×256)

| Distortion | MSE | SSIM | LPIPS | Blind Spot |
|------------|:---:|:----:|:-----:|------------|
| D0: Identical | 0.0000 | 1.0000 | 0.0000 | Baseline |
| **D1: 1px shift** | 0.0058 | **0.1622** | 0.0821 | ⚠️ SSIM crashes to 0.16! Humans can't tell |
| D2: Slight blur | 0.0017 | 0.6614 | **0.3520** | LPIPS catches texture loss |
| D3: Heavy blur | 0.0052 | 0.5059 | 0.5735 | All agree |
| **D4: Brightness +30** | **0.0136** | **0.9345** | **0.0315** | MSE highest, but SSIM/LPIPS say "humans can't tell" |
| D5: Noise σ=15 | 0.0034 | 0.5356 | 0.2925 | All agree |
| **D6: Color shift R+20** | 0.0041 | **0.9581** | **0.1182** | ⚠️ SSIM fooled (0.96), LPIPS catches color change |
| D7: JPEG q=10 | 0.0022 | 0.5498 | 0.5535 | Both agree |

**Conclusion**: Every metric has blind spots. Combined use avoids being fooled. SSIM 0.93 + LPIPS 0.01 = safe. SSIM 0.96 + LPIPS 0.12 = SSIM fooled by color shift.

### E6: Three-Metric Difference Heatmaps (Teacher vs Student, Real generation 1024×1024)

The three metrics "see" completely different things on the same image pair:


- **MSE Map** (left): Only a few bright spots at garment edges and body contours — MSE sees "which pixels differ most in raw value"
- **SSIM Map** (center): The entire body and garment area lights up — SSIM is extremely sensitive to structural changes
- **LPIPS Map** (right): Garment folds, body contours, and background textures highlighted — most aligned with where human eyes focus

---

## Real-World Experiment

### Demo Results (CPU, 256×256 synthetic image)

Run the included `similarity_demo.py` to reproduce.

**Original test image** (256×256, synthetic geometric shapes + textures):

![Original Test Image](images/test_image_original.png)

**7 distortions applied, SSIM vs LPIPS comparison**:

![Comparison Grid](images/comparison_grid.png)

Detailed scores:

```
Distortion               SSIM    LPIPS  Interpretation
----------------------------------------------------------------------
1px_shift              0.9556   0.0114  SSIM sensitive, LPIPS immune
blur_slight            0.9390   0.1223  SSIM OK, LPIPS catches texture loss
blur_heavy             0.8720   0.2405  Both detect degradation
brightness+30          0.9788   0.0504  SSIM tolerant, LPIPS moderate
noise_σ15              0.3042   0.4698  Both agree: severely degraded
color_shift            0.9551   0.1619  SSIM OK, LPIPS catches color change
jpeg_q10               0.8573   0.1915  Both penalize compression artifacts
local_patch            0.9739   0.0495  Both detect, small local change
```

**Key observations**:

| Distortion | Winner | Why |
|------------|--------|-----|
| **1px shift** | LPIPS | SSIM penalizes pixel misalignment; LPIPS sees "same image" |
| **Slight blur** | LPIPS | SSIM barely notices; LPIPS catches texture destruction via VGG |
| **Brightness** | SSIM | SSIM is robust to uniform brightness change; LPIPS moderately penalizes |
| **Color shift** | LPIPS | SSIM treats R/G/B independently per channel; LPIPS integrates color perception |
| **Noise σ=15** | SSIM | SSIM drops to 0.30 (harsh); LPIPS at 0.47 (also harsh but proportional) |

### FID Demo Results (CPU, 100 synthetic images per set)

Run the included `fid_demo.py` to reproduce.

**Experiment 1 — Engine Alignment: FID vs SSIM Side-by-Side**

This experiment asks: "Can FID replace SSIM for engine alignment testing?" Answer: **No — use the right tool for the job**.

We generated 100 reference images and applied 5 perturbation types, then compared FID (batch-level) vs SSIM (per-image average):

| Perturbation | FID | Avg SSIM | Interpretation |
|:------------:|:---:|:--------:|----------------|
| Identical copy | ~0.0 | 1.000 | Both detect perfect match |
| Slight noise (σ=10) | 125.3 | 0.881 | FID overreacts to noise; SSIM gives graded response |
| Color shift (hue+10°) | 0.6 | 0.999 | FID barely notices; SSIM ignores it too |
| Slight blur (σ=1) | 4.6 | 0.994 | Both: minor difference |
| Heavy noise (σ=50) | 165.7 | 0.168 | Both agree: severely different |

![Engine Alignment: FID vs SSIM](images/fid_experiment1_engine_alignment.png)

**Takeaway**: FID is not designed for paired image comparison. It jumps from 0 to 125 with slight noise because it measures distributional shift, not per-image similarity. For "are these two outputs identical?" questions, SSIM and LPIPS are the right tools.

**Experiment 2 — Model Capability: Where FID Shines**

This experiment shows FID's real strength: comparing **unpaired** image distributions to evaluate model quality.

We simulated three generative models producing 100 images each:
- **Good model**: Diverse, high-quality images (varied colors, shapes, textures)
- **Bad model**: Low-quality images (noisy, dull colors, simple shapes)
- **Collapsed model**: 100 copies of the same image (mode collapse)

All compared against a "real" reference set of 100 diverse images:

| Model | FID Score | Interpretation |
|:-----:|:---------:|----------------|
| Good | **48.6** | Closest to real distribution |
| Bad | 176.8 | Far from real — low quality detected |
| Collapsed | 170.2 | Far from real — no diversity detected |

![Model Capability Comparison](images/fid_experiment2_model_capability.png)

**Takeaway**: FID correctly ranks Good < Bad ≈ Collapsed. Neither SSIM nor LPIPS could make this assessment, because there are no paired images to compare — only two sets.

*Visual samples from each model set (notice the diversity difference):*

![Model Samples](images/fid_experiment2_samples.png)

**Experiment 3 — Sample Size Sensitivity**

FID estimates a 2048-dimensional covariance matrix. Fewer samples than dimensions means unstable estimates. We verified this by subsampling 5 times at each size:

| Samples | FID Mean | FID Std | Stability |
|:-------:|:--------:|:-------:|:---------:|
| 10 | 124.5 | ±10.3 | ❌ Unreliable |
| 25 | 83.8 | ±3.1 | ⚠️ Rough indicator |
| 50 | 65.0 | ±2.4 | ⚠️ Usable with caution |
| 100 | 48.1 | ±1.0 | ✅ Reasonably stable |

![Sample Sensitivity](images/fid_experiment3_sample_sensitivity.png)

**Takeaway**: With only 10 samples, repeating the exact same experiment yields FID values ranging from ~107 to ~135 — enough variance to reverse rankings between two models. Use ≥100 samples for meaningful comparisons.

### Production Observations (GPU, diffusion model image generation, 50 samples)

From our diffusion model inference benchmarks on H100:

| Comparison | Approx SSIM | Observation |
|------------|:-----------:|-------------|
| Same engine, eager vs compile | ~0.93 | `torch.compile` does not degrade quality |
| Cross-engine, same resolution | ~0.91 | Minor numerical differences from different implementations |
| Cross-engine, mixed resolution | ~0.88 | Resolution mismatch artificially lowers SSIM |

**SSIM judgment thresholds** (calibrated from production experience):

| SSIM Range | Judgment | Action |
|:----------:|:--------:|--------|
| ≥ 0.95 | EXCELLENT | Direct replacement, no visual review needed |
| 0.85 ~ 0.95 | ACCEPTABLE | Minor differences, visual spot-check recommended |
| < 0.85 | POOR | Significant quality drop, investigate root cause |

**Gotcha: Resolution mismatch artificially lowers SSIM**

When comparing outputs from different engines, output resolution may differ if the size calculation references different input images. Resize before computing SSIM introduces interpolation artifacts, lowering scores by up to 0.4 in worst cases. Always ensure matching resolution or log which samples were resized.

### Cross-Engine Validation with Three Metrics (Seed Alignment Discovery)

In a cross-engine diffusion model image generation validation (comparing Diffusers vs an alternative inference engine), we used all three metrics together and discovered that **random seed is the dominant factor** in output differences:

| Comparison | LPIPS | SSIM | FID | Conclusion |
|------------|:-----:|:----:|:---:|------------|
| Same model, different engines, **random seed** | 0.072 | 0.906 | 11.04 | "Engines differ moderately" |
| Same model, different engines, **fixed seed** | **0.005** | **0.992** | **1.38** | "Engines are nearly identical" |
| Improvement from seed alignment | **14×** | +0.086 | **8×** | Seed alignment eliminates most differences |

All three metrics independently confirmed the same conclusion: with seed alignment, the two engines produce virtually identical outputs. This multi-metric cross-validation gives much stronger confidence than any single metric.

**Lesson learned**: When cross-engine SSIM is lower than expected (~0.90 instead of ~0.95), check seed alignment before investigating algorithmic differences.

### LPIPS in Distillation Training

In diffusion model distillation (reducing inference steps from 40 to 8), the actual loss function is **MSE + LPIPS hybrid**, not pure LPIPS. Like having an "art teacher + art critic" working together:

```python
# Actual distillation loss structure (from source code analysis):
loss_1 = align_trajectory()       # MSE (art teacher)
  # Compares student vs teacher velocity step-by-step in latent space
  # velocity = (teacher_next_latent - current_latent) / Δσ
  # Full gradient chain → precise guidance for each step

loss_2 = compute_regularization()  # LPIPS (art critic)
  # After student runs 8 steps, VAE decode to pixel space
  # LPIPS(AlexNet) compares student image vs teacher image
  # .detach() cuts intermediate gradients → only checks final result, saves memory

loss = loss_1 + loss_2  # 1:1 direct sum
```

**Why MSE + LPIPS instead of just one?**

| Scenario | Painting Analogy | Problem |
|----------|-----------------|--------|
| MSE only | Teacher watches each stroke, no one checks final painting | Each stroke is correct but painting lacks soul |
| LPIPS only | Critic only sees finished painting, can't tell which stroke went wrong | Knows it's bad but not how to fix it |
| **MSE + LPIPS** | **Teacher guides each stroke + critic checks final result** | **Each stroke correct + painting looks good** |

**Why LPIPS uses .detach() (doesn't backprop through each step)?**

If LPIPS also backpropped through every step, memory usage would double (need to store entire gradient chain), and MSE is already precisely guiding each step. Using .detach() to only check the final result = minimum cost for quality assurance.

**Key details**:
- LPIPS only compares the **final images**, not per-step. VAE decode is called only 2 times per training step (student once + teacher once), LPIPS computed only once.
- LPIPS reference image is the teacher model's generated image (`trajectory_teacher[-1]` via VAE decode).
- Although .detach() cuts intermediate gradients, LPIPS's numerical value still participates in the total loss. The optimizer learns through LPIPS value trends across training rounds to indirectly determine "which direction to adjust parameters makes the final image look better."

## Pitfalls in Practice

### 1. Score Direction Confusion

| Metric | "Images are identical" | "Images are completely different" |
|--------|:---------------------:|:--------------------------------:|
| SSIM | **1.0** | 0.0 |
| LPIPS | **0.0** | 1.0 |

This is the most common source of bugs. Always double-check: is a "high score" good or bad?

### 2. SSIM is Pixel-Aligned

A perfectly identical image shifted by 1 pixel will show SSIM < 1.0. If your inference pipeline introduces sub-pixel alignment differences (e.g., different interpolation modes), SSIM will penalize this even though the images are visually identical.

**Fix**: Use LPIPS when pixel alignment is not guaranteed.

### 3. LPIPS Requires a Neural Network

LPIPS needs the VGG-16 model (~528MB download, first-time only). This means:
- First call is slow (model loading)
- Needs PyTorch installed
- Not suitable for environments where you can't run neural networks

**Fix**: Use SSIM for quick CI/CD checks; reserve LPIPS for quality audits.

### 4. Neither Metric Captures Semantic Correctness

SSIM and LPIPS both measure low-level similarity. They cannot tell you:
- "Is the person wearing the right garment?" (use CLIP Score)
- "Are the generated images diverse enough?" (use FID/KID)
- "Does the text prompt match the output?" (use CLIP Score)

### 5. Resolution Mismatch Kills SSIM

If two images have different resolutions, you must resize before computing SSIM. This resize step introduces interpolation artifacts that lower the score.

**Fix**: Always ensure matching resolution, or log which samples were resized and compute separate statistics.

### 6. FID is Unstable with Small Samples

FID estimates a 2048-dimensional covariance matrix. With fewer samples than dimensions, the estimate is unreliable:

| Sample Size | FID Mean | FID Std Dev | Reliability |
|:-----------:|:--------:|:-----------:|:-----------:|
| 10 | 124.5 | **10.3** | ❌ Unreliable — variance too high |
| 25 | 83.8 | 3.1 | ⚠️ Rough indicator only |
| 50 | 65.0 | 2.4 | ⚠️ Usable with caution |
| 100 | 48.1 | **1.0** | ✅ Reasonably stable |

*(Data from fid_demo.py Experiment 3: same-quality distributions, 5 random subsampling trials per size)*

![FID Sample Sensitivity](images/fid_experiment3_sample_sensitivity.png)

With 10 samples, repeating the exact same experiment gives FID values ranging from 107 to 135 — a 28-point spread! At 100 samples, the spread narrows to ~2 points.

**Fix**: Use at least 100 samples. If you only have 50, report FID as a rough indicator, not a precise measurement. For published results, the community standard is ≥ 50,000 images.

## Quick Reference

### All Image Similarity Metrics

| Category | Metric | Full Name | Score Direction | Needs AI? | Best For |
|----------|--------|-----------|:---------------:|:---------:|----------|
| **Pixel** | MSE | Mean Squared Error | Low=similar | ❌ | Raw pixel difference |
| | PSNR | Peak Signal-to-Noise Ratio | High=similar | ❌ | Image compression quality |
| **Structural** | SSIM | Structural Similarity Index | High=similar | ❌ | Engineering verification |
| | MS-SSIM | Multi-Scale SSIM | High=similar | ❌ | More robust than SSIM |
| **Perceptual** | LPIPS | Learned Perceptual Similarity | Low=similar | ✅ VGG | Perceived quality matching |
| **Distribution** | FID | Fréchet Inception Distance | Low=better | ✅ Inception | Batch-level quality |
| | KID | Kernel Inception Distance | Low=better | ✅ Inception | Small-sample batch quality |
| **Semantic** | CLIP Score | CLIP Similarity | High=better | ✅ CLIP | Text-image alignment |
| **Human** | MOS | Mean Opinion Score | High=better | ❌ (humans) | Ground truth quality |

### Decision Flowchart

```mermaid
flowchart TB
    Q{"Need to compare images?"}
    Q --> P["Pixel-exact check?"]
    Q --> H["Human-like perception?"]
    Q --> B["Batch quality?"]
    Q --> T["Text-image alignment?"]
    P --> SSIM["SSIM"]
    H --> LPIPS["LPIPS"]
    B --> FID["FID"]
    T --> CLIP["CLIP Score"]

    style SSIM fill:#fff3e0,stroke:#FF8C00
    style LPIPS fill:#f3e8ff,stroke:#800080
    style FID fill:#e8f4ff,stroke:#0078D4
    style CLIP fill:#e8ffe8,stroke:#107C10
```

## Run the Demos

### SSIM vs LPIPS Demo

```bash
pip install torch torchvision lpips scikit-image matplotlib Pillow numpy
python similarity_demo.py --save-images
```

Generates a 256×256 synthetic test image, applies 7 types of distortion, and compares SSIM vs LPIPS for each. Runs on CPU in ~30 seconds.

### FID Demo

```bash
pip install torch torchvision scipy scikit-image matplotlib Pillow numpy
python fid_demo.py --save-images
```

Runs three experiments demonstrating FID's strengths and limitations:

| Experiment | What It Shows | Time (CPU) |
|:----------:|---------------|:----------:|
| 1 | FID vs SSIM on paired images (engine alignment) | ~2 min |
| 2 | FID on unpaired sets (model capability comparison) | ~2 min |
| 3 | FID variance across sample sizes (10–100) | ~5 min |

Run a specific experiment: `python fid_demo.py --experiment 2 --save-images`

---

**Author**: Xinyu Wei (魏新宇)
