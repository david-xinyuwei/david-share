"""One-shot infrastructure setup for the Foundry Hosted Agent + Toolbox demo.

Creates (or verifies) the minimum Azure resources this repo needs:

  - Resource group
  - Cognitive Services account (Foundry account)
  - Foundry project
  - One chat model deployment (default: gpt-4.1-mini)
  - Optional: one image model deployment (gpt-image-1)

After it finishes, prints the values you need to put in `.env`.

Authentication: relies on `az login` having been run for the target subscription.
This script uses the Azure CLI under the hood (subprocess) to keep the dependency
surface tiny.

Usage:

    az login
    az account set --subscription <subscription-id>
    python infra/setup_foundry.py \
        --resource-group rg-toolbox-demo \
        --account toolbox-demo-ais \
        --project toolbox-project-v2 \
        --location eastus2

Add `--with-image` to also deploy gpt-image-1 for the direct_image_generate tool.
"""
import argparse
import json
import shlex
import subprocess
import sys
from typing import Any


def run(cmd: str) -> tuple[int, str]:
    print(f"$ {cmd}")
    result = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    out = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        print(out)
    return result.returncode, out


def az(cmd: str) -> dict[str, Any] | list[Any] | None:
    code, out = run(cmd)
    if code != 0:
        return None
    out = out.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def ensure_resource_group(name: str, location: str) -> None:
    if az(f"az group show -n {name}"):
        print(f"[ok] resource group {name} already exists.")
        return
    az(f"az group create -n {name} -l {location}")


def ensure_account(rg: str, name: str, location: str) -> None:
    if az(f"az cognitiveservices account show -g {rg} -n {name}"):
        print(f"[ok] account {name} already exists.")
        return
    az(
        f"az cognitiveservices account create -g {rg} -n {name} "
        f"-l {location} --kind AIServices --sku S0 --yes"
    )


def ensure_deployment(rg: str, account: str, deployment: str, model: str, version: str, sku: str = "GlobalStandard") -> None:
    existing = az(
        f"az cognitiveservices account deployment show -g {rg} -n {account} --deployment-name {deployment}"
    )
    if existing:
        print(f"[ok] deployment {deployment} already exists.")
        return
    az(
        f"az cognitiveservices account deployment create -g {rg} -n {account} "
        f"--deployment-name {deployment} --model-name {model} --model-version {version} "
        f"--model-format OpenAI --sku-name {sku} --sku-capacity 1"
    )


def ensure_project(rg: str, account: str, project: str) -> None:
    print(f"[note] Project creation is not exposed via `az cognitiveservices` today.")
    print(f"       Open the Foundry portal and create project {project!r} under account {account!r}")
    print(f"       https://ai.azure.com")
    print(f"       Then re-run this script with the same arguments to verify deployments.")


def print_env(account: str, project: str, location: str, with_image: bool) -> None:
    project_endpoint = f"https://{account}.services.ai.azure.com/api/projects/{project}"
    print()
    print("=" * 60)
    print("Suggested .env (copy into the repo root):")
    print("=" * 60)
    print(f"FOUNDRY_PROJECT_ENDPOINT={project_endpoint}")
    print("AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4-1-mini")
    print("TOOLBOX_NAME=agent-tools")
    print("AZURE_AUTH_MODE=cli")
    print("PORT=8088")
    print("ENABLE_DIRECT_WEB_SEARCH=true")
    if with_image:
        print("AZURE_AI_IMAGE_DEPLOYMENT_NAME=gpt-image-1")
        print("ENABLE_DIRECT_IMAGE_GENERATE=true")
    print("=" * 60)
    print(f"Region: {location}")
    print(
        "Note: confirm region supports the chosen models and tool types in the "
        "Foundry docs region matrix."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", default="eastus2")
    parser.add_argument("--chat-deployment", default="gpt-4-1-mini")
    parser.add_argument("--chat-model", default="gpt-4.1-mini")
    parser.add_argument("--chat-version", default="2025-04-14")
    parser.add_argument("--with-image", action="store_true")
    parser.add_argument("--image-deployment", default="gpt-image-1")
    parser.add_argument("--image-model", default="gpt-image-1")
    parser.add_argument("--image-version", default="2025-04-15")
    args = parser.parse_args()

    if az("az account show") is None:
        print("ERROR: not logged in. Run `az login` then `az account set --subscription <id>` first.")
        sys.exit(1)

    ensure_resource_group(args.resource_group, args.location)
    ensure_account(args.resource_group, args.account, args.location)
    ensure_deployment(args.resource_group, args.account, args.chat_deployment, args.chat_model, args.chat_version)
    if args.with_image:
        ensure_deployment(args.resource_group, args.account, args.image_deployment, args.image_model, args.image_version)
    ensure_project(args.resource_group, args.account, args.project)

    print_env(args.account, args.project, args.location, args.with_image)


if __name__ == "__main__":
    main()
