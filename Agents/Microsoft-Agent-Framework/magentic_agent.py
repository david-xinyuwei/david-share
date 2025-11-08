import logging
logging.getLogger('agent_framework').setLevel(logging.ERROR)

"""
🤖 Enhanced MagenticBuilder with User Interaction

Enhancement Approach:
1. Leverage MagenticBuilder's native orchestration capabilities
2. Capture Agent responses in event stream
3. Add user interaction logic - ask if user wants to follow up
4. Inject follow-up questions back into the workflow

Core Enhancements:
- Listen to MagenticAgentMessageEvent (Agent completion)
- Pause workflow to ask user for follow-up questions
- If user has questions, continue execution with new input

Install dependencies:
pip install agent-framework --pre
"""

import os
import asyncio
from dotenv import load_dotenv

from agent_framework import (
    MagenticBuilder,
    MagenticAgentMessageEvent,
    MagenticOrchestratorMessageEvent,
    MagenticAgentDeltaEvent,
    MagenticFinalResultEvent,
    WorkflowOutputEvent,
)
from agent_framework.azure import AzureOpenAIChatClient
from azure.core.credentials import AzureKeyCredential


class InteractiveMagenticOrchestrator:
    """Magentic Orchestrator with User Interaction Support"""
    
    def __init__(self):
        """Initialize"""
        load_dotenv()
        
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-chat")
        
        if not endpoint or not api_key:
            raise ValueError("Please set environment variables")
        
        # Create Chat Client
        self.chat_client = AzureOpenAIChatClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            deployment_name=deployment,
        )
        
        print(f"✅ Connected: {endpoint}")
        print(f"🎯 Deployment: {deployment}\n")
        
        # Create Agents
        self._create_agents()
        
        # Build Magentic Workflow
        self._build_workflow()
        
        # Interaction state
        self.interaction_enabled = True
    
    def _create_user_input_tool(self):
        """Create user input tool"""
        def ask_user(question: str) -> str:
            """
            Ask the user for information.
            
            Args:
                question: The question to ask
                
            Returns:
                User's answer
            """
            print(f"\n{'='*60}")
            print(f"❓ {self.__class__.__name__} needs your information:")
            print(f"{'='*60}")
            answer = input(f"{question}\nYour answer: ").strip()
            print(f"{'='*60}\n")
            return answer
        
        return ask_user
    
    def _create_agents(self):
        """Create all Agents"""
        # Create user input tool
        ask_user_tool = self._create_user_input_tool()
        
        self.weather_agent = self.chat_client.create_agent(
            name="WeatherAgent",
            description="Weather query expert",
            instructions=(
                "You are a weather query expert. You can query weather "
                "conditions for any city and answer concisely."
            )
        )
        
        self.calculator_agent = self.chat_client.create_agent(
            name="CalculatorAgent",
            description="Mathematical calculation expert",
            instructions=(
                "You are a mathematical calculation expert. You can perform "
                "various math calculations including arithmetic, algebra, "
                "statistics, etc. Provide detailed calculation steps and "
                "final answers. For complex problems, explain the calculation "
                "process step by step."
            )
        )
        
        self.travel_agent = self.chat_client.create_agent(
            name="TravelAgent",
            description="Travel planning expert",
            instructions=(
                "You are a travel planning expert. You can provide users with "
                "travel advice, itinerary planning, attraction recommendations, "
                "etc. Provide practical and detailed travel suggestions.\n\n"
                "**IMPORTANT**: If you need user's personal information "
                "(such as ID number, age, nationality, travel dates, etc.) "
                "to provide more accurate advice, use the ask_user tool to "
                "ask the user. For example: ask_user('Please provide your "
                "age and travel dates')"
            ),
            tools=[ask_user_tool]  # Add user input tool
        )
        
        # Build agent mapping dynamically
        self.agent_map = {
            "WeatherAgent": self.weather_agent,
            "weather": self.weather_agent,
            "CalculatorAgent": self.calculator_agent,
            "calculator": self.calculator_agent,
            "TravelAgent": self.travel_agent,
            "travel": self.travel_agent,
        }
    
    def _build_workflow(self):
        """Build Magentic Workflow"""
        print("=" * 60)
        print("🏗️  Building Magentic Workflow...")
        print("=" * 60)
        
        self.workflow = (
            MagenticBuilder()
            .participants(
                weather=self.weather_agent,
                calculator=self.calculator_agent,
                travel=self.travel_agent,
            )
            .with_standard_manager(
                chat_client=self.chat_client,
                max_round_count=20,  # Support multi-round
                max_stall_count=5,
                max_reset_count=2,
            )
            .build()
        )
        
        print("✅ Workflow built successfully!\n")
        print("📋 Available Agents:")
        print("   - WeatherAgent (weather queries)")
        print("   - CalculatorAgent (math calculations)")
        print("   - TravelAgent (travel advice)")
        print()
    
    async def run_with_interaction(self, initial_task: str):
        """Run Magentic workflow with user interaction support"""
        print("=" * 60)
        print("🚀 Starting Magentic workflow execution")
        print("=" * 60)
        print(f"📝 Initial task: {initial_task}\n")
        
        # Collect Agent's complete responses
        agent_responses = {}
        current_streaming_agent = None
        current_response = ""
        
        # Run Magentic workflow
        async for event in self.workflow.run_stream(initial_task):
            
            # 1. Orchestrator messages (Manager's decisions)
            if isinstance(event, MagenticOrchestratorMessageEvent):
                print(f"\n{'=' * 60}")
                print(f"🧠 Orchestrator [{event.kind}]:")
                print(f"{'=' * 60}")
                message_text = getattr(event.message, 'text',
                                     str(event.message))
                print(message_text)
                print()
            
            # 2. Agent streaming output (incremental)
            elif isinstance(event, MagenticAgentDeltaEvent):
                # Detect Agent switching
                if current_streaming_agent != event.agent_id:
                    if current_streaming_agent:
                        print("\033[0m")  # Reset color
                        print()
                    
                    print(f"\n{'-' * 60}")
                    print(f"🤖 {event.agent_id or 'Agent'} is working...")
                    print(f"{'-' * 60}\n")
                    print("\033[92m", end="")  # Green
                    current_streaming_agent = event.agent_id
                    current_response = ""
                
                # Streaming output
                if event.text:
                    print(event.text, end="", flush=True)
                    current_response += event.text
            
            # 3. Agent completed response (complete message)
            elif isinstance(event, MagenticAgentMessageEvent):
                print("\033[0m")  # Reset color
                print()
                
                agent_id = event.agent_id or "Agent"
                message_text = getattr(event.message, 'text', '')
                
                # Save response
                agent_responses[agent_id] = message_text or current_response
                current_response = ""
                current_streaming_agent = None
                
                # ✅ Key: Implement user interaction here!
                if self.interaction_enabled:
                    should_continue = await self._interact_with_agent(
                        agent_id,
                        agent_responses[agent_id]
                    )
                    
                    if not should_continue:
                        print("\n⏸️  User chose to pause workflow")
                        break
            
            # 4. Final result
            elif isinstance(event, MagenticFinalResultEvent):
                print("\n" + "=" * 60)
                print("✅ Magentic workflow completed!")
                print("=" * 60)
                if event.message:
                    message_text = getattr(event.message, 'text',
                                         str(event.message))
                    print(f"Final result:\n{message_text}")
            
            # 5. Output event
            elif isinstance(event, WorkflowOutputEvent):
                output_text = getattr(event.data, 'text', str(event.data))
                print(f"\n📤 Output: {output_text}")
        
        print("\n" + "=" * 60)
        print("🎉 Workflow execution ended")
        print("=" * 60)
    
    async def _interact_with_agent(
        self,
        agent_name: str,
        response: str
    ) -> bool:
        """Interact with current Agent
        
        Args:
            agent_name: Agent name
            response: Agent's response content
            
        Returns:
            bool: True=continue workflow, False=pause
        """
        print(f"\n{'-' * 60}")
        print(f"💬 {agent_name} has completed response")
        print(f"{'-' * 60}")
        print("You can:")
        print("  1. Continue workflow (let Orchestrator decide next step)")
        print(f"  2. Follow up with {agent_name}")
        print("  3. Pause workflow")
        
        choice = input("\nChoose (1-3, default=1): ").strip() or "1"
        
        if choice == "1":
            print("\n✅ Continuing workflow")
            return True
        
        elif choice == "2":
            # Follow-up loop with current Agent
            print(f"\n💡 Tip: You can ask {agent_name} multiple questions")
            print("Note: This creates a new conversation, "
                  "won't affect current workflow")
            print("Press Enter on empty line to stop\n")
            
            # Get corresponding Agent from instance mapping
            agent = self.agent_map.get(agent_name)
            if not agent:
                print(f"❌ Agent not found: {agent_name}")
                return True
            
            # Create a thread for follow-up session
            thread = agent.get_new_thread()
            conversation_history = f"Previously you answered:\n\n{response}\n\n"
            
            # Follow-up loop
            while True:
                question = input(
                    f"💬 Ask {agent_name} (empty to stop): "
                ).strip()
                
                if not question:
                    print("✅ Ending follow-up")
                    break
                
                print(f"\n🤖 {agent_name} is answering...\n")
                print("\033[92m", end="")
                
                # Use accumulated conversation history
                full_context = (conversation_history +
                              f"User follow-up: {question}")
                
                agent_response = ""
                async for chunk in agent.run_stream(full_context,
                                                   thread=thread):
                    if chunk.text:
                        print(chunk.text, end="", flush=True)
                        agent_response += chunk.text
                
                print("\033[0m\n")
                
                # Update conversation history
                conversation_history += (f"User follow-up: {question}\n\n"
                                       f"Your answer: {agent_response}\n\n")
            
            # Ask whether to continue workflow
            continue_choice = input(
                "\nContinue workflow? (y/n, default=y): "
            ).strip().lower() or "y"
            return continue_choice == "y"
        
        elif choice == "3":
            print("\n⏸️  Pausing workflow")
            return False
        
        else:
            print("\n❌ Invalid choice, continuing workflow")
            return True
    
    async def run_interactive_loop(self):
        """Run interactive main loop"""
        print("\n" + "=" * 60)
        print("🤖 Interactive Magentic Orchestration System")
        print("=" * 60)
        
        while True:
            print("\n" + "=" * 60)
            task = input("💬 Enter task (or 'exit' to quit): ").strip()
            
            if not task or task.lower() == "exit":
                print("\n👋 Goodbye!")
                break
            
            try:
                await self.run_with_interaction(task)
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()


async def main():
    """Main function"""
    try:
        orchestrator = InteractiveMagenticOrchestrator()
        await orchestrator.run_interactive_loop()
        
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

