#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-tuned-expanded/rep-1/decode}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

for concurrency in 8 16 32 64 96 128 192 256; do
  run_point 8192 1024 "$concurrency" 256 32 900 "Output token throughput"
done

printf 'Client sweep complete. Validate both 1P1D service logs before accepting points.\n'