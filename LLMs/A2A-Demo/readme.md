## A2A Demo on Azure OpenAI

Refer to：

https://github.com/google/A2A/tree/main/samples/python/agents/semantickernel

Replace the **agent.py** with my program.

Set .env as my example:

Server端：

```
(semantickernel) (base) root@pythonvm:~/A2A/samples/python/agents/semantickernel# uv run .
```

Client：

```
(base) root@pythonvm:~/A2A/samples/python# uv run hosts/cli --agent http://localhost:10020
======= Agent Card ========
{"name":"SK Travel Agent","description":"Semantic Kernel-based travel agent providing comprehensive trip planning services including currency exchange and personalized activity planning.","url":"http://localhost:10020/","version":"1.0.0","capabilities":{"streaming":true,"pushNotifications":true,"stateTransitionHistory":false},"defaultInputModes":["text"],"defaultOutputModes":["text"],"skills":[{"id":"trip_planning_sk","name":"Semantic Kernel Trip Planning","description":"Handles comprehensive trip planning, including currency exchanges, itinerary creation, sightseeing, dining recommendations, and event bookings using Frankfurter API for currency conversions.","tags":["trip","planning","travel","currency","semantic-kernel"],"examples":["Plan a budget-friendly day trip to Seoul including currency exchange.","What's the exchange rate and recommended itinerary for visiting Tokyo?"]}]}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 我想去火星
Select a file path to attach? (press enter to skip): 
stream event => {"jsonrpc":"2.0","id":"73e24f6385aa465d973da48ec452a7df","result":{"id":"f1feec1f3cf24ab2a4226b355e31f00b","status":{"state":"working","message":{"role":"agent","parts":[{"type":"text","text":"Building the trip plan..."}]},"timestamp":"2025-05-12T19:20:34.474595"},"final":false}}
stream event => {"jsonrpc":"2.0","id":"73e24f6385aa465d973da48ec452a7df","result":{"id":"f1feec1f3cf24ab2a4226b355e31f00b","artifact":{"parts":[{"type":"text","text":"我已经咨询了一位专门负责活动策划的代理，他们提供了关于火星旅行目前可行性与未来发展期望的详细信息。请您查阅，若有其他问题也随时可以取得进一步帮助！"}],"index":0,"append":false}}}
stream event => {"jsonrpc":"2.0","id":"73e24f6385aa465d973da48ec452a7df","result":{"id":"f1feec1f3cf24ab2a4226b355e31f00b","status":{"state":"completed","timestamp":"2025-05-12T19:20:36.099466"},"final":true}}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 那我到底怎么去啊
Select a file path to attach? (press enter to skip): 
stream event => {"jsonrpc":"2.0","id":"19be1b12412d4bc6bf0461afb124060c","result":{"id":"a5d7214361724f589bb9863771f78b27","status":{"state":"working","message":{"role":"agent","parts":[{"type":"text","text":"Building the trip plan..."}]},"timestamp":"2025-05-12T19:21:35.689521"},"final":false}}
stream event => {"jsonrpc":"2.0","id":"19be1b12412d4bc6bf0461afb124060c","result":{"id":"a5d7214361724f589bb9863771f78b27","artifact":{"parts":[{"type":"text","text":"目前火星旅行主要在研究和计划阶段，您可以通过参与模拟基地训练、关注相关航天组织的动态，以及探索地球上的类似火星环境来逐步接近这个目标。如果需要详细的地球类火星体验场所或学习课程，我可以为您安排相关信息。"}],"index":0,"append":false}}}
stream event => {"jsonrpc":"2.0","id":"19be1b12412d4bc6bf0461afb124060c","result":{"id":"a5d7214361724f589bb9863771f78b27","status":{"state":"completed","timestamp":"2025-05-12T19:21:37.004340"},"final":true}}
=========  starting a new task ======== 

What do you want to send to the agent? (:q or quit to exit): 请安排
Select a file path to attach? (press enter to skip): 
stream event => {"jsonrpc":"2.0","id":"fa9fccfc45864ff9a3a4019ee463b657","result":{"id":"178f3c598f3d4e20994793f07a96cb6f","status":{"state":"working","message":{"role":"agent","parts":[{"type":"text","text":"Building the trip plan..."}]},"timestamp":"2025-05-12T19:22:55.112357"},"final":false}}
stream event => {"jsonrpc":"2.0","id":"fa9fccfc45864ff9a3a4019ee463b657","result":{"id":"178f3c598f3d4e20994793f07a96cb6f","artifact":{"parts":[{"type":"text","text":"已经为您推荐了适合体验类火星环境的详细方案，包括地点选择（如美国犹他州的火星沙漠研究站、中国甘肃的模拟基地等）、相关的火星模拟任务以及学习课程。这些将帮助您最真实地感受火星旅行的未来潜力。如需具体安排或预订详情，请随时联系。"}],"index":0,"append":false}}}
stream event => {"jsonrpc":"2.0","id":"fa9fccfc45864ff9a3a4019ee463b657","result":{"id":"178f3c598f3d4e20994793f07a96cb6f","status":{"state":"completed","timestamp":"2025-05-12T19:22:56.626164"},"final":true}}
```

Server:

```
INFO:     Uvicorn running on http://localhost:10020 (Press CTRL+C to quit)
INFO:     127.0.0.1:50112 - "GET /.well-known/agent.json HTTP/1.1" 200 OK
INFO:common.server.task_manager:Upserting task f1feec1f3cf24ab2a4226b355e31f00b
INFO:     127.0.0.1:41086 - "POST / HTTP/1.1" 200 OK
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling ActivityPlannerAgent-ActivityPlannerAgent function with args: {"messages":"你好，能否帮助规划一次去火星的旅行？"}
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent invoking.
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=705, prompt_tokens=83, total_tokens=788, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 13.085413s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:common.server.task_manager:Getting task f1feec1f3cf24ab2a4226b355e31f00b
INFO:     127.0.0.1:46086 - "POST / HTTP/1.1" 200 OK
INFO:common.server.task_manager:Upserting task a5d7214361724f589bb9863771f78b27
INFO:     127.0.0.1:48150 - "POST / HTTP/1.1" 200 OK
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling ActivityPlannerAgent-ActivityPlannerAgent function with args: {"messages":"旅行者需要明确的指导如何实现火星旅行，请重新规划事件并提供当前可能的步骤及推荐建议。"}
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent invoking.
(semantickernel) (base) root@pythonvm:~/A2A/samples/python/agents/semantickernel# uv run .INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=1087, prompt_tokens=95, total_tokens=1182, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 22.029185s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:common.server.task_manager:Getting task a5d7214361724f589bb9863771f78b27
INFO:     127.0.0.1:35970 - "POST / HTTP/1.1" 200 OK
INFO:common.server.task_manager:Upserting task 178f3c598f3d4e20994793f07a96cb6f
INFO:     127.0.0.1:43412 - "POST / HTTP/1.1" 200 OK
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.chat_completion_client_base:processing 1 tool calls in parallel.
INFO:semantic_kernel.kernel:Calling ActivityPlannerAgent-ActivityPlannerAgent function with args: {"messages":"旅行者需要安排与类火星环境相关的活动以及相关的学习课程和模拟基地体验，请提供详细信息和建议。"}
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent invoking.
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:semantic_kernel.connectors.ai.open_ai.services.open_ai_handler:OpenAI usage: CompletionUsage(completion_tokens=1078, prompt_tokens=98, total_tokens=1176, completion_tokens_details=CompletionTokensDetails(accepted_prediction_tokens=0, audio_tokens=0, reasoning_tokens=0, rejected_prediction_tokens=0), prompt_tokens_details=PromptTokensDetails(audio_tokens=0, cached_tokens=0))
INFO:semantic_kernel.functions.kernel_function:Function ActivityPlannerAgent-ActivityPlannerAgent succeeded.
INFO:semantic_kernel.functions.kernel_function:Function completed. Duration: 25.123008s
INFO:httpx:HTTP Request: POST https://ai-xinyuwei8714ai888427144375.openai.azure.com/openai/deployments/gpt-4o-1120/chat/completions?api-version=2024-12-01-preview "HTTP/1.1 200 OK"
INFO:common.server.task_manager:Getting task 178f3c598f3d4e20994793f07a96cb6f
INFO:     127.0.0.1:47330 - "POST / HTTP/1.1" 200 OK
```





