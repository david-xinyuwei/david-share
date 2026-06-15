# Hybrid Edge-Cloud Example

This example shows a safe handoff pattern between a device-side process and a cloud-hosted agent.

## Flow

1. `edge_agent.py` collects deterministic sensor readings and writes `contract.json`.
2. `cloud_handoff.py` reads the contract and submits a structured prompt to the hosted agent Responses endpoint.
3. The hosted agent can use `code_interpreter` to calculate statistics and return a recommendation.

## Run

```bash
python edge_agent.py
AGENT_URL=http://localhost:8088/responses python cloud_handoff.py
```

## Example Output

```text
[edge] current_owner=cloud
[edge] wrote contract.json
[cloud] accepted contract_id=task-1234abcd
[cloud] objective=Compute mean, min, and max for each signal and return a short ventilation recommendation.
```
