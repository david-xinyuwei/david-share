# 5D KV Cache：精度、分页和显存布局不是一回事

> **系列**: DL-Algorithm-Insights | **作者**: 魏新宇 (Xinyu Wei)

**语言**: [English](README.md) | 中文

---

## 这是什么？

**一句话版本**：5D KV Cache 不是一种新精度，也不会凭空减少显存，它是一种面向特定 Attention kernel 的物理数据排布。

排查大模型推理配置时，这四个词常常一起出现：

```text
FP8 E4M3
PagedAttention
vectorized_5d
AITER / FlyDSL
```

它们很容易被当成同一项优化。实际上，这四个词分别回答四个不同问题：

| 概念 | 它回答的问题 |
|---|---|
| FP8、BF16 | 每个数用多少位保存，数值精度是多少？ |
| PagedAttention | KV Cache 如何分配、回收和映射？ |
| 5D layout | 一页 KV 数据在显存里按什么顺序排列？ |
| AITER、FlyDSL、FA3 | 哪个 kernel 读取并计算这些数据？ |

![四层概念](images/fig1-four-layers.png)

*图 1：四个词分别属于四个不同的层次*

---

## 为什么重要

把这四层混在一起，配置看似对了，实际可能走了慢路径；更糟的是，程序可以正常启动，但 kernel 读错物理布局。

布局读错不会抛异常，shape 也对得上，服务照常返回结果——只是算错了。这类问题不会在启动日志里报警，只会体现为精度莫名其妙地掉。

**范围声明**：**5D KV Cache 不是行业统一标准名。** 不同框架可能有不同的 5D 定义。本文分析的是公开 SGLang ROCm 实现 `878fff156` 中的 `SHUFFLE 5D` 快照，配置名为 `SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d`。所有结论都限定在这条实现路径内，不外推到其他框架、GPU 或 kernel。

---

## 先把几个词说清楚

全文绕不开几个英文词，先一次讲明白：

| 词 | 说的是什么 |
|---|---|
| **kernel** | GPU 上真正跑起来的那段程序。一次 Attention 计算，最终就是一个或几个 kernel 在跑 |
| **KV** | Key 和 Value，模型为每个 token 算出来、存起来备查的两组向量 |
| **layout** | 布局：数据在显存里按什么顺序摆（本文主题） |
| **page** | 页：把显存切成的固定大小的块，每块装固定数量的 token |
| **Prefill** | 预填充阶段：把输入的整段话一次性算完 |
| **Decode** | 解码阶段：一个字一个字往外生成 |
| **backend** | 后端：框架把某一步交给谁去算 |

---

## KV Cache 先解决什么问题

先打个比方。你参加一场长会议，每次发言前都要参考前面所有人说过的话。如果每次都靠回忆把整场会重新推演一遍，越往后越慢。正常做法是边听边记纪要，需要时直接翻。

KV Cache 就是这份纪要。

Transformer 每生成一个新 token，都要让当前 Query 与此前所有 token 的 Key、Value 做 Attention。如果每一步都重新计算历史 K/V，重复计算会越来越多。KV Cache 的做法很直接：每一层算完历史 token 的 K 和 V 后，把它们保存在显存里，后续解码直接读取。

代价是这份纪要会越记越厚，而且必须放在显存里。后面所有优化，本质都在回答三个问题：**用多大的字写、往哪儿放、按什么顺序摆。**

KV Cache 的容量可以粗略估算为：

```text
KV字节数 ≈ 层数 × token数 × 2（K和V）× KV head数 × head维度 × 每元素字节数
```

举一个纯算例，不对应某个具体模型：

```text
32层
128K token
8个KV heads
head_dim = 128
```

| 存储精度 | 每元素字节数 | KV Cache 容量 |
|---|---:|---:|
| BF16 | 2 | 约 16 GiB |
| FP8 | 1 | 约 8 GiB |

16 GiB 是什么概念？一张 80 GiB 的卡，光这一个长请求的 KV 就吃掉五分之一，而模型权重还没算。这就是为什么 KV Cache 的精度和摆法会被反复推敲。

这里把容量减半的是 **FP8**，不是 5D。

---

## 往哪儿放：PagedAttention 把显存切成标准房间

实际推理服务不能给每个请求预留一整块最大上下文显存。这就像开酒店不能因为客人"可能住三十天"就先锁死整层楼，而要按标准房间分配，再用登记表记录谁住哪几间。

PagedAttention 就是这套房间管理制度：把 KV 拆成固定大小的 page，再用页表把"某个请求的第 N 个逻辑页"映射到显存中的物理页。

为了建立直觉，可以把 Paged KV 的逻辑结构画成：

```text
[B, P, H, D]
```

- `B`：物理 page/block 数量
- `P`：每页容纳的 token 数
- `H`：KV head 数
- `D`：head 维度

这不是 PagedAttention 规定的统一物理 shape。真实实现可以是扁平 buffer 配合页表，也可以采用其他维度顺序。

到这里为止，显存已经切成一间间标准房，谁住哪几间也记清楚了。但还有一个问题没回答：**一间房里的东西，按什么顺序摆？**

---

## 按什么顺序摆：一页之内的 layout

Attention 刚算出的 K/V，最朴素的摆法是照着它算出来的样子摆：

```text
[N, H, D]
```

- `N`：token 数（源码里叫 `size`，即这块缓存能放多少个 token）
- `H`：KV head 数（`head_num`）
- `D`：每个 head 的维度（`head_dim`）

这三个字母连起来就是 **NHD**，也是源码里给这种布局起的名字。它的规则只有一句：**先把一个 token 的所有维度写完，再写下一个 token**。

NHD 不是唯一选择。同一批数据完全可以按别的顺序摆，元素一个不少，只是谁在前谁在后变了。本文要拆的 5D 就是另一种摆法。

再强调一遍这两层的分工：**PagedAttention 管页怎么来，layout 管页里怎么摆。** 两者相互独立，可以自由组合。

---

## "5D" 具体是哪五维

这条实现对 K 和 V 采用了不同的五维排布。

**K Cache**

```text
[B, H, D/X, P, X]
```

**V Cache**

```text
[B, H, P/X, Dv, X]
```

各维含义如下：

| 符号 | 含义 |
|---|---|
| `B` | page/block 数量 |
| `H` | KV head 数 |
| `P` | page size，即每页 token 数 |
| `D` / `Dv` | K 或 V 的 head 维度 |
| `X` | 最内层向量宽度 |

`X` 不是手工拍出来的参数。源码按 16 字节向量计算：

```text
X = 16 / 每元素字节数
```

可以把它想成叉车托盘：托盘宽度固定是 16 字节，箱子越小，一趟能装的箱子就越多。

| KV 存储类型 | 每元素字节数 | X |
|---|---:|---:|
| FP8 | 1 | 16 |
| BF16 / FP16 | 2 | 8 |

![向量宽度](images/fig3-vector-width.png)

*图 2：X 由 16 字节除以元素字节数决定*

假设 `page_size=64`、`head_dim=192`、KV 为 FP8，那么：

```text
K: [B, H, 12, 64, 16]
V: [B, H, 4, 192, 16]
```

可以直接验算：`192÷16=12`，所以 K 的第三维是 12；`64÷16=4`，所以 V 的第三维是 4。

K 和 V 的元素总数都没有变化：

```text
B × H × 192 × 64
```

变化的是地址顺序，而不是数据数量。

仓库里也是同一回事：同样一万箱货，按"先分订单号、再分品类"码放，和按"先分品类、再分订单号"码放，箱子一箱不多一箱不少，但拣货员跑动的距离可能差好几倍。

---

## 把规模缩到最小，看一遍真实地址

上面的参数太大，看不到顺序。把规模缩到能用眼睛数清的程度：

```text
4个token（page_size=4）
head_dim=4
X=2（为了看清楚，这里把向量宽度简化成2）
```

一共 `4 × 4 = 16` 个元素。NHD 的规则是"先把一个 token 写完"：

```text
地址： 0     1     2     3     4     5     6     7   ...
内容：t0d0  t0d1  t0d2  t0d3  t1d0  t1d1  t1d2  t1d3  ...
      \_____ token0 _____/ \_____ token1 _____/
```

5D 把 head_dim 拆成 `4 ÷ 2 = 2` 块，先把所有 token 的前两维写完，再写后两维：

```text
地址： 0     1     2     3     4     5     6     7
内容：t0d0  t0d1  t1d0  t1d1  t2d0  t2d1  t3d0  t3d1
      \________ 所有token的 d0、d1 ________/

地址： 8     9     10    11    12    13    14    15
内容：t0d2  t0d3  t1d2  t1d3  t2d2  t2d3  t3d2  t3d3
      \________ 所有token的 d2、d3 ________/
```

![NHD 与 5D 对比](images/fig2-nhd-vs-5d.png)

*图 3：同样 16 个元素，颜色代表 token，只有地址顺序变了*

两边都是 16 个元素，一个不多一个不少。变的只是谁挣到了哪个地址。

真实参数只是把这个规律放大：`X` 从 2 变成 16，`head_dim` 从 4 变成 192，`page_size` 从 4 变成 64，规则一模一样。

---

## 为什么 K 和 V 的 5D 形状不一样

Attention 包含两次主要矩阵运算：

```text
1. Q × Kᵀ → Attention scores
2. Softmax(scores) × V → 输出
```

两步访问 K 和 V 的模式不同。从公开源码的 shape 和索引公式看，这条实现采用了下面的设计：

- K 布局把 `head_dim` 拆成 `D/X` 和 `X`，让点积所需的 head 向量按固定宽度分块。
- V 布局把 page 内 token 位置拆成 `P/X` 和 `X`，让 Value 聚合可以按 token 块读取。

![K 与 V 的切法](images/fig4-k-vs-v.png)

*图 4：K 沿 head_dim 切，V 沿 token 位置切*

这里的 16 字节是该实现的存储向量合同，不应外推成所有 GPU、所有 kernel 统一的向量宽度。

源码中的写入 kernel 会把普通 `[N,H,D]` 的 K/V 按索引**打散写入**（scatter）到这两种物理布局。如果后续的读取方只接受线性布局，还得按同一套索引公式**再取回来**（gather）；能直接读 5D 的 kernel 则可以省掉这次还原。

打散写入和取回都不是零成本操作。频繁切换布局，会吃掉布局优化带来的收益。

这正是"layout 是数据合同"的含义：**shape 相同不代表物理含义相同，`view()` 也不能把 NHD 变成 SHUFFLE 5D。**

还是用仓库打比方：把货架标签从"A 区"改成"B 区"，货其实还在原地。拣货员照着新标签去取，拿到的是错的货，而且他不会报错，只会把错的货发出去。

`view()` 就是改标签。它只改变解释方式，不会执行真实的数据重排。

---

## 5D 为什么可能更快

5D layout 本身不减少 Attention 的数学运算量。它优化的是数据移动：

1. 最内层固定为 16 字节向量，便于 kernel 做向量化 load/store。
2. K 和 V 分别按消费方向排布，减少跨步读取。
3. 在这条 SGLang 实现中，5D pool 被交给 AITER CK `mha_batch_prefill_func` 和 `pa_decode_gluon` 原生消费。
4. 数据已经按 kernel 需要的形状保存，运行时不必反复重排（permute）或转置。

公开 SGLang 源码对这条集成路径的描述很直接：SHUFFLE 5D 让对应的 AITER Prefill 与 Paged Decode 读取方直接读物理缓存，并避免运行时重排。这里引用的是 SGLang 侧的数据合同，不代表所有 AITER 版本和所有 Attention 变体都具备相同支持。

这与 FlashAttention 强调的 IO-aware 原则是一致的：GPU Attention 的瓶颈不只在计算量，还在 HBM 显存与片上存储之间搬了多少数据、按什么顺序搬。

但“可能更快”不等于“在任何模型和硬件上都更快”。5D 是绑定后端的优化，收益取决于 GPU 架构、KV 数据类型、page size、head_dim、Attention 后端，以及是否存在能直接读它的 kernel。

没有匹配 kernel 时，结果取决于具体实现：非 AITER 后端会忽略该环境变量并保持 NHD；部分不兼容组合会在启动校验时失败；是否存在其他回退路径（fallback）必须以运行日志为准。

---

## 5D 和 FP8 为什么总是一起出现

在很多 AMD 推理配置里，下面几项常常成套出现：

```text
--kv-cache-dtype fp8_e4m3
SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d
--page-size 64
--attention-backend aiter
```

这不代表"5D 就是 FP8"。准确关系是：

```text
FP8 决定每个元素占 1 字节
5D 决定这些元素如何排列
page size 决定一页放多少 token
AITER/FlyDSL/Gluon 决定谁来读取
```

从内存池实现看，5D 同样允许 BF16/FP16，此时 `X=8`。真正的限制来自 kernel 支持矩阵：特定 GPU、dtype、head_dim 和 page size 的组合，是否有可以直接消费该布局的 kernel。

因此，把 KV 从 FP8 改回 BF16 时，不能只看服务能否启动，还要确认：

- `X` 是否从 16 正确变为 8
- page size 与 head_dim 是否仍可被 X 整除
- 实际加载的是哪个 Prefill/Decode kernel
- 是否发生静默回退
- 性能与数值结果是否重新验证

---

## 为什么 Target 用 5D，Draft 却可能用 NHD

投机解码里通常同时存在 Target 模型和 Draft 模型。它们不一定使用相同的 Attention kernel。

在本文分析的公开实现中：

```text
Target worker：AITER SHUFFLE 5D
Speculative draft worker：NHD
```

原因不是 Draft"不需要优化"，而是当时的 Multi-layer EAGLE Draft Extend 路径只理解普通 NHD 缓存。

继续用仓库的说法：Target 和 Draft 是两个拣货员，只有 Target 学过新货架的码货规则。强行让 Draft 也去新货架取货，他不会慢一点，而是会按老规矩数格子，搬回一堆错的箱子。

如果让 Draft 直接继承全局 5D 配置，它就会按 NHD 方式解释已经 shuffle 过的物理数据，结果不是变慢，而是 Attention 语义被破坏。

沿用前面那个极小例子就能看到后果。Draft 想取 token0 的完整向量，按 NHD 规则它会去读地址 0 到 3：

```text
它以为拿到的是：t0d0  t0d1  t0d2  t0d3
实际拿到的是：  t0d0  t0d1  t1d0  t1d1
                              ↑↑↑↑↑↑↑↑↑↑↑
                              这两个是token1的数据
```

![布局读错](images/fig5-wrong-layout.png)

*图 5：Draft 按 NHD 读 5D 数据，token1 的数据混了进来*

注意这里不会抛异常，shape 也对得上，服务照常返回结果——只是算错了。

源码因此给 Draft 单独覆盖为 NHD，同时让 Target 继续使用 5D。

这也是判断 layout 问题最实用的一条经验：**不要只看全局环境变量，要分别检查 Target 和 Draft 的实际布局。**

---

## 五个常见误区

| 误区 | 正确理解 |
|---|---|
| 5D 是一种量化格式 | 5D 是物理布局；FP8/BF16 才是数据类型 |
| 5D 会让 KV 容量减半 | FP8 让容量减半；5D 主要改变排列顺序 |
| PagedAttention 就是 5D | Paging 管理逻辑页和物理页；5D 管理页内布局 |
| 改一个环境变量就完成优化 | dtype、page、layout 和 kernel 必须形成闭合合同 |
| Target 和 Draft 一定共用布局 | 不一定；它们可能由不同 kernel 消费 |

---

## 如何确认运行时真的用了 5D

不要只检查启动脚本。至少核对四层证据：

| 层级 | 要确认什么 |
|---|---|
| 启动参数 | KV 数据类型、page size、Attention 后端 |
| 进程环境 | `SGLANG_AITER_KV_CACHE_LAYOUT` 的实际值 |
| 分配日志 | KV Cache 实际 dtype 和容量 |
| kernel 日志 | Target/Draft 布局与实际加载的 Prefill/Decode kernel |

一个通用的日志检查思路：

```bash
grep -E \
  'server_args=|KV Cache is allocated|SHUFFLE 5D|Using NHD|mha_batch_prefill|pa_decode' \
  server.log
```

如果只看到 `vectorized_5d` 环境变量，却没有匹配的 kernel 或 layout 日志，最多只能说明"请求了 5D"，不能证明"5D 路径已生效"。常见情况有两类：

- 后端不是 AITER，配置被忽略，内存池仍采用 NHD。
- dtype、page size 或 head_dim 不满足约束，服务在启动校验阶段失败。

服务能启动，也不代表一定命中了预期 kernel。最终仍要核对 kernel 加载日志和性能数据。

---

## 三句话记住 5D KV Cache

**What**：5D KV Cache 是把 Paged KV 按 page、head、向量块等五个轴重新排列的物理存储布局。

**Why**：它让特定 Attention kernel 按原生向量宽度连续读取 K/V，减少运行时重排和低效显存访问。

**Boundary**：它不等于 FP8、不天然节省容量，也不是跨 GPU、跨后端通用的标准格式。

---

## 复现本文配图

本文所有示意图都由脚本生成，可以自行修改参数重画：

```bash
pip install -r requirements.txt
python scripts/make_figures.py
```

图片会输出到 `images/`。脚本顶部的 `T`、`D`、`X` 控制那个极小例子的规模。

---

## 公开资料

本文的技术结论全部来自下列公开源码与论文，可逐条核对：

1. SGLang 公开源码：`vectorized_5d` 环境变量及 K/V shape
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/environ.py

2. SGLang 公开源码：5D 内存池分配与向量宽度 X
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/mem_cache/memory_pool.py

3. SGLang 公开源码：NHD 与 SHUFFLE 5D 的写入/还原索引
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/layers/attention/utils.py

4. SGLang 公开源码：Target 使用 5D、Draft 覆盖为 NHD
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/model_executor/model_runner_kv_cache_mixin.py

5. AITER：AMD 面向 ROCm 的高性能 AI 算子库
   https://github.com/ROCm/aiter

6. PagedAttention 论文：*Efficient Memory Management for Large Language Model Serving with PagedAttention*
   https://arxiv.org/abs/2309.06180

7. FlashAttention 论文：*Fast and Memory-Efficient Exact Attention with IO-Awareness*
   https://arxiv.org/abs/2205.14135
