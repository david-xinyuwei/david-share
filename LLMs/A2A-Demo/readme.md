## A2A Demo on Azure OpenAI

### A2A 快速PoC

参考:

*https://github.com/google/A2A/tree/main/samples/python/agents/semantickernel*

原始repo是针对OpenAI开发的，如果想使用Azure OpenAI，只需要用我repo的 **agent.py** 文件替换原始repo中的对应文件即可。

设置.env范例：

```
AZURE_OPENAI_ENDPOINT="https://ai-xinyuwei8714ai888427144375.openai.azure.com"
AZURE_OPENAI_API_KEY="Al**"
AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o-1120"
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

### 代码分析：

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

## A2A与MCP的类比

首先，A2A与MCP不是冲突，而是分层协作—它们解决的问题根本就不在同一“层”，用网络协议的比喻大概是这样：

• MCP 像 “TCP”：把一台智能体内部（或它对外提供的）“功能/工具”抽象成统一调用格式，让模型能可靠地“打 API 电话”。
• A2A 像 “HTTP”：定义两台真正独立的智能体之间如何发现彼此、交换目标、流式回包、做鉴权。
二者可以同时出现：Agent A 先按 A2A 找到 Agent B → Agent B 内部再用 MCP 去调某个 PDF-QA、SQL-Query、支付网关等工具。

——核心区别与互补——

1. 关注对象
   • MCP：Agent ↔ Tool / 外部资源（“单兵拿武器”）。
   • A2A：Agent ↔ Agent / 多智能体编队（“部队协同作战”）。
   引用①②
2. 消息粒度
   • MCP 消息通常是一次函数调用描述（name、args、schema）+ 可选中间思考。
   • A2A 消息是一个完整任务生命周期：目标、进度事件、子调用、最终结果。
   引用③⑤
3. 发现与治理
   • MCP 默认你已经知道要调哪把“工具”，主要解决“怎么调”。
   • A2A 附带 Agent Card、目录服务、mTLS/OAuth 等，让你先“找到”合适的 Agent，再谈调用。
   引用①④
4. 组合关系
   • A2A 调用链里可以嵌套 MCP：
   (A) 出行规划 Agent ——A2A→ (B) 财务 Agent ——MCP→ 汇率 API。
   • 反过来，一台 Agent 也可以在同一流程里既回复 A2A 消息，又把一些子任务暴露成 MCP 函数。



——有没有重叠？——
• 都基于 JSON（RPC 或变体），字段有点像；
• 都鼓励在 message 中携带 “function schema”；
• 但规范级别、目标场景不同，官方工作组也明确将两者并列为“互补协议”③。
所以它们不是竞争关系，而是可堆叠的两层：
Agent 网络层（A2A）
↕
工具调用层（MCP）

——典型使用场景——
• 只做“模型调工具”——用 MCP 就够。
• 想让多家公司、跨云 Agent 协作——A2A 必不可少；每台 Agent 内部再随意选 MCP、LangChain-Tools、SK-Plugins 等实现工具调用。

