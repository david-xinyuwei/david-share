# Copyright (c) Microsoft. All rights reserved.
"""
HITL Workflow: DevUI Trigger + Terminal Approval
- Trigger workflow from DevUI browser interface
- Approve in Terminal window
- Visualization updates in real-time
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from agent_framework import AgentExecutor, WorkflowBuilder
from agent_framework.azure import AzureOpenAIChatClient
from hitl_agent import (
    WorkflowCoordinator,
    StageExecutor,
    HumanReviewerExecutor,
    Stage,
)


def create_workflow():
    """Create HITL workflow"""
    load_dotenv()
    
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-chat")
    
    if not endpoint or not api_key:
        print("❌ Error: Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY")
        sys.exit(1)
    
    # Create chat client
    chat_client = AzureOpenAIChatClient(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2025-01-01-preview",
        max_tokens=1500,
    )
    
    # Create 4 agents
    researcher_agent = chat_client.create_agent(
        instructions="Professional researcher responsible for collecting materials."
    )
    outline_agent = chat_client.create_agent(
        instructions="Document architect responsible for structure design."
    )
    writer_agent = chat_client.create_agent(
        instructions="Technical writer responsible for content composition."
    )
    editor_agent = chat_client.create_agent(
        instructions="Editor responsible for refining and formatting."
    )
    
    # Create agent executors
    researcher_exec = AgentExecutor(agent=researcher_agent, id="researcher_agent")
    outline_exec = AgentExecutor(agent=outline_agent, id="outline_agent")
    writer_exec = AgentExecutor(agent=writer_agent, id="writer_agent")
    editor_exec = AgentExecutor(agent=editor_agent, id="editor_agent")
    
    # Create stage executors
    researcher = StageExecutor(researcher_exec, Stage.RESEARCH, "researcher")
    outline_designer = StageExecutor(outline_exec, Stage.OUTLINE, "outline_designer")
    writer = StageExecutor(writer_exec, Stage.WRITING, "writer")
    editor = StageExecutor(editor_exec, Stage.EDITING, "editor")
    
    # Create coordinator and human reviewer
    coordinator = WorkflowCoordinator()
    human_reviewer = HumanReviewerExecutor()
    
    # Build workflow (14 executors, 16 edges)
    workflow = (
        WorkflowBuilder()
        .set_start_executor(coordinator)
        .add_edge(coordinator, researcher)
        .add_edge(coordinator, outline_designer)
        .add_edge(coordinator, writer)
        .add_edge(coordinator, editor)
        .add_edge(researcher, researcher_exec)
        .add_edge(outline_designer, outline_exec)
        .add_edge(writer, writer_exec)
        .add_edge(editor, editor_exec)
        .add_edge(researcher_exec, researcher)
        .add_edge(outline_exec, outline_designer)
        .add_edge(writer_exec, writer)
        .add_edge(editor_exec, editor)
        .add_edge(researcher, coordinator)
        .add_edge(outline_designer, coordinator)
        .add_edge(writer, coordinator)
        .add_edge(editor, coordinator)
        .add_edge(coordinator, human_reviewer)
        .add_edge(human_reviewer, coordinator)
        .build()
    )
    
    return workflow


def main():
    """Main entry point"""
    print("="*70)
    print("🚀 HITL Workflow - DevUI Trigger + Terminal Approval")
    print("="*70)
    print()
    print("📌 How to use:")
    print("   1. Browser: Open http://localhost:8080")
    print("   2. Browser: Enter topic in DevUI input box")
    print("   3. Terminal: Approval prompts will appear HERE")
    print("   4. Terminal: Type 'y' or 'n' to approve/reject")
    print("   5. Browser: Watch workflow visualization update")
    print()
    print("="*70)
    print()
    
    # Create workflow
    print("Creating workflow...")
    workflow = create_workflow()
    print("✅ Workflow created (14 executors, 16 edges)")
    print()
    
    # Start DevUI server
    try:
        from agent_framework_devui import serve
    except ImportError:
        print("❌ Error: agent-framework-devui not installed")
        print("   Install: pip install agent-framework-devui --pre")
        sys.exit(1)
    
    print("🌐 Starting DevUI server on port 8080...")
    print()
    print("="*70)
    print("✅ DevUI Ready: http://localhost:8080")
    print("="*70)
    print()
    print("⏳ Waiting for workflow execution from DevUI...")
    print("   (Enter a topic in the browser to start)")
    print()
    
    # Serve workflow - this will handle approval prompts in Terminal
    serve(entities=[workflow], port=8080, auto_open=True)


if __name__ == "__main__":
    main()
