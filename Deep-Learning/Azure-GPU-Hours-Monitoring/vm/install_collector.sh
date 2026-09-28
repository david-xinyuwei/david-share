#!/bin/bash
# Installs the DCGM GPU collector as a systemd service.
# Usage (on the GPU VM, as root): bash install_collector.sh
# Expects gpu_collector.py next to this script, or GPUMON_B64 env with its base64 content.
set -euo pipefail

command -v dcgmi >/dev/null || { echo "dcgmi not found, install datacenter-gpu-manager first"; exit 1; }

systemctl enable --now nvidia-dcgm 2>/dev/null || systemctl enable --now dcgm

install -d -m 0755 /opt/gpumon /var/log/gpumon
if [ -n "${GPUMON_B64:-}" ]; then
  echo "$GPUMON_B64" | base64 -d > /opt/gpumon/gpu_collector.py
else
  install -m 0755 "$(dirname "$0")/gpu_collector.py" /opt/gpumon/gpu_collector.py
fi
chmod 0755 /opt/gpumon/gpu_collector.py

cat > /etc/systemd/system/gpumon.service <<'EOF'
[Unit]
Description=DCGM GPU metrics collector for Azure Monitor (GpuMetrics_CL)
After=nvidia-dcgm.service network-online.target
Wants=nvidia-dcgm.service

[Service]
ExecStart=/usr/bin/python3 /opt/gpumon/gpu_collector.py
Restart=always
RestartSec=10
Nice=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gpumon
systemctl restart gpumon
sleep 3
systemctl --no-pager --lines=5 status gpumon
