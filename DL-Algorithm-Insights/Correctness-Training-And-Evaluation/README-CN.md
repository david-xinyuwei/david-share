# 系统跑通，不等于结论成立：精度、MTP、Online RL 与完整评测方法

[English Full Edition](M03_correctness_training_evaluation_full_article_EN.md) | 中文完整版

> 把配置、运行、语义和结论分成四道门，再完整保留四本精度账、MTP non-greedy 修复、RL 两条轴和跨机 Benchmark 三个分母陷阱。

---

📌 **更多推理优化实践在 GitHub**

- **GitHub Repo**：<https://github.com/david-xinyuwei/david-share>
- **本系列**：`DL-Algorithm-Insights/`

---

*Author: 魏新宇 (Xinyu Wei) | Microsoft AI and Apps GBB Senior System Engineer*

---

## 怎么读这篇完整稿

这不是摘要版。下方每个“原稿章节”都保留对应旧稿的全部技术正文、表格、代码、公式、版本边界、误区、验证方法和参考来源。只删除重复的公众号引流、作者署名与横向分隔线；删除清单和逐图 SHA-256 记录在 `FULL_MERGE_LEDGER.md`。

本篇包含 6 张总览图和 35 张逐字节保留的原图。先用总览图建立位置感，再进入完整章节；总览图负责合并关系，细节图负责保留原始视觉信息，两者不互相替代。

## 六张总览图

![配置、运行、语义与结论的四层证据](images/m03_fig1_four_gates.png)

*图 1：上一层通过只是下一层的前置条件。HTTP 200、Job Succeeded 或非空输出，都不能自动证明语义和结论。*

![数值、决策与任务质量三层精度](images/m03_fig2_precision_layers.png)

*图 2：数值误差是连续量，Router/Token 是离散决策，任务分数又是有限样本聚合。三层必须分别验收。*

![存储、计算、通信和路由四本精度账](images/m03_fig3_four_ledgers.png)

*图 3：输入、乘法、累加、Softmax、输出可以使用不同 dtype；“FP8 Attention”不是从头到尾都做 FP8 运算。*

![MTP Greedy 与 Non-greedy 验证语义](images/m03_fig4_mtp_semantics.png)

*图 4：这不是“随机数不同”，而是目标分布定义不同。服务正常返回 Token，只能证明运行成功，不能证明请求语义被执行。*

![Online/Offline 与 On/Off-policy 四象限](images/m03_fig5_rl_axes.png)

*图 5：Prompt 固定不等于 Offline；模型能生成回答也不等于 Online。关键是当前策略的新行为能否取得目标环境的新反馈并回流训练。*

![归一化、外推和权重复制三个分母陷阱](images/m03_fig6_benchmark_traps.png)

*图 6：三个陷阱的分子都可以是真的；错误来自悄悄更换节点数、扩展效率或权重份数。*

---

## 完整技术正文


<!-- SOURCE-BEGIN id=03 source=03_accuracy_chain_article.md sha256=2b438f53e288f44b68762525dcf6f41f832fcf4589838fe68e42bfa555611de2 body_sha256=4309c579c94ab270782a93a097c085a2653e7bd9dd5e8e266bd7697e7489a157 -->
## 原稿 #3：模型精度到底在哪丢的？一条推理链上的四本账

> KV Cache、混合精度 Attention、量化 All-Reduce、Router GEMM，分别在存储、计算、通信和路由环节改变数值。它们不能用一句“开了 FP8”概括。









> 同一份模型放到两种 GPU 平台上，即使 benchmark 分数接近，为什么仍不能直接断言数值完全等价？

排查一套真实推理配置时，常会遇到四类开关：

```text
KV Cache 是否使用 FP8
Attention 内部到底使用哪些精度
Quick Reduce 通信是否启用量化
MoE Router 是否从 FP32 降到 FP16
```

这四项看似都是“量化”，实际对应推理链上的四个不同位置。

![原稿 #3 图 1](images/s03_03_accuracy_chain_article_img01.png)

先说结论：**推理精度不是一个开关，而是一条数据流。** 数据每经过一次存储、类型转换、求和、压缩或排序，都可能出现数值差异。


### 先把几个词说清楚

| 词 | 说的是什么 |
|---|---|
| **FP32** | 32 位浮点数，范围和有效数字通常比低位格式更充足 |
| **BF16** | BFloat16，16 位浮点数；指数范围接近 FP32，但有效数字更少 |
| **FP8 E4M3** | 8 位浮点格式，4 位指数、3 位尾数；占用更小，但可表示的数更稀疏 |
| **INT8** | 8 位整数；通常配合缩放因子近似表达浮点数据 |
| **KV Cache** | Key/Value Cache（键值缓存），保存历史 token 的 K/V 向量供后续 Attention 重用 |
| **Attention** | 注意力计算，让当前 Query 根据历史 Key/Value 聚合信息 |
| **All-Reduce** | 多张 GPU 汇总各自部分结果，并让每张卡都得到汇总值的集合通信 |
| **Quick Reduce** | 为减少跨 GPU 数据量而提供的量化 All-Reduce 实现 |
| **Router** | Mixture of Experts（混合专家模型）中的路由器，决定每个 token 交给哪些专家处理 |
| **GEMM** | General Matrix Multiply（通用矩阵乘） |
| **MTP** | Multi-Token Prediction（多 token 预测），让草稿路径一次提出多个候选 token |
| **kernel** | GPU 上实际执行的一段计算程序；同一算子可以有多套 kernel 实现 |
| **KL 散度** | Kullback-Leibler Divergence（库尔贝克-莱布勒散度），衡量两个概率分布的差异 |


### “精度一致”其实有三层

人们说“精度一样”，可能在说三件完全不同的事。

![原稿 #3 图 2](images/s03_03_accuracy_chain_article_img02.png)

#### 第一层：数值是否接近

同一个张量的最大绝对误差、相对误差、余弦相似度是否在阈值内。

```text
参考值：0.5002
优化值：0.5000
```

差值只有 `0.0002`，数值上可能非常接近。

#### 第二层：决策是否一致

模型经常不是直接使用这个数，而是拿它排序、选 Top-K 或采样。

```text
专家 A：0.5002
专家 B：0.5001
```

只要出现很小扰动，A、B 的顺序就可能交换。数值误差很小，路由决策却变了。

#### 第三层：任务质量是否一致

最终 benchmark 分数、多轮对话质量、代码执行成功率是否相近。

任务分数相同，只能说明这批样本没有把差异放大；不能证明中间张量逐位相同。反过来，中间存在微小误差，也不等于任务质量一定下降。

因此后文严格区分三种结论：

- **存在数值误差入口**：从数据类型和算法上可以确定。
- **当前测试未观察到质量下降**：只对测试范围有效。
- **完全无影响**：需要更强证据，通常不能仅凭一次 benchmark 得出。


### 第一本账：存储精度——KV Cache 用什么保存

Transformer 生成新 token 时，会反复读取历史 Key 和 Value。KV Cache 就是这些历史向量的长期存储区。

将 KV Cache 从 BF16 改成 FP8，最直接的收益是容量下降：同样显存可以保存更多 token，或者承载更大并发。

```text
BF16：每个元素 2 字节
FP8 ：每个元素 1 字节
```

但代价也很明确：BF16 中相邻的多个数，转成 FP8 后可能落到同一个可表示值。

![原稿 #3 图 3](images/s03_03_accuracy_chain_article_img03.png)

注意两个边界：

1. KV 通常是**写入缓存时量化一次**，不是每次读取都重新量化。
2. 量化误差虽然不会因为“读取次数”自动成倍增加，但这些近似值会参与后续 Attention，并通过新 token 和后续层继续传播。

所以 FP8 KV Cache 的风险更容易在这些场景暴露：

- 超长上下文
- 多轮对话
- 对微小概率差异敏感的推理
- MTP 校验或 Top-K 边界接近的场景

“短 benchmark 分数没掉”不等于“长上下文完全等价”。


### 第二本账：计算精度——一个 kernel 里可能有四种类型

很多配置表会写“FP8 Attention”或“BF16 Attention”，但一个 Attention kernel 往往不是从头到尾只有一种数据类型。

一个真实的混合精度路径可以是：

```text
Q / K / V 输入：FP8
点积累加：       FP32
Softmax：        FP32
最终输出：       BF16
```

![原稿 #3 图 4](images/s03_03_accuracy_chain_article_img04.png)

为什么这样设计？

- Q/K/V 占数据搬运大头，用 FP8 可以减少显存带宽。
- 点积需要累加大量乘法结果，FP32 累加可降低求和误差。
- Softmax 包含指数运算和归一化，对数值范围敏感，通常保留更高精度。
- 输出回到 BF16，方便接入模型后续层。

因此下面两句话都可能是错的：

```text
“输入是 FP8，所以所有计算都是 FP8。”
“输出是 FP32，所以前面一定按 FP32 计算。”
```

判断一个 kernel 的精度，至少要问四个问题：输入类型、乘法类型、累加类型、输出类型。

#### Fresh chunk 与 cached chunk 也可能不同

在 chunked prefill（分块预填充）里，第一块新输入可能直接使用新鲜的 BF16 K/V；进入缓存后，后续块读取的却是 FP8 KV Cache。

```text
首个新鲜 chunk：BF16 K/V → Attention
后续 cached chunk：FP8 K/V → 反量化尺度 → Attention
```

这意味着同一个 Prefill 阶段也可能存在两条数值路径。只写一句“Prefill 是 BF16”会漏掉缓存读取部分。


### 第三本账：通信精度——配置写 INT8，线上一定是 INT8 吗

Tensor Parallel（张量并行）会把一次矩阵计算拆到多张 GPU。每张卡得到部分结果后，需要通过 All-Reduce 汇总。

标准路径可以直接传 BF16。Quick Reduce 为了减少通信量，会采用类似下面的路径：

```text
BF16 局部结果
    ↓ 量化
低位 codec + 缩放因子
    ↓ 跨 GPU 传输与汇总
恢复到后续计算需要的浮点表示
```

![原稿 #3 图 5](images/s03_03_accuracy_chain_article_img05.png)

它没有改模型权重，也没有把后续所有计算永久改成低位格式；它只压缩通信阶段的数据。

但“只在通信时压缩”不等于“数学上无损”。BF16 映射到低位格式时，一般仍会出现舍入和截断，只是通过缩放因子控制误差。

#### 配置名与实际 codec 还可能不一致

公开源码对照还暴露了一个更隐蔽的问题：

```text
SGLang 配置层：QuickReduceRegime.INT8 = 1
                         ↓ 把数值 1 传给 AITER
AITER 3f4ab482：QuickReduceQuantLevel.FP8 = 1
```

也就是说，在这组精确版本里，环境变量写 `ROCM_QUICK_REDUCE_QUANTIZATION=INT8`，实际传入 AITER 后选择的是 **FP8 codec**。配置层名称不能代替实现层证据。

这不是文字游戏，而是验证方法：**不能只看环境变量名字，还要顺着枚举值追到实际 kernel 的 dispatch。** 不同分支和版本可能已经修正或改变映射，所以结论必须绑定 commit。

因此更严谨的结论应写成：

> 一组测试没有观察到输出乱码或任务质量异常，只能说明该测试范围内未发现问题；不能外推为所有模型、上下文和低位 codec 的通用保证。

更低位数会进一步减少通信量，也会让可表示值更稀疏。位数越低，越需要重新做端到端验证。


### 第四本账：路由精度——很小的误差也可能换专家

Mixture of Experts 模型不会让每个 token 经过所有专家。Router 先计算一组 logits（未归一化分数），再选择 Top-K 专家。

某条优化路径会把 Router 权重从 FP32 转成 FP16，使用 FP16 乘法，同时保留 FP32 累加与 FP32 logits 输出。

```text
输入：        BF16
Router 权重：FP16
乘法：        FP16
累加：        FP32
输出 logits：FP32
```

输出是 FP32，不代表结果等同于“FP32 权重 × FP32 输入”。权重在转成 FP16 时已经发生近似。

![原稿 #3 图 6](images/s03_03_accuracy_chain_article_img06.png)

举一个简化例子：

```text
原始 logits：专家 A = 0.5002，专家 B = 0.5001
近似后：     专家 A = 0.5000，专家 B = 0.5001
```

误差只有万分之几，但 Top-1 专家从 A 变成了 B。对于 Top-K Router，更应该观察专家集合的重合率，而不只是 logits 平均误差。

Router 精度还可能影响 MTP：专家路径变化后，Target 与 Draft 的预测分布可能稍微拉开，进而影响候选 token 接受率。


### 隐藏的第五项：数据类型相同，也不保证结果逐位相同

即使两边都写着 BF16 或 FP32，结果仍可能不同。

#### 求和顺序不同

浮点加法不满足严格结合律。下面是简化示意：

```text
(a + b) + c
和
a + (b + c)
```

在实数数学里相等，在有限位浮点数里可能因为中间舍入得到不同结果。GPU 并行归约改变求和顺序，就可能产生细微差异。

#### 舍入模式不同

从高精度转换到低精度时，需要决定落到上方还是下方的可表示值。不同硬件指令、编译选项或 kernel 可能采用不同路径。

#### Kernel fallback 不同

某个形状没有命中预期 kernel 时，框架可能退回另一套实现。两边启动参数一样，但真正执行的程序不同。

因此逐算子对齐不能只检查环境变量，还要检查：

```text
相同输入
→ 实际命中的 kernel
→ 每一步输入/累加/输出类型
→ 张量误差
→ 决策是否翻转
```


### 工程上真正应该做什么

把讨论压缩成四条：

1. **先建立公平 baseline。** 关闭额外量化和通信压缩，与参考配置对齐后再比较性能。
2. **关闭优化会降低性能或容量。** BF16 KV 占用更大；BF16 通信数据更多；FP32 Router 更慢。这是可预期代价。
3. **当前测试没发现质量问题，不等于理论上无误差。** 需要把结论限定在模型、数据集、上下文和运行版本内。
4. **最终配置取决于业务。** 性能优先可以接受已验证的轻微数值差异；高一致性场景则可能关闭更多优化。

这不是“精度和性能只能二选一”，而是要先建立可审计 baseline，再逐项打开经过验证的优化。


### 正确的精度验证应该怎么做

最稳妥的方法是单变量实验。

![原稿 #3 图 7](images/s03_03_accuracy_chain_article_img07.png)

#### 第一步：锁定 baseline

固定：

- 同一份权重和 tokenizer
- 同一批 prompts
- 相同 decoding 参数、随机种子
- 相同 batch、上下文长度和输出长度
- 明确的软件版本与实际加载路径

#### 第二步：一次只开一个优化

```text
Baseline：BF16 KV + 非量化 All-Reduce + FP32 Router
实验 A：只开 FP8 KV
实验 B：只开 Quick Reduce 量化
实验 C：只开 FP16 Router
实验 D：只换 Prefill / Decode kernel
```

#### 第三步：分四层看结果

| 层级 | 建议指标 |
|---|---|
| 张量数值 | 最大绝对误差、相对误差、余弦相似度、KL 散度 |
| 决策一致 | Router Top-K 重合率、token 翻转率、MTP 接受长度 |
| 任务质量 | benchmark 分数、代码执行通过率、人工质量评估 |
| 鲁棒边界 | 长上下文、多轮对话、不同 batch、不同随机种子 |

#### 第四步：确认运行时真的生效

不要只看启动脚本。还要核对进程环境、分配日志、kernel 日志和实际模块路径。

“参数写了”只能证明请求了这个优化，不能证明运行时命中了它。


### 五个常见误区

| 误区 | 正确理解 |
|---|---|
| benchmark 分数一样，所以数值完全一样 | 任务分数只能覆盖该数据集，不能证明张量逐位一致 |
| 没有乱码，所以没有精度损失 | 没有明显故障不等于没有小概率决策差异 |
| FP8 KV Cache 等于整个 Attention 都是 FP8 | 存储、乘法、累加、Softmax 和输出可以使用不同类型 |
| 输出是 FP32，所以 Router 就是 FP32 计算 | 权重或输入可能已经转成 FP16/BF16 |
| 配置写 INT8，所以线上一定传 INT8 | 必须追踪枚举值到实际 codec；本文精确版本中数值 1 映射到 FP8 |


### 三句话记住

**位置**：存储、计算、通信和路由，是四个独立的数值入口。

**边界**：存在误差入口，不等于已观察到任务质量下降；测试没掉分，也不等于完全无影响。

**方法**：先锁定高精度 baseline，再一次只开一个优化，同时检查张量、决策、任务和长上下文。


### 公开资料

1. PyTorch：Numerical Accuracy，浮点运算顺序与平台差异
   https://docs.pytorch.org/docs/stable/notes/numerical_accuracy.html

2. NVIDIA Transformer Engine：FP8 Primer
   https://docs.nvidia.com/deeplearning/transformer-engine/user-guide/examples/fp8_primer.html

3. 公开 SGLang fork 快照：Fresh BF16、cached FP8 与 FlyDSL Prefill 路径
   https://github.com/sammysun0711/sglang/blob/b0f860b81104eb3e9aae40cce391e56443e2d688/python/sglang/srt/layers/attention/aiter_utils.py

4. 公开 SGLang fork 快照：BF16 激活、FP16 Router 权重、FP32 累加与输出
   https://github.com/sammysun0711/sglang/blob/b0f860b81104eb3e9aae40cce391e56443e2d688/python/sglang/srt/layers/moe/mixed_router_gemm.py

5. 公开 SGLang fork 快照：配置层将 `INT8` 枚举为数值 1
   https://github.com/sammysun0711/sglang/blob/b0f860b81104eb3e9aae40cce391e56443e2d688/python/sglang/srt/distributed/device_communicators/quick_all_reduce.py

6. AITER 精确提交：实现层将数值 1 映射为 FP8 codec
   https://github.com/ROCm/aiter/blob/3f4ab482a2986919c784e469e23cfac7f93bb153/csrc/include/quick_all_reduce.cuh
<!-- SOURCE-END id=03 -->

---

<!-- SOURCE-BEGIN id=06 source=06_mtp_nongreedy_fix_article.md sha256=34647915b90c67434549d968fc5a006c4c5238c67aea259950e12b16798ddde7 body_sha256=239fd92e8c84623b1c55ed4e8c48a5cf1ca63769d4a6ce12ba224837daea5355 -->
## 原稿 #6：你设置了 temperature=1，MTP 验证却还在走 Greedy

> 服务器正常启动、MTP 正常出 Token、日志里也没有报错，但 non-greedy 请求在 HIP 上却被静默送进 greedy verifier。本文从公开 commit `878fff156` 出发，拆解这类“没有崩溃，却改变了算法语义”的隐形 Bug。









### 先说结论

这次 Bug 不是“投机解码不能运行”，而是更隐蔽的一类问题：

```text
请求要求 non-greedy sampling
          ↓
HIP / ROCm 路径缺少对应的随机验证实现
          ↓
程序没有失败，而是继续走 greedy verification
          ↓
temperature、top-k、top-p 的采样语义没有被正确带进验证阶段
```

![原稿 #6 图 1](images/s06_06_mtp_nongreedy_fix_article_img01.png)

它危险就危险在：**服务看起来一切正常。**

- HTTP 返回正常；
- MTP acceptance 指标仍然有数；
- GPU 利用率也可能正常；
- 甚至生成速度还不错；
- 但算法执行的已经不是请求指定的那条采样路径。

所以这不是普通性能 Bug，而是 **semantic fallback（语义回退）**：程序从一种算法语义退到了另一种，却没有显式失败。


### MTP / EAGLE 到底在做什么

先不用任何公式。

普通自回归生成时，Target 模型每次 forward 通常只确定下一个 Token：

```text
Target forward → 1 个新 Token → Target forward → 再 1 个 Token
```

MTP / EAGLE 的思路是：让一个更便宜的 Draft 路径先猜后面几个 Token，再让 Target 一次性检查这些猜测。

![原稿 #6 图 2](images/s06_06_mtp_nongreedy_fix_article_img02.png)

```text
Draft：我猜后面是 [A, B, C]
Target：我一次看完，决定 A/B/C 能接受到哪里
```

如果三个都通过，这次 Target forward 就推进了多个 Token；如果中途拒绝，就从拒绝处按 Target 的规则继续。

因此投机解码有两类工作：

| 阶段 | 负责什么 |
|---|---|
| Draft | 提候选，尽量多猜对几个 Token |
| Verify | 按 Target 的真实规则决定接受、拒绝和最终采样 |

**Draft 猜得快不够，Verify 还必须守住 Target 的采样语义。**否则速度可能还在，输出分布却变了。


### Greedy 和 non-greedy 差在哪

假设 Target 对下一个 Token 给出三种概率：

```text
A：50%
B：30%
C：20%
```

![原稿 #6 图 3](images/s06_06_mtp_nongreedy_fix_article_img03.png)

#### Greedy

永远选择概率最高的 A：

```text
argmax([0.5, 0.3, 0.2]) = A
```

同一输入重复运行，选择规则始终是“拿第一名”。

#### Non-greedy

按概率分布抽样：

```text
A 大约出现 50%
B 大约出现 30%
C 大约出现 20%
```

`temperature` 会改变这个分布的尖锐程度；`top-k` 和 `top-p` 会裁掉部分候选，再对剩余概率重新归一化。

在本文对应的实测配置里，`temperature=1.0` 属于 non-greedy 请求。但更严谨地说，是否属于 non-greedy，要看完整的 sampling 参数，而不是只看一个数字。

**Greedy 和 non-greedy 不是“随机数多少”的差别，而是生成分布的定义不同。**


### 最容易混的两个 top-k

这个 Bug 的适用范围写着：

```text
MTP topk=1 (tree_topk)
```

很多人会立刻得出结论：top-k 已经是 1，那不就是 greedy 吗？

不是。这里存在两个完全不同的 top-k。

![原稿 #6 图 4](images/s06_06_mtp_nongreedy_fix_article_img04.png)

| 名字 | 控制什么 | `=1` 的含义 |
|---|---|---|
| `speculative_eagle_topk` / `tree_topk` | Draft 树每层保留几个分支 | 每层只沿一条 Draft 链往前猜 |
| Sampling `top_k` | Target 最终采样保留几个词表候选 | 只保留概率最高的一个候选时，才接近 greedy |

`tree_topk=1` 只是说 Draft 候选是一条链：

```text
Token1 → Token2 → Token3
```

它并没有要求 Target 在验证和最终出词时必须 `argmax`。

所以完全可能同时成立：

```text
Draft tree_topk = 1
Target sampling = non-greedy
```

这正是 commit `878fff156` 修复的窄范围。


### Bug 就藏在一个条件分支里

修复前，EAGLE V2 的采样分支可以概括为：

```python
if sampling_info.is_all_greedy or _is_npu or _is_hip:
    target_predict = torch.argmax(next_token_logits, dim=-1)
    verify_tree_greedy(...)
else:
    # stochastic verification
```

![原稿 #6 图 5](images/s06_06_mtp_nongreedy_fix_article_img05.png)

注意最后那个 `_is_hip`。

它意味着：

```text
只要运行在 HIP 上
→ 不管请求是否 non-greedy
→ 都进入 argmax + greedy verifier
```

请求里的 `temperature`、sampling `top_k` 和 `top_p` 并没有在这条验证路径里发挥应有作用。

#### 为什么会这样

从 commit 注释看，原因不是开发者想故意改变算法，而是：

> 这版代码里的 HIP 路径缺少 CUDA 已有的 target-only stochastic verifier。

面对“当前 backend 没有实现”时，代码选择继续运行，并复用已有的 greedy verifier。

这在工程上容易理解，却有一个严重问题：**fallback 改变了请求语义。**

正确做法至少应该满足其一：

1. 实现语义等价的 fallback；
2. 明确报错，告诉用户 non-greedy 不受支持；
3. 显式告警并要求用户确认降级。

最危险的就是现在这种：没有失败，也没有让用户意识到算法已经变了。


### 为什么这会影响准确率与可比性

如果请求本来就是 greedy，这个分支没有问题。

但当请求要求 non-greedy 时，greedy verifier 可能改变：

- Draft Token 被接受或拒绝的轨迹；
- 拒绝后由 Target 采出的下一个 Token；
- 后续上下文，因此也改变后续所有生成；
- Agent 任务中的工具调用、代码修改和控制流。

![原稿 #6 图 6](images/s06_06_mtp_nongreedy_fix_article_img06.png)

对于普通短文本，一次分叉可能只让措辞不同。

对于 Coding Agent 或长轨迹任务，一次 Token 分叉可能变成：

```text
选了不同工具
→ 打开不同文件
→ 形成不同 patch
→ 触发不同测试
→ 最终 Pass / Fail 改变
```

这也是为什么“模型、Prompt、temperature 都一样”仍不等于跨 backend 的方法一致：**sampling 参数写在请求里，不代表每个 backend 都真正执行了同一采样语义。**


### commit `878fff156` 改了什么

这个公开 commit 的标题是：

> `bugfix(MTP): Fix HIP non-greedy EAGLE verification for MTP topk=1 (tree_topk) speculative decoding`

它修改了两个文件：

```text
python/sglang/srt/environ.py
python/sglang/srt/speculative/eagle_utils.py
```

总计：

```text
215 insertions
1 deletion
```

![原稿 #6 图 7](images/s06_06_mtp_nongreedy_fix_article_img07.png)

#### 第一处：增加环境变量门控

```python
SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY = EnvBool(False)
```

默认是 `False`，保持旧行为不变。

只有显式设置：

```bash
export SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1
```

才会启用新验证路径。

#### 第二处：增加 HIP 的 Torch / Python stochastic verifier

新路径只在四个条件同时满足时启用：

```python
use_hip_py_stochastic_verify = (
    _is_hip
    and not sampling_info.is_all_greedy
    and envs.SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY.get()
    and verify_input.tree_topk == 1
)
```

四个条件翻成大白话：

1. 当前是 HIP；
2. 请求不是 greedy；
3. 环境变量明确打开；
4. Draft 树每层只有一个分支。

**缺任何一个，都不会进入这条新路径。**


### 新验证路径怎么工作

新代码不是简单把 `argmax` 换成 `torch.multinomial`。

它补齐了整条 target verification 流程：

![原稿 #6 图 8](images/s06_06_mtp_nongreedy_fix_article_img08.png)

#### 1. 应用 temperature

```python
target_probs = softmax(next_token_logits / temperature)
```

temperature 改变概率分布的平滑程度。

#### 2. 按顺序应用 top-k 和 top-p

commit 的注释明确写了顺序：

```text
先做 top-k renorm
再做 top-p renorm
```

裁剪后重新归一化，得到 Target 的有效采样分布。

#### 3. 逐层验证 Draft 链

因为 `tree_topk=1`，Draft 是一条链。验证器沿链向前检查每个候选 Token。

它使用预生成的随机数（代码里称为 `coins`），结合 Target 概率与 acceptance threshold 决定接受还是拒绝。

#### 4. 拒绝后按 Target 分布补采样

如果 Draft Token 被拒绝，就不能继续沿原链硬走。验证器要从调整后的 Target 权重中采出新的 Token。

这一步决定了 non-greedy 语义是否真的回来了。

#### 5. 写回同一组输出张量

新 helper 会更新：

```text
predict
accept_index
num_correct_drafts
```

让后续 EAGLE 流程继续使用相同的数据合同。


### 为什么用 Torch / Python fallback

CUDA 路径已有 target-only stochastic verifier，但这版 HIP 栈没有等价 kernel。

commit 选择用 PyTorch 张量操作先补齐正确性：

- sort；
- cumsum；
- masked_fill；
- scatter；
- 按 CDF 和随机数采样。

优点是：

```text
不用等待新的 HIP kernel
先恢复 non-greedy 语义
```

代价也很明确：

```text
它未必是最终性能最优实现
```

所以环境变量默认关闭并不奇怪。这是一个典型的工程取舍：**先提供 opt-in correctness path，再决定是否内核化和默认启用。**


### 如何正确启用

环境变量必须在启动 SGLang 服务之前设置：

```bash
export SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1

python3 -m sglang.launch_server \
  ... \
  --speculative-algorithm EAGLE \
  --speculative-eagle-topk 1 \
  --enable-multi-layer-eagle
```

![原稿 #6 图 9](images/s06_06_mtp_nongreedy_fix_article_img09.png)

注意三件事。

#### 1. 这不是启动参数

它不会出现在 `ps` 的命令行里。

因此只检查：

```bash
ps -ef | grep sglang.launch_server
```

证明不了这个 fix 已启用。

#### 2. 必须检查真实模型进程的环境

可用精确变量名检查：

```bash
tr '\0' '\n' < /proc/<MODEL_PID>/environ \
  | grep '^SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY='
```

期望输出：

```text
SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1
```

#### 3. 必须同时锁定源码身份

同名环境变量在没有对应 commit 的旧代码上不会产生这个行为。

所以至少还要记录：

```bash
git -C /path/to/sglang rev-parse HEAD
```

并确认源码包含新 gate 与 stochastic verifier。


### 后续 commit 做了什么

在 `878fff156` 中，环境变量的代码默认值仍然是 `False`。

后续公开 commit `b0f860b8` 修改的是评测启动脚本：

```bash
export SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY="${SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY:-1}"
```

也就是说：

| 层次 | 默认行为 |
|---|---|
| `environ.py` 的全局代码默认值 | `False` |
| 后续 accuracy eval launcher | 未显式覆盖时导出 `1` |

![原稿 #6 图 10](images/s06_06_mtp_nongreedy_fix_article_img10.png)

这两句话不能混成一句“后来默认开启了”。

准确说法是：

> 后续评测脚本把这个 gate 的默认环境值设成了 1；框架全局环境声明本身仍是 opt-in 设计。

本文分析的是 `sammysun0711/sglang` 公开 fork 的 commit。截至本文核查时，在 `sgl-project/sglang` 默认分支代码搜索中未找到同名 gate，因此不能写成“SGLang 主仓已经普遍启用”。


### 一轮 499 题实测能证明什么

项目中确实完成过一轮启用该 fix 的 499 题 Coding Agent benchmark：

| 项 | 结果 |
|---|---:|
| 范围 | 499 题，单轮 |
| Pass | 366 |
| Fail | 133 |
| 得分 | 73.35% |
| 平均步数 | 79.10 |
| MTP | EAGLE，3 steps，multi-layer |
| Draft tree | `speculative_eagle_topk=1` |

三份独立数据源对账一致：

```text
trajectory：499 题
reward：499 题
results：499 题
```

`366 + 133 = 499`，无空状态，独立复算与输出一致。

![原稿 #6 图 11](images/s06_06_mtp_nongreedy_fix_article_img11.png)

运行资产还包括：

- wrapper 在服务启动前导出 gate；
- runtime validator 设计为读取 `/proc/<pid>/environ`；
- 交付 bundle 封存对应 SGLang commit；
- 结果按 499 题完整审计。

#### 但它不能证明什么

这轮结果**不能**证明：

```text
打开 fix 就提高了 X 个百分点
```

因为没有一轮完全相同条件下、只把 gate 从 0 改到 1 的 full499 A/B。

其他历史运行还存在 MTP 开关、radix cache、runtime epoch 等差异，不能拿分数直接相减后归因给这个 commit。

因此可守结论是：

> fix-enabled 路径完成过一轮 499 题运行并得到可审计结果，证明该路径能承载完整 workload；当前证据不支持量化该 fix 的单变量分数收益。


### 真正严谨的 A/B 应该怎么做

如果要回答“这个 fix 到底改变了什么”，至少做三组实验。

![原稿 #6 图 12](images/s06_06_mtp_nongreedy_fix_article_img12.png)

| 组别 | gate | temperature | 目的 |
|---|---:|---:|---|
| A | 0 | 1.0 | 复现 HIP 静默 greedy fallback |
| B | 1 | 1.0 | 验证 stochastic verifier |
| C | 1 | 0 | 验证 greedy 请求不受影响 |

必须固定：

- 同一 commit；
- 同一模型与权重；
- 同一 Prompt 集；
- 同一 Draft 配置；
- 同一 sampling `top_k` / `top_p`；
- 同一 seed 策略；
- 同一 backend 与硬件；
- 同一服务启动 epoch。

#### 不能只看一条输出

non-greedy 本来就有随机性。单个 Prompt 输出不同，不足以证明实现正确；单个 Prompt 恰好相同，也不足以证明没生效。

应同时观察：

```text
输出 Token 分布
accept length 分布
Draft 接受 / 拒绝轨迹
最终任务成功率
端到端 wall-clock
```

#### Greedy 控制组必须不变

C 组是非常重要的负对照：当请求本来就是 greedy 时，开关不应该改变输出路径。

如果 C 组也变了，说明 fix 的作用范围可能超出了设计边界。


### 为什么这类 Bug 比崩溃更难查

崩溃至少会告诉你：路径不可用。

语义回退却会制造一种错觉：

```text
服务能跑
≈ 配置生效
≈ 算法一致
```

这三个等号都不成立。

#### 配置存在，不等于执行到了

请求里有 `temperature=1.0`，只能证明调用者提出了要求。

它不能证明：

- backend 支持这项语义；
- verifier 选择了 stochastic path；
- fallback 没有偷偷换成 argmax。

#### 指标看起来正常，不等于语义正确

accept length、吞吐和 GPU 利用率都是运行指标，不是 sampling 语义证明。

#### 跨平台“参数一致”，不等于方法一致

NVIDIA / CUDA 路径有 stochastic verifier，HIP 路径却强制 greedy。即使两边命令行完全相同，执行方法仍然不同。

这正是 benchmark 对齐中最容易漏掉的一层：

```text
参数一致
→ 代码分支一致
→ 算法语义一致
→ 结果才可比较
```


### 五个常见误区

| 误区 | 正确理解 |
|---|---|
| MTP 能出 Token，就说明 MTP 正确 | 能运行只证明控制流通了，不证明 verifier 语义正确 |
| `tree_topk=1` 就是 greedy sampling | 它只约束 Draft 树分支数，和 Target sampling top-k 不是一回事 |
| 请求设置 temperature，就一定按 temperature 采样 | backend 可能不支持或发生 silent fallback |
| 设置了环境变量就算启用 | 还要核对真实模型进程环境和源码 commit |
| 366/499 证明 fix 提升了准确率 | 它证明 fix-enabled 路径完成全量运行，不是单变量 A/B |


### 四句话记住

**第一句**：MTP 的 Draft 负责猜，Verify 负责守住 Target 的真实采样语义。

**第二句**：旧 HIP 分支把 non-greedy 请求静默送进 argmax + greedy verifier，这是语义回退，不只是性能回退。

**第三句**：commit `878fff156` 为 HIP + non-greedy + `tree_topk=1` 增加了 opt-in Torch stochastic verifier，必须通过环境变量开启。

**第四句**：验证这类 fix，不能只看命令行和服务健康；必须核对源码、进程环境、代码分支和统计分布。

如果只能记一句：**配置写了什么不重要，最终走进了哪个算法分支才重要。**


### 公开资料

1. HIP non-greedy EAGLE verification 修复 commit
   https://github.com/sammysun0711/sglang/commit/878fff15647fe3dabb32aa3a335b0ad16e3ee878

2. 同一 commit 的原始 patch
   https://github.com/sammysun0711/sglang/commit/878fff15647fe3dabb32aa3a335b0ad16e3ee878.patch

3. 后续评测 launcher 默认启用 gate 的 commit
   https://github.com/sammysun0711/sglang/commit/b0f860b81104eb3e9aae40cce391e56443e2d688

4. SGLang 官方仓库
   https://github.com/sgl-project/sglang

5. EAGLE：Speculative Sampling Requires Rethinking Feature Uncertainty
   https://arxiv.org/abs/2401.15077

6. Fast Inference from Transformers via Speculative Decoding
   https://arxiv.org/abs/2211.17192
<!-- SOURCE-END id=06 -->

---

<!-- SOURCE-BEGIN id=07 source=07_online_offline_rl_article.md sha256=1ba5832338f6694084680e18c25648e4ef4d6ed08015d84b75dc547fbb264c36 body_sha256=83471988d18ce5d974c0641081178c11ff99c1ea763e9793102b76a4908152f5 -->
## 原稿 #7：Online RL 到底“在线”在哪？用一辆测试车讲清四个概念

> Online / Offline 和 On-policy / Off-policy 是两条不同的分类轴。本文不从公式开始，而是让一辆测试车不断上路：看它何时能获得新的真实反馈、训练时又在看谁的行车录像，再回到 Agent Lightning 和 Microsoft Foundry 的真实代码与实测路径。









### 先说结论

强化学习里最容易混淆的，不是算法名字，而是两个看起来很像的 `on / off`：

```text
Online / Offline
问：训练期间，当前策略还能不能从目标环境获得新的交互与奖励？

On-policy / Off-policy
问：训练当前策略的数据，是不是由当前策略自己产生的？
```

![原稿 #7 图 1](images/s07_07_online_offline_rl_article_img01.png)

所以正确的判断法是：

> **Online / Offline 看“新反馈还能不能回来”；On / Off-policy 看“这段经历是谁产生的”。**

这两个问题彼此独立。

- Online RL 可以是 On-policy；
- Online RL 也可以是 Off-policy；
- Offline RL 通常面对 Off-policy 数据；
- “线上客户数据”不是 Online RL 的定义；
- “离线文件”也不是 Offline RL 的充分条件。

后面所有概念，都用同一辆测试车解释。


### 先搭一个测试车世界

假设我们在训练一辆自动驾驶测试车。

| 强化学习术语 | 小车里的对应物 |
|---|---|
| Policy / Actor | 当前驾驶模型 |
| Environment | 测试道路、交通规则和其他车辆 |
| Observation / State | 车辆实际读到的传感器观测 / 环境的完整真实状态 |
| Action | 加速、刹车、转向 |
| Reward | 安全、到达、舒适度、碰撞等综合得分 |
| Rollout | 当前策略与环境交互产生的一段行车轨迹；可以完整结束，也可以被截断 |

![原稿 #7 图 2](images/s07_07_online_offline_rl_article_img02.png)

严格说，真实自动驾驶更接近 **POMDP（部分可观测马尔可夫决策过程）**：道路拥有完整 `State`，但车通常只能通过摄像头、雷达等传感器获得 `Observation`。为了不让符号干扰理解，下面直接用 `o` 表示车辆当时实际看到的观测。

一条最小经历可以写成：

```text
观测 o_t：雨天，前方弯道，当前时速 45 km/h
动作 a_t：减速到 30 km/h 并右转
新观测 o_{t+1}：安全通过弯道
奖励 r_t：按当前 Reward 规则得到 +10
```

一整段连续经历则可能是：

```text
出发
→ 识别红灯
→ 刹车
→ 等待绿灯
→ 转弯
→ 避让行人
→ 到达终点
→ 整段轨迹的 Return 为 86 分
```

这段“实际跑一遍并记录交互过程”，就是一次 **Rollout**。它不一定非要跑到自然终点；达到最大步数、超时或被安全系统中止的一段轨迹，也可以作为一个截断 Rollout。

单步得到的是 Reward `r_t`；整段轨迹累计得到的是 Return。常见定义是：

$$
G_t = \sum_{k=0}^{T-t} \gamma^k r_{t+k}
$$


### Online RL：当前车还能继续上路拿到新反馈

Online RL 的关键不是“数据来自线上用户”，也不是“模型每秒更新”。

它真正要求的是：

```text
当前驾驶模型提出新动作
        ↓
进入目标环境或高保真受控环境执行
        ↓
环境返回新观测；冻结的 Reward 规则计算得分
        ↓
这条新经历用于后续训练
```

![原稿 #7 图 3](images/s07_07_online_offline_rl_article_img03.png)

例如驾驶模型从 1.0 更新成 2.0 后，2.0 又在高保真模拟器或封闭测试场的湿滑弯道上尝试新的减速策略，获得新的侧滑反馈，并按冻结的 Reward 规则计算得分。

小车只是控制问题的教学抽象。真实自动驾驶通常先在模拟器、封闭测试场和受控测试车队中验证，不会直接让生产车辆在公共道路上自由探索。

这就是 Online：**更新后的策略会继续影响下一轮训练数据长什么样。**

#### Prompt 或题库固定，仍然可以是 Online

大模型训练中，题目可能来自一份固定 Prompt 集。

但如果每轮都执行：

```text
同一批 Prompt
→ 当前模型重新生成回答或工具轨迹
→ 测试 / Grader / 环境重新打分
→ 新回答与新 Reward 回流训练
```

它仍然是 Online RL。

题目是否固定，不决定 Online / Offline；**当前策略的新行为能否得到新的环境反馈**，才决定。


### Offline RL：只能从冻结的历史经历学习

Offline RL 不是“没有老师”，更不是“没有奖励”。

经典 Offline RL 数据本来就包含：

```text
(state, action, reward, next_state)
```

它的限制是：训练期间不再从目标环境收集新的交互数据。

![原稿 #7 图 4](images/s07_07_online_offline_rl_article_img04.png)

还是那辆车。

现在我们只有一个冻结的历史录像库：

```text
人类司机的录像
旧版驾驶模型的录像
每一步状态、动作与奖励
事故和接管记录
```

当前模型当然仍能：

- 更新参数；
- 对录像反复训练；
- 对某个新动作预测价值；
- 生成一个候选驾驶方案；
- 甚至借助世界模型生成合成轨迹。

但它不能把刚想到的新动作送回目标环境，取得新的可信转移数据，再按冻结的 Reward 规则获得新分数并加入证据集。

这也是 Offline RL 的核心困难：

> 模型最容易对历史数据没有覆盖的动作过度乐观，却没有机会通过真实交互及时纠正。

Conservative Q-Learning 一类方法之所以强调“保守”，正是为了缓解这种数据分布与新策略之间的偏移。


### On-policy：当前司机主要学习自己刚开的录像

现在只讨论 Online RL 内部的第一种方式。

当前驾驶模型是 `πₖ`：

```text
πₖ 亲自上路
→ 产生一批最新 Rollout
→ 用这批数据更新 πₖ
→ 得到 πₖ₊₁
→ πₖ₊₁ 重新上路
```

![原稿 #7 图 5](images/s07_07_online_offline_rl_article_img05.png)

这叫 On-policy，因为数据来自本轮更新所针对的当前策略。

注意一个经常被误解的地方：

```text
πₖ 产生数据
→ 用数据更新
→ 得到 πₖ₊₁
```

并不矛盾。

`πₖ₊₁` 在更新前还不存在，当然不可能提前产生这批数据。所谓 On-policy，是说数据由更新开始时的当前策略 `πₖ` 产生。

#### On-policy 不等于每条数据只能用一次

PPO 通常会把同一批新 Rollout 切成 mini-batch，训练多个 epoch。

它仍然通常被归为 On-policy，因为这些数据只在短期内服务于当前更新，不会长期放进经验池，让许多代之后的策略反复抽取。


### Off-policy：当前司机也能学习旧司机或其他司机的录像

如果当前模型是 2.0，但训练数据还包括：

```text
1.0 的历史录像
人类老司机的示范
其他模型的轨迹
2.0 当前刚产生的新录像
```

那么行为数据的生产者不再只等于当前目标策略，这就是 Off-policy。

![原稿 #7 图 6](images/s07_07_online_offline_rl_article_img06.png)

需要强调：

> **Off-policy 不是“只用别人的旧数据”，而是允许使用不由当前策略产生的数据。**

这些数据既可能来自别人，也可能来自模型自己的旧版本。

#### 为什么 2.0 还要学习 1.0 的旧经历

因为升级到 2.0 通常只是参数向前走了一小步，不代表 1.0 的所有经验都已经被完整吸收。

旧经历仍可能包含稳定的环境规律：

```text
这个湿滑路口晚刹车会侧滑
这个盲区经常出现行人
这种连续变道会触发接管
```

复用旧 Rollout 有三个现实价值：

1. 一次训练未必学透所有样本；
2. 事故等稀有经历值得重复学习；
3. 重新撞车、重新跑工具链都很贵。

但旧数据也不能无限使用。

- 环境规则变了，要丢弃或重新标注；
- Reward 规则变了，要重新打分或新建数据版本；
- 旧策略与当前策略相差太远，要修正、降权、裁剪或丢弃；
- 重复过多会导致过拟合。

这就是 Off-policy 算法经常需要 Importance Sampling、保守估计或 Replay Buffer 淘汰策略的原因。


### 四种组合放在一张图里

现在把两条分类轴合起来。

![原稿 #7 图 7](images/s07_07_online_offline_rl_article_img07.png)

| 组合 | 小车怎么训练 | 典型理解 |
|---|---|---|
| Online + On-policy | 当前车持续上路，主要学自己刚产生的新录像 | PPO、GRPO 常见主线 |
| Online + Off-policy | 当前车持续上路，同时复用经验池里的新旧录像 | DQN、SAC 常见主线 |
| Offline + Off-policy | 测试环境不再提供新交互，只学冻结历史库 | CQL、IQL 等 |
| Offline + On-policy | 只能在训练起点非常窄地重合；策略一更新，固定数据便不再来自当前策略 | 不是常见稳定分类 |

最重要的区别出现在模型更新后：

```text
Online Off-policy：
旧录像继续学 + 新模型继续上路 + 新录像继续加入经验池

Offline RL：
固定录像库反复学 + 新模型不能从目标环境取得新的真实轨迹
```

所以两者虽然都可能使用“旧数据”，但一个数据池持续进新证据，另一个数据集已经冻结。


### Rollout、Epoch 和 Rollback 不是一回事

这三个词很容易在中文语境里混在一起。

![原稿 #7 图 8](images/s07_07_online_offline_rl_article_img08.png)

#### Rollout：出去实践一次

```text
一辆车从出发到完成任务
或一个 Agent 从收到问题到完成工具调用
```

它产生训练数据。

#### Epoch：把已有训练数据完整学习一遍

假设收集了 1,000 条 Rollout：

```text
完整遍历这 1,000 条数据一次 = 1 个 Epoch
再完整学习一遍             = 第 2 个 Epoch
```

它消耗训练数据。

实际训练时，一个 Epoch 通常还会被切成多个 mini-batch，并对应多次梯度更新。

#### Rollback：退回旧版本

如果模型更新后评测失败，把部署恢复到上一个 checkpoint，才叫 Rollback。

一句话记住：

> **Rollout 向前跑一遍；Epoch 把记录学一遍；Rollback 向后退一个版本。**


### Reward Model 不是强化学习的必选角色

Reward 是强化学习的核心，但 Reward Model 只是产生 Reward 的一种方式。

![原稿 #7 图 9](images/s07_07_online_offline_rl_article_img09.png)

自动驾驶的 Reward 可以来自：

- 是否碰撞；
- 是否到达；
- 是否急刹；
- 是否人工接管；
- 舒适度、时间和能耗的加权规则。

大模型 Agent 的 Reward 也可以来自：

- 单元测试；
- 数学答案检查器；
- 格式规则；
- 环境 `get_reward()`；
- 学习型 Reward Model；
- 多个奖励函数的加权组合。

所以更准确的角色关系是：

```text
Reward：必需的学习信号
Reward Model：可选的打分器
```

#### Reward 值会变，Reward 规则要版本化

每次 Rollout 的结果不同，Reward 数值当然会变。

但判分规则不能在同一正式训练 lineage 中悄悄变化。

```text
Reward v1 完成一轮训练
→ 分析问题
→ 发布 Reward v2
→ 新建训练身份和评测基线
```

否则无法判断模型真的变好了，还是判卷标准变了。


### Online RL 会不会把客户机密拿去训练

不一定。

Online RL 可以只使用：

- 公开题库；
- 合成任务；
- 沙箱环境；
- 人工编写的训练场景；
- 脱敏且获得授权的数据。

“Online”描述训练闭环，不描述数据敏感等级。

但如果 Rollout 来自客户生产 Agent，它可能记录：

```text
Prompt 与上下文
工具调用和返回值
内部代码、订单、邮件或合同
模型回答
Reward 与评审结果
```

所以必须先经过数据治理。

![原稿 #7 图 10](images/s07_07_online_offline_rl_article_img10.png)

安全路径应当是：

```text
授权范围内采集
→ 数据最小化
→ 秘密 / PII / 商业数据脱敏
→ 客户与租户隔离
→ 审核和 Reward
→ 进入受控训练池
→ 独立 Holdout
→ Canary 与回滚
```

脱敏审核并不会自动把 Online RL 变成 Offline RL。

只要更新后的策略仍会产生下一轮新轨迹，新轨迹经过同样治理后继续回流，这个闭环仍然是 Online RL。


### Agent Lightning 当前代码实际做的是哪一种

下面不靠产品名字猜，直接看微软官方仓库固定快照：

```text
microsoft/agent-lightning
commit d2c4d1f6307afd5948cd302a1928306d859daa06
```

核心 VERL 路径的训练节拍可以概括为：

![原稿 #7 图 11](images/s07_07_online_offline_rl_article_img11.png)

```text
当前模型 / vLLM endpoint
→ Agent Runner 执行新 Rollout
→ Tracer / Store 收集 spans 与 Reward
→ Adapter 转成 Triplet / train batch
→ clear_data_and_server 清理本批 daemon 状态
→ compute_advantage
→ update_actor
→ 新权重进入下一轮
```

对应代码里可以直接看到：

```text
run_until_all_finished()
get_train_data_batch(...)
clear_data_and_server()
compute_advantage(...)
update_actor(...)
```

这是一条 Online RL 控制流：当前模型持续执行 Agent 任务，取得新的轨迹和奖励，再更新权重。

#### 核心开箱路径：Online + GRPO / PPO-style

当前 Algorithm Zoo 公开列出的核心算法只有：

- APO：提示词优化；
- VERL：权重强化学习。

官方示例与配置大量使用 GRPO，整体属于 On-policy 或近似 On-policy 的 Online RL 主线：新 Rollout 服务于当前一轮更新，而不是从长期 Replay Buffer 随机抽取多代历史经验。

#### Contrib 中确实有名为 Off-policy 的 EMPO² 模式

固定快照的 `contrib/env_verl` 中可以看到：

```text
empo2_train_mode = "off-policy"
```

但它属于 Contrib / 实验路径，围绕 Tips 与 Online Self-Distillation 组织训练，并不是核心 Algorithm Zoo 的通用历史 Replay Buffer 实现。

所以不能把它写成：

```text
Agent Lightning 已经内置完整 DQN / SAC / CQL / IQL 能力
```

#### 当前固定快照没有开箱即用的 Offline RL Trainer

Store 能保存 Rollout 和 Span，Algorithm 接口也允许用户自定义。

因此架构上可以接入自编 Off-policy 或 Offline 算法；但在这个固定 commit 的核心 Algorithm Zoo 中，没有看到开箱即用的 Replay Buffer / Offline RL Trainer。

准确结论是：

> **Agent Lightning 是可扩展的训练编排框架；当前核心现成权重 RL 路径主要是 Online GRPO，而不是“所有 RL 算法都已经内置”。**


### Foundry Custom Code Training 又提供哪一层

Agent Lightning 解决 Agent 执行、轨迹、算法与资源更新之间的编排。

Microsoft Foundry Custom Code Training 提供的则是托管执行面：

![原稿 #7 图 12](images/s07_07_online_offline_rl_article_img12.png)

| Foundry 提供 | 客户提供 |
|---|---|
| 托管 GPU 与 Ray | 模型、数据和容器 |
| 作业生命周期与重试 | 训练代码和参数 |
| 只读输入挂载 | Agent / 工具环境 |
| 日志与指标 | Rollout 与 Reward / Grader |
| Checkpoint 和模型资产 | GRPO / PPO 等算法语义 |

公开实测 Repo 已完成一条 Foundry + VERL 路径：

```text
Qwen3-14B
单节点 4×A100 80GB PCIe
128 个 Prompt，每个 Prompt 采样 3 次（n=3 samples per prompt）
14 / 14 optimizer steps
4 次 validation
Foundry Job 5h41m
模型与 checkpoint 输出已注册
```

它证明的是：Custom Code Training 可以托管客户自定义的 Online GRPO 执行链。

四次 validation 分数分别是：

```text
训练前：0.05565
step 5：0.05242
step 10：0.05565
step 14：0.05726
```

它们在很低的基线附近先降、回到原值、再小幅上升。单次 14 步运行无法把这点变化与运行噪声分开。

它不证明：

- 14 步已经收敛；
- 模型质量显著提升；
- 另一种 GPU 或模型可以直接复用同一配置；
- 这条 Repo 使用了 Agent Lightning。

最后再区分一个相近名字：

- **Foundry Managed Compute**：公开文档定义为开源 / 社区模型的托管推理部署；
- **Custom Code Training**：客户自带代码执行 SFT / RL 的训练路径。

前者是推理部署，后者才是本文 Online RL 的托管训练落点。


### 十个常见误区

| 误区 | 正确理解 |
|---|---|
| Online RL 就是拿线上客户数据训练 | Online 描述交互闭环，不描述数据来源和敏感等级 |
| Offline RL 没有奖励 | 固定数据通常就包含 Reward，也可以使用奖励模型 |
| 模型能生成新回答，就一定是 Online RL | 还要看新回答能否获得目标环境的新反馈并回流训练 |
| 固定 Prompt 就是 Offline RL | 当前策略每轮重新生成并重新评分，仍可是 Online RL |
| Off-policy 就是只用别人的数据 | 也包括当前模型旧版本的数据，还可以混入当前新数据 |
| Online Off-policy 和 Offline RL 一样 | 前者经验池持续加入新交互，后者数据集冻结 |
| Rollout 就是 Epoch | Rollout 产生经历；Epoch 遍历已有数据 |
| Rollout 就是 Rollback | 一个向前试跑，一个退回旧版本 |
| Reward Model 是必需组件 | 必需的是 Reward；测试、规则和环境也可以给 Reward |
| Agent Lightning 已内置所有 RL | 核心现成路径是 APO / VERL；其他算法需按当前代码边界说明 |


### 五句话记住

**第一句**：Online / Offline 看当前策略能不能从目标环境取得新的交互和奖励。

**第二句**：On / Off-policy 看训练数据是否必须由当前策略产生。

**第三句**：Online Off-policy 会同时学习旧经验和持续加入的新经验；Offline RL 只能从冻结数据集学习。

**第四句**：Rollout 是一次完整实践，Epoch 是把实践记录学习一遍，Rollback 是退回旧版本。

**第五句**：Agent Lightning 当前核心现成路径主要是 Online GRPO；Foundry Custom Code Training 可以托管客户自定义的 Online RL，但训练语义仍由客户代码定义。

如果只能记一句：

> **先问新反馈还能不能回来，再问这段经历是谁产生的。**


### 公开资料

1. Offline Reinforcement Learning: Tutorial, Review, and Perspectives on Open Problems  
   https://arxiv.org/abs/2005.01643

2. Conservative Q-Learning for Offline Reinforcement Learning  
   https://arxiv.org/abs/2006.04779

3. OpenAI Spinning Up：Proximal Policy Optimization  
   https://spinningup.openai.com/en/latest/algorithms/ppo.html

4. Hugging Face TRL：GRPO Trainer  
   https://huggingface.co/docs/trl/main/en/grpo_trainer

5. Microsoft Agent Lightning 官方仓库（本文代码审计快照 `d2c4d1f`）  
   https://github.com/microsoft/agent-lightning/tree/d2c4d1f6307afd5948cd302a1928306d859daa06

6. Agent Lightning：Bird's Eye View  
   https://github.com/microsoft/agent-lightning/blob/d2c4d1f6307afd5948cd302a1928306d859daa06/docs/deep-dive/birds-eye-view.md

7. Agent Lightning：Algorithm Zoo  
   https://github.com/microsoft/agent-lightning/blob/d2c4d1f6307afd5948cd302a1928306d859daa06/docs/algorithm-zoo/index.md

8. Microsoft Foundry Custom Code Training 实测 Repo（公开 commit）  
   https://github.com/david-xinyuwei/david-share/tree/2a73df5ea407a029eeb5f3cf62eb38e7564a3cc2/Deep-Learning/AI-Foundry-Custom-Code-Training

9. Microsoft Learn：Managed Compute overview  
   https://learn.microsoft.com/en-us/azure/foundry/concepts/managed-compute-overview

10. Microsoft Learn：Deploy open-source models with Managed Compute  
    https://learn.microsoft.com/en-us/azure/foundry/how-to/deploy-models-managed
<!-- SOURCE-END id=07 -->

---

<!-- SOURCE-BEGIN id=12 source=12_scaling_pitfalls_article.md sha256=3dfcf06afb8fde2f44477a8bdd008b19c4ede6ee2c0037f95450daef32367b65 body_sha256=09c34e91f64557201a2db576e5896f31122399d5a2b6f6b9fe2da2df10c3f722 -->
## 原稿 #12：跨机器性能对比，最容易踩的三个口径陷阱

> 两边的数字都是真的，方法也都没造假，结论却能差出好几倍。问题不在数据，在分母。









### 先看一个能把人绕进去的对话

甲方拿来一张表，说他们的平台在某个长上下文场景下能跑到 `X` tok/s。

乙方在自己的机器上测，跑到了 `0.98X`。

于是有人下结论：**两边性能基本持平。**

听起来没毛病。但如果甲方那个 `X` 是 **32 张卡的总吞吐除以 4** 得来的，而乙方的 `0.98X` 是 **8 张卡实测**，那这句"基本持平"就已经悄悄变成了另一句话：

```text
8 张卡 ≈ 32 张卡
```

没有人撒谎，没有人改数据。**方法是对的，口径错了。**

这类事在跨平台、跨团队、跨供应商的对比里非常常见。本文把最容易踩的三个口径陷阱拆开讲清楚。


### 陷阱一：归一化陷阱

#### 现象

一份报告里写着"单节点吞吐"，但这个数字并不是在单节点上测出来的，而是：

```text
单节点等效吞吐 = N 个节点的实测总吞吐 ÷ N
```

这是一种**合理且常见**的归一化做法。多节点部署下，模型权重是跨节点分片的，你没法只启动其中一个节点去单独测——它装不下完整模型。所以只能整套跑，再除以节点数。

问题不在这个做法本身，而在**它和真正的单节点实测长得一模一样**，都是一个 tok/s 数字。

#### 为什么这不等价

```text
真·单节点实测：
  一台机器独立完成全部工作，自给自足

N 节点归一化：
  N 台机器协同完成，再把功劳平摊
```

第二种情况里，那"一个节点份额"是**依赖另外 N-1 个节点存在才成立的**。你把它单独拎出来，它跑不了。

![原稿 #12 图 1](images/s12_12_scaling_pitfalls_article_img01.png)


#### 怎么识别

看到任何"单节点/单卡"数字，先问三个问题：

| 问题 | 为什么要问 |
|---|---|
| 这是实测还是折算？ | 折算数带着协同红利 |
| 折算的分母是多少？ | 除以 4 和除以 32 完全不是一回事 |
| 被折算的那套部署是什么形态？ | 拓扑不同，可比性不同 |

#### 正确的说法

不要说"我们和对方持平"，要说：

> 我们的单节点实测吞吐，约等于对方 N 节点总吞吐的 1/N。

多一句限定，结论就守得住。


### 陷阱二：外推陷阱

#### 现象

陷阱一的镜像版本。既然可以"总吞吐 ÷ N"，那反过来"单节点 × N"是不是也行？

```text
我们单节点跑 Y
所以 4 节点能跑 4Y
所以我们和对方 4 节点持平
```

**这一步是没有证据的。**

#### 扩展效率

定义一个系数：

```text
η = N 节点实测吞吐 / (N × 单节点实测吞吐)
```

只有 `η = 100%` 时，乘 `N` 才成立。

![原稿 #12 图 2](images/s12_12_scaling_pitfalls_article_img02.png)


现实中 `η` 通常小于 1，因为多节点会引入单节点不存在的成本：

- 跨节点集合通信（走网络，带宽比机内互联低一个数量级）
- MoE 的专家负载不均衡，快的等慢的
- KV 传输、Router 调度、连接建立
- Batch 不够大时，喂不饱更多的卡

但 `η` 也**不一定**小于 1。更大的显存池可能让 batch 开得更大，反而提升单卡利用率。所以**连方向都不能靠推理确定**，必须实测。

#### 一个公开旁证

DeepSeek 在公开的推理系统说明里提到，大规模跨节点专家并行会引入较大的通信开销，因此他们专门用**双 batch 重叠**来把通信藏到计算后面。

如果多节点扩展天然线性，就不需要为此专门设计机制了。

#### 正确的说法

> 我们目前只有单节点实测数据。多节点扩展效率尚未测量，不做线性外推。

这句话看起来是在示弱，实际上是在**保护自己**。因为一旦对方真的部署了多节点、发现达不到 `N` 倍，你之前所有的结论都会被一起推翻。


### 陷阱三：显存陷阱

这个最隐蔽，因为它违反直觉：**卡更多，可用显存反而可能更少。**

#### 权重复制税

同样是 32 张卡，有两种完全不同的用法：

**方案 A：4 套独立副本**

每台机器跑一份完整模型，前面挂个路由分发请求。

```text
每台机器都要装下完整权重
→ 权重被存了 4 份
```

**方案 B：一份模型摊在 32 卡上**

用 EP（专家并行）把权重跨节点分片。

```text
权重只存 1 份，摊薄到 32 张卡
```

#### 算一笔账

用公开数据举例。DeepSeek-V3 总参数 671B，FP8 权重约 `671 GB`；假设单卡显存 `141 GB`：

| | 总显存 | 权重占用 | 可用 KV | KV 占比 |
|---|---:|---:|---:|---:|
| A：4 套独立副本 | 4,512 GB | **2,684 GB**（4 份） | **1,828 GB** | 41% |
| B：EP32 单份分片 | 4,512 GB | **671 GB**（1 份） | **3,841 GB** | 85% |

**硬件完全相同，可用 KV 差 2.1 倍。**

![原稿 #12 图 3](images/s12_12_scaling_pitfalls_article_img03.png)


差的那 2,013 GB，全部变成了重复存放的模型权重。

#### 为什么这条如此致命

KV cache 的容量直接决定两件事：

```text
最大并发数    = KV 池容量 ÷ (上下文长度 × 每 token KV 大小)
最长上下文    受单个请求能否装进 KV 池限制
```

在长上下文场景下，KV 才是真正的瓶颈资源。权重多存三份，等于把一半以上的显存预算烧在了重复数据上。

#### 一个反直觉推论

假设有两种卡：甲卡 `192 GB`，乙卡 `141 GB`。

单看规格，甲卡显存多 36%。但如果甲卡只能跑"4 套独立副本"，而乙卡能跑"EP32 单份分片"：

| | 总显存 | 权重 | 可用 KV |
|---|---:|---:|---:|
| 甲卡 × 32（4 套副本） | 6,144 GB | 2,684 GB | **3,460 GB** |
| 乙卡 × 32（EP32 分片） | 4,512 GB | 671 GB | **3,841 GB** |

**总显存少 27% 的乙卡，可用 KV 反而多 11%。**

![原稿 #12 图 4](images/s12_12_scaling_pitfalls_article_img04.png)


所以在 MoE 大模型的多机部署里，**能不能跨节点分片权重，比单卡显存大小更重要**。这是软件栈能力问题，不是硬件参数问题。


### 三个陷阱的共同点

它们看起来是三件事，本质是同一件：

```text
分子都是真实测量值
分母被悄悄换掉了
```

| 陷阱 | 被换掉的分母 |
|---|---|
| 归一化 | 节点数（32 卡的成果，按 8 卡记账） |
| 外推 | 扩展效率（默认当成了 100%） |
| 显存 | 权重份数（当成了 1 份，实际 N 份） |

**任何比率，先问分母。** 这句话适用于吞吐对比，也适用于通过率、可用性、良品率、覆盖率。


### 一张交付前自检清单

写进任何对外材料之前，逐条过一遍：

```text
□ 每个数字标注了：实测 / 折算 / 推算
□ 折算数字写明了分母和被折算的部署形态
□ 没有出现未经实测的 "×N" 外推
□ 显存和并发的对比说明了权重存了几份
□ 两边的 GPU 数量、拓扑、并行方式写在同一张表里
□ 单次运行的结果没有被写成稳定结论
□ 不能确认的部分，明确标注为"未验证"而不是省略
```

最后一条最重要。**省略不是中立，省略是默认对自己有利。**


### 五句话记住

**第一句**：看到"单节点吞吐"，先问是实测还是总量除以节点数。

**第二句**：单节点乘 N 不等于 N 节点，扩展效率必须实测。

**第三句**：卡数相同，权重存 1 份还是 N 份，可用 KV 能差一倍以上。

**第四句**：三个陷阱的分子都是真的，问题都出在分母。

**第五句**：不确定的地方写"未验证"，比省略更安全。


### 写在最后

这三个陷阱都不是"有人想骗你"。恰恰相反，它们通常出现在**双方都很专业、都在认真做事**的场景里——因为归一化本身是合理的，外推是自然的，显存账是容易被忽略的。

真正的风险是：一句听起来没问题的结论，被写进材料、发给客户、进了商务流程，等到实际部署时才发现对不上。到那时，成本已经不是改一张表能覆盖的了。

**结论可以保守，口径必须精确。**


### 公开资料

- DeepSeek-V3/R1 推理系统概览（EP32/DP32 与 EP144/DP144 部署形态、双 batch 重叠）
- 本系列前作：《TP 和 EP 到底差在哪》——通信原语、top-k 与 `EP/TP = k/2` 教学模型

> 本文所有数值均为基于公开规格的算术示例，用于说明口径差异，不代表任何具体产品的实测性能。
<!-- SOURCE-END id=12 -->

---

## 本篇可逆合并账本

| 原稿 | 原始 SHA-256 | 正文 SHA-256 | 原图 |
|---:|---|---|---:|
| #3 `03_accuracy_chain_article.md` | `2b438f53e288f44b68762525dcf6f41f832fcf4589838fe68e42bfa555611de2` | `4309c579c94ab270782a93a097c085a2653e7bd9dd5e8e266bd7697e7489a157` | 7 |
| #6 `06_mtp_nongreedy_fix_article.md` | `34647915b90c67434549d968fc5a006c4c5238c67aea259950e12b16798ddde7` | `239fd92e8c84623b1c55ed4e8c48a5cf1ca63769d4a6ce12ba224837daea5355` | 12 |
| #7 `07_online_offline_rl_article.md` | `1ba5832338f6694084680e18c25648e4ef4d6ed08015d84b75dc547fbb264c36` | `83471988d18ce5d974c0641081178c11ff99c1ea763e9793102b76a4908152f5` | 12 |
| #12 `12_scaling_pitfalls_article.md` | `3dfcf06afb8fde2f44477a8bdd008b19c4ede6ee2c0037f95450daef32367b65` | `09c34e91f64557201a2db576e5896f31122399d5a2b6f6b9fe2da2df10c3f722` | 4 |

> 账本中的正文 SHA 对应“移除重复发布脚手架、抽取原图并提升标题层级”后的确定性正文。生成器会从本篇反向提取每个来源区间并逐字节比较；任一缺行、错序或缺图都会失败。
