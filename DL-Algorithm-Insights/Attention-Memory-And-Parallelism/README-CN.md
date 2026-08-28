# 从一块 KV Cache 到 32 张卡：把 Attention、5D 与 TP/DP/EP 一次讲全

[English Full Edition](M02_attention_memory_parallelism_full_article_EN.md) | 中文完整版

> 从 KV Cache 的 dtype、Paging 和页内 Layout 出发，走到 Flash/Paged Attention、TP/DP/EP、MiMo 192/128 与 TP8-interleaved checkpoint。

本文不新增 Benchmark 结果，不对 SHUFFLE 5D 作行业普遍性声明，不宣称 FP8 或任何 DSL 必然带来通用性能提升，也不宣称 MiMo `192/128` Kernel 已通过 NVIDIA CuTe DSL 实现或实测。

---

📌 **更多推理优化实践在 GitHub**

- **GitHub Repo**：<https://github.com/david-xinyuwei/david-share>
- **本系列**：`DL-Algorithm-Insights/`

---

*Author: 魏新宇 (Xinyu Wei) | Microsoft AI and Apps GBB Senior System Engineer*

---

## 怎么读这篇完整稿

这不是摘要版。下方每个“原稿章节”都保留对应旧稿的全部技术正文、表格、代码、公式、版本边界、误区、验证方法和参考来源。只删除重复的公众号引流、作者署名与横向分隔线；删除清单和逐图 SHA-256 记录在 `FULL_MERGE_LEDGER.md`。

本篇包含 6 张总览图和 49 张逐字节保留的原图。先用总览图建立位置感，再进入完整章节；总览图负责合并关系，细节图负责保留原始视觉信息，两者不互相替代。

## 六张总览图

![Attention 优化的五条正交轴](images/m02_fig1_five_axes.png)

*图 1：FP8、PagedAttention、5D、FlashAttention、TP/DP/EP 不是五个竞争方案，而是五条可以组合的设计轴。*

![MiMo Attention 的 128Q、8KV 与 192/128 非对称维度](images/m02_fig2_mimo_shape.png)

*图 2：GQA 的 128Q/8KV 决定 head ownership；K=192、V=128 决定 load、tile 和 fragment 合同。两者不能只用“有多少张 GPU”解释。*

![PagedAttention、NHD 与 SHUFFLE 5D 的职责边界](images/m02_fig3_paged_5d_flash.png)

*图 3：Paging、页内 Layout 与 FlashAttention 式计算是三层合同。`view()` 只能重新解释 shape，不能免费把 NHD 变成 SHUFFLE 5D。*

![TP、DP、EP 的切分对象和通信方向](images/m02_fig4_tp_dp_ep.png)

*图 4：TP 是“大家合做一份”，DP 是“每组各做不同请求”，EP 是“数据去找专家”。三者可以在同一批 GPU 上重叠建组。*

![TP8、DP4、EP32 的重叠通信组](images/m02_fig5_tp8_dp4_ep32.png)

*图 5：公共 Attention 路径在四个 DP 组中各保留完整 TP8；占模型权重大头的 384 个 experts 则由一个 EP32 域共同保存。*

![一个 token 的 Attention、EP 和 KV 路径](images/m02_fig6_token_journey.png)

*图 6：跨 EP 域的是 token hidden states，不是每层 KV Cache。KV 跟随请求归属；PD 分离时才发生独立的 KV 角色交接。*

---

## 完整技术正文


<!-- SOURCE-BEGIN id=01 source=5d_kv_cache_article.md sha256=271476111d1ac493e8fb7807fb434649048a7c1886f443e0c28225ff379cb9f1 body_sha256=6a1fbcddb29776a820efd4dd2f2a6933704047957288304dc591418510779845 -->
## 原稿 #1：5D KV Cache 到底是什么？别再把精度、分页和显存布局混在一起

> 5D KV Cache 不是一种新精度，也不会凭空减少显存。它是一种面向特定 Attention kernel 的物理数据排布。








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

![原稿 #1 图 1](images/s01_5d_kv_cache_article_img01.png)

把这四层混在一起，配置看似对了，实际可能走了慢路径；更糟的是，程序可以正常启动，但 kernel 读错物理布局。

这篇只讲第一件事：**5D KV Cache 到底是什么。**

### KV Cache 先解决什么问题

先打个比方。你参加一场长会议，每次发言前都要参考前面所有人说过的话。如果每次都靠回忆把整场会重新推演一遍，越往后越慢。正常做法是边听边记纪要，需要时直接翻。

KV Cache 就是这份纪要。

Transformer 每生成一个新 token，都要让当前 Query 与此前所有 token 的 Key、Value 做 Attention。如果每一步都重新计算历史 K/V，重复计算会越来越多。

KV Cache 的做法很直接：每一层算完历史 token 的 K 和 V 后，把它们保存在显存里，后续解码直接读取。

代价是这份纪要会越记越厚，而且必须放在显存里。后面所有优化，本质都在回答三个问题：用多大的字写、往哪儿放、按什么顺序摆。

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

| 存储精度 | 每元素字节数 | KV Cache容量 |
|---|---:|---:|
| BF16 | 2 | 约16 GiB |
| FP8 | 1 | 约8 GiB |

16 GiB是什么概念？一张80 GiB的卡，光这一个长请求的KV就吃掉五分之一，而模型权重还没算。这就是为什么KV Cache的精度和摆法会被反复推敲。

这里把容量减半的是 **FP8**，不是5D。

### 往哪儿放：PagedAttention 把显存切成标准房间

实际推理服务不能给每个请求预留一整块最大上下文显存。这就像开酒店不能因为客人“可能住三十天”就先锁死整层楼，而要按标准房间分配，再用登记表记录谁住哪几间。

PagedAttention 就是这套房间管理制度：把KV拆成固定大小的page，再用页表把“某个请求的第N个逻辑页”映射到显存中的物理页。

为了建立直觉，可以把Paged KV的逻辑结构画成：

```text
[B, P, H, D]
```

- `B`：物理page/block数量
- `P`：每页容纳的token数
- `H`：KV head数
- `D`：head维度

这不是PagedAttention规定的统一物理shape。真实实现可以是扁平buffer配合页表，也可以采用其他维度顺序。

到这里为止，显存已经切成一间间标准房，谁住哪几间也记清楚了。但还有一个问题没回答：**一间房里的东西，按什么顺序摆？**

### 按什么顺序摆：一页之内的 layout

Attention刚算出的K/V，最朴素的摆法是照着它算出来的样子摆：

```text
[N, H, D]
```

- `N`：token 数（源码里叫 `size`，即这块缓存能放多少个 token）
- `H`：KV head 数（`head_num`）
- `D`：每个 head 的维度（`head_dim`）

这三个字母连起来就是 **NHD**，也就是源码里给这种布局起的名字。它的规则只有一句：**先把一个 token 的所有维度写完，再写下一个 token**。

NHD不是唯一选择。同一批数据完全可以按别的顺序摆，元素一个不少，只是谁在前谁在后变了。本文要拆的 5D 就是另一种摆法。

再强调一遍这两层的分工：**PagedAttention 管页怎么来，layout 管页里怎么摆。** 两者相互独立，可以自由组合。

### “5D”具体是哪五维

先说明边界：**5D KV Cache不是行业统一标准名。** 不同框架可能有不同的5D定义。本文分析的是公开SGLang ROCm实现 `878fff156` 中的 `SHUFFLE 5D` 快照，配置名为：

```text
SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d
```

这条实现对K和V采用了不同的五维排布。

#### K Cache

```text
[B, H, D/X, P, X]
```

#### V Cache

```text
[B, H, P/X, Dv, X]
```

各维含义如下：

| 符号 | 含义 |
|---|---|
| `B` | page/block数量 |
| `H` | KV head数 |
| `P` | page size，即每页token数 |
| `D` / `Dv` | K或V的head维度 |
| `X` | 最内层向量宽度 |

`X`不是手工拍出来的参数。源码按16字节向量计算：

```text
X = 16 / 每元素字节数
```

可以把它想成叉车托盘：托盘宽度固定是16字节，箱子越小，一趟能装的箱子就越多。

因此：

| KV存储类型 | 每元素字节数 | X |
|---|---:|---:|
| FP8 | 1 | 16 |
| BF16 / FP16 | 2 | 8 |

![原稿 #1 图 2](images/s01_5d_kv_cache_article_img02.png)

假设 `page_size=64`、`head_dim=192`、KV为FP8，那么：

```text
K: [B, H, 12, 64, 16]
V: [B, H, 4, 192, 16]
```

可以直接验算：`192÷16=12`，所以K的第三维是12；`64÷16=4`，所以V的第三维是4。

K和V的元素总数都没有变化：

```text
B × H × 192 × 64
```

变化的是地址顺序，而不是数据数量。

仓库里也是同一回事：同样一万箱货，按“先分订单号、再分品类”码放，和按“先分品类、再分订单号”码放，箱子一箱不多一箱不少，但拣货员跑动的距离可能差好几倍。

### 把规模缩到最小，看一遍真实地址

上面的参数太大，看不到顺序。把规模缩到能用眼睛数清的程度：

```text
4个token（page_size=4）
head_dim=4
X=2（为了看清楚，这里把向量宽度简化成2）
```

一共 `4 × 4 = 16` 个元素。NHD的规则是“先把一个token写完”：

```text
地址： 0     1     2     3     4     5     6     7   ...
内容：t0d0  t0d1  t0d2  t0d3  t1d0  t1d1  t1d2  t1d3  ...
      \_____ token0 _____/ \_____ token1 _____/
```

5D把head_dim拆成 `4 ÷ 2 = 2` 块，先把所有token的前两维写完，再写后两维：

```text
地址： 0     1     2     3     4     5     6     7
内容：t0d0  t0d1  t1d0  t1d1  t2d0  t2d1  t3d0  t3d1
      \________ 所有token的 d0、d1 ________/

地址： 8     9     10    11    12    13    14    15
内容：t0d2  t0d3  t1d2  t1d3  t2d2  t2d3  t3d2  t3d3
      \________ 所有token的 d2、d3 ________/
```

![原稿 #1 图 3](images/s01_5d_kv_cache_article_img03.png)

两边都是16个元素，一个不多一个不少。变的只是谁挣到了哪个地址。

真实参数只是把这个规律放大：`X`从2变成16，`head_dim`从4变成192，`page_size`从4变成64，规则一模一样。

### 为什么K和V的5D形状不一样

Attention包含两次主要矩阵运算：

```text
1. Q × Kᵀ → Attention scores
2. Softmax(scores) × V → 输出
```

两步访问K和V的模式不同。从公开源码的shape和索引公式看，这条实现采用了下面的设计：

- K布局把 `head_dim` 拆成 `D/X` 和 `X`，让点积所需的head向量按固定宽度分块。
- V布局把page内token位置拆成 `P/X` 和 `X`，让Value聚合可以按token块读取。

![原稿 #1 图 4](images/s01_5d_kv_cache_article_img04.png)

这里的16字节是该实现的存储向量合同，不应外推成所有GPU、所有kernel统一的向量宽度。

源码中的写入kernel会把普通 `[N,H,D]` K/V scatter到这两种物理布局。如果后续consumer只接受线性布局，还需要按同一索引公式gather回来；能原生消耹5D的kernel则可以省掉这次还原。

scatter和gather都不是零成本操作。频繁切换layout，会吃掉布局优化带来的收益。

这正是“layout是数据合同”的含义：**shape相同不代表物理含义相同，`view()`也不能把NHD变成SHUFFLE 5D。**

还是用仓库打比方：把货架标签从“A区”改成“B区”，货其实还在原地。拣货员照着新标签去取，拿到的是错的货，而且他不会报错，只会把错的货发出去。

`view()`就是改标签。它只改变解释方式，不会执行真实的数据重排。

### 5D为什么可能更快

5D layout本身不减少Attention的数学运算量。它优化的是数据移动：

1. 最内层固定为16字节向量，便于kernel做向量化load/store。
2. K和V分别按消费方向排布，减少跨步读取。
3. 在这条SGLang实现中，5D pool被交给AITER CK `mha_batch_prefill_func`和 `pa_decode_gluon`原生消费。
4. 数据已经按kernel需要的形状保存，运行时不必反复permute或transpose。

公开SGLang源码对这条集成路径的描述很直接：SHUFFLE 5D让对应的AITER Prefill与Paged Decode consumer读取物理缓存，并避免运行时permute。这里引用的是SGLang侧的数据合同，不代表所有AITER版本和所有Attention变体都具备相同支持。

这与FlashAttention强调的IO-aware原则是一致的：GPU Attention的瓶颈不只在计算量，还在HBM显存与片上存储之间搬了多少数据、按什么顺序搬。

但“可能更快”不等于“在任何模型和硬件上都更快”。5D是backend-specific优化，收益取决于：

- GPU架构
- KV dtype
- page size
- head_dim
- Attention backend
- 是否存在匹配的consumer kernel

没有匹配kernel时，结果取决于具体实现：非AITER backend会忽略该环境变量并保持NHD；部分不兼容组合会在启动校验时失败；是否存在其他fallback必须以运行日志为准。

### 5D和FP8为什么总是一起出现

在很多AMD推理配置里，下面几项常常成套出现：

```text
--kv-cache-dtype fp8_e4m3
SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d
--page-size 64
--attention-backend aiter
```

这不代表“5D就是FP8”。准确关系是：

```text
FP8决定每个元素占1字节
5D决定这些元素如何排列
page size决定一页放多少token
AITER/FlyDSL/Gluon决定谁来读取
```

从内存池实现看，5D同样允许BF16/FP16，此时 `X=8`。真正的限制来自kernel支持矩阵：特定GPU、dtype、head_dim和page size的组合，是否有可以直接消费该布局的kernel。

因此，把KV从FP8改回BF16时，不能只看服务能否启动，还要确认：

- `X`是否从16正确变为8
- page size与head_dim是否仍可被X整除
- 实际加载的是哪个Prefill/Decode kernel
- 是否发生静默回退
- 性能与数值结果是否重新验证

### 为什么Target用5D，Draft却可能用NHD

投机解码里通常同时存在Target模型和Draft模型。它们不一定使用相同的Attention kernel。

在本文分析的公开实现中：

```text
Target worker：AITER SHUFFLE 5D
Speculative draft worker：NHD
```

原因不是Draft“不需要优化”，而是当时的Multi-layer EAGLE Draft Extend路径只理解普通NHD缓存。

继续用仓库的说法：Target和Draft是两个拣货员，只有Target学过新货架的码货规则。强行让Draft也去新货架取货，他不会慢一点，而是会按老规矩数格子，搬回一堆错的箱子。

如果让Draft直接继承全局5D配置，它就会按NHD方式解释已经shuffle过的物理数据，结果不是变慢，而是Attention语义被破坏。

沿用前面那个极小例子就能看到后果。Draft想取token0的完整向量，按NHD规则它会去读地址0到3：

```text
它以为拿到的是：t0d0  t0d1  t0d2  t0d3
实际拿到的是：  t0d0  t0d1  t1d0  t1d1
                              ↑↑↑↑↑↑↑↑↑↑↑
                              这两个是token1的数据
```

![原稿 #1 图 5](images/s01_5d_kv_cache_article_img05.png)

注意这里不会抛异常，shape也对得上，服务照常返回结果——只是算错了。

源码因此给Draft单独覆盖为NHD，同时让Target继续使用5D。

这也是判断layout问题最实用的一条经验：**不要只看全局环境变量，要分别检查Target和Draft的实际布局。**

### 五个常见误区

| 误区 | 正确理解 |
|---|---|
| 5D是一种量化格式 | 5D是物理布局；FP8/BF16才是数据类型 |
| 5D会让KV容量减半 | FP8让容量减半；5D主要改变排列顺序 |
| PagedAttention就是5D | Paging管理逻辑页和物理页；5D管理页内布局 |
| 改一个环境变量就完成优化 | dtype、page、layout和kernel必须形成闭合合同 |
| Target和Draft一定共用布局 | 不一定；它们可能由不同kernel消费 |

### 如何确认运行时真的用了5D

不要只检查启动脚本。至少核对四层证据：

| 层级 | 要确认什么 |
|---|---|
| 启动参数 | KV dtype、page size、Attention backend |
| 进程环境 | `SGLANG_AITER_KV_CACHE_LAYOUT`的实际值 |
| 分配日志 | KV Cache实际dtype和容量 |
| kernel日志 | Target/Draft布局与实际加载的Prefill/Decode kernel |

一个通用的日志检查思路：

```bash
grep -E \
  'server_args=|KV Cache is allocated|SHUFFLE 5D|Using NHD|mha_batch_prefill|pa_decode' \
  server.log
```

如果只看到 `vectorized_5d` 环境变量，却没有匹配的kernel或layout日志，最多只能说明“请求了5D”，不能证明“5D路径已生效”。常见情况有两类：

- backend不是AITER，配置被忽略，内存池仍采用NHD。
- dtype、page size或head_dim不满足约束，服务在启动校验阶段失败。

服务能启动，也不代表一定命中了预期kernel。最终仍要核对kernel加载日志和性能数据。

### 三句话记住5D KV Cache

**What**：5D KV Cache是把Paged KV按page、head、向量块等五个轴重新排列的物理存储布局。

**Why**：它让特定Attention kernel按原生向量宽度连续读取K/V，减少运行时重排和低效显存访问。

**Boundary**：它不等于FP8、不天然节省容量，也不是跨GPU、跨backend通用的标准格式。

### 公开资料

1. SGLang公开源码：`vectorized_5d`环境变量及K/V shape  
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/environ.py

2. SGLang公开源码：5D内存池分配与向量宽度X  
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/mem_cache/memory_pool.py

3. SGLang公开源码：NHD与SHUFFLE 5D的写入/还原索引  
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/layers/attention/utils.py

4. SGLang公开源码：Target使用5D、Draft覆盖为NHD  
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/model_executor/model_runner_kv_cache_mixin.py

5. AITER：AMD面向ROCm的高性能AI算子库  
   https://github.com/ROCm/aiter

6. PagedAttention论文：*Efficient Memory Management for Large Language Model Serving with PagedAttention*  
   https://arxiv.org/abs/2309.06180

7. FlashAttention论文：*Fast and Memory-Efficient Exact Attention with IO-Awareness*  
   https://arxiv.org/abs/2205.14135
<!-- SOURCE-END id=01 -->

---

<!-- SOURCE-BEGIN id=04 source=04_paged_flash_aiter_article.md sha256=ebf09f31954ddbff777cee87d13e1b9335cd5932b2aef72a4d060099dff2c662 body_sha256=d69c2f45097c1b02bc86aa4117eadf7ff6300b2781519cd9d5d2a75ef035be92 -->
## 原稿 #4：从 PagedAttention 到 FlashAttention

> 这两个名字几乎总是一起出现，却在解决完全不同的问题。先分清它们的分工，才能看懂配置里的 FA3、FlashInfer、AITER、Triton 到底在选什么。








先给结论：

```text
FlashAttention：怎么把 Attention 算得更快、更省中间显存
PagedAttention：历史 K/V 分页存放时，怎么找到它们并算完
算子库：AITER、FlashInfer 等，把上面两类能力做成可调用的 kernel
```

它们不是三个互斥选项，也不是一条简单的父子关系。

![原稿 #4 图 1](images/s04_04_paged_flash_aiter_article_img01.png)


### 先用一个比方建立直觉

正式拆解之前，先用点菜打个比方。后面所有细节都能挂在这个框架上。

![原稿 #4 图 2](images/s04_04_paged_flash_aiter_article_img02.png)

在餐厅点一份宏保鸡丁：食材是鸡丁、花生、辣椒，菜名就是宏保鸡丁，端上来还是那盘宏保鸡丁。变的只有中间那段：谁炒、切多大块、什么火候、多快上菜。

注意力这件事，结构完全相同：

| 餐厅 | 注意力 | 变不变 |
|---|---|---|
| 食材：鸡丁、花生、辣椒 | 输入：Q、K、V | 不变 |
| 菜名：宏保鸡丁 | 要算的东西：Attention 公式 | 不变 |
| 端上来那盘菜 | 输出：O | 不变，数值等价 |
| 谁炒、怎么炒、多快端上来 | 哪个 backend、怎么算、多久算完 | 可以完全不同 |

这就是全文的主线：**Q、K、V 进去，O 出来，这份合同从头到尾不变；而中间“怎么做出来”，有非常多种写法。**

FlashAttention 论文把这个性质称为 exact attention（精确注意力）——算出来的结果与标准做法一致，只是更快。所以后面出现的 PagedAttention、AITER、FlashInfer 以及各种 backend，改的都是做法，不是输入，也不是结果。


### 先把几个词说清楚

| 词 | 说的是什么 |
|---|---|
| **Attention** | 注意力计算，根据 Query 与 Key 的相关性，对 Value 加权求和 |
| **Q / K / V** | Query（查询）、Key（键）、Value（值）三组向量 |
| **KV Cache** | Key/Value Cache（键值缓存），保存历史 token 的 K/V 供后续解码使用 |
| **FA** | FlashAttention，I/O-aware（Input/Output-aware，感知输入输出数据搬运）的精确 Attention 算法 |
| **PA** | PagedAttention，让 Attention 按页表读取分页 KV Cache 的算法与执行方式 |
| **kernel** | GPU 上实际执行的一段计算程序 |
| **CUDA** | Compute Unified Device Architecture，NVIDIA 的 GPU 编程平台 |
| **HIP** | Heterogeneous-compute Interface for Portability，AMD ROCm 上与 CUDA 写法接近的 C++ 编程接口 |
| **HBM** | High Bandwidth Memory（高带宽显存），容量较大但离计算单元较远 |
| **SRAM** | Static Random-Access Memory（静态随机存储器），GPU 片上容量较小但速度更快 |
| **AITER** | AMD 的 ROCm 高性能 AI（Artificial Intelligence，人工智能）算子库。官方 README 称 AI Tensor Engine for ROCm，官方文档也使用 AMD Inference and Training Enhanced Repository 这一展开 |
| **FlashInfer** | NVIDIA 平台上面向推理的算子库与 kernel 生成器 |
| **backend** | 后端，此处指统一接口下可替换的具体实现，与网页开发的前后端无关 |
| **JIT** | Just-In-Time（即时编译），运行时才生成并编译具体代码 |
| **ROCm** | Radeon Open Compute，AMD 的 GPU 软件平台 |


### 三者共同的起点：Attention 公式

标准缩放点积 Attention 可以写成：

$$
O = \operatorname{softmax}\left(\frac{QK^\mathsf{T}}{\sqrt{d}}\right)V
$$

它分三步：

1. 计算 $QK^\mathsf{T}$，得到 Attention scores（注意力分数）。
2. 对每一行做 Softmax，得到概率。
3. 概率再乘 $V$，得到输出 $O$。

![原稿 #4 图 3](images/s04_04_paged_flash_aiter_article_img03.png)

FlashAttention 和 PagedAttention 都不改变这条数学公式。区别在于，它们解决公式落到 GPU 上时的不同工程问题。


### FlashAttention：不要把完整注意力矩阵搬来搬去

假设序列长度是 $N$，完整的 $QK^\mathsf{T}$ 矩阵有 $N \times N$ 个元素。

传统实现可能把这张大矩阵写入 HBM，随后再读取它做 Softmax，然后再次读取概率矩阵与 $V$ 相乘。长序列下，大量时间花在显存读写，而不只是乘加计算。

FlashAttention 的核心做法是：

```text
Q、K、V 分成小块
      ↓
把当前小块搬进片上存储
      ↓
计算局部 QKᵀ
      ↓
使用 online Softmax 更新行最大值、指数和与输出
      ↓
处理下一块，不保存完整注意力矩阵
```

![原稿 #4 图 4](images/s04_04_paged_flash_aiter_article_img04.png)

这里的 online Softmax（在线 Softmax）很关键。普通 Softmax 似乎必须看到整行才能得到最大值和分母；在线算法维护运行中的最大值与指数和，因此可以分块处理，最后仍得到数学上等价的精确 Attention 结果。

FlashAttention 主要减少：

- HBM 与片上存储之间的数据搬运
- 完整 Attention 矩阵的中间存储
- 多个独立 kernel 之间的读写开销

所以它回答的是：

> **Q、K、V 已经给我了，如何把 Attention 算得更快、更省临时显存？**

它可以用于训练，也可以用于推理的 Prefill（预填充）阶段；这些场景并不要求存在历史 KV Cache。


### FlashAttention 不是一个版本，而是四代

只说“用了 FlashAttention”通常不够精确。官方仓库里已经有四代，各自解决的瓶颈并不相同。

| 代次 | 主要解决什么 | 关键手段 |
|---|---|---|
| FlashAttention（2022） | HBM 读写太多 | 分块、在线 Softmax、反向重算 |
| FlashAttention-2（2023） | 并行度与工作划分不足 | 重排循环、改进线程束之间的任务切分 |
| FlashAttention-3（2024） | FA2 在 H100 上只用到约 35% 峰值算力 | 利用 Hopper 的异步能力与低精度 |
| FlashAttention-4 | 面向更新的硬件 | 用 CuTeDSL 重写，覆盖 Hopper 与 Blackwell |

![原稿 #4 图 5](images/s04_04_paged_flash_aiter_article_img05.png)

FA3 的三项核心手段值得单独记住：

1. **异步与 warp specialization（线程束分工）**：让一部分线程束专门搬数据、另一部分专门算矩阵，利用 TMA（Tensor Memory Accelerator，张量内存加速器）与 WGMMA（Warpgroup Matrix Multiply-Accumulate，线程束组矩阵乘加）的异步特性。
2. **GEMM 与 Softmax 重叠**：矩阵乘走 Tensor Core，指数运算走多功能单元，两者吞吐差距很大，所以让它们并行，而不是排队。
3. **低精度误差控制**：FP8 下采用 incoherent processing（非相干处理），用 Hadamard 变换把离群值“摊开”，降低量化误差。

官方公开数据：FP16 相比 FA2 提速约 1.5–2.0 倍，达到约 740 TFLOPS；FP8 接近 1.2 PFLOPS，数值误差约为基线 FP8 attention 的 1/2.6。

必须同时记住边界：官方 README 把 FA3 标为 beta，并写明要求 H100 / H800 与 CUDA 12.3 以上。所以“FA3 更快”是有硬件前提的，不能直接外推到任意 GPU。


### PagedAttention：历史 K/V 不必连续放在显存里

在线推理解码时，每个请求的 KV Cache 会不断增长，而且不同请求长度不同、结束时间不同。

如果为每个请求预留一整块最大长度的连续显存，会产生大量浪费：

```text
请求 A：实际 700 token，却预留 32K
请求 B：实际 8K token，却预留 32K
请求 C：生成结束，留下中间空洞
```

PagedAttention 借鉴操作系统虚拟内存，把 KV Cache 切成固定大小的 Page（页）。

```text
请求的逻辑页：0 → 1 → 2 → 3
                 │   │   │   │
页表映射         ▼   ▼   ▼   ▼
物理页：        17   4  29   8
```

![原稿 #4 图 6](images/s04_04_paged_flash_aiter_article_img06.png)

请求看到的是连续的逻辑 token，实际物理页可以分散在显存任何位置。页表记录逻辑页到物理页的映射。

这样可以：

- 按需增加 KV Cache，而不是一次预留最大长度
- 回收已结束请求的页面
- 减少外部碎片
- 在请求或候选序列之间共享页面

但 PagedAttention 不只是一个“内存分配器”。真正计算时，Attention kernel 必须理解页表：根据当前 token 的逻辑位置找到物理页，从页中读取 K/V，再完成 Attention。

所以它回答的是：

> **历史 K/V 分散在很多物理页里，如何直接找到并使用它们完成 Attention？**


### 两者怎么上下游配合

从推理服务的控制流程看，PagedAttention 位于上游，FlashAttention 式计算位于下游：

```text
新 token 产生 K/V
        ↓
缓存分配器申请 Page，更新页表
        ↓
下一步生成 Query
        ↓
Paged kernel 按页表定位历史 K/V
        ↓
分块计算 QKᵀ → online Softmax → 乘 V
        ↓
输出进入下一层，新 K/V 再写回 Page
```

![原稿 #4 图 7](images/s04_04_paged_flash_aiter_article_img07.png)

但高性能实现通常不会真的执行：

```text
先把所有分页 K/V 拼成连续张量
再调用普通 FlashAttention
```

这样会增加一次大规模 gather（收集）和显存拷贝，抵消分页收益。

更常见的做法是把两类思想融合进同一个 kernel：

1. 读取页表，得到物理 Page 编号。
2. 分块加载该页的 K/V。
3. 计算局部 $QK^\mathsf{T}$。
4. 使用在线 Softmax 更新全局状态。
5. 将局部概率乘 $V$ 并更新输出累加器。
6. 转到下一页，直到遍历完上下文。

因此，二者更准确的关系是：

> **PagedAttention 提供“分页寻址合同”；FlashAttention 提供“分块计算和在线归一化方法”。Paged kernel 可以同时实现这两套思想。**


### 不是所有 FlashAttention kernel 都能直接读取 Page

这一点很重要。

普通 FlashAttention kernel 通常接收连续或规则步长的 Q/K/V 张量。分页 KV Cache 还需要：

- block table（块表）
- context lengths（上下文长度）
- Page 大小
- 每个 Page 的物理编号
- 可能存在的量化 scale（缩放因子）

如果 kernel 没有这些输入，它就不认识页表。

此时只有两种选择：

```text
方案 A：先 gather 成连续 K/V，再调用普通 FlashAttention
方案 B：使用原生支持 Page Table 的 Paged Attention kernel
```

![原稿 #4 图 8](images/s04_04_paged_flash_aiter_article_img08.png)

方案 A 更通用，但多一次整理和拷贝；方案 B 更高效，但 kernel 必须和 Page 大小、KV layout、数据类型等合同匹配。

所以“用了 FlashAttention”不能自动推出“支持 Paged KV”；“用了 PagedAttention”也不能自动推出“使用官方 FlashAttention 实现”。


### Prefill 和 Decode 为什么常走不同路径

#### Prefill：一次处理很多 Query

Prefill 需要处理整段输入，Q 往往有很多行。此时大矩阵计算占比高，FlashAttention 式分块计算非常合适。

#### Decode：每个请求通常只有一个新 Query

Decode 每一步对每个请求通常只有一个新 Query，却要读取整段历史 KV Cache。此时：

- $QK^\mathsf{T}$ 的矩阵形状更瘦
- 历史 K/V 读取占比更高
- 多请求的 Page Table 访问变得重要

因此在线服务常见：

```text
Prefill：Dense / Ragged FlashAttention 风格 kernel
Decode：Paged Attention kernel
```

把三个阶段摊开看，分工更清楚：

| | 训练 | 推理 Prefill | 推理 Decode |
|---|---|---|---|
| FlashAttention 式计算 | 常用 | 常用 | 可用，需要带 KV Cache 的变体 |
| PagedAttention | 一般不涉及 | 可用于前缀复用与分块预填充 | 主要战场 |

这不是硬规则。具体框架可以提供支持 Paged KV 的 Prefill，也可以提供带 KV Cache 的 FlashAttention 变体。关键仍是实际 kernel 接口和运行日志。


### AITER 在这张图里是什么

AITER 既不是新的 Attention 数学公式，也不是 KV Cache 管理机制。

AITER 是 AMD 的高性能 AI 算子库，面向 ROCm 提供生产级 GPU kernel。官方列出的能力包括：

- Multi-Head Attention（多头注意力）
- Multi-Latent Attention（多潜变量注意力）
- Paged Attention
- GEMM（通用矩阵乘）
- Mixture of Experts（混合专家）
- 归一化、量化和通信算子

![原稿 #4 图 9](images/s04_04_paged_flash_aiter_article_img09.png)

AITER 内部可以同时使用多种实现技术：

```text
AITER 算子库
├─ Composable Kernel（CK）C++ 模板
├─ Triton
├─ Gluon
├─ FlyDSL
└─ 手写汇编
```

这几个名字分别是什么、各自出自哪家，后面会专门列表说清楚。

所以：

- `--attention-backend aiter` 表示让框架使用 AITER 提供的 Attention 路径。
- `pa_decode_gluon` 表示 AITER 中一套用 Gluon 实现的 Paged Decode kernel。
- 另一条 AITER 路径也可能使用 CK、Triton、FlyDSL 或汇编。

AITER 的角色是：

> **把适合 AMD GPU 的 FA、PA、GEMM、MoE 等具体 kernel 实现组织成一个算子库，供 SGLang、vLLM 等推理框架调用。**


### 看一眼真实 AITER Paged Decode kernel

AITER 公开的 `pa_decode_gluon` 源码把上下游关系写得很清楚。它同时接收：

```text
query
key_cache / value_cache
block_tables
context_lengths
```

kernel 内部执行：

```text
读取 block_tables
→ 得到物理 Page 编号
→ 分块加载 K/V
→ 计算 QK scores
→ 在线更新最大值和指数和
→ 计算概率 × V
→ 输出结果
```

![原稿 #4 图 10](images/s04_04_paged_flash_aiter_article_img10.png)

也就是说，这不是“先 PA、后 FA”两个独立程序，而是一个 Paged Decode kernel 同时完成：

- PagedAttention 的页表寻址
- FlashAttention 式的分块计算与在线 Softmax
- AMD Instinct GPU 上的矩阵指令调度

这正是二者在真实系统里的融合方式。


### 同一层还有 FlashInfer

只讲 AITER，容易让人误以为“算子库”是 AMD 特有的东西。NVIDIA 侧的同层角色是 FlashInfer。

它的官方定位是一句很关键的话：**a library and kernel generator for inference**（面向推理的库与 kernel 生成器），为 Attention、GEMM 和 MoE 提供统一 API。

![原稿 #4 图 11](images/s04_04_paged_flash_aiter_article_img11.png)

三个值得记住的点。

**第一，它明确说自己有多个后端实现。** 官方 README 列出的后端包括 FlashAttention-2/3、cuDNN、CUTLASS 和 TensorRT-LLM。也就是说，调用 FlashInfer 的 Attention 接口，底下真正跑的可能就是 FA2 或 FA3 的实现。库调用算法实现，这层关系是官方写明的。

**第二，它用块稀疏（block-sparse）格式统一表达 KV Cache。** 论文的做法是把存储形态各异的 KV Cache 都表示成块稀疏矩阵与可组合格式，再配合 JIT 编译生成对应 kernel。分页 KV 在这个视角下不是特例，而是块稀疏的一种。

**第三，它同样覆盖 Prefill、Decode 与 Append 三类场景**，并提供 POD-Attention 这种把 prefill 与 decode 融合到一起的 kernel。所以前面说的“Prefill 与 Decode 常走不同 kernel”是常见做法，不是必然结构。

和 AITER 对照着看，层级关系就很清楚：

| | AITER | FlashInfer |
|---|---|---|
| 定位 | 算子库 | 库与 kernel 生成器 |
| 平台 | AMD ROCm | NVIDIA，Turing 到 Blackwell |
| 内部实现技术 | CK、Triton、Gluon、FlyDSL、HIP、汇编 | CUDA C++、Python JIT，Blackwell 上还有 CuTe DSL |
| 是否包含分页 Attention | 是 | 是，以块稀疏格式表达 |
| 是否是一种 Attention 算法 | 否 | 否 |

两者都不是“第三种 Attention 算法”，而是把 FA 式计算与 PA 式寻址落到具体硬件上的工程载体。


### 这些 kernel 到底是用什么写的

最常被问的一个问题：这两样东西是用 Triton 写的，还是 CUDA、ROCm？

答案是：**都可以**。FA 和 PA 是算法与机制，不绑定任何一种语言。同一套思想在不同平台、不同项目里，由不同工具写成。

![原稿 #4 图 12](images/s04_04_paged_flash_aiter_article_img12.png)

FlashAttention 的公开实现路径：

| 路径 | 用什么写 | 平台 |
|---|---|---|
| FA1 / FA2 官方 | CUDA C++ 加 CUTLASS 模板库 | NVIDIA |
| FA3 官方 | CUDA C++ 加 CUTLASS，编译目标 `sm90a` | NVIDIA Hopper |
| FA4 | CuTeDSL | NVIDIA Hopper 与 Blackwell |
| 官方 ROCm CK 后端 | C++ 模板（Composable Kernel，可组合内核） | AMD |
| 官方 ROCm Triton 后端 | Triton | AMD |
| Triton 官方教程实现 | Triton | 同一份代码可跑 NVIDIA 与 AMD |

PagedAttention 的公开实现路径：

| 路径 | 用什么写 | 平台 |
|---|---|---|
| vLLM 最初的分页 Attention kernel | CUDA C++ | NVIDIA |
| vLLM ROCm 分页 Attention | HIP C++ | AMD |
| AITER `pa_decode_gluon` | Gluon | AMD |
| AITER 分区归约 | C++、FlyDSL、Triton 三条可选路径 | AMD |
| AITER C++ 接口层 | HIP C++ 加 Jinja 代码模板 | AMD |
| AITER 极致优化算子 | 手写汇编 | AMD 指定架构 |
| FlashInfer 分页与块稀疏 Attention | CUDA C++ 加 Python JIT 生成 | NVIDIA |
| FA3 内置分页 KV 支持 | CUDA C++ | NVIDIA Hopper |

有两处细节最能说明“语言不是关键”。
**第一处**，`pa_decode_gluon` 的分区归约步骤在源码里按顺序尝试三种实现：先试 C++ 接口，不可用则试 FlyDSL，再不可用就退回 Triton kernel。同一个数学步骤，三种写法，运行时择一。

**第二处**，官方 FlashAttention 仓库把 AITER 作为 submodule（子模块）引入；其 FA3 包在 ROCm 上会直接导入 AITER 的 Triton kernel。所以“FA3 属于 N 卡、AITER 属于 A 卡”这种二分并不成立：在这条路径上，跑起来的是 FA3 的接口，底下正是 AITER 的实现。

#### 表格里那些名字，分别是什么

上面两张表出现了不少写法名，一次说清楚，顺便标明出身。

| 名字 | 大白话 | 谁家的 | 地位 |
|---|---|---|---|
| CUDA C++ / HIP C++ | 最底层的写法，地址、线程、同步全自己管 | NVIDIA / AMD | 正式 |
| CUTLASS / CuTe | C++ 模板库，提供 layout 代数与矩阵乘构件 | NVIDIA | 正式 |
| CK（Composable Kernel） | C++ 模板库，把 kernel 拆成可组合的构件 | AMD | 正式 |
| Triton | 用 Python 写 kernel，分块自己定，布局细节交给编译器 | 社区，起于 OpenAI | 正式，跨 NVIDIA 与 AMD |
| Gluon | Triton 编译栈里的低层语言，把布局与流水线交回开发者 | Triton 项目内 | 正式 |
| FlyDSL | 把“数据怎么摆”变成可运算的对象，再据此生成 kernel | AMD | 实验性，不在 ROCm 发行版内 |
| 手写汇编 | 直接安排 GPU 指令，只用于稳定热点 | 各家自有 | 正式 |

这里最容易混的一点是：**CUDA 和 ROCm 并不和 Triton、FlyDSL 站在同一层。**前者是平台底座——运行时、驱动、官方库；后者是底座之上的写法。摆成四层就清楚了。

![原稿 #4 图 13](images/s04_04_paged_flash_aiter_article_img13.png)

从上往下：先选用什么语言写，再由各自的编译器翻译成 GPU 指令，落到 CUDA 或 ROCm 这两个平台底座上，最后由硬件执行。Triton 的价值在于一份代码两边都能编；而 FlyDSL 的编译产物只到 ROCDL，也就是只落到 ROCm 这一侧。

#### 难的不是数学，是“数据摆在哪”

为什么写法能分出这么多种？因为写 kernel 时真正难的往往不是数学——Attention 公式就那么几步——而是另一件事：**几万个线程同时干活，每个都得知道自己该去显存的哪个位置取数。**

显存只是一条排好队的格子，而你脑子里的数据是方的。每次取数都要做一次翻译。

![原稿 #4 图 14](images/s04_04_paged_flash_aiter_article_img14.png)

拿图里那个 4 行 6 列的矩阵，问“第 2 行第 3 列在显存第几格”，答案是一个乘加：

```text
2 × 6 + 3 = 15
↑   ↑   ↑
│   │   └ 列号：这一行里往右走 3 格
│   └─── 一行有 6 格
└─────── 行号：跳过前面 2 整行
```

行号列号都从 0 数起。分两步：先跳过 2 整行，`2×6=12`，停在 12 号格；再往右走 3 格，得 15。这跟“第 2 周第 3 天是全年第几天”是同一个算法，只是把“一周 7 天”换成了“一行 6 格”。

那两个“要走多远”——6 和 1——打包起来就叫 **Stride**；矩阵多大叫 **Shape**。合在一起：

```text
Layout = (Shape, Stride) = ((4,6), (6,1))
```

**四个数，把“数据怎么摆”说完了。**

麻烦在于，真实 kernel 里这个公式不是一层，是套起来的：整个矩阵怎么摆、切给每组线程哪一块、组内再切给每 64 个线程哪一块、每个线程的寄存器怎么排、搬进片上内存时要不要错开以避开访存冲突、矩阵乘指令要求数据以什么姿势躺着。**每一层都是一组 (Shape, Stride)，上层切法一改，下面全变。**

于是那个漂亮的 `2 × 6 + 3`，在真实代码里长成十几项乘加。改任何一层的分块，整串都要重推——**推错一个数，结果是错的，而且往往不报错。**

#### “摆放方式可以拿来算”是什么意思

先说最关键的一点：**这些运算动的是公式，不是数据。一个字节都不会被搬。**

看两个例子，都能对着上面那张图验算。

**转置：把两个数对调。**

```text
原来：Shape=(4,6)  Stride=(6,1)   按行读
转置：Shape=(6,4)  Stride=(1,6)   按列读
```

原矩阵第 2 行第 3 列是 15 号格。转置后它成了第 3 行第 2 列，`3×1 + 2×6 = 15`，同一格。**数据没动，只换了两个数的位置。**

**切块：一个 Layout 算出两个。**

把 4×6 切成四个 2×3 的小块，你只需要说“切成 2×3”：

```text
块内怎么走：  Shape=(2,3)  Stride=(6,1)
块之间怎么跳：Shape=(2,2)  Stride=(12,3)
```

`12` 和 `3` 是算出来的：往下一个块要跨 2 行，`2×6=12`；往右一个块要跨 3 列，`3×1=3`。验一下右上那块的第 0 行第 1 列：块间 `0×12+1×3=3`，块内 `0×6+1×1=1`，合计 4——正是原矩阵第 0 行第 4 列。

这类运算官方列出的有四个：

| 运算 | 大白话 | 拿 4×6 举例 |
|---|---|---|
| divide | 切 | 切成四个 2×3，算出块间 Stride=(12,3) |
| product | 拼 | 反过来：块内摆法 × 块间摆法 = 整体摆法 |
| composition | 叠 | 先按 A 方式摆，再在此基础上按 B 方式取 |
| partition | 分 | 把切好的块派给具体哪个线程 |

**所谓“拿来算”，就是 Layout 能传进函数、能被切、能被拼、能被叠，而不是写死在代码里的一串常数。**

#### 三种写法的分工，以及 FlyDSL 的位置

同一件事，三种态度：

| 写法 | 布局这件事怎么处理 | 代价 |
|---|---|---|
| CUDA / HIP C++ | 自己手写下标 | 改一次分块，整串索引重推，极易错 |
| Triton | 说“取这一块”，布局交编译器 | 省事，但控制权交出去了 |
| FlyDSL | 布局是个能拿在手里的对象 | 要自己想清楚，但能算、能改、能反复试 |

具体点说：想把块从 64×64 改成 32×128，手写 C++ 要把 `idx = block_y*12 + block_x*3 + ty*6 + tx` 这类式子里的每个常数重推一遍；用 Layout 代数则是换一次 divide 的参数，那些常数由它算。

FlyDSL 的名字到这里也就好懂了。官方仓库标题直接给了展开——**Flexible layout python DSL**，灵活布局 Python 领域专用语言，`Fly` 取自 Flexible layout，不是“飞”。它管的是“用什么写”，不是“算什么”。

![原稿 #4 图 15](images/s04_04_paged_flash_aiter_article_img15.png)

模型说要算注意力，这是算什么；backend 决定谁来算；库里再挑出具体 kernel；而**那段 kernel 当初是用哪种语言写出来的**，才是它所在的位置。前面第一处证据正是现成例子：分区归约这一个功能，AITER 里用 C++、FlyDSL、Triton 各写了一份，功能完全一样。回到前面餐厅那个比方——backend 是厨师，FlyDSL 是写菜谱用的语言，菜没变，写法变了。

再往上看一层动机：NVIDIA 那边由 CUTLASS 里的 CuTe 提供这套 layout 代数，FlyDSL 官方致谢中明确写了思路借鉴自 CuTe。把它理解成“ROCm 侧的同类工具，而且直接用 Python 写”，大致不差——这一句是归纳，官方并未这么表述。

#### 那为什么不干脆全用 Triton

绝大多数时候就是在用 Triton，AITER 里大量 kernel 就是 Triton 写的。问题只出在最后那一截：想手动把数据错开摆以避开访存冲突、想指定矩阵乘指令要求的数据姿势、想手排搬运与计算的重叠——这些在 Triton 层面没有表达方式。

三个证据：

**一、Triton 自己做了 Gluon。**它就在 Triton 栈内，干的正是“把布局与流水线交回开发者”。如果 Triton 一直够用，没必要加这一层。

**二、最快的 Attention 实现没有一个是纯 Triton 写的。**FA3 走 CUDA 与 CUTLASS，FA4 用 CuTeDSL。

**三、AITER 那段代码的尝试顺序：先试 C++，不行试 FlyDSL，再不行退回 Triton。**Triton 排在最后，是兜底，不是首选。

所以真实分工是分层的：

| 场景 | 用什么 | 为什么 |
|---|---|---|
| 绝大多数算子 | Triton | 够快、好写、两边卡都能跑 |
| 少数极致热点：GEMM、Attention、MoE | Gluon、CuTe、FlyDSL 或汇编 | 要手控布局才能压到最后那一截 |

为什么偏偏是这三个？因为**优化收益等于“这个算子占多少时间”乘以“它能快多少”**。一个占 40% 时间的算子快 30%，整体快 12%；一个占 0.5% 的算子就算快十倍，整体也快不到 0.5%。

而这三个恰好都是“搬得多、算得也多”：GEMM 是每层的核心，权重矩阵动辄几千见方；Attention 除两次大矩阵乘外还要把整个 KV Cache 读一遍，长上下文下就是几十 GB 的纯搬运；MoE 是一堆小矩阵乘外加按路由分发 token，分发本身就是纯粹的“数据往哪摆”。其余算子——归一化、激活、加法——数据过一遍就完事，摆法怎么整都差不多，根本没得调。

打个比方：搬家时钢琴、冰箱、床垫怎么抬能差一小时，台灯和遥控器怎么拿都一样。**力气要花在难搬的东西上。**

还有一层：**换一代硬件，最优摆法就得重来。**矩阵乘指令变了、缓存变了，原来最快的切法可能就不再是最快的。这才是这类工具存在的真正理由——不是为了写得优雅，是为了让“重调”这件事扛得住。

#### Gluon 和 FlyDSL：不是二选一

看那个文件本身就明白了：`pa_decode_gluon` 的主 kernel 是 Gluon 写的，所以文件才叫这个名；FlyDSL 只出现在其中一小段归约里，还只是三个候选之一。**Gluon 管主体，FlyDSL 管一段，各管各的。**

那它们侧重差在哪？

| | Triton | Gluon | FlyDSL |
|---|---|---|---|
| 住在哪 | Triton 栈 | Triton 栈内的低层入口 | 独立的 MLIR `fly` 方言 |
| 给你什么 | 说“取这块”，布局交编译器 | 让你指定 layout 与流水线 | 让你对 layout 做运算 |
| 能编到哪些卡 | NVIDIA 与 AMD | 随 Triton | 仅 AMD GPU |

大白话：**Gluon 是 Triton 给你开的后门**，还在 Triton 的房子里，只是让你能亲手调家具；**FlyDSL 是另盖一间房**，主打“摆放方式本身可以拿来算”，走的是 CuTe 那一路。

差别最终落在谁为正确性负责。**声明**是你说“就是这样”，写错了往往不报错、只是结果不对；**推导**是你说“这样切”，数由它算。嵌套五六层的时候，这个差别就是“改不改得动”的差别。

顺带解开一个坑：**名字里带 Gluon，不代表整段都是 Gluon 写的。**

#### 边界：这条路还在试

三条如实说明：

- FlyDSL 官方 Disclaimer 写明它是**实验性工具、不属于官方 ROCm 发行版**；官方测试表里 GEMM 与 MoE 已较成熟，**PagedAttention 与 FlashAttention 仍标注为性能调优进行中**。
- 上文 `divide` 的写法是**示意**，确切函数名与签名以官方仓库为准。
- Gluon 与 FlyDSL 的对比反映的是两者公开材料各自强调的侧重，**不是逐条 API 的穷尽比较**；AMD 为何不直接扩展 Gluon，官方没有公开解释。

看 AITER 那三条依次尝试的路径，更像是“几条路一起养着，让实测说话”，而不是已经选定了谁。**兜底始终是 Triton。**

因此判断一条路径的正确方法，始终是看它实际调用了哪个 kernel、接口要什么参数，而不是看名字属于哪一派。


### 说到 backend，注意力还分前端后端吗

看测试报告时经常出现 `--attention-backend aiter` 这类写法。回到开头的比方：这个参数就是在指定**这道菜由哪个师傅炒**。菜名和食材都没变。

这里的 backend 不是网页开发里的前后端，而是借用编译器术语：**上层是统一接口，下层是可替换的具体实现**。

麻烦在于，这条链上“后端”至少有三种不同含义。

![原稿 #4 图 16](images/s04_04_paged_flash_aiter_article_img16.png)

| 含义 | 谁在选 | 例子 |
|---|---|---|
| 框架层的 Attention backend | 推理框架 | 选 AITER、FlashInfer 还是某个 Triton 实现 |
| 编译器的前端与后端 | 编译工具链 | Triton 前端写 Python，后端生成 NVIDIA 或 AMD 机器码 |
| 库内部的后端 | 算子库自己 | FlashInfer 官方列出的后端包含 FA2/FA3、cuDNN、CUTLASS、TensorRT-LLM |

模型代码本身通常只调用一个统一的 Attention 接口，并不关心底下是谁。真正决定跑哪段程序的，是框架的 backend 选择，加上库内部的再次选择。

#### 选了 backend，不等于选定了唯一 kernel

以 vLLM 的 ROCm 环境变量为例，AITER 不是一个开关，而是一组。

`VLLM_ROCM_USE_AITER` 是父开关，官方注释写明它 acts as a parent switch。在它下面还有一批分算子的子开关：

```text
VLLM_ROCM_USE_AITER_MHA        多头注意力
VLLM_ROCM_USE_AITER_MLA        多潜变量注意力
VLLM_ROCM_USE_AITER_MOE        混合专家
VLLM_ROCM_USE_AITER_LINEAR     线性层与 GEMM
VLLM_ROCM_USE_AITER_RMSNORM    归一化
VLLM_ROCM_USE_AITER_UNIFIED_ATTENTION
```

也就是说，“用 AITER”可以只用它的注意力而不用它的 MoE，也可以反过来。

再往下还有一层。`VLLM_ROCM_AITER_MLA_ASM_PADDING` 的取值是 `auto`、`gluon`、`asm`：`auto` 在有 Gluon 构建的架构上走 Gluon，否则走汇编路径；`gluon` 强制 Gluon；`asm` 强制汇编。官方注释同时说明，在 gfx942 上没有 Gluon 构建，所以无论怎么设置都会走汇编路径。

把这几层叠起来就是：

```text
模型调用统一 Attention 接口
        ↓
框架按 backend 配置选择实现
        ↓
父开关与分算子子开关决定哪些算子真的走 AITER
        ↓
库内按 Prefill / Decode、形状、数据类型、GPU 架构选具体 kernel
        ↓
最终执行的可能是 CK、Triton、Gluon、FlyDSL 或汇编写的程序
```

所以回到最初那个问题：注意力本身没有前端后端之分，**有前后端之分的是调用它的软件栈**。报告里只写一个 backend 名字，信息是不完整的；要还原一次运行，还需要子开关、GPU 架构和实际加载的 kernel。

#### 那 frontend 又指什么

有 backend，自然会问 frontend 在哪。这里要小心：frontend 这个词在推理生态里被用于好几件完全不同的事，**其中没有一个是 Attention 算子的“前端”**。

| 说到 frontend 时 | 实际指什么 | 它的对面是谁 |
|---|---|---|
| SGLang 的 frontend language | 写 LLM 程序的领域专用语言 | runtime 执行引擎 |
| vLLM 的 frontend | 接收 HTTP 请求的 API 服务器进程 | backend engine 进程 |
| 编译器的 frontend | 写 kernel 所用的那层语言 | 生成机器码的编译后端 |
| Attention 的调用入口 | 模型代码里那一行统一调用 | `--attention-backend` 选中的实现 |

![原稿 #4 图 17](images/s04_04_paged_flash_aiter_article_img17.png)

前两个最容易和 Attention 混淆，值得单独说清楚。

SGLang 论文摘要写明，它由 a frontend language and a runtime 组成：前端负责生成与并行控制的编程原语，运行时负责 RadixAttention 等执行优化。所以 SGLang 的 frontend 管的是**怎么写 LLM 程序**，它的对面是 runtime。而 `--attention-backend` 是 runtime **内部**的启动参数，两者隔着一整层。

vLLM 的用法又不一样。它的环境变量注释写明，`VLLM_RPC_BASE_PATH` 用于 frontend api server 与 backend engine process 之间通信，`VLLM_USE_RUST_FRONTEND` 则是用 Rust frontend 二进制替代 Python API server 进程。这里的 frontend 是**接收 HTTP 请求的那个进程**，属于进程架构，和 Attention 用哪个 kernel 无关。

真正与 Attention 后端配对的，是模型代码里那一行调用。以 vLLM 的 Llama 实现为例：

```python
# 声明一个统一的 Attention 层
self.attn = attn_cls(self.num_heads, self.head_dim, self.scaling, ...)

# 执行时只有这一行
attn_output = self.attn(q, k, v)
```

这行代码里只有 `q, k, v`，没有 AITER、没有 Triton、没有页表、没有 kernel 名字。换 backend 时它一个字都不用改——这正是分前后端的目的。

也正因为这一层**只有一个入口、没得选**，官方才不需要给它起名字，你在配置项里只会看到 backend。所以看到报告里写 backend 时，正确的追问不是“那 frontend 是什么”，而是：**这个 backend 具体选中了哪个 kernel**。


### 一张表彻底分清

| | FlashAttention | PagedAttention | 算子库（AITER / FlashInfer） |
|---|---|---|---|
| 它是什么 | I/O-aware 精确 Attention 算法 | 面向分页 KV Cache 的 Attention 算法与执行接口 | 高性能 kernel 的集合与统一入口 |
| 主要问题 | Attention 如何少搬数据、少存中间矩阵 | 非连续历史 K/V 如何管理、定位并参与计算 | 哪些高性能 kernel 可供框架调用 |
| 核心输入 | Q/K/V | Q、分页 K/V、页表、序列长度 | 取决于具体算子 |
| 是否管理 KV Cache | 否 | 是，紧密配合缓存分配器 | 库内提供相关 kernel，但缓存策略由框架协调 |
| 是否负责 Attention 计算 | 是 | 是 | 其中的 Attention kernel 负责 |
| 是否是一种算法 | 是 | 是 | 否 |
| 是否可同时出现 | 可与分页寻址融合 | 可采用 FA 式计算 | 可同时提供 FA 与 PA 相关实现 |


### 常见误区一次说清

| 误区 | 正确理解 |
|---|---|
| PA 和 FA 是两种互斥 Attention | 优化对象不同，可以融合在同一个 kernel 中 |
| PA 只管内存，不做计算 | Paged kernel 还要按页表读取 K/V 并完成 Attention |
| FA 专门针对 KV Cache | FA 优化通用 Attention，训练时没有历史 KV Cache 也可使用 |
| FA kernel 天然认识 Page Table | 必须由 kernel 接口明确支持，否则需要先 gather |
| AITER 是一种 Attention 算法 | AITER 是算子库，内部包含多类 Attention 和其他算子实现 |
| FlashAttention 只有一个版本 | 已有四代；FA3 依赖 Hopper 特性，FA4 用 CuTeDSL 重写 |
| FA3 属于 N 卡、AITER 属于 A 卡 | 官方 FA3 包在 ROCm 上导入的正是 AITER 的 Triton kernel |
| FA 或 PA 必然用某一种语言写 | CUDA、HIP、Triton、Gluon、FlyDSL、CK 模板、汇编都能写 |
| FlyDSL 是一种新的 Attention 优化 | 它是写 kernel 用的语言，管“用什么写”，不管“算什么” |
| CUDA / ROCm 和 Triton / FlyDSL 是同层选项 | 前两个是平台底座，后两个是底座之上的写法 |
| Layout 的切、拼、叠会搬动数据 | 变的只是算地址的公式，数据一个字节不动 |
| 有了 Triton，就不需要更低层的写法 | Triton 项目自己做了 Gluon；最快的 Attention 实现都不是纯 Triton |
| 文件名带 Gluon，整段就是 Gluon 写的 | 主 kernel 走 Gluon，其中分区归约另有三条路径依次尝试 |
| 算子库是 AMD 特有的东西 | NVIDIA 侧有 FlashInfer，同样是库而不是算法 |
| 选了 FlashInfer 就不是 FA 了 | FlashInfer 的后端本来就包含 FA2/FA3 实现 |
| 注意力自己分前端后端 | 分前后端的是软件栈，不是 Attention 算法 |
| 写清 backend 名字就能复现 | 还需要分算子开关、GPU 架构和实际加载的 kernel |
| 换 backend 会改变模型输出 | FA 是 exact attention，结果数值等价，差别在速度与显存 |


### 四句话记住

**FlashAttention**：拿到 Q/K/V 后，如何用分块和在线 Softmax 少搬数据、少存中间矩阵。

**PagedAttention**：历史 K/V 分散在物理 Page 中，如何通过页表直接找到并参与 Attention。

**AITER**：在 AMD ROCm 平台上，把 PA、FA、GEMM、MoE 等高性能 kernel 打包给推理框架使用。

**FlashInfer**：在 NVIDIA 平台上扮演同类角色，并把不同 KV Cache 形态统一成块稀疏格式。

如果只能记一句，记这句：**食材是 Q、K、V，菜是 Attention，剩下的都是师傅之间的差别。**


### 公开资料

1. FlashAttention 原始论文
   https://arxiv.org/abs/2205.14135

2. PagedAttention / vLLM 原始论文
   https://arxiv.org/abs/2309.06180

3. AITER 官方仓库
   https://github.com/ROCm/aiter

4. AITER 官方文档
   https://rocm.github.io/aiter/

5. AITER Gluon Paged Decode 源码
   https://github.com/ROCm/aiter/blob/main/aiter/ops/triton/gluon/pa_decode_gluon.py

6. vLLM PagedAttention 论文对应仓库
   https://github.com/vllm-project/vllm

7. FlashAttention-3 论文
   https://arxiv.org/abs/2407.08608

8. FlashAttention-3 官方博客
   https://tridao.me/blog/2024/flash3/

9. FlashAttention 官方仓库
   https://github.com/Dao-AILab/flash-attention

10. Triton 官方 Fused Attention 教程
    https://triton-lang.org/main/getting-started/tutorials/06-fused-attention.html

11. FlashInfer 论文
    https://arxiv.org/abs/2501.01005

12. FlashInfer 官方仓库
    https://github.com/flashinfer-ai/flashinfer

13. vLLM 环境变量文档（含 ROCm AITER 开关）
    https://docs.vllm.ai/en/latest/configuration/env_vars.html

14. FlyDSL 官方仓库
    https://github.com/ROCm/FlyDSL
<!-- SOURCE-END id=04 -->

---

<!-- SOURCE-BEGIN id=05 source=05_tp_vs_ep_article.md sha256=d40a6ea2dcd88cd9f69d5044b4f46ab13d91ebbebd8f02fc4e2c2099559e3a0d body_sha256=1ce6ab8ed41c4df7d0ed099edd53d762f68c578f626fbd13052e672d42a24f02 -->
## 原稿 #5：TP 和 EP 到底差在哪

> TP 和 EP 不是两种互相替代的加速开关。TP 负责把一份大计算拆开，EP 负责把许多独立专家分开。切法不同，token 的走法不同，通信原语和性能瓶颈也就完全不同。









### 先只看一个 token 走过一层

先不讲公式，也不讲通信库。

一个 token 进入 MoE Transformer 层后，大致走两段：

```text
token 的 hidden state
        ↓
Attention：读取 Q/K/V，完成注意力计算
        ↓
Router：给 token 选择 top-k 个专家
        ↓
Experts：选中的专家分别处理这个 token
        ↓
把多个专家结果加权合并
```

![原稿 #5 图 1](images/s05_05_tp_vs_ep_article_img01.png)

这两段天然适合不同的并行方式：

- **Attention 用 TP**：一份大矩阵计算，被多张卡合力完成。
- **Experts 用 EP**：许多独立专家，被分开放在不同卡上。

所以真实系统通常是：

```text
同一层里，Attention 走 TP，MoE Experts 走 EP。
```

**TP 和 EP 会同时出现，不是在两者之间二选一。**


### TP：把一件大事拆开做

TP 是 Tensor Parallelism，张量并行。

它把同一个权重矩阵，沿某个维度切到多张卡上。每张卡只完成这次矩阵乘的一部分。

![原稿 #5 图 2](images/s05_05_tp_vs_ep_article_img02.png)

拿一个最简单的矩阵乘说明：

```text
Y = X @ W
```

把 W 切成四份之后：

```text
Y = X₁@W₁ + X₂@W₂ + X₃@W₃ + X₄@W₄
      卡0       卡1       卡2       卡3
```

每张卡算出来的只是加法中的一项，是**部分和**，不是最终答案。

下一层又要继续使用 Y，所以四张卡必须完成两件事：

1. 把四份部分和加起来；
2. 让参与下一步的每张卡都拿到结果。

这正是 **AllReduce**：先 Reduce（规约求和），再让 All（所有 rank）拿到结果。

所以 TP 使用 AllReduce 不是经验选择，而是被数学结构逼出来的。


### EP：把许多独立专家分开做

EP 是 Expert Parallelism，专家并行。

MoE 里原本就有很多相互独立的专家。EP 不把一个专家切碎，而是把完整专家分开放到不同卡上。

![原稿 #5 图 3](images/s05_05_tp_vs_ep_article_img03.png)

假设 token `t1` 目前在卡 0，Router 却选择了专家 3 和专家 7：

```text
t1 在卡0
  ├─ 一份发给专家3所在的卡
  └─ 一份发给专家7所在的卡
```

专家算完后，两个结果还要回到 token 原来的位置，再按照 Router 权重合并。

因此 EP 有两次通信：

```text
dispatch：把 token 发到被选中的专家
   ↓ 专家算
combine ：把专家结果送回并合并
```

每个源 rank 都可能给每个目标 rank 发不同数量的 token，同时从每个 rank 收到不同数量的 token。

这就是 **AllToAll** 的数据形态：各发各的、各收各的。

所以 EP 使用 AllToAll，同样不是随手选择，而是被动态路由逼出来的。


### 先把 top-k 讲明白

`top-k` 中的 k，表示**每个 token 会被送给几个专家**。

![原稿 #5 图 4](images/s05_05_tp_vs_ep_article_img04.png)

例如总共有 64 个专家：

```text
top-k = 1：每个 token 只选 1 个专家
top-k = 2：每个 token 选 2 个专家
top-k = 8：每个 token 选 8 个专家
```

如果 `top-k=4`，一个 token 的 hidden state 就会形成 4 个专家任务。这里的“复制”是逻辑上的专家派发；本地专家不需要走网卡，通信库也会做打包和融合。

现在再看 `kA` 就不玄了：

- `A`：这一批 token 的 hidden state 一共有多少字节；
- `k`：每个 token 选几个专家；
- `kA`：这批 token 形成的**逻辑专家输入总量**。

一个具体例子：

```text
token 数 = 1000
hidden   = 4096
数据类型 = BF16，每个数 2 字节

A = 1000 × 4096 × 2
  = 8,192,000 字节
  ≈ 8.2 MB
```

如果 `top-k=4`：

```text
kA = 4 × 8.2 MB = 32.8 MB
```

它的意思只是：1000 个 token 一共产生 4000 份“送给某个专家”的 hidden-state 任务。

**它不是说物理网络一定精确传 32.8 MB。**本地路由不出卡，dispatch 可能使用 FP8，combine 可能使用 BF16，还会有路由元数据和负载不均衡。`kA` 是理解规模的逻辑账，不是抓包结果。


### TP 和 EP 的第一张完整对照表

![原稿 #5 图 5](images/s05_05_tp_vs_ep_article_img05.png)

| 维度 | TP 张量并行 | EP 专家并行 |
|---|---|---|
| 切什么 | 一份权重矩阵、Attention head | 多个独立专家 |
| 每张卡拿到什么 | 同一个算子的一个分片 | 完整的若干专家 |
| token 怎么走 | 同一批 token 由 TP 组共同计算 | token 被 Router 发到目标专家 |
| 结果是什么 | 部分和，必须汇总 | 完整专家输出，必须送回合并 |
| 典型原语 | AllReduce | Dispatch / Combine 形态的 AllToAll |
| 主要难点 | 高频同步、延迟 | 动态路由、负载不均、带宽与延迟 |
| 常见拓扑 | 通常留在高速机内互联域 | 可以扩到跨节点，但难度很高 |

一句话：

```text
TP = 把一件事拆开做，最后必须汇总。
EP = 把多件事分开做，数据必须去找负责它的人。
```


### 通信原语只需要先懂两个

#### AllReduce：求和，而且人人都要

对同一个大小为 A 的张量，带宽最优的 ring AllReduce 常用账本是：

```text
每个 rank 的发送量 ≈ 2A × (P-1) / P
每个 rank 同时接收同样多的数据
```

P 是 rank 数。

那个 2 从哪来？

![原稿 #5 图 6](images/s05_05_tp_vs_ep_article_img06.png)

```text
AllReduce = ReduceScatter + AllGather
```

第一趟一边求和一边散开，第二趟再把结果收齐。

#### AllToAll：每个人给每个人发不同的东西

如果一个 rank 打包后的总发送缓冲区是 A，并且均匀发向 P 个 rank：

```text
每个 rank 的远端发送量 ≈ A × (P-1) / P
```

同样大小的输入缓冲区下，ring AllReduce 的常用发送量大约是 AllToAll 的两倍。

**但这还不能推出 TP 的总通信一定更大。**因为 EP 的发送缓冲区会被 top-k 放大。


### 通讯量：先比较“单次”，再比较“一层”

这是最容易算错的一笔账。

#### 单次原语比较

假设两边都处理同样大小的 A：

```text
一次 ring AllReduce：约 2A × (P-1)/P
一次 AllToAll      ：约  A × (P-1)/P
```

所以只看单次、同尺寸 payload，AllReduce 更重。

#### 一层的教学模型

现在加上次数和 top-k。假设：

1. 经典 dense TP block 有两次 AllReduce；
2. EP 有一次 dispatch 和一次 combine；
3. dispatch 与 combine 使用相同字节宽度；
4. 路由均匀，先忽略本地专家和元数据；
5. 两边的基础激活大小都记作 A。

那么每个 rank 的发送量近似为：

```text
TP：2 次 × 2A × (P-1)/P = 4A × (P-1)/P
EP：2 次 × kA × (P-1)/P = 2kA × (P-1)/P
```

共同的 `(P-1)/P` 抵消后：

```text
EP / TP = k / 2
```

![原稿 #5 图 7](images/s05_05_tp_vs_ep_article_img07.png)

| top-k | 在上述教学假设下，EP ÷ TP |
|---:|---:|
| 1 | 0.5× |
| **2** | **1×，打平** |
| 4 | 2× |
| 8 | 4× |

#### 为什么分界线正好是 top-k=2

因为：

```text
AllReduce 的单次系数是 2
AllToAll 的单次系数是 1
EP 的 payload 又乘了 k

2kA = 4A  →  k = 2
```

没有其他玄机，就是两个 2 正好抵消。

#### 这不是通用定律

上面的 `k/2` 是**教学模型**，不是每个模型都能直接套的性能公式。

真实系统会改变这笔账：

- TP+EP 会在同一个 MoE block 里并存，不一定是在比较两个替代方案；
- MoE block 的 TP AllReduce 次数取决于切法和 sequence parallel；
- dispatch 常用 FP8，combine 可能用 BF16，二者字节宽度不同；
- 本地专家不走远端网络；
- top-k 路由不均会产生 hot rank；
- 通信与 GEMM 可以重叠；
- AllToAll 实现可能融合重排、量化和 combine 归约。

所以工程上要比较的是：

```text
每层实际远端字节数 + 每次 collective 延迟 + 与计算重叠后的关键路径时间
```

不是只看 `4A` 或 `2kA`。


### 一个反直觉点：TP 加卡，每卡流量很快饱和

把 P 代入 `2A(P-1)/P`：

![原稿 #5 图 8](images/s05_05_tp_vs_ep_article_img08.png)

| TP rank 数 P | 一次 ring AllReduce 每 rank 的发送量 |
|---:|---:|
| 2 | 1.00 A |
| 4 | 1.50 A |
| 8 | 1.75 A |
| 16 | 1.875 A |
| 无限大 | 趋近 2A |

从 TP=8 增到 TP=16，每 rank 的发送量只增加约 7%。

但 TP 仍然很难跨节点，因为它的问题不仅是字节数：

- collective 出现在很多层的关键路径上；
- 每次都要等参与 rank 达到依赖点；
- 小消息时启动延迟和同步抖动会放大；
- 慢 rank 会拖住整个 TP 组。

所以 TP 的痛点通常是**高频同步和尾延迟**，不是“卡越多，每卡字节数无限增长”。


### 既然 EP 通信很重，为什么还要用 EP

因为不用 EP，专家 GEMM 会被切得又瘦又碎。

![原稿 #5 图 9](images/s05_05_tp_vs_ep_article_img09.png)

举一个示意数字：

```text
hidden = 4096
单个专家 intermediate = 1408
```

如果用 TP=8 切一个专家：

```text
[tokens, 4096] @ [4096, 176]
                           ↑ 1408 ÷ 8
```

矩阵变得很窄。token 数本来就可能不多，再叠加专家负载不均，GPU 矩阵核心很难吃满。

如果用 EP=8：

```text
[本卡收到的 tokens, 4096] @ [4096, 1408]
```

每张卡保存完整专家，GEMM 形状更完整，权重也更连续。

EP 的本质是：

```text
用通信，换完整专家、权重容量和更好的 GEMM 形状。
```

这也是为什么大型 MoE 经常把两者组合起来：

- Attention 继续 TP；
- Experts 优先 EP；
- 专家仍然太大时，再在专家内部叠加 expert TP。


### TP 留在机内，EP 跨节点：但别理解成 EP 不怕延迟

![原稿 #5 图 10](images/s05_05_tp_vs_ep_article_img10.png)

常见拓扑会把 TP 组放在 NVLink / XGMI 等高速机内互联域，而用 EP 扩到更多节点。

原因不是“EP 延迟不敏感”。事实上：

- **Prefill 的 EP** token 多，通常更偏带宽瓶颈；
- **Decode 的 EP** token 少、消息小，非常看重延迟；
- AllToAll 还会受负载不均、NIC 映射和拥塞影响。

专用 EP 库通常同时提供两类路径：

- high-throughput：面向 prefill / training 的大消息；
- low-latency：面向 decode 的小消息。

TP 通常留在机内，是因为它在大量层中持续同步；EP 承担跨节点扩展，是因为专家数量和权重容量必须向外扩，而且软件可以围绕 dispatch/combine 专门优化 RDMA、低精度传输和计算重叠。

**两边都难，只是难点不同。**


### 一次真实项目里，TP 和 EP 是怎样并存的

在一次 8-GPU/节点的 MoE 推理项目中，能稳定复现的基础拓扑是：

```text
Attention TP = 8
local EP     = 8
DP           = 1
```

含义是：

- 8 张卡共同完成 Attention；
- 专家也分布在这 8 张卡上；
- TP 和 EP 使用同一批 GPU，但建立不同的通信组、服务不同的算子。

另一个参考拓扑为了扩大专家域，保持 `attention TP=8` 不变，通过更多 DP 组把 global EP 扩到 16 或 32。

这个模式非常值得记：

```text
Attention TP 钉在硬件和模型允许的值；
需要扩大模型容量和并发时，向 DP / global EP 方向扩。
```

#### 当时踩过的跨节点 EP 坑

旧版软件栈中，单节点 local EP=8 可用，但 SGLang + MI300X + CX7 的跨节点 MORI 路径曾在并发请求下出现 hang / deadlock。关闭 MoE A2A backend 后请求可运行，这个差分把问题缩到 dispatch/combine 路径。

这条历史结论必须带日期和版本理解。当前 MORI 官方 README 已列出 MI300X + CX7 的 EP8 / EP16 / EP32 dispatch、combine 带宽和延迟数据，也提供跨节点正确性测试。**不能把旧栈的问题说成 AMD 现在“没有 A2A”。**

真正可复用的排障方法是：

```text
单节点先过 → 跨节点最小请求 → 提高并发 → 关闭专用 A2A 做差分
```


### EP 不切 Attention head，也不切 KV

在常见 MoE 并行分工中：

```text
TP → Attention head、QKV 投影、Attention 输出
EP → MoE Experts
```

所以 EP 只改变 token 去哪个专家，不改变 KV Cache 的 head ownership。

![原稿 #5 图 11](images/s05_05_tp_vs_ep_article_img11.png)

一个模型与框架版本的真实约束是：fused-QKV 模型要求 effective attention TP 等于 8。框架计算：

```text
effective_attn_tp = tp_size // dp_size // attn_cp_size
```

于是：

| 配置 | effective attention TP | 结果 |
|---|---:|---|
| TP=8, DP=1, CP=1 | 8 | 通过 |
| TP=8, DP=2, CP=1 | 4 | 启动校验失败 |
| TP=16, DP=2, CP=1 | 8 | 通过，但需要更大的全局 TP 域 |

这说明**在这个具体模型和框架里**，拆小 Attention TP 的是 DP / CP 的组划分，不是 EP。

这不是所有模型的通用公式。其他模型可能允许复制 KV head，或者使用不同 QKV layout。对外结论必须限定到具体 config、框架版本和 kernel 路径。

#### “KV 不出服务器”也要限定场景

常见设计会把 Attention TP 组和 rank-owned KV 留在节点内，EP 只传当前 token 的 hidden state。

但 PD 分离是明确例外：Prefill 完成后，KV Cache 会通过 Mooncake / MORI-IO 等点对点 RDMA 路径传给 Decode 节点。

```text
稳态 Attention：KV 留在所属 rank
PD 交接       ：KV 跨节点传一次
```

PD 的 KV transfer 是点对点数据传输，不是 EP 的 AllToAll。


### 为什么还需要 DeepEP、MORI 这类专用库

这里要纠正一个已经过时的说法：**当前 NCCL 文档已经把 `AlltoAll`、`Gather`、`Scatter` 列为正式 collective。**所以不能再说“因为 NCCL 没有 AllToAll，才需要 DeepEP”。

通用 AllToAll 只解决：

```text
每个 rank 的固定分块，交换到所有其他 rank。
```

MoE 的真实 dispatch/combine 还要解决：

- 每个 token 的 top-k 路由；
- 每个目标专家收到的 token 数不相等；
- token permutation 和反向还原；
- expert alignment 与 padding；
- FP8 dispatch、BF16 combine；
- combine 中的加权归约；
- 跨节点 RDMA 与多 NIC 映射；
- 通信和专家 GEMM 重叠；
- prefill 高吞吐与 decode 低延迟两套策略。

DeepEP 官方把自己描述为面向 EP 的高吞吐、低延迟 dispatch/combine GPU kernel 库；MORI-EP 也提供节点内和跨节点 dispatch/combine，并把 KV transfer 放在单独的 MORI-IO 点对点库里。

所以专用库的价值不是“发明了 AllToAll”，而是：

```text
把 Router 之后的整个 MoE 数据面做成一条高性能流水线。
```


### DP 和 CP 放在哪里

#### DP：推理时不等于 AllReduce

训练时 DP 要 AllReduce 梯度；推理没有梯度同步。

推理中的普通 DP 是多份完整模型处理不同请求，彼此基本独立。

但 DP attention 会改变 Attention group 的划分，因此在前面的特定框架里进入了 `tp // dp // cp` 公式。

#### CP：不要看到名字就猜原语

不同 Context / Sequence Parallel 方法使用的原语不同：

| 实现 | 常见通信 |
|---|---|
| Megatron sequence parallel | AllGather + ReduceScatter |
| Ulysses | AllToAll |
| Ring Attention | 环形 Send / Recv |
| 本项目检视的 SGLang attention CP 路径 | `cp_all_gather_into_tensor` |

**并行名称不能直接推出通信原语，要看实现源码。**


### 附录：本文用到的常见通信动作

“通信原语一共只有九个”并不严谨。MPI 还有 Barrier、AllToAllv、邻居集合通信等变体。下面只列本文和主流 GPU 推理最常遇到的基础动作。

![原稿 #5 图 12](images/s05_05_tp_vs_ep_article_img12.png)

| 原语 | 大白话 | 是否规约 |
|---|---|---|
| Broadcast | 一个 rank 发给所有 rank | 否 |
| Reduce | 所有 rank 汇总到一个 rank | 是 |
| AllReduce | 汇总后所有 rank 都拿到结果 | 是 |
| Gather | 所有 rank 收集到一个 rank | 否 |
| AllGather | 每个 rank 都收齐所有分片 | 否 |
| Scatter | 一个 rank 把不同分片发给各 rank | 否 |
| ReduceScatter | 先规约，每个 rank 留一个结果分片 | 是 |
| AllToAll | 每个 rank 给每个 rank 发不同分片 | 否 |
| Send / Recv | 两个 rank 点对点通信 | 否 |


### 排查 TP / EP 问题的实战顺序

| 症状 | 第一检查项 |
|---|---|
| 启动时报 Attention TP 不匹配 | 模型 head 配置、QKV layout、实际 TP/DP/CP group |
| 单节点 EP 正常，跨节点 hang | A2A backend、NIC 映射、RDMA、并发差分 |
| Decode 延迟突然升高 | 小消息 A2A 延迟、负载不均、slow rank |
| Prefill 吞吐上不去 | A2A 带宽、dispatch dtype、通信计算重叠 |
| TP 跨节点后 TPOT 变差 | collective 次数、尾延迟、拓扑映射 |
| 参数写了却没效果 | 服务运行时配置与实际加载路径，不看命令行表面 |

最有用的三组差分：

```text
TP：机内 vs 跨节点
EP：专用 A2A backend on vs off
路由：top-k 小 vs 大
```

一次只改一个变量，才能知道瓶颈到底在哪。


### 常见误区一次说清

| 误区 | 正确理解 |
|---|---|
| TP 和 EP 二选一 | 同一个 MoE 层里通常同时使用 |
| AllReduce 单次最重，所以 TP 总通信最大 | 单次系数与整层 payload 是两笔账 |
| `kA` 就是网卡实传字节 | 它是逻辑专家输入量，实际还受本地路由、dtype、元数据影响 |
| top-k=2 时 EP 一定等于 TP | 只在明确列出的教学假设下打平 |
| MoE 稀疏，所以通信也稀疏 | 稀疏省计算；每个 token 仍会形成 k 个专家任务 |
| EP 可以跨节点，所以不怕延迟 | Decode EP 对小消息延迟非常敏感 |
| EP 会拆 Attention head 和 KV | EP 只分专家；Attention / KV 属于另一组并行 |
| TP 上限永远等于 KV head 数 | 这是模型、QKV layout 和框架相关约束，不是普遍定律 |
| NCCL 没有 AllToAll | 当前 NCCL 文档已提供 `ncclAlltoAll()` |
| 有通用 AllToAll 就不需要 DeepEP / MORI | MoE 还需要路由、重排、低精度、归约、RDMA 和重叠 |
| PD 传 KV 属于 EP 通信 | 它是独立的点对点 KV transfer |


### 五句话记住

**第一句**：TP 把一份大计算切开，每张卡只有部分结果；EP 把完整专家分开，token 去找专家。

**第二句**：TP 因此需要 AllReduce，EP 因此需要 dispatch / combine 形态的 AllToAll。

**第三句**：同尺寸单次通信里 AllReduce 更重；整层通信则必须把 top-k、dtype、次数和本地路由一起算。

**第四句**：TP 与 EP 会在同一个 MoE 模型中并存，不能把 `4A` 和 `2kA` 当成所有模型的通用二选一公式。

**第五句**：真正的工程指标不是原语名字，而是实际远端字节数、collective 延迟、负载不均和关键路径时间。

如果只能记一句：**通信原语不是选出来的，是被数据切法逼出来的。**


### 公开资料

1. NCCL 集合通信操作（当前文档含 AlltoAll / Gather / Scatter）
   https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/collectives.html

2. NCCL 点对点通信
   https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/usage/p2p.html

3. RCCL 官方仓库
   https://github.com/ROCm/rccl

4. Megatron-LM（张量并行）
   https://arxiv.org/abs/1909.08053

5. Megatron sequence parallel
   https://arxiv.org/abs/2205.05198

6. GShard（MoE 与 top-2 路由）
   https://arxiv.org/abs/2006.16668

7. Switch Transformer（top-1 路由）
   https://arxiv.org/abs/2101.03961

8. DeepSpeed-Ulysses
   https://arxiv.org/abs/2309.14509

9. Ring Attention
   https://arxiv.org/abs/2310.01889

10. DeepEP 官方仓库
    https://github.com/deepseek-ai/DeepEP

11. MORI 官方仓库
    https://github.com/ROCm/mori

12. SGLang 官方仓库
    https://github.com/sgl-project/sglang

13. 历史跨节点 MORI / SGLang 问题记录（仅作为旧栈排障案例，不代表当前支持状态）
    https://github.com/sgl-project/sglang/issues/19991
    https://github.com/ROCm/mori/issues/168
<!-- SOURCE-END id=05 -->

---

<!-- SOURCE-BEGIN id=13 source=13_why_dsl_attention_article.md sha256=4d1f179fad7e54be6c80e65bd80c841f233b02d11ab96fbd81ed9eac5ea048d9 body_sha256=8892ad9dfc0047b2b7a9c82f370ac2aefe5ab179952e277371fddec9830b8e38 -->
## 原稿 #13：CuTe DSL 与 FlyDSL 到底强在哪？从数据摆放到 AMD 192/128 Attention

> 数学公式没有变，模型也没有变。NVIDIA CuTe DSL 与 AMD FlyDSL 真正开放出来的，是公式里的数字如何映射到地址、线程和片上存储，以及它们何时从全局显存搬进共享存储，再进入矩阵计算单元。








### 客户真正问的不是“CuTe DSL / FlyDSL 是什么”

客户真正想知道的是两件事：

1. **为什么这次需要写专用 Kernel，现成的不能直接用？**
2. **专用 Kernel 到底改了什么，为什么会更快？**

先给结论：

> 不是其他技术绝对做不了，而是现成 Kernel 只覆盖了它预先支持的形状。遇到非对称、非标准或组合复杂的模型结构时，通用实现可能只能 padding、回退到慢路径，或者直接不支持。CuTe DSL 与 FlyDSL 都让 Kernel 工程师用 Python 显式描述特殊形状的数据布局和执行计划：前者面向 NVIDIA CUDA，后者面向 AMD ROCm/HIP。

> **范围边界**：前半篇讲 CuTe DSL 与 FlyDSL 共享的数据摆放方法；后半篇的 `K=192、V=128` 是 XiaomiMiMo 公开 shape 对应的 **AMD/FlyDSL 案例**。本文没有展示或宣称该 MiMo Kernel 已在 NVIDIA CuTe DSL 上实现、命中或获得性能收益。

这句话里有三个层次，必须分开：

| 层次 | 决定什么 | 这次有没有改变 |
|---|---|---|
| 模型数学 | Q、K、V 怎么算，Attention 公式是什么 | **没有** |
| 张量形状 | Q/K/V 各有多宽，head 怎么组织 | **没有** |
| Kernel 执行 | 数据怎么切块、搬运、复用和计算 | **改变了** |

![三层](images/s13_13_why_dsl_attention_article_img03.png)

*图 1：模型公式、张量形状和 Kernel 执行是三个不同层次。CuTe DSL 与 FlyDSL 主要改变第三层。*


### 一、先看这个模型到底“特殊”在哪

以公开模型 **XiaomiMiMo/MiMo-V2.5-Pro** 为例。其官方 `config.json` 给出的 Attention 关键字段包括：

| 字段 | 值 |
|---|---:|
| Query heads | 128 |
| KV heads | 8 |
| Q/K head dimension | 192 |
| V head dimension | 128 |
| QKV 权重布局 | `fused_qkv` |

来源：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro/blob/main/config.json>

最值得注意的是：

```text
K 的宽度 = 192
V 的宽度 = 128
```

**K 和 V 不一样宽。**

这并不违反 Attention 数学。Q·K 需要 Q 与 K 的维度一致；V 是被注意力权重加权汇总的内容，V 可以使用不同的宽度。

但对 Kernel 来说，这意味着不能简单地把 K 和 V 当成两块一模一样的砖。

#### 如果现成 Kernel 只接受等宽 K/V

一种兼容办法是把 V 从 128 补零到 192：

```text
原生：K = 192，V = 128
补齐：K = 192，V = 192
```

数学结果仍可保持一致，因为补上的维度都是零，最后再把多余部分切掉。

但 GPU 并不知道这些零“没有意义”。它仍然可能为它们：

- 分配内存；
- 从内存读取；
- 搬到 LDS/Register；
- 参与矩阵乘加；
- 写回中间结果；
- 最后再切掉。

#### 浪费了多少？

只看 V：

```text
128 → 192
```

V 被放大到原生宽度的 `1.5×`，即多出 50% 的无效宽度。

这里的 50% 以原生 `128` 为分母；下面的 33.33% 以补齐后的 `192` 为分母。两者描述的是同一段 64 维差额，只是观察方向不同。

从旧的 padded 路径切回原生 128，V 部分减少：

$$
\frac{192-128}{192}=33.33\%
$$

把 K 和 V 合起来看：

```text
padded K+V：192 + 192 = 384
原生   K+V：192 + 128 = 320
```

从 padded 路径切回原生布局，K+V 合计宽度减少：

$$
\frac{384-320}{384}=16.67\%
$$

![非对称维度与 padding](images/s13_13_why_dsl_attention_article_img04.png)

*图 2：padding 能保证兼容，但会为不存在的信息分配、搬运并计算额外空间。比例为形状算术，不代表端到端模型加速比例。*

这里必须强调：**K+V 宽度减少 16.67%，不等于整套模型快 16.67%。** Attention 只是整层的一部分，最终收益还取决于它原来占总时间的多少。


### 二、为什么现成通用 Kernel 不能自动适配？

很多人会问：

> 不就是一个矩阵乘法吗？把参数从 192 改成 128 不就行了吗？

问题在于，高性能 GPU Kernel 不是一个“任意形状计算器”。它更像一条为了特定箱子尺寸设计的自动化流水线。

#### 一个仓库的例子

假设仓库原来的传送带专门处理 `192×192` 的箱子：

- 叉车一次正好搬 192 个单位；
- 货架正好留 192 个位置；
- 每组工人正好处理固定 tile；
- 装车顺序与 MFMA 指令形状正好匹配。

现在来了一个 `192×128` 的箱子。

有三种选择：

1. **padding**：给小箱子套一个 192 的大纸箱，旧流水线继续运行；
2. **通用慢路径**：换人工搬运，什么尺寸都能处理，但吞吐下降；
3. **专用 Kernel**：重新规划传送带，让它原生处理 192/128。

第一种最快上线但浪费，第二种最兼容但慢，第三种开发成本最高但性能最好。

#### 通用性为什么和极致性能冲突？

为了跑快，Kernel 通常会提前固定或约束很多决策：

- tile 是 `64×64`、`128×64` 还是其他形状；
- 一个 wave/warp 负责哪块数据；
- 每个线程一次读取多少元素；
- LDS 如何排列，才能避免 bank conflict；
- Register 如何分配，才能匹配 MFMA；
- 需要几级流水和双缓冲；
- 哪些步骤融合，哪些步骤单独执行。

形状一变，原来的最佳组合可能不再最佳，甚至无法正确运行。

> 通用 Kernel 的价值是覆盖面；专用 Kernel 的价值是在一个关键形状上把硬件吃满。

![通用与专用](images/s13_13_why_dsl_attention_article_img05.png)

*图 3：通用路径用兼容性覆盖更多形状；DSL 专用路径为真实热点形状重新安排数据和计算。*


### 三、CuTe DSL 与 FlyDSL 到底多提供了什么？

CUDA/HIP C++、CUTLASS/CK、Triton 都可以写 GPU Kernel。CuTe DSL 与 FlyDSL 并没有获得某种别人没有的硬件权限。

它们的共同价值是：把原来隐藏在大量地址计算、模板参数和线程下标中的东西，变成 Python 中可以显式组合的对象。

#### 先把两个名字摆正

NVIDIA 官方对 **CuTe DSL** 的定义是：

> CuTe DSL is a Python-based domain-specific language (DSL) designed for dynamic compilation of high-performance GPU kernels. It evolved from the C++ CUTLASS library and is now available as a decorator-based DSL.

它不是“CuTe C++ 的一层 Python 包装”这么简单。它提供 `@cute.jit`、`@cute.kernel`、JIT cache、DLPack 集成，以及对 layout、copy、MMA 和底层 NVIDIA GPU 能力的显式控制。

来源：<https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl_general/dsl_introduction.html>

ROCm/FlyDSL 官方把它定义为：

> A Python DSL and an MLIR stack for authoring high-performance GPU kernels with explicit layouts and tiling.

关键词是：

- **explicit layouts**：显式布局；
- **tiling**：显式分块；
- **Python DSL**：用 Python 描述；
- **MLIR stack**：编译成底层 GPU 指令。

来源：<https://github.com/ROCm/FlyDSL>

把两者并排看，更容易理解：

| | NVIDIA CuTe DSL | AMD FlyDSL |
|---|---|---|
| 来源 | CUTLASS/CuTe C++ 演进出的 Python DSL | 采用 CuTe Layout Algebra 的 AMD Python DSL |
| 目标平台 | NVIDIA CUDA | AMD ROCm/HIP |
| Host / Kernel 装饰器 | `@cute.jit` / `@cute.kernel` | `@flyc.jit` / `@flyc.kernel` |
| Layout API 前缀 | `cute.make_layout`、`cute.zipped_divide` | `fx.make_layout`、`fx.zipped_divide` |
| 数据搬运 | `cute.copy` + Copy Atom/Tiled Copy；可接 TMA、cp.async 等架构能力 | `fx.copy` + Copy Atom/Tiled Copy；可接 ROCDL buffer load/store 等能力 |
| 片上路径 | GMEM → SMEM/RMEM；新架构还可能使用 TMEM | GMEM/HBM → LDS/VGPR |
| 矩阵计算 | Tiled MMA，落到对应代际的 Tensor Core 指令 | Tiled MMA，落到 MFMA/WMMA |
| 编译路径 | Python decorator DSL 动态 JIT 到 CUDA 目标 | Python → Fly MLIR → ROCDL/LLVM → HSACO |

**共享的是 Layout Algebra 和 Kernel 设计方法，不共享 API 二进制，也不能把一份代码原样切换后端。**

下文先讲两者共同的数学模型，再分别标注 NVIDIA CuTe DSL 与 AMD FlyDSL 的 API。`K=192、V=128` 来自小米模型和 AMD 优化场景，因此最后的具体落地以 FlyDSL 为例；这不等于本文已经在 NVIDIA 上验证了同一条 MiMo Kernel。

#### “显式布局”用大白话怎么理解？

同一份矩阵在显存里只是一长串数字。Kernel 必须回答：

```text
逻辑坐标 (第几行, 第几列)
              ↓
对应显存里的哪个地址
              ↓
由哪个线程读取
              ↓
一次读取几个连续元素
              ↓
放到 LDS 的哪个位置
              ↓
再进入哪个线程的 Register
```

PyTorch 的 `A @ B` 只说明“算什么”；CuTe DSL / FlyDSL 这一层则描述“这些数字由谁搬、搬到哪、怎么重复利用”。

但这仍然有点抽象。**两套 DSL 继承的 CuTe Layout，本质上都是一个可以计算的映射函数。**

#### 第一步：逻辑坐标映射到线性偏移

一个 layout 由 `Shape（形状）` 和 `Stride（步长）` 组成：

```text
Layout = (Shape, Stride)
线性偏移 = 逻辑坐标 · Stride
```

先看 AMD FlyDSL 官方文档中的例子：

```python
shape = fx.make_shape(128, 64)
stride = fx.make_stride(1, 128)
layout = fx.make_layout(shape, stride)
coord = fx.make_coord(3, 5)
offset = fx.crd2idx(coord, layout)
```

NVIDIA CuTe DSL 用同一套 Shape/Stride 思想，但 API 属于 `cutlass.cute`：

```python
import cutlass.cute as cute

layout = cute.make_layout((128, 64), stride=(1, 128))
offset = layout((3, 5))
```

CuTe DSL 官方 notebook 直接把 Layout 定义为 Shape/Stride 对，并强调它把 coordinate space 映射到 index space；`layout(coord)` 就是调用这个映射函数。

坐标 `(3, 5)` 相对 tensor 基址的偏移为：

$$
3\times1+5\times128=643
$$

这里的逻辑矩阵是 `128×64`，但数据按 `(1,128)` 的步长存放：第一维移动一格，地址加 1；第二维移动一格，地址加 128。这就是 column-major（列优先）映射。

如果换成 `(64,1)`，同一个逻辑坐标会映射到：

$$
3\times64+5\times1=197
$$

数学上的元素仍然叫 `A[3,5]`，但它相对 tensor 基址的线性偏移完全不同。

这里必须再收紧一步：**offset 不是绝对 HBM 物理地址。**实际 byte address 可以简化成：

```text
tensor allocation 的基址 + offset × dtype_bytes
```

基址由 runtime 和 allocator 决定；CuTe DSL / FlyDSL layout 控制的是“拿到这个 tensor 之后，逻辑坐标怎样映射到相对偏移”。它不会指定某个值必须落在第几块 HBM 芯片、哪个绝对物理地址。

![同一逻辑坐标在不同 layout 下映射到不同物理地址](images/s13_13_why_dsl_attention_article_img01.png)

*图 7：layout 不是一张“矩阵长什么样”的图片，而是从逻辑坐标到线性偏移的函数。Shape 相同，Stride 不同，访问顺序就不同。*

这一步已经决定了很多性能问题：

- 相邻线程读到的是不是相邻地址；
- 一次 128-bit load 能不能装满有效数据；
- 一个 wavefront 的访问能否合并成较少的 HBM transactions；
- 转置、切片和 padding 是只改映射，还是必须真的搬一次数据。

#### 第二步：把大矩阵分给 block，再分给 thread

只有“坐标到地址”还不够。Kernel 还要决定谁负责哪个坐标。

两套 DSL 都用 layout algebra（布局代数）继续做两层分解：

```text
完整 Tensor
  ↓ zipped_divide / tiled_divide
每个 workgroup 负责一个 tile
  ↓ thread-value layout
每个 thread 负责 tile 中的一组 values
```

AMD FlyDSL 官方 GEMM 示例的核心结构是：

```python
bA = fx.zipped_divide(A, tileA)
bA = fx.slice(bA, (None, bid))

thr_copy = tiled_copy.get_slice(tid)
src = thr_copy.partition_S(bA)
dst = thr_copy.partition_D(dst_tensor)
fx.copy(copy_atom, src, dst)
```

这几行分别回答：

1. `zipped_divide`：大矩阵怎样切成 tiles；
2. `slice(..., bid)`：当前 block 拿哪个 tile；
3. `get_slice(tid)`：当前 thread 在协作复制中的位置；
4. `partition_S / partition_D`：该 thread 从哪里读、往哪里写；
5. `fx.copy`：真正发出数据搬运。

**`make_layout` 本身不会搬数据。**它定义映射；`fx.copy`、buffer load/store 等操作才会根据这个映射执行真实读写。这条边界很重要：layout 是“地址与所有权计划”，copy 才是“搬家动作”。

如果 destination 是 MFMA 的 register fragment，官方 tiled-MMA 示例不是直接对 fragment 调 `partition_D`，而是先做：

```python
frag_A = thr_mma.make_fragment_A(bA)
copy_frag_A = thr_copy.retile(frag_A)
fx.copy(copy_atom, src, copy_frag_A, pred=None)
```

`partition_D` 用来得到普通 destination tensor 的线程分区；`retile` 则把已有 fragment 重新解释成与 tiled copy 兼容的 value layout。两者都在解决“当前 thread 应该看见哪一组值”，但消费对象不同。

NVIDIA 官方 `tour_to_sol_gemm.ipynb` 是 **Python CuTe DSL** 示例：文件顶部使用 `import cutlass.cute as cute`，Kernel 使用 `@cute.kernel`。下面这些调用位于该 Python Kernel 内部，并非 CuTe C++ 代码：

```python
@cute.kernel
def kernel(
  tiled_mma: cute.TiledMma,
  mA_mkl: cute.Tensor,
  mC_mnl: cute.Tensor,
  # ...其余参数省略
):
  gA = cute.local_tile(
    mA_mkl, mma_tiler_mnk, mma_coord_mnk, proj=(1, None, 1)
  )
  thr_mma = tiled_mma.get_slice(0)
  tCgA = thr_mma.partition_A(gA)

  tDtC = tmem_thr_copy.partition_S(tCtAcc_epi)
  tDgC = tmem_thr_copy.partition_D(gC_epi)
  cute.copy(tmem_tiled_copy, tDtC[None, None, i], tCrAcc)
```

这里的 `local_tile` 取出当前 CTA 的 tile，`partition_A/B/C` 生成 MMA 看到的 tensor view，`partition_S/D` 生成 copy 看到的 source/destination view，`cute.copy` 才真正发出数据搬运。FlyDSL 当前没有把 `local_tile` 暴露成一个同名入口，官方建议用 `zipped_divide + slice` 表达等价分解。这正说明：**代数语义相近，API 和硬件执行细节不同。**

代码来源：<https://github.com/NVIDIA/cutlass/blob/main/examples/python/CuTeDSL/cute/notebooks/tour_to_sol_gemm.ipynb>

#### 用一个 4×8 toy tile 看清 thread × value layout

假设有一个 row-major 的 `4×8` FP32 tile，共 32 个值。为了讲清机制，先用 8 个 lane 做一个简化映射，每个 lane 负责连续 4 个值：

| Lane | 负责的逻辑元素 | HBM 线性偏移 |
|---:|---|---|
| 0 | `A[0,0:4]` | `0..3` |
| 1 | `A[0,4:8]` | `4..7` |
| 2 | `A[1,0:4]` | `8..11` |
| 3 | `A[1,4:8]` | `12..15` |
| 4 | `A[2,0:4]` | `16..19` |
| 5 | `A[2,4:8]` | `20..23` |
| 6 | `A[3,0:4]` | `24..27` |
| 7 | `A[3,4:8]` | `28..31` |

这个 toy layout 可以写成：`offset = 4 × lane + value`，其中 `value=0..3`。

于是 lane 0 的四个 FP32 正好连续占 16 bytes，也就是 128 bits；在 source address 满足该 copy atom 的对齐与合法访问约束时，一个 `BufferCopy128b` 可以一次取完。lane 1 紧接着读取后面的 16 bytes。这里的重点不是“永远用 8 个 lane”，而是：**thread × value layout 能让编译器算出每个 lane 的每个 value 对应哪个 tensor offset。**真实 Kernel 会根据 dtype、wavefront、tile 和 MFMA 指令选择实际映射。

接下来，同一批逻辑值进入 LDS 时可以换一套 destination layout：

```text
partition_S：lane 0 从 HBM offsets 0..3 读取
partition_D：lane 0 写入 LDS destination layout 指定的位置
fx.copy：按 copy atom 执行这次 128-bit 搬运
```

因此，`partition_S` 和 `partition_D` 不是两个额外的数据中转站；它们是 source/destination 的线程视图。真正的运行时数据路径仍然是 `HBM → LDS → VGPR/MFMA`。

#### 第三步：同一个 tile 在 GMEM、共享存储和寄存器中可以有不同摆法

高性能 Kernel 通常不会让一种 layout 从头用到尾。

| 层级 | NVIDIA CuTe DSL | AMD FlyDSL | 常见目标 |
|---|---|---|---|
| 全局显存 | GMEM | GMEM / HBM | 连续、对齐、向量化读取 |
| 片上共享存储 | SMEM | LDS | 多线程复用、避免 bank conflict |
| 线程寄存器 | RMEM / Register | VGPR / Register | 匹配 MMA/MFMA fragment |
| 新架构专用存储 | Blackwell 可使用 TMEM | 取决于 AMD 架构能力 | 承接 accumulator 或专用数据路径 |
| 输出显存 | GMEM | GMEM / HBM | 连续写回或匹配下一个 fused stage |

例如 GMEM 中一行连续的数据，搬进 SMEM/LDS 后未必仍按朴素行优先存放。Kernel 可以用 swizzle（重排）把原本会撞到同一个 bank 的访问打散。

两边的 API 细节不同：CuTe DSL 官方 Blackwell GEMM notebook 把 composed SMEM layout 的 `outer` layout 与 `inner` swizzle 交给 `SmemAllocator`；FlyDSL 指南则展示用地址算术显式构造 XOR 映射，例如按 16-byte 粒度把 row 信息异或进 column address。也就是说，两者都能表达 bank-friendly layout，但不能把 NVIDIA 的 swizzle helper 名称直接套到 AMD API。

#### 第四步：Copy Atom 决定一次怎么搬

layout 说明“谁拥有哪些元素”，copy atom 说明“每次用什么硬件粒度去搬”。

```python
copy_atom = fx.make_copy_atom(
    fx.rocdl.BufferCopy128b(),
    fx.Float32,
)
```

这里的 `BufferCopy128b` 是 **FlyDSL/AMD** 的 128-bit buffer copy atom。若数据是 FP32，一次正好搬 4 个连续值。

**CuTe DSL/NVIDIA** 同样有 `cute.make_copy_atom`、Tiled Copy 与 `cute.copy`，但具体 atom 随架构和路径变化：普通 global/shared copy、cp.async、TMA、TMEM load/store 都不是同一条硬件指令。共同抽象是“atom 定义单次搬运能力，tiled copy 再把它分布给一组 threads”。

如果 thread-value layout 让一个线程负责的 4 个值在 HBM 中连续且对齐，这个 load 会装满有效数据。若四个值分散在远处，就需要更多指令，或者先重排数据。

因此，“数据摆放”至少有四层含义：

```text
逻辑元素映射到哪个相对 offset
→ 哪个 block / thread 拥有它
→ 它在 HBM、LDS、VGPR 中分别怎样排列
→ 每次用多宽的 copy atom 搬运
```

![Thread-value layout 决定每个 lane 搬哪些值，copy 再让数据穿过 HBM、LDS 和 VGPR](images/s13_13_why_dsl_attention_article_img02.png)

*图 8：左边是编译期 ownership 映射，右边才是运行时真实数据路径。`partition_S/D` 只生成线程视图，不是内存层级。*

#### 回到 AMD 的 192/128 案例：为什么这个能力正好有用

MiMo-V2.5-Pro 的 K head 是 192 维，V head 是 128 维。旧的等宽路径把 V padding 到 192，是因为原有 Kernel 的 tile、load 和 fragment 布局都围绕等宽 K/V 建立。

专用路径要做的不是简单删除 64 个零，而是同时重排整条数据路径：

```text
K：按 192 宽度选择 tile、向量读取和 fragment
V：按 128 宽度选择另一套 tile、向量读取和 fragment
两者在 Attention 语义要求的位置重新汇合
```

FlyDSL 的价值就在这里：K 和 V 可以拥有不同的 layout，再通过 composition、divide、partition 和 copy 组合成各自的执行计划。模型仍计算同一个 Attention；变化的是 192 和 128 这些数字怎样落到 AMD 硬件上。

CuTe DSL 在 NVIDIA 上也能表达“K 和 V 使用不同 layout、tile、copy 与 MMA fragment”的同类设计；但是，能表达不等于这个特定 MiMo `192/128` Kernel 已经在 NVIDIA 上实现或验证。本文没有提供该项实测，因此不作命中或性能声明。

> CuTe DSL 与 FlyDSL 不是“可以控制数据”这么泛。更准确地说，它们让 Kernel 作者显式控制：逻辑坐标如何映射到相对偏移、tile 如何分给线程、数据如何穿过目标 GPU 的内存层级，以及最终如何匹配 MMA fragment。

#### 它不是在“控制业务数据”

CuTe DSL 与 FlyDSL 控制的是 GPU Kernel 内部的张量元素，不是数据库里的客户数据。

```text
HBM：远处的大仓库
  ↓
LDS：车间旁的小仓库
  ↓
Register：工人手里的工具箱
  ↓
MFMA：真正执行矩阵乘加
```

![GPU 数据路径](images/s13_13_why_dsl_attention_article_img06.png)

*图 4：高性能 Kernel 的核心工作之一，是让全局显存→片上共享存储→寄存器→矩阵计算单元的数据流持续运转。NVIDIA 常写作 GMEM→SMEM/RMEM→MMA，AMD 常写作 HBM/GMEM→LDS/VGPR→MFMA。*


### 四、CuTe DSL 与 FlyDSL 是怎么提速的？

两套 DSL 都不是“开启即加速”的开关。收益来自工程师借助它们做出的具体执行计划。

#### 机制一：去掉 padding

针对 `K=192、V=128` 原生生成不同宽度的加载和计算路径，不再把 V 补到 192。

直接收益：

- 少分配无效 V 空间；
- 少搬运补零部分；
- 少做无效乘加；
- 少写回最终会被切掉的结果。

这是最容易解释、也最容易验证的一类收益。

#### 机制二：为真实形状选择合适 tile

一个 `128×128` tile 对某些矩阵很好，对 `192×128` 未必最好。

不合适的 tile 可能造成：

- 边界处大量空槽；
- 部分线程没有有效工作；
- Register/LDS 占用过高；
- 同时驻留的 wave 数下降。

专用 Kernel 可以按真实形状选择 `BLOCK_M/BLOCK_N/BLOCK_K`，减少尾块浪费。

#### 机制三：让内存访问连续

GPU 喜欢一组线程读取连续、对齐的地址。如果 64 个线程各自跳着读，硬件可能需要拆成多次内存事务。

通过 layout，工程师可以安排：

```text
相邻线程 → 相邻数据
一次读取 → 4/8/16 个连续元素
整组访问 → 对齐到合适边界
```

同样的字节数，搬运次数更少，实际带宽更高。

#### 机制四：搬一次，多用几次

HBM 很远。高性能 Kernel 会把一个 tile 搬到 LDS，让多个线程反复使用。

```text
糟糕：每做一次乘法都回 HBM 拿数据
良好：一个 tile 搬进 LDS 后完成大量乘加
```

这叫提高 data reuse（数据复用）。

#### 机制五：搬运和计算重叠

处理 tile 0 时，提前搬运 tile 1：

```text
时间轴：
搬 tile0 ──┐
            ├─ 算 tile0 ──┐
            │              ├─ 算 tile1 ──┐
            └─ 搬 tile1 ───┘              ├─ ...
                           └─ 搬 tile2 ────┘
```

如果安排得好，计算单元不必停下来等下一批数据。

#### 机制六：融合中间步骤

如果 QKV 变换、位置编码、类型转换、写 cache 分成多个 Kernel：

```text
Kernel A 写 HBM
Kernel B 再读 HBM
Kernel B 写 HBM
Kernel C 再读 HBM
```

适当融合后，中间结果可以留在 Register/LDS，减少 HBM 往返和 Kernel launch。

但融合不是越多越好。融合过度可能使 Register 压力过大、occupancy 下降。因此仍要基于真实 shape 测量。

![六类收益](images/s13_13_why_dsl_attention_article_img07.png)

*图 5：CuTe DSL / FlyDSL 的收益来自具体优化机制，不来自 DSL 名称本身。图为机制示意，不代表各项收益比例。*


### 五、为什么先用 Python Layout DSL，而不是直接手写 CUDA/HIP C++？

CUDA C++ 与 HIP C++ 当然能做到同样的控制。问题是工程成本。

| 方案 | 优点 | 代价 |
|---|---|---|
| 现成库/预编译 Kernel | 稳定、上线快 | 特殊 shape 可能没有覆盖 |
| Triton | 开发快，适合快速验证 | 线程级 layout 控制通常更间接 |
| CuTe DSL | Python 开发 + CuTe Layout Algebra + NVIDIA 底层能力 | 需要 CUDA 架构与 Kernel 知识 |
| FlyDSL | Python 开发 + CuTe-style Layout Algebra + AMD 底层能力 | 需要 ROCm 架构与 Kernel 知识 |
| CuTe C++ / CK 模板 | 极强的性能与复用能力 | 模板复杂，编译和调试成本高 |
| HIP/CUDA C++ | 控制最直接 | 工作量最大、最易写错 |

对一个新形状，合理路径通常是：

1. 先确认目标平台的现成 CUTLASS/cuDNN/AITER/CK/Triton Kernel 是否已经支持；
2. 若不支持，用 DSL 快速验证正确的 layout 和 tile；
3. 对真实热点 shape 做 benchmark 与 autotune；
4. 稳定后可继续保留 DSL，或按长期维护需要下沉到 CuTe C++/CUDA C++、CK/HIP C++；
5. 用 AOT 预编译覆盖生产常见 shape，避免首次请求 JIT。

所以“必须先做 DSL”的准确含义不是：

> 只有 DSL 能完成数学计算。

而是：

> 当现成 Kernel 没覆盖关键特殊形状时，DSL 往往是补齐专用高性能路径的最快工程入口。

![决策树](images/s13_13_why_dsl_attention_article_img08.png)

*图 6：先复用现成 Kernel；只有关键 shape 缺失或热点性能不够时，才进入 DSL/底层 Kernel 开发。*


### 六、同一套 Layout Algebra，不是同一个后端

CuTe DSL 不是 FlyDSL 文章里的一个“对照物”，它本身就是 NVIDIA CUTLASS 的 Python Kernel DSL；FlyDSL 则是 AMD 对同类 Python layout-programming 需求的实现，并明确采用 CuTe Layout Algebra。

| | AMD | NVIDIA |
|---|---|---|
| GPU 平台 | ROCm/HIP | CUDA |
| Python Kernel DSL | FlyDSL | CuTe DSL |
| 布局思想 | 采用 CuTe Layout Algebra | CuTe Layout Algebra 原生体系 |
| 底层编译 | Python/Fly MLIR → ROCDL/LLVM → HSACO | Python decorator DSL 动态 JIT 到 CUDA 目标 |
| 算子生态 | AITER | CUTLASS/cuDNN/FlashInfer 等 |

ROCm 官方文档明确说明：FlyDSL 采用 CuTe layout algebra 的同一代数框架，并为 AMD ROCm/HIP GPU 提供 Python API 与 MLIR 编译路径。

来源：

- <https://github.com/ROCm/FlyDSL/blob/main/docs/cute_layout_algebra_guide.md>
- <https://rocm.blogs.amd.com/software-tools-optimization/flydsl-python-native/README.html>
- <https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl.html>

这叫“技术位置和设计思想相近”，不是 API 兼容，也不是同一份代码直接换后端。


### 七、客户最容易误解的五件事

#### 误解一：用了 DSL，模型就变了

没有。权重、Attention 公式、输出语义都不应该改变。DSL 改的是执行计划。

#### 误解二：CuTe DSL / FlyDSL 会自动优化所有模型

不会。工程师仍要选择 tile、线程映射、流水级数和融合边界，并通过真实测试验证。

#### 误解三：去掉 16.67% 的 K+V 宽度，模型就快 16.67%

不成立。端到端收益取决于 Attention 在总耗时中的占比，以及瓶颈究竟在计算、显存带宽还是通信。

可用 Amdahl 定律表达：

$$
S_{total}=\frac{1}{(1-p)+p/S_{kernel}}
$$

其中 `p` 是该 Kernel 原来占端到端时间的比例，`S_kernel` 是 Kernel 自身加速倍数。

#### 误解四：既然专用 Kernel 更快，就应该所有 shape 都专用化

专用 Kernel 太多会增加编译、缓存、测试和维护成本。只应覆盖生产中高频、昂贵、稳定的 shape。

#### 误解五：Kernel benchmark 很快，就代表线上服务很快

Kernel benchmark 不含请求调度、KV 管理、跨卡通信、网络、采样和排队。必须分别报告：

```text
Kernel microbenchmark
→ 单节点算子集成
→ 模型端到端
→ 多节点服务
```

上一层通过不能自动为下一层授予 PASS。


### 八、客户该如何验收这项优化？

不要只问“开没开 CuTe DSL/FlyDSL”，而要问下面这些可验证问题：

| 验收问题 | 需要的证据 |
|---|---|
| 是否真的命中目标 DSL Kernel？ | 运行日志中的具体 CuTe DSL/FlyDSL Kernel 名称、版本与 GPU 平台 |
| 是否去掉 V padding？ | 生效的 K/V head dimension 与 KV allocation |
| 数值是否一致？ | 与 BF16/PyTorch reference 的误差测试 |
| Kernel 自身快多少？ | 同 shape、同 dtype、同 warmup 的 microbenchmark |
| 模型端到端快多少？ | 同请求集、同并发、同输出长度的 E2E |
| 首次请求是否受 JIT 影响？ | 冷启动与缓存命中分别报告 |
| 生产常见 shape 是否覆盖？ | AOT/JIT Kernel manifest 与 fallback 统计 |
| 未命中时发生什么？ | 明确 fallback 到 CUTLASS/cuDNN/CK/Triton/CUDA/HIP 的日志 |

**真正的交付不是“有 CuTe DSL/FlyDSL 代码”，而是“目标 workload 确实命中新 Kernel，结果正确，且端到端收益可复现”。**


### 九、五句话记住

**第一句**：通用 Kernel 不是笨，而是它只为已经覆盖的形状负责。

**第二句**：特殊模型结构可能被 padding 成通用形状，能跑，但会浪费内存搬运和计算。

**第三句**：CuTe DSL 与 FlyDSL 都不改变公式，而是显式安排 tile、线程、内存层级和流水。

**第四句**：提速来自去 padding、少搬运、多复用、搬算重叠和合理融合，不来自“DSL”三个字。

**第五句**：Kernel 快不等于模型快；必须按 microbenchmark → 单机 E2E → 多节点逐级验收。


### 参考资料

- XiaomiMiMo/MiMo-V2.5-Pro 官方模型配置：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro/blob/main/config.json>
- ROCm/FlyDSL 官方仓库：<https://github.com/ROCm/FlyDSL>
- FlyDSL CuTe Layout Algebra Guide：<https://github.com/ROCm/FlyDSL/blob/main/docs/cute_layout_algebra_guide.md>
- FlyDSL Architecture Guide：<https://github.com/ROCm/FlyDSL/blob/main/docs/architecture_guide.md>
- NVIDIA CuTe DSL Introduction：<https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl_general/dsl_introduction.html>
- NVIDIA CuTe DSL Programming Model：<https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl.html>
- NVIDIA CuTe Layout Algebra Notebook：<https://github.com/NVIDIA/cutlass/blob/main/examples/python/CuTeDSL/cute/notebooks/cute_layout_algebra.ipynb>
- NVIDIA Tour of SOL GEMM Notebook：<https://github.com/NVIDIA/cutlass/blob/main/examples/python/CuTeDSL/cute/notebooks/tour_to_sol_gemm.ipynb>
- FlyDSL CuTe Layout Algebra Guide：<https://github.com/ROCm/FlyDSL/blob/main/docs/cute_layout_algebra_guide.md>
- AMD ROCm Blog — FlyDSL Python Native：<https://rocm.blogs.amd.com/software-tools-optimization/flydsl-python-native/README.html>
- ROCm/AITER 官方仓库：<https://github.com/ROCm/aiter>
- NVIDIA CuTe DSL：<https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl.html>
- 本系列前作：《Triton、FlyDSL、CK、HIP C++ 到底差在哪？》

> 本文所有百分比均为公开模型 shape 的确定性算术，用于解释 padding 与数据布局，不代表任何具体平台的端到端实测性能。
<!-- SOURCE-END id=13 -->

---

<!-- SOURCE-BEGIN id=14 source=14_head_limit_tp_dp_ep_article.md sha256=40545d5104c1bc78dbf8912221d931a9d7a510f6c0f3e60d1ec54816f15a9a63 body_sha256=a7d0402d064464fd01a10321872e440854a36df3bf5a58479e2e49e188ffec51 -->
## 原稿 #14：为什么 16 张卡反而切不动？从 8 个 KV Heads 讲透 TP、DP 和 EP

> 卡越多，不一定越容易切。MiMo-V2.5-Pro 有 128 个 Query heads，却只有 8 组 KV（Key-Value，键值）heads；真正限制 Attention 并行度的，恰恰是这个更小的数字。







### 先把几个词说清楚

| 缩写 | 英文全称 | 本文中的意思 |
|---|---|---|
| GPU | Graphics Processing Unit | 图形处理器，也就是文章里的“卡” |
| Q / K / V | Query / Key / Value | Attention 中的查询、键和值 |
| KV | Key-Value | K 与 V 的合称；KV cache 保存历史 token 的 K/V 状态 |
| TP | Tensor Parallelism | 张量并行，多张卡合做同一份计算 |
| DP | Data Parallelism | 数据并行，多组卡分别处理不同请求 |
| EP | Expert Parallelism | 专家并行，把完整专家分散到不同 ranks |
| MoE | Mixture of Experts | 混合专家模型，每个 token 只激活部分专家 |
| GQA | Grouped Query Attention | 分组查询注意力，多组 Q 共享较少的 KV heads |
| SWA | Sliding Window Attention | 滑动窗口注意力，只关注局部历史窗口 |
| MTP | Multi-Token Prediction | 多 Token 预测，用轻量模块预测后续多个 token |
| LM head | Language Model head | 语言模型输出头，把 hidden state 投影到词表 |
| FP8 | 8-bit Floating Point | 8 位浮点格式，用于权重、激活或 KV cache 等低精度表示 |
| PD | Prefill/Decode Disaggregation | 预填充/解码分离，把 Prefill 和 Decode 部署到不同服务或节点 |


### 一个反直觉的问题

一台服务器有 8 张 GPU，Attention Tensor Parallelism（TP，张量并行）设成 8，模型能正常运行。

现在增加到两台服务器、16 张 GPU。直觉上，把 TP 从 8 改成 16，应该能把模型切得更细：

```text
8 张卡能切，16 张卡应该更能切。
```

实际情况却可能相反：服务在加载权重时就失败，连第一个请求都收不到。

问题不在 GPU 数量，也不在某张“特殊的卡”。真正的限制来自模型 Attention 的 head 布局，以及 checkpoint 当初是怎样分片、量化和保存的。

这篇文章从这个具体问题出发，依次讲清楚：

- 模型里到底有哪些“head”；
- 为什么 Query head 能继续切，KV head 却卡住了；
- 强行切半个 KV head 会改变哪些计算和通信；
- Data Parallelism（DP，数据并行）如何绕开这个限制；
- `TP8 / DP4 / EP32` 到底如何在同一批 32 张 GPU 上同时成立；
- TP、DP 和 Expert Parallelism（EP，专家并行）分别切什么。

![模型中真正需要区分的 head 与模块](images/s14_14_head_limit_tp_dp_ep_article_img01.png)

*图 1：Attention head、LM head 和 MTP module 名字里都可能出现“head”，但它们不是同一种可分割对象。*


### 先把模型里的“head”数清楚

以公开模型 `XiaomiMiMo/MiMo-V2.5-Pro` 为例，官方配置给出的关键结构如下。

| 组件 | 数量或形状 | 它是什么 |
|---|---:|---|
| Transformer layers | 70 | 1 个 Dense 层 + 69 个 MoE 层 |
| Global Attention layers | 10 | 可以看完整历史上下文 |
| Sliding Window Attention layers | 60 | 每层只看 128-token 局部窗口 |
| Query heads | 128 / Attention 层 | 产生查询向量 Q |
| Key heads | 8 / Attention 层 | 产生匹配索引 K |
| Value heads | 8 / Attention 层 | 产生被汇总的内容 V |
| Q/K head dimension | 192 | 每个 Q、K head 的宽度 |
| V head dimension | 128 | 每个 V head 的宽度 |
| LM head | 1 个输出模块 | 把 6144 维 hidden state 投影到 152,576 词表 |
| MTP modules | 3 | Multi-Token Prediction（多 Token 预测）模块，不是 Attention head |
| Routed experts | 384 / MoE 层 | 每个 MoE 层拥有的专家总数 |
| Experts per token | 8 | 每个 token 实际激活的专家数 |

来源：

- XiaomiMiMo 官方模型卡：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro>
- 官方 `config.json`：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro/blob/main/config.json>

这里最容易混淆三件事。

`1 Dense + 69 MoE` 描述每层的 FFN 类型，`10 Global + 60 SWA` 描述每层的 Attention 类型；这是两条交叉分类轴。第 0 层既是唯一的 Dense FFN 层，也是 10 个 Global Attention 层之一。

#### LM head 不是 152,576 个 Attention heads

LM head 是一个输出投影模块：

```text
[hidden_size = 6144]
          ↓ LM head
[vocab_size = 152576]
```

它可以按词表维度或 hidden 维度做矩阵分片，也可以按运行时策略复制。它没有“只有一个，所以不能被 TP8 整除”的问题。

#### 3 个 MTP modules 也不是 3 个 Attention heads

MTP（Multi-Token Prediction，多 Token 预测）用三个轻量模块预测后续 token，帮助 speculative decoding（推测解码）。这里的 3 表示预测模块层数，不参与 `128 ÷ TP` 或 `8 ÷ TP` 的 head 分配。

#### MiMo-V2.5-Pro 没有一部分 MQA、一部分 GQA

这个模型混合的是两种**注意范围**：

```text
10 层 Global Attention
60 层 Sliding Window Attention
```

两类层使用的都是：

```text
128 个 Q heads
8 个 K heads
8 个 V heads
```

这属于 GQA（Grouped Query Attention，分组查询注意力）。每 16 个 Q heads 共用一组 K/V：

$$
128 \div 8 = 16
$$

MQA（Multi-Query Attention，多查询注意力）只有 1 组 KV heads；MHA（Multi-Head Attention，多头注意力）则让 Q、K、V head 数量相同。不要把 Global Attention 的 `GA` 和 GQA 混在一起。

![MHA、GQA、MQA 的区别](images/s14_14_head_limit_tp_dp_ep_article_img02.png)

*图 2：Hybrid Attention 描述“看多远”，MHA/GQA/MQA 描述“Q 如何共享 K/V”，它们是两条不同的分类轴。*


### 为什么 TP8 刚好，TP16 却卡住

TP 的基本动作是：把同一层的大矩阵或多个 heads 分给一组 GPU，共同处理**同一批请求**。

对 MiMo-V2.5-Pro，Attention TP8 的分配非常整齐：

| 每个 Attention TP rank | 分到多少 |
|---|---:|
| Q heads | `128 ÷ 8 = 16` |
| K heads | `8 ÷ 8 = 1` |
| V heads | `8 ÷ 8 = 1` |
| Q rows | `16 × 192 = 3072` |
| K rows | `1 × 192 = 192` |
| V rows | `1 × 128 = 128` |
| fused QKV rows | `3072 + 192 + 128 = 3392` |

每张 GPU 不是“Q 卡”“KV 卡”或“LM 卡”。同一个 rank 同时持有这一层的 Q/K/V 分片、输出投影分片，以及运行时分配给它的其他模型权重。

如果把 Attention TP 直接改成 16：

```text
Q：128 ÷ 16 = 8 heads / rank     可以
K：  8 ÷ 16 = 0.5 head / rank   当前路径不支持
V：  8 ÷ 16 = 0.5 head / rank   当前路径不支持
```

真正卡住的是 K/V，不是 Q，更不是 LM head。

![TP8 与 TP16 的 head 分配](images/s14_14_head_limit_tp_dp_ep_article_img03.png)

*图 3：TP16 不是 GPU 不够，而是 8 组 KV heads 无法按当前“完整 head 分配”路径平均放到 16 个 Attention ranks。*


### 这不是纯数学限制，而是 checkpoint 与 Kernel 合同

从数学上说，一个 192 维的 K head 当然可以切成两半：

```text
rank 0：K 的前 96 维
rank 1：K 的后 96 维
```

但 Attention 不能让两边各算各的就结束。

对于一个 Query 和 Key：

$$
QK^T = Q_0K_0^T + Q_1K_1^T
$$

两张卡必须先把部分点积相加，才能进入 Softmax。V 也要保持分片并在后面合并，或者再做一次通信。

于是“切半个 head”会牵动整条路径：

1. Q/K/V 权重加载方式；
2. FP8 scale 的分片与索引；
3. KV cache 的内存布局；
4. QK 点积在 Softmax 前的跨卡归约；
5. V 输出的分片与合并；
6. Global Attention、SWA 和 Paged Attention kernel；
7. Prefill/Decode 之间的 KV 序列化合同。

MiMo-V2.5-Pro 的公开 FP8 fused-QKV checkpoint 是按 Attention TP8 的 rank 交错方式导出的。SGLang 官方支持说明记录了一个直接失败签名：把错误的并行参数用于加载时，checkpoint 中的 scale shape 为 `[216, 48]`，运行时却构造出 `[212, 48]`。

这两个数字来自不同的分块顺序：

```text
每个 TP8 rank 的 fused-QKV rows = 3392
FP8 block rows / rank            = ceil(3392 ÷ 128) = 27
checkpoint 保存 8 个独立分片    = 8 × 27 = 216

如果先把 8 个分片拼平再分块：
ceil((3392 × 8) ÷ 128) = ceil(27136 ÷ 128) = 212
```

`216` 保留了“每个 TP8 rank 独立量化”的边界；`212` 则错误地把它当成一整块连续矩阵。两者不是 padding 几行就能静默忽略的差异。

这不是“精度可能差一点”，而是权重无法按预期落到参数上，服务启动失败。

来源：SGLang MiMo-V2.5-Pro day-0 support：<https://github.com/sgl-project/sglang/pull/23808>

![切分单个 KV head 带来的计算与通信](images/s14_14_head_limit_tp_dp_ep_article_img04.png)

*图 4：切 head 内部维度并非不可实现，但必须在 Softmax 前汇总部分点积，并重做 V 输出、KV cache 和 kernel 合同。*


### 两个看似简单的绕法，为什么都不理想

#### 绕法一：复制 KV heads

如果 8 个 KV heads 不够分给 16 张卡，可以让相邻两张卡各存一份相同的 KV head：

```text
rank 0、1   → 都保存 KV head 0
rank 2、3   → 都保存 KV head 1
...
rank 14、15 → 都保存 KV head 7
```

一些通用 GQA runtime 会采用类似策略。但它有两个代价：

- KV cache 被复制，增加卡数没有扩大有效 KV 容量；
- 当前 FP8 fused-QKV checkpoint 仍按 TP8 rank 分片，复制 KV 并不能自动修好 weight loader 和 scale shape。

它可以是某些模型、某些 checkpoint 的合法实现，却不是把这个模型的 `--tp` 从 8 改成 16 就能得到的免费能力。

#### 绕法二：让每个 head 横着切

这就是前面讨论的 head-dimension parallel Attention。它能扩大单个请求使用的设备范围，但会把跨卡通信放进每层 Attention 的关键路径。

数学上可行，工程上需要一条新的分布式 Attention 实现。没有对应 kernel、checkpoint adapter 和 KV layout，就不能把它当作配置选项。


### 实际解法：不要把 Attention TP 扩到 16

两台 8-GPU 服务器可以组成两个独立的 Attention TP8 组：

```text
Attention 组 A：GPU 0–7，处理请求集合 A
Attention 组 B：GPU 8–15，处理请求集合 B
```

这就是 DP Attention（Data-Parallel Attention，数据并行注意力）的核心：

- 每组内部仍是 Attention TP8；
- 不同组处理不同请求；
- 每组拥有自己的请求状态和 KV cache；
- Attention 公共权重在组之间复制；
- MoE experts 可以继续在更大的 EP 域中全局分片。

当前 SGLang 的关键关系是：

$$
\text{effective Attention TP} = \frac{\text{global TP size}}{\text{DP size}}
$$

两节点 16 GPU 的官方示例使用：

```text
--tp 16 --dp 2 --ep 16 --enable-dp-attention
```

因此：

```text
effective Attention TP = 16 ÷ 2 = 8
```

这里的 `--tp 16` 是全局 rank 域，不表示每个 Attention 计算真的拆成 TP16。启用 DP Attention 后，它被分成两个 effective TP8 组。

同理，四节点 32 GPU 的概念拓扑是：

```text
--tp 32 --dp 4 --ep 32 --enable-dp-attention
```

注意不是 `32 × 4 × 32` 张卡。仍然只有 32 个 ranks，只是同一批 ranks 在不同模块中加入不同的通信组。


### TP8 / DP4 / EP32 到底怎么切

以 32 张 GPU 为例。

#### Attention：四个 TP8 组

```text
DP0：ranks  0–7  → Attention TP8
DP1：ranks  8–15 → Attention TP8
DP2：ranks 16–23 → Attention TP8
DP3：ranks 24–31 → Attention TP8
```

每组内部，每个 rank 仍然拿到：

```text
16 个 Q heads
1 个 K head
1 个 V head
```

四个组处理不同请求，所以这是数据并行；组内八张卡共同完成同一请求，所以组内又是张量并行。

#### MoE：一个全局 EP32 专家域

每个 MoE 层有 384 个 routed experts：

$$
384 \div 32 = 12
$$

每个 EP rank 保存 12 个完整专家。每个 token 只激活 8 个专家；这个 `top-8` 是 Router 的选择数，不需要除以 32。

#### LM head：不是这次 TP8 限制的来源

LM head 是输出矩阵。运行时可以对词表维度分片、复制，或使用专门的 DP LM-head 路径。它是否分片由框架实现决定，不受“只有 8 个 KV heads”这个约束。

152,576 这个词表大小恰好可以被 8 和 32 整除，但即使不能整除，常见 runtime 也可以 padding 词表行。它不是当前 fused-QKV 启动失败的控制点。

![TP8、DP4、EP32 的通信组](images/s14_14_head_limit_tp_dp_ep_article_img05.png)

*图 5：同一批 32 个 ranks 在 Attention 阶段组成 4 个 TP8 组，在 MoE 阶段又共同组成 1 个 EP32 专家域。*


### 一个 token 在这套拓扑中怎样走

假设请求 A 被分给 DP0。

```text
请求 A
  ↓
DP0 的 8 张卡共同完成 Attention
  ↓
Router 为每个 token 选出 8 个 experts
  ↓
token hidden states 通过 EP32 AllToAll 发往专家所在 ranks
  ↓
专家计算完成，结果 combine 回 DP0
  ↓
DP0 进入下一层 Attention
```

这里要区分两种完全不同的数据：

- EP 跨节点传的是当前层的 token hidden states 和路由信息；
- KV cache 属于 Attention 状态，稳态下留在请求所属的 TP8 Attention 组。

因此，EP32 扩大的是专家权重分布域，不会让一个请求的 KV cache 自动铺到全部 32 张卡上。

PD（Prefill/Decode Disaggregation，预填充/解码分离）是例外。Prefill 和 Decode 在不同服务器时，Prefill 算好的 KV cache 会通过 Mooncake 等传输引擎交给 Decode 节点。那是角色交接时的 KV 点对点传输，不是每一层 EP AllToAll。

![Token 路由与 KV cache 的不同路径](images/s14_14_head_limit_tp_dp_ep_article_img06.png)

*图 6：hidden states 跟随 EP 路由跨专家域；KV cache 跟随请求归属留在 Attention 组，只有 PD 角色交接时跨节点传输。*


### DP 和 TP 到底差在哪

这两个概念最容易因为“都用了多张卡”而混在一起。

#### TP：多张卡合做同一个请求

TP 切的是同一个算子的权重和计算：

```text
同一个请求
  ├─ rank 0 算一部分
  ├─ rank 1 算一部分
  └─ ...
最后通过 collective 合成完整结果
```

特点是：

- 权重在 TP 组内分片；
- 单个请求同时占用整组 GPU；
- 多层都需要同步通信；
- 可以降低每卡权重占用；
- 对尾延迟、慢 rank 和跨节点通信很敏感。

#### DP：多组卡分别做不同请求

DP 不切同一个请求：

```text
请求 A → DP0
请求 B → DP1
请求 C → DP2
请求 D → DP3
```

普通 DP 会复制整套模型。DP Attention + EP 则更精细：

- Attention 和公共层按 DP 组复制；
- 每组内部继续用 TP8；
- 专家权重不随 DP 组复制，而是通过 EP32 全局分片。

所以 `TP8 / DP4 / EP32` 不是“4 份完整 1T 模型”。被复制的是公共 Attention 路径；占模型绝大多数的 MoE expert 权重由 32 张卡共同保存一份全局专家池。

#### EP：数据去找专家

EP 不切 Q/K/V heads。它把完整 experts 分散到不同 ranks：

```text
384 experts ÷ EP32 = 12 experts / rank
```

Router 选择哪些 experts，token 就通过 dispatch 去哪些 ranks；算完再 combine 回原来的 Attention 组。

![TP、DP、EP 的核心区别](images/s14_14_head_limit_tp_dp_ep_article_img07.png)

*图 7：TP 切一项计算，DP 切请求集合，EP 切专家集合。三者可以在同一模型层里同时出现。*


### 哪些数字必须整除，哪些不是

| 数字 | 本拓扑中的约束 | 原因 |
|---|---|---|
| 128 Q heads | 必须能被 effective Attention TP8 分配 | 每 rank 16 个 Q heads |
| 8 K heads | 当前 checkpoint/runtime 要求 effective TP8 | 每 rank 1 个完整 K head |
| 8 V heads | 当前 checkpoint/runtime 要求 effective TP8 | 每 rank 1 个完整 V head |
| Q/K dim 192 | 当前策略不按 TP8 切 head 内部维度 | 完整 head 归一个 Attention rank |
| V dim 128 | 当前策略不按 TP8 切 head 内部维度 | 与 K 非对称，由专用 kernel 支持 |
| 384 experts | EP32 下均分为每 rank 12 个 | 当前 DeepEP/均匀 expert placement 合同 |
| top-8 experts/token | 不除以 EP32 | 表示 Router 每 token 选择 8 个专家 |
| 3 MTP modules | 不除以 TP8 | 是预测模块层数，不是 Attention heads |
| 70 layers | 没有 PP 时不按 GPU 数切 | 只有 Pipeline Parallelism 才按层切阶段 |
| 1 个 LM head | 不做“1 ÷ 8” | 它是矩阵模块，不是 Attention head 个数 |

最准确的说法不是“KV head 永远不能切”，而是：

> 这个 FP8 fused-QKV checkpoint 与当前 SGLang loading/kernel 路径要求 effective Attention TP=8。若要切单个 KV head 的内部维度，需要新的 checkpoint adapter、KV layout 和 distributed Attention kernel。


### 强行改成 TP16，会留下什么后遗症

| 做法 | 能否启动 | 主要后果 |
|---|---|---|
| 直接把 `--tp 8` 改成 `--tp 16` | 当前路径不能 | FP8 scale/weight shape 不匹配，启动失败 |
| 把单个 KV head 横切两半 | 需要新实现 | Softmax 前增加归约；V、KV layout、所有 Attention kernel 都要改 |
| 复制 KV heads 到两张卡 | 取决于 runtime/checkpoint | KV cache 复制，增加 GPU 却不扩大有效 KV 池 |
| 使用 DP Attention | 官方路径 | 保持 effective TP8；增加请求吞吐，但单请求 KV 仍只属于一个 TP8 组 |
| 使用 EP32 | 官方 MoE 路径 | 专家权重跨 32 ranks 分片；增加 MoE AllToAll，不改变 Attention head ownership |

这里没有免费的午餐：

- TP16 想扩大单请求 Attention 域，就要付出新的跨卡归约和 kernel 复杂度；
- DP4 保持成熟 TP8 路径，代价是公共权重复制，收益是总请求吞吐；
- EP32 节省专家权重副本，代价是动态 AllToAll 与负载均衡。


### 设计并行拓扑时，按这个顺序问

#### 一、checkpoint 是按什么 TP 导出的？

先看权重和 quantization scale 的真实布局。参数名字能写成 16，不代表 checkpoint 能按 16 加载。

#### 二、Attention 的最小可分单元是什么？

检查 Q heads、KV heads、head dimension，以及 runtime 是分 head、复制 KV，还是支持 head-dimension parallel。

#### 三、模型的大头权重在哪里？

Dense 模型主要看 TP/PP；MoE 模型还要看 experts 是否应该用 EP 分开，避免把每个专家都切成很窄的矩阵。

#### 四、目标是单请求延迟，还是集群总吞吐？

- 想让一个请求用更多卡：关注 TP、PP、Context Parallelism；
- 想同时处理更多请求：关注 DP；
- 想分散 MoE expert 权重：关注 EP。

如果目标没说清楚，“把并行度调大”没有意义。


### 最后记住六句话

**第一句**：GPU 不是 Q 卡、KV 卡或 LM 卡；每个 rank 同时持有多个模块的分片。

**第二句**：MiMo-V2.5-Pro 的 10 个 Global Attention 层和 60 个 SWA 层都是 `128 Q / 8 KV` 的 GQA，不是 MQA/GQA 混用。

**第三句**：TP8 能跑、TP16 不能直接跑，控制点是 8 个 KV heads 与 TP8-interleaved fused-QKV checkpoint。

**第四句**：DP Attention 不是切半个 KV head，而是多开几个完整 TP8 Attention 组，分别处理不同请求。

**第五句**：`TP8 / DP4 / EP32` 中，Attention 有 4 个 TP8 组，384 个 experts 则通过 EP32 分成每卡 12 个。

**第六句**：TP 切同一个计算，DP 切请求，EP 切专家；它们不是三选一，而是可以同时存在的三条并行轴。


### 参考资料

- XiaomiMiMo/MiMo-V2.5-Pro 模型卡：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro>
- MiMo-V2.5-Pro `config.json`：<https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro/blob/main/config.json>
- SGLang MiMo-V2.5 Cookbook：<https://docs.sglang.io/cookbook/autoregressive/Xiaomi/MiMo-V2.5>
- SGLang MiMo-V2.5-Pro day-0 support：<https://github.com/sgl-project/sglang/pull/23808>

> 文中的模型结构、head 数量和 shape 来自公开配置；并行约束特指公开 FP8 fused-QKV checkpoint 与对应 SGLang 路径。其他模型、checkpoint 或 runtime 可能支持 KV replication、不同 TP layout 或 head-dimension parallel，不能直接套用本文结论。
<!-- SOURCE-END id=14 -->

---

## 本篇可逆合并账本

| 原稿 | 原始 SHA-256 | 正文 SHA-256 | 原图 |
|---:|---|---|---:|
| #1 `5d_kv_cache_article.md` | `271476111d1ac493e8fb7807fb434649048a7c1886f443e0c28225ff379cb9f1` | `6a1fbcddb29776a820efd4dd2f2a6933704047957288304dc591418510779845` | 5 |
| #4 `04_paged_flash_aiter_article.md` | `ebf09f31954ddbff777cee87d13e1b9335cd5932b2aef72a4d060099dff2c662` | `d69c2f45097c1b02bc86aa4117eadf7ff6300b2781519cd9d5d2a75ef035be92` | 17 |
| #5 `05_tp_vs_ep_article.md` | `d40a6ea2dcd88cd9f69d5044b4f46ab13d91ebbebd8f02fc4e2c2099559e3a0d` | `1ce6ab8ed41c4df7d0ed099edd53d762f68c578f626fbd13052e672d42a24f02` | 12 |
| #13 `13_why_dsl_attention_article.md` | `4d1f179fad7e54be6c80e65bd80c841f233b02d11ab96fbd81ed9eac5ea048d9` | `8892ad9dfc0047b2b7a9c82f370ac2aefe5ab179952e277371fddec9830b8e38` | 8 |
| #14 `14_head_limit_tp_dp_ep_article.md` | `40545d5104c1bc78dbf8912221d931a9d7a510f6c0f3e60d1ec54816f15a9a63` | `a7d0402d064464fd01a10321872e440854a36df3bf5a58479e2e49e188ffec51` | 7 |

> 账本中的正文 SHA 对应“移除重复发布脚手架、抽取原图并提升标题层级”后的确定性正文。生成器会从本篇反向提取每个来源区间并逐字节比较；任一缺行、错序或缺图都会失败。
