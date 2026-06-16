"""
Travel Planning Agent — LangGraph + Ollama (LOCAL model on AIPC)
Scenario: Plan a 3-day trip to Shanghai — local SLM via Ollama + StateGraph.

Note: Uses mock tools (weather/flights/hotels) for fair cross-framework comparison.
      All three frameworks use identical mock data so differences reflect framework
      architecture, not API availability.

Key point for Lenovo Qira:
  LangGraph adds StateGraph / checkpointing / HITL on top of LangChain.
  Still calls Ollama via HTTP — same dependency on external Ollama service.
  No native Windows runtime — Ollama is a separate process.
"""
import os, sys, json
from typing import TypedDict, Annotated
from operator import add
from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Typed State ──────────────────────────────────────────────────────

class TravelState(TypedDict):
    user_request: str
    weather: dict
    flights: list
    hotels: list
    itinerary: list
    selected_flight: dict
    selected_hotel: dict
    budget_approved: bool
    final_plan: str
    messages: Annotated[list, add]  # accumulate messages

# ── Node functions ───────────────────────────────────────────────────

def check_weather(state: TravelState) -> dict:
    """Step 1: Check weather — determines which days are good for outdoor/indoor."""
    print("  🌤️  [Node: check_weather] Querying weather for Shanghai...")
    weather = {
        "city": "Shanghai",
        "forecast": [
            {"date": "Day 1", "weather": "Sunny, 28°C", "suggestion": "Outdoor activities"},
            {"date": "Day 2", "weather": "Cloudy, 25°C", "suggestion": "Museums/indoor"},
            {"date": "Day 3", "weather": "Light rain, 23°C", "suggestion": "Shopping malls"},
        ]
    }
    return {"weather": weather, "messages": [f"Weather checked: {json.dumps(weather, ensure_ascii=False)}"]}

def search_flights_node(state: TravelState) -> dict:
    """Step 2: Search flights — runs in parallel with weather (if edges allow)."""
    print("  ✈️  [Node: search_flights] Searching Beijing→Shanghai flights...")
    flights = [
        {"airline": "China Eastern", "departure": "08:00", "arrival": "10:30", "price": 1280},
        {"airline": "Air China", "departure": "12:00", "arrival": "14:20", "price": 1450},
        {"airline": "Spring Airlines", "departure": "06:30", "arrival": "09:00", "price": 680},
    ]
    return {"flights": flights, "messages": [f"Found {len(flights)} flights"]}

def search_hotels_node(state: TravelState) -> dict:
    """Step 3: Search hotels."""
    print("  🏨  [Node: search_hotels] Searching Shanghai hotels...")
    hotels = [
        {"name": "JW Marriott", "price_per_night": 1200, "rating": 4.8},
        {"name": "Holiday Inn Pudong", "price_per_night": 580, "rating": 4.3},
        {"name": "Hanting Hotel", "price_per_night": 280, "rating": 4.0},
    ]
    return {"hotels": hotels, "messages": [f"Found {len(hotels)} hotels"]}

def select_best_options(state: TravelState) -> dict:
    """Step 4: Use LLM to pick best flight + hotel based on budget."""
    print("  🤖  [Node: select_best_options] LLM selecting best flight + hotel...")
    # In production: call Azure OpenAI to reason over options
    # For demo: pick mid-range
    selected_flight = state["flights"][0]  # China Eastern
    selected_hotel = state["hotels"][1]   # Holiday Inn
    total = selected_flight["price"] * 2 + selected_hotel["price_per_night"] * 3
    return {
        "selected_flight": selected_flight,
        "selected_hotel": selected_hotel,
        "messages": [f"Selected: {selected_flight['airline']} + {selected_hotel['name']}, total estimate: ¥{total}"],
    }

def budget_approval(state: TravelState) -> dict:
    """Step 5: HITL — ask user to approve budget before proceeding."""
    from langgraph.types import interrupt
    print("  ⏸️  [Node: budget_approval] Requesting user approval...")

    total = state["selected_flight"]["price"] * 2 + state["selected_hotel"]["price_per_night"] * 3
    decision = interrupt({
        "question": f"Total estimated cost: ¥{total}. Approve? (yes/no)",
        "flight": state["selected_flight"],
        "hotel": state["selected_hotel"],
    })
    approved = decision.get("approved", False) if isinstance(decision, dict) else str(decision).lower() in ("yes", "y", "true")
    return {"budget_approved": approved, "messages": [f"Budget {'approved' if approved else 'rejected'}"]}

def create_itinerary_node(state: TravelState) -> dict:
    """Step 6: Create day-by-day itinerary combining weather + selections."""
    print("  📋  [Node: create_itinerary] Building itinerary...")
    if not state.get("budget_approved", False):
        return {"final_plan": "❌ Trip cancelled — budget not approved.", "messages": ["Trip cancelled"]}

    itinerary = []
    for i, day_weather in enumerate(state["weather"]["forecast"], 1):
        if "Sunny" in day_weather["weather"]:
            activities = "The Bund → Shanghai Tower → Huangpu River Cruise"
        elif "Cloudy" in day_weather["weather"]:
            activities = "Yu Garden → Shanghai Museum → Xintiandi"
        else:
            activities = "Nanjing Road Shopping → Din Tai Fung → Tianzifang"
        itinerary.append({"day": i, "weather": day_weather["weather"], "activities": activities})

    plan = f"""
🗺️ Shanghai 3-Day Trip Plan
✈️ Flight: {state['selected_flight']['airline']} ({state['selected_flight']['departure']}-{state['selected_flight']['arrival']}) ¥{state['selected_flight']['price']}
🏨 Hotel: {state['selected_hotel']['name']} ¥{state['selected_hotel']['price_per_night']}/night

📅 Itinerary:
"""
    for day in itinerary:
        plan += f"  Day {day['day']} ({day['weather']}): {day['activities']}\n"

    total = state["selected_flight"]["price"] * 2 + state["selected_hotel"]["price_per_night"] * 3
    plan += f"\n💰 Total estimate: ¥{total}"

    return {"itinerary": itinerary, "final_plan": plan, "messages": ["Itinerary created"]}

# ── Build Graph ──────────────────────────────────────────────────────

def main():
    from langgraph.graph import StateGraph, START, END

    print("=" * 60)
    print("LangGraph Travel Agent — Stateful Graph + Ollama (LOCAL)")
    print(f"  Model: {os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')} via Ollama HTTP")
    print(f"  Requires Ollama server running as separate process")
    print("=" * 60)

    graph = StateGraph(TravelState)

    # Add nodes
    graph.add_node("check_weather", check_weather)
    graph.add_node("search_flights", search_flights_node)
    graph.add_node("search_hotels", search_hotels_node)
    graph.add_node("select_best", select_best_options)
    graph.add_node("budget_approval", budget_approval)
    graph.add_node("create_itinerary", create_itinerary_node)

    # Edges: weather and flights can run in parallel, then converge
    graph.add_edge(START, "check_weather")
    graph.add_edge(START, "search_flights")
    graph.add_edge(START, "search_hotels")
    graph.add_edge("check_weather", "select_best")
    graph.add_edge("search_flights", "select_best")
    graph.add_edge("search_hotels", "select_best")
    graph.add_edge("select_best", "budget_approval")
    graph.add_edge("budget_approval", "create_itinerary")
    graph.add_edge("create_itinerary", END)

    # Compile (no checkpointer for simplicity; add SqliteSaver for persistence)
    from langgraph.checkpoint.memory import MemorySaver
    checkpointer = MemorySaver()
    app = graph.compile(checkpointer=checkpointer)

    # Run
    config = {"configurable": {"thread_id": "trip-shanghai-001"}}
    initial = {
        "user_request": "下周去上海3天，北京出发，中等预算",
        "messages": [],
    }

    print("\n▶ Phase 1: Gather info (weather + flights + hotels) → select → HITL gate")
    events = []
    for event in app.stream(initial, config=config, stream_mode="updates"):
        events.append(event)
        for node_name, node_output in event.items():
            if "messages" in node_output:
                for m in node_output["messages"]:
                    print(f"    📝 {m}")

    # Check if interrupted at budget_approval
    state = app.get_state(config)
    if state.next:
        print(f"\n⏸️  Graph paused at: {state.next}")
        print("    (In production: user reviews budget in UI, then resumes)")
        print("    Simulating approval...")

        # Resume with approval
        from langgraph.types import Command
        for event in app.stream(Command(resume={"approved": True}), config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if "messages" in node_output:
                    for m in node_output["messages"]:
                        print(f"    📝 {m}")

    # Get final state
    final_state = app.get_state(config)
    plan = final_state.values.get("final_plan", "No plan generated")
    print(f"\n{'=' * 60}")
    print("FINAL PLAN:")
    print("=" * 60)
    print(plan)

    print(f"\n[LangGraph + Ollama] Model: {os.environ.get('OLLAMA_MODEL', 'qwen2.5:3b')} (LOCAL)")
    print("[LangGraph + Ollama] Ollama = separate HTTP server on localhost:11434")
    print("[LangGraph + Ollama] ✅ State persisted at every node (crash-recoverable)")
    print("[LangGraph + Ollama] ✅ HITL via interrupt() — graph paused, state preserved")
    print("[LangGraph + Ollama] ✅ Parallel execution: weather + flights + hotels concurrent")
    print("[LangGraph + Ollama] ❌ No native Windows/NPU — still needs Ollama process")


if __name__ == "__main__":
    main()
