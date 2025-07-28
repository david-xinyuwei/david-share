from __future__ import annotations

import datetime
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    Agent,
    AgentThread,
    ListSortOrder,
    ThreadMessage,
    ThreadRun,
    ToolOutput,
)
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


class FoundryCalendarAgent:
    """
    A calendar-management agent running on Azure AI Foundry.
    """

    def __init__(self, name: str = "Calendar-Agent"):
        # Custom name → multiple logical agents in one project
        self.endpoint = os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"]
        self.credential = DefaultAzureCredential()
        self.name = name

        self.agent: Optional[Agent] = None
        self.threads: Dict[str, str] = {}  # context-id → thread-id

    # ------------------------------------------------------------------ #
    #                       Foundry client helper                         #
    # ------------------------------------------------------------------ #
    def _client(self) -> AgentsClient:
        """Return a new AgentsClient (context-manager friendly)."""
        return AgentsClient(
            endpoint=self.endpoint,
            credential=self.credential,
            api_version="2024-05-01-preview",
        )

    # ------------------------------------------------------------------ #
    #                          Agent bootstrap                            #
    # ------------------------------------------------------------------ #
    async def create_agent(self) -> Agent:
        """Create the remote agent once, reuse afterwards."""
        if self.agent:
            return self.agent

        with self._client() as cli:
            self.agent = cli.create_agent(
                model=os.environ["AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"],
                name=self.name,
                instructions=self._instructions(),
                tools=self._tools(),
            )
            logger.info("✅ Created agent %s (%s)", self.agent.id, self.name)
            return self.agent

    # --------------------------- instructions ------------------------- #
    @staticmethod
    def _instructions() -> str:
        """System prompt – create meeting immediately when asked."""
        now = datetime.datetime.now().isoformat()
        return f"""You are an intelligent calendar assistant.

Capabilities
• Check availability
• Create meeting events
• Suggest optimal time slots

Rules
1. If the user only asks whether a slot is free, answer free / busy.
2. If the user explicitly asks to schedule / create a meeting,
   create it right away and respond exactly:

   “Meeting 『<title>』 has been created for <start> – <end>.”

3. Use RFC-3339 timestamps; default calendar is 'primary'.
4. No additional confirmation.
Current server time: {now}
"""

    # ----------------------------- tools ------------------------------ #
    @staticmethod
    def _tools() -> List[Dict[str, Any]]:
        """Return mock tool definitions."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Return whether a slot is free.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "start_time": {"type": "string"},
                            "end_time": {"type": "string"},
                            "calendar_id": {
                                "type": "string",
                                "default": "primary",
                            },
                        },
                        "required": ["start_time", "end_time"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_upcoming_events",
                    "description": "Return upcoming events.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_results": {"type": "integer", "default": 10},
                            "time_range_hours": {"type": "integer", "default": 24},
                        },
                    },
                },
            },
        ]

    # ------------------------------------------------------------------ #
    #                          Thread helpers                            #
    # ------------------------------------------------------------------ #
    async def create_thread(self) -> AgentThread:
        with self._client() as cli:
            th = cli.threads.create()
            self.threads[th.id] = th.id
            logger.info("🧵 Thread %s created (%s)", th.id, self.name)
            return th

    async def _push(
        self, thread_id: str, text: str, role: str = "user"
    ) -> ThreadMessage:
        with self._client() as cli:
            return cli.messages.create(thread_id=thread_id, role=role, content=text)

    # ------------------------------------------------------------------ #
    #                       Main conversation loop                        #
    # ------------------------------------------------------------------ #
    async def run_conversation(self, thread_id: str, user_text: str) -> List[str]:
        if not self.agent:
            await self.create_agent()

        await self._push(thread_id, user_text)

        with self._client() as cli:
            run = cli.runs.create(thread_id=thread_id, agent_id=self.agent.id)

            # Poll until tool calls (if any) are done
            while run.status in ("queued", "in_progress", "requires_action"):
                time.sleep(1)
                run = cli.runs.get(thread_id, run.id)
                if run.status == "requires_action":
                    await self._handle_tool_calls(run, thread_id)

            # Collect assistant replies
            msgs = cli.messages.list(thread_id, order=ListSortOrder.DESCENDING)
            answers = [
                t.text.value
                for m in msgs
                if m.role == "assistant"
                for t in (m.text_messages or [])
            ]
            return answers or ["(no reply)"]

    # ------------------------------------------------------------------ #
    #                  Mock tool-call fulfilment (demo)                  #
    # ------------------------------------------------------------------ #
    async def _handle_tool_calls(self, run: ThreadRun, thread_id: str):
        required = getattr(run, "required_action", None)
        if not required:
            return

        outputs: List[Dict[str, str]] = []
        for tc in required.submit_tool_outputs.tool_calls:
            fn = tc.function.name
            if fn == "check_availability":
                payload = {"available": True, "message": "The slot is free."}
            elif fn == "get_upcoming_events":
                payload = {"events": []}
            else:
                payload = {"error": f"Unknown function {fn}"}

            outputs.append({"tool_call_id": tc.id, "output": json.dumps(payload)})

        with self._client() as cli:
            cli.runs.submit_tool_outputs(
                thread_id=thread_id, run_id=run.id, tool_outputs=outputs
            )

    # ------------------------------------------------------------------ #
    #                              Cleanup                               #
    # ------------------------------------------------------------------ #
    async def cleanup_agent(self):
        if self.agent:
            with self._client() as cli:
                cli.delete_agent(self.agent.id)
            self.agent = None
            logger.info("🗑️  Deleted %s", self.name)


# ---------------------------------------------------------------------- #
#                      factory used by the executor                      #
# ---------------------------------------------------------------------- #
async def create_foundry_calendar_agent(name: str = "Calendar-Agent") -> FoundryCalendarAgent:
    """
    Convenience factory expected by foundry_agent_executor.py.
    Returns an agent instance with its remote resource already created.
    """
    agent = FoundryCalendarAgent(name=name)
    await agent.create_agent()
    return agent