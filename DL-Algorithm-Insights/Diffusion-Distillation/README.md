# Diffusion Distillation — From 40 Steps to 8 Steps

> **Train a student model to reproduce what a teacher model does in 40 steps — in just 8 steps.**

## What Is It?

**Diffusion Distillation** is a technique that compresses the multi-step denoising process of a diffusion model into far fewer steps, without retraining the model from scratch. A large pre-trained model (the teacher) runs the full denoising loop and generates supervision signals; a lightweight adapter (the student, typically a LoRA) learns to skip most of the steps while maintaining output quality.

The result: the same model architecture, dramatically fewer inference steps, similar visual quality.

## Why It Matters

A 20-billion-parameter diffusion model running at full quality takes **40–50 denoising steps** per image. On an H100 GPU, that's roughly **30–45 seconds per image**. For any production service handling real users, this is a hard blocker.

The naive solution — reduce steps without any distillation — causes severe quality degradation. The output looks "melted" because the ODE solver is being asked to make huge jumps it was never trained for.

Distillation solves this properly: teach the model *how to make large jumps* by having it observe the teacher's full trajectory, then learn to jump 5 teacher-steps at a time.

**Production motivation (Virtual Try-On example)**:

| Mode | Steps | Relative Time | Quality |
|:----:|:-----:|:-------------:|:-------:|
| Teacher (no distillation) | 40–50 | 1.0× (baseline) | Baseline |
| End-to-end distillation | ~15 | ~0.4× | Good |
| **Trajectory distillation** | **~8** | **~0.2×** | **Better** |

> Times are end-to-end inference (TextEncoder + DiT + VAE) with CFG on a single H100 GPU. See [Full-Scale Production Benchmark](#full-scale-production-benchmark) for detailed measurements.

---

## Running on Azure

This entire experiment — training a 20B-parameter diffusion model distillation from scratch — ran on a **single [Standard_NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/ncads-h100-v5)** VM instance.

| Resource | Spec | Role in this experiment |
|----------|------|------------------------|
| GPU | 1 × NVIDIA H100 NVL, 94 GB VRAM | Model weights + activation memory |
| vCPU | 40 × AMD EPYC Genoa | Data preprocessing, CPU offload target |
| System RAM | 320 GiB | Text encoder CPU offload buffer |
| OS disk | Azure Premium SSD | Training scripts, checkpoints, logs |

### Technology Stack at a Glance

This table summarizes **every technique** that makes it possible to distill a 20B-parameter diffusion model on a single H100 GPU:

| Category | Technique | What It Does | Where Used | Detail Section |
|----------|-----------|-------------|:----------:|:--------------:|
| **Algorithm** | Trajectory Distillation (2nd-gen) | Student learns to skip 5x teacher steps by matching intermediate checkpoints | Core training loop | [Deep Dive](#deep-dive-trajectory-distillation) |
| **Algorithm** | Velocity Matching Loss | Loss built in velocity (vector field) space, not latent (position) space | Loss function | [Loss Functions](#loss-functions-latent-matching-vs-velocity-matching) |
| **Parameter Efficiency** | LoRA (low rank) | Only a small fraction of params are trainable → optimizer states stay tiny | Student adapter | [Step 2](#step-2-train-the-student-lora-as-the-adapter) |
| **Precision** | BF16 (bfloat16) | Half the memory vs FP32; 20B model = ~40 GB instead of ~80 GB | All model weights | [Setup](#setup) |
| **Memory — Teacher** | `torch.no_grad()` | Prevents storing activations for 40 teacher steps → saves ~50 GB | Teacher forward pass | [VRAM Analysis](#why-the-student-fits-in-vram-despite-having-gradients) |
| **Memory — Student** | Block-level Gradient Checkpointing | Only saves block inputs; recomputes internals during backward → significant memory saving | Student forward/backward | [VRAM Analysis](#why-the-student-fits-in-vram-despite-having-gradients) |
| **Memory — Student** | Per-step Backward | Calls `.backward()` after each of 8 steps, then `.detach()` → saves ~30 GB | Student backward pass | [Per-Step Backward](#2-per-step-backward-to-avoid-oom) |
| **Memory — Offload** | Text Encoder CPU Offload | Moves ~14 GB text encoder to CPU after encoding → frees GPU for DiT | Text conditioning | [VRAM Analysis](#why-the-student-fits-in-vram-despite-having-gradients) |
| **Architecture** | Serial Teacher→Student | Teacher and student never coexist in VRAM — teacher runs first, caches 8 latents, then exits | Training pipeline | [Serial Execution](#teacher-and-student-serial-not-concurrent) |

### VRAM Budget (Training Peak)

Training peak within single-GPU capacity. See [VRAM analysis](#why-the-student-fits-in-vram-despite-having-gradients) for per-component breakdown.

> Without these memory optimization techniques combined, naive training of the same 20B model would require significantly more VRAM than a single GPU provides.

**What "single VM" means in practice**:

- No InfiniBand, no NCCL multi-node setup, no Kubernetes orchestration
- No tensor parallelism code — the same model weights run in both teacher and student roles
- Total training wall-clock time: **a few hours** for a multi-epoch run on a 20B model
- Cost model: pay for one VM, run one job, shut it down — no standing cluster

The memory engineering described in [Why the Student Fits in VRAM](#why-the-student-fits-in-vram-despite-having-gradients) is precisely what makes single-instance training viable. Without those three techniques combined, this workload would require a multi-GPU setup.

For practitioners looking to reproduce or adapt this work, the recommended starting point is the `Standard_NC40ads_H100_v5` SKU available in Azure East US. The [NCads H100 v5 series documentation](https://learn.microsoft.com/en-us/azure/virtual-machines/ncads-h100-v5) covers driver setup, Gen2 VM requirements, and storage configuration.

---

## How It Works

### Core Terminology: ODE, SDE, Velocity, Flow Matching

Before diving into distillation, these four concepts are essential.

#### ODE vs SDE — Two Ways to Model Denoising

| | ODE (Ordinary Differential Equation) | SDE (Stochastic Differential Equation) |
|---|---|---|
| **In plain English** | **Deterministic navigation** — direction and step size fully determined | **Navigation + random jitter** — deterministic direction plus random noise |
| **Analogy** | Bullet train: fixed rails, same start = same end | Sailboat: right heading but wind blows, each trip slightly different |
| **Formula** | dz/dt = v(z, t) | dz = v(z,t)dt + g(t)dW |
| **Same start, run twice** | **Identical** | **Slightly different** |
| **Representatives** | DDIM, **Flow Matching** | DDPM |
| **Distillation friendliness** | **High** — deterministic path can be precisely imitated | Low — path varies each time |

> All distillation discussed below uses the **ODE (Flow Matching)** framework.

#### Velocity — The "Speed" in Latent Space

```
dz/dt = v_θ(z_t, t)
```

- z_t = latent state at time t (**position**)
- v_θ = model-predicted velocity (**speed** = derivative of position w.r.t. time)

Velocity is the **tangent direction + rate** of the latent trajectory. Latent differences z_{t-1} - z_t mix in scheduler step-size scaling and differ from velocity by an order of magnitude — **cannot substitute latent differences for velocity**.

#### Flow Matching — Learning the Shortest Path

**Flow Matching** directly trains a velocity field: learn the rate field of the shortest path from noise to data. Compared to "predict noise → subtract", "predict velocity → follow" is more direct and naturally distillation-friendly.

| Method | Model Predicts | Distillation Approach |
|------|:---:|---------|
| **DDPM (SDE)** | noise epsilon | Difficult: path varies each time |
| **DDIM (ODE)** | noise epsilon | Possible but indirect |
| **Flow Matching (ODE)** | **velocity v** | **Naturally friendly: velocity MSE directly usable as distillation loss** |

> **This is why distillation loss is built in velocity space, and diagnosis must also be in velocity space.**

---

### The Denoising Trajectory

A diffusion model generates images by iteratively removing noise from a pure Gaussian noise tensor (the *latent*). Each step t produces an intermediate latent z_t:

```
z_T (pure noise) → z_{T-1} → z_{T-2} → ... → z_0 (clean image)
```

This sequence of latent states is the **trajectory** — the denoising path through high-dimensional latent space.

Key insight: the trajectory is not a straight line. Different steps carry different information:

| Denoising Phase | Steps (example 40-step) | What Happens |
|:---------------:|:-----------------------:|--------------|
| Noise-dominant | 1–5 | Random Gaussian — no structure |
| Color emergence | 5–12 | Global color tones form, rough outlines appear |
| Structure formation | 12–25 | Body shapes, object boundaries become clear |
| Detail refinement | 25–35 | Textures, fine edges, patterns sharpen |
| Micro-adjustment | 35–40 | Subtle lighting/sharpness corrections |

The following visualization shows the actual 40-step teacher denoising process, with intermediate latents decoded through the VAE decoder at key steps:

![40-step denoising trajectory](images/decoded_steps_40vs8.png)

Top row: Teacher denoising at steps 0→10→20→30→40 — progressing from pure noise to a clean image. Bottom row: Distilled student achieving visually identical results in just 8 steps (0→2→4→6→8).

---

### Three Generations of Distillation

The field has evolved through three generations, each trading storage/complexity for better compression:

| Generation | Method | Supervision Signal | Teacher on GPU | Step Compression | Representative |
|:----------:|--------|:-----------------:|:--------------:|:----------------:|---------------|
| **1st — Online** | Teacher + student co-train | **Final output only** (clean latent/image) | ✅ Full time | 40→15 (~2.7×) | Progressive Distillation |
| **2nd — Offline (Trajectory)** | Teacher runs once, stores trajectories | **K intermediate checkpoints** (stepwise alignment) | Pre-compute only | 40→8 (5×) | TwinFlow |
| **3rd — Teacher-free** | No separate teacher | Math interpolation (no teacher output) | ❌ Never | Variable | IMM, Consistency Models |

> **1st gen — what the teacher provides**: runs N denoising steps → produces the **final clean latent** → student is trained to match that endpoint in N/2 steps. No intermediate states are stored or used.

**Why the 2nd generation achieves better compression**: by supervising every intermediate checkpoint (not just the final output), the student gets much denser guidance.

> **⚠️ Key distinction: 2nd-gen trajectory distillation has two variants**
>
> | Variant | Supervision Signal | Loss Domain | Representative |
> |---------|-------------------|------------|---------------|
> | **Latent Matching** | Teacher's latent states z_t at K timesteps | `MSE(z_student, z_teacher)` — in **latent (position) space** | TwinFlow |
> | **Velocity Matching** | Teacher's velocity v_t at each step | `MSE(v_student, v_teacher)` — in **velocity (vector field) space** | DiffSynth Trajectory Imitation |
>
> The key difference: Latent Matching requires "reaching the same position", Velocity Matching requires "predicting the same direction". **When loss is built in velocity space, diagnosis must also be in velocity space (see Three-Layer Framework below).**

---

### Deep Dive: Trajectory Distillation

This is the 2nd-generation approach — the most widely used in high-quality production diffusion models.

#### Step 1: Collect Teacher Trajectories (Offline, Once)

The baseline model runs the full N-step denoising loop for each training sample and records K intermediate latent states:

```python
# Teacher collects 40-step trajectory, records latents at 8 checkpoints
for sample in training_data:
    z = sample_noise()
    trajectory = {0: z.clone()}          # record starting noise
    for t in range(N, 0, -1):            # full N-step denoising
        v = teacher(z, t, condition)     # predict denoising direction
        z = step(z, v, dt)              # Euler step
        if t in key_timesteps:           # only store K checkpoints
            trajectory[t] = z.clone()
    save(trajectory, sample_id)          # store latent tensors (not images)
# Teacher goes offline — no longer needed during student training
```

Why store latent tensors (not decoded images)?
- Latent is 6× smaller than pixel space (128×128×16 vs 1024×1024×3)
- No lossy VAE encode/decode round-trip → exact supervision signal
- Direct loss computation during training (no re-encoding overhead)

#### Step 2: Train the Student (LoRA as the Adapter)

The student is the same base model + a LoRA adapter. LoRA modifies the attention and modulation layers to predict larger denoising steps:

```python
# Student = base model + trainable LoRA
# LoRA is added to key attention and modulation layers
lora_config = LoraConfig(
    r=<rank>,
    target_modules=[
        # attention Q/K/V projections
        # cross-attention projections  
        # modulation layers
        # ... (model-specific target modules)
    ]
    # Everything else stays frozen — base params unchanged
    # Only LoRA params are updated
)

for step in range(training_steps):
    traj = load_trajectory(sample_id)        # teacher's recorded path
    z = traj[T_max]                          # start from the same noise

    for i, (t_now, t_teacher) in enumerate(student_8_steps):
        with lora_enabled():
            v = model(z, t_now, condition)   # student predicts (LoRA ON)
        z_student = step(z, v, large_dt)     # large jump: 5 teacher-steps
        z_teacher = traj[t_teacher]          # teacher's ground truth

        loss += perception_loss(z_student, z_teacher)  # Approach A: Latent Matching
        # Approach B: Velocity Matching (more common in production)
        # v_teacher = teacher(z, t_now, condition)
        # v_student = model(z, t_now, condition)
        # loss += MSE(v_student, v_teacher) + LPIPS(decode(z_student), decode(z_teacher))
        z = z_student                        # continue from student's output
        loss.backward()                      # backward immediately — avoids accumulating 8-step graph
        loss = 0

    optimizer.step()                         # update only LoRA params
```

Why LoRA instead of full fine-tuning?
- The denoising *direction* is already correct — LoRA only adjusts the *magnitude*
- Full fine-tuning risks catastrophic forgetting of the base model's understanding
- A moderate LoRA rank is sufficient: the velocity field correction is low-rank

#### Conceptual Visualization: Latent Norm Trajectory

The following diagrams illustrate the core idea — how a student model with only 8 steps closely tracks the teacher's 40-step denoising path:

![Latent Norm trajectory concept](images/distill_trajectory_40vs8.png)

- **Top (Teacher, blue)**: 40-step denoising — Latent Norm smoothly decays from ~135 (pure noise) to ~16 (clean latent), small step-size, smooth path
- **Bottom (Student, orange)**: 8-step denoising — same start and end, but each step spans 5 teacher-steps. The LoRA guides the model to denoise accurately in large jumps
- **Gray reference line**: Teacher trajectory overlaid on the Student plot — the student closely follows it

![Step mapping concept](images/distill_step_mapping_40vs8.png)

- **Top row (blue, Teacher)**: Full 40-step denoising sequence, σ_max → Clean
- **Bottom row (orange, Student)**: 8-step denoising, each step spanning 5 teacher-steps
- **Purple dashed arrows**: Alignment between teacher and student steps
- **Distillation objective**: LoRA is trained so the student's latent or velocity at each alignment point matches the teacher's

#### Loss Functions: Latent Matching vs Velocity Matching

Trajectory distillation loss functions fall into two camps:

**Approach A — Latent Matching (position alignment)**:
```
L = MSE(z_student_t, z_teacher_t) + LPIPS(decode(z_student), decode(z_teacher))
```
Matches **latent states** (positions). Variants include IMM (moment matching: mu+sigma distribution).

**Approach B — Velocity Matching (vector field alignment)**:
```
L = MSE(v_student_t, v_teacher_t) + LPIPS(decode(z_student), decode(z_teacher))
```
Matches **velocity** (model-predicted denoising direction).

**Key difference**:
- Latent Matching requires "reaching the same position" — latent-space diagnosis is valid
- Velocity Matching requires "predicting the same direction" — **diagnosis must be in velocity space**

> **In practice, Velocity Matching is more common**: flow matching models have DiT outputs that directly predict velocity (noise_pred). Velocity MSE can be computed directly from model outputs.

---

### Why Trajectory Distillation Beats End-to-End Distillation

| | End-to-End | Trajectory |
|---|---|---|
| **Supervision signal** | Final output only | Every intermediate checkpoint |
| **Student freedom** | Can take any path to the endpoint | Must follow the teacher's route |
| **Risk** | "Shortcut" paths that bypass key intermediate representations | Forced to learn the semantically meaningful stages |
| **Step compression** | 40→15 (2.7×) typical | 40→8 (5×) achieved |
| **Storage** | ~50GB (final images) | ~320GB (trajectory tensors) |
| **Complexity** | Low | High |

The latent space visualization shows why the dense supervision matters: most semantic structure (color + outline) emerges in the first 30% of steps. A student that only sees the final output can "get lucky" on the endpoint while completely bypass these critical intermediate representations. Trajectory matching forces it to navigate the same semantic milestones.

![Two-stage pipeline](images/two_stage_pipeline.png)

---

## Real-World Experiment

### Setup

All experiments run on a **single [Azure Standard_NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/ncads-h100-v5) VM** — one H100 NVL GPU (94 GB VRAM), 40 vCPU, 320 GiB RAM — with a 20-billion-parameter Multimodal Diffusion Transformer (MMDiT).

| Parameter | Value |
|-----------|-------|
| Cloud VM | [Azure Standard_NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/ncads-h100-v5) |
| GPU | 1 × NVIDIA H100 NVL (94 GB VRAM) |
| Base model | 20B MMDiT DiT (BF16) |
| LoRA rank / alpha | Low-rank adapter |
| Teacher steps | Full denoising schedule |
| Student steps | Reduced schedule |
| Training epochs | Multiple |
| Training samples | Small dataset of image pairs |
| Optimizer | AdamW |
| Gradient checkpointing | Block-level |
| GPU memory usage | Well within single-GPU capacity |

The four memory optimization techniques (see [Technology Stack](#technology-stack-at-a-glance) for summary, [VRAM Analysis](#why-the-student-fits-in-vram-despite-having-gradients) for deep dive) allow training a 20B-parameter model on a **single** Azure NC40ads H100 v5 GPU without OOM.

---

### Why the Student Fits in VRAM Despite Having Gradients

A natural question: if the student keeps gradients and the teacher does not, why does the student use *less* VRAM than an unguarded teacher pass? Three reasons compound:

**Reason 1 — Fewer steps (8 vs 40)**

Activation memory scales linearly with the number of denoising steps processed. Without any optimizations:

```
Teacher (no_grad OFF): 40 steps × per-step activations → very large
Student (gradients ON): 8 steps × per-step activations → much smaller baseline
```

The student starts at 1/5 the activation footprint just from having fewer steps.

**Reason 2 — Block-level gradient checkpointing**

Normal gradient-enabled training stores every layer's output for all 60 transformer blocks:

```
layer1_act + layer2_act + ... + layer60_act  (all 60 stored simultaneously)
```

**What "block-level" means**: the 20B MMDiT model is structured as 60 Transformer Blocks. Each Block is treated as one checkpoint unit — only the *input* to each Block is saved; everything computed *inside* the Block (attention scores, MLP intermediates) is discarded after the forward pass and recomputed from the Block's input during backward.

```
Block 1          Block 2          Block 3     ...   Block 60
[input saved] → [input saved] → [input saved] → ... → [input saved]
 internals?       internals?       internals?           internals?
 discarded        discarded        discarded            discarded

backward needs Block 2 internals?
  → re-run Block 2 forward from its saved input → use result → discard again
```

**Granularity tradeoff**: checkpoint granularity is a dial between memory and compute —

| Granularity | Checkpoints saved | Extra compute | Memory saving |
|:-----------:|:-----------------:|:-------------:|:-------------:|
| Every layer (fine) | All 60 | ~0% | ~0% |
| **Block-level (our choice)** | **60 block inputs** | **~30%** | **~60–80%** |
| Every N blocks (coarse) | Few | ~60%+ | Maximum |
| No checkpointing | None | ~100% extra | None |

Block-level is the validated sweet spot for this architecture: coarse enough to save most activation memory, fine enough that recompute overhead stays under 30%.

Cost: ~30% extra compute time. Saving: ~60–80% of activation memory.

**Reason 3 — Per-step backward**

Naive implementation waits for all 8 student steps to finish, then calls `backward()` once — holding 8 steps of computation graphs simultaneously:

```python
# ❌ Holds all 8 steps in memory at once
total_loss = sum(step_losses)
total_loss.backward()
```

Per-step backward releases each step's graph immediately:

```python
# ✅ At most 1 step's graph in memory at any time
for i in range(8):
    step_loss.backward()
    z = z.detach()   # cut cross-step gradient flow
```

**VRAM budget at peak (single A/B phase)**:

| Component | VRAM |
|-----------|:----:|
| 20B model weights (BF16) | ~40 GB |
| Student activations (with GC) | Modest |
| Optimizer states (LoRA only, not full model) | Minimal |
| Teacher latent cache | Minimal |
| **Total** | **Well within 94 GB** |

The optimizer only tracks LoRA parameters (a small fraction of 20B), which is why optimizer state is negligible.

---

### Teacher and Student: Serial, Not Concurrent

A common misconception: "the teacher and student run in parallel."  
In trajectory distillation, **they run strictly sequentially within every training step**:

```
Step N:
  1. Teacher forward  (torch.no_grad(), 40 denoising steps)
     → record 8 intermediate latents: z_t1, z_t2, ..., z_t8
     → computation graph is immediately released (no_grad)

  2. Student forward  (with gradients, 8 denoising steps)
     → each student output compared against the matching teacher latent
     → MSE loss accumulated across 8 steps

  3. Backward + optimizer step
     → only LoRA weights are updated
```

This serial design is not incidental — it is the reason single-GPU training is feasible:

| | 1st-gen Online Distillation | Our Trajectory Distillation |
|--|--|--|
| Teacher / Student relationship | **Concurrent forward passes**, sometimes sharing the computation graph | **Serial**: teacher runs first, student runs second |
| Teacher gradients | Sometimes retained | Always `no_grad` — graph released immediately |
| Supervision signal | Final output only (clean latent) | 8 intermediate latents across the full trajectory |
| Peak VRAM | Higher (two computation graphs coexist) | Lower (teacher graph gone before student starts) |

**Why does `no_grad` matter for the teacher?** Teacher and student share the *same* 20B model weights — there is only one copy in VRAM. The problem is not two separate models; it is *how many steps worth of activations are stored at once*:

```
Teacher forward WITHOUT no_grad (40 steps):
  PyTorch assumes a backward() is coming
  → stores intermediate activations for ALL 40 steps → ~50 GB extra
  → backward never actually runs — memory occupied for nothing

Teacher forward WITH no_grad (40 steps):
  PyTorch knows no backward() is coming
  → frees each layer's activations immediately after use
  → only one layer in memory at a time → near-zero overhead
```

The student runs only 8 steps (far fewer than the teacher's 40) and uses gradient checkpointing on top — so even with gradients enabled, its activation footprint is smaller than an unguarded 40-step teacher pass.

---

### Training Loss Curve

Training converged steadily across all epochs with no overfitting. The loss decreased monotonically, indicating stable learning.

**Training completed in a few hours on a single GPU. Loss dropped significantly with monotonic decrease and no overfitting.**

---

### Distillation Quality Analysis: Three-Layer Framework

> **Core methodology: Evaluate distillation in pixel space, diagnose in velocity space, idempotency check across all three layers.**
>
> The diagnosis domain must match the loss function domain. If loss is built in velocity space, diagnosis must also be in velocity space. "Alignment" observed in latent space can be misleading — endpoints being close does not mean the path is correct.

```
┌──────────────────────────────────────────────────┐
│  Layer 3: Pixel Space (Evaluation)               │
│  SSIM / FID / LPIPS / Visual Inspection          │
│  Answers: How good is the final output?          │
├──────────────────────────────────────────────────┤
│  Layer 2: Velocity Space (Diagnosis)             │
│  PCA trajectory / L2 norm / Teacher-Student      │
│  Answers: Where did velocity learning fail?      │
│  ✅ Matches velocity loss domain                 │
├──────────────────────────────────────────────────┤
│  Layer 1: Latent Space (Reference)               │
│  Latent Norm / Cosine / Heatmaps                 │
│  Answers: Did endpoints converge? (necessary,    │
│           not sufficient)                        │
│  ⚠️ Shows "did it arrive" not "how it got there"│
└──────────────────────────────────────────────────┘
```

**Idempotency check**: Findings across all three layers must be consistent. When velocity diagnosis reveals a problem, pixel evaluation should show corresponding degradation.

#### Layer 1: Latent Space Analysis (Endpoint Reference)

> **⚠️ Note**: Latent metrics reflect **endpoint convergence** — necessary but not sufficient for quality diagnosis. Same endpoint does not mean same path.

This figure shows GPU-measured latent space metrics — Teacher (40 steps) vs Student (8 steps):

![Trajectory analysis](images/trajectory_40vs8_analysis.png)

Four subplots:
1. **Latent Norm decay**: Teacher's smooth curve vs Student's 8-point jumps
2. **MSE**: Per-step latent difference. Lower = better alignment
3. **Cosine Similarity**: Final cosine similarity > 0.98
4. **Channel Statistics**: Both models evolve similarly

> These metrics confirm good endpoint convergence but cannot diagnose velocity field learning quality.

#### Layer 2: Velocity Space Diagnosis (Matches Loss Domain)

> When the loss function is built in velocity space (`MSE(v_student, v_teacher)`), diagnosis must also be in velocity space. Velocity capture: monkey-patch `scheduler.step` to intercept `noise_pred` (= velocity after CFG rescaling). Latent differences (`z_{t-1} - z_t`) mix scheduler sigma scaling and differ from true velocity by an order of magnitude.

**Method**:
1. Monkey-patch `scheduler.step` to intercept `noise_pred` (= velocity)
2. PCA-reduce Teacher's velocity vectors to 2D
3. Project Student's velocity vectors onto Teacher's PCA basis
4. Plot overlay comparison

**Core finding — the "Missing Turn" phenomenon**:
1. **Student hugs Teacher's right arc** — velocity directions match, LoRA learned the velocity field direction
2. **Teacher's unique left arc** — corresponds to mid-timesteps, completely skipped by Student
3. **CFG does not affect trajectory shape** — changes magnitude not direction
4. **Teacher L2 norm range >> Student** — Student lacks mid-timestep low-norm phase

**Velocity Overlay — Teacher (blue) vs Student (red/yellow), projected onto Teacher PCA basis:**

![E12d Velocity Overlay](images/E12d_velocity_overlay_comparison.png)

> Student 8-step hugs Teacher's right arc (direction matched), but Teacher's unique left arc (mid-timestep turning region) is entirely skipped.

**Joint PCA: Teacher + Student CFG=2 in same coordinate system:**

![Joint PCA CFG=2](images/E12d_velocity_joint_pca_cfg2.png)

**Conclusion**: 8-step distillation learns the velocity direction but timestep sampling is too sparse — the critical mid-timestep turning region is skipped. This is **invisible to latent-space metrics**.

**Improvement directions**:
- Multi-NFE distillation (4+8+16 steps) → cover more mid-timesteps
- Dense sampling near t=0 → terminal timesteps are critical for details
- Adaptive timestep schedule → allocate more steps where velocity changes rapidly

#### Layer 3: Pixel Space Evaluation (Ultimate Standard)

Pixel evaluation is the final arbiter — regardless of loss domain, the goal is good images. Idempotency check: velocity diagnosis predicts detail degradation → SSIM < 1.0 confirms it.

---

### Visual Quality: Teacher vs Student

Both teacher and student final latents decoded through the VAE decoder:

![Teacher vs Student comparison](images/trajectory_40vs8_final_compare.png)

The visual difference is negligible to the human eye.

---

### Quality Metrics Across 10 Test Samples

> **Note**: This early evaluation used a lightweight verification pipeline (DiffSynth framework, cfg_scale=1). See the [Full-Scale Production Benchmark](#full-scale-production-benchmark-50-samples) below for the definitive 50-sample results using production parameters (diffusers, CFG=4).

Evaluated on 10 diverse samples (varying garment styles, model types, resolutions):

Across the test samples:
- **Most samples rated Excellent** (SSIM ≥ 0.95) or **Good** (≥ 0.92)
- **All samples SSIM > 0.86** — zero catastrophic failures
- Average speedup across all samples: **~5×** (larger images take longer, speedup ratio is stable)

---

### Full-Scale Production Benchmark

The trajectory analysis above used a debug-mode pipeline. To validate under **production conditions**, we ran a larger benchmark using the standard diffusers pipeline with production hyperparameters.

#### Test Design

| Parameter | Teacher | Student |
|-----------|:-------:|:-------:|
| Framework | diffusers | diffusers |
| Inference steps | Full schedule | Reduced schedule |
| CFG | Enabled | Enabled |
| Prompt | Real text prompt | Same |
| LoRA | None | Distilled adapter, fused |
| Scheduler | FlowMatchEulerDiscrete | Same |
| Precision | BF16 | BF16 |

**Only variable changed**: step count and LoRA loading. Everything else held constant for fair comparison.

#### Performance Results

The distilled student achieves a **~5× speedup** over the teacher with near-identical GPU memory usage. Latency reduction is consistent across all samples with very low variance.

> End-to-end latency includes TextEncoder encoding + DiT denoising + VAE decode. With CFG enabled, the DiT runs **2 forward passes per step** (conditional + unconditional).

![Production Benchmark Inference Time](images/production_bench_inference_time.png)

#### Quality Assessment: SSIM / PSNR

SSIM and PSNR computed against Teacher full-step output as reference:

- **Majority of samples achieve Good or better quality** (SSIM ≥ 0.85)
- **Over half achieve Very Good or Excellent** (SSIM ≥ 0.90)
- A small percentage show significant divergence on high-difficulty inputs

The quality distribution confirms that trajectory distillation preserves visual fidelity for most inputs, with degradation primarily on out-of-distribution or high-complexity samples.

#### Denoising Trajectory Comparison (Production Pipeline)

Using debug instrumentation to capture per-step latent statistics (mean / std) with the production pipeline:

| Metric | Teacher | Student |
|--------|:------:|:------:|
| Final latent mean deviation | — | Small |
| Final latent std deviation | — | Very small |

![Production Benchmark Trajectory](images/production_bench_trajectory.png)

> Blue = Teacher 40 steps, Orange = Student 8 steps. The Student closely tracks the Teacher’s denoising trajectory in latent space despite using only 8 steps.

#### Outlier Analysis

The lowest-SSIM samples represent genuinely difficult inputs (complex garment textures, dense detail regions, complex poses). They consistently score lowest across all evaluation methods, indicating input complexity rather than systematic model failure.

### CFG ROI is Extremely Poor at Low Step Counts

> **Test framework: diffusers** (standard pipeline, production config). See environment details below.

Distillation's core value is reducing step counts. A natural question arises: **is enabling CFG worthwhile for the student model (8 steps)?** We ran a steps×CFG cross-experiment on H100 with the LoRA-fused model (full-step + CFG output as reference baseline):

**Test Environment**:

| Item | Detail |
|------|--------|
| Framework | diffusers (standard `DiffusionPipeline`) |
| Model | 20B-parameter DiT-based diffusion model, LoRA-fused (student) |
| Attention Backend | SDPA (PyTorch default) |
| Precision | BF16 |
| Hardware | 1× NVIDIA H100 NVL (94 GB VRAM) |
| CFG Implementation | True CFG — conditional + unconditional dual forward pass |
| Timing | End-to-end wall-clock (TextEncoder + DiT + VAE), single-image, no batching |

**Key findings from the steps×CFG matrix**:

- **CFG consistently adds ~2× time** (conditional + unconditional dual forward pass)
- **CFG gains are negligible at low step counts**: minimal SSIM improvement at reduced steps
- **At equal time budget, adding steps vastly outperforms adding CFG**: step gains are an order of magnitude higher than CFG gains
- **Physical reason**: At low step counts each step takes a large stride with insufficient guidance accumulation; CFG benefits become perceptible only above ~20 steps

![CFG and Step Count Comparison Grid](images/cfg_batch_comparison_grid.png)

**Implication for distillation**: The ROI of enabling CFG with a student model at reduced steps is low. If latency is the primary goal, **running the distilled student without CFG is a reasonable choice**, significantly reducing latency with minimal quality loss.

#### diffusers Batch Throughput is Completely Flat

Diffusers pipeline-level batching is pure sequential looping — batch=N time = batch=1 × N. Throughput improvement requires engine-level optimization (e.g., continuous batching).

---

## Known Issues and Troubleshooting

### 1. Training-Inference Conditioning Mismatch

**This is the most commonly overlooked issue** — easy to introduce when copying code between scripts, nearly impossible to spot from loss curves alone.

**Scenario**: You copy a helper function from a *visualization script* (which used `prompt=""` for simplicity) into your *training script*. The function runs fine. The loss converges normally. But the trained LoRA only learned to denoise under empty-prompt conditioning.

At inference time, the user provides a real text prompt. The model was never trained for this. Quality may appear fine on easy samples, but fail catastrophically on others.

**What the data shows**:

| Version | Training Prompt | Inference Prompt | Quality Impact |
|---------|:--------------:|:-----------------:|:--------------:|
| Buggy | `""` (empty) | Real text | Catastrophic failures on some samples |
| Fixed | Real text | Real text | Consistent quality across all samples |

Empty-prompt training can introduce **catastrophically failing samples** that don't exist after the fix. The loss curve shows no warning.

**Rule**: Before training, explicitly verify every conditioning input against what the inference script uses:

```
Checklist — train vs infer must match:
☐ prompt text (not empty vs real text!)
☐ negative_prompt
☐ CFG scale
☐ image input order (if multi-image)
☐ image preprocessing (resize/normalize)
☐ scheduler parameters (shift/beta)
```

---

### 2. Per-Step Backward to Avoid OOM

Naive implementation accumulates the full 8-step computation graph, then calls `backward()` once — OOM on 20B models. The fix is backward after each individual step with `.detach()` to cut cross-step gradients. See [Reason 3 — Per-step backward](#why-the-student-fits-in-vram-despite-having-gradients) for the detailed explanation and code example.

---

### 3. Gradient Checkpointing (GC) + CPU Offload Interaction

Block-level gradient checkpointing recomputes forward passes during backward. If your Text Encoder was offloaded to CPU *before* the backward pass, the recompute will try to use tensors that are no longer on GPU.

**Symptom**: `RuntimeError: Expected all tensors to be on the same device` during backward.

**Fix**: wrap the TE encoding call in `torch.no_grad()` so those tensors are excluded from the autograd graph entirely — GC won't try to recompute through them:

```python
with torch.no_grad():
    prompt_emb = text_encoder(tokens)   # excluded from autograd graph
text_encoder.to("cpu")                  # safe to offload now
torch.cuda.empty_cache()
```

---

### 4. LoRA Toggle Correctness

During trajectory collection, LoRA must be completely disabled. During student training steps, it must be enabled. Mixing them silently produces wrong training targets.

```python
# WRONG: LoRA partially active / wrong state
model.train()  # doesn't control LoRA state

# RIGHT: explicit toggle
def set_lora_enabled(model, enabled: bool):
    for module in model.modules():
        if isinstance(module, BaseTunerLayer):
            module.enable_adapters(enabled)

with set_lora_enabled(model, False):   # Teacher collection
    trajectory = collect_teacher(...)

with set_lora_enabled(model, True):    # Student training
    loss = train_student_step(...)
```

---

## Quick Reference

### Should You Use Distillation?

| Requirement | Recommendation |
|-------------|---------------|
| Need < 10-step inference | Trajectory Distillation (2nd gen) |
| Need good quality at <20 steps | End-to-end distillation (1st gen) |
| No training budget | Teacher-free / consistency model |
| Need absolute quality, no latency constraint | No distillation, use full steps |

### Three Generations at a Glance

| | 1st Gen (Online) | 2nd Gen (Trajectory) | 3rd Gen (Teacher-free) |
|---|:---:|:---:|:---:|
| Teacher GPU time | Full training | Pre-compute once | None |
| Step compression | ~2.7× | **>6×** | Variable |
| Quality | Good | **Better** | Acceptable |
| Storage overhead | Low | High (trajectory tensors) | None |
| Implementation complexity | Low | High | Medium |

### Key Experiment Numbers (H100, 20B DiT)

| Metric | Value | Notes |
|--------|-------|-------|
| Training loss reduction | Significant | Multi-epoch, monotonic |
| Training time | A few hours | Single GPU |
| Teacher inference | Baseline | Full denoising schedule, with CFG |
| Student inference | **~5× faster** | Reduced schedule, with CFG |
| Final cosine similarity (latent) | >0.98 | |
| Quality (SSIM vs teacher) | High | Majority of samples Good or better |
| GPU memory (training) | Well within single-GPU capacity | |
| GPU memory (inference) | Similar to teacher | |

### Further Reading

| Resource | What It Covers |
|----------|----------------|
| [Progressive Distillation (Salimans, 2022)](https://arxiv.org/abs/2202.00512) | The 1st-gen foundation paper |
| [Consistency Models (Song, 2023)](https://arxiv.org/abs/2303.01469) | Teacher-free approach |
| [TwinFlow](https://arxiv.org/abs/2503.00120) | Offline trajectory distillation (2nd gen) |
| [DiffSynth-Studio Distill-LoRA](https://huggingface.co/DiffSynth-Studio/Qwen-Image-Distill-LoRA) | End-to-end community implementation |

---

**Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer
