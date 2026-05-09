"""Edge agent — runs locally, does the cheap private steps, writes the task contract.

In a real device this would integrate with the local sensor APIs, microphone, OS
shell, etc. Here we simulate by generating fake sensor readings deterministically.
"""
import argparse
import json
import random
from pathlib import Path

from contract import Step, TaskContract


def simulate_sensor_capture(seed: int = 42) -> dict[str, list[float]]:
    """Simulate a device capturing 24 hours of sensor readings."""
    random.seed(seed)
    return {
        "temperature_c": [round(20 + 5 * random.random(), 2) for _ in range(24)],
        "humidity_pct": [round(40 + 20 * random.random(), 2) for _ in range(24)],
        "co2_ppm": [round(400 + 600 * random.random(), 2) for _ in range(24)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Edge agent — local task initiator")
    parser.add_argument(
        "--contract",
        default="contract.json",
        help="Path to write the shared task contract.",
    )
    parser.add_argument(
        "--intent",
        default=(
            "Analyze 24 hours of indoor air-quality sensor data and tell the user "
            "whether ventilation is needed. Use code_interpreter to compute the "
            "statistics, do not eyeball them."
        ),
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    contract_path = Path(args.contract)

    # Step 1: edge collects sensor data (cheap, private, offline).
    readings = simulate_sensor_capture(seed=args.seed)
    print(f"[edge] Captured 24 hourly readings for 3 sensors (seed={args.seed}).")

    contract = TaskContract(intent=args.intent)
    contract.plan = [
        Step(
            step_id=1,
            owner="edge",
            description="Capture indoor sensor readings",
            status="done",
            result={"readings_summary": {k: f"{len(v)} hourly values" for k, v in readings.items()}},
        ),
        Step(
            step_id=2,
            owner="cloud",
            description=(
                "Use code_interpreter to compute mean / max / min for each sensor, "
                "then advise whether ventilation is needed (CO2 > 1000 ppm sustained = yes)."
            ),
            status="pending",
        ),
    ]
    contract.artifacts = {"sensor_readings": readings}
    contract.current_owner = "cloud"
    contract.bump(who="edge")
    contract.save(contract_path)

    print(f"[edge] Wrote contract to {contract_path}")
    print(f"[edge] current_owner now = {contract.current_owner}")
    print(f"[edge] artifact size = {len(json.dumps(readings))} bytes")
    print("[edge] Closing lid. Cloud takes over.")


if __name__ == "__main__":
    main()
