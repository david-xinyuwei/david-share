#!/bin/bash
# Setup script for NVIDIA Dynamo PD Disaggregation Benchmark
# Tested on: Ubuntu 24.04.4 LTS, Python 3.12.3, CUDA 13.2, 2x H100 NVL
# Author: Xinyu Wei (魏新宇)

set -e

echo "=== Step 1: Create Python venv ==="
python3 -m venv /root/dynamo-env
source /root/dynamo-env/bin/activate

echo "=== Step 2: Install SGLang ==="
pip install "sglang[all]"

echo "=== Step 3: Install Dynamo + NIXL ==="
pip install ai-dynamo nixl

echo "=== Step 4: Patch SGLang for Dynamo compatibility ==="
# Dynamo 1.0.1 imports get_local_ip_auto, get_zmq_socket, maybe_wrap_ipv6_address
# from sglang.srt.utils, but SGLang 0.5.10 moved them to sglang.srt.utils.network
# without re-exporting. maybe_wrap_ipv6_address doesn't exist at all in SGLang 0.5.10.
INIT_FILE="/root/dynamo-env/lib/python3.12/site-packages/sglang/srt/utils/__init__.py"
if ! python3 -c "from sglang.srt.utils import get_local_ip_auto" 2>/dev/null; then
    echo "Patching SGLang utils for Dynamo compatibility..."
    python3 -c "
f='$INIT_FILE'
c=open(f).read()
c+='\nfrom sglang.srt.utils.network import get_local_ip_auto, get_zmq_socket\ndef maybe_wrap_ipv6_address(addr):\n    return f\"[{addr}]\" if \":\" in addr and not addr.startswith(\"[\") else addr\n'
open(f,'w').write(c)
print('Patched successfully')
"
fi
python3 -c "from sglang.srt.utils import get_local_ip_auto, get_zmq_socket, maybe_wrap_ipv6_address; print('Import verification: OK')"

echo "=== Step 5: Install NATS server ==="
NATS_VER=v2.11.3
wget -qO /tmp/nats.tar.gz "https://github.com/nats-io/nats-server/releases/download/${NATS_VER}/nats-server-${NATS_VER}-linux-amd64.tar.gz"
tar xzf /tmp/nats.tar.gz -C /tmp/
cp /tmp/nats-server-${NATS_VER}-linux-amd64/nats-server /usr/local/bin/
echo "NATS: $(nats-server --version)"

echo "=== Step 6: Install etcd ==="
ETCD_VER=v3.5.21
wget -qO /tmp/etcd.tar.gz "https://github.com/etcd-io/etcd/releases/download/${ETCD_VER}/etcd-${ETCD_VER}-linux-amd64.tar.gz"
tar xzf /tmp/etcd.tar.gz -C /tmp/
cp /tmp/etcd-${ETCD_VER}-linux-amd64/etcd /tmp/etcd-${ETCD_VER}-linux-amd64/etcdctl /usr/local/bin/
echo "etcd: $(etcd --version | head -1)"

echo "=== Step 7: Download model ==="
MODEL_DIR="/root/models/Qwen3-8B"
if [ ! -d "$MODEL_DIR" ]; then
    pip install huggingface_hub
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3-8B', local_dir='$MODEL_DIR')
print('Model downloaded')
"
else
    echo "Model already exists at $MODEL_DIR"
fi

echo "=== Setup complete ==="
echo "Versions:"
python3 -c "import sglang; print(f'  SGLang: {sglang.__version__}')"
pip show ai-dynamo 2>/dev/null | grep Version | sed 's/^/  Dynamo: /'
pip show nixl 2>/dev/null | grep Version | sed 's/^/  NIXL: /'
echo "  NATS: $(nats-server --version)"
echo "  etcd: $(etcd --version | head -1)"
echo ""
echo "Run benchmarks: bash scripts/run_benchmark.sh all"
