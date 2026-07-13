#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 2 ]]; then
  printf 'Usage: %s INPUT_TOKENS CONCURRENCY\n' "$0" >&2
  exit 2
fi

input_tokens="$1"
concurrency="$2"
case "$input_tokens" in
  8192|65536|262144) ;;
  *) printf 'Unsupported input length: %s\n' "$input_tokens" >&2; exit 2 ;;
esac
case "$concurrency" in
  1|2|4|8|16) ;;
  *) printf 'Unsupported concurrency: %s\n' "$concurrency" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${LOG_DIR:-/data/mimo-tuned-expanded/rep-1/dp2}"
export LOG_DIR
source "$SCRIPT_DIR/benchmark_common.sh"

run_point "$input_tokens" 1 "$concurrency" 32 1 900 "Input token throughput"