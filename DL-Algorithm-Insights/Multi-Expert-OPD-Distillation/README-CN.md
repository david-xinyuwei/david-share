# 多专家在线策略蒸馏：DeepSeek-V4 如何把 10+ 个领域专家融合成一个模型

*Author: 魏新宇 (Xinyu Wei)*

> 深入剖析 On-Policy Distillation (OPD) — DeepSeek-V4 用来把 10+ 个领域专家模型整合成单一统一模型的 post-training 方法，完全替代了传统的 mixed RL 阶段。

[English](README.md) | [配套阅读：Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) | [关联：LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)

## Executive Summary

| 方法 | 专家如何融合 | 失败模式 | DeepSeek-V4 用了？ |
|------|-------------|---------|:----------------:|
| **Weight Averaging**（权重平均） | 权重算术平均 | 能力相互干扰 → 质量退化 | ❌ |
| **Task Arithmetic**（TIES、DARE 等） | 任务向量加减 | 比平均好，但仍是参数空间启发式 | ❌ |
| **Mixed RL**（多任务 PPO/GRPO） | 跨任务联合 reward | reward hacking、训练不稳定 | ❌（V3.2 用过，V4 替换） |
| **On-Policy Distillation (OPD)** | 在 student trajectory 上做 logit 层对齐 | 训练慢，但稳定 + 保真 | ✅ **V4 的选择** |

> *"the mixed Reinforcement Learning (RL) stage was entirely replaced by On-Policy Distillation (OPD)."*
> — DeepSeek-V4 Technical Report, Section 5.1

DeepSeek 通过从 base 模型分支并跑领域 RL，训出了 10+ 个领域专家（数学、代码、写作、Agent、推理等）。然后他们面临每个多专家系统都会遇到的问题：**怎么把这些专家融合成一个生产模型，又不丢失各自的特长？**

本文解释 V4 为什么选 OPD 而不是其他方案，用一个具体例子走完整个方法，并展示 V4 是怎么解决工程层面的难题（10+ teacher 的 logits、词表 > 100k）。

---

## 背景：多专家融合问题

现代 LLM 需要在多个领域都能干活——数学、代码、写作、Agent 工具调用、多语言翻译。标准做法是：

1. **Pre-train** 一个 base 模型用多样化数据
2. **Specialize** 复制出多份，各自用 SFT + RL 训成领域专家
3. **Merge** 把这些专家融合成一个生产部署的模型

第 3 步最难。一旦你有了，比如说 10 个各自在自己领域比 base 强的专家，简单的合并方式要么把特长平均掉，要么导致训练不稳定。

### 为什么不能各专家分开部署？

生产部署强烈倾向单一模型：

- **成本**：一个模型 = 一套 GPU。十个模型 = 十倍推理成本。
- **延迟**：把请求路由到对应专家会增加 round-trip 开销。
- **能力组合**：真实用户问题往往跨领域（如"写 Python 代码解决这道数学题"）。单个内化了所有专长的模型可以组合它们；路由的专家做不到。
#### 那 LoRA 热切换呢？

有个合理的工程反驳：“现代推理服务栈（vLLM、SGLang）都支持 LoRA 热切换——1 个 base + N 个小 adapter，按需切换。干么还要融合？”

LoRA 热切换**对很多场景就是正确答案**——但不适用于 V4 这种 frontier 模型。对比：

| 维度 | LoRA 热切换 | OPD 融合后单模型 |
|------|:-------------:|:--------------------:|
| 专家存储 | ~MB 级 adapter | 无（知识烘入 base） |
| 切换延迟 | 每请求 1-50ms | 0（无切换） |
| 跨领域 query（数学+代码） | ❌ 每请求只能挂 1 个 adapter | ✅ 所有能力同时在线 |
| 能力天花板 | 受 LoRA rank 限制（通常 r=16-64） | 全参数 fine-tune 上限 |
| 专家训练成本 | 便宜（LoRA 训练） | 贵（全 RL 训练） |
| 适用场景 | 多租户定制、单领域 query | Frontier 质量、跨领域复合 query |

V4 选融合是因为：(1) DeepSeek 的 specialist 是全参数 RL 产出，不是 LoRA adapter；(2) Frontier 质量的数学/代码/Agent 任务常常跨领域；(3) Router 服务化带来的运维复杂度 DeepSeek 不想要。

对大多数企业多租户场景，LoRA 热切换仍是更实用的答案。

### 为什么不直接把专家当作 MoE expert 塑进去？

另一个自然反应：“V4 本身就是 MoE 架构，有上百个 expert 槽位。为什么不把每个外部 specialist 插进其中一个槽位？”听起来优雅，但结构上不可行。5 条原因：

| # | 不匹配 | 详细 |
|:-:|--------|------|
| 1 | **粒度** | MoE expert 是**单个 Transformer block 内的一个 FFN 子网络**（~100MB）。外部 specialist 是**一个完整模型**（几百 GB），含 attention、embedding 和所有 FFN 层。你不能把一个完整模型塞进一个 FFN 槽位。 |
| 2 | **架构不兼容** | 外部 specialist 可能是从 V3.2 派生（V3.2 架构）；V4 student 用 CSA/HCA + mHC。层维度、attention 机制、残差结构都不同——FFN 权重不能直接移植。 |
| 3 | **Router 不认识** | MoE router 是 pre-training 阶段从零训出来路由到已有 expert 的。塑入陆生 expert，router 没信号说何时调用。重训 router ≈ 重训整个模型。 |
| 4 | **专长是全身性的** | 一个“数学专家”模型的数学能力编码在**每一层**上——attention 模式、embedding 表示、所有 FFN 协作。只移植一层 FFN 只拿到 < 1% 能力。 |
| 5 | **与 MoE 设计意图不同** | V4 用的是 *fine-grained* expert——每个专门 token 级别 pattern（某种语法结构、某类知识 token），不是一整个领域。一个“领域专家”对应几百个 fine-grained expert 的协作行为，不是 1：1 映射。 |

> **一句话**：OPD 用**行为复刻**（logit 分布匹配）融合；直接塑 MoE expert 需要**零件移植**（权重插入）——后者因为零件接口不兼容而失败。

排除了这两个自然替代方案后，业界最终聚焦在四种严肃的多专家融合方法上。
### 四种候选方案

| 方案 | 机制 | 为什么不够好 |
|------|------|-------------|
| **Weight Averaging** | `θ_merged = (θ_1 + θ_2 + ... + θ_N) / N` | 非线性函数的线性插值。数学专家的权重和代码专家的权重在 loss 地形里互相抵消，常常落到比任一专家都差的区域。 |
| **Task Arithmetic**（TIES、DARE） | `θ_merged = θ_base + Σ τ_i · (θ_i − θ_base)`，加上符号/稀疏化启发式 | 比朴素平均好，因为保留了 task vector。但仍在参数空间操作，忽略了网络输出的变化。 |
| **Mixed RL** | 单次 RL run + 多任务 reward 信号 | 不同领域的 reward 函数常常冲突（如数学要求长 step-by-step 推理，chat 要求简洁回答）。训练不稳定；一个任务的 reward 梯度可能破坏另一个任务。 |
| **On-Policy Distillation (OPD)** | 把多个 teacher 蒸馏到 student，student 自己采样 trajectory 并用反向 KL 匹配每个 teacher 的分布 | 单步慢（student 必须 rollout），但训练稳定，student 自然学到任务条件的行为 |

DeepSeek-V3.2 用的是 Mixed RL。**V4 完全放弃了它**，改用 OPD。

---

## OPD 是什么？

OPD 是标准知识蒸馏的改进版。理解什么让它"on-policy"，最好和离线版对比：

<div align="center">
  <img src="images/opd_vs_offline.png" width="720" alt="Offline vs On-Policy Distillation 对比">
  <p><em>Offline distillation：student 拟合 teacher 的 trajectory。OPD：student 拟合 teacher 对 student 自己 trajectory 的打分。</em></p>
</div>

### Offline Distillation（传统做法）

```
Step 1: Teacher 生成一个答案
Step 2: Student 训练去模仿这个答案
```

Student 看到的全是 teacher 会产生的数据。推理时，student 被要求从自己（不同的）分布生成——这种训练/推理 gap 会损害泛化，特别是长自回归生成中误差会累积。

### On-Policy Distillation

```
Step 1: Student 生成一个答案（rollout）
Step 2: Teacher 计算这个答案中每个 token 位置上的概率分布
Step 3: Student 更新自己，让分布在这些位置上更接近 teacher
```

Student 始终在**自己的行为**上学反馈。没有训练/推理分布不匹配的问题。这正是让 on-policy RL 比 off-policy 更 sample-efficient 的同一原理——只不过这里把 reward 信号换成了 teacher 的 logit 分布。

### 一个具体例子（一个训练 step）

假设 prompt 是 `"解：12 × 7 = "`，teacher 是数学专家。

**Step 1 — Student rollout**（student 采样自己的续写）：
```
Student 生成："让我想想。12 × 7 = 12 × 5 + 12 × 2 = 60 + 24 = 84"
```

**Step 2 — Teacher 打分**（数学专家看到同样的 prompt + student 的续写，在每个位置计算 logits）：
```
"84" 这个位置：
  Teacher logits → softmax → P(token | context)
  P("84") = 0.92（teacher 高度自信）
  P("82") = 0.03
  P("76") = 0.02
  ...

"60" 这个位置：  
  Teacher P("60") = 0.71（teacher 在这里也会选 60）
  Teacher P("70") = 0.05
  ...
```

**Step 3 — Student 更新**（计算 student 和 teacher 分布的反向 KL，更新 student 权重让分布往 teacher 靠）：
```
每个 token 位置：L = Σ_v π_θ(v) · [log π_θ(v) − log π_E(v)]
反向传播，更新 θ。
```

注意：student 是基于**自己的拆解策略**（"12 × 5 + 12 × 2"）被打分，不是 teacher 的。如果 teacher 会用别的方法，student 不需要照抄——只要在 student 走的每一步上，teacher 都认可就行。

---

## OPD vs MoE：两种不同的“Expert”

V4 **既是 MoE 架构、又是 OPD 后训练的成果**。这是两个完全独立的概念，恰好用了同一个词“expert”——这是常见混淆的源头。澄清：

| 概念 | 是什么 | 存在期 | V4-Pro 数量 |
|------|------|--------|:----------:|
| **MoE expert**（架构层） | 一个 Transformer block 内的单个 FFN 子网络，router 按 token 选 | **永久**——是模型架构的一部分 | ~256 fine-grained expert × ~60 层 = ~15K 个 expert |
| **OPD 领域专家**（仅训练期） | 一个完整独立模型，按某领域（数学/代码/写作）全参数 RL 训出 | **仅训练期**——OPD 蒸馏后消失 | 训练时 10+，训练后 0 |

要可视化 V4 Transformer 内部的架构层 MoE——看清 fine-grained FFN expert 相对于 Attention、KV Cache 和其他组件的位置——请看 [KV-Cache-Deep-Dive 中的完整 MoE Transformer 流水线图](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive#moe-variant-when-step-5-becomes-a-mixture-of-experts)。核心要点：每个 MoE "expert" 是一个小 FFN（如 4096→1408→4096），由 router 逐 token 选择。OPD specialist 是整个几千亿参数的模型。它们是完全不同的东西。

### MoE expert 的"技能"从哪来？

一个常见的追问：既然没人给 MoE expert 贴"数学 expert" / "写作 expert" 的标签，它们是怎么变得专业化的？

答案：**专业化是 pre-training 中由 Router-Expert 的反馈循环自动形成的。**

```
Pre-training 初始化：
  Expert 1, 2, ..., 256：随机 FFN 权重，没有任何技能
  Router：随机权重，瞎选

Pre-training 进行中（万亿 token 训练）：
  随机扰动让某些 expert 在某类 token pattern 上略好一点
  → Router 学会在遇到这类 pattern 时更倾向选它们
  → 这些 expert 在这类 pattern 上收到更多梯度
  → 它们变得更擅长
  → 正反馈循环把分工固化下来

Pre-training 结束：
  Expert 17：主要被英文语法 token 激活
  Expert 42：主要被数学符号激活
  Expert 103：主要被中文叙述 token 激活
  Expert 200：主要被代码缩进 token 激活
  ...
  （但没有人给它们贴标签。是 Router 学会的，是 expert 自己适应的。）
```

**重要细节**：expert 的"技能"不是一个领域，而是一类 **token-level pattern**。严格说没有"数学 expert"；只有"被数学运算符 token 激活的那个 expert"——它在统计上看起来像数学专家。一道数学题的不同 token（数字、运算符、标点等）会激活很多不同 expert，每个都贡献最终输出的一部分。

### OPD 梯度流：哪些 Expert 真正被更新？

现在可以回答最微妙的问题：**当 OPD 一步训练发生时，10+ 个教练全部打分，student 中哪些 MoE expert 被更新？**

从 OPD loss 严格逻辑推导：

$$L = \sum_{i=1}^{N} w_i \cdot D_{KL}(\pi_\theta \,\|\, \pi_{E_i})$$

对任意参数 `θ_p`（如某个 expert 的 FFN 权重），梯度为：

$$\frac{\partial L}{\partial \theta_p} = \sum_{i=1}^{N} w_i \cdot \frac{\partial D_{KL}(\pi_\theta \,\|\, \pi_{E_i})}{\partial \theta_p}$$

教练分布 `π_E_i` 是**冻结的**（不依赖 `θ_p`），所以梯度非零的唯一路径是通过 `π_θ`——student 输出分布。链式法则：

$$\frac{\partial D_{KL}}{\partial \theta_p} = \frac{\partial D_{KL}}{\partial \pi_\theta} \cdot \frac{\partial \pi_\theta}{\partial \theta_p}$$

如果 `θ_p` 没参与产生 `π_θ` 的 forward 计算，那么 `∂π_θ / ∂θ_p = 0` **严格为零**（它根本不在计算图里）。

**对一个训练样本（如一道数学题）**：

| 组件 | 参与 forward？ | 收到梯度？ |
|------|:--------------:|:---------:|
| Embedding、Attention、LM Head | ✅ 总是 | ✅ 总是 |
| Router | ✅ 总是 | ✅ 总是 |
| **被 Router 选中的** MoE expert（top-8） | ✅ 是 | ✅ 是（梯度流过） |
| **未被选中的** MoE expert（其他 248 个） | ❌ 否 | ❌ 严格为零 |

**关键**："10 个教练都给每个样本打分" 这个事实只改变了流到**被选中** expert 的梯度的**组成**——它无法让梯度流到**未被选中**的 expert。未被选中的 expert FFN 权重在数学上与这个样本的 loss 完全断开。

所以一道数学题进来时：

1. Router 选出 top-8 个处理数学 pattern token 的 expert，记为集合 M
2. Forward pass 只用 M（其他 248 个 expert 被绕开）
3. 10+ 个教练都对 student 输出打分：
   - 数学教练：高质量 KL 信号（它懂数学）
   - 其他 9 个教练：低幅噪声（它们不懂数学，给出近均匀分布）
4. 梯度反向传播，按 `w_i` 加权求和：
   - 数学教练的梯度占主导（KL 大 → 梯度大）
   - 其他教练的梯度互相抵消接近零（随机噪声）
5. 主导梯度只更新 **M 中的 expert**（以及 Router/Attention 等）
6. 其他 248 个 expert：梯度 = 0，权重不变

**最终结果**：数学 expert 接受数学训练，写作 expert 接受写作训练，代码 expert 接受代码训练——尽管所有教练在每一步都在场。**Router（架构层）和梯度稀疏性（数学层）共同实现了清晰的分工。**

### 可视化：推理路径 vs OPD 训练路径

两张图把上面的机制画清楚。

**图 A — 推理时（一个 token 走过 60 层）**：

```mermaid
graph TD
    INPUT["Input Token<br/>例: '12'<br/>4096-dim hidden state"] --> L1
    
    subgraph L1["Layer 1"]
        L1_ATT["Attention<br/>(CSA/HCA)"] --> L1_ROUTER
        L1_ROUTER["Router<br/>4096d → 256 logits"]
        L1_ROUTER -->|"top-8"| L1_E["Expert {17, 42, 89,<br/>103, 128, 156, 200, 233}<br/>+ Shared Expert"]
        L1_E --> L1_OUT["输出 4096d<br/>→ 下一层"]
    end
    
    L1 --> L2
    
    subgraph L2["Layer 2"]
        L2_ATT["Attention"] --> L2_ROUTER
        L2_ROUTER["Router"]
        L2_ROUTER -->|"top-8"| L2_E["Expert {5, 23, 67,<br/>91, 120, 178, 201, 245}<br/>+ Shared Expert"]
        L2_E --> L2_OUT["输出 4096d<br/>→ 下一层"]
    end
    
    L2 --> DOTS["...<br/>(每层都重复:<br/>Attention → Router → top-8 expert)"]
    
    DOTS --> L60
    
    subgraph L60["Layer 60"]
        L60_ATT["Attention"] --> L60_ROUTER
        L60_ROUTER["Router"]
        L60_ROUTER -->|"top-8"| L60_E["Expert {3, 47, 88,<br/>112, 145, 189, 217, 250}<br/>+ Shared Expert"]
        L60_E --> L60_OUT["输出 4096d"]
    end
    
    L60 --> LM_HEAD["LM Head<br/>4096d → 150K vocab<br/>→ 预测下一个 token"]
    
    style L1 fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style L2 fill:#E8EAF6,stroke:#283593,stroke-width:2px
    style L60 fill:#FCE4EC,stroke:#C62828,stroke-width:2px
    style DOTS fill:#FFF9C4,stroke:#F9A825,stroke-width:2px,stroke-dasharray:5 5
    style L1_ROUTER fill:#9C27B0,color:#fff
    style L2_ROUTER fill:#9C27B0,color:#fff
    style L60_ROUTER fill:#9C27B0,color:#fff
    style L1_E fill:#CE93D8
    style L2_E fill:#CE93D8
    style L60_E fill:#CE93D8
    style INPUT fill:#FFE082
    style LM_HEAD fill:#FFAB91
```

图 A 的关键观察：
- **60 层，每层有自己独立的 256 个 expert 池**（Layer 1 和 Layer 2 的 expert 池**完全独立**，互不共享）
- **每层 Router 独立选 top-8**（同一个 token 在不同层选的 expert 编号不同）
- **每个 token 总激活量** = 60 × (8 routed + 1 shared) = **540 个 expert 实例**（共 ~15,000 个里）
- 对应约 49B 激活参数（≈ V4-Pro 总参数 1.6T 的 3%）

**图 B — OPD 一步训练**：

```mermaid
graph TD
    INPUT["训练样本: 数学题<br/>例: '12 × 7 = ?'<br/>当前 token = '12'"] --> SPLIT[" "]
    
    SPLIT -.->|"同一 token 输入"| STUDENT
    SPLIT -.->|"同一 token 输入"| TEACHERS
    
    subgraph STUDENT["Student (V4 MoE，正在被训练)"]
        direction TB
        S_L1["Layer 1: Attention → Router → top-8 expert<br/>{17, 42, 89, 103, ...}"] --> S_L2["Layer 2: 同样结构<br/>{5, 23, 67, 91, ...}"]
        S_L2 --> S_DOTS["...60 层都重复..."]
        S_DOTS --> S_LMHEAD["LM Head"]
        S_LMHEAD --> S_DIST["π_θ:<br/>student 的全词表概率分布<br/>(150K-dim)"]
    end
    
    subgraph TEACHERS["10+ Specialist 教练 (冻结，不训练)"]
        direction TB
        T_MATH["数学 Specialist<br/>(完整模型)<br/>→ 输出概率分布"]
        T_CODE["代码 Specialist<br/>→ 输出概率分布"]
        T_WRITE["写作 Specialist<br/>→ 输出概率分布"]
        T_DOTS["...其他 ~7 个..."]
    end
    
    S_DIST --> LOSS
    T_MATH -->|"π_E1: 高质量信号<br/>(数学题它最懂)"| LOSS
    T_CODE -->|"π_E2: 噪声信号<br/>(数学题它不懂)"| LOSS
    T_WRITE -->|"π_E3: 噪声信号"| LOSS
    T_DOTS -->|"..."| LOSS
    
    LOSS["Loss = Σᵢ wᵢ · KL(π_θ ‖ π_Ei)<br/>所有 N 个教练全部加权求和<br/>(论文 Eq.29)"]
    
    LOSS --> GRAD["反向传播梯度"]
    
    GRAD -.->|"数学教练梯度主导<br/>更新 student 参数"| S_UPDATE["✅ 更新 Student:<br/>• Embedding<br/>• 每层 Attention<br/>• 每层 Router<br/>• 每层被选中的 8 个 expert<br/>(其余 248 个 expert 梯度=0)"]
    
    GRAD -.->|"❌ 不更新"| T_FROZEN["教练全程冻结<br/>不被训练"]
    
    style INPUT fill:#FFE082
    style SPLIT fill:#FFFFFF,stroke:#FFFFFF
    style STUDENT fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style TEACHERS fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    style LOSS fill:#FFAB91,stroke:#BF360C,stroke-width:3px
    style GRAD fill:#FFCC80,stroke:#E65100,stroke-width:2px
    style S_UPDATE fill:#C8E6C9,stroke:#2E7D32,stroke-width:2px
    style T_FROZEN fill:#FFCDD2,stroke:#B71C1C,stroke-width:2px
    style S_DIST fill:#9C27B0,color:#fff
    style T_MATH fill:#F8BBD0
    style T_CODE fill:#F8BBD0
    style T_WRITE fill:#F8BBD0
    style T_DOTS fill:#F8BBD0,stroke-dasharray:3 3
```

图 B 的关键观察：
- **所有 N 个教练每一步都跑 forward**（Eq.29 求和所有 KL 项——没有"挑教练"的步骤）
- **只有对口教练给出有用梯度**（数学题上数学教练分布尖锐 → KL 大 → 信号强；其他教练分布近均匀 → 噪声）
- **教练全程冻结**——只有 student 的参数被更新
- **Student 内部，只有 Router 选中的 expert 收到梯度**——每层未被选中的 expert 梯度严格为 0

"所有教练都打分"（Eq.29）+ "只有被选中的 expert 参与计算"（MoE forward）这两个机制叠加，产生了一个优雅的性质：**数学上 10+ 个教练全程参与，但实际效果是每道题只训了 router-pattern 与之对齐的 expert，主要由真正懂这个领域的教练指导**。

### OPD 蒸馏的能力最终去了哪里？

当 OPD 蒸馏后的 student 推理时接到一道数学题：

1. **Embedding** 层激活数学相关的 token embedding
2. **Attention** 层（CSA/HCA）关注数学相关上下文
3. Step 5 的 **Router** 把 token 调度给那些在 OPD 训练中成为数学 token pattern 专家的 MoE expert（这是自动的——梯度下降决定哪个 expert 处理哪个 pattern）
4. **多个 MoE expert** 给出加权输出（没有任何单一 expert “是”那个数学专家）
5. **LM Head** 映射到数学相关词表

OPD 训练时教出这些行为的“数学专家模型”早就被删了。它的能力现在**分布在整个 student 模型上**，不集中在任何一个组件里。

这与架构层 MoE 本质不同——MoE 每个 expert FFN 是有独立参数的离散单元。OPD 融合产生的**能力是梯度下降分布出来的**，不是架构设计出来的。

---

## 数学：反向 KL + GKD 框架

V4 论文的 OPD 目标函数（公式 29）：

$$L_{OPD}(\theta) = \sum_{i=1}^{N} w_i \cdot D_{KL}(\pi_\theta \,\|\, \pi_{E_i})$$

有三个地方值得拆开看。

### 1. KL 是反向，不是正向

| 方向 | 公式 | 行为 |
|-----|------|-----|
| **Forward KL** `D_KL(π_E ‖ π_θ)` | `Σ π_E(v) · [log π_E(v) − log π_θ(v)]` | "Mode-covering" — student 试图在 teacher 有概率的所有地方都放上非零概率。Offline distillation 常用。 |
| **Reverse KL** `D_KL(π_θ ‖ π_E)` | `Σ π_θ(v) · [log π_θ(v) − log π_E(v)]` | "Mode-seeking" — student 集中在 teacher 的高概率 mode 上。 |

OPD 用**反向 KL**因为：
- Trajectory 来自 `π_θ`（student），用 `π_θ(v)` 加权很自然
- Mode-seeking 行为产生更尖锐、更果断的 student 输出（适合生成）
- 在 student-sampled trajectory 上算 forward KL 方差会很大，因为我们要在 student 很少选的 token 上评估 teacher 概率

### 2. 期望是在 student trajectory 上

KL 在 student-sampled trajectory 的每个 token 上计算。这就是"on-policy"的含义：

$$D_{KL}(\pi_\theta \,\|\, \pi_{E_i}) = \mathbb{E}_{y \sim \pi_\theta}\left[\sum_{t} \sum_v \pi_\theta(v|y_{<t}) \log \frac{\pi_\theta(v|y_{<t})}{\pi_{E_i}(v|y_{<t})}\right]$$

如果改从 teacher 采样，就退化成了 offline distillation。

### 3. 权重 `w_i` 隐式做领域路由

论文解释：
> *"the unified policy π_θ selectively learns from the specialized expert relevant to the current task context (e.g., aligning with the mathematics expert for math reasoning tasks and the coding expert for programming tasks)."*

这能 work 是因为每个 teacher 的分布在自己领域上很尖锐、在其他领域上很平。当 trajectory 是数学题时，只有数学专家产生 low-loss 梯度；其他 teacher 贡献的近似均匀分布噪声会相互抵消。

所以即使所有 teacher 都加在一起，每个任务自然会和对应专家对齐。这比显式做任务路由简单得多。

---


### OPD 在 GKD 框架下的位置

明确了反向 KL 目标函数后，我们可以用 GKD（Generalized Knowledge Distillation，泛化知识蒸馏）框架来精确定位 OPD 在所有蒸馏方法中的位置。


OPD 不是独立方法——它实际上是更通用框架 **GKD（Generalized Knowledge Distillation，泛化知识蒸馏）** 的一个**特定配置**。GKD 由 Agarwal 等人（Google DeepMind, 2023）提出。理解 GKD 让 OPD 的设计空间一目了然。

### GKD 统一损失函数

GKD 用两个超参数把所有蒸馏方法参数化：

```
GKD Loss = (1 - lmbda) × KL_offline + lmbda × KL_on_policy
                                                ↑
                              "lmbda" 控制 on-policy 比例
                              0 = 纯 offline, 1 = 纯 on-policy

KL_inner = (1 - beta) × Forward_KL + beta × Reverse_KL
                                              ↑
                              "beta" 控制 KL 方向
                              0 = 纯 forward KL, 1 = 纯 reverse KL
```

### 所有蒸馏方法都是 GKD 的某个配置

| 配置 | 方法 | Trajectory 来源 | KL 方向 |
|------|-----|---|---|
| `lmbda=0, beta=0` | 经典 SFT 蒸馏 | Teacher | Forward |
| `lmbda=0, beta=1` | Sequence-level KD + reverse KL | Teacher | Reverse |
| `lmbda=1, beta=0` | On-policy + forward KL | Student | Forward |
| **`lmbda=1, beta=1`** | **OPD（V4 选择）** | **Student** | **Reverse** |
| `lmbda=0.5, beta=0.5` | 混合配置 | 50/50 | 50/50 |

DeepSeek-V4 的 OPD 是边界情况：**最大 on-policy + 最大 reverse KL**。

这个泛化性正是为什么 TRL 的 `GKDTrainer` 是开始 OPD 实验最简单的方式：**设 `lmbda=1.0, beta=1.0` 就是 OPD**。

> 🔗 GKD 论文：Agarwal et al., *On-Policy Distillation of Language Models: Learning from Self-Generated Mistakes*, NeurIPS 2024 (arXiv:2306.13649)。DeepMind 官方实现：https://github.com/google-deepmind/gkd

### KL 方向问题，直觉理解

常见困惑："如果 `beta=0`（forward KL）让 student 覆盖 teacher 所有 mode，为什么 V4 选 `beta=1`（reverse KL）放弃某些 mode？"

答案：student 容量有限，无法完美拟合多峰 teacher 分布。被迫近似时，两个 KL 方向产生相反行为：

```
Teacher 分布（多峰，比如一道数学题有 3 种合理表述）：
   ▲
   │ ████        ████        ████
   │ ████        ████        ████
   └──────────────────────────────
      "84"     "answer:84"  "= 84"
       0.4         0.3         0.3

Forward KL（mode-covering）：
   ▲
   │ ████   ███        ████        
   │ ████   █████      ████        ← 概率铺平到所有 mode
   │ ████   ███████    ████        ← 输出：随机折中的怪东西
   └──────────────────────────────

Reverse KL（mode-seeking）：
   ▲
   │ ████████                       ← 集中赌一个 mode
   │ ████████                        
   │ ████████                       ← 输出：果断的单一答案
   └──────────────────────────────
```

对 LLM 生成（每个位置必须选一个具体 token），reverse KL 的 **mode-seeking** 行为产生果断、连贯的输出。Forward KL 产生犹豫、混合的输出，往往不对应 teacher 任何一个真实 mode。

这就是为什么 OPD 专门选反向 KL——不是因为它能捕获更多信息，而是因为它**学到了适合自回归生成的行为类型**。

---

## 多专家 OPD 的工程化

<div align="center">
  <img src="images/multi_teacher_opd.png" width="600" alt="Multi-Expert OPD Pipeline">
  <p><em>多专家 OPD：student 采样 → 所有 teacher 打分 → 加权 KL 梯度更新 student。</em></p>
</div>

DeepSeek-V4 同时从 **10+ 个 teacher** 蒸馏。朴素实现有两个致命问题：

### 问题 1 — Logit 存储爆炸

为每个训练样本、每个 teacher、每个 token 位置存全词表 logits：

- 词表 `|V| > 100,000`（Qwen3、DeepSeek-V3 系列）
- 序列长度 `L = 2048-32768`（长上下文训练）
- 每个位置每个 teacher 的 logits：`|V| × 4 bytes (FP32) = 400 KB`
- 10 个 teacher × 32K seq × 400 KB = **每个训练样本 128 GB**——内存装不下，存盘也存不下。

**V4 的解决方案**（论文 Section 5.2.2）：只缓存每个 teacher 的**最后一层 hidden states**，不缓存 logits。Hidden states 是 `d_model × 2 bytes` (BF16)，每个 token 通常 7-14 KB——小好几个数量级。训练时把缓存的 hidden states 过 teacher 的预测头，按需精确重建完整 logits。

代价：增加少量重计算（每个 token 一次矩阵乘法），换来巨大的内存节省。

### 问题 2 — 同时加载 10+ teacher 权重

每个 teacher 可能是几千亿参数的模型。同时把 10 个塞进 GPU 显存不可行。

**V4 的解决方案**：teacher 权重用 ZeRO 风格参数分片，按需从中心化存储加载。Teacher 分批调度；数据按 teacher 索引重排，最小化 prediction head 的上下文切换（论文 Section 5.2.2）。

### 为什么折腾这些？为什么不用全 logits + 少 teacher？

V4 论文明确反对一种常见的省事做法——把全词表 KL 简化成单个 per-token KL 估计：

> *"prior works usually simplify the full-vocabulary KL loss into a token-level KL estimate at each token position [...] Although this approach is resource-efficient, it leads to **high variance in gradient estimation and often causes training instability**. Therefore, we adopt full-vocabulary logit distillation in our OPD."*

Token-level KL 只看 teacher 给 student 选中的那个 token 分配的概率，忽略了分布的其他部分。这丢失了"teacher 对所选 token 相比其他选项有多自信"的信息——而这恰恰是蒸馏最重要的信号。全词表 KL 更贵但梯度方差更低、训练更稳定。

---

## OPD 与其他多专家方法对比

### vs Weight Averaging

| 方面 | Weight Averaging | OPD |
|-----|:----------------:|:---:|
| 融合发生在哪 | 参数空间 | Logit 空间（输出行为） |
| 捕捉非线性交互？ | ❌ 不能 | ✅ 能（训练完成的） |
| 速度 | 即时（无训练） | 慢（student rollout + 多 teacher forward） |
| 质量保留 | 通常较差（最佳专家的 70-90%） | 强（往往达到或超过该领域最佳专家） |
| 超参数 | 只有融合权重 | 权重 `w_i`、学习率、训练步数、采样温度 |

权重平均本质上是在问："如果我在非凸 loss 地形上的两个好点之间走中点，我还在好的区域吗？" 答案常常是否定的——神经网络 loss 地形充满了山谷，中点远高于两个端点。

### vs Task Arithmetic（TIES、DARE 等）

Task arithmetic 是 weight merging 的精致版：

```
对每个专家 i：task_vector_i = θ_i − θ_base
融合：       θ_merged = θ_base + Σ_i τ_i · task_vector_i（加上符号 + 稀疏化启发式）
```

比朴素平均好，因为它把"fine-tuning 改了什么"从 base 模型里剥离。但仍受同一个根本问题影响：参数空间组合不一定产生连贯的输出行为。TIES 和 DARE 加了启发式（符号选举、幅度剪枝）来缓解干扰，但底层假设——"好的行为在权重空间线性可组合"——经验上站不住脚。

OPD 直接绕过这个问题，在输出空间工作。不管参数最终是什么，student 因产生匹配 teacher 的分布而被奖励。

> 🔗 我们另有一个 Repo [LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)，量化了参数空间合并如何降低质量。OPD 是绕开这个问题的另一条路。

### vs Mixed RL（V3.2 用过、V4 抛弃的方案）

Mixed RL 用多领域的 reward 信号同时训练一个模型：

```
每个 batch：从领域 mix 中采样任务 → 用组合 reward 跑 RL update
```

问题：
- Reward 函数不可组合。数学 reward 可能偏好 500-token 解答；chat reward 可能偏好 80-token 回答。同时优化两者会产生不连贯的长度策略。
- 模型不知道自己在服务哪个领域，所以它学到的是平均行为，而不是领域条件行为。
- Reward hacking 被放大——一个领域可被利用的 reward 会污染所有领域的梯度。

OPD 没有这些问题：
- 每个 teacher 的分布隐式做了领域专业化（teacher 自己就是按领域训出来的）
- KL 信号是稠密的（每个 token、每个 vocab 位置）vs 稀疏的 RL reward（每个 trajectory 一个标量）
- 不需要设计 reward 函数——teacher 分布就是隐式 reward

### vs SFT（Supervised Fine-Tuning）—— Exposure Bias 问题

一个常见的疑问：**为什么不直接用 SFT 在每个 specialist 的输出上训练 student？** 看起来更简单——收集 specialist 对 prompt 的回答，然后把 (prompt, response) 对喂给 student fine-tune。

这种方法在一定程度上有效，但有一个根本问题，叫 **Exposure Bias**：

```
SFT 训练：
  Prompt:   "Solve: 13 × 7 = ?"
  Teacher 答案："13 × 7 = 91"
  
  Student 在每一步学：
    Step 1: 前缀 "13 ×" → 预测下一个 token
            （这个前缀是 teacher 写的——干净、正确）
    Step 2: 前缀 "13 × 7" → 预测下一个 token
            （还是 teacher 的前缀）
    Step 3: 前缀 "13 × 7 =" → 预测下一个 token（= "91"）
  
  整个训练过程，student 只见过 teacher 生成的前缀。
```

但推理时**没有 teacher**——student 自己生成前缀：

```
推理时：
  Step 1: 前缀 "" → student 生成 "13"
  Step 2: 前缀 "13" → student 生成 "×"
  Step 3: 前缀 "13 ×" → student 生成 "7"
  Step 4: 前缀 "13 × 7" → student 不小心生成 "+"（错了！）
  Step 5: 前缀 "13 × 7 +"  ← ⚠️ 训练时从未见过这个前缀！
          Student 不知道怎么从自己的错误中恢复。
          → 输出可能崩坏："13 × 7 + 91 = 104"（胡说）
```

**这就是 exposure bias**：student 训练时从未"暴露"在自己生成的前缀（可能含错）下。推理时一旦自己出错，没有学过"刚才写错了，下一步怎么办"的行为。

OPD 通过**on-policy 采样**解决：

```
OPD 训练：
  Step 1: Student 用自己当前能力生成完整 trajectory：
          "Let me think... 13 × 7 = 81... 等等，重算一下：13 × 7 = 91"
          （包含 student 自己的错误和自我纠正）
  Step 2: Specialist 在每个 token 位置打分
  Step 3: Student 在【自己的错误】上学习
  
  → Student 学过"刚写错时怎么继续"
  → 推理时能自我纠错（这就是推理模型的"等等，让我重新想"）
```

这就是为什么 frontier 推理模型（DeepSeek-R1、OpenAI o1 等）都用 on-policy 训练（RL 或 OPD）——纯 SFT 教不会自我纠正。

| 维度 | SFT | OPD |
|------|:---:|:---:|
| 训练数据前缀来自 | Teacher | **Student 自己** |
| 每 token 信号 | 1 个标签（teacher 选的 token） | **完整分布（~150K 个概率）** |
| 训练/推理分布一致 | ❌ 不一致 | ✅ 一致 |
| 自我纠错能力 | ❌ 教不会 | ✅ 能教会 |
| 多教师支持 | ❌ 必须挑一个或顺序训（catastrophic forgetting） | ✅ 天然 Σᵢ 支持 |

### vs RL / RLAIF —— 只是更密的 reward 信号

自然的下一个问题：**RL 也能解决 exposure bias（student 自己采样）——为什么不直接用 RL？**

你说得对——V3.2 用的就是 RL。V4 *试过* RL 然后用 OPD 替换。关键洞察：

**OPD = 把 teacher logit 分布当 reward 信号的 RL。**

两者都是 on-policy 训练（student 采样）。唯一区别是 student 每个 trajectory 收到的反馈类型：

| 方法 | 每条 trajectory 的反馈 | 每 token 信号密度 |
|------|---|:---:|
| **RL with rule reward**（如数学正确性） | 1 个标量（如 +1 / -1） | ~0.001（1 / 1000 tokens） |
| **RLHF**（人工反馈） | 1 个标量 | ~0.001 |
| **RLAIF**（LLM 当裁判，如 GPT-5 打分） | 1 个标量 | ~0.001 |
| **OPD** | 每 token 完整词表分布（~150K） | **150,000** |

OPD 的反馈密度大约是 scalar RL reward 的 **1.5 × 10⁸ 倍**。这意味着：
- 梯度更稳定（方差更低）
- 收敛更快
- 不需要设计 reward 函数（teacher 分布就是 reward）
- 不会 reward hacking（你没法通过钻一个维度的漏洞来骗过 150K 维分布）

**那为什么大家不都用 OPD？** 因为它需要 **teacher 的全词表 logits**——这就是实际的硬墙。

#### 隐藏的限制：API 是否给 logits

商业 LLM API（OpenAI、Anthropic 等）**不暴露全词表 logits**：

| API | top_logprobs 上限 | 能做完整 OPD？ |
|-----|:--:|:--:|
| Azure OpenAI Chat Completions | 20 | ❌（只占 0.013% 词表） |
| Azure OpenAI Completions | 5 | ❌（只占 0.003%） |
| Anthropic Claude API | 不暴露 | ❌ |
| **自部署开源模型**（Llama / Qwen / DeepSeek） | 全部 | ✅ 完整词表 |

> 来源：[Azure OpenAI REST API Reference](https://learn.microsoft.com/en-us/azure/foundry/openai/reference) — `top_logprobs` 是 "An integer between 0 and 20 specifying the number of most likely tokens to return at each token position"。

这就是为什么 V4 必须自家来做：specialist 是自部署的，能拿到全词表 logits。用 GPT-5 当 teacher 的初创公司只能做"top-20 KL 的 RLAIF"，比完整 OPD 弱很多（V4 论文 Section 5.1.2 明确反对这种近似）。

> 🔗 小团队想做类似 OPD：自部署一个开源 teacher（如 Llama-3-70B、Qwen2.5-72B、DeepSeek-V3），就能拿到全词表 logits。这正是 DeepSeek-R1 蒸馏 Qwen 系列的做法。

### vs Step Distillation（Diffusion 模型）—— 不同领域、不同机制

熟悉图像生成的工程师可能听过 diffusion 模型语境下的"蒸馏"——比如把 50 步 Stable Diffusion teacher 蒸馏成 8 步 student（LCM、Lightning、Hyper-SD 等）。**这是完全不同的一种蒸馏，不是 OPD。**

| 维度 | Step Distillation（Diffusion） | OPD（LLM） |
|------|:----:|:---:|
| 领域 | Diffusion 图像生成 | 自回归 LLM |
| 目标 | 减少推理步数（50 → 8） | 融合多个领域专家 |
| Teacher 在训练时的行为 | 离线**一次性**生成 trajectory；之后退场 | 每个训练 step **在线**计算 logits |
| On-policy 还是 offline？ | **Offline**（teacher 的 trajectory 保存为固定数据集） | **On-policy**（student 的 trajectory 实时打分） |
| 训练信号 | Teacher 的中间去噪状态 | Teacher 的完整词表分布 |

Step Distillation 中，teacher 的角色是**预先生成训练数据集**。数据集生成后，teacher 退场，student 用普通监督方式训练。

OPD 中，teacher **始终在训练循环中**——每一步都给 student 的实时采样打分。

这是两种完全不同的方法，碰巧都叫"distillation"。当有人说"我们用了蒸馏"，一定要问：**on-policy 还是 offline？单 teacher 还是多 teacher？teacher 给什么信号？** 答案决定了讨论的是哪种方法。

---


### vs 速度场蒸馏（Diffusion 模型）


熟悉 diffusion 模型的工程师可能听过"速度场蒸馏"（Flow Matching、Lightning 等）用于图像生成。**OPD 不是这个。** 快速澄清：

| 概念 | OPD（LLM） | 速度场蒸馏（Diffusion） |
|------|---|---|
| 领域 | 自回归 LLM | Diffusion 图像/视频生成 |
| 学的对象 | 类别 token 分布（~150K 维） | 连续速度向量（~1024 维） |
| Loss 类型 | **反向 KL 散度** | **MSE on velocity** |
| 目标 | 多专家能力融合 | 减少推理步数（50 → 8） |
| Teacher 信号 | 词表上的概率 | 每个 timestep 的速度预测 |
| 例子 | DeepSeek-V4、Qwen3、MiMo-V2-Flash | Stable Diffusion 3、Flux、Qwen-Image-Lightning |

这是两种完全不同的方法，碰巧都叫 "distillation"。讨论 LLM 蒸馏时，OPD/GKD 是相关家族；讨论 diffusion 模型蒸馏时，Step Distillation（Progressive Distillation、ADD、Lightning、Hyper-SD）是相关家族。

---

## DeepSeek-V4 中哪些是原创？

OPD 在学术界已经研究了几年。V4 贡献的诚实拆解：

| 组件 | 起源 | 来源 |
|------|------|------|
| 知识蒸馏（通用） | Hinton et al., 2015 | "Distilling the Knowledge in a Neural Network" |
| 反向 KL 蒸馏 | 生成模型文献 | Various 2018-2023 |
| On-policy distillation 概念 | Agarwal et al., 2023 (GKD) | "Generalized Knowledge Distillation" |
| 多教师蒸馏 | 2020-2024 多篇学术工作 | Various |
| **完全用 OPD 替代 mixed RL** | ✅ V4 — 第一个这么做的主流大模型 | V4 论文 Section 5.1 |
| **全词表 OPD（拒绝 token-level KL 近似）** | ✅ V4 — 明确反对常见的省事做法 | V4 论文 Section 5.1.2 |
| **10+ teacher 万亿参数级别的蒸馏** | ✅ V4 — 工程规模史无前例 | V4 论文 Section 5.2.2 |
| **Hidden-state 缓存重建 logits** | ✅ V4 — 原创工程技巧 | V4 论文 Section 5.2.2 |

简单说：**OPD 方法本身不是新的**。V4 的贡献在于：(1) 战略性地把 OPD 作为多专家融合的*唯一*机制，(2) 不计代价坚持全词表 KL，(3) 让这套方法在 10+ 万亿参数 teacher 规模下跑得动的工程基础设施。

---

明确了原创性贡献后，我们来讨论 OPD 的诚实局限：

## OPD 的诚实局限

OPD 不是万能药。三个值得理解的现实约束：

### 1. 覆盖度依赖数据，不是架构保证

OPD 只更新 router 在每个训练样本中选中的 MoE expert。OPD 训练数据分布之外的 token-level pattern 对应的 expert，在整个 OPD 中**永远不会被选中**——它们保留 pre-training 权重不变。

```
如果 OPD 训练数据只覆盖 数学 + 代码 + 写作：
  → 数学/代码/写作 pattern 对应的 expert 收到 OPD 更新（实际中是大多数 expert）
  → 处理罕见 pattern 的 expert（如冷门语言、niche 符号）
    收不到 OPD 信号 → 只保留 pre-training 能力

→ OPD 覆盖度 = OPD 训练数据覆盖度 ≠ "256 个 expert 全都被均等训练"
```

V4 用多样化训练数据 + "general chat" specialist（激活面广）来缓解这点，但**没有**理论上保证每个 expert 都被改进——这是数据工程选择，不是数学保证。

### 2. 梯度归因不精确

Teacher 在**输出层**给反馈（next-token 分布），但 student 的错误可能发生在**任何中间层**（错的 attention 模式、错的 router 选择、错的 FFN 计算）。反向传播的梯度只能"猜"是哪个内部组件的责任。

实际效果：
- 训练比理想情况慢（部分梯度落在无辜组件上）
- 没出错的 expert 也会收到一点小梯度更新
- 用小学习率 + 多步训练 + 多教师噪声相消来压制

V4 没有声称解决这个问题——他们只是经验性地调参绕开。

### 3. 规模决定可行性

完整的 V4 OPD pipeline（10+ teacher × 万亿参数 × 全词表 KL）只对以下组织可行：
- 自部署 teacher 模型（商业 API top_logprobs 上限 20）
- 中心化权重存储 + ZeRO 风格 sharding
- 自定义 hidden state 缓存（防止 logit 存储爆炸到 TB 量级）

对小团队：OPD 类训练的简化版本（单个开源 teacher + 标准 PyTorch）仍然非常有效。但 V4 的 *完整* 配置是 frontier 公司的专属能力。

---

## 快速上手：代码与工具

### OPD 实现：骨架代码

PyTorch 单 GPU 上的最小 OPD 训练循环（演示，非生产）：

```python
import torch
import torch.nn.functional as F

def opd_loss(student_logits, teacher_logits_list, weights):
    """
    全词表反向 KL OPD loss。
    来源：DeepSeek-V4 论文 Section 5.1.2 公式 (29)

    参数:
        student_logits:        (B, L, |V|) — student forward 输出
        teacher_logits_list:   list of N tensors，每个 (B, L, |V|)
        weights:               list of N 浮点数，加和为 1.0

    返回:
        scalar loss tensor
    """
    student_logp = F.log_softmax(student_logits, dim=-1)
    student_p = student_logp.exp()

    total_loss = 0.0
    for w, t_logits in zip(weights, teacher_logits_list):
        teacher_logp = F.log_softmax(t_logits, dim=-1)
        # 反向 KL: D_KL(π_θ || π_E) = Σ π_θ * (log π_θ - log π_E)
        kl_per_token = (student_p * (student_logp - teacher_logp)).sum(dim=-1)  # (B, L)
        total_loss += w * kl_per_token.mean()
    return total_loss


def opd_train_step(student, teachers, prompts, weights, optimizer, max_new_tokens=256):
    """
    一个 on-policy distillation 训练 step。
    """
    # 1. Student 采样 rollout（no_grad 避免显存爆炸）
    with torch.no_grad():
        rollout_ids = student.generate(prompts, max_new_tokens=max_new_tokens,
                                        do_sample=True, temperature=1.0)

    # 2. Forward pass：student 带梯度计算 logits
    student_logits = student(rollout_ids).logits  # (B, L, |V|)

    # 3. 每个 teacher 给同样的 rollout 打分（不需要梯度）
    with torch.no_grad():
        teacher_logits_list = [t(rollout_ids).logits for t in teachers]

    # 4. 计算 OPD loss 并反向传播
    loss = opd_loss(student_logits, teacher_logits_list, weights)
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(student.parameters(), max_norm=1.0)
    optimizer.step()
    return loss.item()
```

几个实践注意事项：

- **Tokenizer 对齐是必须的**。所有 teacher 和 student 必须用同一个 tokenizer（这样 logits 才能逐 token 比较）。实践中这意味着选同一族的模型（Qwen 2.5/3 系列、Llama 3 系列等）。
- **反向 KL 容易 NaN**。学习率从小开始（5e-7 到 1e-6），用 BF16 mixed precision，gradient clipping 保持在 1.0。
- **Trajectory 长度有讲究**。太短 = 每步蒸馏信号不够。太长 = 显存和时间爆炸。256-512 token 是小规模实验的合理起点。
- **Teacher 的显存**。即使 `no_grad`，多个 teacher 同时放 GPU 也会累积。Ablation 研究可以考虑 CPU offload（`device_map="auto"` + `offload_folder`）。

---


### OPD 代码生态（2026 现实检查）

骨架代码理清了概念，接下来看看目前实际可用的 OPD 训练工具和框架。


DeepSeek 没开源 V4 OPD 训练代码。**截至 2026 年中，没有任何 frontier 模型公司开源完整的 OPD 训练 pipeline。** 真正存在的是一层**第三方开源框架**（HuggingFace TRL、KDFlow、NeMo-RL 等），可以让你自己实现 OPD 风格的训练。

> ⚠️ **OPD 还远不是工业标配实践。** 现实采用情况（2026 年中）：
> - ~90% 的 LLM 微调项目用 **SFT + LoRA**（小模型定制）
> - ~8% 用 SFT + 简单 RLHF
> - ~1.5% 用复杂 RL（PPO/GRPO）
> - **<1% 用 OPD** —— 仅限少数 frontier 实验室
>
> 称 OPD 为"工业标配"会误导读者；"frontier 实验室的后训练新趋势"是更准确的表述。

### 今天就可以 fork 的可用实现

| Repo | URL | Stars | 适合 |
|------|------|:----:|------|
| **HuggingFace TRL `GKDTrainer`** | https://github.com/huggingface/trl | 15.7k | 单 teacher OPD 最快路径（设 `lmbda=1.0, beta=1.0`） |
| **songmzhang/KDFlow** ⭐ | https://github.com/songmzhang/KDFlow | 122 | LLM 蒸馏专用框架，SGLang teacher inference + FSDP2 student training |
| **NVIDIA NeMo-RL** | https://github.com/NVIDIA-NeMo/RL | — | 多教师 + 跨 tokenizer 大规模 |
| **MS-SWIFT (阿里)** | https://github.com/modelscope/ms-swift | 14k | 内置 GKD trainer（`examples/train/rlhf/gkd/`） |
| **OpenRLHF** | https://github.com/OpenRLHF/OpenRLHF | 9.4k | Ray + vLLM + DeepSpeed；reward 函数可定制做 OPD |
| **verl-project/verl** (字节) | https://github.com/verl-project/verl | 21.1k | 大量 OPD 论文 fork verl 作为 base |
| **agentica-project/AReaL** | — | — | OPD over student-sampled trajectories |
| **THUDM/slime（智谱）** | https://github.com/THUDM/slime | — | 统一 RL stack 支持 OPD |

### `GKDTrainer` 到底是什么——大白话

如果上面的表格感觉太抽象，最简单的心智模型是：

> **`GKDTrainer` 是 HuggingFace 的"一键 OPD 训练器"**——你提供学生模型、教师模型、数据集，设两个开关，它帮你搞定一切：学生采样、教师打分、KL loss、反向传播、checkpoint 保存。

只有两个关键开关：

| 参数 | 含义 | OPD 应该设 |
|------|------|:---------:|
| `lmbda` | 学生自己采样 trajectory 的比例（vs 用 teacher 的） | **1.0**（100% on-policy） |
| `beta` | KL 方向（0 = forward KL，1 = reverse KL） | **1.0**（reverse KL） |

最小完整示例：

```python
from trl.experimental.gkd import GKDTrainer, GKDConfig

config = GKDConfig(
    lmbda=1.0,      # 100% on-policy → OPD
    beta=1.0,       # reverse KL → OPD
    output_dir="./output",
    learning_rate=5e-7,
    per_device_train_batch_size=4,
    max_new_tokens=512,
)

trainer = GKDTrainer(
    model="Qwen/Qwen2.5-1.5B-Instruct",          # 学生
    teacher_model="Qwen/Qwen2.5-Math-7B",         # 教师（必须共享 tokenizer！）
    args=config,
    train_dataset=my_dataset,
    processing_class=tokenizer,
)

trainer.train()
```

就这么简单——和 `SFTTrainer` 一样的 API，只多了一个 teacher_model 和两个开关。完整实现（`generalized_jsd_loss` + `training_step`）在 `trl/experimental/gkd/gkd_trainer.py` 里大约 30 行 PyTorch。

GKD 其他配置对应其他蒸馏方法：

| `lmbda` | `beta` | 等价于 |
|:-------:|:------:|---------------|
| 0 | 0 | 经典 SFT 蒸馏（offline + forward KL） |
| 0 | 1 | Sequence-level KD with reverse KL |
| 1 | 0 | On-policy + forward KL（少见） |
| **1** | **1** | **OPD（V4 选择）** |
| 0.5 | 0.5 | 混合模式 |

所以 `GKDTrainer` 覆盖整个蒸馏设计空间——`lmbda=1, beta=1` 只是 OPD 那个角落。

### thunlp/OPD：学术深度版（不是生产框架）

如果想从研究层面研究 OPD 行为，**[thunlp/OPD](https://github.com/thunlp/OPD)** 是 GitHub 上最完整的开源实现（清华 NLP 出品，223 stars，配套论文 [arXiv:2604.13016](https://arxiv.org/abs/2604.13016) "Rethinking On-Policy Distillation"）。

**优势**：
- 学术权威性（清华 NLP，出过 MiniCPM/OpenBMB）
- 论文不是简单复现——识别了 *OPD 何时失败* 并提出恢复策略（off-policy cold start、teacher-aligned prompt selection）
- 提供已发布的 baseline checkpoint（`Qwen3-1.7B-SFT`、`Qwen3-4B-Base-GRPO`）在 HuggingFace 上
- 配置丰富：`LOG_PROB_TOP_K`、`TOP_K_STRATEGY`（`only_stu` / `only_tch` / `intersection` / `union` / `union-intersection`）、`REWARD_WEIGHT_MODE`（`student_p` / `teacher_p` / `none`）—— 适合做 ablation 研究

**注意事项**：
- **硬件门槛高**：实验跑在 8 × NVIDIA A800 80GB GPU（数学领域 SFT + RL + OPD 完整 pipeline）
- **需要两个 conda 环境**：verl（训练）+ LlamaFactory（SFT）
- **公开配置只有单教师**，不是 V4 风格的多教师 OPD
- **默认用 Top-K KL 近似**（`LOG_PROB_TOP_K=16`）—— 不是 V4 论文坚持的全词表 KL
- **核心 OPD loss 藏在他们 fork 的 verl 里**（`verl/trainer/main_ppo.py` + `algorithm.adv_estimator=token_reward_direct`），公开的 `on_policy_distillation.sh` 是配置 shell 不是独立 PyTorch 代码
- README 没标 license（商用前需确认）

**结论**：

| 用例 | 最佳工具 |
|------|---------|
| 一坐下来读完 OPD 代码 | TRL `gkd_trainer.py`（数学部分 ~30 行） |
| 单 GPU 跑 OPD | TRL `GKDTrainer` |
| 复现 OPD 学术结果 + 研究失败模式 | thunlp/OPD（需要 8×A800） |
| 做 V4 风格的多教师 OPD | 都不直接支持——需要 fork TRL 或 KDFlow 加 Σᵢ teacher 循环 |

### Awesome list 与元资源

- **OPD 精选 list**：https://github.com/chrisliu298/awesome-on-policy-distillation （~32 stars，每日更新）—— 包含 ~21 篇核心 OPD 论文 + 13 个训练框架
- **平行 awesome list**：https://github.com/nick7nlp/Awesome-LLM-On-Policy-Distillation
- **最佳概念博客**：https://thinkingmachines.ai/blog/on-policy-distillation/ （Thinking Machines 出品）
- **GOLD 实战教程**（HuggingFace H4，附 TRL 代码）：https://huggingface.co/spaces/HuggingFaceH4/on-policy-distillation
- **OPD Survey 论文**：arXiv 2604.00626 (2026)

> ⚠️ **关于 awesome-list 的提醒**：这些是有用的入口，但不应当作一手来源。我们亲自验证过——一些 awesome-list 流传的"X 模型用了 OPD"声明，读了实际论文后发现是错的（模型名不匹配、方法被错贴标签等）。引用前必须回溯到原始技术报告。

### 工业界使用 OPD 的模型（从原始论文验证）

> ⚠️ **方法说明**：本表只保留了**亲自阅读并验证原始技术报告/论文**中明确提及 OPD 的模型。本 Repo 早期草稿从第三方 awesome-list（[chrisliu298/awesome-on-policy-distillation](https://github.com/chrisliu298/awesome-on-policy-distillation)）复制了更长的清单；后续验证发现模型名错误（如 "GLM-5" 公开不存在，只有 GLM-4.5；"Nemotron-Cascade 2" 不存在，最接近的 Nemotron-Nano-2 用的是 Minitron 风格的 forward KL distillation而非 OPD）。下表是清理后的验证版本。

| 年份 | 模型 | OPD 用法 | 原始来源 |
|------|------|---------|---------|
| 2025 | **Qwen3** | “Strong-to-weak distillation” 结合 off-policy 和 on-policy 知识转移训练小模型 | [arXiv:2505.09388](https://arxiv.org/abs/2505.09388) §1, §4 |
| 2026 | **MiMo-V2-Flash**（小米） | **Multi-Teacher On-Policy Distillation (MOPD)** 作为主要 post-training 阶段；明确表述为"a new paradigm that formulates knowledge distillation as a reinforcement learning process; the student model learns from its own generated responses" | [GitHub README](https://github.com/XiaomiMiMo/MiMo-V2-Flash) §1, §5.1; arXiv 2601.02780 |
| 2026 | **DeepSeek-V4** | "the mixed RL stage was entirely replaced by On-Policy Distillation (OPD)"；多教师蒸馏融合 10+ 领域专家到统一模型 | DeepSeek-V4 Tech Report §5.1 |

**其他被声称使用 OPD 的模型**（Baichuan-M3、GLM-5、Nemotron-Cascade 2、HY-Embodied-0.5 等）要么：(a) 模型名与公开发布不匹配，(b) 原报告使用不同术语不能确认是 OPD，(c) 报告细节不足以确认。在直接验证前从表中排除。

> 截至 2026 年中，开源独立复现 V4 multi-teacher OPD 的窗口期仍然开放。

### 按角色快速起步

| 目标 | 推荐路径 |
|------|---------|
| 快速跑通单教师 OPD | **TRL `GKDTrainer`** + `lmbda=1.0, beta=1.0` |
| 生产级 OPD 框架 | **KDFlow**（LLM 蒸馏专用，文档详细） |
| 多教师 OPD（最贴近 V4） | **NeMo-RL** 或在 KDFlow 上扩展 + 参考 MiMo-V2 MOPD recipe |
| 基于 verl 生态 | **HJSang/OPSD_OnPolicyDistillation** + 自加 multi-teacher 循环 |

---

## OPD 在 V4 系列中的位置

DeepSeek-V4 是一组协调的创新。OPD 扮演特定角色：

| 创新 | 用途 | 详见 |
|------|------|------|
| 长上下文高效 attention（CSA + HCA） | 让 1M-token context 在计算上可行 | [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention) |
| Manifold-Constrained Hyper-Connections (mHC) | 加强深层模型的 residual connections | V4 论文 Section 2.2 |
| Muon Optimizer | 更快收敛 + 训练稳定性 | V4 论文 Section 2.4 |
| FP4 量化感知训练 | 减少训练和推理的内存带宽压力 | V4 论文 Section 3.4 |
| **On-Policy Distillation（本文）** | **把 10+ 个专家融合成单一生产模型** | V4 论文 Section 5.1 |
| Quick Instruction（KV cache 复用做辅助任务） | 减少 chatbot 场景的 TTFT | V4 论文 Section 5.1.1 |

OPD 是**post-training 的收官之作**——把所有用新架构训出的领域专家整合成最终上线模型的方法。

---

## 附录：H100 上的 OPD 验证实验

我们在单张 NVIDIA H100 NVL（95 GB）上跑了一个 OPD 实验，验证 GKD-based OPD 训练流程是否可行，亲眼观察 loss 动态，并测量 OPD 在 GSM8K 上对端任务准确率的提升。

### TL;DR — 诚实结果

我们跑了 6 轮 OPD 训练 + 3 次评测。**没有任何一个 OPD checkpoint 在 GSM8K test[:100] 上击败未蒸馏的 baseline。**

| 对比 | Baseline | OPD | Δ pp |
|------|---------:|----:|-----:|
| Run 5 ckpt-10（greedy，训了 10 步），N=100 | 19.0% | **18.0%** | **−1.0**（CI 重叠） |
| Run 6 ckpt-20（sampling，训了 20 步），N=100 | 19.0% | **0.0%** | **−19.0**（模型坍缩） |

**为什么都没成功**：1.78B 规模 + 单卡 H100 + TRL 1.4.0 GKDTrainer 默认配置下，OPD 不稳定。三种失败模式我们都撞上了：
1. **bf16 NaN in on-policy generation**（Run 2、3、4 — `softmax` 溢出）
2. **Greedy decoding 导致梯度爆炸**（Run 5 — 15 步后 `grad_norm=NaN`）
3. **Reverse-KL mode collapse**（Run 6 — 即使 loss 0.5165 看起来健康，学生也输出 `!!!!!!` × 200）

我们从这条 trail 上提取到的：每一轮失败的清晰法医分析，以及生产级 OPD（DeepSeek-V4）必须工程化掉的内容 — KL 锚、fp32 logit matmul、大 batch、谨慎 warmup。Loss 曲线本身从未告诉我们真相；只有端任务评测才揭穿了 collapse。

完整法医分析见下面 [bf16 NaN 调查](#bf16-nan-调查--法医取证全过程) 和 [Run 6 为什么失败](#run-6-为什么失败--reverse-kl--mode-collapse--没修对的-hook) 章节。

### 实验配置

| 项 | 值 |
|-------|-------|
| GPU | NVIDIA H100 NVL，95 GB VRAM |
| Student | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B`（1.78B 参数） |
| Teacher | `hbx/JustRL-DeepSeek-1.5B`（1.78B 参数，thunlp/OPD 验证过的配对） |
| 数据集 | GSM8K train split，500 samples |
| 框架 | HuggingFace TRL 1.4.0 `GKDTrainer`（experimental） |
| PyTorch | 2.11.0+cu130，bf16 混合精度 |
| GKD 配置 | `lmbda=1.0`（100% on-policy），`beta=1.0`（reverse KL）= 纯 OPD |
| 训练参数 | lr=1e-6，batch=1，grad_accum=8，1 epoch → 63 步 |
| 评测 | GSM8K test[:30]，greedy decoding（do_sample=False），max_new_tokens=512 |

为什么选这对模型？thunlp/OPD 论文（arXiv:2604.13016）验证过从 `JustRL-DeepSeek-1.5B`（reasoning RL checkpoint）蒸馏到 base `DeepSeek-R1-Distill-Qwen-1.5B` 能提升 GSM8K 准确率。我们沿用他们的 student-teacher 配对。

### 5 轮训练，3 种失败模式 — 真实的工程故事

我们用同一个训练脚本跑了 5 轮，每次都改进。失败日志本身就很有价值：

| Run | 跑到 | 失败原因 | 之后改了什么 |
|-----|------|---------|-------------|
| 1 | step 23/63 | Azure 内核升级强制重启 VM | （脚本未变） |
| 2 | step 3/63 | bf16 NaN（on-policy `softmax`） | 给 `model.generation_config` 加 `top_k=50, top_p=0.95` |
| 3 | step 17/63 | bf16 NaN 又来（top-k 不够） | 改用 `do_sample=False`（在 `model.generation_config` 上） |
| 4 | step 38/63 | bf16 NaN 又来 — patch 根本没生效 | **追查 TRL 源码** |
| 5 | step 15（梯度爆炸 → loss=0） | greedy decoding 导致梯度不稳定 | killed；**但 checkpoint-10 保住了，能用** |

### 训练 Loss 动态

各轮可用数据：

| Step | Run 1 Loss | Run 3 Loss | Run 4 Loss | Run 5 Loss | LR |
|:----:|:----------:|:----------:|:----------:|:----------:|:----------:|
| 5 | 0.5337 | 0.5246 | 0.5788 | 0.4375 | 9.365e-07 |
| 10 | 0.6157 | 0.5961 | 0.5744 | **0.4858** ← **最佳 ckpt** | 8.571e-07 |
| 15 | 0.6218 | 0.5573 | — | 1.701（NaN grad） | 7.778e-07 |
| 20 | 0.5715 | — | — | 0.0（已死） | 6.984e-07 |
| 25 | — | — | 0.6239 | — | 6.190e-07 |
| 30 | — | — | 0.6444 | — | 5.397e-07 |
| 35 | — | — | **0.4863** | — | 4.603e-07 |

**观察：**

1. **Loss 起步 0.43-0.58**（取决于 random seed 和 decoding 方式）— student 和 teacher 之间的初始 reverse KL。合理，因为两者共享 Qwen2 架构。

2. **采样型 run（1、3、4）展现了经典 OPD 模式**：loss 在前 15 步升至 0.60-0.65（student 探索发散区域），然后回落至 0.50 以下（学会对齐）。Run 4 跑到了最低采样 loss 0.4863（step 35）。

3. **Greedy run（5）初期收敛更快**（step 10 即 loss 0.4858）— 但 greedy decoding 让梯度失去 on-policy KL 隐式依赖的噪声，step 15 就梯度爆炸了。

4. **采样路径的跨 run 一致性** — Run 1 和 3 的 loss 轨迹几乎相同（差异 <5%），证明 OPD 可复现。

<div align="center"><img src="images/opd_loss_curve.png" width="720"></div>

### bf16 NaN 调查 — 法医取证全过程

这是最难啃的一块。三轮连崩，都是同一个错误，每次都"打了 patch"。

**症状（Runs 2、3、4）：**
```
/pytorch/aten/src/ATen/native/cuda/TensorCompare.cu:109:
Assertion `probability tensor contains either `inf`, `nan` or element < 0` failed.
torch.AcceleratorError: CUDA error: device-side assert triggered
```

崩溃发生在 transformers generation 的 `_sample()` — bf16 logits 溢出 → softmax 出 NaN/Inf → multinomial 采样 assert。

**尝试修复（Runs 3、4）：**
```python
# trainer 初始化后
trainer.model.generation_config.top_k = 50
trainer.model.generation_config.top_p = 0.95
trainer.model.generation_config.do_sample = False  # Run 4
```

**为什么没生效** — 读 TRL 源码才发现：

```python
# trl/experimental/gkd/gkd_trainer.py 第 439 行
unwrap_model_for_generation(
    model, self.accelerator,
    generation_kwargs=self.generation_kwargs,  # Override model.generation_config with generation_kwargs to fix transformers#42762
)
```

**TRL 故意忽略 `model.generation_config`，用自己的 `self.generation_kwargs` dict（在 `GKDTrainer.__init__` 中构建）。** 改 `model.generation_config` 是静默 no-op。TRL 维护者特意加了这个 override 就是为了绕过 `transformers#42762`（也就是我们撞上的同一个 bf16 NaN bug）。

**实际有效的修复（Run 5）：**
```python
# trainer 初始化后，改 TRL 实际用的那个 dict
trainer.generation_kwargs["do_sample"] = False
trainer.generation_kwargs["temperature"] = 1.0
trainer.generation_kwargs["top_k"] = 0
from transformers import GenerationConfig
trainer.generation_config = GenerationConfig(**trainer.generation_kwargs)
```

这次成功了 — Run 5 干净通过 step 17。但 greedy on-policy generation 又带来了新问题：没有采样噪声，step 15 时梯度爆炸（`grad_norm=NaN`，loss 卡在 0）。**Greedy decoding 不是 on-policy distillation 的免费午餐。**

**教训：**
1. 读框架源码。`trainer.model.generation_config` 和 `trainer.generation_kwargs` 看起来可互换，其实不是。
2. bf16 + 采样会 NaN。bf16 + greedy 会梯度爆炸。最稳妥的答案是 generation 时用 fp32 logits，而不是改 decoding 策略。
3. `save_steps=10`（不是默认 100）在你还没充分信任训练流程时是必须的。

### 端任务评测 — 诚实的现实检验

**更新（跑完更大评测后）：原来的 "+6.67pp" 结果是测量假象。**

我们最初用 `Run 5 checkpoint-10` 在 `GSM8K test[:30]` 上对比 baseline，看到 2 倍提升（6.67% → 13.33%）。但修复了答案抽取器的小 bug（`460.` 与 `460` 不匹配）+ 把 N 扩到 100 后，画面完全变了：

| 对比 | Baseline | OPD | Δ pp | 95% Wilson CI 重叠？ |
|------|---------:|----:|-----:|:-------------------:|
| N=30，buggy 抽取器（初版） | 6.67% | 13.33% | +6.67 | 是 — 重叠 |
| **N=100，修过 bug（Run 5 ckpt-10）** | **19.0%** | **18.0%** | **−1.0** | **完全重叠** |
| **N=100，修过 bug（Run 6 ckpt-20）** | **19.0%** | **0.0%** | **−19.0** | **OPD 模型坍缩** |

**Run 5 ckpt-10**：用 greedy on-policy generation 训了 10 步。看了 80 个样本后，学生的 GSM8K 准确率与 baseline 在统计上无差异 — 既没好也没坏。10 步 OPD 根本不够。

**Run 6 ckpt-20**：用 sampling on-policy generation 训了 20 步。训练 loss 降到 0.5165（我们观察到的最低值）。但评测时模型对每道题都输出 **`!!!!!!!!...`** 重复 200 个 token。**Policy 坍缩。** "好 loss" 是误导。

### Run 6 为什么失败 — Reverse KL + Mode Collapse + 没修对的 hook

两种失败模式叠加：

**1. Reverse-KL 陷阱**

OPD 在 student 生成的轨迹上最小化 $\text{KL}(\pi_{\text{student}} \| \pi_{\text{teacher}})$。Reverse KL 是 **mode-seeking**：学生只要找到 **任何一个** teacher 给非零概率的 token 就被奖励。存在退化解 — 永远输出一个 token，只要 teacher 在某处给那个 token > 0 概率。在小 batch（batch=1, grad_accum=8）+ 看似保守实际不够保守的 lr（5e-7）下，学生找到了这个陷阱。

从训练 loss 看不出来这个坍缩。Loss 0.5165 看起来很健康。只有端任务评测才暴露 `!!!!!!`。

**2. 我们的 fp32 修复根本没让 matmul 在 fp32 跑**

为防止 bf16 logit 溢出，我们给 `lm_head` 加了 forward hook：

```python
def upcast_to_fp32(module, input, output):
    return output.float()
hook = trainer.model.lm_head.register_forward_hook(upcast_to_fp32)
```

这**看起来对**但其实错了。Forward hook 在 module 计算完输出**之后**运行。所以实际流程是：

```
hidden_states (bf16) ──▶ lm_head matmul (在 bf16 里算！) ──▶ logits (bf16，可能已经是 inf) ──▶ .float() = fp32 NaN
                                  ▲
                            溢出发生在这里，hook 之前
```

我们在伤害发生之后用 fp32 "保存"了结果。要防溢出，matmul 本身必须在 fp32 跑。正确的修复方法之一：

```python
# 方案 A：lm_head 权重整体转 fp32（最干净）
trainer.model.lm_head = trainer.model.lm_head.float()

# 方案 B：用 forward_pre_hook 在 matmul 前升级输入
def upcast_input(module, args):
    return tuple(x.float() if hasattr(x, 'dtype') and x.dtype == torch.bfloat16 else x
                 for x in args)
trainer.model.lm_head.register_forward_pre_hook(upcast_input)
```

我们没察觉，是因为我们验证了 hook **注册成功**（打印了 "fp32 hook attached"），但从未验证中间 logits 是否真的变成 fp32 了。**症状消失 ≠ 修复生效。**

### 我们学到了什么

1. **Loss 曲线会骗人。** Reverse-KL 训练可以 loss 下降但模型变废。端任务评测不可省略。

2. **Mode collapse 是 OPD 特有的失败模式**，不是通用 bug。它直接来自 reverse-KL 目标。生产级 OPD 实现需要：reference model 的 KL 锚、梯度裁剪、fp32 logits、大 batch（噪声平均掉容易引发坍缩的梯度）。

3. **TRL GKDTrainer 有内部状态会覆盖你天真打的 patch。** `trainer.model.generation_config` 看起来是改 generation 的入口，但 TRL 用的是 `self.generation_kwargs`。读框架源码。

4. **bf16 + on-policy 采样是结构性地雷。** `top_k`/`top_p` 降低 NaN 概率但不消除。换 greedy 避免 softmax NaN，但带来梯度不稳定。真正的修复是 fp32 logits 计算 — **而且必须验证 matmul 在 fp32 跑，不只是 matmul 后的 tensor**。

5. **`save_steps=10`（不是默认 100）在调试时极重要。** 降 `save_steps` 之前的四次崩溃全部丢失了训练状态，因为默认 100 > 实际存活步数（17-38）。降到 10 才救回了能评测的 checkpoint。

6. **生产级 OPD 是另一个量级。** 我们的 1.78B × 1.78B 配置在 500 个样本上要 36 GB + ~70 分钟/epoch。DeepSeek-V4 的 671B × 10+ teachers 在完整规模下需要数千 GPU-hours，加稀疏 top-K logit 存储、分布式 teacher 服务，外加我们这次撞到的所有失败模式背后的稳定性基础设施（KL 锚、精心 warmup、大 batch）。架构能迁移；工程难度差几个数量级。

### 实验脚本

- [`scripts/run_opd.py`](scripts/run_opd.py) — 主 OPD 训练循环（Run 5 / Run 6 版本）
- [`scripts/eval_opd.py`](scripts/eval_opd.py) — N 样本 GSM8K 评测，含 Wilson 95% CI
- [`scripts/generate_loss_curve.py`](scripts/generate_loss_curve.py) — 重新生成 loss/accuracy 图
- [`data/experiment_results.json`](data/experiment_results.json) — 所有 loss 值和评测结果

### 状态

**Phase 1（基础设施验证）：完成。** OPD 训练循环在 H100 + TRL 1.4.0 上能跑。Loss 动态符合 reverse-KL 理论。多个失败模式已根因定位（TRL `generation_kwargs` override；bf16 NaN；无效的 forward-hook fp32 修复；reverse-KL mode collapse）。

**Phase 2（端任务验证）：阴性 / 零结果。** 6 轮训练没有任何 checkpoint 在 GSM8K 上击败未蒸馏的 baseline。Run 5 ckpt-10 与 baseline 在统计上无差异（N=100 上 −1pp）；Run 6 ckpt-20 坍缩到单 token 输出。**1.78B 规模 + 单卡 H100 + TRL 默认配置的 OPD 不是免费的胜利** — 它需要 DeepSeek-V4 默默工程化掉的稳定性基础设施（KL 锚、matmul 自身的 fp32 logits、大 batch）。

**我们还没做的（需要再迭代一轮）：**
- 把 `lm_head` 权重转 fp32（matmul 溢出的真正修复）
- 加 KL 锚约束学生不离原始模型太远，防止 mode collapse
- lr 降到 1e-7 + warmup
- 加上以上保护重训并重测

5 次失败的 run + ckpt-10 那次"部分阳性"以上面完整工程轨迹的形式被记录下来。**本 Repo 的目标是讲清楚 OPD 在 V4 论文里如何工作。验证实验展示了"GKDTrainer 默认配置"不等于 V4 用的生产级 OPD，并具体指出缺了什么。**

---

## 参考文献

- DeepSeek-AI. (2026). *DeepSeek-V4: Towards Highly Efficient Million-Token Context Intelligence*. Technical Report. [PDF](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf) — Section 5.1（Post-Training Pipeline）和 Section 5.2（RL and OPD Infrastructures）
- Hinton, G., Vinyals, O., & Dean, J. (2015). *Distilling the Knowledge in a Neural Network*. arXiv:1503.02531
- Agarwal, R. et al. (2023). *GKD: Generalized Knowledge Distillation for Auto-regressive Sequence Models*. arXiv:2306.13649（首次为 LLM 形式化 on-policy distillation）
- Shao, Z. et al. (2026). *On-Policy Distillation of Language Models: Learning from Self-Generated Mistakes*. arXiv:2604.13016（thunlp/OPD — 本实验使用的学术 OPD 实现）
- Yadav, P. et al. (2023). *TIES-Merging: Resolving Interference When Merging Models*. arXiv:2306.01708（带符号选举的 task arithmetic）
- Yu, L. et al. (2024). *Language Models are Super Mario: Absorbing Abilities from Homologous Models via DARE*. arXiv:2311.03099
- 配套阅读：[Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention)（V4 的 CSA+HCA attention 机制）
- 前置知识：[KV-Cache-Deep-Dive](https://github.com/david-xinyuwei/david-share/tree/master/Deep-Learning/KV-Cache-Deep-Dive)（Transformer 基础、KV Cache、MoE 架构图）
- 关联阅读：[LoRA-Merge-Quality-Impact](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/LoRA-Merge-Quality-Impact)（量化参数空间合并的退化）

---

## 项目信息

| 项 | 值 |
|----|----|
| Author | 魏新宇 (Xinyu Wei) |
| 日期 | 2026-05 |
| 状态 | **理论深度解读 + H100 部分实验**（见附录） |
| 来源 | DeepSeek-V4 Technical Report（Section 5.1、5.2） |
| 配套 | [Long-Context-Efficient-Attention](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights/Long-Context-Efficient-Attention)（V4 系列） |

*本文是 [DL-Algorithm-Insights](https://github.com/david-xinyuwei/david-share/tree/master/DL-Algorithm-Insights) 系列的一部分——用论文为基础的分析（在适用时）配合真实 GPU 实验来解释深度学习算法。*
