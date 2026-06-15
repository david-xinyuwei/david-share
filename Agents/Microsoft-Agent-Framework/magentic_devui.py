# Copyright (c) Microsoft. All rights reserved.
"""
DevUI Launcher for Magentic Workflow

This script creates a DevUI visualization server for the Magentic workflow
defined in magentic_agent.py. It mirrors the structure used by hitl_devui.py
and provides helpful logging plus environment validation before launching the
DevUI on port 8080.

Usage:
    python magentic_devui.py

The DevUI will be available at: http://localhost:8080
"""

import sys
import os

# Fix Windows console encoding to support emoji and Unicode output
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding="utf-8",
        errors="replace",
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer,
        encoding="utf-8",
        errors="replace",
    )

from dotenv import load_dotenv

# Ensure local imports resolve when running as a script
sys.path.insert(0, os.path.dirname(__file__))

from magentic_agent import InteractiveMagenticOrchestrator


def create_orchestrator():
    """Create the Magentic orchestrator for DevUI visualization."""
    load_dotenv()

    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = (
        os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        or "gpt-5-chat"
    )

    if not endpoint or not api_key:
        print(
            "❌ Error: Please set AZURE_OPENAI_ENDPOINT and "
            "AZURE_OPENAI_API_KEY environment variables"
        )
        sys.exit(1)

    print("🔄 Preparing Magentic orchestrator...")
    orchestrator = InteractiveMagenticOrchestrator()
    print(
        "✅ Magentic orchestrator created — available agents: Weather, "
        "Calculator, Travel"
    )
    print(f"   Using deployment: {deployment}")
    return orchestrator


def main():
    """Main entry point — create orchestrator and start DevUI server."""
    print("=" * 70)
    print("🚀 Starting DevUI Server for Magentic Workflow")
    print("=" * 70)
    print()
    print("📊 Visualization includes:")
    print("   - Magentic orchestrator with Weather, Calculator, Travel agents")
    print("   - Interactive manager with follow-up support")
    print("   - Streamed event graph suitable for DevUI exploration")
    print()
    print("🌐 DevUI will be available at: http://localhost:8080")
    print("=" * 70)
    print()

    try:
        orchestrator = create_orchestrator()

        try:
            from agent_framework.devui import serve
        except ImportError:
            print("❌ Error: agent-framework-devui package not installed")
            print(
                "   Please install it: pip install agent-framework-devui "
                "--pre"
            )
            sys.exit(1)

        print("🔧 Starting DevUI server on port 8080...")
        serve(entities=[orchestrator.workflow], port=8080, auto_open=True)

    except KeyboardInterrupt:
        print("\n⚠️  Server stopped by user")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"\n❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()