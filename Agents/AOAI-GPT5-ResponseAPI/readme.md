# 在 Azure OpenAI GPT‑5 中使用Responses API：推理链复用、加密、摘要与成本分析

## Refer to

- *[Reasoning Token 复用机制分析（Joey Zeng）](https://github.com/joeyzenghuan/AI-Learning-Samples/blob/main/Responses-API/reasoning_token_validation/reasoning_token_reuse_analysis_detailed.md)*   
- *[OpenAI Cookbook：Responses API Reasoning Items 示例](https://github.com/openai/openai-cookbook/blob/main/examples/responses_api/reasoning_items.ipynb)*

## **TL;DR**

- **Effort 是决定 reasoning tokens 长度的核心变量**

  - `minimal` Effort 几乎不产生推理链（ratio≈0%），`low` Effort 约 0%~50%，`medium`/`high` 可达 70%~93%。
  - `"summary":"detailed"` 并不会增加 reasoning token 数量。推理长度主要由 Effort 控制。

- **`previous_response_id` 支持跨轮直接复用推理链**

  reasoning token的复用条件

  1. 如果上一轮模型返回的是assistant类型的message，那在新一轮次的调用过程中，出现在这条assistant message前的所有reasoning token都会被responses api主动清零，此时cached token一定为0。
  2. 如果是连续多次的function call调用, reasoning token可以一直保留，cached token会随着调用轮次的增加而增加。
  3. 如果不同轮次的function call之间出现模态变化，比如前一轮是function_call_output提供的是纯文本，新的一轮带图片(以function_call_output:string + role:user type:input_image组合)，那么reasoning token还会复用，但cached token可能降为0（新的多模态请求可能路由到不同的endpoint）

  

- **Encrypted 模式加密的是推理链，不是最终输出**

  - `include=["reasoning.encrypted_content"]` 返回加密推理链 blob，业务可本地保存后回传复用。
  - `store=False`：服务端不保存明文，满足 ZDR/GDPR 合规，但无法在服务端统计 reasoning token。
  - `store=True`：服务端保留明文，可做完整 usage 统计；可同时返回加密版本供本地持久化。

- **Responses API 相对传统 Chat Completions API 的优势**

  - 原生推理链管理与复用（含加密链）
  - 推理链摘要观测（`concise` / `auto` / `detailed`）
  - 原生支持多轮链路复用 + 条件推理链调用
  - 完整支持 function calling、多模态输入输出、结构化响应合并

  

------

## **背景与问题**

在生产落地 LLM 时，常遇到以下工程痛点：

1. **多轮推理链丢失**
   - 多轮对话中，模型无法“记住”上文的 chain-of-thought，只能每轮从零推理，浪费算力、降低逻辑一致性。
2. **上下文维护成本高**
   - Chat Completions 必须显式传回完整 chat history：
     - token 成本高，长对话容易超过 context 长度限制。
3. **推理链无法直接访问和复用**
   - 无 API 获取上一轮推理链，更无法传递它（尤其是加密形式）到下一请求中。
4. **合规与数据主权要求**
   - 在 ZDR/GDPR 等安全合规场景下，供应商不应保存明文推理链，但业务侧仍希望在本地持有并跨轮利用这些链路。
5. **推理链可观测性与成本治理**
   - 调试需要查看推理链推演细节（观测 reasoning token 占比），但不能暴露 raw chain-of-thought。
   - 需要验证 `"summary":"detailed"` 等模式对 reasoning token 成本的真实影响，进行算力成本优化。



## **Responses API vs Chat Completions API**

| 特性         | Chat Completions API | Responses API                                          |
| ------------ | -------------------- | ------------------------------------------------------ |
| 上下文管理   | 必须传回完整messages | `previous_response_id` 在服务端缓存推理链（自动续用）  |
| 推理链复用   | 无法直接复用         | reasoning item 明文ID或加密blob，显式/自动复用         |
| 推理链摘要   | 无内建               | `reasoning.summary`，安全可读，不暴露raw CoT           |
| 推理链加密   | 无                   | store=False + encrypted_content，本地保存回传，ZDR合规 |
| 工具调用输出 | 混在message里        | output结构分type=message/tool_call/reasoning           |
| 多模态结构化 | 支持有限             | 原生结构化input/output，多type并行                     |

**提升能力总结：**

- 真正的推理链引用 + 自动/加密回传机制
- 合规下的安全推理链复用
- 更结构化的多模态与工具调用管理

## Prompt Cache的顺序

### **Prompt 构造顺序**

```
System Prompt → Tool Definitions → Messages
```

**Messages 内部顺序**：User → Assistant(含隐藏 COT) → Function Call → Function Call Output

### **COT（Reasoning Tokens）位置**

- 出现在 **Assistant 消息** 的隐藏部分（`type=reasoning`），和可见 `output_text` 并列
- 不是单独消息，嵌在 Assistant role 中

### **Prompt Cache 命中条件**

- 首缓存块 ≥ 1024 tokens
- 从 Prompt 开头截取
- **System Prompt ≥ 1024 tokens**：首块只含 System Prompt（稳定，但不含 COT）
- **System Prompt < 1024 tokens**：首块拼入 Tools/Messages（可能含 COT，但动态内容变动易失效）

### **Messages/COT 进入缓存的意义**

- COT 在被缓存块命中时可实际节约成本
- 命不中则虽逻辑复用，计算仍重跑

### **逻辑 vs 成本复用**

- **逻辑复用**：`previous_response_id` 保留推理链，保证一致性
- **缓存命中**：Prompt Cache 命中，减少解码与推理成本

### **服务端行为**

- assistant → user：清空 RT，CT=0
- assistant → function_call：保留 RT，CT 稳定或递增
- 连续 function_call：RT保留 + CT递增
- 模态切换：RT保留，CT可能清零

![images](https://github.com/david-xinyuwei/david-share/blob/master/Agents/AOAI-GPT5-ResponseAPI/images/1.png)

### 测试结果分析

以下数据均为两轮调用（R1 首轮、R2 续接轮），R2 一律采用 previous_response_id；所有场景均包含长 System Prompt（≥1024 tokens），以便观测 Prompt Cache 命中（cached_tokens）。

表1：多场景 Token 数据（含缓存命中）

| 场景        | round | store | input_tokens | output_tokens | reasoning_tokens | completion_tokens | cached_tokens | reasoning_ratio |
| ----------- | ----- | ----- | ------------ | ------------- | ---------------- | ----------------- | ------------- | --------------- |
| BASIC       | R1    | —     | 3515         | 346           | 320              | 26                | 0             | 92.5%           |
| BASIC       | R2    | —     | 3549         | 212           | 192              | 20                | 3456          | 90.6%           |
| FUNCTION    | R1    | —     | 3637         | 225           | 192              | 33                | 0             | 85.3%           |
| FUNCTION    | R2    | —     | 3934         | 25            | 0                | 25                | 3840          | 0.0%            |
| ENCRYPTED   | R1    | False | 3519         | 789           | 704              | 85                | 0             | 89.2%           |
| ENCRYPTED   | R2    | False | 4316         | 408           | 384              | 24                | 3456          | 94.1%           |
| ENCRYPTED   | R1    | True  | 3519         | 1305          | 1216             | 89                | 0             | 93.2%           |
| ENCRYPTED   | R2    | True  | 3617         | 290           | 256              | 34                | 0             | 88.3%           |
| SUMMARY     | R1    | —     | 3519         | 1883          | 1536             | 347               | 0             | 81.6%           |
| SUMMARY     | R2    | —     | 3880         | 841           | 768              | 73                | 3456          | 91.3%           |
| PREVIOUS_ID | R1    | —     | 3524         | 135           | 128              | 7                 | 0             | 94.8%           |
| PREVIOUS_ID | R2    | —     | 3540         | 310           | 256              | 54                | 3456          | 82.6%           |

要点解读

- previous_response_id 下第二轮（R2）在多数场景出现明显的 cached_tokens（例如 BASIC_R2=3456、FUNCTION_R2=3840、SUMMARY_R2=3456、PREVIOUS_ID_R2=3456），说明 Prompt Cache 命中生效，降低输入成本并提升响应速度。
- FUNCTION_R2 的 reasoning_tokens 为 0，但 cached_tokens=3840，体现“工具输出续接 + 缓存命中”：第二轮主要是可见补述，未产生链式推理，但前缀缓存显著命中。
- ENCRYPTED 场景：
  - store=False：R2 cached_tokens=3456，表明“加密推理项拼接无状态复用”同时可触发前缀缓存命中。
  - store=True：R2 cached_tokens=0（在该路由/部署下未返回缓存命中指标），但 reasoning 仍显著，符合“合规持久化 + 逻辑复用”预期。

表2：AB 对比测试（R1 vs R2，R2 使用 previous_response_id） 为简洁展示，这里列出各 Effort 下的代表性组合与 identical 场景；R2 多数出现 cached_tokens（3456），体现缓存命中。

| effort  | summary            | case | input_tokens | output_tokens | reasoning_tokens | completion_tokens | cached_tokens | reasoning_ratio |
| ------- | ------------------ | ---- | ------------ | ------------- | ---------------- | ----------------- | ------------- | --------------- |
| minimal | none               | R1   | 3522         | 69            | 0                | 69                | 0             | 0.0%            |
| minimal | none               | R2   | 3598         | 38            | 0                | 38                | 0             | 0.0%            |
| minimal | auto               | R1   | 3522         | 87            | 0                | 87                | 0             | 0.0%            |
| minimal | auto               | R2   | 3616         | 49            | 0                | 49                | 3456          | 0.0%            |
| minimal | detailed           | R1   | 3522         | 59            | 0                | 59                | 0             | 0.0%            |
| minimal | detailed           | R2   | 3588         | 28            | 0                | 28                | 3456          | 0.0%            |
| low     | none               | R1   | 3522         | 73            | 0                | 73                | 0             | 0.0%            |
| low     | none               | R2   | 3602         | 50            | 0                | 50                | 3456          | 0.0%            |
| low     | auto               | R1   | 3522         | 65            | 0                | 65                | 0             | 0.0%            |
| low     | auto               | R2   | 3594         | 91            | 64               | 27                | 3456          | 70.3%           |
| low     | detailed           | R1   | 3522         | 67            | 0                | 67                | 0             | 0.0%            |
| low     | detailed           | R2   | 3596         | 106           | 64               | 42                | 3456          | 60.4%           |
| medium  | none               | R1   | 3522         | 209           | 128              | 81                | 0             | 61.2%           |
| medium  | none               | R2   | 3610         | 159           | 128              | 31                | 3456          | 80.5%           |
| medium  | auto               | R1   | 3522         | 327           | 256              | 71                | 0             | 78.3%           |
| medium  | auto               | R2   | 3600         | 225           | 192              | 33                | 3456          | 85.3%           |
| medium  | detailed           | R1   | 3522         | 310           | 256              | 54                | 0             | 82.6%           |
| medium  | detailed           | R2   | 3583         | 160           | 128              | 32                | 3456          | 80.0%           |
| high    | none               | R1   | 3522         | 377           | 320              | 57                | 0             | 84.9%           |
| high    | none               | R2   | 3586         | 284           | 256              | 28                | 3456          | 90.1%           |
| high    | auto               | R1   | 3522         | 261           | 192              | 69                | 3456          | 73.6%           |
| high    | auto               | R2   | 3598         | 292           | 256              | 36                | 3456          | 87.7%           |
| high    | detailed           | R1   | 3522         | 317           | 256              | 61                | 3456          | 80.8%           |
| high    | detailed           | R2   | 3590         | 362           | 320              | 42                | 3456          | 88.4%           |
| minimal | identical_dialogue | R1   | 3526         | 301           | 0                | 301               | 3456          | 0.0%            |
| minimal | identical_dialogue | R2   | 3845         | 36            | 0                | 36                | 3456          | 0.0%            |
| low     | identical_dialogue | R1   | 3526         | 361           | 128              | 233               | 0             | 35.5%           |
| low     | identical_dialogue | R2   | 3777         | 32            | 0                | 32                | 3456          | 0.0%            |
| medium  | identical_dialogue | R1   | 3526         | 1241          | 1088             | 153               | 0             | 87.7%           |
| medium  | identical_dialogue | R2   | 3697         | 167           | 128              | 39                | 3456          | 76.6%           |
| high    | identical_dialogue | R1   | 3526         | 1901          | 1728             | 173               | 0             | 90.9%           |
| high    | identical_dialogue | R2   | 3717         | 230           | 192              | 38                | 3456          | 83.5%           |
| low     | identical_code     | R1   | 3528         | 201           | 128              | 73                | 0             | 63.7%           |
| low     | identical_code     | R2   | 3625         | 80            | 0                | 80                | 3456          | 0.0%            |
| medium  | identical_code     | R1   | 3528         | 394           | 320              | 74                | 0             | 81.2%           |
| medium  | identical_code     | R2   | 3626         | 332           | 256              | 76                | 3456          | 77.1%           |
| high    | identical_code     | R1   | 3528         | 1816          | 1728             | 88                | 3456          | 95.2%           |
| high    | identical_code     | R2   | 3640         | 670           | 576              | 94                | 3456          | 86.0%           |

AB 测试要点

- R2（prev_id）多数出现 cached_tokens=3456（或更高），表明缓存命中稳定。minimal 场景下 reasoning_tokens≈0，但 prev_id 仍可带来缓存命中（如 minimal/auto、minimal/detailed 的 R2）。
- identical_dialogue：R2 常将 reasoning_tokens 降至极低或 0（如 low/medium/high），同时缓存命中（3456），是成本与逻辑的一体化最佳场景。
- identical_code：视改动规模而定，R2 的 reasoning_tokens 显著下降（例如 high: 1728→576，-66.7%），且缓存命中（3456），体现“保留大结构 + 局部重推”的真实工程场景。

表3：previous_response_id 模式下的 Token 节省对比（基于本次 A/B）

| Effort  | 场景类型           | R1 reasoning_ratio | R2 reasoning_ratio | 比例变化(pp) | R1 reasoning_tokens | R2 reasoning_tokens | Token减少比例 |
| ------- | ------------------ | ------------------ | ------------------ | ------------ | ------------------- | ------------------- | ------------- |
| minimal | identical_dialogue | 0.0%               | 0.0%               | 0.0          | 0                   | 0                   | 0%            |
| low     | identical_dialogue | 35.5%              | 0.0%               | -35.5        | 128                 | 0                   | 100.0%        |
| medium  | identical_dialogue | 87.7%              | 76.6%              | -11.1        | 1088                | 128                 | 88.2%         |
| high    | identical_dialogue | 90.9%              | 83.5%              | -7.4         | 1728                | 192                 | 88.9%         |
| low     | identical_code     | 63.7%              | 0.0%               | -63.7        | 128                 | 0                   | 100.0%        |
| medium  | identical_code     | 81.2%              | 77.1%              | -4.1         | 320                 | 256                 | 20.0%         |
| high    | identical_code     | 95.2%              | 86.0%              | -9.2         | 1728                | 576                 | 66.7%         |

字段说明

- 比例变化（pp）：R2 相对 R1 的 reasoning_ratio 变化（负值为下降）。
- Token减少比例：R2 相对 R1 的 reasoning_tokens 降幅，是衡量逻辑推理“绝对节省”的核心指标。与缓存命中（cached_tokens）共同解读，能同时反映逻辑与成本两层优化。

综合分析结论（基于最新数据）

1. previous_response_id 是你当前部署环境下稳定的 Prompt Cache 命中路径
   - R2 普遍出现 cached_tokens（多为 3456/3840），说明服务端对前缀缓存块命中成功，实际降低输入成本与延迟。
   - 即使 minimal Effort 推理几乎为 0，prev_id 仍能带来缓存命中（如 minimal/auto 与 minimal/detailed 的 R2）。
2. Effort 决定推理链长度与复用空间
   - minimal：reasoning_tokens≈0，逻辑复用价值低，但 prev_id 仍可能命中缓存（节省输入成本）。
   - medium/high：reasoning_tokens 高，逻辑复用与缓存命中双优势显著（如 high identical_code: 1728→576，-66.7%，且 R2 cached_tokens 命中）。
3. 任务类型影响节省效果
   - identical_dialogue：R2 reasoning_tokens 大幅下降甚至归零（低/中/高均显著），同时 cached_tokens 命中，最接近“理想复述链”。
   - identical_code：R2 仍需局部重推（reasoning 降幅 20%~66%+），同时 cached_tokens 命中，符合真实工程场景。
4. 加密场景差异
   - store=False：R2 可见 cached_tokens 命中（3456），说明加密推理链的无状态复用也能触发前缀缓存。
   - store=True：本次路由下未返回 cached_tokens 指标（R2=0），但 reasoning 仍显著；可视为“合规持久化 + 逻辑复用”的路径（是否返回缓存命中指标因区域/路由策略而异）。
5. 双指标联合解读（逻辑 vs 成本）
   - reasoning_tokens（逻辑复用） + cached_tokens（成本命中）需同时观察：如 FUNCTION_R2，reasoning=0 但 cached_tokens=3840，说明第二轮主要复述工具结果，前缀缓存仍显著命中，达到“逻辑简化 + 成本优化”。

总之，基于本次实测，采用 previous_response_id + 长且稳定的 System Prompt（≥1024 tokens）+ 参数一致（tools、store、reasoning、parallel_tool_calls 等）是你当前环境中稳定命中 Prompt Cache 的最佳实践；在 identical_dialogue 与 identical_code 场景下，能够同时实现“推理链复用（逻辑一致）”与“缓存命中（成本与延迟优化）”的双赢效果。

------

## 判定清单

### 推理链复用（逻辑一致）判定清单

- 请求侧硬信号（满足其一即可）
  - 第二轮请求显式携带 previous_response_id=上一轮的 response.id（适用于 store=True 或默认）。
  - 在 store=False 场景，第一轮 include=["reasoning.encrypted_content"]，第二轮把上一轮 resp.output 原样拼入 input（含 reasoning.encrypted_content）。
- 指标侧典型信号（辅助判断）
  - 第二轮 R2 的 usage.output_tokens_details.reasoning_tokens 相较 R1显著下降（少推/不重推）。
    - 例：FUNCTION_R1 reasoning=192 → R2=0；SUMMARY_R1=1536 → R2=768；BASIC_R1=320 → R2=192。
  - 解释型问题可能出现 R2 reasoning_tokens 上升，但文本明显“沿用并解释上一轮结论”（逻辑延续仍成立）。
    - 例：PREVIOUS_ID_R1=128 → R2=256（“Explain your previous decision”会展开解释）。
- 行为侧信号（尤其工具链）
  - 连续 function_call + function_call_output：R2 常出现 reasoning≈0 但能直接生成正确的可见回答，表明复用了上一轮的推断与工具结果。
  - function_call 的 call_id 在两轮间正确传递与匹配。
- 反事实对照（最有说服力）
  - 把同一 R2 请求去掉 previous_response_id 重跑：通常 reasoning_tokens 上升、文本风格与结论容易漂移。对比可直接证明 prev_id 带来的逻辑延续。

### 缓存命中（Prompt Cache 复用）判定清单

- 直接指标
  - usage.input_tokens_details.cached_tokens（cached_in）在 R2 大于 0，即命中缓存前缀块。
    - 例：BASIC_R2=3456，FUNCTION_R2=3840，SUMMARY_R2=3456，AB 多数 R2=3456。
- 触发前提（尽量同时满足）
  - 提示词前缀长度 ≥ 1024 tokens（建议长且稳定的 System Prompt 放在最前）。
  - 前缀内容完全一致（System → Tools → Messages 顺序；Tools 定义稳定不变）。
  - 路由/模态一致（避免 text→image 等切换导致路由变化）。
  - 两轮参数一致（store、parallel_tool_calls、reasoning.effort/summary、tools 列表等）。
  - 在缓存生命周期内复用（通常数分钟内；避免缓存驱逐）。
- 注意
  - 个别路由/部署下可能不返回 cached_tokens 指标，即便服务端有内部缓存（此时不要把“cached=0”误判为逻辑未复用）。

### store × 加密 × prev_id × 复用方式 × 缓存命中 总览表

| 场景组合                       | store | include ["reasoning.encrypted_content"] | 能否用 prev_id | 复用载体与方式                                               | 逻辑复用（CoT复用）              | 缓存命中（cached_tokens）                    | 典型示例（本次实测）                                         | 备注                                                       |
| ------------------------------ | ----- | --------------------------------------- | -------------- | ------------------------------------------------------------ | -------------------------------- | -------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| A：会话态复用（最简）          | True  | 可选                                    | 可以           | R2 直接带 previous_response_id                               | 是（服务端存明文 reasoning）     | 常见命中（前缀≥1024、前缀一致）              | BASIC_R2=3456、FUNCTION_R2=3840、SUMMARY_R2=3456、AB多为3456 | 加不加密仅影响是否拿到密文副本，与 prev_id 无关            |
| B：会话态复用 + 加密链（双持） | True  | 是                                      | 可以           | R2 带 prev_id，同时拿密文副本                                | 是                               | 命中与否视前缀、路由而定（有时不报指标）     | ENCRYPTED_R2 store=True cached=0（但 reasoning 显著）        | 某些路由/部署不返回 cached_tokens 指标，勿据此否定逻辑复用 |
| C：无状态复用（ZDR 合规）      | False | 是                                      | 不可以         | 客户端持有密文，R2 把 R1 的 resp.output（含 encrypted_content）原样拼回 input | 是（服务端内存解密使用，不落盘） | 可能命中（前缀≥1024、前缀一致）              | ENCRYPTED_R2 store=False cached=3456                         | prev_id 不可用；密文是“可回传载体”，实现逻辑复用的必要条件 |
| D：无状态但不加密（无法复用）  | False | 否                                      | 不可以         | 无可回传载体（没有 encrypted_content）                       | 否                               | 仅可能靠前缀重复命中缓存，但不具备推理链复用 | 无（不推荐）                                                 | 满足 ZDR 但丧失跨轮逻辑复用能力                            |

#### 表格字段说明

- store：是否在服务端保留上一轮明文推理链（有状态 vs 无状态）。
- include ["reasoning.encrypted_content"]：是否请求“加密推理链”作为客户端可回传载体。
- 能否用 prev_id：
  - store=True 或默认可用；store=False 通常不可用（previous_response_not_found）。
- 复用载体与方式：
  - 会话态：服务端保留明文，直接 prev_id 续接；
  - 无状态：客户端持有密文，在下一轮原样拼回 input，让服务端内存解密继续推。
- 逻辑复用（CoT复用）：是否沿用上一轮推理链，实现少推/不重推、逻辑一致。
- 缓存命中（cached_tokens）：是否命中提示词前缀缓存，降低输入成本与延迟；与 store/加密无直接因果，仅与前缀一致性、长度与路由有关。
- 典型示例：使用你最新一次实测中的数据定位该组合的可观测表现。

### 如何联合判读

- 互相独立但互补：
  - 推理链复用（逻辑一致）不依赖缓存命中：即使 cached_in=0，也可能逻辑复用成功（prev_id 或加密 reasoning）。
    - 例：ENCRYPTED store=True 的 R2 cached=0，但 reasoning 显著，逻辑复用成立。
  - 缓存命中（cached_in>0）是成本/延迟层面的优化：证明前缀被免算，真实降本提速。
- 双赢场景（多数 R2）：
  - R2 携带 prev_id + 前缀稳定一致 → reasoning_tokens 降、cached_in>0 → 同时达成逻辑一致与成本优化。
    - 例：BASIC_R2 reasoning=192 且 cached=3456；FUNCTION_R2 reasoning=0 且 cached=3840。
- 特殊场景：
  - reasoning 上升但 cached 命中：解释型或补充型问题需要展开，但前缀仍命中缓存（逻辑延续 + 成本优化同时成立）。
  - reasoning 降但 cached=0：逻辑复用成立，成本指标未暴露或未命中（可重试或优化前缀/参数一致性）。

### 常见误区与边界

- 误区：把 cached_tokens=0 误判为“没有复用”。纠正：逻辑复用的判定看 prev_id/加密 reasoning 的传递与 reasoning_tokens/文本一致性。
- 边界：
  - assistant → 紧接 user（非工具链）容易触发服务端清空历史推理；用 prev_id 可绕过这类清空并续接逻辑。
  - 多模态切换（text→image）可能导致路由变化、缓存失效，但逻辑复用仍可能成立。
  - identical 两轮在你的环境不一定返回 cached_tokens（路由/策略差异），prev_id 更稳。

### 快速排查流程（建议按序走）

- 步骤1（逻辑复用）：检查是否传了 previous_response_id（store=True）或拼入 resp.output（store=False+加密 reasoning）；确认 R2 输出围绕 R1 结论延续。
- 步骤2（成本命中）：检查 R2 的 cached_tokens 是否 >0；若为 0，核对前缀长度≥1024、System/Tools/参数/模态一致、调用间隔是否处于缓存生命周期。
- 步骤3（辅助指标）：比较 R1/R2 的 reasoning_tokens 是否下降（非解释型问题应显著下降）。
- 步骤4（反事实对照）：移除 prev_id 重跑 R2，看逻辑与推理长度是否变化，作为复用的旁证。
- 步骤5（结论输出）：同时给出“逻辑复用是否成立”“缓存是否命中”的双结论，并指出优化方向（如加长 System 前缀、稳定 Tools、参数一致、在生命周期内调用）。

八、最佳实践（在你当前环境中已验证有效）

- 统一用 previous_response_id 续接 R2（逻辑复用最稳、缓存命中概率最高）。
- 放一个长且稳定的 System Prompt 在最前（≥1024 tokens），把 Tools 定义放在其后且保持不变。
- 保持参数一致（store、parallel_tool_calls、reasoning.effort/summary、tools 列表）。
- 在缓存生命周期内复用，避免 assistant→紧接 user 的新轮切分（尽量在函数链中续接）。
- 对 ENCRYPTED：
  - store=False：用加密 reasoning.encrypted_content 本地回传复用；本次实测 R2 cached_in=3456，双赢成立。
  - store=True：prev_id 续接逻辑复用成立；若 cached_tokens 未返回，属路由/策略差异，不影响逻辑复用结论。



## **验证方法**

```
(base) root@linuxworkvm:~# cat responses_playbook6.py  
```

```
import os
import sys
import json
import argparse
from openai import AzureOpenAI

GPT5_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "AlP*")
GPT5_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://ai-xinyuwei8714ai888427144375.cognitiveservices.azure.com/")
GPT5_RESPONSES_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")
GPT5_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5")

COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"

LONG_SYSTEM = "This is a stable system instruction. " * 500

def ensure_key():
    if not GPT5_API_KEY or not GPT5_ENDPOINT or not GPT5_RESPONSES_API_VERSION or not GPT5_DEPLOYMENT_NAME:
        print("Azure GPT-5 config missing")
        sys.exit(1)

def client():
    return AzureOpenAI(
        api_key=GPT5_API_KEY,
        azure_endpoint=GPT5_ENDPOINT,
        api_version=GPT5_RESPONSES_API_VERSION
    )

usage_records_all = []
usage_records_ab = []

def print_usage_record(tag, usage, store_flag=None):
    it = usage.get("input_tokens", 0)
    ot = usage.get("output_tokens", 0)
    rt = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)
    completion = ot - rt
    cached_in = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
    ratio = f"{(rt/ot*100):.1f}%" if ot else "0%"
    store_info = f"(store={store_flag})" if store_flag is not None else ""
    print(f"[{tag}] {store_info} TOKENS: input={it}, output={ot}, reasoning={rt}, completion={completion}, cached_in={cached_in}, ratio={ratio}")

def extract_call_id(resp_obj):
    try:
        for item in getattr(resp_obj, "output", []):
            typ = getattr(item, "type", None)
            if typ in ("function_call", "tool_call"):
                cid = getattr(item, "call_id", None)
                if cid:
                    return cid
    except Exception:
        pass
    try:
        out_list = resp_obj.model_dump().get("output", [])
        for item in out_list:
            if isinstance(item, dict) and item.get("type") in ("function_call", "tool_call"):
                cid = item.get("call_id")
                if cid:
                    return cid
    except Exception:
        pass
    return None

def weather_tool():
    return [{
        "type": "function",
        "name": "get_weather",
        "description": "Get current temperature in Celsius.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"}
            },
            "required": ["latitude", "longitude"],
            "additionalProperties": False
        },
        "strict": True
    }]

def cmd_basic():
    print("\n===== BASIC 模式（prev_id）=====")
    c = client()
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "tell me a joke"}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[BASIC] OUTPUT R1:", resp1.output_text)
    usage1 = resp1.model_dump().get("usage", {})
    print_usage_record("BASIC_R1", usage1)
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": "tell me one more"}], previous_response_id=resp1.id, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[BASIC] OUTPUT R2:", resp2.output_text)
    usage2 = resp2.model_dump().get("usage", {})
    print_usage_record("BASIC_R2", usage2)
    usage_records_all.append(("BASIC_R1", usage1))
    usage_records_all.append(("BASIC_R2", usage2))

def cmd_function():
    print("\n===== FUNCTION 模式（prev_id）=====")
    c = client()
    tools = weather_tool()
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "What's the weather like in Paris today?"}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, tools=tools, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    usage1 = resp1.model_dump().get("usage", {})
    print_usage_record("FUNCTION_R1", usage1)
    call_id = extract_call_id(resp1)
    if not call_id:
        print(COLOR_RED + "[FUNCTION] No function_call id found in R1 output" + COLOR_RESET)
        return
    func_out = [{"type": "function_call_output", "call_id": call_id, "output": "15°C"}]
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=func_out, tools=tools, previous_response_id=resp1.id, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[FUNCTION] OUTPUT R2:", resp2.output_text)
    usage2 = resp2.model_dump().get("usage", {})
    print_usage_record("FUNCTION_R2", usage2)
    usage_records_all.append(("FUNCTION_R1", usage1))
    usage_records_all.append(("FUNCTION_R2", usage2))

def cmd_encrypted(store_flag):
    print(f"\n===== ENCRYPTED 模式（store={store_flag}）=====")
    c = client()
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "What's the weather like in Paris today?"}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=store_flag, include=["reasoning.encrypted_content"], reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[ENCRYPTED] OUTPUT R1:", resp1.output_text)
    usage1 = resp1.model_dump().get("usage", {})
    print_usage_record("ENCRYPTED_R1", usage1, store_flag=store_flag)
    if store_flag:
        resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": "Thanks, summarize briefly."}], previous_response_id=resp1.id, store=store_flag, include=["reasoning.encrypted_content"], reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    else:
        context2 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "Thanks, summarize briefly."}]
        context2 += resp1.output
        resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context2, store=store_flag, include=["reasoning.encrypted_content"], reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[ENCRYPTED] OUTPUT R2:", resp2.output_text)
    usage2 = resp2.model_dump().get("usage", {})
    print_usage_record("ENCRYPTED_R2", usage2, store_flag=store_flag)
    usage_records_all.append((f"ENCRYPTED_R1_store_{store_flag}", usage1))
    usage_records_all.append((f"ENCRYPTED_R2_store_{store_flag}", usage2))

def cmd_summary():
    print("\n===== SUMMARY 模式（prev_id）=====")
    c = client()
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "Explain differences between photosynthesis and respiration."}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[SUMMARY] OUTPUT R1:", resp1.output_text[:200], "...")
    usage1 = resp1.model_dump().get("usage", {})
    print_usage_record("SUMMARY_R1", usage1)
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": "Summarize the key points in one sentence."}], previous_response_id=resp1.id, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[SUMMARY] OUTPUT R2:", resp2.output_text[:200], "...")
    usage2 = resp2.model_dump().get("usage", {})
    print_usage_record("SUMMARY_R2", usage2)
    usage_records_all.append(("SUMMARY_R1", usage1))
    usage_records_all.append(("SUMMARY_R2", usage2))

def cmd_previous_id():
    print("\n===== PREVIOUS_ID 场景（prev_id）=====")
    c = client()
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "Is 2 less than 10? Answer True or False."}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[PREVIOUS_ID] OUTPUT R1:", resp1.output_text)
    usage1 = resp1.model_dump().get("usage", {})
    print_usage_record("PREVIOUS_ID_R1", usage1)
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": "Explain your previous decision."}], previous_response_id=resp1.id, store=True, reasoning={"summary": "detailed", "effort": "high"}, parallel_tool_calls=False)
    print("[PREVIOUS_ID] OUTPUT R2:", resp2.output_text)
    usage2 = resp2.model_dump().get("usage", {})
    print_usage_record("PREVIOUS_ID_R2", usage2)
    usage_records_all.append(("PREVIOUS_ID_R1", usage1))
    usage_records_all.append(("PREVIOUS_ID_R2", usage2))

def run_ab_case(effort, summary_mode):
    c = client()
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": "Explain why the sky is blue in a concise way."}]
    reasoning_param = {"effort": effort}
    if summary_mode != "none":
        reasoning_param["summary"] = summary_mode
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=True, reasoning=reasoning_param, parallel_tool_calls=False)
    usage1 = resp1.model_dump().get("usage", {})
    print(f"[AB] effort={effort}, summary={summary_mode}, case=R1, OUTPUT:", resp1.output_text[:160])
    print_usage_record(f"AB-{effort}-{summary_mode}-R1", usage1)
    usage_records_ab.append((effort, summary_mode, "R1", usage1))
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": "Repeat briefly."}], previous_response_id=resp1.id, store=True, reasoning=reasoning_param, parallel_tool_calls=False)
    usage2 = resp2.model_dump().get("usage", {})
    print(f"[AB] effort={effort}, summary={summary_mode}, case=R2(prev_id), OUTPUT:", resp2.output_text[:160])
    print_usage_record(f"AB-{effort}-{summary_mode}-R2", usage2)
    usage_records_ab.append((effort, summary_mode, "R2", usage2))

def run_prev_id_identical_dialogue(effort):
    c = client()
    q1 = "曹操厉害还是孙权厉害？请简要说明理由"
    q2 = "请用一句话简要复述你刚才的结论"
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": q1}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=True, reasoning={"summary": "detailed", "effort": effort}, parallel_tool_calls=False)
    usage1 = resp1.model_dump().get("usage", {})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": q2}], previous_response_id=resp1.id, store=True, reasoning={"summary": "detailed", "effort": effort}, parallel_tool_calls=False)
    usage2 = resp2.model_dump().get("usage", {})
    usage_records_ab.append((effort, "identical_dialogue", "R1", usage1))
    usage_records_ab.append((effort, "identical_dialogue", "R2", usage2))

def run_prev_id_identical_code(effort):
    c = client()
    q1 = "写一个Python函数，输入一个列表，返回列表中所有偶数的平方"
    q2 = "在你刚才的代码基础上，增加过滤条件，只保留正偶数的平方"
    context1 = [{"role": "system", "content": LONG_SYSTEM}, {"role": "user", "content": q1}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context1, store=True, reasoning={"summary": "detailed", "effort": effort}, parallel_tool_calls=False)
    usage1 = resp1.model_dump().get("usage", {})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=[{"role": "user", "content": q2}], previous_response_id=resp1.id, store=True, reasoning={"summary": "detailed", "effort": effort}, parallel_tool_calls=False)
    usage2 = resp2.model_dump().get("usage", {})
    usage_records_ab.append((effort, "identical_code", "R1", usage1))
    usage_records_ab.append((effort, "identical_code", "R2", usage2))

def cmd_ab_summary():
    print("\n===== AB 测试（全部使用 prev_id）=====")
    for eff in ["minimal", "low", "medium", "high"]:
        for summ in ["none", "auto", "detailed"]:
            run_ab_case(eff, summ)
        run_prev_id_identical_dialogue(eff)
        run_prev_id_identical_code(eff)

def print_table_all():
    print("\n=== 表1: ALL模式 Token 数据 ===")
    print("场景                    | input_tokens | output_tokens | reasoning_tokens | completion_tokens | cached_tokens | reasoning_ratio")
    for name, usage in usage_records_all:
        it = usage.get("input_tokens", 0)
        ot = usage.get("output_tokens", 0)
        rt = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)
        completion = ot - rt
        cached_in = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
        ratio = f"{(rt/ot*100):.1f}%" if ot else "0%"
        print(f"{name:<23} | {it:<12} | {ot:<13} | {rt:<16} | {completion:<17} | {cached_in:<13} | {ratio}")

def print_table_ab():
    print("\n=== 表2: AB测试 Token 数据 ===")
    print("effort   | summary              | case   | input_tokens | output_tokens | reasoning_tokens | completion_tokens | cached_tokens | reasoning_ratio")
    for eff, summ, case, usage in usage_records_ab:
        it = usage.get("input_tokens", 0)
        ot = usage.get("output_tokens", 0)
        rt = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)
        completion = ot - rt
        cached_in = usage.get("input_tokens_details", {}).get("cached_tokens", 0)
        ratio = f"{(rt/ot*100):.1f}%" if ot else "0%"
        print(f"{eff:<8} | {summ:<20} | {case:<6} | {it:<12} | {ot:<13} | {rt:<16} | {completion:<17} | {cached_in:<13} | {ratio}")

def cmd_all():
    cmd_basic()
    cmd_function()
    cmd_encrypted(store_flag=False)
    cmd_encrypted(store_flag=True)
    cmd_summary()
    cmd_previous_id()
    print_table_all()
    cmd_ab_summary()
    print_table_ab()

if __name__ == "__main__":
    ensure_key()
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["basic","function","encrypted_false","encrypted_true","summary","previous_id","ab_summary","all"])
    args = p.parse_args()
    if args.mode == "basic":
        cmd_basic(); print_table_all()
    elif args.mode == "function":
        cmd_function(); print_table_all()
    elif args.mode == "encrypted_false":
        cmd_encrypted(store_flag=False); print_table_all()
    elif args.mode == "encrypted_true":
        cmd_encrypted(store_flag=True); print_table_all()
    elif args.mode == "summary":
        cmd_summary(); print_table_all()
    elif args.mode == "previous_id":
        cmd_previous_id(); print_table_all()
    elif args.mode == "ab_summary":
        cmd_ab_summary(); print_table_ab()
    elif args.mode == "all":
        cmd_all()
```



完整执行代码：

```
(base) root@linuxworkvm:~# python responses_playbook6.py all
```

测试结果：

```
===== BASIC 模式（prev_id）=====
[BASIC] OUTPUT R1: I tried to make a belt out of clocks—turns out it was a waist of time.
[BASIC_R1]  TOKENS: input=3515, output=346, reasoning=320, completion=26, cached_in=0, ratio=92.5%
[BASIC] OUTPUT R2: I asked my dog what’s two minus two—he said nothing.
[BASIC_R2]  TOKENS: input=3549, output=212, reasoning=192, completion=20, cached_in=3456, ratio=90.6%

===== FUNCTION 模式（prev_id）=====
[FUNCTION_R1]  TOKENS: input=3637, output=225, reasoning=192, completion=33, cached_in=0, ratio=85.3%
[FUNCTION] OUTPUT R2: Right now in Paris it’s about 15°C. Would you like details like rain chance or wind?
[FUNCTION_R2]  TOKENS: input=3934, output=25, reasoning=0, completion=25, cached_in=3840, ratio=0.0%

===== ENCRYPTED 模式（store=False）=====
[ENCRYPTED] OUTPUT R1: I don’t have live weather access. If you want, I can look it up for you.

Typical late-September in Paris: highs around 18–21°C (64–70°F), lows 10–13°C (50–55°F), partly cloudy with a chance of light showers.

Would you like me to fetch the current forecast from Météo-France or Weather.com?
[ENCRYPTED_R1] (store=False) TOKENS: input=3519, output=789, reasoning=704, completion=85, cached_in=0, ratio=89.2%
[ENCRYPTED] OUTPUT R2: It repeatedly emphasizes that the message is a stable system instruction, stressing its persistence and consistency.
[ENCRYPTED_R2] (store=False) TOKENS: input=4316, output=408, reasoning=384, completion=24, cached_in=3456, ratio=94.1%

===== ENCRYPTED 模式（store=True）=====
[ENCRYPTED] OUTPUT R1: I don’t have live access to weather data. Typically in late September, Paris is mild: daytime highs around 18–20°C (64–68°F), lows 11–13°C (52–55°F), with a mix of sun and clouds and occasional showers.

If you want the exact conditions right now, I can guide you to Météo-France or interpret a screenshot from your weather app.
[ENCRYPTED_R1] (store=True) TOKENS: input=3519, output=1305, reasoning=1216, completion=89, cached_in=0, ratio=93.2%
[ENCRYPTED] OUTPUT R2: Mild and variable: highs around 18–20°C, lows 11–13°C, partly cloudy with a chance of showers.
[ENCRYPTED_R2] (store=True) TOKENS: input=3617, output=290, reasoning=256, completion=34, cached_in=0, ratio=88.3%

===== SUMMARY 模式（prev_id）=====
[SUMMARY] OUTPUT R1: In short: Photosynthesis stores energy in sugars using light; respiration releases energy from sugars to make ATP.

Key differences:
- Purpose: Photosynthesis is anabolic (builds glucose); respiration ...
[SUMMARY_R1]  TOKENS: input=3519, output=1883, reasoning=1536, completion=347, cached_in=0, ratio=81.6%
[SUMMARY] OUTPUT R2: Photosynthesis is a light-dependent, anabolic, endergonic process in chloroplasts that makes glucose and O2 from CO2 and H2O, whereas respiration is a light-independent, catabolic, exergonic process i ...
[SUMMARY_R2]  TOKENS: input=3880, output=841, reasoning=768, completion=73, cached_in=3456, ratio=91.3%

===== PREVIOUS_ID 场景（prev_id）=====
[PREVIOUS_ID] OUTPUT R1: True
[PREVIOUS_ID_R1]  TOKENS: input=3524, output=135, reasoning=128, completion=7, cached_in=0, ratio=94.8%
[PREVIOUS_ID] OUTPUT R2: Because 2 is a smaller number than 10. On the number line, 2 lies to the left of 10; equivalently, 10 − 2 = 8 > 0, so 2 < 10.
[PREVIOUS_ID_R2]  TOKENS: input=3540, output=310, reasoning=256, completion=54, cached_in=3456, ratio=82.6%

=== 表1: ALL模式 Token 数据 ===
场景                    | input_tokens | output_tokens | reasoning_tokens | completion_tokens | cached_tokens | reasoning_ratio
BASIC_R1                | 3515         | 346           | 320              | 26                | 0             | 92.5%
BASIC_R2                | 3549         | 212           | 192              | 20                | 3456          | 90.6%
FUNCTION_R1             | 3637         | 225           | 192              | 33                | 0             | 85.3%
FUNCTION_R2             | 3934         | 25            | 0                | 25                | 3840          | 0.0%
ENCRYPTED_R1_store_False | 3519         | 789           | 704              | 85                | 0             | 89.2%
ENCRYPTED_R2_store_False | 4316         | 408           | 384              | 24                | 3456          | 94.1%
ENCRYPTED_R1_store_True | 3519         | 1305          | 1216             | 89                | 0             | 93.2%
ENCRYPTED_R2_store_True | 3617         | 290           | 256              | 34                | 0             | 88.3%
SUMMARY_R1              | 3519         | 1883          | 1536             | 347               | 0             | 81.6%
SUMMARY_R2              | 3880         | 841           | 768              | 73                | 3456          | 91.3%
PREVIOUS_ID_R1          | 3524         | 135           | 128              | 7                 | 0             | 94.8%
PREVIOUS_ID_R2          | 3540         | 310           | 256              | 54                | 3456          | 82.6%

===== AB 测试（全部使用 prev_id）=====
[AB] effort=minimal, summary=none, case=R1, OUTPUT: Sunlight contains all colors. As it passes through the atmosphere, tiny air molecules scatter shorter (bluer) wavelengths much more than longer (redder) ones—a 
[AB-minimal-none-R1]  TOKENS: input=3522, output=69, reasoning=0, completion=69, cached_in=0, ratio=0.0%
[AB] effort=minimal, summary=none, case=R2(prev_id), OUTPUT: Air molecules scatter shorter blue wavelengths of sunlight more than red (Rayleigh scattering), so scattered blue light reaches us from all directions, making t
[AB-minimal-none-R2]  TOKENS: input=3598, output=38, reasoning=0, completion=38, cached_in=0, ratio=0.0%
[AB] effort=minimal, summary=auto, case=R1, OUTPUT: Sunlight contains many colors. As it passes through Earth’s atmosphere, tiny air molecules scatter shorter (bluer) wavelengths much more than longer (redder) on
[AB-minimal-auto-R1]  TOKENS: input=3522, output=87, reasoning=0, completion=87, cached_in=0, ratio=0.0%
[AB] effort=minimal, summary=auto, case=R2(prev_id), OUTPUT: Air molecules scatter shorter (blue) wavelengths of sunlight more than longer ones (Rayleigh scattering), so the sky looks blue; at sunrise/sunset, blue is scat
[AB-minimal-auto-R2]  TOKENS: input=3616, output=49, reasoning=0, completion=49, cached_in=3456, ratio=0.0%
[AB] effort=minimal, summary=detailed, case=R1, OUTPUT: Sunlight contains many colors. As it passes through the atmosphere, tiny molecules scatter shorter wavelengths (blue) much more than longer ones (red)—a process
[AB-minimal-detailed-R1]  TOKENS: input=3522, output=59, reasoning=0, completion=59, cached_in=0, ratio=0.0%
[AB] effort=minimal, summary=detailed, case=R2(prev_id), OUTPUT: Blue light from the sun is scattered more by air molecules (Rayleigh scattering), so the sky appears blue.
[AB-minimal-detailed-R2]  TOKENS: input=3588, output=28, reasoning=0, completion=28, cached_in=3456, ratio=0.0%
[AB] effort=low, summary=none, case=R1, OUTPUT: Because sunlight hits air molecules and tiny particles, shorter blue wavelengths scatter in all directions more than longer red ones (Rayleigh scattering). That
[AB-low-none-R1]  TOKENS: input=3522, output=73, reasoning=0, completion=73, cached_in=0, ratio=0.0%
[AB] effort=low, summary=none, case=R2(prev_id), OUTPUT: Blue light scatters more than other colors when sunlight passes through the atmosphere (Rayleigh scattering), so we see a blue sky. At sunrise and sunset, the l
[AB-low-none-R2]  TOKENS: input=3602, output=50, reasoning=0, completion=50, cached_in=3456, ratio=0.0%
[AB] effort=low, summary=auto, case=R1, OUTPUT: Because air molecules scatter shorter (bluer) wavelengths of sunlight more efficiently than longer (red) wavelengths. This Rayleigh scattering sends blue light 
[AB-low-auto-R1]  TOKENS: input=3522, output=65, reasoning=0, completion=65, cached_in=0, ratio=0.0%
[AB] effort=low, summary=auto, case=R2(prev_id), OUTPUT: Air molecules Rayleigh-scatter short (blue) wavelengths more than red, so the sky looks blue.
[AB-low-auto-R2]  TOKENS: input=3594, output=91, reasoning=64, completion=27, cached_in=3456, ratio=70.3%
[AB] effort=low, summary=detailed, case=R1, OUTPUT: Sunlight has many colors. Air molecules scatter shorter wavelengths (blue) much more than longer ones—a process called Rayleigh scattering—so the scattered ligh
[AB-low-detailed-R1]  TOKENS: input=3522, output=67, reasoning=0, completion=67, cached_in=0, ratio=0.0%
[AB] effort=low, summary=detailed, case=R2(prev_id), OUTPUT: Because air molecules Rayleigh-scatter shorter wavelengths more strongly, blue light is scattered across the sky; at sunrise and sunset, the longer path removes
[AB-low-detailed-R2]  TOKENS: input=3596, output=106, reasoning=64, completion=42, cached_in=3456, ratio=60.4%
[AB] effort=medium, summary=none, case=R1, OUTPUT: Because of Rayleigh scattering: air molecules scatter shorter wavelengths of sunlight (blue/violet) much more than longer ones. Our eyes are more sensitive to b
[AB-medium-none-R1]  TOKENS: input=3522, output=209, reasoning=128, completion=81, cached_in=0, ratio=61.2%
[AB] effort=medium, summary=none, case=R2(prev_id), OUTPUT: Rayleigh scattering makes short wavelengths scatter most; blue dominates because our eyes are more sensitive to it and violet is partly absorbed.
[AB-medium-none-R2]  TOKENS: input=3610, output=159, reasoning=128, completion=31, cached_in=3456, ratio=80.5%
[AB] effort=medium, summary=auto, case=R1, OUTPUT: Because of Rayleigh scattering: air molecules scatter shorter wavelengths of sunlight (blue/violet) much more than longer ones. The scattered light we see from 
[AB-medium-auto-R1]  TOKENS: input=3522, output=327, reasoning=256, completion=71, cached_in=0, ratio=78.3%
[AB] effort=medium, summary=auto, case=R2(prev_id), OUTPUT: Air molecules Rayleigh-scatter short wavelengths most, so the sky looks blue; violet is less visible to our eyes and partly absorbed.
[AB-medium-auto-R2]  TOKENS: input=3600, output=225, reasoning=192, completion=33, cached_in=3456, ratio=85.3%
[AB] effort=medium, summary=detailed, case=R1, OUTPUT: Because of Rayleigh scattering: air molecules scatter short-wavelength sunlight much more than long wavelengths. Violet scatters the most, but our eyes are less
[AB-medium-detailed-R1]  TOKENS: input=3522, output=310, reasoning=256, completion=54, cached_in=0, ratio=82.6%
[AB] effort=medium, summary=detailed, case=R2(prev_id), OUTPUT: Rayleigh scattering: air molecules scatter short wavelengths more; violet is less seen/partly absorbed, so the sky looks blue.
[AB-medium-detailed-R2]  TOKENS: input=3583, output=160, reasoning=128, completion=32, cached_in=3456, ratio=80.0%
[AB] effort=high, summary=none, case=R1, OUTPUT: The sky looks blue because air molecules scatter shorter-wavelength sunlight (Rayleigh scattering) more than longer wavelengths. Violet scatters even more, but 
[AB-high-none-R1]  TOKENS: input=3522, output=377, reasoning=320, completion=57, cached_in=0, ratio=84.9%
[AB] effort=high, summary=none, case=R2(prev_id), OUTPUT: Air molecules scatter short-wavelength sunlight more (Rayleigh scattering), and we perceive the scattered light as blue.
[AB-high-none-R2]  TOKENS: input=3586, output=284, reasoning=256, completion=28, cached_in=3456, ratio=90.1%
[AB] effort=high, summary=auto, case=R1, OUTPUT: Because of Rayleigh scattering: air molecules scatter shorter wavelengths of sunlight much more strongly than longer ones. Blue light is scattered across the sk
[AB-high-auto-R1]  TOKENS: input=3522, output=261, reasoning=192, completion=69, cached_in=3456, ratio=73.6%
[AB] effort=high, summary=auto, case=R2(prev_id), OUTPUT: Rayleigh scattering: the atmosphere scatters short wavelengths most, so blue dominates our view; violet is scattered more but is less visible and partly absorbe
[AB-high-auto-R2]  TOKENS: input=3598, output=292, reasoning=256, completion=36, cached_in=3456, ratio=87.7%
[AB] effort=high, summary=detailed, case=R1, OUTPUT: Because of Rayleigh scattering: air molecules scatter shorter wavelengths of sunlight much more than longer ones. Blue and violet light are scattered most, but 
[AB-high-detailed-R1]  TOKENS: input=3522, output=317, reasoning=256, completion=61, cached_in=3456, ratio=80.8%
[AB] effort=high, summary=detailed, case=R2(prev_id), OUTPUT: Rayleigh scattering makes air scatter short wavelengths most; we see blue rather than violet because the Sun emits less violet, ozone absorbs some, and our eyes
[AB-high-detailed-R2]  TOKENS: input=3590, output=362, reasoning=320, completion=42, cached_in=3456, ratio=88.4%

=== 表2: AB测试 Token 数据 ===
effort   | summary              | case   | input_tokens | output_tokens | reasoning_tokens | completion_tokens | cached_tokens | reasoning_ratio
minimal  | none                 | R1     | 3522         | 69            | 0                | 69                | 0             | 0.0%
minimal  | none                 | R2     | 3598         | 38            | 0                | 38                | 0             | 0.0%
minimal  | auto                 | R1     | 3522         | 87            | 0                | 87                | 0             | 0.0%
minimal  | auto                 | R2     | 3616         | 49            | 0                | 49                | 3456          | 0.0%
minimal  | detailed             | R1     | 3522         | 59            | 0                | 59                | 0             | 0.0%
minimal  | detailed             | R2     | 3588         | 28            | 0                | 28                | 3456          | 0.0%
minimal  | identical_dialogue   | R1     | 3526         | 301           | 0                | 301               | 3456          | 0.0%
minimal  | identical_dialogue   | R2     | 3845         | 36            | 0                | 36                | 3456          | 0.0%
minimal  | identical_code       | R1     | 3528         | 163           | 0                | 163               | 0             | 0.0%
minimal  | identical_code       | R2     | 3715         | 114           | 0                | 114               | 3456          | 0.0%
low      | none                 | R1     | 3522         | 73            | 0                | 73                | 0             | 0.0%
low      | none                 | R2     | 3602         | 50            | 0                | 50                | 3456          | 0.0%
low      | auto                 | R1     | 3522         | 65            | 0                | 65                | 0             | 0.0%
low      | auto                 | R2     | 3594         | 91            | 64               | 27                | 3456          | 70.3%
low      | detailed             | R1     | 3522         | 67            | 0                | 67                | 0             | 0.0%
low      | detailed             | R2     | 3596         | 106           | 64               | 42                | 3456          | 60.4%
low      | identical_dialogue   | R1     | 3526         | 361           | 128              | 233               | 0             | 35.5%
low      | identical_dialogue   | R2     | 3777         | 32            | 0                | 32                | 3456          | 0.0%
low      | identical_code       | R1     | 3528         | 201           | 128              | 73                | 0             | 63.7%
low      | identical_code       | R2     | 3625         | 80            | 0                | 80                | 3456          | 0.0%
medium   | none                 | R1     | 3522         | 209           | 128              | 81                | 0             | 61.2%
medium   | none                 | R2     | 3610         | 159           | 128              | 31                | 3456          | 80.5%
medium   | auto                 | R1     | 3522         | 327           | 256              | 71                | 0             | 78.3%
medium   | auto                 | R2     | 3600         | 225           | 192              | 33                | 3456          | 85.3%
medium   | detailed             | R1     | 3522         | 310           | 256              | 54                | 0             | 82.6%
medium   | detailed             | R2     | 3583         | 160           | 128              | 32                | 3456          | 80.0%
medium   | identical_dialogue   | R1     | 3526         | 1241          | 1088             | 153               | 0             | 87.7%
medium   | identical_dialogue   | R2     | 3697         | 167           | 128              | 39                | 3456          | 76.6%
medium   | identical_code       | R1     | 3528         | 394           | 320              | 74                | 0             | 81.2%
medium   | identical_code       | R2     | 3626         | 332           | 256              | 76                | 3456          | 77.1%
high     | none                 | R1     | 3522         | 377           | 320              | 57                | 0             | 84.9%
high     | none                 | R2     | 3586         | 284           | 256              | 28                | 3456          | 90.1%
high     | auto                 | R1     | 3522         | 261           | 192              | 69                | 3456          | 73.6%
high     | auto                 | R2     | 3598         | 292           | 256              | 36                | 3456          | 87.7%
high     | detailed             | R1     | 3522         | 317           | 256              | 61                | 3456          | 80.8%
high     | detailed             | R2     | 3590         | 362           | 320              | 42                | 3456          | 88.4%
high     | identical_dialogue   | R1     | 3526         | 1901          | 1728             | 173               | 0             | 90.9%
high     | identical_dialogue   | R2     | 3717         | 230           | 192              | 38                | 3456          | 83.5%
high     | identical_code       | R1     | 3528         | 1816          | 1728             | 88                | 3456          | 95.2%
high     | identical_code       | R2     | 3640         | 670           | 576              | 94                | 3456          | 86.0%
```



单独执行AB测试：

```
(base) root@linuxworkvm:~# python responses_playbook4.py ab_summary
```

