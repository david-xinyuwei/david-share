# 强化学习（RL）与有监督微调（SFT）的选择以及奖励函数的优化

本文首先将阐述强化学习（RL）和监督微调（SFT）在实现方式上的区别，然后通过一个具体案例，详细说明如何设计SFT和GRPO流水线。

## SFT和RL选择

大多数情况下训练模型先 SFT 再 RL 更安全、更高效，尤其是对能力尚弱的小模型或需要严格格式输出的任务。不过这并不是绝对法则，下面补充几点可作为快速校验的要点。

**一、为什么“先 SFT 后 RL”通常更好**

1. 训练稳定性
   • 直接 RL（尤其是小模型）容易出现 KL 爆冲、梯度爆炸，模型甚至崩盘。
   • SFT 先把策略锚定在“基本正确、格式合规”的空间，再让 RL 微调，KL 跳变小很多，收敛更稳。
2. 数据利用效率
   • SFT 等价于“先喂答案教基础功”；RL 更像“在掌握基础后练举一反三”。
   • 如果一开始就 RL，模型会在大量无意义探索上浪费步数。
3. 人工标注成本
   • SFT 阶段可用少量高质量标注（或合成高质量标注）直接模仿；RL 阶段只用奖励信号即可继续放大效果，二者配合能节省标注量。

**二、直接 RL 的合理场景**

1. 几乎没有标注数据、但可以自动计算奖励
   例如：解数独、玩 Atari 游戏，环境本身给出分数。
2. 大模型已具备强基础能力
   GPT-4、Claude 3-Sonnet 这一级别，格式和基本推理已比较稳，直接 RL（或 RLAIF）效果也可接受。
3. 任务鼓励高多样性、无法提供单一“标准答案”
   如创意写作、对话风格优化，仅用偏好打分即可训练。

**三、实践经验速查表**

| 情况               | 建议策略                            | 备注                    |
| ------------------ | ----------------------------------- | ----------------------- |
| 有一批高质量标注   | 先 SFT，后 RL                       | 主流 RLHF/GRPO Pipeline |
| 只有合成弱标注     | 可尝试短 SFT + RL                   | 先对齐格式再放大能力    |
| 纯交互式/环境奖励  | 直接 RL/在线 RL                     | 如游戏、机器人控制      |
| 预算极低、模型极小 | 先小规模 SFT，再视情况决定是否加 RL | RL 计算开销更大         |

1. 我们的奖励函数是不是完全依赖“答案==标准答案”？
   如果是，说明我们已经有明确标注；SFT 通常先做更划算。
2. 我们有多大 GPU/TPU 预算？
   RL（尤其 GRPO/PPO）往往需要比 SFT 高 2-4 倍的算力。
3. 任务对“推理链”可解释性要求高吗？
   先 SFT（教会标签格式）再 RL（提升正确率）更容易满足可解释输出。

**结论 ：**

“先 SFT 再 RL”并非硬性规定，但在绝大多数需要结构化输出、且有可用标注的场景下是最省心、最稳妥的路径。只有当标注极少或任务天然提供可计算奖励时，才会优先考虑“直接 RL”。

### RL常见问题

前文提到的RL常见的KL爆冲、梯度爆炸、模型崩盘问题，本小节详细介绍。

| 术语     | 问题本质（到底是哪里出了问题）           | 属于哪种概念                                          | 错误的具体表现（学术描述）                                   |
| -------- | ---------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------ |
| KL爆冲   | 模型输出分布变化太剧烈、速度太快         | 输出分布问题 （Distribution-level issue）             | KL散度指标短期内急剧上升（如超过10或更高）；<br>策略模型与参考模型的概率分布差异迅速扩大；<br>导致模型输出质量急剧下降，如明显的文本内容混乱、重复或断句异常； |
| 梯度爆炸 | 训练过程参数更新数值过大、模型变得不稳定 | 训练过程中参数更新的问题 （Training stability issue） | 反向传播过程中梯度范数（Gradient norm）异常剧增（数值巨大甚至趋于无穷或NaN）；<br>训练损失(loss)数值异常增大甚至跳跃至无穷大或NaN；<br>模型权重参数技术层面上更新幅度异常大，导致网络计算存溢出或数值退化； |
| 模型崩盘 | 模型生成的内容变得单一、呆板、无法泛化   | 模型最终表现问题 （Final-generation quality issue）   | 模型生成内容多样性急速降低，信息熵（Entropy）显著减小；<br>输出分布退化到极少的模式（如mode collapse），文本表现为反复生成单一或少数固定答案；<br>在训练集之外的数据上表现能力急剧下降，泛化能力严重受损。 |

一般情况下，这三个问题会组成一条「连锁反应」：

```
奖励函数设计不佳或超参错误
      ↓↓导致↓↓
   KL爆冲 --> 梯度爆炸 --> 模型参数剧烈变化或NaN
      ↓↓进一步导致↓↓
   模型崩盘 (输出单一、低质)
```

**① KL爆冲**

**KL 散度 (Kullback–Leibler Divergence)** 本质上衡量的确实是 **两个概率分布之间的差距**。在 **DPO (Direct Preference Optimization)** 方法中，**参考模型(reference model)** 和 **训练中模型(policy model)** 之间计算的就是 **KL散度**。

**用简单例子解释一下：**

假设默认模型只会讲三句话：“我们好”、“谢谢”、“再见”。

它现在的“说话概率”（也可以叫“原始概率分布”）是：

| 鹦鹉自己的当前概率分布（P分布） | 概率 |
| ------------------------------- | ---- |
| 我们好                          | 0.6  |
| 谢谢                            | 0.3  |
| 再见                            | 0.1  |

我们心目中理想的“模型应该说话的概率分布”（目标概率分布）是：

| 我们想要的目标概率分布（Q分布） | 概率 |
| ------------------------------- | ---- |
| 我们好                          | 0.2  |
| 谢谢                            | 0.7  |
| 再见                            | 0.1  |

我们希望模型朝着**目标概率(Q分布)\**学习，但它原本的习惯是\**当前概率(P分布)**。

这时候，为了知道我们的鹦鹉**目前的概率分布 P** 与 **目标概率分布 Q** 差距有多远。

- KL散度 **越小** = 两个概率 **越接近**。
- KL散度 **越大** = 两个概率分布的差距 **越明显**。
- 

在例子中，如果原来模型会说:“我们好(Hello)”，但我们想教它说:"谢谢(Thank you)"，那么就有了：

- 一个**原始模型**的分布（Original distribution）：擅长说“我们好”；
- 一个**目标模型**的分布（Target distribution）：我们希望它能学会说“谢谢”。

假设我们给了模型过分高的奖励，比如只要提到“谢谢”，我们奖励20分。模型会在几步内学得太猛，突然所有问题只回复：“谢谢谢谢！”这就是KL距离瞬间爆发。



KL爆冲 发生以后，需要用算法调整KL惩罚系数 (β)

```
Loss总 = 奖励损失 + β × KL散度
```

提高β，比如0.01 → 0.1，约束模型变化的幅度。

**② 梯度爆炸**

深度学习中很常见的梯度爆炸问题主要是指：

- 网络在**训练过程中**因为某次更新的**梯度过大**，导致**模型参数突然变化过大**，从而网络可能变得不稳定甚至崩溃。

最常见导致梯度爆炸的情况，很少是简单的代码Bug；事实上更多是**算法超参设置不当或数值计算不稳定**导致的：

- **学习率（LR）过大**：
  如原本建议的学习率是`1e-5`，但使用了过高学习率（如`1e-2`或者更高），一次参数更新迈步过大，造成梯度过大。
- **奖励信号设计不合理（尺度过大）**：
  有时设计奖励信号时，没有进行归一化处理，例如我们奖励的值过大（比如正常奖励是±1，却给了数百甚至上万），导致更新步幅过猛，产生极大的梯度数值。
- **网络结构本身设计或优化器配置不好**：
  比如神经网络某些层的初始化不合理，或梯度累计出现了数值问题，使得运动过程中梯度持续放大。
- **未使用梯度裁剪或裁剪设置值过大**：
  如果训练过程中未用梯度裁剪方法，或梯度裁剪的上限值设置过大（如10以上），一旦梯度猛增就不能约束，即可引发梯度爆炸。

算法表现为梯度值剧烈变大甚至NaN。

**③ 模型崩盘**

模型崩盘的本质含义是：

- 模型的参数被 “过度优化” 到单一或极少数的策略上（也称为Mode Collapse）；
- 策略分布发生严重的退化，模型无法再生成丰富、多样化的内容。

模型崩盘有典型的指标，例如：

- 输出的**熵大幅降低**（Entropy↓），表示语言多样性消失；
- **生成内容变得单一固定**，重复度极高；
- 在训练数据以外的泛化能力和稳健性大幅下降。

算法上，熵的定义是：

```
熵值 = -sum( p(X_i)*log(p(X_i)) )
# 熵越低，表示模型生成的语言越单调单一，越接近崩盘
```

一种典型的模型崩盘的表现是：

- 训练前语言多样性熵值 ≈ 8 到 10；

- 训练后模型崩盘，语言熵值 下降至 1～2 左右。

  

模型崩盘最常见的直接原因是源于强化学习训练过程本身的一系列内在问题（尤其是强化学习），例如：

- **奖励函数过于单一和简单**：导致模型倾向走极端，重复一种行为；
- **长时间训练、KL问题持续未解决**：模型能力持续退化，最终彻底丢失多样性；
- **连续出现梯度爆炸但未干预**：参数持续异常更新，模型能力根本不能正常保留；
- **数据质量较低或过拟合于一种模式**：模型长时间反复学习有限模式，无法泛化。

如果出现上述问题我们还继续训练，鹦鹉最后脑袋就真的弄坏了。比如它彻底只会一招，一问就吐出“苹果苹果”或彻底傻掉不回话，再训练也没用（模型崩溃）。

## TRL中的GRPO

目前GRPO Trainer已经被集成到TRL中：*https://huggingface.co/docs/trl/main/grpo_trainer*

**GRPO中的群组优势**(Group Advantage)"

“群组优势”(group advantage) 只是把 **已有 reward** 做一次“组内中心化／截断”以降低梯度方差；它并不会自己产生 reward。
因此在所有基于策略梯度的方法里，仍必须先有某种“奖励来源”——可以是

1. 规则型（rule-based）
   ‑ 如你脚本中的 `reward_format_exact`、`reward_answer`，直接硬编码 +5/–2/–4。
2. 奖励模型（reward model, RM）
   ‑ 先用人类偏好或比较数据训练一个专门网络，然后用该网络给生成文本打分。
   ‑ 常见于对话偏好强化（ChatGPT、RLHF）或复杂开放任务。
3. 其他外部信号
   ‑ 例如环境分数、用户点击率、游戏得分等。

无论 reward 来源是哪一种，**群组优势只是后处理**：

```
┌─────────┐   ┌────────────┐
生成 N 个候选 → │ Reward  │ → │ group mean │ → Advantage
                 └─────────┘   └────────────┘
```

------

**假设一个场景**：

你给同样一个问题，让你的AI模型连续生成了好几个答案（比如4个候选方案）。
然后你对这4个答案逐个打个分：好的答案分数高，不好的答案分数低。

现在问题来了：如何引导模型变得更聪明呢？很简单：

------

 **GRPO的处理方式（用一个例子解释）**：

- 首先，我们每个回合生成多个答案，这些答案是一个“群组(group)”，也就是"一轮回答"。
- 给所有答案打个分（比如：第一个成绩80，第二个60，第三个90，第四个70）。
- 然后算一下这一组答案的**平均得分**。比如算出来平均价是75分。

 **这个平均分，其实可以简单理解为当前这个模型的“平均水平”，也就是在这个问题/情况里面模型平时能达到的表现，我们称为“基线”或baseline。**

- 接下来就很好理解了：我们每个方案的得分，去和这个“平均水平”比较一下：
  - 第一个答案是80分，平均是75分，说明方案很好，超过平均了。那么，下次就要更多地鼓励模型产生类似于第一个方案的答案（提高概率）。
  - 第二个答案是60分，低于75的平均分，代表比平常差了，下次就要少生产这样的方案，给的概率低一点。
  - 第三个答案90分，那非常好，比均值高很多，下次要显著增加出现类似方案的概率;
  - 第四个70分，比75分平均值差一些，也是会稍微降低一点概率。

用这种方法，每次都生产多个方案后“看一眼周围方案的平均水平”，就知道“自己这次到底是进步了还是退步了”。
而每次都用“进步的还是退步了”来决定下次的升级。



## TRL SFT+GRPO训练qwen模型

在本小节中，我们展示一个例子，先进行SFT，再进行GRPO。

### **SFT 阶段（监督微调）**

• 数据集

- HF Hub：`unsloth/OpenMathReasoning-mini`
- split：`"cot"`（带模型生成的 chain-of-thought）

• 使用的字段

| 列名                 | 示例                        | 用途                             |
| -------------------- | --------------------------- | -------------------------------- |
| `problem`            | “Given √(x²+165) − … = 7 …” | 题干                             |
| `expected_answer`    | `14`                        | 数值答案（必须能 cast 为 float） |
| `generated_solution` | `<think> … </think>`        | 思路文本                         |

其它列（`problem_type`, `pass_rate_72b_tir` 等）在代码中未被引用。

• 构造对话（chat_template）

```
system    : 固定 system_prompt
user      : {problem}
assistant : <start_working_out>{thoughts}<end_working_out>
            <SOLUTION>{expected_answer}</SOLUTION>
```



其中
`thoughts = generated_solution` 去掉包裹的 `<think>…</think>` 标签。

• 生成训练文本

```
tok.apply_chat_template(messages, tokenize=False)
```



得到完整 prompt+answer 作为 LM 监督目标。

• 过滤 / 采样

1. 若 `expected_answer` 不能转成 `float` → 丢弃该行。
2. 若传参 `--sft_sample_frac<1` → 再随机下采样。

• 训练目标
标准因果语言模型 loss；此阶段 **不** 用奖励函数。

### **GRPO 阶段（RL fine-tune）**

• 数据集

- HF Hub：`open-r1/DAPO-Math-17k-Processed`
- configuration `"en"`, split `"train"`

• 使用的字段

| 列名       | 示例（截取）                      | 用途                   |
| ---------- | --------------------------------- | ---------------------- |
| `prompt`   | “In △ABC, sin∠A = 4/5 … 求 a+b+c” | 题干                   |
| `solution` | `34`                              | 真实数值答案（字符串） |

其余列（`data_source`, `ability`, …）均不参与训练。

• 对话模板

```
system : 固定 system_prompt
user   : {prompt}
# assistant 留空，由模型生成
```



调用 `tok.apply_chat_template(..., add_generation_prompt=True)`
→ 模板末尾自动附 `<start_working_out>`，作为模型生成起点。

• 数据过滤

1. 渲染后仅含 prompt 的 token 数 ≤ `max_prompt_length`(≈ seq_len/2) 才保留；
2. 目的是保证再生成 ≤ `max_completion_length` token 时总长不超 context 窗口。

• 保存到 RL 训练集的字段

```
{"prompt": messages_list,   # list[dict]
 "answer": solution.strip()}
```



• 采样参数（SamplingParams）

```
temperature = 0.7
top_p       = 0.9
max_tokens  = 256
stop        = ["</SOLUTION>", tok.eos_token]
num_generations = 4   # 默认，可用 CLI 调整
```

GRPO奖励函数优化：

`reward_format_exact` (格式奖励)

| 对比维度            | 原始版                                 | **渐进式版本**（当前有效）                     |
| ------------------- | -------------------------------------- | ---------------------------------------------- |
| 初始得分基线        | -2                                     | **0**（更温和，有效鼓励模型输出标签）          |
| 标签存在奖励        | 每标签 +1 (但基于 -2 基线，很容易负分) | 每标签 +1 (**基于 0 起步，更易正分；最多+4**)  |
| 缺标签惩罚          | 起始即 -2，下限较低                    | 无额外惩罚（仅不给分，不再额外惩罚）           |
| `reasoning`长度要求 | 至少 10 个词，否则 -1                  | **至少 6 个词** (要求较低，早期更易满足)       |
| 得分范围裁剪        | 无显式裁剪                             | 限制在 [-2, +4] (避免极端偏离)                 |
| 典型分布            | -2 ~ 0，持续负分                       | **+1 ~ +2 稳定正分**                           |
| 设计目的            | 严格惩罚缺失标签，几乎无正反馈         | **快速鼓励标签格式，加强正激励，稳定梯度信号** |

`reward_answer` (数值答案奖励)

| 对比维度                   | 原始版                                 | **渐进式版本**（当前有效）                           |
| -------------------------- | -------------------------------------- | ---------------------------------------------------- |
| 无法匹配`<SOLUTION>`标签块 | -4                                     | **-1** (惩罚柔和，更易纠正)                          |
| 提取数字失败 (无法解析)    | -2                                     | **-1**                                               |
| 数字解析成功 & 完全正确    | +8                                     | **+8**（未改动）                                     |
| 数字解析成功 & 近似正确    | 无（只有完全正确才有奖励）             | **+4** (新增奖励项：误差<1% 或 <1e-2 即可得分)       |
| 数字解析成功 & 不够准确    | -2 (严厉惩罚)                          | **0** (不给奖但也不罚，用于推进模型收敛)             |
| 奖励值典型分布             | 离散 {-4, -2, +8} 且极其稀疏，多数为负 | **密集，并具备明确路径** {-1, 0, +4, +8}             |
| 设计目的                   | 一刀切，难以提供有效梯度               | **提供多等级奖励**：先鼓励解析数字，再逐渐逼近准确值 |

| 训练阶段        | 原始版本效果                             | **渐进式版本**（当前有效）效果                               |
| --------------- | ---------------------------------------- | ------------------------------------------------------------ |
| 早期(0~200步)   | 总reward≈ -5，几乎无正奖励，难以有效训练 | **总reward约0.3~1.0，明显正奖励，更易于策略梯度推进**        |
| 中期(200~800步) | 标签可能学到，但总体仍是负奖励居多       | **开始得到“近似答案”奖励(+4)，总reward稳步提高**             |
| 后期(>1000步)   | 少数样本+8，多数仍负，总reward低迷不前   | **reward_answer稳居0或正值区域，总reward轻易突破2+，稳步提高** |

## 代码展示

### 环境准备

```
# 1. 创建新的虚拟环境
python3 -m venv grpo-env

# 2. 激活虚拟环境
source grpo-env/bin/activate

# 3. 升级pip并安装环境依赖(从导出的requirements.txt)
pip install --upgrade pip
pip install -r requirements.txt


```

运行代码

```
# 纯 GRPO
python qwen3_grpo_train3.py --grpo_steps 10 --print_every 1 --debug_every 1

# 轻量 SFT(10%) + GRPO
python qwen3_grpo_train3.py --do_sft --sft_epochs 1 --sft_sample_frac 0.1 \
       --grpo_steps 10 --print_every 1 --debug_every 1
       
# SFT(100%) + GRPO
python qwen3_grpo_train3.py --do_sft --sft_epochs 1  \
       --grpo_steps 10 --print_every 1 --debug_every 1
```

训练中资源利用率：

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

主代码：

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

执行代码：

```
python qwen3_grpo_train3.py --do_sft --sft_epochs 2 --sft_sample_frac 0.3        --grpo_steps 1500 --print_every 1 --debug_every 1
```

### 输出日志

**SFT部分：**

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

SFT日志分析：

起点 ≈ 5.05 → 终点 ≈ 4.03
• 单位：token-level cross-entropy（对数损失）。
• 换算 perplexity：exp(5.05)=156 → exp(4.03)=56，下降约 64 %。
• 对于只训练 280 步、数据量 2.2 k、且 LoRA 只动 0.8 % 参数的场景，这属于“正常下降”。

**GRPO部分**

我们针对一个prompt模型生成了四个答案，然后进行群组优势打分。

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

推理验证：

推理脚本

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

推理验证

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

答案回答正确，而且有solution tag。

##### **备注：训练结果指标解读**

 SFTTrainer 日志里出现字段：

| 字段                     | 含义                                     | 典型范围          | 计算方式                        |
| ------------------------ | ---------------------------------------- | ----------------- | ------------------------------- |
| loss                     | teacher-forcing 交叉熵平均值（越低越好） | 0.7 → 0.3         | `CrossEntropy(outputs, labels)` |
| mean_token_accuracy      | token 级 top-1 准确率                    | 0.65 → 0.80       | `1 - ppl` 近似值                |
| num_tokens               | 当前 step 处理的 token 数                | batch×seq_len     | 统计 tokenizer 输入长度         |
| train_runtime            | 整个 epoch 耗时 (最终行)                 | 280-300 s         | end_time - start_time           |
| train_samples_per_second | 每秒处理样本数                           | ≈(batch/step)/sec | HF Trainer 统计                 |
| train_steps_per_second   | 每秒更新步数                             | ≈1 / step_latency | HF Trainer 统计                 |
| train_loss               | 全 epoch 的 loss 平均值（最终行）        | 0.85              | 所有 step loss 加权平均         |

SFT、GRPO 通用字段

| 字段          | 含义                           |
| ------------- | ------------------------------ |
| epoch         | 当前步对应的 epoch 比例        |
| loss          | SFT：交叉熵；GRPO：KL − reward |
| grad_norm     | 当前梯度 L2 范数，过大可能爆炸 |
| learning_rate | 每 step 动态学习率             |
| num_tokens    | step 内处理 token 数           |
| logging_steps | n 步打印一次，决定日志行粒度   |

GRPOTrainer 特有字段

| 字段名 (日志 key)             | 含义                                           | 判读规则   |
| ----------------------------- | ---------------------------------------------- | ---------- |
| **rewards/cor_reward/mean**   | 数字奖励均值（+2 完全正确；+1 仅差 1；0 其余） | ↑ 越高越好 |
| **rewards/fmt_reward/mean**   | XML 格式奖励均值（满足模板得 +1）              | ↑ 越高越好 |
| **reward**                    | cor + fmt 的批均值 ∈ [0, 3]                    | ↑ 越高越好 |
| **reward_std**                | 批内 reward 的标准差                           | 中等即可   |
| **frac_reward_zero_std**      | reward＝0 的样本比例                           | ↓ 越低越好 |
| **kl**                        | 策略与底座模型的 KL 散度                       | 中等最好   |
| **loss**                      | β·KL – reward（GRPO 目标）                     | 趋势即可   |
| **grad_norm**                 | 当前梯度 L2 范数                               | ↓ 避免爆   |
| **completions/mean_length**   | 8 条回答平均 token 长度                        | 监控长度   |
| **completions/clipped_ratio** | 回答被 `max_completion_length` 截断的比例      | ↓ 越低越好 |
| **epoch**                     | 已训练进度 (0-1 = 0-100 %)                     | —          |





