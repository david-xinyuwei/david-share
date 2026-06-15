from __future__ import annotations

import argparse
import os
import subprocess
import sys


REQUIRED_ENV = [
    "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    "TOOLBOX_NAME",
]


def require_env() -> None:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if not os.getenv("AZURE_AI_PROJECT_ENDPOINT") and not os.getenv("FOUNDRY_PROJECT_ENDPOINT"):
        missing.append("AZURE_AI_PROJECT_ENDPOINT or FOUNDRY_PROJECT_ENDPOINT")
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required environment variables: {joined}")


def run(command: list[str], dry_run: bool) -> None:
    print("$ " + " ".join(command))
    if dry_run:
        return
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Foundry demo infrastructure helpers.")
    parser.add_argument("--setup-toolbox", action="store_true", help="Create or update the configured Foundry Toolbox.")
    parser.add_argument("--verify", action="store_true", help="Verify Toolbox MCP discovery after setup.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    args = parser.parse_args()

    require_env()

    if not args.setup_toolbox and not args.verify:
        parser.error("Select at least one action: --setup-toolbox or --verify")

    python = sys.executable
    if args.setup_toolbox:
        run([python, "scripts/create_toolbox.py", "--with-code-interpreter", "--with-file-search", "--with-web-search", "--set-default"], args.dry_run)
    if args.verify:
        run([python, "scripts/verify_toolbox.py"], args.dry_run)


if __name__ == "__main__":
    main()
