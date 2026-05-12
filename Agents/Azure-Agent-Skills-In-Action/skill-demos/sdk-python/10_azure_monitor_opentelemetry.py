"""
TRIPLE:
  Skill: azure-monitor-opentelemetry-py
  Prompt: "Using azure-monitor-opentelemetry-py skill, write a Python module that configures
           server-side OpenTelemetry for a FastAPI backend — auto-instrument FastAPI + httpx,
           emit custom GenAI agent spans, and configure W3C trace context propagation."
  Deliverable: This file — drop-in Python module for FastAPI instrumentation

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-monitor-opentelemetry-py
"""
import os
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

# Skill rule: call configure_azure_monitor ONCE at startup, before any request
connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(
        connection_string=connection_string,
        enable_live_metrics=True,
    )
    print("[OTel] Azure Monitor configured. Auto-instrumenting FastAPI + httpx.")
else:
    print("[OTel] WARNING: APPLICATIONINSIGHTS_CONNECTION_STRING not set. Running without telemetry.")

tracer = trace.get_tracer("foundry-demo-backend", "1.0.0")


def trace_agent_invocation(agent_name: str, agent_id: str, model: str,
                           tools_used: list[str], duration_ms: int,
                           input_tokens: int, output_tokens: int, success: bool):
    """Emit a GenAI agent span with OTel semantic conventions.

    Attributes follow:
      - https://opentelemetry.io/docs/specs/semconv/gen-ai/
      - gen_ai.system, gen_ai.agent.name, gen_ai.usage.*, etc.
    """
    with tracer.start_as_current_span("gen_ai.agent.invoke") as span:
        span.set_attribute("gen_ai.system", "azure_ai_foundry")
        span.set_attribute("gen_ai.operation.name", "agent_invoke")
        span.set_attribute("gen_ai.agent.name", agent_name)
        span.set_attribute("gen_ai.agent.id", agent_id)
        span.set_attribute("gen_ai.request.model", model)
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        span.set_attribute("gen_ai.usage.total_tokens", input_tokens + output_tokens)
        span.set_attribute("agent.tools.invoked", str(tools_used))
        span.set_attribute("duration_ms", duration_ms)
        if not success:
            span.set_status(trace.StatusCode.ERROR)


# Usage in FastAPI:
#
#   from otel_setup import trace_agent_invocation
#
#   @app.post("/api/chat")
#   async def chat(...):
#       result = _ask_agent(message, agent_id)
#       trace_agent_invocation(
#           agent_name=result["agent_name"], agent_id=result["agent_id"],
#           model="gpt-4.1-mini", tools_used=[t["name"] for t in result["tool_calls"]],
#           duration_ms=result["elapsed_ms"],
#           input_tokens=result["input_tokens"], output_tokens=result["output_tokens"],
#           success=True,
#       )
