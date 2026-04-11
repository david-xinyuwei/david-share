# KV Cache 深度解析：从原理到实战

> **A Deep Dive into KV Cache: From Fundamentals to Production Sizing**

[English Version](README.md)

---

## Executive Summary

KV Cache 是 LLM 推理（Inference）中**最关键的内存消耗来源**。理解 KV Cache 的原理和计算方法，是做好 LLM 部署、GPU 选型、VRAM 估算的基础。

本文由浅入深分为 6 个层级：

| 层级 | 主题 | 你将学到 |
|:---:|------|---------|
| **L0** | 零基础入门 | 不需要任何前置知识，用一个例子从头到尾走通 LLM 推理全过程和 KV Cache |
| **L1** | KV Cache 是什么 | 从 Attention 机制推导出 KV Cache 的诞生原因 |
| **L2** | KV Cache 有多大 | 通用公式推导 + 实际模型数值计算 |
| **L3** | 四种减少 KV Cache 的架构 | GQA → Hybrid Attention → MLA → Hybrid Mamba |
| **L4** | 量化对 KV Cache 的影响 | Weight 量化释放空间、KV Cache 量化、敏感层分析 |
| **L5** | 生产部署 VRAM 估算 | 实测验证 + GPU 选型决策树 |

**核心结论（四模型 KV Cache 对比，32K tokens, BF16, batch=1）**：

| Model | Architecture | Attention Layers | KV Cache | vs Baseline |
|-------|-------------|:---:|:---:|:---:|
| Qwen3-30B-A3B | Standard GQA | 48/48 (100%) | **3.00 GiB** | baseline |
| GLM-4.7-Flash | Compressed MLA | 47/47 (100%) | **1.65 GiB** | −45% |
| Qwen3.5-35B-A3B | Hybrid Attention | 10/40 (25%) | **0.625 GiB** | −79% |
| Nemotron-3-Nano-30B | Hybrid Mamba+Attn | 6/52 (12%) | **0.19 GiB** | −94% |

> 数据来源：HuggingFace config.json 参数 + Python 脚本计算。验证脚本见 [scripts/kv_cache_calculator.py](scripts/kv_cache_calculator.py)。

---

## L0: 零基础入门——用一个例子走通全过程

> 如果你已经了解 Transformer 的基本原理，可以跳过本章直接看 L1。

### LLM 整个推理过程就干了一件事：给定前面的字，猜下一个字

```
输入: "今天天气"
模型猜: "真" (概率最高)
输入变成: "今天天气真"
模型猜: "好" (概率最高)
输入变成: "今天天气真好"
模型猜: "！" (概率最高)
```

就是一个字一个字蹦出来的。每次只猜一个。那怎么猜？靠下面 6 步。

### Step 1: 把字变成编号

模型不认字，只认数字。这一步叫**分词（Tokenize）**。

```
"今天天气" → [3920, 8514, 8514, 6720]
```

就像一本字典："今"排在第 3920 页，"天"排在第 8514 页。这一步纯查字典，没有任何"智能"，在 CPU 上完成。

### Step 2: 把编号变成一长串特征数字

模型有一张大表（**Embedding 表**），15 万行，每行 4096 个数字。用编号当行号，取对应行：

```
第 3920 行 → [0.12, -0.34, 0.56, ..., 0.23]   ← 4096 个数字，代表"今"
第 8514 行 → [0.45, 0.23, -0.11, ..., -0.05]   ← 代表"天"
```

> **向量**就是一组有序的数字。4096 个数字排成一列 = 一个 4096 维向量。

**为什么要这一步？** 编号 3920 和 8514 之间没有数学关系。但这 4096 个数字是训练出来的——语义相近的字（如"好"和"棒"）的向量会很接近，不相关的字会很远。把编号变成有含义的数字，后面才能做运算。

### Step 3: 把每个字的向量拆成三份——分别用于"找人"和"传话"

接下来要让每个字去看看前面的字，从中获取上下文信息。这件事分成三个角色：

1. **Q（提问者）**："我要找什么样的字？"——当前字发出查询
2. **K（应答者）**："我是什么字，我的特征是什么"——每个历史字亮出身份标签，等着被 Q 匹配
3. **V（传话者）**："如果我被选中了，我传什么内容"——被匹配上的字传递实际语义

所以把同一个 4096 维向量，用三个不同的**权重矩阵**（"压缩器"），压缩成三份不同的 128 维向量：

```
"气" 的 4096 个数字
    ├── × 压缩器A (W_Q矩阵) → Q = [128个数字]  ← "我要找什么样的字"（提问）
    ├── × 压缩器B (W_K矩阵) → K = [128个数字]  ← "我是什么字"（亮身份，等被匹配）
    └── × 压缩器C (W_V矩阵) → V = [128个数字]  ← "被选中后，我传什么内容"（传话）
```

> **权重矩阵**就是一张数字表格（如 4096 行 × 128 列），里面的数字是训练时自动学出来的。"压缩"的过程就是矩阵乘法——4096 个数字按这张表格的配方做加权求和，变成 128 个数字。三个压缩器配方不同，所以压缩出来的结果不同。

**这一步叫线性投影（Linear Projection）。**

### Step 4: Q 提问、K 应答、V 传话——这就是 Attention（注意力）

模型在猜"今天天气"后面的字，需要让"气"去看前面所有字，搞清楚上下文。

**第一步：Q 提问、K 应答 → 打分（Score）**

"气"拿自己的 Q（提问："我前面是什么？"），去和每个字亮出的 K（身份标签）做比较。比较方式是**点积**（两组 128 个数字对应位相乘再加一起，得一个分数）。Q 和 K 越匹配，分数越高：

```
"气"的Q × "今"的K = 0.3  ← Q 问的和"今"的 K 不太匹配
"气"的Q × "天"的K = 0.8  ← 很匹配（天气是一个词）
"气"的Q × "天"的K = 0.7  ← 也匹配
"气"的Q × "气"的K = 0.5  ← 一般
```

**第二步：归一化（Softmax）**

把分数变成百分比（加起来 = 100%），同时放大差距——大的更大、小的更小：

```
[0.3, 0.8, 0.7, 0.5] → [10%, 35%, 30%, 25%]
```

**第三步：按概率从 V 中取内容（加权传话）**

用百分比混合每个字的 V（**V 是被选中后实际传递的内容，和用来匹配的 K 不同**）：

```
输出 = 10% × "今"的V + 35% × "天"的V + 30% × "天"的V + 25% × "气"的V
```

**"气"现在拿到了融合了上下文的新向量**——主要包含"天"的信息（35%+30%=65%），因为"天气"是一个整体。

### Step 5: 独立消化——FFN（前馈神经网络）

Attention 是字与字之间的**交流**。FFN 是每个字**独立消化吸收**刚收到的信息：

```
交流后的向量 → × 矩阵₁ → 激活函数（引入非线性：如负数变0，让模型能学复杂关系）→ × 矩阵₂ → 输出
```

> 为什么需要激活函数？如果只有矩阵乘法（线性运算），不管叠多少层都等价于一层。加了激活函数，模型才能学到弯曲的、复杂的关系。

**一层 = Attention（交流）+ FFN（消化）。** 一共叠 36 层，信息被反复"交流→消化"，理解越来越深：

```
第 0 层: 理解字面意思（"天"+"气"="天气"）
第 15 层: 理解语境（在讨论天气状况）
第 35 层: 综合判断（下一个字应该是"真/不/很"之类的）
```

### Step 6: 猜字——LM Head（语言模型头）

36 层过完后，最后一个字"气"的向量已经融合了全句的理解。做最后一次矩阵乘法：

```
4096 个数字 × 矩阵(4096×150000) = 150000 个数字
                                      ↓
                     每个数字对应词汇表中一个字的概率
                          取最高的 → "真"
```

输出"真"。

### KV Cache 在这个例子中的作用

猜完"真"后，要继续猜下一个字。输入变成"今天天气真"，需要重新跑 Step 4。

**问题**：Step 4 打分需要每个历史字的 K，传话需要每个历史字的 V。如果不缓存，每猜一个字都要把"今""天""天""气""真"的 K 和 V 全部重新算——**重复劳动**。

**KV Cache 就是把算过的 K 和 V 存起来**：

```
猜"真"时:   算了 今K 天K 天K 气K      → 存进 Cache
猜"好"时:   Cache 已有历史 K，只新算 真K → 追加到 Cache
猜"！"时:   Cache 已有历史 K，只新算 好K → 追加到 Cache
```

| | 不缓存 | 有 KV Cache |
|---|---|---|
| 每猜一个字要算几个 K/V | **所有字都重新算** | **只算 1 个新字** |
| 速度 | 越来越慢（字越多算越多） | 恒定快（每次只算 1 个） |
| 代价 | 无 | Cache 越来越大，**占 GPU 显存** |

**这就是 KV Cache 的全部：存起来不重复算，用显存换速度。**

---

## L1: KV Cache 到底是什么？

### 1.1 从一句话的完整处理过程说起

以 "今天天气" 为例（与 L0 相同的例子，这里加入技术细节），模型处理这句话经历以下步骤：

**Step 1: 分词（Tokenize）** — 纯文本操作，不涉及向量

Tokenizer 把字符串切成子串，然后查**词表**（纯文本→整数的映射字典）转成整数 ID：

```
"今"   → 3920
"天"   → 8514
"天"   → 8514
"气"   → 6720
```

词表就是一个字典 `{"今": 3920, "天": 8514, ...}`，没有向量、没有浮点数。这一步在 CPU 上完成。

**Step 2: Embedding 查表** — 整数 → 浮点向量

模型的**第一层权重**是一张 Embedding 表（shape: `[词表大小 × hidden_size]`，如 `[152064 × 4096]`）。用 token ID 当行号，取对应那一行：

```
3920  → x₁ = [0.12, -0.34, 0.56, 0.78, ...]   ← 4096 个浮点数，代表"今"
8514  → x₂ = [0.45, 0.23, -0.11, 0.67, ...]   ← 代表"天"
6720  → x₄ = [0.33, 0.17, -0.08, 0.51, ...]   ← 代表"气"
```

> **为什么需要这一步？** 整数 ID 不能做数学运算（8856 - 8831 = 25 没有语义含义），但浮点向量可以做点积、矩阵乘法、比较相似度。Embedding 表就是"整数→向量"的桥梁。

Embedding 表本身是模型权重的一部分，在训练中学习到的。数学上等价于 one-hot 向量乘以矩阵（实际实现用直接查行，更快）。

**Step 3: 线性投影（Linear Projection）** — 产生 Q、K、V

> **什么是线性投影？** 就是矩阵乘法。把一个 4096 维的向量乘以一个 4096×128 的矩阵，变成 128 维的向量。"线性"是因为只有乘法和加法，没有弯曲（非线性函数）。"投影"是因为从高维空间（4096）投射到低维空间（128），类似于从 3D 物体投影出 2D 影子——保留了部分信息，丢弃了其他。

每一层有三个**训练好的权重矩阵** W_Q、W_K、W_V（模型参数的一部分，推理时固定不变）。每个 token 的 embedding 分别乘以这三个矩阵：

$$Q_t = x_t W_Q, \quad K_t = x_t W_K, \quad V_t = x_t W_V$$

同一个 embedding x_t，过三个不同的矩阵，得到三组不同的数字。三个矩阵就像三套不同的"滤镜"——对同一张照片（embedding）用不同滤镜拍，得到三张侧重不同特征的照片（Q、K、V）。

**Step 4: Attention（注意力）计算** — Q 和 K 配对打分，然后用 V 传内容

> **什么是 Attention？** 字面意思就是"注意力"——让模型决定生成当前 token 时，应该**关注**前面哪些 token。计算分三小步：
>
> 1. **打分**：用当前 token 的 Q 和每个历史 token 的 K 做**点积**（两组数字对应位置相乘再相加，得到一个分数）。分数越高 = 越相关。
> 2. **归一化（Softmax）**：把所有分数转成概率（加起来 = 1）。Softmax 做的就是 $e^{x_i} / \sum e^{x_j}$——让大的分数变更大，小的变更小，然后归一化。效果类似于"放大差距后投票"。
> 3. **加权求和**：用归一化后的概率对所有历史 token 的 V 做加权平均。概率高的 token 贡献多，低的贡献少。最终输出 = 融合了上下文信息的新向量。

$$\text{score}_{t,j} = \frac{Q_t \cdot K_j^\top}{\sqrt{d_k}} \quad \text{（除以} \sqrt{d_k} \text{防止点积数值太大导致 softmax 梯度消失）}$$

$$\text{output}_t = \sum_j \text{softmax}(\text{score}_{t,:})_j \cdot V_j$$

**Step 5: FFN（Feed-Forward Network，前馈神经网络）+ 下一层**

> **什么是 FFN？** 就是两次矩阵乘法夹一个激活函数。Attention 的输出经过 FFN 做一次"深加工"：
>
> ```
> Attention 输出 (128维) → × 矩阵₁ → 激活函数(SiLU) → × 矩阵₂ → FFN 输出 (4096维)
> ```
>
> **激活函数**（如 SiLU/ReLU）是一个简单的非线性变换——比如 ReLU 就是"负数变 0，正数不变"。加了它模型才能学到弯曲的、复杂的关系，否则多少层矩阵乘法叠起来都等价于一层（线性叠加还是线性）。
>
> FFN 可以理解为每个 token 的"独立思考"——Attention 是 token 之间交流信息，FFN 是每个 token 独立消化吸收这些信息。

每一层 = Attention + FFN。36 层叠起来，信息被反复"交流→消化→交流→消化"，越来越深入理解。

**Step 6: LM Head（语言模型头）— 预测下一个 token**

> **什么是 LM Head？** 就是最后一个矩阵乘法。把 36 层处理完的 4096 维向量映射到词表大小（如 15 万维），每一维对应词表中一个 token 的概率分。取概率最高的那个 token 就是模型的预测结果。
>
> ```
> 第 36 层输出 (4096维) → × W_head (4096×152064) → logits (152064维)
>                                                      ↓
>                                          取 argmax → token ID → 查词表 → "，"
> ```

**完整流程图（Step 1 → Step 6）：**

```mermaid
graph TD
    subgraph STEP1["Step 1: 分词 Tokenize (CPU)"]
        INPUT["用户输入<br/>今天天气"] --> TOK["Tokenizer 切分+查词表<br/>今→3920, 天→8514<br/>天→8514, 气→6720"]
    end

    subgraph STEP2["Step 2: Embedding 查表 (GPU)"]
        TOK --> EMB["用 token ID 当行号<br/>取 Embedding 权重表对应行<br/>→ 每个 token 得到 4096 维浮点向量"]
    end

    subgraph STEP3["Step 3: 线性投影 Linear Projection"]
        EMB --> WQ["x × W_Q 矩阵"]
        EMB --> WK["x × W_K 矩阵"]
        EMB --> WV["x × W_V 矩阵"]
        WQ --> Q["Q 查询向量 (128维)"]
        WK --> K["K 身份向量 (128维)"]
        WV --> V["V 内容向量 (128维)"]
    end

    subgraph CACHE_ZONE["KV Cache — HBM 显存中持久存储"]
        KC["K₁ K₂ K₃ ... Kₜ<br/>V₁ V₂ V₃ ... Vₜ<br/>每生成一个 token 追加一组<br/>只增不减, 直到对话结束"]
    end

    subgraph STEP4["Step 4: Attention (注意力计算)"]
        SCORE["Score = Q × Kᵀ / √d<br/>Q和每个历史K做点积<br/>得分数表(临时,用完就扔)"]
        SOFT["Softmax 归一化成概率"]
        OUT["Output = Weight × V<br/>用概率加权所有历史V"]
        SCORE --> SOFT --> OUT
    end

    subgraph STEP5["Step 5: FFN (前馈神经网络) + 重复"]
        FFN["FFN: 两次矩阵乘法+激活函数<br/>128维 → 4096维"]
        NEXT["输出作为下一层输入<br/>重复 36 层"]
    end

    subgraph STEP6["Step 6: 预测下一个 token"]
        PREDICT["LM Head (语言模型头)<br/>4096维 → 15万维(词表大小)<br/>取概率最高的 = 下一个 token"]
        LOOP["生成的 token 回到 Step 2<br/>继续生成下一个 (Decode 循环)"]
    end

    K -->|"存入"| KC
    V -->|"存入"| KC
    Q --> SCORE
    KC -->|"读取所有历史 K"| SCORE
    KC -->|"读取所有历史 V"| OUT
    OUT --> FFN --> NEXT
    NEXT --> PREDICT --> LOOP
    LOOP -.->|"Decode 循环"| EMB

    style STEP1 fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    style STEP2 fill:#E8EAF6,stroke:#283593,stroke-width:2px
    style STEP3 fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    style CACHE_ZONE fill:#C8E6C9,stroke:#1B5E20,stroke-width:3px
    style STEP4 fill:#FFF3E0,stroke:#E65100,stroke-width:2px
    style STEP5 fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    style STEP6 fill:#FCE4EC,stroke:#C62828,stroke-width:2px
    style KC fill:#4CAF50,color:#fff
    style SCORE fill:#FF9800,color:#fff
    style Q fill:#FFE082
    style K fill:#A5D6A7
    style V fill:#A5D6A7
```
    style STEP4 fill:#FFF3E0,stroke:#E65100
    style STEP5 fill:#F3E5F5,stroke:#7B1FA2
    style KC fill:#4CAF50,color:#fff
    style SCORE fill:#FF9800,color:#fff
```

### 1.2 权重矩阵里有什么？

Q、K、V 三个权重矩阵里**就是一堆训练出来的浮点数**。以下是从真实 Qwen3-0.6B 模型文件中读取的实际数字：

```
W_Q (q_proj.weight) [2048 × 1024] = 2,097,152 个数字:
  [+0.0034, -0.0035, -0.0127, +0.0204, +0.0143, ...]
  [-0.0244, +0.0081, +0.0006, +0.0209, +0.0007, ...]
  ...

W_K (k_proj.weight) [1024 × 1024] = 1,048,576 个数字:
  [-0.0166, -0.0762, -0.0302, +0.0334, +0.0571, ...]
  [+0.0226, -0.0537, -0.0520, +0.0645, +0.0182, ...]
  ...

W_V (v_proj.weight) [1024 × 1024] = 1,048,576 个数字:
  [+0.0121, -0.0033, +0.0005, -0.0051, -0.0552, ...]
  [+0.0105, -0.0015, -0.0024, -0.0001, +0.0131, ...]
  ...
```

**三个矩阵的结构完全一样**（都是浮点数表格），**区别来自训练过程**——它们在 Attention 计算图中的位置不同，导致训练时梯度不同，最终收敛到不同的数字：

- W_Q 的产物在 QKᵀ 的**左边** → 训练时梯度迫使它学会提取"查找需求"
- W_K 的产物在 QKᵀ 的**右边** → 梯度迫使它学会提取"身份特征"
- W_V 的产物在 weight × V 的**右边** → 梯度迫使它学会提取"需要传递的语义内容"

矩阵乘法（x × W_K）的本质是**对 embedding 各维度做加权求和**——W_K 每一行的数字决定了"从 4096 维 embedding 中，哪些维度放大、哪些维度忽略、怎么混合成 128 维的 K 向量"。三个矩阵就是三套不同的"混合配比"。

> **V 不是 Embedding 的原始内容**。V 是 Embedding 经过 W_V 加工后的版本——W_V 决定了"从 Embedding 中提取什么信息来传递"。如果不同层的 W_V 不同（事实如此），每层 Attention 可以选择性传递不同方面的信息。

### 1.3 KV Cache 到底缓存了什么？

**KV Cache 缓存的是每层每个历史 token 的 K 向量和 V 向量**——即 x_t × W_K 和 x_t × W_V 的乘积结果。

**不是** Attention Score（QKᵀ），**不是** Attention Weight（softmax 后的概率），**不是**原始 Embedding x_t。

```
KV Cache 存的东西:
Layer 0:  { K: [K₁, K₂, ..., Kₜ],  V: [V₁, V₂, ..., Vₜ] }
Layer 1:  { K: [K₁, K₂, ..., Kₜ],  V: [V₁, V₂, ..., Vₜ] }
...
Layer 35: { K: [K₁, K₂, ..., Kₜ],  V: [V₁, V₂, ..., Vₜ] }
```

每个 K_i 和 V_i 是一个 `[num_kv_heads × head_dim]` 的浮点向量。

**缓存 K 和 V 而不缓存 Q 和 Score 的原因：**

| 东西 | 能缓存吗？ | 原因 |
|------|:---------:|------|
| **K** | ✅ | K_j = x_j × W_K，x_j 和 W_K 都不随后续 token 变化，一旦算出就固定 |
| **V** | ✅ | 同上，V_j = x_j × W_V 也是固定的 |
| **Q** | ❌ | Q_t 属于当前 token，每步都是新的，没法复用 |
| **Score** | ❌ | Score = Q × Kᵀ，Q 每步都变 → Score 必须每步重算 |

### 1.4 Prefill 和 Decode 两个阶段

推理分为两个阶段：

| 阶段 | 发生什么 | KV Cache 变化 |
|:---:|--------|-----------|
| **Prefill** | 用户输入的 prompt 一次性并行处理 | Cache 填入所有 prompt token 的 K、V |
| **Decode** | 逐个生成新 token | 每步追加 1 组新的 K、V |

以 "今天天气" 为例：

```
Prefill: 4个token并行处理 → Cache = [K₁...K₄, V₁...V₄]
Decode Step 1: 生成 "真"  → 只算 K₅V₅，追加到 Cache
Decode Step 2: 生成 "好"  → 只算 K₆V₆，追加到 Cache
Decode Step 3: 生成 "！"  → 只算 K₇V₇，追加到 Cache
```

**Decode 阶段每一步只需要算 1 个 token 的 K、V。** 前面所有历史 token 的 K、V 直接从 Cache 取。这就是 KV Cache 节省算力的核心机制。

### 1.5 KV Cache 的代价：GPU 显存

| | 无 Cache | 有 KV Cache |
|---|:---:|:---:|
| 每步 K,V 计算量 | $O(t)$ | $O(1)$ |
| 总计算量（T 步） | $O(T^2)$ | $O(T)$ |
| 额外内存 | 0 | $O(T)$ — Cache 随序列增长 |

**KV Cache = 用线性内存换掉二次计算。** Cache 只增不减（直到对话结束），每生成一个 token 就追加一组 K、V。这就是为什么长上下文推理需要大量 GPU 显存。

> **一句话总结**：KV Cache 存的是每层每个历史 token 的 Key 和 Value 投影向量（x_t × W_K 和 x_t × W_V 的乘积结果）。它们在 Attention 计算之前通过线性投影产生，一旦算出就不再变化，因此可以缓存给后续 token 复用。

---

## L2: KV Cache 有多大？

### 2.1 通用公式推导

对于一个标准的 Transformer 模型，KV Cache 的大小取决于：

| 符号 | 含义 | 示例（Qwen3-8B） |
|------|------|:---------:|
| $L$ | 层数（num_hidden_layers） | 36 |
| $H_{kv}$ | KV Head 数量（num_key_value_heads） | 8 |
| $D$ | Head 维度（head_dim） | 128 |
| $T$ | 序列长度（context length） | 32,768 |
| $B$ | 批大小（concurrent sequences） | 1 |
| $b$ | 每个元素的字节数（BF16=2, FP8=1） | 2 |

每一层每个 token 需要存储：
- **K** 向量：$H_{kv} \times D$ 个元素
- **V** 向量：$H_{kv} \times D$ 个元素
- 合计：$2 \times H_{kv} \times D$ 个元素

$$\boxed{\text{KV Cache (bytes)} = L \times 2 \times H_{kv} \times D \times T \times B \times b}$$

### 2.2 实际计算：Qwen3-8B

```
KV per token = 36 × 2 × 8 × 128 × 2 = 147,456 bytes ≈ 144 KiB/token

Context 1K   → 144 KiB × 1,024   = 144 MiB
Context 32K  → 144 KiB × 32,768  = 4.5 GiB
Context 128K → 144 KiB × 131,072 = 18.0 GiB
```

**注意**：Qwen3-8B 的模型权重（BF16）约 16.4 GB。也就是说：

| Context Length | Model Weights | KV Cache | Total VRAM | 占比 |
|:-:|:-:|:-:|:-:|:-:|
| 1K | 16.4 GB | 0.14 GiB | ~16.6 GB | KV 占 ~1% |
| 32K | 16.4 GB | 4.5 GiB | ~21 GB | KV 占 ~22% |
| 128K | 16.4 GB | 18.0 GiB | ~35 GB | KV 占 **52%** |

> **关键洞察**：在长上下文场景中，KV Cache 占用的显存**超过模型权重本身**。KV Cache 才是真正的 "VRAM Killer"。

### 2.3 KV Cache 随 Context Length 线性增长

$$\text{KV Cache} \propto T$$

上下文翻倍 → KV Cache 翻倍。这是一个**线性关系**，没有优化空间（在标准架构下）。

### 2.4 MHA vs MQA vs GQA

全称：
- **MHA**（Multi-Head Attention）：K、V head 数 = Q head 数（如 LLaMA-1）
- **MQA**（Multi-Query Attention）：所有 Q head 共享 1 组 K、V（如 Falcon）
- **GQA**（Grouped-Query Attention）：每 $g$ 个 Q head 共享 1 组 K、V（如 LLaMA-3、Qwen3）

| 类型 | $H_{kv}$ | KV Cache 比 MHA | 质量 |
|------|:-------:|:---:|:---:|
| MHA | = $H_q$（如 32） | 1× | 最好 |
| GQA | $H_q / g$（如 8） | $1/g$（如 1/4） | 接近 MHA |
| MQA | 1 | $1/H_q$（如 1/32） | 略有下降 |

GQA 是当前的**主流选择**：在几乎不损失质量的前提下，将 KV Cache 压缩到 MHA 的 $1/g$。

---

## L3: 四种减少 KV Cache 的架构

当前最先进的 ~30B 参数 MoE 模型采用了四种不同的策略来减少 KV Cache。以下逐一分析。

### 3.1 Standard GQA — Qwen3-30B-A3B

**最经典的方案**：所有层都使用 GQA，每层都有完整的 KV Cache。

```
Qwen3-30B-A3B (HuggingFace config):
  num_hidden_layers:      48
  num_key_value_heads:    4
  head_dim:               128

KV per token = 48 × 2 × 4 × 128 × 2 = 98,304 bytes = 96 KiB
KV @ 32K     = 96 KiB × 32,768 = 3.0 GiB
```

**优势**：实现简单，推理引擎兼容性最好。
**劣势**：KV Cache 最大。

### 3.2 Hybrid Linear + Full Attention — Qwen3.5-35B-A3B

**核心思路**：不是所有层都需要 Full Attention。用 **Linear Attention**（无需 KV Cache）替代大部分层，仅保留少量 Full Attention 层。

```
Qwen3.5-35B-A3B (HuggingFace config):
  num_hidden_layers:      40
  layer_types:            10 full_attention + 30 linear_attention
  num_key_value_heads:    2
  head_dim:               256

KV per token = 10 × 2 × 2 × 256 × 2 = 20,480 bytes = 20 KiB
KV @ 32K     = 20 KiB × 32,768 = 0.625 GiB
```

**为什么有效？**
- **Linear Attention** 层使用循环（recurrent）机制，维护固定大小的状态，不随序列长度增长
- 只有 10/40 = **25%** 的层需要 KV Cache
- KV Cache 压缩比：$(10 \times 2 \times 256) / (48 \times 4 \times 128)$ = **20.8%** of Qwen3

**代价**：
- Linear Attention 层的表达能力弱于 Full Attention
- 这些层**对量化高度敏感**（INT4 量化后精度显著下降）

### 3.3 Multi-head Latent Attention (MLA) — GLM-4.7-Flash

**核心思路**：不存完整的 K 和 V 向量，而是存一个**低秩压缩表示**（latent），推理时再解压。

在标准 Attention 中，每层需要存储：
- K: $H_{kv} \times D$ 个元素
- V: $H_{kv} \times D$ 个元素

MLA 将其压缩为：
- **一个 latent 向量**：$r_{kv}$ 维（kv_lora_rank）
- **加上 RoPE 部分**：$d_{rope}$ 维（qk_rope_head_dim）

$$\text{MLA per token per layer} = (r_{kv} + d_{rope}) \times b$$

```
GLM-4.7-Flash (HuggingFace config):
  num_hidden_layers:      47
  kv_lora_rank:           512
  qk_rope_head_dim:       64

Latent width = 512 + 64 = 576
KV per token = 47 × 576 × 2 = 54,144 bytes ≈ 52.9 KiB
KV @ 32K     = 52.9 KiB × 32,768 = 1.65 GiB
```

**为什么有效？**
- 标准 GQA 每层存 $2 \times H_{kv} \times D$ 个元素（如 Qwen3: $2 \times 4 \times 128 = 1024$）
- MLA 每层只存 576 个元素 → **压缩到 56%**
- 但 GLM 有 47 层全部使用 MLA，没有"跳过"某些层，所以总量仍 > Qwen3.5

**代价**：
- 推理时需要额外的矩阵乘法来"解压" latent → K, V
- 推理引擎需要专门适配 MLA（vLLM 已支持）

### 3.4 Hybrid Mamba + Attention — Nemotron-3-Nano-30B

**最激进的方案**：用 **Mamba（SSM，状态空间模型）** 替代绝大部分 Attention 层。Mamba 层不需要任何 KV Cache。

```
Nemotron-3-Nano-30B (HuggingFace config):
  num_hidden_layers:        52
  hybrid_override_pattern:  MEMEM*EMEMEM*EMEMEM*EMEMEM*EMEMEM*EMEMEMEM*EMEMEMEME
  attention layers (*):     6
  num_key_value_heads:      2
  head_dim:                 128

KV per token = 6 × 2 × 2 × 128 × 2 = 6,144 bytes = 6 KiB
KV @ 32K     = 6 KiB × 32,768 = 0.1875 GiB ≈ 192 MiB
```

**为什么有效？**
- 52 层中只有 6 层（**11.5%**）是 Attention → KV Cache 极小
- Mamba 层使用固定大小的循环状态（recurrent state），不随 T 增长

**代价**：
- Mamba 层有自己的 recurrent state（本文未计入，约 ~100-200 MiB）
- 在需要精确"回看"长距离 token 的任务上，纯 Mamba 可能不如 Attention
- 推理引擎兼容性较窄（需要 Mamba kernel 支持）

### 3.5 对比总结

以下是四种架构在 32K context、BF16、batch=1 下的 KV Cache 对比：

| Rank | Model | Per-Token | KV @ 32K | Compression | Strategy |
|:---:|-------|:---:|:---:|:---:|------|
| 1 | Nemotron-3-Nano-30B | 6 KiB | 0.19 GiB | **94%↓** | 仅 12% 层用 Attention |
| 2 | Qwen3.5-35B-A3B | 20 KiB | 0.625 GiB | **79%↓** | 仅 25% 层用 Full Attention |
| 3 | GLM-4.7-Flash | 53 KiB | 1.65 GiB | **45%↓** | MLA 低秩压缩每层 |
| 4 | Qwen3-30B-A3B | 96 KiB | 3.00 GiB | baseline | 全部层标准 GQA |

> **关键洞察**："减少参与 Attention 的层数"（Hybrid 策略）比"压缩每层存储"（MLA 策略）更有效。Nemotron 和 Qwen3.5 都通过大幅减少 Attention 层实现了最大压缩。

---

## L4: 量化对 KV Cache 的影响

### 4.1 Weight 量化间接帮助 KV Cache

量化模型权重不会直接减少 KV Cache 的大小（KV Cache 精度由推理引擎控制），但会**释放 GPU 显存**给 KV Cache 使用：

```
Example: Qwen3-8B on 24GB GPU

BF16 weights:  16.4 GB     INT4 weights:  ~5 GB
Remaining:      7.6 GB     Remaining:     19 GB
KV headroom:   ~7 GB       KV headroom:   ~18 GB (2.4× more!)
Max context:   ~48K        Max context:   ~125K
```

量化从 BF16 → INT4 释放了 **~11 GB** 显存空间，可以支撑从 48K 到 125K 的上下文，或者同时处理更多并发请求。

### 4.2 KV Cache 量化

推理引擎（如 vLLM）支持将 KV Cache 本身从 BF16 降低到 FP8：

$$\text{FP8 KV Cache} = \text{BF16 KV Cache} \times 0.5$$

| KV dtype | Qwen3-8B @ 32K | 质量影响 |
|:---:|:---:|:---:|
| BF16 (2 bytes) | 4.5 GiB | baseline |
| FP8 (1 byte) | 2.25 GiB | 通常可忽略 |

在 vLLM 中启用 FP8 KV Cache：

```bash
vllm serve Qwen/Qwen3-8B --kv-cache-dtype fp8
```

### 4.3 量化敏感层：哪些不能碰？

来自 Qwen3.5 量化实测的关键发现（来源：Benjamin Marie, Kaitchup）：

| 组件 | 能否 INT4 量化？ | 原因 |
|------|:---:|------|
| MLP 层 | ✅ 可以 | 对量化鲁棒 |
| Full Attention 层 | ✅ 可以 | 对量化较鲁棒 |
| **Linear Attention 层** | ❌ 避免 | 量化后精度显著下降 |
| **Shared Expert** (MoE) | ❌ 避免 | 量化后整体精度崩塌 |
| Embedding / LM Head | ❌ 默认保留 16-bit | 量化工具默认不动 |

**实践命令（AutoRound，保留 Linear Attention 层为 16-bit）**：

```bash
auto-round-best --model Qwen/Qwen3.5-9B \
                --scheme "W4A16" \
                --ignore_layers "linear_attn" \
                --output_dir Qwen3.5-9B \
                --enable_torch_compile
```

### 4.4 量化模型的意外行为："过度思考"

一个反直觉的发现：4-bit 量化的 Reasoning 模型会**生成更多的思考 token**，导致在受限的最大上下文长度下回答被截断。

| Model | Thinking ON truncation rate (AIME25) |
|-------|:---:|
| Qwen3.5-9B（原始 BF16） | ~30% |
| Qwen3.5-9B（INT4 量化） | ~70% |

**机制（推测）**：量化引入的细微精度损失可能影响模型的"何时停止思考"判断，导致 reasoning 循环更长。

**应对策略**：给量化模型设置更高的 `--max-model-len`，或使用 `max_completion_tokens` 限制生成长度。

---

## L5: 生产部署 VRAM 估算

### 5.1 VRAM 总公式

$$\boxed{\text{Total VRAM} = W + K + O}$$

| 符号 | 含义 | 估算方法 |
|------|------|---------|
| $W$ | 模型权重 | params × bytes_per_param（8B × 2 = 16 GB for BF16） |
| $K$ | KV Cache | $L \times 2 \times H_{kv} \times D \times T \times B \times b$（用本文 L2 公式） |
| $O$ | Runtime Overhead | ~10% of $W$（CUDA kernels, activations, fragmentation） |

### 5.2 实测验证（Azure H100 NVL 95GB）

以下使用 **Azure H100 NVL 95GB GPU VM** + **vLLM 0.19.0** 实测，验证公式准确性。

**测试环境**：
- GPU: NVIDIA H100 NVL, 95,830 MiB (93.6 GiB)
- Driver: 595.58.03, CUDA 13.2
- Model: Qwen/Qwen3-8B, BF16
- vLLM: 0.19.0, `--max-model-len 32768 --gpu-memory-utilization 0.95`

**启动命令**：

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-8B \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.95
```

**实测结果**：

| 阶段 | VRAM Used | 说明 |
|------|:---------:|------|
| 模型加载完毕 | **16,565 MiB (16.18 GiB)** | BF16 权重 + runtime overhead |
| vLLM 完全启动 | **92,049 MiB (89.89 GiB)** | 权重 + KV Cache pool 预分配 |
| vLLM 报告 KV 可用内存 | **70.72 GiB** | 用于 KV Cache 的空间 |
| vLLM 报告 KV 容量 | **514,944 tokens** | 最大可缓存 token 数 |

**公式验证**：

| 指标 | 公式预测 | 实测 | 误差 |
|------|:-------:|:----:|:----:|
| 模型权重 | 8.19B × 2 = 16.38 GB | 16.57 GB | +1.2% |
| KV 每 token | 36 × 2 × 8 × 128 × 2 = 144 KiB | — | — |
| KV 总量验证 | 514,944 × 144 KiB = **70.72 GiB** | vLLM 报告 **70.72 GiB** | <0.01% |
| 24K token 推理 | — | 0.1s（H100 + FlashAttention v3） | — |

> **结论**：公式计算与实测完美吻合。KV Cache per-token = 144 KiB 的理论值，在 vLLM 的实际 KV pool 分配中得到精确验证。

### 5.3 Concurrency 的影响

KV Cache 随并发线性增长：

$$K_{total} = K_{per\_sequence} \times B$$

| Batch Size | KV Cache (Qwen3-8B, 32K) | Total VRAM |
|:---:|:---:|:---:|
| 1 | 4.5 GiB | ~23 GB |
| 4 | 18.0 GiB | ~37 GB |
| 8 | 36.0 GiB | ~55 GB |

> 这就是为什么高并发场景需要 80 GB GPU（A100/H100）或多 GPU tensor parallelism。

### 5.4 GPU 选型决策树

```
Q1: 模型权重（BF16）能放进单GPU吗？
│
├── YES → Q2: 留给 KV Cache 的空间够吗？
│   │     （GPU VRAM − Weights − 10% overhead ≥ KV Cache for target context × concurrency）
│   │
│   ├── YES → 单 GPU + Data Parallelism
│   │         (vllm --dp N)
│   │
│   └── NO  → 选项A: 量化权重（BF16→INT4）释放空间
│             选项B: 降低 max context length (--max-model-len)
│             选项C: 使用 FP8 KV Cache (--kv-cache-dtype fp8)
│             选项D: 升级到更大显存 GPU
│
└── NO  → Tensor Parallelism (vllm --tp N)
          注意: N 必须能整除 num_attention_heads
```

---

## Appendix A: Score Matrix / FlashAttention / PagedAttention 关系

理解 KV Cache 后，还需要理清它和其他三个概念的关系。

### A.1 四个概念的分类

| 分类 | 概念 | 是什么 |
|:---:|------|------|
| **数据** | **Score Matrix** | Q × Kᵀ 的点积结果，T×T 的分数表。临时计算，用完就扔 |
| **数据** | **KV Cache** | K 和 V 向量的持久存储，在 HBM 中，持续整个对话 |
| **优化技术** | **FlashAttention** | 优化 **Score** 的计算方式——分块在 Shared Memory 中算，Score 不落地 HBM |
| **优化技术** | **PagedAttention** | 优化 **KV Cache** 的存储方式——分页管理 HBM，减少显存碎片 |

**FlashAttention 优化的是 Score，PagedAttention 优化的是 KV Cache。两者不冲突，vLLM 同时使用。**

### A.2 Score Matrix vs KV Cache

Score 矩阵是 KV Cache 的**消费者**——Score 的计算需要读取 KV Cache 中的 K。

| 对比 | **Score Matrix** | **KV Cache** |
|------|:---:|:---:|
| 是什么 | Q 和 K 的点积结果（T×T 表格） | K 和 V 向量本身 |
| 生命周期 | 每步重算，用完就扔 | 持续整个对话 |
| 大小随序列 | $O(T^2)$ | $O(T)$ |
| 存在哪 | 标准: HBM；FlashAttention: Shared Memory | HBM |
| 能缓存吗 | ❌ 每步 Q 变了必须重算 | ✅ 历史 K、V 不变 |

### A.3 FlashAttention: Score 不落地 HBM

**问题**：标准 Attention 在 HBM 中 materialize 完整的 T×T Score 矩阵。32K context → Score = 32K × 32K × 2 bytes = **2 GB**，反复读写 HBM 是带宽瓶颈。

**解决方案**：把 Q、K、V 分块（tile）加载到 GPU 的 **Shared Memory**（每个 SM ~200 KB 的片上高速存储），在 Shared Memory 中完成 Score 计算 + softmax + 乘 V，**只把最终 Output 写回 HBM**。

```
标准 Attention:
  HBM → 算完整 Score (T×T) → 写 HBM → 读 Score → softmax → 写 HBM → 读 × V → 写 HBM
  （Score 矩阵在 HBM 中反复读写）

FlashAttention:
  HBM → 搬一小块 Q,K 到 Shared Memory → 算 Score tile → online softmax → 乘 V tile → 写 Output
  （Score 从头到尾没进过 HBM）
```

**Online Softmax**：普通 softmax 需要先看到整行所有 Score（求 max 和 sum），但分块后每次只看到一小块。FlashAttention 用 online softmax 算法——维护 running max 和 running sum，每个 tile 更新一次，最终数学上等价于完整 softmax。

**Prefill vs Decode 的区别**：
- **Prefill**（处理 prompt）：Q 是长序列，Q/K/V 都需要分块
- **Decode**（逐 token 生成）：Q 只有 1 个 token（1×128），不需要分块；只有 K/V 的序列维度分块

### A.4 PagedAttention: KV Cache 分页管理

**问题**：KV Cache 需要连续内存。多请求并发时，请求结束释放的内存留下"洞"（碎片），新请求要连续空间但找不到 → OOM，即使总空闲够。

**解决方案**：像操作系统虚拟内存一样，把 HBM 切成固定大小的 Page（如每页存 16 个 token 的 KV）。每个请求的 KV Cache 可以分散在不连续的 Page 上，通过 Page Table 管理。

| | 无 PagedAttention | 有 PagedAttention |
|---|---|---|
| KV 存储 | 每请求一块连续内存 | 不连续的 Page |
| 碎片 | 严重 | 几乎没有 |
| 显存利用率 | ~50-70% | **~95%+** |
| 并发能力 | 低 | **同显存多 2-4x 请求** |

### A.5 三者如何协作（vLLM）

```
1. 新 token → 线性投影 → K₆, V₆
2. K₆, V₆ 存入 KV Cache → PagedAttention 决定放哪个 Page
3. Q₆ × [K₁...K₆]ᵀ → Score → FlashAttention 分块在 Shared Memory 算
4. Score → online softmax → × V → Output 写回 HBM
```

| 技术 | 作用对象 | 优化了什么 | 来源 |
|------|---------|----------|------|
| KV Cache | K, V 向量 | 省计算（不重复算历史 K,V） | Transformer 原始设计 |
| FlashAttention | Score 计算 | 省带宽（Score 不经过 HBM） | Tri Dao, Stanford 2022 |
| PagedAttention | KV Cache 存储 | 省显存（解决碎片问题） | vLLM, UC Berkeley 2023 |

---

## Reproducing

### Environment

```bash
pip install requests
```

### KV Cache Calculator

计算任意 HuggingFace 模型的 KV Cache 大小：

```bash
# Standard GQA model
python scripts/kv_cache_calculator.py Qwen/Qwen3-8B

# Hybrid attention model
python scripts/kv_cache_calculator.py Qwen/Qwen3.5-35B-A3B

# MLA model
python scripts/kv_cache_calculator.py zai-org/GLM-4.7-Flash

# Hybrid Mamba model
python scripts/kv_cache_calculator.py nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16

# Custom parameters
python scripts/kv_cache_calculator.py Qwen/Qwen3-8B \
    --context-length 131072 \
    --batch-size 4 \
    --dtype-bytes 1  # FP8
```

### Expected Output (Qwen3-8B)

```
Model: Qwen/Qwen3-8B
Architecture: gqa
  layers:                        36
  num_kv_heads:                   8
  head_dim:                     128
  per_token_bytes:          147456
  per_token_kib:             144.0
  context_length:            32768
  total_gib:                4.5000

  >>> KV Cache = 4.5000 GiB (4.8318 GB) for 32768 tokens, batch=1
```

### Script List

| Script | Purpose |
|--------|---------|
| [kv_cache_calculator.py](scripts/kv_cache_calculator.py) | Calculate KV cache size for any HuggingFace model |

---

