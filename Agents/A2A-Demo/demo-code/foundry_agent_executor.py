"""
AI Foundry Agent Executor for the A2A framework.
Adaptation of the ADK executor pattern for Azure AI Foundry agents.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, List

# ────────────────────────────────────────────────
#  Import from the original file: foundry_agent.py
#  (Do NOT change unless you rename that file)
# ────────────────────────────────────────────────
from foundry_agent import (
    FoundryCalendarAgent,
    create_foundry_calendar_agent,
)

from a2a.server.agent_execution import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    AgentCard,
    FilePart,
    FileWithBytes,
    FileWithUri,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils.message import new_agent_text_message

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class FoundryAgentExecutor(AgentExecutor):
    """
    Runs an Azure AI Foundry calendar agent inside the A2A execution runtime.
    """

    def __init__(self, card: AgentCard):
        self._card = card
        self._foundry_agent: Optional[FoundryCalendarAgent] = None
        self._threads: Dict[str, str] = {}  # context-id → thread-id

    # ------------------------------------------------------------------ #
    #                        Agent / thread helpers                       #
    # ------------------------------------------------------------------ #
    async def _get_or_create_agent(self) -> FoundryCalendarAgent:
        """
        Lazy-instantiate the underlying Foundry agent.
        `card.name` is used as the remote agent name so that different
        executors do not interfere with each other.
        """
        if not self._foundry_agent:
            self._foundry_agent = await create_foundry_calendar_agent(self._card.name)
        return self._foundry_agent

    async def _get_or_create_thread(self, context_id: str) -> str:
        """
        Return the thread-id bound to the given context-id.
        A new thread is created on first encounter.
        """
        if context_id not in self._threads:
            agent = await self._get_or_create_agent()
            thread = await agent.create_thread()
            self._threads[context_id] = thread.id
            logger.info("🧵 New thread %s for context %s", thread.id, context_id)
        return self._threads[context_id]

    # ------------------------------------------------------------------ #
    #                        Core processing logic                        #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _parts_to_text(parts: List[Part]) -> str:
        """Flatten A2A message parts into plain text."""
        acc: List[str] = []
        for p in parts:
            root = p.root
            if isinstance(root, TextPart):
                acc.append(root.text)
            elif isinstance(root, FilePart):
                if isinstance(root.file, FileWithUri):
                    acc.append(f"[File: {root.file.uri}]")
                elif isinstance(root.file, FileWithBytes):
                    acc.append(f"[File: {len(root.file.bytes)} bytes]")
            else:
                logger.warning("Unsupported part %s ignored", type(root))
        return " ".join(acc)

    async def _process_request(self, context: RequestContext, updater: TaskUpdater) -> None:
        """Convert the incoming request, call the Foundry agent, stream responses."""
        user_text = self._parts_to_text(context.message.parts)

        # Notify start
        updater.update_status(
            TaskState.working,
            message=new_agent_text_message("Processing your request...", context_id=context.context_id),
        )

        agent     = await self._get_or_create_agent()
        thread_id = await self._get_or_create_thread(context.context_id)

        responses = await agent.run_conversation(thread_id, user_text)

        # Stream incremental replies
        for resp in responses:
            updater.update_status(
                TaskState.working,
                message=new_agent_text_message(resp, context_id=context.context_id),
            )

        # Mark as complete
        updater.complete(
            message=new_agent_text_message(
                responses[-1] if responses else "Task completed.",
                context_id=context.context_id,
            )
        )

    # ------------------------------------------------------------------ #
    #                   AgentExecutor interface methods                  #
    # ------------------------------------------------------------------ #
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info("👉 execute called for ctx=%s", context.context_id)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)

        if not context.current_task:
            updater.submit()
        updater.start_work()

        try:
            await self._process_request(context, updater)
        except Exception as exc:
            logger.exception("Execution error")
            updater.failed(
                message=new_agent_text_message(f"Error: {exc}", context_id=context.context_id)
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        logger.info("⚠️  cancel called for ctx=%s", context.context_id)
        TaskUpdater(event_queue, context.task_id, context.context_id).fail(
            message=new_agent_text_message("Task cancelled by user", context_id=context.context_id)
        )

    async def cleanup(self) -> None:
        if self._foundry_agent:
            await self._foundry_agent.cleanup_agent()
            self._foundry_agent = None
        self._threads.clear()
        logger.info("🧹 FoundryAgentExecutor cleanup finished")


# Factory used by A2A server bootstrap
def create_foundry_agent_executor(card: AgentCard) -> FoundryAgentExecutor:
    return FoundryAgentExecutor(card)