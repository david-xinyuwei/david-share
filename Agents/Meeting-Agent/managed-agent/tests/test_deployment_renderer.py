import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_renderer_resolves_private_values_outside_public_source(tmp_path: Path) -> None:
    environment = {
        "AZURE_AI_PROJECT_ENDPOINT": (
            "https://example.services.ai.azure.com/api/projects/example-project"
        ),
        "AZURE_AI_PROJECT_NAME": "example-project",
        "AZURE_RESOURCE_GROUP": "example-rg",
        "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000000",
    }
    environment_path = tmp_path / "environment.json"
    environment_path.write_text(json.dumps(environment), encoding="utf-8")
    output_dir = tmp_path / "rendered"

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "render_deployment_source.py"),
            "--env-json",
            str(environment_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rendered = yaml.safe_load((output_dir / "azure.yaml").read_text(encoding="utf-8"))
    prompt = rendered["services"]["managed-meeting-agent"]["config"]["promptAgent"]
    assert prompt == {
        "apiVersion": "v1",
        "baseUrl": "https://ai.azure.com/api",
        "modelEndpoint": "https://example.services.ai.azure.com",
        "projectEndpoint": environment["AZURE_AI_PROJECT_ENDPOINT"],
        "resourceGroup": "example-rg",
        "subscriptionId": environment["AZURE_SUBSCRIPTION_ID"],
        "workspace": "example-project",
    }
    assert (output_dir / "agent.yaml").read_bytes() == (ROOT / "agent.yaml").read_bytes()
    assert (output_dir / "instructions.md").read_bytes() == (
        ROOT / "instructions.md"
    ).read_bytes()
    assert (output_dir / "skills" / "meeting-package" / "SKILL.md").read_bytes() == (
        ROOT / "skills" / "meeting-package" / "SKILL.md"
    ).read_bytes()
    manifest = json.loads(
        (output_dir / "DEPLOY-SOURCE-MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["service_name"] == "managed-meeting-agent"
    assert manifest["private_values_written_only_under_ignored_azure_directory"] is True


def test_deploy_script_requires_double_isolation() -> None:
    source = (ROOT / "scripts" / "deploy-managed-agent.sh").read_text(
        encoding="utf-8"
    )

    for name in (
        "AZURE_CONFIG_DIR",
        "AZD_CONFIG_DIR",
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
    ):
        assert f"${{{name}:?" in source
    assert "render_deployment_source.py" in source
    assert "trap restore_public_yaml EXIT" in source
    assert 'cp "$deploy_root/azure.yaml" "$public_azure_yaml"' in source
    assert '--cwd "$ROOT"' in source
    assert "azd deploy managed-meeting-agent" in source