#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-tuned-expanded/rep-1/dp2}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

for input_tokens in 8192 65536 262144; do
  for concurrency in 1 2 4 8 16; do
    run_point "$input_tokens" 1 "$concurrency" 32 1 900 "Input token throughput"
  done
done

printf 'Client sweep complete. Validate both DP=2 service logs and worker distribution before accepting points.\n'