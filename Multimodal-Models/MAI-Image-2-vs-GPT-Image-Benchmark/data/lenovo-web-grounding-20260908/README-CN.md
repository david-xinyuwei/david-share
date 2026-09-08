# 联想新品：MAI-Image-2.6 联网效果选例

[English](README.md) | [主报告：双模型对比](../../README-CN.md)

**本页展示观察到新品文字事实改善的两个场景：IdeaPad Vibe 和 Yoga 9n 2-in-1。** 每个场景保留联网开／关的全部两轮，共 8 张正式原图，不挑选其中最好的一轮。

这是按已观察到的改善选择的案例展示，不代表全量测试或所有场景都会提升。完整补测为 3 个场景、12 个正式样本，另有两次预热；原始数据和完整对照均保留，其余场景不在本页展示。下方指标仅由这 8 个展示样本重算，每组 4 个样本，预热不计入。本轮没有调用 GPT，不覆盖原有双模型报告。

## 主要结果

开启组在两轮中都写对了 IdeaPad Vibe 的配色、屏幕选项，以及新 Yoga 的主要规格与模式名称；关闭组两轮都出现这些新品信息的错误。这里的改善指核对过的文字事实，不是整体美感、产品外观或所有额外文案均正确。

| 场景 | 关闭联网，两轮观察 | 开启联网，两轮观察 |
| --- | --- | --- |
| IdeaPad Vibe 配色海报 | 每轮都给出 4 个不属于官方七色的名称。屏幕分别写成 14/16 和 14/15.3/16 英寸 | 两轮均列对七个官方配色名称，屏幕均为 14/15 英寸 |
| Yoga 9n 2-in-1 创作者海报 | 屏幕分别写成 14.5 和 14 英寸，均写为 Intel Core Ultra，仅列四种模式，漏掉 Canvas | 两轮均写对 16 英寸、NVIDIA RTX Spark、五种模式，以及屏幕和 Haptic Force Pad 的笔输入 |

Yoga 关闭组第二轮提到了可选触控板笔输入，比第一轮的“键盘面支持笔输入”更接近公告，但屏幕、平台和模式数量仍错误。开启组也有图文一致性问题：第二轮的 `Tablet Mode` 标签下仍画着竖起的屏幕，不能当作准确的平板模式示意。文字事实改善不等于成品已达到正式营销素材要求。

## 耗时与失败

| 指标 | 关闭联网 | 开启联网 |
| --- | ---: | ---: |
| 返回图片 / 展示样本 | 4/4 | 4/4 |
| 首次请求成功 / 展示样本 | 4/4 | 1/4 |
| 展示样本的 HTTP 请求次数 | 4 | 7 |
| HTTP 408 次数 | 0 | 3 |
| 成功 HTTP 请求平均耗时 | 35.75 秒 | 68.91 秒 |
| 成功 HTTP 请求 P50 | 34.57 秒 | 67.23 秒 |
| 含失败、重试的逻辑调用平均耗时 | 35.77 秒 | 168.21 秒 |

三次 HTTP 408 均出现在开启组：第一轮的 IdeaPad、第一轮的 Yoga、第二轮的 Yoga。每次均在既定重试策略下成功，失败没有从日志或耗时中删除。服务只返回 Timeout，未定位到 Bing、模型推理或其他内部环节，因此不作进一步根因归因。

成功 HTTP 耗时覆盖发出请求至完整响应接收，不含 JSON 解码。逻辑调用耗时还包括失败请求、退避、JSON/base64 处理和响应元数据写入，不含外侧固定 5 秒间隔及最后的 PNG 文件写盘。两者都不是纯 GPU 推理时间。

## 看原图

以下为两类展示场景的全部 8 张原始 PNG，均来自 MAI-Image-2.6，固定 1024×1024、`auto_aspect_ratio=false`。没有重新生成、修图或替换输出。

### IdeaPad Vibe：第一轮

检查官方配色名称与 14/15 英寸选项，而不只是版式。

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![IdeaPad 第一轮，关闭联网](mai-image-2.6-web-off/r1/01_test.png) | ![IdeaPad 第一轮，开启联网](mai-image-2.6-web-on/r1/01_test.png) |

### IdeaPad Vibe：第二轮

本轮反转请求顺序，先开启、后关闭；展示列顺序仍保持左关右开。

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![IdeaPad 第二轮，关闭联网](mai-image-2.6-web-off/r2/01_test.png) | ![IdeaPad 第二轮，开启联网](mai-image-2.6-web-on/r2/01_test.png) |

### Yoga 9n 2-in-1：第一轮

检查屏幕尺寸、计算平台、五种模式名称和两个笔输入表面的文字，不将模式插图视作产品实拍。

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Yoga 第一轮，关闭联网](mai-image-2.6-web-off/r1/02_test.png) | ![Yoga 第一轮，开启联网](mai-image-2.6-web-on/r1/02_test.png) |

### Yoga 9n 2-in-1：第二轮

同样反转请求顺序。模式名称写对，但开启图中的 `Tablet Mode` 姿态仍需纠正。

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Yoga 第二轮，关闭联网](mai-image-2.6-web-off/r2/02_test.png) | ![Yoga 第二轮，开启联网](mai-image-2.6-web-on/r2/02_test.png) |

## 范围与证据

- 模型为 MAI-Image-2.6，部署版本 2026-07-31；同一 Sweden Central GlobalStandard 部署，串行请求，固定 1024×1024，自动比例显式关闭。
- 完整补测使用三条提示词，本页选取其中第 1、2 题；每题两组的提示词完全相同，唯一请求差异是 `web_grounding` 布尔值。第二轮反转组别顺序。核对答案只在参照文件中，未加入模型请求。
- 原图已逐张检查。观察为 AI 辅助非盲评，不是客户反馈、人工偏好投票或统计显著性结论；本页每组只有 4 个样本，且场景按已观察到的改善选入，不能据此计算全量提升率。
- 返回元数据未提供检索查询、来源 URL 或调用轨迹。输入文本 token 数有变化，但不能据此确定具体检索来源或内部实现。图片上“基于官方信息”的字样也不是检索证据。
- 本轮验证的是所选事实是否匹配公告，不是产品摄影、机身几何、Logo 或色彩校准。正式营销素材仍需使用批准的产品参考图并进行人工审核。
- 本轮没有 GPT 对照，因此不能从这些结果得出 MAI 相对 GPT-Image-2 的优势结论。

实际正式执行：2026-09-08 02:06:40–02:23:50 UTC，退出码 0，状态 `COMPLETED`。

完整原始结果（12 样本）：[5way_v2_results.json](5way_v2_results.json)；全部尝试：[attempts.jsonl](attempts.jsonl)；全量机器可读汇总（不是上表的选例统计）：[web-grounding-summary.json](web-grounding-summary.json)；原始逐图观察：[visual-review.json](visual-review.json)；[出处与文件哈希](provenance.json)。未展示样本与完整原图证据均保留，未从证据中删除。

原始结果 SHA-256：`669617dd5d59d0748a0fc398d98ec4c59cb4b26cc9655138edf9b6c9622f3c1b`。

## 复现与核验

先完成[主报告的环境配置](../../README-CN.md)，在本项目根目录运行。`MAI_ENDPOINT` 和 `AZURE_API_KEY` 从安全环境变量读取。以下离线命令不调用模型，也不修改归档：

```bash
python scripts/summarize_web_grounding.py data/lenovo-web-grounding-20260908 --require-complete --check
```

需要重跑完整三题补测时，使用当时实际执行的冻结脚本和原提示词，结果写入新目录。第一条只检查参数；第二条会真实调用模型，包含两次预热和 12 个计划正式样本：

```bash
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction --dry-run
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction
```

`--resume` 只用于继续同一批次，不替换已完成样本；保留失败和全部两轮。本次发布没有重新调用模型。

## 官方参照

参照页面在请求前读取并保存快照，URL 与快照哈希见 [source-captures.json](source-captures.json)。[冻结核对项](source/reference-facts.json)记录的是事前计划和参考事实，不代表执行状态。

- [Lenovo IdeaPad Vibe 公告，2026-09-03](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/)
- [Lenovo Yoga 新品公告，2026-09-03](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/)
- [MAI 图像接口参数](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)

**当前建议：优先把联网能力用于需要准确引用近期新品信息的营销初稿；不要默认对所有图片开启。** 本轮事实改善伴随更高延迟和三次超时重试，是否采用应结合客户对等待时间、事实审核和素材用途的要求。