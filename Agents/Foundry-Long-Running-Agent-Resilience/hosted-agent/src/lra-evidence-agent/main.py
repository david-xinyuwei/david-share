"""Repository-owned Hosted Agent for deterministic LRA fault testing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import uuid
from datetime import datetime, timezone

from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)

from contract import ContractError, STAGES, build_stage_record, parse_work_spec

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("lra-evidence-agent")

FAULT_INJECTION_ENABLED = (
    os.environ.get("LRA_ENABLE_FAULT_INJECTION", "false").lower() == "true"
)
DEFAULT_STAGE_DELAY_MS = int(os.environ.get("LRA_STAGE_DELAY_MS", "500"))
PROCESS_INSTANCE_ID = (
    f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
)
INJECTED_EXIT_CODE = 86

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(resilient_background=True)
)
set_resilient_tasks_enabled(True)


def _output_count(stream: ResponseEventStream) -> int:
    output = getattr(stream.response, "output", None)
    if output is None:
        getter = getattr(stream.response, "get", None)
        output = getter("output") if callable(getter) else None
    return len(output or [])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


async def _defer_for_recovery(
    context: ResponseContext,
    work_id: str,
) -> None:
    LOGGER.warning(
        "LRA_SHUTDOWN_DEFER at_utc=%s response_id=%s work_id=%s instance=%s",
        _utc_now(),
        context.response_id,
        work_id,
        PROCESS_INSTANCE_ID,
    )
    await context.exit_for_recovery()


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    cancellation_signal: asyncio.Event,
):
    raw_input = await context.get_input_text() or ""
    try:
        spec = parse_work_spec(raw_input, DEFAULT_STAGE_DELAY_MS)
    except ContractError as error:
        stream = ResponseEventStream(
            response_id=context.response_id,
            request=request,
        )
        yield stream.emit_created()
        yield stream.emit_failed(
            code="invalid_request_error",
            message=str(error),
        )
        return

    if spec.crash_after_stage is not None and not FAULT_INJECTION_ENABLED:
        stream = ResponseEventStream(
            response_id=context.response_id,
            request=request,
        )
        yield stream.emit_created()
        yield stream.emit_failed(
            code="fault_injection_disabled",
            message=(
                "crash_after_stage requires "
                "LRA_ENABLE_FAULT_INJECTION=true in a non-production deployment"
            ),
        )
        return

    if context.is_recovery and context.persisted_response is not None:
        stream = ResponseEventStream(
            response_id=context.response_id,
            response=context.persisted_response,
        )
        start = _output_count(stream)
    else:
        stream = ResponseEventStream(
            response_id=context.response_id,
            request=request,
        )
        start = 0

    LOGGER.info(
        "LRA_ENTRY at_utc=%s response_id=%s work_id=%s mode=%s "
        "start=%d instance=%s",
        _utc_now(),
        context.response_id,
        spec.work_id,
        "recovered" if context.is_recovery else "fresh",
        start,
        PROCESS_INSTANCE_ID,
    )

    yield stream.emit_created()
    if context.shutdown.is_set():
        await _defer_for_recovery(context, spec.work_id)
        return
    if cancellation_signal.is_set():
        return
    yield stream.emit_in_progress()

    for stage_index in range(start, len(STAGES)):
        await asyncio.sleep(spec.stage_delay_ms / 1000)
        if context.shutdown.is_set():
            await _defer_for_recovery(context, spec.work_id)
            return
        if cancellation_signal.is_set():
            return

        record = build_stage_record(
            spec=spec,
            stage_index=stage_index,
            process_instance_id=PROCESS_INSTANCE_ID,
            recovered_entry=context.is_recovery,
        )
        message = stream.add_output_item_message()
        yield message.emit_added()
        text = message.add_text_content()
        yield text.emit_added()
        yield text.emit_delta(
            json.dumps(record, ensure_ascii=True, sort_keys=True)
        )
        yield text.emit_text_done()
        yield text.emit_done()
        yield message.emit_done()
        yield stream.checkpoint()

        LOGGER.info(
            "LRA_STAGE_COMMITTED at_utc=%s response_id=%s work_id=%s "
            "stage=%d instance=%s",
            _utc_now(),
            context.response_id,
            spec.work_id,
            stage_index,
            PROCESS_INSTANCE_ID,
        )
        if (
            FAULT_INJECTION_ENABLED
            and not context.is_recovery
            and spec.crash_after_stage == stage_index
        ):
            LOGGER.critical(
                "LRA_INJECTED_PROCESS_LOSS at_utc=%s response_id=%s work_id=%s "
                "after_stage=%d exit_code=%d",
                _utc_now(),
                context.response_id,
                spec.work_id,
                stage_index,
                INJECTED_EXIT_CODE,
            )
            await asyncio.sleep(0.5)
            os._exit(INJECTED_EXIT_CODE)

    LOGGER.info(
        "LRA_COMPLETED at_utc=%s response_id=%s work_id=%s instance=%s",
        _utc_now(),
        context.response_id,
        spec.work_id,
        PROCESS_INSTANCE_ID,
    )
    yield stream.emit_completed()


if __name__ == "__main__":
    app.run()
