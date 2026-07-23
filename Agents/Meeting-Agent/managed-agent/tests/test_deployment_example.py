from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_deployment_example_uses_minimal_capacity_and_placeholders() -> None:
    deployment = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
    service = deployment["services"]["managed-meeting-agent"]

    assert service["config"]["deployments"][0]["sku"]["capacity"] == 1
    prompt = service["config"]["promptAgent"]
    assert all(str(value).startswith("${") for key, value in prompt.items() if key in {
        "modelEndpoint", "projectEndpoint", "resourceGroup", "subscriptionId", "workspace"
    })
