## A2A Demo on Azure OpenAI



## 什么是A2A

A2A，全称 Agent-to-Agent（“代理到代理”），是一种允许不同类型、专长各异的AI代理之间直接沟通、任务委托和协作完成工作的协议。

例如，它允许主代理（如个人助理）像项目经理那样，协调一组专业代理的工作。

这样一来，就解决了目前AI代理各自孤立运行的问题，开启了构建复杂多代理协作系统的全新可能性。

根据官方文档，A2A 构建在以下 5 个核心原则之上：

1. **简单性**：充分复用现有的技术标准（HTTP、JSON-RPC、SSE、推送通知等）。
2. **企业级支持**：自带认证、安全、隐私保护、追踪与监控支持。
3. **异步优先**：可以处理非常耗时的任务，并能随时提供有意义的进度更新。
4. **多模态支持**：可支持多种数据模态，包括文本、音频/视频、表单、Iframe 等。
5. **不透明执行**：代理之间无需公开自己的具体思考过程、计划步骤或使用的工具。

你可以把它理解成AI代理们一种标准化的方式：让它们能够相互介绍、说明自己的能力和共同完成任务。

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/A2A-Demo/images/1.png)

接下来，我们看一下组成 A2A 的核心组件有哪些。

## A2A 协议的关键组件

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/A2A-Demo/images/3.png)

A2A 由以下核心组件构成：

- **客户端-服务端模型（Client-Server Model）**：
  A2A 基于客户端-服务端架构，客户端代理请求完成某项任务，服务端（专业代理或工具）执行该任务。不过在任务执行流程中，这些角色可能会动态变化。
- **代理卡片（Agent Cards）**：
  一种 JSON 格式的文件，类似于代理的“个人简介”，包含代理 ID、名字、工作类型、安全细节、MCP支持等信息，用于客户端代理发现合适的专业代理。
- **任务（Task）**：
  任务是 A2A 中工作的基本单位，清晰地分成几个阶段——已提交（submitted）、处理中（working）、待输入（input-required）、已完成（completed）、失败（failed）或已取消（cancelled）。这样有助于有效地管理进度和工作流程。
- **消息结构（Message Structure）**：
  在每个任务中，代理通过消息进行沟通。消息中包含实际内容，这些内容可支持多模态信息格式。
- **产物（Artefacts）**：
  任务输出的最终成果以产物形式交付。这些产物为结构化结果，确保最终输出的一致性和易用性。

💡注意：为保持本文易于理解，这里只涵盖了最基本的部分。详细的深入内容可见[这里](https://composio.dev/blog/mcp-vs-a2a-everything-you-need-to-know/)

搞清楚核心组件后，让我们深入了解整个A2A协议到底如何运作。

## A2A 协议的工作原理

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/A2A-Demo/images/2.png)

### 第一步：代理发现（Agent Discovery）

- 每一个专业代理都会先发布“代理卡片”（类似于代理的简历）。
- 代理卡片列出其能力（例如：“旅行规划”、“预算分析”）。
- 请求任务的代理通过这些代理卡片，发现和选取合适的专业代理。

### 第二步：任务委托（Task Delegation）

- 请求代理将任务委派给被选定的专家代理。
- 委派的任务以自然语言描述，允许更高的灵活度。
- 举个例子：“寻找价格合理的航班与住宿。”
- 专家代理利用自己的智能，解释并执行这些高层次需求。

### 第三步：任务处理（Task Processing，多轮交互）

- 任务有一个生命周期：未开始 (pending) → 运行中 (running) → 中间过程更新 (intermediate updates) → 已完成 (completed)/ 失败 (failed)。
- 请求代理可获得任务收到确认报告、实时跟踪进展、中途获取结果，并持续监测任务最新状态。

### 第四步：任务完成与结果交付（Completion & Delivery）

- 所有任务完成后，请求代理会整理汇集所有的产物（artefacts）。
- 最终产出是一套连贯整合的整体解决方案（例如，一份完整的旅行计划方案）。
- 请求代理可以根据需要对收集到的数据进一步提炼加工，用于展示或后续使用。

多代理之间的无缝协作能实现复杂的工作流。但实际上，多代理系统经常遇到工具不兼容、上下文信息缺失和目标差异等问题。

为了应对这些问题，MCP 提供了有效解决方案。

## 代理发现机制（灵感来源于 OpenID Connect）

那么，这些代理（Agent）是如何彼此互相感知、相互认识的呢？

每个托管代理的组织都会提供一个公开的发现（Discovery）网址，其形式如下：

```
yourdomain.com/.well-known/agent.json
```

这个JSON文件相当于代理的一份个人资料，通常包含：

- 代理的名称与描述
- 已声明的能力（Capabilities）
- 可以处理的示例查询（Queries）
- 支持的模态（Modalities）与通信协议（Protocols）

这种方法的灵感源自于 OpenID Connect 的发现机制（即 `.well-known/openid-configuration`），确保代理之间可以自动相互发现与互操作，而无需依赖紧密耦合或手动配置。

所有这些代理都会使用 `.well-known/agent.json` 文件进行注册，因此，借助于 A2A 协议所提供的标准化消息与协调格式，生态系统中的任何新代理都能够动态地发现、评估并与之互动。



## A2A 与 MCP 对比分析

| 特性     | MCP（模型上下文协议 Model Context Protocol） | A2A（代理间协议 Agent-to-Agent Protocol） |
| -------- | -------------------------------------------- | ----------------------------------------- |
| 通信模式 | 代理 ↔ 外部系统或 API                        | 代理 ↔ 代理                               |
| 目标     | API 集成                                     | 协作与互操作性                            |
| 层次定位 | 后端（数据/API访问层）                       | 中间层（代理网络层）                      |
| 技术标准 | REST、JSON、数据库驱动Driver                 | JSON-RPC、服务（Services）、事件(Events)  |
| 灵感来源 | 语言服务器协议（LSP）                        | OpenID Connect，服务发现机制              |

MCP提供代理执行单独任务所需的工具，而A2A协议则促进代理之间的合作与协同。两者功能互补，确保系统能够有效地执行单项任务，也能协调更复杂、多步骤的流程。

虽然MCP赋予代理完成特定任务所需的工具，A2A则使各个代理互相协作，确保整体体验一致、流畅。

Anthropic公司的MCP协议和Google公司的A2A协议都推动了AI系统与外部组件之间的互动，但它们各自适用的场景与架构有所区别：

| 类别（Category）                   | Anthropic MCP                                                | Google A2A                                                   |
| ---------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| 主要目标（Main Objective）         | 专门用于单个AI模型与外部工具和数据管道的连接。               | 支持跨环境多个自主AI代理之间的互动。                         |
| 最佳适用场景（Best Fit Scenario）  | 适用于需要受控且安全的数据访问的企业级系统。                 | 适合于分布式企业（B2B）场景下多个AI代理的协作需求。          |
| 通信协议（Communication Protocol） | 本地通信：STDIO；远程通信：HTTP及服务端发送事件（SSE），支持实时响应。 | 基于HTTP/HTTPS，同时支持Webhook和SSE，具备异步、可扩展的消息传输能力。 |
| 服务发现（Service Discovery）      | 基于预先固定的服务器配置；连接需手动定义                     | 使用代理卡片（Agent Cards）实现动态发现并连接兼容能力的代理。 |
| 交互模式（Interaction Pattern）    | 自上而下方式——语言模型（LLM）直接访问外部资源。              | 点对点（Peer-to-peer）协作模式，代理间地位平等。             |
| 安全方法（Security Approach）      | 强调代理间跨越信任边界进行安全交互的能力，适用于多代理体系。 | 专注于单一AI模型与外部工具和数据管道的连接安全。             |
| 流程处理（Workflow Handling）      | 为简单直接的请求-响应型流程优化。                            | 专为实现带有状态跟踪和生命周期管理的长期任务设计。           |

### Demo1：Semantic Kernel Agent with A2A Protocol

参考:

https://github.com/google-a2a/a2a-samples/tree/main/samples/python/agents/semantickernel

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/A2A-Demo/images/4.png)

设置.env范例：

```
AZURE_OPENAI_API_KEY="your-azure-api-key-here"
AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME="your-deployment-name"
AZURE_OPENAI_API_VERSION="2024-12-01-preview"
```

Server side：

```
(semantickernel) (base) root@pythonvm:~/A2A/samples/python/agents/semantickernel# uv run .
```

Client side：

```
(base) root@pythonvm:~/A2A/samples/python# uv run hosts/cli --agent http://localhost:10020
======= Agent Card ========
{"name":"SK Travel Agent","description":"Semantic Kernel-based travel agent providing comprehensive trip planning services including currency exchange and personalized activity planning.","url":"http://localhost:10020/","version":"1.0.0","capabilities":{"streaming":true,"pushNotifications":true,"stateTransitionHistory":false},"defaultInputModes":["text"],"defaultOutputModes":["text"],"skills":[{"id":"trip_planning_sk","name":"Semantic Kernel Trip Planning","description":"Handles comprehensive trip planning, including currency exchanges, itinerary creation, sightseeing, dining recommendations, and event bookings using Frankfurter API for currency conversions.","tags":["trip","planning","travel","currency","semantic-kernel"],"examples":["Plan a budget-friendly day trip to Seoul including currency exchange.","What's the exchange rate and recommended itinerary for visiting Tokyo?"]}]}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 请把 1000 美元换算成今日的欧元，并告诉我当前的 USD/EUR 汇率。
Select a file path to attach? (press enter to skip): 
stream event => {"jsonrpc":"2.0","id":"ac4d7acdaa454c4fbc9bccae89afffbd","result":{"id":"baad7e5fd6454c9fa90e7f0ef83d2a87","status":{"state":"working","message":{"role":"agent","parts":[{"type":"text","text":"Building the trip plan..."}]},"timestamp":"2025-05-12T19:46:11.589663"},"final":false}}
stream event => {"jsonrpc":"2.0","id":"ac4d7acdaa454c4fbc9bccae89afffbd","result":{"id":"baad7e5fd6454c9fa90e7f0ef83d2a87","artifact":{"parts":[{"type":"text","text":"当前 USD/EUR 汇率为 1 美元兑换 0.88873 欧元。将 1000 美元换算为欧元的结果是 888.73 欧元。"}],"index":0,"append":false}}}
stream event => {"jsonrpc":"2.0","id":"ac4d7acdaa454c4fbc9bccae89afffbd","result":{"id":"baad7e5fd6454c9fa90e7f0ef83d2a87","status":{"state":"completed","timestamp":"2025-05-12T19:46:12.728531"},"final":true}}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 帮我规划 3 天的京都深度文化之旅，包括寺庙、茶道和清水寺夜景，不需要预算信息。
Select a file path to attach? (press enter to skip): 
stream event => {"jsonrpc":"2.0","id":"9f7491061a90447d95eca574dc9c1672","result":{"id":"2a43b94912d64568a7546138a5f4cbd6","status":{"state":"working","message":{"role":"agent","parts":[{"type":"text","text":"Building the trip plan..."}]},"timestamp":"2025-05-12T19:47:31.118192"},"final":false}}
stream event => {"jsonrpc":"2.0","id":"9f7491061a90447d95eca574dc9c1672","result":{"id":"2a43b94912d64568a7546138a5f4cbd6","artifact":{"parts":[{"type":"text","text":"以下是一个为期三天的京都深度文化之旅行程，包含寺庙参观、茶道体验和清水寺夜景欣赏：\n\n---\n\n**第一天：探索清水寺及其文化魅力**\n- 上午：游览清水寺以及周边古老街区，如三年坂和二年坂。\n- 下午：参观高台寺，并体验其独特的庭院美景和历史氛围。\n- 晚上：欣赏清水寺夜间点灯展现的别样景致。\n\n---\n\n**第二天：深入茶道与传统艺术**\n- 上午：参观金阁寺，欣赏其金光四射的外观与优雅的庭园。\n- 下午：参加京都地区的传统茶道体验，并了解日本茶道的深厚文化。\n- 晚上：漫步祗园地区，感受艺妓文化的深奥与美丽。\n\n---\n\n**第三天：哲学与禅意的探索**\n- 上午：游览银阁寺及其独特的禅意庭园。\n- 下午：沿哲学之道散步，途中体验美丽的风景并接触多个隐秘寺庙如南禅寺。\n- 晚上：放松于京都车站附近，观察现代与传统的交汇。\n\n---\n\n这是一份经过精心设计的深度文化行程，能够有效结合京都的历史与景点特色，希望您喜欢！"}],"index":0,"append":false}}}
stream event => {"jsonrpc":"2.0","id":"9f7491061a90447d95eca574dc9c1672","result":{"id":"2a43b94912d64568a7546138a5f4cbd6","status":{"state":"completed","timestamp":"2025-05-12T19:47:47.272484"},"final":true}}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 我和朋友打算 10 月去首尔 2 天，每人每天预算 120 美元。请先告诉我总预算折算成韩元，然后安排一个性价比高的行程（美食、购物、景点都要）。
Select a file path to attach? (press enter to skip): 
stream event => {"jsonrpc":"2.0","id":"bfd35e00e6e446e4a65d7dc385edf1d0","result":{"id":"69e9be843a464587a1534d009c00bfa1","status":{"state":"working","message":{"role":"agent","parts":[{"type":"text","text":"Building the trip plan..."}]},"timestamp":"2025-05-12T19:48:37.878563"},"final":false}}

stream event => {"jsonrpc":"2.0","id":"bfd35e00e6e446e4a65d7dc385edf1d0","result":{"id":"69e9be843a464587a1534d009c00bfa1","artifact":{"parts":[{"type":"text","text":"**总预算为 240 美元，折算为韩元的结果如下：**\n- 当前汇率：1 美元 = 1400.39 韩元。\n- 换算结果：240 美元 ≈ 336,093.6 韩元。\n\n**2 天的首尔旅行行程安排如下：**\n\n### 第一天：传统与现代的碰撞\n- 上午：\n  - **景福宫** (Gyeongbokgung Palace)：参观首尔最著名的宫殿，费用约 2.5 美元。\n  - **北村韩屋村**：漫步传统韩屋街区，免费参观。\n- 中午：\n  - 午餐于传统餐厅享用参鸡汤，每人约 13 美元。\n- 下午：\n  - **仁寺洞文化街**：购物与观赏当地艺术和手工艺作品。\n- 晚上：\n  - **广藏市场**：选购韩国小吃进行晚餐，预算约 12 美元。\n  - 结束于汉江公园夜景。\n\n### 第二天：潮流与美食结合\n- 上午：\n  - **梨花洞壁画村**：欣赏艺术与拍照打卡。\n  - 逛附近的梨花女子大学校园。\n- 中午：\n  - 午餐附近享用平价韩式拌饭或炸鸡，每人约 8 美元。\n- 下午：\n  - **自由市场与弘大潮流街**：挑选服饰和饰品，购物预算约 40 美元。\n- 晚上：\n  - 晚餐体验韩式烧烤，每人约 20 美元。\n  - 游览南山N首尔塔，感受城市美丽夜景。\n\n希望这份指南能让您的首尔之行充实且愉快！如需调整计划，请随时告知。"}],"index":0,"append":false}}}
stream event => {"jsonrpc":"2.0","id":"bfd35e00e6e446e4a65d7dc385edf1d0","result":{"id":"69e9be843a464587a1534d009c00bfa1","status":{"state":"completed","timestamp":"2025-05-12T19:49:03.634058"},"final":true}}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 
What do you want to send to the agent? (:q or quit to exit): 
```

Server:

```
INFO:     127.0.0.1:37330 - "POST / HTTP/1.1" 200 OK
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling CurrencyExchangeAgent-CurrencyExchangeAgent function with args: {"messages":"请将 1000 美元换算成今日的欧元，并提供当前 USD/EUR 汇率。」"}
INFO:semantic_kernel.functions.kernel_function:Function CurrencyExchangeAgent-CurrencyExchangeAgent invoking.
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=28, prompt_tokens=179, total_tokens=207, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling CurrencyPlugin-get_exchange_rate function with args: {"currency_from":"USD","currency_to":"EUR","date":"latest"}
INFO:semantic_kernel.functions.kernel_function:Function CurrencyPlugin-get_exchange_rate invoking.
INFO:httpx:HTTP Request: GET https://api.frankfurter.app/latest?from=USD&to=EUR "HTTP/1.1 200 OK"
INFO:semantic_kernel.functions.kernel_function:Function CurrencyPlugin-get_exchange_rate succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 0.857762s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=63, prompt_tokens=226, total_tokens=289, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function CurrencyExchangeAgent-CurrencyExchangeAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 4.907472s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:common.server.task_manager:Getting task baad7e5fd6454c9fa90e7f0ef83d2a87
INFO:     127.0.0.1:48532 - "POST / HTTP/1.1" 200 OK
INFO:common.server.task_manager:Upserting task 2a43b94912d64568a7546138a5f4cbd6
INFO:     127.0.0.1:45952 - "POST / HTTP/1.1" 200 OK
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling ActivityPlannerAgent-ActivityPlannerAgent function with args: {"messages":"我想要一个为期三天的旅行计划，专注于京都的文化体验，包括寺庙参观、茶道活动和清水寺的夜景欣赏，请设计一个行程。"}
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent invoking.
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=1081, prompt_tokens=114, total_tokens=1195, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 25.213248s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:common.server.task_manager:Getting task 2a43b94912d64568a7546138a5f4cbd6
INFO:     127.0.0.1:46478 - "POST / HTTP/1.1" 200 OK
INFO:common.server.task_manager:Upserting task 69e9be843a464587a1534d009c00bfa1
INFO:     127.0.0.1:49484 - "POST / HTTP/1.1" 200 OK
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 2 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling CurrencyExchangeAgent-CurrencyExchangeAgent function with args: {"messages": "请帮助我将240美元转换为韩元，并提供当前的美元对韩元汇率。"}
INFO:semantic_kernel.functions.kernel_function:Function CurrencyExchangeAgent-CurrencyExchangeAgent invoking.
INFO:semantic_kernel.kernel:Calling ActivityPlannerAgent-ActivityPlannerAgent function with args: {"messages": "请帮助规划一个为期2天的首尔旅行行程，其中包括美食、购物和景点活动，重点强调高性价比体验。每天预算为每人120美元。"}
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent invoking.
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=29, prompt_tokens=177, total_tokens=206, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling CurrencyPlugin-get_exchange_rate function with args: {"currency_from":"USD","currency_to":"KRW","date":"latest"}
INFO:semantic_kernel.functions.kernel_function:Function CurrencyPlugin-get_exchange_rate invoking.
INFO:httpx:HTTP Request: GET https://api.frankfurter.app/latest?from=USD&to=KRW "HTTP/1.1 200 OK"
INFO:semantic_kernel.functions.kernel_function:Function CurrencyPlugin-get_exchange_rate succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 0.831601s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=70, prompt_tokens=226, total_tokens=296, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function CurrencyExchangeAgent-CurrencyExchangeAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 4.645086s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=1110, prompt_tokens=111, total_tokens=1221, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 31.210555s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:common.server.task_manager:Getting task 69e9be843a464587a1534d009c00bfa1
INFO:     127.0.0.1:40238 - "POST / HTTP/1.1" 200 OK
```

### 调用分析

agent.py 里，总共出现了 3 个真正意义上的 ChatCompletionAgent，外加 1 个工具插件：

1. TravelManagerAgent
   • 角色：总控 / 路由器。
   • 对外暴露为 A2A Server，本体就是启动的 “SK Travel Agent”。
   • 职责：
   – 接收用户请求；
   – 判断是“货币/金额”还是“活动/行程”；
   – 把任务转给下面两个专用代理；
   – 汇总结果，按 A2A 格式流式返回。
2. CurrencyExchangeAgent
   • 角色：货币与预算问题专家。
   • 被注册为 TravelManagerAgent 的一个插件（Skill-Agent）。
   • 内部调用 CurrencyPlugin.get_exchange_rate()，真正触发 Frankfurter API。
   • 只有当用户消息里出现金额、汇率、兑换等关键词时才会被 TravelManager 选中。
3. ActivityPlannerAgent
   • 角色：行程／活动规划专家。
   • 处理除货币之外的一切旅行体验内容：景点、餐饮、课程、门票等。
   • 在你的“火星旅行”对话中，所有回帖都由它生成；因此它两次访问 Azure OpenAI，每轮开销 ~1000 tokens。

———————————————
辅助组件（不是 Agent）：
• CurrencyPlugin
– 一个工具插件（kernel_function）；包含单个函数 get_exchange_rate()。
– 仅被 CurrencyExchangeAgent 调用，不对外暴露。

• ChatHistoryAgentThread
– 用来保存对话历史的线程对象；按 sessionId 复用，重启进程会清零。

———————————————
层次关系
A2A 调用链 = (客户端) → TravelManagerAgent ─┬─> CurrencyExchangeAgent ──> CurrencyPlugin/Frankfurter
└─> ActivityPlannerAgent ──> Azure OpenAI

因此，外部世界只看得到 1 个 A2A Agent（TravelManager）。内部又包含 2 个子智能体，各自负责不同职能。

### 调用结果分析

在上面的调用例子中，三类 Agent 都被按预期触发了。
日志可拆成三段，对应你连续输入的三条 prompt：

┌── 第 1 条 prompt ───────────────────────── “请把 1000 美元换算成今日的欧元……” · TravelManager 收到请求
· 路由到 CurrencyExchangeAgent
· CurrencyExchangeAgent ⇒ CurrencyPlugin.get_exchange_rate()
└─ 日志出现 GET https://api.frankfurter.app/latest?from=USD&to=EUR
· 未调用 ActivityPlannerAgent
→ 只动用「汇率代理」

┌── 第 2 条 prompt ───────────────────────── “帮我规划 3 天京都深度文化之旅……” · TravelManager 路由到 ActivityPlannerAgent
· 日志仅见两次 Azure OpenAI 请求，没有 Frankfurter GET
→ 只动用「行程规划代理」

┌── 第 3 条 prompt ───────────────────────── “首尔 2 天，每人每天预算 120 美元…” · TravelManager 同时识别到“货币 + 行程”
· 日志显示 parallel 调用 2 个 tool call：
① CurrencyExchangeAgent ⇒ CurrencyPlugin（USD→KRW）→ Frankfurter GET
② ActivityPlannerAgent ⇒ Azure OpenAI（行程生成）
→ 两个子代理都被激活，结果在 CLI 合并返回

因此：

• TravelManagerAgent：三轮都在工作（对外唯一 A2A 服务端）。
• CurrencyExchangeAgent：在第 1、3 条 prompt 中被调用。
• ActivityPlannerAgent：在第 2、3 条 prompt 中被调用。
• CurrencyPlugin / Frankfurter API：在两次涉及汇率的任务中被调用。

总结：此次试验充分验证了路由逻辑；所有子代理在合适的语境下都被调动起来，功能正常。



