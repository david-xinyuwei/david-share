# GPT-Image-2 Token Bucket 机制实测 — Azure OpenAI

本仓库通过实测验证 OpenAI GPT-Image-2 模型的 **Token Size Bucket** 机制，部署于 Azure OpenAI Service。核心问题：**`quality` 和 `size` 参数如何影响输出 Token 消耗和延迟？**

## Executive Summary

GPT-Image-2（`v2026-04-21`）使用**确定性 Token 分配**，由两个因素决定：`quality` 和 `size`。输出 Token **完全独立于 Prompt 内容** —— 相同的 quality+size 组合始终产生完全相同的 Token 数。

### Output Token 矩阵（3 种尺寸 × 3 种质量 = 9 种组合）

| Size ↓ \ Quality → | low | medium | high |
|:-------------------|:---:|:------:|:----:|
| **1024×1024**（正方形） | 208 | 805 | 3,171 |
| **1024×1536**（竖版） | 365 | 1,415 | 5,574 |
| **1536×1024**（横版） | 358 | 1,401 | 5,546 |

### 延迟矩阵（秒）

| Size ↓ \ Quality → | low | medium | high |
|:-------------------|:---:|:------:|:----:|
| **1024×1024** | 19.6 | 59.7 | 187.9 |
| **1024×1536** | 23.8 | 49.9 | 128.0 |
| **1536×1024** | 27.3 | 46.9 | 128.9 |

> **测试条件**：gpt-image-2 `v2026-04-21`，Azure OpenAI `api-version=2025-04-01-preview`，GlobalStandard 部署（capacity=9），East US 2 区域。Prompt："A golden retriever puppy in a sunlit meadow"（16 input tokens）。每种组合测试一次。延迟为客户端端到端测量（WSL on Windows，East US 区域）。

**核心发现**：

1. **Output tokens = f(size, quality)** —— Prompt 内容对输出 Token 无影响。通过 4 个不同 Prompt（3–20 词）在 1024×1024 low 下验证：全部返回 208 tokens。
2. **竖版/横版 Token 约为正方形的 1.75 倍** —— 与像素数之比 1.5 倍（1,572,864 vs 1,048,576 像素）基本吻合。
3. **竖版 ≈ 横版** —— 1024×1536 和 1536×1024 产生几乎相同的 Token（365 vs 358, 1415 vs 1401, 5574 vs 5546），存在轻微方向差异。
4. **延迟主要由 quality 决定**，与 size 关系不大 —— high quality 比 low 慢 2–10 倍，但更大尺寸不一定更慢。

## Background

### 什么是 "Token Size Bucket"？

[Introducing GPT-Image-2 in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) 博客描述了 **Mode 2 — Token size bucket selection** 机制：

- Routing layer 从 **6 个 Token 桶**中选择：16、24、36、48、64、96
- 映射到 Legacy Size Tier：`smimage`、`image`、`xlimage`
- 系统分析 Prompt 复杂度、细节需求和场景类型，自动选择桶

**这不是用户可配置的参数。** API 中没有 `token_bucket` 或 `output_token_count` 参数。用户通过以下方式间接影响 Token 分配：

1. **`quality` 参数**（low / medium / high）—— 主要控制手段
2. **`size` 参数**（1024x1024、1024x1536、1536x1024）—— 分辨率控制
3. **Prompt 复杂度** —— 系统可能根据 Prompt 分析调整分配

### 模型信息

| 属性 | 值 | 来源 |
|:-----|:---|:-----|
| Model（模型） | gpt-image-2 | [Azure Model Catalog](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) |
| Version（版本） | 2026-04-21 | `az cognitiveservices account list-models` |
| Status（状态） | Generally Available | Model catalog |
| Format（格式） | OpenAI | Azure deployment |
| Deprecation（退役） | 2027-04-21 | Model catalog |
| API Capabilities（能力） | imageGenerations, imageEdits, convo2im | Model capabilities |

### API 响应结构

GPT-Image-2 相比 GPT-Image-1.5 返回更丰富的响应结构：

```json
{
  "created": 1776825308,
  "background": "opaque",
  "data": [{ "b64_json": "<base64 image data>" }],
  "output_format": "png",
  "quality": "low",
  "size": "1024x1024",
  "usage": {
    "input_tokens": 9,
    "input_tokens_details": {
      "image_tokens": 0,
      "text_tokens": 9
    },
    "output_tokens": 208,
    "total_tokens": 217
  }
}
```

相比 GPT-Image-1.5 的新增字段：
- `background`："opaque"（或请求时可为 "transparent"）
- `output_format`："png" / "jpeg"
- `usage.input_tokens_details`：文本 vs 图像输入 Token 的细分
- 完整 `usage` 对象含 `output_tokens`（GPT-Image-1.5 在 `data[0]` 中使用 `num_output_tokens`）

## Methodology（测试方法）

### 测试设计

- **模型**：gpt-image-2 `v2026-04-21`，Azure OpenAI（East US 2）
- **API 版本**：`2025-04-01-preview`
- **部署**：GlobalStandard，capacity=9
- **尺寸**：1024x1024（固定）
- **Quality 级别**：low、medium、high
- **Prompt**：
  1. 简单：*"A simple red circle on white background"*（最简场景）
  2. 复杂：*"A photorealistic golden retriever puppy sitting in a sunlit meadow with wildflowers, shallow depth of field, professional photography"*（高复杂度场景）

### 变量控制

| 变量 | 状态 | 值 |
|:-----|:-----|:---|
| Model（模型） | 固定 | gpt-image-2 |
| Size（尺寸） | 固定 | 1024x1024 |
| n（数量） | 固定 | 1 |
| Quality（质量） | **变量** | low / medium / high |
| Prompt（提示词） | **变量** | Simple / Complex |

## Results（实测结果）

### 各 Quality 级别的 Token 使用量

| Prompt | Quality | Input Tokens | Output Tokens | Total Tokens |
|:-------|:--------|:------------|:-------------|:-------------|
| Simple ("red dot") | low | 9 | **208** | 217 |
| Simple ("red dot") | medium | 9 | **805** | 814 |
| Simple ("red dot") | high | 9 | **3,171** | 3,180 |
| Complex ("golden retriever") | low | 32 | **208** | 240 |
| Complex ("golden retriever") | medium | 32 | **805** | 837 |
| Complex ("golden retriever") | high | 32 | **3,171** | 3,203 |

**关键发现**：

1. **输出 Token 完全由 `quality` 决定**，与 Prompt 复杂度无关。简单和复杂 Prompt 在相同 quality 下产生完全相同的输出 Token。
2. **输入 Token 随 Prompt 长度变化** —— 5 词 Prompt 为 9 个 Token，20 词 Prompt 为 32 个 Token。
3. **Token 倍率**：low : medium : high = 1 : 3.87 : 15.24

### 生成图片 — 视觉对比

#### Prompt 1："A simple red circle on white background"

| Low (208 tokens) | Medium (805 tokens) | High (3,171 tokens) |
|:---:|:---:|:---:|
| ![low](images/red_dot/red_dot_low.png) | ![medium](images/red_dot/red_dot_medium.png) | ![high](images/red_dot/red_dot_high.png) |

#### Prompt 2："A photorealistic golden retriever puppy..."

| Low (208 tokens) | Medium (805 tokens) | High (3,171 tokens) |
|:---:|:---:|:---:|
| ![low](images/dog/dog_low.png) | ![medium](images/dog/dog_medium.png) | ![high](images/dog/dog_high.png) |

## 如何选择合适的 Quality

| 使用场景 | 推荐 Quality | 原因 |
|:---------|:------------|:-----|
| 缩略图 / 预览图 | **low** | Token 消耗最少，速度最快（~20s） |
| 营销 / 社交媒体 | **medium** | 细节与速度的良好平衡 |
| 印刷 / 专业用途 | **high** | 最高细节，但 Token 消耗 15 倍，延迟约 3 分钟 |
| 原型设计 / 迭代 | **low** | 快速反馈，最低 Token 消耗 |
| 大规模 A/B 测试 | **low** 或 **medium** | 批量生成的 Token 效率最优 |

## Known Limitations（已知限制）

1. **样本量**：2 个 Prompt × 3 个 Quality 级别。生产级 Benchmark 应测试 20+ 个不同 Prompt。
2. **单一分辨率**：仅测试 1024×1024。1024×1536 和 1536×1024 可能产生不同的 Token 数量。
3. **无重复测试**：每个组合仅测试一次。方差分析需要多次运行。
4. **Preview API**：使用 `2025-04-01-preview` —— GA 版本行为可能变化。
5. **单一区域**：仅 East US 2。延迟因区域而异。

## Reproducing the Benchmark（复现测试）

### 前置条件

- Azure 订阅，已开通 Azure OpenAI 访问权限
- GPT-Image-2 模型访问权限（限制访问 — [在此申请](https://aka.ms/oai/gptimage1access)）
- Python 3.8+，安装 `openai` 包

### 环境搭建

```bash
git clone https://github.com/david-share/Multimodal-Models.git
cd Multimodal-Models/GPT-Image-2-Token-Bucket-Benchmark
pip install openai azure-identity
```

### 部署模型

```bash
az cognitiveservices account deployment create \
  --name YOUR_RESOURCE_NAME \
  --resource-group YOUR_RG \
  --deployment-name gpt-image-2 \
  --model-name gpt-image-2 \
  --model-version "2026-04-21" \
  --model-format OpenAI \
  --sku-capacity 9 \
  --sku-name GlobalStandard
```

### 运行测试

```bash
export AZURE_OPENAI_ENDPOINT="https://YOUR_RESOURCE.openai.azure.com/"
export AZURE_OPENAI_KEY="YOUR_KEY"

python scripts/benchmark_gpt_image2.py \
  --endpoint $AZURE_OPENAI_ENDPOINT \
  --key $AZURE_OPENAI_KEY \
  --deployment gpt-image-2
```

### 脚本清单

| 脚本 | 用途 |
|:-----|:-----|
| `scripts/benchmark_gpt_image2.py` | 主测试脚本 — 测试各 quality 级别，保存图片 + Token 数据 |

## References（参考资料）

- [Introducing GPT-Image-2 in Microsoft Foundry](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-openais-gpt-image-2-in-microsoft-foundry/4514417) — TC Blog，描述 Token Bucket 机制
- [Azure OpenAI Image Generation](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e) — API 文档
- [Azure Foundry Models](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure) — 模型目录

---

*Author: Xinyu Wei — 实测于 Azure OpenAI, 2026 年 4 月 22 日*

[![Running on Azure](https://img.shields.io/badge/Running%20on-Microsoft%20Azure-blue?logo=microsoft-azure)](https://azure.microsoft.com)
