# Microsoft Foundry 的训练：方式、方法、支持的模型和区域

[English](FOUNDRY_TRAINING.md) · 返回 [README](../README_CN.md)

本页整理自 Microsoft Learn 的文章 [Training in Microsoft Foundry](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/overview)。不用离开仓库，就能查到本仓库这两条路径周围还有哪些选择：两种训练方式、几种定制方法、训练在哪里运行、训练好的模型怎么部署，以及 Microsoft 为每一项列出的模型和区域。

> **本页是什么。** 本仓库作者根据这篇文章整理的摘要，依据的是 2026 年 11 月 17 日最后更新的版本，读取于 2026 年 11 月 23 日。[支持的模型](#支持的模型)、[Global 训练支持的区域](#global-训练支持的区域)和 [Serverless 部署支持的区域](#serverless-部署支持的区域)三节的表格，逐格照录文章里的值。说明文字是作者自己的表述，不是 Microsoft 的原文，本页也不是 Microsoft 的官方页面。文章会更新，选模型和区域之前请先看文章。

## 本仓库用的是哪一种组合

本仓库有两条路径，终点都是部署在 Managed compute 上的 LoRA 适配器。两条都在 README 的第 3 步里：选项 A 在门户里提交 Managed Training 任务，选项 B 运行 `training/programmed_training_sft.py` 里的循环。两条路径都用同一份数据实际跑过，README 报告了方法和结果。

| 文章里的选项 | 路径 1：Managed Training（第 3 步的选项 A） | 路径 2：Programmed Training（第 3 步的选项 B） | 所在章节 |
|---|---|---|---|
| 模型 | `Qwen3.8-27B`（预览） | `Qwen3.8-27B`（预览） | [支持的模型](#支持的模型) |
| 训练方式 | Managed Training（托管训练） | Programmed Training（预览） | [两种训练方式](#两种训练方式) |
| 定制方法 | 监督微调（SFT） | 示例仓库里的监督训练配方；预定义的方法只属于 Managed Training | [定制方法](#定制方法) |
| 训练类型 | Global | 训练循环里没有这一项设置 | [训练类型](#训练类型) |
| 部署选项 | Managed compute（托管计算）：LoRA 适配器挂在基础模型的部署上 | 相同 | [部署选项](#部署选项) |
| Foundry 项目所在区域 | 作者测试时用的是 East US 2 | 作者测试时用的是 East US 2 | [Global 训练支持的区域](#global-训练支持的区域) |

两条路径见 [README](../README_CN.md)：每一条怎么运行，各自测到了什么。本页其余部分是文章列出的其他选择。下文表格里的对勾表示 Microsoft 声明提供这种组合，不代表本仓库测过。

## 什么时候值得训练

训练是用任务相关的数据，让一个预训练模型适应你的任务。它改的是模型权重，不是往每条提示词里加示例。团队手里有高质量的任务数据时，文章列了六种用处：

- **准确性和相关性。** 提示词里放不下的大量示例，可以通过训练教给模型。
- **缩短提示词。** 提示词里的示例少了，token 费用和延迟都会下降。
- **风格和结构。** 回答保持统一的语气、格式或 schema。
- **工具调用。** 选哪个工具、参数怎么填，都更准。
- **检索到的上下文。** 模型学会用相关的上下文，忽略无关的内容。
- **用更小的模型。** 用大模型（教师模型）生成的示例训练小模型，让它以更低的费用和延迟完成任务。

这些效果都没有保证，要用留出的数据把训练后的模型和基线对比。训练会增加训练费用和托管费用（见 [Manage fine-tuning costs](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/cost-management)）。它既不能代替检索来获取最新信息，也不能代替应用自身的安全控制。

## 两种训练方式

Foundry 有两种训练方式。两种都运行在 Foundry 管理的训练基础设施上，你都不用自己准备训练用的 GPU。

| 问题 | Managed Training（托管训练） | Programmed Training（预览） |
|---|---|---|
| 训练循环由谁运行 | Foundry。你提交一个任务，带上数据和设置 | 你自己的 Python 程序。程序请求哪些训练和采样操作，Foundry 就执行哪些 |
| 适合谁 | 初学者，以及更愿意用预定义流程、不想碰底层训练操作的 AI 工程师 | 要自己搭训练流程、有经验的机器学习从业者 |
| 你能控制什么 | 数据、该方法支持的超参数，以及 RFT 任务的评分器 | 损失函数、奖励、rollout、梯度累积、权重更新和检查点 |
| 训练方法 | SFT、DPO 和 RFT，具体看模型；也可以用教师模型生成的 SFT 数据做蒸馏 | SFT、强化学习、偏好学习、蒸馏和自定义损失函数的示例配方 |
| 文章举的例子 | 蒸馏一个更大的模型、从客服对话里学习、用评分器改进回答 | 收集调用工具的 rollout、使用自己定义的奖励、改变训练循环里更新和评估的做法 |

- Programmed Training 是预览功能，要先提交访问申请并获批，才能创建训练会话：[预览申请表](https://aka.ms/foundry-interactive-training-signup)。
- 文章建议刚接触模型定制的人从 Managed Training 开始。
- 一个模型支持某种训练方式、方法或模态，不等于也支持另一种；示例仓库里有某个配方，也不说明服务提供这种组合。以[支持的模型](#支持的模型)一节的表为准。

名词：rollout 是模型把一个任务完整做一遍的一次尝试；评分器（grader）是给模型生成的回答打分的组件。

第二种方式的详细介绍：[What is Programmed Training (preview)?](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/programmed-training/overview)

## 定制方法

定制方法决定模型从什么里学。三种预定义方法都属于 Managed Training。Programmed Training 没有预定义方法，它提供的是训练用的基本操作，由你自己搭流程。

| 方法 | 模型从什么里学 | 什么时候适用 |
|---|---|---|
| **监督微调（SFT）** | 提示词和你期望的回答，成对给出 | 你能示范出模型应该学会的行为 |
| **偏好微调，用直接偏好优化（DPO）** | 对同一个输入，一个更好的回答和一个被否定的回答 | 质量取决于偏好，比如语气或完整程度，没有唯一的正确答案 |
| **强化微调（RFT）** | 提示词，加一个给模型生成的回答打分的评分器 | 解法不止一种，而且你能可靠地给解法的质量打分 |

Microsoft Learn 上的指南：[监督微调](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning)、[直接偏好优化](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning-direct-preference-optimization)、[强化微调](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reinforcement-fine-tuning)。

## 训练类型

训练类型决定训练任务在哪里运行，以及适用哪种容量、价格和保证。它和部署类型是两回事：部署类型决定训练好的模型怎么提供推理服务。

| 训练类型 | 训练在哪里运行 | 价格和保证 |
|---|---|---|
| **Standard** | 在 Foundry 资源所在的区域 | 保证数据驻留。适合数据必须留在某个区域的业务 |
| **Data zone** | 在一个数据区域（data zone）内，不限定在单个区域。目前只支持美国数据区域 | 适合数据必须留在该数据区域内的业务 |
| **Global** | 使用你所在区域之外的容量。数据和权重会被复制到实际训练的区域 | 价格比 Standard 低，不提供数据驻留。适合没有驻留要求、又想少排队的业务 |
| **Developer** | 使用闲置容量 | 能省下不少费用。不保证延迟，也没有服务级别协议：任务可能被抢占，之后再恢复。不提供数据驻留。适合做试验和对价格敏感的业务 |

## 部署选项

训练好的模型，Foundry 用两种方式之一来部署，两者的推理基础设施和计费方式不同：

- **Serverless（无服务器部署）。** Foundry 托管微调后的模型，推理基础设施也由它运行。
- **Managed compute（托管计算）。** 用独占 GPU 运行对应的基础模型，再挂上一个或多个兼容的 LoRA 适配器。在 Managed compute 上部署适配器目前是预览功能。本仓库用的就是这一种。

一个模型能用哪一种，取决于模型、部署选项和训练产出的是什么，见[支持的模型](#支持的模型)。Serverless 下有五种部署类型，决定推理在哪里运行、用什么容量、怎么计费：

| Serverless 部署类型 | 推理在哪里运行 | 计费和限制 |
|---|---|---|
| **Standard** | 在部署所在的区域 | 按 token 计费；微调模型如需托管费，另计 |
| **Data Zone Standard** | 在一个数据区域内。只支持美国数据区域 | 按 token 计费 |
| **Global Standard** | 使用全球容量。自定义模型的权重可能暂时存放在资源所属地理范围之外 | 按 token 计费 |
| **Developer** | 在全球范围 | 按 token 计费，没有按小时收的托管费。不保证数据驻留，没有可用性服务级别协议。只用于评估：部署保留 24 小时 |
| **Provisioned Throughput** | 使用区域容量 | 按预配吞吐量单位（PTU）计费，吞吐量可预期 |

部署步骤见 [Deploy fine-tuned models](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/deploy-fine-tuned-models)。

## 支持的模型

文章列了 18 个模型。每一行是一个模型：支持哪种训练方式（括号里是 Managed Training 的方法）、哪些训练类型、哪些部署选项。能用 Serverless 部署的模型，默认可以用 Global Standard、Data Zone Standard 和 Developer 三种部署类型，表注另有说明的除外。Standard 和 Provisioned Throughput 另有两张表，见 [Serverless 部署支持的区域](#serverless-部署支持的区域)。

| 模型 ID | 训练方式 | 训练类型 | 部署选项 |
|---|---|---|---|
| `MAI-Code-1.1-Flash`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(RFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;❌<br>Data zone:&nbsp;❌<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |
| `Muse-Glimmer-30B`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;RFT)<br>Programmed Training:&nbsp;✅ | Standard:&nbsp;❌<br>Data zone:&nbsp;❌<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;❌<br>Managed compute:&nbsp;✅ |
| `Llama-3.3-70B-Instruct` | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;❌<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;❌ | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |
| `Qwen3-32B` | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;❌<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;❌ | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |
| `Qwen3.6-35B-A3B`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;RFT)<br>Programmed Training:&nbsp;✅ | Standard:&nbsp;❌<br>Data zone:&nbsp;❌<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;❌<br>Managed compute:&nbsp;✅ |
| `Qwen3.8-27B`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;RFT)<br>Programmed Training:&nbsp;✅ | Standard:&nbsp;❌<br>Data zone:&nbsp;❌<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;❌<br>Managed compute:&nbsp;✅ |
| `gpt-oss-20b` | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;✅ | Standard:&nbsp;❌<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;❌ | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |
| `gpt-oss-120b`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;RFT)<br>Programmed Training:&nbsp;✅ | Standard:&nbsp;❌<br>Data zone:&nbsp;❌<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;❌<br>Managed compute:&nbsp;✅ |
| `Ministral-3B`<br>(2411) | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;❌<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;❌ | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |
| `gpt-4o-mini`<br>(2024-07-18) | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<sup>4</sup><br>Managed compute:&nbsp;❌ |
| `gpt-4o`<br>(2024-08-06) | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;DPO)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<sup>4</sup><br>Managed compute:&nbsp;❌ |
| `gpt-4.1`<br>(2025-04-14) | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;DPO)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<br>Managed compute:&nbsp;❌ |
| `gpt-4.1-mini`<br>(2025-04-14) | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;DPO)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<br>Managed compute:&nbsp;❌ |
| `gpt-4.1-nano`<br>(2025-04-14) | Managed Training:&nbsp;✅&nbsp;(SFT,&nbsp;DPO)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<br>Managed compute:&nbsp;❌ |
| `o4-mini`<br>(2025-04-16) | Managed Training:&nbsp;✅&nbsp;(RFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;✅ | Serverless:&nbsp;✅<br>Managed compute:&nbsp;❌ |
| `gpt-5`<br>(2025-08-07)<sup>2</sup> | Managed Training:&nbsp;✅&nbsp;(RFT)<br>Programmed Training:&nbsp;❌ | Standard:&nbsp;✅<br>Data zone:&nbsp;✅<br>Global:&nbsp;✅<br>Developer:&nbsp;❌ | Serverless:&nbsp;✅<sup>3</sup><br>Managed compute:&nbsp;❌ |
| `MedImageInsight-Premium`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;❌ | Global | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |
| `CXRReportgen-Premium`<br>（预览） | Managed Training:&nbsp;✅&nbsp;(SFT)<br>Programmed Training:&nbsp;❌ | Global | Serverless:&nbsp;✅<sup>1</sup><br>Managed compute:&nbsp;❌ |

表注：

- <sup>1</sup> 这个模型的 Serverless 部署只支持 Global Standard 部署类型。
- <sup>2</sup> GPT-5 的强化微调需要邀请，通过你的 Microsoft 客户团队登记。
- <sup>3</sup> 这个模型的 Serverless 部署只支持 Standard 部署类型，区域见下文。
- <sup>4</sup> 这个模型不支持 Developer 部署类型。

对本仓库这条路径，这张表说明了什么：

- 18 个模型全部支持 Managed Training。
- 能部署到 Managed compute 的有 4 个：`Muse-Glimmer-30B`、`Qwen3.6-35B-A3B`、`Qwen3.8-27B` 和 `gpt-oss-120b`。它们都是预览模型，Managed Training 支持 SFT 和 RFT，也支持 Programmed Training，训练类型只有 Global 和 Developer，都不能用 Serverless 部署。
- 支持 Programmed Training 的有 5 个：上面 4 个，加上 `gpt-oss-20b`（它用 Serverless 部署）。

## Global 训练支持的区域

Global Managed Training 和 Programmed Training 要求 Foundry 项目建在下表 27 个区域之一。Global 训练每个 token 的价格比 Standard 低（见[价格](https://aka.ms/oai/pricing)），不提供[数据驻留](https://aka.ms/data-residency)。Standard 和 Data zone 训练支持的区域另算，不在这张表里。

| Foundry 项目所在区域 | Global Managed Training | Programmed Training（预览） |
|---|---|---|
| Australia East | ✅ | ✅ |
| Brazil South | ✅<sup>1</sup> | ❌ |
| Canada Central | ✅<sup>1</sup> | ❌ |
| Canada East | ✅<sup>1</sup> | ✅ |
| East US | ✅ | ✅ |
| East US 2 | ✅ | ✅ |
| France Central | ✅<sup>1</sup> | ❌ |
| Germany West Central | ✅<sup>1</sup> | ❌ |
| Italy North | ✅<sup>1</sup> | ❌ |
| Japan East | ✅<sup>1,2</sup> | ❌ |
| Korea Central | ✅ | ✅ |
| North Central US | ✅ | ✅ |
| Norway East | ✅<sup>1</sup> | ❌ |
| Poland Central | ✅<sup>1,3</sup> | ❌ |
| South Africa North | ✅<sup>1</sup> | ❌ |
| South Central US | ✅<sup>1</sup> | ❌ |
| South India | ✅<sup>1</sup> | ❌ |
| Southeast Asia | ✅<sup>1</sup> | ❌ |
| Spain Central | ✅<sup>1</sup> | ❌ |
| Sweden Central | ✅ | ✅ |
| Switzerland North | ✅ | ✅ |
| Switzerland West | ✅<sup>1</sup> | ❌ |
| UAE North | ✅<sup>4</sup> | ✅ |
| UK South | ✅ | ✅ |
| West Europe | ✅<sup>1</sup> | ❌ |
| West US | ✅<sup>1</sup> | ❌ |
| West US 3 | ✅ | ✅ |

表注：

- <sup>1</sup> 这个区域不支持 `Qwen3.6-35B-A3B`、`Qwen3.8-27B`、`Muse-Glimmer-30B` 和 `gpt-oss-120b` 的 Managed Training。
- <sup>2</sup> Japan East 不支持视觉微调。
- <sup>3</sup> Poland Central 不支持 `gpt-4.1-nano` 的 Managed Training。
- <sup>4</sup> UAE North 的 Global Managed Training 只支持 `Qwen3.6-35B-A3B`、`Qwen3.8-27B`、`Muse-Glimmer-30B` 和 `gpt-oss-120b`。

对本仓库这条路径，这张表说明了什么：

- `Qwen3.8-27B` 的 Global Managed Training 列在 10 个区域：Australia East、East US、East US 2、Korea Central、North Central US、Sweden Central、Switzerland North、UAE North、UK South 和 West US 3。
- Programmed Training 列在 11 个区域：上面 10 个，加上 Canada East。

## Serverless 部署支持的区域

只有下表 7 个模型支持 Serverless 的 Standard 部署类型，各自支持的区域如下：

| 模型 ID | Standard 部署：<br>East US 2 | Standard 部署：<br>North Central US | Standard 部署：<br>Sweden Central |
|---|---|---|---|
| `gpt-4o-mini` | ❌ | ✅ | ✅ |
| `gpt-4o` | ✅ | ❌ | ✅ |
| `gpt-4.1` | ❌ | ✅ | ✅ |
| `gpt-4.1-mini` | ❌ | ✅ | ✅ |
| `gpt-4.1-nano` | ❌ | ✅ | ✅ |
| `o4-mini` | ✅ | ❌ | ✅ |
| `gpt-5` | ❌ | ✅ | ✅ |

只有下表 3 个模型支持 Serverless 的 Provisioned Throughput 部署，各自支持的区域如下：

| 模型 ID | Provisioned Throughput 部署：<br>North Central US | Provisioned Throughput 部署：<br>Sweden Central |
|---|---|---|
| `gpt-4o-mini` | ✅ | ✅ |
| `gpt-4o` | ✅ | ✅ |
| `gpt-4.1` | ❌ | ✅ |

这两张表和本仓库的路径无关：`Qwen3.8-27B` 不能用 Serverless 部署。

## 要提前考虑的局限

文章把训练称为一个反复迭代的工程过程，不保证一定有改进，并列了 8 件要提前考虑的事：

1. **数据质量和覆盖面。** 示例要准确、一致、有代表性。上传数据之前，检查有没有漏掉的场景、重复数据、偏见和敏感信息。
2. **过拟合和评估泄漏。** 训练数据、验证数据和最终测试数据要分开。比较检查点时看留出任务上的表现，不要只看训练损失。
3. **有误导性的奖励信号。** 用正确的、错误的和对抗性的回答分别测试 RFT 评分器。如果模型是在钻评分器的空子，奖励上升并不说明任务做得更好。
4. **试验和费用。** 预算要算上反复运行、评分、评估、托管和推理。目标指标没有改进的试验就停掉。
5. **模型和部署的兼容性。** 训练之前确认方法、档位、版本和部署资格。适配器不能换到名字相近的另一个基础模型上用。
6. **维护。** 任务数据变了，或者基础模型临近停用时，重新评估质量。可能需要重新训练、重新部署。
7. **安全和治理。** 检查数据处理方式和托管的安全评估。应用自身的安全控制要保留，并且对最终提供推理的运行环境做评估。
8. **Programmed Training 运行时的责任。** 驱动程序、环境、分词、检查点和恢复逻辑都由你维护。在训练会话里采样得到的结果，不能证明模型在生产环境部署后的表现。

## Microsoft Learn 上的指南

- [Customize a model with supervised fine-tuning](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning)（监督微调）
- [Customize a model with direct preference optimization](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning-direct-preference-optimization)（直接偏好优化）
- [Customize a model with reinforcement fine-tuning](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/reinforcement-fine-tuning)（强化微调）
- [Get started with Programmed Training](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/programmed-training/quickstart)（Programmed Training 快速入门）
- [Customize a premium healthcare AI model](https://learn.microsoft.com/en-us/azure/foundry/how-to/healthcare-ai/fine-tune-premium-healthcare-models)（定制医疗 AI 模型）
- [Deploy fine-tuned models](https://learn.microsoft.com/en-us/azure/foundry/fine-tuning/deploy-fine-tuned-models)（部署微调后的模型）
- [Run evaluations from the Foundry portal](https://learn.microsoft.com/en-us/azure/foundry/how-to/evaluate-generative-ai-app)（在 Foundry 门户里做评估）
- [Fine-tuning samples on GitHub](https://github.com/microsoft-foundry/fine-tuning)（GitHub 上的微调示例）
