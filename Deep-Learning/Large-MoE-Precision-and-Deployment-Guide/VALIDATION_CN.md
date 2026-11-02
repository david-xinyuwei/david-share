# 验证说明：组件精度与资源复算

[English](VALIDATION.md) · [主文档](README_CN.md) · [数据](data/model-evidence.json)

## 验证什么

本项目的可执行工具只读取公开元数据或重放已经保存的元数据，计算张量数据负载。它不运行模型、不申请 GPU、不决定生产卡数，不输出吞吐或质量分数。

两个采集时间分别为：模型 API 元数据 `2026-11-01T12:49:24.528Z`；原厂 NVFP4 配置摘要 `2026-11-01T12:51:18.489Z`。时间使用 UTC。数据文件保留了模型 ID、固定 revision、实际读取状态和范围；来源发布者与原始模型开发者是不同维度。

## 复算与测试

环境：Node.js 20+，不需要 npm 包。Shell 可以是 PowerShell 或 Bash，工作目录是本专题目录。也可以从其他目录通过绝对路径启动脚本；数据路径相对于脚本解析，不依赖当前目录。

```bash
node tools/inspect.mjs
node --test tests/inspect.test.mjs tests/census.test.mjs tests/mi300x.test.mjs
```

第一条成功时输出 JSON，`result_type` 为 `CALCULATED_FROM_PUBLIC_METADATA`，模型推理状态始终为 `NOT_RUN`。`tensor_payload_bytes` 是各 dtype 元素数乘以其存储字节数后求和；GB 用十进制，GiB 用二进制。它不包括 safetensors 文件头、其他文件、KV/状态缓存、运行工作区和通信缓冲。

第二条运行十九项测试。`inspect.test.mjs`（九项）：三个完整组件表及双语引用/本地链接一致性、独立仓库开篇、版式守卫（两版 README 的每卡预算、MI300X 结果、速度探针、复现步骤和先看结论五张对比表保持完整列数，没有被 `<br>` 切断的代码标识、空 `<code>` 标签或两列堆叠表；针对 2026-11-02 的版式回退）、U8 打包字节而非逻辑参数量、六行负载复算、Muse 401 保留、Nemotron router 排除、未知 dtype 拒绝、新 revision 不继承旧配置结论、联网失败不回退成旧数据成功。`census.test.mjs`（四项）：普查字节与 API 元数据逐字节一致、两个模型关键组件的 dtype 与张量数、未分类组件与篡改总数被拒绝。`mi300x.test.mjs`（六项）：`data/mi300x-run/summary.json` 的每个数字能回到对应的原始请求/响应/日志文件，公开投影中没有私有标识，四份文档引用的 Nemotron 与 Inkling 实测数字与 summary 一致，第 2 轮服务速度探针的中位数（并发 1 和 8 的 TTFT、解码与总吞吐 tok/s）在每份文档中都以带单位的表格行出现且与 `08_perf.json` 重算值逐字一致，文档没有宣称未执行的吞吐/质量验收，对 Muse 通过的描述只用 summary 中那次运行的加载/KV/token 数字，以及并行布局图（`images/mi300x-parallel-layout-{en,zh}.svg`）画的正是 summary 里三个第 2 轮布局的 TP/PP/EP 大小和每卡权重/KV 显存、只嵌入台账登记的未改动 Azure 虚拟机图标、哈希与 `data/visual-evidence.json` 一致，且在两份 README 中都以“原创”图说嵌入。测试中的 HTTP 返回对象是单元测试桩，不是在线模型证据。

## 新数据而非旧快照

```bash
node tools/inspect.mjs --live
```

这会重新调用六个模型的公开 API。检查返回的 `capture_utc` 与 `revision`，然后比较张量负载。该模式明确清空旧配置摘要，因为它没有重新检查大体积量化配置。遇到 HTTP 错误、未知 dtype 或身份变化时退出失败；不得把旧数据改为当前结果。

不需要也不应为此工具提供模型下载凭据。Muse 原始量化配置的访问限制是单独的已知缺口，不能通过其他账号或镜像绕过。

## 需要保留的异常

Nemotron BF16 的 API `safetensors.total` 与逐 dtype 元素数之和并不一致。工具同时报告两者及 `metadata_total_matches=false`，使用逐 dtype 计数计算字节，不悄悄修改源数据。压缩 checkpoint 的 `U8` 和 scale 张量元素数也不是原始逻辑参数量。

## 模型上线验收

从[主文档的步骤](README_CN.md#先选可验证路径再启动服务)选择该模型自己的官方配方。实际执行时必须记录权重 SHA、引擎提交/镜像摘要、GPU、并行拓扑、内核选择、K/V 与其他状态精度、请求原文和结果。BF16、FP8、NVFP4 使用相同真实业务任务；未跑的组合保持 `NOT_RUN`，不得借其他模型的结果补齐。

必须覆盖质量、结构化输出、工具调用、所需模态、长上下文、目标并发、峰值显存和持续运行。结果按实际观测记录，不把正常加载当成业务成功，不把低比特存储当成原生低比特计算。

## 当前验证状态

| 验证项 | 状态与边界 |
|---|---|
| 公开模型身份与六个固定 revision | 已读取 API；三个 BF16 版本于 2026-11-02 完整下载（Nemotron 3 Ultra 1,121,078,235,607 字节，Inkling 1,904,787,107,666 字节，Muse Spark Open 1,644,365,682,665 字节——Meta 当天上午批准闸门后下载）；其余六个版本未下载 |
| 原厂 NVFP4 配置 | Nemotron 与 Inkling 已解析；Muse 返回 401，未解析 |
| 逐张量 dtype 普查 | 两个 BF16 版本通过：从 safetensors 文件头读出 51,023 + 1,552 个张量，文件头字节合计与 API 元数据一致，无未分类名字模式（见「逐张量 dtype 普查」） |
| 文件诊断 | 已执行编辑器检查；不等于 Node 测试通过 |
| Node 测试与 CLI | 通过：十九项测试，零失败（`node --test tests/inspect.test.mjs tests/census.test.mjs tests/mi300x.test.mjs`，每次推送由 GitHub Actions `large-moe-precision-guide-ci.yml` 在 Ubuntu 和 Windows 上复跑）；覆盖三个四列表、每表 25 项、全部九个版本、双语来源/链接、六行字节复算、普查与 API 字节一致性、关键组件 dtype，以及文档引用的 MI300X 实测数字与 `data/mi300x-run/summary.json` 一致 |
| 表格布局 | 通过：四页全部表格分别检查 1280 和 390 像素宽度；分别核对表格和容器，均无横向溢出 |
| 本地完整预览 | 本修订等待脚本完成时超时，不计为完整渲染通过。图像字节和图源码未变，GitHub 显示另行验收 |
| MI300X BF16 加载与 smoke，Nemotron 3 Ultra | 8 × MI300X 通过（尝试 3）：引擎就绪，两条请求回答正确；内核、缓存精度与显存记录在「MI300X 实测」 |
| MI300X BF16 加载与 smoke，Inkling | 2 × 8 MI300X 通过（尝试 6，TP8 × PP2）：引擎就绪，三条请求返回，`max_tokens=1024` 的一条给出正确最终答案；TP8 × DP2 + EP16 布局（尝试 5）就绪后第二条请求挂起，记为该布局在本镜像上未通过 |
| MI300X BF16 加载与 smoke，Muse Spark Open | 2 × 8 MI300X 通过（尝试 3，TP8 × PP2，`vllm/vllm-openai-rocm:v0.33.0` + Ray）：引擎 4 分 36 秒就绪，四条请求返回，`max_tokens=4096` 的一条在 1,289 个推理 token 后给出正确最终答案；尝试 1（配方镜像没有 Ray）和尝试 2（配方镜像只编译了 `gfx950` → 融合 qk-norm/rope/kv-insert 内核段错误）记在「第 2 轮」 |
| 服务速度探针（TTFT、tok/s，并发 1 和 8） | 通过（第 2 轮）：Inkling TP8×PP2、Nemotron TP8+EP 和 Muse TP8×PP2 各跑 1 次 `09_perf_probe.py`（一条短提示、max_tokens 256、每档 3 轮），数字见「第 2 轮」；这是量级探针，不是 benchmark |
| 吞吐分布、长提示、业务任务质量、长上下文、生产稳定性 | 三个模型均 NOT_RUN |
| NVFP4 版本在 MI300X 上的加载路径 | NOT_RUN；发布方说法只覆盖 Blackwell/Hopper，vLLM ROCm 对 ModelOpt NVFP4 是拒绝还是反量化未核实 |
| FP8 版本在任何 GPU 上 | NOT_RUN；不在本轮实测范围内 |
| 独立中文与双语语义审查 | 本修订通过：五处措辞、条件和来源链接问题已修复并独立复验；不代表视觉或推理验收 |
| GitHub 发布与线上页面 | 以本专题的公开提交及检查结果为准；本地预览不替代线上验收 |

未执行的检查不能标为通过。公开来源、原理分析与可执行工具分别有自己的验收边界。

独立文本复核覆盖四份双语文档及组件表，第二轮逐项复验修正后的五个问题。`AI_NATIVE_CHINESE_AUDIT=PASS`，`AI_BILINGUAL_SEMANTIC_AUDIT=PASS`。它不执行模型、不复跑性能测试，也不代替实际组件精度验证。来源单元格对应与本地链接的确定性检查另行通过。

## 重建文档预览

使用 PowerShell 7 的内置 `ConvertFrom-Markdown`，无需安装 npm 包；浏览器渲染 Mermaid 和 KaTeX 时需要访问脚本中固定版本的公共 CDN。从本专题目录执行：

```powershell
./tools/preview.ps1 -OutputDirectory "$env:TEMP/large-moe-guide-preview"
```

同一个入口生成四页并记录源文件与 HTML 的 SHA-256。三个模型各用四列表，保留全部组件与版本，要求表格自身无需横向滚动。测试应分别比较每张表的 `scrollWidth` 与 `clientWidth`，并查看实际截图。官方图的来源、尺寸与 SHA-256 见 [visual-evidence.json](data/visual-evidence.json)。预览不替代 GitHub 线上页面或独立双语语义复审。

## 逐张量 dtype 普查

```bash
python3 tools/tensor_census.py <snapshot_dir> <out.json>   # 在已下载 checkpoint 的机器上运行；只读文件头
node tools/census.mjs --table                               # 本地汇总 data/tensor-census/*.json 并与 API 元数据交叉核对
```

`tensor_census.py` 读取每个 `.safetensors` 文件的 8 字节头长度和 JSON 头，得到每个张量的名字、dtype、shape 和字节范围，不读取权重数据、不需要 GPU。按名字正则把张量归入组件（词嵌入、注意力、路由器、路由专家、共享专家、潜空间投影、Mamba 投影、Mamba 状态参数、短卷积、归一化与偏置、编码器、稠密 MLP、MTP、输出层）；未匹配的名字模式会被记录在 `unmatched_patterns_top`，测试要求它为空。

| 模型与 revision | 文件 | 张量 | 文件头字节合计 | 与 API 元数据算出的字节 |
|---|---:|---:|---:|---|
| Nemotron 3 Ultra BF16 `77df655d` | 225 | 51,023 | 1,121,049,257,984 | 一致 |
| Inkling BF16 `828496ee` | 109 | 1,552 | 1,904,755,280,148 | 一致 |

普查于 2026-11-02 在 Azure `Standard_ND96isr_MI300X_v5` 上对完整下载的快照执行，结果保存在 [data/tensor-census/](data/tensor-census/)。`node --test tests/census.test.mjs` 检查两份普查与 `model-evidence.json` 的字节一致性、关键组件的 dtype 和张量数（如 Nemotron 路由器 48 个 F32 `e_score_correction_bias`、Inkling 128 个融合专家张量和 128 个 F32 标量），以及对未分类组件的拒绝。

## MI300X 实测

<a id="mi300x-实测"></a>

**问题。** 三个模型的发布方都没有给出 MI300X 上的 BF16 部署记录；本项目在 2026-11-02 用两台 Azure `Standard_ND96isr_MI300X_v5`（每台 8 × MI300X 192 GB，Spot）实际加载，回答"BF16 原厂权重能否在 MI300X 上用 vLLM ROCm 跑起来、实际选中了什么内核、缓存是什么精度、显存用了多少"。

**环境。** 宿主机 Ubuntu 24.04.5、内核 `6.8.0-1067-azure`、ROCm 6.4.4（amdgpu 6.12.12）；容器 `rocm/vllm:rocm10.1.0_ubuntu24.04_py3.14-pytorch_2.13.0_vllm-0.29.0`（镜像 ID `e0ea9a10…`，vLLM `0.29.1.dev0+g98dff2a81`，torch `2.13.0+rocm10.1.0`，Triton 3.8.0，aiter 已装）。权重放在 8 × 3.5 TB 本地 NVMe 组成的 RAID0 上。容器参数 `--network host --ipc host --device /dev/kfd --device /dev/dri --ulimit memlock=-1:-1 --shm-size 64g`。

### Nemotron 3 Ultra BF16，单机 8 卡

启动命令（与模型卡的 vLLM 示例对齐，去掉 CUDA 专有项）：

```bash
vllm serve nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16 --revision 77df655d5e9f8362164ed14dd8b48f8bce657498 \
  --trust-remote-code --dtype bfloat16 --tensor-parallel-size 8 --enable-expert-parallel \
  --max-model-len 65536 --gpu-memory-utilization 0.90 --max-num-seqs 16 --max-num-batched-tokens 16384 \
  --enable-chunked-prefill --enable-prefix-caching --mamba-ssm-cache-dtype float16 --reasoning-parser nemotron_v3
# 环境：VLLM_ROCM_USE_AITER=1 VLLM_ROCM_USE_AITER_MOE=0
```

三次尝试，每次只改一个变量：

| 尝试 | 改动 | 结果 | 日志中的根因 |
|---|---|---|---|
| 1 | 默认（AITER MoE 开） | 构建模型时失败 | `ValueError: Unquantized MoE backend ROCm AITER does not support the deployment configuration since kernel does not support no act_and_mul MLP layer`——LatentMoE 专家是 `relu2` 非门控 MLP，AITER 融合 MoE 内核要求 act_and_mul 结构 |
| 2 | `VLLM_ROCM_USE_AITER_MOE=0` | 权重加载完成（136.51 GiB/卡，443 s），Mamba2 内核预热时失败 | `mamba_ssm.py selective_state_update … PHILOX_ROUNDS` → `LLD failed to link hsaco … ld.lld: error: target emulation unknown`；同镜像内最小 Triton 内核可编译运行，故为随机舍入 SSU 内核特有 |
| 3 | 再去掉 `--enable-mamba-cache-stochastic-rounding` | **就绪并生成** | — |

尝试 3 的决定性日志行（rank 0）：

```text
Using TRITON Unquantized MoE backend out of potential backends: ['TRITON', 'BATCHED_TRITON']
Using TritonExperts MoE backend
Found incompatible backend(s) [TURBOQUANT] with AttentionType.DECODER. Overriding with ROCM_ATTN out of potential backends: ['ROCM_ATTN', 'ROCM_AITER_FA', 'ROCM_AITER_UNIFIED_ATTN', 'TRITON_ATTN']
Using ['AITER_CUSTOM', 'PYNCCL'] all-reduce backends … for group 'tp:0'   /   Using ['PYNCCL'] … for group 'ep:0'
Using triton Mamba SSU backend
Using SSM config from …/selective_state_update/headdim=64,dstate=128,device_name=AMD_Instinct_MI300X,cache_dtype=float16.json
Setting attention block size to 1056 tokens to ensure that attention page size is >= mamba page size
Model loading took 136.51 GiB memory and 111.97 seconds          # 第二次加载，页缓存命中；首次 443 s
Available KV cache memory: 23.07 GiB
GPU KV cache size: 3,490,022 tokens, Maximum concurrency for 65,536 tokens per request: 53.25x
Free memory on device (186.12/191.45 GiB) … Actual usage is 146.67 GiB for consumed memory (weights + non-torch), 2.57 GiB for peak activation
init engine (profile, create kv cache, warmup model) took 119.58 s (compilation: 22.31 s)
```

两条 smoke 请求（`temperature=0`，原文见 `evidence/nemotron_bf16_8xMI300X/02_smoke_request.json`、`03_smoke2_request.json`）：

| 请求 | 输入 | 输出 token（其中推理） | 墙钟 | 内容判断 |
|---|---|---:|---:|---|
| 中文，"用一句话说明 BF16 和 FP16 的区别"，`max_tokens=200` | 31 token | 94（21） | 1.61 s | 正确：BF16 7 位尾数 + 8 位指数，FP16 5 位指数 + 10 位尾数 |
| 英文，Mamba-2 与 softmax attention 三点区别，`max_tokens=256` | 42 token | 209（29） | 5.42 s | 连贯：线性 vs 二次复杂度、固定状态 vs 完整 KV、并行性 |

这只证明"能加载、能生成、内核和缓存精度如上"；不是吞吐、质量或长上下文验收。证据：[data/mi300x-run/nemotron_bf16_8xMI300X/](data/mi300x-run/nemotron_bf16_8xMI300X/)（请求、响应、`rocm-smi` JSON、服务日志关键行、`00_meta.txt`）；完整容器日志和三次尝试日志因体积保存在作者的私有证据目录，其 SHA-256 列在同目录的 `SHA256SUMS.private.txt`。本节引用的每个数字由 `tools/mi300x_evidence.py summarize` 从这些原始文件重算并由 `tests/mi300x.test.mjs` 核对。

### Inkling BF16，双机 16 卡

两台机器各放一份完整快照（1,904,787,107,666 字节），容器加 `--device /dev/infiniband`，用 Ray 跨机。RCCL 环境：`NCCL_IB_HCA=^mlx5_8:1,mlx5_an0:1 NCCL_NET_GDR_LEVEL=0 NCCL_IB_PCI_RELAXED_ORDERING=1 GLOO_SOCKET_IFNAME=eth0`。启动命令（尝试 5 的布局）：

```bash
vllm serve thinkingmachines/Inkling --revision 828496eeae4c243ff1a22f7f28ff83694f2f7bc9 \
  --trust-remote-code --dtype bfloat16 --tokenizer-mode inkling --reasoning-parser inkling \
  --tensor-parallel-size 8 --data-parallel-size 2 --data-parallel-size-local 1 --data-parallel-backend ray --enable-expert-parallel \
  --max-model-len 65536 --gpu-memory-utilization 0.90 --max-num-seqs 16 --max-num-batched-tokens 16384 \
  --enable-chunked-prefill --distributed-timeout-seconds 3600 --kernel-config '{"enable_jit_warmup": false}'
# 环境：VLLM_ROCM_USE_AITER=1（AITER 融合 MoE 对 Inkling 的门控 SwiGLU 专家可用）
```

六次尝试，每次只改一个变量：

| 尝试 | 布局与改动 | 结果 | 日志中的根因 |
|---|---|---|---|
| 1 | TP16，`NCCL_IB_HCA` 白名单，默认 GPU Direct RDMA | RCCL 初始化挂起 8 分钟以上 | `Peermem not available, falling back to GPU Direct RDMA (DMAbuf)` 后再无 `Init COMPLETE`。同镜像 `torchrun` 16 进程 all_reduce 探针：同环境超时；加 `NCCL_NET_GDR_LEVEL=0` 后通过（64 MiB all_reduce 2.4 ms，busbw 52.4 GB/s） |
| 2 | TP16，`NCCL_NET_GDR_LEVEL=0` | 16 个 rank 进入模型构建后被模型自身拒绝 | `Error: sconv SWA cache supports tp_size <= num_kv_heads (8), got 16`——滑窗短卷积缓存的切分上限是 8，与模型卡"节点内 TP、节点间 DP、EP 跨全部 rank"的多机配方一致 |
| 3 | TP8 × DP2 + EP16（Ray） | 启动即失败 | `Not enough resources to allocate 2 DP ranks on DP master node <node0-private-ip>, possible to fit 1 DP ranks`——Ray DP 默认把全部 DP rank 放在主节点 |
| 4 | 加 `--data-parallel-size-local 1` | 16 个 rank 权重加载完成、AITER MoE 选中、HIP graph 捕获完成，预热时失败 | `kernel_warmup → fa4_cutedsl_warmup → _warm_inkling_fa4_rel_attention` 导入 CUDA 专有 `vllm.vllm_flash_attn` → `ImportError: … requires the CUDA flash attention extensions (_vllm_fa2_C or _vllm_fa3_C). On ROCm, use upstream flash_attn.` 预热门只看配置类不看平台，而模型本身有 AMD 注意力实现（`vllm/models/inkling/amd/attention.py`） |
| 5 | 加 `--kernel-config '{"enable_jit_warmup": false}'` | **引擎就绪**（`/health` 200）；第 1 条请求（DP rank 0）4.76 s 返回；第 2 条请求被调度到 DP rank 1（另一台机器）后**无输出**，5 分钟后引擎崩溃 | DP1 全部 worker 连续 5 次 `No available shared memory broadcast block found in 60 seconds` → `TimeoutError: RPC call to sample_tokens timed out.`（`multiproc_executor.py:435`）→ `EngineCore encountered a fatal error`；DP0 随后 `gloo … Connection closed by peer [<node1-private-ip>]`。挂起期间 16 卡 GPU 利用率均为 0 %，无 `hipcc`/`clang` 进程，Triton 缓存无新条目——不是 JIT 编译，是跨机 DP/EP 集合通信没有完成 |
| 6 | TP8 × PP2（`--pipeline-parallel-size 2 --distributed-executor-backend ray`，每台机器一个流水级，不用 DP/EP） | **就绪并生成**：三条请求全部返回，`max_tokens=1024` 的一条正常结束（`finish_reason=stop`）并给出正确最终答案 | — （Ray worker 首次加入时撞上 head 的 GCS 启动竞态 `GCS returned an authentication error`，重启 worker 容器后正常加入） |

尝试 5 的决定性日志行：

```text
Model loading took 114.88 GiB memory and 55.747657 seconds        # DP1；DP0 为 66.9 s
[aiter] [fused_moe] using 2stage default for ('gfx942', 304, 8, 6144, 3072, 16, 5, <ActivationType.Silu: 0>, 'torch.bfloat16', 'torch.bfloat16', 'torch.bfloat16', 'QuantType.No', True, False)
Available KV cache memory: 50.25 GiB
GPU KV cache size: 317,040 tokens, Maximum concurrency for 65,536 tokens per request: 4.84x   # 每个 DP rank
Free memory on device (186.5/191.45 GiB) on startup … Actual usage is 117.4 GiB for consumed memory
init engine (profile, create kv cache, warmup model) took 76.77 s
WARNING [jit_monitor.py:141] Triton kernel JIT compilation during inference: _silu_and_mul_triton_kernel   # 第 1 条请求期间
INFO [shm_broadcast.py:801] No available shared memory broadcast block found in 60 seconds.               # 第 2 条请求期间，DP1，连续 5 次
TimeoutError: RPC call to sample_tokens timed out.
```

尝试 5 的 smoke 请求（`temperature=0`，原文见 `evidence/inkling_bf16_16xMI300X/02_smoke_request.json`、`03_smoke2_request.json`）：

| 请求 | 输入 | 输出 token（其中推理） | 墙钟 | 内容判断 |
|---|---|---:|---:|---|
| 中文，"用一句话说明 BF16 和 FP16 的区别"，`max_tokens=200` | 27 token | 200（199），`finish_reason=length` | 4.76 s | 推理段正确展开（BF16 8 位指数 / 7 位尾数，FP16 5 位指数 / 10 位尾数，范围 vs 精度），200 token 内未结束推理，无最终答案段 |
| 英文，Mamba-2 与 softmax attention 三点区别，`max_tokens=256` | 39 token | 0 | 600 s 超时 | 无输出：被调度到远端 DP rank，见上表尝试 5 |

尝试 6（TP8 × PP2）的决定性日志行：

```text
Using ['AITER_CUSTOM', 'PYNCCL'] all-reduce backends … for group 'tp:0'   /   Using ['PYNCCL'] … for group 'pp:0'
Using ROCm AITER Unquantized MoE backend out of potential backends: ['ROCm AITER', 'TRITON', 'BATCHED_TRITON']
Using MoEPrepareAndFinalizeNoDPEPModular
Using AiterExperts MoE backend
[aiter] [fused_moe] using 2stage default for ('gfx942', 304, 64, 6144, 384, 256, 6, <ActivationType.Silu: 0>, 'torch.bfloat16', 'torch.bfloat16', 'torch.bfloat16', 'QuantType.No', True, False)
Model loading took 109.52 GiB memory and 176.401031 seconds        # PP0（节点 0，前半层）；PP1 为 116.12 GiB、80.8 s
Available KV cache memory: 57.39 GiB                                # PP0；PP1 为 51.02 GiB
GPU KV cache size: 398,239 tokens, Maximum concurrency for 65,536 tokens per request: 6.08x
Free memory on device (185.74/191.45 GiB) on startup … Actual usage is 112.54 GiB for consumed memory (weights + non-torch)   # PP0；PP1 为 118.9 GiB
init engine (profile, create kv cache, warmup model) took 56.47 s
```

尝试 6 的 smoke 请求（`temperature=0`，原文见 `evidence/inkling_bf16_16xMI300X_pp2/02_smoke_request.json`、`03_smoke2_request.json`、`07_smoke3_request.json`）：

| 请求 | 输入 | 输出 token（其中推理） | 墙钟 | 内容判断 |
|---|---|---:|---:|---|
| 中文，"用一句话说明 BF16 和 FP16 的区别"，`max_tokens=200` | 27 token | 200（199），`finish_reason=length` | 2.97 s | 推理段正确展开，200 token 内未结束推理 |
| 英文，Mamba-2 与 softmax attention 三点区别，`max_tokens=256` | 39 token | 256（255），`finish_reason=length` | 4.06 s | 推理段正确：O(N²) vs O(N)、pairwise QK + softmax vs 状态更新、Mamba-2 的 SSD；256 token 内未结束推理 |
| 同第一条，`max_tokens=1024` | 27 token | 441（362），`finish_reason=stop` | 6.52 s | **正确**："BF16 保留了与 FP32 相同的 8 位指数（动态范围大、不易溢出），但尾数仅 7 位（精度较低）；而 FP16 有 10 位尾数（精度更高），却只有 5 位指数（动态范围小、易溢出或下溢）。" |

Inkling 是推理模型，推理段通常超过 200 token；前两条请求的 `max_tokens` 沿用 Nemotron 的设置，所以只拿到推理段。第三条把上限放到 1024 后得到完整回答。

每卡权重：PP 布局下 PP0 109.52 GiB、PP1 116.12 GiB（两个流水级各持一半层，每层内 TP8，专家不切 EP）；DP+EP 布局下每卡 114.88 GiB。[主文档的预算表](README_CN.md#资源估算)按 EP16+TP8 算出 122 GB（专家 1855.4 GB ÷ 16 + 非专家 49.3 GB ÷ 8），差额来自 vLLM 把部分非专家张量按 EP 组切分；量级一致。

这组结果证明：BF16 原厂权重能在 16 × MI300X 上装载、由 AITER 融合 MoE 内核服务并给出正确回答（TP8 × PP2 布局）；跨机 DP/EP 布局在本镜像上没有完成第二条请求，是本项目记录的现状而非模型或硬件的结论。证据：[data/mi300x-run/inkling_bf16_16xMI300X_pp2/](data/mi300x-run/inkling_bf16_16xMI300X_pp2/)（尝试 6：三条请求与响应、`rocm-smi` JSON、服务日志关键行）、[data/mi300x-run/inkling_bf16_16xMI300X/](data/mi300x-run/inkling_bf16_16xMI300X/)（尝试 5：第一条响应、超时的第二条请求、关键行）。完整容器日志、两台机器的 Ray worker 日志、尝试 1–4 日志和 RCCL 探针日志在作者的私有证据目录，SHA-256 列在各目录的 `SHA256SUMS.private.txt`；主机名、私网 IP 和登录用户在公开投影中换成了角色标签。运行脚本见 [scripts/mi300x/](scripts/mi300x/)。

### 第 2 轮（2026-11-02 上午）：复跑 + 服务速度探针 + Muse

<a id="第-2-轮"></a>

两台 VM 于 2026-11-02 03:05 释放后在 10:06 重新启动（本地 NVMe 为临时盘，权重与镜像全部重下：三个模型 4.67 TB 在两节点上 17 分钟内下完，字节数与第 1 轮完全一致）。第 2 轮的目的：对第 1 轮已通过的布局各跑一次**服务速度探针**，并在 Meta 批准权重闸门后首次尝试 Muse。

**探针方法**（[`scripts/mi300x/09_perf_probe.py`](scripts/mi300x/09_perf_probe.py)，纯标准库，在节点 0 宿主机上向 `127.0.0.1:8000` 发请求）：固定英文提示词 "Explain in about 150 words why mixture-of-experts models keep the router in higher precision than the experts."（37 token），`max_tokens 256`，`temperature 0`，`stream: true` 且 `stream_options.include_usage: true`；先发 1 条预热请求，再按并发 1、并发 8 各跑 3 轮，每轮用线程同时发出全部请求。指标定义：TTFT = 发出到第一个带 `content` 或 `reasoning_content` 的分片；单请求解码速度 = (completion_tokens − 1) ÷ (末分片时刻 − 首分片时刻)；总吞吐 = 一轮所有流的 completion_tokens 之和 ÷ (该轮末次结束 − 首次发出)。`completion_tokens` 来自服务端最后一个带 `usage` 的分片。探针前后各记一次 `rocm-smi --showmeminfo vram`。这是量级探针：一条短提示、两个并发档、每档 3 轮；它不是 benchmark，也不替代业务负载测试。

| 模型 · 布局（第 2 轮） | 就绪 | smoke（与第 1 轮同样三条） | 并发 1（n=3）：TTFT 中位 / 单请求解码 / 总吞吐 | 并发 8（n=24）：TTFT 中位 / 单请求解码 / 总吞吐 | 结束原因 |
|---|---|---|---|---|---|
| Inkling BF16 · TP8×PP2 · 0.29 镜像 | 03:46:25Z（head 03:39:08Z 启动；冷加载 249.6 / 243.7 s；`init engine` 58.22 s；KV 57.39 / 51.02 GiB、398,239 token，与第 1 轮完全一致） | 3/3 返回：3.01 s / 4.10 s / 5.57 s；`max_tokens=1024` 那条 377 token（推理 302）`finish_reason=stop`，答案正确 | **0.045 s** / **68.9 tok/s** / 68.3 tok/s | **0.097 s**（最大 0.102） / **42.5 tok/s** / **335.8 tok/s** | 全部 27 条 `length`（推理段未在 256 token 内结束） |
| Nemotron 3 Ultra BF16 · TP8+EP · 0.29 镜像 | 04:05:02Z（启动 03:49:28Z；冷加载 744.5 s，比第 1 轮的 443 s 慢——本轮三个模型同时下载后页缓存已被 Inkling 占满；`init engine` 117.78 s；KV 23.07 GiB、3,490,022 token，与第 1 轮完全一致） | 3/3 `stop`：1.61 s / 5.39 s / 1.60 s；中文答案与第 1 轮逐字一致（94 token，推理 21） | **0.170 s** / **60.7 tok/s** / 58.6 tok/s | **0.358 s**（最大 1.17） / **42.0 tok/s** / **317.4 tok/s** | 全部 27 条 `length`（256 token 上限先到；答案段已开始） |
| Muse Spark Open BF16 · TP8×PP2 · v0.33.0+Ray 镜像（尝试 3） | 04:22:41Z（head 04:18:05Z 启动；16 个 rank 全部 `Model loading took 99.1 GiB memory`，流水级 0 用 95.0 s、流水级 1 用 39.6–43.1 s；`init engine` 64.22 s；`Available KV cache memory` 72.05 / 71.98 GiB，`GPU KV cache size: 8,130,184 tokens`） | 3/3 返回：6.69 s / 4.33 s / 12.41 s，全部 `finish_reason=length` 停在推理段内（200 / 256 / 1024 token）；追加第 4 条——同一中文提示、`max_tokens=4096`——以 `stop` 结束，1,354 个 completion token（推理 1,289），16.4 s，一句话答案正确（BF16 是 8 位指数 + 7 位尾数，范围与 FP32 一样但精度低；FP16 是 5 + 10，精度更高但容易溢出） | **0.205 s** / **84.6 tok/s** / 79.5 tok/s | **0.506 s**（最大 0.518） / **47.6 tok/s** / **348.6 tok/s** | 全部 27 条 `length`（推理段未在 256 token 内结束） |

Inkling 第 2 轮的加载和 KV 数字与第 1 轮尝试 6 逐字一致（`Model loading took 109.52 / 116.12 GiB`、`Available KV cache memory 57.39 / 51.02 GiB`、`GPU KV cache size 398,239 tokens`），说明这套布局的显存占用是确定的；smoke 墙钟时间 3.01 / 4.10 / 5.57 s 与第 1 轮的 2.97 / 4.06 / 6.52 s 同量级。探针期间 `rocm-smi` 显示节点 0 每卡 170.6–171.2 GiB、节点 1 177.2–177.9 GiB 已用（权重 + KV 预分配 + 运行时），探针前后数值不变。证据：[data/mi300x-run/inkling_bf16_16xMI300X_pp2_run2/](data/mi300x-run/inkling_bf16_16xMI300X_pp2_run2/)（含 `08_perf.json` 全部 28 条请求的逐条记录）。

**Muse Spark Open BF16 的三次尝试**（权重闸门于 2026-11-02 上午批准；`meta-models/Muse-Spark-Open-816B-A42B` revision `0fb02478…`，1,644,365,682,665 字节，两节点各一份；配置：62 层、hidden 8192、256 专家 top-8、128 Q 头 / 16 KV 头 / head_dim 64、词表 202,048；1.64 TB ÷ 8 = 205 GB 单机装不下，所以沿用 Inkling 通过的双机 TP8 × PP2）：

| 尝试 | 镜像 | 结果 | 日志中的根因 |
|---|---|---|---|
| 1 | `vllm/vllm-openai-rocm:muse-spark-open`（vLLM 配方镜像，vLLM 0.29.1rc1，2026-10-15 推送） | 1 秒内失败 | worker：`/bin/bash: line 1: ray: command not found`；head：`pydantic ValidationError for ParallelConfig: Failed to import Ray: No module named 'ray'`——镜像没装 Ray；vLLM 多机执行器要求 Ray ≥ 2.43.0（`vllm/v1/executor/ray_executor.py`）。配方是 MI355X（288 GB）单机 TP8，从不需要多机 |
| 2 | 同上 + `ray[default]==2.55.1`（[`Dockerfile.muse-ray`](scripts/mi300x/Dockerfile.muse-ray)，`BASE=muse-spark-open`） | Ray 集群 16 卡组成，**16 个 rank 全部加载权重**（`Model loading took 104.84 GiB memory and 189.7 seconds`，`Materialized residual-path constants for 62 gated residual connections`），然后在 `determine_available_memory` 阶段**全部段错误**，`RayWorkerProc rank=[15] died unexpectedly` → `Engine core initialization failed` | 每个 worker 的 `.err` 都是 `!!!!!!! Segfault encountered !!!!!!!` 于 `csrc/libtorch_stable/fused_muse_spark_qknorm_rope_kv_insert_kernel.hip:647/821`（`launchFusedMuseSparkTyped<BFloat16,…>`）；节点 1 `dmesg`：`amdgpu: Freeing queue vital buffer … queue evicted` ×7。镜像内 `PYTORCH_ROCM_ARCH=gfx950`，`llvm-objdump --offloading` 显示 `_C_stable_libtorch.abi3.so`（含该内核符号）28 个代码对象全是 `gfx950`，`_C.abi3.so`、`_rocm_C.abi3.so` 同样只有 `gfx950`；宿主机 `rocminfo` 为 `gfx942`。**没有 MI300X 的代码对象**，HIP 启动该内核即越界。融合路径在 `models/muse_spark/amd/model.py:535` 对 ROCM_AITER_FA + BF16 + head_dim 64 无条件启用，无环境变量可关 |
| 3 | `vllm/vllm-openai-rocm:v0.33.0`（2026-11-02 02:45 UTC 发布，vLLM 0.33.0，torch 2.13.0+rocm10.0.0，`PYTORCH_ROCM_ARCH=gfx90a;gfx942;gfx950;gfx11xx;gfx12xx`，同一个 `vllm/models/muse_spark/` 代码树，`_C_stable_libtorch.abi3.so` 每个架构 28 个代码对象且含 `fused_muse_spark_qknorm_rope_kv_insert`）+ `ray[default]==2.55.1` | **通过**：Ray 集群 33 s 组成，权重加载，显存探测穿过同一个融合内核无错，`/health` 200 于 04:22:41Z，四条请求返回，探针跑完（见上表） | 日志：`Using MuseSparkTritonExperts MoE backend`、`Using ROCM_AITER_FA backend (selected via --attention-backend)`、all-reduce `tp:0` 为 `['AITER_CUSTOM', 'PYNCCL']`、`pp:0` 为 `['PYNCCL']`、`Enabled custom fusions: norm_quant, act_quant, allreduce_rms, mla_dual_rms_norm, qk_norm_rope_kvcache`；容器内 `vllm 0.33.0+rocm100`、`ray 2.55.1`。与尝试 2 唯一的差别是基础镜像，所以尝试 2 的失败归因于缺 `gfx942` 代码对象，不是模型或布局 |

尝试 2 的证据：节点 0 `attempt2_head_full.log`、`attempt2_image_code_objects.txt`（`llvm-objdump` 输出）、`host_gfx_arch.txt`；节点 1 8 个 Ray `worker-*.err`（段错误栈）、`raylet.err`、`dmesg_amdgpu_tail.txt`——在作者的私有证据目录，SHA-256 列于 `SHA256SUMS.private.txt`。镜像探查与段错误栈证明的是**这个镜像没为 gfx942 编译**，不是模型或 MI300X 的结论；v0.33.0 的代码对象清单说明上游已经在编译 gfx942，所以尝试 3 用它。尝试 3 的证据：[data/mi300x-run/muse_bf16_16xMI300X_pp2_run2/](data/mi300x-run/muse_bf16_16xMI300X_pp2_run2/)（服务器关键日志行、四对请求/响应、`rocm-smi` 快照、含全部 28 条请求逐条记录的 `08_perf.json`）。探针期间 `rocm-smi` 显示节点 0 每卡 180.0–180.9 GiB、节点 1 180.3–181.4 GiB 已用（权重 99.1 GiB + KV 预分配约 72 GiB + 运行时）；Muse 的 KV 池是三个模型中最大的，因为 16 个 KV 头 × head_dim 64 使它每 token 的 KV 占用最小（同样 32,768 `max_model_len` 下 813 万 token，Inkling 39.8 万、Nemotron 349 万）。

## 后续 GPU 验证

MI300X 的 BF16 加载、smoke 和服务速度探针在三个模型上都已完成（Nemotron 3 Ultra 和 Inkling 用 0.29.0 镜像，Muse Spark Open 用 v0.33.0 镜像）。未执行的仍是：① Muse 的多模态路径（用了 `--language-model-only`，视觉编码器没有加载），以及 Inkling、Nemotron 在同一个 v0.33.0 镜像上的复跑——受控的跨模型对比需要这一步；② 三个模型的 NVFP4 版本在 MI300X 上的加载路径——MI300X 没有 FP4 矩阵算力，发布方的说法只覆盖 Blackwell 和 Hopper，vLLM ROCm 对 ModelOpt NVFP4 checkpoint 是拒绝还是反量化加载，尚未核实；③ 吞吐分布、长提示、业务任务质量、长上下文稳定性，对三个模型均未执行——第 2 轮的探针只给一条短提示在两个并发档的量级。任何后续实测都在本专题中补充，不另建平行结论页。