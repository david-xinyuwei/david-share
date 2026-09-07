# Qwen3.8-27B：MTP 与 DFlash 2 实测

同样起草 7 个候选 token，DFlash 2 比模型自带的 MTP 快多少？更快输出的回答，还能答对吗？这次在单张 H100 NVL 上，用同一批代码题和数学题，同时测速度、得分和截断情况。

在三个并发档位、三个随机种子（seed）的九组配对中，DFlash 2 的输出吞吐均高于 MTP7。得分总体接近，但并发 4 的第三次运行里，DFlash 2 的代码题答对 **29/32**，MTP7 为 **31/32**，而且 DFlash 2 做完这一组题更慢。**吞吐优势已经测到，准确率不下降尚未得到证明。**

这是作者在 vLLM 上的部署实测，不是 DFlash 论文的完整复现。正式结果来自同一批 64 题的重复测试；完整题集阶段未执行，详见[测试覆盖](#测试覆盖与未执行项)。

> 作者：魏新宇（Xinyu Wei）

[English](README.md) | [中文](README-CN.md) | [推测解码总览](../../README-CN.md)

[结果](#吞吐与答案质量) · [方法](#测试方法) · [How to Run](#how-to-run) · [覆盖范围](#测试覆盖与未执行项) · [离线复算](#离线复算)

实验日期：2026-09-06。运行标识：`qwen38-quality-20260906`。

---

<a id="s-阶段结果"></a>

## 吞吐与答案质量

使用 32 道 HumanEval+ 代码题和 32 道 MATH-500 数学题，三条路线在并发 1、4、8 下各跑三次，共 27 组。每组都是同一批题，**每类 32 题重复三次，不是 96 道独立题**。

基线不开推测解码；MTP7 和 DFlash 2-7 都起草 7 个候选 token。下表的吞吐和整组耗时分别取三次运行的中位数。得分和截断列的三个数，依次对应 seed **20260906、20260907、20260908**；每个得分的分母都是 32。

![三种路线在并发 1、4、8 下的输出吞吐](images/throughput.png)

*图 1：作者实测。柱形表示三次运行的中位数，误差线表示最小值和最大值，不是置信区间；同一批 64 题，吞吐包含 thinking token。来源：[逐组记录](data/groups.json)。*

<!-- BEGIN RESULT_TABLE -->
### 吞吐与整组耗时

| 并发 | 路线 | 吞吐（tok/s） | 整组耗时（秒） |
| --- | --- | --- | --- |
| 1 | 基线 | 53.40 | 3458.61 |
| 1 | MTP7 | 113.34 | 1591.09 |
| 1 | DFlash 2-7 | 150.51 | 1149.41 |
| 4 | 基线 | 190.08 | 1037.22 |
| 4 | MTP7 | 382.85 | 470.35 |
| 4 | DFlash 2-7 | 451.74 | 377.79 |
| 8 | 基线 | 287.72 | 577.44 |
| 8 | MTP7 | 565.24 | 308.08 |
| 8 | DFlash 2-7 | 741.07 | 249.68 |

### 代码与数学得分

| 并发 | 路线 | 代码答对数 /32 | 数学答对数 /32 |
| --- | --- | --- | --- |
| 1 | 基线 | 29、31、30 | 30、30、30 |
| 1 | MTP7 | 30、31、31 | 30、28、31 |
| 1 | DFlash 2-7 | 30、31、30 | 29、32、30 |
| 4 | 基线 | 31、31、31 | 30、31、30 |
| 4 | MTP7 | 30、30、31 | 29、29、29 |
| 4 | DFlash 2-7 | 31、31、29 | 31、31、30 |
| 8 | 基线 | 31、31、31 | 30、29、30 |
| 8 | MTP7 | 31、31、30 | 29、29、30 |
| 8 | DFlash 2-7 | 31、31、30 | 30、31、30 |

本次所有被评分器判对的回答都正常结束，因此“答对数”和“正常结束且答对数”相同，不重复列两遍。两项原始字段均保留在数据文件中。

<details>
<summary>查看三次运行的截断情况</summary>

| 并发 | 路线 | 代码截断数 | 数学截断数 |
| --- | --- | --- | --- |
| 1 | 基线 | 1、1、2 | 2、1、2 |
| 1 | MTP7 | 2、1、1 | 1、2、1 |
| 1 | DFlash 2-7 | 2、1、2 | 2、0、1 |
| 4 | 基线 | 1、1、1 | 1、0、2 |
| 4 | MTP7 | 2、2、1 | 2、1、2 |
| 4 | DFlash 2-7 | 1、1、3 | 1、1、1 |
| 8 | 基线 | 1、1、1 | 2、2、2 |
| 8 | MTP7 | 1、1、2 | 2、1、1 |
| 8 | DFlash 2-7 | 1、1、2 | 2、1、2 |

达到输出上限的回答仍保留在每次 32 题的分母中。

</details>
<!-- END RESULT_TABLE -->

以上各表由[已保存的汇总](data/summary.json)生成。吞吐按“服务端确认的输出 token 总数 ÷ 整组耗时”计算，**包含 thinking、错答和截断回答**。计时从首个测量请求派发，到最后一个请求的终止事件接收完成；不含模型下载、启动、预热和评分。这不是 GPU 纯解码吞吐。

### 为什么还要看正确答案的交付速度

<!-- BEGIN COUNTEREXAMPLE -->
并发 4 的第三次运行（seed 20260908）出现了一个例外：**DFlash 2 输出 token 更快，但做完同一组题反而更慢。** 下表只统计正常结束且答对的回答，耗时取自这一次运行，不是三次运行的中位数。

| 路线 | 整组耗时（秒） | 代码答对数 /32 | 数学答对数 /32 |
| --- | --- | --- | --- |
| MTP7 | 450.87 | 31 | 29 |
| DFlash 2-7 | 484.07 | 29 | 30 |

DFlash 2 有 3 份代码回答达到输出上限。用“正常结束且答对数 ÷ 整组耗时”衡量正确答案的交付速度，DFlash 2 与 MTP7 的比值为：代码 **0.8713**，数学 **0.9635**。两者都小于 1。这说明 token 吞吐优势不能直接当成正确答案的交付优势；这次差异的原因尚未定位。
<!-- END COUNTEREXAMPLE -->

## 客户端延迟

TTFT 是等待首个输出 token 的时间；TPOT 是首个 token 之后，平均每个输出 token 的交付间隔；回答耗时是从请求派发到接收终止事件的时间。三项都从客户端观察，数值越低越好。

每个配置先分别计算三次运行的 P50，再取三个 P50 的中位数，**不是把所有响应合并后求一次分位数**。缺失或无定义的值不补零。

<!-- BEGIN LATENCY_TABLE -->
### 首 token 等待（TTFT，ms）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 82.727 | 75.127 | 80.286 |
| 4 | 104.008 | 110.259 | 115.994 |
| 8 | 106.598 | 124.699 | 124.781 |

### token 交付间隔（TPOT，ms/token）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 18.567 | 8.011 | 5.875 |
| 4 | 20.104 | 8.549 | 6.739 |
| 8 | 20.845 | 10.041 | 7.892 |

### 单次回答耗时（秒）

| 并发 | 基线 | MTP7 | DFlash 2-7 |
| --- | --- | --- | --- |
| 1 | 16.359 | 6.236 | 6.185 |
| 4 | 19.035 | 8.661 | 5.237 |
| 8 | 18.457 | 9.915 | 7.742 |

每个配置、每项指标均有 192 份有效响应记录，缺失 0 份。这是重复运行的观测数，不是独立题目数。
<!-- END LATENCY_TABLE -->

<details>
<summary>查看延迟的精确定义</summary>

TTFT 从派发请求计时，到首个非空生成 `token_ids` 事件为止；空的角色事件或 usage 事件不算首 token。TPOT 按 `(last_token_time - first_token_time) / (completion_tokens - 1)` 计算，仅在输出多于一个 token、且 token-ID 覆盖校验通过时有效。

一个推测解码 SSE 块可以包含多个 token，所以这些是客户端接收侧指标，不是 GPU kernel 的执行时间。定义见[配置](evidence/configuration.json)，观测值见[逐组记录](data/groups.json)。

</details>

<a id="已记录的方法"></a>

## 测试方法

三条路线固定目标模型、数值精度、题目、输出预算和采样设置，只切换推测解码配置。参数来自当时保存的[配置](evidence/configuration.json)，实际加载检查记录在[运行证据](evidence/run.json)的 `activation` 中。

| 项目 | 本次设置 |
|---|---|
| 硬件 | 单张 H100 NVL，张量并行度为 1 |
| 目标模型 | Qwen3.8-27B，BF16 |
| MTP | 目标 checkpoint 自带的多 token 预测权重，未另行训练或转换 |
| DFlash 2 | incoai 发布的 Qwen3.8-27B-DFlash2，BF16 |
| 推理引擎 | vLLM 0.28.0，实际加载 Model Runner V2 |
| 候选数量 | 基线为 0；MTP7 和 DFlash 2-7 均为 7 |
| 输出预算 | 每题最多 16,384 个 token，包含 thinking |
| 思考设置 | 开启并保留 thinking，`reasoning_effort="xhigh"` |
| 采样 | temperature 为 1.0，top_p 为 0.95，top_k 为 20 |
| 配对方式 | 并发 1、4、8；seed 为 20260906、20260907、20260908 |

每类 32 个题目 ID 按预先固定的 SHA-256 排序规则选取，不参考回答和分数。三条路线使用相同的逐题 seed，但这不代表每一步随机抽样完全对齐。代码题由 EvalPlus 官方工具评分，数学题由 Math-Verify 官方工具评分。

<details>
<summary>查看固定版本、完整参数与请求样例</summary>

以下链接固定到实际使用的版本，不指向模型仓库当前最新版：

| 对象 | 版本记录 |
|---|---|
| 目标模型 | [Qwen3.8-27B checkpoint](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) |
| DFlash 2 | [Qwen3.8-27B-DFlash2 checkpoint](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2/tree/dedf8df68adfb1afeaf7b7480c0a0243108177b4)，架构为 `DFlash2DraftModel` |
| vLLM | [0.28.0 固定源码](https://github.com/vllm-project/vllm/tree/2cf0a6915ce544dc493a0990f2ea38d81601128a) |
| EvalPlus | [固定源码](https://github.com/evalplus/evalplus/tree/26d6d00bb1fd0fa37f39c99d5290da67891d1c5e)，使用官方 sanitize/evaluate CLI |
| Math-Verify | [固定源码](https://github.com/huggingface/Math-Verify/tree/ba3d3aaff23b3f4cac7a14672b4f6e293d97c98b)，使用官方 `evaluate_model_outputs.py` |

其余参数为 `min_p=0.0`、`presence_penalty=0.0`、`repetition_penalty=1.0`。模板同时设置 `enable_thinking=true` 和 `preserve_thinking=true`；调度上限为 `max_model_len=32768`、`max_num_seqs=16`、`max_num_batched_tokens=16384`。

客户端与服务端同机，经过回环地址按固定顺序、固定并发补位派发。固定客户端并发，不代表 GPU 批次形状相同。归档路线标识分别为 `baseline`、`mtp7`、`dflash2_7`；配置中的基础 seed 为 20260906。

[请求样例](evidence/request-examples.json)保存了第一组基线运行中 `HumanEval/69` 和 `MATH-500/100` 的提示词、完整参数及哈希。`raw_correct` 记录评分器判对数，`normal_correct` 还要求 `finish_reason=stop`；二者在本次 S 阶段恰好一致。离线分析使用已保存的评分，不重新判分。

</details>

## How to Run

### 1. 先分清目标模型和 draft 权重

约 3.8 GB 的文件是 **DFlash 2 的 draft model，不是完整的 Qwen3.8-27B，也不是它的 MTP 权重**。不能把该文件作为 `--model` 再指定 `method=mtp`。三条路线都必须加载完整目标 checkpoint：

| 路线 | 目标模型 | 推测配置 |
|---|---|---|
| 基线 | Qwen3.8-27B | 不传 `--speculative-config` |
| MTP7 | 同一目标 checkpoint，使用其自带 MTP 权重 | `method="mtp"`，不另传 draft model |
| DFlash 2-7 | 同一目标 checkpoint，另挂 DFlash 2 draft | `method="dflash"`，`model` 指向 draft 目录 |

本次归档记录的目标 `.safetensors` 共 18 个、55,563,006,776 字节（约 55.56 GB）；draft 权重为 1 个、3,848,817,896 字节（约 3.85 GB / 3.58 GiB）。这是磁盘权重大小，不是推理所需总显存。**DFlash 2 是 checkpoint 的名称，本次 vLLM 的启动方法仍写 `dflash`，不是 `dflash2` 或 `draft_model`。**

以下使用 Linux x86_64、Bash 和 Python 3.12。实测硬件为单张 H100 NVL；需要支持 CUDA 13 的 NVIDIA 驱动，以及目标、draft、KV cache 和工作区所需显存。其他 GPU 容量与数值行为需另行验证。

### 2. 准备固定版本

从本仓库的 `Deep-Learning/Speculative-Decoding/experiments/20260906-qwen38` 目录执行。下面的环境创建仅用于首次安装；已有经过验证的相同版本环境时直接激活，不要重建。下载会占用数十 GB 磁盘空间。

```bash
python3 -m venv "$HOME/.venvs/qwen38-specdec"
source "$HOME/.venvs/qwen38-specdec/bin/activate"
python -m pip install 'vllm==0.28.0' 'torch==2.13.0' 'transformers==5.16.1'
python -m pip check

export MODEL_ROOT="$HOME/models/qwen38"
hf download Qwen/Qwen3.8-27B \
	--revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0 \
	--local-dir "$MODEL_ROOT/target"
hf download incoai/Qwen3.8-27B-DFlash2 \
	--revision dedf8df68adfb1afeaf7b7480c0a0243108177b4 \
	--local-dir "$MODEL_ROOT/draft"
```

模型目录中应包含配置、全部权重分片和目标 tokenizer，不能只下载一块权重。上述包版本来自原安装记录；这里只固定关键包，不保证未来解析出的所有间接依赖逐字节相同。

### 3. 设置三条路线共用的启动超参

在服务端终端执行一次，三种启动方式共用同一个 Bash 数组。目标路径不要包含 `dflash` 字样，避免模型路径识别与实际角色混淆。日志保存在仓库外，不要将新运行的私有数据提交到公共 Repo。

```bash
set -euo pipefail
export VLLM_USE_V2_MODEL_RUNNER=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export RUN_DIR="$HOME/specdec-runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"

COMMON=(
	--model "$MODEL_ROOT/target"
	--served-model-name Qwen/Qwen3.8-27B
	--dtype bfloat16 --tensor-parallel-size 1
	--max-model-len 32768
	--max-num-seqs 16 --max-num-batched-tokens 16384
	--gpu-memory-utilization 0.9
	--no-enable-prefix-caching --kv-cache-dtype auto
	--attention-backend FLASH_ATTN --mamba-ssm-cache-dtype float32
	--reasoning-parser qwen3 --stream-interval 1
	--generation-config vllm --seed 20260906
	--limit-mm-per-prompt '{"image":0,"video":0,"audio":0}'
	--host 127.0.0.1 --port 18080
)
```

关键区别：模型和 KV cache 使用 BF16，但 Mamba SSM cache 固定为 FP32。`max-num-seqs=16` 是服务端调度上限，不是客户端必须发 16 路并发。`generation-config=vllm` 避免模型目录的生成默认值覆盖显式实验设置。

### 4. 选择一种方式启动

**同一 GPU、同一端口只运行其中一条。** 一条路线测完后，在服务端终端按 `Ctrl+C` 停止，并用 `nvidia-smi` 确认该服务已退出，再启动下一条。

基线，不启用推测解码：

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	2>&1 | tee "$RUN_DIR/baseline-server.log"
```

MTP7，使用目标模型自带的 MTP 权重：

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	--speculative-config '{"method":"mtp","num_speculative_tokens":7,"rejection_sample_method":"standard"}' \
	2>&1 | tee "$RUN_DIR/mtp7-server.log"
```

DFlash 2-7，额外加载配套 draft checkpoint：

```bash
python -I -B -m vllm.entrypoints.openai.api_server "${COMMON[@]}" \
	--speculative-config "{\"method\":\"dflash\",\"model\":\"$MODEL_ROOT/draft\",\"num_speculative_tokens\":7,\"rejection_sample_method\":\"standard\"}" \
	2>&1 | tee "$RUN_DIR/dflash2_7-server.log"
```

另开同机终端，先检查 `curl --fail http://127.0.0.1:18080/v1/models` 能返回 `Qwen/Qwen3.8-27B`。同时核对启动日志中实际生效的模式、V2 runner 和精度；DFlash 应加载 `DFlash2DraftModel`。服务就绪只证明加载完成，还需要下一步真实请求。

### 5. 设置客户端请求与采样

客户端始终调用同一个 `/v1/chat/completions` 和同一个 `model` 名称，**不在客户端切换 MTP/DFlash**。模式由上面的服务端启动参数决定。本实验没有 Web search 或 RAG；这里的客户端设置是采样、thinking、输出预算和请求并发。`top_k=20` 是输出采样范围，不是服务端每轮起草的 7 个 token。

| 客户端设置 | 本次值 |
|---|---|
| 采样 | `temperature=1.0`、`top_p=0.95`、`top_k=20`、`min_p=0.0` |
| 重复惩罚 | `presence_penalty=0.0`、`repetition_penalty=1.0` |
| 思考 | `reasoning_effort="xhigh"`，模板开启并保留 thinking |
| 输出上限 | `max_completion_tokens=16384`，包含 thinking |
| 流式统计 | `stream=true`、`include_usage=true`、`return_token_ids=true`、`include_reasoning=true`、`stream_interval=1` |
| 客户端并发 | 正式子集分别为 1、4、8；三次基础 seed 为 20260906、20260907、20260908 |

每题实际 seed 为 `int(SHA256(f"{base_seed}|{task_id}")[:8], 16) % 2147483647`，不是把基础 seed 原样用于每题。[请求样例](evidence/request-examples.json)已保存当时发送的完整 JSON。下面直接发送其中一份，不重写提示词或猜参数。

在客户端终端进入同一实验目录并激活相同 Python 环境，然后执行：

```bash
set -euo pipefail
source "$HOME/.venvs/qwen38-specdec/bin/activate"
CLIENT_RUN="$HOME/specdec-runs/client-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$CLIENT_RUN"
python -c 'import json; from pathlib import Path; samples=json.loads(Path("evidence/request-examples.json").read_text(encoding="utf-8")); print(json.dumps(samples[0]["request"], ensure_ascii=False))' \
	> "$CLIENT_RUN/request.json"
curl --fail-with-body --no-buffer --connect-timeout 10 --max-time 600 \
	http://127.0.0.1:18080/v1/chat/completions \
	-H 'Content-Type: application/json' \
	--data-binary @"$CLIENT_RUN/request.json" \
	| tee "$CLIENT_RUN/response.sse"
```

`samples[0]` 是代码题，改为 `samples[1]` 可发送数学题。检查完整 SSE 中的生成 `token_ids`、最终 `usage`、`finish_reason` 和 `[DONE]`；`finish_reason=length` 表示触及上限，不能当作正常完成的答案。三条路线应使用相同请求 JSON。此处 curl 的超时与记录方式仅用于单请求复现，不用于计算上文性能表。

### 复现范围

上述命令依据实际安装记录、启动参数及[测量源码](source/campaign_runner.py)的 `server_command` 整理，仅将本机路径改为环境变量；本次文档修订没有重新开 GPU。**它提供三种服务启动与真实请求的复现路径，不把一次 curl 请求冒充完整 benchmark。**

复跑得分表还必须保持同一批 64 题、27 组、固定顺序和并发补位策略，执行原测量逻辑及 EvalPlus/Math-Verify 评分。原 `campaign_runner.py` 的入口还依赖准备阶段的完整输入与运行合同，不能直接拿删去内部字段的公开配置去运行 `--stage all`。现有公开快照提供启动/请求说明和离线复算，尚不是完整 27 组实验的独立安装包。官方方法入口：[MTP](https://github.com/vllm-project/vllm/blob/v0.28.0/docs/features/speculative_decoding/mtp.md)、[固定版本推测配置源码](https://github.com/vllm-project/vllm/blob/2cf0a6915ce544dc493a0990f2ea38d81601128a/vllm/config/speculative.py)。

<a id="执行覆盖"></a>

## 测试覆盖与未执行项

原计划包含四个阶段。本文的速度和得分表只使用 S 阶段，兼容性检查和贪心诊断不混入正式子集结果。

| 阶段 | 完成组数 | 实际响应数 | 状态 |
|---|---:|---:|---|
| C：兼容性检查 | 6 | 48 | 已完成 |
| G：贪心诊断 | 36 | 144 | 已完成 |
| S：重复子集 | 27 | 1,728 | 已完成 |
| F：完整题集 | 0 | 0 | 未执行 |

总计完成 **69/81 组、1,920/5,904 份响应**。剩余 12 组、3,984 份响应保持 `NOT_RUN`，既不从计划中删除，也不当作答错。运行记录的总体状态因此仍为 `BLOCKED`。

F 原本要让三条路线在并发 1 和 8 下，分别完成全部 164 道 HumanEval+ 和 500 道 MATH-500，每题一次，seed 为 20260906。本轮预算没有覆盖这一阶段，因此未启动；已测子集不能写成全量题集成绩。[覆盖记录](evidence/run.json)保留原计划和未执行项。

<details>
<summary>查看各阶段的测量耗时</summary>

| 阶段 | 测量组耗时合计（秒） |
|---|---:|
| C | 928.51 |
| G | 387.09 |
| S | 27,800.41 |
| F | 0，未执行 |

这里只累加各测量组的耗时，显示到小数点后两位；精确值保留在[运行证据](evidence/run.json)中。这不是 VM 总占用时间，“已完成”也不表示每份答案都正确。

</details>

<a id="证据与复算边界"></a>

## 证据与代码

| 入口 | 可核对的内容 |
|---|---|
| [执行程序](source/campaign_runner.py) | 当时使用的组派发、计时和实验控制代码 |
| [评分接入](source/scoring.py)、[流式计时](source/stream_metrics.py) | 官方评分与回答如何绑定，token 如何核对，延迟如何计算 |
| [配置](evidence/configuration.json)、[请求样例](evidence/request-examples.json) | 固定参数及两份带哈希的实际请求 |
| [实验记录](evidence/run.json) | 测试覆盖、加载检查、测量耗时及来源成员哈希 |
| [逐组记录](data/groups.json)、[数值汇总](data/summary.json) | 题目 ID、已存评分、计时、计数和配对结果 |
| [分析程序](analyze_results.py)、[验收程序](validate_report.py) | 重新汇总数字，检查报告和证据是否一致 |

这些源码是实际执行版本的归档，不是从零部署 GPU 的完整安装包。**完整原始回答和 SSE 流仍在作者的私有归档中，没有在此重新分发。** 公开文件不含基础设施定位信息或凭据；归档及成员哈希说明来源，但不能独立证明运行行为。

## 离线复算

在本目录执行，使用 Python 3.10+ 标准库，无需额外依赖、GPU、网络或凭据：

```bash
python validate_report.py
python -m unittest discover -p "test_*.py"
```

验收应输出 `REPORT_GATE=PASS`，测试全部通过，两条命令的退出码都为 0。它们不发起新推理，也不重新评分。需要重新生成数值汇总时，执行：

```bash
python analyze_results.py --groups data/groups.json --output regenerated
```

输出可与[已发布汇总](data/summary.json)对照。程序只读取已保存的评分、计数和计时，不执行生成的答案。从父目录运行的命令见[总览快速开始](../../README-CN.md#快速开始)。

<details>
<summary>重新生成图片和报告</summary>

为分析命令追加 `--figure regenerated/throughput.png` 可生成吞吐图，此项需要 [Matplotlib 3.10.9](requirements-figures.txt)。数值复算本身不需要 Matplotlib。

审阅修改后，`python validate_report.py --refresh` 会重建结果表格和文件哈希清单。默认验收命令只读，不改写证据。图片字节可能随字体或平台变化。

</details>

## 结论适用到哪里

- 可以说明本次固定配置、固定子集中的性能和得分，不能证明统计显著性、分布等价或正式非劣效。
- 吞吐、客户端延迟、正确答案交付速度是不同指标，不能互相替代，也不能据此推断 GPU kernel 的独立性能。
- 本轮换了模型、checkpoint 和引擎，不能据此认定[旧版 DFlash 的并发故障](../20260905-quality/README-CN.md)已修复。两轮结果独立保留。