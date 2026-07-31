#!/bin/bash
set -euo pipefail

SWE_BENCH_COMMIT=f7bbbb2ccdf479001d6467c9e34af59e44a840f9
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SWE_BENCH_DIR="${SWE_BENCH_DIR:-$REPO_ROOT/.dependencies/SWE-bench}"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-$REPO_ROOT/requirements-lock.txt}"

test -f "$REQUIREMENTS_FILE"
python -m pip install -r "$REQUIREMENTS_FILE"

if test -e "$SWE_BENCH_DIR" && ! test -d "$SWE_BENCH_DIR/.git"; then
  echo "SWE_BENCH_DIR exists but is not a Git checkout: $SWE_BENCH_DIR" >&2
  exit 2
fi
if ! test -d "$SWE_BENCH_DIR/.git"; then
  mkdir -p "$(dirname "$SWE_BENCH_DIR")"
  git clone --filter=blob:none https://github.com/SWE-bench/SWE-bench.git "$SWE_BENCH_DIR"
fi

git -C "$SWE_BENCH_DIR" fetch --depth=1 origin "$SWE_BENCH_COMMIT"
git -C "$SWE_BENCH_DIR" -c advice.detachedHead=false checkout --detach "$SWE_BENCH_COMMIT"
test "$(git -C "$SWE_BENCH_DIR" rev-parse HEAD)" = "$SWE_BENCH_COMMIT"
if test -n "$(git -C "$SWE_BENCH_DIR" status --porcelain=v1 --untracked-files=all)"; then
  echo "SWE-bench checkout is dirty; use a clean SWE_BENCH_DIR: $SWE_BENCH_DIR" >&2
  exit 3
fi
test -f "$SWE_BENCH_DIR/swebench/harness/constants/fixtures/tokio-rs__tokio-6724.Cargo.lock"

python -m pip install -e "$SWE_BENCH_DIR"
SWE_BENCH_EXPECTED_DIR="$(cd "$SWE_BENCH_DIR" && pwd -P)" python - <<'PY'
import importlib.metadata
import os
import pathlib
import swebench.harness.run_evaluation as runner

assert importlib.metadata.version("mini-swe-agent") == "2.4.6"
path = pathlib.Path(runner.__file__).resolve()
expected = pathlib.Path(os.environ["SWE_BENCH_EXPECTED_DIR"]).resolve()
if path != expected and expected not in path.parents:
    raise RuntimeError(f"SWE-bench imported from {path}, expected under {expected}")
print(f"ENVIRONMENT_SETUP=PASS mini-swe-agent=2.4.6 harness={path}")
PY