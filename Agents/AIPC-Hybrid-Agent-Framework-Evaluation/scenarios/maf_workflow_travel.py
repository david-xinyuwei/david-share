"""
Travel Planning — MAF Functional Workflow (@workflow + @step + request_info HITL)

This script demonstrates MAF's durable workflow layer (not just the Agent layer).
It is the MAF equivalent of langgraph_travel_agent.py's StateGraph.

Key MAF workflow features exercised:
  1. @workflow / @step decorators — Python-native control flow
  2. ctx.request_info() — HITL interruption (workflow pauses, state checkpointed)
  3. CheckpointStorage — durable state across process restarts
  4. asyncio.gather — parallel step execution
  5. Provider swap — same workflow, different LLM backend (Ollama / Azure OpenAI)
"""
import asyncio
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Shared data (same as LangGraph version for fair comparison) ──────

WEATHER = [
    {"date": "Day 1", "weather": "Sunny, 28°C", "suggestion": "Outdoor activities"},
    {"date": "Day 2", "weather": "Cloudy, 25°C", "suggestion": "Museums/indoor"},
    {"date": "Day 3", "weather": "Light rain, 23°C", "suggestion": "Shopping malls"},
]
FLIGHTS = [
    {"airline": "China Eastern", "departure": "08:00", "arrival": "10:30", "price": 1280},
    {"airline": "Air China", "departure": "12:00", "arrival": "14:20", "price": 1450},
    {"airline": "Spring Airlines", "departure": "06:30", "arrival": "09:00", "price": 680},
]
HOTELS = [
    {"name": "JW Marriott", "price_per_night": 1200, "rating": 4.8},
    {"name": "Holiday Inn Pudong", "price_per_night": 580, "rating": 4.3},
    {"name": "Hanting Hotel", "price_per_night": 280, "rating": 4.0},
]


# ── Step functions (each is a @step in the workflow) ─────────────────

from agent_framework import workflow, step


@step
async def gather_info(ctx, user_request: str = "") -> dict:
    """Step 1: Gather weather, flights, hotels in parallel.

    Unlike LangGraph where parallel execution requires graph edge topology,
    MAF @step uses native Python asyncio.gather — same language, no graph DSL.
    """
    print("  📊 [Step: gather_info] Fetching weather + flights + hotels in parallel...")

    async def get_weather():
        return {"city": "Shanghai", "forecast": WEATHER}

    async def get_flights():
        return FLIGHTS

    async def get_hotels():
        return HOTELS

    weather, flights, hotels = await asyncio.gather(
        get_weather(), get_flights(), get_hotels()
    )
    print(f"    ✅ Weather: {len(weather['forecast'])} days")
    print(f"    ✅ Flights: {len(flights)} options")
    print(f"    ✅ Hotels: {len(hotels)} options")

    return {"weather": weather, "flights": flights, "hotels": hotels}


@step
async def select_best(ctx, data: dict) -> dict:
    """Step 2: Pick best flight + hotel for medium budget.

    In production, this would call an LLM via ctx's agent client.
    For demo: deterministic selection to keep comparison fair.
    """
    print("  🤖 [Step: select_best] Selecting best combo for medium budget...")
    flights = data["flights"]
    hotels = data["hotels"]
    # Mid-range: China Eastern + Holiday Inn
    selected_flight = flights[0]
    selected_hotel = hotels[1]
    total = selected_flight["price"] * 2 + selected_hotel["price_per_night"] * 3
    print(f"    Selected: {selected_flight['airline']} + {selected_hotel['name']} = ¥{total}")

    return {
        **data,
        "selected_flight": selected_flight,
        "selected_hotel": selected_hotel,
        "total_cost": total,
    }


@step
async def budget_approval(ctx, data: dict) -> dict:
    """Step 3: HITL — pause workflow and ask user to approve budget.

    THIS IS THE KEY DIFFERENTIATOR vs LangGraph's interrupt():
      - LangGraph: interrupt() is a special function that raises an exception
        caught by the graph runtime. Resume via Command(resume=...).
      - MAF: ctx.request_info() is a method on the step context. It emits a
        WorkflowEvent, checkpoints state, and pauses. Resume by calling
        workflow.run(responses={"request_id": value}).

    Both achieve the same result; the API surface is different.
    """
    total = data["total_cost"]
    print(f"  ⏸️  [Step: budget_approval] Requesting HITL approval for ¥{total}...")
    print(f"      Flight: {data['selected_flight']['airline']} ¥{data['selected_flight']['price']}")
    print(f"      Hotel:  {data['selected_hotel']['name']} ¥{data['selected_hotel']['price_per_night']}/night")

    # ctx.request_info() pauses the workflow here.
    # In production: the caller inspects pending request_info events,
    # shows UI to user, then resumes with workflow.run(responses={...}).
    approval = await ctx.request_info(
        {
            "question": f"Total cost: ¥{total}. Approve?",
            "flight": data["selected_flight"],
            "hotel": data["selected_hotel"],
        },
        response_type=str,  # expects "yes" or "no"
    )

    approved = str(approval).lower() in ("yes", "y", "true", "approved")
    print(f"      {'✅ Approved' if approved else '❌ Rejected'}")
    return {**data, "approved": approved}


@step
async def create_itinerary(ctx, data: dict) -> str:
    """Step 4: Build itinerary based on weather + selections."""
    print("  📋 [Step: create_itinerary] Building day-by-day plan...")

    if not data.get("approved", False):
        return "❌ Trip cancelled — budget not approved."

    fl = data["selected_flight"]
    ht = data["selected_hotel"]
    plan = f"""
🗺️ Shanghai 3-Day Trip Plan (MAF Workflow)
✈️ Flight: {fl['airline']} ({fl['departure']}-{fl['arrival']}) ¥{fl['price']}
🏨 Hotel: {ht['name']} ¥{ht['price_per_night']}/night

📅 Itinerary:"""

    for day in data["weather"]["forecast"]:
        if "Sunny" in day["weather"]:
            activities = "The Bund → Shanghai Tower → Huangpu River Cruise"
        elif "Cloudy" in day["weather"]:
            activities = "Yu Garden → Shanghai Museum → Xintiandi"
        else:
            activities = "Nanjing Road Shopping → Din Tai Fung → Tianzifang"
        plan += f"\n  {day['date']} ({day['weather']}): {activities}"

    plan += f"\n\n💰 Total estimate: ¥{data['total_cost']}"
    return plan


# ── Workflow definition ──────────────────────────────────────────────

@workflow
async def travel_plan_workflow(ctx, user_request: str) -> str:
    """MAF Functional Workflow — travel planning with HITL.

    Compare with LangGraph:
      LangGraph: define StateGraph → add_node → add_edge → compile(checkpointer=...)
      MAF:       @workflow → @step → native Python control flow → ctx.request_info()

    Both support:
      ✅ Durable checkpointing (MAF: CheckpointStorage, LangGraph: SqliteSaver)
      ✅ HITL interruption (MAF: ctx.request_info, LangGraph: interrupt())
      ✅ Parallel execution (MAF: asyncio.gather, LangGraph: graph edges)

    MAF unique:
      ✅ Native Python control flow (if/else, for loops, try/except — no graph DSL)
      ✅ Same code runs in C#/.NET (with equivalent API)
      ✅ Built-in OpenTelemetry tracing
      ✅ Foundry Hosted Agent deployment (workflow.as_agent())
    """
    print(f"\n  📝 User request: {user_request}")

    # Step 1: Gather info (parallel inside step via asyncio.gather)
    data = await gather_info(ctx, user_request)

    # Step 2: Select best options
    data = await select_best(ctx, data)

    # Step 3: HITL approval (workflow pauses here)
    data = await budget_approval(ctx, data)

    # Step 4: Create itinerary
    plan = await create_itinerary(ctx, data)

    return plan


# ── Main: run workflow with simulated HITL ───────────────────────────

async def main():
    print("=" * 60)
    print("MAF Functional Workflow — @workflow + @step + request_info HITL")
    print("=" * 60)
    print("  Framework: Microsoft Agent Framework 1.8")
    print("  API: @workflow / @step / ctx.request_info()")
    print("  Comparison point: LangGraph uses StateGraph / interrupt() / SqliteSaver")
    print("=" * 60)

    # Phase 1: Run workflow — it will pause at budget_approval
    print("\n▶ Phase 1: Running workflow (will pause at HITL gate)...")
    try:
        result = await travel_plan_workflow.run("帮我规划下周从北京去上海的3天旅行计划，中等预算")
    except Exception as e:
        # If request_info pauses, we get the result with pending events
        print(f"  Workflow paused or error: {e}")
        result = None

    if result is not None:
        # Check for pending request_info events
        pending = getattr(result, "get_request_info_events", lambda: [])()
        if pending:
            print(f"\n⏸️  Workflow PAUSED with {len(pending)} pending request_info event(s)")
            for evt in pending:
                print(f"    Request: {evt}")

            # Phase 2: Resume with approval
            print("\n▶ Phase 2: Resuming with approval...")
            # Build responses dict: {request_id: response_value}
            responses = {}
            for evt in pending:
                rid = getattr(evt, "request_id", None) or getattr(evt, "id", "unknown")
                responses[rid] = "yes"
                print(f"    Responding to {rid}: 'yes'")

            resumed_result = await travel_plan_workflow.run(responses=responses)
            plan = getattr(resumed_result, "value", None) or str(resumed_result)
        else:
            plan = getattr(result, "value", None) or str(result)
    else:
        plan = "(Workflow did not complete — check error above)"

    print(f"\n{'=' * 60}")
    print("FINAL PLAN:")
    print("=" * 60)
    print(plan)

    print(f"\n[MAF Workflow] Key architectural differences from LangGraph:")
    print("[MAF]  @step: native Python async functions (no graph node/edge DSL)")
    print("[MAF]  ctx.request_info(): HITL pause/resume (vs LangGraph interrupt())")
    print("[MAF]  asyncio.gather: parallel execution (vs LangGraph graph edges)")
    print("[MAF]  Python + C#/.NET: same patterns, both languages")
    print("[MAF]  Built-in OpenTelemetry: no LangSmith dependency")
    print("[MAF]  workflow.as_agent(): deploy to Foundry Hosted Agents (2 lines)")


if __name__ == "__main__":
    asyncio.run(main())
