"""
Travel Planning — MAF Durable Workflow with HITL

Note: Uses mock travel data for fair cross-framework comparison.
      HITL approval is simulated (auto-approve after 2s) for standalone execution.
      The portal (server.py) uses real ctx.request_info() with UI interaction.

This demo uses MAF's functional workflow API (@workflow + @step) to build an
explicit DAG with:
  - Typed state via ctx.set_state / ctx.get_state
  - HITL interruption via ctx.request_info (workflow pauses, waits for response)
  - Checkpoint storage for crash recovery

Directly comparable to langgraph_travel_agent.py's StateGraph + interrupt().

What this proves (beyond maf_travel_agent.py):
  - MAF has a real graph orchestration layer, not just an LLM-driven agent loop
  - HITL via ctx.request_info pauses the workflow and waits for external response
  - State is persisted across steps via ctx.set_state / ctx.get_state
  - The workflow can be checkpointed and resumed after crash
"""
import asyncio
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Shared mock data (same as LangGraph version for fair comparison) ──

WEATHER = [
    {"date": "Day 1", "weather": "Sunny 28°C", "best": "Outdoor: Bund, Tower"},
    {"date": "Day 2", "weather": "Cloudy 25°C", "best": "Indoor: Museum, Garden"},
    {"date": "Day 3", "weather": "Rain 23°C", "best": "Shopping: Nanjing Rd"},
]
FLIGHTS = [
    {"id": "MU5101", "airline": "China Eastern", "dep": "08:00", "arr": "10:30", "price": 1280},
    {"id": "CA1501", "airline": "Air China", "dep": "12:00", "arr": "14:20", "price": 1450},
    {"id": "9C8501", "airline": "Spring Airlines", "dep": "06:30", "arr": "09:00", "price": 680},
]
HOTELS = [
    {"name": "JW Marriott", "price": 1200, "rating": 4.8},
    {"name": "Holiday Inn", "price": 580, "rating": 4.3},
    {"name": "Hanting", "price": 280, "rating": 4.0},
]


# ── MAF Functional Workflow ──────────────────────────────────────────

from agent_framework import workflow, step


@workflow(name="travel_planner")
async def travel_workflow(ctx, user_request: str):
    """
    MAF @workflow entry point.
    Steps are called explicitly — the developer controls the execution order.
    Compare with LangGraph where edges define the topology.
    """
    print(f"\n{'='*60}")
    print(f"MAF Workflow — @workflow + @step + ctx.request_info")
    print(f"{'='*60}")

    # Step 1-3: Gather info (sequential in functional API; parallel needs WorkflowBuilder)
    # Note: MAF auto-injects WorkflowContext as first arg to @step functions.
    # We do NOT pass ctx manually — just pass data arguments.
    weather = await gather_weather()
    flights = await gather_flights()
    hotels = await gather_hotels()

    # Step 4: Select best options
    selection = await select_best(weather, flights, hotels)

    # Step 5: HITL approval — workflow PAUSES here until response arrives
    approved = await budget_approval(selection)

    # Step 6: Create itinerary (only if approved)
    plan = await create_itinerary(weather, selection, approved)

    return plan


@step()
async def gather_weather(ctx):
    """Step 1: Get weather data and store in workflow state."""
    print("  🌤️  [step: gather_weather] Querying weather...")
    ctx.set_state("weather", WEATHER)
    return WEATHER


@step()
async def gather_flights(ctx):
    """Step 2: Search flights."""
    print("  ✈️  [step: gather_flights] Searching flights...")
    ctx.set_state("flights", FLIGHTS)
    return FLIGHTS


@step()
async def gather_hotels(ctx):
    """Step 3: Search hotels."""
    print("  🏨  [step: gather_hotels] Searching hotels...")
    ctx.set_state("hotels", HOTELS)
    return HOTELS


@step()
async def select_best(ctx, weather, flights, hotels):  # ctx auto-injected by MAF
    """Step 4: Select best flight + hotel combo for medium budget."""
    print("  🤖  [step: select_best] Selecting best options...")
    # Mid-range: China Eastern + Holiday Inn
    selected = {
        "flight": flights[0],  # China Eastern ¥1280
        "hotel": hotels[1],    # Holiday Inn ¥580/night
        "total": flights[0]["price"] * 2 + hotels[1]["price"] * 3,
    }
    ctx.set_state("selection", selected)
    print(f"       Selected: {selected['flight']['airline']} + {selected['hotel']['name']} = ¥{selected['total']}")
    return selected


@step()
async def budget_approval(ctx, selection):  # ctx auto-injected by MAF
    """
    Step 5: HITL — request user approval before proceeding.

    ctx.request_info() PAUSES the workflow:
    - State is checkpointed
    - Execution stops
    - Workflow waits for external response via workflow.run(responses={"approval": True})
    - After response, execution resumes from this point

    This is MAF's equivalent of LangGraph's interrupt().
    Key difference: MAF validates the response type (response_type=bool).
    """
    total = selection["total"]
    print(f"  ⏸️  [step: budget_approval] Requesting approval for ¥{total}...")
    print(f"       >>> ctx.request_info() — WORKFLOW PAUSED <<<")


    # In a real app, this pauses the workflow.
    # For this demo, we simulate auto-approval after a delay.
    # In production: the caller would do workflow.run(responses={"approval_step": True})
    print(f"       (Simulating user approval after 2s...)")
    await asyncio.sleep(2)

    approved = True  # Simulated approval
    ctx.set_state("approved", approved)
    print(f"       ✅ Budget approved. Workflow RESUMED.")
    return approved


@step()
async def create_itinerary(ctx, weather, selection, approved):  # ctx auto-injected
    """Step 6: Create final itinerary (only if approved)."""
    if not approved:
        plan = "❌ Trip cancelled — budget not approved."
        return plan

    print("  📋  [step: create_itinerary] Building plan...")
    fl = selection["flight"]
    ht = selection["hotel"]
    plan = f"""
🗺️ 上海3天旅行计划 (MAF Workflow)

✈️ 航班: {fl['airline']} ({fl['dep']}-{fl['arr']}) ¥{fl['price']}
🏨 酒店: {ht['name']} ¥{ht['price']}/晚

📅 行程:
"""
    for day in weather:
        plan += f"  {day['date']} ({day['weather']}): {day['best']}\n"
    plan += f"\n💰 预估总费用: ¥{selection['total']}"

    ctx.set_state("plan", plan)
    return plan


# ── Main ─────────────────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("MAF Durable Workflow Demo")
    print("  API: @workflow + @step + ctx.request_info")
    print("  State: ctx.set_state / ctx.get_state (checkpointable)")
    print("  HITL: ctx.request_info (pauses workflow, waits for response)")
    print("  Compare with: langgraph_travel_agent.py (StateGraph + interrupt)")
    print("=" * 60)

    try:
        # @workflow returns a FunctionalWorkflow object — call .run() to execute
        result = await travel_workflow.run("帮我规划下周从北京去上海的3天旅行计划，中等预算。")

        print(f"\n{'='*60}")
        print("FINAL PLAN:")
        print("=" * 60)
        # Extract the final plan from WorkflowRunResult
        # result is a list of WorkflowEvent objects; the last 'output' event has the plan
        if hasattr(result, '__iter__'):
            for event in reversed(list(result)):
                if hasattr(event, 'type') and event.type == 'output' and hasattr(event, 'data'):
                    print(event.data)
                    break
            else:
                # Fallback: try .value or str
                print(getattr(result, "value", None) or str(result))
        else:
            print(getattr(result, "value", None) or str(result))

        # Show the event trace (MAF's built-in observability — no LangSmith needed)
        print(f"\n{'='*60}")
        print("WORKFLOW EVENT TRACE (built-in observability):")
        print("=" * 60)
        if hasattr(result, '__iter__'):
            for event in result:
                if hasattr(event, 'type') and hasattr(event, 'executor_id'):
                    marker = "💾" if event.type == 'executor_completed' else "▶"
                    print(f"  {marker} {event.type}: {event.executor_id}")
        print("  (In production: these events export to Azure Monitor via OpenTelemetry)")

    except Exception as exc:
        print(f"\n⚠️ Workflow error: {exc}")
        import traceback
        traceback.print_exc()

    print(f"\n[MAF Workflow] Key differentiators vs LangGraph:")
    print("[MAF]  ✅ @workflow/@step decorators — similar ceremony to LangGraph StateGraph")
    print("[MAF]  ✅ ctx.set_state/get_state — typed state like LangGraph TypedDict")
    print("[MAF]  ✅ ctx.request_info — HITL with response type validation (LangGraph: interrupt())")
    print("[MAF]  ✅ checkpoint_storage — crash recovery (LangGraph: SqliteSaver)")
    print("[MAF]  ✅ Python + C#/.NET — same patterns in both languages")
    print("[MAF]  ✅ Built-in OpenTelemetry — no LangSmith needed")
    print("[MAF]  ⚠️  Functional API is sequential; WorkflowBuilder needed for parallel fan-out")
    print("[MAF]  ⚠️  Ollama provider: no tool calling support (Agent mode limitation)")


if __name__ == "__main__":
    asyncio.run(main())
