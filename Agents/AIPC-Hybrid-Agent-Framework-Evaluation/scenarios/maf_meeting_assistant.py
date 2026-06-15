"""
AIPC Meeting Assistant — Microsoft Agent Framework Implementation

Demonstrates: WorkflowBuilder + executors + RequestInfoExecutor for durable HITL workflows.
This is a skeleton showing the framework's approach; fill in real tools for production.
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()


# --- Executor functions (each step in the workflow) ---

async def transcribe_executor(context) -> dict:
    """Step 1: Local transcription. Runs on-device via Ollama or local Whisper."""
    audio_path = context.state.get("audio_path", "/tmp/meeting.wav")
    transcript = f"[Transcription of {audio_path}] Meeting discussed Q3 targets..."
    return {"transcript": transcript}


async def extract_executor(context) -> dict:
    """Step 2: Extract action items. MAF can use different providers per executor."""
    # In production: use context.agent with Ollama provider for local,
    # or Azure OpenAI provider for complex reasoning
    action_items = [
        {"assignee": "Alice", "task": "Prepare Q3 budget draft", "deadline": "Friday"},
        {"assignee": "Bob", "task": "Review vendor proposals", "deadline": "Next Monday"},
    ]
    return {"action_items": action_items}


async def draft_executor(context) -> dict:
    """Step 3: Draft email using cloud LLM (Azure OpenAI provider)."""
    action_items = context.state.get("action_items", [])
    items_text = "\n".join(
        f"- {item['assignee']}: {item['task']} (by {item['deadline']})"
        for item in action_items
    )
    return {"email_draft": f"Subject: Meeting Follow-up\n\nAction items:\n{items_text}"}


async def send_executor(context) -> dict:
    """Step 5: Send email (only if approved)."""
    if not context.state.get("approved", False):
        return {"result": "Email cancelled by user."}
    # In production: call Microsoft Graph API via MAF tool
    return {"result": "Email sent successfully."}


# --- Build the workflow ---

async def build_and_run():
    """
    MAF approach: WorkflowBuilder with graph-based orchestration.

    Key characteristics:
    - WorkflowBuilder defines a directed graph of executors
    - RequestInfoExecutor provides native HITL (pauses workflow, collects user input)
    - Checkpointing at superstep boundaries for crash recovery
    - Built-in OpenTelemetry for observability
    - Can deploy to Foundry Hosted Agents with 2 additional lines
    - Supports both Python and C#/.NET with consistent APIs
    """
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import AzureCliCredential

    # In a full implementation, you would use:
    # 1. WorkflowBuilder to define the graph
    # 2. Add executors for each step
    # 3. Add a RequestInfoExecutor for the HITL approval gate
    # 4. Compile and run with checkpointing enabled

    # Simplified demonstration of the agent creation pattern:
    agent = Agent(
        client=FoundryChatClient(
            credential=AzureCliCredential(),
        ),
        name="MeetingAssistant",
        instructions=(
            "You are an AIPC meeting assistant. "
            "Transcribe meetings, extract action items, draft follow-up emails, "
            "and request user approval before sending."
        ),
    )

    # In production, you would build a full WorkflowBuilder graph:
    #
    # workflow = WorkflowBuilder()
    # workflow.add_executor("transcribe", transcribe_executor)
    # workflow.add_executor("extract", extract_executor)
    # workflow.add_executor("draft", draft_executor)
    # workflow.add_executor("approval", RequestInfoExecutor(
    #     prompt="Do you approve sending this email?",
    #     schema={"approved": bool}
    # ))
    # workflow.add_executor("send", send_executor)
    #
    # workflow.add_edge(START, "transcribe")
    # workflow.add_edge("transcribe", "extract")
    # workflow.add_edge("extract", "draft")
    # workflow.add_edge("draft", "approval")
    # workflow.add_edge("approval", "send")
    # workflow.add_edge("send", END)
    #
    # compiled = workflow.compile(checkpointing=True)
    # result = await compiled.run({"audio_path": "/tmp/meeting.wav"})

    result = await agent.run(
        "Process the meeting recording at /tmp/meeting.wav. "
        "Extract action items and draft a follow-up email."
    )
    print(result)


def main():
    asyncio.run(build_and_run())


if __name__ == "__main__":
    main()
