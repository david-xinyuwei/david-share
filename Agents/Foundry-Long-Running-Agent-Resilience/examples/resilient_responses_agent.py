"""Minimal Responses handler with process-loss recovery enabled.

This follows the public resilient-streaming pattern. Replace run_stage with
your own work. Use external storage as well when progress includes business
state, large artifacts, or side effects rather than response output alone.
"""

from __future__ import annotations

# README_RESPONSES_SNIPPET_START
import asyncio

from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)

STAGES = ("analyze", "generate", "refine")

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(resilient_background=True)
)
set_resilient_tasks_enabled(True)


async def run_stage(stage: str, prompt: str) -> str:
    """Replace this body with one completed, safely repeatable stage."""
    await asyncio.sleep(0)
    return f"[{stage}] result for: {prompt}"


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    cancellation_signal: asyncio.Event,
):
    if context.is_recovery and context.persisted_response is not None:
        stream = ResponseEventStream(
            response_id=context.response_id,
            response=context.persisted_response,
        )
        start = len(stream.response.get("output") or [])
    else:
        stream = ResponseEventStream(
            response_id=context.response_id,
            request=request,
        )
        start = 0

    yield stream.emit_created()
    if context.shutdown.is_set():
        await context.exit_for_recovery()
    if cancellation_signal.is_set():
        return

    yield stream.emit_in_progress()
    prompt = await context.get_input_text() or ""

    for index, stage in enumerate(STAGES):
        if index < start:
            continue

        result = await run_stage(stage, prompt)
        if context.shutdown.is_set():
            await context.exit_for_recovery()
        if cancellation_signal.is_set():
            return

        message = stream.add_output_item_message()
        yield message.emit_added()
        text = message.add_text_content()
        yield text.emit_added()
        yield text.emit_text_done(result)
        yield text.emit_done()
        yield message.emit_done()
        yield stream.checkpoint()

    yield stream.emit_completed()


if __name__ == "__main__":
    app.run()
# README_RESPONSES_SNIPPET_END
