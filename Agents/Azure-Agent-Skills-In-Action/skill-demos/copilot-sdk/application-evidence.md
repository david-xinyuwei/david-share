# Copilot SDK Skill — Live Demo

> This application was built following the `copilot-sdk` skill from
> [microsoft/skills](https://github.com/microsoft/skills).

## What was built

A complete demo web application (`app/server.py` + `app/static/index.html`) that:

1. Manages multiple **Foundry Agent personas** (each with different tool subsets)
2. Routes user messages through the **Responses protocol** to hosted agents
3. Displays **live execution traces** (step-by-step tool invocation visualization)
4. Supports **voice input** via Azure OpenAI Whisper
5. Supports **image generation** via gpt-image-1
6. Shows **real-time agent health**, logs, and call history

## Evidence from real implementation

### Server (FastAPI + Responses protocol)

```python
# app/server.py — key pattern from copilot-sdk skill
resp = httpx.post(
    ep["url"],  # Foundry hosted agent /responses endpoint
    json={"input": constraint},  # Responses protocol input
    headers={"Authorization": f"Bearer {_get_token('https://ai.azure.com/.default')}"},
    timeout=timeout,
)
payload = resp.json()

# Parse structured output
for item in payload.get("output", []):
    if item.get("type") == "message":
        for c in item.get("content", []):
            if c.get("type") == "output_text":
                text_parts.append(c["text"])
    if item.get("type") == "function_call_output":
        tool_calls.append({"name": item.get("name"), "output": item.get("output")})
```

### Multi-agent pattern (agent personas with tool subsets)

```python
# Each Foundry Agent = a name + a tool subset + a hosted agent binding
AGENTS = {
    "default": {
        "name": "Default agent (all tools)",
        "tools": ["code_interpreter", "file_search", "web_search",
                  "direct_web_search", "direct_image_generate"],
    },
    "math-only": {
        "name": "Math agent (code_interpreter only)",
        "tools": ["code_interpreter"],
    },
    "rag-only": {
        "name": "Knowledge agent (file_search only)",
        "tools": ["file_search"],
    },
}
```

### Session management via Responses API

The Responses protocol manages conversation history server-side:
```python
agent = Agent(
    ...
    default_options={"store": False},
    # Hosted Agents Responses protocol manages conversation history
)
```

### Streaming and tool hooks

```python
# Voice: Browser MediaRecorder → Whisper STT → Agent → Response
@app.post("/api/voice")
async def voice(audio: UploadFile, agent_id: str):
    # Whisper transcription
    transcript = httpx.post(whisper_url, files={"file": audio}).text
    # Forward to agent
    result = _ask_agent(transcript, agent_id)

# Image: Direct Foundry Image API call
@app.post("/api/image")
async def image_gen(prompt: str, agent_id: str):
    resp = httpx.post(f"{ACCOUNT_BASE}/openai/v1/images/generations",
                      json={"model": "gpt-image-1", "prompt": prompt})
```

## Skill guidance followed

| Skill Topic | Our Implementation |
|-------------|-------------------|
| Responses protocol integration | ✅ POST /responses with Bearer auth |
| Session management | ✅ Server-side via Responses API (store: false for stateless hosting) |
| Custom tools alongside MCP | ✅ direct_web_search, direct_image_generate as @tool functions |
| Multi-agent personas | ✅ Agent registry with per-agent tool subsets |
| Streaming response parsing | ✅ Parse output → message → content → output_text chain |
| Whisper integration | ✅ Audio → Whisper STT → Agent pipeline |
| Error handling | ✅ Try-catch with user-visible error messages |
| Token management | ✅ DefaultAzureCredential → Bearer token per request |

## Source code

Full implementation: [`Foundry-Hosted-Agent-Toolbox-Demo/app/`](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Foundry-Hosted-Agent-Toolbox-Demo/app)

**Verdict**: The `copilot-sdk` skill's patterns for session management, custom tools,
streaming, and Responses protocol directly match our implementation. The skill would
have reduced discovery time for the correct output parsing chain
(`output[] → message → content[] → output_text`) and the auth scope (`ai.azure.com/.default`).
