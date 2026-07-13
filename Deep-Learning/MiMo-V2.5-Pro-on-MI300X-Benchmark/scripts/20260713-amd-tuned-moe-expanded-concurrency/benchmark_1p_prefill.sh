#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-tuned-expanded/rep-1/prefill}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

for input_tokens in 8192 65536 262144; do
  for concurrency in 1 2 4 8; do
    run_point "$input_tokens" 1 "$concurrency" 16 1 600 "Input token throughput"
  done
done

printf 'Client sweep complete. Validate both 1P1D service logs before accepting points.\n'