# 深入解析 DeepSeek DeepEP：如何用极致通信优化加速现代 MoE 模型

DeepEP 本质上把同步的 All-to-All (A2A) 通信拆成若干条 GPU 直连的异步 P2P 流：先在源端只挑出必须跨卡的 token 压成 FP8 小包，再并行走 NVLink / RDMA。这样数据量骤减且通信与计算能完全重叠，最终把带宽跑到硬件极限、把单 token 往返延迟压到百微秒级，几乎抹平 MoE 模型的通信瓶颈。

| 缩写             | 全称                     | 本文语义                                  |
| ---------------- | ------------------------ | ----------------------------------------- |
| MoE              | Mixture-of-Experts       | 稀疏激活的大模型结构                      |
| Expert           | —                        | 通常是一段两层 MLP (FFN)                  |
| dispatch/combine | —                        | token→Expert / Expert→token 的 All-to-All |
| NVLink           | NVIDIA 高速 GPU 互连     | ~150 GB/s 单向                            |
| RDMA             | Remote DMA over IB       | ~45 GB/s 单向（400 Gb/s CX-7）            |
| FP8              | 8 bit 浮点               | E4M3 或 E5M2，DeepEP 用于传输             |
| SM               | Streaming Multiprocessor | GPU 里的“核心簇”                          |
| QP               | Queue Pair               | RDMA 中的“通信通道”                       |

------

## 1. 为何 MoE 必须先解决通信

1. **激活稀疏**
   token 只走 k 个 Expert（k ≪ N_expert）→ 计算省，但 *路由信息* 变多。

2. **All-to-All 两跳**

   ```
   Router
     └── dispatch : 把 token 送到目标 GPU/Expert
     └── compute  : Expert MLP 并行
     └── combine  : 把结果拉回原 GPU
   ```

   

3. **通信成本实测（8 GPU, 8 Expert, batch = 4096）**

   | 阶段     | NCCL AllToAll | 比例 |
   | -------- | ------------- | ---- |
   | dispatch | 0.42 ms       | 35 % |
   | compute  | 0.48 ms       | 40 % |
   | combine  | 0.39 ms       | 25 % |

   → **65 % 时间 GPU 在等“快递”**，吞吐与延迟双双受限。

------

## 2. DeepEP = 专为 Expert-Parallel 打造的通信栈

### 2.1 设计目标

| 目标     | 可量化指标                               |
| -------- | ---------------------------------------- |
| 吃满带宽 | NVLink ≥ 150 GB/s；RDMA ≥ 45 GB/s        |
| 最小延迟 | 解码单 token < 0.4 ms                    |
| 重叠计算 | SM Idle < 5 %                            |
| 精准搬运 | 只发跨卡 token，配合 FP8 ↓ 数据量 ≥ 60 % |
| 易用     | Python API + handle 自动管理             |

### 2.2 两套内核

| 内核            | 优化对象 | 推荐场景       |
| --------------- | -------- | -------------- |
| **normal**      | 吞吐     | 训练 / Prefill |
| **low-latency** | 单包时延 | 自回归解码     |

------

## 3. 深剖架构

```
┌───────────────── Python ─────────────────┐
│ Router                               │  Buffer (dispatch/combine API)
│  topk_idx / weight                   │   ├─ get_dispatch_layout()
└─▼──────────────▲──────────────────────┘   └─ low_latency_dispatch()
  runtime.cu: 管理 stream / event / 显存
     │
┌────┴─ NVLink P2P (intranode.cu) ────────────┐
│     自定义 PTX + IPC 直接 GPU↔GPU          │
└─▲──────────────────┬──────────────────────┘
  │                  │
┌─┴─ RDMA P2P (internode.cu) ────────────────┐
│ GPU-initiated NVSHMEM, QP=Expert, VL 分流 │
└────────────────────────────────────────────┘
```



### 3.1 数据流 10 步详解

| #    | 步骤                                    | GPU / CPU | 典型耗时     |
| ---- | --------------------------------------- | --------- | ------------ |
| 1    | Kernel 扫 topk_idx，分类本卡/跨卡 token | GPU       | 5–10 µs      |
| 2    | `cub::Scan` 得到发送 offset 表          | GPU       | < 0.1 ms     |
| 3    | 动态 malloc 精确 send-buf               | CPU       | PCIe async   |
| 4    | Kernel ② 将需跨卡 token 打包 + FP8 压缩 | GPU       | 0.02–0.1 ms  |
| 5    | 提交 NVLink / RDMA DMA 任务             | GPU → DMA | 0.05 ms      |
| 6    | **Expert MLP 计算**                     | GPU       | 0.3–1 ms     |
| 7    | RDMA 完成写显存 + flag 更新             | DMA       | 隐藏在 #6 内 |
| 8    | combine 调用：读取 handle 中偏移        | GPU       | 0.02 ms      |
| 9    | 稀疏 axpy 加权求和                      | GPU       | 0.05–0.2 ms  |
| 10   | 可选反向：dispatch / combine 对调       | GPU       | 同上         |

### 3.2 内核亮点

1. **自定义 PTX**
   `ld.global.nc.L1::no_allocate.L2::256B`
   – 指定不污染 L1，分 256 B chunk 写 L2→NVLink。

2. **RDMA 直写**

   ```
   nvshmemx_putmem_nbi_block(remote_ptr, local_ptr, bytes, pe)
   ```

   

   – GPU 发 Work Request，无 host 轮询。
   – 一 Expert = 一 QP，抢占冲突 < 2 %。

3. **Hook 式重叠**

   ```
   recv, cnt, handle, evt, hook = buf.low_latency_dispatch(...)
   do_attention()
   hook()   # 需要结果前再触发 RDMA read
   ```

   

   – 0 SM 占用的双 micro-batch overlap👇

   ```
   ┌Attention┐┌MoE(Expert)┐
   Token i   ████▒▒▒▒▒▒
   Token i+1     ████▒▒▒▒
   ↑————— RDMA / NVLink 在灰色后台跑 ————↑
   ```

   

4. **SM 配额**
   `Buffer.set_num_sms(24)` → 将通信 kernel 限制 24 SM，其余留给 GEMM。

------

## 4. 编程模型

### 4.1 环境 & 安装

```
export NVSHMEM_DIR=$HOME/nvshmem
python setup.py install          # 或 --symlink
```



硬件要求：H100/H800 (Hopper)，CUDA ≥ 12.3，PyTorch ≥ 2.1。
*Ampere 支持在 roadmap 上，带宽会降低。*

### 4.2 训练完整示例（前向 + 反向）

```
import torch, torch.distributed as dist
from deep_ep import Buffer

group = dist.new_group()
buf = Buffer(group, nvl_bytes=0, rdma_bytes=256<<20)
Buffer.set_num_sms(24)           # 通信占 1/6 SM

def moe_forward(x_fp8, idx, w):
    recv, _, _, _, hdl, _ = buf.dispatch(x_fp8, idx, w, num_experts=8)
    y = expert_mlp(recv)                      # 你的 MLP
    out, _ = buf.combine(y, hdl)
    return out, hdl

def moe_backward(grad_out, hdl):
    grad_recv, _, _, _, _, _ = buf.dispatch(grad_out, handle=hdl)   # combine 的反向
    grad_in, _ = buf.combine(grad_recv, hdl)                        # dispatch 的反向
    return grad_in
```



### 4.3 解码（超低延迟）完整示例

```
buf = Buffer(group, 0, rdma_bytes=32<<20,
             low_latency_mode=True, num_qps_per_rank=local_experts)

def decode_step(hidden_fp8, idx, w):
    r, cnt, hdl, evt, hook = buf.low_latency_dispatch(
            hidden_fp8, idx, num_max_dispatch_tokens_per_rank=128,
            num_experts=8, return_recv_hook=True)

    attn_out = attention_block(hidden_fp8)   # 与通信重叠
    hook()                                   # 真正收包
    y = expert_mlp(r)                        # Expert 计算
    out, _, _ = buf.low_latency_combine(y, idx, w, hdl)
    return out
```



------

## 5. 性能

### 5.1 吞吐（训练 4096 tok，top-8）

| GPU×Node | Expert | NCCL (Tok/s) | DeepEP (Tok/s) | 提升    |
| -------- | ------ | ------------ | -------------- | ------- |
| 8×1      | 8      | 190 k        | **300 k**      | ↑ 1.58× |
| 64×8     | 64     | 1.46 M       | **2.33 M**     | ↑ 1.60× |

### 5.2 单 token 延迟（解码 batch = 128）

| Expert | NCCL (ms) | DeepEP normal | DeepEP LL | 说明      |
| ------ | --------- | ------------- | --------- | --------- |
| 8      | 0.78      | 0.52          | **0.38**  | NVLink 内 |
| 256    | 1.23      | 0.74          | **0.45**  | 跨机+RDMA |

### 5.3 火焰图对比（8 GPU）

```
NCCL all_to_all        DeepEP normal
██████ 通信            █ 通信提交
▒▒▒▒▒ 计算             ████ 计算
██████ 通信            ░░ 通信后台
```



GPU Idle: 39 % → **4 %**

------

## 6. DeepEP vs 其它通信库

| 特性             | NCCL AllToAll | MPI_Alltoallw | OneCCL | **DeepEP** |
| ---------------- | ------------- | ------------- | ------ | ---------- |
| P2P 精确分拣     | ✗             | ✗             | 部分   | ✔          |
| NVLink↔RDMA 转发 | ✗             | ✗             | ✗      | ✔          |
| FP8 原生         | ✗             | ✗             | ✗      | ✔          |
| Hook-overlap     | 手写          | 难            | ✗      | ✔          |
| 单 token <0.4 ms | ✗             | ✗             | ✗      | ✔          |
| 专门针对 MoE     | ✗             | ✗             | ✗      | ✔          |

------

## 7. 部署 & 调优 Checklist

1. 网络
   - InfiniBand 400 Gb/s；VL0(normal), VL1(low-lat)、VL2(其它)。
   - Adaptive Routing：normal 关，low-lat 开（避免死锁）。
2. 显存预算
   - normal：NV-buf≈hidden·batch·fp8；RDMA-buf≈NV-buf。
   - low-lat：RDMA-buf ≈ batch_max·hidden·fp8·(4+ε)。
3. SM 配额
   - 训练 10~25 %，解码 0 （低延迟内核不占 SM）。
4. FP8 误差
   - dispatch 用 FP8，expert 内部切回 BF16；实际 loss 浮动 < 0.1 %。
5. 调参脚本
   - `tests/bench_normal.py --auto_tune`：给定 batch / hidden 自动算最佳 buffer。
   - `tests/profile_decode.py`：双 micro-batch overlap 示范。

------

## 8. 真实案例

### 8.1 DeepSeek-V3 671 B 预训练

- 128×H800，128 Expert。
- 替换通信后 **总训练天数从 18 天 → 11 天**，云租赁节省 ~$1.4 M。

### 8.2 GPT-MoE 社区复现

- 256 Expert，256 GPU (8 node)。
- DeepEP vs NCCL：迭代时间 3.7 s → 2.3 s，验证集 ppl 持平。

### 8.3 线上 Chatbot (batch 64)

- 两层解码 pipeline：attention→DeepEP→MLP。
- 延迟 28 ms → 14 ms，QPS +85 %。

------

## 9. Roadmap

1. **兼容 Ampere / Ada**（不含自定义 PTX，带宽约降 20 %）。
2. **自适应精度**：根据链路拥塞在 FP8 / FP16 间动态切换。
3. **拥堵控制**：集成 DCQCN 自动阈值。
4. **Optical IB & CXL**：预研 800 Gb/s 互连。
5. **统一稀疏 GEMM**：MoE-MLP 与通信 Buffer 直接零拷贝。

------

## 10. 结语

DeepEP 把 All-to-All 这种“看似天生慢、不可并行”的通信拆成了 **精确分拣 + 多路 P2P 并行 + 后台 DMA** 的流水线，在大规模稀疏模型时代扛起了 **Expert-Parallel 的通信底座**：

- 训练：带宽跑满，便宜算力不被闲置；
- 推理：单 token 400 µs 以内，真正实时对话；
- 工程：几行 Python API 即可迁移，几乎零侵入。

> 因为 NCCL All-to-All 卡住吞吐或延迟，试着把那行代码换成 `deep_ep.Buffer.dispatch()` —— 也许这一小步，就能让你的 GPU 集群满血复活。