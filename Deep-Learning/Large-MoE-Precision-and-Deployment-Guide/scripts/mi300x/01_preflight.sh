#!/bin/bash
# 01_preflight.sh — prepare one ND96isr_MI300X_v5 node and record what it is. Run with sudo.
#   sudo -E bash scripts/mi300x/01_preflight.sh
# What it does (idempotent):
#   1. prints kernel / ROCm / GPU / NVMe / InfiniBand facts into $MOE_ROOT/logs/01_preflight.log
#   2. if $MOE_SCRATCH is not mounted: builds a RAID0 over the local NVMe devices and mounts it there
#   3. moves the Docker and containerd stores onto $MOE_SCRATCH (the OS disk is 256 GB; two model images
#      plus layer cache exceed it). Docker 29 keeps images in containerd's store, so containerd must move too.
# Expected observations at the end: GPU_COUNT=8, NVME_FREE_GB > 3000, docker_root and containerd root under $MOE_SCRATCH.
set -u
. "$(dirname "$0")/00_env.sh"
exec > >(tee -a "$MOE_ROOT/logs/01_preflight.log") 2>&1
echo "PREFLIGHT_START=$(date -u +%FT%TZ) host=$(hostname) up=$(uptime -p)"

echo "--- kernel/os ---"; uname -r; . /etc/os-release; echo "$PRETTY_NAME"
echo "--- rocm host ---"; cat /opt/rocm/.info/version 2>/dev/null || ls -d /opt/rocm*; dkms status 2>/dev/null | grep -i amdgpu | head -2
echo "--- gpus ---"
rocm-smi --showproductname --showmeminfo vram --json 2>/dev/null | python3 -c '
import sys, json
d = json.load(sys.stdin); print("GPU_COUNT=" + str(len(d)))
for k, v in d.items(): print(k, v.get("Card Series", ""), v.get("VRAM Total Memory (B)", ""))' 2>/dev/null || rocm-smi --showproductname | head -20
echo "--- disks ---"; df -h / | tail -1; lsblk -d -n -o NAME,SIZE,TYPE | grep nvme | tr '\n' ';'; echo

if ! mountpoint -q "$MOE_SCRATCH"; then
  echo "RAID0: assembling local NVMe -> $MOE_SCRATCH"
  apt-get install -y -qq mdadm >/dev/null 2>&1 || true
  DEVS=$(ls /dev/nvme?n1 | tr '\n' ' ')
  mdadm --create --run /dev/md0 --level=0 --raid-devices=$(echo $DEVS | wc -w) $DEVS >/dev/null 2>&1 \
    && mkfs.xfs -f /dev/md0 >/dev/null 2>&1 && mkdir -p "$MOE_SCRATCH" && mount /dev/md0 "$MOE_SCRATCH"
fi
df -h "$MOE_SCRATCH" | tail -1
echo "NVME_FREE_GB=$(df -BG --output=avail "$MOE_SCRATCH" | tail -1 | tr -d 'G ')"
mkdir -p "$HF_CACHE/hub" "$MOE_SCRATCH/docker" "$MOE_SCRATCH/containerd"
chown -R "${SUDO_USER:-$USER}" "$HF_CACHE" 2>/dev/null

echo "--- docker / containerd stores ---"
if ! grep -q '"data-root"' /etc/docker/daemon.json 2>/dev/null || ! grep -q "$MOE_SCRATCH/containerd" /etc/containerd/config.toml 2>/dev/null; then
  systemctl stop docker.socket docker containerd 2>/dev/null
  echo "{\"data-root\":\"$MOE_SCRATCH/docker\",\"default-ulimits\":{\"memlock\":{\"Name\":\"memlock\",\"Hard\":-1,\"Soft\":-1}}}" > /etc/docker/daemon.json
  [ -f /etc/containerd/config.toml ] && cp -a /etc/containerd/config.toml "/etc/containerd/config.toml.bak-$(date -u +%Y%m%d)"
  # containerd config schema v3 rejects the old `disabled_plugins = ["cri"]` line; keep the file minimal.
  printf 'version = 3\nroot = "%s/containerd"\n' "$MOE_SCRATCH" > /etc/containerd/config.toml
  systemctl reset-failed containerd docker 2>/dev/null
  systemctl start containerd; sleep 2; systemctl start docker; sleep 3
fi
echo "containerd=$(systemctl is-active containerd) docker=$(systemctl is-active docker)"
docker info -f 'docker_root={{.DockerRootDir}} driver={{.Driver}} server={{.ServerVersion}}' 2>&1
echo "containerd_root=$(grep '^root' /etc/containerd/config.toml)"

echo "--- infiniband ---"; echo "ib_active=$(ibstat 2>/dev/null | grep -c 'State: Active')"; ls /sys/class/infiniband/ 2>/dev/null | tr '\n' ' '; echo
echo "--- hugging face reachability ---"
curl -sS -o /dev/null -w 'HF_HTTP=%{http_code} t=%{time_total}s\n' --max-time 20 "https://huggingface.co/api/models/$NEMOTRON_ID" || echo HF_UNREACHABLE
echo "PREFLIGHT_END=$(date -u +%FT%TZ)"
