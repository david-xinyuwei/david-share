# Foundry Agent Service — Inline Base64 图片大小限制

## 问题

Azure AI Foundry Agent Service 项目端点（`*.services.ai.azure.com`）在 Responses API（`/responses`）中拒绝 inline base64 图片。相同图片在 AOAI 直连端点（`*.openai.azure.com`）正常工作。这是一个已知的 regression，跟踪于 [GitHub #46305](https://github.com/Azure/azure-sdk-for-python/issues/46305)。

## 关键发现

| 发现 | 详情 |
|:---|:---|
| 有效阈值 | ~64KB 请求体（二分搜索：最后通过 65,661B，首次失败 65,725B） |
| AOAI 直连 | 9/9 通过，最大 2.2MB 请求体 |
| `detail` 参数 | 无效果 — `detail` 控制模型端处理，不影响请求体大小 |
| **Workaround: file_id** | 通过 `/openai/v1/files` 上传，在 `/responses` 中引用 `file_id`。8/8 通过（72KB–7.9MB） |
| Workaround: resize | 客户端发送前缩放图片也可行 |
| 外部确认 | [GitHub #46305](https://github.com/Azure/azure-sdk-for-python/issues/46305) — 独立客户报告 |

## 架构

```mermaid
flowchart TB
    IMG["📷 图片 72KB–7.9MB"]

    subgraph broken["❌ Inline Base64 — 已损坏"]
        direction TB
        A1["将图片编码为 base64"]
        A2["POST /responses 带 base64 JSON"]
        A3{"JSON body > ~64KB?"}
        A4["400 invalid_payload\n7/9 图片失败"]
        A5["✅ 模型响应\n2/9 图片通过"]
        A1 --> A2 --> A3
        A3 -- "是" --> A4
        A3 -- "否" --> A5
    end

    subgraph works["✅ file_id 上传 — WORKAROUND"]
        direction TB
        B1["POST /openai/v1/files\nmultipart 上传"]
        B2["获得 file_id"]
        B3["POST /responses\nJSON body ~200 bytes"]
        B4["✅ 模型响应\n8/8 图片通过"]
        B1 --> B2 --> B3 --> B4
    end

    IMG --> A1
    IMG --> B1

    style A4 fill:#d13438,color:#fff
    style A5 fill:#107c10,color:#fff
    style B4 fill:#107c10,color:#fff
    style A3 fill:#ffd93d,color:#333
```

Foundry 项目端点和 AOAI 直连端点共享同一底层模型，但请求处理路径不同。项目端点对 inline base64 图片有 payload 大小限制（~64KB），直连端点没有。

**大小计算公式**：base64 编码会将图片数据膨胀 4/3（33%），加上 ~220 字节 JSON 开销：

```
JSON body 大小 = 图片大小 × 4/3 + ~220 字节
图片大小上限 = (64KB body 限制 - 220 字节) × 3/4 ≈ 48KB
```

所以实际限制约为**原始图片 48KB**（不是 64KB — 64KB 是 JSON body 限制，不是图片限制）。

切换到 AOAI 直连端点（`*.openai.azure.com`）并不总是可行的 — 使用项目端点的应用可能依赖仅通过项目端点提供的能力（如 Bing grounding、agentic tools、failover 逻辑）。

`file_id` workaround 使用的是 Responses API 自身的 `/openai/v1/files` 上传端点。这是 Responses API 的标准功能 — 不特定于任何 Agent 框架。上传走 `multipart/form-data`（不是 JSON），不受 JSON body 大小限制。

## 测试结果

### Agent Service vs AOAI 直连 — Inline Base64

| 图片 (KB) | Base64 (KB) | 请求体 (KB) | Agent Service | AOAI 直连 |
|---:|---:|---:|:---:|:---:|
| 3 | 4 | 4 | PASS | PASS |
| 22 | 29 | 29 | PASS | PASS |
| 109 | 145 | 146 | FAIL 400 | PASS |
| 196 | 261 | 261 | FAIL 400 | PASS |
| 319 | 426 | 426 | FAIL 400 | PASS |
| 566 | 755 | 755 | FAIL 400 | PASS |
| 963 | 1,285 | 1,285 | FAIL 400 | PASS |
| 1,042 | 1,389 | 1,390 | FAIL 400 | PASS |
| 1,995 | 2,659 | 2,660 | FAIL 400 | PASS |

Agent Service: 2/9 通过（仅 body <64KB）。AOAI 直连: 9/9 全通过。

错误: `400 invalid_payload: "The provided data does not match the expected schema"` — 当 inline base64 图片数据超过大小限制时返回。

### 精确阈值（二分搜索，Binary Search）

| 请求体大小 | 结果 |
|---:|:---|
| 65,533 B (64.0 KB) | PASS |
| 65,661 B (64.1 KB) | **PASS** ← 最后通过 |
| 65,725 B (64.2 KB) | **FAIL** ← 首次失败 |
| 66,557 B (65.0 KB) | FAIL |

### Body 大小 vs 图片数据

发送 500KB **纯文本**请求体（无图片）到 Agent Service：**通过**。限制专门针对 inline base64 图片数据，不是总请求体大小。

### file_id Workaround — 全尺寸矩阵

通过 `/openai/v1/files` 上传图片（purpose=`assistants`），然后在 `/responses` 中引用 `file_id`：

| 图片 | 大小 | Inline Base64 | file_id |
|:---|:---|:---|:---|
| 合成图 | 72 KB | FAIL 400 | **PASS** |
| 合成图 | 249 KB | FAIL 400 | **PASS** |
| 合成图 | 877 KB | FAIL 400 | **PASS** |
| 合成图 | 2.2 MB | FAIL 400 | **PASS** |
| 合成图 | 3.9 MB | FAIL 400 | **PASS** |
| 合成图 | 7.9 MB | FAIL 400 | **PASS** |
| 真实照片 1 | 238 KB | FAIL 400 | **PASS** |
| 真实照片 2 | 220 KB | FAIL 400 | **PASS** |

8/8 通过 file_id，在同一 Foundry 端点。对照组：inline base64 5/5 全部 FAIL。

## Workaround

### 方案 1: file_id 上传（推荐）

保持 Foundry 项目端点不变 — 不丢失 agentic 层、Bing 连接器或 failover 逻辑。只改图片输入方式，其他代码不变。

**改前 vs 改后**：

```diff
  # 你现有的客户端设置（不变）
  client = project.get_openai_client()  # 或者你获取 OpenAI client 的方式

+ # 新增：先上传图片
+ file = client.files.create(file=open("photo.jpg", "rb"), purpose="assistants")

  response = client.responses.create(
      model="gpt-4o-mini",
      input=[{"role": "user", "content": [
          {"type": "input_text", "text": "Describe this image"},
-         {"type": "input_image", "image_url": "data:image/jpeg;base64,..."}
+         {"type": "input_image", "file_id": file.id}
      ]}],
  )
```

就这么多。改两行。

**完整 Python 示例**：

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project = AIProjectClient(
    endpoint="https://RESOURCE.services.ai.azure.com/api/projects/PROJECT",
    credential=DefaultAzureCredential(),
)
client = project.get_openai_client()

# Step 1: 上传图片（绕过 inline base64 大小限制）
file = client.files.create(file=open("photo.jpg", "rb"), purpose="assistants")

# Step 2: 在 responses.create 中使用 file_id（替换 inline base64）
response = client.responses.create(
    model="gpt-4o-mini",
    input=[{"role": "user", "content": [
        {"type": "input_text", "text": "Describe this image"},
        {"type": "input_image", "file_id": file.id}
    ]}],
)
print(response.output_text)
```

**完整 Node.js / TypeScript 示例**：

```javascript
const { AIProjectClient } = require("@azure/ai-projects");
const { DefaultAzureCredential } = require("@azure/identity");
const fs = require("fs");

const project = new AIProjectClient(PROJECT_ENDPOINT, new DefaultAzureCredential());
const client = await project.getOpenAIClient();

// Step 1: 上传图片
const file = await client.files.create({
  file: fs.createReadStream("photo.jpg"),
  purpose: "assistants"
});

// Step 2: 使用 file_id（替换 inline base64）
const response = await client.responses.create({
  model: "gpt-4o-mini",
  input: [{ role: "user", content: [
    { type: "input_text", text: "Describe this image" },
    { type: "input_image", file_id: file.id }
  ]}]
});
console.log(response.output_text);
```

### 方案 2: 客户端 Resize

GPT-4o-mini `detail:auto` 最大处理 2048×2048 像素。发送前缩放可减少请求体大小，对模型理解质量零影响。

```python
from PIL import Image
from io import BytesIO
import base64

def resize_for_foundry(image_path, max_body_kb=60, max_width=1024, max_height=1024):
    with open(image_path, 'rb') as f:
        raw = f.read()
    max_image_bytes = int((max_body_kb - 1) * 1024 * 3 / 4)
    if len(raw) <= max_image_bytes:
        return base64.b64encode(raw).decode()
    img = Image.open(BytesIO(raw))
    img.thumbnail((max_width, max_height), Image.LANCZOS)
    quality = 80
    for _ in range(5):
        buf = BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=quality)
        if len(buf.getvalue()) <= max_image_bytes:
            return base64.b64encode(buf.getvalue()).decode()
        quality -= 10
    return base64.b64encode(buf.getvalue()).decode()
```

**Bash 集成**:
```bash
# 之前（大图失败）:
base64 < "$IMAGE_FILE" | tr -d '\n' | jq ...

# 之后（始终可用）:
python workaround_resize_python.py "$IMAGE_FILE" | jq ...
```

## 为什么 file_id 有效

Responses API 支持两种传图方式：

1. **Inline base64**（`image_url: "data:image/jpeg;base64,..."`）— 图片嵌入 JSON 请求体。在 Foundry 项目端点上，这个 body 受 ~64KB 大小限制。

2. **file_id 引用**（`file_id: "assistant-xxx"`）— 图片先通过 `POST /openai/v1/files` 以 `multipart/form-data` 上传（不是 JSON）。`/responses` 请求体只包含短小的 file_id 字符串（~50 bytes）。图片二进制永远不会进入 JSON payload。

`/openai/v1/files` 是 Responses API 的标准端点。它不特定于任何 Agent 框架 — 无论应用是否使用 agentic 功能，工作方式都一样。

## 外部证据

- [GitHub #46305](https://github.com/Azure/azure-sdk-for-python/issues/46305) — 独立客户确认 regression: "This scenario worked for us about one week ago." 通过 Python / C# / raw REST 复现。
- [MS Q&A 5859143](https://learn.microsoft.com/en-us/answers/questions/5859143/) — 同一报告者在 Q&A 平台
- [Responses API 文档](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses) — base64 data URL 是官方支持的输入方式，未记录大小限制

## 复现

### 前置条件

```bash
pip install azure-ai-projects azure-identity Pillow
export FOUNDRY_KEY="<your-key>"
export AOAI_KEY="<your-key>"
```

### 运行测试

```bash
# Agent Service vs AOAI 直连对比
python scripts/test_agent_service_image.py

# 精确阈值二分搜索
python scripts/find_threshold.py

# 验证 resize workaround
python scripts/verify_resize_workaround.py
```

### 脚本清单

| 脚本 | 用途 |
|:---|:---|
| `test_agent_service_image.py` | Agent Service vs AOAI 直连对比 |
| `find_threshold.py` | 精确 body 大小阈值二分搜索 |
| `verify_resize_workaround.py` | Resize workaround 验证 |
| `workaround_resize_python.py` | Python 客户端 resize（bash pipe 兼容） |
| `workaround_resize_node.js` | Node.js 客户端 resize |

---

*Author: Xinyu Wei — Azure AI Global Black Belt*
