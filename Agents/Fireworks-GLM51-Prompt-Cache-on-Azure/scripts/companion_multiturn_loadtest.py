#!/usr/bin/env python3
"""Multi-turn AI companion cache benchmark for Azure AI Foundry Fireworks.

This benchmark simulates companion-style multi-turn sessions with a long stable
persona/memory prefix and fixed assistant history fixtures. Fixed assistant
turns are intentional: the first pass isolates prompt-cache and routing behavior
instead of measuring answer quality.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import statistics
import time
from pathlib import Path
from typing import Any

import aiohttp


SYSTEM_PROMPT = """
You are a warm, emotionally intelligent AI companion designed for long-running
supportive conversations. You remember stable user preferences, use a calm tone,
and keep replies grounded in the user's prior context. You are not a therapist,
doctor, financial advisor, or legal advisor. When the user is distressed, respond
with empathy, reflect the emotion, and offer one small practical next step.

Conversation principles:
- Keep the user feeling seen without overexplaining.
- Prefer short, concrete suggestions over generic motivational slogans.
- Avoid dramatic language and avoid pretending certainty about the user's life.
- Respect the user's agency and do not pressure them.
- Preserve continuity with prior turns and stable memory.
- Do not mention benchmarking, prompt caching, test harnesses, or internal state.
- If the user asks for code or technical help, be practical and concise.
- If the user expresses safety risk, encourage contacting local emergency or crisis support.

Response style:
- Two short paragraphs maximum unless the user explicitly asks for depth.
- Acknowledge emotion first, then offer one useful next step.
- Use natural, conversational language.
- Do not include bullet lists unless they clearly help.
""".strip()


STATIC_APP_CONTEXT = """
Application context:
This companion product keeps a stable per-user memory block and app policy at the
front of the prompt. The current user message is appended at the end. The memory
block should be deterministic and preserve ordering across turns. Volatile fields
such as timestamps, request IDs, experiment IDs, and current mood scores should
not appear before the stable persona and memory prefix.

Cache-friendly prompt layout:
1. stable system policy
2. stable companion style rules
3. stable user memory in deterministic order
4. ordered conversation history
5. current user message at the end
""".strip()


MEMORY_BANK = [
    "The user prefers gentle encouragement over direct criticism.",
    "The user likes short replies with one concrete next step.",
    "The user dislikes generic motivational slogans.",
    "The user often checks in late at night and prefers a calm tone.",
    "The user is navigating career uncertainty and wants low-pressure support.",
    "The user values continuity and appreciates references to prior context.",
    "The user enjoys light humor only when it does not dismiss the concern.",
    "The user prefers practical rituals, such as writing one note or taking a short walk.",
    "The user sometimes overthinks messages and wants help making wording simpler.",
    "The user wants the companion to remember emotional patterns, not just facts.",
    "The user responds well to reflective listening before advice.",
    "The user does not want medicalized language for ordinary stress.",
    "The user is sensitive to sounding needy in social situations.",
    "The user wants help building momentum without being pushed.",
    "The user prefers a confident but soft tone.",
    "The user wants the assistant to ask at most one follow-up question.",
    "The user likes concrete next actions that take less than ten minutes.",
    "The user often returns to the theme of balancing ambition and rest.",
    "The user is trying to communicate more clearly at work.",
    "The user values privacy and does not want personal details repeated unnecessarily.",
    "The user likes when the companion notices progress from prior turns.",
    "The user wants help choosing words without over-polishing them.",
    "The user sometimes asks for reassurance but prefers honest reassurance.",
    "The user prefers responses that end with one actionable suggestion.",
]


USER_MESSAGES = [
    "I feel oddly tired today even though nothing dramatic happened. Can you help me sort out what to do next?",
    "I keep rewriting the same message and it is making me anxious. I want it to sound calm, not needy.",
    "I had a decent workday but now I feel like I did not do enough. How should I think about that?",
    "I want to check in with someone I care about, but I do not want to make the conversation heavy.",
    "I got feedback today and I cannot tell if I am learning from it or just spiraling about it.",
    "Can you help me make a tiny plan for tonight so I do not waste the evening doomscrolling?",
    "I am proud of one thing I did today, but I also feel embarrassed saying that out loud.",
    "I need to send a concise update tomorrow morning and I want to stop overthinking it.",
    "I feel disconnected from my usual rhythm. What is one small reset that would not feel fake?",
    "Can you help me end the day in a way that makes tomorrow easier?",
]


FIXED_ASSISTANT_RESPONSES = [
    "That kind of tired can be real even when nothing dramatic happened. Start by lowering the bar: pick one small care task, then one small closure task, and let that count for tonight.",
    "A calm message usually sounds more direct than perfect. Write the simplest version first, then remove one extra explanation. The goal is warmth, not proof.",
    "That sounds like the ambition part of you is still scanning for unfinished work. Try naming one thing that moved forward today, then choose one clear stopping point.",
    "You can keep it light and still be sincere. A short check-in with one specific detail often feels warmer than a big emotional preface.",
    "Feedback can land in the body before it becomes useful. For tonight, separate the signal from the sting: write one useful note and leave the rest for tomorrow.",
    "Tiny plan: put your phone somewhere slightly inconvenient, do one ten-minute reset, then choose a low-effort reward. Make the evening easy to start, not impressive.",
    "You are allowed to be proud without making a speech about it. Just name it plainly: one thing worked, and it matters that you noticed.",
    "For tomorrow's update, lead with the outcome, then add the next step. If you keep it factual, you will not need to defend the work.",
    "A reset does not need to be profound. Change one sensory thing: light, water, posture, or a short walk. Let the body get the first vote.",
    "Make tomorrow easier by removing one decision now. Put the first task somewhere visible, then stop negotiating with the rest of the night.",
]


GROUPS = [
    "no_affinity",
    "x_session_affinity",
    "prompt_cache_key",
    "best_practice_both",
    "dynamic_prefix_antipattern",
    "shuffled_memory_antipattern",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-turn AI companion cache benchmark.")
    parser.add_argument("--endpoint", default=os.getenv("FIREWORKS_AZURE_ENDPOINT"), help="Azure AI Services endpoint")
    parser.add_argument("--deployment", default=os.getenv("FIREWORKS_DEPLOYMENT"), help="Azure AI Foundry deployment name")
    parser.add_argument("--api-version", default=os.getenv("FIREWORKS_API_VERSION", "2025-04-01-preview"))
    parser.add_argument("--bearer-token", default=os.getenv("FIREWORKS_BEARER_TOKEN"), help="Microsoft Entra access token")
    parser.add_argument("--api-key", default=os.getenv("FIREWORKS_API_KEY"), help="API key, if local auth is enabled")
    parser.add_argument("--sessions", type=int, default=16)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--groups", nargs="+", default=GROUPS, choices=GROUPS)
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--request-timeout", type=float, default=60.0, help="Per-request total and socket-read timeout in seconds")
    parser.add_argument("--output-dir", default="data/companion-multiturn-run")
    return parser.parse_args()


def auth_headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if args.bearer_token:
        headers["Authorization"] = f"Bearer {args.bearer_token}"
    elif args.api_key:
        headers["api-key"] = args.api_key
    else:
        raise SystemExit("Provide FIREWORKS_BEARER_TOKEN or FIREWORKS_API_KEY.")
    return headers


def percentile(values: list[float], p: float) -> float | None:
    values = [value for value in values if value is not None]
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100
    lower = math.floor(k)
    upper = math.ceil(k)
    if lower == upper:
        return ordered[int(k)]
    return ordered[lower] * (upper - k) + ordered[upper] * (k - lower)


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_memory_for_session(session_id: int, shuffled: bool, turn_id: int) -> list[str]:
    items = list(MEMORY_BANK)
    # Add deterministic session facts. These differ across users but remain fixed within a session unless shuffled.
    items.extend(
        [
            f"Session profile index: {session_id:02d}.",
            f"Preferred companion nickname variant: companion-{session_id % 4}.",
            f"The user prefers check-ins every {2 + (session_id % 3)} days.",
            f"The user is currently focusing on one work theme and one rest theme.",
        ]
    )
    if shuffled:
        rng = random.Random(session_id * 1000 + turn_id)
        rng.shuffle(items)
    return items


def build_messages(group: str, session_id: int, turn_id: int, repeat_id: int) -> list[dict[str, str]]:
    shuffled = group == "shuffled_memory_antipattern"
    memory_items = stable_memory_for_session(session_id, shuffled=shuffled, turn_id=turn_id)
    memory_block = "\n".join(f"- {item}" for item in memory_items)
    dynamic_prefix = ""
    if group == "dynamic_prefix_antipattern":
        dynamic_prefix = f"Volatile request metadata: repeat={repeat_id}; session={session_id}; turn={turn_id}; unix_bucket={int(time.time())}.\n\n"
    system = f"""{dynamic_prefix}{SYSTEM_PROMPT}

Stable User Memory:
{memory_block}

{STATIC_APP_CONTEXT}"""
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    for previous_turn in range(1, turn_id):
        user = USER_MESSAGES[(previous_turn - 1 + session_id) % len(USER_MESSAGES)]
        assistant = FIXED_ASSISTANT_RESPONSES[(previous_turn - 1 + session_id) % len(FIXED_ASSISTANT_RESPONSES)]
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": assistant})
    current = USER_MESSAGES[(turn_id - 1 + session_id) % len(USER_MESSAGES)]
    messages.append({"role": "user", "content": current})
    return messages


def request_identity(group: str, session_id: int, repeat_id: int) -> str:
    # Repeat ID is included to keep separate benchmark repeats from sharing cache accidentally.
    return f"companion-r{repeat_id}-s{session_id:02d}"


async def send_one(
    session: aiohttp.ClientSession,
    args: argparse.Namespace,
    url: str,
    base_headers: dict[str, str],
    group: str,
    repeat_id: int,
    session_id: int,
    turn_id: int,
) -> dict[str, Any]:
    identity = request_identity(group, session_id, repeat_id)
    payload: dict[str, Any] = {
        "messages": build_messages(group, session_id, turn_id, repeat_id),
        "max_tokens": args.max_tokens,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "perf_metrics_in_response": True,
    }
    headers = dict(base_headers)
    if group in {"x_session_affinity", "best_practice_both", "dynamic_prefix_antipattern", "shuffled_memory_antipattern"}:
        headers["x-session-affinity"] = identity
    if group in {"prompt_cache_key", "best_practice_both", "dynamic_prefix_antipattern", "shuffled_memory_antipattern"}:
        payload["prompt_cache_key"] = identity
    started = time.perf_counter()
    usage = None
    perf = None
    chunks = 0
    streamed_chars = 0
    try:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=args.request_timeout, sock_read=args.request_timeout)) as response:
            text_for_error = ""
            async for raw in response.content:
                decoded = raw.decode(errors="ignore")
                if response.status != 200:
                    text_for_error += decoded
                for raw_line in decoded.splitlines():
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        continue
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    chunks += 1
                    usage = obj.get("usage") or usage
                    perf = obj.get("perf_metrics") or perf
                    for choice in obj.get("choices") or []:
                        delta = choice.get("delta") or {}
                        streamed_chars += len(delta.get("content") or "")
            elapsed = time.perf_counter() - started
            if response.status != 200:
                return {
                    "group": group,
                    "repeat": repeat_id,
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "http": response.status,
                    "elapsed_sec": round(elapsed, 4),
                    "error_body": text_for_error[:1200],
                }
            usage = usage or {}
            details = usage.get("prompt_tokens_details") or {}
            perf = perf or {}
            prompt_tokens = usage.get("prompt_tokens") or 0
            cached_tokens = details.get("cached_tokens") or 0
            completion_tokens = usage.get("completion_tokens") or 0
            generation_sec = as_float(perf.get("generation-duration"))
            processing_sec = as_float(perf.get("server-processing-time"))
            return {
                "group": group,
                "repeat": repeat_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "http": response.status,
                "elapsed_sec": round(elapsed, 4),
                "server_ttft_sec": as_float(perf.get("server-time-to-first-token")),
                "server_processing_sec": processing_sec,
                "generation_sec": generation_sec,
                "prompt_tokens": prompt_tokens,
                "cached_tokens": cached_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": usage.get("total_tokens"),
                "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
                "output_tokens_per_sec_generation": round(completion_tokens / generation_sec, 4) if generation_sec else None,
                "output_tokens_per_sec_processing": round(completion_tokens / processing_sec, 4) if processing_sec else None,
                "chunks": chunks,
                "streamed_chars": streamed_chars,
                "backend_host": perf.get("backend-host"),
            }
    except Exception as error:  # noqa: BLE001 - keep load failures visible in JSONL
        return {
            "group": group,
            "repeat": repeat_id,
            "session_id": session_id,
            "turn_id": turn_id,
            "exception": repr(error),
            "elapsed_sec": round(time.perf_counter() - started, 4),
        }


async def run_turn(
    session: aiohttp.ClientSession,
    args: argparse.Namespace,
    url: str,
    base_headers: dict[str, str],
    group: str,
    repeat_id: int,
    turn_id: int,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(args.concurrency)

    async def guarded(session_id: int) -> dict[str, Any]:
        async with semaphore:
            return await send_one(session, args, url, base_headers, group, repeat_id, session_id, turn_id)

    return await asyncio.gather(*[guarded(session_id) for session_id in range(args.sessions)])


def summarize_slice(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [item for item in results if item.get("http") == 200]

    def values(key: str) -> list[float]:
        return [item[key] for item in ok if item.get(key) is not None]

    prompt_tokens = sum(int(item.get("prompt_tokens") or 0) for item in ok)
    cached_tokens = sum(int(item.get("cached_tokens") or 0) for item in ok)
    completion_tokens = sum(int(item.get("completion_tokens") or 0) for item in ok)
    http_counts: dict[str, int] = {}
    for item in results:
        key = str(item.get("http") or "exception")
        http_counts[key] = http_counts.get(key, 0) + 1
    return {
        "requests": len(results),
        "success": len(ok),
        "errors": len(results) - len(ok),
        "http_counts": http_counts,
        "tokens": {
            "prompt": prompt_tokens,
            "cached": cached_tokens,
            "completion": completion_tokens,
            "cache_ratio": round(cached_tokens / prompt_tokens, 4) if prompt_tokens else None,
        },
        "server_ttft_sec": {
            "avg": round(statistics.mean(values("server_ttft_sec")), 4) if values("server_ttft_sec") else None,
            "p50": round(percentile(values("server_ttft_sec"), 50), 4) if values("server_ttft_sec") else None,
            "p90": round(percentile(values("server_ttft_sec"), 90), 4) if values("server_ttft_sec") else None,
            "p95": round(percentile(values("server_ttft_sec"), 95), 4) if values("server_ttft_sec") else None,
            "p99": round(percentile(values("server_ttft_sec"), 99), 4) if values("server_ttft_sec") else None,
        },
        "output_tokens_per_sec_generation": {
            "avg": round(statistics.mean(values("output_tokens_per_sec_generation")), 4) if values("output_tokens_per_sec_generation") else None,
            "p50": round(percentile(values("output_tokens_per_sec_generation"), 50), 4) if values("output_tokens_per_sec_generation") else None,
            "p10": round(percentile(values("output_tokens_per_sec_generation"), 10), 4) if values("output_tokens_per_sec_generation") else None,
            "p90": round(percentile(values("output_tokens_per_sec_generation"), 90), 4) if values("output_tokens_per_sec_generation") else None,
        },
    }


async def main_async(args: argparse.Namespace) -> None:
    if not args.endpoint or not args.deployment:
        raise SystemExit("--endpoint and --deployment are required.")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    endpoint = args.endpoint.rstrip("/")
    url = f"{endpoint}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    base_headers = auth_headers(args)
    all_results: list[dict[str, Any]] = []
    raw_path = output_dir / "companion_multiturn_requests.jsonl"
    raw_path.write_text("", encoding="utf-8")
    connector = aiohttp.TCPConnector(limit=args.concurrency)
    async with aiohttp.ClientSession(connector=connector) as session:
        for repeat_id in range(1, args.repeats + 1):
            for group in args.groups:
                for turn_id in range(1, args.turns + 1):
                    turn_results = await run_turn(session, args, url, base_headers, group, repeat_id, turn_id)
                    all_results.extend(turn_results)
                    with raw_path.open("a", encoding="utf-8") as handle:
                        for item in turn_results:
                            print(json.dumps(item), file=handle)
                    print(json.dumps({"event": "turn_done", "repeat": repeat_id, "group": group, "turn": turn_id, "summary": summarize_slice(turn_results)}))
    group_summaries = {}
    turn_summaries = []
    for group in args.groups:
        group_items = [item for item in all_results if item.get("group") == group]
        group_summaries[group] = summarize_slice(group_items)
        for turn_id in range(1, args.turns + 1):
            turn_items = [item for item in group_items if item.get("turn_id") == turn_id]
            summary = summarize_slice(turn_items)
            summary.update({"group": group, "turn_id": turn_id})
            turn_summaries.append(summary)
    summary = {
        "deployment": args.deployment,
        "scenario": "synthetic AI companion multi-turn cache benchmark",
        "sessions": args.sessions,
        "turns": args.turns,
        "repeats": args.repeats,
        "groups": args.groups,
        "max_tokens": args.max_tokens,
        "history_strategy": "fixed assistant responses; live model output is not fed into later turns",
        "stable_prefix_design": "long companion persona, deterministic user memory, static app instructions, growing fixed conversation history, current user message at end",
        "group_summaries": group_summaries,
        "turn_summaries": turn_summaries,
    }
    (output_dir / "companion_multiturn_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"event": "complete", "output_dir": str(output_dir), "summary_path": str(output_dir / "companion_multiturn_summary.json")}, indent=2))


def main() -> None:
    asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    main()