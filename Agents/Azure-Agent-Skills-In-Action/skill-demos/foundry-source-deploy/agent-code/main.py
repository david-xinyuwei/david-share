"""
Foundry Source Code Deploy — Hello World Agent
This agent uses the Responses protocol with agent_framework.
"""
from agent_framework import AgentBase, ResponsesHostServer
from agent_framework.tools import tool


class HelloWorldAgent(AgentBase):
    """A minimal hello-world agent deployed from source code (no Docker required)."""

    @tool
    def get_current_time(self) -> str:
        """Return the current UTC time."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    @tool
    def calculate(self, expression: str) -> str:
        """Evaluate a simple math expression safely."""
        # Only allow safe math operations
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "Error: Only numeric expressions with +, -, *, /, (, ) are allowed."
        try:
            result = eval(expression)  # Safe: input is restricted to digits and operators
            return str(result)
        except Exception as e:
            return f"Error: {e}"


if __name__ == "__main__":
    agent = HelloWorldAgent()
    server = ResponsesHostServer(agent)
    server.run(host="0.0.0.0", port=8088)
