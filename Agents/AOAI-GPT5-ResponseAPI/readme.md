# **在 Azure OpenAI GPT‑5 中使用Responses API：推理链复用、加密、摘要与成本分析**

## **TL;DR**

- **Effort 是决定 reasoning tokens 长度的核心变量**
  - `minimal` Effort 几乎不产生推理链（ratio≈0%），`low` Effort 约 0%~50%，`medium`/`high` 可达 70%~93%。
  - `"summary":"detailed"` 并不会增加 reasoning token 数量。推理长度主要由 Effort 控制。
- **`previous_response_id` 支持跨轮直接复用推理链**
  - 当第二轮 Prompt 与第一轮差异较大（普通多轮问答），模型会复用部分逻辑，但仍生成补充推理链 → 节省有限。
  - 在完全匹配或高度相关的 identical case 下，可直接套用 Round1 推理链：
    - **identical_dialogue**（复述型问题）：低 Effort 可直接到 0 reasoning token，高 Effort 节省达 80%~95%。
    - **identical_code**（代码小改）：节省 30%~65%，更贴近真实业务用例。
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

## 结果展示

#### **表1：多场景推理Tokens数据说明**

| 场景                  | effort | summary  | store | input_tokens | output_tokens | reasoning_tokens | completion_tokens | reasoning_ratio |
| --------------------- | ------ | -------- | ----- | ------------ | ------------- | ---------------- | ----------------- | --------------- |
| BASIC                 | high   | detailed | —     | 10           | 473           | 448              | 25                | 94.7%           |
| FUNCTION              | high   | detailed | —     | 648          | 728           | 704              | 24                | 96.7%           |
| ENCRYPTED_store_False | high   | detailed | False | 442          | 1368          | 1344             | 24                | 98.2%           |
| ENCRYPTED_store_True  | high   | detailed | True  | 452          | 1517          | 1472             | 45                | 97.0%           |
| SUMMARY               | high   | detailed | —     | 14           | 3095          | 2496             | 599               | 80.6%           |
| PREVIOUS_ID           | high   | detailed | —     | 35           | 267           | 192              | 75                | 71.9%           |

1. **BASIC**
   - Effort=high、summary=detailed → 最大化推理链长度，reasoning_ratio 高达 94.7%。
   - 整个输出 448 tokens 都是推理链，Completion 部分仅 25 tokens。
2. **FUNCTION**
   - Effort=high、summary=detailed
   - 高 input_tokens 因 function schema 占用大量输入 token，输出部分 reasoning 占 96.7%。
3. **ENCRYPTED_store_False**
   - Effort=high、summary=detailed、store=False（服务端不保留推理链明文）
   - 仍然生成了 1344 reasoning tokens（比例最高 98.2%），说明加密不减推理链长度。
4. **ENCRYPTED_store_True**
   - Effort=high、summary=detailed、store=True（保留推理链明文 + 返回加密副本）
   - 推理链长达 1472 tokens，completion_tokens 稍多（45），比例 97.0%。
5. **SUMMARY**
   - Effort=high、summary=detailed
   - Completion 增加到 599 tokens（输出解释详细），reasoning_ratio 降到 80.6%。
6. **PREVIOUS_ID**
   - Effort=high、summary=detailed
   - 第二轮调用复用上一轮 reasoning，reasoning_ratio 降到 71.9%，更多 token 用在可见输出（75 tokens）。



#### **表2：AB 对比测试**

| effort  | summary            | case           | input_tokens | output_tokens | reasoning_tokens | completion_tokens | reasoning_ratio |
| ------- | ------------------ | -------------- | ------------ | ------------- | ---------------- | ----------------- | --------------- |
| minimal | none               | normal         | 17           | 68            | 0                | 68                | 0.0%            |
| minimal | auto               | normal         | 17           | 76            | 0                | 76                | 0.0%            |
| minimal | detailed           | normal         | 17           | 91            | 0                | 91                | 0.0%            |
| minimal | detailed           | prev_id_round1 | 17           | 90            | 0                | 90                | 0.0%            |
| minimal | detailed           | prev_id_round2 | 117          | 63            | 0                | 63                | 0.0%            |
| minimal | identical_dialogue | prev_id_round1 | 21           | 469           | 0                | 469               | 0.0%            |
| minimal | identical_dialogue | prev_id_round2 | 508          | 54            | 0                | 54                | 0.0%            |
| minimal | identical_code     | prev_id_round1 | 23           | 221           | 0                | 221               | 0.0%            |
| minimal | identical_code     | prev_id_round2 | 268          | 258           | 0                | 258               | 0.0%            |
| low     | none               | normal         | 17           | 149           | 64               | 85                | 43.0%           |
| low     | auto               | normal         | 17           | 62            | 0                | 62                | 0.0%            |
| low     | detailed           | normal         | 17           | 104           | 0                | 104               | 0.0%            |
| low     | detailed           | prev_id_round1 | 17           | 95            | 0                | 95                | 0.0%            |
| low     | detailed           | prev_id_round2 | 122          | 141           | 64               | 77                | 45.4%           |
| low     | identical_dialogue | prev_id_round1 | 21           | 431           | 64               | 367               | 14.8%           |
| low     | identical_dialogue | prev_id_round2 | 406          | 42            | 0                | 42                | 0.0%            |
| low     | identical_code     | prev_id_round1 | 23           | 311           | 192              | 119               | 61.7%           |
| low     | identical_code     | prev_id_round2 | 166          | 165           | 64               | 101               | 38.8%           |
| medium  | none               | normal         | 17           | 121           | 64               | 57                | 52.9%           |
| medium  | auto               | normal         | 17           | 82            | 0                | 82                | 0.0%            |
| medium  | detailed           | normal         | 17           | 314           | 256              | 58                | 81.5%           |
| medium  | detailed           | prev_id_round1 | 17           | 81            | 0                | 81                | 0.0%            |
| medium  | detailed           | prev_id_round2 | 108          | 191           | 128              | 63                | 67.0%           |
| medium  | identical_dialogue | prev_id_round1 | 21           | 951           | 640              | 311               | 67.3%           |
| medium  | identical_dialogue | prev_id_round2 | 350          | 169           | 128              | 41                | 75.7%           |
| medium  | identical_code     | prev_id_round1 | 23           | 801           | 704              | 97                | 87.9%           |
| medium  | identical_code     | prev_id_round2 | 144          | 423           | 320              | 103               | 75.7%           |
| high    | none               | normal         | 17           | 520           | 448              | 72                | 86.2%           |
| high    | auto               | normal         | 17           | 447           | 384              | 63                | 85.9%           |
| high    | detailed           | normal         | 17           | 585           | 512              | 73                | 87.5%           |
| high    | detailed           | prev_id_round1 | 17           | 383           | 320              | 63                | 83.6%           |
| high    | detailed           | prev_id_round2 | 90           | 378           | 320              | 58                | 84.7%           |
| high    | identical_dialogue | prev_id_round1 | 21           | 2410          | 2240             | 170               | 92.9%           |
| high    | identical_dialogue | prev_id_round2 | 209          | 158           | 128              | 30                | 81.0%           |
| high    | identical_code     | prev_id_round1 | 23           | 1306          | 1216             | 90                | 93.1%           |
| high    | identical_code     | prev_id_round2 | 137          | 866           | 768              | 98                | 88.7%           |

1. **Effort 对 reasoning_tokens 有决定性影响**
   - `minimal` Effort：几乎没有 reasoning token（ratio ≈ 0%），`previous_response_id` 节省空间为零。
   - `low` Effort：存在部分 reasoning（30-60% 比例），不同 summary 模式差异明显。
   - `medium`/`high` Effort：reasoning 占比普遍高（70-90%+），推理链冗长，复用潜力最大。
2. **summary 参数对占比影响忽略不计，但能控制输出结构**
   - auto/none 模式经常使 reasoning_tokens 接近 0（尤其低 Effort）。
   - detailed 模式保留最大化推理链，便于观测节省效果。
3. **previous_response_id 在普通场景（normal/detailed）节省有限**
   - 当第二轮问题与第一轮关联度低，模型会重新推理。
   - medium/high Effort 下 prev_id_round2 与 round1 reasoning 占比接近，节省不明显。
4. **identical 场景才是节省亮点**
   - identical_dialogue（复述型）：低 Effort 直接归零，高 Effort 在 token 个数上可节省 80~95%，占比下降 10%~13%。
   - identical_code（小改型）：节省 30~65%，仍有重新推理需求，占比下降 4%~23%。
5. **重要的双指标解读**
   - **占比变化（ratio change）**：反映推理部分比例的下降幅度（例如 high identical_code: 93.1%→88.7%，-4.4pp）。
   - **绝对节省（absolute saving）**：推理token个数减少百分比（例如 high identical_code: 1216→768，36.8% fewer tokens）。
   - 仅看比例变化会低估节省效果，尤其当输出总tokens也明显缩短时。

#### **表3：previous_response_id模式下 Token 节省效果对比分析表**- 基于A/B test

| Effort  | 场景类型           | Round1 reasoning_ratio | Round2 reasoning_ratio | 比例下降(pp) | Round1 reasoning_tokens | Round2 reasoning_tokens | Token减少比例 |
| ------- | ------------------ | ---------------------- | ---------------------- | ------------ | ----------------------- | ----------------------- | ------------- |
| minimal | identical_dialogue | 0.0%                   | 0.0%                   | 0            | 0                       | 0                       | 0%            |
| minimal | identical_code     | 0.0%                   | 0.0%                   | 0            | 0                       | 0                       | 0%            |
| low     | identical_dialogue | 14.8%                  | 0.0%                   | -14.8        | 64                      | 0                       | **100%**      |
| low     | identical_code     | 61.7%                  | 38.8%                  | -22.9        | 192                     | 64                      | **66.7%**     |
| medium  | identical_dialogue | 67.3%                  | 75.7%                  | +8.4         | 640                     | 128                     | **80.0%**     |
| medium  | identical_code     | 87.9%                  | 75.7%                  | -12.2        | 704                     | 320                     | **54.5%**     |
| high    | identical_dialogue | 92.9%                  | 81.0%                  | -11.9        | 2240                    | 128                     | **94.3%**     |
| high    | identical_code     | 93.1%                  | 88.7%                  | -4.4         | 1216                    | 768                     | **36.8%**     |

**表格字段说明：**

- **Ratio下降(pp)**：Round2推理占比相较Round1下降了多少个百分点（负数表示降低，正数表示反而增加）
- **Token减少比例**：Round2推理token个数相较Round1减少的百分比，是衡量节省效果的核心指标

------

## **主要分析结论**

1. **Effort 决定推理链长度与节省潜力**
   - minimal Effort 下 reasoning_tokens 本来就接近 0 → 无节省空间
   - Effort 越高，Round1 推理链越长，Previous ID 节省出来的 reasoning_tokens 个数越多（特别是 identical 场景下降明显）
2. **任务类型影响节省效果**
   - **identical_dialogue（对话复述型）**
     - 低、中、高 Effort 下都能显著节省推理 token 个数
     - 在 high Effort 下节省比例高达 **94.3%**
     - 这是 previous_response_id 最理想的复用场景
   - **identical_code（代码小改型）**
     - 虽然依赖第一轮推理链，但代码修改仍需模型进行部分局部逻辑推演
     - 节省比例在 **36%~66%** 之间，不会像纯复述那样归零
3. **比例变化 vs. 绝对节省**
   - **比例下降（Reasoning Ratio Change）**：例如 high identical_code 从 93.1% → 88.7% 只下降 4.4 个百分点，看起来不大
   - **绝对节省（Absolute Saving）**：但其 reasoning token 从 1216 → 768，实际减少了 **448 个 token（36.8%）**，这是核心节省量
   - 这两个指标结合看，才能全面反映节省效果：比例变化反映结构变化，绝对节省反映成本节约
4. **真实 vs. 理想节省场景**
   - 理想场景：identical_dialogue（只需复述、零新增信息） → 节省接近 100%
   - 真实场景：identical_code（有小改动、但保留大部分结构） → 节省显著但非 100%，更符合生产中的链条复用方式

------

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

------



## **验证方法**

```
(base) root@linuxworkvm:~# cat responses_playbook4.py  
```

```
import os
import sys
import json
import argparse
from openai import AzureOpenAI

# ===== Azure GPT-5 配置 =====
GPT5_API_KEY = "Al*"
GPT5_ENDPOINT = "https://ai-xinyuwei8714ai888427144375.cognitiveservices.azure.com/"
GPT5_RESPONSES_API_VERSION = "2025-03-01-preview"
GPT5_DEPLOYMENT_NAME = "gpt-5"

COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"

def ensure_key():
    if not GPT5_API_KEY or not GPT5_ENDPOINT or not GPT5_RESPONSES_API_VERSION or not GPT5_DEPLOYMENT_NAME:
        print("Azure GPT-5 config missing"); sys.exit(1)

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
    ct = ot - rt
    ratio = f"{(rt/ot*100):.1f}%" if ot else "0%"
    store_info = f"(store={store_flag})" if store_flag is not None else ""
    print(f"[{tag}] {store_info} TOKENS: input={it}, output={ot}, reasoning={rt}, completion={ct}, ratio={ratio}")

# ===== 基础场景 =====
def cmd_basic():
    print("\n===== BASIC 模式 =====")
    c = client()
    resp = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
        reasoning={"summary": "detailed", "effort": "high"},
        input="tell me a joke"
    )
    print("[BASIC] OUTPUT:", resp.output_text)
    usage = resp.model_dump().get("usage", {})
    print_usage_record("BASIC", usage)
    usage_records_all.append(("BASIC", usage))

def cmd_function():
    print("\n===== FUNCTION 模式 =====")
    c = client()
    tools = [{
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
    context = [{"role": "user", "content": "What's the weather like in Paris today?"}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context, tools=tools,
                               reasoning={"summary": "detailed", "effort": "high"})
    context += resp1.output
    result = "15°C"
    context.append({"type": "function_call_output", "call_id": context[-1].call_id, "output": result})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context, tools=tools,
                               reasoning={"summary": "detailed", "effort": "high"})
    print("[FUNCTION] OUTPUT:", resp2.output_text)
    usage = resp2.model_dump().get("usage", {})
    print_usage_record("FUNCTION", usage)
    usage_records_all.append(("FUNCTION", usage))

def cmd_encrypted(store_flag):
    print(f"\n===== ENCRYPTED 模式 (store={store_flag}) =====")
    c = client()
    context = [{"role": "user", "content": "What's the weather like in Paris today?"}]
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context,
                               store=store_flag, include=["reasoning.encrypted_content"],
                               reasoning={"summary": "detailed", "effort": "high"})
    context += resp1.output
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME, input=context,
                               store=store_flag, include=["reasoning.encrypted_content"],
                               reasoning={"summary": "detailed", "effort": "high"})
    print("[ENCRYPTED] OUTPUT:", resp2.output_text)
    usage = resp2.model_dump().get("usage", {})
    print_usage_record("ENCRYPTED", usage, store_flag=store_flag)
    usage_records_all.append((f"ENCRYPTED_store_{store_flag}", usage))

def cmd_summary():
    print("\n===== SUMMARY 模式 =====")
    c = client()
    resp = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
        input="Explain differences between photosynthesis and respiration.",
        reasoning={"summary": "detailed", "effort": "high"}
    )
    print("[SUMMARY] OUTPUT:", resp.output_text[:200],"...")
    usage = resp.model_dump().get("usage", {})
    print_usage_record("SUMMARY", usage)
    usage_records_all.append(("SUMMARY", usage))

def cmd_previous_id():
    print("\n===== PREVIOUS_ID 模式 =====")
    c = client()
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input="Is 2 less than 10? Answer True or False.",
                               reasoning={"summary": "detailed", "effort": "high"})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input="Explain your previous decision.",
                               previous_response_id=resp1.id,
                               reasoning={"summary": "detailed", "effort": "high"})
    print("[PREVIOUS_ID] OUTPUT:", resp2.output_text)
    usage = resp2.model_dump().get("usage", {})
    print_usage_record("PREVIOUS_ID", usage)
    usage_records_all.append(("PREVIOUS_ID", usage))

# ===== AB 测试 =====
def run_ab_case(effort, summary_mode):
    c = client()
    reasoning_param = {"effort": effort}
    if summary_mode != "none":
        reasoning_param["summary"] = summary_mode
    resp = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                              input="Explain why the sky is blue in a concise way.",
                              reasoning=reasoning_param)
    usage = resp.model_dump().get("usage", {})
    print(f"[AB] effort={effort}, summary={summary_mode}, case=normal, OUTPUT:", resp.output_text)
    print_usage_record(f"AB-{effort}-{summary_mode}-normal", usage)
    usage_records_ab.append((effort, summary_mode, "normal", usage))

def run_prev_id_case_for_effort(effort):
    c = client()
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input="Explain why the sky is blue in a concise way.",
                               reasoning={"summary": "detailed", "effort": effort})
    usage1 = resp1.model_dump().get("usage", {})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input="Explain your previous decision briefly.",
                               previous_response_id=resp1.id,
                               reasoning={"summary": "detailed", "effort": effort})
    usage2 = resp2.model_dump().get("usage", {})
    usage_records_ab.append((effort, "detailed", "prev_id_round1", usage1))
    usage_records_ab.append((effort, "detailed", "prev_id_round2", usage2))

# ===== identical 对话场景 =====
def run_prev_id_identical_dialogue(effort):
    q1 = "曹操厉害还是孙权厉害？请简要说明理由"
    q2 = "请用一句话简要复述你刚才的结论"
    c = client()
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input=q1,
                               reasoning={"summary": "detailed", "effort": effort})
    usage1 = resp1.model_dump().get("usage", {})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input=q2,
                               previous_response_id=resp1.id,
                               reasoning={"summary": "detailed", "effort": effort})
    usage2 = resp2.model_dump().get("usage", {})
    rt1 = usage1.get("output_tokens_details", {}).get("reasoning_tokens", 0)
    rt2 = usage2.get("output_tokens_details", {}).get("reasoning_tokens", 0)
    if rt2 < rt1:
        print(f"{COLOR_GREEN}[Dialogue] Reasoning tokens reduced from {rt1} to {rt2} ({(rt1-rt2)/rt1*100:.1f}% saved){COLOR_RESET}")
    else:
        print(f"{COLOR_RED}[Dialogue] Reasoning tokens did not decrease ({rt1} → {rt2}){COLOR_RESET}")
    usage_records_ab.append((effort, "identical_dialogue", "prev_id_round1", usage1))
    usage_records_ab.append((effort, "identical_dialogue", "prev_id_round2", usage2))

# ===== identical 代码场景 =====
def run_prev_id_identical_code(effort):
    q1 = "写一个Python函数，输入一个列表，返回列表中所有偶数的平方"
    q2 = "在你刚才的代码基础上，增加过滤条件，只保留正偶数的平方"
    c = client()
    resp1 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input=q1,
                               reasoning={"summary": "detailed", "effort": effort})
    usage1 = resp1.model_dump().get("usage", {})
    resp2 = c.responses.create(model=GPT5_DEPLOYMENT_NAME,
                               input=q2,
                               previous_response_id=resp1.id,
                               reasoning={"summary": "detailed", "effort": effort})
    usage2 = resp2.model_dump().get("usage", {})
    rt1 = usage1.get("output_tokens_details", {}).get("reasoning_tokens", 0)
    rt2 = usage2.get("output_tokens_details", {}).get("reasoning_tokens", 0)
    if rt2 < rt1:
        print(f"{COLOR_GREEN}[Code] Reasoning tokens reduced from {rt1} to {rt2} ({(rt1-rt2)/rt1*100:.1f}% saved){COLOR_RESET}")
    else:
        print(f"{COLOR_RED}[Code] Reasoning tokens did not decrease ({rt1} → {rt2}){COLOR_RESET}")
    usage_records_ab.append((effort, "identical_code", "prev_id_round1", usage1))
    usage_records_ab.append((effort, "identical_code", "prev_id_round2", usage2))

# ===== AB 汇总 =====
def cmd_ab_summary():
    print("\n===== AB 测试 =====")
    for eff in ["minimal", "low", "medium", "high"]:
        for summ in ["none", "auto", "detailed"]:
            run_ab_case(eff, summ)
        run_prev_id_case_for_effort(eff)
        run_prev_id_identical_dialogue(eff)
        run_prev_id_identical_code(eff)

# ===== 表格输出 =====
def print_table_all():
    print("\n=== 表1: ALL模式 Token 数据 ===")
    print("场景                    | input_tokens | output_tokens | reasoning_tokens | completion_tokens | reasoning_ratio")
    for name, usage in usage_records_all:
        it = usage.get("input_tokens", 0)
        ot = usage.get("output_tokens", 0)
        rt = usage.get("output_tokens_details", {}).get("reasoning_tokens", 0)
        ct = ot - rt
        ratio = f"{(rt/ot*100):.1f}%" if ot else "0%"
        print(f"{name:<23} | {it:<12} | {ot:<13} | {rt:<16} | {ct:<17} | {ratio}")

def print_table_ab():
    print("\n=== 表2: AB测试 Token 数据 ===")
    print("effort   | summary              | case             | input_tokens | output_tokens | reasoning_tokens | completion_tokens | reasoning_ratio")
    for eff, summ, case, usage in usage_records_ab:
        it = usage.get("input_tokens",0)
        ot = usage.get("output_tokens",0)
        rt = usage.get("output_tokens_details",{}).get("reasoning_tokens",0)
        ct = ot - rt
        ratio = f"{(rt/ot*100):.1f}%" if ot else "0%"
        print(f"{eff:<8} | {summ:<20} | {case:<16} | {it:<12} | {ot:<13} | {rt:<16} | {ct:<17} | {ratio}")

# ===== ALL 模式 =====
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

# ===== 主入口 =====
if __name__ == "__main__":
    ensure_key()
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["basic","function","encrypted_false","encrypted_true",
                                    "summary","previous_id","ab_summary","all"])
    args = p.parse_args()
    if args.mode == "basic": cmd_basic(); print_table_all()
    elif args.mode == "function": cmd_function(); print_table_all()
    elif args.mode == "encrypted_false": cmd_encrypted(store_flag=False); print_table_all()
    elif args.mode == "encrypted_true": cmd_encrypted(store_flag=True); print_table_all()
    elif args.mode == "summary": cmd_summary(); print_table_all()
    elif args.mode == "previous_id": cmd_previous_id(); print_table_all()
    elif args.mode == "ab_summary": cmd_ab_summary(); print_table_ab()
    elif args.mode == "all": cmd_all()
```

完整执行代码：

```
(base) root@linuxworkvm:~# python responses_playbook4.py all
```

单独执行AB测试：

```
(base) root@linuxworkvm:~# python responses_playbook4.py ab_summary
```



### 参考：

https://github.com/openai/openai-cookbook/blob/main/examples/responses_api/reasoning_items.ipynb