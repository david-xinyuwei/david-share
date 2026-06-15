from __future__ import annotations
import logging
import os
import uuid

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from starlette.responses import JSONResponse, PlainTextResponse

# ------------------------------------------------------------------  env / logger
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("writer-agent")

A2A_TOKEN = os.getenv("A2A_TOKEN")          # required bearer token

# ------------------------------------------------------------------  OpenAI client
client = openai.AsyncAzureOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    azure_endpoint=os.environ["OPENAI_API_BASE"],
    api_version=os.environ["OPENAI_API_VERSION"],
)
MODEL = os.environ["OPENAI_DEPLOYMENT"]     # deployment / model name

# ------------------------------------------------------------------  FastAPI app
app = FastAPI()

# ------------------------------------------------------------------  Agent card
HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", "10011")

@app.get("/.well-known/agent.json")
def card() -> dict:
    """Return the static AgentCard so that other agents can discover us."""
    return {
        "name": "writer-agent",
        "description": "Generates 300-character Chinese essays via ChatCompletion.",
        "url": f"http://{HOST}:{PORT}/",
        "version": "1.0.0",
        "capabilities": {"streaming": False, "auth": "bearer"},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "write_essay",
                "name": "Write Essay",
                "description": "Return a ~300 Chinese-character short essay.",
            }
        ],
    }

# ------------------------------------------------------------------  core business
async def write_essay(prompt: str) -> str:
    """Call Azure OpenAI and return a trimmed essay string."""
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Generate a 300-character Chinese essay."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()

# ------------------------------------------------------------------  JSON-RPC entry
@app.post("/")
async def root(request: Request, authorization: str | None = Header(None)):
    # Bearer-token check
    if authorization != f"Bearer {A2A_TOKEN}":
        raise HTTPException(401, "Unauthorized")

    # Extract prompt from A2A JSON-RPC payload
    body = await request.json()
    prompt = body["params"]["message"]["parts"][0]["text"]

    essay = await write_essay(prompt)

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": body["id"],
            "result": {
                "Task": {
                    "id": uuid.uuid4().hex,
                    "contextId": "ctx",
                    "status": "completed",
                },
                "Message": {
                    "messageId": uuid.uuid4().hex,
                    "role": "assistant",
                    "parts": [{"kind": "text", "text": essay}],
                },
            },
        }
    )

# ------------------------------------------------------------------  health probe
@app.get("/health")
def health():
    return PlainTextResponse("ok")