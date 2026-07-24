"""Render a private azd deployment tree from the public Agent source."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "agent.yaml",
    "instructions.md",
    "skills/meeting-package/SKILL.md",
)
REQUIRED_ENV = (
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_AI_PROJECT_NAME",
    "AZURE_RESOURCE_GROUP",
    "AZURE_SUBSCRIPTION_ID",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    values = json.loads(args.env_json.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED_ENV if not values.get(key)]
    if missing:
        raise RuntimeError(f"Missing azd environment values: {', '.join(missing)}")

    project_endpoint = str(values["AZURE_AI_PROJECT_ENDPOINT"])
    parsed = urlparse(project_endpoint)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".services.ai.azure.com")
        or "/api/projects/" not in parsed.path
    ):
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT is not a Foundry project URL")
    model_endpoint = f"{parsed.scheme}://{parsed.hostname}"

    output_dir = args.output_dir.expanduser().resolve()
    if output_dir == ROOT or ROOT in output_dir.parents:
        expected_parent = (ROOT / ".azure").resolve()
        if output_dir != expected_parent and expected_parent not in output_dir.parents:
            raise ValueError("Deployment output inside the source tree must stay under .azure")
    shutil.rmtree(output_dir, ignore_errors=True)
    for relative in SOURCE_FILES:
        source = ROOT / relative
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    deployment = yaml.safe_load((ROOT / "azure.yaml").read_text(encoding="utf-8"))
    service = deployment["services"]["managed-meeting-agent"]
    prompt = service["config"]["promptAgent"]
    prompt.update(
        {
            "modelEndpoint": model_endpoint,
            "projectEndpoint": project_endpoint,
            "resourceGroup": str(values["AZURE_RESOURCE_GROUP"]),
            "subscriptionId": str(values["AZURE_SUBSCRIPTION_ID"]),
            "workspace": str(values["AZURE_AI_PROJECT_NAME"]),
        }
    )
    rendered_yaml = output_dir / "azure.yaml"
    rendered_yaml.write_text(
        yaml.safe_dump(deployment, sort_keys=False),
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "schema_version": 1,
        "agent_name": service["config"]["promptAgent"].get(
            "name", deployment["name"]
        ),
        "service_name": "managed-meeting-agent",
        "source_files": {
            relative: _sha256(ROOT / relative) for relative in SOURCE_FILES
        },
        "public_azure_yaml_sha256": _sha256(ROOT / "azure.yaml"),
        "rendered_azure_yaml_sha256": _sha256(rendered_yaml),
        "private_values_written_only_under_ignored_azure_directory": True,
    }
    (output_dir / "DEPLOY-SOURCE-MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest))
    return 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())