# Copyright (c) Microsoft. All rights reserved.
"""
Simple test script for MagenticBuilder with Azure OpenAI GPT-5-chat
Run this after setting environment variables.
"""
import asyncio
import os
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework._workflows import MagenticBuilder
from agent_framework._workflows._magentic import MagenticFinalResultEvent, MagenticAgentMessageEvent

async def main():
    # Read credentials from environment variables
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5-chat")
    
    if not endpoint or not api_key:
        print("❌ Error: Please set environment variables:")
        print("   AZURE_OPENAI_ENDPOINT")
        print("   AZURE_OPENAI_API_KEY")
        print("   AZURE_OPENAI_DEPLOYMENT_NAME (optional, defaults to 'gpt-5-chat')")
        return
    
    print(f"✅ Using endpoint: {endpoint}")
    print(f"✅ Using deployment: {deployment}")
    print()
    
    # Create Azure OpenAI chat client
    chat_client = AzureOpenAIChatClient(
        azure_endpoint=endpoint,
        api_key=api_key,
        deployment_name=deployment,
        api_version="2025-01-01-preview"
    )
    
    # Create a simple research agent
    researcher = ChatAgent(
        chat_client=chat_client,
        instructions="You are a helpful research assistant. Provide concise, accurate answers."
    )
    
    # Create a writer agent
    writer = ChatAgent(
        chat_client=chat_client,
        instructions="You are a skilled writer. Transform research into clear, engaging content."
    )
    
    # Build Magentic workflow
    print("🚀 Building Magentic workflow...")
    workflow = (
        MagenticBuilder()
        .participants(researcher=researcher, writer=writer)
        .with_standard_manager(chat_client=chat_client, max_round_count=5)
        .build()
    )
    
    # Test task
    task = "What are the key benefits of using AI agents in software development? Provide a brief 2-paragraph summary."
    
    print(f"📝 Task: {task}")
    print()
    print("⏳ Running workflow with GPT-5-chat...")
    print("-" * 60)
    
    try:
        # Run the workflow and collect events
        final_text = None
        
        async for event in workflow.run_stream(task):
            # Look for the final result event
            if isinstance(event, MagenticFinalResultEvent):
                if hasattr(event.message, 'text'):
                    final_text = event.message.text
            elif isinstance(event, MagenticAgentMessageEvent):
                # Collect writer messages as backup
                if event.agent_id == 'writer' and hasattr(event.message, 'text'):
                    final_text = event.message.text  # Keep updating with latest writer output
        
        print()
        print("=" * 60)
        print("✅ WORKFLOW COMPLETED!")
        print("=" * 60)
        print()
        print("📊 Final Answer:")
        print()
        
        if final_text:
            print(final_text)
        else:
            print("⚠️ Could not extract final text from workflow events")
        
        print()
        print("✨ Success! GPT-5-chat is working with MagenticBuilder!")
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERROR OCCURRED")
        print("=" * 60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print()
        print("💡 Troubleshooting tips:")
        print("1. Verify your API key is correct")
        print("2. Check that the deployment name 'gpt-5-chat' exists in your Azure OpenAI resource")
        print("3. Ensure your Azure subscription has access to GPT-5-chat")
        print("4. Try using a different API version (e.g., '2024-10-21')")

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Magentic + GPT-5-chat Test")
    print("=" * 60)
    print()
    asyncio.run(main())
