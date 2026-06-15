# Copyright (c) Microsoft. All rights reserved.
"""
DevUI Launcher for Multi-Stage HITL Workflow

This script creates a DevUI visualization server for the hitl_agent.py workflow.
It builds the workflow structure and serves it on port 8080 for ReactFlow visualization.

Usage:
    python hitl_devui.py
    
The DevUI will be available at: http://localhost:8080
"""

import sys
import os

# Fix Windows console encoding to support emoji and Unicode
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding='utf-8', errors='replace'
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding='utf-8', errors='replace'
    )

from dotenv import load_dotenv
from agent_framework import (
    AgentExecutor,
    WorkflowBuilder,
)
from agent_framework.azure import AzureOpenAIChatClient

# Import executors from the HITL workflow
import sys
sys.path.insert(0, os.path.dirname(__file__))

from hitl_agent import (
    WorkflowCoordinator,
    StageExecutor,
    HumanReviewerExecutor,
    Stage,
)


def create_workflow():
    """
    Create the multi-stage HITL workflow structure for DevUI visualization.
    
    This creates the same workflow structure as in hitl_agent.py
    but only for visualization purposes (no actual execution).
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Azure OpenAI configuration
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-chat")
    
    if not endpoint or not api_key:
        print("❌ Error: Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables")
        sys.exit(1)
    
    # Create chat client
    chat_client = AzureOpenAIChatClient(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2025-01-01-preview",
        max_tokens=1500,
    )
    
    # Create 4 specialized agents
    researcher_agent = chat_client.create_agent(
        instructions="Professional researcher responsible for collecting and organizing relevant materials. Provides detailed and accurate information."
    )
    
    outline_agent = chat_client.create_agent(
        instructions="Document architect responsible for designing clear document structures and outlines. Ensures logical clarity and hierarchical organization."
    )
    
    writer_agent = chat_client.create_agent(
        instructions="Professional technical writer responsible for composing detailed document content. Language is professional and content is substantial."
    )
    
    editor_agent = chat_client.create_agent(
        instructions="Professional editor responsible for refining and formatting documents. Ensures fluent language and standardized formatting."
    )
    
    # Create Agent Executors
    researcher_exec = AgentExecutor(agent=researcher_agent, id="researcher_agent")
    outline_exec = AgentExecutor(agent=outline_agent, id="outline_agent")
    writer_exec = AgentExecutor(agent=writer_agent, id="writer_agent")
    editor_exec = AgentExecutor(agent=editor_agent, id="editor_agent")
    
    # Create Stage Executors (wrappers around AgentExecutors)
    researcher = StageExecutor(researcher_exec, Stage.RESEARCH, "researcher")
    outline_designer = StageExecutor(outline_exec, Stage.OUTLINE, "outline_designer")
    writer = StageExecutor(writer_exec, Stage.WRITING, "writer")
    editor = StageExecutor(editor_exec, Stage.EDITING, "editor")
    
    # Create coordinator and human reviewer
    coordinator = WorkflowCoordinator()
    human_reviewer = HumanReviewerExecutor()
    
    # Build the complex workflow with 14 executors and 16 edges
    workflow = (
        WorkflowBuilder()
        .set_start_executor(coordinator)
        # Coordinator -> Stage Executors
        .add_edge(coordinator, researcher)
        .add_edge(coordinator, outline_designer)
        .add_edge(coordinator, writer)
        .add_edge(coordinator, editor)
        # Stage Executors -> Agents
        .add_edge(researcher, researcher_exec)
        .add_edge(outline_designer, outline_exec)
        .add_edge(writer, writer_exec)
        .add_edge(editor, editor_exec)
        # Agents -> Stage Executors
        .add_edge(researcher_exec, researcher)
        .add_edge(outline_exec, outline_designer)
        .add_edge(writer_exec, writer)
        .add_edge(editor_exec, editor)
        # Stage Executors -> Coordinator
        .add_edge(researcher, coordinator)
        .add_edge(outline_designer, coordinator)
        .add_edge(writer, coordinator)
        .add_edge(editor, coordinator)
        # Coordinator -> Human Reviewer
        .add_edge(coordinator, human_reviewer)
        # Human Reviewer -> Coordinator
        .add_edge(human_reviewer, coordinator)
        .build()
    )
    
    return workflow


def main():
    """
    Main entry point - creates workflow and starts DevUI server.
    """
    print("=" * 70)
    print("🚀 Starting DevUI Server for Multi-Stage HITL Workflow")
    print("=" * 70)
    print()
    print("📊 Workflow Structure:")
    print("   - 4 Stages: Research → Outline → Writing → Editing")
    print("   - 4 Specialized Agents (Researcher, Architect, Writer, Editor)")
    print("   - 14 Executors total")
    print("   - 16 Edges (connections)")
    print("   - 4 Human-in-the-Loop approval points")
    print()
    print("🌐 DevUI will be available at: http://localhost:8080")
    print("=" * 70)
    print()
    
    try:
        # Create workflow
        workflow = create_workflow()
        
        # Import and start DevUI server
        try:
            from agent_framework.devui import serve
        except ImportError:
            print("❌ Error: agent-framework-devui package not installed")
            print("   Please install it: pip install agent-framework-devui --pre")
            sys.exit(1)
        
        print("✅ Workflow created successfully")
        print("🔧 Starting DevUI server on port 8080...")
        print()
        
        # Serve the workflow visualization
        serve(entities=[workflow], port=8080, auto_open=True)
        
    except KeyboardInterrupt:
        print("\n⚠️  Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


