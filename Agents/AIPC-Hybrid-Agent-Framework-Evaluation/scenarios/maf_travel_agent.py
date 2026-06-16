"""
Travel Planning Agent — Microsoft Agent Framework + Ollama

Scenario: plan a 3-day trip to Shanghai with a local SLM through MAF's real
OllamaChatClient provider.

What this proves:
    1. MAF can wrap a local Ollama model through a provider client.
    2. Tools are registered on the Agent, not hand-rolled as raw OpenAI schemas.
    3. The same Agent abstraction can later swap to OpenAIChatClient,
         OpenAIChatCompletionClient, FoundryChatClient, or FoundryLocalClient.

What this does not prove yet:
    - Durable WorkflowBuilder checkpointing / RequestInfoExecutor HITL.
    - Hyperlight sandbox execution. That needs Windows host WHP/hypervisor support.
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Tool functions ───────────────────────────────────────────────────

def get_weather(city: str) -> dict:
    return {
        "city": city,
        "forecast": [
            {"date": "Day 1", "weather": "Sunny, 28°C", "suggestion": "Outdoor"},
            {"date": "Day 2", "weather": "Cloudy, 25°C", "suggestion": "Indoor"},
            {"date": "Day 3", "weather": "Light rain, 23°C", "suggestion": "Shopping"},
        ]
    }

def search_flights(origin: str, destination: str) -> list:
    return [
        {"airline": "China Eastern", "departure": "08:00", "arrival": "10:30", "price": 1280},
        {"airline": "Air China", "departure": "12:00", "arrival": "14:20", "price": 1450},
        {"airline": "Spring Airlines", "departure": "06:30", "arrival": "09:00", "price": 680},
    ]

def search_hotels(city: str) -> list:
    return [
        {"name": "JW Marriott", "price_per_night": 1200, "rating": 4.8},
        {"name": "Holiday Inn Pudong", "price_per_night": 580, "rating": 4.3},
        {"name": "Hanting Hotel", "price_per_night": 280, "rating": 4.0},
    ]

# ── Real MAF Agent ───────────────────────────────────────────────────
# This uses agent_framework.ollama.OllamaChatClient, not the raw OpenAI SDK.
# For cloud routing, swap the provider client to OpenAIChatClient
# (Responses API) or OpenAIChatCompletionClient (Chat Completions).

async def main():
    from agent_framework.ollama import OllamaChatClient

    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

    print("=" * 60)
    print(f"MAF Travel Agent — REAL OllamaChatClient ({ollama_model})")
    print(f"  Ollama endpoint: {ollama_base}")
    print("  Framework path: agent_framework.ollama.OllamaChatClient.as_agent")
    print("  Boundary: agent/provider proof; workflow checkpoint/HITL is a separate demo")
    print("=" * 60)

    instructions = (
        "你是一个旅行规划助手。请按以下步骤规划：\n"
        "1. 用 get_weather 查目的地天气\n"
        "2. 用 search_flights 搜机票\n"
        "3. 用 search_hotels 搜酒店\n"
        "4. 综合以上信息，用中文给出完整旅行计划和费用预估。"
    )

    client = OllamaChatClient(host=ollama_base, model=ollama_model)
    agent = client.as_agent(
        name="AIPCTravelAgent",
        instructions=instructions,
        tools=[get_weather, search_flights, search_hotels],
    )

    print("\n▶ Running MAF Agent with local Ollama tool calling...")
    try:
        result = await agent.run("帮我规划下周从北京去上海的3天旅行计划，中等预算。")
    except Exception as exc:
        print("\nRUN FAILED")
        print("Reason:", exc)
        print("Check that Ollama is running and the model supports tool calling.")
        raise

    print(f"\n{'=' * 60}")
    print("FINAL PLAN:")
    print("=" * 60)
    print(getattr(result, "text", None) or str(result))

    print(f"\n[MAF Agent] Model: {ollama_model} (LOCAL)")
    print("[MAF] Framework-level differentiators to validate separately:")
    print("[MAF]     OpenAIChatClient           → Responses API / hosted tools")
    print("[MAF]     OpenAIChatCompletionClient → Chat Completions compatibility")
    print("[MAF]     OllamaChatClient           → local Ollama provider")
    print("[MAF]     FoundryLocalClient         → local Foundry runtime")
    print("[MAF]     WorkflowBuilder            → durable workflow / HITL semantics")
    print("[MAF]     agent-framework-hyperlight → sandbox, requires WHP/hypervisor support")
    print("[MAF] ✅ C#/.NET + Python — Windows-native, not Python-only")
    print("[MAF] ✅ Foundry Hosted Agents — same code deploys to Azure cloud")
    print("[MAF] ✅ OpenTelemetry built-in — no LangSmith dependency")
    print("[MAF] ✅ WorkflowBuilder — graph orchestration + checkpointing + HITL")


if __name__ == "__main__":
    asyncio.run(main())
