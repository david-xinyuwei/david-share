# Azure NC RTX Pro 6000 V6 BSE 完整对比测试报告

> 全面对比NC RTX 6000 Pro Blackwell /NC H100 NVL /NC A100 PCIe /NV A10 四款 GPU
>
> For fairness, each test is performed using the same data type across all four GPUs.

---

## 测试环境

### 硬件配置

| 配置项 | RTX 6000 Pro Blackwell | H100 NVL | A100 PCIe | A10 |
|--------|------------------------|----------|-----------|-----|
| **GPU 型号** | RTX Pro 6000 Blackwell DC-4-96Q | NVIDIA H100 NVL | NVIDIA A100 80GB PCIe | NVIDIA A10-24Q (vGPU) |
| **架构** | Blackwell (GB202) | Hopper (GH100) | Ampere (GA100) | Ampere (GA102) |
| **显存** | 96 GB GDDR7 | 94 GB HBM3 | 80 GB HBM2e | 24 GB GDDR6 |

### GPU硬件单元说明

| 硬件单元 | 功能 | 典型应用 |
|----------|------|----------|
| **NVDEC** | 视频解码 (H.264/H.265/AV1 → 原始帧) | 视频播放、AI 视频分析预处理 |
| **NVENC** | 视频编码 (原始帧 → MP4) | 直播推流、视频导出、云游戏 |
| **NVJPG** | JPEG 硬件加速编解码 | 批量图像处理、训练数据预处理 |
| **Tensor Core** | AI 矩阵乘法加速 | LLM、Stable Diffusion、视频生成 |
| **RT Core** | 光线追踪计算 | 游戏光追、3D 渲染、CAD 预览 |
| **CUDA Core** | 通用并行计算 | 所有 GPU 计算的基础 |

### 硬件单元配置矩阵

| 硬件单元 | RTX 6000 Pro Blackwell | H100 NVL | A100 PCIe | A10 |
|----------|------------------------|----------|-----------|-----|
| **NVDEC** (解码器) | ✅ 4个 (第6代) | ✅ 7个 | ✅ 5个 | ✅ 2个 |
| **NVENC** (编码器) | ✅ **4个 (第9代, AV1)** | ❌ **无** | ❌ **无** | ✅ 1个 (第7代) |
| **NVJPG** | ✅ 支持 | ✅ 7个 | ✅ 5个 | ❌ 不支持 |
| **Tensor Core** | ✅ 第5代 | ✅ 第4代 | ✅ 第3代 | ✅ 第3代 |
| **RT Core** | ✅ **188个 (第4代)** | ❌ **无** | ❌ **无** | ✅ 72个 (第2代) |
| **NVLink** | ❌ 无 | ✅ 支持 | ✅ 支持 | ❌ 无 |

---

## 场景支持矩阵

### AI 场景

| 场景 | 所需硬件 | RTX 6000 | H100 | A100 | A10 |
|------|----------|----------|------|------|-----|
| LLM 训练 (>70B) | Tensor Core + NVLink + 大显存 | ❌ | ✅ | ✅ | ❌ |
| LLM 微调 (7B-70B) | Tensor Core + 大显存 | ✅ | ✅ | ✅ | ⚠️ |
| LLM 推理 | Tensor Core | ✅ | ✅ | ✅ | ⚠️ |
| AI 图像生成 (SD/FLUX) | Tensor Core | ✅ | ✅ | ✅ | ✅ |
| **AI 视频生成 (含 MP4 输出)** | Tensor Core + **NVENC** | ✅ | ❌ | ❌ | ✅ |

### 视频/媒体场景

| 场景 | 所需硬件 | RTX 6000 | H100 | A100 | A10 |
|------|----------|----------|------|------|-----|
| **视频转码** | NVDEC + **NVENC** | ✅ | ❌ | ❌ | ✅ |
| 仅视频解码 | NVDEC | ✅ | ✅ | ✅ | ✅ |
| **直播推流** | **NVENC** | ✅ | ❌ | ❌ | ✅ |
| 视频 AI 分析 | NVDEC + Tensor Core | ✅ | ✅ | ✅ | ✅ |

### 游戏/渲染场景

| 场景 | 所需硬件 | RTX 6000 | H100 | A100 | A10 |
|------|----------|----------|------|------|-----|
| **云游戏** | RT Core + NVENC | ✅ | ❌ | ❌ | ✅ |
| **3D 渲染 (光追)** | **RT Core** | ✅ | ❌ | ❌ | ✅ |
| Blender 渲染 | RT Core | ✅ | ❌ | ❌ | ✅ |
| CAD 实时预览 | RT Core + CUDA | ✅ | ❌ | ❌ | ✅ |
| VDI (虚拟桌面) | NVENC + 图形 | ✅ | ❌ | ❌ | ✅ |

### 🎯 选型三大原则

1. **需要视频编码输出？** → 必须有 NVENC → **排除 H100 / A100**
2. **需要光线追踪？** → 必须有 RT Core → **排除 H100 / A100**
3. **纯 AI 计算？** → 看 Tensor Core + 显存 + NVLink

---

## 1. 网络配置测试 

### 测试结果

| 项目 | Standard_NC256ds_xl_RTXPRO6000BSE_v6 结果 |
|------|------------------|
| **网卡型号** | Microsoft Azure Network Adapter (MANA) |
| **Azure 带宽上限** | **100 Gbps** |
| **实测带宽 (单流)** | 30 Gbps |
| **实测带宽 (16流)** | **50 Gbps** |
| **RDMA/RoCE** | ❌ 不支持 |
| **InfiniBand** | ❌ 不支持 |

### 结论

- RTX 6000 VM 使用 Azure MANA 以太网，最高 100 Gbps
- 无 RDMA/InfiniBand 支持，不适合多节点 GPU 通信密集型训练

---

## 2. GPU P2P 互联测试

### 测试结果

| 项目 | Standard_NC256ds_xl_RTXPRO6000BSE_v6 结果 |
|------|---------------|
| **nvidia-smi topo -p2p** | OK (硬件层面支持) |
| **PyTorch can_device_access_peer()** | **False** (实测仍达 ~43 GB/s) |
| **GPU0 → GPU1 带宽** | **41.26 GB/s** |
| **GPU1 → GPU0 带宽** | **44.46 GB/s** |
| **NCCL AllReduce** | **~43.5 GB/s** |

### P2P 对比

| GPU 配置 | P2P 带宽 | 说明 |
|----------|----------|------|
| **RTX 6000 MIG** | ~43 GB/s | PCIe Gen5 |
| **H100 NVL** | ~450 GB/s | NVLink 4.0 直连 |
| **A100 PCIe** | ~25 GB/s | PCIe Gen4 |

---

## 3. FP32 算力测试

### 测试结果

| 指标 | RTX 6000 Pro Blackwell |
|------|------------------------------|
| **理论 FP32** | 116.95 TFLOPS |
| **实测峰值** | **109.20 TFLOPS** |
| **效率** | **93.4%** |
| **SM 数量** | 188 |
| **CUDA Cores** | 24,064 |

---

## 4. LLM 推理测试

### 测试配置

| 参数 | 值 |
|------|-----|
| **模型** | microsoft/Phi-3.5-mini-instruct (3.8B) |
| **推理引擎** | vLLM |
| **测试工具** | guidellm |

### 测试结果

| GPU | Output Tokens/s | 相对性能 |
|-----|-----------------|----------|
| **H100 NVL** | **3083.6** | **100%** (基准) |
| **RTX 6000 Blackwell MIG** | **2835.4** | **92.0%** |
| **A100 PCIe** | **2119.6** | **68.7%** |
| **A10 24GB** | **563.1** | **18.3%** |

### 可视化

```
Output Tokens/s (越高越好)
════════════════════════════════════════════════════════════
H100 NVL        ██████████████████████████████████████████  3083.6 tok/s (100%)
RTX 6000 BW     ██████████████████████████████████████▌     2835.4 tok/s (92%)
A100 PCIe       ███████████████████████████▍                2119.6 tok/s (69%)
A10 24GB        ███████▎                                    563.1 tok/s (18%)
════════════════════════════════════════════════════════════
```

---


## 4.1 NVFP4 (W4A4) 量化推理 Benchmark (RTX PRO 6000 Blackwell 专属)

> ⚠️ **Blackwell 独占功能**: NVFP4 需要 SM120 原生 FP4 Tensor Core，仅 RTX PRO 6000 Blackwell 支持

### 测试背景

NVFP4 (NV FP4 W4A4) 是 NVIDIA Blackwell 架构的独特优势：
- **W4A4**: 权重 4-bit + 激活 4-bit，比 FP8 (W8A8) 更激进的量化
- **仅 Blackwell 支持**: 需要 SM100/SM120 的原生 FP4 Tensor Core
- **显存节省**: 模型体积比 FP8 小约 35% (9.9GB vs 15.3GB for 14B)

### 测试配置

| 参数 | 值 |
|------|-----|
| **模型** | Qwen3-14B-NVFP4 (RedHatAI 预量化) vs Qwen3-14B-FP8 |
| **量化格式** | NVFP4 W4A4 (compressed-tensors) |
| **测试工具** | vLLM 0.12.0 (原生 CUTLASS NVFP4 kernel) |
| **负载** | 200 prompts, 512 input tokens, 128 output tokens |
| **测试条件** | 完全相同的 input/output tokens，公平对比 |

### 测试结果

| 精度 | 模型 | Input Tokens | Output Tokens | Time | Output TPS |
|------|------|--------------|---------------|------|------------|
| **NVFP4 (W4A4)** | Qwen3-14B-NVFP4 | 102,400 | 25,600 | 9.22s | **2,777 tok/s** |
| **FP8 (W8A8)** | Qwen3-14B-FP8 | 102,400 | 25,600 | 12.75s | **2,009 tok/s** |

### 性能对比

```
NVFP4 vs FP8 (Qwen3-14B, RTX PRO 6000 Blackwell)
════════════════════════════════════════════════════════════
NVFP4 (W4A4)    ██████████████████████████████████████████  2,777 tok/s (+38%)
FP8 (W8A8)      ██████████████████████████████              2,009 tok/s (基准)
════════════════════════════════════════════════════════════
```

### 关键指标对比

| 指标 | NVFP4 (W4A4) | FP8 (W8A8) | 差异 |
|------|--------------|------------|------|
| **Output TPS** | **2,777** | 2,009 | **+38%** |
| **模型体积** | **9.9 GB** | 15.3 GB | **-35%** |
| **KV Cache 可用** | 65.5 GiB | 60.1 GiB | +9% |
| **推理时间** | **9.22s** | 12.75s | **-28%** |

### 踩坑记录 ⚠️

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| NVFP4 模型加载为 BF16 | SGLang 0.5.x 不识别 NVFP4 格式 | 改用 vLLM |
| vLLM 0.13.0 显示 "platform does not support cutlass NVFP4" | vLLM 0.13.0 移除了 SM120 NVFP4 支持 | **降级到 vLLM 0.12.0** |
| FlashInfer 0.5.3 无 fp4 模块 | 版本太旧 | 编译 FlashInfer 0.6.0rc2 |
| 首次测试 input tokens 不一致 | 不同 tokenizer 编码差异 | 使用固定 token IDs 确保公平 |

### 环境要求

```bash
# 必须使用 vLLM 0.12.0 (0.13.0 不支持 SM120 NVFP4)
pip install vllm==0.12.0

# 验证 NVFP4 支持
python -c "from vllm._custom_ops import cutlass_scaled_mm_supports_fp4; print(f'NVFP4 support: {cutlass_scaled_mm_supports_fp4(120)}')"
# 预期输出: NVFP4 support: True
```

### 结论

1. **NVFP4 比 FP8 快 38%** - Blackwell 原生 FP4 Tensor Core 加速显著
2. **显存占用更低** - 更小的模型体积 = 更大的 KV Cache = 更高并发
3. **Blackwell 独占优势** - H100/A100 无法使用 NVFP4，只有 RTX PRO 6000 Blackwell 支持
4. **版本敏感** - 必须使用 vLLM 0.12.0，0.13.0 已移除 SM120 支持

> 💡 **推荐**: 在 RTX PRO 6000 Blackwell 上，优先使用 NVFP4 量化模型，可获得比 FP8 额外 38% 的性能提升。

---



## 4.1.1 张量并行 (TP=1 vs TP=2) 性能对比

> ⚠️ **RTX PRO 6000 双卡配置**: 测试何时使用 TP=2 能获得收益

### 背景

当单张 RTX PRO 6000 无法充分利用双卡优势（小模型），或大模型需要跨两张 GPU 进行张量并行时：
- **TP=1**: 单卡推理，模型完全放在一张 GPU 上
- **TP=2**: 张量并行跨 2 张 GPU，模型权重分布在两张卡上

### 测试配置

| 参数 | 值 |
|------|-----|
| **框架** | vLLM 0.12.0 |
| **小模型** | Qwen3-14B-FP8 (用于对比 TP 通信开销) |
| **大模型** | Qwen2.5-VL-72B-Instruct-FP8-dynamic |
| **测试工具** | vllm bench serve |
| **负载** | 64 prompts, 512 输入 tokens, 256 输出 tokens, 并发=16 |
| **KV Cache** | FP8 |

### 小模型结果 (Qwen3-14B-FP8)

| 配置 | 输出吞吐量 | TTFT | TPOT |
|------|----------:|-----:|-----:|
| **TP=1** | **276.02 tok/s** | 1036 ms | 49.40 ms |
| **TP=2** | 266.19 tok/s | 1252 ms | 52.16 ms |
| **差异** | **-3.6%** | +21% 更慢 | +5.6% 更慢 |

> ⚠️ **14B 模型太小，TP=2 反而更慢** - GPU 间通信开销超过了并行计算收益。

### 大模型结果 (Qwen2.5-VL-72B-FP8)

| 配置 | 输出吞吐量 | TTFT | TPOT |
|------|----------:|-----:|-----:|
| **TP=1** | 232.02 tok/s | 1695 ms | 62.57 ms |
| **TP=2** | **294.77 tok/s** | 1801 ms | 47.42 ms |
| **差异** | **+27.0%** | +6.3% 更慢 | **-24.2% 更快** |

### 鲁棒性验证 (第二次重测)

为验证测试结果的稳定性和可重复性，我们在第二天重新运行了相同测试：

| 指标 | 第1天 TP=1 | 第2天 TP=1 | 波动 | 第1天 TP=2 | 第2天 TP=2 | 波动 |
|------|-----------|-----------|------|-----------|-----------|------|
| **输出吞吐量** | 232.02 tok/s | 231.50 tok/s | **-0.2%** | 294.77 tok/s | 296.46 tok/s | **+0.6%** |
| **TPOT** | 62.57 ms | 62.40 ms | -0.3% | 47.42 ms | 46.76 ms | -1.4% |
| **TTFT** | 1695 ms | 1779 ms | +5.0% | 1801 ms | 1891 ms | +5.0% |

> ✅ **结论：测试结果高度稳定** - 吞吐量波动 <1%，具有良好的可重复性。

### GPU 间通信带宽 (PCIe Gen5，无 NVLink)

TP=2 推理时，两张 GPU 通过 PCIe 通信。实测 P2P 带宽：

| 方向 | 带宽 | 说明 |
|------|------|------|
| **GPU0 → GPU1** | **41.26 GB/s** | PCIe Gen5 x16 |
| **GPU1 → GPU0** | **44.46 GB/s** | PCIe Gen5 x16 |
| **NCCL AllReduce** | **~43.5 GB/s** | 双向聚合 |

> ⚠️ **PCIe Gen5 (单向 ~43 GB/s) 带宽有限** - NVLink 单向约 450 GB/s（快约 10 倍）。PCIe 是 TP>1 的瓶颈。72B 模型仍可获得 27% 提升，但更大模型或 TP>2 可能受限。

### 可视化

```
TP=1 vs TP=2 输出吞吐量对比
═════════════════════════════════════════════════════════════
Qwen3-14B (小模型 - TP 通信开销占主导)
  TP=1    ██████████████████████████████████████████  276.02 tok/s (基准)
  TP=2    ████████████████████████████████████████▌   266.19 tok/s (-3.6%)

Qwen2.5-VL-72B (大模型 - TP 收益显现)
  TP=1    ██████████████████████████████████████      232.02 tok/s (基准)
  TP=2    ████████████████████████████████████████████████  294.77 tok/s (+27%)
═════════════════════════════════════════════════════════════
```

### 关键发现

1. **模型大小决定 TP 收益**
   - 小模型 (<30B): TP=2 增加开销，**建议使用 TP=1**
   - 大模型 (>70B): TP=2 提供 **25-35% 加速**

2. **TPOT (每 Token 生成时间) 在 TP=2 下显著改善**
   - 72B 模型: 62.57ms → 47.42ms (**每 token 快 24%**)
   - 原因是跨 2 张 GPU 的并行矩阵运算

3. **TTFT (首 Token 时间) 在 TP=2 下略有增加**
   - 跨 GPU 同步增加约 100ms 延迟
   - 但吞吐量提升足以弥补这一代价

### 配置建议

| 模型大小 | 推荐配置 | 原因 |
|---------|---------|------|
| **<30B 参数** | **TP=1** | 通信开销 > 并行收益 |
| **30B-70B 参数** | 需测试 | 取决于具体模型架构 |
| **>70B 参数** | **TP=2** | 25-35% 吞吐提升 |

> 💡 **经验法则**: 只有当单卡无法舒适地容纳模型，或模型足够大 (>70B) 能从并行计算中获益时，才使用 TP=2。

---
## 4.2 SGLang BF16/FP8 三卡对比 (200 并发)

> 测试日期: 2025-12 | 框架: SGLang 0.5.6.post2 + FlashInfer 0.5.3

### 测试背景

对比 H100、RTX PRO 6000、A100 三款 GPU 在 **高并发 (200 prompts)** 场景下的 BF16 与 FP8 推理性能差异：

- **BF16**: 原始精度，无量化
- **FP8**: 预量化模型 (RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic)
- **原生 FP8 Tensor Core**: H100 (Hopper) 和 RTX PRO 6000 (Blackwell) 支持原生 FP8，A100 需要 Marlin fallback

### 测试配置

| 参数 | 值 |
|------|-----|
| **框架** | SGLang 0.5.6.post2 |
| **FlashInfer** | 0.5.3 |
| **模型 (BF16)** | Qwen/Qwen2.5-14B-Instruct |
| **模型 (FP8)** | RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic |
| **并发** | 200 prompts |
| **输入** | 512 tokens |
| **输出** | 128 tokens |
| **request_rate** | inf (压力测试) |
| **random_range_ratio** | 0.0 (固定长度) |

### 测试结果

| GPU | BF16 (tok/s) | FP8 (tok/s) | FP8 vs BF16 | FP8 实现 |
|-----|-------------:|------------:|:-----------:|:--------:|
| **H100 NVL 96GB** | 2,197 | 2,681 | **+22%** | 原生 FP8 Tensor Core |
| **RTX PRO 6000 96GB** | 1,579 | 2,353 | **+49%** | 原生 FP8 Tensor Core |
| **A100 80GB PCIe** | 1,196 | - | - | Marlin fallback |

> ⚠️ **A100 说明**: A100 SGLang 200 并发仅有 BF16 测试数据，FP8 测试未保存。A100 无原生 FP8 Tensor Core，需要 Marlin kernel fallback。

### 可视化

```
SGLang 200 并发 BF16 吞吐量 (tok/s)
═════════════════════════════════════════════════════════════
H100 NVL        ████████████████████████████████████████████  2,197 tok/s
RTX PRO 6000    ████████████████████████████████              1,579 tok/s
A100 PCIe       ████████████████████████                      1,196 tok/s
═════════════════════════════════════════════════════════════

SGLang 200 并发 FP8 吞吐量 (tok/s)
═════════════════════════════════════════════════════════════
H100 NVL        ████████████████████████████████████████████  2,681 tok/s
RTX PRO 6000    ████████████████████████████████████████      2,353 tok/s
A100 PCIe       (未测试)
═════════════════════════════════════════════════════════════
```

### 测试方法

```bash
# SGLang 服务启动 (BF16)
python -m sglang.launch_server \
  --model-path Qwen/Qwen2.5-14B-Instruct \
  --dtype bfloat16 \
  --tp 1 --port 30000

# SGLang 服务启动 (FP8, RTX PRO 6000 最佳配置)
python -m sglang.launch_server \
  --model-path RedHatAI/Qwen2.5-14B-Instruct-FP8-dynamic \
  --attention-backend triton \
  --kv-cache-dtype fp8_e4m3 \
  --tp 1 --port 30000

# Benchmark 命令
python -m sglang.bench_serving --backend sglang \
  --dataset-name random --num-prompts 200 \
  --random-input-len 512 --random-output-len 128 \
  --random-range-ratio 0.0 \
  --host 127.0.0.1 --port 30000
```

### 踩坑记录 ⚠️

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| **吞吐量差 3 倍** | `--random-range-ratio` 默认 1.0 (随机长度) | 对标测试用 **0.0** (固定长度) |
| **Runtime 量化 OOM** | `--quantization fp8` 启动时 OOM | 必须用 **预量化 FP8 模型** |
| **FlashInfer 版本** | v0.2.0 比 FA2 慢 1.5x | 用 **v0.5.3+** |
| **复现结果不一致** | total_input_tokens 不同 | **先对比 JSON 输出的 total_input_tokens** |

### 关键发现

1. **FP8 原生支持差异显著**
   - H100/RTX PRO 6000: 原生 FP8 Tensor Core，加速比 22-49%
   - A100: Marlin fallback，加速比约 29% (基于 vLLM 50 并发数据)

2. **RTX PRO 6000 FP8 加速比最高 (+49%)**
   - Blackwell 架构 FP8 优化更激进
   - 从 1,579 提升到 2,353 tok/s

3. **测试参数影响巨大**
   - `random_range_ratio=0.0`: 测缓存友好极限 (Radix Cache 命中)
   - `random_range_ratio=1.0`: 测真实负载场景 (无缓存)

---


## 5. SFT 全参微调测试

### 测试配置

| 参数 | 值 |
|------|-----|
| **模型** | Qwen/Qwen3-8B-Base (8.19B 参数) |
| **训练类型** | Full Fine-Tuning |
| **精度** | BF16 |

### 测试结果

| GPU | 训练时间 | 速度 (s/step) | 相对 H100 |
|-----|---------|--------------|-----------|
| **H100 NVL** | **19.74 min** | **11.84** | **100%** |
| **RTX 6000 MIG** | 25.14 min | 15.09 | 78.5% |
| **A100 PCIe** | 36.98 min | 22.19 | 53.4% |

---

## 6. FLUX 图像生成测试

### 测试配置

| 参数 | 值 |
|------|-----|
| **模型** | FLUX.1 schnell (12B 参数) |
| **分辨率** | 1024×1024 |
| **推理步数** | 4 steps |

### 测试结果

| GPU | 平均时间 | 每分钟生成 | 相对性能 |
|-----|---------|-----------|----------|
| **H100 NVL** | **1.25s** | **47.8 张** | **100%** |
| **RTX 6000** | **1.42s** | **42.3 张** | **88%** |
| **A100 PCIe** | **2.16s** | **27.8 张** | **58%** |
| **A10 24GB** | ❌ **OOM** | - | - |

---

## 7. Blender 渲染测试

### 测试结果

| GPU | **纯渲染时间** | 相对性能 |
|-----|---------------|----------|
| **RTX 6000** | **~2.15s** | **3.76x** ✅ |
| **A10** | **~8.08s** | 1.00x (基准) |

> **说明**: H100/A100 无 RT Core，不适合光追渲染

---

## 8. NVENC 视频编码测试

### 单流测试结果 (H.264)

| Preset | RTX 6000 | A10 | 胜出 |
|--------|----------|-----|------|
| **P1 (最快)** | 167 fps | 197 fps | A10 +18% |
| **P4 (平衡)** | **129 fps** | 97 fps | **RTX 6000 +33%** ✅ |
| **P7 (高质量)** | **87 fps** | 60 fps | **RTX 6000 +45%** ✅ |

### 多流并行测试

| 并行流数 | RTX 6000 | A10 | 倍数 |
|---------|----------|-----|------|
| 1 流 | 98 fps | 87 fps | 1.13x |
| 4 流 | **313 fps** | 87 fps* | **3.6x** |
| 12 流 | **348 fps** | 87 fps* | **4.0x** |

> *A10 vGPU 模式仅支持单流并行  
> **注意**: H100/A100 无 NVENC，无法进行此测试

---

## 四款 GPU 综合对比

### 🏆 场景推荐

| 使用场景 | 推荐 GPU | 理由 |
|----------|----------|------|
| **3D 渲染/动画** | 🥇 **RTX 6000** | RT Core 碾压级优势，H100/A100 不支持 |
| **AI 图像生成 (追求性能)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 最快，RTX 6000 比 A100 快 52% |
| **视频转码 (多流)** | 🥇 **RTX 6000** > 🥈 A10 | 4x 吞吐量优势，H100/A100 不支持 |
| **AI 视频生成 (含 MP4 输出)** | 🥇 **RTX 6000** > 🥈 A10 | H100/A100 无 NVENC，无法输出视频 |
| **LLM 推理 (追求性能)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 最快，RTX 6000 达 92% |
| **LLM 训练 (>70B 大模型)** | 🥇 H100 > 🥈 A100 | 需要 NVLink 多卡并行，RTX 6000 不支持 |
| **SFT 微调 (追求性能)** | 🥇 H100 > 🥈 RTX 6000 > 🥉 A100 | H100 最快，RTX 6000 比 A100 快 47% |
| **云游戏/VDI** | 🥇 **RTX 6000** > 🥈 A10 | RT Core + NVENC，H100/A100 不支持 |
| **直播推流** | 🥇 **RTX 6000** > 🥈 A10 | NVENC 第9代 vs 第7代，H100/A100 无 NVENC |

### 定位总结

| GPU | 定位 | 优势 | 限制 |
|-----|------|------|------|
| **RTX 6000** | 全能专业卡 | 硬件单元齐全，完整流水线，96GB GDDR7，128 vCPU | 无 NVLink |
| **H100** | 纯 AI 算力卡 | 最强 Tensor Core，94GB HBM3，NVLink | **无 NVENC，无 RT Core** |
| **A100** | AI 训练/推理 | 生态成熟，80GB HBM2e，NVLink | **无 NVENC，无 RT Core** |
| **A10** | 推理/图形/VDI | 有 NVENC + RT Core，支持分片 GPU，440GB 内存 | 显存较小 (24GB) |


---

## 📦 仓库结构

```
NC-RTX-Pro-6000V6-BSE-Benchmark/
├── README.md                      # 英文文档
├── README-CN.md                   # 中文文档（本文件）
├── benchmark_tp_comparison.py     # TP=1 vs TP=2 性能对比脚本
├── gpu_p2p_bandwidth_test.py      # GPU P2P 带宽测试脚本
└── requirements.txt               # Python 依赖
```

---

## 🚀 快速开始

### 环境准备

```bash
# 创建 conda 环境（推荐）
conda create -n vllm012 python=3.11
conda activate vllm012

# 安装依赖
pip install -r requirements.txt
```

### 运行 TP 性能对比测试

比较张量并行（TP=1 vs TP=2）对推理性能的影响：

```bash
# TP=1 测试（单卡）
python benchmark_tp_comparison.py \
    --model Qwen/Qwen2.5-VL-72B-Instruct-FP8 \
    --tp 1 \
    --port 8000

# TP=2 测试（双卡）
python benchmark_tp_comparison.py \
    --model Qwen/Qwen2.5-VL-72B-Instruct-FP8 \
    --tp 2 \
    --port 8001
```

### GPU P2P 带宽测试

测量 GPU 之间的点对点通信带宽：

```bash
python gpu_p2p_bandwidth_test.py
```

RTX PRO 6000 预期输出（PCIe Gen5，无 NVLink）：
- GPU0 → GPU1: ~41-44 GB/s
- GPU1 → GPU0: ~41-44 GB/s

---

## 📊 脚本说明

| 脚本 | 用途 | 关键指标 |
|------|------|----------|
| `benchmark_tp_comparison.py` | 比较 TP=1 vs TP=2 推理性能 | 输出吞吐量 (tok/s)、TTFT、TPOT |
| `gpu_p2p_bandwidth_test.py` | 测量 GPU P2P 带宽 | 带宽 (GB/s)、NVLink/PCIe 检测 |

---
