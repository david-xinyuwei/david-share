# MAI-Image-2 vs MAI-Image-2e vs GPT-Image-1.5：Azure AI 图像生成基准测试

对 Azure 图像生成模型的 **5 种配置**进行综合延迟基准测试：**MAI-Image-2**、**MAI-Image-2e**（Efficient 效率版）和 **GPT-Image-1.5** 三个质量档位（low / medium / high），使用相同的提示词和分辨率。

## 核心结果

| 模型 | Quality | 平均延迟 | 平均文件大小 | 通过率 |
|------|:-------:|:--------:|:----------:|:------:|
| GPT-Image-1.5 | low | **13.1s** | 1,772 KB | 22/22 |
| MAI-Image-2e | N/A（固定单档） | **17.4s** | 1,631 KB | 22/22 |
| MAI-Image-2 | N/A（固定单档） | **21.1s** | 1,575 KB | 22/22 |
| GPT-Image-1.5 | medium | 21.3s | 1,936 KB | 22/22 |
| GPT-Image-1.5 | high | 44.0s | 2,075 KB | 22/22 |

> - GPT-Image-1.5 (low) 速度最快（13.1s），比 MAI-Image-2e 快 33%。
> - MAI-Image-2 ≈ GPT-Image-1.5 (medium) 延迟相当（~21s）。
> - MAI 模型**没有 quality 参数** — 仅输出固定单一质量档位。

## 公平对比设计

### 对齐维度

| 维度 | 5 组统一设定 | 状态 |
|------|:----------:|:----:|
| 提示词 | 相同的 11 个 Surreal 风格提示词 | ✅ 对齐 |
| 分辨率 | 1024×1024 | ✅ 对齐 |
| 输出格式 | PNG (b64_json) | ✅ 对齐 |
| 网络环境 | 同一台机器（East US） | ✅ 对齐 |
| 测试日期 | 2026-04-19 | ✅ 对齐 |
| 预热 | 每组 1 次丢弃请求 | ✅ 对齐 |
| 调用间隔 | 每次 API 调用间等待 5s（对称） | ✅ 对齐 |
| **Quality** | MAI：不适用 / GPT：low、medium、high | 🔀 **差异项** |
| **模型** | MAI-Image-2 / MAI-Image-2e / GPT-Image-1.5 | 🔀 被测变量 |

### 为什么 Quality 是差异项而非对齐项

MAI-Image-2 和 MAI-Image-2e 的 API 仅接受 4 个参数：`model`、`prompt`、`width`、`height`。**不存在 `quality` 参数**（[来源](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python)）。GPT-Image-1.5 支持 `quality` 参数（low / medium / high），控制输出图像 token 数量（token 越多 = 细节越多 = 速度越慢）。为公平评估 MAI 固定质量对标 GPT 的哪个档位，我们测试了 GPT 的全部三档。

### 公平性控制措施

- **预热**：每组模型/质量配置各执行 1 次丢弃请求后再开始计时
- **顺序翻转**：Round 1 按 A→E 顺序执行，Round 2 按 E→A 反转
- **对称等待**：每次 API 调用间统一等待 5s
- **2 轮测试**：每个数据点取 2 次测量的平均值

## 逐提示词延迟对比

| # | 提示词 | MAI-2 | MAI-2e | GPT low | GPT med | GPT high |
|:-:|:-------|:-----:|:------:|:-------:|:-------:|:--------:|
| 1 | 金属和服少女 | 20.5s | 17.8s | 13.8s | 19.9s | 45.7s |
| 2 | 森林传送门 | 20.9s | 17.3s | 13.3s | 21.0s | 43.8s |
| 3 | 月球宇航员 | 19.7s | 17.3s | 12.6s | 20.3s | 40.4s |
| 4 | LOTR 小红龙 | 21.2s | 17.2s | 11.7s | 20.8s | 41.4s |
| 5 | 梦幻生物 | 20.8s | 16.5s | 12.3s | 21.6s | 44.4s |
| 6 | 丛林天坑 | 22.0s | 19.2s | 13.2s | 22.7s | 42.2s |
| 7 | 科技少女 | 20.7s | 17.4s | 12.8s | 21.4s | 46.1s |
| 8 | 迷幻宇宙 | 23.2s | 19.4s | 15.2s | 23.8s | 47.1s |
| 9 | 分形生物 | 23.1s | 17.0s | 13.2s | 20.4s | 44.6s |
| 10 | 愤怒猫鼓手 | 20.5s | 15.9s | 12.8s | 21.0s | 44.5s |
| 11 | 猴子音乐家 | 19.1s | 16.6s | 13.1s | 21.7s | 44.0s |
| **平均** | | **21.1s** | **17.4s** | **13.1s** | **21.3s** | **44.0s** |

> 每个单元格为 2 轮测量的平均值。Round 1 顺序 A→E，Round 2 顺序 E→A（翻转）。

## 并排图片对比

详见英文版 README.md 中的完整 11 组 × 5 模型并排图片。每组图片路径：

```
images/mai-image-2/{01-11}_test.png
images/mai-image-2e/{01-11}_test.png
images/gpt-image-1.5-low/{01-11}_test.png
images/gpt-image-1.5-medium/{01-11}_test.png
images/gpt-image-1.5-high/{01-11}_test.png
```

## API 对比

### 请求参数

| 特性 | MAI-Image-2 / MAI-Image-2e | GPT-Image-1.5 |
|------|:---------------------------:|:-------------:|
| API 路径 | `/mai/v1/images/generations` | `/openai/deployments/{name}/images/generations` |
| 认证方式 | Entra ID + API Key | API Key + Entra ID |
| 参数 | `model`、`prompt`、`width`、`height` | `prompt`、`n`、`size`、`quality` |
| 质量控制 | **不可用**（固定单档） | `low` / `medium` / `high` |
| 分辨率 | 灵活：W≥768, H≥768, W×H≤1,048,576 | 固定：1024×1024 / 1792×1024 / 1024×1792 |
| 输出格式 | 仅 PNG | PNG / URL |
| 输出数量 | 1（固定） | 1–10 |
| 最大提示词 | 32,000 tokens | 4,000 字符 |

> **来源**：MAI 参数来自 [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python)。GPT 参数来自 [Azure OpenAI 文档](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/dall-e)。

### 能力对比

| 能力 | MAI-Image-2 | MAI-Image-2e | GPT-Image-1.5 |
|------|:---:|:---:|:---:|
| 文字生图 | ✅ | ✅ | ✅ |
| 图片编辑 | ❌ | ❌ | ✅ |
| 图像修复（Inpainting） | ❌ | ❌ | ✅ |
| 灵活宽高比 | ✅ | ✅ | ❌（固定尺寸） |
| 质量档位 | ❌（固定单档） | ❌（固定单档） | ✅（low/med/high） |

### 定价

| 模型 | 文本输入 | 图像输出 | 来源 |
|------|:--------:|:--------:|:----:|
| MAI-Image-2 | USD 5 / 1M tokens | USD 33 / 1M tokens | [Tech Community 2026-04-02](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-transcribe-1-mai-voice-1-and-mai-image-2-in-microsoft-foundry/4507787) |
| MAI-Image-2e | USD 5 / 1M tokens | USD 19.50 / 1M tokens | [Tech Community 2026-04-14](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-image-2-efficient-faster-more-efficient-image-generation/4510918) |
| GPT-Image-1.5 | USD 5 / 1M tokens | USD 32 / 1M tokens | [Azure OpenAI 定价](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) |

> GPT-Image-1.5 按 token 计费 — `quality=low` 生成更少 token（单张更便宜），`quality=high` 生成更多 token（单张更贵）。MAI 模型为固定单档。

### Rate Limits

| 模型 | Tier 1 RPM | Tier 6 RPM |
|------|:----------:|:----------:|
| MAI-Image-2 | 9 | 90 |
| MAI-Image-2e | 18 | 180 |

> 来源：[Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python)

## 选型建议

| 使用场景 | 推荐 | 原因 |
|----------|:----:|------|
| 最快生成速度 | GPT-Image-1.5 (low) | 平均 13.1s |
| 速度 + 微软第一方 | MAI-Image-2e | 17.4s，不依赖 OpenAI |
| 最高画质细节 | GPT-Image-1.5 (high) | 输出 token 最多，但 44s |
| 图片编辑/修复 | GPT-Image-1.5 | MAI 无编辑 API |
| 灵活宽高比 | MAI-Image-2 / 2e | 像素预算内任意 W×H |
| 长提示词（>4K 字符） | MAI-Image-2 / 2e | 支持 32K token 提示词 |
| 大规模低成本 | MAI-Image-2e | USD 19.50/1M 输出 token |

## 如何复现

### 前提条件

- Azure 订阅 + Azure AI Services 资源
- 已部署：MAI-Image-2、MAI-Image-2e（AI Services）、gpt-image-1.5（Azure OpenAI）
- Python 3.x + `requests`
- Azure CLI (`az`) 已登录

### 运行

```bash
git clone https://github.com/david-share/Multimodal-Models.git
cd Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark

# 编辑 scripts/benchmark_5way.py — 设置你的端点和凭据
pip install requests
python scripts/benchmark_5way.py
```

## 仓库结构

```
.
├── README.md                            # 英文版
├── README-CN.md                         # 中文版（本文件）
├── prompts.csv                          # 11 个 Surreal 风格测试提示词
├── data/
│   └── 5way_benchmark_results.json      # 原始基准测试数据
├── scripts/
│   └── benchmark_5way.py                # 5 组基准测试脚本
└── images/
    ├── mai-image-2/                     # 11 张图片
    ├── mai-image-2e/                    # 11 张图片
    ├── gpt-image-1.5-low/              # 11 张图片
    ├── gpt-image-1.5-medium/           # 11 张图片
    └── gpt-image-1.5-high/             # 11 张图片
```
