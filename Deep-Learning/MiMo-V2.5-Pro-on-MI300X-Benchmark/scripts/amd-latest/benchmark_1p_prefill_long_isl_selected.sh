#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/onep/prefill-long-isl-selected}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

run_point 131072 1 4 16 1 1800 "Input token throughput"
run_point 196608 1 4 16 1 2400 "Input token throughput"

printf 'Selected 128K/192K 1P1D Prefill points completed. Validate service logs before reporting.\n'
