"""Minimal MAF @workflow + @step + request_info HITL test."""
from agent_framework import workflow, step
import asyncio

@step
async def add_step(ctx, x: int):
    print(f"  add_step: {x} -> {x+1}")
    return x + 1

@step
async def approval_step(ctx, cost: int):
    print(f"  approval_step: requesting approval for cost={cost}")
    answer = await ctx.request_info(
        {"question": f"Approve cost {cost}?"},
        response_type=str,
    )
    print(f"  approval_step: got answer={answer!r}")
    return f"approved={answer}"

@workflow
async def test_wf(ctx, val: int):
    print(f"  workflow start: val={val}")
    val = await add_step(val)
    print(f"  after add_step: val={val}")
    result = await approval_step(cost=val)
    print(f"  after approval: result={result}")
    return result

async def main():
    print("Phase 1: Run workflow (should pause at request_info)...")
    run_result = await test_wf.run(42)
    print(f"  Result type: {type(run_result).__name__}")
    print(f"  Value: {run_result.value}")

    pending = run_result.get_request_info_events()
    print(f"  Pending request_info events: {len(pending)}")
    if pending:
        for e in pending:
            print(f"    request_id={e.request_id}, data={e.request_data}")

        print("\nPhase 2: Resume with 'yes'...")
        resumed = await test_wf.run(responses={pending[0].request_id: "yes"})
        print(f"  Resumed value: {resumed.value}")
    else:
        print("  No HITL pause — workflow completed directly.")

if __name__ == "__main__":
    asyncio.run(main())
