# 在 Azure GPU 虚拟机上优化大模型推理

[![Hardware](https://img.shields.io/badge/Azure-ND%20MI300X%20v5-0078D4)](#架构与测试环境)
[![Engine](https://img.shields.io/badge/SGLang-fork%20878fff1-2E7D32)](upstream/SOURCES.lock.json)
[![Comparison](https://img.shields.io/badge/comparison-MI300X%20vs%20MI300X-6A1B9A)](#mi300x-实测结果)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/llm-inference-optimization-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/llm-inference-optimization-ci.yml)

**同样的 GPU，一个支持 1M 上下文的 MoE 模型到底能提速多少？提速又落在哪一层？** 本仓库以 Azure ND MI300X v5 虚拟机上的 MiMo-V2.5-Pro 为例（384 个路由专家、滑动窗口与 GQA 混合注意力、3 层 MTP），把推理链路上用到的全部优化手段逐项讲清楚。这些手段分属三层：推理框架层、算子层、负载与部署层。每一项都给出打开它的开关、固定 commit 里真实的代码改动（有代码改动的话）、它对模型输出的影响；实测过的项目还给出它让 MI300X 相对 MI300X 自己快了多少。

优化后的栈比基线栈快多少（都在 MI300X 上实测，MI300X 自己和自己比）：

<!-- BEGIN GENERATED: cumulative -->
| MI300X 上实测 | 优化前 → 后 | 倍数 |
|---|---|---:|
| Decode 图捕获，单开关<br>16K/1K，16 路并发，基线栈 | 107.4 → 334.0 tok/s | **3.11×** |
| 128K prefill，1 个请求，8 张 GPU<br>单机 → 1P1D 的 prefill 服务 | 6,915 → 16,390 tok/s | **2.37×** |
| Decode 每 token 耗时，64 路并发<br>MTP 固定接受长度 3，越低越好 | 45.86 → 17.00 ms | **2.70×** |
| Decode 每 token 耗时，64 路并发<br>MTP 按实际接受，越低越好 | 45.86 → 30.07 ms | **1.53×** |
| 64K prefill，4 路并发<br>基线栈 prompt 平均 60,610 token | 13,919 → 19,023 tok/s | **1.37×** |
| 8K prefill，4 路并发<br>基线栈 prompt 平均 7,792 token | 16,644 → 20,781 tok/s | **1.25×** |
<!-- END GENERATED: cumulative -->

<!-- BEGIN GENERATED: glance -->
- 在其余不变的栈上单独改一项：block-scale FP8 GEMM 与 unified verify 两个开关让 64K 上下文 decode **+25.65%**（同一会话 A/B）；按 shape 调优的 fused-MoE 表让 8K prefill **+24.32%**（[详情](#单项优化各自带来多少)）。
- 这些倍数不能相乘：每一行比较的是不同的一对运行。每一行的负载和拓扑见[从基线栈到优化后](#从基线栈到优化后累计提升)。本页没有任何性能数字拿 MI300X 和其他加速器比较。
<!-- END GENERATED: glance -->

框架层和负载层可以原样搬到 NVIDIA GPU 上，算子层每一项都写明了 CUDA 上的对应实现。

作者：Xinyu Wei · [English](README.md) · [实测结果](#mi300x-实测结果) · [三层优化](#三层优化逐项拆解) · [复现](#客户如何复现) · [测试](#测试与离线校验)

## 从这里开始

| 想做什么 | 入口 |
|---|---|
| 看从基线栈到优化后总共快了多少 | [从基线栈到优化后](#从基线栈到优化后累计提升) |
| 看单项优化各自带来多少 | [单项优化各自带来多少](#单项优化各自带来多少) |
| 看吞吐从 8K 到 256K 上下文怎样变化 | [吞吐怎样随上下文长度变化](#吞吐怎样随上下文长度变化) |
| 查公开基准上的准确率 | [在优化后的 kernel 上实测的准确率](#在优化后的-kernel-上实测的准确率) |
| 查某一项优化：开关、代码、证据、对输出的影响 | [三层优化逐项拆解](#三层优化逐项拆解) |
| 把这套方法用到 NVIDIA GPU 上 | [迁移到 NVIDIA GPU](#迁移到-nvidia-gpu)，以及 `cuda-hopper-pd` profile |
| 在你的 MI300X 虚拟机上部署优化后的栈 | [客户如何复现](#客户如何复现) |
| 不用 GPU 核对已发布的数字 | [测试与离线校验](#测试与离线校验) |

## 本仓库做了什么、提供什么

- **推理引擎与 kernel**——归上游 SGLang、AMD AITER、Composable Kernel、FlyDSL 项目；MiMo 专用的提交是 AMD 工程师在公开 fork 中完成的。这里提供固定的 commit 身份，以及文中讨论的每个 commit 的完整 patch（[`upstream/`](upstream/)）。
- **优化方法与实测数据**——本仓库。MI300X 优化前后的实测对比，附原始压测输出的公开投影（[`evidence/`](evidence/)）；逐项技术解读和代码摘录；每个数字的适用边界。
- **启动配置**——本仓库。实测 MI300X 栈的机器可读 profile 和一份 NVIDIA 模板（[`profiles/`](profiles/)），可渲染成启动命令，并支持单项消融（[`tools/render_launch.py`](tools/render_launch.py)）。
- **部署**——本仓库。从公开源码构建固定版本 runtime 的 Dockerfile、把每个服务角色作为独立容器启动的脚本、就绪检查和设置模板（[`docker/`](docker/)）。
- **校验**——本仓库。离线测试和 CI，从已提交的证据重新算出每个发布的数字。

你需要自备：Azure ND MI300X v5 容量（PD 路线两台，单机路线一台）、MiMo-V2.5-Pro 权重，以及能访问 RDMA 的容器宿主机。

不提供：模型权重；证据投影背后的私有原始日志（只记录其 SHA-256）；与其他加速卡的比较；打开 FP8 KV cache 时的准确率结果；任何 NVIDIA 上的实测。每项优化会对准确率产生什么影响、怎么核对，见[哪些优化可能改变模型输出](#哪些优化可能改变模型输出)。

## MI300X 实测结果

所有数字都是 MI300X 和 MI300X 自己比。建议从上往下读：先看从基线栈到优化后的总提升，再看单项优化各自带来多少，最后是每组对比的细节。优化后的测试打开了 FP8 KV cache，阶段对比那几次运行记录的环境显示 INT8 Quick Reduce 也是打开的。两者都有损，它们对准确率的影响本仓库没有测，见[哪些优化可能改变模型输出](#哪些优化可能改变模型输出)。

### 从基线栈到优化后：累计提升

**问题。** 所有优化都打开以后，同一个模型、同一批 MI300X 虚拟机，比第一版能跑起来的栈快多少？

**输入。** 基线栈，即第一版把模型跑起来的配置：SGLang v0.5.11、Triton FP8 GEMM，不开投机解码，KV cache 用默认类型。它的 decode 和 128K prefill 测点用 Triton attention；8K/64K prefill 测点已经在用 AITER attention。它的 128K prefill 测点跑在一台 VM 上，其余测点和优化后一样是两台 VM 的 1P1D。优化后的栈：下文[阶段对比](#阶段对比按-shape-调优的-fused-moe-表)用的栈，即 AITER attention、CK FP8 GEMM、FP8 KV、EAGLE MTP、调优 fused-MoE 表，1P1D 走 8 路 InfiniBand。单开关那一行比较的是基线栈在同一轮会话里的两次运行。

这组对比的倍数见页面顶部的表格。

Decode 的倍数在很大程度上取决于 MTP 草稿 token 的接受率。优化后的吞吐测试把接受长度固定为每步 3 个 token，这是偏乐观的条件；同一套栈的一个较早版本，在同样的随机 prompt 上按草稿模型实际达到的接受率跑过一次，可作参考点。两者逐点列出（每个数值下方是相对基线栈的倍数）：

<!-- BEGIN GENERATED: cumulative-decode -->
| 指标 | 基线栈<br>16K 输入 | 按实际<br>接受 | 固定接受<br>长度 3 |
|---|---:|---:|---:|
| TPOT ms<br>并发 32 | 29.41 | 23.20<br>1.27× | 13.65<br>2.15× |
| TPOT ms<br>并发 64 | 45.86 | 30.07<br>1.53× | 17.00<br>2.70× |
| tok/s<br>并发 32 | 658 | 1,238<br>1.88× | 1,936<br>2.94× |
| tok/s<br>并发 64 | 1,396 | 1,645<br>1.18× | 2,458<br>1.76× |
<!-- END GENERATED: cumulative-decode -->

**边界。** 这是前后对比，不是 A/B：kernel、库版本和启动参数是一起变的，所以倍数属于整套栈，不属于某一项改动。基线栈的 decode 输入是 16K token，优化后是 8K。上下文越短，每步 decode 越便宜，所以 decode 倍数里有一部分来自负载差异，而不是栈本身。按实际接受的那次运行用的是较早的 AITER 版本，没有调优 fused-MoE 表，也没开 unified verify，而且随机 prompt 很难猜中，所以它说明不了真实流量上的接受率。基线栈的 8K 和 64K prompt 平均为 7,792 和 60,610 个 token，优化后的运行是正好 8,192 和 65,536，所以这两个倍数是近似值。基线栈的 128K 测点跑在一台 VM 上，prefill 和 decode 在同一个服务里；优化后的测点跑在 1P1D 的 prefill 服务上；两者都用 8 张 GPU 做 prefill。基线栈的 decode 和 128K 数值来自汇总报告；图捕获这一对以及基线栈的 8K/64K prefill 测点是客户端原始输出。基线栈的客户端在大约 340 个输出 token（请求的是 1,024）时就结束了请求，所以图捕获的倍数只能在这两次运行之间比较。来源和哈希见 [`evidence/runs.json`](evidence/runs.json) 和 [`evidence/raw-manifest.json`](evidence/raw-manifest.json)。

### 单项优化各自带来多少

每一行只在其余不变的栈上改一处。A/B 是同一轮测试里只改指定的开关；阶段对比是在更新一个库的前后，重复同一套已记录的启动和压测脚本。这些测试把 MTP 接受长度固定为 3 个草稿 token，所以应当看作相对提升，而不是生产吞吐。第一行是调度器的生成吞吐，后两行是客户端测得的输入和输出吞吐。

**输入。** 每一行都写明了负载、并发和拓扑；每组对比的完整输入见下面对应的小节。

<!-- BEGIN GENERATED: headline -->
| 改了什么 | 优化前 → 优化后（tok/s） | 变化 |
|---|---|---:|
| CK FP8 GEMM + unified verify<br>64K/1K decode，batch 16，单机<br>*两开关 A/B，各 2 次* | 743 → 934 | **+25.65%** |
| 调优 fused-MoE 表<br>8K prefill，并发 4，1P1D<br>*阶段对比，各 1 次* | 16,716 → 20,781 | **+24.32%** |
| 调优 fused-MoE 表<br>8K/1K decode，并发 128，1P1D<br>*阶段对比，各 1 次* | 2,209 → 2,487 | **+12.56%** |
<!-- END GENERATED: headline -->

**边界。** 每一行的收益只属于该行写明的改动，以及它当时所在的栈。各行是在不同的栈和负载上测的，不能相乘得出上面的累计倍数。

### 受控 A/B：64K 上下文下的 block-scale FP8 GEMM 路径

**问题。** 单台 MI300X 虚拟机上，最终版的 GEMM 与 verify 路径在长上下文下能带来多少稳态 decode 吞吐？

**输入。** 每个请求正好携带 65,536 个输入 token ID，生成 1,024 个 token；同时有 16 个请求在跑，调度器保持 batch 16。MTP 以固定接受 3 个草稿 token 的方式运行（`SGLANG_SIMULATE_ACC_LEN=3`、`SGLANG_SIMULATE_ACC_METHOD=match-expected`）。用 `--mem-fraction-static 0.95` 扩大 KV 池，保证 16 个 64K 上下文能同时放下。吞吐取的是 16 个请求全部在跑时调度器日志里的生成速率；每次运行的第一个满 batch 采样跨越 prefill 到 decode 的切换，按测试前定好的规则剔除。

**变量。** 两个环境变量，一起打开：优化组加上 `SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1` 和 `SGLANG_AITER_UNIFIED_VERIFY=1`。主机、容器、镜像、模型、启动参数、压测命令和 KV 设置完全相同；每组各起两次全新服务，两组背靠背连续跑完。

<!-- BEGIN GENERATED: ab-table -->
| 组别 | 第 1、2 次 | 均值 |
|---|---:|---:|
| 基线 | 740.29、745.95 | 743.12 |
| 优化后 | 931.58、935.92 | 933.75 |
| 变化 |  | **+25.65%** |
<!-- END GENERATED: ab-table -->

每组两次运行之间差异都在 1% 以内，而两组差距远超这个波动。两组都是调度器的生成吞吐（tok/s）。用 batch 除以吞吐，就是 16 个请求里每一个等一个 token 的时间：

<!-- BEGIN GENERATED: ab-tpot -->
| 组别 | 折算 TPOT（ms） |
|---|---:|
| 基线 | 21.53 |
| 优化后 | 17.14 |
| 变化 | **-20.42%** |
<!-- END GENERATED: ab-tpot -->

折算 TPOT 按 `1000 × 16 / tok/s` 计算，不是客户端实测的延迟。

**边界。** 两个变量是一起打开的，收益属于这一对开关，不能拆给其中任何一个。测试是单机、prefill 和 decode 在同一个服务里完成，不能推到 PD 部署上。原始采样值在 [`evidence/raw/ab-64k-bs16.json`](evidence/raw/ab-64k-bs16.json)，可以追溯到其中登记了 SHA-256 的审计文件。

### 阶段对比：按 shape 调优的 fused-MoE 表

**问题。** 在双机 PD 部署里，MiMo 专用的 fused-MoE 调优表改变了什么？

**输入。** Prefill：随机 prompt，长度 8,192 或 65,536 token，输出 1 个 token，16 个 prompt，并发 4，1 个预热请求，清缓存，seed 12345。Decode：随机 prompt 8,192 token，输出 1,024 token，256 个 prompt，并发 16 到 128，32 个预热请求，清缓存，seed 12345。每次运行的完整客户端参数都保存在 [`evidence/raw/`](evidence/raw/)。

**变量。** AITER 从 `fc96a4f` 升级到加入了 [`d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9) 调优表的版本（实际加载的 CSV 与该 commit 中的文件 SHA-256 相同）。前后两次运行的 prefill 启动脚本、router 脚本和两份压测脚本 SHA-256 完全一致，decode 服务记录下来的环境变量行也一致。decode 启动脚本的完整哈希只在“之后”那次记录过，sglang commit 只在“之前”那次记录过，所以把差异归到这张表上证据很强，但还没有同一轮内的 A/B 来证明。

Prefill，客户端测得（吞吐取整；精确值见 `evidence/measurements.json`）：

<!-- BEGIN GENERATED: stage-prefill -->
| 输入 token | tok/s 优化前 → 后 | 变化 |
|---:|---:|---:|
| 8,192 | 16,716 → 20,781 | **+24.32%**<br>TTFT -15.15% |
| 65,536 | 17,254 → 19,023 | **+10.25%**<br>TTFT -9.36% |
<!-- END GENERATED: stage-prefill -->

Decode，同一批运行：

<!-- BEGIN GENERATED: stage-decode -->
| 并发 | tok/s 优化前 → 后 | 变化 |
|---:|---:|---:|
| 16 | 1,299 → 1,332 | **+2.52%**<br>TPOT +1.79% |
| 32 | 1,911 → 1,936 | **+1.33%**<br>TPOT +1.11% |
| 64 | 2,188 → 2,458 | **+12.33%**<br>TPOT +12.58% |
| 128 | 2,209 → 2,487 | **+12.56%**<br>TPOT +14.05% |
<!-- END GENERATED: stage-decode -->

Prefill 吞吐上去的同时，首 token 时间也缩短了。Decode 在并发 64 和 128 时，输出吞吐提升了约八分之一，TPOT 也差不多涨了同样的幅度：服务每一步同时处理的请求更多，单个请求每个 token 多等一点，但整批完成得更快。

**边界。** 每个点前后各只跑了一次，不是交错进行的 A/B。前后两次都剔除了 256K prefill 点：在 `--context-length 262144` 下，262,144 token 的 prompt 加上 MiMo 的特殊 token 放不下，服务端可能返回错误内容，而客户端仍然记为成功。另有一次尝试用 `AITER_BYPASS_TUNE_CONFIG=1` 作为基线在同一轮里做 A/B，64K 时出现 GPU 内存访问错误，结果被判无效，所以这张表目前没有同一轮内的 A/B。

### Decode 在哪里饱和：并发阶梯

**问题。** 1P1D 的 decode 路径，客户端并发加到多少以后吞吐就不再增长？多出来的并发代价是什么？

**输入。** 与上面阶段对比“之前”那次相同的负载（8K 输入 / 1K 输出）和相同的栈，每个点 256 个 prompt，客户端并发 16 到 256。

<!-- BEGIN GENERATED: ladder -->
| 并发<br>（实测） | Output<br>tok/s | TPOT<br>（ms） | TTFT（s）<br>均值 / P99 |
|---:|---:|---:|---:|
| 16<br>(15.8) | 1,322 | 10.79 | 1.2 / 7.1 |
| 32<br>(30.9) | 1,914 | 13.37 | 2.8 / 14.1 |
| 64<br>(59.5) | 2,199 | 15.49 | 11.9 / 27.6 |
| 96<br>(84.0) | 2,201 | 15.06 | 23.7 / 40.8 |
| 128<br>(104.6) | 2,204 | 14.83 | 33.4 / 54.4 |
| 192<br>(135.4) | 2,203 | 14.72 | 47.9 / 81.3 |
| 256<br>(151.8) | 2,208 | 14.60 | 55.5 / 107.3 |
<!-- END GENERATED: ladder -->

并发到 64 时吞吐进入平台期。再往上，TPOT 基本不变，平均和 P99 首 token 时间却一直增长：多出来的请求没有带来吞吐，只是更晚拿到第一个 token。实测并发（括号内，客户端按时间平均的在途请求数）也不再跟随配置值增长。这与服务端的最大运行请求数和 KV 容量开始起作用相符，但这些运行没有调度器 trace 可以证实。

**边界。** 每个点只跑一次，而且是在加入调优 MoE 表之前的栈上测的。饱和点会随上下文长度、KV 容量和 `--max-running-requests` 变化，换配置就要重新测。

### 吞吐怎样随上下文长度变化

**问题。** 在优化后的 PD 栈上，上下文从 8K 增长到 256K token 时，prefill 速度和 decode batch 怎样变化？

**输入。** 两台 VM 组成 1P1D，用优化后栈的镜像，`--context-length 262151`。Prefill：随机 prompt、输出 1 个 token，每个点 16 个请求，客户端并发 1 到 8；256K 测点直接发送精确的 token ID。Decode：输出 1,024 个 token，MTP 固定接受长度 3。Decode batch 和生成速率取自 decode 服务的调度器日志（`#running-req`），不是客户端。表中 prefill 取 1 个请求时的值，decode 取该长度下测过的最高客户端并发；decode 两列分别是服务实际运行的 batch，以及总生成速率和它除以 batch 得到的每请求速率。

<!-- BEGIN GENERATED: context-table -->
| 上下文 | Prefill tok/s<br>1 个请求 | Decode batch<br>（稳态 / 峰值） | Decode tok/s<br>合计、每请求 |
|---|---:|---:|---:|
| 8K | 16,835 | 51 / 54<br>并发 128 | 2,333<br>45.8 |
| 64K | 18,057 | 4 / 5<br>并发 96 | 288<br>71.9 |
| 128K | 16,390 | 1 / 1<br>并发 32 | 138<br>138.2 |
| 192K | 13,827 | 1 / 1<br>并发 16 | 125<br>125.0 |
| 256K | 12,632 | 1 / 1<br>并发 4 | 128<br>127.8 |
<!-- END GENERATED: context-table -->

整个范围内 prefill 都保持在每秒约 12,600 到 18,100 个输入 token，一个 256K 的 prompt 大约 21 秒就能处理完。Decode 不一样：64K 时即使有 96 个请求在途，decode 服务也只同时跑 4 到 5 个；从 128K 起，即使有 32 个请求在途，也一次只跑 1 个。每个请求本身仍然很快，每秒 125 到 140 个 token，但服务的总速率从 8K 时的每秒约 2,300 个 token 降到约 130。长上下文下决定吞吐的是 KV 池，不是 kernel 速度，见[按 KV 容量估算 decode batch](#按-kv-容量估算-decode-batch)。

**边界。** 8K 和 64K 两行来自一组测试，128K 到 256K 来自同一镜像上的另一组测试；每个点只跑了一次。256K prefill 在 4 个请求在途时的测点被判无效：两次服务生命周期都出现 GPU 内存访问错误，所以不报告数值。256K 的 decode 行用 261,120 个输入 token，这样 1,024 个输出 token 仍能放进上下文。Decode 用的是固定 MTP 接受长度 3，属于偏乐观的条件。

### 增加第二个 prefill 副本

**问题。** 当瓶颈在 prefill 时，同一个路由后面再加一个完整的 TP8 服务能带来多少？

**输入。** 两个副本：两台 VM，每台跑一个优化后栈的普通 TP8 服务（不是 PD 模式），两个服务都注册到同一个 `sglang_router`，按轮询分配；每个点 32 个请求。一个服务：同一组测试里 1P1D 部署的 prefill 服务；每个点 16 个请求。两者都用随机 prompt、输出 1 个 token。表中比较的是各自 1 个和 2 个请求在途时的结果。

<!-- BEGIN GENERATED: replicas-table -->
| 输入 token | 一个服务<br>1 → 2 个在途 | 两个副本<br>1 → 2 个在途 |
|---:|---:|---:|
| 8,192 | 16,835 → 19,618<br>1.17× | 20,752 → 41,202<br>**1.99×** |
| 65,536 | 18,057 → 19,860<br>1.10× | 19,695 → 38,984<br>**1.98×** |
| 262,144 | 12,382 → 12,378<br>1.00× | 12,783 → 25,064<br>**1.96×** |
<!-- END GENERATED: replicas-table -->

一个服务多一个在途请求只多 0% 到 17%，因为两个请求挤在同样的 8 张 GPU 上。两个副本则接近翻倍，因为第二个请求落到了空闲的副本上；首 token 时间基本不变（64K 时为 3.33 s 和 3.35 s）。再增加到 8 个或 16 个在途，最多再多 13%（8K），64K 和 256K 则不再增加。

**边界。** 这里测的是输出长度为 1 时的 prefill 容量。副本是普通服务，而单服务参照是 PD 的 prefill 服务，所以两列除了副本数不同，服务模式也不同。这不是 2P1D 的结果：测试中没有 decode 服务，也没有 KV 传输。每个点只跑了一次。

### 本仓库没有测的部分

Decode 图捕获只在基线栈上测过，那时的栈没有 MTP 和 AITER kernel；它在优化后栈里的贡献没有单独拆分。FlyDSL paged-attention decode kernel、向量化 5D KV 布局、page 64 和 head 192 的 prefill tile 都在最终固定的 runtime 里，但微软已发布的测试没有单独测过它们，所以本页不给出它们的加速数字。它们的代码改动在[三层优化逐项拆解](#三层优化逐项拆解)里讲清楚了；要测它们，可以在单机 profile 上按同样的 A/B 方法去做。

## 架构与测试环境

<img src="images/architecture-cn.png" width="900" alt="三层优化：负载层、推理框架层、算子层，运行在 Azure ND MI300X v5 上">

请求从负载层进入（压测客户端，PD 模式下还有 router），由 SGLang 调度，最终由算子层的 kernel 执行。框架层决定每一层用哪个 kernel，kernel 决定这一层跑多快，负载层决定这次测量有没有代表性。虚线框是后续提交，不在任何实测配置里。

<img src="images/test-topology-cn.png" width="900" alt="两台 ND MI300X v5 上的 1P1D 实测拓扑，KV 经 Mooncake 走 8 路 InfiniBand">

阶段对比和并发阶梯跑在两台 ND MI300X v5 上：VM A 上是 prefill 服务（TP8）、PD router 和压测客户端，VM B 上是 decode 服务（TP8），KV cache 通过 Mooncake 走 8 路 InfiniBand 从 prefill 传到 decode。客户端指标（TTFT、TPOT、输入和输出 tok/s）由 VM A 上的 `sglang.bench_serving` 采集。64K A/B 则在单机上完成：一个 TP8 服务同时做 prefill 和 decode，吞吐取自调度器日志。

## 三层优化逐项拆解

先看总览：每项技术一行，写明它在 MI300X 上的效果，以及会不会改变模型输出。点名字跳到这一项的卡片：开关、NVIDIA 上的对应做法、代码、证据、对输出的影响，后面是解释，有 diff 的附上真实 diff。

<!-- BEGIN GENERATED: technique-overview -->
**推理框架层**

| 优化手段 | 在 MI300X 上的效果 | 对输出 |
|---|---|---|
| [混合 SWA + GQA 的逐层 attention 分派](#混合-swa--gqa-的逐层-attention-分派) | 部分已打开，未单独拆分 | 算术不变 |
| [FP8 KV cache + 向量化 5D 分页布局](#fp8-kv-cache--向量化-5d-分页布局) | 部分已打开，未单独拆分 | 有损 |
| [MTP target verify 使用 AITER unified attention](#mtp-target-verify-使用-aiter-unified-attention) | decode +25.65%，与 CK GEMM 合计（A/B） | 算术不变 |
| [多层 EAGLE MTP 投机解码及校验修复](#多层-eagle-mtp-投机解码及校验修复) | 已打开，未单独拆分 | 实现正确则不变 |
| [Chunked prefill、page size 与 SWA 池容量](#chunked-prefillpage-size-与-swa-池容量) | 在最终 runtime 中，未实测 | 算术不变 |
| [Decode 图捕获（HIP graph）](#decode-图捕获hip-graph) | decode 3.11×（A/B） | 算术不变 |

**算子层**

| 优化手段 | 在 MI300X 上的效果 | 对输出 |
|---|---|---|
| [FlyDSL paged-attention decode kernel（head 192，page 64）](#flydsl-paged-attention-decode-kernelhead-192page-64) | 在最终 runtime 中，未实测 | 算术不变 |
| [权重预重排的 block-scale FP8 GEMM](#权重预重排的-block-scale-fp8-gemm) | decode +25.65%，与 unified verify 合计（A/B） | 算术不变 |
| [张量并行 all-reduce 使用 INT8 Quick Reduce](#张量并行-all-reduce-使用-int8-quick-reduce) | 已打开，未单独拆分 | 有损 |
| [按 shape 调优的 fused-MoE kernel 表](#按-shape-调优的-fused-moe-kernel-表) | 8K prefill +24.32%，decode +12.56%（阶段对比） | 算术不变 |
| [head 192、page 64 的 FP8 batch-prefill tile](#head-192page-64-的-fp8-batch-prefill-tile) | 在最终 runtime 中，未实测 | 算术不变 |
| [混合精度 Triton router（MoE gate）GEMM](#混合精度-triton-routermoe-gategemm) | 后续提交，未实测 | 有损 |

**负载与部署层**

| 优化手段 | 在 MI300X 上的效果 | 对输出 |
|---|---|---|
| [Prefill/Decode 分离（1P1D），KV 走 RDMA](#prefilldecode-分离1p1dkv-走-rdma) | 已打开，未单独拆分 | 算术不变 |
| [一个路由后挂多个 prefill 副本（DP=2）](#一个路由后挂多个-prefill-副本dp2) | 8K prefill 1.99×（两个副本） | 算术不变 |
| [Fake prefill：只测 decode](#fake-prefill只测-decode) | 已发布的测试中未使用 | 仅测试方法 |
| [性能测试固定 MTP 接受长度](#性能测试固定-mtp-接受长度) | 已打开，未单独拆分 | 仅测试方法 |
| [按饱和点设计并发阶梯](#按饱和点设计并发阶梯) | 找到饱和点（并发阶梯） | 仅测试方法 |
<!-- END GENERATED: technique-overview -->

「已打开，未单独拆分」指这个开关在已发布的测试中是打开的，但没有单独测出它的贡献；「部分已打开」指只有其中一部分是打开的，例如 AITER backend 打开了，FlyDSL 分派没有；「在最终 runtime 中，未实测」指它属于固定的最终 runtime，而本仓库没有发布这个 runtime 的吞吐。

### 推理框架层

#### 混合 SWA + GQA 的逐层 attention 分派

<!-- BEGIN GENERATED: card-attention-dispatch -->
- **MI300X 上的开关**：`--attention-backend aiter`；全注意力层的 verify 走 FlyDSL，SWA/sink 层和普通 decode 留在 AITER
- **NVIDIA 上**：`--attention-backend fa3` 或 `flashinfer`；凡是一个 kernel 覆盖不了两种窗口类型的地方，都按层拆开
- **代码**：[ba15db1](https://github.com/sammysun0711/sglang/commit/ba15db1a576dcdc8d51ba15bd069b9fd1f748d97), [0cfc48b](https://github.com/sammysun0711/sglang/commit/0cfc48b0e374d7e84c122f739182a39feea56d46)
- **证据**：实测时已开 AITER 后端；FlyDSL 分派只在固定 runtime 中
- **对输出的影响**：算术不变。全注意力层和滑动窗口层用不同 kernel，每个都计算精确 attention。
<!-- END GENERATED: card-attention-dispatch -->

MiMo-V2.5-Pro 同时有全注意力层和带 attention sink 的滑动窗口层，没有哪一个 paged-attention kernel 在两种层上都最快，所以由后端按层分派。在 MTP target verify 阶段，全注意力层交给 FlyDSL kernel，SWA 层和 sink 层留在 AITER 路径上：

<!-- BEGIN GENERATED: excerpt-flydsl-layer-split -->
摘自 [`sammysun0711/sglang@ba15db1`](https://github.com/sammysun0711/sglang/commit/ba15db1a576dcdc8d51ba15bd069b9fd1f748d97) 的 diff，文件 `python/sglang/srt/layers/attention/aiter_backend.py`（本地副本：[sammysun0711__sglang__ba15db1.patch](upstream/patches/sammysun0711__sglang__ba15db1.patch)）。

```diff
+                    is_swa_layer = (
+                        layer.sliding_window_size is not None
+                        and layer.sliding_window_size > -1
+                    )
+                    use_flydsl = (
+                        getattr(self, "_use_flydsl_pa_decode", False)
+                        and not is_swa_layer
+                        and sinks is None
+                    )
+                    target_verify_fn = (
+                        forward_target_verify_flydsl_5d
+                        if use_flydsl
+                        else forward_target_verify_vectorized_5d
+                    )
```
<!-- END GENERATED: excerpt-flydsl-layer-split -->

同样的思路也省掉了 prefill 端的一次拷贝：commit [`0cfc48b`](https://github.com/sammysun0711/sglang/commit/0cfc48b0e374d7e84c122f739182a39feea56d46) 把带缓存前缀的 prefill 直接交给 page-64 kernel，不再先把分页 KV 拼成一块连续缓冲区。

#### FP8 KV cache + 向量化 5D 分页布局

<!-- BEGIN GENERATED: card-fp8-kv-5d -->
- **MI300X 上的开关**：`--kv-cache-dtype fp8_e4m3` + `SGLANG_AITER_KV_CACHE_LAYOUT=vectorized_5d`
- **NVIDIA 上**：`--kv-cache-dtype fp8_e4m3`；FA3/FlashInfer 的分页布局本来就保留 16 字节内层向量
- **代码**：[78cd40c](https://github.com/sammysun0711/sglang/commit/78cd40c7a5102524536daf9a3178426777174d2d), [e11c515](https://github.com/sammysun0711/sglang/commit/e11c5155f0845079211c2a4d0b8a4ab3669039f9), [10a9401](https://github.com/sammysun0711/aiter/commit/10a94012efc1260dfdf16ba2f52fbda40a518a17)
- **证据**：实测时已开 FP8 KV；5D 布局只在固定 runtime 中
- **对输出的影响**：有损。K、V 以 FP8 E4M3（3 位尾数）存储，每个张量一个缩放系数，每个缓存 token 都会损失精度；5D 布局本身只是重排字节。
<!-- END GENERATED: card-fp8-kv-5d -->

到了 1M 上下文，决定能同时放多少请求的是 KV cache，而不是权重。FP8 E4M3 存储让每个 token 的字节数减半。向量化 5D 布局再把每一页重新排列，让最内层维度正好是一个 16 字节的向量，这样一个 wavefront 里每个 lane 用一条宽加载指令就能取到自己那一段：

<!-- BEGIN GENERATED: excerpt-kv-5d-vector-width -->
摘自 [`sammysun0711/sglang@78cd40c`](https://github.com/sammysun0711/sglang/commit/78cd40c7a5102524536daf9a3178426777174d2d) 的 diff，文件 `python/sglang/srt/mem_cache/memory_pool.py`（本地副本：[sammysun0711__sglang__78cd40c.patch](upstream/patches/sammysun0711__sglang__78cd40c.patch)）。

```diff
+        if layout == "vectorized_5d":
+            # X is the inner vectorization width in the SHUFFLE layout,
+            # determined by the STORAGE dtype (not the compute dtype) since
+            # it controls how many elements fit in 16 bytes of the on-pool
+            # tensor. For fp8 storage X=16, for bf16/fp16 X=8.
+            self._kv_vector_x = 16 // self.store_dtype.itemsize
```
<!-- END GENERATED: excerpt-kv-5d-vector-width -->

同一个 commit 还让 MTP 草稿模型继续使用普通的按 token 排列（NHD）的 KV 池，而目标模型使用 5D 池，因为草稿用的 kernel 读不了 5D 布局。在 NVIDIA 上，`--kv-cache-dtype fp8_e4m3` 这个开关完全一样；FA3 和 FlashInfer 的分页布局本来就保留 16 字节内层向量以便 128 位加载，所以能搬过去的是原理，而不是开关。

#### MTP target verify 使用 AITER unified attention

<!-- BEGIN GENERATED: card-unified-verify -->
- **MI300X 上的开关**：decode 服务上设 `SGLANG_AITER_UNIFIED_VERIFY=1`
- **NVIDIA 上**：不需要；CUDA 的 attention 后端用自己的 kernel 做 verify
- **代码**：无代码改动（仅配置）
- **证据**：实测 A/B，与 CK GEMM 路径一起打开
- **对输出的影响**：算术不变。只决定用哪个 attention kernel 校验草稿 token，计算的仍是精确 attention。
<!-- END GENERATED: card-unified-verify -->

MTP 做 target verify 时，decode 服务要一次校验每个请求的 4 个位置。`SGLANG_AITER_UNIFIED_VERIFY=1` 把这一步交给 AITER 的 unified attention kernel，而不是通用路径。它只是配置；在 64K A/B 里它和 CK GEMM 路径一起打开，所以收益属于这两个开关的组合。

#### 多层 EAGLE MTP 投机解码及校验修复

<!-- BEGIN GENERATED: card-eagle-mtp -->
- **MI300X 上的开关**：`--speculative-algorithm EAGLE --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 --enable-multi-layer-eagle`
- **NVIDIA 上**：同一组开关
- **代码**：[db840d9](https://github.com/sammysun0711/sglang/commit/db840d935a9f7097dbeb5f1b0dba4d261057a2bd), [f26ae30](https://github.com/sammysun0711/sglang/commit/f26ae30063143411f3ae552af1830fa46e3ee0fd), [878fff1](https://github.com/sammysun0711/sglang/commit/878fff15647fe3dabb32aa3a335b0ad16e3ee878)
- **证据**：实测时以固定接受长度打开；f26ae30、878fff1 只在固定 runtime 中
- **对输出的影响**：实现正确则不变。投机解码只有在校验正确时才保持目标模型的输出分布。在 HIP 上，878fff1 之前采样校验会悄悄退回贪心，temperature 实际不起作用。
<!-- END GENERATED: card-eagle-mtp -->

MiMo 自带 3 层 MTP，每个 decode 步起草 3 个 token、一次校验 4 个。投机解码只有在草稿和目标模型经常一致时才划算，而在 ROCm 上有三个问题让一致率偏低甚至结果出错：draft-extend 读的是全注意力池而不是 SWA 池，用的 kernel 也和 target verify 不同（[`db840d9`](https://github.com/sammysun0711/sglang/commit/db840d935a9f7097dbeb5f1b0dba4d261057a2bd)）；各 TP rank 的校验结果可能不一致，导致集合通信错位（[`f26ae30`](https://github.com/sammysun0711/sglang/commit/f26ae30063143411f3ae552af1830fa46e3ee0fd)）；在 HIP 上，采样（非贪心）校验会悄悄退回贪心校验，`temperature` 实际不起作用（[`878fff1`](https://github.com/sammysun0711/sglang/commit/878fff15647fe3dabb32aa3a335b0ad16e3ee878)，需通过 `SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1` 显式打开）。这些开关在 CUDA 上相同。

#### Chunked prefill、page size 与 SWA 池容量

<!-- BEGIN GENERATED: card-memory-sizing -->
- **MI300X 上的开关**：`--chunked-prefill-size 65536 --page-size 64 --swa-full-tokens-ratio 0.01`
- **NVIDIA 上**：同一组开关；具体数值按 HBM 容量和 kernel 支持的 page size 重新推算
- **代码**：无代码改动（仅配置）
- **证据**：实测时为 chunk 32768、page 32
- **对输出的影响**：算术不变。chunk 和 page 大小改变的是切分方式，不是计算内容；SWA 比例只决定池子大小。
<!-- END GENERATED: card-memory-sizing -->

这几项是配置而不是代码，但它们决定上面那些 kernel 能不能跑起来。最终 runtime 用 `--chunked-prefill-size 65536`、`--page-size 64`（FlyDSL 和 CK kernel 就是按这个 page size 写的）和 `--swa-full-tokens-ratio 0.01`。最后这一项把滑动窗口池压到全注意力池的 1%，因为 SWA 层永远只需要最后一个窗口的 token，省下来的 HBM 给了全注意力 KV 池，也就换来了更长的上下文。

#### Decode 图捕获（HIP graph）

<!-- BEGIN GENERATED: card-decode-graph-capture -->
- **MI300X 上的开关**：decode 服务上默认打开：不要给 decode 服务传 `--disable-cuda-graph`（prefill 服务保留该参数）
- **NVIDIA 上**：默认行为相同，使用 CUDA graph；`--cuda-graph-max-bs` 限定捕获的 batch 上限
- **代码**：无代码改动（仅配置）
- **证据**：在基线栈上实测 A/B（Triton attention，无 MTP）
- **对输出的影响**：算术不变。捕获的图重放的是同一批 kernel；省掉的是 launch 开销，算术不变。
<!-- END GENERATED: card-decode-graph-capture -->

一个 decode step 要跑几百个小 kernel，batch 小的时候，launch 它们的时间和它们实际运行的时间差不多。SGLang 对每个 decode batch size 先捕获一次 HIP graph（NVIDIA 上是 CUDA graph），之后整步只需一次 launch 重放。基线栈为了绕开多机挂起问题用 `--disable-cuda-graph` 关掉了它；在 decode 服务上重新打开，是本页实测到的最大的一步。prefill 服务仍保留 `--disable-cuda-graph`，因为 prefill 的 batch 大且不规则。每个被捕获的 batch size 都要占 HBM，会和 KV 池争显存。

### 算子层

#### FlyDSL paged-attention decode kernel（head 192，page 64）

<!-- BEGIN GENERATED: card-flydsl-pa-decode -->
- **MI300X 上的开关**：`SGLANG_AITER_PA_DECODE_IMPL=flydsl` + `SGLANG_FLYDSL_PA_NUM_PARTITIONS=16`
- **NVIDIA 上**：CuTe DSL 或 FlashInfer 的 decode kernel；partition 数对应 split-KV
- **代码**：[c99d5cd](https://github.com/sammysun0711/FlyDSL/commit/c99d5cd97864c11e459cff9169d387d312790782), [ba15db1](https://github.com/sammysun0711/sglang/commit/ba15db1a576dcdc8d51ba15bd069b9fd1f748d97), [a2fd773](https://github.com/sammysun0711/sglang/commit/a2fd773ab43f960f5f2c29b5c592b0ca43c5ba8f)
- **证据**：在固定 runtime 中；kernel 未单独测试
- **对输出的影响**：算术不变。精确 paged attention。已修复的两个缺陷（query 元素未搬入、32 位偏移溢出）产生的是错误输出，而不是小幅漂移，所以这个 kernel 会拒绝没测过的 shape。
<!-- END GENERATED: card-flydsl-pa-decode -->

FlyDSL 是构建在 MLIR 上的 Python DSL，写 kernel 时描述的是布局（一个张量如何切分到 lane、wave 和 tile 上），而不是手写下标运算，地址由编译器生成。MiMo 的 decode kernel 在 MiMo 的 shape 上有两个缺陷，都在 [`c99d5cd`](https://github.com/sammysun0711/FlyDSL/commit/c99d5cd97864c11e459cff9169d387d312790782) 中修复，之后合入上游 ROCm/FlyDSL [#1064](https://github.com/ROCm/FlyDSL/commit/ed9885eca4ffc45e2ec1dc45fa00824baa6b56d3)。

head size 为 192 时，16 个 lane 各自要搬 12 个 query 元素。旧规则把它舍成一次 8 元素加载，于是每行 query 有三分之一没有进 LDS，输出出现 NaN。修复后改为三次 4 元素（64 位）加载：

<!-- BEGIN GENERATED: excerpt-flydsl-query-load -->
摘自 [`sammysun0711/FlyDSL@c99d5cd`](https://github.com/sammysun0711/FlyDSL/commit/c99d5cd97864c11e459cff9169d387d312790782) 的 diff，文件 `kernels/attention/pa_decode_tile.py`（本地副本：[sammysun0711__FlyDSL__c99d5cd.patch](upstream/patches/sammysun0711__FlyDSL__c99d5cd.patch)）。

```diff
         # Per-lane Q chunk (QCHUNK 16-bit elems) fetched in QLOAD_UNIT-wide
-        # pieces (128b max per buffer load): head_dim=256 needs 2 pieces.
-        QLOAD_UNIT = QCHUNK if QCHUNK < 8 else 8
+        # pieces (128b max per buffer load).  Use 64-bit loads when QCHUNK is
+        # not divisible by 8: head_dim=192 gives QCHUNK=12 and therefore needs
+        # three 4-element loads.  Rounding it down to one 8-element load leaves
+        # one third of every query row unstaged in LDS.
+        QLOAD_UNIT = 8 if QCHUNK % 8 == 0 else 4
         N_QLOADS = QCHUNK // QLOAD_UNIT
         _q_copy_op = fx.rocdl.BufferCopy128b() if QLOAD_UNIT == 8 else fx.rocdl.BufferCopy64b()
         _q_load_chunk = _make_flat_loader(query_ptr, Q_DTYPE, QLOAD_UNIT, _q_copy_op)
```
<!-- END GENERATED: excerpt-flydsl-query-load -->

物理页号用 32 位放得下，但一旦单个 KV cache 超过 2 GiB（1M 上下文时就会超过），由页号算出的字节偏移就会溢出。修复是在任何偏移运算之前先把页号提升到 64 位：

<!-- BEGIN GENERATED: excerpt-flydsl-int64-offset -->
摘自 [`sammysun0711/FlyDSL@c99d5cd`](https://github.com/sammysun0711/FlyDSL/commit/c99d5cd97864c11e459cff9169d387d312790782) 的 diff，文件 `kernels/attention/pa_decode_tile.py`（本地副本：[sammysun0711__FlyDSL__c99d5cd.patch](upstream/patches/sammysun0711__FlyDSL__c99d5cd.patch)）。

```diff
         def _k_ops(phys, a):
+            # Physical page ids fit in i32, but their byte/element offsets do
+            # not once an individual KV cache grows beyond 2 GiB.
+            phys = fx.Int64(phys)
             within_page_tok = (a * c16 + lane16) % block_size
```
<!-- END GENERATED: excerpt-flydsl-int64-offset -->

在 SGLang 一侧（[`ba15db1`](https://github.com/sammysun0711/sglang/commit/ba15db1a576dcdc8d51ba15bd069b9fd1f748d97)），这个 kernel 需要显式打开；遇到没有验证过的 shape 会直接拒绝启动，而不是悄悄算出错误的 attention：

<!-- BEGIN GENERATED: excerpt-flydsl-dispatch-gate -->
摘自 [`sammysun0711/sglang@ba15db1`](https://github.com/sammysun0711/sglang/commit/ba15db1a576dcdc8d51ba15bd069b9fd1f748d97) 的 diff，文件 `python/sglang/srt/layers/attention/aiter_backend.py`（本地副本：[sammysun0711__sglang__ba15db1.patch](upstream/patches/sammysun0711__sglang__ba15db1.patch)）。

```diff
+        incompatibilities = []
+        if self.use_mla:
+            incompatibilities.append("MLA is unsupported")
+        if self.topk != 1:
+            incompatibilities.append(f"top-k must be 1, got {self.topk}")
+        if self.page_size != 64:
+            incompatibilities.append(f"page size must be 64, got {self.page_size}")
+        if self.max_context_len > 1_048_576:
+            incompatibilities.append(
+                "maximum context must not exceed 1,048,576 tokens, got "
+                f"{self.max_context_len}"
+            )
+        if (self.num_head, self.num_kv_head, self.head_dim) != (16, 1, 192):
+            incompatibilities.append(
+                "TP-local shape must be 16Q/1KV/head-192, got "
+                f"{self.num_head}Q/{self.num_kv_head}KV/head-{self.head_dim}"
+            )
+        if self.input_dtype != torch.bfloat16:
+            incompatibilities.append(
+                f"model dtype must be BF16, got {self.input_dtype}"
+            )
+        if self.kv_cache_dtype != fp8_dtype:
+            incompatibilities.append(
+                f"KV cache dtype must be FP8 E4M3, got {self.kv_cache_dtype}"
+            )
+        if not is_gfx942_supported():
+            incompatibilities.append("phase 1 is validated only on gfx942")
+        if incompatibilities:
+            raise RuntimeError(
+                "SGLANG_AITER_PA_DECODE_IMPL=flydsl is incompatible with this "
+                "target backend: " + "; ".join(incompatibilities)
+            )
```
<!-- END GENERATED: excerpt-flydsl-dispatch-gate -->

[`a2fd773`](https://github.com/sammysun0711/sglang/commit/a2fd773ab43f960f5f2c29b5c592b0ca43c5ba8f) 让上下文 partition 数可配（8、16、24 或 32）。最终 runtime 用 16，让长上下文拆到足够多的 workgroup 上，把 304 个计算单元占满。上游 [#1065](https://github.com/ROCm/FlyDSL/commit/e46db6020b4560de82a7136d78cc33a5186338f4) 后来又支持了 BF16 KV 以及 K、V 不同的 head size，MiMo 128 维的 value head 不必再补齐到 192。这类先写布局的 kernel，在 NVIDIA 上对应的是 CuTe DSL；partition 数对应 split-KV。

#### 权重预重排的 block-scale FP8 GEMM

<!-- BEGIN GENERATED: card-ck-a8w8-gemm -->
- **MI300X 上的开关**：`SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE=1`
- **NVIDIA 上**：DeepGEMM（`SGLANG_ENABLE_JIT_DEEPGEMM=1`）或 CUTLASS 的 block-scale GEMM
- **代码**：[2f9b9ae](https://github.com/sammysun0711/sglang/commit/2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0), [fc96a4f](https://github.com/sammysun0711/aiter/commit/fc96a4f9f5f3e931cbb9de275c8aa01136417500)
- **证据**：实测 A/B，与 unified verify 一起打开
- **对输出的影响**：算术不变。Triton 路径和 CK 路径都按 1x128 块把激活量化成 FP8，权重都是同一份 FP8 block-scale checkpoint；这个开关换的是 kernel，不是精度。
<!-- END GENERATED: card-ck-a8w8-gemm -->

MiMo 的线性层是 FP8，每 128 宽的块一个缩放系数。在 gfx942 上，SGLang 原本用 Triton kernel 做这个 GEMM。Commit [`2f9b9ae`](https://github.com/sammysun0711/sglang/commit/2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0) 加了一个开关，改用 AITER 里的 Composable Kernel 实现，并在加载时把权重一次性重排成矩阵核心读取的布局：

<!-- BEGIN GENERATED: excerpt-ck-gemm-select -->
摘自 [`sammysun0711/sglang@2f9b9ae`](https://github.com/sammysun0711/sglang/commit/2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0) 的 diff，文件 `python/sglang/srt/layers/quantization/fp8_utils.py`（本地副本：[sammysun0711__sglang__2f9b9ae.patch](upstream/patches/sammysun0711__sglang__2f9b9ae.patch)）。

```diff
     elif _use_aiter_gfx95:
         use_triton = use_aiter_triton_gemm_w8a8_tuned_gfx950(n, k)
+    elif _use_aiter_ck_blockscale_bpreshuffle_gfx942:
+        use_triton = False
+    elif _use_aiter_ck_blockscale_gfx942:
+        use_triton = False
     else:
         use_triton = True
 
+    # The weight-preshuffled CK kernel consumes a transposed activation scale.
+    use_bpreshuffle = not use_triton and (
+        _use_aiter_bpreshuffle_gfx95 or _use_aiter_ck_blockscale_bpreshuffle_gfx942
+    )
+
```
<!-- END GENERATED: excerpt-ck-gemm-select -->

AITER [`fc96a4f`](https://github.com/sammysun0711/aiter/commit/fc96a4f9f5f3e931cbb9de275c8aa01136417500) 为 304 CU 的 MI300X 补充了 MiMo 各 GEMM 尺寸的 tile 配置。上面实测的 A/B 同时打开了两个开关，这条路径是其一，另一个是 unified verify，所以收益不能全部算在 GEMM 头上。在 NVIDIA 上承担同样角色的是 DeepGEMM（`SGLANG_ENABLE_JIT_DEEPGEMM=1`）或 CUTLASS 的 block-scale FP8 GEMM，它们的权重预打包就相当于这里的预重排。

#### 张量并行 all-reduce 使用 INT8 Quick Reduce

<!-- BEGIN GENERATED: card-int8-quick-reduce -->
- **MI300X 上的开关**：`ROCM_QUICK_REDUCE_QUANTIZATION=INT8`（基础镜像默认设置；设为 `NONE` 即关闭）
- **NVIDIA 上**：默认没有对应功能；NCCL 和 SGLang 自定义 all-reduce 都按全精度求和
- **代码**：无代码改动（仅配置）
- **证据**：实测吞吐时已打开，继承自基础镜像；未单独拆分
- **对输出的影响**：有损。走 Quick Reduce 的张量并行 all-reduce，会先把各卡的部分和量化成 INT8，再在 8 张卡之间相加。
<!-- END GENERATED: card-int8-quick-reduce -->

张量并行在每个 attention 和 MoE 块之后都要把 8 张 GPU 的部分结果加起来。Quick Reduce 是 SGLang 自定义 all-reduce 路径里给 ROCm 用的 all-reduce；设置 `ROCM_QUICK_REDUCE_QUANTIZATION=INT8` 后，它把要发送的数据量化成 INT8，GPU 之间传的字节更少。阶段对比那几次运行记录的环境显示它是打开的；设置它的是基础镜像，不是启动脚本；见[哪些优化可能改变模型输出](#哪些优化可能改变模型输出)里的提醒。

#### 按 shape 调优的 fused-MoE kernel 表

<!-- BEGIN GENERATED: card-tuned-fused-moe -->
- **MI300X 上的开关**：AITER 里的 `mimo_v2_5_pro_b16_tuned_fmoe.csv`
- **NVIDIA 上**：用 `tuning_fused_moe_triton.py` 生成的 Triton fused-MoE JSON
- **代码**：[d725746](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9)
- **证据**：实测阶段对比
- **对输出的影响**：算术不变。按 token 数在已有 fused-MoE kernel 中选择，模型计算不变。
<!-- END GENERATED: card-tuned-fused-moe -->

MoE 层的开销取决于一个 batch 里落了多少 token。AITER 可以按 token 数选用不同的 fused-MoE kernel，[`d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9) 记录的是针对 MiMo 专家 shape（hidden size 6,144，单个 TP rank 看到的专家中间维度 256，384 个专家，top-8）离线搜索出的最优结果：

<!-- BEGIN GENERATED: moe-table -->
| Token 数 | Kernel | 耗时（µs） | TFLOPS |
|---:|---|---:|---:|
| 2,048 | A | 703.2 | 219.9 |
| 4,096 | B | 1,069.8 | 289.1 |
| 8,192 | B | 1,412.0 | 438.0 |
| 16,384 | B | 2,680.7 | 461.4 |
| 32,768 | B | 4,816.4 | 513.6 |

每一行的 block_m 都是 64；耗时和 TFLOPS 是调优器自己在每个 token 数下测到的值。Kernel 字母含义：

- A = `fmoe_bf16_blockscaleFp8_g1u1_vs_silu_64x256`
- B = `fmoe_bf16_blockscaleFp8_g1u1_vs_ps_silu_64x256`
<!-- END GENERATED: moe-table -->

从 4,096 个 token 起，搜索都选中了 kernel B（带 `_ps_` 的变体），而且 batch 越大实际 TFLOPS 越高。这张表只改变跑哪个 kernel，不改变模型计算。NVIDIA 上的对应做法是 SGLang 的 Triton fused-MoE 配置，用 `benchmark/kernels/fused_moe_triton/tuning_fused_moe_triton.py` 按专家数、尺寸、数据类型和 GPU 分别生成。

#### head 192、page 64 的 FP8 batch-prefill tile

<!-- BEGIN GENERATED: card-ck-prefill-tile -->
- **MI300X 上的开关**：AITER `3f4ab48` 自带的 CK patch，只对这个精确 shape 分派
- **NVIDIA 上**：确认分页 prefill 路径没有退回到「先 gather 再算稠密 attention」
- **代码**：[3f4ab48](https://github.com/sammysun0711/aiter/commit/3f4ab482a2986919c784e469e23cfac7f93bb153), [0cfc48b](https://github.com/sammysun0711/sglang/commit/0cfc48b0e374d7e84c122f739182a39feea56d46)
- **证据**：在固定 runtime 中，本仓库未测吞吐
- **对输出的影响**：算术不变。去掉补齐到 head 256 的路径，改用精确的 head-192 tile。
<!-- END GENERATED: card-ck-prefill-tile -->

[`3f4ab48`](https://github.com/sammysun0711/aiter/commit/3f4ab482a2986919c784e469e23cfac7f93bb153) 带了一个临时的 Composable Kernel patch，专门为 MiMo 的 shape（head 192、FP8 或 BF16、page 64、向量化布局）增加一个 batch-prefill tile，同时保留补齐到 head 256 的旧路径作为兜底。配合框架层的缓存前缀直通，长的缓存前缀可以直接在分页缓存里原地读取。

#### 混合精度 Triton router（MoE gate）GEMM

<!-- BEGIN GENERATED: card-mixed-router-gemm -->
- **MI300X 上的开关**：`SGLANG_MIMO_MIXED_ROUTER=1`，用于 token 数不少于 2,048 的 router batch
- **NVIDIA 上**：同一个 Triton kernel 在 CUDA 上也能编译；重新调 block 大小即可
- **代码**：[1f9bb2b](https://github.com/sammysun0711/sglang/commit/1f9bb2b4c55cdc7bd5de1ac7977f76afab101a97)
- **证据**：后续提交，未实测
- **对输出的影响**：有损。router 权重从 FP32 降到 FP16，激活从 BF16 转成 FP16 后再累加。router logits 决定选哪 8 个专家，微小变化就可能换掉 token 用的专家。
<!-- END GENERATED: card-mixed-router-gemm -->

MoE router 要把每个 token 的 hidden state 乘上一个 384 × 6,144 的 FP32 权重。[`1f9bb2b`](https://github.com/sammysun0711/sglang/commit/1f9bb2b4c55cdc7bd5de1ac7977f76afab101a97) 为 token 数不少于 2,048 的 batch 加了一个可选的 Triton kernel：缓存一份 FP16 的 router 权重，在寄存器里把 BF16 激活转成 FP16，累加和输出仍然是 FP32：

<!-- BEGIN GENERATED: excerpt-router-gate -->
摘自 [`sammysun0711/sglang@1f9bb2b`](https://github.com/sammysun0711/sglang/commit/1f9bb2b4c55cdc7bd5de1ac7977f76afab101a97) 的 diff，文件 `python/sglang/srt/models/mimo_v2.py`（本地副本：[sammysun0711__sglang__1f9bb2b.patch](upstream/patches/sammysun0711__sglang__1f9bb2b.patch)）。

```diff
     def forward(self, hidden_states):
+        if (
+            get_bool_env_var("SGLANG_MIMO_MIXED_ROUTER")
+            and hidden_states.is_cuda
+            and hidden_states.dtype == torch.bfloat16
+            and hidden_states.shape[0] >= 2048
+        ):
+            from sglang.srt.layers.moe.mixed_router_gemm import mixed_router_gemm
+
+            if self._mixed_router_weight is None:
+                self._mixed_router_weight = self.weight.detach().to(torch.float16)
+            return mixed_router_gemm(hidden_states, self._mixed_router_weight)
```
<!-- END GENERATED: excerpt-router-gate -->

<!-- BEGIN GENERATED: excerpt-router-kernel-dot -->
摘自 [`sammysun0711/sglang@1f9bb2b`](https://github.com/sammysun0711/sglang/commit/1f9bb2b4c55cdc7bd5de1ac7977f76afab101a97) 的 diff，文件 `python/sglang/srt/layers/moe/mixed_router_gemm.py`（本地副本：[sammysun0711__sglang__1f9bb2b.patch](upstream/patches/sammysun0711__sglang__1f9bb2b.patch)）。

```diff
+    accumulator = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.float32)
+    for k_start in range(0, K, BLOCK_K):
+        x = tl.load(
+            x_ptrs,
+            mask=(offs_m[:, None] < M) & (k_start + offs_k[None, :] < K),
+            other=0.0,
+        )
+        weight = tl.load(
+            weight_ptrs,
+            mask=(offs_n[None, :] < N) & (k_start + offs_k[:, None] < K),
+            other=0.0,
+        )
+        accumulator = tl.dot(
+            x.to(tl.float16), weight, acc=accumulator, out_dtype=tl.float32
+        )
+        x_ptrs += BLOCK_K * stride_xk
+        weight_ptrs += BLOCK_K * stride_wk
```
<!-- END GENERATED: excerpt-router-kernel-dot -->

这个提交在后来的分支上，不在固定的 runtime 里，本页任何数字都不包含它。因为是纯 Triton kernel，它在 CUDA 上同样能编译，只需要重新调 block 大小。

### 负载与部署层

#### Prefill/Decode 分离（1P1D），KV 走 RDMA

<!-- BEGIN GENERATED: card-pd-disaggregation -->
- **MI300X 上的开关**：`--disaggregation-mode prefill|decode --disaggregation-transfer-backend mooncake` + `sglang_router --pd-disaggregation`
- **NVIDIA 上**：同一组开关；通过 GPUDirect RDMA 使用 mooncake 或 nixl
- **代码**：无代码改动（仅配置）
- **证据**：实测时已打开，未单独拆分
- **对输出的影响**：算术不变。KV cache 在两个服务之间逐字节拷贝。
<!-- END GENERATED: card-pd-disaggregation -->

Prefill 受算力限制，decode 受访存限制；一次长 prefill 会拖住同一组 GPU 上的每一个 decode 步。PD 部署让两个阶段各用一个 TP8 服务，KV cache 通过 Mooncake 走 8 路 InfiniBand 传输。比开关更重要的是两件运维上的事：容器必须带 `--privileged`、`/dev/mem` 和 `CAP_SYS_ADMIN`，否则 Mooncake 会悄悄从 RDMA 退回 TCP；router 必须等两个服务都就绪后再启动。在 NVIDIA 上，这些开关完全相同，传输后端可选 `mooncake` 或 `nixl`。

#### 一个路由后挂多个 prefill 副本（DP=2）

<!-- BEGIN GENERATED: card-prefill-replicas -->
- **MI300X 上的开关**：每台 VM 一个完整的 TP8 服务，两个服务注册到同一个 `sglang_router`
- **NVIDIA 上**：路由和参数相同；每个副本都要一份完整模型
- **代码**：无代码改动（仅配置）
- **证据**：实测：两个副本上 1 个与 2 个请求同时在跑的对比
- **对输出的影响**：算术不变。每个请求完整地跑在一个副本上，没有任何切分或近似。
<!-- END GENERATED: card-prefill-replicas -->

路由把每个请求整个交给一个完整的 TP8 服务，没有任何集合通信跨 VM，所以只要有 2 个请求在途，两个副本就能让 prefill 接近翻倍（[实测](#增加第二个-prefill-副本)）。代价是每个副本都要一份完整模型。这里先做副本的原因是：

- **每台 VM 一个 TP8** 是稳定的基础：每台 VM 有 8 张 GPU，模型的 8 个 KV head 正好每张 GPU 一个。
- **专家并行**（EP），无论是单台 VM 内还是跨 VM，都不在这里任何一组实测配置中。副本不引入新的集合通信就能增加 prefill 容量；EP 会改变每个 MoE 层的通信方式，所以要单独做 A/B，而不是当作一个开关。

#### Fake prefill：只测 decode

<!-- BEGIN GENERATED: card-fake-prefill -->
- **MI300X 上的开关**：decode 服务 `--disaggregation-transfer-backend fake`；客户端 `--fake-prefill`
- **NVIDIA 上**：上游 SGLang 的同一功能
- **代码**：无代码改动（仅配置）
- **证据**：在固定 runtime 的脚本里；已发布的测试没有用到
- **对输出的影响**：仅测试方法。decode 服务从一份并非由 prompt 算出来的 KV cache 开始。
<!-- END GENERATED: card-fake-prefill -->

想在没有 prefill 服务的情况下研究 decode kernel，就让 decode 服务带上 `--disaggregation-mode decode --disaggregation-transfer-backend fake`，客户端加 `--fake-prefill`。这样 decode 服务会把每个请求当作 KV 已经到位直接开始解码。在长上下文下，真实 prefill 会占掉大部分时间，这个办法能把 decode 吞吐单独拎出来；它是上游 SGLang 的功能，两个平台都能用。

#### 性能测试固定 MTP 接受长度

<!-- BEGIN GENERATED: card-simulated-acceptance -->
- **MI300X 上的开关**：`SGLANG_SIMULATE_ACC_LEN=3 SGLANG_SIMULATE_ACC_METHOD=match-expected`
- **NVIDIA 上**：上游 SGLang 的同一组变量
- **代码**：无代码改动（仅配置）
- **证据**：实测时已打开，未单独拆分
- **对输出的影响**：仅测试方法。草稿 token 按规则被接受，而不是由模型决定，生成的文本不是模型的输出。
<!-- END GENERATED: card-simulated-acceptance -->

`SGLANG_SIMULATE_ACC_LEN=3` 让每个 MTP 步都正好接受 3 个草稿 token。这样 kernel 测量不受接受率波动影响，不同轮次的结果可以直接比较，但对真实负载来说吞吐会偏高。准确率测试必须去掉这两个变量；用固定接受长度测出的吞吐，不能当作生产吞吐引用。

#### 按饱和点设计并发阶梯

<!-- BEGIN GENERATED: card-concurrency-ladder -->
- **MI300X 上的开关**：`bench_serving --max-concurrency 16 ... 256`，固定 prompt、预热请求和 seed
- **NVIDIA 上**：同一个客户端
- **代码**：无代码改动（仅配置）
- **证据**：实测并发阶梯
- **对输出的影响**：仅测试方法。一种加载方式，不改变模型。
<!-- END GENERATED: card-concurrency-ladder -->

吞吐只有在说明负载时才有意义。固定 prompt、warmup 和 seed，逐级提高客户端并发，直到输出吞吐不再上升，再把这个平台值连同它的 TTFT 一起报告；[上文的并发阶梯](#decode-在哪里饱和并发阶梯)就是例子。过了平台期，多加的并发只会增加排队时间。

#### 精确输入与上下文余量

随机 prompt 压测会把文本重新分词，服务端的实际长度可能漂移。长上下文测点应直接传 token ID（`--tokenize-prompt`），并把模型的特殊 token 算进去：MiMo 会加 4 个，所以传 65,532 个 ID 才是服务端正好 65,536 个 token。`--context-length` 也要留同样的余量，否则最长的测点可能带着错误内容被记为「成功」，上面 256K 点被剔除正是这个原因。

#### 按 KV 容量估算 decode batch

"batch 16" 这样的说法可以指四种不同的东西，长上下文下它们会分开：

- **客户端并发**：客户端同时保持在途的请求数（`--max-concurrency`）。
- **Prefill batch**：一个 prefill 步接收多少个新请求、多少个 prompt token，受 `--chunked-prefill-size`（单个请求的一块）、`--max-prefill-tokens`（每步 token 数）和 `--prefill-max-requests` 限制。
- **Decode batch**：一个 decode 步里有多少个请求在生成 token，服务端日志里记为 `#running-req`。
- **准入上限**：`--max-running-requests`，是上限，不是保证。

Decode batch 受 KV 池限制：所有运行中请求的 token（输入、已生成的 token 和预留）都要放得下。请求长度相同时，batch 最多是 `floor(KV 池 token 数 / (输入 + 输出 token 数))`，分页、MTP 状态和预留会让实际值更低。提高客户端并发或 `--max-running-requests` 都不能让 batch 超过这个上限。这些 VM 上的两个实测说明了这一点：

- `--mem-fraction-static 0.95` 时，一台 TP8 VM 的全注意力 KV 池有 1,442,464 个 token。16 个 64K 输入、1K 输出的请求需要 1,064,960 个 token，占池子的 74%，所以 16 个请求能同时 decode；这就是 [64K A/B](#受控-ab64k-上下文下的-block-scale-fp8-gemm-路径) 的设置。
- PD 的 decode 服务用 `--mem-fraction-static 0.85`，64K 时同时只跑 4 到 5 个请求，从 128K 起只跑 1 个（[上下文长度表](#吞吐怎样随上下文长度变化)）。

先按"上下文长度 × batch"规划显存和拓扑，再去调 kernel；报告结果时把 `#running-req` 和客户端并发写在一起。

#### 全新服务重复测

每个被采纳的 A/B 组都在全新启动的服务上跑两次。两次结果相差约 1% 以内（见 A/B 表），才能说 25% 的差距是真的；每组只跑一次是说明不了问题的。测一个新的上下文长度时，先测 1 个请求，再测几个依次发送，再测几个同时发送，最后在全新服务上重复；中途失败的点作为无效点发布，不做估算。

### 哪些优化可能改变模型输出

吞吐提升的前提是答案不变。上面每一项技术对数值的影响可以归成四类，类别决定了上线前要核对什么。优化后的吞吐测试打开了 FP8 KV 和固定 MTP 接受长度，阶段对比那几次运行还记录到 INT8 Quick Reduce 是打开的。[下面的准确率](#在优化后的-kernel-上实测的准确率)用的是同一批 kernel、按实际接受的 MTP，但没有打开 FP8 KV cache，所以已发布的准确率结果都不覆盖 FP8 KV。

上面每张卡片最后一行写了该项对输出的影响。按类别归总：

<!-- BEGIN GENERATED: precision-summary -->
- **有损——上线前必须核对准确率**。数据通路上某处用了更少的比特，可能让输出产生系统性偏移，上线前必须用准确率基准核对。 [FP8 KV cache + 向量化 5D 分页布局](#fp8-kv-cache--向量化-5d-分页布局)；[张量并行 all-reduce 使用 INT8 Quick Reduce](#张量并行-all-reduce-使用-int8-quick-reduce)；[混合精度 Triton router（MoE gate）GEMM](#混合精度-triton-routermoe-gategemm)
- **只有实现正确时才不改变输出**。设计上不改变输出分布，但前提是实现正确；一旦有 bug，输出会变而且不报错。 [多层 EAGLE MTP 投机解码及校验修复](#多层-eagle-mtp-投机解码及校验修复)
- **算术不变，只换 kernel 或布局**。算术约定不变，只换 kernel、布局或调度。求和顺序变了，结果可能在最后几位有差异，但不是系统性偏差。 [混合 SWA + GQA 的逐层 attention 分派](#混合-swa--gqa-的逐层-attention-分派)；[MTP target verify 使用 AITER unified attention](#mtp-target-verify-使用-aiter-unified-attention)；[Chunked prefill、page size 与 SWA 池容量](#chunked-prefillpage-size-与-swa-池容量)；[Decode 图捕获（HIP graph）](#decode-图捕获hip-graph)；[FlyDSL paged-attention decode kernel（head 192，page 64）](#flydsl-paged-attention-decode-kernelhead-192page-64)；[权重预重排的 block-scale FP8 GEMM](#权重预重排的-block-scale-fp8-gemm)；[按 shape 调优的 fused-MoE kernel 表](#按-shape-调优的-fused-moe-kernel-表)；[head 192、page 64 的 FP8 batch-prefill tile](#head-192page-64-的-fp8-batch-prefill-tile)；[Prefill/Decode 分离（1P1D），KV 走 RDMA](#prefilldecode-分离1p1dkv-走-rdma)；[一个路由后挂多个 prefill 副本（DP=2）](#一个路由后挂多个-prefill-副本dp2)
- **测试方法——生成内容不能算分**。这种模式下生成的内容不是模型的回答，绝不能拿来算准确率。 [Fake prefill：只测 decode](#fake-prefill只测-decode)；[性能测试固定 MTP 接受长度](#性能测试固定-mtp-接受长度)；[按饱和点设计并发阶梯](#按饱和点设计并发阶梯)
<!-- END GENERATED: precision-summary -->

INT8 Quick Reduce 要单独提醒。实测时用的启动脚本都没有设置它：`rocm/sgl-dev` 基础镜像自带 `ROCM_QUICK_REDUCE_QUANTIZATION=INT8`，实测时记录下来的容器环境里就有它（哈希见 [`evidence/runs.json`](evidence/runs.json)），从这个镜像启动的每个服务都会继承。本仓库的 profile 把它显式写了出来，让这个继承值可见、可以消融；固定 runtime 的准确率角色把它重新设成 `NONE`。在干净构建时，同样的基础镜像 ENV 机制还悄悄覆盖了 Dockerfile 的一个 ARG，所以那里的每个版本参数都加了 `PIN_` 前缀。

#### 在优化后的 kernel 上实测的准确率

**问题。** 用优化后的 kernel、MTP 按实际接受，模型在公开基准上是否仍然答得对？

**输入。** 两台 VM，每台跑一个独立的 TP8 服务（prefill 和 decode 在同一个服务里），用的是优化后栈的 kernel：AITER attention、CK block-scale FP8 GEMM、调优 fused-MoE 表（启动前核对哈希），以及按草稿模型实际接受率运行的多层 EAGLE MTP（固定接受长度的变量都已去掉并做了检查）。权重为 FP8，KV cache 为模型默认精度（没有 `--kv-cache-dtype`），page size 1，1M 上下文。AIME 用 temperature 1.0、top-p 0.95、最多 65,536 个 token，打开 thinking；其他五个基准用 temperature 0、最多 16,384 个 token。每个基准都按原始顺序取前面的题目评分，遍数见表。输出为空且达到 token 上限的回答算错。

<!-- BEGIN GENERATED: accuracy-table -->
| 基准 | 评分范围 | 准确率 |
|---|---|---:|
| AIME24_25 | 前 16 题 × 1 遍 | **100.00%**<br>16 / 16 |
| CMMLU | 前 128 题 × 3 遍 | **89.84%**<br>345 / 384 |
| MinervaMath | 前 1,536 题 × 3 遍 | **97.61%**<br>4,498 / 4,608 |
| MMLU-Pro | 前 512 题 × 2 遍 | **89.36%**<br>915 / 1,024 |
| MMLU-Redux | 前 512 题 × 3 遍 | **96.22%**<br>1,478 / 1,536 |
| SuperGPQA | 前 512 题 × 1 遍 | **70.31%**<br>360 / 512 |
<!-- END GENERATED: accuracy-table -->

**边界。** 这些是子集上的绝对分数（共 3,216 道题、8,080 个评分回答），不是 A/B。没有给关掉优化的运行打分，所以这张表说明的是优化后的 kernel 和按实际接受的 MTP 能给出正常的答案，而不是它们对输出毫无影响。有两个有损开关没有覆盖：FP8 KV cache 是关着的；Quick Reduce 的实际设置没有记录（启动脚本没有设置，基础镜像导出的是 INT8）。基准前面的题目可能比整体更容易或更难，16 道 AIME 题单独看说明不了什么。FP8 KV 和 Quick Reduce 按下面的步骤核对。

**kernel 级数值检查。** 上游提交为每个 MiMo 专用 kernel 加了测试，在 MiMo 的 shape（head 192、page 64、FP8 KV、query 长度 4）上与 PyTorch 参考实现比对，其中包括 2 GiB 偏移的用例。这些测试需要 MI300X，本仓库没有运行：

<!-- BEGIN GENERATED: numerical-tests -->
- [`ROCm/FlyDSL@e46db60`](https://github.com/ROCm/FlyDSL/commit/e46db6020b4560de82a7136d78cc33a5186338f4) `tests/kernels/test_pa.py::test_tile_pa_vectorized_5d_matches_torch`
- [`ROCm/FlyDSL@e46db60`](https://github.com/ROCm/FlyDSL/commit/e46db6020b4560de82a7136d78cc33a5186338f4) `tests/kernels/test_pa.py::test_pa_decode_ps_rejects_unsupported_bf16_asymmetric_paths`
- [`ROCm/FlyDSL@e46db60`](https://github.com/ROCm/FlyDSL/commit/e46db6020b4560de82a7136d78cc33a5186338f4) `tests/kernels/test_pa.py::test_pa_decode_ps_rejects_non_divisible_gqa_heads`
- [`ROCm/FlyDSL@ed9885e`](https://github.com/ROCm/FlyDSL/commit/ed9885eca4ffc45e2ec1dc45fa00824baa6b56d3) `tests/kernels/test_pa.py::test_fp8_head_dim_192_matches_torch`
- [`ROCm/FlyDSL@ed9885e`](https://github.com/ROCm/FlyDSL/commit/ed9885eca4ffc45e2ec1dc45fa00824baa6b56d3) `tests/kernels/test_pa.py::test_fp8_cache_offset_above_2gib`
- [`sammysun0711/FlyDSL@c99d5cd`](https://github.com/sammysun0711/FlyDSL/commit/c99d5cd97864c11e459cff9169d387d312790782) `tests/kernels/test_pa.py::test_mimo_v25_pro_head_192_accuracy`
- [`sammysun0711/aiter@10a9401`](https://github.com/sammysun0711/aiter/commit/10a94012efc1260dfdf16ba2f52fbda40a518a17) `op_tests/triton_tests/test_pa_decode_gluon.py::test_mimo_head_192_full_context_regression`
- [`sammysun0711/aiter@3f4ab48`](https://github.com/sammysun0711/aiter/commit/3f4ab482a2986919c784e469e23cfac7f93bb153) `op_tests/test_batch_prefill.py::test_batch_prefill_mimo_fp8_vectorized_page64`
<!-- END GENERATED: numerical-tests -->

kernel 测试证明的是 kernel 在测过的 shape 上与参考实现一致，并不能衡量 FP8 存储或 INT8 求和对端到端答案的影响；那需要模型级的检查。

**如何在你的模型上检查一个有损开关（本仓库未运行）。** 用固定 runtime 的准确率角色（真实 MTP 接受、Quick Reduce 关闭），每组只改一个有损开关。FP8 KV 这一组不是严格的单变量：FlyDSL decode 只支持 FP8 KV，所以这组同时把 target verify 的 kernel 换回了 AITER。

```bash
# A 组：FP8 KV cache（线上配置）
python tools/render_launch.py --profile rocm-mi300x-single --role server > arm_a.sh
# B 组：BF16 KV cache。FlyDSL decode 依赖 FP8 KV，渲染器会要求两者一起去掉。
python tools/render_launch.py --profile rocm-mi300x-single --role server --ablate fp8-kv-5d --ablate flydsl-pa-decode > arm_b.sh
# Quick Reduce：在启动命令前 export ROCM_QUICK_REDUCE_QUANTIZATION=INT8，再跑一次 A 组。
```

对每一组，用固定版本 SGLang 自带的评测工具、temperature 0、在公开数据集上跑：

```bash
python3 -m sglang.test.run_eval --port 30001 --eval-name gsm8k --num-examples 1319
python3 -m sglang.test.run_eval --port 30001 --eval-name mmlu --num-examples 2000
python3 -m sglang.test.run_eval --port 30001 --eval-name gpqa
```

先把 A 组跑两遍，两遍之间的差可以当作初筛用的粗略噪声下限；两组之间的差落在这个范围内，就不能算是开关带来的影响。要发布结论，每组应重复多次并给出置信区间。打开 `fake-prefill` 或 `simulated-acceptance` 时生成的任何内容都不能拿来算分。

### 常见误解

- **「kernel 快多少倍，模型就快多少倍。」** FlyDSL kernel 只在 target verify 阶段的全注意力层上运行（见上面的分派代码），SWA 层、sink 层和其他算子的开销没变，kernel 的加速会被这部分占比稀释。
- **「调优 MoE 表同时改善了吞吐和延迟。」** decode 并发 64 和 128 时吞吐提升约 12%，TPOT 同时上升 12.6%–14.1%：这张表是用单 token 延迟换整批吞吐。
- **「客户端并发越高，吞吐越高。」** 并发阶梯在 64 就到平台期，再往上只有首 token 时间在增长。
- **「启动脚本没设的精度开关，就是关着的。」** `ROCM_QUICK_REDUCE_QUANTIZATION=INT8` 来自基础镜像的 ENV，实测时用的启动脚本都没有设置它，但它是打开的。要看进程环境，而不是看脚本。
- **「成功数 100% 就说明每个请求都正常。」** `--context-length` 太小时，超长 prompt 可能返回错误内容却被客户端记为成功；上下文余量规则就是为了拦住这种情况。

### 迁移到 NVIDIA GPU

框架层和负载层都是上游 SGLang：PD 分离、fake prefill、固定接受长度、EAGLE MTP、FP8 KV、chunked prefill 和 SWA 比例在 CUDA 上用的是同一组开关。算子层换的是实现，方法不变：按层类型选 attention kernel，用权重预打包的 block-scale FP8 GEMM，并在你自己的 GPU 上重新跑 fused-MoE 调优。[`profiles/cuda-hopper-pd.json`](profiles/cuda-hopper-pd.json) 把这套对应关系写成了配置，渲染出的角色与 MI300X profile 一致：

```bash
python tools/render_launch.py --profile cuda-hopper-pd --role decode
python tools/render_launch.py --profile cuda-hopper-pd --role decode --ablate ck-a8w8-gemm
```

CUDA profile 只是模板（`TEMPLATE_NOT_MEASURED`）。page size 和 SWA 比例要按你的 GPU 显存重新推算；每一项技术在采用之前，都应该按同样的 A/B 规则测一遍。

## 客户如何复现

用本仓库的 Dockerfile 部署优化后的栈：镜像只构建一次，推到你自己的镜像仓库，每个服务都作为一个独立容器从这个镜像启动。两条路线用同一个镜像。**单机**：一个 TP8 服务，用最终 runtime 的配置。**两台 VM 的 1P1D**：实测吞吐背后的 prefill/decode 拓扑。不用 GPU 核对已发布数字是另一条路径，见[测试与离线校验](#测试与离线校验)。

**1. 检查每台 VM。** Azure ND MI300X v5，已装好 ROCm 驱动和 Docker（含 BuildKit）。

```bash
rocm-smi --showproductname   # 8 个条目 GPU[0] ... GPU[7]，型号为 MI300X
ibv_devinfo -l               # 1P1D：8 个 RDMA 设备，mlx5_ib0 ... mlx5_ib7
show_gids                    # 1P1D：确定 MC_GID_INDEX 用的 GID index（实测 VM 上是 3）
df -h /mnt/models            # 本地 NVMe 卷上留出权重的空间（约 1 TB）
docker buildx version
```

权重从 VM 的本地 NVMe 卷加载：每次启动容器都要把权重完整读一遍。这类 VM 的本地 NVMe 是临时存储，VM deallocate 后数据就没了，所以持久副本要放在别处（例如 Azure Blob Storage），每次分配 VM 后再拷到 NVMe 上。

**2. 在每台 VM 上取得部署文件和模型。** 把模型固定到一个版本，这样每台 VM、以后每次重新部署加载的都是同一批文件。启动参数里有 `--trust-remote-code`，因为模型自带建模代码；请审阅你固定的那个版本里的代码。

```bash
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share && git sparse-checkout set Deep-Learning/LLM-Inference-Optimization-on-Azure-GPU-VMs
cd Deep-Learning/LLM-Inference-Optimization-on-Azure-GPU-VMs
export MODELS=/mnt/models
export MODEL_REPO=        # 模型在 Hugging Face 上的仓库 id，见其模型卡
export MODEL_REVISION=    # 你验证过的 commit
hf download "$MODEL_REPO" --revision "$MODEL_REVISION" --local-dir "$MODELS/MiMo-V2.5-Pro"
cp docker/mimo.env.example docker/mimo.env
```

填好 [`docker/mimo.env`](docker/mimo.env.example)，把同一份文件复制到每台 VM。服务要读取的设置都在里面：镜像 digest（第 3 步得到）、容器内的模型路径；1P1D 还需要两台 VM 的地址、RDMA 设备和 GID index。下面的主机命令用 `set -a; . docker/mimo.env; set +a` 加载它，容器则通过 `--env-file` 读取。

**3. 镜像只构建一次，推到镜像仓库。** 在任意一台装有 BuildKit 的 x86-64 机器上执行，用其中一台 VM 也可以：

```bash
export ACR_NAME=          # 你的 Azure Container Registry
REGISTRY="$ACR_NAME.azurecr.io"
az acr login --name "$ACR_NAME"
docker buildx build --platform linux/amd64 --tag "$REGISTRY/mimo-mi300x:$(git rev-parse --short=12 HEAD)" \
  --metadata-file build-meta.json --push docker/
DIGEST=$(python3 -c "import json; print(json.load(open('build-meta.json'))['containerimage.digest'])")
echo "IMAGE=$REGISTRY/mimo-mi300x@$DIGEST"   # 把这一行写进每台 VM 的 docker/mimo.env
```

然后在每台 VM 上：`set -a; . docker/mimo.env; set +a; docker pull "$IMAGE"`。

[Dockerfile](docker/Dockerfile) 从按 digest 固定的公开基础镜像开始，检出 SGLang `878fff1`、AITER `3f4ab48`（含 Composable Kernel `af7118e` 及其自带 patch），从 PyPI 安装 FlyDSL `0.2.4`，并取 `c99d5cd` 的 FlyDSL kernel；wheel 哈希、CK commit 或最后的 import 检查任何一项对不上，构建都会停止。tag 记录源码 commit；按 digest 运行，保证两台 VM 以及之后每次重启用的都是同一个镜像。基础镜像已缓存时，干净构建约 6 分钟，镜像 27.9 GB。

**4. 渲染启动脚本。** profile 把实测配置转成每个角色一个脚本；主机、路径和设备都保留为变量，由容器从 `docker/mimo.env` 读取。

单机：

```bash
mkdir -p run
python3 tools/render_launch.py --profile rocm-mi300x-single --role server > run/server.sh
```

1P1D（在每台 VM 上渲染，或渲染一次后复制 `run/`）：

```bash
mkdir -p run
python3 tools/render_launch.py --profile rocm-mi300x-pd --role prefill --ablate simulated-acceptance > run/prefill.sh
python3 tools/render_launch.py --profile rocm-mi300x-pd --role decode --ablate simulated-acceptance > run/decode.sh
python3 tools/render_launch.py --profile rocm-mi300x-pd --role router > run/router.sh
```

这些是上线服务用的配置，不是压测配置。`--ablate simulated-acceptance` 去掉了测量时用的固定 MTP 接受长度，MTP 只保留模型真正接受的草稿 token。单机的 `server` 角色本来就按实际接受运行，并且关闭了 Quick Reduce。1P1D 脚本保留了和实测一致的 INT8 Quick Reduce；在你的负载上[核对准确率](#哪些优化可能改变模型输出)之前，可以加 `--ablate int8-quick-reduce` 改为全精度求和。

**5. 启动服务。** 单机：

```bash
set -a; . docker/mimo.env; set +a
bash docker/run-role.sh server run/server.sh
bash docker/wait-ready.sh 127.0.0.1 30001 3600 mimo-server
```

1P1D：

```bash
set -a; . docker/mimo.env; set +a
bash docker/run-role.sh prefill run/prefill.sh                         # 在 VM A 上
bash docker/run-role.sh decode run/decode.sh                           # 在 VM B 上
bash docker/wait-ready.sh "$PREFILL_HOST" 30000 3600 mimo-prefill      # 在 VM A 上
bash docker/wait-ready.sh "$DECODE_HOST" 30001 3600                    # 在 VM A 上
bash docker/run-role.sh router run/router.sh                           # 在 VM A 上，两个都打印 READY 之后再启动
```

[`docker/run-role.sh`](docker/run-role.sh) 把每个角色启动为一个有名字的容器（`mimo-server`、`mimo-prefill`、`mimo-decode`、`mimo-router`），容器的主进程就是服务本身：失败时最多自动重启 3 次，日志自动轮转，模型只读挂载，设置从 env 文件读取。只有 GPU 角色才拿到 RDMA 和 AITER 需要的宿主机权限（`--privileged`、宿主机 IPC、`/dev/kfd`、`/dev/dri`、`/dev/mem`、`CAP_SYS_ADMIN`），所以只在专用的 GPU 虚拟机上运行。[`docker/wait-ready.sh`](docker/wait-ready.sh) 轮询不会生成 token 的 `/server_info`，打印服务报告的 KV 容量；如果指定的容器已经退出，就提前结束等待。容器第一次启动时要编译 AITER JIT kernel 并加载权重，需要几十分钟。

所有容器都用宿主机网络，服务监听所有网卡。30000 和 30001 端口只放行两台 VM 私网地址之间的访问；40000 端口同样不要对外开放，VM 之外的客户端需要访问时，在前面加一个带认证的网关。

**6. 确认优化已生效，再发一个请求。** 单机：

```bash
docker logs mimo-server 2>&1 | grep -m1 module_gemm_a8w8_blockscale_bpreshuffle   # CK block-scale GEMM
docker logs mimo-server 2>&1 | grep -m1 mimo_v2_5_pro_b16_tuned_fmoe              # 调优 fused-MoE 表
curl -s --retry 30 --retry-connrefused --retry-delay 10 http://127.0.0.1:30001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "default", "messages": [{"role": "user", "content": "What is 17 * 23? Reply with the number."}], "max_tokens": 1024, "temperature": 0}'
```

1P1D：prefill 服务的检查和请求在 VM A 上执行，decode 服务的检查在 VM B 上执行。

```bash
docker logs mimo-decode 2>&1 | grep -m1 module_gemm_a8w8_blockscale_bpreshuffle   # CK block-scale GEMM
docker logs mimo-prefill 2>&1 | grep -m1 mimo_v2_5_pro_b16_tuned_fmoe             # 调优 fused-MoE 表
docker logs mimo-prefill 2>&1 | grep -i mooncake | grep -m3 mlx5_ib                # 正在使用的 RDMA 设备
docker logs mimo-prefill 2>&1 | grep -i mooncake | grep -i -m3 tcp                 # 应当没有输出
curl -s --retry 30 --retry-connrefused --retry-delay 10 http://127.0.0.1:40000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model": "default", "messages": [{"role": "user", "content": "What is 17 * 23? Reply with the number."}], "max_tokens": 1024, "temperature": 0}'
```

每项检查都输出注释里说的内容，并且回复中 `choices[0].message.content` 含有 `391`、`finish_reason` 为 `stop`，即为完成。

**7. 日常运维。**

- **日志：** `docker logs -f mimo-decode`。
- **重启：** `docker restart mimo-decode` 会保留容器里已编译好的 AITER kernel；`docker rm` 会把它们丢掉，下次启动要重新编译。
- **崩溃、卡死和重启机器：** 服务崩溃后容器会自动重启，最多 3 次。VM 或 Docker 重启后容器不会自动拉起，卡死的服务也不会被重启。无人值守运行时，用 systemd 或带就绪检查的编排工具来执行第 5 步的命令。
- **升级或回滚：** 构建并推送新镜像（第 3 步），更新 `docker/mimo.env` 里的 `IMAGE`。在每台 VM 上用 `docker rm -f` 删掉各角色容器，再重复第 5 步：先启动服务，最后启动路由。回滚就是换回之前的 digest。只有一组服务时，这就是一次停机维护：进行中的请求会失败，新容器就绪之前服务暂停。要避免停机，就用新 digest 再起一组服务，检查通过后再切换路由。
- **停止：** 在 VM A 上 `docker rm -f mimo-router mimo-prefill`，在 VM B 上 `docker rm -f mimo-decode`；单机则是 `docker rm -f mimo-server`。之后把 VM deallocate（`az vm deallocate`）；只在 VM 内部关机，计算资源仍会计费。deallocate 也会清空本地 NVMe，下次分配 VM 后要从第 1 步的拷贝开始。

**复现页面上的数字。** 本页的吞吐是在 MTP 固定接受长度 3 的条件下测的。要和它比较，渲染 prefill 和 decode 时不要加 `--ablate simulated-acceptance`，重启这两个容器，然后在 VM A 上把压测客户端作为一次性容器运行：

```bash
python3 tools/render_launch.py --profile rocm-mi300x-pd --role bench-decode > run/bench-decode.sh
python3 tools/render_launch.py --profile rocm-mi300x-pd --role bench-prefill > run/bench-prefill.sh
CONCURRENCY=64 bash docker/run-role.sh bench run/bench-decode.sh | tee decode_c64.log
INPUT_LEN=8192 bash docker/run-role.sh bench run/bench-prefill.sh | tee prefill_8k.log
python3 tools/bench_log.py project decode_c64.log -o my_decode_c64.txt
python3 tools/bench_log.py parse my_decode_c64.txt
```

`Successful requests` 等于 prompt 数量（decode 256、prefill 16）即为完成。不加 `--dataset-path` 时，`bench_serving` 会下载它用来采样文本的 ShareGPT 文件，离线主机需要准备本地副本。这套配置只用于测量。

**测量一项改动。** 渲染同一个角色、去掉一项技术，只替换这一个容器，每组用完全相同的客户端命令跑两次。下面的例子在 1P1D 的 decode 服务上去掉已发布 A/B 的两个开关；它只是演示方法，并没有重复 [`evidence/runs.json`](evidence/runs.json) 里记录的单机 64K 实验：

```bash
python3 tools/render_launch.py --profile rocm-mi300x-pd --role decode --ablate ck-a8w8-gemm --ablate unified-verify > run/decode-baseline.sh
docker rm -f mimo-decode && bash docker/run-role.sh decode run/decode-baseline.sh
```

**哪些步骤实际跑过。** 在一台只有 CPU、装有 Docker 的虚拟机上跑过：第 3 步的镜像构建（干净环境，用 `--metadata-file` 和 `--load` 代替 `--push`，见 [`evidence/docker-build.json`](evidence/docker-build.json) 和 [`evidence/deploy-check.json`](evidence/deploy-check.json)）；用 `run-role.sh` 从渲染出的脚本启动路由角色，路由就是容器的主进程，`docker stop` 0.5 秒返回；`wait-ready.sh` 对一个模拟的 `/server_info` 的检查；以及压测角色的变量传递和只读模型挂载。还没有跑过：推送镜像和按 digest 拉取、GPU 角色（server、prefill、decode），以及第 6 步的检查和请求。这些步骤依据的是记录下来的启动配置。另外，这个 Dockerfile 构建的 runtime 比实测吞吐所用的栈更新，各测量小节都写明了所用的栈。

### 容易误判的故障

下面是在 MI300X 上把这套栈跑起来时的运维观察，不是实测结果；只有图捕获这一项在本页有公开的数字。第一组只会让运行变慢，服务照常工作。

- **KV 传输退回 TCP。** 容器没有 `--privileged`、`/dev/mem` 和 `CAP_SYS_ADMIN` 时，Mooncake 会悄悄改用 TCP 而不是 RDMA。token 仍然正确，吞吐却会下降。把"RDMA 已初始化"作为启动检查项。
- **decode 服务关掉了图捕获。** 加了 `--disable-cuda-graph` 后，decode 服务在[基线 A/B](#从基线栈到优化后累计提升) 中只剩三分之一的吞吐，日志里没有任何异常。每次运行前，把每个启动脚本和已知正确的版本逐项比对。
- **镜像里有两份 kernel 库。** 同一个 AITER 版本从不同目录导入时表现不同。要检查导入路径和服务日志里的 kernel 名称，而不只是版本号。
- **调优表从未命中。** 对没有调优记录的 fused-MoE shape，AITER 会在日志里打印 `default`。启动时检查日志里关键 shape 的情况。

第二组会让服务停下或卡住，但原因容易看错：

- **多线程加载权重卡住。** 在 PD 服务上，多线程加载权重时各张量并行 rank 卡在缺页处理里；`--model-loader-extra-config '{"enable_multithread_load": false}'` 解决了这个问题。
- **prefill 服务上的重叠调度。** 它触发了 HIP 非法地址错误，所以吞吐测试都用了 `--disable-overlap-schedule`。
- **会生成 token 的健康检查。** SGLang 的 `/health` 默认会真的生成一个 token（`SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION`），频繁探测把 prefill 服务的 detokenizer 卡住了。把它设为 `0`，改为轮询 `/server_info`。
- **每步一次的 all-gather 在约 200K token 时超时。** 在数据并行度为 1 时，SGLang 已有的开关 `SGLANG_SCHEDULER_SKIP_ALL_GATHER=1` 可以避开它。
- **照搬其他 GPU 配置里的值。** 从另一套系统照搬的 `--chunked-prefill-size` 在启动时就失败了。这类值要按本 runtime 的限制推算。

## 测试与离线校验

在任何装有 Python 3.10 及以上版本的机器上都能核对已发布的数字，不需要 GPU；在上一节第 2 步克隆的目录里执行：

```bash
python -m unittest discover -s tests -v
python tools/build_evidence.py --check
python tools/build_readme.py --check
```

全部测试通过、两个检查都输出 `PASS` 即为完成。每项检查覆盖的范围：

- `python -m unittest discover -s tests -v`——上游 patch 与 SHA-256 锁一致；每份日志投影都能解析且与清单一致；发布的变化率能从绝对值重算；启动命令渲染和消融在两个平台上都符合文档；容器启动脚本为每个角色生成预期的 `docker run`，就绪检查只接受 JSON（这两项在 Linux 和 macOS 上运行）；README 不含私有内容或超出范围的比较。
- `python tools/build_evidence.py --check`——`evidence/measurements.json` 与从 `evidence/raw/`、`evidence/runs.json` 重新构建的结果完全一致。
- `python tools/build_readme.py --check`——两份 README 里每张生成的表、列表和每段代码摘录，都与从证据和固定 patch 重新渲染的结果一致。
- `python tools/draw_diagrams.py --check`——已提交的 PNG 的 SHA-256 与 `images/SOURCES.json` 记录一致。
- `python tools/check_repo.py`——链接和图片都能解析，标题顺序符合读者动线，每张表最多四列，中英文生成块里的数字一致，没有私有路径、主机名或超出范围的比较。

CI 在 Ubuntu 和 Windows、Python 3.10 与 3.12 上运行同一组命令（[workflow](../../.github/workflows/llm-inference-optimization-ci.yml)）。这些检查都不会启动 GPU 或服务：它们证明的是「已发布的数字确实来自已提交的证据」，而不是「重新跑一遍能得到同样的结果」。上一节的部署才是真正把这套栈跑起来的途径。

## 边界、目录与资料

**边界。**

- `LOCAL_MEASUREMENT`：A/B 和阶段对比各自只覆盖一种负载 shape，其他上下文长度、并发和 batch 组成没有在同样的控制条件下测过。
- `LOCAL_MEASUREMENT`：吞吐是在 MTP 固定接受 3 个 token 的条件下测的。真实负载平均接受的草稿 token 更少，吞吐会更低。
- `NOT_MEASURED`：最终 runtime（FlyDSL decode、向量化 5D KV、page 64、1M 上下文）没有在这里发布微软自己的吞吐测试，混合精度 router GEMM 也没有。
- `NOT_MEASURED`：有损开关（FP8 KV cache、INT8 Quick Reduce、混合精度 router）对准确率的影响没有测；吞吐测试时前两个是打开的。[优化后 kernel 的子集准确率](#在优化后的-kernel-上实测的准确率)是在 FP8 KV cache 关闭时测的。上面的步骤覆盖 FP8 KV 和 Quick Reduce；router 的改动需要在包含提交 `1f9bb2b` 的 runtime 上单独做 A/B。
- `NOT_MEASURED`：这里没有任何内容在 NVIDIA GPU 上跑过，CUDA profile 只是上游开关的对应关系。
- `SOURCE_FACT`：摘录中 FlyDSL、CK 和 MTP 的 shape 检查把每个 kernel 限定在 MiMo 的 shape 上（每个 rank 16 个 query head、1 个 KV head，head 192，page 64，gfx942）。换一个模型需要重新验证，不是改改开关就行。

**目录。**

- [`evidence/runs.json`](evidence/runs.json)——每次运行的身份、拓扑、控制变量和脚本哈希。
- [`evidence/raw/`](evidence/raw/)——各数据源的投影：`sglang.bench_serving` 输出（每次运行的负载参数和结果块）、调度器日志审计中的 A/B 采样值、长上下文和副本的结果表、逐条回答的准确率评分，以及基线栈的客户端结果和汇总。
- [`evidence/raw-manifest.json`](evidence/raw-manifest.json)——每份私有原始日志及其公开投影的 SHA-256。
- [`evidence/measurements.json`](evidence/measurements.json)——全部对比结果，由 `tools/build_evidence.py` 生成。
- [`evidence/docker-build.json`](evidence/docker-build.json)——干净 Docker 构建的回执：commit、Dockerfile 哈希、构建器、镜像 id 以及日志里的各步记录。
- [`evidence/deploy-check.json`](evidence/deploy-check.json)——在只有 CPU 的虚拟机上做的容器检查回执：跑了哪些部署步骤、观察到什么、哪些没跑，以及被测脚本的哈希。
- [`upstream/`](upstream/)——文中讨论的每个 commit 的完整 patch，以及 `SOURCES.lock.json`（哈希、许可证、所属层、是否在固定 runtime 中）。
- [`profiles/`](profiles/)——技术目录、实测的 MI300X profile 和 NVIDIA 模板。
- [`tools/`](tools/)——日志投影与解析、证据和 README 生成器、启动命令渲染、画图、公开内容审计。
- [`tests/`](tests/)——离线测试。
- [`docker/`](docker/)——Dockerfile、按角色启动容器的脚本、就绪检查和设置模板。
- [`images/`](images/)——示意图及其哈希台账。

**上游提交。**

<!-- BEGIN GENERATED: upstream-table -->
- [`ROCm/FlyDSL@e46db60`](https://github.com/ROCm/FlyDSL/commit/e46db6020b4560de82a7136d78cc33a5186338f4) — [Kernel][PA] Support BF16 vectorized KV with asymmetric K/V head dim (#1065)  
  算子层 · 上游后续提交，不在固定 runtime 中
- [`ROCm/FlyDSL@ed9885e`](https://github.com/ROCm/FlyDSL/commit/ed9885eca4ffc45e2ec1dc45fa00824baa6b56d3) — [Bugfix][PA] Fix D192 query staging and 64-bit cache offsets (#1064)  
  算子层 · 上游后续提交，不在固定 runtime 中
- [`sammysun0711/FlyDSL@c99d5cd`](https://github.com/sammysun0711/FlyDSL/commit/c99d5cd97864c11e459cff9169d387d312790782) — Fix head-192 PA decode accuracy and long-context for MiMo-V2.5-Pro  
  算子层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/aiter@10a9401`](https://github.com/sammysun0711/aiter/commit/10a94012efc1260dfdf16ba2f52fbda40a518a17) — fix(pa_decode_gluon): correct head-192 persistent MTP decode  
  算子层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/aiter@3f4ab48`](https://github.com/sammysun0711/aiter/commit/3f4ab482a2986919c784e469e23cfac7f93bb153) — feat (MHA): Optimize MiMo FP8 page-64 batch prefill with a head-192 CK specialization  
  算子层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/aiter@d725746`](https://github.com/sammysun0711/aiter/commit/d725746a0f8c233d8e46e2771a7c8dbcd06e40d9) — add tuend moe (#5)  
  算子层 · 在实测 runtime 中
- [`sammysun0711/aiter@fc96a4f`](https://github.com/sammysun0711/aiter/commit/fc96a4f9f5f3e931cbb9de275c8aa01136417500) — Add MiMO-v2.5-Pro ck a8w8 blockscale gemm tuned config on MI300X (gfx942 304 CU)  
  算子层 · 在实测 runtime 中
- [`sammysun0711/sglang@0cfc48b`](https://github.com/sammysun0711/sglang/commit/0cfc48b0e374d7e84c122f739182a39feea56d46) — feat(MHA): Route MiMo cached prefill directly to AITER page-64 attention  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/sglang@1f9bb2b`](https://github.com/sammysun0711/sglang/commit/1f9bb2b4c55cdc7bd5de1ac7977f76afab101a97) — (feat): Add opt-in mixed-precision Triton router GEMM for MiMo prefill  
  算子层 · 后续分支，不在任何 runtime 中
- [`sammysun0711/sglang@2f9b9ae`](https://github.com/sammysun0711/sglang/commit/2f9b9aedf32977bc5d088a86ec0a73bcf432a4d0) — Add env variable SGLANG_USE_AITER_CK_BLOCKSCALE and SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE to use ck a8w8 gemm on gfx942 instead of triton a8w8 gemm  
  推理框架层 · 在实测 runtime 中
- [`sammysun0711/sglang@78cd40c`](https://github.com/sammysun0711/sglang/commit/78cd40c7a5102524536daf9a3178426777174d2d) — fix(speculative): isolate AITER MTP draft KV layout and graph metadata  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/sglang@878fff1`](https://github.com/sammysun0711/sglang/commit/878fff15647fe3dabb32aa3a335b0ad16e3ee878) — bugfix(MTP): Fix HIP non-greedy EAGLE verification for MTP topk=1 (tree_topk) speculative decoding  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/sglang@a2fd773`](https://github.com/sammysun0711/sglang/commit/a2fd773ab43f960f5f2c29b5c592b0ca43c5ba8f) — feat(flydsl pa decode): add configurable FlyDSL partition counts  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/sglang@ba15db1`](https://github.com/sammysun0711/sglang/commit/ba15db1a576dcdc8d51ba15bd069b9fd1f748d97) — feat: Add opt-in FlyDSL paged decode for MiMo EAGLE verification  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/sglang@db840d9`](https://github.com/sammysun0711/sglang/commit/db840d935a9f7097dbeb5f1b0dba4d261057a2bd) — [AMD] Fix aiter SWA handling in draft_extend_v2 for MTP speculative decoding  
  推理框架层 · 在实测 runtime 中
- [`sammysun0711/sglang@e11c515`](https://github.com/sammysun0711/sglang/commit/e11c5155f0845079211c2a4d0b8a4ab3669039f9) — feat(aiter attention backend): use Gluon PA for vectorized-5D target verification  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
- [`sammysun0711/sglang@f26ae30`](https://github.com/sammysun0711/sglang/commit/f26ae30063143411f3ae552af1830fa46e3ee0fd) — fix(EAGLE verification): sync result across TP ranks  
  推理框架层 · 在固定 runtime 中，本仓库未测吞吐
<!-- END GENERATED: upstream-table -->

**资料。** [SGLang](https://github.com/sgl-project/sglang) · [AITER](https://github.com/ROCm/aiter) · [FlyDSL](https://github.com/ROCm/FlyDSL) · [Composable Kernel](https://github.com/ROCm/composable_kernel) · [Mooncake](https://github.com/kvcache-ai/Mooncake) · [Azure ND MI300X v5 系列](https://learn.microsoft.com/azure/virtual-machines/sizes/gpu-accelerated/ndmi300xv5-series)。各 patch 保留其上游许可证（SGLang 与 FlyDSL 为 Apache-2.0，AITER 为 MIT），详见 [`upstream/SOURCES.lock.json`](upstream/SOURCES.lock.json)。
