# LLM 数学推理的强化学习方法：从规则奖励到自验证证明

> 一篇由浅入深的技术科普与分析报告：用"剧组"类比理解 RLHF/GRPO 的角色分工，并对比 DeepSeek-R1（可验证奖励）与 DeepSeekMath-V2（自验证证明）的训练架构。

---

## 🎯 写作目标

- 解释：LLM 在数学推理中为何"规则奖励"与"LLM-as-Judge"会并存
- 讲清：Actor / Reward / Reference / Critic(Value) 在 RLHF 中分别干什么、会不会训练、为什么需要
- 给出：DeepSeek-R1 与 DeepSeekMath-V2 的训练架构与关键算法（含图）
- 对比：何时该用可验证奖励，何时必须训练 verifier

---

## 🎭 第一章：用"剧组"理解强化学习中的角色（最重要的直觉）

先把"训练里谁是谁"讲清楚，后面所有论文细节才不会绕。

### 1.1 PPO/RLHF：一个需要"四个角色"的剧组

| 组件 | 剧组类比 | 一句话职责 | 是否在训练中更新参数？ |
|---|---|---|---|
| **Actor (policy)** | 🎬 演员 | 负责"表演"——生成回答 | ✅ 会训练 |
| **Reward Model (RM)** | 👨‍⚖️ 评委 | 给表演打分（偏好/质量） | ✅ 先训练好；PPO 阶段通常冻结 |
| **Reference Model** | 📜 原剧本 | 防止演员为了高分"演变形"（KL 约束） | ❌ 冻结 |
| **Critic / Value Model** | 🎓 陪练教练 | 一边陪练、一边学习"这段表演大概能拿几分" | ✅ 会训练（与 Actor 同步） |

#### 训练信号怎么流动？（PPO 架构图）

```text
Prompt x
  │
  ▼
┌───────────────┐        ┌──────────────────┐
│ Actor πθ      │        │ Reference πref   │
│ (演) 生成 y   │        │ (原剧本)         │
└──────┬────────┘        └───────┬──────────┘
       │                          │
       │ logπθ(y|x)               │ logπref(y|x)
       │                          │
       ▼                          ▼
   ┌──────────────────────────────────────────┐
   │ KL Penalty:   -β · (logπθ - logπref)     │
   └──────────────────────────────────────────┘
                  │
                  │ 生成的 (x, y)
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
┌───────────────┐     ┌───────────────┐
│ Reward Model  │     │ Critic Vψ     │
│ r = RM(x,y)   │     │ v = Vψ(x)     │
│ (评委打分)     │     │ (教练估分)     │
└──────┬────────┘     └──────┬────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
           Advantage A = r - v
                  │
                  ├──> 更新 Actor θ（让高 A 的行为更常出现）
                  └──> 更新 Critic ψ（让 v 更接近 r）
```

**关键点**：Reward Model 和 Critic 是**并行计算**的，都基于生成的 (x, y)，然后一起算 Advantage。

#### 为什么 Critic 要"一起训练"？

- Actor 在变强（政策分布在变），回报分布也在变
- Critic 如果不跟着学，它对"能拿几分"的预测会越来越不准
- Critic 越准，Actor 更新越稳（方差更小）

> 这就是我把 Critic 类比成"陪练教练"的原因：它不是旁观者，它要不断校准自己。

### 1.2 GRPO：把"教练"拿掉，用"组内对比"当 baseline

DeepSeek-R1/DeepSeekMath-V2 都强调 **GRPO**。直觉上：

- PPO 需要 Critic 估 baseline
- GRPO 直接对同一个 prompt 采样一组回答，用 **组内相对表现** 作为 baseline，因此不必单独训练 Critic

#### GRPO 更新的直觉（伪代码）

```text
给定 prompt x:
  1) 从 Actor 采样 K 个回答 y1..yK
  2) 为每个回答算 reward: r1..rK
  3) 计算组内 baseline（例如平均值 r̄）
  4) 对每个样本用 (ri - r̄) 做权重更新 Actor
  5) 仍可加 KL(Actor || Reference) 约束
```

可视化：

```text
同一题 x
  ├─ y1 → r1
  ├─ y2 → r2
  ├─ y3 → r3
  └─ yK → rK

组内 baseline r̄ = mean(r)
优势项: Ai = ri - r̄
```

---

## 🧠 第二章：数学推理的两类任务，决定了两类奖励

### 2.1 "填空题" vs "证明题"

| 任务类型 | 典型竞赛 | 输出 | 验证难度 | 适合的 reward |
|---|---|---|---|---|
| **可验证最终答案** | AIME/HMMT 等 | 一个数 / 一个选项 | ✅ 极低 | 规则奖励（exact match / unit tests） |
| **证明/推理过程** | IMO/Putnam | 长证明链 | ❌ 极高 | 训练 verifier（LLM-as-Judge） |

**核心矛盾**（论文原话）：

> *"Pursuing higher final answer accuracy doesn't address a key issue: correct answers don't guarantee correct reasoning."*

直觉：
- 填空题：reward 是"对/错"
- 证明题：reward 是"严谨度/完整性/是否存在致命漏洞"

---

## 🔧 第三章：DeepSeek-R1——"可验证奖励"如何把推理能力拉起来

> 要点：R1 在数学/代码任务上大量使用 **规则奖励**（可验证），在通用任务上才引入更主观的模型打分。

### 3.1 R1 的"规则 reward"长啥样？

```python
def rule_reward(answer, ground_truth):
    # 1) format reward（例如必须包含 \boxed{}）
    if not has_boxed(answer):
        return 0.0

    # 2) accuracy reward（严格比对）
    return 1.0 if extract_boxed(answer) == ground_truth else 0.0
```

### 3.2 规则奖励的工程优势

- **可靠**：几乎无噪声
- **便宜**：不用调用额外 LLM
- **可规模化**：可跑大量 rollout
- **抗 reward hacking**：对齐目标清晰

### 3.3 但它的天花板也很明确

- correct final answer ≠ correct reasoning
- 对证明题根本不适用（没有"唯一可判定"的 ground truth）

---

## 🔬 第四章：DeepSeekMath-V2——"自验证证明"训练架构（含 meta-verification）

这一部分来自 DeepSeekMath-V2 论文（已在本机 `DeepSeekMath_V2.pdf` 中核对）。

### 4.1 Verifier：先训练"评委"会抓问题、会打分

Verifier 的目标（论文 2.1.1）：对给定问题 X 和证明 Y，输出分析 + 分数 $s \in \{0, 0.5, 1\}$。

**评分标准**（三档制）：
- **1 分**：完全正确，所有步骤严谨清晰
- **0.5 分**：整体逻辑正确，但有细节遗漏或小错误
- **0 分**：存在致命逻辑错误或严重缺口

**Verifier 的 RL 奖励**（论文公式）：
- $R_{format}$：检查输出有没有按要求包含"评价 + boxed 分数"
- $R_{score}(s', s) = 1 - |s' - s|$：预测分数与专家标注分数的距离

### 4.2 Meta-Verifier：专门防止"评委瞎编问题"

论文 2.1.2 的关键洞察：

> *"When evaluating flawed proofs during training, the verifier can receive full reward by predicting the correct scores while hallucinating non-existent issues, undermining its trustworthiness."*

问题：Verifier 如果只被监督"分数对不对"，可能用"胡编的漏洞"来解释低分。

**解决方案**：引入 meta-verification，让另一个模型去审查 verifier 的分析是否**真实、合理、足以支撑该分数**。

**增强后的 Verifier reward**（论文公式）：

$$R_V = R_{format} \cdot R_{score} \cdot R_{meta}$$

其中 $R_{meta}$ 来自 meta-verifier 对"评审文本"的质量打分。

**效果**：验证分析的质量分数从 **0.85 提升到 0.96**，同时保持分数预测准确率不变。

#### 两层验证架构图（Proof → Verifier → Meta-Verifier）

```text
Problem X + Proof Y
        │
        ▼
┌───────────────────────┐
│ Verifier πφ           │
│ - 找漏洞/缺口          │
│ - 解释为什么扣分        │
│ - 输出 score s∈{0,0.5,1}│
└───────────┬───────────┘
            │ (当 s 不高时更值得复核)
            ▼
┌───────────────────────┐
│ Meta-Verifier πη       │
│ - 审查"评审文本"是否真实│
│ - 审查扣分理由是否成立  │
│ - 输出质量分 ms∈{0,0.5,1}│
└───────────┬───────────┘
            ▼
最终用于训练/筛选的可信评审
```

### 4.3 Generator：从 Verifier checkpoint 初始化，再学"写证明 + 自评"

论文 2.2.2 的关键做法：
- Generator 输出两段：证明 $Y$ + 自我评估 $Z$
- 让 Verifier 给证明打分，同时对自评进行 meta-verification

**奖励函数**（论文给了系数）：

$$R = R_{format}(Y,Z) \cdot (\alpha \cdot R_Y + \beta \cdot R_Z)$$

其中（直觉解释）：
- $R_Y$：证明是否真的好
- $R_Z$：你自评是不是诚实、准确（需要 verifier + meta-verifier 来检查）
- 论文设置 $\alpha = 0.76, \beta = 0.24$

**激励机制**（论文原话）：
- *"Faithful acknowledgment of errors is rewarded over false claims of correctness."*
- *"A good strategy to obtain high rewards is to identify and resolve as many issues as possible before finalizing the response."*

#### "自验证证明"闭环图（生成→自评→外部验证→训练信号）

```text
Prompt X
  │
  ▼
┌───────────────────────────────┐
│ Generator πθ                   │
│ 生成: Proof Y + Self-Review Z  │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Verifier πφ                    │
│ 对 Proof Y 打分: s             │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Meta-Verifier πη               │
│ 审查 Self-Review Z 的诚实性/质量 │
└───────────────┬───────────────┘
                ▼
Reward R = α·(proof score) + β·(self-review fidelity)
```

### 4.4 Verification-Generation 协同进化

论文 Section 2.3 描述的**自动化闭环**是最大亮点：

1. **Verifier → Generator**：用 verifier 作为 reward model 训练 generator
2. **Generator → Verifier**：generator 变强后产生更难验证的证明，挑战 verifier
3. **自动标注**：对每个证明生成 n 个验证分析，用 meta-verification 筛选，自动标注难题

```text
For each proof:
  1) Generate n independent verification analyses
  2) For analyses with score 0 or 0.5:
     - Generate m meta-verification assessments
     - Valid if majority confirms findings
  3) If ≥k valid analyses give lowest score → label with that score
  4) If no legitimate issues → label with 1
  5) Otherwise → discard or route to human
```

> **在最后两轮训练迭代中，全自动流程完全替代了人工标注。**

### 4.5 推理时：一个模型，疯狂的推理开销

**关键发现**：论文明确说 —— 

> "All experiments used a **single model**, our final proof generator, which performs **both proof generation and verification**."

**不是两个模型权重，是一个模型通过 prompt 切换角色！**

```text
┌─────────────────────────────────────────────────────────────────────┐
│              推理时：单模型 + Prompt 角色切换                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  同一个模型权重 πθ                                                   │
│      │                                                              │
│      ├── Prompt A (Generation) ──► 生成证明 Y + 自评 Z               │
│      │                                                              │
│      └── Prompt B (Verification) ─► 验证别人的证明（majority voting） │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**但代价是什么？看看论文的推理配置：**

| 配置项 | 数值 | 说明 |
|--------|------|------|
| 初始证明样本 | **64** | 每个问题生成 64 个候选证明 |
| 验证分析/证明 | **64** | 每个证明要跑 64 次验证 |
| 并行线程 | **32** | Best@32 选择 |
| 迭代改进轮数 | **最多 16** | refinement iterations |
| 每轮改进 | **64 个证明 × 8 个分析** | 选最高分的配对 |

**推理开销估算**（单个 IMO 问题）：
```
初始: 64 proofs × 64 verifications = 4,096 次推理
迭代: 16 rounds × 64 pairs = 1,024 次 refinement
总计: ~5,000+ 次模型调用/问题
```

**这就是 "scaling test-time compute" 的真正含义！**

论文原文："By scaling test-time compute under verifier guidance, our model solves problems that **require hours of effort from human competitors**."

**所以这不是省时间的方案，是"用算力换准确率"：**
- ✅ **优点**：只需要一个模型权重，部署简单
- ❌ **缺点**：推理开销巨大，适合离线竞赛场景
- 🎯 **适用**：IMO/CMO/Putnam 这种"给你几小时做一题"的场景


---

## 📝 第五章：核心 Prompt 模板（论文精华）

### 5.1 Proof Generation Prompt（完整版）

这个 prompt 让模型**生成证明 + 自评**，是实现"自验证"的关键：

```text
Your task is to solve a given problem. The problem may ask you to 
prove a statement, or ask for an answer. If finding an answer is 
required, you should come up with the answer, and your final solution 
should also be a rigorous proof of that answer being valid.

Your final solution to the problem should be exceptionally comprehensive 
and easy-to-follow, which will be rated according to the following 
evaluation instruction:

'''
Here is the instruction to evaluate the quality of a solution to a problem. 
The problem may ask for a proof of statement, or ask for an answer. If 
finding an answer is required, the solution should present the answer, 
and it should also be a rigorous proof of that answer being valid.

Please evaluate the solution and score it according to the following criteria:
- If the solution is completely correct, with all steps executed properly 
  and clearly demonstrated, then the score is 1
- If the solution is generally correct, but with some details omitted or 
  minor errors, then the score is 0.5
- If the solution does not actually address the required problem, contains 
  fatal errors, or has severe omissions, then the score is 0

Additionally, referencing anything from any paper does not save the need 
to prove the reference. It's okay IF AND ONLY IF the solution also presents 
a valid proof of the reference argument(s); otherwise, if the solution 
omits the proof or if the proof provided is not completely correct, the 
solution should be scored according to the criteria above, and definitely 
not with a score of 1
'''

In fact, you already have the ability to rate your solution yourself, 
so you are expected to reason carefully about how to solve a given problem, 
evaluate your method according to the instruction, and refine your solution 
by fixing issues identified until you can make no further progress.

In your final response, you should present a detailed solution to the 
problem followed by your evaluation of that solution.

- To give a good final response, you should try your best to locate 
  potential issues in your own (partial) solution according to the 
  evaluation instruction above, and fix them as many as you can.
- A good final response should just faithfully present your progress, 
  including the best solution you can give, as well as a faithful 
  evaluation of that solution.
- Only when you fail to locate any issues in your solution should you 
  score it with 1.
- If you do notice some issues in your solution but fail to resolve them 
  with your best efforts, it's totally ok to faithfully present the issues 
  in your final response.
- The worst final response would provide a wrong solution but lie that 
  it's correct or claim that it's correct without careful error checking. 
  A better version should faithfully identify errors in the solution. 
  Remember! You CAN'T cheat! If you cheat, we will know, and you will 
  be penalized!

Your final response should be in the following format:

## Solution
... // Your final solution to the problem here. You should try your best 
to optimize the quality of your solution according to the evaluation 
instruction above before finalizing it here.

## Self Evaluation
Here is my evaluation of the solution:
... // Your evaluation here. You are required to present in detail the 
key steps of the solution or the steps for which you had doubts regarding 
their correctness, and explicitly analyze whether each step is accurate.

Based on my evaluation, the final overall score should be: \boxed{...}

--
Here is your task input:
## Problem
{question}
```

**关键设计**：
- 明确告诉模型"你有能力自评"（In fact, you already have the ability...）
- 强调诚实："The worst final response would provide a wrong solution but lie..."
- 威慑作弊："Remember! You CAN'T cheat! If you cheat, we will know, and you will be penalized!"

### 5.2 Proof Verification Prompt（完整版）

```text
## Instruction
Your task is to evaluate the quality of a solution to a problem. The 
problem may ask for a proof of statement, or ask for an answer. If 
finding an answer is required, the solution should present the answer, 
and it should also be a rigorous proof of that answer being valid.

Please evaluate the solution and score it according to the following criteria:
- If the solution is completely correct, with all steps executed properly 
  and clearly demonstrated, then the score is 1
- If the solution is generally correct, but with some details omitted or 
  minor errors, then the score is 0.5
- If the solution does not actually address the required problem, contains 
  fatal errors, or has severe omissions, then the score is 0

Additionally, referencing anything from any paper does not save the need 
to prove the reference. It's okay IF AND ONLY IF the solution also presents 
a valid proof of the reference argument(s).

Your response format:
Here is my evaluation of the solution:
... // Present key steps, analyze correctness, explain errors if any

Based on my evaluation, the final overall score should be: \boxed{...}

--
Here is your task input:
## Problem
{question}

## Solution
{proof}
```

### 5.3 Meta-Verification Prompt（完整版）

```text
You are given a "problem", "solution", and "solution evaluation", 
and you need to assess whether this "solution evaluation" is reasonable.

Your task is to analyze the "solution evaluation" from these aspects:

1. Step Restatement: Check whether the "solution" actually has the behaviors 
   mentioned in the "solution evaluation"

2. Defect Analysis (MOST IMPORTANT): Check whether the errors or defects 
   pointed out are reasonable
   - For each defect found, analyze:
     a) whether this defect actually exists
     b) whether the analysis of this defect is accurate
   - Note: positive components (claims of correctness) are NOT in your scope

3. Expression Analysis: Whether expressions are accurate

4. Score Analysis: Whether the final score matches the defects found

Importantly: If the "solution evaluation" believes the "solution" is completely 
accurate and has not found any errors, then regardless of whether the "solution" 
itself is actually accurate, you should still consider its analysis reasonable.
```

**设计精妙之处**：
- Meta-verifier **只审查"找出的问题"是否真实**，不审查"声称正确"的部分
- 这避免了无限递归审查的问题

---

## 📊 第六章：实验结果

### 6.1 各类别证明能力对比

![Figure 1: CNML-Level 各类别得分](images/figure1-cnml-scores.png)

*DeepSeekMath-V2 在代数、几何、数论、组合、不等式五类上均超过 GPT-5-Thinking-High 和 Gemini 2.5 Pro。*

### 6.2 迭代改进效果 & ProofBench 结果

![Figure 2-3: 迭代改进与 ProofBench](images/figure2-3-refinement-proofbench.png)

**关键发现**：
- Pass@1 随迭代次数显著提升
- Best@32（自评选出的最佳）远高于平均，说明模型能准确区分证明质量
- 在 IMO-ProofBench Basic 集上超过 DeepMind 的 DeepThink (IMO Gold)

### 6.3 竞赛成绩

| 竞赛 | 完全解决 | 得分率 |
|---|---|---|
| **IMO 2025** | P1, P2, P3, P4, P5 | **83.3%** 🥇 |
| **CMO 2024** | P1, P2, P4, P5, P6 | **73.8%** 🥇 |
| **Putnam 2024** | 11/12 题 | **98.3%** (118/120，超人类最高分90) |

---

## 📐 第七章：对比与选型建议

### 7.1 什么时候用规则 reward？什么时候训练 verifier？

| 场景 | 推荐 | 原因 |
|---|---|---|
| 有标准答案/可执行验证（数学结果、单测） | 规则 reward | 便宜、可靠、可规模化 |
| 需要评估推理过程（证明、审稿、复杂推理） | 训练 verifier | 只能靠语义判断 |
| 担心 verifier 幻觉/胡编 | 加 meta-verification | 提升"评审文本"的可信度 |
| 需要模型迭代改进自己的输出 | 训练 self-verification | 让模型"知道"自己的 reward function |

### 7.2 DeepSeek-R1 vs DeepSeekMath-V2 总结

| 维度 | DeepSeek-R1 | DeepSeekMath-V2 |
|---|---|---|
| **目标任务** | 通用推理（数学/代码/通用） | 数学证明（定理证明） |
| **主要 reward** | 规则奖励（final answer match） | 训练 verifier + meta-verifier |
| **能否评估推理过程** | ❌ 只看最终答案 | ✅ 可评估证明严谨性 |
| **自验证能力** | ❌ | ✅ 可自评并迭代改进 |
| **代表竞赛** | AIME, HMMT | IMO, CMO, Putnam |

---

## ⚠️ 局限性

- **训练代码与数据未开源**：论文描述可复现"思路"，但很难复现"同等效果"
- **proof verifier 评估依然是概率式**：需要多样本/投票/复核策略降低误判
- **最难的 IMO 级别问题仍具挑战性**：论文承认 *"the hardest IMO-level problems remain challenging for our model"*

---

## 🔄 第八章：三种 RL 训练方案对比

除了 DeepSeekMath-V2 论文中的方法，实际工程中还有两种主流方案：**Agent Lightning**（本地训练）和 **Azure RFT**（云端托管）。

### 8.1 三种方案全景对比

| 维度 | DeepSeekMath-V2 (论文方法) | Agent Lightning (本地) | Azure RFT (云端) |
|------|---------------------------|------------------------|------------------|
| **目标** | 数学证明（定理证明） | 数学推理（应用题） | 通用推理任务 |
| **训练算法** | GRPO + Verifier RL | GRPO / PPO / DAPO | 托管 RFT (未公开) |
| **奖励来源** | 训练的 Verifier + Meta-Verifier | 自定义函数（规则+结构） | Grader（规则/模型/代码） |
| **自验证能力** | ✅ 训练模型自评+改进 | ❌ 仅外部奖励 | ❌ 仅外部奖励 |
| **推理时迭代** | ✅ 5000+ 次/题 | ❌ 单次生成 | ❌ 单次生成 |
| **支持模型** | DeepSeek 系列 | 开源模型 (Qwen, LLaMA) | OpenAI (o4-mini, GPT-5) |
| **硬件要求** | 大规模集群 | 40GB+ GPU (H100/A100) | 无需本地 GPU |
| **开源程度** | 论文公开，代码未开源 | 完全开源 | 托管服务 |
| **适用场景** | IMO/Putnam 竞赛级证明 | 工程级数学推理 | 快速原型/OpenAI生态 |

### 8.2 奖励函数设计对比

三种方案都需要定义"什么是好的回答"，但实现方式不同：

#### DeepSeekMath-V2：三层验证奖励

```text
┌─────────────────────────────────────────────────────────────────┐
│                  DeepSeekMath-V2 奖励架构                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Generator 输出: Proof Y + Self-Evaluation Z                    │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐                                            │
│  │ Verifier πφ     │ ──► R_Y = proof_score (0/0.5/1)           │
│  │ (训练的评委)     │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ Meta-Verifier πη│ ──► R_meta = 自评是否诚实 (0/0.5/1)        │
│  │ (审查评委)       │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  R = R_format · (α·R_Y + β·R_Z)    α=0.76, β=0.24              │
│                                                                 │
│  特点: 奖励模型本身需要训练，能评估推理过程质量                    │
└─────────────────────────────────────────────────────────────────┘
```

#### Agent Lightning：组合式规则奖励

```python
def compute_reward(response, ground_truth):
    reward = 0.0
    
    # 1) 结构奖励: 是否包含推理链
    if "<think>" in response and "</think>" in response:
        reward += 0.5  # 格式正确
    
    # 2) 正确性奖励: 最终答案
    if extract_answer(response) == ground_truth:
        reward += 2.0  # 答案正确
    
    # 3) 深度奖励: 推理充分性
    if len(extract_think(response)) > 100:
        reward += 0.5  # 推理够长
    
    return reward  # 最高 3.0

# 特点: 规则简单、无需训练评委、只看最终答案+格式
```

#### Azure RFT：Grader 组合

```python
# Multigrader 示例: 组合多种评分方式
{
    "type": "multi",
    "graders": {
        "correctness": {
            "type": "python",
            "source": "def grade(s,i): return 1.0 if s.output==i.answer else 0.0"
        },
        "format": {
            "type": "string_check",
            "operation": "like",
            "input": "{{ sample.output_text }}",
            "reference": "\boxed{"
        },
        "quality": {
            "type": "score_model",
            "model": "gpt-4o-2024-08-06",
            "input": [{"role": "user", "content": "Rate this solution..."}]
        }
    },
    "calculate_output": "correctness * 0.6 + format * 0.2 + quality * 0.2"
}

# 特点: 灵活组合、支持 LLM-as-Judge、托管运行
```

### 8.3 关键区别：自验证 vs 外部奖励

| 特性 | DeepSeekMath-V2 | Agent Lightning / Azure RFT |
|------|-----------------|----------------------------|
| **模型知道奖励函数吗？** | ✅ 是，训练时学会了验证规则 | ❌ 否，只知道奖励信号 |
| **能自我改进吗？** | ✅ 推理时自评+迭代修复 | ❌ 生成后无法自我修正 |
| **推理开销** | 🔴 极高 (~5000次/题) | 🟢 低 (1次生成) |
| **适合实时应用？** | ❌ 离线竞赛 | ✅ 在线服务 |

**核心洞察**：

DeepSeekMath-V2 的"自验证"是**训练时教会模型验证能力**，让它推理时能：
1. 生成答案的同时生成自评
2. 根据自评发现问题
3. 迭代改进直到自评满分

而 Agent Lightning / Azure RFT 是**纯外部奖励**，模型不知道"为什么这个答案好"，只知道"这个答案得了高分"。

### 8.4 训练复杂度对比

```text
DeepSeekMath-V2 训练流程（复杂）:
─────────────────────────────────────────────────────
阶段1: 训练 Verifier（需要人工标注证明质量）
   │
   ▼
阶段2: 训练 Meta-Verifier（防止 Verifier 幻觉）
   │
   ▼
阶段3: 训练 Generator（用 Verifier 作为 Reward Model）
   │
   ▼
阶段4: 协同进化（Generator↔Verifier 互相提升）
─────────────────────────────────────────────────────

Agent Lightning 训练流程（简单）:
─────────────────────────────────────────────────────
阶段1: 定义奖励函数（规则代码）
   │
   ▼
阶段2: GRPO 训练（单阶段）
─────────────────────────────────────────────────────

Azure RFT 训练流程（最简单）:
─────────────────────────────────────────────────────
步骤1: 准备 JSONL 数据
步骤2: 定义 Grader（JSON 配置）
步骤3: 提交训练任务（Azure Portal / API）
─────────────────────────────────────────────────────
```

### 





