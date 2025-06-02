from __future__ import annotations
"""
orch_llm_router.py  –  LLM-based router with post-processing filter

Changes versus the previous version
-----------------------------------
•  _postprocess()  keeps only the clean “Meeting …” sentence(s) from
   Calendar agents; if no such sentence is found it falls back to the
   original text.
•  call_agent()  now returns _postprocess(_extract(resp.json())).
Everything else stays the same.
"""

import json, logging, os, re, asyncio
from typing import Dict, Any, List
from uuid import uuid4

import httpx, openai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from starlette.responses import JSONResponse

# ───────────────────────────  env / logger
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("llm-router")

A2A_TOKEN   = os.getenv("A2A_TOKEN")
AUTH_HEADER = {"Authorization": f"Bearer {A2A_TOKEN}"}

# ───────────────────────────  OpenAI client
client = openai.AsyncAzureOpenAI(
    api_key        = os.environ["OPENAI_API_KEY"],
    azure_endpoint = os.environ["OPENAI_API_BASE"],
    api_version    = os.environ["OPENAI_API_VERSION"],
)
MODEL = os.environ["OPENAI_DEPLOYMENT"]

# ───────────────────────────  downstream registry
DOWNSTREAM: Dict[str, str] = {
    "Calendar-Workday": "http://localhost:10007/",
    "Calendar-Weekend": "http://localhost:10008/",
    "writer-agent":     "http://localhost:10011/",
}

# ───────────────────────────  FastAPI
app = FastAPI()

@app.get("/health")
def health(): return {"ok": True}

@app.get("/.well-known/agent.json")
def card():
    return {
        "name": "llm-router",
        "description": "multi-intent router",
        "url": "http://localhost:10009/",
        "version": "1.0.0",
        "capabilities": {"streaming": False, "auth": "none"},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
    }

# ───────────────────────────  helpers
def _extract(data: Any) -> str:
    """Try several JSON paths to pull out the assistant text."""
    for path in [
        ["result", "Message", "parts", 0, "text"],
        ["result", "status", "message", "parts", 0, "text"],
        ["choices", 0, "message", "parts", 0, "text"],
    ]:
        try:
            node = data
            for p in path:
                node = node[p]
            return node
        except Exception:
            pass
    # fallback: search history
    for msg in reversed(data.get("result", {}).get("history", [])):
        if msg.get("role") == "agent" and msg.get("parts"):
            return msg["parts"][0]["text"]
    return ""

def _postprocess(text: str) -> str:
    """
    Keep only lines that start with 'Meeting ' (case-insensitive).
    If no such line exists, return the original text.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    meeting_lines = [ln for ln in lines if ln.lower().startswith("meeting ")]
    return "\n".join(meeting_lines) if meeting_lines else text
# ───────────────────────────  outbound call
async def call_agent(url: str, prompt: str) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid4()),
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid4()),
                "parts": [{"kind": "text", "text": prompt}],
            }
        },
    }
    async with httpx.AsyncClient(timeout=90) as cli:
        resp = await cli.post(url, json=payload, headers=AUTH_HEADER)
        if resp.status_code != 200:
            raise RuntimeError(f"{url} {resp.status_code}: {resp.text[:120]}")
        raw_text = _extract(resp.json())
        return _postprocess(raw_text)[:1000]

# ───────────────────────────  LLM classification
SYSTEM_PROMPT_MULTI = (
    "Identify every task in USER’s Chinese request. "
    "Return JSON array only. Each element: "
    '{"route":"Calendar-Workday|Calendar-Weekend|writer-agent",'
    '"rewritten":"..."}  Ignore unsupported tasks.'
)

async def classify_multi(text: str) -> List[Dict[str, str]]:
    rsp = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_MULTI},
            {"role": "user", "content": text[:2000]},
        ],
        temperature=0,
        max_tokens=200,
    )
    tasks = json.loads(rsp.choices[0].message.content.strip())
    return tasks if isinstance(tasks, list) else [tasks]

# ───────────────────────────  main endpoint
@app.post("/")
async def router(req: Request):
    body = await req.json()
    try:
        req_id = body["id"]
        user = "".join(
            p["text"]
            for p in body["params"]["message"]["parts"]
            if p.get("kind") == "text"
        )
    except Exception:
        raise HTTPException(400, "Bad payload")

    tasks = await classify_multi(user)
    logger.info("tasks: %s", tasks)

    coros, labels = [], []
    for t in tasks:
        if t["route"] in DOWNSTREAM:
            coros.append(call_agent(DOWNSTREAM[t["route"]], t["rewritten"]))
            labels.append(t["route"])

    answers: List[str] = []
    if coros:
        try:
            answers = await asyncio.gather(*coros)
        except Exception as exc:
            answers = [
                f"[{labels[i]} failed] {exc}" for i in range(len(coros))
            ]

    if not answers:
        answers = ["Sorry, unable to fulfill your request at the moment."]

    return JSONResponse(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "Task": {"id": uuid4().hex, "contextId": "ctx", "status": "completed"},
                "Message": {
                    "messageId": uuid4().hex,
                    "role": "assistant",
                    "parts": [{"kind": "text", "text": "\n\n".join(answers)}],
                },
            },
        }
    )