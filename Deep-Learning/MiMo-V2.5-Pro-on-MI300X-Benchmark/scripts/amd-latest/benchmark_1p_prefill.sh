#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/onep/prefill}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

run_point 8192 1 4 16 1 600 "Input token throughput"
run_point 65536 1 4 16 1 600 "Input token throughput"
run_point 262144 1 4 16 1 900 "Input token throughput" token_ids

printf 'Final 1P1D Prefill workloads completed. Validate all service logs before reporting.\n'