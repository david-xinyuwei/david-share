#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-amd-latest/onep/decode-long-context}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

# Requested 64K input / 1K output at selected concurrency points.
run_point 65536 1024 16 32 4 2400 "Output token throughput"
run_point 65536 1024 32 64 4 2400 "Output token throughput"
run_point 65536 1024 64 128 8 3000 "Output token throughput"
run_point 65536 1024 96 192 8 3600 "Output token throughput"

# Requested 255K input + 1K output = 256K total sequence length.
# This is not a 256K-input claim; 256K input + 1K output exceeds context 262151.
run_point 261120 1024 1 1 0 2400 "Output token throughput"

printf 'Final-runtime long-context Decode workloads completed. Validate all service logs before reporting.\n'
