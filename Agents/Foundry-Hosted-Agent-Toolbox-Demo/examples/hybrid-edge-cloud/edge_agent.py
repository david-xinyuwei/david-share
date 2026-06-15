from __future__ import annotations

from pathlib import Path
import random

from contract import build_contract, write_contract


def collect_sensor_readings(seed: int = 42) -> dict[str, list[float]]:
    random.seed(seed)
    return {
        "temperature_c": [round(20 + random.random() * 5, 2) for _ in range(24)],
        "humidity_pct": [round(40 + random.random() * 20, 2) for _ in range(24)],
        "co2_ppm": [round(400 + random.random() * 600, 2) for _ in range(24)],
    }


def main() -> None:
    readings = collect_sensor_readings()
    contract = build_contract(
        device_id="edge-device-001",
        readings=readings,
        objective="Compute mean, min, and max for each signal and return a short ventilation recommendation.",
    )
    output_path = write_contract(contract, Path(__file__).with_name("contract.json"))
    print(f"[edge] contract_id={contract.contract_id}")
    print(f"[edge] current_owner={contract.current_owner}")
    print(f"[edge] wrote {output_path}")


if __name__ == "__main__":
    main()
