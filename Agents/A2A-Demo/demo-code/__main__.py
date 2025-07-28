from __future__ import annotations

import logging, os
from typing import List

import click, uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from foundry_agent_executor import create_foundry_agent_executor

# ───────────── env / logger ─────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

A2A_TOKEN = os.getenv("A2A_TOKEN") or "A2A-DEMO-SECRET"

# ────────── Bearer-Token middleware ───────
class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.headers.get("authorization") != f"Bearer {A2A_TOKEN}":
            return PlainTextResponse("Unauthorized", status_code=401)
        return await call_next(request)

def _env(k, d): return os.getenv(k, d)

# ────────────────── CLI ──────────────────
@click.command()
@click.option("--host", default=lambda: _env("HOST", "localhost"))
@click.option("--port", default=lambda: int(_env("PORT", 10007)), type=int)
def main(host: str, port: int):
    # 1) AgentCard
    agent_name = os.getenv("AGENT_NAME", "Calendar-Agent")
    skills: List[AgentSkill] = [
        AgentSkill(
            id="check_availability",
            name="Check Availability",
            description="Verify if the given time slot is free",
            tags=["calendar"],
        ),
        AgentSkill(
            id="get_upcoming_events",
            name="Upcoming Events",
            description="List upcoming meetings",
            tags=["calendar"],
        ),
    ]
    card = AgentCard(
        name=agent_name,
        description="Calendar agent powered by Azure AI Foundry.",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(streaming=True, auth="bearer"),
        skills=skills,
    )

    executor = create_foundry_agent_executor(card)
    handler  = DefaultRequestHandler(agent_executor=executor,
                                     task_store=InMemoryTaskStore())
    a2a_app  = A2AStarletteApplication(agent_card=card, http_handler=handler)
    routes   = a2a_app.routes()         
    async def health(_: Request): return PlainTextResponse("ok")
    routes.append(Route("/health", health, methods=["GET"]))

    app = Starlette(routes=routes)
    app.add_middleware(BearerAuthMiddleware)

    logger.info("Listening http://%s:%s/  (%s)", host, port, agent_name)
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()