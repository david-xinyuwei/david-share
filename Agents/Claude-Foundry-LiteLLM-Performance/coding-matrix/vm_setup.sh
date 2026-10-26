#!/usr/bin/env bash
# One-time setup of the East US 2 benchmark VM (Ubuntu 24.04).
set -euo pipefail

sudo apt-get update -qq >/dev/null
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io python3-venv python3-pip git jq >/dev/null
sudo usermod -aG docker "$USER"

python3 -m venv ~/venv
~/venv/bin/pip install -q --upgrade pip
~/venv/bin/pip install -q httpx==0.28.1 azure-identity==1.25.1
~/venv/bin/python -c 'import httpx, azure.identity; print("httpx", httpx.__version__, "azure-identity", azure.identity.__version__)'
docker --version

if [ ! -d ~/polyglot-benchmark ]; then
  git clone -q https://github.com/Aider-AI/polyglot-benchmark.git ~/polyglot-benchmark
fi
git -C ~/polyglot-benchmark log -1 --format='polyglot-benchmark %H %cd'
for lang in cpp go java javascript python rust; do
  echo "$lang $(ls ~/polyglot-benchmark/$lang/exercises/practice | wc -l)"
done
