"""
Travel Planning Agent — LangChain + Ollama (LOCAL model on AIPC)
Scenario: Plan a 3-day trip to Shanghai — runs entirely on local SLM via Ollama.

Note: Uses mock tools (weather/flights/hotels) for fair cross-framework comparison.
      All three frameworks use identical mock data so differences reflect framework
      architecture, not API availability.

Key point for Lenovo Qira:
  LangChain calls Ollama via HTTP (localhost:11434).
  Ollama must be running as a separate server process.
  No native Windows runtime integration — relies on external Ollama service.
"""
import os, sys, json
from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Mock tools ───────────────────────────────────────────────────────

def get_weather(city: str, dates: str = "") -> str:
    """Get weather forecast for a city."""
    return json.dumps({"city": city, "forecast": [
        {"date": "Day 1", "weather": "Sunny, 28°C", "suggestion": "Outdoor activities"},
        {"date": "Day 2", "weather": "Cloudy, 25°C", "suggestion": "Museums/indoor"},
        {"date": "Day 3", "weather": "Light rain, 23°C", "suggestion": "Shopping malls"},
    ]}, ensure_ascii=False)

def search_flights(origin: str, destination: str) -> str:
    """Search available flights."""
    return json.dumps({"flights": [
        {"airline": "China Eastern", "departure": "08:00", "arrival": "10:30", "price": 1280},
        {"airline": "Spring Airlines", "departure": "06:30", "arrival": "09:00", "price": 680},
    ]}, ensure_ascii=False)

def search_hotels(city: str) -> str:
    """Search available hotels."""
    return json.dumps({"hotels": [
        {"name": "Holiday Inn Pudong", "price_per_night": 580, "rating": 4.3},
        {"name": "Hanting Hotel", "price_per_night": 280, "rating": 4.0},
    ]}, ensure_ascii=False)

# ── LangChain + Ollama Agent ─────────────────────────────────────────

def main():
    from langchain_ollama import ChatOllama
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage, ToolMessage

    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")

    print("=" * 60)
    print(f"LangChain Travel Agent — LOCAL Ollama ({ollama_model})")
    print(f"  Ollama endpoint: {ollama_base}")
    print(f"  Requires Ollama server running as separate process")
    print("=" * 60)

    llm = ChatOllama(base_url=ollama_base, model=ollama_model, temperature=0)

    tools = [tool(get_weather), tool(search_flights), tool(search_hotels)]
    llm_with_tools = llm.bind_tools(tools)

    messages = [HumanMessage(content=(
        "帮我规划下周去上海的3天旅行。我从北京出发，中等预算。"
        "请：1) 查天气 2) 搜机票 3) 搜酒店 4) 给出完整计划。"
    ))]

    tool_map = {t.name: t for t in tools}

    for i in range(8):
        print(f"\n--- Iteration {i+1} ---")
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if response.tool_calls:
            for tc in response.tool_calls:
                print(f"  [Tool] {tc['name']}({json.dumps(tc['args'], ensure_ascii=False)[:60]})")
                result = tool_map[tc["name"]].invoke(tc["args"])
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))
        else:
            print(f"\n{'=' * 60}")
            print("FINAL PLAN (from local SLM):")
            print("=" * 60)
            print(response.content[:2000])
            break

    print(f"\n[LangChain + Ollama] Model: {ollama_model} (LOCAL)")
    print("[LangChain + Ollama] Ollama = separate HTTP server on localhost:11434")
    print("[LangChain + Ollama] No native Windows/NPU integration")
    print("[LangChain + Ollama] No built-in checkpointing or HITL")

if __name__ == "__main__":
    main()
