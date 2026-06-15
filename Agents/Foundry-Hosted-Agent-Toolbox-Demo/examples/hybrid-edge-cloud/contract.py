from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json
import time
import uuid


@dataclass
class SensorContract:
    contract_id: str
    version: int
    created_at: float
    current_owner: str
    device_id: str
    objective: str
    readings: dict[str, list[float]]


def build_contract(device_id: str, readings: dict[str, list[float]], objective: str) -> SensorContract:
    return SensorContract(
        contract_id="task-" + uuid.uuid4().hex[:8],
        version=1,
        created_at=time.time(),
        current_owner="cloud",
        device_id=device_id,
        objective=objective,
        readings=readings,
    )


def write_contract(contract: SensorContract, path: str | Path) -> Path:
    target = Path(path)
    target.write_text(json.dumps(asdict(contract), indent=2), encoding="utf-8")
    return target


def read_contract(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
