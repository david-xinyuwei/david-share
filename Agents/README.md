# AI Agents

Projects on building, hosting and operating AI agents, and on the models, APIs and gateways they call. Most run on Microsoft Foundry and Azure. Each folder is a self-contained project with its own README.

[Back to the main page](../README.md)

- [Build, host and operate agents on Microsoft Foundry](#build-host-and-operate-agents-on-microsoft-foundry)
- [Agent applications and frameworks](#agent-applications-and-frameworks)
- [Voice agents](#voice-agents)
- [Models, APIs and gateways on Azure](#models-apis-and-gateways-on-azure)
- [Retrieval, evaluation and safety](#retrieval-evaluation-and-safety)
- [Archive](#archive)

## Build, host and operate agents on Microsoft Foundry

| Project | What it covers |
|---|---|
| [Foundry-Agent-Lifecycle-Build-Deploy-Operate](Foundry-Agent-Lifecycle-Build-Deploy-Operate/) | The agent lifecycle announced at Build 2026: build locally with any framework, deploy as a hosted agent, operate with tracing and evaluation |
| [Foundry-Hosted-Agent-Toolbox-Demo](Foundry-Hosted-Agent-Toolbox-Demo/) | Hosted agent with Toolbox, Memory and Skills: a recorded walkthrough of building, testing, evaluating, tracing and governing the agent |
| [Foundry-Long-Running-Agent-Resilience](Foundry-Long-Running-Agent-Resilience/) | Recovering a hosted agent after process loss: 8 of 8 measured interruption-recovery scenarios and the client reattach contract |
| [Azure-Agent-Sandbox-Hosting](Azure-Agent-Sandbox-Hosting/) | Five ways to host an agent sandbox on Azure: ACA Sandboxes, Foundry hosted agent, AKS + agent-sandbox, BYO-AKS and E2B on an Azure VM |
| [Foundry-Agent-ModelOps-Governance](Foundry-Agent-ModelOps-Governance/) | One operational plane for the models behind agents: improve, deploy, call, monitor and attribute cost |
| [AI-Foundry-Agent-VNET-Deployment](AI-Foundry-Agent-VNET-Deployment/) | Foundry Agent Service with a bring-your-own VNET: deployment scripts, verification tools and the scope of network isolation |
| [AI-Agent-Private-Endpoint](AI-Agent-Private-Endpoint/) | Step-by-step network hardening of a Foundry project with private endpoints |
| [Foundry-Agent-Service-Image-Size-Limit](Foundry-Agent-Service-Image-Size-Limit/) | Inline base64 image limit on the Foundry Agent Service project endpoint, compared with the Azure OpenAI endpoint |
| [Azure-Agent-Skills-In-Action](Azure-Agent-Skills-In-Action/) | Evidence-first review of the Agent Skills ecosystem, using Azure as the live test bed |
| [Deep-Research-Usage](Deep-Research-Usage/) | Azure Deep Research setup with service principal authentication and multi-turn conversations |
| [Hyperlight-MXC-Sandbox-Landscape](Hyperlight-MXC-Sandbox-Landscape/) | Hyperlight and MXC, the Windows agent trust platform from Build 2026, with Windows smoke-test results |
| [AIPC-Hybrid-Agent-Framework-Evaluation](AIPC-Hybrid-Agent-Framework-Evaluation/) | Two paths to Windows-native local agent execution on an AI PC: an Agent Framework loop versus MXC with a runtime backend |

## Agent applications and frameworks

| Project | What it covers |
|---|---|
| [Thermal-3D-Modeling-Studio](Thermal-3D-Modeling-Studio/) | Azure OpenAI GPT-6 Astra writes a three.js concept model or a CadQuery script, and OpenCascade turns the script into a STEP solid; includes scripted Azure deployment and tests |
| [Meeting-Agent](Meeting-Agent/) | Provider-neutral meeting pipeline with Azure OpenAI structured analysis, traceable artifacts and human-controlled New Outlook drafts |
| [M365-Morning-Sweep](M365-Morning-Sweep/) | Executive-assistant agent: Microsoft Graph and Azure OpenAI briefings of M365 email, calendar and chat with a live dashboard |
| [Microsoft-Agent-Framework](Microsoft-Agent-Framework/) | Microsoft Agent Framework workflows: a human-in-the-loop pipeline and MagenticBuilder orchestration |
| [A2A-Demo](A2A-Demo/) | Minimal end-to-end demo of A2A-compatible micro-agents cooperating |
| [Azure-MCP-Solution](Azure-MCP-Solution/) | Hands-on guide to using and integrating MCP servers |
| [Agent-Design-Practice](Agent-Design-Practice/) | Agent design practices for speed, cost and reliability |
| [Pi-Agent-OpenClaw-Architecture](Pi-Agent-OpenClaw-Architecture/) | Architecture of Pi, a minimalist coding agent, and OpenClaw, the personal assistant built on it |
| [NemoClaw-on-Azure](NemoClaw-on-Azure/) | NemoClaw on an Azure Linux VM: deployment guide, Azure OpenAI integration and security features |
| [Web-Agent](Web-Agent/) | NLWeb conversational endpoints backed by Azure AI Search |
| [Foundry-Local](Foundry-Local/) | Foundry Local installation and verification on Windows with Open WebUI |

## Voice agents

| Project | What it covers |
|---|---|
| [Voice-Live-Agent](Voice-Live-Agent/) | Chinese-language desktop voice agent on the Voice Live API; its tools run on the user's PC, and three connection modes can be compared side by side |
| [Voice-Live-API-AIPC](Voice-Live-API-AIPC/) | Windows AI PC voice agent: the Voice Live API plus 24 local tools for conversation, camera perception, desktop control, information lookup and allowlisted email |
| [StackChan-Azure-Voice-Assistant](StackChan-Azure-Voice-Assistant/) | Azure backend that turns the StackChan ESP32-S3 desktop robot, on stock firmware, into a voice assistant (demo only) |

For the Voice Live building blocks (speech recognition, models and voices), see the [Azure Voice Live component reference](../Multimodal-Models/Azure-Voice-Live/).

## Models, APIs and gateways on Azure

| Project | What it covers |
|---|---|
| [Model-And-Router-Benchmark](Model-And-Router-Benchmark/) | Three candidate models and Model Router measured for a latency-sensitive assistant across reasoning effort, API path and deployment capacity |
| [Claude-Foundry-LiteLLM-Performance](Claude-Foundry-LiteLLM-Performance/) | Claude Opus, Sonnet and Haiku 5.5 on Microsoft Foundry: thinking, effort, prompt caching, latency and coding accuracy |
| [AOAI-Model-Migration-Benchmark](AOAI-Model-Migration-Benchmark/) | Migrating a low-latency assistant from gpt-4o-mini to newer model families: benchmark and PTU traffic management |
| [gpt4o-to-gpt51-migration](gpt4o-to-gpt51-migration/) | Raw results of an earlier GPT-4o vs GPT-5.1 comparison: 7 scenarios, 5 runs each (January 2026) |
| [AOAI-Priority-Processing-Benchmark](AOAI-Priority-Processing-Benchmark/) | Standard vs Priority Processing pay-as-you-go: measured token generation speed |
| [AOAI-GPT5-ResponseAPI](AOAI-GPT5-ResponseAPI/) | Azure OpenAI GPT-5 Responses API with chain-of-thought reuse and cost analysis |
| [AOAI-APIM-Gateway-LoadBalancing](AOAI-APIM-Gateway-LoadBalancing/) | Multi-region Azure OpenAI load balancing with the APIM AI Gateway: priority and weight routing, circuit breaker, backend pool |
| [Azure-Context-Cache-E2E-Validation](Azure-Context-Cache-E2E-Validation/) | Fail-closed validation of the Azure Context Cache quickstart with real cached-token evidence |
| [Fireworks-on-Azure-Foundry](Fireworks-on-Azure-Foundry/) | Open-weight models on Microsoft Foundry through Fireworks: catalog deployments, bring-your-own-weights upload and benchmarks against Azure-native serving |
| [Fireworks-GLM51-Prompt-Cache-on-Azure](Fireworks-GLM51-Prompt-Cache-on-Azure/) | Which prompt and request settings raise the Fireworks GLM-5.1 prompt-cache hit rate, by how much, and the evidence behind it |

## Retrieval, evaluation and safety

| Project | What it covers |
|---|---|
| [Foundry-IQ](Foundry-IQ/) | Foundry IQ knowledge retrieval with Azure AI Search for agentic RAG |
| [5-ways-chunking](5-ways-chunking/) | Five chunking methods for RAG: principles and code |
| [LLM-Judgment](LLM-Judgment/) | Using LLMs as judges to evaluate other LLMs |
| [AI-Content-Safety](AI-Content-Safety/) | Azure AI Content Safety for text, image and video moderation |

## Archive

These projects stay in place so existing links keep working. The models, APIs or tool versions they use have since been superseded; check current documentation before reusing the steps.

| Project | What it covered |
|---|---|
| [AzureOpenAI-HA](AzureOpenAI-HA/) | Azure OpenAI failover with custom scripts; for the gateway approach, see [AOAI-APIM-Gateway-LoadBalancing](AOAI-APIM-Gateway-LoadBalancing/) |
| [Best-practices-for-MaaS-and-SLM](Best-practices-for-MaaS-and-SLM/) | Running Phi-3 small language models on mobile devices, with MaaS practices |
| [Dify-With-AI-Search](Dify-With-AI-Search/) | Dify with Azure AI Search |
| [graphrag](graphrag/) | Microsoft GraphRAG configuration and validation |
| [Magentic-One](Magentic-One/) | Multi-agent tests with Magentic-One |
| [OLM-benchmark-evaluation](OLM-benchmark-evaluation/) | Online LLM benchmark evaluation inspired by optimum-benchmark |
| [Perplexity-test](Perplexity-test/) | Perplexity measurement for evaluating LLMs |
| [Phi-RAG](Phi-RAG/) | RAG with Phi-2/Phi-3, LlamaIndex and ChromaDB |
| [Prompt-Engineer-Examples](Prompt-Engineer-Examples/) | Prompt engineering techniques with examples |
| [RAG-Best-Practice](RAG-Best-Practice/) | RAG with GPT-4 and Azure AI Search |
| [Reasoning-CoT](Reasoning-CoT/) | o1-style reasoning and chain-of-thought training methods |
| [Use-GPT4-as-Translator](Use-GPT4-as-Translator/) | GPT-4 translation quality comparison |
