# Azure OpenAI Priority Processing：Standard vs Priority PAYGO 基准测试

**作者**：魏新宇 (Xinyu Wei) | **日期**：2026-04-05 | **模型**：gpt-5.4 (2026-03-05) | **区域**：swedencentral

## 摘要

[Priority Processing](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing) 是 Azure OpenAI 的新功能（Preview），在 GlobalStandard/DataZoneStandard 部署上以 1.75 倍定价提供**有保证的 Token 生成速度**。

### 各指标收益条件（216 条记录，IQR 去噪）

| 指标 | 收益条件 | 幅度 | 原因 |
|---|---|:---:|---|
| **TTFT** | ✅ 始终有效（任意输入/输出长度） | **P50: 1296→1221ms (-6%)，σ: ±81→±34ms (-58%)** | Priority 获得更快的调度，与请求大小无关 |
| **TPS (tokens/s)** | ✅ 输出 ≥50 tokens | **+35–39%**（短输入），**+49–66%**（长输入） | Decode 阶段加速；输入越长收益越大 |
| **E2E 延迟** | ✅ 输出 ≥50 tokens | **-17–27%**（短输入），**-25–37%**（长输入） | E2E = TTFT + GenTime；GenTime 占比随输出增大 |
| **并发下 TTFT** | ✅ 并发请求 | **P95 -52%** | Priority 避免了 Standard 的队列尖峰 |
| **❌ 无收益** | 输出 ≤30 tokens | TPS ±2%，E2E -4.5% | GenTime 仅 ~97ms（占 E2E <7%）；加速 30% 也只省 ~29ms，被 TTFT 噪声淹没 |

### 为什么短输出无显著收益

```mermaid
flowchart LR
    E2E["E2E"] --> TTFT["TTFT<br/>= 网络 + 排队<br/>+ prefill + 首token解码"]
    E2E --> GenTime["GenTime<br/>= 剩余token解码<br/>= (tokens-1) / TPS"]
    
    subgraph S20["20 tokens"]
        T20["TTFT=1295ms<br/>(92%)"]
        G20["GenTime=97ms<br/>(7%)"]
        R20["Priority 省<br/>~29ms → 噪声淹没"]
    end
    
    subgraph S1000["1000 tokens"]
        T1000["TTFT=1237ms<br/>(5%)"]
        G1000["GenTime=22558ms<br/>(95%)"]
        R1000["Priority 省<br/>~7500ms → 效果显著"]
    end
    
    style S20 fill:#fff3cd,stroke:#ffc107
    style S1000 fill:#d4edda,stroke:#28a745
    style R20 fill:#f8d7da,stroke:#dc3545
    style R1000 fill:#d4edda,stroke:#28a745
```

> Priority **主要加速 Decode（GenTime -26~32%）**，同时也改善 TTFT（-7%，σ -53%）。GenTime 改善约为 TTFT 改善的 4 倍。当输出 ≤30 tokens 时，GenTime 仅 <100ms——即使加速 30% 也只省 ~29ms，小于 TTFT 测量噪声（σ=81ms）。收益存在但**在该尺度下无法测量**。

### 二维结果：输出长度 × 输入长度

| 输入 | 输出 | Std TPS | Pri TPS | **ΔTPS** | Std E2E | Pri E2E | **ΔE2E** |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 短 | 50 | 34.9 | 48.4 | **+39%** | 2.6s | 2.2s | -18% |
| 短 | 200 | 42.7 | 58.4 | **+37%** | 5.8s | 4.6s | -21% |
| 短 | 500 | 45.1 | 60.9 | **+35%** | 11.9s | 9.4s | -21% |
| 短 | 1000 | 43.1 | 59.7 | **+39%** | 24.5s | 17.9s | -27% |
| **长** | **200** | 40.1 | 59.8 | **+49%** | 6.1s | 4.6s | **-25%** |
| **长** | **500** | 38.2 | 63.6 | **+67%** | 14.4s | 9.1s | **-37%** |

> **输入越长 → Priority 收益越大**：输出=500 时，短输入 ΔTPS=+35% vs 长输入 ΔTPS=**+67%**（+32pp）。Standard 的 TPS 在长上下文 Prefill 压力下下降；Priority 保持 TPS 保证不受输入长度影响。

### 什么决定 Priority 收益——控制变量分析

两个变量影响 Priority 的 TPS 提升百分比（ΔTPS%），但通过**不同机制**：

**输出长度决定"是否"有可测量的收益：**
- E2E = TTFT + GenTime，其中 GenTime = 输出 tokens / TPS
- 20 tokens 时：GenTime ≈ 97ms（占 E2E 的 7%）→ 加速 30% 仅省 ~29ms → 被 TTFT 噪声（σ=81ms）淹没
- 1000 tokens 时：GenTime ≈ 22,558ms（占 E2E 的 95%）→ 加速 30% 省 ~7,500ms → 效果显著
- 阈值：输出 ≥50 tokens 才有可测量收益

**输入长度决定收益"幅度"：**
- Priority TPS 不受输入长度影响（有 TPS 保证）：short_500 Pri=60.9，long_500 Pri=63.6
- Standard TPS 在长 prefill 压力下下降：short_500 Std=45.1，long_500 Std=**38.2**（-15%）
- 由于 ΔTPS% = (Pri - Std) / Std，Std 下降（分母缩小）→ 百分比增大
- 结果：同样输出=500，ΔTPS 从 +35%（短输入）增加到 +67%（长输入）

| 变量 | 对 ΔTPS% 的影响 | 机制 |
|---|---|---|
| **输出长度** | 决定收益是否可测量 | GenTime 占 E2E 比例：占比低 → 噪声淹没信号 |
| **输入长度** | 放大收益百分比 | Standard TPS 在 prefill 负载下下降；Priority TPS 保持不变 |

### TTFT（每 Tier N=99，IQR 去噪）

| Tier | TTFT P50 | TTFT P95 | Mean±σ |
|---|:---:|:---:|:---:|
| Standard | 1296 ms | 1449 ms | 1300 ± 81 ms |
| **Priority** | **1221 ms** | **1281 ms** | **1224 ± 34 ms** |
| **差值** | **-75 ms (-5.8%)** | **-168 ms** | **σ: ±81→±34ms (-58%)** |

![Priority Processing Benchmark](images/priority_processing_benchmark.png)

---

## 1. Priority Processing 是什么？

Priority Processing 是一种按使用量付费的选项，提供**有保证的 Token 生成速度（TPS）**，无需 PTU 承诺。

| 维度 | Standard PAYGO | **Priority PAYGO** | PTU |
|--------|:---:|:---:|:---:|
| TPS 保证 | 尽力而为 | **99% > 50 TPS**（gpt-5.4） | 有保证 |
| 定价 | 基础费率 | **1.75 倍基础费率** | 固定月费 |
| 承诺 | 无 | **无** | 月度/年度 |
| TTFT 改善 | — | **P50 -6%，σ ±81→±34ms** | 有 |
| 长上下文（>128K） | 正常 | 降级为 Standard | 正常 |

**支持的模型**（截至 2026-04）：

| 模型 | 延迟目标 | 区域 |
|---|:---:|---|
| gpt-5.4 (2026-03-05) | 99% > 50 TPS | polandcentral, southcentralus, swedencentral |
| gpt-5.2 (2025-12-11) | 99% > 50 TPS | 20+ 区域 |
| gpt-5.1 (2025-11-13) | 99% > 50 TPS | 20+ 区域 |
| gpt-4.1 (2025-04-14) | 99% > 80 TPS | 20+ 区域 |

> 来源：[Microsoft Learn — Priority Processing](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing)

---

## 2. Priority 加速什么（不加速什么）

```mermaid
flowchart LR
    E2E["E2E 延迟"] --> TTFT["TTFT<br/>(prefill + 首token解码)<br/>P50 -6%, σ ±81→±34ms"]
    E2E --> GenTime["GenTime<br/>(剩余token解码)<br/>+30~43% 更快<br/>（主要收益）"]
    
    style TTFT fill:#fff3cd,stroke:#ffc107
    style GenTime fill:#d4edda,stroke:#28a745
```

Priority **主要加速 Decode**（GenTime -26~32%，即 TPS +30~43%），同时也改善 TTFT（-7%，σ -53%）。TTFT = 网络 + 调度 + Prefill + 首 token 解码；GenTime = 剩余 token 解码。TTFT 主要由 Prefill 主导，因此改善较小（约为 GenTime 改善的 1/4）。E2E 改善随输出长度增加，因为 GenTime 在 E2E 中的占比增大。

| 组件 | Standard | Priority | 影响 |
|---|:---:|:---:|:---:|
| TTFT（prefill + 首token解码） | 1296 ms | 1221 ms | P50 -6%，σ ±81→±34ms |
| GenTime（剩余token解码） | 取决于输出 | **+30~43% 更快** | 主要收益 |
| E2E（总和） | 取决于输出 | -16~30% | 随输出长度增加 |

### 实测 vs 微软 SLA 承诺

微软[文档](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/priority-processing)中 Priority Processing 的延迟目标为 gpt-5.4 **99% > 50 TPS**（P50，每 5 分钟窗口）。我们的实测验证了这一承诺：

| 输出 | Standard TPS P50 | ≥50? | Priority TPS P50 | ≥50? |
|:---:|:---:|:---:|:---:|:---:|
| ≤30 | 51.3 | ✅ | 50.2 | ✅ 踩线 |
| 50 | 38.2 | ❌ | 49.8 | ⚠️ 踩线 |
| 100 | 44.1 | ❌ | 60.2 | ✅ |
| 200 | 44.6 | ❌ | 59.8 | ✅ |
| 500 | 45.7 | ❌ | 63.1 | ✅ |
| 1000 | 43.6 | ❌ | 62.4 | ✅ |

> **Standard 在 6 个场景中有 5 个跌破 50 TPS**（38–46 TPS）。Priority 在全部 6 个场景达标或接近达标（50–63 TPS，50tok 为 49.8 踩线）。这正是 Priority Processing 的核心价值：提供 Standard 无法保证的 TPS 下限。

---

## 3. 何时使用 Priority Processing

| 场景 | 输入 | 输出 | ΔTPS | ΔE2E | ROI | 原因 |
|---|:---:|:---:|:---:|:---:|:---:|---|
| **Agent 多轮对话** | 长 (1K-10K) | 200-1000 | +49~66% | -25~37% | ✅✅✅ | context 累积→输入越来越长→Standard TPS 持续下降 |
| **RAG 长回答** | 长 (2K-8K) | 200-1000 | +49~66% | -25~37% | ✅✅✅ | 检索 chunks 塞满 context→长输入 |
| **Code generation** | 长 (1K-4K) | 200-2000 | +49~66% | -25~37% | ✅✅✅ | 代码上下文大+生成代码长 |
| **内容生成（长 prompt）** | 长 (1K+) | 500-2000 | +49~66% | -25~37% | ✅✅✅ | 长 system prompt + 品牌规范 |
| **流式聊天** | 短 (<500) | 100-500 | +35~39% | -17~21% | ✅✅ | 用户实时看 output stream，速度感知明显 |
| **邮件/报告生成** | 短 (<500) | 200-1000 | +35~39% | -17~27% | ✅✅ | 中等输出，稳定收益 |
| **高并发突发** | 任意 | >50 | +30~43% | P95 -52% | ✅✅ | 尾延迟控制，避免 queue spike |
| **短问短答** | 短 | <30 | ≈0% | -4% | ❌ | GenTime <100ms，收益被噪声淹没，白付 75% |
| **意图分类/路由** | 短 | 5-20 | ≈0% | ≈0% | ❌ | 输出太短，零可测量收益 |

> **最佳场景**：长输入 + 长输出（Agent、RAG、Code）。Priority 的 TPS 保证不变，而 Standard 的 TPS 在长上下文 prefill 压力下下降——百分比差距越拉越大。

### 成本收益分析

Priority 定价为 Standard 的 1.75 倍。加速是否值得？

| 输出 | E2E 节省 | 成本溢价 | 是否值得？ |
|:---:|:---:|:---:|:---:|
| 50 tok | 0.3s | +75% | 仅延迟敏感场景 |
| 200 tok | 1.3s | +75% | 用户交互场景推荐 |
| 500 tok | 3.1s | +75% | **推荐** |
| 1000 tok | 7.1s | +75% | **强烈推荐** |

---

## 4. 并发负载性能

10 并发负载下（25 请求，输出=200）：

| 指标 | Standard | Priority | 差值 |
|---|:---:|:---:|:---:|
| TTFT P50 | 1452 ms | 1249 ms | -14% |
| **TTFT P95** | 3296 ms | **1590 ms** | **-52%** |
| E2E P50 | 5365 ms | 4227 ms | -21% |
| TPS P50 | 54.6 | 68.9 | +26% |
| 吞吐量 | 1.6 req/s | 1.9 req/s | +19% |

> Priority 在负载下的最大优势：**尾延迟控制** — TTFT P95 降低 52%。Standard 受队列突发影响；Priority 保持一致延迟。

---

## 5. 混合架构：PTU + Priority + Standard

```mermaid
flowchart TB
    APIM["流量路由器<br/>（APIM）"] --> PTU["PTU<br/>（基线）"]
    APIM --> PRI["Priority<br/>（溢出）"]
    APIM --> STD["Standard<br/>（后台）"]
    
    PTU --- P1["稳定流量<br/>最低延迟<br/>固定成本"]
    PRI --- P2["峰值 / 突发<br/>TPS 保证<br/>无承诺"]
    STD --- P3["批量 / 异步<br/>最低成本"]
    
    style PTU fill:#d4edda,stroke:#28a745
    style PRI fill:#fff3cd,stroke:#ffc107
    style STD fill:#e2e3e5,stroke:#6c757d
    style APIM fill:#e8d5f5,stroke:#7209b7
```

| 流量类型 | 路由到 | 原因 |
|---|---|---|
| 稳定基线 | PTU | 最低延迟 + 固定成本 |
| 峰值溢出 | **Priority PAYGO** | TPS 有保证 + 无承诺 |
| 后台任务 | Standard PAYGO | 最低成本 |

---

## 6. 限制

- **区域可用性**：gpt-5.4 Priority 仅在 3 个区域可用（polandcentral、southcentralus、swedencentral）
- **Ramp Rate 限制**：15 分钟内 TPM 增幅超过 50% 可能触发降级
- **长上下文**：Prompt 超过 128K Token 自动降级
- **Mini/Nano 模型**：不支持（仅旗舰模型：gpt-5.4、gpt-5.2、gpt-5.1、gpt-4.1）
- **`service_tier` 响应字段**：`2025-04-01-preview` API 版本不返回此字段

---

## 7. 复现基准测试

### 前置条件

- Python 3.10+
- 在支持区域部署 gpt-5.4（GlobalStandard）的 Azure OpenAI 资源
- `httpx` 包

### 运行

```bash
pip install httpx
python scripts/benchmark_priority_processing.py \
  --endpoint https://YOUR_ENDPOINT.openai.azure.com \
  --api-key YOUR_API_KEY \
  --deployment YOUR_DEPLOYMENT_NAME \
  --iterations 8 --warmup 2
```

### 数据文件

| 文件 | 说明 |
|------|-------------|
| `data/benchmark_priority_multilength.json` | 6 种输出长度 × 8 轮 × 2 Tier（96 条记录） |
| `data/benchmark_priority_full_v3.json` | 6 场景 × 5 轮 × 2 Tier（60 条记录，短+长 Prompt） |

---

## 8. 测试方法论

- **模型**：gpt-5.4 (2026-03-05)，GlobalStandard 部署
- **区域**：swedencentral（Priority Processing 支持）
- **参数**：`reasoning_effort=none`、`stream=True`、`service_tier=default|priority`
- **执行**：Standard/Priority **交替执行**（消除时间偏差）
- **去噪**：IQR 1.5 倍四分位距异常值去除
- **指标**：TTFT、TPS（内容块 / 生成时间）、E2E
- **测试环境**：Windows VM（East Asia）→ swedencentral 部署
