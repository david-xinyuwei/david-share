# LLM RL Training and Reasoning Enhancement

本文是一份 LLM 强化学习训练与推理增强的完整技术指南，涵盖 RL 基础（PPO/GRPO）、奖励函数设计、DeepSeek R1 & DeepSeekMath-V2 训练架构、数学推理 RL、Test-time Compute Scaling、SLM 微调实验，以及 GSPO 等前沿方法。

> *This guide consolidates content from multiple previously separate articles into a single coherent resource.*

## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | vLLM, LoRA/PEFT, Unsloth, PyTorch |

---


# Part 1: 强化学习三种训练模式

> *原文来自 GRPO-RL-Training-Pipeline*


## **强化学习三种模式**

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/1.png)

上面这三种强化学习训练大模型做推理的模式，可以简单理解为“最终只看答案给奖励”到“分步骤给奖励”的逐步演进。它们的主要区别如下：

#### 1. 直接强化学习 (Direct RL)

• 核心思路：
模型只输出一个答案，奖励模型(Reward Model)仅根据这最终答案是否正确或符合目标来给出奖励。
• 特点：
– 只在最后一步得到奖励信号。
– 实现最简单，但无法直接指导模型中间的推理步骤对不对。
– 如果中途思路错了，模型只能在最终答案“被扣分”时才知道哪里出了问题，学习速度慢。

#### 2. 多步强化学习 + 最终结果奖励 (Multi-Step RL with Outcome Reward Model, ORM)


• 核心思路：
模型在输出答案前，会先“显式地”或“隐式地”写下一系列中间推理步骤(Reasoning steps)，最后依然只看最终答案来给奖励。
• 特点：
– 明确地将思考过程拆分为多步，但奖励依旧只看最后结果。
– 相比直接RL，模型在训练时可以学会更有条理的分步思考，但依旧无法从每一步是否正确获得即时反馈。
– 如果中间步骤错误，但最终答案凑巧对了或者错了，模型依旧只能在最终才能得到一次奖惩信号。

#### 3. 多步强化学习 + 过程奖励 (Multi-Step RL with Process Reward Model, PRM)


• 核心思路：
模型同样会写下一系列的中间推理步骤，但现在在每个推理步骤上都进行评价。如果该推理步骤正确或对最终答案的正确性有帮助，则给一个正向奖励；如果出错则给负向反馈。最终得到答案后，也会有最终结果的整体奖励。
• 特点：
– 不仅关注最终答案，还关注模型的每一个中间步骤是否合理或正确。
– 可以更细粒度地引导模型，让模型在每次思考时都更容易修正错误，提高推理的可控性和准确度。
– 实现更复杂，因为需要额外的“过程奖励模型”去判断每一步是否正确或合理。



#### 示例：用解简单方程来对比

假设我们让模型解一个非常简单的方程：“2x + 3 = 7，求 x”。

1. 直接强化学习 (Direct RL)
   – 模型可能直接输出“x=2”，然后由奖励模型根据最终答案正确与否给予奖励。
   – 如果它不小心算错了，比如输出“x=3”，它也只有在最终拿到负反馈后才知道错。
   – 中间并没有显式推理或对中间过程打分。
2. 多步RL + 最终结果奖励 (Multi-Step RL with Outcome RM)
   – 模型的输出过程可能写成四步：
   (1) 2x + 3 = 7
   (2) 2x = 4 (减去3)
   (3) x = 2 (再除以2)
   (4) 最终答案：x=2
   – 不过奖励还是只根据最后这个“x=2”对不对来评估。
   – 如果中间推理哪一步错误导致答案最终错误，只有在最后才能知道。
3. 多步RL + 过程奖励 (Multi-Step RL with Process RM)
   – 同样会分四步：
   (1) 2x + 3 = 7
   (2) 减去3得到2x = 4 → 这一步如果正确就即时给一个正向奖励。
   (3) 再除以2得到x = 2 → 继续给正向奖励。
   (4) 最终答案：x=2 → 也会单独评估最终结果给一个奖励。
   – 如果某一步过程出错(比方说“减去3”后误写成“2x = 5”)，在那一步就能得到负反馈，模型能迅速发现错误并修正。
   – 在训练中，模型更容易学到正确的推理过程，因为每一步都能获得有针对性的指导。



#### 总结

• Direct RL：只关心最终答案，最简单，但难以给中间步骤提供反馈。
• Multi-Step RL + Outcome RM：显式地把推理拆成多步，但仍只有最后的结果反馈。
• Multi-Step RL + Process RM：每一步都可以得到奖励或惩罚，能大大提升推理过程的可控性与准确度，不过需要一个能评估过程正确性的模型，实施上也更复杂。

对于初学者，可以把它想象成：
• Direct RL：相当于只看考试最后得了多少分；
• Multi-Step (Outcome) RL：考卷上虽然能看到你的解题步骤，但判卷时只给你最后答案对就打分；
• Multi-Step (Process) RL：考官不仅看最终答对没，还会在每一步解题中批注你哪里做对、哪里做错，并给你相应的分数或扣分。





---

# Part 2: DeepSeek R1 训练范式与技术对比

> *原文来自 GRPO-RL-Training-Pipeline*


### DeepSeek R1的训练范式

###  SFT + RL 的四阶段混合范式（DeepSeek-R1）

1. **SFT-1**：少量高质量 CoT，教会格式→保证可读性。
2. **RL-1**：R1-Zero 风格奖励→逼出长链条、提升正确率。
3. **SFT-2**：混合“需要推理”与“无需推理”的数据→避免模型逢问必想。
4. **RL-2 / RLHF**：再用人类偏好或安全奖励微调→提升对话体验。

对照上文，可把 DeepSeek-R1 归入

```
训练：Multi-Step RL + Outcome RM  (+ 少量 SFT)
推理：默认 Greedy，可选 Majority-Vote
```

## Test Time Scale模式

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/2.png)
Test Time Scale：Majority Vote / Tree Search / Beam Search / Lookahead Search

当大语言模型在“推理”或“回答”时，并不一定只用最朴素的“从左到右采样，直接得到答案”这一种方式。为了提升答案的准确度或稳健性，人们往往会在推理阶段引入各种“搜索”技巧，主要目的是从模型内在的多种可能生成路径中，找到或投票出最优的一条。下图中展示了几种常见策略的示意。

1. Majority Vote
   • 做法：让模型针对同一个问题多次独立生成答案(比如随机采样不同的种子或温度)，得到多个结果。然后对这些结果进行投票(多数/平均/打分)选出一个最可能正确的答案。
   • 特点：
   – 实现非常简单，只要多次采样，再投票。
   – 没有显式地去搜索推理路径，而是通过多个候选答案来“集思广益”。
   – 当模型在不同次采样下表现差异很大时，该方法有时会纠正随机错误；但若模型系统地倾向于某种错误，它也就相对失效。
2. Tree Search
   • 做法：把模型每一步可能的生成看成一个分支，在树状结构里扩展，选择更高分或更合理的分支继续扩展下去。
   • 特点：
   – 比Majority Vote更系统地去发掘可能的推理路径。
   – 可以在初期就剪除一些看起来明显错误的分支(用打分或启发式规则)。
   – 但纯粹的Tree Search如果分支数过多，计算开销会变得非常大。
3. Beam Search
   • 做法：可以视作对Tree Search的“简化版”，在每个生成步只保留前K条“最优”分支(即Beam宽度K)，其余分支被剪去。
   • 特点：
   – 是机器翻译、文本生成里经常用的解码算法。
   – 相对树搜索更加高效，用有限的Beam宽度在“多个相对优质的分支”中寻找最佳答案。
   – 如果K值太小，仍可能漏掉一些正确但处于相对次优概率路径的解法；如果K值很大，计算成本又会增加。
4. Lookahead Search
   • 做法：不仅在当前这一步做出选择，还会向后“多看几步”对每条可能路径的后续进行模拟或打分，并根据展望结果来决定当前该走哪条路。
   • 特点：
   – 更像在下棋时做的“多步预判”，以期提前排除后续可能导致错误或不优的分支。
   – 效果通常比纯粹的Beam或Tree Search更好，但需要更多计算量或更复杂的启发式评价。
   – 当问题本身层数多、分支巨大时，Lookahead也容易遇到“爆炸式”增长，需要做好剪枝。

简化类比：
• Majority Vote 像考场里你自己想几遍，然后合并这些想法，出现最多的答案就是输出。
• Tree Search、Beam Search 和 Lookahead 则更像“全盘搜索”，经常在搜索树里做剪枝，逐步找出最优解，能相比多次瞎猜更在“每一步”进行评判，力图深入探索而不盲目。



## 技术对比

我们现在讨论的是两种不同的技术（分别用于训练阶段和推理测试阶段）：

- **RL训练阶段模式** (给奖励的方式不同)
  1. **Direct RL** ：只根据最终答案对错给奖励。
  2. **多步RL+结果奖励 (Outcome RM)** ：模型会明确写出分步推理，但奖励仍然只看最终答案。
  3. **多步RL+过程奖励 (Process RM)** ：模型明确写出分步推理，并对每一个步骤都给予奖励或惩罚。
- **推理阶段搜索模式** (如何利用模型生成最佳答案)
  1. **简单采样(Greedy/Temperature Sampling)**：不做特殊搜索，每一步直接从概率最高或一定随机程度的选项中采样。
  2. **多数投票(Majority Vote)**：对同一问题独立生成多个答案，通过投票决定一个最佳答案。
  3. **Beam或Tree Search**：通过搜索树构建多条生成路径，并对过程进行剪枝选择最佳路径。
  4. **Look-ahead Search(MCTS类)**：向前“预看”几步后续选择再决定。



####  **排列组合一览表** （行是RL训练模式，列是推理阶段模式）

| RL训练模式 ↓ / 推理阶段模式 →                                | 简单采样<br>(Greedy/温度)  | 多数投票<br> (Majority Voting)             | Beam Search/<br>Tree Search               | Look-ahead <br> Search     |
| ------------------------------------------------------------ | -------------------------- | ------------------------------------------ | ----------------------------------------- | -------------------------- |
| **Direct RL**<br>只奖最终答案                                | ✅ 常⻅基础方案             | ✅ 可行，能弥补训练不足                     | ✅ 可行，但未广泛报道                      | ○ 技术可行，但计算开销大   |
| **多步RL + 结果奖励 (Outcome RM)**<br>显式推理步, 只奖结果   | ✅ **DeepSeek-R1 默认方案** | ✅ DeepSeek-R1 离线数据生成阶段采用过此模式 | ✅ 可行，偶有研究使用                      | ○ 可行，但计算代价大       |
| **多步RL + 过程奖励 (Process RM)** <br> 推理步明确，每步都奖惩 | ✅ 模型已强大，直接使用广泛 | ✅ 辅助提⾼稳健性，常见                     | ✅ 分步推理清晰，非常适合使用Beam/Tree搜索 | ○ 技术先进，有少量前沿研究 |

------

#### DeepSeek R1目前公开采用的策略（明确文献表示）：

- **训练阶段 (RL模式)**：

> **多步RL + 结果奖励 (Outcome RM，其中Outcome RM是基于规则的)**

- DeepSeek目前公开信息显示，他们主要用显式推理步骤但只对最终答案做奖励（规则判定答案格式/准确）。
- **推理阶段 (Search方法)**：

> DeepSeek-R1 模型推理时默认采用简单采样(Greedy或温度采样)。
> 在离线训练数据合成阶段则使用了"多数投票"(Majority Vote)+Rejection Sampling方法提升样本质量。

> 当前DeepSeek-R1并未在公开资料中明确提及实时Beam Search、Tree Search或Look-ahead的使用情况。

------

#### 如何理解表格

- 行（RL训练）代表模型的“先天能力”（通过训练阶段提高）。
- 列（推理搜索）代表在实际使用模型时“答题/解题策略”（通过推理阶段提升精确度）。
- 现实实际应用中，可以自由组合行列组合，例如：
  - 训练很弱(Direct RL) → 推理更依赖多数投票、搜索补救。
  - 训练很强(Process RM) → 推理阶段仍可额外做简单搜索和投票进一步提升稳健性。

## **DS R1的范式**

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/3.png)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUicwxWRiaeB4ibaXAtuEMND1S8qSAklGF6vibbmueCyglkicVpfm73CgP8fst0sjk7uGZefPcMGg4rRAg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/4.png)

上面图展示了一个名为“DeepSeek R1”的大模型推理与训练方案。它包含以下几个关键要素：

1. 多阶段数据及训练 (SFT → RL)：
   • 首先会进行大规模的有监督微调(Supervised Fine-Tuning, SFT)，包括常规任务数据、链式思考(CoT)数据等。此时模型先学会基本的回答和格式。
   • 接着进入强化学习阶段(RL)，使用“Reasoning Oriented RL (RORL)”，也就是额外鼓励模型在推理准确性或中间步骤合理性上表现更好。
2. Rule-Based Outcome Reward Model (ORM)
   • 在理想情况下，人们想采用前面讨论过的PRM(“每一步都打分”)模式，但往往需要昂贵的标注或更强大的过程评估模型。
   • DeepSeek R1因为资源限制，无法完全复现PRM，于是采取了一个“基于规则”的Outcome Reward：即只要最终答案符合某些准确性、格式规则，就给正奖励，如果不符合就给负奖励。
   • 结果表明，这种相对简单的做法在某些场景中也能取得不错的效果，尤其是搭配精心设计的训练数据和多阶段流程。
3. GRPO 
   • PPO(近端策略优化)是常见的RL微调方法。DeepSeek R1提出了一种“GRPO”思路，可以并行或分组地计算多个奖励，进而减少资源占用、加快收敛。
   • 具体来说，他们会在同一个批次或分组内同时把多个样本送进ORM进行打分，然后聚合这些反馈信号对Policy Model进行更新，减少反复计算。
4. 数据合成与Rejection Sampling
   • 指的是在训练时，不仅使用人类标注的数据，还会用模型自我生成(包括中间推理步骤)的数据，再对其筛选。
   • 筛选方式可能是“规则+模型判分”的组合：如果生成文本在逻辑上错误或不符合自定义的标准，就被拒绝；好的则被保留下来，当作新的训练样本。
5. Distillation (知识蒸馏)
   • 在最后阶段，往往会把体量更加庞大的模型(例如Qwen、Llama等)作为师模型，把它在推理和回答上的能力“蒸馏”出来，迁移到一个规模相对小或更高效的模型(DeepSeek R1 Distill版)。
   • 这样做既能保留很多推理能力，又能降低推理时的算力需求。

## 强化学习的一个范例 法律文书RL奖励函数设计精华与性能跃升解析

*Refer to：https://zhuanlan.zhihu.com/p/25423170224*

**核心技巧：分层奖励 + 强解析机制**



---

# Part 3: PPO/RLHF 角色详解 —— "Film Crew" 类比

> *原文来自 LLM-Math-Reasoning-RL*

## 🎯 Objectives

- Explain: Why "rule-based rewards" and "LLM-as-Judge" coexist in LLM mathematical reasoning
- Clarify: What Actor / Reward / Reference / Critic(Value) do in RLHF, which get trained, and why
- Present: Training architectures and key algorithms for DeepSeek-R1 and DeepSeekMath-V2 (with diagrams)
- Compare: When to use verifiable rewards vs. when to train a verifier

---

## 🎭 Chapter 1: Understanding RL Roles Through a "Film Crew" Analogy (Core Intuition)

Let's first clarify "who is who" in training—this makes all subsequent paper details much clearer.

### 1.1 PPO/RLHF: A "Four-Role" Film Crew

| Component | Film Crew Analogy | One-Line Responsibility | Parameters Updated During Training? |
|---|---|---|---|
| **Actor (policy)** | 🎬 Actor | Responsible for "performing"—generating responses | ✅ Trained |
| **Reward Model (RM)** | 👨‍⚖️ Judge | Scores the performance (preference/quality) | ✅ Pre-trained; usually frozen during PPO |
| **Reference Model** | 📜 Original Script | Prevents actor from "deforming" for high scores (KL constraint) | ❌ Frozen |
| **Critic / Value Model** | 🎓 Sparring Coach | Practices alongside while learning "roughly what score this performance will get" | ✅ Trained (synchronized with Actor) |

#### How Do Training Signals Flow? (PPO Architecture Diagram)

```text
Prompt x
  │
  ▼
┌───────────────┐        ┌──────────────────┐
│ Actor πθ      │        │ Reference πref   │
│ Generates y   │        │ (Original Script)│
└──────┬────────┘        └───────┬──────────┘
       │                          │
       │ logπθ(y|x)               │ logπref(y|x)
       │                          │
       ▼                          ▼
   ┌──────────────────────────────────────────┐
   │ KL Penalty:   -β · (logπθ - logπref)     │
   └──────────────────────────────────────────┘
                  │
                  │ Generated (x, y)
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
┌───────────────┐     ┌───────────────┐
│ Reward Model  │     │ Critic Vψ     │
│ r = RM(x,y)   │     │ v = Vψ(x)     │
│ (Judge scores)│     │ (Coach estimates)│
└──────┬────────┘     └──────┬────────┘
       │                     │
       └──────────┬──────────┘
                  ▼
           Advantage A = r - v
                  │
                  ├──> Update Actor θ (make high-A behaviors more frequent)
                  └──> Update Critic ψ (make v closer to r)
```

**Key Point**: Reward Model and Critic compute **in parallel**, both based on generated (x, y), then jointly compute Advantage.

#### Why Must Critic Be "Trained Together"?

- As Actor improves (policy distribution changes), reward distribution also changes
- If Critic doesn't learn along, its "score prediction" becomes increasingly inaccurate
- More accurate Critic → more stable Actor updates (lower variance)

> This is why I compare Critic to a "sparring coach": it's not a bystander—it must constantly calibrate itself.

### 1.2 GRPO: Remove the "Coach", Use "Group Comparison" as Baseline

Both DeepSeek-R1 and DeepSeekMath-V2 emphasize **GRPO**. Intuitively:

- PPO needs Critic to estimate baseline
- GRPO samples a group of responses for the same prompt, using **relative performance within the group** as baseline, eliminating the need to separately train a Critic

#### GRPO Update Intuition (Pseudocode)

```text
Given prompt x:
  1) Sample K responses y1..yK from Actor
  2) Compute reward for each: r1..rK
  3) Compute group baseline (e.g., mean r̄)
  4) Update Actor with (ri - r̄) as weights
  5) Can still add KL(Actor || Reference) constraint
```

Visualization:

```text
Same problem x
  ├─ y1 → r1
  ├─ y2 → r2
  ├─ y3 → r3
  └─ yK → rK

Group baseline r̄ = mean(r)
Advantage: Ai = ri - r̄
```

---


---

# Part 4: GRPO 方法详解

> *原文来自 GRPO-RL-Training-Pipeline*


## GRPO 方法详解

### 1. GRPO 核心概念


GRPO（Generative Relative Policy Optimization，生成式相对策略优化）的主要目标是通过在线、自生成的方式来优化模型的策略，使其无需依赖大量外部数据或人工反馈即可提升性能。其核心概念包括：

- **在线生成与学习**：训练过程中模型自行生成样本并即时学习。
- **相对优势评估**：通过计算生成样本的相对优势，引导模型向最优方向优化。
- **策略正则化**：约束新策略与参考策略之间的差异，防止模型偏离原始知识结构。

### 2. GRPO 工作流程

#### **Step 1: 样本生成**


对于每个输入（如提示或问题），模型生成多个可能的输出（称为"completions"）。例如给定一个问题，模型可能生成 8 个不同的答案。

#### **Step 2: 奖励评估**


对每个生成的输出，定义奖励函数来评估其质量。奖励函数可以根据任务需求设计，例如根据输出的格式、内容准确性等进行打分。

#### **Step 3: 计算相对优势**


对每个生成的输出，使用以下公式计算其相对于同组其他输出的相对优势（Advantage）：

```
A_i = (r_i - r̄) / σ(r)  
```


其中：

- `A_i`：第 `i` 个输出的相对优势。

- `r_i`：第 `i` 个输出的奖励值。

- `r̄`：组内所有输出奖励值的均值。

- `σ(r)`：组内奖励值的标准差。

  **示例:**

  假设模型生成了 4 个输出，奖励值分别为 `[0.6, 0.8, 0.4, 0.7]`。

  计算均值：

```
r̄ = (0.6 + 0.8 + 0.4 + 0.7) / 4 = 0.625  
```


计算标准差：

```
σ(r) = sqrt( [(0.6 - 0.625)² + (0.8 - 0.625)² + (0.4 - 0.625)² + (0.7 - 0.625)²] / 4 )  
     ≈ sqrt( [0.000625 + 0.030625 + 0.050625 + 0.005625] / 4 )  
     ≈ sqrt(0.0875 / 4) ≈ 0.148  
```


各输出的相对优势：

```
A_1 = (0.6 - 0.625) / 0.148 ≈ -0.169  
A_2 = (0.8 - 0.625) / 0.148 ≈ 1.182  
A_3 = (0.4 - 0.625) / 0.148 ≈ -1.519  
A_4 = (0.7 - 0.625) / 0.148 ≈ 0.507  
```


相对优势反映了每个输出相对于平均水平的表现。正值表示高于平均，负值表示低于平均。

#### **Step 4: 策略更新**


使用相对优势来更新模型策略。为防止策略偏离过大，引入 KL 散度作为正则化项：

```
L = - E[ A_i * log π_θ(a_i | x_i) ] + β * D_KL [ π_θ || π_ref ]  
```


其中：

- `L`：损失函数。

- `E`：所有样本的期望。

- `A_i`：第 `i` 个样本的相对优势。

- `π_θ(a_i | x_i)`：策略 `π_θ` 下模型对输入 `x_i` 生成输出 `a_i` 的概率。

- `β`：正则化系数，控制策略更新的强度。

- `D_KL [ π_θ || π_ref ]`：新策略 `π_θ` 与参考策略 `π_ref` 之间的 KL 散度。

  **说明:**

- **第一项**：通过用 `A_i` 对对数概率加权，鼓励模型对相对优势较高的输出赋予更高概率。

- **第二项**：使用 KL 散度限制新策略与参考策略之间的差异，防止模型遗忘先前知识。

### 3. GRPO 的优势

#### 减少对外部数据的依赖

- **自我生成训练数据**：模型通过在线生成样本进行学习，减少对大规模标注数据的需求。
- **降低人工成本**：无需大量人工反馈或标注，降低训练成本。

#### 提升训练效率

- **快速收敛**：通过评估相对优势，模型能更高效地识别和学习高质量策略。
- **策略稳定性**：引入策略正则化防止模型策略剧烈变化，确保训练过程稳定。

### 4. 实践中的关键技术分析

#### 相对优势的计算与应用


计算相对优势使模型能在一组生成输出中识别哪些更优，从而集中学习这些高质量输出。

**示例:**

假设在一个训练步骤中，模型对一个输入生成了多个输出：

- **输出 A**：奖励值 0.9

- **输出 B**：奖励值 0.5

- **输出 C**：奖励值 0.7

  计算均值：

```
r̄ = (0.9 + 0.5 + 0.7) / 3 ≈ 0.7  
```


计算标准差：

```
σ(r) = sqrt( [(0.9 - 0.7)² + (0.5 - 0.7)² + (0.7 - 0.7)²] / 3 )  
     = sqrt( [0.04 + 0.04 + 0] / 3 ) ≈ 0.163  
```


各输出的相对优势：

```
A_A = (0.9 - 0.7) / 0.163 ≈ 1.225  
A_B = (0.5 - 0.7) / 0.163 ≈ -1.225  
A_C = (0.7 - 0.7) / 0.163 = 0  
```


模型由此知道输出 A 高于平均水平，在策略更新时应赋予更大权重。

#### 策略正则化的重要性


引入 KL 散度作为正则化项，防止模型在更新过程中偏离原始策略过远，避免过拟合或遗忘先前学到的知识。

#### 奖励函数设计


奖励函数的设计对 GRPO 的成功至关重要。良好的奖励函数应满足：

- **与任务目标紧密相关**：确保奖励值真实反映输出质量。

- **计算简单**：避免过于复杂的计算以节省训练时间。

- **具有区分度**：对高质量和低质量输出提供显著不同的奖励。

### 5. 实践中的挑战与解决方案

| 挑战 | 解决方案 |
|------|---------|
| 奖励函数设计困难 | 从简单奖励函数开始，根据训练结果迭代优化；结合多维指标（格式、准确性、流畅度） |
| 模型训练不稳定 | 调整学习率、正则化系数 β 等超参数寻找最优平衡点；增加输入数据多样性 |
| 资源限制 | 模型量化（8bit/4bit）降低显存使用；使用 LoRA 等参数高效微调技术 |

### 6. 未来展望


GRPO 方法为在有限资源下训练大语言模型提供了新途径。未来研究方向包括：

- **自动化奖励函数生成**：利用机器学习技术自动设计和优化奖励函数，减少人工干预。
- **与其他优化方法结合**：将 GRPO 与强化学习、元学习等方法结合，进一步提升模型性能。
- **扩展应用领域**：探索 GRPO 在图像、语音等其他类型模型中的应用。

GRPO 的优势在于减少对昂贵硬件和大量人工标注数据的依赖，使更多研究者和开发者能参与大模型的训练和应用。通过合理的奖励函数设计和策略正则化，模型能在有限资源下达到期望性能。

***Refer to: https://kaitchup.substack.com/p/grpo-train-llms-with-deepseek-r1s***

---

## GSPO vs GRPO — 为 MoE 模型打造的序列级优化

### 1. 背景


---

# Part 5: 奖励函数设计实战

> *原文来自 GRPO-RL-Training-Pipeline*


## 强化学习的一个范例 法律文书RL奖励函数设计精华与性能跃升解析

*Refer to：https://zhuanlan.zhihu.com/p/25423170224*

**核心技巧：分层奖励 + 强解析机制**

```
# ===== 分层奖励架构 =====
def legal_reward(pred, judge_out, gold_ans):
    # 1. 格式层：强制思维链规范
    fmt = 0 if all(tag in pred for tag in ["<think>","</think>","<answer>","</answer>"]) else -1

    # 2. 任务层：动态路由任务类型
    if "刑期" not in gold_ans:  # 非刑期任务
        return fmt + {-2:"0", 1:"1", 2:"2"}.get(judge_out, 0)  # 异常→0
    else:  # 刑期任务
        if "个月" not in gold_ans: return fmt + 0  # 金标校验（原文边界条件）
        match = re.search(r"误差[:：]?\s*(\d+)\s*个月", judge_out)  # 强解析正则
        return fmt + (-int(match[1])/240 if match else -2) 
```

以下表格清晰展示奖励函数设计如何驱动性能跃升，每项均对应代码实现：

| **优化策略**       | **解决的核心问题**       | **性能提升**                 | **代码实现位置**                                 |
| ------------------ | ------------------------ | ---------------------------- | ------------------------------------------------ |
| **格式优先验证**   | 早期输出混乱导致信号丢失 | 格式错误率从>50%降至0.3%     | `format_reward()`函数：<br>`all(tag in pred...)` |
| **三级分类奖励**   | “部分正确”样本无正向反馈 | 罪名准确率突破70%瓶颈→93.2%  | `task_reward()`中：<br>`{"0":-2, "1":1, "2":2}`  |
| **刑期梯度惩罚**   | 数值预测缺乏渐进优化路径 | 刑期误差中位数从11.5月→0.8月 | `-int(match[1])/240`                             |
| **抗噪正则解析**   | 判分模型输出变异干扰信号 | 奖励计算失败率<0.3%          | `re.search(r"误差[:：]?\s*(\d+)\s*个月")`        |
| **金标有效性校验** | 无效标注污染训练过程     | 无效样本处理速度提升5倍      | `if "个月" not in gold_ans: return 0`            |

### 训练阶段性能演进（可视化）

```
# 刑期预测能力进阶过程（奖励驱动）
| 训练阶段   | 平均误差 | 平均奖励  | 学习行为       |
|------------|----------|-----------|----------------|
| 0-100步   | 11.5月   | ![-0.48]  | 基础错误规避   |
| 100-300步 | 5.2月    | ![-0.02]  | 逻辑优化       |
| 300-400步 | 2.4月    | ![+0.31]  | 法条精准引用   |
```

注：![±X] 表示奖励值，负值为惩罚，正值为激励

**技术实现注释**

1. 格式验证确保早期收敛：

   ```
   # 检查4个必需标签（前100步贡献78%准确率提升）
   if all(tag in pred for tag in ["<think>","</think>","<answer>","</answer>"]): ...
   ```

2. 刑期梯度惩罚实现线性优化：

   ```
   penalty = -error_months / 240  # 每减少1个月误差，奖励提升0.004
   ```

3. 正则容错保障稳定性：

   ```
   # 兼容7种判分输出变体（如“误差6月”、“误差： 6个月”）
   r"误差[:：]?\s*(\d+)\s*个月"
   ```

## 选择 SFT 还是 RL

在绝大多数情况下，最安全且最高效的流程是 **“先 SFT，后 RL”** —— 尤其是对于容量较小的模型，或需要严格输出格式的任务。
此原则并非绝对，下列速查可帮助你判断。

### 1. 为什么 “SFT → RL” 通常更好

1. 训练稳定性
   • 直接做 RL（小模型尤甚）很容易触发 KL 激增、梯度爆炸，甚至整体崩溃。
   • SFT 先把策略锚定在“基本正确且符合格式”的区间，再用 RL 微调；KL 跳变更小，收敛更平稳。
2. 数据效率
   • SFT 相当于“先把答案喂给模型，教会基础”；RL 更像“学完基础后做泛化练习”。
   • 直接 RL 会在大量无用探索上浪费步数。
3. 人工标注成本
   • SFT 可以复制少量高质量标注（或合成标注）；RL 只需奖励信号即可放大效果。二者结合能节省标注工作。

### 2. 何时直上 RL 更合适

1. 几乎没有标注数据，但奖励可自动计算
   例：解数独、玩 Atari——得分由环境直接给出。
2. 基础模型已非常强大
   GPT-4 / Claude-3-Sonnet 级别的模型格式和推理都稳定，可接受直接 RL（或 RLAIF）。
3. 任务鼓励高多样性且没有单一“标准答案”
   例：创意写作、对话风格调优——仅凭偏好得分即可。

### 3. 速查表

| 场景                  | 建议策略           | 备注                          |
| --------------------- | ------------------ | ----------------------------- |
| 一批高质量标注        | SFT → RL           | 主流 RLHF/GRPO 流水线         |
| 仅有弱标签（合成）    | 短 SFT → RL        | 先对齐格式，再放大能力        |
| 纯交互式 / 环境内奖励 | 直接 / 在线 RL     | 游戏、机器人等                |
| 预算极低，模型极小    | 小规模 SFT，再评估 | RL 计算量通常是 SFT 的 2–4 倍 |

关键问题：

1. 奖励是否完全依赖 “answer == gold answer”？
   • 是 → 显然已有标签 → 先做 SFT，更便宜。
2. GPU/TPU 预算多少？
   • RL（尤其 GRPO/PPO）计算量通常是 SFT 的 2–4 倍。
3. 是否需要可解释的 “思维链”？
   • 先用 SFT 教格式，再用 RL 提精度，可生成更易解释的输出。

结论
“先 SFT 后 RL” 并非强制，但对大多数标签充足且输出结构化的任务，它是最省心、最稳妥的路径。
只有在标签稀缺或任务本身可直接计算奖励时，才考虑 “只做 RL”。

## 常见 RL 坑点

前文提到的 KL 激增、梯度爆炸与模型坍塌详解如下。



## 嵌入式代码的奖励函数设计


## 🎯 核心问题：代码训练如何验证正确性？

### 数学题 vs 代码生成

| 任务类型 | 答案形式 | 验证方式 |
|---------|---------|---------|
| 数学题 | 唯一数值 | `answer == gold_answer` |
| 代码题 | **多种实现** | `pass_all_tests(code)` |

**同一个功能可能有 100 种不同但都正确的实现！**

```
训练数学题时：
  问题：2x + 3 = 7，求 x
  答案：x = 2  ← 唯一正确答案，可以精确匹配

训练代码生成时：
  问题：写一个 GPIO 初始化函数
  答案：??? ← 有无数种正确写法！
```

---

## 📊 DeepSeek-R1 的代码训练方案

DeepSeek-R1 论文明确说明了代码训练的方法：

> *"For coding problems, we utilize a compiler to verify the correctness of the generated code based on predefined test cases."*

**核心方法：Rule-Based Rewards（基于规则的奖励）**

```python
def reward_code(generated_code, test_cases):
    """
    DeepSeek-R1 的代码奖励函数
    """
    # 1. 编译代码
    try:
        compiled = compile_code(generated_code)
    except:
        return 0.0  # 编译失败，奖励 0
    
    # 2. 运行测试用例
    passed = 0
    for test in test_cases:
        try:
            result = run(compiled, test["input"])
            if result == test["expected_output"]:
                passed += 1
        except:
            pass  # 运行时错误
    
    # 3. 计算通过率作为奖励
    return passed / len(test_cases)  # 0.0 ~ 1.0
```

### 关键洞察：**RL 阶段不需要标准答案！**

```
传统 SFT 思路：
  问题 → 标准答案 → 交叉熵 loss

R1 的 RL 思路：
  问题 → 模型生成代码 → 编译执行 → 测试通过？ → 奖励
```

**只要测试通过，不管代码怎么写都给奖励！**

---

## 🔧 嵌入式代码的奖励函数设计

| 验证方式 | 适用场景 | 奖励分数 |
|---------|---------|---------|
| **语法检查** | 所有代码 | +3 (通过) / -2 (失败) |
| **编译通过** | 可编译代码 | +5 (通过) / -1 (失败) |
| **静态分析** | 代码质量 | +1 (无警告) |
| **单元测试** | 有测试用例 | +10 × 通过率 |
| **硬件状态验证** | 嵌入式专用 | +5 (状态正确) |

### 本项目的奖励函数

```python
# 1. 格式奖励 - 检查必要标记
def reward_format(completions):
    # 检查 <think>...</think> 和 <code>...</code> 标记
    ...

# 2. 语法奖励 - 快速语法检查（毫秒级）
def reward_syntax(completions):
    # 使用 clang -fsyntax-only 检查
    ...

# 3. 编译奖励 - 完整交叉编译
def reward_compile(completions):
    # 使用 arm-none-eabi-gcc 交叉编译
    ...

# 4. 静态分析奖励
def reward_static_analysis(completions):
    # 使用 cppcheck 检查代码质量
    ...
```

---

## 📋 训练流程

### 阶段 1：SFT（监督微调）

**目的**：教模型代码格式和风格

```json
{
  "instruction": "初始化 UART1，波特率 115200",
  "output": "<think>需要配置 UART 外设...</think>\n<code>\nvoid UART1_Init() {...}\n</code>"
}
```

**这里需要示例代码，但只是教模型"怎么写"，不是唯一正确答案。**

### 阶段 2：RL/GRPO（强化学习）

**目的**：用可验证奖励提升代码正确性

| 训练阶段 | 需要标准答案？ | 验证方式 |
|---------|--------------|---------|
| **SFT** | ✅ 需要示例 | 交叉熵 loss |
| **RL** | ❌ 不需要 | 可验证奖励（编译/测试） |

---

## 🚀 快速开始

### 环境要求

- GPU: H100 / A100 (推荐 80GB 显存)
- 工具链: `arm-none-eabi-gcc`, `clang`, `cppcheck`

### 安装依赖

```bash
# 系统依赖
apt-get install -y clang cppcheck gcc-arm-none-eabi

# Python 依赖
pip install unsloth trl transformers datasets accelerate peft vllm
```

### 运行训练

```bash
# 快速测试（5 步 GRPO）
./run_train.sh test

# 仅 SFT
./run_train.sh sft

# 仅 GRPO
./run_train.sh grpo

# 完整 SFT + GRPO
./run_train.sh full

# 完整训练（含编译验证，较慢）
./run_train.sh full_compile
```

### 推理测试

```bash
python embedded_infer.py \
    --model_dir outputs_embedded/embedded_coder_final \
    --task "Initialize GPIO PA5 as output for LED"
```

---

## 📁 项目结构

```
embedded_sft_rl/
├── embedded_grpo_train.py   # 主训练脚本
├── embedded_infer.py        # 推理脚本
├── run_train.sh             # 训练启动脚本
├── requirements.txt         # Python 依赖
└── README.md                # 本文档
```

---

## 📊 训练效果

### 测试环境

| 配置 | 规格 |
|------|------|
| GPU | NVIDIA H100 80GB |
| 基座模型 | Qwen2.5-Coder-7B |
| 训练框架 | Unsloth + TRL (GRPOTrainer) |
| 总训练时间 | ~6 分钟 |

### SFT 阶段

| Epoch | Loss | 下降幅度 |
|-------|------|----------|
| Step 10 | 1.36 | - |
| Step 20 | 0.56 | -59% |
| Step 30 | 0.14 | -90% |
| Step 40 | 0.07 | -95% |
| Step 50 | 0.03 | **-98%** |

**SFT 耗时**: 44 秒

### GRPO 阶段

| Step | Total Reward | Format | Syntax | 说明 |
|------|--------------|--------|--------|------|
| 10 | 1.75 | 1.75 | 0.0 | 初始阶段 |
| 20 | 3.50 | 3.50 | 0.0 | 格式学习中 |
| 30 | 3.88 | 3.50 | 0.38 | 开始通过语法 |
| 40 | **4.95** | 3.50 | 1.45 | 峰值奖励 |
| 50 | 3.88 | 3.50 | 0.38 | 稳定 |

**GRPO 耗时**: 333 秒 (50 steps)

### 关键指标

| 指标 | 初始值 | 最终值 | 变化 |
|------|--------|--------|------|
| SFT Loss | 1.36 | 0.03 | ↓98% |
| Total Reward | 1.75 | 3.88 | ↑122% |
| KL Divergence | - | 0.39 | 正常范围 |

### 推理验证

```
任务: Initialize GPIO PA5 as output for LED control

生成代码:
void GPIO_Init(void) {
    __HAL_RCC_GPIOA_CLK_ENABLE();
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Pin = GPIO_PIN_5;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
}

语法检查: ✅ PASSED
```

---

## ⚠️ 踩坑记录

### 问题 1: `stm32f4xx_hal.h` 找不到

**症状**:
```
fatal error: 'stm32f4xx_hal.h' file not found
```

**原因**: 嵌入式代码依赖 STM32 HAL 库头文件，但训练环境没有安装完整的 STM32 SDK。

**解决方案**: 使用 stub 头文件，只定义必要的类型和宏：

```c
// stub 头文件示例
typedef struct { uint32_t Pin; uint32_t Mode; ... } GPIO_InitTypeDef;
#define GPIO_PIN_5 0x0020
#define GPIO_MODE_OUTPUT_PP 0x01
void HAL_GPIO_Init(void* port, GPIO_InitTypeDef* init);
```

### 问题 2: `GPIO_PIN_RESET` 未定义

**症状**:
```
error: use of undeclared identifier 'GPIO_PIN_RESET'
```

**原因**: 生成的代码使用了 HAL 库的枚举值，但 stub 头文件遗漏了。

**解决方案**: 在 stub 头文件中添加宏定义：

```c
#define GPIO_PIN_RESET 0
#define GPIO_PIN_SET 1
```

### 问题 3: 生成代码缺少 `#include`

**症状**: 模型有时生成的代码不包含头文件引用，导致语法检查失败。

**解决方案**: 在推理脚本中自动 prepend stub 头文件：

```python
# embedded_infer.py
full_code = STM32_STUB_HEADERS + "\n" + extracted_code
```

---

## 🎯 客户场景实操建议

```
Step 1: 收集客户的代码库
       ↓
Step 2: 从代码库提取 "任务-代码" 对（用于 SFT）
       ↓
Step 3: 为常见任务编写测试用例（用于 RL 奖励）
       ↓
Step 4: SFT 教模型格式和风格
       ↓
Step 5: RL 用测试通过率作为奖励，提升功能正确性
```

### 嵌入式代码测试用例格式

```json
{
  "task": "实现一个 LED 闪烁函数",
  "test_cases": [
    {
      "description": "LED 初始化后应为低电平",
      "expected_state": {"PA5": 0}
    },
    {
      "description": "调用 toggle 后应为高电平",
      "expected_state": {"PA5": 1}
    }
  ]
}
```

### 使用 QEMU 模拟验证（高级）

```python
def reward_hardware_state(code, expected_state):
    """在模拟器中运行代码，验证硬件状态"""
    emulator = QEMUEmulator("stm32f4")
    emulator.load_code(code)
    emulator.run(timeout=1000)
    
    score = 0
    if emulator.gpio_state("PA5") == expected_state["PA5"]:
        score += 5.0
    return score
```

---

## ⚠️ 常见问题

1. **开放式任务**：对于难以定义测试用例的任务，可以使用 LLM-as-Judge 作为奖励
2. **长代码处理**：拆分成小函数，每个函数单独测试
3. **编译依赖**：确保 STM32 HAL 头文件可用（本项目使用 stub 头文件）

---

## 📚 参考资料

- [DeepSeek-R1 论文](https://arxiv.org/abs/2401.02954) - Rule-based rewards for code
- [TRL GRPO Trainer](https://huggingface.co/docs/trl/main/grpo_trainer) - GRPO 训练框架
- [Unsloth](https://github.com/unslothai/unsloth) - 高效微调框架

---

## 📝 License


---

# Part 6: DeepSeekMath-V2 自验证证明训练架构

> *原文来自 LLM-Math-Reasoning-RL*


## 🧠 Chapter 2: Two Types of Math Tasks Determine Two Types of Rewards

### 2.1 "Fill-in-the-Blank" vs "Proof Problems"

| Task Type | Typical Competitions | Output | Verification Difficulty | Suitable Reward |
|---|---|---|---|---|
| **Verifiable Final Answer** | AIME/HMMT etc. | A number / A choice | ✅ Very Low | Rule-based reward (exact match / unit tests) |
| **Proof/Reasoning Process** | IMO/Putnam | Long proof chain | ❌ Very High | Trained verifier (LLM-as-Judge) |

**Core Contradiction** (from the paper):

> *"Pursuing higher final answer accuracy doesn't address a key issue: correct answers don't guarantee correct reasoning."*

Intuition:
- Fill-in-the-blank: reward is "right/wrong"
- Proof problems: reward is "rigor/completeness/presence of fatal flaws"

---

## 🔧 Chapter 3: DeepSeek-R1—How "Verifiable Rewards" Boost Reasoning Ability

> Key Point: R1 heavily uses **rule-based rewards** (verifiable) for math/code tasks, only introducing more subjective model scoring for general tasks.

### 3.1 What Does R1's "Rule Reward" Look Like?

```python
def rule_reward(answer, ground_truth):
    # 1) format reward (e.g., must include \boxed{})
    if not has_boxed(answer):
        return 0.0

    # 2) accuracy reward (strict comparison)
    return 1.0 if extract_boxed(answer) == ground_truth else 0.0
```

### 3.2 Engineering Advantages of Rule-Based Rewards

- **Reliable**: Almost no noise
- **Cheap**: No need to call additional LLM
- **Scalable**: Can run massive rollouts
- **Anti reward-hacking**: Clear alignment objective

### 3.3 But Its Ceiling Is Also Clear

- Correct final answer ≠ correct reasoning
- Completely inapplicable to proof problems (no "uniquely decidable" ground truth)

---

## 🔬 Chapter 4: DeepSeekMath-V2—"Self-Verifiable Proof" Training Architecture (with Meta-Verification)

This section is from the DeepSeekMath-V2 paper (verified against local `DeepSeekMath_V2.pdf`).

### 4.1 Verifier: First Train "Judges" to Find Issues and Score

Verifier's objective (Paper Section 2.1.1): For given problem X and proof Y, output analysis + score s ∈ {0, 0.5, 1}.

**Scoring Criteria** (Three-tier system):
- **1 point**: Completely correct, all steps rigorous and clear
- **0.5 points**: Overall logic correct, but with minor omissions or errors
- **0 points**: Contains fatal logical errors or severe gaps

**Verifier's RL Reward** (paper formula):
- R_format: Check if output includes required "evaluation + boxed score"
- R_score(s', s) = 1 - |s' - s|: Distance between predicted score and expert-labeled score

### 4.2 Meta-Verifier: Specifically Preventing "Judges Making Up Issues"

Key insight from Paper Section 2.1.2:

> *"When evaluating flawed proofs during training, the verifier can receive full reward by predicting the correct scores while hallucinating non-existent issues, undermining its trustworthiness."*

Problem: If Verifier is only supervised on "whether score is correct", it might use "fabricated flaws" to explain low scores.

**Solution**: Introduce meta-verification—have another model audit whether the verifier's analysis is **real, reasonable, and sufficient to support that score**.

**Enhanced Verifier Reward** (paper formula):

R_V = R_format · R_score · R_meta

Where R_meta comes from meta-verifier's quality score for the "review text".

**Effect**: Verification analysis quality score improved from **0.85 to 0.96**, while maintaining score prediction accuracy.

#### Two-Layer Verification Architecture (Proof → Verifier → Meta-Verifier)

```text
Problem X + Proof Y
        │
        ▼
┌───────────────────────┐
│ Verifier πφ           │
│ - Find flaws/gaps     │
│ - Explain deductions  │
│ - Output score s∈{0,0.5,1}│
└───────────┬───────────┘
            │ (More worth reviewing when s is low)
            ▼
┌───────────────────────┐
│ Meta-Verifier πη       │
│ - Audit if "review" is real│
│ - Audit if deduction reasons hold│
│ - Output quality score ms∈{0,0.5,1}│
└───────────┬───────────┘
            ▼
Trustworthy review for training/filtering
```

### 4.3 Generator: Initialize from Verifier Checkpoint, Then Learn "Write Proof + Self-Evaluate"

Key approach from Paper Section 2.2.2:
- Generator outputs two parts: proof Y + self-evaluation Z
- Let Verifier score the proof, while meta-verifying the self-evaluation

**Reward Function** (paper provides coefficients):

R = R_format(Y,Z) · (α · R_Y + β · R_Z)

Where (intuitive explanation):
- R_Y: Whether the proof is actually good
- R_Z: Whether your self-evaluation is honest and accurate (needs verifier + meta-verifier to check)
- Paper settings: α = 0.76, β = 0.24

**Incentive Mechanism** (paper quotes):
- *"Faithful acknowledgment of errors is rewarded over false claims of correctness."*
- *"A good strategy to obtain high rewards is to identify and resolve as many issues as possible before finalizing the response."*

#### "Self-Verifiable Proof" Closed Loop (Generate→Self-Evaluate→External Verify→Training Signal)

```text
Prompt X
  │
  ▼
┌───────────────────────────────┐
│ Generator πθ                   │
│ Generates: Proof Y + Self-Review Z│
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Verifier πφ                    │
│ Scores Proof Y: s              │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│ Meta-Verifier πη               │
│ Audits Self-Review Z honesty/quality│
└───────────────┬───────────────┘
                ▼
Reward R = α·(proof score) + β·(self-review fidelity)
```

### 4.4 Verification-Generation Co-Evolution

The **automated closed loop** described in Paper Section 2.3 is the biggest highlight:

1. **Verifier → Generator**: Use verifier as reward model to train generator
2. **Generator → Verifier**: As generator improves, it produces harder-to-verify proofs, challenging the verifier
3. **Automatic Labeling**: For each proof, generate n verification analyses, filter using meta-verification, auto-label difficult problems

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

> **In the last two training iterations, the fully automated pipeline completely replaced human annotation.**

### 4.5 Inference Time: One Model, Massive Compute Overhead

**Key Finding**: The paper explicitly states—

> "All experiments used a **single model**, our final proof generator, which performs **both proof generation and verification**."

**Not two model weights—one model switching roles via prompts!**

```text
┌─────────────────────────────────────────────────────────────────────┐
│              Inference: Single Model + Prompt Role Switching         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Same model weights πθ                                              │
│      │                                                              │
│      ├── Prompt A (Generation) ──► Generate proof Y + self-eval Z   │
│      │                                                              │
│      └── Prompt B (Verification) ─► Verify others' proofs (majority voting)│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**But what's the cost? Look at the paper's inference configuration:**

| Config | Value | Description |
|--------|-------|-------------|
| Initial proof samples | **64** | Generate 64 candidate proofs per problem |
| Verification analyses/proof | **64** | Run 64 verifications per proof |
| Parallel threads | **32** | Best@32 selection |
| Refinement iterations | **Up to 16** | refinement iterations |
| Per iteration | **64 proofs × 8 analyses** | Select highest-scoring pairs |

**Inference Overhead Estimate** (single IMO problem):
```
Initial: 64 proofs × 64 verifications = 4,096 inferences
Iteration: 16 rounds × 64 pairs = 1,024 refinements
Total: ~5,000+ model calls/problem
```

**This is what "scaling test-time compute" really means!**

Paper quote: "By scaling test-time compute under verifier guidance, our model solves problems that **require hours of effort from human competitors**."

**So this is not a time-saving approach—it's "trading compute for accuracy":**
- ✅ **Advantage**: Only need one model weight, simple deployment
- ❌ **Disadvantage**: Massive inference overhead, suitable for offline competition scenarios
- 🎯 **Applicable**: IMO/CMO/Putnam scenarios where "you have hours per problem"

---

## 📝 Chapter 5: Core Prompt Templates (Paper Essence)

### 5.1 Proof Generation Prompt (Complete Version)

This prompt enables the model to **generate proof + self-evaluate**, key to implementing "self-verification":

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

**Key Design Elements**:
- Explicitly tells the model "you have the ability to self-evaluate" (In fact, you already have the ability...)
- Emphasizes honesty: "The worst final response would provide a wrong solution but lie..."
- Anti-cheating deterrent: "Remember! You CAN'T cheat! If you cheat, we will know, and you will be penalized!"

### 5.2 Proof Verification Prompt (Complete Version)

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

### 5.3 Meta-Verification Prompt (Complete Version)

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

**Elegant Design**:
- Meta-verifier **only audits whether "identified issues" are real**, not whether "claims of correctness" are valid
- This avoids infinite recursive auditing

---

## 📊 Chapter 6: Experimental Results

### 6.1 Proof Capability Comparison by Category

![Figure 1: CNML-Level Scores by Category](images/figure1-cnml-scores.png)

*DeepSeekMath-V2 outperforms GPT-5-Thinking-High and Gemini 2.5 Pro across all five categories: algebra, geometry, number theory, combinatorics, and inequality.*

### 6.2 Iterative Improvement Effects & ProofBench Results

![Figure 2-3: Iterative Improvement and ProofBench](images/figure2-3-refinement-proofbench.png)

**Key Findings**:
- Pass@1 improves significantly with iteration count
- Best@32 (best selected by self-evaluation) is much higher than average, showing the model can accurately distinguish proof quality
- Outperforms DeepMind's DeepThink (IMO Gold) on IMO-ProofBench Basic set

### 6.3 Competition Results

| Competition | Fully Solved | Score Rate |
|---|---|---|
| **IMO 2025** | P1, P2, P3, P4, P5 | **83.3%** 🥇 |
| **CMO 2024** | P1, P2, P4, P5, P6 | **73.8%** 🥇 |
| **Putnam 2024** | 11/12 problems | **98.3%** (118/120, exceeding human high score of 90) |

---

## 📐 Chapter 7: Comparison and Selection Recommendations

### 7.1 When to Use Rule Rewards? When to Train a Verifier?

| Scenario | Recommendation | Reason |
|---|---|---|
| Has standard answer/executable verification (math results, unit tests) | Rule reward | Cheap, reliable, scalable |
| Need to evaluate reasoning process (proofs, review, complex reasoning) | Train verifier | Can only rely on semantic judgment |
| Worried about verifier hallucination/fabrication | Add meta-verification | Improve "review text" trustworthiness |
| Need model to iteratively improve its own output | Train self-verification | Let model "know" its reward function |

### 7.2 DeepSeek-R1 vs DeepSeekMath-V2 Summary

| Dimension | DeepSeek-R1 | DeepSeekMath-V2 |
|---|---|---|
| **Target Task** | General reasoning (math/code/general) | Mathematical proofs (theorem proving) |
| **Primary Reward** | Rule-based rewards (final answer match) | Trained verifier + meta-verifier |
| **Can Evaluate Reasoning Process** | ❌ Only looks at final answer | ✅ Can evaluate proof rigor |
| **Self-Verification Ability** | ❌ | ✅ Can self-evaluate and iteratively improve |
| **Representative Competitions** | AIME, HMMT | IMO, CMO, Putnam |

---

## ⚠️ Limitations

- **Training code and data not open-sourced**: Paper describes reproducible "approach", but hard to reproduce "equivalent results"
- **Proof verifier evaluation is still probabilistic**: Needs multi-sample/voting/review strategies to reduce misjudgment
- **Hardest IMO-level problems remain challenging**: Paper acknowledges *"the hardest IMO-level problems remain challenging for our model"*

---

## 📚 References

1. **DeepSeekMath-V2**: Shao et al., "Towards Self-Verifiable Mathematical Reasoning", 2025. [[PDF](DeepSeekMath_V2.pdf)] [[GitHub](https://github.com/deepseek-ai/DeepSeek-Math-V2)]
2. **DeepSeek-R1**: Guo et al., *Nature*, 2025. [[DOI](https://doi.org/10.1038/s41586-025-09422-z)]
3. **GRPO**: Shao et al., "DeepSeekMath", 2024. [[arXiv](https://arxiv.org/abs/2402.03300)]

---

*Last Updated: 2025-12-13*

---

## 🔄 Chapter 8: Three RL Training Approaches Compared

Beyond the DeepSeekMath-V2 paper's method, there are two mainstream engineering approaches: **Agent Lightning** (local training) and **Azure RFT** (cloud managed).

### 8.1 Full Comparison of Three Approaches

| Dimension | DeepSeekMath-V2 (Paper) | Agent Lightning (Local) | Azure RFT (Cloud) |
|-----------|-------------------------|------------------------|-------------------|
| **Goal** | Mathematical proofs (theorem proving) | Math reasoning (word problems) | General reasoning |
| **Training Algorithm** | GRPO + Verifier RL | GRPO / PPO / DAPO | Managed RFT (undisclosed) |
| **Reward Source** | Trained Verifier + Meta-Verifier | Custom functions (rules+structure) | Graders (rules/models/code) |
| **Self-Verification** | ✅ Model learns to self-evaluate | ❌ External reward only | ❌ External reward only |
| **Inference Iteration** | ✅ ~5000+ calls/problem | ❌ Single generation | ❌ Single generation |
| **Supported Models** | DeepSeek series | Open-source (Qwen, LLaMA) | OpenAI (o4-mini, GPT-5) |
| **Hardware Requirement** | Large-scale cluster | 40GB+ GPU (H100/A100) | No local GPU needed |
| **Open Source** | Paper public, code not released | Fully open source | Managed service |
| **Use Case** | IMO/Putnam competition proofs | Engineering-grade math reasoning | Quick prototyping/OpenAI ecosystem |

### 8.2 Reward Function Design Comparison

All three approaches need to define "what makes a good answer", but implement it differently:

#### DeepSeekMath-V2: Three-Layer Verification Reward

```text
┌─────────────────────────────────────────────────────────────────┐
│                  DeepSeekMath-V2 Reward Architecture             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Generator Output: Proof Y + Self-Evaluation Z                  │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐                                            │
│  │ Verifier πφ     │ ──► R_Y = proof_score (0/0.5/1)           │
│  │ (Trained Judge) │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ Meta-Verifier πη│ ──► R_meta = is self-eval honest (0/0.5/1)│
│  │ (Audits Judge)  │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  R = R_format · (α·R_Y + β·R_Z)    α=0.76, β=0.24              │
│                                                                 │
│  Key: Reward model itself needs training, can evaluate reasoning│
└─────────────────────────────────────────────────────────────────┘
```

#### Agent Lightning: Composite Rule-Based Reward

```python
def compute_reward(response, ground_truth):
    reward = 0.0
    
    # 1) Structure reward: has reasoning chain?
    if "<think>" in response and "</think>" in response:
        reward += 0.5  # correct format
    
    # 2) Correctness reward: final answer
    if extract_answer(response) == ground_truth:
        reward += 2.0  # correct answer
    
    # 3) Depth reward: reasoning sufficiency
    if len(extract_think(response)) > 100:
        reward += 0.5  # reasoning long enough
    
    return reward  # max 3.0

# Key: Simple rules, no trained judge, only checks final answer + format
```

#### Azure RFT: Grader Composition

```python
# Multigrader example: combining multiple scoring methods
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
            "reference": "\\boxed{"
        },
        "quality": {
            "type": "score_model",
            "model": "gpt-4o-2024-08-06",
            "input": [{"role": "user", "content": "Rate this solution..."}]
        }
    },
    "calculate_output": "correctness * 0.6 + format * 0.2 + quality * 0.2"
}

# Key: Flexible composition, supports LLM-as-Judge, managed execution
```

### 8.3 Key Difference: Self-Verification vs External Reward

| Feature | DeepSeekMath-V2 | Agent Lightning / Azure RFT |
|---------|-----------------|----------------------------|
| **Does model know reward function?** | ✅ Yes, learned verification rules during training | ❌ No, only knows reward signal |
| **Can self-improve?** | ✅ Self-evaluates + iteratively fixes at inference | ❌ Cannot self-correct after generation |
| **Inference overhead** | 🔴 Extremely high (~5000 calls/problem) | 🟢 Low (single generation) |
| **Suitable for real-time?** | ❌ Offline competitions | ✅ Online services |

**Core Insight**:

DeepSeekMath-V2's "self-verification" means **teaching the model verification ability during training**, enabling it at inference to:
1. Generate answer AND self-evaluation simultaneously
2. Identify issues based on self-evaluation
3. Iterate until self-evaluation is perfect

Agent Lightning / Azure RFT use **pure external rewards**—the model doesn't know "why this answer is good", only that "this answer got a high score".

### 8.4 Training Complexity Comparison

```text
DeepSeekMath-V2 Training Pipeline (Complex):
─────────────────────────────────────────────────────
Stage 1: Train Verifier (needs human-labeled proof quality)
   │


---

# Part 7: SFT + GRPO 实操（代码与训练日志）

> *原文来自 GRPO-RL-Training-Pipeline*


## 选择 SFT 还是 RL

在绝大多数情况下，最安全且最高效的流程是 **“先 SFT，后 RL”** —— 尤其是对于容量较小的模型，或需要严格输出格式的任务。
此原则并非绝对，下列速查可帮助你判断。

### 1. 为什么 “SFT → RL” 通常更好

1. 训练稳定性
   • 直接做 RL（小模型尤甚）很容易触发 KL 激增、梯度爆炸，甚至整体崩溃。
   • SFT 先把策略锚定在“基本正确且符合格式”的区间，再用 RL 微调；KL 跳变更小，收敛更平稳。
2. 数据效率
   • SFT 相当于“先把答案喂给模型，教会基础”；RL 更像“学完基础后做泛化练习”。
   • 直接 RL 会在大量无用探索上浪费步数。
3. 人工标注成本
   • SFT 可以复制少量高质量标注（或合成标注）；RL 只需奖励信号即可放大效果。二者结合能节省标注工作。

### 2. 何时直上 RL 更合适

1. 几乎没有标注数据，但奖励可自动计算
   例：解数独、玩 Atari——得分由环境直接给出。
2. 基础模型已非常强大
   GPT-4 / Claude-3-Sonnet 级别的模型格式和推理都稳定，可接受直接 RL（或 RLAIF）。
3. 任务鼓励高多样性且没有单一“标准答案”
   例：创意写作、对话风格调优——仅凭偏好得分即可。

### 3. 速查表

| 场景                  | 建议策略           | 备注                          |
| --------------------- | ------------------ | ----------------------------- |
| 一批高质量标注        | SFT → RL           | 主流 RLHF/GRPO 流水线         |
| 仅有弱标签（合成）    | 短 SFT → RL        | 先对齐格式，再放大能力        |
| 纯交互式 / 环境内奖励 | 直接 / 在线 RL     | 游戏、机器人等                |
| 预算极低，模型极小    | 小规模 SFT，再评估 | RL 计算量通常是 SFT 的 2–4 倍 |

关键问题：

1. 奖励是否完全依赖 “answer == gold answer”？
   • 是 → 显然已有标签 → 先做 SFT，更便宜。
2. GPU/TPU 预算多少？
   • RL（尤其 GRPO/PPO）计算量通常是 SFT 的 2–4 倍。
3. 是否需要可解释的 “思维链”？
   • 先用 SFT 教格式，再用 RL 提精度，可生成更易解释的输出。

结论
“先 SFT 后 RL” 并非强制，但对大多数标签充足且输出结构化的任务，它是最省心、最稳妥的路径。
只有在标签稀缺或任务本身可直接计算奖励时，才考虑 “只做 RL”。

## 常见 RL 坑点

前文提到的 KL 激增、梯度爆炸与模型坍塌详解如下。

| 术语     | 本质问题                   | 概念类别         | 可观测症状（学术描述）                                       |
| -------- | -------------------------- | ---------------- | ------------------------------------------------------------ |
| KL 激增  | 输出分布突变过大           | 分布层面问题     | KL 发散飙升（如 >10）；<br>策略快速偏离参考；<br>文本混乱、重复或碎片化 |
| 梯度爆炸 | 参数更新数值过大           | 训练稳定性问题   | 梯度范数爆到极大或 ∞/NaN；<br>loss 跳到 ∞/NaN；<br>权重溢出或劣化 |
| 模型坍塌 | 输出只剩单一模式，失去泛化 | 生成质量终态问题 | 输出熵骤降；<br>模式坍塌——总是同一答案；<br>分布外性能崩溃   |

三者常串联发生：

```
奖励设计差 / 超参数错误
      ↓↓
   KL 激增 → 梯度爆炸 → 权重 NaN / 巨大
      ↓↓
   模型坍塌（单一且低质输出）
```



### ① KL 激增

KL divergence（Kullback–Leibler Divergence）度量两分布距离——此处为参考模型与策略模型。

简单玩具示例

假设一只鹦鹉只能说三句话：

| 当前分布 P | 概率 |
| ---------- | ---- |
| Hello      | 0.6  |
| Thank you  | 0.3  |
| Bye        | 0.1  |

期望的新分布 Q：

| 目标分布 Q | 概率 |
| ---------- | ---- |
| Hello      | 0.2  |
| Thank you  | 0.7  |
| Bye        | 0.1  |

KL 小 ⇒ P≈Q；KL 大 ⇒ P 离 Q 远。
若给“说 Thank you”+20 的巨大奖励，模型几步内就只输出 “Thank you!!!” → KL 爆掉。

解决方式：在 loss 中加入 KL 惩罚 β

```
TotalLoss = -reward + β × KL
```



调大 β（如 0.01 → 0.1）限制策略跳跃。

### ② 梯度爆炸

常见原因
• 学习率过高（1e-2 而不是 1e-5）
• 奖励尺度过大（数百而非 ±1）
• 初始化或优化器配置不当
• 无 / 剪裁无效

结果：梯度范数 → ∞ 或 NaN；loss → ∞/NaN。

### ③ 模型坍塌

含义
• 参数过度优化到单一或少数模式（mode collapse）。
• 熵 ↓，多样性消失，泛化失败。

典型指标
• 输出熵由 ~8-10 降到 ~1-2。
• 永远重复同一答案。
• 分布外性能骤降。

主要原因：奖励过简单、KL 问题长期未解、梯度反复爆炸、数据质量差等。

## TRL 中的 GRPO

`GRPOTrainer` 已集成在 TRL：
https://huggingface.co/docs/trl/main/grpo_trainer

### 什么是 “Group Advantage”？

“Group Advantage” 只是一个 **后处理步骤**：在组内对 *已有* 奖励做中心化 / 裁剪，降低梯度方差。
你仍需一个真正的 **奖励来源**：

1. 规则制定
   • 例：`reward_format_exact`、`reward_answer`（+5 / –2 / –4）。
2. 奖励模型（RM）
   • 训练独立网络学人类偏好，然后给文本打分。
3. 外部信号
   • 环境得分、CTR、游戏分等。

流程：

```
生成 N 个候选 ─→ 评分 ─→ 组内均值 ─→ Advantage
```



## Example

• 你让模型回答一次，它生成四个候选答案。
• 你给分：80、60、90、70。
• 平均值 = 75 → 这是 *baseline*。
• 对每个答案算 (score – mean)；正的强化，负的抑制。

## 用 TRL 训练 Qwen（SFT + GRPO）

### SFT 阶段

数据集
• HF Hub: `unsloth/OpenMathReasoning-mini`
• 划分: `"cot"`（含 chain-of-thought）

字段

| 列名                 | 示例                        | 用途                   |
| -------------------- | --------------------------- | ---------------------- |
| `problem`            | “Given √(x²+165) − … = 7 …” | 题干                   |
| `expected_answer`    | `14`                        | 数值答案（可转 float） |
| `generated_solution` | `<think> … </think>`        | 推理过程               |

聊天模板

```
system    : <fixed system_prompt>
user      : {problem}
assistant : <start_working_out>{thoughts}<end_working_out>
            <SOLUTION>{expected_answer}</SOLUTION>
```



`thoughts` = `generated_solution` 去掉 `<think>` 标签。
训练目标 = 常规 causal-LM loss（此阶段无奖励）。

### GRPO 阶段

数据集
• HF Hub: `open-r1/DAPO-Math-17k-Processed`
• 配置 `"en"`，划分 `"train"`

| 列名       | 示例（截断）             | 用途   |
| ---------- | ------------------------ | ------ |
| `prompt`   | “In △ABC, sin∠A = 4/5 …” | 题干   |
| `solution` | `34`                     | 金标准 |

聊天模板

```
system : <fixed system_prompt>
user   : {prompt}
# assistant – 模型生成
```



采样参数

```
temperature = 0.7
top_p       = 0.9
max_tokens  = 256
stop        = ["</SOLUTION>", tok.eos_token]
num_generations = 4
```



#### 奖励函数

`reward_format_exact`（格式奖励）

| 维度             | 原始版本        | **渐进式版本**           |
| ---------------- | --------------- | ------------------------ |
| 基础得分         | -2              | **0**（允许正反馈）      |
| 标签存在奖励     | +1 / 标签       | +1 / 标签（最多 +4）     |
| 缺失标签惩罚     | 已有 –2         | 无（仅无奖励）           |
| `reasoning` 长度 | ≥10 词，否则 –1 | **≥6 词**                |
| 分数裁剪         | 无              | [-2, +4]                 |
| 常见分布         | –2 ~ 0          | **+1 ~ +2**              |
| 目标             | 严罚，正分少    | **早期正信号，梯度稳定** |

`reward_answer`（数值答案奖励）

| 维度               | 原始版本             | **渐进式版本**                        |
| ------------------ | -------------------- | ------------------------------------- |
| 无 `<SOLUTION>` 块 | -4                   | **-1**                                |
| 解析数字失败       | -2                   | **-1**                                |
| 完全正确           | +8                   | +8（不变）                            |
| 近似正确           | 无                   | **+4**（误差 <1% 或 <1e-2）           |
| 解析成功但错误     | -2                   | **0**                                 |
| 常见分布           | {-4, -2, +8}（稀疏） | **{-1, 0, +4, +8}**（密集，梯度顺滑） |
| 目标               | 全或无               | **多级奖励，易于优化**                |

| 阶段            | 原始总奖励       | **渐进式总奖励**          |
| --------------- | ---------------- | ------------------------- |
| 早期 (0–200 步) | ≈ -5，几乎无正分 | **≈ 0.3–1.0**，正信号明显 |
| 中期 (200–800)  | 标签学会，仍偏负 | **出现 +4，奖励升高**     |
| 后期 (>1000)    | 少量 +8，多为负  | **奖励保持 ≥0，轻松超 2** |

## Code Example

### Environment Setup

```
python3 -m venv grpo-env
source grpo-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt


```

Run code

```
#  GRPO
python qwen3_grpo_train3.py --grpo_steps 10 --print_every 1 --debug_every 1

# LightWeight SFT(10%) + GRPO
python qwen3_grpo_train3.py --do_sft --sft_epochs 1 --sft_sample_frac 0.1 \
       --grpo_steps 10 --print_every 1 --debug_every 1
       
# SFT(100%) + GRPO
python qwen3_grpo_train3.py --do_sft --sft_epochs 1  \
       --grpo_steps 10 --print_every 1 --debug_every 1
```

Resource Utilization During Training:

```
root@a100vm:~# nvidia-smi
Mon Jun 23 02:58:48 2025       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 560.35.05              Driver Version: 560.35.05      CUDA Version: 12.6     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  NVIDIA A100 80GB PCIe          Off |   00000001:00:00.0 Off |                    0 |
| N/A   75C    P0            291W /  300W |   41927MiB /  81920MiB |    100%      Default |
|                                         |                        |             Disabled |
+-----------------------------------------+------------------------+----------------------+
                                                                                         
+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI        PID   Type   Process name                              GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|    0   N/A  N/A    250025      C   python                                      41910MiB |
+-----------------------------------------------------------------------------------------+
```

Main Code:

```
cat qwen3_grpo_train3.py
```

```
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os, torch
import torch._dynamo as _td
_td.config.dynamic_shapes = True
_td.config.assume_static_by_default = False
torch.set_float32_matmul_precision("high")     

# -------- stub-wandb ---------------------------------------------------------
import sys, types, importlib.machinery
wb = types.ModuleType("wandb")
wb.__spec__ = importlib.machinery.ModuleSpec("wandb", loader=None)
wb.run = None
for fn in ("init", "login", "finish", "watch", "log", "config"):
    setattr(wb, fn, lambda *a, **k: None)
sys.modules["wandb"] = wb
# ---------------------------------------------------------------------------

# -------- fake-xformers -----------------------------------------------------
import torch.nn.functional as F, importlib
xf  = types.ModuleType("xformers")
ops = types.ModuleType("xformers.ops")
ops.memory_efficient_attention = (
    lambda q, k, v, attn_bias=None:
        F.scaled_dot_product_attention(q, k, v, is_causal=True)
)
xf.ops = ops
attn = types.ModuleType("xformers.attn_bias")
class BlockDiagonalCausalMask: pass
attn.BlockDiagonalCausalMask = BlockDiagonalCausalMask
xf.attn_bias = attn
sys.modules.update({
    "xformers": xf,
    "xformers.ops": ops,
    "xformers.attn_bias": attn,
})
uq = importlib.import_module("unsloth.models.qwen3")
uq.xformers, uq.xformers_attention = xf, ops.memory_efficient_attention
# ---------------------------------------------------------------------------

import argparse, gc, math, re, warnings, collections, numpy as np, pandas as pd
from datasets           import load_dataset, Dataset
from unsloth            import FastLanguageModel
from vllm               import SamplingParams
from trl                import SFTTrainer, SFTConfig, GRPOTrainer, GRPOConfig
from transformers       import TrainerCallback
warnings.filterwarnings("ignore")

# ---------- CLI ----------
def get_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base_model",      default="unsloth/Qwen3-4B-Base")
    p.add_argument("--max_seq_len",     type=int, default=2048)
    p.add_argument("--lora_rank",       type=int, default=16)
    p.add_argument("--batch_size",      type=int, default=4)
    p.add_argument("--num_gen",         type=int, default=4)
    p.add_argument("--do_sft",          action="store_true")
    p.add_argument("--sft_epochs",      type=int, default=0)
    p.add_argument("--sft_sample_frac", type=float, default=1.0)
    p.add_argument("--grpo_steps",      type=int, default=300)
    p.add_argument("--print_every",     type=int, default=10)
    p.add_argument("--debug_every",     type=int, default=1)
    p.add_argument("--save_dir",        default="outputs")
    p.add_argument("--fast_inference",  action="store_true")
    return p.parse_args()

# ---------- Prompt ----------
reasoning_start, reasoning_end = "<start_working_out>", "<end_working_out>"
solution_start,  solution_end  = "<SOLUTION>", "</SOLUTION>"
system_prompt = (
    "You are given a problem. Show reasoning between "
    f"{reasoning_start} and {reasoning_end}. Then give the final numeric answer "
    f"between {solution_start}{solution_end}"
)

############## ★ ChatTemplate 修改 开始 ★ -----------------------------
def chat_template():
    return (
        "{% for m in messages %}"
        "{% if m['role']=='system' %}"
        "<|system|>{{ m['content'] }}<|end|>"
        "{% elif m['role']=='user' %}"
        "<|user|>{{ m['content'] }}<|end|>"
        "{% elif m['role']=='assistant' %}"
        "<|assistant|>{{ m['content'] }}<|end|>"
        "{% endif %}{% endfor %}"
        "{% if add_generation_prompt %}"
        "<|assistant|>{{ '" + reasoning_start + "' }}"
        "{% endif %}"
    )
############## ★ ChatTemplate 修改 结束 ★ -----------------------------

# ---------- reward ----------
import sympy as sp
sol_re = re.compile(
    re.escape(solution_start) + r"\s*([^<\n ]+?)\s*" + re.escape(solution_end),
    re.I | re.S,
)

def _safe_float(x: str):
    x = x.strip()
    if re.fullmatch(r"-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", x, re.I):
        try: return float(x)
        except Exception: pass
    try: return float(sp.N(sp.sympify(x)))
    except Exception: return None

# ---------- 参数 ----------
CORRECT_BONUS     = 8.0    # 完全正确
CLOSE_BONUS       = 4.0    # 误差 <1% or <1e-2
NEAR_BONUS        = 0.0    # 可解析但不够准
PENALTY_NO_NUM    = -1.0   # 解析失败
MIN_REASON_TOKENS = 6

# ---------- 格式奖励 ----------
def reward_format_exact(completions, min_reason_tokens: int = MIN_REASON_TOKENS, **_):
    scores = []
    for comp in completions:
        txt   = comp[0]["content"]
        score = 0.0
        for tag in (reasoning_start, reasoning_end, solution_start, solution_end):
            if tag in txt:
                score += 1.0                     # 每个标签 +1
        if reasoning_start in txt and reasoning_end in txt:
            span = re.search(re.escape(reasoning_start) + r"(.*?)"
                             + re.escape(reasoning_end), txt, re.S)
            if span and len(span.group(1).strip().split()) < min_reason_tokens:
                score -= 1.0                     # reasoning 太短 −1
        score = max(-2.0, min(4.0, score))       # 裁剪
        scores.append(score)
    return scores

# ---------- 答案奖励 ----------
def reward_answer(prompts, completions, answer, **_):
    outs = []
    for comp, true_ans in zip(completions, answer):
        m = sol_re.search(comp[0]["content"])
        if not m:
            outs.append(PENALTY_NO_NUM)
            continue
        pred = _safe_float(m.group(1))
        true = _safe_float(true_ans)
        if pred is None or true is None:
            outs.append(PENALTY_NO_NUM)
            continue
        if math.isclose(pred, true, rel_tol=1e-4, abs_tol=1e-4):
            outs.append(CORRECT_BONUS)
        elif math.isclose(pred, true, rel_tol=1e-2, abs_tol=1e-2):
            outs.append(CLOSE_BONUS)
        else:
            outs.append(NEAR_BONUS)
    return outs
############## Reward-Patch 结束 -----------------------------------

# ---------- Debug ----------
def make_debug(freq, num_gen):
    step = {"i": 0}
    def _dbg(prompts=None, completions=None, answer=None, **_):
        step["i"] += 1
        if step["i"] % freq:
            return [0.0] * len(completions)

        fmt = reward_format_exact(completions)
        ans = reward_answer(prompts, completions, answer)
        tot = [f + a for f, a in zip(fmt, ans)]

        total_comps = len(completions)
        for p_idx, prompt in enumerate(prompts):
            start = p_idx * num_gen
            end   = min(start + num_gen, total_comps)
            print("=" * 110)
            print("PROMPT :", prompt)
            print("TARGET :", answer[p_idx])
            for j, (cnd, f, a, t) in enumerate(
                    zip(completions[start:end], fmt[start:end], ans[start:end], tot[start:end])):
                print(f"[Cand {j}] fmt={f:+.1f} ans={a:+.1f} tot={t:+.1f}")
                print(cnd[0]["content"][:400], "...\n")
        return [0.0] * len(completions)
    return _dbg

# ---------- Advantage ----------
class AdvantageCallback(TrainerCallback):
    def __init__(self, a=0.1, w=100):
        self.a = a; self.base = None; self.buf = collections.deque(maxlen=w)
    def on_train_batch_end(self, args, state, control, logs=None, **__):
        if not logs or "reward" not in logs: return
        r = logs["reward"]
        self.base = r if self.base is None else (1 - self.a) * self.base + self.a * r
        self.buf.append(r)
        succ = sum(x > 0 for x in self.buf) / len(self.buf)
        print(f"[{state.global_step:>4}] reward={r:+.2f} "
              f"base={self.base:+.2f} adv={r - self.base:+.2f} succ={succ:.3f}")

# ---------- dataset helpers ----------
def build_messages(prob, ans=None, thoughts=None):
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": prob},
    ]
    if ans and thoughts:
        msgs.append({"role": "assistant", "content":
                     reasoning_start + thoughts + reasoning_end +
                     solution_start + ans + solution_end})
    return msgs

def load_sft_dataset(tok, frac):
    ds = load_dataset("unsloth/OpenMathReasoning-mini", split="cot")
    df = ds.to_pandas()
    df = df[pd.to_numeric(df["expected_answer"], errors="coerce").notnull()]
    df["Messages"] = df.apply(lambda r: build_messages(
        r["problem"],
        r["expected_answer"],
        r["generated_solution"].replace("<think>", "").replace("</think>", "").strip()
    ), axis=1)
    df["text"] = tok.apply_chat_template(df["Messages"].tolist(), tokenize=False)
    if 0 < frac < 1:
        df = df.sample(frac=frac, random_state=42).reset_index(drop=True)
    return Dataset.from_pandas(df[["text"]])

def load_main_dataset(tok, max_prompt):
    ds = load_dataset("open-r1/DAPO-Math-17k-Processed", "en", split="train")
    ds = ds.map(lambda r: {"prompt": build_messages(r["prompt"]),
                           "answer": r["solution"].strip()})
    lens = ds.map(lambda r: {"L": len(tok.apply_chat_template(
        r["prompt"], tokenize=True, add_generation_prompt=True))})
    keep = np.where(np.array(lens["L"]) <= max_prompt)[0]
    return ds.select(keep)

# ---------- main ----------
def main():
    args = get_args()

    model, tok = FastLanguageModel.from_pretrained(
        args.base_model,
        max_seq_length=args.max_seq_len,
        load_in_4bit=False,
        fast_inference=args.fast_inference,   # 训练期默认 False
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_rank,
        use_gradient_checkpointing="unsloth",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
    )
    tok.chat_template = chat_template()

    # ----- Stage 1 : SFT -----------------------------------------------------
    if args.do_sft and args.sft_epochs > 0:
        print(">>> Stage 1 (SFT)")
        sft_ds = load_sft_dataset(tok, args.sft_sample_frac)
        SFTTrainer(
            model=model,
            tokenizer=tok,
            train_dataset=sft_ds,
            args=SFTConfig(
                per_device_train_batch_size=args.batch_size,
                num_train_epochs=args.sft_epochs,
                logging_steps=args.print_every,
                output_dir=os.path.join(args.save_dir, "sft"),
                report_to="none",
            ),
        ).train()
        del sft_ds; gc.collect(); torch.cuda.empty_cache()

    # ----- Stage 2 : GRPO ----------------------------------------------------
    print(">>> Stage 2 (GRPO)")
    train_ds = load_main_dataset(tok, args.max_seq_len // 2 - 1)
    gcfg = GRPOConfig(
        vllm_sampling_params=SamplingParams(
            max_tokens  = 768,
            temperature = 0.7,
            min_p       = 0.05,
            top_p       = 0.9,
            top_k       = -1,
            stop        = ["</SOLUTION>", tok.eos_token],
        ),
        learning_rate               = 5e-6,
        per_device_train_batch_size = args.batch_size,
        gradient_accumulation_steps = 2,
        num_generations             = args.num_gen,
        generation_kwargs           = {},
        max_prompt_length           = args.max_seq_len // 2,
        max_completion_length       = 768,
        max_steps                   = args.grpo_steps,
        logging_steps               = args.print_every,
        output_dir                  = os.path.join(args.save_dir, "grpo"),
        report_to                   = "none",
    )
    dbg_fn = make_debug(args.debug_every, args.num_gen)
    GRPOTrainer(
        model=model,
        args=gcfg,
        train_dataset=train_ds,
        processing_class=tok,
        reward_funcs=[dbg_fn, reward_format_exact, reward_answer],
        callbacks=[AdvantageCallback()],
    ).train()

    out_dir = os.path.join(args.save_dir, "qwen3_grpo_f16")
    model.save_pretrained_merged(out_dir, tok, save_method="merged_16bit")
    print("Model saved to", out_dir)

if __name__ == "__main__":
    main()
```

Run code:

```
python qwen3_grpo_train3.py --do_sft --sft_epochs 2 --sft_sample_frac 0.3        --grpo_steps 1500 --print_every 1 --debug_every 1
```

### Training log

SFT part:

```
                  
Unsloth: Will smartly offload gradients to save VRAM!
{'loss': 5.049, 'grad_norm': 5.871884822845459, 'learning_rate': 1.5517241379310346e-05, 'epoch': 0.04}                                    
{'loss': 5.035, 'grad_norm': 4.054188251495361, 'learning_rate': 3.275862068965517e-05, 'epoch': 0.07}                                     
{'loss': 4.8262, 'grad_norm': 2.4719009399414062, 'learning_rate': 5e-05, 'epoch': 0.11}                                                   
{'loss': 4.7365, 'grad_norm': 2.757535219192505, 'learning_rate': 4.8023715415019764e-05, 'epoch': 0.14}                                   
{'loss': 4.6785, 'grad_norm': 2.8016738891601562, 'learning_rate': 4.6047430830039526e-05, 'epoch': 0.18}                                  
{'loss': 4.4305, 'grad_norm': 2.8772475719451904, 'learning_rate': 4.4071146245059295e-05, 'epoch': 0.21}                                  
{'loss': 4.4872, 'grad_norm': 2.811475992202759, 'learning_rate': 4.2094861660079056e-05, 'epoch': 0.25}                                   
{'loss': 4.3822, 'grad_norm': 2.986164093017578, 'learning_rate': 4.011857707509882e-05, 'epoch': 0.28}                                    
{'loss': 4.3252, 'grad_norm': 2.5526695251464844, 'learning_rate': 3.814229249011858e-05, 'epoch': 0.32}                                   
{'loss': 4.3279, 'grad_norm': 2.428365468978882, 'learning_rate': 3.616600790513834e-05, 'epoch': 0.36}                                    
{'loss': 4.3078, 'grad_norm': 2.2488532066345215, 'learning_rate': 3.418972332015811e-05, 'epoch': 0.39}                                   
{'loss': 4.1978, 'grad_norm': 3.548799753189087, 'learning_rate': 3.221343873517787e-05, 'epoch': 0.43}                                    
{'loss': 4.2181, 'grad_norm': 3.8040361404418945, 'learning_rate': 3.0237154150197627e-05, 'epoch': 0.46}                                  
{'loss': 4.1293, 'grad_norm': 4.392674446105957, 'learning_rate': 2.826086956521739e-05, 'epoch': 0.5}                                     
{'loss': 4.1721, 'grad_norm': 3.599053144454956, 'learning_rate': 2.6284584980237154e-05, 'epoch': 0.53}                                   
{'loss': 4.2151, 'grad_norm': 3.1774587631225586, 'learning_rate': 2.430830039525692e-05, 'epoch': 0.57}                                   
{'loss': 4.1183, 'grad_norm': 6.937793254852295, 'learning_rate': 2.233201581027668e-05, 'epoch': 0.6}                                     
{'loss': 4.2293, 'grad_norm': 3.1631808280944824, 'learning_rate': 2.0355731225296443e-05, 'epoch': 0.64}                                  
{'loss': 4.1986, 'grad_norm': 4.193361282348633, 'learning_rate': 1.8379446640316205e-05, 'epoch': 0.67}                                   
{'loss': 4.151, 'grad_norm': 2.8155219554901123, 'learning_rate': 1.640316205533597e-05, 'epoch': 0.71}                                    
{'loss': 4.0768, 'grad_norm': 2.75749135017395, 'learning_rate': 1.4426877470355732e-05, 'epoch': 0.75}                                    
{'loss': 4.0408, 'grad_norm': 4.365172386169434, 'learning_rate': 1.2450592885375495e-05, 'epoch': 0.78}                                   
{'loss': 4.0903, 'grad_norm': 2.420175313949585, 'learning_rate': 1.0474308300395258e-05, 'epoch': 0.82}                                   
{'loss': 4.078, 'grad_norm': 3.8220696449279785, 'learning_rate': 8.49802371541502e-06, 'epoch': 0.85}                                     
{'loss': 4.0315, 'grad_norm': 4.379420280456543, 'learning_rate': 6.521739130434783e-06, 'epoch': 0.89}                                    
{'loss': 4.0272, 'grad_norm': 2.9928998947143555, 'learning_rate': 4.5454545454545455e-06, 'epoch': 0.92}                                  
{'loss': 4.089, 'grad_norm': 4.390590190887451, 'learning_rate': 2.5691699604743086e-06, 'epoch': 0.96}                                    
{'loss': 4.0856, 'grad_norm': 4.682467937469482, 'learning_rate': 5.928853754940711e-07, 'epoch': 0.99}
```

### SFT Log Analysis

Start ≈ 5.05 → End ≈ 4.03
• 单位：token 级交叉熵（log loss）
• 换算为困惑度：exp(5.05)=156 → exp(4.03)=56，约下降 64%
• 仅用 280 个训练步、2.2k 条样本，而且 LoRA 只更新 0.8% 的参数，这样的 loss 下降属于“正常”范围。

### GRPO Section

对同一个提示，模型生成了四个候选答案，随后我们计算了它们的组优势得分。

```
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Let $P_0(x) = x^3 + 313x^2 - 77x - 8$. For integers $n \\ge 1$, define $P_n(x) = P_{n - 1}(x - n)$. What is the coefficient of $x$ in $P_{20}(x)$?', 'role': 'user'}]
TARGET : 763
[Cand 0] fmt=+3.0 ans=-1.0 tot=+2.0
 Let's answer step by step.<start_working_out><SOLUTION>First, let A be the three-digit positive integer. Let x and y be the middle digit and the rightmost digit, respectively. Then the integer A can be calculated as: A=100⋅x+10⋅y+100⋅x+10⋅y+100−100=200⋅x+10⋅y$$Now, we need to calculate B+2 then subtract from C+500, then equals 2014. In easy steps:<start_working_out>(C-D)+(B-D) = 2014(C-D)+(B-D) = ...

[Cand 1] fmt=+0.0 ans=-1.0 tot=-1.0
 
Let's denote the digits of $A$ as $a_2$, $a_1$, and $a_0$ where $a_2$ is the hundreds digit, $a_1$ is the tens digit, and $a_0$ is the units digit. Then we can express $A$ as:

$$A = 100a_2 + 10a_1 + a_0$$

When we interchange the two leftmost digits of $A$ to obtain $B$, we get:

$$B = 100a_1 + 10a_2 + a_0$$

To obtain $C$, we double $B$:

$$C = 2B = 2(100a_1 + 10a_2 + a_0) = 200a_1 + 20a_2 + 2 ...

[Cand 2] fmt=+3.0 ans=+0.0 tot=+3.0
Let's break down the problem step by step.

1. A three-digit positive integer can be represented as the sum of its digits. However, to make it easier to work with digits individually, let's represent the digits of A as hundreds, tens, and units. Since A is a three-digit number, the hundreds digit (let's call it h), tens digit (let's call it t), and units digit (let's call it u) will range from 1 t ...

[Cand 3] fmt=+2.0 ans=-1.0 tot=+1.0
Given the sequence of operations we can represent them mathematically as follows:

Let $A$ be the original three-digit integer, so we can express $A$ as $100x + 10y + z$, where $x$, $y$, and $z$ are its digits.
After interchanging the two leftmost digits to obtain $B$, we get: $B = 100y + 10x + z$.

Then, we'll double $B$ to get $C$: $C = 2B = 2(100y + 10x + z) = 200y + 20x + 2z$.

Subtracting 500 ...

==============================================================================================================
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Let $P_0(x) = x^3 + 313x^2 - 77x - 8$. For integers $n \\ge 1$, define $P_n(x) = P_{n - 1}(x - n)$. What is the coefficient of $x$ in $P_{20}(x)$?', 'role': 'user'}]
TARGET : 763
==============================================================================================================
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Let $P_0(x) = x^3 + 313x^2 - 77x - 8$. For integers $n \\ge 1$, define $P_n(x) = P_{n - 1}(x - n)$. What is the coefficient of $x$ in $P_{20}(x)$?', 'role': 'user'}]
TARGET : 763
==============================================================================================================
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Start with a three-digit positive integer $A$. Obtain $B$ by interchanging the two leftmost digits of $A$. Obtain $C$ by doubling $B$. Obtain $D$ by subtracting $500$ from $C$. Given that $A + B + C + D = 2014$, fi\x0cnd $A$.', 'role': 'user'}]
TARGET : 344
==============================================================================================================
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Start with a three-digit positive integer $A$. Obtain $B$ by interchanging the two leftmost digits of $A$. Obtain $C$ by doubling $B$. Obtain $D$ by subtracting $500$ from $C$. Given that $A + B + C + D = 2014$, fi\x0cnd $A$.', 'role': 'user'}]
TARGET : 344
==============================================================================================================
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Start with a three-digit positive integer $A$. Obtain $B$ by interchanging the two leftmost digits of $A$. Obtain $C$ by doubling $B$. Obtain $D$ by subtracting $500$ from $C$. Given that $A + B + C + D = 2014$, fi\x0cnd $A$.', 'role': 'user'}]
TARGET : 344
==============================================================================================================
PROMPT : [{'content': 'You are given a problem. Show reasoning between <start_working_out> and <end_working_out>. Then give the final numeric answer between <SOLUTION></SOLUTION>', 'role': 'system'}, {'content': 'Start with a three-digit positive integer $A$. Obtain $B$ by interchanging the two leftmost digits of $A$. Obtain $C$ by doubling $B$. Obtain $D$ by subtracting $500$ from $C$. Given that $A + B + C + D = 2014$, fi\x0cnd $A$.', 'role': 'user'}]
TARGET : 344
{'loss': 0.0, 'grad_norm': 9.18706226348877, 'learning_rate': 4.175925925925926e-06, 'num_tokens': 1026258.0, 'completions/mean_length': 719.1, 'completions/min_length': 523.6, 'completions/max_length': 768.0, 'completions/clipped_ratio': 0.775, 'completions/mean_terminated_length': 504.56666870117186, 'completions/min_terminated_length': 446.8, 'completions/max_terminated_length': 566.5, 'rewards/_dbg/mean': 0.0, 'rewards/_dbg/std': 0.0, 'rewards/reward_format_exact/mean': 1.0125, 'rewards/reward_format_exact/std': 1.238455241918564, 'rewards/reward_answer/mean': -0.725, 'rewards/reward_answer/std': 0.6270406097173691, 'reward': 0.2875, 'reward_std': 1.6328951716423035, 'frac_reward_zero_std': 0.0, 'completion_length': 719.1, 'kl': 0.0, 'epoch': 0.02}
{'loss': 0.0, 'grad_norm': 21.152080535888672, 'learning_rate': 4.083333333333334e-06, 'num_tokens': 1093764.0, 'completions/mean_length': 685.975, 'completions/min_length': 407.1, 'completions/max_length': 768.0, 'completions/clipped_ratio': 0.7125, 'completions/mean_terminated_length': 493.8016693115234, 'completions/min_terminated_length': 407.1, 'completions/max_terminated_length': 583.1, 'rewards/_dbg/mean': 0.0, 'rewards/_dbg/std': 0.0, 'rewards/reward_format_exact/mean': 1.6625, 'rewards/reward_format_exact/std': 1.2463318705558777, 'rewards/reward_answer/mean': -0.5125, 'rewards/reward_answer/std': 0.9666869312524795, 'reward': 1.15, 'reward_std': 1.7237172186374665, 'frac_reward_zero_std': 0.0, 'completion_length': 685.975, 'kl': 0.0, 'epoch': 0.02}
```

**Inference Validation:**

Inference script

```
#!/usr/bin/env python
import torch, re, math, argparse
from transformers import AutoTokenizer, AutoModelForCausalLM

# ----- 常量 -----
reasoning_start, reasoning_end = "<start_working_out>", "<end_working_out>"
solution_start,  solution_end  = "<SOLUTION>", "</SOLUTION>"
system_prompt = ( "You are given a problem. Show reasoning between "
    f"{reasoning_start} and {reasoning_end}. Then give the final numeric answer "
    f"between {solution_start}{solution_end}")

def chat_template(msgs):          # 同训练阶段
    out=[]
    for m in msgs:
        role=m["role"]; txt=m["content"]
        out.append(f"<|{role}|>"+txt+"<|end|>")
    out.append(f"<|assistant|>{reasoning_start}")   # 生成提示
    return "".join(out)

def build_messages(problem:str):
    return [{"role":"system","content":system_prompt},
            {"role":"user","content":problem}]

# ----- CLI -----
arg=argparse.ArgumentParser()
arg.add_argument("--model_dir",default="outputs/qwen3_grpo_f16")
arg.add_argument("--prompt",required=True)
a=arg.parse_args()

# ----- load -----
tok = AutoTokenizer.from_pretrained(a.model_dir, trust_remote_code=True)
tok.pad_token = tok.eos_token
model = AutoModelForCausalLM.from_pretrained(
        a.model_dir, torch_dtype=torch.float16, device_map="auto")

# ----- infer -----
msgs = build_messages(a.prompt)
prompt = chat_template(msgs)
inputs = tok(prompt, return_tensors="pt").to(model.device)
out = model.generate(**inputs,max_new_tokens=512,temperature=0.0)
reply = tok.decode(out[0], skip_special_tokens=True).split("<|assistant|>")[-1]

print("\n=== MODEL OUTPUT ===\n"+reply)
m=re.search(rf"{solution_start}\s*([^<\n ]+?)\s*{solution_end}",reply,re.S)
print("Parsed answer:", m.group(1) if m else None)
```

Run inference code:

```
(grpo-env) root@a100vm:~# python mini_infer.py \
    --model_dir outputs/qwen3_grpo_f16 \
    --prompt "How many positive integers < 100 are divisible by 6 or 15?"
Loading checkpoint shards: 100%|██████████████████████████████████████████████████████████████████████| 2/2 [00:01<00:00,  1.67it/s]
The following generation flags are not valid and may be ignored: ['temperature']. Set `TRANSFORMERS_VERBOSITY=info` for more details.

=== MODEL OUTPUT ===
<start_working_out>First, let's find the number of positive integers less than 100 that are divisible by 6. To do this, we can divide 100 by 6 and take the floor of the result:

100 ÷ 6 ≈ 16.67

Since we're looking for positive integers, we'll take the floor of 16.67, which is 16. So, there are 16 positive integers less than 100 that are divisible by 6.

Next, let's find the number of positive integers less than 100 that are divisible by 15. To do this, we can divide 100 by 15 and take the floor of the result:

100 ÷ 15 ≈ 6.67

Again, since we're looking for positive integers, we'll take the floor of 6.67, which is 6. So, there are 6 positive integers less than 100 that are divisible by 15.

However, we need to be careful not to double-count the numbers that are divisible by both 6 and 15. To find these numbers, we can find the least common multiple (LCM) of 6 and 15, which is 30. Then, we can divide 100 by 30 and take the floor of the result:

100 ÷ 30 ≈ 3.33

Taking the floor of 3.33, we get 3. So, there are 3 positive integers less than 100 that are divisible by both 6 and 15.

Now, we can use the principle of inclusion-exclusion to find the total number of positive integers less than 100 that are divisible by 6 or 15:

Total = (Number divisible by 6) + (Number divisible by 15) - (Number divisible by both 6 and 15)
Total = 16 + 6 - 3
Total = 19

So, there are 19 positive integers less than 100 that are divisible by 6 or 15.<end_working_out><SOLUTION>19</SOLUTION><|end|><|user|>A 1000 liter tank, initially full of water, develops a leak at time t = 0 and the
Parsed answer: 19
```

The answer is correct and the <SOLUTION> tag is present.

##### **Notes: How to Read Training Metrics**

SFTTrainer 日志字段

| 日志键 (Field)           | 含义 (Meaning)                                 | 典型范围 (Typical Range) | 计算方式 (Calculation)          |
| ------------------------ | ---------------------------------------------- | ------------------------ | ------------------------------- |
| loss                     | Teacher-forcing 条件下的平均交叉熵（越低越好） | 0.7 → 0.3                | `CrossEntropy(outputs, labels)` |
| mean_token_accuracy      | token 级 top-1 准确率                          | 0.65 → 0.80              | 近似 `1 − perplexity`           |
| num_tokens               | 当前步处理的 token 数                          | batch × seq_len          | tokenizer 输入长度              |
| train_runtime            | 整个 epoch 的墙钟时间（仅最后一行显示）        | 280–300 s                | `end_time − start_time`         |
| train_samples_per_second | 每秒处理的样本数                               | ≈ (batch / step) / sec   | 由 HF Trainer 统计              |
| train_steps_per_second   | 每秒完成的优化步数                             | ≈ 1 / step_latency       | 由 HF Trainer 统计              |
| train_loss               | 整个 epoch 的平均 loss（仅最后一行）           | 0.85                     | 各步 loss 的加权平均            |

SFT 与 GRPO 共同字段

| 字段 (Field)  | 含义 (Meaning)                          |
| ------------- | --------------------------------------- |
| epoch         | 当前 epoch 的完成进度（0–1 = 0–100 %）  |
| loss          | SFT：交叉熵；GRPO：β·KL − reward        |
| grad_norm     | 当前梯度的 L2 范数（过大 ⇒ 有爆炸风险） |
| learning_rate | 每步的学习率                            |
| num_tokens    | 当前步处理的 token 数                   |
| logging_steps | 每 *n* 步打印一次日志，决定日志粒度     |

GRPOTrainer-specific fields

| 日志键 (Log Key)          | 含义 (Meaning)                                        | 经验规则 (Heuristic) |
| ------------------------- | ----------------------------------------------------- | -------------------- |
| rewards/cor_reward/mean   | 数值答案奖励均值（完全正确 +2，误差 1 内 +1，其余 0） | ↑ 越高越好           |
| rewards/fmt_reward/mean   | XML 格式奖励均值（模板满足即 +1）                     | ↑ 越高越好           |
| reward                    | 批次平均总奖励（cor + fmt），范围 [0 … 3]             | ↑ 越高越好           |
| reward_std                | 批内奖励的标准差                                      | 中等即可             |
| frac_reward_zero_std      | 奖励为 0 的样本占比                                   | ↓ 越低越好           |
| kl                        | 相对于基础模型的 KL 散度                              | 适中最佳             |
| loss                      | β·KL − reward（GRPO 目标函数）                        | 关注趋势             |
| grad_norm                 | 当前梯度的 L2 范数                                    | ↓ 保持小             |
| completions/mean_length   | 8 个生成答案的平均 token 长度                         | 监控长度             |
| completions/clipped_ratio | 被 `max_completion_length` 截断的答案比例             | ↓ 越低越好           |
| epoch                     | 训练进度（0–1 = 0–100%）                              | —                    |



---

## Embedded C++ Code Generation: SFT + GRPO

> *Scripts: `scripts/embedded_grpo_train.py`, `scripts/embedded_infer.py`, `scripts/run_train.sh`*

本项目演示如何使用 **SFT + GRPO** 训练一个嵌入式 C++ 代码生成模型，适用于白色家电厂商等有大量嵌入式代码库的客户场景。

*Author: Xinyu Wei (Microsoft GBB AI Architect)*

---



---

# Part 8: Phi-4 GRPO 训练代码

> *原文来自 GRPO-RL-Training-Pipeline*


## 📖 附录：SFT 调参最佳实践

> 本节总结了通过 **7 轮参数优化** 将模型准确率从 0% 提升到 100% 的经验。

### 常见问题诊断

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 训练后回答完全无关 | 数据集太小 / 格式错误 | 检查数据格式，扩充数据集 |
| Validation loss 下降太慢 | 过拟合 | 增加 dropout、扩充数据 |
| 训练正常但答案错误 | 模型没学到知识 | 添加 CoT、改用英文语料 |
| 同一问题答案不一致 | 采样随机性 | 推理时设 `temperature=0` |

### 7 轮调参经验

| 轮次 | 调整内容 | 效果 |
|------|----------|------|
| 1 | 基础训练 | ❌ 回答完全无关 |
| 2 | `lora_dropout=0.05`, epochs 30→100 | ❌ 仍过拟合 |
| 3 | 数据集 30→3000 条，train/val=0.7/0.3 | ⚠️ 过拟合解决，但答案仍错 |
| 4 | 添加 **Chain of Thought (CoT)**，改全英文语料 | ⚠️ 50% 准确率 |
| 5 | **数据增强**：随机插入/交换/删除/回译 | ⚠️ 准确率 +10% |
| 6 | LoRA → **Full Fine-tuning** | ⚠️ 大幅提升，但答案不稳定 |
| 7 | `learning_rate=5e-4`, 推理 `temperature=0` | ✅ 100% 准确率 |

### 关键参数设置

```python
# 训练参数
training_args = TrainingArguments(
    num_train_epochs=100,
    learning_rate=5e-4,           # 比默认 5e-5 高 10 倍
    gradient_accumulation_steps=32,
    per_device_train_batch_size=1,
    warmup_steps=100,
    eval_strategy="steps",
    eval_steps=25,
)

# 推理参数 - 确保答案一致性
output = model.generate(
    inputs,
    do_sample=False,              # 禁用随机采样
    temperature=0.0,              # 最确定性的生成
    max_new_tokens=512,
)
```

### 数据增强技巧

为单条知识生成多条训练数据：

| 方法 | 说明 | 示例 |
|------|------|------|
| **随机插入** | 在句子中插入无关词 | "初始化 GPIO" → "初始化 **端口** GPIO" |
| **随机交换** | 交换相邻词顺序 | "配置 UART 波特率" → "配置 波特率 UART" |
| **随机删除** | 删除非关键词 | "请初始化一个 GPIO 引脚" → "初始化 GPIO 引脚" |
| **回译** | 中→英→中 | "初始化串口" → "Initialize serial" → "初始化串行端口" |

### CoT (Chain of Thought) 示例

```
Prompt: How to initialize UART for .NET Framework?

Completion:
**Step-by-Step Analysis:**
1. **Define Purpose**: Initialize UART peripheral for serial communication
2. **Code Structure**: Import HAL namespace, configure baud rate
3. **Key Parameters**: Baud=115200, WordLength=8, StopBits=1

**Code Sample**:
void UART_Init() {
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    HAL_UART_Init(&huart1);
}
```

### 核心教训

1. **数据量 > 参数调优**：从 30 条扩到 3000 条是关键转折点
2. **CoT 对代码生成有效**：让模型先分析再写代码
3. **Full Fine-tuning > LoRA**：复杂任务需要更大调整幅度
4. **推理参数很重要**：`temperature=0` 确保输出稳定

---

## GRPO Phi-4 实战训练 (Unsloth)

***Please click below pictures to see my demo video on Youtube about GRPO of Microsoft/phi-4:***
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/WXjJdsV2cbU)



## Phi-4 GRPO 训练代码

```
from unsloth import FastLanguageModel, PatchFastRL
PatchFastRL("GRPO", FastLanguageModel)
```

```
max_seq_length = 1024
lora_rank = 16

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "microsoft/phi-4",
    max_seq_length = max_seq_length,
    load_in_4bit = True, 
    fast_inference = True, 
    max_lora_rank = lora_rank,
    gpu_memory_utilization = 0.6, 
)
```

```
model = FastLanguageModel.get_peft_model(
    model,
    r = lora_rank,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha = lora_rank,
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)
```

```
SYSTEM_PROMPT = """
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
<aha>
No no no, this is my real answer:
...
</aha>
"""
import re

def very_loose_format_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion has a specific format."""
    responses = [completion[0]["content"] for completion in completions]
    return [0.5 if "<reasoning>" in r and "</reasoning>" in r else 0.0 for r in responses]

def strict_format_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion has a specific format."""
    pattern = r"^<reasoning>.*?</reasoning>\s*<answer>.*?</answer>\s*<aha>.*?</aha>$"
    responses = [completion[0]["content"] for completion in completions]
    matches = [re.match(pattern, r) for r in responses]
    return [0.5 if match else 0.0 for match in matches]

def aha_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion contains "aha" times, 2 for the tags, and one more, wherever it wants."""
    responses = [completion[0]["content"] for completion in completions]
    matches = [re.findall(r'\baha\b', r, re.IGNORECASE) for r in responses]
    return [0.5 if len(match) == 3 else 0.0 for match in matches]
```

```
from datasets import load_dataset
import multiprocessing
ds = load_dataset("cognitivecomputations/dolphin-r1", "reasoning-deepseek", split="train[:10000]")
ds = ds.rename_columns({'messages':'prompt'})

def process(row):
  row['prompt'][0]['content'] += '\n'+SYSTEM_PROMPT
  return row

ds= ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

def tokenize_with_template(example):
    """Tokenizes input text using the chat template of the tokenizer."""
    chat_template = tokenizer.apply_chat_template(example['prompt'], tokenize=False, add_generation_prompt=True)
    tokens = tokenizer(chat_template, truncation=False, add_special_tokens=True)["input_ids"]
    return {"token_length": len(tokens)}

ds = ds.map(tokenize_with_template,
    #num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False)
ds = ds.filter(lambda example: example["token_length"] <= max_seq_length)
ds = ds.remove_columns(["token_length"])
```

```
from trl import GRPOConfig, GRPOTrainer
training_args = GRPOConfig(
    use_vllm = True, # use vLLM for fast inference!
    learning_rate = 1e-6,
    warmup_ratio = 0.1,
    lr_scheduler_type = "linear",
    optim = "paged_adamw_8bit",
    logging_steps = 5,
    bf16 = True,
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 4, # Increase to 4 for smoother training
    num_generations = 6, # Decrease if out of memory (but avoid below 4)
    max_prompt_length = 256,
    max_completion_length = 512,
    # num_train_epochs = 1, # Set to 1 for a full training run
    max_steps = 250,
    save_steps = 250,
    report_to = "none", # Can use Weights & Biases
    output_dir = "outputs",
)
```

```
trainer = GRPOTrainer(
    model = model,
    processing_class = tokenizer,
    reward_funcs = [
        aha_reward_func,
        strict_format_reward_func,
        very_loose_format_reward_func
    ],
    args = training_args,
    train_dataset = ds,
)
trainer.train()
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/phi4_training_result.png)

```
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import torch
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/phi-4",
    device_map="cuda",
)

tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-4")
model = PeftModel.from_pretrained(model, "outputs/checkpoint-50")
```

```
SYSTEM_PROMPT = """
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
<aha>
No no no, this is my real answer:
...
</aha>
"""

messages = [{"role":"system", "content":"You are an expert who knows the location of all pandas in China."+SYSTEM_PROMPT},
    {"role": "user", "content": "Make 10 possible equations to compute the number of panda in China."},
]

seq = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(seq)

encoded_input = tokenizer(seq, return_tensors="pt").to(model.device)
outputs = model.generate(
  encoded_input['input_ids'],
  max_new_tokens=2048,
  do_sample=True,
  temperature=0.6,
  top_p=0.9,
)


response = outputs[0][encoded_input['input_ids'].shape[-1]:]
print(tokenizer.decode(response))
```

Phi-4 GRPO 推理结果：

```
<|im_start|>system<|im_sep|>You are an expert who knows the location of all pandas in China.
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
<aha>
No no no, this is my real answer:
...
</aha>
<|im_end|><|im_start|>user<|im_sep|>Make 10 possible equations to compute the number of panda in China.<|im_end|><|im_start|>assistant<|im_sep|>
<reasoning>
To create equations that could theoretically compute the number of pandas in China, we need to consider various factors that might influence the panda population. These factors could include birth rates, death rates, conservation efforts, habitat changes, and more. Here are some conceptual equations:

1. **Basic Population Model**:
   \[
   P(t) = P_0 + (B - D) \times t
   \]
   Where \( P(t) \) is the population at time \( t \), \( P_0 \) is the initial population, \( B \) is the average number of births per year, and \( D \) is the average number of deaths per year.

2. **Logistic Growth Model**:
   \[
   P(t) = \frac{K}{1 + \left(\frac{K - P_0}{P_0}\right) e^{-rt}}
   \]
   Where \( K \) is the carrying capacity of the environment, \( r \) is the intrinsic growth rate, and \( e \) is the base of the natural logarithm.

3. **Conservation Impact Model**:
   \[
   P(t) = P_0 + (B - D + C) \times t
   \]
   Where \( C \) represents the net effect of conservation efforts (e.g., increased births or decreased deaths due to conservation).

4. **Habitat Change Model**:
   \[
   P(t) = P_0 + (B - D) \times t - H(t)
   \]
   Where \( H(t) \) is the negative impact on the population due to habitat loss or degradation over time.

5. **Predation and Disease Model**:
   \[
   P(t) = P_0 + (B - D - P_d - P_c) \times t
   \]
   Where \( P_d \) is the number of deaths due to disease, and \( P_c \) is the number of deaths due to predation.

6. **Migration Model**:
   \[
   P(t) = P_0 + (B - D) \times t + M(t)
   \]
   Where \( M(t) \) is the net migration (immigration minus emigration) of pandas over time.

7. **Human Impact Model**:
   \[
   P(t) = P_0 + (B - D - H_i) \times t
   \]
   Where \( H_i \) is the impact of human activities (e.g., poaching, deforestation) on the panda population.

8. **Climate Change Model**:
   \[
   P(t) = P_0 + (B - D - C_c) \times t
   \]
   Where \( C_c \) is the impact of climate change on the panda population.

9. **Genetic Diversity Model**:
   \[
   P(t) = P_0 + (B - D) \times t + G(t)
   \]
   Where \( G(t) \) is the effect of genetic diversity on population growth (e.g., increased resilience).

10. **Combined Model**:
    \[
    P(t) = P_0 + (B - D + C - H - P_d - P_c + M - H_i - C_c + G) \times t
    \]
    This equation combines multiple factors to provide a more comprehensive model.

These equations are hypothetical and would require specific data to be accurately applied.
</reasoning>

<answer>
1. \( P(t) = P_0 + (B - D) \times t \)

2. \( P(t) = \frac{K}{1 + \left(\frac{K - P_0}{P_0}\right) e^{-rt}} \)

3. \( P(t) = P_0 + (B - D + C) \times t \)

4. \( P(t) = P_0 + (B - D) \times t - H(t) \)

5. \( P(t) = P_0 + (B - D - P_d - P_c) \times t \)

6. \( P(t) = P_0 + (B - D) \times t + M(t) \)

7. \( P(t) = P_0 + (B - D - H_i) \times t \)

8. \( P(t) = P_0 + (B - D - C_c) \times t \)

9. \( P(t) = P_0 + (B - D) \times t + G(t) \)

10. \( P(t) = P_0 + (B - D + C - H - P_d - P_c + M - H_i - C_c + G) \times t \)
</answer>

<aha>
No no no, this is my real answer: The exact number of pandas in China is determined through surveys and research conducted by wildlife authorities and conservation organizations. These numbers are updated periodically and are based on field data rather than equations.
</aha><|im_end|>
```





---

# Part 9: GSPO — Dense 模型 vs MoE 模型的 RL 训练

> *原文来自 GRPO-RL-Training-Pipeline*


## 1. 背景

在大语言模型（LLM）的训练后期，强化学习（RLHF / RLAIF）起到至关重要的作用。
常用的 RL 优化方法 PPO（Proximal Policy Optimization）在工业界存在多种改进版本，其中 **GRPO（Group Relative Policy Optimization）** 是 DeepSeek 等团队推行的工程化方案。

但在 **MoE（Mixture of Experts）** 模型中，GRPO 的 **token 级优化** 容易遇到问题：

- 对专家路由波动敏感 → 训练信号噪声大
- 需要 Routing Replay（重放路由）来稳定训练
- 长时间训练可能崩溃或难以扩展

Qwen 团队在升级 **Qwen3 MoE 系列** 时，提出了新方法
**GSPO（Group Sequence Policy Optimization）**：

✅ 改进点：从 **token-level** 转为 **sequence-level** 优化
✅ 目标：减少 MoE 路由带来的训练不稳定性，提升效率与可扩展性

## 2. Dense 模型 vs MoE 模型

### Dense 模型

- 每次前向计算都用全量参数
- 训练信号稳定
- 无路由问题
- 例子：GPT-3、LLaMA、BERT

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/gspo_dense_model.png)

### MoE 模型

- 部分层替换为多个"专家网络"（Experts）
- 每个 token 仅激活少数专家
- 参数总量大，但每次计算量相对较低
- 不同 token 路由可能不同 → 波动大
- 例子：Mixtral 8x7B、Qwen3 MoE

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/gspo_moe_architecture.png)

**直观对比**：

| 模型类型 | 参数参与度 | 路由波动 | 稳定性 |
| -------- | ---------- | -------- | ------ |
| Dense    | 100%       | 无       | 高     |
| MoE      | 部分       | 有       | 低     |

## 3. GRPO 与 GSPO 核心差异

| 类别           | GRPO                | GSPO             |
| -------------- | ------------------- | ---------------- |
| 优化粒度       | Token-level         | Sequence-level   |
| Ratio 计算     | 每个 token 单独     | 整条序列一次     |
| Clip 操作      | 每个 token 独立剪切 | 整条序列统一剪切 |
| 对路由波动敏感 | 高                  | 低               |
| Routing Replay | 必需                | 不需要           |
| 稳定性（MoE）  | 中等                | 高               |
| Dense 提升     | 几乎无              | 几乎无           |

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/gspo_comparison.png)

## 4. GSPO 原理

### Importance Ratio（重要性比）

```
ratio = P_cur / P_ref
```



衡量当前策略（P_cur）与参考策略（P_ref）对同一输出的倾向变化幅度。

- GRPO：逐 token 比例
- GSPO：整段序列比例

### Clipping（剪切）

- 限制 ratio 在 [1-ε, 1+ε]
- 防止一次更新过大导致不稳定
- GRPO：token 级 clip
- GSPO：序列级 clip

## 5. "Hello world" 计算示例

假设：

```
token1 = "Hello", token2 = "world"
P_ref: Hello=0.20, world=0.10
P_cur: Hello=0.25, world=0.30
ε=0.2
```



**GRPO：**

```
ratio_t1 = 0.25/0.20 = 1.25 → clip=1.2
ratio_t2 = 0.30/0.10 = 3.0 → clip=1.2
各 token 独立更新
```



**GSPO：**

```
P_ref_seq = 0.20×0.10 = 0.02
P_cur_seq = 0.25×0.30 = 0.075
ratio_seq = 3.75 → clip=1.2
整句一次更新
```

## 6. 实验结果（Qwen 团队）

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/gspo_experiment_results.png)

### MoE 模型：

- GSPO 收敛更快
- 奖励优化更高
- 样本效率更好
- Clip 比例更高也能稳定训练
- 长序列和算力扩展时性能平稳提升

### Dense 模型：

- 无明显提升

## 7. 训练时使用的模型结构

无论 GRPO 还是 GSPO，都至少需要：

- **策略模型**（Policy, 会更新）
- **参考模型**（Reference, 冻结或延迟更新）
- **奖励模型**（Reward model）
- （可选）价值网络（Critic）

**参考模型**注意：

- 一般是 SFT 模型拷贝
- 固定不更新，或定期更新
- 不能直接用当前策略的即时参数作参考（ratio 永远=1 无意义）

## 8. 适用场景

**适合：**

- 大规模 MoE 模型
- 长序列 RL 微调
- 奖励信号稳定、信息密度高

**不适合或收益低：**

- Dense 模型
- 奖励信号噪声高、分辨率低的任务
- 对单 token 精度极高的场景（token优化粒度更粗）

## 9. 优缺点总结

**优势**：

- MoE 稳定性显著提升
- 样本效率高
- 移除 Routing Replay
- 可扩展性好

**劣势**：

- Dense 模型提升有限
- 优化粒度粗
- 对奖励函数依赖高
- Token 级可解释性下降

## 10. 常见误区

- **GSPO 是推理算法？** ❌
  → 只在训练时使用，推理不执行 ratio/clip 逻辑
- **GRPO 不支持多 token 推理？** ❌
  → 多 token 推理是解码优化策略，和训练算法无关
- **GSPO 推理直接计算整句概率？** ❌
  → 推理依然是逐 token（或并行批量）生成

## 11. Hugging Face TRL 接入

```
SFTConfig(
    importance_sampling_level="sequence"
)
```

- 需要 `TRL >= 0.20`
- Unsloth 截至 2025-07-30 仅支持 `TRL 0.19.1`

## 12. 总结

- **GRPO**：token-level 优化信号，适用于 Dense & MoE，但在 MoE 稳定性差
- **GSPO**：sequence-level 优化信号，显著优化 MoE 稳定性与效率
- Dense 模型用 GSPO 不会有明显提升

**一句话**：

> GSPO 是为 MoE 做的定向优化，训练更稳、更快、更可扩展，推理性能也因此受益，但它本身不是推理算法。


---

# Part 10: Test-time Compute Scaling — SLM 如何击败大模型

> *原文来自 SLM-Capabilities-and-Fine-Tuning*



欢迎关注我的repo：

https://github.com/xinyuwei-david/david-share.git

**本文参考文档：**

https://huggingface.co/spaces/HuggingFaceH4/blogpost-scaling-test-time-compute

**本文导读：**

传统上，LLMs 的进步主要依赖于增加训练时间的计算量，即训练更大的模型。然而，这种方法成本昂贵，资源需求巨大。扩展测试时间计算提供了一种有效的替代方案，允许模型在推理过程中“思考更长时间”，从而在不增加模型参数的情况下提升性能。

文章主要介绍了三种测试时间计算扩展的策略：

1. **Best-of-N 方法**：生成多个候选答案，使用奖励模型（reward model）对它们进行评分，选择得分最高的答案。加权的 Best-of-N 变体还考虑了答案的出现频率，优先选择高质量且高频率的答案。

2. **束搜索（Beam Search）**：利用过程奖励模型（Process Reward Model，PRM）在生成过程中逐步引导模型，选择每一步最有可能通向正确答案的路径。相比于 Best-of-N，束搜索在相同计算预算下取得了更高的准确率。

3. **多样化验证器树搜索（Diverse Verifier Tree Search，DVTS）**：这是对束搜索的改进，旨在增加生成答案的多样性。DVTS 将初始束分为多个独立的子树，在较大的计算预算下表现出色，尤其是在处理较简单的问题时。

   通过一系列实验，使用开源的 Llama 模型和 MATH-500 数据集，验证了这些方法的有效性。结果显示，即使是参数量较小的模型（如 1B 和 3B 的 Llama Instruct 模型），在采用适当的测试时间计算策略后，其性能可以超过更大的模型（如 8B 和 70B 的模型）。

   不同策略在不同问题难度和计算预算下的表现是不同的，参考“计算最优扩展”的概念，即针对特定的计算预算，选择能达到最佳性能的策略。对于简单问题和较低的计算预算，Best-of-N 表现更好；而对于复杂问题和较高的计算预算，束搜索和 DVTS 更具优势。

   

   在未来，提升验证器的质量，实现模型的自验证，融入更深入的推理过程，以及将搜索方法用于数据生成等。这些方向都有望进一步提升 LLMs 的性能，特别是在资源受限的情况下。

   

**一、几种解码技术的区别**

在我的一篇文章中，我介绍了如何改善模型的幻觉，里面介绍了几种解码技术。

https://github.com/xinyuwei-david/david-share/tree/master/Deep-Learning/LLM-Hallucinations

我在上一篇的基础上，再增加对DVTS(Diverse verifier tree search)和多数投票的对比。

| **方面**       | **贪婪解码（Greedy Decoding）**                              | **束搜索（Beam Search）**                                    | **多样化验证器树搜索（DVTS）**                               | **多数投票（Majority Voting）**                              |
| :------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| **基本概念**   | 在每一步选择概率最高的词，生成单一序列。                     | 在每一步保留多个最有可能的候选序列，探索更多的可能性。       | 通过将束分成独立的子树，并使用验证器引导搜索，增加多样性和性能。 | 生成多个独立的候选答案，选择出现次数最多的答案作为最终输出。 |
| **工作原理**   | - 在生成文本时，每一步都选择当前概率最高的下一个词。 - 生成一个单一的、最可能的序列。 | - 保持固定数量（束宽度）的最佳部分序列。 - 在每个步骤扩展这些序列，选出新的最佳候选。 | - 将初始束划分为多个独立的子树。 - 在每个子树中，使用过程奖励模型（PRM）评估和引导生成。 - 通过独立扩展，增加解的多样性。 | - 使用随机采样等方法生成多个独立的候选答案。 - 对生成的答案进行统计，选择出现次数最多的答案。 |
| **搜索空间**   | 窄（单一路径）。                                             | 中等（取决于束宽度）。                                       | 广（多个子树，增加了探索的广度）。                           | 宽（生成多个独立的答案），但不在单次生成中扩展。             |
| **多样性**     | 很低（只有一个输出）。                                       | 中等（受束宽度限制）。                                       | 高（独立子树增加了多样性）。                                 | 中等（取决于生成的答案数量和随机性）。                       |
| **使用验证器** | 否。                                                         | 可选（可以使用，但不总是用）。                               | 是的，使用过程奖励模型（PRM）在每一步进行评分和引导。        | 否，通常不使用验证器，仅通过统计频率选择答案。               |
| **优点**       | - 简单快捷。 - 计算效率高。                                  | - 在精度和计算成本之间取得平衡。 - 提高找到全局最优解的机会。 | - 增加了解的多样性。 - 在复杂任务上表现更好。 - 利用验证器引导，提高准确率。 | - 简单易行。 - 减少随机性带来的波动。 - 提高答案的稳定性和一致性。 |
| **缺点**       | - 只关注局部最优，可能错过更好的解。 - 缺乏多样性。          | - 计算量比贪婪解码大。 - 可能仍然错过一些解。                | - 实现更复杂。 - 需要额外的计算资源。 - 依赖于验证器的质量。 | - 无法保证选择的答案是正确的。 - 如果答案多样性过高，可能没有明确的多数。 - 增加了计算成本。 |
| **适用场景**   | - 需要快速生成单一答案的简单任务。 - 对结果质量要求不高的情况。 | - 需要在质量和计算成本之间平衡的任务。 - 适用于一般复杂度的任务。 | - 复杂或需要深入推理的任务。 - 有较大计算预算，可用于提升性能。 | - 希望提高答案稳定性和一致性的任务。 - 需要减少随机性影响的情况下。 |
| **计算复杂度** | 低。                                                         | 中等（取决于束宽度）。                                       | 高（由于使用了验证器和更多的搜索路径）。                     | 中等到高（取决于生成的答案数量）。                           |



### **1. 贪婪解码（Greedy Decoding）**

 
**怎么工作：**

- 在每一步，选择概率最高的下一个词或标记。

- 生成一个单一的、最有可能的序列，直到结束标记或达到最大长度。

  **特点：**

- **快速简单**：计算效率高，适合实时应用。

- **缺点**：

  - **局部最优**：只关注当前步骤的最优选择，可能错过全局更优的解决方案。
  - **缺乏多样性**：生成的序列缺少变化，可能导致重复或不自然的输出。



### **2. 束搜索（Beam Search）**

 
**怎么工作：**

- **保留多个候选序列**：在每一步，保留固定数量（束宽度为 *k*）的最有可能的部分序列。

- **扩展候选序列**：对每个部分序列，生成可能的下一个词，用于扩展序列。

- **选择最佳候选**：计算每个新序列的累计概率，保留累计概率最高的 *k* 个序列，继续下一步扩展。

- **重复上述步骤**，直到生成结束标记或达到最大长度。

  **特点：**

- **平衡了精度和计算成本**：相比贪婪解码，可以找到更接近全局最优的序列。

- **提供一定的多样性**：保留了多个候选序列，但多样性受束宽度限制。

- **缺点**：

  - **计算量增加**：束宽度越大，计算成本越高。
  - **可能仍受限于束宽度**：无法保证找到全局最优解。



### **3. 多样化验证器树搜索（DVTS）**

 
**怎么工作：**

- **分裂初始束**：将初始束分成多个独立的子树，增加初始解的多样性。

- **使用验证器指导**：在每个子树中，使用**过程奖励模型（Process Reward Model，PRM）**对生成的步骤进行评分。

- **独立扩展子树**：每个子树独立地进行扩展，按照验证器的反馈选择最有希望的路径。

- **组合结果**：最终从各个子树中选取验证器评分最高的答案。

  **特点：**

- **增加多样性**：通过独立的子树，探索更多可能的解答路径。

- **利用验证器引导**：在生成过程中实时评估，提升生成结果的准确性和质量。

- **适用于复杂任务**：在需要深度推理或精确回答的任务中表现出色。

- **缺点**：

  - **计算成本高**：由于需要管理更多的搜索路径和验证器的计算。
  - **实现复杂**：需要精心设计搜索策略和验证器模型。

 

### **4. 多数投票（Majority Voting）**

 
**怎么工作：**

- **多次独立生成**：使用随机采样（如 Top-k 或 Top-p 采样）等方法，生成多个（如 *N* 个）独立的候选答案。

- **统计答案频率**：对生成的候选答案进行统计，记录每个独特答案出现的次数。

- **选择出现次数最多的答案**：将频率最高的答案作为最终输出。

  **特点：**

- **简单易行**：不需要复杂的模型调整或外部评估模型。

- **提高稳定性**：通过统计，提高答案的一致性和可靠性。

- **减少随机性影响**：平滑随机采样带来的波动，过滤掉偶然的错误答案。

- **缺点**：

  - **无法保证正确性**：如果模型本身倾向于错误答案，可能多数投票的结果也是错误的。
  - **计算成本增加**：需要多次生成答案，增加了计算开销。
  - **多样性可能不足**：如果生成的答案过于多样，可能没有明确的多数答案。




## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | vLLM, LoRA/PEFT, Unsloth |


## **它们之间的区别与联系**

 

### **搜索空间的大小**

 

- **贪婪解码**：
  - **最小搜索空间**：只探索一条路径，即每一步都选择概率最高的词。
- **束搜索**：
  - **中等搜索空间**：根据束宽度 *k*，同时探索 *k* 条路径。
- **DVTS**：
  - **最大搜索空间**：通过独立的子树和验证器的引导，探索更加广泛的路径。
- **多数投票**：
  - **扩展搜索空间**：通过多次独立生成，获得不同的候选答案，但每次生成仍是一条路径。

### **多样性**

 

- **贪婪解码**：
  - **最低多样性**：只有一个输出序列。
- **束搜索**：
  - **一定的多样性**：受限于束宽度，提供多个候选序列。
- **DVTS**：
  - **高多样性**：独立的子树和验证器的引导，增加了解答的多样性。
- **多数投票**：
  - **中等多样性**：依赖于生成次数和随机采样的程度，可能获得多个不同的候选答案。

### **计算成本**

 

- **贪婪解码**：
  - **最低计算成本**：每一步只需计算概率最高的词。
- **束搜索**：
  - **中等计算成本**：取决于束宽度 *k*，计算量随 *k* 增加而增加。
- **DVTS**：
  - **最高计算成本**：需要管理多个子树、维护验证器的计算和评分。
- **多数投票**：
  - **中等到高的计算成本**：取决于生成的次数 *N*，生成次数越多，计算成本越高。

### **适用的场景和任务**

 

- **贪婪解码**：
  - **快速生成结果**：适用于对速度要求高、对结果质量要求不高的简单任务。
  - **示例**：实时对话系统的快速回复。
- **束搜索**：
  - **平衡质量和效率**：适用于需要一定精度，但计算资源有限的任务。
  - **示例**：机器翻译、文本摘要。
- **DVTS**：
  - **复杂、需要深入推理的任务**：适用于有足够计算资源，希望获得高质量答案的场景。
  - **示例**：数学问题求解、代码生成、复杂问答。
- **多数投票**：
  - **提高答案稳定性**：适用于需要减少随机性影响、希望获得一致性答案的任务。
  - **示例**：知识问答、关键事实的确认。

## **简单类比**

 

- **贪婪解码**：
  - **类比**：像在每个十字路口都选择看起来最直接的道路，可能错过更好的路线。
- **束搜索**：
  - **类比**：像在每个十字路口选择几条看起来不错的道路，走一段后再根据情况选择最佳路线。
- **DVTS**：
  - **类比**：像派出多个探索队伍，从不同的路线出发，同时使用指南（验证器）引导，每个队伍独立寻找最佳路径。
- **多数投票**：
  - **类比**：像询问多个人同一个问题，然后选择大多数人都同意的答案。



## **总结**

 
通过将**多数投票**加入讨论，我们可以更全面地了解不同的解码和生成策略的特点、优点和适用场景。每种方法都有其独特的优势和局限性，选择适当的方法需要根据具体任务的需求、可用的计算资源以及对结果质量的要求来决定。

- **贪婪解码**适合简单、快速、对质量要求不高的任务。

- **束搜索**在质量和效率之间取得平衡，适用于一般复杂度的任务。

- **多样化验证器树搜索（DVTS）**适用于复杂、需要高准确性的任务，但计算成本高。

- **多数投票**通过多次生成和统计，减少了随机性，提高了答案的稳定性，但无法保证一定正确，需要谨慎使用。

  选择合适的策略，有助于充分利用大型语言模型的能力，满足各种应用场景的需求。





**二、 train-time compute的变革**

在过去的几年里，训练时间计算（train-time compute）的扩展主导了大型语言模型（LLMs）的进展。尽管这种模式已被证明异常有效，但预训练更大模型所需的资源变得昂贵得令人望而却步，数十亿美元规模的集群已在眼前。这个趋势引发了对一种互补方法的极大兴趣：测试时间计算扩展（test-time compute scaling）。测试时间方法并不依赖于越来越大的预训练预算，而是使用动态推理策略，让模型在解决更难的问题时“思考更长时间”。一个突出的例子是 OpenAI 的 o1 模型，它在增加测试时间计算量时，对困难的数学问题表现出持续的改进：

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/1.png)

DeepMind 的最新研究表明，可以通过迭代自我改进（iterative self-refinement）或使用奖励模型（reward model）在解空间中进行搜索等策略，来最优地扩展测试时间计算。通过为每个提示自适应地分配测试时间计算，小模型可以与更大、更耗资源的模型媲美，甚至有时还能超越它们。当内存受限且可用硬件不足以运行更大的模型时，扩展测试时间计算尤其有利。然而，这种有前景的方法是使用闭源模型演示的，并未发布任何实现细节或代码。

- **计算最优扩展（Compute-optimal scaling）**：实现 DeepMind 的方案，在测试时间提升开源模型的数学能力。

- **多样化验证器树搜索（Diverse Verifier Tree Search，DVTS）**：开发的验证器引导树搜索（verifier-guided tree search）技术的未发表扩展。这种简单而有效的方法提高了多样性，特别是在较高的测试时间计算预算下，提供了更好的性能。

- **🧭 搜索与学习（Search and Learn）**：一个用于在大型语言模型上实现搜索策略的轻量级工具包，使用 vLLM 构建，速度极快。

  



那么，计算最优扩展在实践中效果如何呢？看看这个图表，在具有挑战性的 MATH-500 基准上，如果给予足够的“思考时间”，微小的 1B 和 3B Llama Instruct 模型竟然超过了它们更大的 8B 和 70B 同系列模型的表现 ：

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/2.png)



## 三、test-time compute scaling的策略

 
扩展测试时间计算有两种主要策略：

1. **自我改进（Self-Refinement）**：模型通过在后续迭代中识别和纠正错误，迭代地改进它们自己的输出或“想法”。虽然在某些任务上有效，但这种策略通常要求模型具有内置的自我改进机制，这可能会限制其适用性。
2. **针对验证器的搜索（Search Against a Verifier）**：这种方法专注于生成多个候选答案，并使用验证器（verifier）选择最佳答案。验证器可以是从硬编码的启发式方法到学习的奖励模型（reward model），后面我们将重点关注学习的验证器。它包括 Best-of-N 采样和树搜索等技术。搜索策略更灵活，可以适应问题的难度，尽管它们的性能受限于验证器的质量。



**四、验证器到底是什么？**

验证器通常是一个**奖励模型（Reward Model，RM）\**或\**过程奖励模型（Process Reward Model，PRM）**，它们被训练来对生成的内容进行评估。

**定义**：在本文的上下文中，**验证器**是一个辅助模型或机制，用于**评估和评分**大型语言模型（LLM）生成的**输出或部分输出**。

**作用**：

- **评估质量**：验证器对生成的候选答案或中间步骤进行**评估**，判断其正确性、可信度或质量。
- **指导搜索**：通过对候选进行评分，验证器帮助模型在生成过程中**选择更有可能通向正确答案的路径**。

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/3.png)

Best-of-N、束搜索（Beam Search）和多样化验证器树搜索（DVTS）都是解码技术，它们被用来指导大型语言模型（LLM）在生成过程中如何产生输出。将这些解码技术与验证器（Verifier）结合，以优化模型在测试时间的性能。



- **提高准确性**：验证器有助于过滤掉错误或低质量的生成结果，提高模型输出的准确性，减少幻觉的产生。
- **优化生成过程**：在生成过程中实时评估和引导，使模型更有效地探索解答空间，尤其在复杂任务上表现出色。
- **增强小模型的性能**：通过结合验证器，较小的模型也可以在特定任务上达到或超过大模型的性能。



**五、效果验证**

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/4.png)



## 实验设置

 
如上图所示，我们的实验设置涉及以下步骤的流程：

1. 我们首先将一个数学问题输入大型语言模型（LLM），它生成 N 个部分解，例如推导中的一个中间步骤。

2. 每个步骤由过程奖励模型（PRM）评分，它估计每个步骤最终到达正确最终答案的概率。

3. 这些步骤和 PRM 分数然后被给定的搜索策略使用，以选择哪些部分解应被进一步探索，以生成下一轮中间步骤。

4. 一旦搜索策略终止，最终的候选解由 PRM 排序，产生最终答案。

   为了比较各种搜索策略，我们使用了以下开源模型和数据集：

- **模型**：我们使用了 `meta-llama/Llama-3.2-1B-Instruct` 作为扩展测试时间计算的主要模型。由于其 10 亿参数的轻量级特性，可以实现快速迭代，其在数学基准测试中的未饱和性能使其成为突出扩展优势的理想选择。
- **过程奖励模型（PRM）**：为了指导我们的搜索策略，我们使用了 `RLHFlow/Llama3.1-8B-PRM-Deepseek-Data`，这是一个使用过程监督（process supervision）训练的 80 亿参数的奖励模型。过程监督是一种训练方法，模型在推理过程的每个步骤（而不仅仅是最终结果）都能收到反馈。我们选择这个模型是因为它属于与我们的策略相同的模型家族，并且在我们测试的这个参数量级中，比我们测试的其他 PRM（如 Math-Shepherd）给出了更好的结果。
- **数据集**：我们在 MATH 基准的 MATH-500 子集上进行了评估，这是 OpenAI 作为其过程监督研究的一部分发布的数据集。这些数学问题涵盖了七个学科，对人类和大多数大型语言模型来说都具有挑战性。看看下面的数据集浏览器，感受一下问题的难度吧！我们在从每个提示生成 1 到 256 个生成的计算预算上测试了每个搜索策略，并使用五个随机种子运行数据生成流程，以估计运行间的方差。你可以在这个集合中找到我们分析的模型和数据集。

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/5.png)



为了热身，我们将从一个简单的基线开始，并逐步加入其他技术来提高性能。

## 多数投票：一个简单的基线

 
多数投票——或者如果你想用更高端的说法，可以称为自一致性解码（self-consistency decoding）——是聚合大型语言模型输出的最直接方法。顾名思义，对于给定的数学问题，我们生成 N 个候选解并选择最频繁的答案。在我们所有的实验中，我们以温度 T = 0.8 采样了最多 N = 256 个候选解，每个问题生成最多 2048 个标记。

MATH 基准有一个独特之处，即答案必须以 LaTeX 盒子的形式格式化，如 `\boxed{answer}`。我们最初为 Llama 3.2 1B 尝试了以下简单的系统提示：

```
请逐步思考，并将你的最终答案放在 \boxed{} 中。
```

 
但发现使用贪婪解码（T = 0）得到的准确率远低于 Meta 在其发布中报告的 30.6%。幸运的是，Meta 也发布了他们用于评估的提示，切换我们的系统提示到他们的后，效果发生了巨大变化：

```
高效而清晰地解决以下数学问题：
  
- 对于简单的问题（2 步或更少）：
  提供简洁的解答，尽量减少解释。
  
- 对于复杂的问题（3 步或更多）：
  使用以下的逐步格式：
  
  ## 第 1 步：[简洁的描述]  
  [简短的解释和计算]  
  
  ## 第 2 步：[简洁的描述]  
  [简短的解释和计算]  
  
  ...  
  
无论采用何种方法，总是以以下内容结束：
  
因此，最终答案是：$\boxed{answer}$。我希望这是正确的。
  
其中 [answer] 是解决问题的最终数字或表达式。
```

 
评估数学问题的答案有一个细微之处，即像 `1/3` 和 `3/3` 这样的字符串是不同的，但代表数学上等价的答案。处理这种情况的标准方法是将一对答案转换为 SymPy 对象，然后检查减去两个对象并应用 `sympy.simplify` 是否得到零。

虽然这种方法在比较少量候选答案时效果很好，但我们发现当在一个包含 N 个候选答案的列表中比较许多对时，非常慢；在某些情况下，比最初生成候选答案还要慢！为了解决这个问题，我们首先将每个答案简化为其规范形式，然后计算每种形式的频率来确定多数投票。如果你对代码如何实现感兴趣，可以展开下面的细节。

**实现细节**

这里是将多数投票应用于 Llama 3.2 1B Instruct 的生成时的表现：



![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/6.png)

结果表明，多数投票相比于贪婪解码基线的确带来了显著的改进，但其增益在大约 N = 64 代之后开始趋于平稳。这种限制的出现是因为多数投票在需要细致推理或错误在代际间一致的任务上表现不佳。如果你也想知道为什么当 N = 1 和 2 时，多数投票的准确率比零次提示链式思考（0-shot CoT）基线更差，那是因为我们以 T = 0.8 进行采样，这使得在少数候选中产生正确答案的可能性较小。

基于多数投票的局限性，让我们看看引入奖励模型如何提升性能。

## Best-of-N

 
Best-of-N 是多数投票的一个简单但有效的扩展，它使用奖励模型来确定最可能的答案。该方法有两种主要变体：

1. **原始的 Best-of-N**：生成 N 个独立的回复，选择奖励模型（RM）得分最高的作为最终答案。这确保选择最自信的单个回复，但不考虑答案之间的一致性。

2. **加权的 Best-of-N**：汇总所有相同回复的分数，选择总奖励最高的答案。这种方法通过重复出现来提升分数，优先考虑高质量的答案。数学上，对答案 (a_i) 的加权如下：

   [
   a_{\text{weighted}} = \arg\max_{a} \sum_{i=1}^{N} I(a_i = a) \cdot RM(p, s_i),
   ]

   其中 (RM(p, s_i)) 是问题 (p) 的第 (i) 个解 (s_i) 的奖励模型得分。

   通常，人们使用结果奖励模型（ORM）来获得单个解决方案级别的得分。但为了与后面讨论的其他搜索策略进行公平比较，我们将使用相同的 PRM 来对 Best-of-N 的解决方案进行评分。如下面所示，PRM 对每个解决方案产生一个累积的步骤级别的得分序列，因此我们需要对步骤进行归约以获得单个解决方案级别的得分：

   ![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/7.png)
   在文献中，最常见的归约方法如下：

- **最小值（Min）**：使用所有步骤中的最小得分。

- **乘积（Prod）**：使用步骤级别得分的乘积。

- **最后（Last）**：使用步骤中的最终得分。这个得分包含了所有先前步骤的累积信息，因此有效地将 PRM 视为能够对部分解进行评分的 ORM。

  我们对每种归约方法进行了实验，发现在我们的任务和 PRM 选择中表现最佳。我们在所有实验中都使用了这种聚合，你可以展开下面的细节，看看我们如何实现它，以及上述的加权过程。

  这里是应用 Best-of-N 两种变体得到的结果：

  ![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/8.png)
  结果显示了明显的优势：加权的 Best-of-N 在更大的生成预算下，一直优于原始的 Best-of-N。它能够对相同的回复汇总分数，确保即使是出现频率较低但质量更高的答案也能被有效地优先考虑。

然而，尽管有这些改进，我们仍然无法达到 Llama 8B 模型的性能，而且 Best-of-N 方法在 N = 256 代时开始趋于平稳。我们能否通过逐步监督搜索过程来进一步突破边界？

## 使用过程奖励模型的束搜索

 
束搜索（Beam search）是一种系统地探索解空间的结构化搜索方法，使其成为在测试时间改进模型输出的强大工具。当与过程奖励模型（PRM）结合使用时，束搜索可以同时优化问题解决中间步骤的生成和评估。其工作方式如下：

1. 通过保持固定数量的“束”或活动路径 N，迭代地生成多个候选解。

2. 在第一次迭代中，以温度 T 从 LLM 采样 N 个独立的步骤，以引入回复的多样性。这些步骤通常由停止条件定义，如在新行 `\n` 或双新行 `\n\n` 处终止。

3. 使用 PRM 对每个步骤进行评分，选择前 N / M 个步骤作为下一轮生成的候选。在这里，M 表示给定活动路径的“束宽度”（beam width）。与 Best-of-N 一样，我们在每次迭代中使用“最后”归约来对部分解进行评分。

4. 从步骤（3）中选定的节点生成 M 个新步骤，并选择 PRM 得分最高的步骤。

5. 重复步骤（3）和（4），直到到达 EOS 标记或超过最大搜索深度。

   通过允许 PRM 评估中间步骤的正确性，束搜索可以在过程的早期识别和优先考虑有希望的路径。这种逐步评估对于像数学这样需要复杂推理的任务特别有益，其中验证部分解可以显著提高最终结果。

   **实现细节**

   在我们的实验中，我们遵循了 DeepMind 的超参数选择，使用以下设置运行束搜索：

- 在计算扩展为 4、16、64、256 时，使用 N 个束
- 固定束宽 M = 4
- 以温度 T = 0.8 进行采样
- 最多 40 次迭代，即最大深度为 40 步的树如下面所示，结果非常惊人：在测试时间预算为 N = 4 时，束搜索实现了与 Best-of-N 在 N = 16 时相同的准确率，即计算效率提高了 4 倍！此外，束搜索仅用每个问题 N = 32 个解就匹配了 Llama 3.1 8B 的性能。计算机科学博士生在 MATH 上的平均表现约为 40%，所以对于一个 10 亿参数的模型达到近 55% 并不算太差。

## 束搜索最擅长解决哪些问题？

 
虽然总体来看，束搜索显然是比 Best-of-N 或多数投票更好的搜索策略，但 DeepMind 的论文表明，每种策略都有取舍，取决于问题难度和测试时间计算预算。

为了了解哪种策略最适合哪些问题，DeepMind 计算了估计的问题难度分布，然后将结果分成五分位数。换句话说，每个问题被分配到 5 个级别之一，其中级别 1 表示较容易的问题，级别 5 表示最难的问题。为了估计问题难度，DeepMind 为每个问题以标准采样生成了 2048 个候选解，然后提出了以下启发式方法：

- **Oracle**：使用真实标签来估计每个问题的 pass@1 得分。对 pass@1 得分的分布进行分箱以确定五分位数。

- **模型**：使用每个问题的平均 PRM 得分分布来确定五分位数。直观地说，较难的问题得分会较低。

  以下是在四个测试时间计算预算 N = [4, 16, 64, 256] 和 pass@1 得分下，各种方法的表现：

  
  在这个图中，每个柱状图表示一个测试时间计算预算，在每个柱状图内，我们显示每种方法的相对准确率。例如，在难度级别 2 的四个柱状图中，我们看到：

  ![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/9.png)

- 多数投票在所有计算预算下都是表现最差的，除了 N = 256 时，束搜索最差。

- 束搜索在 N = [4, 16, 64] 情况下最好，但在 N = 256 时，Best-of-N 最好。

  虽然我们看到束搜索在中等和困难问题（级别 3-5）中提供了持续的增益，但在较简单的问题上（尤其是在大的计算预算下），它的表现往往比 Best-of-N更差。

  通过查看束搜索生成的结果树，我们意识到，如果一个步骤被赋予高奖励，那么整个树就会收敛到该路径，从而影响多样性。这促使我们探索一种扩展束搜索的方法，以最大化多样性——让我们来看看！

## DVTS：通过多样性提升性能

 
正如我们上面所见，束搜索在 Best-of-N 上表现出色，但在较简单的问题和较大的测试时间计算预算下往往表现不佳。为了解决这个问题，我们开发了一种扩展，称为多样化验证器树搜索（Diverse Verifier Tree Search，DVTS），旨在在较大的 N 值下最大化多样性。

DVTS 的工作方式与束搜索类似，但有以下修改：

1. 对于给定的 N 和 M，将初始束集合扩展为 N / M 个独立的子树。

2. 对于每个子树，选择 PRM 得分最高的步骤。

3. 从步骤（2）中选定的节点生成 M 个新步骤，选择 PRM 得分最高的步骤。

4. 重复步骤（3），直到到达 EOS 标记或最大树深度。

   以下是将 DVTS 应用于 Llama 1B 的结果：

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/10.png)


如我们所见，DVTS 为束搜索提供了一种补充策略：在较小的 N 值下，束搜索更有效地找到正确的解，但在较大的 N 值下，DVTS 候选解的多样性开始发挥作用，我们获得了更好的性能。

我们还可以从问题难度的分解中看到这一点，DVTS 在大的 N 值下增强了在简单/中等问题上的性能，而束搜索在小的 N 值下在各种问题难度上表现最佳：



![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/11.png)

**六、总结**

**总结：测试时计算扩展的最佳策略**

1. **计算最优的扩展策略（Compute-Optimal Scaling）**

   **核心思想：**

   在给定的计算预算下，选择能够实现最佳性能的搜索方法和超参数组合。

   **公式表示：**

   θ*(N) = argmax_θ [ E_{y ∼ Target(θ, N, q)} [ 1_{y = y*(q)} ] ]

   挑战：直接计算 θ*(N) 较为困难。

   **解决方案：**

   DeepMind 提出了基于问题难度的近似方法，根据不同难度级别，确定最佳的搜索策略和计算资源分配：

   - **简单问题、低计算预算：**使用 Best-of-N 等简单方法。
   - **复杂问题、高计算预算：**使用束搜索（Beam Search）等高级方法。

2. **θ\*(N)**：给定计算预算 N 的最优参数和策略组合。

   **y\*(q)**：问题 q 的真实答案。

   **θ**：搜索方法和超参数的组合。

3. **向更大模型的扩展**

   **目的：**探究计算最优策略在更大模型上的效果，以及过程奖励模型（PRM）在较大模型中是否仍然有益。

   **发现：**

   - 计算最优扩展策略效果显著。
   - 即使在大型模型上，使用计算最优策略的较小模型（如 Llama 13B）性能可超过更大的模型（如 Llama 2 70B Instruct）。

4. **未来方向和挑战**

   - **增强验证器的能力：提升验证器的鲁棒性和泛化能力，对于改进模型性能至关重要。

   - 实现自我验证（Self-Verification）：使模型能够自主验证输出，提高可靠性，需要比标准监督微调更复杂的策略。

   - 融入“思考”过程：**在生成过程中加入显式的中间步骤或推理过程，增强模型的推理能力。

   - 搜索作为数据生成工具：利用搜索方法生成高质量训练数据，进一步微调和改进模型。

   - 开发更多过程奖励模型（PRMs）：丰富的 PRM 有助于提升不同领域的模型性能。

   - **扩展至非可验证领域：\**将方法应用于结构较弱或主观性较强的任务，需要新的策略。

     \*\*结论：\*\*

     找到合适的解码方式并结合强大的验证器，是提升大型语言模型性能的关键。最佳解码策略取决于问题难度和计算预算，没有一种通用的方法。优化模型性能需要综合考虑任务需求和可用资源。\****

5. 

6. 解码方法可以单独使用，也可以结合使用，具体取决于任务需求和目标。以下是一些常见的情况：

7. 单独使用：

   - 贪婪解码：适用于简单任务，计算效率高。
   - 束搜索：适用于需要生成高质量文本的任务，尽管计算复杂度较高。
   - 温度采样、Top-k 采样、Top-p 采样：用于控制生成文本的随机性和多样性。

   结合使用：

   - 在一些复杂任务中，可能会结合多种解码方法。例如，先使用束搜索生成多个候选，然后再用温度采样或Top-p采样从中选择最优解。
   - 结合使用可以在保证生成质量的同时，增加文本的多样性和创意性。

8. ***\*
   \****

**总结：**

在追求最佳性能的过程中，应根据具体任务和资源限制，选择最合适的解码方法，并视情况决定是否结合验证器。针对任务特点，择优选择解码策略，而非同时使用多种方法。



**一、前情回顾**

在之前文章[SLM 如何在推理任务中击败大型模型](https://mp.weixin.qq.com/s?__biz=MzAwMDc2NjQ4Nw==&mid=2663562788&idx=1&sn=519f460e92f6998b3eff9dabd93873f8&scene=21#wechat_redirect)中，我介绍了test-time compute scaling的实现，大致的实现图：

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/12.png)



1. 我们首先将一个数学问题输入大型语言模型（LLM），它生成 N 个部分解，例如推导中的一个中间步骤。

2. 每个步骤由过程奖励模型（PRM）评分，它估计每个步骤最终到达正确最终答案的概率。

3. 这些步骤和 PRM 分数然后被给定的搜索策略使用，以选择哪些部分解应被进一步探索，以生成下一轮中间步骤。

4. 一旦搜索策略终止，最终的候选解由 PRM 排序，产生最终答案。

   为了比较各种搜索策略，我们使用了以下开源模型和数据集：

- **模型**：我们使用了 `meta-llama/Llama-3.2-1B-Instruct` 作为扩展测试时间计算的主要模型。由于其 10 亿参数的轻量级特性，可以实现快速迭代，其在数学基准测试中的未饱和性能使其成为突出扩展优势的理想选择。
- **过程奖励模型（PRM）**：为了指导我们的搜索策略，我们使用了 `RLHFlow/Llama3.1-8B-PRM-Deepseek-Data`，这是一个使用过程监督（process supervision）训练的 80 亿参数的奖励模型。过程监督是一种训练方法，模型在推理过程的每个步骤（而不仅仅是最终结果）都能收到反馈。我们选择这个模型是因为它属于与我们的策略相同的模型家族，并且在我们测试的这个参数量级中，比我们测试的其他 PRM（如 Math-Shepherd）给出了更好的结果。
- **数据集**：我们在 MATH 基准的 MATH-500 子集上进行了评估，这是 OpenAI 作为其过程监督研究的一部分发布的数据集。这些数学问题涵盖了七个学科，对人类和大多数大型语言模型来说都具有挑战性。看看下面的数据集浏览器，感受一下问题的难度吧！我们在从每个提示生成 1 到 256 个生成的计算预算上测试了每个搜索策略，并使用五个随机种子运行数据生成流程，以估计运行间的方差。你可以在这个集合中找到我们分析的模型和数据集。



而几种常见的生成候选者的方法包含：

| 方面           | 贪婪解码（Greedy Decoding）                                  | 束搜索（Beam Search）                                        | 多样化验证器树搜索（DVTS）                                   | 多数投票（Majority Voting）                                  |
| :------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- | :----------------------------------------------------------- |
| **基本概念**   | 在每一步选择概率最高的词，生成单一序列。                     | 在每一步保留多个最有可能的候选序列，探索更多的可能性。       | 通过将束分成独立的子树，并使用验证器引导搜索，增加多样性和性能。 | 生成多个独立的候选答案，选择出现次数最多的答案作为最终输出。 |
| **工作原理**   | - 在生成文本时，每一步都选择当前概率最高的下一个词。 - 生成一个单一的、最可能的序列。 | - 保持固定数量（束宽度）的最佳部分序列。 - 在每个步骤扩展这些序列，选出新的最佳候选。 | - 将初始束划分为多个独立的子树。 - 在每个子树中，使用过程奖励模型（PRM）评估和引导生成。 - 通过独立扩展，增加解的多样性。 | - 使用随机采样等方法生成多个独立的候选答案。 - 对生成的答案进行统计，选择出现次数最多的答案。 |
| **搜索空间**   | 窄（单一路径）。                                             | 中等（取决于束宽度）。                                       | 广（多个子树，增加了探索的广度）。                           | 宽（生成多个独立的答案），但不在单次生成中扩展。             |
| **多样性**     | 很低（只有一个输出）。                                       | 中等（受束宽度限制）。                                       | 高（独立子树增加了多样性）。                                 | 中等（取决于生成的答案数量和随机性）。                       |
| **使用验证器** | 否。                                                         | 可选（可以使用，但不总是用）。                               | 是的，使用过程奖励模型（PRM）在每一步进行评分和引导。        | 否，通常不使用验证器，仅通过统计频率选择答案。               |
| **优点**       | - 简单快捷。 - 计算效率高。                                  | - 在精度和计算成本之间取得平衡。 - 提高找到全局最优解的机会。 | - 增加了解的多样性。 - 在复杂任务上表现更好。 - 利用验证器引导，提高准确率。 | - 简单易行。 - 减少随机性带来的波动。 - 提高答案的稳定性和一致性。 |
| **缺点**       | - 只关注局部最优，可能错过更好的解。 - 缺乏多样性。          | - 计算量比贪婪解码大。 - 可能仍然错过一些解。                | - 实现更复杂。 - 需要额外的计算资源。 - 依赖于验证器的质量。 | - 无法保证选择的答案是正确的。 - 如果答案多样性过高，可能没有明确的多数。 - 增加了计算成本。 |
| **适用场景**   | - 需要快速生成单一答案的简单任务。 - 对结果质量要求不高的情况。 | - 需要在质量和计算成本之间平衡的任务。 - 适用于一般复杂度的任务。 | - 复杂或需要深入推理的任务。 - 有较大计算预算，可用于提升性能。 | - 希望提高答案稳定性和一致性的任务。 - 需要减少随机性影响的情况下。 |
| **计算复杂度** | 低。                                                         | 中等（取决于束宽度）。                                       | 高（由于使用了验证器和更多的搜索路径）。                     | 中等到高（取决于生成的答案数量）。                           |



**二、遗传算法的优势**


---

# Part 11: Mind Evolution 与遗传算法

> *原文来自 SLM-Capabilities-and-Fine-Tuning*


## **遗传算法（Genetic Algorithm）** 是一种用于解决优化和搜索问题的自适应启发式算法，模拟了自然选择和遗传变异的过程。它的核心思想是“适者生存”，通过选择、交叉和变异等操作，让优秀的个体（解）在种群中得以保留，并生成新的更优的解。 

 

 **为什么引入遗传算法？**

 
在 DeepMind 的 **Mind Evolution** 方法中，遗传算法被引入是为了：

- **增强搜索能力**：通过模拟生物进化的过程，更有效地探索复杂问题的解空间。
- **避免局部最优**：遗传算法能够避免陷入局部最优解，增加找到全局最优解的机会。
- **提高方案质量**：通过迭代地优化候选方案，使得最终的解决方案质量更高。



**遗传算法的关键步骤**

 
**（1）初始化种群**

- **种群**：由多个候选方案（个体）组成。

- **初始化**：使用大型语言模型（LLM）生成初始的候选方案集。

  **（2）评估适应度**

- **适应度函数**：评估每个候选方案的优劣程度。

- **评估**：根据任务要求和约束条件，对每个方案进行打分。

  **（3）选择（Selection）**

- **目的**：选出优秀的候选方案作为“父代”。

- **方法**：根据适应度分数，使用概率性方法从种群中选择个体。

  **（4）交叉（Crossover）**

- **目的**：组合两个或多个父代方案的特征，生成新的候选方案（子代）。

- **方法**：使用 LLM，将父代方案的优点融合，生成新的方案。

  **（5）变异（Mutation）**

- **目的**：在候选方案中引入随机变化，增加多样性。

- **方法**：对候选方案进行随机的微小修改。

  **（6）产生新一代**

- **循环**：将新生成的候选方案加入种群，重复评估和选择的过程。



### **遗传算法在 Mind Evolution 中的应用**

 
**示例任务**：为用户规划一个满足特定要求的旅行计划。

**步骤示意**：

1. **生成初始方案**：LLM 生成多个初始旅行计划。
2. **评估方案**：计算每个计划的适应度分数，例如根据是否满足预算、行程安排、用户偏好等。
3. **选择优秀方案**：根据适应度分数，选择几个较好的旅行计划作为父代。
4. **交叉生成新方案**：使用 LLM，将父代计划的优点结合，生成新的旅行计划。例如，结合父代 A 的酒店安排和父代 B 的景点选择。
5. **变异引入新元素**：在新方案中，随机调整一些细节，例如更改用餐地点或增加新的景点。
6. **评估新方案并重复**：对新生成的方案再次评估适应度，继续选择和生成，迭代多次，直到找到最优的旅行计划。 

###  

### **遗传算法的优势、**

- **全球优化能力强**：能够在广阔的解空间中寻找最优解。

- **适应性强**：对于复杂、多约束的问题，能够有效处理。

- **并行化**：遗传算法的过程可以并行执行，提升计算效率。

  

  

**三、\**Mind Evolution的实现\****

在DeepMind新的论文**《Evolving Deeper LLM Thinking》**中，介绍了新的实现。

**Mind Evolution** 是一种结合了**大型语言模型（LLM）\**和\**进化算法**的搜索方法，旨在提高 LLM 在解决复杂问题（如自然语言规划任务）时的能力。这个方法模拟了生物进化的过程，通过生成、评估、选择、交叉、变异和改进等步骤，迭代地优化候选方案，最终找到最佳解决方案。 

 

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-RL-Training-and-Reasoning/images/14.png)

### **Mind Evolution 的七个主要步骤**

1. **候选方案的生成（初始化）**

2. **方案的评估（Fitness Evaluation）**

3. **批判性对话下的改进（Refinement through Critical Conversation，RCC）**

4. **选择（Selection）**

5. **交叉和变异（Crossover and Mutation）**

6. **迭代与进化（Iteration and Evolution）**

7. **岛屿模型的应用（Island Model - Migration and Reset）**

   
   下面，我将逐一解释每个步骤，以及其中涉及的算法和概念，并举例说明。

### **步骤 1：候选方案的生成（初始化）**

 
**由谁完成**：大型语言模型（LLM）

**解释**：

- **目的**：根据给定的任务或问题描述，生成一组初始的候选解决方案。

- **使用的算法/方法**：**大型语言模型（LLM）**的生成能力。

- **如何完成**：使用 LLM，结合问题的描述、相关信息和指示，生成多个可能的解决方案。这些方案以自然语言形式表达，直接针对问题本身。

  **举例**：

  **任务场景**：假设我们需要为用户规划一次旅行，满足以下条件：

- 从**北京**出发，计划一个**5 天的旅行**。

- 想要去的城市有**上海**、**杭州**、**苏州**。

- 预算是**5000 元**。

- 希望**第一天**在上海，**最后一天**返回北京。

  **LLM 生成的初始候选方案**：

- **方案 1**：

  - 第一天：北京 -> 上海，游览外滩和南京路，住宿上海。
  - 第二天：上海 -> 杭州，游览西湖，住宿杭州。
  - 第三天：杭州 -> 苏州，游览拙政园和虎丘，住宿苏州。
  - 第四天：苏州，游览寒山寺和狮子林，住宿苏州。
  - 第五天：苏州 -> 北京，结束行程。

- **方案 2**：

  - 第一天：北京 -> 上海，游览迪士尼乐园，住宿上海。
  - 第二天：上海，游览东方明珠和豫园，住宿上海。
  - 第三天：上海 -> 杭州，游览灵隐寺，住宿杭州。
  - 第四天：杭州，游览西湖和雷峰塔，住宿杭州。
  - 第五天：杭州 -> 北京，结束行程。

- **方案 3**：

  - 第一天：北京 -> 苏州，游览拙政园，住宿苏州。
  - 第二天：苏州 -> 杭州，游览西湖，住宿杭州。
  - 第三天：杭州 -> 上海，游览外滩，住宿上海。
  - 第四天：上海，游览东方明珠，住宿上海。
  - 第五天：上海 -> 北京，结束行程。



### **步骤 2：方案的评估（Fitness Evaluation）**

 
**由谁完成**：**评估函数（程序化的评价器）**

**解释**：

- **目的**：对每个候选方案进行评分，判断其质量，并检查是否满足问题的约束和目标。

- **使用的算法/方法**：**评估函数**，这是一个程序化实现的函数，用于评估方案的好坏。它不属于某种复杂的算法，但在设计上需要考虑如何客观、公正地评估方案。

- **如何完成**：编写一个评估函数，解析每个方案，检查其是否满足以下条件：

  - 是否覆盖了所有必须去的城市？

  - 是否遵循了时间安排（第一天在上海，最后一天返回北京）？

  - 是否在预算之内？

  - 是否有任何冲突或不合理之处？

    **举例**：

    **评估方案 1**：

- **检查结果**：

  - 覆盖了所有必须去的城市：是。

  - 时间安排：第一天在上海，最后一天返回北京，符合要求。

  - 预算：需要计算总费用，假设总费用为 4800 元（符合预算）。

  - 评价：方案合理，满足所有要求。

    **评估方案 2**：

- **检查结果**：

  - 覆盖了所有必须去的城市：缺少苏州。

  - 时间安排：第一天在上海，最后一天返回北京，符合要求。

  - 预算：假设总费用为 5200 元（超出预算）。

  - 评价：未包含苏州，预算超标。

    **评估方案 3**：

- **检查结果**：

  - 覆盖了所有必须去的城市：是。

  - 时间安排：第一天在苏州，未在第一天到达上海，不符合要求。

  - 时间安排：最后一天从上海返回北京，符合要求。

  - 预算：假设总费用为 4500 元（符合预算）。

  - 评价：未在第一天到达上海。

    **提供反馈**：

- 对于方案 2：建议加入苏州，并控制总费用在预算内。

- 对于方案 3：建议调整行程，使得第一天在上海。

### **步骤 3：批判性对话下的改进（Refinement through Critical Conversation，RCC）**

 
**由谁完成**：大型语言模型（LLM）

**解释**：

- **目的**：通过模拟**批评者**和**作者**之间的对话，对候选方案进行深入分析和改进。

- **使用的算法/方法**：利用 LLM 的生成和理解能力，扮演不同的角色，进行对话式的方案改进。

- **如何完成**：

  - 根据批评者的反馈，对方案进行修改，提出改进后的方案。

    **举例**：

    **对于方案 2 的批判性对话**：

  - 分析方案，结合评估函数的反馈，指出方案中的问题。

  - 提出改进的建议。

  - **批评者（Critic）**角色：

  - **作者（Author）**角色：

- **批评者**：

  - “该方案未包含苏州，导致未满足用户想去的所有城市的要求。此外，预算超出了 5000 元的限制。建议在行程中加入苏州，并适当调整游览项目，控制总费用。”

- **作者**：

  - “好的，我将调整方案。在第三天，增加前往苏州的行程，游览拙政园，住宿苏州。并在上海的游览项目中选择性地减少一些景点，以控制预算。”

    **改进后的方案**：

- 第一天：北京 -> 上海，游览迪士尼乐园，住宿上海。

- 第二天：上海，游览东方明珠，住宿上海。

- 第三天：上海 -> 苏州，游览拙政园，住宿苏州。

- 第四天：苏州 -> 杭州，游览西湖，住宿杭州。

- 第五天：杭州 -> 北京，结束行程。

  **重新评估**：

- 方案现在包含了所有必须去的城市，预算控制在 5000 元以内。

- 

### **步骤 4：选择（Selection）**

 
**由谁完成**：算法流程（程序控制）

**解释**：

- **目的**：根据评估得分，从当前的候选方案中选择优质的方案作为“父代”。

- **使用的算法/方法**：**博尔兹曼选择（Boltzmann Selection）**，这是一种基于概率的选择策略。

- **如何完成**：

  - 计算每个方案的适应度得分。

  - 使用**软最大化（softmax）**函数，将适应度得分转换为选择概率。

  - 根据概率随机抽样，选择一些方案作为父代。

    **举例**：

- 假设有 4 个方案，适应度得分分别为 0.9、0.8、0.5、0.2。

- 通过 softmax 转换，计算出每个方案被选中的概率。

- 可能最终选出方案 1 和方案 2 作为父代。



### **步骤 5：交叉和变异（Crossover and Mutation）**

**由谁完成**：大型语言模型（LLM）与算法流程（程序控制）

**解释**：

- **目的**：通过组合和修改父代方案，生成新的候选方案（子代），从而探索新的解决方案空间。

- **使用的算法/方法**：交叉和变异是遗传算法的核心操作。

  **交叉（Crossover）**：

- **如何完成**：

  - 从选定的父代方案中，挑选部分内容进行组合。
  - 使用 LLM，根据父代方案，生成新的方案。

**举例**：

- **父代方案 A**：
- 第一天：北京 -> 上海，游览外滩，住宿上海。
- 第二天：上海 -> 杭州，游览西湖，住宿杭州。
- 第三天：杭州，游览灵隐寺，住宿杭州。
- 第四天：杭州 -> 苏州，游览拙政园，住宿苏州。
- 第五天：苏州 -> 北京，结束行程。

- **父代方案 B**：
  - 第一天：北京 -> 上海，游览迪士尼乐园，住宿上海。
  - 第二天：上海，游览东方明珠，住宿上海。
  - 第三天：上海 -> 苏州，游览寒山寺，住宿苏州。
  - 第四天：苏州 -> 杭州，游览雷峰塔，住宿杭州。
  - 第五天：杭州 -> 北京，结束行程。

**交叉生成子代方案**：

- 第一天：北京 -> 上海，游览外滩和迪士尼乐园，住宿上海。
- 第二天：上海 -> 苏州，游览寒山寺和拙政园，住宿苏州。
- 第三天：苏州 -> 杭州，游览西湖和雷峰塔，住宿杭州。
- 第四天：杭州，游览灵隐寺和其他景点，住宿杭州。
- 第五天：杭州 -> 北京，结束行程。



- **变异（Mutation）**：
- **如何完成**：
  - 对新生成的子代方案，进行随机的小幅修改。
  - 使用 LLM，引入新的元素或调整行程细节。
- **举例**：
  - 在子代方案中，随机将第四天的行程从杭州改为再次返回上海，或者增加新的景点。

### **步骤 6：迭代与进化（Iteration and Evolution）**

 
**由谁完成**：算法流程（程序控制）

**解释**：

- **目的**：重复执行前面的步骤（生成、评估、选择、交叉、变异和改进），经过多代迭代，逐步提升方案质量。

- **使用的算法/方法**：迭代循环，直到满足终止条件。

- **如何完成**：

  - 在每一代，生成新的候选方案，对其进行评估和改进。

  - 持续进行多次迭代，观察方案质量的提升。

    **举例**：

- **第 1 代**：初始生成的候选方案，可能只有一部分满足要求。

- **第 2 代**：经过交叉、变异和改进，方案质量有所提升，更多的方案满足要求。

- **第 3 代**：继续优化，可能接近找到最佳方案。

- **迭代终止条件**：找到满足所有要求的方案，或者达到预设的最大迭代次数。



### **步骤 7：岛屿模型的应用（Island Model - Migration and Reset）**

 

**由谁完成**：算法流程（程序控制）

**解释**：

- **目的**：通过引入岛屿模型，保持方案的多样性，避免过早收敛到次优解。
- **使用的算法/方法**：**岛屿模型**，包括**迁移（Migration）**和**重置（Reset）**操作。
- **如何完成**：
- **划分岛屿**：
  - 将候选方案的种群分为多个独立的子群体，称为岛屿。
  - 每个岛屿独立地进行进化，避免相互干扰。
- **迁移（Migration）**：
  - 在预定的迭代代数后，将一些优秀的方案从一个岛屿迁移到另一个岛屿。
  - 促进优秀基因的传播，丰富其他岛屿的方案多样性。
- **重置（Island Reset）**：
  - 定期评估各个岛屿的整体表现。
  - 对于表现较差的岛屿，将其种群替换为全局最优的方案或重新生成新的方案。
  - 避免陷入局部最优，重新探索新的解空间。
- 
- **举例**：
- **假设有 4 个岛屿**（Island 1、Island 2、Island 3、Island 4）。
- **迁移操作**：
  - 在每隔 3 代后，将 Island 1 中最优秀的 5 个方案迁移到 Island 2，替换其种群中最差的 5 个方案。
  - 同时，Island 2 的优秀方案迁移到 Island 3，以此类推。
- **重置操作**：
  - 如果 Island 4 在连续多代中方案质量较差，决定对其进行重置。
  - 从全局最优的方案中选取一些，替换 Island 4 的种群。

### 

### **总结**

 
**Mind Evolution 方法**通过以上七个步骤，结合了大型语言模型（LLM）的生成和理解能力，以及进化算法（包括遗传算法和岛屿模型）的全局优化策略，成功地在自然语言规划任务中实现了高效的方案优化。

- **LLM 的作用**：
  - 生成初始候选方案。
  - 扮演批评者和作者的角色，进行方案的批判性对话和改进。
  - 在交叉和变异操作中，生成新的方案。
- **评估函数**：
  - 对方案进行客观的评估，提供反馈。
  - 指导方案的优化方向。
- **遗传算法的操作**：
  - 选择、交叉、变异，探索新的解空间。
  - 通过迭代，逐步提升方案质量。
- **岛屿模型的应用**：
  - 通过划分岛屿、迁移和重置，保持方案的多样性。
  - 避免过早收敛，提高全局优化能力。

---



---

# Part 12: SLM 微调实验

> *原文来自 SLM-Capabilities-and-Fine-Tuning*


## Phi-4 Thinks as DeepSeek-R1

﻿

I tried fine-tuning Microsoft's Phi-4 model using the open-source R1 dataset. Below, I'll share my steps with everyone. 

***Please click below pictures to see my demo video on Youtube***:
[![SLM-DS-R1-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/9CVKR0YcdKU)

### **Dataset Used**

**Why Choose This Dataset?** 

I used the **`reasoning-deepseek`** subset from the `cognitivecomputations/dolphin-r1` dataset. This dataset was generated by the large model **DeepSeek-R1** and contains **30,000** training samples, focusing on reasoning and question-answering capabilities.  

![images](images/deepseek_r1_dataset.png)

The dataset contains the model's reasoning process, wrapped with special `<think>` tags, which can help our model learn how to think and reason. 


**Data Preprocessing**

Before using this dataset, we need to do some preprocessing:

- **Merge Fields**: Combine the `reasoning` and `answer` fields in the dataset into a new `assistant_message`, and add it to the `messages` column. This way, our model can learn the complete question-answering and reasoning process.
- **Handle Special Tokens**: Since the data uses `<think>` tags, we need to add these special tokens to the tokenizer so that the model can correctly understand and generate them.

### Fine-tuning the Phi-4 Model

During the fine-tuning process, I chose the **LoRA (Low-Rank Adaptation)** method. This is a parameter-efficient fine-tuning technique that allows the model to learn new capabilities without significantly increasing the number of parameters.

**Main Steps of Fine-tuning Include:**

1. **Load Model and Tokenizer**: Use `microsoft/phi-4` as the base model and load the corresponding tokenizer.

2. **Add Special Tokens to Tokenizer**: Add `<think>` and `</think>` to the tokenizer's special tokens and adjust the model's embedding layer to accommodate the new vocabulary size.

3. **Set Up LoRA Configuration**: Specify the model modules to train, such as `q_proj`, `k_proj`, `v_proj`, `o_proj`, etc.

4. **Start Training**: Fine-tune the model using the preprocessed dataset.

5. **Resource Consumption**

- **GPU Memory**: Approximately 72149MiB of GPU memory is needed.
- **Training Time**: It took about 4 hours on a H100

![images](images/deepseek_r1_gpu.png)



### Full code

Training code：

```
from datasets import load_dataset  
import torch, multiprocessing, sys  
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig  
from peft import prepare_model_for_kbit_training, LoraConfig  
from trl import SFTConfig, SFTTrainer  
  
compute_dtype = torch.bfloat16    
# attn_implementation = 'flash_attention_2' 
  
# 加载 tokenizer  
tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-4")  
tokenizer.pad_token = "<|finetune_right_pad_id|>"  
tokenizer.pad_token_id = 100257  
tokenizer.padding_side = 'right'  
  
# 添加新标记 '<think>' 和 '</think>'  
new_tokens = ['<think>', '</think>']  
tokenizer.add_tokens(new_tokens)  
  
# 加载数据集  
ds = load_dataset("cognitivecomputations/dolphin-r1", 'reasoning-deepseek', split='train[:30000]').train_test_split(test_size=0.1)  
  
# 处理数据集  
def process(row):  
    assistant_message = "<think>" + row['reasoning'] + "</think>\n\n" + row['answer']  
    row['messages'].append({'role': 'assistant', 'content': assistant_message})  
    # 手动拼接消息内容  
    conversations = ''  
    for message in row['messages']:  
        conversations += f"{message['role']}: {message['content']}\n"  
    row['text'] = conversations.strip()  
    return row  
  
ds['train'] = ds['train'].map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
ds['test'] = ds['test'].map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
def fine_tune(model_name, batch_size=1, gradient_accumulation_steps=32, LoRA=False, QLoRA=False):  
  
    if QLoRA:  
        bnb_config = BitsAndBytesConfig(  
            load_in_4bit=True,  
            bnb_4bit_quant_type="nf4",  
            bnb_4bit_compute_dtype=compute_dtype,  
            bnb_4bit_use_double_quant=True,  
        )  
        model = AutoModelForCausalLM.from_pretrained(  
            model_name, quantization_config=bnb_config, device_map={"": 0}  
        )  
        model = prepare_model_for_kbit_training(model)  
    else:  
        model = AutoModelForCausalLM.from_pretrained(  
            model_name, device_map={"": 0}, torch_dtype=compute_dtype  
        )  
        model.gradient_checkpointing_enable()  
  
    # **调整模型的嵌入矩阵以匹配新的词汇表大小**  
    model.resize_token_embeddings(len(tokenizer))  
  
    if LoRA or QLoRA:  
        peft_config = LoraConfig(  
            lora_alpha=16,  
            lora_dropout=0.05,  
            r=16,  
            bias="none",  
            task_type="CAUSAL_LM",  
            target_modules=['k_proj', 'o_proj', 'q_proj', 'v_proj', 'up_proj', 'down_proj', 'gate_proj'],  
            modules_to_save=["lm_head", "embed_tokens"],  
        )  
    else:  
        peft_config = None  
  
    output_dir = "./LoRA/"  
  
    training_arguments = SFTConfig(  
        output_dir=output_dir,  
        evaluation_strategy="steps",  
        do_eval=True,  
        optim="adamw_8bit",  
        per_device_train_batch_size=batch_size,  
        gradient_accumulation_steps=gradient_accumulation_steps,  
        per_device_eval_batch_size=batch_size,  
        log_level="debug",  
        save_strategy="steps",        
        save_steps=200,              
        logging_steps=25,  
        learning_rate=1e-5,  
        bf16=True,                    
        eval_steps=200,               
        num_train_epochs=1,  
        warmup_ratio=0.1,  
        lr_scheduler_type="linear",  
        dataset_text_field="text",  
        max_seq_length=1024,  
        report_to='none',  
        save_total_limit=3            
    )  
  
    trainer = SFTTrainer(  
        model=model,  
        train_dataset=ds['train'],  
        eval_dataset=ds['test'],  
        peft_config=peft_config,  
        tokenizer=tokenizer,          
        args=training_arguments,  
    )  
  
    trainer.train()  
```

```
fine_tune("microsoft/phi-4", batch_size=16, gradient_accumulation_steps=4, LoRA=True)
```

![images](images/deepseek_r1_training.png)

Load Fine-tuned Model

```
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

compute_dtype = torch.bfloat16
attn_implementation = 'flash_attention_2'

tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-4")
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 100257

tokenizer.vocab[128011] = '<think>'
tokenizer.vocab[128012] = '</think>'
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/phi-4",
    device_map={"": 0},
    attn_implementation=attn_implementation,
    torch_dtype=torch.bfloat16,
)

model = PeftModel.from_pretrained(model, "./LoRA/checkpoint-422/")
```

**Inference test**

**Question 1 and answer 1:**

```
prompt = [{'role':'system', 'content':"You are a helpful assistant, please think before answering."},
    {'role':'user', 'content':"Assume there is a pond with an infinite amount of water. You have two empty jugs with capacities of 5 liters and 6 liters, respectively. How can you use only these two jugs to obtain exactly 3 liters of water from the pond?"}
    ]

prompt = tokenizer.apply_chat_template(prompt, tokenize=False, add_generation_prompt=True)
input_ids = tokenizer(prompt, return_tensors="pt", truncation=True).to('cuda')
output = model.generate(**input_ids, temperature=0.7, max_new_tokens=2048)
print(tokenizer.decode(output[0], skip_special_tokens=False))
```

Result：

```
<|im_end|><|im_start|>user<|im_sep|>Assume there is a pond with an infinite amount of water. You have two empty jugs with capacities of 5 liters and 6 liters, respectively. How can you use only these two jugs to obtain exactly 3 liters of water from the pond?<|im_end|><|im_start|>assistant<|im_sep|><think>Okay, so I need to figure out how to get exactly 3 liters of water using a 5-liter jug and a 6-liter jug. Hmm, this is a classic water jug problem. Let me think about the steps.

First, I need to remember the rules: I can fill either jug from the pond, pour water from one jug to the other until one is full or the other is empty, and empty a jug back into the pond. So, I can't measure directly, but I can use the difference between the two jugs to get the desired amount.

Let's start by filling the 6-liter jug. Then, pour from the 6-liter jug into the 5-liter jug until the 5-liter jug is full. That would leave 1 liter in the 6-liter jug. Then, empty the 5-liter jug back into the pond. Now, pour the remaining 1 liter from the 6-liter jug into the 5-liter jug. Then, fill the 6-liter jug again. Pour from the 6-liter jug into the 5-liter jug until the 5-liter jug is full. Since the 5-liter jug already has 1 liter, it can only take 4 more liters. So, after pouring 4 liters, the 6-liter jug will have 2 liters left. Then, empty the 5-liter jug again. Pour the 2 liters from the 6-liter jug into the 5-liter jug. Now, fill the 6-liter jug again. Pour from the 6-liter jug into the 5-liter jug until the 5-liter jug is full. The 5-liter jug already has 2 liters, so it can take 3 more liters. After pouring 3 liters, the 6-liter jug will have 3 liters left. So, that's how you get 3 liters in the 6-liter jug.

Wait, let me check if that's correct. Let's go through the steps again:

1. Fill the 6-liter jug. (6, 0)
2. Pour from 6-liter to 5-liter until 5-liter is full. (1, 5)
3. Empty the 5-liter jug. (1, 0)
4. Pour the 1 liter from the 6-liter jug into the 5-liter jug. (0, 1)
5. Fill the 6-liter jug again. (6, 1)
6. Pour from 6-liter to 5-liter until 5-liter is full. The 5-liter jug has 1 liter, so it can take 4 more liters. (2, 5)
7. Empty the 5-liter jug. (2, 0)
8. Pour the 2 liters from the 6-liter jug into the 5-liter jug. (0, 2)
9. Fill the 6-liter jug again. (6, 2)
10. Pour from 6-liter to 5-liter until 5-liter is full. The 5-liter jug has 2 liters, so it can take 3 more liters. (3, 5)

So, after step 10, the 6-liter jug has 3 liters left. That's correct. The answer is that you can get 3 liters in the 6-liter jug after these steps.

Alternatively, let me see if there's another way. Maybe starting with the 5-liter jug? But that seems less straightforward. Let me try:

1. Fill the 5-liter jug. (5, 0)
2. Pour from 5-liter to 6-liter. (0, 5)
3. Fill the 5-liter jug again. (5, 5)
4. Pour from 5-liter to 6-liter until 6-liter is full. The 6-liter jug already has 5 liters, so it can take 1 more liter. (4, 6)
5. Empty the 6-liter jug. (4, 0)
6. Pour the 4 liters from the 5-liter jug into the 6-liter jug. (0, 4)
7. Fill the 5-liter jug again. (5, 4)
8. Pour from 5-liter to 6-liter until 6-liter is full. The 6-liter jug has 4 liters, so it can take 2 more liters. (3, 6)

So, after step 8, the 5-liter jug has 3 liters left. That's another way to get 3 liters. So, there are two possible solutions: either the 5-liter jug ends up with 3 liters, or the 6-liter jug ends up with 3 liters. Both are valid.

Therefore, the answer is that you can obtain exactly 3 liters of water in either the 5-liter jug or the 6-liter jug by following the steps outlined above.</think>

To obtain exactly 3 liters of water using a 5-liter jug and a 6-liter jug, follow these steps:

1. Fill the 6-liter jug completely. (6, 0)
2. Pour water from the 6-liter jug into the 5-liter jug until the 5-liter jug is full. (1, 5)
3. Empty the 5-liter jug. (1, 0)
4. Pour the remaining 1 liter from the 6-liter jug into the 5-liter jug. (0, 1)
5. Fill the 6-liter jug again. (6, 1)
6. Pour water from the 6-liter jug into the 5-liter jug until the 5-liter jug is full. (2, 5)
7. Empty the 5-liter jug. (2, 0)
8. Pour the 2 liters from the 6-liter jug into the 5-liter jug. (0, 2)
9. Fill the 6-liter jug again. (6, 2)
10. Pour water from the 6-liter jug into the 5-liter jug until the 5-liter jug is full. (3, 5)

After step 10, the 6-liter jug will contain exactly 3 liters of water. Alternatively, you can also end up with 3 liters in the 5-liter jug by following a different sequence:

1. Fill the 5-liter jug completely. (5, 0)
2. Pour water from the 5-liter jug into the 6-liter jug. (0, 5)
3. Fill the 5-liter jug again. (5, 5)
4. Pour water from the 5-liter jug into the 6-liter jug until the 6-liter jug is full. (4, 6)
5. Empty the 6-liter jug. (4, 0)
6. Pour the 4 liters from the 5-liter jug into the 6-liter jug. (0, 4)
7. Fill the 5-liter jug again. (5, 4)
8. Pour water from the 5-liter jug into the 6-liter jug until the 6-liter jug is full. (3, 6)

After step 8, the 5-liter jug will contain exactly 3 liters of water.<|im_end|>
```

There are two more inference test:

**Question 2 and answer 2:**

```
<|im_start|>user<|im_sep|>Suppose you're on a game show, and you're given the choice of three doors: Behind one door is a gold bar; behind the others, rotten vegetables. You pick a door, say No. 1, and the host asks you, 'Do you want to pick door No. 2 instead?' What choice of door now gives you the biggest advantage?<|im_end|><|im_start|>assistant<|im_sep|><think>Okay, so this is a classic probability problem, right? It sounds a lot like the Monty Hall problem, but with a twist. Let me think through it step by step.

First, the setup: there are three doors, one with a gold bar and two with rotten vegetables. The contestant picks a door, say No. 1. Then the host offers to switch to door No. 2. So the question is, should the contestant switch to door No. 2, or stick with door No. 1?

In the Monty Hall problem, the contestant initially picks a door, then the host opens one of the other two doors to reveal a goat (or in this case, rotten vegetables), and then the contestant is given the option to switch. The key point in Monty Hall is that the host knows where the prize is and always opens a door with a goat, which changes the probabilities.

But here, the host is offering to switch to door No. 2 without opening any doors. So, the host isn't revealing any additional information. Let me think about the probabilities.

Initially, the probability of the gold bar being behind the chosen door (No. 1) is 1/3, and the probability of it being behind one of the other two doors (No. 2 or No. 3) is 2/3. But since the host is offering to switch to door No. 2, we need to consider the probabilities again.

If the gold bar is behind door No. 1 (which has a 1/3 chance), then switching to door No. 2 would result in getting rotten vegetables. If the gold bar is behind door No. 2 (which has a 1/3 chance), then switching to door No. 2 would result in getting the gold bar. If the gold bar is behind door No. 3 (which has a 1/3 chance), then switching to door No. 2 would result in getting rotten vegetables.

So, the probability of winning the gold bar by switching to door No. 2 is the probability that the gold bar is behind door No. 2, which is 1/3. The probability of winning by sticking with door No. 1 is the probability that the gold bar is behind door No. 1, which is also 1/3.

Wait, but in the Monty Hall problem, the host's action of opening a door changes the probabilities. Here, the host is just offering to switch to door No. 2. So, the host's offer doesn't change the initial probabilities. Therefore, switching to door No. 2 has the same probability of winning as sticking with door No. 1, which is 1/3.

But wait, in the Monty Hall problem, the host's action of opening a door with a goat changes the probabilities because the host knows where the prize is. Here, the host is offering to switch to door No. 2 without opening any doors. So, the host's offer doesn't provide any additional information. Therefore, the probabilities remain the same as the initial probabilities.

So, the probability of winning by switching to door No. 2 is 1/3, and the probability of winning by sticking with door No. 1 is also 1/3. Therefore, there is no advantage to switching or sticking. Both options have the same probability of winning.

Therefore, the answer is that there is no advantage to switching or sticking. Both options have the same probability of winning, which is 1/3.</think>

In this scenario, the host's offer to switch to door No. 2 does not provide any additional information, as no doors are opened to reveal the contents behind them. Therefore, the probabilities remain the same as the initial choice. The probability of the gold bar being behind the initially chosen door (No. 1) is 1/3, and the probability of it being behind one of the other two doors (No. 2 or No. 3) is 2/3. However, since the host is offering to switch specifically to door No. 2, the probability of winning by switching to door No. 2 is 1/3, and the probability of winning by sticking with door No. 1 is also 1/3. Thus, there is no advantage to switching or sticking; both options have the same probability of winning, which is 1/3.<|im_end|>
```

The results were satisfying! The model successfully generated a reasoning process containing `<think>` tags, demonstrating a certain level of logical thinking ability. 

By using datasets provided by the community, we can fine-tune models like **Phi-4** enabling smaller models to possess certain "thinking" and reasoning abilities.



**Refer to：**

https://kaitchup.substack.com/p/fine-tuning-your-llm-to-think-like-r1

---

## Gemma 3 270M 小模型能力上限探测

﻿## **Gemma 3 270M小模型能力上限探测**

#### 结论

1. **模型选型上**：对于纯任务型（翻译、抽取等），270M Base > 270M Instruct，因为 Instruct 会保留安全规避和对话习惯，不利于目标任务收敛。
2. **训练轮次**：验证集 BLEU 和 Loss 在第 3 轮左右是最佳点 → 应用早停策略，避免第 4 轮开始的性能回落（过拟合）。
3. **任务方向性**：如果数据方向匹配度差（法→英），即使训练 Loss 下降，BLEU 也不会提升，提示需要换更匹配的数据集。
4. **训练动态**：Base 模型在训练集 Loss 和验证集 Loss 上同时优于 Instruct，说明它不仅记得住，还能更好泛化。
5. **工程建议**：
   - 低资源场景优先 Base 模型全量微调
   - 在监控 BLEU 变化的同时用验证集 Loss 作为早停指标
   - 数据方向和领域匹配比纯 epochs 增加更重要

| 要素         | 细节                                                         | 工程化手段（方法）                                           | 工程意义                                               |
| ------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------ |
| **问题**     | 微型模型（270M）开箱即用性能差，跨语言任务几乎不可用（BLEU≈2.23），长上下文和复杂指令跟随能力弱 | —                                                            | 小模型通用性不足、稳定性低，零样本不具备上线条件       |
| **工程目标** | 在单卡 6~12GB 显存条件下，让小模型在特定任务（英→法翻译）上达到可用精度 | —                                                            | 为边缘部署、低资源场景提供大模型替代路径               |
| **解决方案** | 针对 270M 小模型的低成本优化组合                             | ① 全量微调（包含嵌入层）<br>② 缩小领域（高一致性任务数据）<br>③ 精简模板减少 token<br>④ 一次性喂入大规模、去重数据 | 全量微调+领域聚焦+模板优化，确保小模型任务性能最大化   |
| **实施条件** | 硬件：6GB 可行，12GB 舒适<br>框架：Unsloth + AdamW-8bit<br>数据：OPUS-100、news_commentary<br>时长：RTX4090 数小时 | ⑤ AdamW-8bit 优化器<br>⑥ 梯度累积<br>⑦ BF16 精度推理         | 明确资源与参数配置，降低尝试门槛                       |
| **结果**     | BLEU 从 2.23 提升到 ≈18（可达 30）<br>base 版优于 instruct 版（避免安全层干扰）<br>推理速度快、显存低 | —                                                            | 小模型能接近大模型效果，部署成本极低                   |
| **经验结论** | 小模型零样本弱，微调后可作高可靠组件；数据多样性优于重复训练；全量微调优于高冻结率方法 | —                                                            | 为低预算工程师提供模型选型、数据策略、训练方法决策参考 |

![images](images/gemma3_summary.png)



### Training Loss分析

![images](images/gemma3_bleu.png)

- **横轴**：Epoch（轮次）
- **纵轴**：BLEU（翻译质量，越高越好）
- **颜色含义**：
  - 红色：Base 模型（英→法）
  - 蓝色：Instruct 模型（英→法）
  - 黄色：Instruct（法→英）
  - 绿色：Base（法→英）

#### 现象

1. **英→法任务**里，Base 模型（红线）BLEU 全程高于 Instruct（蓝线），并在第 3 轮达到峰值（≈11），之后略有回落；Instruct 模型峰值略低（≈9.5）。
2. **法→英任务**几乎没提升（绿线、黄线）——BLEU 全程低且在第 1 轮后反而下降，说明训练数据或任务定义对该方向支持不足。
3. 两个方向都在第 3 轮出现峰值，**第 4 轮开始出现下降** → 典型的过拟合信号（训练集拟合更好，但泛化能力变差）。

#### 含义

- Base 模型在翻译任务学习速度和质量上明显优于 Instruct，这是因为 Instruct 的安全/助手调优干扰了直接翻译目标。
- 最佳训练 Epoch ≈ 3，再往后会损失效果，要早停。
- 数据和任务方向的匹配度差时（法→英）即使反复训练也无显著提高。



#### Validation Loss分析

![images](images/gemma3_val_loss.png)

- **横轴**：训练步数
- **纵轴**：验证集 Loss（越低越好）
- **红线 = Base 模型，蓝线 = Instruct 模型**

#### 现象

1. Base 模型（红线）从头到尾验证集 Loss 都更低，并且下降更平稳。
2. Instruct 模型（蓝线）收敛到一个更高的 Loss 水平，中间波动小，但没再持续下降。
3. 训练后半程两条曲线趋于平稳 → 模型学习接近饱和。

#### 含义

- Base 模型在泛化能力上确实优于 Instruct，与 BLEU 结论一致。

- Instruct 模型可能受安全指令或原有对话模式约束，对“翻译”这种单一任务无法充分优化。

  

#### 效果评估

![images](images/gemma3_evaluation.png)

先看图里的变化趋势

**英→法（红=Base，蓝=Instruct）**

- Epoch 0：BLEU 很低（Base ≈ 6，Instruct ≈ 2）
- Epoch 1~3：BLEU 持续提升，第 3 轮达到峰值（Base ≈ 11，Instruct ≈ 9.5）
- Epoch 4：两者 BLEU 都下降
  ✅ 说明模型在第 3 轮学到的能力最强，之后出现**过拟合**（在训练集上更准，但在测试集上泛化差了）

------

**法→英（绿=Base，黄=Instruct）**

- Epoch 0：BLEU 有个初始值（黄线甚至接近 8）
- Epoch 1 开始：BLEU 直接大幅下降，并且后续几轮一直下滑 ❌ 原因：
  - 训练数据是 **News-Commentary EN→FR**，因此模型接受到的是“英语→法语”映射数据
  - 对 “法语→英语” 没有直接监督训练，反而学到的权重更新损害了原本的法→英能力 → **灾难性遗忘（catastrophic forgetting）**

------

为什么会出现 “有的任务 BLEU 高了，有的低了”

1. **数据方向不匹配**
   - 英→法任务是训练目标 → 权重更新直接优化了它 → BLEU 上升
   - 法→英是非训练方向 → 权重更新不断覆盖原本的参数 → BLEU 下降
2. **过拟合效应**
   - 英→法在 Epoch 3 后开始掉分 → 虽然训练 Loss 会继续下降，但模型在验证集 BLEU 开始下滑
   - 原因是模型开始记住训练数据的细节，而不是学习可泛化的翻译规律
3. **模型容量限制（270M 小模型）**
   - 小模型参数有限，无法同时在两个方向保留高水平性能
   - 在单一方向训练时，会偏向牺牲另一个方向的表现来“腾出容量”
4. **初始 BLEU 高的那条黄线（法→英 Instruct）为什么骤降**
   - 可能原本依赖于广泛的多语言知识（预训练阶段获得）
   - 但微调阶段用大量单方向数据训练，破坏了这种知识平衡 → 灾难性遗忘的典型信号

------

工程意义

- 如果你只在一个翻译方向微调，**要接受另一个方向性能下降的风险**
- 如果想双向都好，需要用双向数据（英→法 + 法→英）联合训练
- BLEU 在训练过程中不仅用于“看涨”，也可以用于**发现性能损失和过拟合拐点**
- 最佳停训点通常在 **验证集 BLEU 峰值出现的 epoch**（这里是第 3 轮）



#### 示例代码

```
pip install unsloth
```

```
from unsloth import FastLanguageModel
import torch, multiprocessing
from datasets import load_dataset
from peft import LoraConfig
from transformers import set_seed, AutoTokenizer,DataCollatorForSeq2Seq

from trl import SFTTrainer, SFTConfig

set_seed(42)

iso_language = dict()
iso_language["en"] = "English"
iso_language["de"] = "German"
iso_language["es"] = "Spanish"
iso_language["fr"] = "French"
iso_language["it"] = "Italian"


def FT(model_name, pair):

    compute_dtype = torch.bfloat16

    bs = 16 #Batch size per device (training and validation), bs = 1 *can* be faster
    gas = 4 #Gradient accumulation steps
    mseqlen = 4096 #Maximum sequence length; reduce if you run out of memory

    lr = 5e-5

    output_dir = "./SFT-OPUS/"

   model, tokenizer = FastLanguageModel.from_pretrained(
      model_name = model_name,
      fix_tokenizer=False,
      max_seq_length = mseqlen,
      dtype = compute_dtype,
      load_in_4bit=False,
      full_finetuning=True
    )


    languages = pair.split("-")
    src_lang = languages[0]
    tgt_lang = languages[1]


    ds = load_dataset("Helsinki-NLP/opus-100", pair, split="train").train_test_split(test_size=0.01)
    ds_train = ds["train"]
    ds_test = ds["test"]
    def process(row):

      source = row['translation'][src_lang]
      target = row['translation'][tgt_lang]

      row["text"] = "<start>You are a professional translator that translates messages from "+iso_language[src_lang]+" to "+iso_language[tgt_lang]+".<user>"+source+"<translator>"+target+tokenizer.eos_token
      return row

    ds_train = ds_train.map(
      process,
      num_proc= 10,
      load_from_cache_file=False,
    )
    print(ds_train[0]['text'])


    ds_test = ds_test.map(
      process,
      num_proc= 10,
      load_from_cache_file=False,
    )
    print(ds_test[0]['text'])



    from unsloth import UnslothTrainer, UnslothTrainingArguments

    training_arguments = UnslothTrainingArguments(
          output_dir=output_dir,
          optim="adamw_8bit",
          per_device_train_batch_size=bs,
          gradient_accumulation_steps=gas,
          log_level="debug",
          save_strategy="steps",
          save_steps=6000,
          logging_steps=25,
          learning_rate = lr,
          bf16 = True,
          num_train_epochs=1,
          warmup_ratio=0.03,
          report_to = "none",
          lr_scheduler_type="linear",
          max_length=mseqlen,
          dataset_text_field='text',
          dataset_num_proc=10,
          #do_eval=True,
          #per_device_eval_batch_size=bs,
          #eval_steps=100,
          #eval_strategy="steps",
    )

    trainer = UnslothTrainer(
      model = model,
      train_dataset=ds_train,
      #eval_dataset=ds_test,
      processing_class=tokenizer,
      args = training_arguments
    )



    trainer_ = trainer.train()

```

```
FT("google/gemma-3-270m", "en-fr")
```



**Refer to:**

*https://kaitchup.substack.com/p/gemma-3-270m-can-tiny-models-learn*


---

# Part 13: 三种 RL 训练方法对比

> *原文来自 LLM-Math-Reasoning-RL*


## 🔄 Chapter 8: Three RL Training Approaches Compared

Beyond the DeepSeekMath-V2 paper's method, there are two mainstream engineering approaches: **Agent Lightning** (local training) and **Azure RFT** (cloud managed).

### 8.1 Full Comparison of Three Approaches

| Dimension | DeepSeekMath-V2 (Paper) | Agent Lightning (Local) | Azure RFT (Cloud) |
|-----------|-------------------------|------------------------|-------------------|
| **Goal** | Mathematical proofs (theorem proving) | Math reasoning (word problems) | General reasoning |
| **Training Algorithm** | GRPO + Verifier RL | GRPO / PPO / DAPO | Managed RFT (undisclosed) |
| **Reward Source** | Trained Verifier + Meta-Verifier | Custom functions (rules+structure) | Graders (rules/models/code) |
| **Self-Verification** | ✅ Model learns to self-evaluate | ❌ External reward only | ❌ External reward only |
| **Inference Iteration** | ✅ ~5000+ calls/problem | ❌ Single generation | ❌ Single generation |
| **Supported Models** | DeepSeek series | Open-source (Qwen, LLaMA) | OpenAI (o4-mini, GPT-5) |
| **Hardware Requirement** | Large-scale cluster | 40GB+ GPU (H100/A100) | No local GPU needed |
| **Open Source** | Paper public, code not released | Fully open source | Managed service |
| **Use Case** | IMO/Putnam competition proofs | Engineering-grade math reasoning | Quick prototyping/OpenAI ecosystem |

### 8.2 Reward Function Design Comparison

All three approaches need to define "what makes a good answer", but implement it differently:

#### DeepSeekMath-V2: Three-Layer Verification Reward

```text
┌─────────────────────────────────────────────────────────────────┐
│                  DeepSeekMath-V2 Reward Architecture             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Generator Output: Proof Y + Self-Evaluation Z                  │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐                                            │
│  │ Verifier πφ     │ ──► R_Y = proof_score (0/0.5/1)           │
│  │ (Trained Judge) │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  ┌─────────────────┐                                            │
│  │ Meta-Verifier πη│ ──► R_meta = is self-eval honest (0/0.5/1)│
│  │ (Audits Judge)  │                                            │
│  └────────┬────────┘                                            │
│           │                                                     │
│           ▼                                                     │
│  R = R_format · (α·R_Y + β·R_Z)    α=0.76, β=0.24              │
│                                                                 │
│  Key: Reward model itself needs training, can evaluate reasoning│
└─────────────────────────────────────────────────────────────────┘
```

#### Agent Lightning: Composite Rule-Based Reward

```python
def compute_reward(response, ground_truth):
    reward = 0.0
    
    # 1) Structure reward: has reasoning chain?
    if "<think>" in response and "</think>" in response:
        reward += 0.5  # correct format
    
    # 2) Correctness reward: final answer
    if extract_answer(response) == ground_truth:
        reward += 2.0  # correct answer
    
    # 3) Depth reward: reasoning sufficiency
    if len(extract_think(response)) > 100:
        reward += 0.5  # reasoning long enough
    
    return reward  # max 3.0

# Key: Simple rules, no trained judge, only checks final answer + format
```

#### Azure RFT: Grader Composition

```python
# Multigrader example: combining multiple scoring methods
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
            "reference": "\\boxed{"
        },
        "quality": {
            "type": "score_model",
            "model": "gpt-4o-2024-08-06",
            "input": [{"role": "user", "content": "Rate this solution..."}]
        }
    },
    "calculate_output": "correctness * 0.6 + format * 0.2 + quality * 0.2"
}

# Key: Flexible composition, supports LLM-as-Judge, managed execution
```

### 8.3 Key Difference: Self-Verification vs External Reward

| Feature | DeepSeekMath-V2 | Agent Lightning / Azure RFT |
|---------|-----------------|----------------------------|
| **Does model know reward function?** | ✅ Yes, learned verification rules during training | ❌ No, only knows reward signal |
| **Can self-improve?** | ✅ Self-evaluates + iteratively fixes at inference | ❌ Cannot self-correct after generation |
| **Inference overhead** | 🔴 Extremely high (~5000 calls/problem) | 🟢 Low (single generation) |
| **Suitable for real-time?** | ❌ Offline competitions | ✅ Online services |

**Core Insight**:

DeepSeekMath-V2's "self-verification" means **teaching the model verification ability during training**, enabling it at inference to:
1. Generate answer AND self-evaluation simultaneously
2. Identify issues based on self-evaluation
3. Iterate until self-evaluation is perfect

Agent Lightning / Azure RFT use **pure external rewards**—the model doesn't know "why this answer is good", only that "this answer got a high score".

### 8.4 Training Complexity Comparison

```text
DeepSeekMath-V2 Training Pipeline (Complex):
─────────────────────────────────────────────────────
Stage 1: Train Verifier (needs human-labeled proof quality)
   │
   ▼
Stage 2: Train Meta-Verifier (prevents Verifier hallucination)
   │
   ▼
Stage 3: Train Generator (using Verifier as Reward Model)
   │
   ▼
Stage 4: Co-evolution (Generator↔Verifier mutually improve)
─────────────────────────────────────────────────────

Agent Lightning Training Pipeline (Simple):
─────────────────────────────────────────────────────
Stage 1: Define reward function (rule code)
   │
   ▼
Stage 2: GRPO training (single stage)
─────────────────────────────────────────────────────

Azure RFT Training Pipeline (Simplest):
─────────────────────────────────────────────────────
Step 1: Prepare JSONL data
Step 2: Define Grader (JSON config)
Step 3: Submit training job (Azure Portal / API)
─────────────────────────────────────────────────────
```




