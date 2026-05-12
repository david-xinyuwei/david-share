"""
TRIPLE:
  Skill: fastapi-router-py
  Prompt: "Using fastapi-router-py skill, write a FastAPI app skeleton for an agent demo
           dashboard with: health check, CRUD for agents, chat endpoint, voice endpoint,
           static file serving. Use Pydantic models for request bodies, JSONResponse for
           typed returns."
  Deliverable: This file — runnable FastAPI server skeleton

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/fastapi-router-py
"""
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Agent Demo Dashboard")


class AgentCreate(BaseModel):
    name: str
    tools: list[str]
    instructions: str = "You are a helpful assistant."


class AgentUpdate(BaseModel):
    tools: list[str]


# Health check
@app.get("/api/health")
async def health():
    return JSONResponse({"status": "ok"})


# Agent CRUD
AGENTS: dict[str, dict] = {}


@app.get("/api/agents")
async def list_agents():
    return JSONResponse({"agents": list(AGENTS.values())})


@app.post("/api/agents")
async def create_agent(body: AgentCreate):
    import uuid
    aid = "agent-" + uuid.uuid4().hex[:8]
    AGENTS[aid] = {"id": aid, **body.model_dump(), "calls": 0}
    return JSONResponse(AGENTS[aid])


@app.put("/api/agents/{aid}")
async def update_agent(aid: str, body: AgentUpdate):
    if aid not in AGENTS:
        raise HTTPException(404)
    AGENTS[aid]["tools"] = body.tools
    return JSONResponse(AGENTS[aid])


@app.delete("/api/agents/{aid}")
async def delete_agent(aid: str):
    AGENTS.pop(aid, None)
    return JSONResponse({"ok": True})


# Chat endpoint
@app.post("/api/chat")
async def chat(message: str = Form(...), agent_id: str = Form("default")):
    # In production: forward to hosted agent /responses
    return JSONResponse({"text": f"Echo from {agent_id}: {message}", "tool_calls": []})


# Voice endpoint
@app.post("/api/voice")
async def voice(audio: UploadFile = File(...), agent_id: str = Form("default")):
    content = await audio.read()
    return JSONResponse({"transcript": "(whisper STT here)", "text": f"Voice from {agent_id}: {len(content)} bytes"})


# Static files (serve index.html)
# app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
