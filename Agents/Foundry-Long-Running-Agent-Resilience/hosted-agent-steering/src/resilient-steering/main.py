# Copyright (c) Microsoft. All rights reserved.

r"""Resilient, steerable translation agent (responses protocol).

Ported from the Microsoft ``resilient-steering`` Hosted Agent sample and re-shaped
around the same 30-section translation job the Portal's other resilience demos
use, so every scenario shows one business task and differs only in how it is
interrupted.

Two opt-in options drive the behaviour:

- ``resilient_background=True`` — a ``store=true, background=true`` response
  survives process crashes: the framework re-invokes the handler on the next
  process and hands it the persisted response, so translation resumes from the
  last committed section instead of restarting.
- ``steerable_conversations=True`` — a client can POST a new turn on an in-flight
  conversation. The running turn is woken through the cancellation signal
  (``context.pending_input_count > 0``), completes with the sections it has, and
  the framework re-invokes with the new input as a steered turn.

Input (JSON object; empty or plain text means ``{"target": <default>}``)::

    {
      "target": "zh-Hans",            # Azure Translator language code (allow-list below)
      "inject_process_loss": false,   # test affordance, needs LRE_ENABLE_FAULT_INJECTION=true
      "crash_after_stage": 9,         # 0-based section after whose checkpoint the process exits
      "stage_delay_ms": 300           # pacing so the caller can watch sections arrive
    }

Every committed section is one output item carrying an ``lra_stage`` JSON record
(the same schema as the Portal's checkpoint demo), and every entry emits one
``lre_steering_entry`` record with ``entry_mode`` fresh / recovered / steered.

Required environment variables:
    LRA_TRANSLATOR_ENDPOINT, LRA_TRANSLATOR_REGION, LRA_TRANSLATOR_RESOURCE_ID
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from azure.ai.agentserver.core.tasks import set_resilient_tasks_enabled
from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)
from azure.identity import DefaultAzureCredential

from translation_workload import SECTION_IDS, SOURCE_SECTIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("resilient-steering")

options = ResponsesServerOptions(
    resilient_background=True,
    steerable_conversations=True,
)
app = ResponsesAgentServerHost(options=options)
set_resilient_tasks_enabled(True)

FAULT_INJECTION_ENABLED = (
    os.environ.get("LRE_ENABLE_FAULT_INJECTION", "false").lower() == "true"
)
DEFAULT_STAGE_DELAY_MS = int(os.environ.get("LRE_STAGE_DELAY_MS", "300"))
DEFAULT_TARGET = "zh-Hans"
TARGET_LANGUAGES = {
    "zh-Hans": "Simplified Chinese",
    "zh-Hant": "Traditional Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
}
INJECTED_EXIT_CODE = 86
PROCESS_INSTANCE_ID = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
PROCESS_SHA256 = hashlib.sha256(PROCESS_INSTANCE_ID.encode("utf-8")).hexdigest()
TRANSLATOR_CREDENTIAL = DefaultAzureCredential(exclude_interactive_browser_credential=True)

if not os.environ.get("LRA_TRANSLATOR_ENDPOINT"):
    raise RuntimeError("LRA_TRANSLATOR_ENDPOINT is required")


def _parse_spec(raw_input: str) -> dict[str, Any]:
    raw_input = raw_input.strip()
    try:
        candidate = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError:
        candidate = {}
    if not isinstance(candidate, dict):
        raise ValueError("input must be a JSON object")
    target = str(candidate.get("target") or DEFAULT_TARGET)
    if target not in TARGET_LANGUAGES:
        raise ValueError(f"target must be one of {', '.join(sorted(TARGET_LANGUAGES))}")
    crash_after_stage = candidate.get("crash_after_stage", 9)
    if isinstance(crash_after_stage, bool) or not isinstance(crash_after_stage, int):
        raise ValueError("crash_after_stage must be an integer")
    if crash_after_stage not in range(len(SOURCE_SECTIONS)):
        raise ValueError(f"crash_after_stage must be 0-{len(SOURCE_SECTIONS) - 1}")
    stage_delay_ms = candidate.get("stage_delay_ms", DEFAULT_STAGE_DELAY_MS)
    if isinstance(stage_delay_ms, bool) or not isinstance(stage_delay_ms, int):
        raise ValueError("stage_delay_ms must be an integer")
    if stage_delay_ms not in range(0, 10_001):
        raise ValueError("stage_delay_ms must be 0-10000")
    return {
        "target": target,
        "inject_process_loss": candidate.get("inject_process_loss") is True,
        "crash_after_stage": crash_after_stage,
        "stage_delay_ms": stage_delay_ms,
    }


def _translate_sync(text: str, target: str) -> str:
    endpoint = os.environ["LRA_TRANSLATOR_ENDPOINT"].rstrip("/")
    region = os.environ.get("LRA_TRANSLATOR_REGION", "global")
    resource_id = os.environ.get("LRA_TRANSLATOR_RESOURCE_ID", "").strip()
    query = urllib.parse.urlencode({"api-version": "3.0", "from": "en", "to": target})
    # A resource without a custom subdomain is reached through the shared global
    # endpoint and identified by the resource-ID header.
    path = "/translate" if resource_id else "/translator/text/v3.0/translate"
    token = TRANSLATOR_CREDENTIAL.get_token("https://cognitiveservices.azure.com/.default")
    headers = {
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Region": region,
    }
    if resource_id:
        headers["Ocp-Apim-ResourceId"] = resource_id
    request = urllib.request.Request(
        f"{endpoint}{path}?{query}",
        data=json.dumps([{"Text": text}]).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Translator returned HTTP {error.code}: {body}") from error
    try:
        translated = payload[0]["translations"][0]["text"]
    except (IndexError, KeyError, TypeError) as error:
        raise RuntimeError(f"Translator returned an unexpected payload: {payload!r}") from error
    if not isinstance(translated, str) or not translated.strip():
        raise RuntimeError("Translator returned empty text")
    return translated


def _stage_records(response: Any) -> list[dict[str, Any]]:
    output = getattr(response, "output", None)
    if output is None and hasattr(response, "get"):
        output = response.get("output")
    records: list[dict[str, Any]] = []
    for item in output or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            try:
                candidate = json.loads(part.get("text") or "")
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(candidate, dict) and candidate.get("kind") == "lra_stage":
                records.append(candidate)
    return records


def _resume_index(response: Any) -> int:
    """First section that is not yet committed in the persisted response."""
    indexes = [int(record.get("stage_index", -1)) for record in _stage_records(response)]
    return (max(indexes) + 1) if indexes else 0


def _stage_record(
    *,
    response_id: str,
    target: str,
    stage_index: int,
    translated: str,
    entry_mode: str,
) -> dict[str, Any]:
    source = SOURCE_SECTIONS[stage_index]
    return {
        "schema_version": 2,
        "kind": "lra_stage",
        "workload": "translator_batch",
        "work_id": response_id,
        "payload_sha256": hashlib.sha256(target.encode("utf-8")).hexdigest(),
        "target": target,
        "stage_index": stage_index,
        "stage_name": SECTION_IDS[stage_index],
        "stage_count": len(SOURCE_SECTIONS),
        "stage_result_sha256": hashlib.sha256(translated.encode("utf-8")).hexdigest(),
        "entry_mode": entry_mode,
        "process_instance_id": PROCESS_INSTANCE_ID,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "source_text": source,
        "translated_text": translated,
    }


def _emit_json_item(stream: ResponseEventStream, payload: dict[str, Any]):
    message = stream.add_output_item_message()
    yield message.emit_added()
    text = message.add_text_content()
    yield text.emit_added()
    yield text.emit_text_done(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    yield text.emit_done()
    yield message.emit_done()


@app.response_handler
async def handler(
    request: CreateResponse,
    context: ResponseContext,
    cancellation_signal: asyncio.Event,
):
    raw_input = await context.get_input_text() or ""
    try:
        spec = _parse_spec(raw_input)
    except ValueError as error:
        stream = ResponseEventStream(response_id=context.response_id, request=request)
        yield stream.emit_created()
        yield stream.emit_failed(code="invalid_request_error", message=str(error))
        return
    if spec["inject_process_loss"] and not FAULT_INJECTION_ENABLED:
        stream = ResponseEventStream(response_id=context.response_id, request=request)
        yield stream.emit_created()
        yield stream.emit_failed(
            code="fault_injection_disabled",
            message="inject_process_loss requires LRE_ENABLE_FAULT_INJECTION=true",
        )
        return

    # Recovery resumes the persisted response at the first uncommitted section.
    if context.is_recovery and context.persisted_response is not None:
        stream = ResponseEventStream(
            response_id=context.response_id,
            response=context.persisted_response,
        )
        start = _resume_index(stream.response)
        entry_mode = "recovered"
    else:
        stream = ResponseEventStream(response_id=context.response_id, request=request)
        start = 0
        entry_mode = "steered" if context.is_steered_turn else "fresh"

    yield stream.emit_created()
    if context.shutdown.is_set():
        await context.exit_for_recovery()
        return
    if cancellation_signal.is_set():
        yield stream.emit_completed()
        return
    yield stream.emit_in_progress()

    logger.info(
        "LRE_STEERING_ENTRY response=%s mode=%s target=%s start=%d process=%s pending=%d",
        context.response_id,
        entry_mode,
        spec["target"],
        start,
        PROCESS_SHA256,
        context.pending_input_count,
    )
    for event in _emit_json_item(
        stream,
        {
            "kind": "lre_steering_entry",
            "entry_mode": entry_mode,
            "process_sha256": PROCESS_SHA256,
            "target": spec["target"],
            "target_name": TARGET_LANGUAGES[spec["target"]],
            "resume_from": start,
            "stage_count": len(SOURCE_SECTIONS),
            "pending_inputs": context.pending_input_count,
        },
    ):
        yield event

    for stage_index in range(start, len(SOURCE_SECTIONS)):
        translated = await asyncio.to_thread(
            _translate_sync, SOURCE_SECTIONS[stage_index], spec["target"]
        )
        await asyncio.sleep(spec["stage_delay_ms"] / 1000)
        if context.shutdown.is_set():
            await context.exit_for_recovery()
            return
        if cancellation_signal.is_set():
            # Steering pressure (a new turn queued on this conversation) arrives as a
            # cancellation; the committed sections stay valid, so close the turn cleanly.
            logger.info(
                "LRE_STEERING_WIND_DOWN response=%s committed=%d pending=%d",
                context.response_id,
                stage_index,
                context.pending_input_count,
            )
            yield stream.emit_completed()
            return

        record = _stage_record(
            response_id=context.response_id,
            target=spec["target"],
            stage_index=stage_index,
            translated=translated,
            entry_mode=entry_mode,
        )
        for event in _emit_json_item(stream, record):
            yield event
        yield stream.checkpoint()

        if (
            FAULT_INJECTION_ENABLED
            and spec["inject_process_loss"]
            and not context.is_recovery
            and stage_index == spec["crash_after_stage"]
        ):
            logger.critical(
                "LRE_STEERING_PROCESS_LOSS response=%s process=%s after_stage=%d exit_code=%d",
                context.response_id,
                PROCESS_SHA256,
                stage_index,
                INJECTED_EXIT_CODE,
            )
            await asyncio.sleep(0.5)
            os._exit(INJECTED_EXIT_CODE)

    logger.info("LRE_STEERING_COMPLETED response=%s process=%s", context.response_id, PROCESS_SHA256)
    yield stream.emit_completed()


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
