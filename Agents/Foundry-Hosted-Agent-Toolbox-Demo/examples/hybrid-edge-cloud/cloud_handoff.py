from __future__ import annotations

from pathlib import Path
import json
import os

import httpx

from contract import read_contract


def build_prompt(contract: dict) -> str:
    return (
        "Use code_interpreter to analyze this edge-device sensor contract. "
        "Return mean, min, max for each signal and a two-sentence recommendation.\n\n"
        + json.dumps(contract, indent=2)
    )


def submit_to_hosted_agent(prompt: str) -> dict:
    agent_url = os.getenv("AGENT_URL", "http://localhost:8088/responses")
    response = httpx.post(agent_url, json={"input": prompt}, timeout=120.0)
    response.raise_for_status()
    return response.json()


def main() -> None:
    contract_path = Path(__file__).with_name("contract.json")
    contract = read_contract(contract_path)
    print(f"[cloud] accepted contract_id={contract['contract_id']}")
    print(f"[cloud] objective={contract['objective']}")
    payload = submit_to_hosted_agent(build_prompt(contract))
    print(json.dumps(payload, indent=2)[:4000])


if __name__ == "__main__":
    main()
