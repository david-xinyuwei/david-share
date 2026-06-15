# Foundry Agent Post-Training：从 Distillation 到 Reinforcement Learning

[![Microsoft Foundry](https://img.shields.io/badge/Microsoft-Foundry-blue)](https://learn.microsoft.com/azure/ai-foundry/)
[![Build 2026](https://img.shields.io/badge/Build-2026-purple)](https://build.microsoft.com)
[![Official Code](https://img.shields.io/badge/Official%20Code-BRK232-green)](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry)
[![Post-Training](https://img.shields.io/badge/Post--Training-SFT%20%7C%20RFT%20%7C%20Low--Level%20API-orange)](#三层训练体系)

Microsoft Build 2026 发布的 Agent Post-Training 全链路技术拆解——覆盖 distillation、SFT、RFT 和全新的 Foundry Low-Level Training API。基于 BRK231 + BRK232 两个 session。**结果：Qwen3-32B 达到 86.9% retail_quality（~$0.50/M tokens）——超越 GPT-5.4（65%，$15/M）。**

> **Author**: 魏新宇 (Xinyu Wei) — Microsoft AI GBB

[English](README.md) | 中文版 | [微软官方 BRK232 代码 Repo](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry)

---

## 为什么重要

Agent 每轮消耗的 token 是传统 chat 的 **20–30 倍**。当三分之一的企业应用计划在两年内嵌入 agentic AI，成本等式直接崩了。Fine-tuning 比直接用 frontier 模型便宜 **10 倍**：

<div align="center"><img src="images/slide-cost-efficiency.png" width="960"></div>

> 来源：BRK232 Slide 3 — MAI-2-5B Frontier Tuned 质量匹敌 GPT-5.x，成本效率 >10x（95 output tokens/$ vs 10–26）。任务：生成微软技术文档。

| 维度 | 优化前（Frontier 模型） | 优化后（Fine-Tuned 小模型） |
|:-----|:---------------------|:--------------------------|
| **成本** | GPT-5.4 @ $15/M tokens | GPT-4.1 mini fine-tuned @ ~$0.50/M |
| **延迟** | 2–6 秒/轮 | 亚秒级 streaming |
| **质量** | 65–74% 任务准确率 | **84–87%**（超越 frontier） |
| **IP** | 你的领域知识帮别人训模型 | IP 留在自己的定制模型里 |

> "Agent 帮我们做了这个 slide deck，Agent 帮我们做了这个 demo。一半的团队今天已经有某种 production agent 了。问题是：Agent 每轮消耗 20 到 30 倍的 token。"
> — Alicia Frame, Product Lead for Model Customization, Microsoft Foundry ([BRK231](https://build.microsoft.com/en-US/sessions/BRK231))

---

## 目录

- [优化路径](#优化路径)
- [三层训练体系](#三层训练体系)
- [Layer 1: Distillation + SFT — 模仿学习](#layer-1-distillation--sft--模仿学习)
- [Layer 2: Reinforcement Fine-Tuning (RFT) — 从错误中学习](#layer-2-reinforcement-fine-tuning-rft--从错误中学习)
- [Layer 3: Low-Level Training API — 完全掌控算法](#layer-3-low-level-training-api--完全掌控算法)
- [经济账：数字走一遍](#经济账数字走一遍)
- [Leaderboard：质量递进](#leaderboard质量递进)
- [客户生产部署案例](#客户生产部署案例)
- [用 Coding Agent 做 Fine-Tuning](#用-coding-agent-做-fine-tuning)
- [选型指南：什么时候用什么](#选型指南什么时候用什么)
- [从训练到部署](#从训练到部署)
- [上手指南](#上手指南)
- [关键资源](#关键资源)
- [Running on Azure](#running-on-azure)
- [关联 Repo](#关联-repo)
- [核心技术深潜](#核心技术深潜)
- [官方 Repo 全景](#官方-repo-全景)
- [跨 Session 分析](#跨-session-分析训练-vs-推理-vs-agent-运营)
- [持续改进 Playbook](#持续改进-playbook)

---

## 优化路径

Fine-tuning 不是第一步——在 Foundry 里，Agent 优化有自然的递进，从 prompting 到 context 到 tools 到 fine-tuning：

<div align="center"><img src="images/slide-optimization-stack.png" width="960"></div>

> 来源：BRK232 Slide 5 — "Faster, Better, Cheaper" 优化栈。从下到上：Prompting → Context Management（data, grounding, memory）→ Tools Handling（calling instructions, naming, routing）→ **Model Fine-tuning**（RL, SFT）。Agent runtime（plan/act/observe）在最上层，Evaluate & Optimize 作为反馈环。

Fine-tuning 是你的 Agent **功能上已经对了**，但经济上跑不下去或速度不够时才用的优化手段。

> “We've been working on fine-tuning for a while, and I feel like people are finally starting to listen. About half of developers say that they want to replace their out-of-the-box models with fine-tuning.”
> — Alicia Frame ([BRK231](https://build.microsoft.com/en-US/sessions/BRK231))

---

## 三层训练体系

Build 2026 展示了 Foundry 里三个不同的模型定制入口——从"我就想点个按钮"到"把原始梯度 API 给我"：

<div align="center"><img src="images/slide-three-entry-points.png" width="960"></div>

> 来源：BRK232 Slide 20 — "Three entry points. Same Foundry."。High-Level API（托管 fine-tuning，一键 SFT/RFT）、Low-Level API（`create_session` / `sample` / `train`）、Full Control（带自己的框架，Ray/DeepSpeed/自定义）。

从简单 distillation 到完全算法控制，有清晰的成本-质量-投入曲线：

<div align="center"><img src="images/slide-pre-mid-post-training.png" width="960"></div>

> 来源：BRK232 Slide 16 — "Pre. Mid. Post."。Pre-training（$$$$$，数月）创建 base model。Mid-training（$$$，数周）添加领域能力。Post-training（$，数小时）通过 SFT/DPO/RLHF/RFT 对齐输出到 instructions 和 preferences。

| 层级 | 投入 | 控制力 | 适合谁 | 核心 API |
|:----|:----:|:-----:|:------|:---------|
| **1. Managed SFT** | 低 | 低 | 任何开发者 | Foundry UI 或 SDK |
| **2. RFT** | 中 | 中 | ML 工程师 | Foundry SDK + 自定义 grader |
| **3. Low-Level API** | 高 | 完全 | AI 科学家 | `client.sample()` + `client.train()` |

> SFT: "Don't reward what wins. **Teach what to do.**"
> RFT: "Don't teach what to do. **Reward what wins.**"
> — BRK232 Slides, Chris Lauren

### 训练执行模型：GPU 谁来管？

三种训练*方法*（SFT、RFT、Low-Level API）和三种*执行模式*是独立的。例如 RFT 可以通过托管路径跑，也可以通过 Code-First 路径跑：

| 执行模式 | GPU 算力来源 | 用户需要自己管集群？ | 现场证据 |
|:---------|:---------|:---------:|:---------|
| **托管 Fine-Tuning**（Layer 1–2） | Foundry 管理 | 否 | "fire and forget" — BRK232 transcript |
| **Code-First / Ray / SLIME**（Layer 2 进阶） | 用户自己的 Azure GPU quota（4× ND96 H100） | 是——集群、Ray、网络都要自己管 | "expert heavy-duty work" — BRK232 transcript |
| **Low-Level Training API**（Layer 3） | Foundry 管理 | 否——"no cluster, no nothing" | "the server manages all the infra" — BRK232 transcript |

BRK232 现场明确区分了后两种执行模型。Code-First 路径需要用户 provision 集群、管理 Ray、调试网络拓扑，讲者称之为 "expert heavy-duty work"。Low-Level Training API 则强调：*"前一个方案你得有 GPU。但并不是每个人都有 GPU，每个人都有笔记本就够了。"*

> **证据边界**：公开的 Build transcript 证明 Foundry 管理 Low-Level Training API 路径的 GPU 集群，但没有披露底层的具体算力源或 quota 模型。

下面这张 slide 展示了当托管流水线不够用时，四个维度的额外控制力——自定义 reward、自定义 rollout 环境、自定义数据清洗、完整超参控制：

<div align="center"><img src="images/slide-custom-control-options.png" width="960"></div>

> 来源：BRK232 Slide 23 — "What if you need more control?" 四个维度：custom rewards（你的 judges、rubrics、业务规则）、custom rollout environments（模拟器、tool servers、多轮世界）、custom data curation（你的 filters、splits、labeling）、full hyperparameter control（reasoning effort、compute multiplier、batch size、learning rate）。

> **缩写说明**：SFT = Supervised Fine-Tuning。RFT = Reinforcement Fine-Tuning。GRPO = Group Relative Policy Optimization。SLIME = Scalable Language Model Inference and Multi-Environment training。SGLang = 高吞吐 serving/inference 引擎。TRL = Transformer Reinforcement Learning（Hugging Face 库）。

下文用同一个零售退货场景（客服 Agent 处理退款）把每一层走一遍——这是 BRK231 和 BRK232 两个 session 的共同 demo 场景。

---

## Layer 1: Distillation + SFT — 模仿学习

### 原理

用大模型（"老师"，如 GPT-5.4）的生产 traces 来训练小模型（"学生"）：

```
生产 Agent（GPT-5.4）
         │
         ▼
    采集 Traces
    （1,000+ 次含工具调用的对话）
         │
         ▼
    Foundry 自动清洗：
    • 去重
    • 过滤无意义对话  
    • 脱敏 PII
         │
         ▼
    Supervised Fine-Tuning
    （学生：GPT-4.1 mini 或 nano）
         │
         ▼
    部署 fine-tuned 模型
    （同等质量，成本降一个数量级）
```

### Trace → Dataset → Training 一体化

现场 demo 展示了完整的 SFT → RFT 提交流程——数据集配置、算力选择、任务链接，全在一个 VS Code notebook 里：

<div align="center"><img src="images/brk232-sft-rft-code.png" width="960"></div>

> 来源：BRK232 现场 demo — SFT job 提交（上方）通过 `wait_for_sft_lora()` 链接到 RFT job 提交（下方）。[观看 session](https://build.microsoft.com/en-US/sessions/BRK232)

Foundry 的独到之处在于全链路打通：

1. **Hosted Agents 自动采集 traces** — 每次工具调用、每个响应、完整 trajectory 全部记录
2. **"Create Dataset" 按钮**把原始 traces 转成训练数据集 — Foundry UI 显示三种用途选择（Evaluation / SFT / RFT），支持按日期和样本数筛选：

<div align="center"><img src="images/brk231-create-dataset-ui.png" width="960"></div>

> 来源：BRK231 现场 demo — Foundry Portal “Create dataset” 弹窗，在 Agent Traces 页面上。234 条 traces（时间窗口 2026-05-26 – 2026-06-02）。数据集用途：Evaluation、Supervised fine-tuning、Reinforcement fine-tuning 三选一。[观看 session](https://build.microsoft.com/en-US/sessions/BRK231)

3. **一键 SFT** — 选模型、选 tier、开始训练

### 训练 Tier 和成本

| Tier | 成本 | 速度 | 数据驻留 | 场景 |
|:-----|:----|:-----|:--------|:-----|
| **Developer Preview** | **半价**（Spot VMs） | 稍慢 | — | 实验 |
| **Standard** | 全价 | 快 | — | 生产 |
| **Data Zone** | 全价 | 快 | US 驻留保证 | 合规行业 |

> "平台上 SFT 的中位数成本大概 1 美元。不贵。"
> — Alicia Frame ([BRK231](https://build.microsoft.com/en-US/sessions/BRK231))

### SFT 的天花板

Distillation 永远超不过老师。老师模型 74%，蒸馏出来的学生最多逼近但不会超过 74%。要突破天花板，就需要 Layer 2。

BRK232 的 slide 用零售 demo 场景——Mark 的 polo 衫退货——说明了 SFT 机制。一张票，一个专家答案，模型逐 token 模仿：

<div align="center"><img src="images/slide-sft-mechanism.png" width="960"></div>

> 来源：BRK232 Slide 18 — "Don't reward what wins. Teach what to do." 专家 trace 按顺序调 4 个工具（`check_order_status` → `check_return_window` → `process_refund` → `submit_response`）。模型的 32 个 token 逐个和 gold answer 对比。Token #7：专家说 "full"，模型说 "partial"——loss 3.10（32 个中最高）。平均 loss 0.42。权重被推向专家答案。

---

## Layer 2: Reinforcement Fine-Tuning (RFT) — 从错误中学习

RFT 的数据模型和 SFT 根本不同。官方 BRK232 slide 展示了完整的数据-行为矩阵——任何数据源都能驱动任何行为：

<div align="center"><img src="images/slide-data-behavior-matrix.png" width="960"></div>

> 来源：BRK232 Slide 17 — "Pick the data. Pick the behaviors."。左：数据源（traces、合成数据、人工标注、模型 rollouts、工具输出、reward 信号）。右：目标行为（instruction following、tool calling、reasoning chains、style/format、safety alignment、domain expertise）。任意组合均有效。

### 核心区别

SFT 是抄老师的答案。RFT 是**从自己的错误中学习**。BRK232 的 slide 让这个区别一目了然——同一张票（Mark 的 polo 退货），完全不同的学习机制：

<div align="center"><img src="images/slide-rft-mechanism.png" width="960"></div>

> 来源：BRK232 Slide 19 — "Don't teach what to do. Reward what wins." 同一张票，Agent 尝试 32 种方式。Try #21 得分 0.87（赢家）：6 次工具调用，8 维 rubric 检查（tools called +15, right action +20, right item +10, clean format +5, tools used right +12, right amount +20, right reason +5, honesty +0）。Step 4 冗余（-3 分），step 6 过度宣称（-5 分）。模型向这个模式靠拢。

```
SFT:  老师说 "先调 tool A，再调 B，再调 C"
      → 学生背下来："A → B → C"
      → 永远超不过老师

RFT:  模型自己尝试调工具
      → Grader："这次 40 分"  
      → 模型："换个方式试"
      → Grader："这次 85 分"
      → 模型学到更好的策略
```

### Rollout-Grade-Reinforce 循环

每个 prompt，模型生成 **多个候选答案**（rollouts）。Grader 打分。训练过程强化得分高的模式，惩罚得分低的。

<div align="center"><img src="images/rft-rollout-loop.png" width="960"></div>

> 来源：流程基于 BRK231 逐字稿。具体例子用 BRK232 的 [`retail_grader_rft_tools_v3.py`](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry/blob/main/src/post-training-recipe/demo-artifacts/code/retail_grader_rft_tools_v3.py)。

现场 demo 中，**Foundry Rollout Browser** 实时显示了 20 轮 rollout 的 reward 上升趋势，还能下钻到每个 prompt 的逐样本打分和对话对比：

<div align="center"><img src="images/brk232-rollout-browser.png" width="960"></div>

> 来源：BRK232 现场 demo — Streamlit Rollout Browser 作为 Foundry job service 跑在 8501 端口。显示 reward 曲线、prompt 级明细和对话 trace viewer。

Foundry Portal 里的评估结果验证了训练模型的质量——`retail_quality` 在测试场景上打到 0.990：

<div align="center"><img src="images/brk232-evaluation-results.png" width="960"></div>

> 来源：BRK232 现场 demo — Foundry Evaluations 页面，显示 fine-tuned 模型的逐条 `retail_quality` 分数。50 个场景中 49 个 pass 在 0.990+。

用一个具体例子走一步训练。客户说：*"我要退这个瑜伽垫，申请退款。"* 模型生成 4 个 rollout，各尝试不同的工具调用策略：

| Rollout | 调用工具 | 决策 | 金额 | 分数 | 原因 |
|:--------|:---------|:-----|:----:|:----:|:-----|
| #1 | order → policy → payment | 退款 | $29.99 | **0.92** ✅ | 三个工具按顺序调完，金额正确 |
| #2 | order → payment（跳过了 policy！） | 退款 | $29.99 | 0.45 | 答案对但漏了政策检查 |
| #3 | order → policy | 拒绝 | — | 0.20 | 决策错——商品是可退的 |
| #4 | order → policy → payment | 退款 | $50.00 | 0.35 | 工具对但金额错 |

**GRPO**（Group Relative Policy Optimization）保留 Rollout #1，强化模式："三个工具按顺序调完，金额精确匹配"。Rollout #2–4 被惩罚——模型学到：跳过政策检查或退错金额 = 低分。

经过数百步训练，模型把这些模式内化了——还能处理老师模型从来没见过的边界情况。

### Grader 设计：成败关键

Grader 的质量**直接决定 RFT 能不能用**。BRK232 的 slide 明确说了——eval IS the product spec：

<div align="center"><img src="images/slide-eval-is-product-spec.png" width="960"></div>

> 来源：BRK232 Slide 9 — "In the improvement loop, the eval is the product spec."。Scenario Eval Contract 定义五个维度：场景测什么、evaluator 怎么量化、rubric 定义什么叫"好"、数据集里有什么场景、最低 pass 阈值。

BRK232 demo 用了一个 8 维加权 grader：

| 组件 | 权重 | 检查什么 |
|:----|:----:|:--------|
| Verb accuracy | 高 | 动作对不对（refund vs reject） |
| Item accuracy | 中 | 商品识别对不对 |
| Reason quality | 中 | 理由合不合理 |
| Format compliance | 20% | 输出格式下游能用吗 |
| Amount accuracy | 高 | 金额准不准 |
| Tool coverage | 中 | 该调的工具调了没 |
| Workflow integrity | 中 | 工具调用顺序合不合逻辑 |
| Overall integrity | 低 | 有没有 hallucination |

> 来源：[`retail_grader_rft_tools_v3.py`](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry/blob/main/src/post-training-recipe/demo-artifacts/code/retail_grader_rft_tools_v3.py)

> “The quality of your grader is basically going to determine whether this works or not. If there’s no signal, if your grader is just like ‘Everything is wrong’ or ‘Everything is right’, there’s nowhere to go.”
> — Alicia Frame ([BRK231](https://build.microsoft.com/en-US/sessions/BRK231))

### Reward Hacking：必须盯的坑

开发过程中发现的失败模式：模型学会了**完全不调工具**，因为调错工具会被扣分。监控信号：

| 指标 | 健康 | Reward Hacking |
|:----|:-----|:-------------|
| Tool calls/rollout | 稳定或增长 | 掉到 0 |
| Reasoning tokens | 逐步减少 | 乱跳或躺平 |
| KL divergence | 缓慢增长 | 突然飙升 |
| Reward | 稳步爬升 | 突然跳高后不动 |

### RFT 前提：任务必须可验证

RFT 需要**客观打分**——输出对不对必须能判断。适合的任务：
- ✅ 退款处理（金额对不对？操作对不对？）
- ✅ SQL 生成（查询结果对不对？）
- ✅ 代码生成（测试过不过？）
- ❌ 创意写作（没有客观标准）
- ❌ 开放式对话（没有 ground truth）

---

## Layer 3: Low-Level Training API — 完全掌控算法

BRK231 展示了两条训练路径的核心架构区别——**Path A（托管）**是闭环，Foundry 全自动跑；**Path B（交互式）**让你每一步都在环内：

<div align="center"><img src="images/brk231-managed-vs-interactive-training.png" width="960"></div>

> 来源：BRK231 Slide 19 — "Take a peek under the hood"。左：Path A（Azure OAI RFT / 托管 fine-tuning）— 闭环，提交配置后服务自动迭代到完成。右：Path B（Interactive RL / Training API）— 开环，你每步都 review、打分、修改。注意 Grader 位置：Path A 在服务内；Path B **在你这边**。

### "PyTorch as a Service"

Low-Level Training API 的架构在现场揭开——**"一个小 Python 循环，一个大 GPU 集群，三次 API 调用连起来"**：

<div align="center"><img src="images/brk232-low-level-api-architecture.png" width="960"></div>

> 来源：BRK232 现场 slide — 你本地的 `training_loop.py` 通过 3 个 API 调用（`client.sample()`、`client.forward_backward()`、`client.sync_weights()`）驱动托管 GPU 集群上的 Sampler + Trainer + Adapter Store。

Foundry Portal 实时显示训练 session——checkpoint 创建、权重同步事件、gradient norm 和 job 完成状态：

<div align="center"><img src="images/brk232-training-job-logs.png" width="960"></div>

> 来源：BRK232 现场 demo — `qwen3-32b.ft-model` 的 fine-tune session 日志，显示 `optim_step`、`forward_backward`、`sync_weight` 和 checkpoint 创建事件。

给需要完全控制的 AI 科学家——你控制算法，Foundry 管 GPU：

| 你控制的 | Foundry 管的 |
|:--------|:-----------|
| Rollout 策略 | GPU 集群分配 |
| Grader 逻辑（任何语言） | 分布式训练编排 |
| Loss 计算 | 模型权重在节点间同步 |
| Curriculum scheduling | vLLM/SGLang 配置 |
| 算法（GRPO, PPO, DPO, 自定义） | Checkpoint 存储 |
| 超参数 | 训练节点和采样节点之间的网络 |

### 三个核心 Primitive

```python
# 1. 在 GPU 集群上创建 LoRA adapter
session = client.create_session(model="Qwen/Qwen3-32B", cluster="h100-4node")

# 2. Multi-turn rollouts — 模型在 sampling 过程中调用真实工具
rollouts = client.sample(prompts=batch, num_samples=10, tools=tool_defs)

# 3. 梯度更新 — 服务端执行，你不需要下载完整模型权重
client.train(rollouts=rollouts, rewards=grader.score(rollouts), algorithm="grpo")
```

训练循环跑在**你的笔记本上**（或 Azure VM）。GPU 计算通过 `sample()` 和 `train()` 在 Azure 执行。架构有两个节点：training node（前向/反向传播）和 sampling node（rollout 生成）。`sync()` 在两者之间同步 LoRA 权重。

现场 demo 从本地终端启动训练 session，`./launcher.sh` 显示完整超参配置（lr=5e-5, group_size=16, lora_rank=32, max_iters=25）：

<div align="center"><img src="images/brk231-local-launcher-terminal.png" width="960"></div>

> 来源：BRK231 现场 demo — 本地终端跑 `./launcher.sh`，启动 `retail_rl-Qwen-Qwen3-32B` 训练。配置显示 `lr=5e-5`、`group_size=16`、`groups_per_batch=32`、`max_tokens=768`、`lora_rank=32`、`max_iters=25`、`loss_fn=importance_sampling`、`eval_every=2`、`seed=42`。通过 `AZURE_AI_API_KEY` 连接到 Foundry 项目 endpoint。

### BRK232 Demo 结果

| 模型 | retail_quality | 相比 base | 成本 |
|:----|:-------------:|:---------:|:----:|
| Qwen3-32B base | 58.1% | — | $ |
| o4-mini RFT | 82.3% | — | $$ |
| **Qwen3-32B Low-Level RFT** | **86.9%** | **+28.8pp** | **$** |

> 来源：[BRK232 Official Repo](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry)

本地 Run Dashboard（BRK232 `dashboard.py` Streamlit 应用）实时展示了完整训练遥测——reward/correct 曲线、gradient norm + entropy、KL divergence、"Group Composition" 堆叠图（显示 "all-good" rollouts 如何逐步压倒 "all-bad"）：

<div align="center"><img src="images/brk231-training-dashboard.png" width="960"></div>

> 来源：BRK231 现场 demo — Low-Level Training API Run Dashboard（`127.0.0.1:8000`）。左上：train/eval reward+correct。右上：gradient norm + entropy + learning rate。左下：KL divergence (v1/v2)。右下：Group Composition，显示 all-bad（红）→ mixed（橙）→ all-good（绿）的转变过程（26 步）。

### Low-Level API 能做但 Managed RFT 做不了的事

- **Curriculum learning**：从简单 prompt 开始，逐步加难度
- **自定义算法**：不限于 GRPO，PPO、DPO、或全新方法都行
- **训练中途改策略**：改 grader、改 sampling、改超参，随时调
- **任意语言写 grader**：C#、Python、外部 API 都行
- **真实环境交互**：rollout 对接真实工具，不只是模拟
- **完整遥测**：KL divergence、entropy、gradient norm、group composition 全部本地可见

---

## 经济账：数字走一遍

零售退货场景，美国在线退货市场 $900B，假设每天 100 万请求：

### 单请求成本

| 模型 | Tokens/请求 | 单价/M tokens | 单请求成本 | 年成本（1M 请求/天） |
|:----|:-----------:|:------------:|:---------:|:------------------:|
| GPT-5.4 | 12,000 | $15.00 | $0.180 | **$65.7M** |
| o4-mini | 12,000 | $2.50 | $0.030 | $10.9M |
| GPT-4.1 mini SFT | 8,000 | $0.50 | $0.004 | **$1.5M** |
| Qwen3-32B RFT | 6,000 | $0.50 | $0.003 | **$1.1M** |

Fine-tuned 模型消耗更少 token（指令 bake 进权重，不需要长 prompt）+ 每 token 更便宜。复合效应：

**GPT-5.4 → Qwen3-32B RFT：约 60 倍成本降低，质量还高 22 个百分点。**

### 训练成本

| 项目 | 成本 |
|:----|:-----|
| SFT 中位数 | ~$1（Developer tier：$0.50） |
| RFT（4 节点 H100，100 rollouts） | ~$50–200 |
| Low-Level API session（Qwen3-32B，4×H100） | ~$200–500 |
| Developer tier hosting（实验用） | **$0**（无托管费） |

> 来源：SFT 中位数成本来自 Alicia Frame 在 [BRK231](https://build.microsoft.com/en-US/sessions/BRK231) 的引述。RFT 和 Low-Level API 估算基于现场 demo 成本分析（整个 demo 跑完共计 ~$419）。

---

## Leaderboard：质量递进

Session 数据显示质量在 post-training 循环的**每个阶段**都在提升：

<div align="center"><img src="images/slide-hill-climbing-quality.png" width="960"></div>

> 来源：BRK232 Slide 14 — 这张图跟踪的是 **Qwen3-14B** 的 post-training 各阶段。下方 leaderboard 表格跟踪的是**全模型组合**（含 GPT-5.4、o4-mini、GPT-4.1 mini 和 Qwen3-32B）在同一个 `retail_quality` 指标上的表现。绝对值不同是因为 14B 和 32B 使用了不同的模型大小和 evaluation checkpoints。

Demo 在同一个零售退货任务上跟踪了所有 fine-tuning 迭代的质量：

| 阶段 | 模型 | retail_quality | 成本/M tokens | 说明 |
|:----|:----|:-------------:|:------------:|:-----|
| Baseline | GPT-5.4 | 65% | $15.00 | 老师模型 |
| Baseline | o4-mini | 65% | $2.50 | 更小但质量一样 |
| Baseline | GPT-4.1 mini | ~40% | $0.50 | 不 fine-tune 不能用 |
| Baseline | GPT-4.1 nano | ~35% | $0.10 | 不 fine-tune 不能用 |
| **Layer 1** | GPT-4.1 mini SFT | **74%** | $0.50 | 从 GPT-5.4 traces 蒸馏 |
| **Layer 2** | o4-mini RFT | **84%** | $1.00 | 超越老师 |
| **Layer 3** | Qwen3-32B RFT | **86.9%** | ~$0.50 | 开源模型，完全控制 |

关键发现：**最终赢家是开源模型（Qwen3-32B）+ 最大投入（Low-Level API）= 最低成本 + 最高质量。**

### 现场 Demo 到底花了多少钱

Azure Cost Analysis 显示了整个 BRK232 demo session 的 Managed Compute 总成本——**~$419**，分布在 H100 和 A100 加速器上：

<div align="center"><img src="images/brk232-cost-analysis.png" width="960"></div>

> 来源：BRK232 现场 demo — Azure Portal Cost Analysis，按 `deployment:qwen--qwen3-32b-2...` 筛选，时间范围 2026-05-05 – 06-03。明细：Foundry Models / Mngd H100_80GB GI = **$256.28**，Foundry Models / Mngd A100_80GB GI = **$163.13**。覆盖了 demo 期间的训练算力和推理 serving。

---

## 客户生产部署案例

| 客户 | 技术 | 结果 | 来源 |
|:----|:-----|:-----|:-----|
| **Decagon AI** | Distillation + SFT | 客服 Agent 切到更小更快的模型 | BRK231 |
| **Discovery Bank** | Distillation + SFT | 银行 App 延迟：**6s → 1.5s** | BRK231 |
| **DocuSign** | Distillation | AI 文档处理成本**降 50%** | BRK231 |
| **Harvey** | Fine-tuning | 法律 AI Agent，领域 tool calling | BRK231 |
| **UiPath** | Fine-tuning | 自动化 Agent，企业工作流 | BRK231 |

---

## 用 Coding Agent 做 Fine-Tuning

BRK231 演示了 GitHub Copilot 的 fine-tuning skill，用自然语言完成整个流程：

```
用户："我有一个 hosted agent 在 <endpoint>。
       用 tool-calling 准确率做评估，给部分分。
       然后蒸馏成更便宜更快的模型。"

Copilot Fine-Tuning Skill：
  ① 创建自定义 grader（tool call 给部分分）
  ② 评估老师模型 → 78% pass rate  
  ③ 评估 base 小模型 → 表现差
  ④ 启动蒸馏 fine-tuning（自动选模型 + 超参）
  ⑤ 返回 leaderboard：fine-tuned 4.1 mini 达到老师水平
  ⑥ 如果结果变差 → 自动迭代（更多数据、不同实验）
```

可用方式：**GitHub Copilot for Azure** 内置 skill，或独立下载 fine-tuning skill。

---

## 选型指南：什么时候用什么

| 场景 | 建议 | 原因 |
|:----|:-----|:-----|
| Agent 能用但太贵 | **Layer 1: SFT** | 蒸馏 frontier traces 到便宜模型。中位数 ~$1 |
| 老师模型质量不够 | **Layer 2: RFT** | 模型从自己的错误中学，能超越老师 |
| 需要自定义 RL 算法或 curriculum | **Layer 3: Low-Level API** | 完全控制训练循环，Foundry 管 GPU |
| 还没有生产 traces | **先攒 traces** | 用 frontier 模型部署，攒 1,000+ trajectories |
| 任务不可打分 | **Prompt engineering + Agent Optimizer** | RFT 需要可验证的结果 |
| 之前试过 fine-tuning 把模型搞坏了 | **用 fine-tuning coding agent** | 自动选超参，自动迭代 |

---

## 从训练到部署

模型训练完成（无论用哪一层），BRK232 展示了完整的上线路径：

**Step 1: 注册训练好的模型** — 上传权重、从训练 job 注册、或从 Hugging Face 导入：

<div align="center"><img src="images/brk232-model-registry.png" width="960"></div>

> 来源：BRK232 现场 demo — Foundry Models 页面，显示三个已注册的自定义模型：`finetuned-byow-model`（Qwen3-14B）、`custom-qwen3-32B`、`qwen14b-RFT`。

**Step 2: 选择部署路径** — 官方 slide 展示了完整图景——BYOW vs BYOC，两者汇聚到同一个 Foundry endpoint：

<div align="center"><img src="images/slide-train-deploy-scale.png" width="960"></div>

> 来源：BRK232 Slide 22 — "Train custom models anywhere, deploy and scale in Foundry."。BYOW 路径：catalog runtime → Managed Compute / Fireworks。BYOC 路径：自定义镜像 → 自有集群。两者共享同一个 inference endpoint、auth、SDK、evals、agents 和 observability。

下面这张 BRK232 slide 展示了自定义模型在 Managed Compute 上的完整生命周期——模型从哪来（上传 / 训练 job / Hugging Face），支持什么格式（full weights / LoRA），产物类型（BYOW vs BYOC），以及跑在哪（Managed Compute / Fireworks PTU）：

<div align="center"><img src="images/slide-custom-models-managed-compute.png" width="960"></div>

> 来源：BRK232 Slide 33 — "Custom models on Managed Compute: What you bring, what it becomes, where it runs."。四列：(1) Custom models — 从你的环境上传、从训练 job 注册、或从 Hugging Face 导入。(2) Formats — full weights 或 LoRA adapters。(3) Assets — BYOW（Foundry 选 runtime）或 BYOC（你的 serving 镜像，权重挂载）。(4) Compute — Managed Compute（Foundry 管理的 GPU 或你自己的训练集群）或 Fireworks（PTU）。

BRK232 现场 transcript 描述了 custom containers 作为自定义模型部署故事的一部分：*"You can bring custom models with custom containers that have highly optimized runtimes using things like speculative decoding or draft models."* — Chris Lauren, BRK232。具体支持的 runtime 和 compute 组合请以[产品文档](https://learn.microsoft.com/azure/ai-foundry/)为准。

Foundry 还提供 **Managed Compute** 作为开源模型的专用 serving 底座——现已 Public Preview：

<div align="center"><img src="images/slide-managed-compute-preview.png" width="960"></div>

> 来源：BRK232 Slide 21 — "Managed Compute in Microsoft Foundry — Public Preview."。Broad model choice（fine-tuned、开源、自定义），Flexible compute（A100/H100/MI300X），Optimized runtimes（vLLM），统一 endpoint/auth/SDK/evals/agents/observability。

Foundry Model Catalog 支持 45+ 个模型通过 Managed Compute 部署——demo 搜索 "32b" 找到对应的 Qwen3 变体：

<div align="center"><img src="images/brk232-model-catalog-search.png" width="960"></div>

> 来源：BRK232 现场 demo — Foundry Model Catalog 按 "Deployment options: Managed Compute" 筛选，显示 45 个模型。左侧 filter：Availability、Collections、Source、Inference Tasks、Deployment Options（Managed Compute: 45、Serverless API: 125）、Fine-tuning Methods、Domain、Industry。

Deploy 弹窗指定部署类型（"Global Managed Compute"）、部署模板（"qwen--qwen3-32b--40k-nvidia-h100"），确认硬件：**"vLLM on 1 × NVIDIA H100 80 GB at 40K context length"**：

<div align="center"><img src="images/brk232-deploy-managed-compute-dialog.png" width="960"></div>

> 来源：BRK232 现场 demo — `qwen--qwen3-32b` 部署弹窗。Deployment type: Global Managed Compute。Template: `qwen--qwen3-32b--40k-nvidia-h100`。Task: Chat Completions and Responses APIs。Max sequence length: 40,960 tokens。支持 Thinking modes。

**Step 3: 部署到 Foundry endpoint** — 和任何 Foundry 模型一样的 auth、SDK、evals 和 observability：

<div align="center"><img src="images/brk232-managed-compute-playground.png" width="960"></div>

> 来源：BRK232 现场 demo — 已部署的 fine-tuned 模型的 Foundry Playground，显示 project endpoint、API key 和 OpenAI SDK Python 代码片段。

**Step 4: 接入 Agent** — Fine-tuned 模型驱动一个带 tools、knowledge、memory 和 guardrails 的 Foundry hosted agent：

<div align="center"><img src="images/brk232-agent-integration.png" width="960"></div>

> 来源：BRK232 现场 demo — Foundry Agent 页面 `build-demo`，使用 fine-tuned BYOW 模型作为 backbone，配置了 Web Search tool、Knowledge、Memory 和 Guardrails。

---

## 上手指南

### 快速开始（Layer 1 — Foundry UI 5 分钟）

1. 用 frontier 模型部署一个 Hosted Agent
2. 正常使用，攒 1,000+ traces
3. 点 **Create Dataset** → **Start Fine-Tuning**
4. 对比 fine-tuned 模型和 baseline 的评估结果
5. 质量达标就部署

### 完整流水线（Clone 微软官方 BRK232 repo）

```bash
git clone https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry.git
cd Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry
pip install --pre -r src/requirements.txt
```

| 阶段 | Notebook | 模型 | 技术 |
|:----|:---------|:----|:-----|
| 1 | `src/post-training-sft-recipe/retail_sft_submit.ipynb` | Qwen3-32B | SFT（SLIME + Ray + TRL） |
| 2 | `src/Retail_Customer_Agent_Post_Training.ipynb` | Qwen3-14B | GRPO RFT（从 Stage 1 LoRA warm-start） |
| 3 | `src/Retail_Customer_Agent_Training_API.ipynb` | Qwen3-32B | Low-Level API（Private Preview） |

> ⚠️ **Stage 1–2 需要 GPU 集群**：4 节点 H100 或 A100（你自己的 Azure GPU quota）。先小规模验证。
>
> ⚠️ **Stage 3（Low-Level API）**：不需要自备 GPU quota——Foundry 管理 GPU 集群。需要 [Private Preview 权限](https://aka.ms/FoundryTrainingPrPrSignup)。

---

## 关键资源

### Session 录像
| Session | 标题 | Speaker |
|:--------|:-----|:--------|
| [BRK231](https://build.microsoft.com/en-US/sessions/BRK231) | Deploy. Observe. Learn. RL for production agents | Alicia Frame, Omkar More |
| [BRK232](https://build.microsoft.com/en-US/sessions/BRK232) | Post-Training OSS Reasoning Models in Foundry | Chris Lauren, Vijay Aski, Manoj Bableshwar |
| [BRK230](https://build.microsoft.com/en-US/sessions/BRK230) | Build smarter AI systems as models and costs evolve | Yina Arenas, Naomi Moneypenny |

### 代码和文档
| 资源 | 链接 |
|:----|:-----|
| BRK232 官方代码 Repo | [github.com/microsoft/Build26-BRK232-...](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry) |
| BRK231 官方 Repo | [github.com/microsoft/Build26-BRK231](https://github.com/microsoft/Build26-BRK231) |
| Foundry Fine-Tuning 概念 | [learn.microsoft.com](https://learn.microsoft.com/azure/ai-foundry/concepts/fine-tuning-overview) |
| SLIME 框架 | [github.com/THUDM/slime](https://github.com/THUDM/slime) |
| Low-Level API Preview 注册 | [aka.ms/FoundryTrainingPrPrSignup](https://aka.ms/FoundryTrainingPrPrSignup) |
| Foundry Discord（50K+） | [aka.ms/foundry/discord](https://aka.ms/foundry/discord) |
| Training Notebooks | [aka.ms/TrainingBuild2026](https://aka.ms/TrainingBuild2026) |

### 技术栈
| 组件 | 角色 |
|:----|:-----|
| [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/) | 训练、评估、部署的控制平面 |
| [SLIME](https://github.com/THUDM/slime) + [Ray](https://www.ray.io/) | Async GRPO 训练框架 |
| [SGLang](https://github.com/sgl-project/sglang) | 高吞吐 rollout 引擎 |
| [TRL (HuggingFace)](https://huggingface.co/docs/trl) | 带 prompt masking 的 SFT |
| [Qwen3-14B / Qwen3-32B](https://huggingface.co/Qwen) | 开源推理 base model |
| [Streamlit](https://streamlit.io/) | 训练实时 dashboard |

---

## Running on Azure

| 组件 | Azure 服务 | SKU / Tier |
|:----|:---------|:----------|
| 训练控制平面 | Microsoft Foundry | Standard |
| SFT 算力 | Foundry Custom Code training（BYO AML GPU quota） | 4× ND96amsr_A100_v4 或 ND96r_H100_v5 |
| RFT 算力 | Foundry Custom Code training（BYO AML GPU quota） | 4× ND96r_H100_v5（推荐） |
| Low-Level API 算力 | Foundry Fine-Tuning Low-Level API（Foundry 管理的 GPU） | H100 集群（Private Preview） |
| 模型托管 | Foundry Managed Compute | Dedicated GPU（按小时计费） |
| 评估 | Foundry Evaluations | 包含 |
| Traces 和可观测性 | Foundry Tracing + Azure Monitor | 包含 |
| Agent 运行时 | Foundry Hosted Agents | GA（2026 年 7 月） |

> 来源：[BRK232 Official Repo — Prerequisites](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry#prerequisites)

---

## 关联 Repo

| Repo | 关系 |
|:----|:----|
| [4-Steps-of-AOAI-E2E-Fine-Tuning](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice) | 基础：Azure OpenAI 上的 E2E fine-tuning（SFT 基本功）。本文扩展到 **Agent 场景的 RL post-training** |
| [AI-Foundry-Model-Performance](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/AI-Foundry-Model-Performance) | 互补：模型 Benchmark，为"选哪个模型做 fine-tune"提供决策依据 |
| [BF16-FP16-RL](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/BF16-FP16-RL) | 背景：RL 训练中的精度格式，与 GRPO GPU 效率相关 |
| [Budget-Forcing-Inference](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Budget-Forcing-Inference) | 相关：推理时的 token 预算控制——fine-tuning 之后的下一步优化 |

---

## 核心技术深潜

BRK232 demo 依赖多个关键技术。这里逐个拆解每个技术做什么、为什么对 post-training 流水线重要。

### SLIME 框架

[SLIME](https://github.com/THUDM/slime)（Scalable Language Model Inference and Multi-Environment training）是 BRK232 repo 中 SFT 和 RFT recipe 共用的开源框架。底层用 [Ray](https://www.ray.io/) 做分布式训练，用 [SGLang](https://github.com/sgl-project/sglang) 做高吞吐 rollout 引擎。

为什么 SLIME 对这个 demo 重要：
- **多轮 tool-use rollouts**：普通 RL 框架一个 prompt 只生成一个回复，SLIME 支持多轮 agent trajectory——模型调工具、拿结果、推理、再调工具
- **异步 GRPO**：rollout 引擎和训练引擎异步运行——第 N 批在训练的同时，第 N+1 批已经在采样 rollout
- **Ray 原生**：从 1 个节点到 N 个节点不需要改代码。demo 用了 4 个 H100/A100 节点

### GRPO — Group Relative Policy Optimization

GRPO 是 Layer 2（managed RFT）和 Layer 3（Low-Level API）共用的 RL 算法。和 PPO 的核心区别：

| 维度 | PPO | GRPO |
|:-----|:----|:-----|
| **基线** | 独立的 value network（critic） | 采样 reward 的 group mean |
| **显存** | 必须同时训练 critic | 不需要 critic——节省 ~50% GPU 显存 |
| **信号** | Advantage = reward - value 估计 | Advantage = reward - group mean |
| **稳定性** | Clip ratio + KL penalty | Clip ratio + KL penalty |

实操：对每个 prompt，GRPO 生成 `group_size` 个 rollout（demo 默认 16 个），全部打分，用 group mean 作为基线。高于均值的 rollout 被强化；低于均值的被惩罚。不需要 critic network。

### Ray 分布式训练架构

BRK232 训练用 Ray 把工作分布到 4 个 GPU 节点：

```
┌─────────────────────────────────────────┐
│  Ray Head Node                            │
│  ┌────────────┐  ┌────────────────────┐ │
│  │  Trainer    │  │  SGLang Sampler     │ │
│  │  (forward/  │  │  (rollout           │ │
│  │  backward)  │  │   generation)       │ │
│  └────────────┘  └────────────────────┘ │
│       │                     │              │
│       └─────── sync() ─────┘              │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Ray Worker Nodes (3x)                    │
│  Each: 8x H100 80GB or 8x A100 80GB      │
│  Role: tensor-parallel inference shards   │
└─────────────────────────────────────────┘
```

demo 的 `submit_job.py` 关键配置：`distributionType: Ray`，head node 端口 `6379`，实例类型 `Singularity.ND96r_H100_v5`（4 节点）。

### Managed Compute — 推理引擎和加速器

训练好的模型部署到生产时，Foundry Managed Compute 支持：

| 推理引擎 | 场景 | 来源 |
|:---------|:-----|:-----|
| **vLLM** | BRK232 部署 demo 使用的 runtime（"vLLM on 1× NVIDIA H100 80 GB"） | BRK232 Slide 21 + 部署弹窗 |
| **SGLang / NVIDIA NIM** | 官方 slide 提到的 open-model optimized runtimes；BRK232 demo 中 runtime 通过 deployment template 暴露，而不是单独的 engine picker | BRK232 Slide 21 + 部署弹窗 |

| 加速器 | Managed Compute SKU | 典型场景 |
|:-------|:-------------------|:---------|
| **NVIDIA H100 80GB** | `H100_80GB` | Qwen3-32B+ 和高吞吐推理的默认选择 |
| **NVIDIA A100 80GB** | `A100_80GB` | 较小模型（Qwen3-14B）的高性价比选择 |
| **AMD MI300X 192GB** | `MI_300_192GB` | 超长上下文或超大模型（rolling out） |

> 来源：BRK232 Slide 21（Managed Compute 发布）、BRK232 部署弹窗、Azure Cost Analysis 中 H100 和 A100 的费用明细。

### 零售 Demo 环境

BRK232 demo 使用**确定性零售退货环境**，包含 4 个 tools 和 8 维 grader。环境代码完整收录在[官方 repo](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry/tree/main/src/post-training-recipe/demo-artifacts/code) 中：

| 组件 | 文件 | 功能 |
|:----|:-----|:-----|
| 环境 | `retail_env.py` | 分发确定性工具调用，跟踪 episode 状态 |
| 工具 | `retail_tools.py` | `get_order_details`、`check_resolution_policy`、`process_refund`、`lookup_product` |
| 评分器 | `retail_grader_rft_tools_v3.py` | 8 维加权打分：verb、item、reason、format、amount、tool coverage、workflow、integrity |
| Reward | `retail_reward.py` | 调用 grader，为 GRPO 生成标量 reward 信号 |
| 训练入口 | `retail_slime_train.py` | SLIME 入口——在 Foundry 容器内启动 Ray + GRPO |
| Dashboard | `dashboard.py` | 训练期间的 Streamlit rollout browser，端口 8501 |

工具是**确定性的**——相同输入永远产出相同输出。这对 RL 至关重要：reward 信号必须稳定，不能因为 tool 的随机性引入噪声。

---

## 官方 Repo 全景

[BRK232 官方 repo](https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry) 包含 session 中展示的全部源码。目录结构：

```
src/
├── post-training-sft-recipe/          # Stage 1: SFT
│   ├── retail_sft_submit.ipynb           # 入口 notebook
│   ├── slime_sft_setup.py               # setup_env, submit_job, tail_rollouts
│   ├── recipe/
│   │   └── submit_sft.py                  # 发送到 Foundry 的 Job payload
│   ├── demo-artifacts/
│   │   ├── code/sft_retail.py             # HF TRL SFT 脚本（容器内执行）
│   │   └── data/                          # retail_train_sft.jsonl + retail_val_sft.jsonl
│   └── reports/extract_rollouts.py       # 检查 rollout 输出
├── post-training-recipe/              # Stage 2: RFT (GRPO)
│   ├── submit_job.py                    # 构建 CommandJob 并提交
│   ├── helpers.py                       # 数据集上传、GPU 布局、提交
│   └── demo-artifacts/
│       ├── code/
│       │   ├── retail_env.py              # 确定性零售环境
│       │   ├── retail_tools.py            # 4 个确定性工具
│       │   ├── retail_grader_rft_tools_v3.py  # 8 维加权评分器
│       │   ├── retail_reward.py           # GRPO 的 reward shaping
│       │   ├── retail_slime_train.py      # SLIME + Ray 入口
│       │   └── dashboard.py               # Streamlit rollout browser
│       └── data/                          # retail_train.jsonl + retail_val.jsonl
├── post-training-experimentation/      # 本地 grader 测试
│   ├── grader_demo.py                   # 快速 grader 测试
│   ├── debug_grader.py                  # 调试 grader 边界情况
│   └── grader_eval_helpers.py           # 评估工具函数
├── Retail_Customer_Agent_Post_Training.ipynb    # Stage 2 入口 notebook
├── Retail_Customer_Agent_Training_API.ipynb     # Stage 3 入口 notebook
├── Retail_Customer_Agent_Grader_Test_Bed.ipynb  # Grader 测试 notebook
├── slime_rl_setup.py                # setup_env, submit_job, job_status
└── requirements.txt                 # Python 依赖
```

### 如何复现

**前提条件**：
- 一个 [Microsoft Foundry](https://learn.microsoft.com/azure/ai-foundry/) 项目，已挂载 GPU 算力
- 4 个 NVIDIA H100（`ND96r_H100_v5`）或 A100（`ND96amsr_A100_v4`）节点
- User-assigned managed identity (UAI) + storage connection name
- Python 3.11+，Azure CLI 已登录
- Low-Level API（Stage 3）需要 [Private Preview 权限](https://aka.ms/FoundryTrainingPrPrSignup)

**操作步骤**：

```bash
# 1. Clone 并安装
git clone https://github.com/microsoft/Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry.git
cd Build26-BRK232-train-and-deploy-custom-oss-reasoning-models-with-foundry
pip install --pre -r src/requirements.txt \
  --extra-index-url https://pkgs.dev.azure.com/azure-sdk/public/_packaging/azure-sdk-for-python/pypi/simple
az login

# 2. Stage 1 — SFT (Qwen3-32B)
# 打开 src/post-training-sft-recipe/retail_sft_submit.ipynb
# 设置你的 project name，选择集群（h100 或 a100），提交

# 3. Stage 2 — RFT/GRPO (Qwen3-14B，从 Stage 1 LoRA warm-start)
# 打开 src/Retail_Customer_Agent_Post_Training.ipynb
# 设置 project_endpoint、storage_connection_name、managed_identity_*，提交

# 4. Stage 3 — Low-Level API (Qwen3-32B, Private Preview)
# 打开 src/Retail_Customer_Agent_Training_API.ipynb
# 设置 AZURE_AI_API_KEY + PROJECT_ENDPOINT，从头到尾跑 cells

# 5. 本地测试 grader（不需要 GPU）
python src/post-training-experimentation/grader_demo.py
```

> ⚠️ **必须覆盖所有默认值**：内置的值引用 demo 使用的内部 Foundry pilot 项目。提交前必须覆盖 `project_endpoint`、`managed_identity_*`、`storage_connection_name`、数据集 URI 和 `compute_cluster`。

---

## 跨 Session 分析：训练 vs 推理 vs Agent 运营

我们分析了 7 个 Build 2026 session，发现 BRK232 应该放在生命周期中理解，而不是孤立看待：

| 领域 | Sessions | 覆盖内容 |
|:----|:---------|:--------|
| **学习数据** | BRK231, BRK232 | Traces → 数据集 → evaluation/SFT/RFT 数据 |
| **训练** | BRK231, BRK232 | `CommandJob`、Train blade、SFT/RFT jobs、Low-Level Training API |
| **推理部署** | DEM320, BRK232 bridge, BRK230 | Managed Compute 部署、deployment templates、统一 endpoint/auth/SDK |
| **Agent 运营** | BRK241, BRK252, BRK230 | Hosted agents、traces、evals、optimizer、ROI |

核心架构洞察：

> **BRK232 创建或改进模型。Managed Compute 是 serve 开源/自定义模型到生产的一条产品路径。** 不要说"BRK232 就是 Managed Compute"——这会混淆训练和部署的边界。

生命周期是一个持续循环：

```
生产 agent traces
  → Foundry datasets / graders / evals
  → SFT / RFT / Low-Level Training API
  → 改进后的模型产物
  → 部署（Managed Compute / Fireworks / BYOC）
  → 推理 endpoint 被 agents 消费
  → Traces、evals、监控、optimizer
  → 下一轮训练数据集（循环回来）
```

> 来源：基于 BRK231、BRK232、DEM320、BRK230、BRK234、BRK241、BRK252 的 slides、逐字稿和 demo repo 的跨 session 分析。完整分析：[Build-2026-Keynote-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/Foundry-Agent-Post-Training-Deep-Dive/../../../Build-2026-Keynote-Deep-Dive)。

---

## 持续改进 Playbook

BRK232 最后展示了完整的生命周期——从模型选择到持续改进：

<div align="center"><img src="images/slide-continuously-improve.png" width="960"></div>

> 来源：BRK232 Slide 23 — "Continuously improve your AI."。五步 playbook：Pick model → Evaluate → Optimize with RL → Operate with control → Continuously improve。闭环永不停止——生产 traces 回流到下一轮训练循环。

---

*基于 BRK231 官方逐字稿、BRK232 官方代码 Repo、BRK232 官方 Slides、BRK230 session 内容和 Build 2026 材料。2026-06-03/08。*
