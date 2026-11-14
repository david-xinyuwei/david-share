# DL Algorithm Insights

One algorithm or systems topic per folder, explained in depth, from the math and data layout down to kernels and clusters, and checked with experiments.

[Back to the main page](../README.md)

## Systems: from kernels to clusters

| Project | What it covers |
|---|---|
| [GPU-Kernel-Stack-And-Toolchain](GPU-Kernel-Stack-And-Toolchain/) | How one line of PyTorch reaches the GPU: operators, kernels, data layout and the full toolchain |
| [Tile-Layout-MLIR-Lowering](Tile-Layout-MLIR-Lowering/) | How a GPU kernel written in Python becomes machine code: tile, layout, MLIR, NVVM and ROCDL (in Chinese) |
| [Attention-Memory-And-Parallelism](Attention-Memory-And-Parallelism/) | From KV-cache layout to 32 GPUs: attention, memory and parallelism |
| [Correctness-Training-And-Evaluation](Correctness-Training-And-Evaluation/) | Why a running system is not yet a valid conclusion: correctness, MTP, online RL and evaluation |
| [KV-Cache-5D-Layout](KV-Cache-5D-Layout/) | Why precision, paging and physical memory layout are three different things, and what "5D" actually rearranges |
| [Long-Context-Efficient-Attention](Long-Context-Efficient-Attention/) | Long-context efficient attention: CSA + HCA from DeepSeek-V4 |
| [Gated-DeltaNet-Linear-Attention](Gated-DeltaNet-Linear-Attention/) | Gated DeltaNet: from softmax attention to linear attention with the delta rule |

## Training, distillation and evaluation

| Project | What it covers |
|---|---|
| [Multi-Expert-OPD-Distillation](Multi-Expert-OPD-Distillation/) | How DeepSeek-V4 merges 10+ experts with on-policy distillation, verified on Azure |
| [Diffusion-Distillation](Diffusion-Distillation/) | Training a student model to do in 8 steps what a teacher model does in 40 |
| [LoRA-Merge-Quality-Impact](LoRA-Merge-Quality-Impact/) | fuse_lora vs set_adapters: quality impact on diffusion models |
| [Benchmark-Contamination-Detection](Benchmark-Contamination-Detection/) | How to tell whether an LLM has already seen the test set |
| [Image-Similarity-Metrics](Image-Similarity-Metrics/) | How similar are two images? MSE, SSIM, LPIPS, FID and CLIP score compared |
