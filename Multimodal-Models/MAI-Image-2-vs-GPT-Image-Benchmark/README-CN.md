# MAI-Image-2.6 与 GPT-Image-2 / 2.5：全质量档位图像生成对比

[![Models](https://img.shields.io/badge/Models-MAI--Image--2.6%20vs%20GPT--Image--2%20%2F%202.5-0067b8)](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) [![Samples](https://img.shields.io/badge/Samples-87%2F88%20%2B%20132%2F132%20returned-2e7d32)](data/paired-all-quality-20260907/5way_v2_results.json) ![Resolution](https://img.shields.io/badge/Resolution-1024%C3%971024-455a64) ![MAI version](https://img.shields.io/badge/MAI%20version-2026--07--31-6a1b9a) [![Status](https://img.shields.io/badge/Status-Preview%20%C2%B7%20no%20SLA-b26500)](https://azure.microsoft.com/support/legal/preview-supplemental-terms/) [![Tests](https://img.shields.io/badge/Tests-61%20offline-00695c)](tests)

同一台客户端交替调用 MAI-Image-2.6 与 GPT-Image-2 的 low、medium、high 三档，11 个文生图场景各两轮，共 88 个正式样本，保留全部原图、逐次请求记录与失败样本。另有联网信息补充（`web_grounding`）与单图编辑两项能力实测。所有画面判断为非盲评的差异描述，不产出质量评分或偏好胜负。 2026-09-17 另用同一客户端、同一份提示词补测了 GPT-Image-2.5 Flare 与 Sunburst 各三档，共 132 个正式样本，并入同一套图片、耗时与 token 表。

> **作者**: 魏新宇 (Xinyu Wei) — 微软 AI GBB 高级系统工程师

[English](README.md) | [中文](README-CN.md)

[逐题图片](#并排图片对比) · [耗时与请求](#耗时与请求成功情况) · [联网补测](#联网信息补充测试) · [图像编辑](#test-12-换帽子图像编辑) · [复现](#reproduction-how-to) · [原始证据](data/paired-all-quality-20260907)

---

## MAI-Image-2.6 在本轮中体现的能力

以下四条都只依据本仓库的实测记录，`MAI-Image-2.6` 处于 Preview，无 SLA。

1. **11 个场景与 GPT-Image-2 三档并排可比。** 本轮 87/88 个正式样本返回图片，两轮结果和原图全部保留在下方，可以逐题自行比较画面。逐图观察为非盲评的差异描述，没有评出优劣胜负，因此本文不声称画质优于或等同 GPT-Image-2。

2. **每张 1024×1024 图的 output token：MAI-Image-2.6 固定 1,024，介于 GPT-Image-2 low（196）与 medium（1,756）之间，是 high（7,024）的 15%。** 数值全部取自接口返回的 usage，每组所有成功样本完全一致。token 不是金额，两家的费率不同，本仓库不计价；GPT 的档位也不对应 MAI 的任何质量设置。 GPT-Image-2.5 的 low / medium / high 为：GPT-Image-2.5 Flare 196 / 439 / 1,756；GPT-Image-2.5 Sunburst 196 / 439 / 1,756，来自 2026-09-17 的补测。

3. **在对称的 `size=auto` 协议下，四个配置都完成了局部编辑。** 第 12 题只要求把头饰换成博士帽；MAI 与 GPT 三档两轮都换上了帽子，并让人脸、龙袍、侍卫、标题印章和原图宽高比保持在位且可辨，清单均为 5/5。标题字形与输出分辨率仍有差异，逐图记录和第一次方图协议的更正见第 12 题。

4. **`web_grounding=true` 可以在生成时补充联网信息。** 开启后模型会从 Bing Search 检索当前信息作为额外上下文，实测让两个题目的产品文字事实从错误变为与官方发布一致；代价是首试成功率下降、耗时明显上升。这与视觉领域的 dense grounding（密集视觉定位）不是同一件事。

### 厂商公布的性能图表与本轮实测的关系

以下图表取自微软官网 MAI-Image-2.6 页面的 Performance 区（抓取于 2026-09-08）。它们是厂商声明，测量条件与本仓库不同，与我们的实测互不验证。

![文生图排行榜前十](assets/official-microsoft-ai-20260908/arena-text-to-image-top10.png)

厂商标注 MAI-Image-2.6 位列第 2（1,336），第 1 名是 GPT Image 2 Medium（1,381）。这是 Arena 全提示词类别的总分排名，不等于逐场景画质判定，本仓库也没有复现该分数。

本轮实测的同一统计量（成功请求耗时 P50，客户端记录）：MAI-Image-2.6 38.03 秒；GPT-Image-2 low 31.19 秒、medium 64.64 秒、high 171.26 秒。厂商图上 MAI 比 GPT-Image-2-Medium 快 1.31 倍，本轮为 1.70 倍：**方向一致，倍数不同**。

<details>

<summary>另外两张厂商图表（速度、质量与价格前沿）与完整口径说明</summary>

**文生图速度对比**

![文生图速度对比](assets/official-microsoft-ai-20260908/speed-vs-gpt-image-2-medium.png)

厂商脚注写明：内部压测，100 RPM，1024x1024，取中位数，误差带到 P90。对照基线只有 GPT-Image-2-Medium，没有 low 与 high 档。

**图像编辑的质量与价格前沿**

![图像编辑的质量与价格前沿](assets/official-microsoft-ai-20260908/quality-vs-price-frontier.png)

横轴为第三方公布的每千张 API 参考价，纵轴为图像编辑 Arena Elo。厂商标注 MAI-Image-2.6（Elo 1324、$38.90）与 MAI-Image-2.6-Flash（Elo 1311、$19.50）位于 Pareto 前沿；GPT Image 2 high 为 Elo 1318、$211。这是图像编辑任务，与上面的文生图排行榜不是同一件事。价格为第三方公开参考价，不是微软报价，也不代表任何客户的实际成交价。

两者不可互相验证：厂商在 100 RPM 压测下测量，本轮为每分钟 2 次请求、并发 1；本轮 MAI 部署在 Sweden Central、GPT 在 East US 2，客户端在同一台工作站，因此耗时差中包含区域与网络因素，无法从本轮数据里剥离。每组 22 个样本为描述性样本，不是容量或尾延迟结论。本仓库没有测过 `MAI-Image-2.6-Flash`，也没有复现 Arena 或 Artificial Analysis 的 Elo 分数。厂商图上没有的两条：本轮 GPT-Image-2 low 的 P50 为 31.19 秒，比 MAI 更快；MAI 比 GPT-Image-2 high 快 4.50 倍。

[图表来源与逐项读数](assets/official-microsoft-ai-20260908/provenance.json) | [厂商页面](https://microsoft.ai/models/mai-image-2-6/)

</details>

## 并排图片对比

第 1–11 题为文生图。每个场景每一轮有两行图：第一行是 2026-09-07 测的 MAI-Image-2.6 与 GPT-Image-2 low、medium、high；第二行是 2026-09-17 用同一客户端、同一提示词补测的 GPT-Image-2.5 Flare 与 Sunburst 各三档，部署在 swedencentral。两行不是同一时段，图下的耗时要连带日期看。未返回图片的格子保留失败说明。点击图片查看原始 1024x1024 PNG。第 12 题为图像编辑，输入为一张真实照片，没有 2.5 的结果。

### Test 1: 金属和服少女

> **Prompt**: Chrome kimono, a maiden surrounded by metallic flowers, earrings, ornate, dark blue, exquisite realism, high exposure, Canon 5D, cinematic lighting, metallic luster, blurred foreground, depth of field, light

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/01_test.png) | ![GPT-Image-2 low, prompt 1, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/01_test.png) | ![GPT-Image-2 medium, prompt 1, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/01_test.png) | 未返回图片 |
| 38.82 s<br>1856 KiB | 51.44 s<br>1636 KiB | 78.13 s<br>1504 KiB | 3 次尝试；任务耗时 322.06 s |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/01_test.png) | ![GPT-Image-2.5 Flare medium, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/01_test.png) | ![GPT-Image-2.5 Flare high, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/01_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/01_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/01_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/01_test.png) |
| 21.93 s<br>1631 KiB | 21.65 s<br>1652 KiB | 39.92 s<br>1661 KiB | 33.75 s<br>1665 KiB | 39.18 s<br>1738 KiB | 79.29 s<br>1668 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/01_test.png) | ![GPT-Image-2 low, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/01_test.png) | ![GPT-Image-2 medium, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/01_test.png) | ![GPT-Image-2 high, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/01_test.png) |
| 33.96 s<br>1699 KiB | 26.25 s<br>1641 KiB | 63.52 s<br>1704 KiB | 182.78 s<br>1531 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/01_test.png) | ![GPT-Image-2.5 Flare medium, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/01_test.png) | ![GPT-Image-2.5 Flare high, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/01_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/01_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/01_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/01_test.png) |
| 17.66 s<br>1546 KiB | 22.85 s<br>1614 KiB | 30.23 s<br>1780 KiB | 30.74 s<br>1566 KiB | 40.55 s<br>1704 KiB | 75.43 s<br>1608 KiB |

### Test 2: 森林传送门

> **Prompt**: a portal into a mythical forest on the wall of my small messy bedroom

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/02_test.png) | ![GPT-Image-2 low, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/02_test.png) | ![GPT-Image-2 medium, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/02_test.png) | ![GPT-Image-2 high, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/02_test.png) |
| 65.12 s<br>1676 KiB | 41.67 s<br>1438 KiB | 74.93 s<br>1477 KiB | 176.78 s<br>1727 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/02_test.png) | ![GPT-Image-2.5 Flare medium, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/02_test.png) | ![GPT-Image-2.5 Flare high, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/02_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/02_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/02_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/02_test.png) |
| 20.45 s<br>1429 KiB | 20.34 s<br>1457 KiB | 32.41 s<br>1577 KiB | 34.85 s<br>1445 KiB | 37.45 s<br>1401 KiB | 79.97 s<br>1518 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/02_test.png) | ![GPT-Image-2 low, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/02_test.png) | ![GPT-Image-2 medium, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/02_test.png) | ![GPT-Image-2 high, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/02_test.png) |
| 37.43 s<br>1721 KiB | 28.50 s<br>1491 KiB | 60.23 s<br>1489 KiB | 170.60 s<br>1619 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/02_test.png) | ![GPT-Image-2.5 Flare medium, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/02_test.png) | ![GPT-Image-2.5 Flare high, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/02_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/02_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/02_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/02_test.png) |
| 22.78 s<br>1401 KiB | 27.23 s<br>1499 KiB | 34.63 s<br>1525 KiB | 30.09 s<br>1506 KiB | 40.22 s<br>1569 KiB | 72.24 s<br>1380 KiB |

### Test 3: 月球宇航员

> **Prompt**: a tiny astronaut hatching from an egg on the moon

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/03_test.png) | ![GPT-Image-2 low, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/03_test.png) | ![GPT-Image-2 medium, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/03_test.png) | ![GPT-Image-2 high, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/03_test.png) |
| 32.29 s<br>1387 KiB | 82.39 s<br>1354 KiB | 68.42 s<br>1499 KiB | 170.29 s<br>1543 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/03_test.png) | ![GPT-Image-2.5 Flare medium, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/03_test.png) | ![GPT-Image-2.5 Flare high, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/03_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/03_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/03_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/03_test.png) |
| 48.27 s<br>1596 KiB | 21.54 s<br>1499 KiB | 32.30 s<br>1520 KiB | 28.35 s<br>1436 KiB | 36.46 s<br>1410 KiB | 70.93 s<br>1434 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/03_test.png) | ![GPT-Image-2 low, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/03_test.png) | ![GPT-Image-2 medium, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/03_test.png) | ![GPT-Image-2 high, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/03_test.png) |
| 32.19 s<br>1539 KiB | 23.61 s<br>1295 KiB | 59.58 s<br>1428 KiB | 152.75 s<br>1457 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/03_test.png) | ![GPT-Image-2.5 Flare medium, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/03_test.png) | ![GPT-Image-2.5 Flare high, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/03_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/03_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/03_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/03_test.png) |
| 20.04 s<br>1576 KiB | 22.78 s<br>1585 KiB | 33.99 s<br>1507 KiB | 33.48 s<br>1403 KiB | 36.23 s<br>1481 KiB | 74.38 s<br>1428 KiB |

### Test 4: LOTR 小红龙

> **Prompt**: Photo realistic scene inspired by LOTR: [A tiny red dragon in a nest on a medieval wizard's table]. Shot with a macro lens (f/2.8, 50mm) and a Canon EOSR5, the soft focus captures [the cozy morning light filtering through a near by window]. The pastel colors and whimsical steam shapes enhance the serene atmosphere, evoking a DnD RPG setting. The image is rendered in 16K and 8K, highlighting [the intricate details and medieval charm].

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/04_test.png) | ![GPT-Image-2 low, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/04_test.png) | ![GPT-Image-2 medium, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/04_test.png) | ![GPT-Image-2 high, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/04_test.png) |
| 38.63 s<br>1589 KiB | 47.05 s<br>1382 KiB | 65.18 s<br>1457 KiB | 192.56 s<br>1443 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/04_test.png) | ![GPT-Image-2.5 Flare medium, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/04_test.png) | ![GPT-Image-2.5 Flare high, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/04_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/04_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/04_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/04_test.png) |
| 22.31 s<br>1536 KiB | 18.22 s<br>1440 KiB | 31.36 s<br>1383 KiB | 26.78 s<br>1523 KiB | 43.88 s<br>1622 KiB | 81.83 s<br>1630 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/04_test.png) | ![GPT-Image-2 low, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/04_test.png) | ![GPT-Image-2 medium, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/04_test.png) | ![GPT-Image-2 high, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/04_test.png) |
| 34.69 s<br>1585 KiB | 23.98 s<br>1366 KiB | 59.51 s<br>1485 KiB | 171.26 s<br>1402 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/04_test.png) | ![GPT-Image-2.5 Flare medium, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/04_test.png) | ![GPT-Image-2.5 Flare high, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/04_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/04_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/04_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/04_test.png) |
| 18.24 s<br>1381 KiB | 26.90 s<br>1432 KiB | 27.99 s<br>1404 KiB | 36.29 s<br>1557 KiB | 38.24 s<br>1647 KiB | 71.88 s<br>1613 KiB |

### Test 5: 梦幻生物

> **Prompt**: Cute and adorable fluffy cute creature fantasy, dreamlike, surrealism, super cute, trending on artstation

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/05_test.png) | ![GPT-Image-2 low, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/05_test.png) | ![GPT-Image-2 medium, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/05_test.png) | ![GPT-Image-2 high, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/05_test.png) |
| 60.09 s<br>1435 KiB | 29.09 s<br>1673 KiB | 69.86 s<br>1450 KiB | 187.57 s<br>1526 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/05_test.png) | ![GPT-Image-2.5 Flare medium, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/05_test.png) | ![GPT-Image-2.5 Flare high, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/05_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/05_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/05_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/05_test.png) |
| 22.87 s<br>1484 KiB | 24.71 s<br>1635 KiB | 35.22 s<br>1601 KiB | 35.94 s<br>1676 KiB | 40.73 s<br>1685 KiB | 82.79 s<br>1768 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/05_test.png) | ![GPT-Image-2 low, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/05_test.png) | ![GPT-Image-2 medium, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/05_test.png) | ![GPT-Image-2 high, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/05_test.png) |
| 38.42 s<br>1417 KiB | 24.80 s<br>1622 KiB | 63.22 s<br>1437 KiB | 163.33 s<br>1586 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/05_test.png) | ![GPT-Image-2.5 Flare medium, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/05_test.png) | ![GPT-Image-2.5 Flare high, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/05_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/05_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/05_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/05_test.png) |
| 26.37 s<br>1693 KiB | 25.03 s<br>1708 KiB | 30.08 s<br>1650 KiB | 33.82 s<br>1671 KiB | 48.76 s<br>1730 KiB | 78.02 s<br>1723 KiB |

### Test 6: 丛林天坑

> **Prompt**: A hidden cenote in the heart of a lush jungle beckons with crystalline turquoise waters. Vibrant emerald vines cascade down weathered limestone walls, their tendrils barely kissing the water's surface. Shafts of golden sunlight pierce through a natural skylight above, creating a mystical interplay of light and shadow on the cavern walls. Iridescent butterflies flit between exotic orchids clinging to rocky outcrops. A partially submerged Mayan ruin, its intricate carvings softened by time, stand

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/06_test.png) | ![GPT-Image-2 low, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/06_test.png) | ![GPT-Image-2 medium, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/06_test.png) | ![GPT-Image-2 high, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/06_test.png) |
| 80.54 s<br>2149 KiB | 62.70 s<br>2088 KiB | 71.35 s<br>2110 KiB | 190.79 s<br>2024 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/06_test.png) | ![GPT-Image-2.5 Flare medium, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/06_test.png) | ![GPT-Image-2.5 Flare high, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/06_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/06_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/06_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/06_test.png) |
| 20.62 s<br>2095 KiB | 23.65 s<br>2199 KiB | 29.70 s<br>2186 KiB | 31.22 s<br>2178 KiB | 41.48 s<br>2142 KiB | 72.25 s<br>2116 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/06_test.png) | ![GPT-Image-2 low, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/06_test.png) | ![GPT-Image-2 medium, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/06_test.png) | ![GPT-Image-2 high, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/06_test.png) |
| 32.25 s<br>2131 KiB | 35.88 s<br>2042 KiB | 65.19 s<br>2151 KiB | 185.09 s<br>1979 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/06_test.png) | ![GPT-Image-2.5 Flare medium, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/06_test.png) | ![GPT-Image-2.5 Flare high, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/06_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/06_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/06_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/06_test.png) |
| 24.02 s<br>2151 KiB | 24.58 s<br>2188 KiB | 30.02 s<br>2193 KiB | 29.72 s<br>2084 KiB | 39.82 s<br>2205 KiB | 72.77 s<br>2163 KiB |

### Test 7: 科技少女

> **Prompt**: A charming, tech-savvy [girl with short, silver pixie-cut] hair and vibrant [blue] eyes, wearing a casual yet futuristic outfit. She's focused on a holographic interface while working in a sleek, high-tech workshop.

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/07_test.png) | ![GPT-Image-2 low, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/07_test.png) | ![GPT-Image-2 medium, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/07_test.png) | ![GPT-Image-2 high, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/07_test.png) |
| 54.92 s<br>1556 KiB | 33.29 s<br>1543 KiB | 67.74 s<br>1520 KiB | 177.19 s<br>1538 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/07_test.png) | ![GPT-Image-2.5 Flare medium, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/07_test.png) | ![GPT-Image-2.5 Flare high, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/07_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/07_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/07_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/07_test.png) |
| 24.69 s<br>1587 KiB | 30.05 s<br>1572 KiB | 39.26 s<br>1578 KiB | 47.64 s<br>1567 KiB | 44.40 s<br>1529 KiB | 83.86 s<br>1448 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/07_test.png) | ![GPT-Image-2 low, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/07_test.png) | ![GPT-Image-2 medium, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/07_test.png) | ![GPT-Image-2 high, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/07_test.png) |
| 37.63 s<br>1495 KiB | 35.08 s<br>1548 KiB | 66.85 s<br>1529 KiB | 170.62 s<br>1648 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/07_test.png) | ![GPT-Image-2.5 Flare medium, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/07_test.png) | ![GPT-Image-2.5 Flare high, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/07_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/07_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/07_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/07_test.png) |
| 23.76 s<br>1542 KiB | 26.14 s<br>1555 KiB | 36.52 s<br>1544 KiB | 42.77 s<br>1660 KiB | 47.67 s<br>1509 KiB | 89.34 s<br>1530 KiB |

### Test 8: 迷幻宇宙

> **Prompt**: Universe, LSD, Fractal Worlds, Giant Eyes

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/08_test.png) | ![GPT-Image-2 low, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/08_test.png) | ![GPT-Image-2 medium, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/08_test.png) | ![GPT-Image-2 high, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/08_test.png) |
| 36.49 s<br>2305 KiB | 35.03 s<br>2175 KiB | 68.73 s<br>2270 KiB | 174.50 s<br>2250 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/08_test.png) | ![GPT-Image-2.5 Flare medium, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/08_test.png) | ![GPT-Image-2.5 Flare high, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/08_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/08_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/08_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/08_test.png) |
| 21.65 s<br>2262 KiB | 23.34 s<br>2217 KiB | 30.04 s<br>2280 KiB | 37.12 s<br>2159 KiB | 43.32 s<br>2346 KiB | 78.61 s<br>2363 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/08_test.png) | ![GPT-Image-2 low, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/08_test.png) | ![GPT-Image-2 medium, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/08_test.png) | ![GPT-Image-2 high, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/08_test.png) |
| 106.81 s<br>2356 KiB | 99.08 s<br>2441 KiB | 72.83 s<br>2337 KiB | 215.09 s<br>2270 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/08_test.png) | ![GPT-Image-2.5 Flare medium, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/08_test.png) | ![GPT-Image-2.5 Flare high, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/08_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/08_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/08_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/08_test.png) |
| 25.37 s<br>2217 KiB | 26.48 s<br>2253 KiB | 32.88 s<br>2246 KiB | 32.81 s<br>2265 KiB | 45.98 s<br>2401 KiB | 75.23 s<br>2334 KiB |

### Test 9: 分形生物

> **Prompt**: close up dof render of a mythical creature made of detailed spiraling fractals and tendrils, detailed recursive skin texture

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/09_test.png) | ![GPT-Image-2 low, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/09_test.png) | ![GPT-Image-2 medium, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/09_test.png) | ![GPT-Image-2 high, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/09_test.png) |
| 49.96 s<br>1767 KiB | 37.29 s<br>1871 KiB | 61.67 s<br>1731 KiB | 169.84 s<br>1686 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/09_test.png) | ![GPT-Image-2.5 Flare medium, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/09_test.png) | ![GPT-Image-2.5 Flare high, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/09_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/09_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/09_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/09_test.png) |
| 21.77 s<br>1581 KiB | 23.08 s<br>1833 KiB | 29.63 s<br>1805 KiB | 26.27 s<br>1637 KiB | 51.02 s<br>1797 KiB | 76.49 s<br>1646 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/09_test.png) | ![GPT-Image-2 low, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/09_test.png) | ![GPT-Image-2 medium, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/09_test.png) | ![GPT-Image-2 high, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/09_test.png) |
| 41.92 s<br>1737 KiB | 25.10 s<br>1840 KiB | 60.62 s<br>1747 KiB | 241.38 s<br>1666 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/09_test.png) | ![GPT-Image-2.5 Flare medium, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/09_test.png) | ![GPT-Image-2.5 Flare high, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/09_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/09_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/09_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/09_test.png) |
| 16.93 s<br>1761 KiB | 23.64 s<br>1689 KiB | 29.72 s<br>1622 KiB | 31.72 s<br>1763 KiB | 34.80 s<br>1551 KiB | 73.62 s<br>1526 KiB |

### Test 10: 愤怒猫鼓手

> **Prompt**: an angry cat playing drums

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/10_test.png) | ![GPT-Image-2 low, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/10_test.png) | ![GPT-Image-2 medium, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/10_test.png) | ![GPT-Image-2 high, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/10_test.png) |
| 32.92 s<br>1606 KiB | 28.74 s<br>1460 KiB | 57.93 s<br>1603 KiB | 139.24 s<br>1511 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/10_test.png) | ![GPT-Image-2.5 Flare medium, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/10_test.png) | ![GPT-Image-2.5 Flare high, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/10_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/10_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/10_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/10_test.png) |
| 19.46 s<br>1587 KiB | 22.89 s<br>1490 KiB | 44.71 s<br>1399 KiB | 32.57 s<br>1519 KiB | 38.38 s<br>1511 KiB | 75.67 s<br>1486 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/10_test.png) | ![GPT-Image-2 low, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/10_test.png) | ![GPT-Image-2 medium, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/10_test.png) | ![GPT-Image-2 high, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/10_test.png) |
| 42.97 s<br>1652 KiB | 25.43 s<br>1611 KiB | 64.09 s<br>1581 KiB | 153.85 s<br>1592 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/10_test.png) | ![GPT-Image-2.5 Flare medium, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/10_test.png) | ![GPT-Image-2.5 Flare high, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/10_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/10_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/10_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/10_test.png) |
| 24.01 s<br>1482 KiB | 28.90 s<br>1394 KiB | 39.20 s<br>1401 KiB | 31.10 s<br>1432 KiB | 42.36 s<br>1501 KiB | 70.54 s<br>1434 KiB |

### Test 11: 猴子音乐家

> **Prompt**: A monkey playing music

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/11_test.png) | ![GPT-Image-2 low, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/11_test.png) | ![GPT-Image-2 medium, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/11_test.png) | ![GPT-Image-2 high, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/11_test.png) |
| 33.49 s<br>1833 KiB | 27.58 s<br>1671 KiB | 56.04 s<br>1612 KiB | 140.32 s<br>1632 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/11_test.png) | ![GPT-Image-2.5 Flare medium, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r1/11_test.png) | ![GPT-Image-2.5 Flare high, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r1/11_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r1/11_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r1/11_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r1/11_test.png) |
| 20.30 s<br>1682 KiB | 21.21 s<br>1654 KiB | 34.86 s<br>1531 KiB | 32.52 s<br>1670 KiB | 45.18 s<br>1715 KiB | 80.64 s<br>1563 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/11_test.png) | ![GPT-Image-2 low, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/11_test.png) | ![GPT-Image-2 medium, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/11_test.png) | ![GPT-Image-2 high, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/11_test.png) |
| 35.77 s<br>1725 KiB | 27.29 s<br>1615 KiB | 56.27 s<br>1541 KiB | 152.77 s<br>1715 KiB |

| GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/11_test.png) | ![GPT-Image-2.5 Flare medium, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-medium/r2/11_test.png) | ![GPT-Image-2.5 Flare high, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-high/r2/11_test.png) | ![GPT-Image-2.5 Sunburst low, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-low/r2/11_test.png) | ![GPT-Image-2.5 Sunburst medium, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-medium/r2/11_test.png) | ![GPT-Image-2.5 Sunburst high, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-sunburst-high/r2/11_test.png) |
| 17.81 s<br>1624 KiB | 23.97 s<br>1538 KiB | 38.62 s<br>1549 KiB | 30.58 s<br>1545 KiB | 38.63 s<br>1728 KiB | 81.37 s<br>1609 KiB |

### Test 12: 换帽子（图像编辑）

前 11 题都是纯文生图。第 12 题改为图像编辑：把同一张真实照片交给四个配置的编辑接口，只要求改一处，并明确列出必须保持不变的内容。因此每张输出都能按清单逐项核对，不需要审美打分。与前 11 题相同，本题跑 2 轮，第二轮配置顺序反转。

输入为一张 553x311 的 JPEG 照片（39,539 字节，SHA-256 `2f15a826dbc5d0e9…`）：前景人物头戴冕冠，身着刺绣龙袍，左侧持戈侍卫，右侧紫衣人物与门廊建筑，左上角有剧名标题与印章。

发给四个配置的提示词完全相同：

> Replace only the headwear worn by the man in the foreground with a black academic graduation cap with a tassel. Keep his face, beard, expression and pose exactly as they are. Keep his embroidered robe, the courtyard and every other person unchanged.

**受控变量**

MAI 走 `/mai/v1/images/edits`，GPT 走 `/openai/deployments/gpt-image-2/images/edits`。GPT 三档只改 `quality`，`size` 传 `auto`，即由服务自选输出尺寸；MAI 的编辑接口没有尺寸参数，输出尺寸同样由服务决定。两边因此处于同一合同：都没有被要求输出某个固定尺寸。每轮每个配置各调用一次，共 2 轮。

**协议更正**

第一次运行给 GPT 三档传了 `size=1024x1024`，把 16:9 的输入压成方图。MAI 的编辑接口没有尺寸参数，从未受此约束，所以那是只作用于一方的单边约束，两边的基线并不可比。那批输出反映的是本测试填错的参数，不是模型行为，六轮保持项只有 0/5、1/5、0/5、0/5、0/5、0/5，已整体作废，也不放入模型对比。本轮把 GPT 改为 `size=auto`，与 MAI 同为服务自选尺寸，协议才对称。原运行仍保留在归档中，作为该次参数错误的记录。

![第 12 题 size=auto 结果汇总](data/edit-hat-swap-20260909-auto/figures/scenario12-auto-results.png)

下图汇总本题在 `size=auto` 下的结果：输入原图、提示词、尺寸参数说明，以及四个配置各自的输出、实际分辨率与 5 项保持内容的命中数。被作废的方图输出不在图中——它们是本测试参数设置的产物，不是模型行为，放进模型对比会把我们的错误归因给模型；原始运行仍保留在归档中。

| 输入图 |
| --- |
| ![Input photograph](data/edit-hat-swap-20260909-auto/input.jpg) |

**第1轮:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, edit round 1](data/edit-hat-swap-20260909-auto/01_mai-image-2.6.png) | ![GPT-Image-2 low, edit round 1](data/edit-hat-swap-20260909-auto/02_gpt-image-2-low.png) | ![GPT-Image-2 medium, edit round 1](data/edit-hat-swap-20260909-auto/03_gpt-image-2-medium.png) | ![GPT-Image-2 high, edit round 1](data/edit-hat-swap-20260909-auto/04_gpt-image-2-high.png) |
| 34.94 s<br>1585 KiB<br>1360x768 | 32.89 s<br>2411 KiB<br>1672x941 | 44.77 s<br>2373 KiB<br>1672x941 | 109.48 s<br>2167 KiB<br>1672x941 |

| 核对项 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 保持项命中 | 5/5 | 5/5 | 5/5 | 5/5 |
| 换成博士帽 | 是 | 是 | 是 | 是 |
| 人脸与胡须保留 | 是 | 是 | 是 | 是 |
| 龙袍纹样保留 | 是 | 是 | 是 | 是 |
| 侍卫与背景不变 | 是 | 是 | 是 | 是 |
| 标题与印章保留 | 是 | 是 | 是 | 是 |
| 保持原图宽高比 | 是 | 是 | 是 | 是 |

| 配置 | 画面观察 |
| --- | --- |
| MAI-Image-2.6 | 冕冠换成带流苏的黑色博士帽。人脸、胡须、神情、龙袍纹样、左侧持戈侍卫、右侧紫衣人物、门廊建筑全部在原位，输出保持 16:9（1360×768）。左上角标题与印章在原位，英文 THE ADVISORS ALLIANCE 可读但笔画发软，中文四字变形。记录与 PNG 自 2026-09-08 第一轮原样带入。 |
| GPT-Image-2 low | 博士帽换上。人脸、胡须、龙袍纹样、左侧侍卫队列、右侧紫衣人物与门廊建筑全部在原位，输出 1672×941，宽高比与输入一致。标题 THE ADVISORS ALLIANCE 逐字可读，中文四字接近原图，印章在位。 |
| GPT-Image-2 medium | 博士帽换上。人物、龙袍、侍卫、右侧人物与建筑全部在原位，输出 1672×941。标题英文逐字复现，中文接近原图，印章在位。 |
| GPT-Image-2 high | 博士帽换上。人物、龙袍、侍卫、右侧人物与建筑全部在原位，输出 1672×941。标题英文逐字复现，中文接近原图，印章在位。龙袍金线细节比输入更锐，属于放大重绘的结果。 |

**第2轮:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, edit round 2](data/edit-hat-swap-20260909-auto/r2/04_mai-image-2.6.png) | ![GPT-Image-2 low, edit round 2](data/edit-hat-swap-20260909-auto/r2/03_gpt-image-2-low.png) | ![GPT-Image-2 medium, edit round 2](data/edit-hat-swap-20260909-auto/r2/02_gpt-image-2-medium.png) | ![GPT-Image-2 high, edit round 2](data/edit-hat-swap-20260909-auto/r2/01_gpt-image-2-high.png) |
| 36.91 s<br>1618 KiB<br>1360x768 | 27.91 s<br>2406 KiB<br>1672x940 | 46.36 s<br>2388 KiB<br>1672x940 | 110.84 s<br>2119 KiB<br>1672x941 |

| 核对项 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 保持项命中 | 5/5 | 5/5 | 5/5 | 5/5 |
| 换成博士帽 | 是 | 是 | 是 | 是 |
| 人脸与胡须保留 | 是 | 是 | 是 | 是 |
| 龙袍纹样保留 | 是 | 是 | 是 | 是 |
| 侍卫与背景不变 | 是 | 是 | 是 | 是 |
| 标题与印章保留 | 是 | 是 | 是 | 是 |
| 保持原图宽高比 | 是 | 是 | 是 | 是 |

| 配置 | 画面观察 |
| --- | --- |
| MAI-Image-2.6 | 冕冠换成带流苏的黑色博士帽。人脸、胡须、龙袍纹样、侍卫、右侧人物、门廊建筑全部在原位，输出保持 16:9（1360×768）。标题与印章在原位，英文 ALLIANCE 一词笔画明显发软、近乎粘连，中文四字变形。记录与 PNG 自 2026-09-08 第二轮原样带入。 |
| GPT-Image-2 low | 博士帽换上。人物、龙袍、侍卫、右侧人物与建筑全部在原位，输出 1672×940，鬓角略显灰白。标题把 ADVISORS 写成 ASVISORS，中文略有变形，印章在位。 |
| GPT-Image-2 medium | 博士帽换上。人物、龙袍、侍卫、右侧人物与建筑全部在原位，输出 1672×940。标题多了一个撇号，写成 THE ADVISOR'S ALLIANCE；中文接近原图，印章在位。 |
| GPT-Image-2 high | 博士帽换上。人物、龙袍、侍卫、右侧人物与建筑全部在原位，输出 1672×941。标题英文逐字复现，中文接近原图，印章在位。与第一轮 high 结果一致。 |

| 跨轮汇总 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 保持项命中（每轮） | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 |
| 请求耗时（每轮） | 34.94 s / 36.91 s | 32.89 s / 27.91 s | 44.77 s / 46.36 s | 109.48 s / 110.84 s |
| 换成博士帽 | 2/2 | 2/2 | 2/2 | 2/2 |

四个配置在两轮里都换上了博士帽，并且都保住了全部 5 个保持项：人脸、龙袍、侍卫与背景、标题印章、原图宽高比，8 张输出全是 5/5。区别只剩三处。输出分辨率：GPT 三档自选 1672×941（约 157 万像素），MAI 为 1360×768（104 万像素，接口上限 1,048,576）。标题字形：GPT medium 与 high 两轮都把英文标题逐字复现；GPT low 第二轮把 ADVISORS 写成 ASVISORS，GPT medium 第二轮多了一个撇号；MAI 两轮英文可读但笔画发软，中文"军师联盟"四字明显变形。耗时：MAI 约 35 s，GPT low 28–33 s、medium 45–46 s、high 109–111 s。本题提示词要求保持原图，8 张输出在 5 项清单上无差别；标题字形保真度不在清单内，只作观察。

共 2 轮，每轮每个配置一次调用，两轮只说明结果是否重复出现，不构成统计样本；观察为非盲评，只描述与原图的差异，不是画质评分。耗时为客户端 `requests.post` 往返时间，GPT 部署在 East US 2、MAI 在 Sweden Central，客户端为同一台工作站，区域差异未剥离。输出 PNG 均无 alpha 通道。

[请求记录 第1轮](data/edit-hat-swap-20260909-auto/edit-results.json) | [逐图核对 第1轮](data/edit-hat-swap-20260909-auto/edit-review.json) | [请求记录 第2轮](data/edit-hat-swap-20260909-auto/r2/edit-results.json) | [逐图核对 第2轮](data/edit-hat-swap-20260909-auto/r2/edit-review.json) | [标题区域对照图](data/edit-hat-swap-20260909-auto/title-corner-contact-sheet.png) | [公开复现脚本](scripts/run_edit_hat_swap.py)

## 本轮：两模型与全部质量档位

[English](README.md) | [逐题图片](#并排图片对比) | [测量记录](data/paired-all-quality-20260907/5way_v2_results.json) | [指标](data/paired-all-quality-20260907/summary.json) | [请求记录](data/paired-all-quality-20260907/attempts.jsonl)

**本轮 87/88 个正式样本返回图片，1 个未返回图片；另有 4 次预热，不计入正式分母。 GPT-Image-2.5 补测 132/132 个正式样本返回图片，0 个未返回；预热 7 次，同样不计入分母。** 同一客户端交替调用，提示词、尺寸和轮数相同；部署区域不同，不能把端到端耗时差全部归因于模型。质量是非盲评的具体画面观察，不是官方 benchmark 分数、人类偏好胜率或生产可靠性证明。 GPT-Image-2.5 Flare 与 Sunburst 六列来自 2026-09-17 的独立运行：同一客户端、同一份提示词与同一个执行脚本，部署在 swedencentral（与 MAI 同区域）。它与前四列不是同一时段，跨列看耗时要连带日期和区域一起看；token 数由服务端计算，不受这两点影响。

### 测试口径

| 配置 | 模型版本 | 质量参数 | 尺寸 | 区域 | 正式样本 | 测量日期 |
| --- | --- | --- | --- | --- | --- | --- |
| MAI-Image-2.6 | 2026-07-31 | 未传入 | 1024x1024 | swedencentral | 22 | 2026-09-07 |
| GPT-Image-2 low | 2026-04-21 | low | 1024x1024 | eastus2 | 22 | 2026-09-07 |
| GPT-Image-2 medium | 2026-04-21 | medium | 1024x1024 | eastus2 | 22 | 2026-09-07 |
| GPT-Image-2 high | 2026-04-21 | high | 1024x1024 | eastus2 | 22 | 2026-09-07 |
| GPT-Image-2.5 Flare low | 2026-09-08 | low | 1024x1024 | swedencentral | 22 | 2026-09-17 |
| GPT-Image-2.5 Flare medium | 2026-09-08 | medium | 1024x1024 | swedencentral | 22 | 2026-09-17 |
| GPT-Image-2.5 Flare high | 2026-09-08 | high | 1024x1024 | swedencentral | 22 | 2026-09-17 |
| GPT-Image-2.5 Sunburst low | 2026-09-08 | low | 1024x1024 | swedencentral | 22 | 2026-09-17 |
| GPT-Image-2.5 Sunburst medium | 2026-09-08 | medium | 1024x1024 | swedencentral | 22 | 2026-09-17 |
| GPT-Image-2.5 Sunburst high | 2026-09-08 | high | 1024x1024 | swedencentral | 22 | 2026-09-17 |

输入是原报告同一份 11 题 CSV。每组先用 `blue circle` 预热一次；第一轮每题依次调用 MAI、GPT low、medium、high，第二轮反转。并发为 1，每次逻辑调用后间隔 5 秒，最多尝试 3 次，沿用原重试退避。两个 GlobalStandard 部署各配置每分钟 2 次请求；GPT 三档共享同一部署和限额。MAI 请求超时 180 秒，GPT 为 300 秒。 GPT-Image-2.5 补测另起一轮：Flare 与 Sunburst 各自一个 GlobalStandard 部署，每题依次 Flare low、medium、high、Sunburst low、medium、high，第二轮反转；并发、间隔、重试与超时与上述相同。因为 2.5 的 low/medium 约 15–20 秒就能返回，三档连续调用会在 60 秒内对同一部署发起第三次请求而触发自己的配额，所以这轮在计时区之外加了客户端限速：同一部署任意 60 秒内最多起请 2 次，等待时长逐样本记在 `pacing_wait_seconds`，不进入请求耗时。

客户端: Windows-11-10.0.26200-SP0, ARM64, Python 3.13.15, requests 2.34.2.

正式起止时间 (UTC): `2026-09-07T12:32:56.332837+00:00` to `2026-09-07T16:24:46.795573+00:00`. 正式窗口含等待: **13,910.46 s**. 四组合计观测完成速率: **0.38 张/分钟** (不是单模型或最大吞吐).

GPT-Image-2.5 补测正式起止时间 (UTC): `2026-09-17T12:55:11.090492+00:00` to `2026-09-17T15:20:19.735788+00:00`. 正式窗口含等待: **8,708.65 s**.

### 调用链与计时边界

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / Sweden Central"]
    runner --> gpt["GPT-Image-2 / East US 2 / low, medium, high"]
    runner --> gpt25["GPT-Image-2.5 Flare + Sunburst / swedencentral / low, medium, high (2026-09-17)"]
    gpt25 --> evidence
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

原创解释图：本项目实际客户端与服务调用关系，不描绘模型内部结构。 [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) | [GPT image API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e).

### 耗时与请求成功情况

| 指标 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 成功 / 计划样本 | 22 / 22 | 22 / 22 | 22 / 22 | 21 / 22 | 22 / 22 | 22 / 22 | 22 / 22 | 22 / 22 | 22 / 22 | 22 / 22 |
| 首试成功 / 计划样本 | 20 / 22 | 20 / 22 | 20 / 22 | 20 / 22 | 21 / 22 | 22 / 22 | 20 / 22 | 22 / 22 | 22 / 22 | 22 / 22 |
| HTTP 尝试次数 / 429 | 24 / 0 | 24 / 0 | 24 / 0 | 25 / 0 | 23 / 0 | 22 / 0 | 24 / 2 | 22 / 0 | 22 / 0 | 22 / 0 |
| 未成功的 HTTP 尝试 | 2 | 2 | 2 | 4 | 1 | 0 | 2 | 0 | 0 | 0 |
| 未成功尝试累计耗时 (s) | 192.56 | 329.49 | 5,291.35 | 604.30 | 2,829.85 | 0.00 | 6.57 | 0.00 | 0.00 | 0.00 |
| 平均请求耗时 (s) | 45.33 | 38.69 | 65.09 | 175.17 | 22.79 | 24.05 | 33.79 | 33.19 | 41.58 | 77.14 |
| P50 / 描述性 P95 (s) | 38.03 / 79.77 | 31.19 / 81.41 | 64.64 / 74.82 | 171.26 / 215.09 | 21.85 / 26.32 | 23.64 / 28.82 | 32.64 / 39.89 | 32.54 / 42.49 | 40.64 / 48.71 | 76.08 / 83.81 |
| 样本标准差 (s) | 18.56 | 19.69 | 6.01 | 23.51 | 6.25 | 2.79 | 4.37 | 4.86 | 4.30 | 4.88 |
| 最小 / 最大请求耗时 (s) | 32.19 / 106.81 | 23.61 / 99.08 | 56.04 / 78.13 | 139.24 / 241.38 | 16.93 / 48.27 | 18.22 / 30.05 | 27.99 / 44.71 | 26.27 / 47.64 | 34.80 / 51.02 | 70.54 / 89.34 |
| 第一轮 / 第二轮平均 (s) | 47.57 / 43.09 | 43.30 / 34.09 | 67.27 / 62.90 | 171.91 / 178.14 | 24.03 / 21.54 | 22.79 / 25.32 | 34.49 / 33.08 | 33.36 / 33.01 | 41.95 / 41.21 | 78.39 / 75.89 |
| 全部样本平均任务耗时 (s) | 55.06 | 54.65 | 306.58 | 196.12 | 151.93 | 24.13 | 34.72 | 33.24 | 41.63 | 77.19 |
| 成功图片平均大小 (KiB) | 1,737 | 1,673 | 1,666 | 1,683 | 1,675 | 1,687 | 1,679 | 1,678 | 1,724 | 1,681 |

请求耗时从 `requests.post` 调用前到完整 HTTP 响应返回，只统计有图片的成功尝试，不包含后续 JSON/base64 处理和文件写盘。任务耗时覆盖失败尝试、重试等待和响应处理，按全部计划样本统计。失败不以 0 秒进入速度平均值，也不从成功率分母删除。P95 为每组最多 22 个值的描述性线性插值，不是生产尾延迟保证。

### 异常与等待

最长的未成功尝试是 `gpt-image-2-medium-r1-p09`，客户端记录 4,968.72 秒。这是请求调用的客户端经过时间，不是服务端 GPU 推理时长；底层原因未被这些日志确定。异常保留在任务耗时、请求计数和实际完成速率中，未返回图片的样本仍计入计划分母。

| 样本 | 尝试 | HTTP / 异常类型 | 客户端耗时 (s) | 开始 (UTC) | 结束 (UTC) |
| --- | --- | --- | --- | --- | --- |
| gpt-image-2-high-r1-p01 | 1 | ReadTimeout | 301.99 | 2026-09-07T12:35:59.924543+00:00 | 2026-09-07T12:41:11.917183+00:00 |
| gpt-image-2-high-r1-p01 | 2 | ConnectionError | 0.01 | 2026-09-07T12:41:11.921034+00:00 | 2026-09-07T12:41:21.934816+00:00 |
| gpt-image-2-high-r1-p01 | 3 | ConnectionError | 0.00 | 2026-09-07T12:41:21.937598+00:00 | 2026-09-07T12:41:21.941635+00:00 |
| mai-image-2.6-r1-p02 | 1 | ConnectionError | 0.00 | 2026-09-07T12:41:26.958872+00:00 | 2026-09-07T12:41:36.998889+00:00 |
| gpt-image-2-medium-r1-p09 | 1 | ConnectionError | 4,968.72 | 2026-09-07T13:26:31.695448+00:00 | 2026-09-07T14:49:30.415316+00:00 |
| gpt-image-2-low-r1-p11 | 1 | 400 | 20.50 | 2026-09-07T14:58:49.988889+00:00 | 2026-09-07T14:59:20.487114+00:00 |
| gpt-image-2-high-r2-p08 | 1 | ReadTimeout | 302.29 | 2026-09-07T15:40:22.017096+00:00 | 2026-09-07T15:45:34.310843+00:00 |
| mai-image-2.6-r2-p08 | 1 | ReadTimeout | 192.56 | 2026-09-07T15:52:16.770891+00:00 | 2026-09-07T15:55:39.334382+00:00 |
| gpt-image-2-medium-r2-p09 | 1 | ReadTimeout | 322.63 | 2026-09-07T16:01:37.758367+00:00 | 2026-09-07T16:07:10.387228+00:00 |
| gpt-image-2-low-r2-p09 | 1 | ReadTimeout | 309.00 | 2026-09-07T16:08:16.133855+00:00 | 2026-09-07T16:13:35.129678+00:00 |
| gpt-image-2.5-flare-low-r1-p03 | 1 | ConnectionError | 2,829.85 | 2026-09-17T13:04:10.443459+00:00 | 2026-09-17T13:51:30.305674+00:00 |
| gpt-image-2.5-flare-high-r1-p03 | 1 | 429 | 3.28 | 2026-09-17T13:52:50.417450+00:00 | 2026-09-17T13:53:00.695202+00:00 |
| gpt-image-2.5-flare-high-r1-p09 | 1 | 429 | 3.29 | 2026-09-17T14:19:57.895521+00:00 | 2026-09-17T14:20:07.190937+00:00 |

### Token 用量

| 配置 | 返回的输出 token | 成功 / 计划样本 |
| --- | --- | --- |
| MAI-Image-2.6 | 1024 | 22/22 |
| GPT-Image-2 low | 196 | 22/22 |
| GPT-Image-2 medium | 1756 | 22/22 |
| GPT-Image-2 high | 7024 | 21/22 |
| GPT-Image-2.5 Flare low | 196 | 22/22 |
| GPT-Image-2.5 Flare medium | 439 | 22/22 |
| GPT-Image-2.5 Flare high | 1756 | 22/22 |
| GPT-Image-2.5 Sunburst low | 196 | 22/22 |
| GPT-Image-2.5 Sunburst medium | 439 | 22/22 |
| GPT-Image-2.5 Sunburst high | 1756 | 22/22 |

token 用量取自接口返回的 usage，不从模型或档位推算。没有返回值的样本不补零。输出 token 数和 PNG 文件大小都不能单独证明画质。

### 逐场景两轮耗时

单位为秒；失败格对应原始请求记录，不用其他轮次替换。

| 场景 / 轮次 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Sunburst low | GPT-Image-2.5 Sunburst medium | GPT-Image-2.5 Sunburst high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01 / R1 | 38.82 | 51.44 | 78.13 | 失败 | 21.93 | 21.65 | 39.92 | 33.75 | 39.18 | 79.29 |
| 01 / R2 | 33.96 | 26.25 | 63.52 | 182.78 | 17.66 | 22.85 | 30.23 | 30.74 | 40.55 | 75.43 |
| 02 / R1 | 65.12 | 41.67 | 74.93 | 176.78 | 20.45 | 20.34 | 32.41 | 34.85 | 37.45 | 79.97 |
| 02 / R2 | 37.43 | 28.50 | 60.23 | 170.60 | 22.78 | 27.23 | 34.63 | 30.09 | 40.22 | 72.24 |
| 03 / R1 | 32.29 | 82.39 | 68.42 | 170.29 | 48.27 | 21.54 | 32.30 | 28.35 | 36.46 | 70.93 |
| 03 / R2 | 32.19 | 23.61 | 59.58 | 152.75 | 20.04 | 22.78 | 33.99 | 33.48 | 36.23 | 74.38 |
| 04 / R1 | 38.63 | 47.05 | 65.18 | 192.56 | 22.31 | 18.22 | 31.36 | 26.78 | 43.88 | 81.83 |
| 04 / R2 | 34.69 | 23.98 | 59.51 | 171.26 | 18.24 | 26.90 | 27.99 | 36.29 | 38.24 | 71.88 |
| 05 / R1 | 60.09 | 29.09 | 69.86 | 187.57 | 22.87 | 24.71 | 35.22 | 35.94 | 40.73 | 82.79 |
| 05 / R2 | 38.42 | 24.80 | 63.22 | 163.33 | 26.37 | 25.03 | 30.08 | 33.82 | 48.76 | 78.02 |
| 06 / R1 | 80.54 | 62.70 | 71.35 | 190.79 | 20.62 | 23.65 | 29.70 | 31.22 | 41.48 | 72.25 |
| 06 / R2 | 32.25 | 35.88 | 65.19 | 185.09 | 24.02 | 24.58 | 30.02 | 29.72 | 39.82 | 72.77 |
| 07 / R1 | 54.92 | 33.29 | 67.74 | 177.19 | 24.69 | 30.05 | 39.26 | 47.64 | 44.40 | 83.86 |
| 07 / R2 | 37.63 | 35.08 | 66.85 | 170.62 | 23.76 | 26.14 | 36.52 | 42.77 | 47.67 | 89.34 |
| 08 / R1 | 36.49 | 35.03 | 68.73 | 174.50 | 21.65 | 23.34 | 30.04 | 37.12 | 43.32 | 78.61 |
| 08 / R2 | 106.81 | 99.08 | 72.83 | 215.09 | 25.37 | 26.48 | 32.88 | 32.81 | 45.98 | 75.23 |
| 09 / R1 | 49.96 | 37.29 | 61.67 | 169.84 | 21.77 | 23.08 | 29.63 | 26.27 | 51.02 | 76.49 |
| 09 / R2 | 41.92 | 25.10 | 60.62 | 241.38 | 16.93 | 23.64 | 29.72 | 31.72 | 34.80 | 73.62 |
| 10 / R1 | 32.92 | 28.74 | 57.93 | 139.24 | 19.46 | 22.89 | 44.71 | 32.57 | 38.38 | 75.67 |
| 10 / R2 | 42.97 | 25.43 | 64.09 | 153.85 | 24.01 | 28.90 | 39.20 | 31.10 | 42.36 | 70.54 |
| 11 / R1 | 33.49 | 27.58 | 56.04 | 140.32 | 20.30 | 21.21 | 34.86 | 32.52 | 45.18 | 80.64 |
| 11 / R2 | 35.77 | 27.29 | 56.27 | 152.77 | 17.81 | 23.97 | 38.62 | 30.58 | 38.63 | 81.37 |

### 逐场景画面观察

先看可计数的结果，再读逐场景描述。下表统计本次观察记录中出现某类问题的场景数，是这次非盲评的措辞计数，不是模型的缺陷率，也不是质量评分。 GPT-Image-2.5 的图片已在上方并排展示，但未纳入本节的画面观察计数；下表仍只覆盖前四个配置。

| 观测项 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 返回图片 / 计划样本 | 22/22 | 22/22 | 22/22 | 21/22 |
| 裁切 | 1/11 | 3/11 | 2/11 | 2/11 |
| 未请求的文字 | 8/11 | 5/11 | 6/11 | 4/11 |
| 局部难辨或模糊 | 1/11 | 3/11 | 3/11 | 2/11 |

| 场景 | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 1 | 两轮都有蓝色金属和服、花卉与前景虚化；R1背景明亮，R2转为暗调，均未见额外文字。 | 两轮都以紧凑人像和金属花饰为主，画面偏暗；R2衣料更像银色皱箔，高曝光效果不明显。 | 两轮金属花卉与蓝银服饰清楚，整体偏暗；R2面部较光滑、衣料偏硬壳质感。 | R1未返回图片；R2回眸人物与银色金属花饰清楚，顶部发饰被裁切，未见额外文字。 |
| 2 | 两轮都保留凌乱卧室与入口；R1城堡和瀑布比森林抢眼，两轮均加入较多未请求英文标语。 | 两轮石门、林间小路与散落衣物构成场景，室内暗部较深；R2另有海报文字和门框符号。 | 两轮藤蔓石门与卧室杂物可辨；R1门框有发光符号，R2林中出现鹿，部分海报小字难辨。 | 两轮入口内的森林纵深清楚；R1石环有绿色符号，R2木藤入口底部悬离地面。 |
| 3 | 两轮小宇航员、月面和蛋壳均明确；R1是娃娃脸，R2上半蛋壳悬空，带少量服装标记。 | R1宇航员挥手，R2从斑点蛋壳探身；月面和面罩反光明确，未见明显肢体异常。 | 两轮人物都扶着裂壳边缘，月面细节清楚；服装额外加入NASA或类似徽标。 | R1后方高壳壁突出破壳形态，R2挥手且碎壳落地；未见醒目文字或明显结构异常。 |
| 4 | 两轮红龙、巢、桌面、窗光和蒸汽齐全，书名和纸页额外出现大量可读英文。 | 红龙两轮都蜷卧于巢中，器具与背景虚化符合桌面近景；色调偏深暖棕，纸页字迹难辨。 | 两轮蜷睡红龙、书页、枝巢和杯中蒸汽明确；R2局部窗光泛白，书页有密集字样。 | 两轮近景鳞片、巢和器物清楚；R1卷曲身体遮挡肢体，R2杯子遮住部分巢缘，纸卷有小字。 |
| 5 | 两轮白色长耳毛绒主体与浮岛、城堡呼应幻想主题；R2右上多出未请求的英文标语。 | R1粉色长角生物捧发光球，R2白色双角生物趴在苔丘上；两轮均未见额外文字。 | 两轮大眼毛绒主体坐在云上，周围有小配角和梦幻装饰，未见额外文字。 | R1主体头顶似有另一张脸，产生兜帽或双脸歧义；R2大耳生物、花簇和蘑菇清楚，两轮未见文字。 |
| 6 | 两轮水潭、光束、垂藤、兰花和遗迹均出现；R1水下纹理繁密，R2遗迹半浸水关系不易辨认。 | 两轮石庙临水、兰花和光束呼应提示，R1洞壁阴影较重；未见额外叠字。 | 两轮前景石柱、雕刻与浸水结构较明确，建筑占据较多画面，未见额外叠字。 | 两轮光束、水面、垂藤与右侧遗迹清楚；R1洞口部分高光发白，R2前景石柱部分入水。 |
| 7 | 两轮银发蓝眼与全息工坊明确；R1偏动漫风且小字不规整，R2加入NEXA品牌和多处标语。 | 两轮短银发人物点按全息屏，皮肤与夹克质感清楚；均有PROJECT: AURORA，R2杯身另有标语。 | 两轮人物操作机械部件全息图；R1面板右缘被截断，两轮均加入项目名、品牌或标语。 | 两轮发丝、布料和金属反光清楚；全息屏都增加项目名，R2还有额外标语，细小界面字仍难辨。 |
| 8 | 两轮巨眼、星系与密集卷纹构成宇宙景观，并额外加入冥想人物，未见文字。 | 两轮多只巨眼、星球和重复卷纹覆盖天空，地景内容密集；R1细部有颗粒感，均未见文字。 | 两轮以巨眼、球体、旋涡星系和密集纹理为主，R1暗部较深，R2中央几何球发光。 | R1巨眼融入桥状地景并加入行走人物，R2蓝橙双眼近对称且增加冥想人物；均未见文字。 |
| 9 | 两轮银灰龙形侧脸布满螺旋，表面偏雕刻或骨瓷质感，背景虚化；R2另有月下城堡。 | 两轮蓝金镂空龙形近景有清晰眼部和卷须，R1顶部角被裁切，密集装饰的局部连接难辨。 | 两轮蓝金龙首覆盖大小螺旋，浅景深明确，皮肤更像金属雕饰，未见文字。 | R1蓝紫生物有圆瞳与珠粒状螺旋皮肤，卷须交叠处难辨；R2橙眼和多尺度螺旋清楚，未见文字。 |
| 10 | 两轮猫都露齿持双槌打鼓，握槌明显拟人化；鼓组与海报添加英文，R2底鼓和下方文字被裁切。 | 两轮猫露齿举槌，部分前爪有动作模糊；衣服与鼓面增加英文，R2底鼓下缘被裁切。 | 两轮鼓手居中，毛发和镀铬反光清楚；增加I HATE MONDAYS或PAWS OF FURY等文字，部分爪槌边缘模糊。 | 两轮龇牙表情与双槌姿态明确，前景鼓组被画框裁切，另加HISS OFF或BAD KITTY等文字。 |
| 11 | R1猴子弹梨形弦乐器，R2坐在石板路弹吉他；毛发与木纹清楚，书脊或小费碗另有未请求文字。 | 两轮主体弹吉他并增加演出文字，R1脸型偏幼猿，R2琴头被裁切；R1首次输出审核拦截后重试才返回此图。 | 两轮戴草帽猴子弹吉他，背景增加演出文字；R2拨弦手模糊、琴头右端被裁切。 | R1猴子在复古麦克风旁弹吉他，R2闭眼盘腿演奏；材质清楚，背景均有额外英文。 |

逐场景描述来自 [检查记录](data/paired-all-quality-20260907/quality-review.json).

### 本轮实际接口设置

| 接口项目 | MAI-Image-2.6 | GPT-Image-2 / 2.5 |
| --- | --- | --- |
| POST | `/mai/v1/images/generations` | `/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview` |
| Payload | `model`, `prompt`, `width=1024`, `height=1024` | `prompt`, `n=1`, `size=1024x1024`, `quality=low/medium/high` |
| Auth | `api-key` | `api-key` |
| Output | `data[0].b64_json`, PNG | `data[0].b64_json`, PNG |
| Usage | `usage.num_input_text_tokens`, `usage.num_output_tokens` | `usage.input_tokens_details`, `usage.output_tokens_details` |

<a id="reproduction-how-to"></a>
## 复现方法（How-to）与测试

| 目标 | 入口 | 凭据 / 计费 | 完成标志 |
| --- | --- | --- | --- |
| 只读核验已发布证据 | 步骤 4 | 不需要 / 不计费 | 汇总器与回归测试返回 `PASS` |
| 重跑 11 个文生图场景 | 步骤 3 | MAI + GPT / 会计费 | 88 个正式样本全部记录 |
| 重跑联网信息补充测试 | 步骤 5 | MAI / 会计费 | 新目录包含开／关两轮结果 |
| 重跑换帽图像编辑 | 步骤 6 | MAI + GPT / 会计费 | 两轮 8 张 PNG 通过 hash 检查 |
| 重跑 GPT-Image-2.5 六档补测 | 步骤 7 | GPT-2.5 两个部署 / 会计费 | 132 个正式样本全部记录 |

### 1. 克隆并安装依赖

需要可用的 MAI-Image-2.6 和 GPT-Image-2 部署。部署身份由您查询确认，不能仅凭 deployment 名称判断底层模型。先克隆仓库、拉取本项目的 Git LFS 文件，并在 Python 环境安装 requests：

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark
git lfs install
git lfs pull --include="Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**"
python -m pip install requests==2.34.2
```

### 2. 配置自己的部署

下列两个资源根地址和 GPT deployment 名称由您填写。通过自己的秘密管理机制在当前进程提供 `AZURE_API_KEY`（MAI）和 `AZURE_OPENAI_API_KEY`（GPT），不要把值写入源码或 Git。各模型的版本、区域、SKU 和限额环境变量必须填写实际查询结果；下面展示本次实测元数据，不代表您的资源设置。

```powershell
$env:MAI_ENDPOINT = 'https://<mai-resource>.services.ai.azure.com'
$env:GPT_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:GPT_DEPLOYMENT = '<gpt-image-2-deployment>'
$env:GPT_API_VERSION = '2025-04-01-preview'
$env:MAI_MODEL_VERSION = '2026-07-31'
$env:GPT_MODEL_VERSION = '2026-04-21'
$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'
$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'
$env:MAI_DEPLOYMENT_REGION = 'swedencentral'
$env:GPT_DEPLOYMENT_REGION = 'eastus2'
$env:MAI_RATE_LIMIT_RPM = '2.0'
$env:GPT_RATE_LIMIT_RPM = '2.0'
$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'
python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --dry-run
```

### 3. 重跑 11 个文生图场景

第一条模型命令只预热四组，第二条从同一输出目录继续正式矩阵；均会消耗 Azure 服务用量。已有结果不会覆盖，已记录样本不会重跑。续跑要求同一脚本、提示词、端点和配置；中断时在途请求可能已被服务接收。新测试应在执行前保存脚本与 CSV，运行期间不得修改。

```powershell
$run = 'runs/paired-all-quality-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --resume
python scripts/summarize_paired_run.py $run
```

### 4. 只读核验已发布证据

以下命令只重算已保存结果，不调用模型。回归覆盖四档请求、失败分母、原始 usage、图片归属和报告覆盖；模拟 HTTP 只用于离线单元测试，不是图像质量证据。新测批次的汇总与发布必须等全部计划样本结束。

```powershell
python scripts/summarize_paired_run.py data/paired-all-quality-20260907
python scripts/render_paired_report.py data/paired-all-quality-20260907 --check
python -m unittest discover -s tests -v
```

### 5. 重跑联网信息补充测试

联网信息补充测试只需 MAI 部署。第一条只读核验已有归档；第二条只检查参数；第三条才真实重跑完整三题，结果写入新目录，不覆盖已发布数据。

```powershell
python scripts/summarize_web_grounding.py data/lenovo-web-grounding-20260908 --require-complete --check
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction --dry-run
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction
```

### 6. 重跑换帽图像编辑

第 12 题需要 MAI 与 GPT 两个部署。第一条只读核验已发布的两轮 8 张输出；第二条是无凭据、无网络、无写入的 dry-run；第三、四条分别真实执行两轮并写入新目录；第五条只核对配置顺序、`size=auto`、输入与输出 hash。这一步不自动生成主观核对清单，图像质量结论仍需按已发布 review 的方法人工检查。

```powershell
python scripts/summarize_edit_hat_swap.py data/edit-hat-swap-20260909-auto --check
python scripts/run_edit_hat_swap.py --input data/edit-hat-swap-20260909-auto/input.jpg --output runs/edit-hat-swap-reproduction --round 1 --gpt-size auto --dry-run
python scripts/run_edit_hat_swap.py --input data/edit-hat-swap-20260909-auto/input.jpg --output runs/edit-hat-swap-reproduction --round 1 --gpt-size auto
python scripts/run_edit_hat_swap.py --input data/edit-hat-swap-20260909-auto/input.jpg --output runs/edit-hat-swap-reproduction --round 2 --gpt-size auto
python scripts/run_edit_hat_swap.py --output runs/edit-hat-swap-reproduction --check
```

### 7. 重跑 GPT-Image-2.5 六档补测

这一步需要 `gpt-image-2.5-flare` 和 `gpt-image-2.5-sunburst` 两个部署，部署名就是模型名；`--gpt-model` 可重复传入，每个部署展开为 low、medium、high 三组。执行脚本对同一部署每 60 秒最多起请 2 次，与 2 RPM 的部署配额对齐；若你的配额更高，可以改 `RATE_PACING`。第一条只读核验已发布归档；后两条真实调用模型并写入新目录。

```powershell
python scripts/summarize_paired_run.py data/gpt25-paired-20260917
$run = 'runs/gpt25-paired-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --resume
```

文生图执行脚本: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py); 改图执行脚本: [run_edit_hat_swap.py](scripts/run_edit_hat_swap.py); 离线汇总: [summarize_paired_run.py](scripts/summarize_paired_run.py); 报告生成: [render_paired_report.py](scripts/render_paired_report.py); 回归测试: [tests](tests).


### 结论边界

本报告对比 MAI-Image-2.6、GPT-Image-2 三档，以及 GPT-Image-2.5 Flare 与 Sunburst 各三档；2.5 另有 xhigh、max、auto 档，本轮没有测。主要聚合统计来自 11 个 1024x1024 文生图场景；第 12 题是单独报告的 `size=auto` 图像编辑测试，不进入前 11 题的耗时与质量计数，也没有 2.5 的编辑结果。本报告不覆盖 2K、多图参考、文字准确率专项、并发压测或其他认证方式。MAI 没有传质量参数，不能称为任何 GPT 档位的等价档。

证据目录: [data/paired-all-quality-20260907](data/paired-all-quality-20260907). 包含原始图片、测量记录、逐次请求、响应元数据及删减后的公开源码副本。非财务测量字段和图片保持不变；原始执行哈希与公开文件哈希分别记录于 [来源说明](data/paired-all-quality-20260907/provenance.json). 提示词 SHA-256: `be3d628c66a1e4d535d06bcc84246a04aad11f35a48f3133d451fe86283782ce`.

## 联网信息补充测试

本节测试通用的联网信息补充能力：在相同提示词下，对比 MAI-Image-2.6 的 `web_grounding=false/true`，观察文字事实准确性与生成耗时。公开新品资料只是测试题材，不是客户项目或客户采纳案例。

**我们向模型提出的问题**

两个题目都要求模型把真实产品信息画进海报：题目 1 要求列出官方发布的全部配色名与屏幕尺寸选项，题目 2 要求写出产品名、屏幕尺寸、计算平台，并标出官方命名的翻转使用模式与支持笔输入的表面。提示词只要求以官方发布信息为准，没有把正确答案写进提示词。

题目 1（新品配色与尺寸）发给模型的完整提示词：

> Create a polished square English-language launch poster for the Lenovo IdeaPad Vibe series announced at Lenovo Innovation World in September 2026. Present the official launch colour lineup as clearly separated colour swatches, each with its exact official colour name, and include the official screen-size options. Use a restrained stylized laptop silhouette and prioritize readable product information. Base factual claims on Lenovo's announcement; do not substitute colours or models from older IdeaPad products. Do not include prices, purchase links or unsupported specifications.

题目 2（产品规格与使用模式）发给模型的完整提示词：

> Create a polished square English-language creator poster for the Lenovo Yoga 9n 2-in-1 announced at Lenovo Innovation World in September 2026. Include its exact product name, screen size and computing platform. Illustrate and label its officially named convertible usage modes, and describe which surfaces support pen input. Use a simple stylized device illustration with clear readable labels and generous spacing. Base the facts on Lenovo's announcement rather than specifications from older Yoga 9i products. Preserve qualifiers for optional features. Do not include prices or invented specifications.

**受控变量**

唯一变化的是 `web_grounding` 开关。提示词、尺寸、模型版本、部署与轮数完全相同。

完整补测为 12 个正式样本，另有 2 次预热。按已观察到的文字事实改善选取两个题目，保留全部两轮开／关对照，共 8 张原图，每组 4 个样本。下表仅统计这些选例，不是全量提升率。本节没有 GPT 对照，不能据此得出相对 GPT-Image-2 的优势结论。

**文字事实核对结果**

| 测试项 | 关闭联网 | 开启联网 |
| --- | --- | --- |
| 新品配色与尺寸 | 两轮均出现非官方配色名和错误屏幕选项 | 两轮均匹配七种官方配色名及 14/15 英寸选项 |
| 产品规格与使用模式 | 屏幕尺寸和计算平台错误，均漏掉 Canvas 模式 | 两轮均写对 16 英寸、NVIDIA RTX Spark、五种模式及笔输入表面 |

**耗时与请求情况**

| 指标 | 关闭联网 | 开启联网 |
| --- | --- | --- |
| 返回图片 / 展示样本 | 4/4 | 4/4 |
| 首试成功 / 展示样本 | 4/4 | 1/4 |
| HTTP 请求次数 | 4 | 7 |
| HTTP 408 次数 | 0 | 3 |
| 成功请求平均耗时 | 35.75 秒 | 68.91 秒 |
| 成功请求 P50 | 34.57 秒 | 67.23 秒 |
| 含失败重试的逻辑调用平均耗时 | 35.77 秒 | 168.21 秒 |

固定 1024x1024、`auto_aspect_ratio=false`，同一模型版本 2026-07-31、Sweden Central GlobalStandard 部署；第二轮反转请求顺序。两组仅联网开关不同，核对答案未加入提示词。成功请求耗时不含 JSON/base64 处理；逻辑调用耗时包含失败、退避和响应处理，不含外侧 5 秒间隔及最终 PNG 写盘。所有 HTTP 408 和重试均保留，服务未说明内部超时环节，不能把全部额外时间归因于搜索。

文字事实改善不等于画面质量或产品外观保真。第二题第二轮开启图中，`Tablet Mode` 标签下仍画着竖起的屏幕，存在图文不一致。观察为 AI 辅助非盲评，只有少量重复，不是人工偏好或统计显著性结论。响应没有提供检索查询、来源 URL 或调用轨迹；usage 变化不能证明具体检索来源。

#### 新品配色与尺寸 / 第1轮

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 1, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r1/01_test.png) | ![Web grounding on, subject 1, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r1/01_test.png) |

#### 新品配色与尺寸 / 第2轮

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 1, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r2/01_test.png) | ![Web grounding on, subject 1, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r2/01_test.png) |

#### 产品规格与使用模式 / 第1轮

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 2, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r1/02_test.png) | ![Web grounding on, subject 2, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r1/02_test.png) |

#### 产品规格与使用模式 / 第2轮

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 2, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r2/02_test.png) | ![Web grounding on, subject 2, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r2/02_test.png) |

完整原始数据保留，旧批次不重写；本节与上文双模型测试分别统计，复现命令见下方复现与测试章节。

[原始结果](data/lenovo-web-grounding-20260908/5way_v2_results.json) | [全部请求](data/lenovo-web-grounding-20260908/attempts.jsonl) | [逐图观察](data/lenovo-web-grounding-20260908/visual-review.json) | [完整12样本统计](data/lenovo-web-grounding-20260908/web-grounding-summary.json) | [出处与哈希](data/lenovo-web-grounding-20260908/provenance.json)

结果 SHA-256: `669617dd5d59d0748a0fc398d98ec4c59cb4b26cc9655138edf9b6c9622f3c1b`.

官方参考：[IdeaPad Vibe](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/) | [Yoga](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/) | [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)
