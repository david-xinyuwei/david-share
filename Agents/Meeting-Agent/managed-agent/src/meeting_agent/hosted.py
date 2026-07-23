"""Local Invocations host for Meeting Agent."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from .analyzers import (
    Analyzer,
    ManagedAgentAnalyzer,
)
from .hosted_models import HostedMeetingRequest, HostedMeetingResponse
from .hosted_pipeline import build_hosted_run, stream_hosted_run

logger = logging.getLogger("meeting_agent.hosted")
MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_CONCURRENT_RUNS = 2
_run_slots = asyncio.Semaphore(MAX_CONCURRENT_RUNS)


def _openapi_spec() -> dict[str, object]:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Meeting Agent Invocations API",
            "version": "1.0.0",
            "description": (
                "Build a meeting summary, mind map, PowerPoint, and unsent email draft. "
                "Generated files are available through the loopback artifact API."
            ),
        },
        "paths": {
            "/invocations": {
                "post": {
                    "operationId": "buildMeetingArtifacts",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": HostedMeetingRequest.model_json_schema()
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Meeting artifacts generated",
                            "content": {
                                "application/json": {
                                    "schema": HostedMeetingResponse.model_json_schema()
                                }
                            },
                        },
                        "400": {"description": "Malformed JSON"},
                        "422": {"description": "Invalid meeting contract"},
                        "503": {"description": "Managed Agent runtime is unavailable"},
                    },
                }
            }
        },
    }


app = InvocationAgentServerHost(openapi_spec=_openapi_spec())


@app.invoke_handler
async def handle_invoke(request: Request) -> Response:
    """Validate one meeting request and run the artifact pipeline off the event loop."""
    invocation_id = getattr(request.state, "invocation_id", None)
    agent_session_id = getattr(request.state, "session_id", None)
    payload_or_error = await _request_payload(request)
    if isinstance(payload_or_error, Response):
        return payload_or_error
    payload = payload_or_error

    try:
        meeting_request = HostedMeetingRequest.model_validate(payload)
    except ValidationError as error:
        details = [
            {
                "location": ".".join(str(part) for part in item["loc"]),
                "message": item["msg"],
                "type": item["type"],
            }
            for item in error.errors(include_input=False)
        ]
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": "Meeting request is invalid.",
                "details": details,
            },
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )

    try:
        async with _run_slots:
            result = await asyncio.to_thread(
                build_hosted_run,
                meeting_request,
                _session_home(),
                _get_analyzer(),
            )
    except ValueError as error:
        return _error(422, "invalid_meeting", str(error))
    except RuntimeError:
        logger.exception("Meeting analysis failed (invocation=%s)", invocation_id)
        return _error(
            503,
            "analysis_unavailable",
            "Meeting analysis is unavailable. Verify the Managed Agent configuration and retry.",
        )
    except OSError:
        logger.exception("Meeting artifact generation failed (invocation=%s)", invocation_id)
        return _error(
            500,
            "artifact_generation_failed",
            "Meeting artifacts could not be generated.",
        )
    except Exception:
        logger.exception("Unexpected meeting invocation failure (invocation=%s)", invocation_id)
        return _error(500, "internal_error", "The meeting request failed unexpectedly.")

    result = result.model_copy(
        update={
            "agent_session_id": str(agent_session_id) if agent_session_id else None,
            "invocation_id": str(invocation_id) if invocation_id else None,
        }
    )
    logger.info(
        "Meeting run completed (invocation=%s, run=%s, source=%s)",
        invocation_id,
        result.run_id,
        result.source_sha256,
    )
    return JSONResponse(
        result.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


async def handle_invoke_stream(request: Request) -> Response:
    """Stream real model deltas and artifact completion events as NDJSON."""
    payload_or_error = await _request_payload(request)
    if isinstance(payload_or_error, Response):
        return payload_or_error
    payload = payload_or_error
    try:
        meeting_request = HostedMeetingRequest.model_validate(payload)
    except ValidationError as error:
        return JSONResponse(
            {
                "error": "invalid_request",
                "message": "Meeting request is invalid.",
                "details": [
                    {
                        "location": ".".join(str(part) for part in item["loc"]),
                        "message": item["msg"],
                        "type": item["type"],
                    }
                    for item in error.errors(include_input=False)
                ],
            },
            status_code=422,
            headers={"Cache-Control": "no-store"},
        )

    agent_session_id = request.query_params.get("agent_session_id") or None
    invocation_id = getattr(request.state, "invocation_id", None) or uuid4().hex

    async def event_stream():
        queue: asyncio.Queue[tuple[str, dict[str, object]] | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def publish(event: str, data: dict[str, object]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (event, data))

        def run() -> None:
            try:
                stream_hosted_run(
                    meeting_request,
                    _session_home(),
                    _get_analyzer(),
                    publish,
                    agent_session_id=agent_session_id,
                    invocation_id=str(invocation_id),
                )
            except ValueError as error:
                publish("error", {"error": "invalid_meeting", "message": str(error)})
            except RuntimeError:
                logger.exception(
                    "Streaming meeting analysis failed (invocation=%s)",
                    invocation_id,
                )
                publish(
                    "error",
                    {
                        "error": "analysis_unavailable",
                        "message": (
                            "Meeting analysis is unavailable. "
                            "Verify the Managed Agent configuration and retry."
                        ),
                    },
                )
            except OSError:
                logger.exception(
                    "Streaming artifact generation failed (invocation=%s)",
                    invocation_id,
                )
                publish(
                    "error",
                    {
                        "error": "artifact_generation_failed",
                        "message": "Meeting artifacts could not be generated.",
                    },
                )
            except Exception:
                logger.exception(
                    "Unexpected streaming meeting failure (invocation=%s)",
                    invocation_id,
                )
                publish(
                    "error",
                    {
                        "error": "internal_error",
                        "message": "The meeting request failed unexpectedly.",
                    },
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        async with _run_slots:
            worker = asyncio.create_task(asyncio.to_thread(run))
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    event, data = item
                    yield _ndjson(event, data)
            finally:
                await worker

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


app.add_route("/invocations_stream", handle_invoke_stream, methods=["POST"])


@lru_cache(maxsize=1)
def _get_analyzer() -> Analyzer:
    mode = os.environ.get("MEETING_AGENT_ANALYZER", "managed").strip().casefold()
    if mode != "managed":
        raise RuntimeError("MEETING_AGENT_ANALYZER must be 'managed'")
    return ManagedAgentAnalyzer()


def _session_home() -> Path:
    configured = os.environ.get("MEETING_AGENT_SESSION_HOME")
    return Path(configured).expanduser().resolve() if configured else Path.home()


async def _request_payload(request: Request) -> dict[str, object] | Response:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_REQUEST_BYTES:
                return _error(413, "request_too_large", "Request body exceeds 2 MiB.")
        except ValueError:
            return _error(400, "invalid_content_length", "Content-Length is invalid.")
    body = await request.body()
    if len(body) > MAX_REQUEST_BYTES:
        return _error(413, "request_too_large", "Request body exceeds 2 MiB.")
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error(400, "invalid_json", "Request body must be valid JSON.")
    if not isinstance(payload, dict):
        return _error(400, "invalid_json", "Request body must be a JSON object.")
    return payload


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"error": code, "message": message},
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


def _ndjson(event: str, data: dict[str, object]) -> bytes:
    payload = json.dumps(
        {"type": event, "data": data},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"{payload}\n".encode()


def main() -> None:
    port_value = os.environ.get("PORT")
    if port_value is None:
        app.run()
        return
    try:
        port = int(port_value)
    except ValueError as error:
        raise RuntimeError("PORT must be an integer") from error
    if not 1 <= port <= 65_535:
        raise RuntimeError("PORT must be between 1 and 65535")
    app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()