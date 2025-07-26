# Choosing Between Reinforcement Learning (RL) and Supervised Fine-Tuning (SFT) & Reward-Function Optimisation

This document first explains the implementation-level differences between RL and SFT, then walks through a concrete example that shows how to build an SFT-plus-GRPO pipeline.

## **强化学习三种模式**

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Selection-SFT-RL/images/1.png)

上面这三种强化学习训练大模型做推理的模式，可以简单理解为“最终只看答案给奖励”到“分步骤给奖励”的逐步演进。它们的主要区别如下：

#### 直接强化学习 (Direct RL)

• 核心思路：
模型只输出一个答案，奖励模型(Reward Model)仅根据这最终答案是否正确或符合目标来给出奖励。
• 特点：
– 只在最后一步得到奖励信号。
– 实现最简单，但无法直接指导模型中间的推理步骤对不对。
– 如果中途思路错了，模型只能在最终答案“被扣分”时才知道哪里出了问题，学习速度慢。

#### 多步强化学习 + 最终结果奖励 (Multi-Step RL with Outcome Reward Model, ORM)


• 核心思路：
模型在输出答案前，会先“显式地”或“隐式地”写下一系列中间推理步骤(Reasoning steps)，最后依然只看最终答案来给奖励。
• 特点：
– 明确地将思考过程拆分为多步，但奖励依旧只看最后结果。
– 相比直接RL，模型在训练时可以学会更有条理的分步思考，但依旧无法从每一步是否正确获得即时反馈。
– 如果中间步骤错误，但最终答案凑巧对了或者错了，模型依旧只能在最终才能得到一次奖惩信号。

#### 多步强化学习 + 过程奖励 (Multi-Step RL with Process Reward Model, PRM)


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





## Test Time Scale模式

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Selection-SFT-RL/images/2.png)
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

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Selection-SFT-RL/images/3.png)

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUicwxWRiaeB4ibaXAtuEMND1S8qSAklGF6vibbmueCyglkicVpfm73CgP8fst0sjk7uGZefPcMGg4rRAg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1)

![Image](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/Selection-SFT-RL/images/4.png)

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

