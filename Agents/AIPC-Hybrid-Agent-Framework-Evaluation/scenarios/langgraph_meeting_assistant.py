"""
AIPC Meeting Assistant — LangGraph Implementation

Demonstrates: StateGraph + checkpointer + interrupt() for durable HITL workflows.
This is a skeleton showing the framework's approach; fill in real tools for production.
"""

import os
from typing import TypedDict, Annotated
from dotenv import load_dotenv

load_dotenv()


# --- State definition ---

class MeetingState(TypedDict):
    """Typed state that flows through the graph. LangGraph persists this at each checkpoint."""
    audio_path: str
    transcript: str
    action_items: list[dict]
    email_draft: str
    approved: bool
    result: str


# --- Node functions (each step in the workflow) ---

def transcribe(state: MeetingState) -> dict:
    """Step 1: Local transcription. Runs on-device, no cloud call."""
    transcript = f"[Transcription of {state['audio_path']}] Meeting discussed Q3 targets..."
    return {"transcript": transcript}


def extract(state: MeetingState) -> dict:
    """Step 2: Extract action items. Can route to local SLM or cloud LLM."""
    # In production: use state['transcript'] complexity to decide local vs cloud
    action_items = [
        {"assignee": "Alice", "task": "Prepare Q3 budget draft", "deadline": "Friday"},
        {"assignee": "Bob", "task": "Review vendor proposals", "deadline": "Next Monday"},
    ]
    return {"action_items": action_items}


def draft(state: MeetingState) -> dict:
    """Step 3: Draft email using cloud LLM for quality."""
    items_text = "\n".join(
        f"- {item['assignee']}: {item['task']} (by {item['deadline']})"
        for item in state["action_items"]
    )
    return {"email_draft": f"Subject: Meeting Follow-up\n\nAction items:\n{items_text}"}


def approval_gate(state: MeetingState) -> dict:
    """Step 4: HITL approval. LangGraph's interrupt() pauses execution here."""
    from langgraph.types import interrupt

    # This is the key differentiator: interrupt() persists state and waits
    # The graph can be resumed later with the user's decision
    user_decision = interrupt(
        {
            "question": "Do you approve sending this email?",
            "draft": state["email_draft"],
        }
    )
    return {"approved": user_decision.get("approved", False)}


def send(state: MeetingState) -> dict:
    """Step 5: Send email (only if approved)."""
    if not state["approved"]:
        return {"result": "Email cancelled by user."}
    # In production: call Microsoft Graph API
    return {"result": "Email sent successfully."}


# --- Build the graph ---

def build_graph():
    """
    LangGraph approach: explicit state graph with typed state and checkpointing.

    Key characteristics:
    - State is typed (TypedDict) and persisted at each node boundary
    - interrupt() pauses the graph; resume later with user input
    - Checkpointer (SQLite) enables crash recovery
    - Each node is a pure function: state in → partial state out
    """
    from langgraph.graph import StateGraph, START, END
    from langgraph.checkpoint.sqlite import SqliteSaver

    graph = StateGraph(MeetingState)

    # Add nodes
    graph.add_node("transcribe", transcribe)
    graph.add_node("extract", extract)
    graph.add_node("draft", draft)
    graph.add_node("approval_gate", approval_gate)
    graph.add_node("send", send)

    # Add edges (linear pipeline)
    graph.add_edge(START, "transcribe")
    graph.add_edge("transcribe", "extract")
    graph.add_edge("extract", "draft")
    graph.add_edge("draft", "approval_gate")
    graph.add_edge("approval_gate", "send")
    graph.add_edge("send", END)

    # Compile with SQLite checkpointer for durability
    checkpointer = SqliteSaver.from_conn_string("meeting_checkpoints.db")
    return graph.compile(checkpointer=checkpointer)


def main():
    app = build_graph()

    # Start the workflow
    config = {"configurable": {"thread_id": "meeting-001"}}
    initial_state = {"audio_path": "/tmp/meeting.wav"}

    # This will run until it hits interrupt() at approval_gate
    for event in app.stream(initial_state, config=config):
        print(event)

    # In production: user reviews draft, then resumes with approval
    # app.invoke(Command(resume={"approved": True}), config=config)


if __name__ == "__main__":
    main()
