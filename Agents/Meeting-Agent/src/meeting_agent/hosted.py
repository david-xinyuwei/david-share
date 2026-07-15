"""Microsoft Foundry Invocations host for Meeting Agent."""

from __future__ import annotations

import asyncio
import logging
import os
from functools import lru_cache
from pathlib import Path

from azure.ai.agentserver.invocations import InvocationAgentServerHost
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .analyzers import (
    Analyzer,
    AzureOpenAIAnalyzer,
    FoundryOpenAIAnalyzer,
    OfflineContractAnalyzer,
)
from .hosted_models import HostedMeetingRequest, HostedMeetingResponse
from .hosted_pipeline import build_hosted_run

logger = logging.getLogger("meeting_agent.hosted")


def _openapi_spec() -> dict[str, object]:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Meeting Agent Invocations API",
            "version": "1.0.0",
            "description": (
                "Build a meeting summary, mind map, PowerPoint, and unsent email draft. "
                "Generated files are available through the Foundry session files API."
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
                        "503": {"description": "Foundry runtime is not configured"},
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
    try:
        payload = await request.json()
    except Exception:
        return _error(400, "invalid_json", "Request body must be valid JSON.")

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
            "Meeting analysis is unavailable. Verify the Foundry model configuration and retry.",
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


@lru_cache(maxsize=1)
def _get_analyzer() -> Analyzer:
    mode = os.environ.get("MEETING_AGENT_ANALYZER", "foundry").strip().casefold()
    if mode == "foundry":
        return FoundryOpenAIAnalyzer()
    if mode == "azure":
        return AzureOpenAIAnalyzer()
    if mode == "offline-contract":
        if os.environ.get("MEETING_AGENT_ENABLE_OFFLINE_CONTRACT") != "1":
            raise RuntimeError("offline-contract analyzer is disabled")
        return OfflineContractAnalyzer()
    raise RuntimeError(f"unsupported MEETING_AGENT_ANALYZER value: {mode!r}")


def _session_home() -> Path:
    configured = os.environ.get("MEETING_AGENT_SESSION_HOME")
    return Path(configured).expanduser().resolve() if configured else Path.home()


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"error": code, "message": message},
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


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
    app.run(port=port)


if __name__ == "__main__":
    main()