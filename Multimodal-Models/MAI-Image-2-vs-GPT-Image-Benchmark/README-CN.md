# MAI-Image-2 vs MAI-Image-2e vs GPT-Image-1.5：Azure AI 图像生成基准测试

## 概要总结

本基准测试对比了 Azure 三款图像生成模型的 5 种配置（11 个提示词 × 2 轮 = 110 次 API 调用），采用公平性控制（预热、顺序翻转、对称等待）。截至 2026 年 4 月，所有模型均为 Preview 状态。

**模型概况：**

| | MAI-Image-2 | MAI-Image-2e | GPT-Image-1.5 |
|---|:---:|:---:|:---:|
| **供应商** | Microsoft AI（第一方） | Microsoft AI（第一方） | OpenAI via Azure |
| **API** | `/mai/v1/`（专用） | `/mai/v1/`（专用） | `/openai/deployments/`（标准） |
| **质量控制** | 固定单档 | 固定单档 | 3 档（low/med/high） |
| **平均延迟** | 20.1s | 17.2s | 13.3s (low) / 22.8s (med) / 46.3s (high) |
| **输出定价** | USD 33/1M tokens | **USD 19.50/1M tokens** | USD 32/1M tokens |
| **输出 tokens (1024²)** | 1,024（固定） | N/A（API 不返回） | 479 (low) / 1,473 (med) / 4,573 (high) |
| **单张成本 (1024²)** | USD 0.034 | ~USD 0.020* | USD 0.015 (low) / 0.047 (med) / 0.146 (high) |
| **图片编辑** | ❌ | ❌ | ✅ |
| **灵活分辨率** | ✅（768–1366px） | ✅（768–1366px） | ❌（3 种固定尺寸） |
| **最大提示词** | 32K tokens | 32K tokens | 4K tokens |
| **状态** | Preview | Preview | Preview |

**核心结论：** GPT-Image-1.5 `quality=low` 速度最快（13.3s）**且**单张最便宜（USD 0.015）。MAI-Image-2e 输出 token 单价最低（USD 19.50/1M），但每张生成的 token 比 GPT-low 多，实际单张成本更高（~USD 0.020）。MAI-Image-2 单张成本最高（USD 0.034），速度无优势。选型建议：速度+成本 → GPT-low，第一方独立 → MAI-2e，需要编辑 → GPT。

> *MAI-Image-2e 的 API 不返回 token 数。成本基于 MAI-Image-2 在 1024×1024 下固定 1,024 个 output tokens 估算。

> **来源：** MAI API — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai?tabs=python) | MAI-Image-2 定价 — [Tech Community 2026-04-02](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-transcribe-1-mai-voice-1-and-mai-image-2-in-microsoft-foundry/4507787) | MAI-Image-2e 定价 — [Tech Community 2026-04-14](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-mai-image-2-efficient-faster-more-efficient-image-generation/4510918) | GPT-Image-1.5 定价 — [Azure OpenAI 定价](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)

---

对 Azure 图像生成模型的 **5 种配置**进行综合延迟基准测试：**MAI-Image-2**、**MAI-Image-2e**（Efficient 效率版）和 **GPT-Image-1.5** 三个质量档位（low / medium / high），使用相同的提示词和分辨率。

## 核心结果

| 模型 | Quality | 平均延迟 | Output Tokens | 单张成本 | 通过率 |
|------|:-------:|:--------:|:-------------:|:--------:|:------:|
| GPT-Image-1.5 | low | **13.3s** | 479 | **USD 0.015** | 22/22 |
| MAI-Image-2e | N/A（固定单档） | **17.2s** | N/A | ~USD 0.020* | 22/22 |
| MAI-Image-2 | N/A（固定单档） | 20.1s | 1,024（固定） | USD 0.034 | 22/22 |
| GPT-Image-1.5 | medium | 22.8s | 1,473 | USD 0.047 | 22/22 |
| GPT-Image-1.5 | high | 46.3s | 4,573 | USD 0.146 | 22/22 |

> **通过率**（Pass Rate）= API 调用成功次数 / 总调用次数（每个模型 11 个提示词 × 2 轮 = 22 次调用）。
>
> *MAI-Image-2e 的 API 不返回 output token 数。成本按 MAI-Image-2 的固定 1,024 tokens 估算。
>
> - GPT-Image-1.5 (low) 速度最快（13.3s），**且单张成本最低**（USD 0.015）。
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
| 1 | 金属和服少女 | 19.9s | 16.9s | 12.8s | 21.4s | 45.0s |
| 2 | 森林传送门 | 21.7s | 17.0s | 13.8s | 22.3s | 44.2s |
| 3 | 月球宇航员 | 20.2s | 15.6s | 13.1s | 20.6s | 44.2s |
| 4 | LOTR 小红龙 | 20.3s | 17.5s | 12.8s | 22.3s | 44.1s |
| 5 | 梦幻生物 | 18.7s | 15.5s | 12.1s | 21.6s | 46.6s |
| 6 | 丛林天坑 | 20.8s | 18.5s | 14.2s | 24.5s | 45.6s |
| 7 | 科技少女 | 20.1s | 16.8s | 12.6s | 23.1s | 49.8s |
| 8 | 迷幻宇宙 | 21.5s | 20.2s | 14.0s | 23.4s | 48.3s |
| 9 | 分形生物 | 19.7s | 17.3s | 12.3s | 23.0s | 48.2s |
| 10 | 愤怒猫鼓手 | 18.4s | 16.9s | 15.2s | 22.5s | 47.3s |
| 11 | 猴子音乐家 | 20.0s | 17.2s | 13.8s | 25.8s | 46.3s |
| **平均** | | **20.1s** | **17.2s** | **13.3s** | **22.8s** | **46.3s** |

> 每个单元格为 2 轮测量的平均值。Round 1 顺序 A→E，Round 2 顺序 E→A（翻转）。

## 并排图片对比

### Test 1: 金属和服少女

> **Prompt**: Chrome kimono, a maiden surrounded by metallic flowers, earrings, ornate, dark blue, exquisite realism, high exposure, Canon 5D, cinematic lighting, metallic luster, blurred foreground, depth of field, light

**Round 1:**

| MAI-Image-2 (21.2s, 1821KB) | MAI-Image-2e (15.9s, 1494KB) | GPT-1.5 low (14.4s, 1724KB) | GPT-1.5 med (20.7s, 1899KB) | GPT-1.5 high (43.9s, 2137KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/01_test.png) | ![](images/mai-image-2e/r1/01_test.png) | ![](images/gpt-image-1.5-low/r1/01_test.png) | ![](images/gpt-image-1.5-medium/r1/01_test.png) | ![](images/gpt-image-1.5-high/r1/01_test.png) |

**Round 2:**

| MAI-Image-2 (18.6s, 1467KB) | MAI-Image-2e (17.9s, 1723KB) | GPT-1.5 low (11.1s, 1884KB) | GPT-1.5 med (22.0s, 1901KB) | GPT-1.5 high (46.0s, 2026KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/01_test.png) | ![](images/mai-image-2e/r2/01_test.png) | ![](images/gpt-image-1.5-low/r2/01_test.png) | ![](images/gpt-image-1.5-medium/r2/01_test.png) | ![](images/gpt-image-1.5-high/r2/01_test.png) |


### Test 2: 森林传送门

> **Prompt**: a portal into a mythical forest on the wall of my small messy bedroom

**Round 1:**

| MAI-Image-2 (21.9s, 1597KB) | MAI-Image-2e (16.7s, 1706KB) | GPT-1.5 low (14.5s, 1859KB) | GPT-1.5 med (22.5s, 2128KB) | GPT-1.5 high (42.3s, 2242KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/02_test.png) | ![](images/mai-image-2e/r1/02_test.png) | ![](images/gpt-image-1.5-low/r1/02_test.png) | ![](images/gpt-image-1.5-medium/r1/02_test.png) | ![](images/gpt-image-1.5-high/r1/02_test.png) |

**Round 2:**

| MAI-Image-2 (21.5s, 1577KB) | MAI-Image-2e (17.2s, 1484KB) | GPT-1.5 low (13.1s, 1968KB) | GPT-1.5 med (22.1s, 2127KB) | GPT-1.5 high (46.1s, 2280KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/02_test.png) | ![](images/mai-image-2e/r2/02_test.png) | ![](images/gpt-image-1.5-low/r2/02_test.png) | ![](images/gpt-image-1.5-medium/r2/02_test.png) | ![](images/gpt-image-1.5-high/r2/02_test.png) |


### Test 3: 月球宇航员

> **Prompt**: a tiny astronaut hatching from an egg on the moon

**Round 1:**

| MAI-Image-2 (19.8s, 1311KB) | MAI-Image-2e (14.6s, 1330KB) | GPT-1.5 low (13.7s, 1758KB) | GPT-1.5 med (19.9s, 1526KB) | GPT-1.5 high (44.4s, 1625KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/03_test.png) | ![](images/mai-image-2e/r1/03_test.png) | ![](images/gpt-image-1.5-low/r1/03_test.png) | ![](images/gpt-image-1.5-medium/r1/03_test.png) | ![](images/gpt-image-1.5-high/r1/03_test.png) |

**Round 2:**

| MAI-Image-2 (20.6s, 1532KB) | MAI-Image-2e (16.6s, 1279KB) | GPT-1.5 low (12.5s, 1567KB) | GPT-1.5 med (21.2s, 1662KB) | GPT-1.5 high (44.0s, 1771KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/03_test.png) | ![](images/mai-image-2e/r2/03_test.png) | ![](images/gpt-image-1.5-low/r2/03_test.png) | ![](images/gpt-image-1.5-medium/r2/03_test.png) | ![](images/gpt-image-1.5-high/r2/03_test.png) |


### Test 4: LOTR 小红龙

> **Prompt**: Photo realistic scene inspired by LOTR: [A tiny red dragon in a nest on a medieval wizard's table]. Shot with a macro lens (f/2.8, 50mm) and a Canon EOSR5, the soft focus captures [the cozy morning light filtering through a near by window]. The pastel colors and whimsical steam shapes enhance the serene atmosphere, evoking a DnD RPG setting. The image is rendered in 16K and 8K, highlighting [the intricate details and medieval charm].

**Round 1:**

| MAI-Image-2 (19.3s, 1424KB) | MAI-Image-2e (17.8s, 1506KB) | GPT-1.5 low (14.7s, 1521KB) | GPT-1.5 med (22.5s, 1645KB) | GPT-1.5 high (43.9s, 1593KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/04_test.png) | ![](images/mai-image-2e/r1/04_test.png) | ![](images/gpt-image-1.5-low/r1/04_test.png) | ![](images/gpt-image-1.5-medium/r1/04_test.png) | ![](images/gpt-image-1.5-high/r1/04_test.png) |

**Round 2:**

| MAI-Image-2 (21.2s, 1441KB) | MAI-Image-2e (17.1s, 1439KB) | GPT-1.5 low (10.8s, 1518KB) | GPT-1.5 med (22.1s, 1555KB) | GPT-1.5 high (44.2s, 1574KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/04_test.png) | ![](images/mai-image-2e/r2/04_test.png) | ![](images/gpt-image-1.5-low/r2/04_test.png) | ![](images/gpt-image-1.5-medium/r2/04_test.png) | ![](images/gpt-image-1.5-high/r2/04_test.png) |


### Test 5: 梦幻生物

> **Prompt**: Cute and adorable fluffy cute creature fantasy, dreamlike, surrealism, super cute, trending on artstation

**Round 1:**

| MAI-Image-2 (19.6s, 1048KB) | MAI-Image-2e (14.8s, 1202KB) | GPT-1.5 low (11.7s, 1438KB) | GPT-1.5 med (20.4s, 1691KB) | GPT-1.5 high (45.7s, 1526KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/05_test.png) | ![](images/mai-image-2e/r1/05_test.png) | ![](images/gpt-image-1.5-low/r1/05_test.png) | ![](images/gpt-image-1.5-medium/r1/05_test.png) | ![](images/gpt-image-1.5-high/r1/05_test.png) |

**Round 2:**

| MAI-Image-2 (17.8s, 965KB) | MAI-Image-2e (16.1s, 1107KB) | GPT-1.5 low (12.4s, 1518KB) | GPT-1.5 med (22.8s, 1593KB) | GPT-1.5 high (47.5s, 1669KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/05_test.png) | ![](images/mai-image-2e/r2/05_test.png) | ![](images/gpt-image-1.5-low/r2/05_test.png) | ![](images/gpt-image-1.5-medium/r2/05_test.png) | ![](images/gpt-image-1.5-high/r2/05_test.png) |


### Test 6: 丛林天坑

> **Prompt**: A hidden cenote in the heart of a lush jungle beckons with crystalline turquoise waters. Vibrant emerald vines cascade down weathered limestone walls, their tendrils barely kissing the water's surface. Shafts of golden sunlight pierce through a natural skylight above, creating a mystical interplay of light and shadow on the cavern walls. Iridescent butterflies flit between exotic orchids clinging to rocky outcrops. A partially submerged Mayan ruin, its intricate carvings softened by time, stand

**Round 1:**

| MAI-Image-2 (20.0s, 1953KB) | MAI-Image-2e (19.6s, 2255KB) | GPT-1.5 low (12.9s, 2173KB) | GPT-1.5 med (24.3s, 2529KB) | GPT-1.5 high (42.9s, 2502KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/06_test.png) | ![](images/mai-image-2e/r1/06_test.png) | ![](images/gpt-image-1.5-low/r1/06_test.png) | ![](images/gpt-image-1.5-medium/r1/06_test.png) | ![](images/gpt-image-1.5-high/r1/06_test.png) |

**Round 2:**

| MAI-Image-2 (21.6s, 2052KB) | MAI-Image-2e (17.3s, 2192KB) | GPT-1.5 low (15.4s, 2162KB) | GPT-1.5 med (24.7s, 2320KB) | GPT-1.5 high (48.3s, 2464KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/06_test.png) | ![](images/mai-image-2e/r2/06_test.png) | ![](images/gpt-image-1.5-low/r2/06_test.png) | ![](images/gpt-image-1.5-medium/r2/06_test.png) | ![](images/gpt-image-1.5-high/r2/06_test.png) |


### Test 7: 科技少女

> **Prompt**: A charming, tech-savvy [girl with short, silver pixie-cut] hair and vibrant [blue] eyes, wearing a casual yet futuristic outfit. She's focused on a holographic interface while working in a sleek, high-tech workshop.

**Round 1:**

| MAI-Image-2 (21.3s, 1283KB) | MAI-Image-2e (16.5s, 1485KB) | GPT-1.5 low (13.6s, 1636KB) | GPT-1.5 med (22.8s, 1790KB) | GPT-1.5 high (47.4s, 1870KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/07_test.png) | ![](images/mai-image-2e/r1/07_test.png) | ![](images/gpt-image-1.5-low/r1/07_test.png) | ![](images/gpt-image-1.5-medium/r1/07_test.png) | ![](images/gpt-image-1.5-high/r1/07_test.png) |

**Round 2:**

| MAI-Image-2 (18.9s, 1312KB) | MAI-Image-2e (17.0s, 1415KB) | GPT-1.5 low (11.5s, 1590KB) | GPT-1.5 med (23.4s, 1788KB) | GPT-1.5 high (52.2s, 1834KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/07_test.png) | ![](images/mai-image-2e/r2/07_test.png) | ![](images/gpt-image-1.5-low/r2/07_test.png) | ![](images/gpt-image-1.5-medium/r2/07_test.png) | ![](images/gpt-image-1.5-high/r2/07_test.png) |


### Test 8: 迷幻宇宙

> **Prompt**: Universe, LSD, Fractal Worlds, Giant Eyes

**Round 1:**

| MAI-Image-2 (21.4s, 2379KB) | MAI-Image-2e (20.4s, 2528KB) | GPT-1.5 low (13.1s, 2667KB) | GPT-1.5 med (23.9s, 2630KB) | GPT-1.5 high (46.3s, 2621KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/08_test.png) | ![](images/mai-image-2e/r1/08_test.png) | ![](images/gpt-image-1.5-low/r1/08_test.png) | ![](images/gpt-image-1.5-medium/r1/08_test.png) | ![](images/gpt-image-1.5-high/r1/08_test.png) |

**Round 2:**

| MAI-Image-2 (21.6s, 2305KB) | MAI-Image-2e (20.0s, 2509KB) | GPT-1.5 low (14.9s, 2598KB) | GPT-1.5 med (22.9s, 2649KB) | GPT-1.5 high (50.2s, 2634KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/08_test.png) | ![](images/mai-image-2e/r2/08_test.png) | ![](images/gpt-image-1.5-low/r2/08_test.png) | ![](images/gpt-image-1.5-medium/r2/08_test.png) | ![](images/gpt-image-1.5-high/r2/08_test.png) |


### Test 9: 分形生物

> **Prompt**: close up dof render of a mythical creature made of detailed spiraling fractals and tendrils, detailed recursive skin texture

**Round 1:**

| MAI-Image-2 (18.9s, 1463KB) | MAI-Image-2e (17.2s, 1510KB) | GPT-1.5 low (11.5s, 2029KB) | GPT-1.5 med (22.5s, 2108KB) | GPT-1.5 high (48.5s, 2193KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/09_test.png) | ![](images/mai-image-2e/r1/09_test.png) | ![](images/gpt-image-1.5-low/r1/09_test.png) | ![](images/gpt-image-1.5-medium/r1/09_test.png) | ![](images/gpt-image-1.5-high/r1/09_test.png) |

**Round 2:**

| MAI-Image-2 (20.4s, 1407KB) | MAI-Image-2e (17.3s, 1679KB) | GPT-1.5 low (13.1s, 1937KB) | GPT-1.5 med (23.5s, 2244KB) | GPT-1.5 high (47.8s, 2103KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/09_test.png) | ![](images/mai-image-2e/r2/09_test.png) | ![](images/gpt-image-1.5-low/r2/09_test.png) | ![](images/gpt-image-1.5-medium/r2/09_test.png) | ![](images/gpt-image-1.5-high/r2/09_test.png) |


### Test 10: 愤怒猫鼓手

> **Prompt**: an angry cat playing drums

**Round 1:**

| MAI-Image-2 (18.7s, 1551KB) | MAI-Image-2e (16.5s, 1370KB) | GPT-1.5 low (16.7s, 1810KB) | GPT-1.5 med (22.9s, 1825KB) | GPT-1.5 high (44.3s, 1780KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/10_test.png) | ![](images/mai-image-2e/r1/10_test.png) | ![](images/gpt-image-1.5-low/r1/10_test.png) | ![](images/gpt-image-1.5-medium/r1/10_test.png) | ![](images/gpt-image-1.5-high/r1/10_test.png) |

**Round 2:**

| MAI-Image-2 (18.1s, 1409KB) | MAI-Image-2e (17.2s, 1546KB) | GPT-1.5 low (13.7s, 1860KB) | GPT-1.5 med (22.0s, 1895KB) | GPT-1.5 high (50.2s, 1945KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/10_test.png) | ![](images/mai-image-2e/r2/10_test.png) | ![](images/gpt-image-1.5-low/r2/10_test.png) | ![](images/gpt-image-1.5-medium/r2/10_test.png) | ![](images/gpt-image-1.5-high/r2/10_test.png) |


### Test 11: 猴子音乐家

> **Prompt**: A monkey playing music

**Round 1:**

| MAI-Image-2 (20.1s, 1755KB) | MAI-Image-2e (17.3s, 1780KB) | GPT-1.5 low (14.0s, 1711KB) | GPT-1.5 med (25.8s, 1973KB) | GPT-1.5 high (48.7s, 2016KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r1/11_test.png) | ![](images/mai-image-2e/r1/11_test.png) | ![](images/gpt-image-1.5-low/r1/11_test.png) | ![](images/gpt-image-1.5-medium/r1/11_test.png) | ![](images/gpt-image-1.5-high/r1/11_test.png) |

**Round 2:**

| MAI-Image-2 (19.9s, 1679KB) | MAI-Image-2e (17.1s, 1880KB) | GPT-1.5 low (13.5s, 1671KB) | GPT-1.5 med (25.8s, 1940KB) | GPT-1.5 high (43.9s, 2019KB) |
|:---:|:---:|:---:|:---:|:---:|
| ![](images/mai-image-2/r2/11_test.png) | ![](images/mai-image-2e/r2/11_test.png) | ![](images/gpt-image-1.5-low/r2/11_test.png) | ![](images/gpt-image-1.5-medium/r2/11_test.png) | ![](images/gpt-image-1.5-high/r2/11_test.png) |


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
| 最大提示词 | 32,000 tokens | 4,000 tokens |

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
| 最快生成速度 | GPT-Image-1.5 (low) | 平均 13.3s，USD 0.015/张 |
| 速度 + 微软第一方 | MAI-Image-2e | 17.2s，不依赖 OpenAI |
| 最高画质细节 | GPT-Image-1.5 (high) | 输出 token 最多，但 46s |
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

# 编辑 scripts/benchmark_5way_v2.py — 设置你的端点和凭据
pip install requests
python scripts/benchmark_5way_v2.py
```

## 仓库结构

```
.
├── README.md                            # 英文版
├── README-CN.md                         # 中文版（本文件）
├── prompts.csv                          # 11 个 Surreal 风格测试提示词
├── data/
│   └── 5way_v2_results.json           # 原始测试数据（V2，含 token 用量）
├── scripts/
│   └── benchmark_5way_v2.py           # 5 组基准测试脚本（V2）
└── images/
    ├── mai-image-2/                     # 11 张图片
    ├── mai-image-2e/                    # 11 张图片
    ├── gpt-image-1.5-low/              # 11 张图片
    ├── gpt-image-1.5-medium/           # 每个模型含 r1/ 和 r2/ 子目录
    └── gpt-image-1.5-high/             # 每个模型含 r1/ 和 r2/ 子目录
```

## 已知局限性

- **样本量**：仅 11 个提示词（Surreal 风格）。不同提示词类型（如产品摄影、图表、文字渲染）结果可能不同。
- **单一分辨率**：全部测试在 1024×1024。其他分辨率下延迟和成本可能不同。
- **2 轮测试**：每个数据点仅 N=2，统计力有限。两轮间方差 <6%，趋势一致。
- **Preview 模型**：截至 2026 年 4 月所有模型均为 Preview 状态，性能和定价可能在 GA 时变化。
- **区域**：仅从 East US 测试，其他区域延迟可能不同。
