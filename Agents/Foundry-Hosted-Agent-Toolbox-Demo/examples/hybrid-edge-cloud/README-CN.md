# 端云协同 Demo

[`docs/hybrid-edge-cloud-CN.md`](../../docs/hybrid-edge-cloud-CN.md) 描述模式的最小可跑实现。

## 它演示什么

| 步 | 在哪 | 做什么 |
| --- | --- | --- |
| 1 | Edge（这个 Python 进程） | 确定性地生成 24 小时室内空气质量传感器数据。把任务契约写到 `contract.json`。 |
| 2 | Cloud（hosted agent） | 读契约，调本地正在跑的 hosted agent `/responses`，触发 Toolbox `code_interpreter` 计算统计并给出通风建议。 |

契约是唯一集成点。Edge 不直接调云端 tool；云端不看 edge 本地 API。两侧任意一侧可替换，另一侧无需感知。

## 文件

| 文件 | 用途 |
| --- | --- |
| `contract.py` | `TaskContract` 和 `Step` dataclass（共享 state model）。 |
| `edge_agent.py` | "边" — 生成传感器数据 + 写契约。 |
| `cloud_handoff.py` | "云端 handoff" — 读契约，调 hosted agent，写回结果。 |

## 前置

1. 装好 repo 依赖（`pip install -r ../../requirements.txt`）。
2. Hosted agent server 本地跑起来：
   ```bash
   cd ../..
   python main.py
   ```
   （在另一个 terminal 保持运行。默认绑 `http://localhost:8088`。）

## 跑

```bash
cd examples/hybrid-edge-cloud
python edge_agent.py
python cloud_handoff.py
```

中间检查契约：

```bash
cat contract.json | python -m json.tool | head -30
```

## 期望看到什么

`edge_agent.py` 之后：

```
[edge] Captured 24 hourly readings for 3 sensors (seed=42).
[edge] Wrote contract to contract.json
[edge] current_owner now = cloud
[edge] artifact size = 570 bytes
[edge] Closing lid. Cloud takes over.
```

`cloud_handoff.py` 之后：

```
[cloud] Picked up task <id> (contract version 1).
[cloud] Pending step: Use code_interpreter to compute mean / max / min ...
[cloud] Calling hosted agent at http://localhost:8088/responses ...
[cloud] Step complete. Contract version now 3.
============================================================
HOSTED AGENT ANSWER:
============================================================
The mean CO2 is X ppm, max Y, min Z. ... Ventilation is/is not needed because ...
============================================================
```

云端的回答是 model 在 `code_interpreter` 跑完之后生成的。回答中的数字由 toolbox sandbox 中的 Python 真算出来的，不是 model 眼测 — 这就是这套架构的全部意义。

## 怎么映射到真场景

| Demo 部件 | 真场景对应 |
| --- | --- |
| `simulate_sensor_capture` | 设备上的真传感器 SDK。 |
| `contract.json`（文件） | Cosmos DB 文档、Foundry session `/files`、或小 queue。 |
| `cloud_handoff.py`（手动） | 设备 commit 契约时推一个信号（Web PubSub / Event Grid / 轮询 worker）。 |
| 本地 `http://localhost:8088` | Hosted agent 部署后的 Responses endpoint `{project_endpoint}/agents/{name}/endpoint/protocols/openai/v1/responses`。 |
| 嵌入的 artifact JSON | 带 SAS 的 Blob URL，从契约引用。 |

失败案例、lease/TTL 模式、安全边界讨论见 [`docs/hybrid-edge-cloud-CN.md`](../../docs/hybrid-edge-cloud-CN.md)。

## 这个 demo 不是什么

- 不是真实 edge runtime sample。真 edge 集成依赖设备平台。
- 不是生产 transport。生产用 Cosmos / Blob / queue，不用本地文件。
- 不是安全模型。`policy: edge_only` artifact tag 是惯例，本 demo 不强制。
