#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/dp2}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

run_point 8192 1 16 32 1 900 "Input token throughput"
run_point 65536 1 2 32 1 900 "Input token throughput"
run_point 262144 1 2 32 1 1200 "Input token throughput" token_ids

printf 'Final DP=2 Prefill peak workloads completed. Validate both service logs and worker distribution before reporting.\n'