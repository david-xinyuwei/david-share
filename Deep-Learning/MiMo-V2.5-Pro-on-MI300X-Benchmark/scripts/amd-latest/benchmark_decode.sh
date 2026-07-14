#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/onep/decode}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

for concurrency in 16 32 64 128; do
  run_point 8192 1024 "$concurrency" 256 32 900 "Output token throughput"
done

printf 'Final 1P1D Decode workloads completed. Validate all service logs before reporting.\n'