"""Minimal Hosted Agent handler wired to the public resilience task API.

This handler demonstrates the runtime contract. It reads recovery state but
does not claim that TaskMetadata.flush acknowledges durable persistence.
"""

from __future__ import annotations

# README_SNIPPET_START
from typing import Any, TypedDict

from azure.ai.agentserver.core.tasks import RetryPolicy, TaskContext, task


class WorkInput(TypedDict):
    payload: str


@task(name="resilience-api-usage", timeout=None, retry=RetryPolicy())
async def resilience_api_usage(ctx: TaskContext[WorkInput]) -> dict[str, Any]:
    if ctx.shutdown.is_set():
        return await ctx.exit_for_recovery()

    completed = int(ctx.metadata.get("completed_phases", 0) or 0)
    return {
        "task_id": ctx.task_id,
        "input_id": ctx.input_id,
        "entry_mode": ctx.entry_mode,
        "recovery_count": ctx.recovery_count,
        "retry_attempt": ctx.retry_attempt,
        "completed_phases": completed,
        "payload_length": len(ctx.input["payload"]),
    }
# README_SNIPPET_END

