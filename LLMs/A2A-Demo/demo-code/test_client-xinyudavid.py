"""
test_calendar_agents_mixed.py
─────────────────────────────
• Calendar-Workday  – weekday questions (English)
• Calendar-Weekend  – weekend questions (English)

Every answer line is now prefixed with the real agent name instead of
[A2A] / [A2A-stream].
"""

from __future__ import annotations
import asyncio, json, logging, os
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import AgentCard, MessageSendParams, SendMessageRequest, SendStreamingMessageRequest

DEBUG_JSON   = False
HTTP_TIMEOUT = httpx.Timeout(120)

TASKS = {
    "Calendar-Workday": {
        "base": "http://localhost:10007",
        "questions": [
            "Hi! Can you help me manage my schedule?",
            "Am I free tomorrow afternoon from 2 p.m. to 3 p.m.?",
            "What meetings do I have today?",
            "Find the best 1-hour meeting slot for me this week.",
            "Please check my availability next Tuesday afternoon.",
        ],
    },
    "Calendar-Weekend": {
        "base": "http://localhost:10008",
        "questions": [
            "Hi! Can you help me manage my schedule?",
            "Am I free next Saturday afternoon?",
            "Do I have any travel plans today?",
            "Please find me a trip plan to the Summer Palace for this weekend.",
            "Please check my availability next Saturday afternoon.",
        ],
    },
}

# ───────── helper ─────────
def _parts_to_text(parts): return "".join(p.get("text","") for p in parts if p.get("kind")=="text")
def extract_text(obj) -> str:
    if hasattr(obj,"choices") and obj.choices:
        msg=obj.choices[0].message
        if getattr(msg,"parts",None): return _parts_to_text(msg.parts)
    if hasattr(obj,"message") and getattr(obj.message,"parts",None):
        return _parts_to_text(obj.message.parts)
    data = obj.model_dump(mode="json", exclude_none=True) if hasattr(obj,"model_dump") else {}
    for path in [["result","Message","message","parts"],
                 ["result","Message","parts"],
                 ["result","status","message","parts"]]:
        node=data
        for k in path: node=node.get(k,{})
        if node: return _parts_to_text(node)
    return json.dumps(data,ensure_ascii=False)[:200] if DEBUG_JSON else ""

# ───────── main ─────────
async def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    token=os.getenv("A2A_TOKEN")
    if not token:
        print("❌  A2A_TOKEN not set"); return

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT,
                                 headers={"Authorization":f"Bearer {token}"}) as cli:
        for agent, cfg in TASKS.items():
            base, questions = cfg["base"], cfg["questions"]

            if (await cli.get(f"{base}/health")).status_code!=200:
                print(f"\n❌  {agent} /health failed, skipping"); continue

            card:AgentCard = await A2ACardResolver(cli,base).get_agent_card()
            a2a = A2AClient(cli,card)
            print(f"\n✅ Connected to {card.name} ({base})")

            for q in questions:
                print(f"\n👤 {q}")
                params = MessageSendParams(
                    message={"role":"user","messageId":uuid4().hex,
                             "parts":[{"kind":"text","text":q}]})

                # non-streaming
                try:
                    r = await a2a.send_message(SendMessageRequest(id=str(uuid4()),params=params))
                    print(f"   [{agent}]        {extract_text(r) or '(empty)'}")
                except Exception as ex:
                    print(f"   [{agent}]        ERROR → {ex}")

                # streaming
                try:
                    merged=""
                    async for chunk in a2a.send_message_streaming(
                        SendStreamingMessageRequest(id=str(uuid4()),params=params)):
                        merged += extract_text(chunk)
                    print(f"   [{agent}-stream] {merged or '(empty)'}")
                except Exception as ex:
                    print(f"   [{agent}-stream] ERROR → {ex}")

    print("\n🎉  All tests completed.")

if __name__=="__main__":
    print("🤖  Mixed calendar-agent test – ensure both agents are running.\n")
    asyncio.run(main())