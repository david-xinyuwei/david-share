"""
TRIPLE:
  Skill: pydantic-models-py
  Prompt: "Using pydantic-models-py skill, write Pydantic v2 models for the agent registry
           CRUD in our Foundry Demo — with the multi-model pattern: AgentBase, AgentCreate,
           AgentUpdate, AgentResponse. Include field_validator for tool name validation."
  Deliverable: This file — runnable Python module

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/pydantic-models-py
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class AgentBase(BaseModel):
    """Shared fields across all agent operations."""
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    tools: list[str]
    instructions: str = "You are a helpful assistant."
    hosted_agent_id: str = "default"

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: list[str]) -> list[str]:
        allowed = {"code_interpreter", "file_search", "web_search", "direct_web_search", "direct_image_generate"}
        bad = [t for t in v if t not in allowed]
        if bad:
            raise ValueError(f"Unknown tools: {bad}. Allowed: {sorted(allowed)}")
        return v


class AgentCreate(AgentBase):
    """Request body for POST /api/agents."""
    pass


class AgentUpdate(BaseModel):
    """Request body for PUT /api/agents/:id (partial update)."""
    model_config = ConfigDict(str_strip_whitespace=True)

    tools: list[str]
    hosted_agent_id: str | None = None

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, v: list[str]) -> list[str]:
        return AgentBase.validate_tools(v)


class AgentResponse(AgentBase):
    """Response body for GET /api/agents and POST /api/agents."""
    id: str
    created_at: float
    calls: int = 0


# Quick smoke test
if __name__ == "__main__":
    a = AgentCreate(name="Math agent", tools=["code_interpreter"], instructions="Do math.")
    print(f"Create: {a.model_dump_json(indent=2)}")

    u = AgentUpdate(tools=["code_interpreter", "file_search"])
    print(f"Update: {u.model_dump_json(indent=2)}")

    r = AgentResponse(id="agent-abc123", name="Math agent", tools=["code_interpreter"],
                       created_at=datetime.now().timestamp(), calls=42)
    print(f"Response: {r.model_dump_json(indent=2)}")

    # Validation test — should raise ValueError
    try:
        AgentCreate(name="bad", tools=["nonexistent_tool"])
    except Exception as e:
        print(f"\n✅ Validation caught: {e}")
