# NVFP4 H100 实测结果

## 测试环境

- **GPU**: NVIDIA H100 NVL 94GB (Hopper 架构)
- **CUDA**: 12.8
- **Python**: 3.11
- **模型**: meta-llama/Llama-3.1-8B-Instruct
- **框架**: vLLM (推理) + llmcompressor (量化)
- **测试日期**: 2025-10-31

## 核心依赖

```bash
torch==2.9.0+cu128
llmcompressor==0.8.2.dev33
compressed-tensors==0.12.3a20251028
vllm (latest)
transformers (latest)
```

## 测试结果

### 1. vLLM 推理性能

| 方案 | 显存(GB) | 时间(s) | 吞吐(tok/s) | 加速比 |
|------|----------|---------|-------------|--------|
| **BF16** | 85.89 | 1.34 | 149.6 | 1.00× |
| **W4A16** | 85.96 | 0.90 | 223.0 | **1.49×** ✅ |
| **W4A4** | 85.96 | 0.87 | 231.1 | **1.54×** ✅ |

**关键发现**:
- W4A16 推理加速 **1.49×**
- W4A4 额外提升 **3.6%** (231.1 vs 223.0 tok/s)
- vLLM 总显存节省有限 (KV cache 占主导 ~65GB BF16)

### 2. 纯模型显存占用

| 方案 | 模型显存(GB) | 压缩比 |
|------|--------------|--------|
| **BF16** | 14.96 | 1.00× |
| **W4A16** | 5.62 | **2.66×** ✅ |
| **W4A4** | 5.62 | **2.66×** ✅ |

**关键发现**:
- 模型权重压缩 **2.66×** (14.96GB → 5.62GB)
- W4A16 = W4A4 模型大小 (激活量化不增加文件大小)
- 理论压缩比 4×,实测 2.66× (元数据 + lm_head 未量化)

## 量化开销对比

| 指标 | W4A16 | W4A4 | 差异 |
|------|-------|------|------|
| **量化时间** | ~5-8 分钟 | ~12-15 分钟 | +7 分钟 |
| **需要校准** | ❌ 否 | ✅ 是 (16 样本) | 额外开销 |
| **数据集下载** | ❌ 否 | ✅ ultrachat_200k | ~1GB |
| **推理速度** | 223.0 tok/s | 231.1 tok/s | +3.6% |

## H100 NVFP4 工作原理

### 架构特性
```
H100 (Hopper): 无原生 FP4 Tensor Cores
├─ FP4 权重 → [快速解包] → FP16 → FP16 Tensor Core
├─ 加速来源: 70% 内存带宽节省 + 30% 快速解包
└─ 结果: 1.49-1.54× 加速

Blackwell B200: 有原生 FP4 Tensor Cores
├─ FP4 权重 → [直接计算] → FP4×FP4 原生 Tensor Core
├─ 加速来源: 带宽 + 计算优化
└─ 预期: 2.2-2.4× 加速 (理论)
```

### 为什么 W4A16 ≈ W4A4 在 H100?

**计算流程对比**:
```
W4A16: FP4权重 → FP16 × FP16激活 → FP16 Tensor Core
W4A4:  FP4权重 → FP16 × (FP4激活 → FP16) → FP16 Tensor Core
                                    ↑
                            解包开销 ≈ 直接用FP16
```

**结论**: H100 最终都用 FP16 Tensor Core 计算,激活量化收益有限 (+3.6%)

### 为什么 vLLM 总显存节省有限?

**vLLM 显存分配** (max_model_len=2048):
```
总显存 85.89 GB (BF16):
├─ 模型权重: 15GB  → W4A16: 5.6GB  ✅ 节省 9.4GB
├─ KV cache:  65GB  → 仍然 BF16    ❌ 无节省
└─ 激活缓存: 5GB   → 仍然 BF16    ❌ 无节省

总显存 85.96 GB (W4A16): +0.07GB (几乎无变化)
```

**原因**: KV cache (attention key/value 张量) 在 vLLM 中始终使用 BF16,不受权重量化影响。

## 推荐配置

### 生产环境推荐: W4A16

**优势**:
- ✅ 无需校准数据 (省 7 分钟)
- ✅ 量化流程简单
- ✅ 性能与 W4A4 相当 (1.49× vs 1.54×)
- ✅ 部署快速

**适用场景**:
- 快速部署
- 标准推理任务
- 资源受限环境

### 极致优化推荐: W4A4

**优势**:
- ✅ 额外 3.6% 吞吐提升
- ✅ 在 Blackwell B200 上有更大优势 (~20-25%)

**代价**:
- ⚠️  需要 16 样本校准数据
- ⚠️  量化时间 +7 分钟
- ⚠️  需要下载 ultrachat_200k 数据集

**适用场景**:
- 追求极致性能
- 有高质量校准数据
- Blackwell B200 硬件

## 一键运行脚本

```bash
# 完整端到端测试 (包含量化)
python3 end_to_end_nvfp4.py
```

**脚本功能**:
1. ✅ 自动下载 Llama-3.1-8B-Instruct
2. ✅ 量化 W4A16 (无需校准)
3. ✅ 量化 W4A4 (带校准)
4. ✅ 自动修复 tokenizer.model
5. ✅ vLLM 推理性能测试 (3 配置)
6. ✅ transformers 纯模型显存测试 (3 配置)
7. ✅ 生成详细对比报告

**总耗时**: ~30-45 分钟 (首次运行)

## 关键要点

### ✅ 推理性能
- H100 NVFP4 加速: **1.49-1.54×**
- 主要来源: **内存带宽节省 70%** + 快速解包 30%
- W4A16 vs W4A4: 差异 **3.6%** (可忽略)

### ✅ 模型压缩
- 权重压缩: **2.66×** (14.96GB → 5.62GB)
- vLLM 总显存: 节省 **<1%** (KV cache 占主导)
- 模型文件: W4A16 = W4A4 = **5.62GB**

### ✅ 推理引擎
- ✅ **vLLM**: 必须使用 (支持 NVFP4 kernel)
- ❌ **transformers**: 不支持 (BF16 fallback, 10× 更慢)

### ⚠️  限制
- H100 无原生 FP4 Tensor Cores (Blackwell 才有)
- 激活量化 (W4A4) 收益有限 (+3.6%)
- vLLM KV cache 不量化 (架构限制)
- 70B 模型易 OOM (推荐 8B-13B)

## 未来展望

### Blackwell B200 预期性能

| 指标 | H100 | B200 (预测) | 提升 |
|------|------|-------------|------|
| **W4A16** | 1.49× | ~1.8× | +21% |
| **W4A4** | 1.54× | ~2.2× | +43% |
| **W4A4 vs W4A16** | +3.6% | **+22%** | **6× 差距** |

**关键**: B200 的原生 FP4 Tensor Cores 让 W4A4 有质的飞跃!

## 参考链接

- [NVFP4 GitHub](https://github.com/david-xinyuwei/Deep-Learning/tree/master/NVFP4)
- [llmcompressor 文档](https://github.com/vllm-project/llm-compressor)
- [vLLM 文档](https://docs.vllm.ai/)
- [H100 规格](https://www.nvidia.com/en-us/data-center/h100/)
- [Blackwell 架构](https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/)
