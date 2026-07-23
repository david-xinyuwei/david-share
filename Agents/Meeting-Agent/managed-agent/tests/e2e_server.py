"""Test-only Hosted Agent process with an explicitly injected fixture analyzer."""

from __future__ import annotations

import asyncio
import os
from itertools import cycle

from hypercorn.asyncio import serve
from hypercorn.config import Config

from meeting_agent import hosted
from tests.support import StaticFixtureAnalyzer, sample_analysis

ANALYSES = cycle(
    (
        sample_analysis("product-planning"),
        sample_analysis("operations-review"),
    )
)


def _test_analyzer() -> StaticFixtureAnalyzer:
    return StaticFixtureAnalyzer(
        next(ANALYSES),
        response_id="test-fixture-response",
        deltas=('{"fixture":true}',),
    )


async def _app(scope, receive, send) -> None:
    if scope["type"] != "lifespan":
        await hosted.app(scope, receive, send)
        return
    while True:
        message = await receive()
        if message["type"] == "lifespan.startup":
            await send({"type": "lifespan.startup.complete"})
        elif message["type"] == "lifespan.shutdown":
            await send({"type": "lifespan.shutdown.complete"})
            return


def main() -> None:
    mode = os.environ.get("MEETING_AGENT_E2E_MODE", "fixture")
    if mode not in {"fixture", "live"}:
        raise RuntimeError("MEETING_AGENT_E2E_MODE must be fixture or live")
    if mode == "fixture":
        hosted._get_analyzer = _test_analyzer
    port = int(os.environ.get("PORT", "18088"))
    config = Config()
    config.bind = [f"127.0.0.1:{port}"]
    config.accesslog = "-"
    config.errorlog = "-"
    asyncio.run(serve(_app, config))


if __name__ == "__main__":
    main()