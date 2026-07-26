from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_deployment_example_supports_large_inputs_and_uses_placeholders() -> None:
    deployment = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
    service = deployment["services"]["managed-meeting-agent"]

    assert service["config"]["deployments"][0]["sku"]["capacity"] == 100
    prompt = service["config"]["promptAgent"]
    assert all(str(value).startswith("${") for key, value in prompt.items() if key in {
        "modelEndpoint", "projectEndpoint", "resourceGroup", "subscriptionId", "workspace"
    })
