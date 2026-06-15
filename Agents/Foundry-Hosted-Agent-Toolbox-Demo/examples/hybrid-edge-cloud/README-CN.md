# 端云协同示例

这个示例展示设备侧进程和云端 Hosted Agent 之间的安全交接模式。

## 流程

1. `edge_agent.py` 采集确定性的传感器读数，并写入 `contract.json`。
2. `cloud_handoff.py` 读取 contract，并把结构化 prompt 提交给 Hosted Agent Responses endpoint。
3. Hosted Agent 可以使用 `code_interpreter` 计算统计数据并返回建议。

## 运行

```bash
python edge_agent.py
AGENT_URL=http://localhost:8088/responses python cloud_handoff.py
```

## 运行日志示例

```text
[edge] current_owner=cloud
[edge] wrote contract.json
[cloud] accepted contract_id=task-1234abcd
[cloud] objective=Compute mean, min, and max for each signal and return a short ventilation recommendation.
```
