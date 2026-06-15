"""Gaming Cloud demo — three scenarios that show how the Hosted Agent + Toolbox
architecture serves a gaming-cloud use case.

Each scenario is a single user prompt sent to the running agent. The agent
picks the right tools automatically:

  Scenario 1 — Player Support:   file_search + code_interpreter
  Scenario 2 — Game Art Gen:     direct_image_generate
  Scenario 3 — Post-match Intel: direct_web_search + code_interpreter

Prerequisites:
    1. python main.py         (keep running in another terminal)
    2. The Toolbox must include code_interpreter + file_search
    3. direct_web_search and direct_image_generate enabled in .env

Run:
    python examples/gaming-cloud/gaming_demo.py
"""
import argparse
import json
import textwrap

import httpx


def ask(client: httpx.Client, base_url: str, prompt: str) -> str:
    resp = client.post(f"{base_url.rstrip('/')}/responses", json={"input": prompt})
    resp.raise_for_status()
    payload = resp.json()
    chunks = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for c in item.get("content", []):
            if isinstance(c, dict) and c.get("type") == "output_text" and c.get("text"):
                chunks.append(c["text"])
    return "\n".join(chunks) or json.dumps(payload, indent=2)[:2000]


SCENARIOS = [
    {
        "name": "Player Support — performance diagnosis",
        "icon": "🎮",
        "prompt": (
            "A player reports frequent frame drops in the Dragon Valley zone of our game. "
            "Here is their last 10 matches of telemetry (JSON):\n"
            '{"matches": ['
            '{"map": "Dragon Valley", "avg_fps": 28, "min_fps": 12, "gpu_usage_pct": 99, "ram_gb": 14.2, "duration_min": 22},'
            '{"map": "Crystal Arena", "avg_fps": 58, "min_fps": 45, "gpu_usage_pct": 72, "ram_gb": 10.1, "duration_min": 18},'
            '{"map": "Dragon Valley", "avg_fps": 25, "min_fps": 9, "gpu_usage_pct": 100, "ram_gb": 15.0, "duration_min": 25},'
            '{"map": "Sky Fortress", "avg_fps": 55, "min_fps": 40, "gpu_usage_pct": 70, "ram_gb": 9.8, "duration_min": 20},'
            '{"map": "Dragon Valley", "avg_fps": 30, "min_fps": 14, "gpu_usage_pct": 98, "ram_gb": 13.5, "duration_min": 24},'
            '{"map": "Crystal Arena", "avg_fps": 60, "min_fps": 48, "gpu_usage_pct": 68, "ram_gb": 10.0, "duration_min": 17},'
            '{"map": "Dragon Valley", "avg_fps": 22, "min_fps": 8, "gpu_usage_pct": 100, "ram_gb": 15.3, "duration_min": 26},'
            '{"map": "Sky Fortress", "avg_fps": 52, "min_fps": 38, "gpu_usage_pct": 74, "ram_gb": 10.5, "duration_min": 19},'
            '{"map": "Dragon Valley", "avg_fps": 27, "min_fps": 11, "gpu_usage_pct": 99, "ram_gb": 14.8, "duration_min": 23},'
            '{"map": "Crystal Arena", "avg_fps": 57, "min_fps": 44, "gpu_usage_pct": 71, "ram_gb": 10.2, "duration_min": 16}'
            "]}\n\n"
            "1. Use code_interpreter to compute per-map average FPS, GPU usage, and RAM, "
            "then identify which map has the performance problem.\n"
            "2. Use file_search to look up known optimization tips for that map from the game knowledge base.\n"
            "3. Give the player a 3-sentence recommendation."
        ),
    },
    {
        "name": "Game Art Generation — player-described scene",
        "icon": "🎨",
        "prompt": (
            "Use direct_image_generate to create a 1024x1024 game loading screen in a "
            "dark fantasy art style: a dragon perched on a crystal mountain at sunset, "
            "with a lone warrior standing at the base looking up. Dramatic lighting, "
            "high detail, game concept art quality. After generation, describe what "
            "was produced in one sentence."
        ),
    },
    {
        "name": "Post-match Intel — web search + analysis",
        "icon": "📊",
        "prompt": (
            "Use direct_web_search to find the current top 3 most popular esports games "
            "in 2026 by viewership. Then use code_interpreter to create a simple comparison "
            "showing the game names and their approximate peak concurrent viewers. "
            "Return the result as a formatted table."
        ),
    },
]


def main():
    parser = argparse.ArgumentParser(description="Gaming Cloud demo — 3 scenarios")
    parser.add_argument("--base-url", default="http://localhost:8088")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3], help="Run only one scenario (1/2/3)")
    args = parser.parse_args()

    scenarios = SCENARIOS if args.scenario is None else [SCENARIOS[args.scenario - 1]]

    with httpx.Client(timeout=args.timeout) as client:
        for i, sc in enumerate(scenarios, 1):
            print(f"\n{'='*70}")
            print(f"{sc['icon']}  SCENARIO {i}: {sc['name']}")
            print(f"{'='*70}")
            print(f"\nUser prompt (first 200 chars):\n  {sc['prompt'][:200]}...\n")
            print("Calling agent...")
            answer = ask(client, args.base_url, sc["prompt"])
            print(f"\n{sc['icon']}  AGENT RESPONSE:\n")
            for line in answer.split("\n"):
                print(f"  {line}")
            print()


if __name__ == "__main__":
    main()
