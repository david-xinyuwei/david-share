"""
AIPC Meeting Assistant — LangChain Implementation

Demonstrates: create_agent + tools pattern with hybrid local/cloud model routing.
This is a skeleton showing the framework's approach; fill in real tools for production.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# --- Step 1: Define tools ---

def transcribe_audio(audio_path: str) -> str:
    """Local transcription using Whisper via Ollama or local binary."""
    # In production: call local Whisper model
    return f"[Transcription of {audio_path}] Meeting discussed Q3 targets..."


def extract_action_items(transcript: str) -> list[dict]:
    """Extract action items — uses local SLM for simple cases."""
    # In production: route to local SLM or cloud LLM based on complexity
    return [
        {"assignee": "Alice", "task": "Prepare Q3 budget draft", "deadline": "Friday"},
        {"assignee": "Bob", "task": "Review vendor proposals", "deadline": "Next Monday"},
    ]


def draft_email(action_items: list[dict]) -> str:
    """Draft follow-up email — uses cloud LLM for quality."""
    # In production: call Azure OpenAI with Graph API tool
    items_text = "\n".join(f"- {item['assignee']}: {item['task']} (by {item['deadline']})" for item in action_items)
    return f"Subject: Meeting Follow-up\n\nAction items:\n{items_text}"


def send_email(draft: str, approved: bool) -> str:
    """Send email via Graph API — requires HITL approval."""
    if not approved:
        return "Email sending cancelled by user."
    # In production: call Microsoft Graph API
    return "Email sent successfully."


# --- Step 2: Create agent with LangChain ---

def main():
    """
    LangChain approach: create_agent wraps model + tools in a minimal harness.

    Key characteristics:
    - Stateless by default (no built-in checkpointing)
    - Simple tool loop: model decides which tool to call
    - HITL must be implemented manually (input() or callback)
    - Local/cloud routing is manual (you choose which model to call)
    """
    from langchain.agents import create_agent
    from langchain_openai import AzureChatOpenAI

    # Cloud model for complex reasoning
    cloud_model = AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )

    # Create agent with tools
    agent = create_agent(
        model=cloud_model,
        tools=[transcribe_audio, extract_action_items, draft_email, send_email],
        system_prompt=(
            "You are an AIPC meeting assistant. "
            "Transcribe the meeting, extract action items, draft a follow-up email, "
            "and ask the user for approval before sending."
        ),
    )

    # Run the agent
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Process the meeting recording at /tmp/meeting.wav"}]}
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
