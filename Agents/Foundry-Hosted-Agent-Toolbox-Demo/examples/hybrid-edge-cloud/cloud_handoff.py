"""Cloud handoff — reads the task contract, calls the hosted agent's /responses
endpoint with the pending cloud step, updates the contract with the result.

Requires the local Responses server (`python main.py`) to be running, OR a
deployed Foundry hosted agent. Pass --base-url to point elsewhere.
"""
import argparse
import json
from pathlib import Path

import httpx

from contract import TaskContract


def extract_text(payload: dict) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text" and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks) or json.dumps(payload, indent=2)[:1500]


def main() -> None:
    parser = argparse.ArgumentParser(description="Cloud handoff — invoke hosted agent on contract")
    parser.add_argument("--contract", default="contract.json")
    parser.add_argument("--base-url", default="http://localhost:8088")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    contract_path = Path(args.contract)
    contract = TaskContract.load(contract_path)

    if contract.current_owner != "cloud":
        print(f"[cloud] current_owner = {contract.current_owner!r}, nothing to do.")
        return

    cloud_step = next((s for s in contract.plan if s.owner == "cloud" and s.status == "pending"), None)
    if cloud_step is None:
        print("[cloud] No pending cloud step.")
        return

    print(f"[cloud] Picked up task {contract.task_id} (contract version {contract.version}).")
    print(f"[cloud] Pending step: {cloud_step.description[:80]}...")

    cloud_step.status = "in_progress"
    contract.bump(who="cloud")
    contract.save(contract_path)

    # Build the prompt the hosted agent will see. We embed the artifact directly
    # because this demo uses local files; in production you would pass a blob URI.
    readings = contract.artifacts.get("sensor_readings", {})
    prompt = (
        f"User intent: {contract.intent}\n\n"
        f"Sensor readings (24 hourly samples per channel):\n"
        f"{json.dumps(readings, indent=2)}\n\n"
        "Use code_interpreter to compute mean / max / min for each channel, "
        "then state in one paragraph whether ventilation is needed and why."
    )

    body = {"input": prompt}
    print(f"[cloud] Calling hosted agent at {args.base_url}/responses ...")
    with httpx.Client(timeout=args.timeout) as client:
        response = client.post(f"{args.base_url.rstrip('/')}/responses", json=body)
        response.raise_for_status()
        payload = response.json()

    text = extract_text(payload)
    cloud_step.status = "done"
    cloud_step.result = {"answer": text, "response_id": payload.get("id")}
    contract.current_owner = "complete"
    contract.bump(who="cloud")
    contract.save(contract_path)

    print(f"[cloud] Step complete. Contract version now {contract.version}.")
    print("=" * 60)
    print("HOSTED AGENT ANSWER:")
    print("=" * 60)
    print(text)
    print("=" * 60)


if __name__ == "__main__":
    main()
