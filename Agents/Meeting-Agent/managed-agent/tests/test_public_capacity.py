from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_public_capacity_is_minimal() -> None:
    data = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
    capacity = data["services"]["managed-meeting-agent"]["config"]["deployments"][0][
        "sku"
    ]["capacity"]
    assert capacity == 1
