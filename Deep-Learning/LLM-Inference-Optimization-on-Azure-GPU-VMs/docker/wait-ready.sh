#!/usr/bin/env bash
# Wait until an SGLang server answers /server_info with JSON, then print the KV capacity it
# reports. /server_info does not generate tokens; SGLang's /health does by default.
#
#   bash docker/wait-ready.sh <host> <port> [timeout seconds, default 3600] [container name]
#
# With a container name, the wait stops early when that container has exited for good.
# The first start of a new container compiles AITER JIT kernels and loads about 1 TB of
# weights, so allow tens of minutes.
set -euo pipefail

HOST="${1:?usage: wait-ready.sh <host> <port> [timeout] [container]}"
PORT="${2:?usage: wait-ready.sh <host> <port> [timeout] [container]}"
TIMEOUT="${3:-3600}"
CONTAINER="${4:-}"
deadline=$((SECONDS + TIMEOUT))

while true; do
  if body="$(curl -fsS --max-time 10 "http://$HOST:$PORT/server_info" 2>/dev/null)" \
     && tokens="$(printf '%s' "$body" | python3 -c '
import json, sys
def find(x):
    if isinstance(x, dict):
        if isinstance(x.get("max_total_num_tokens"), int):
            return x["max_total_num_tokens"]
        x = list(x.values())
    if isinstance(x, list):
        for v in x:
            r = find(v)
            if r is not None:
                return r
    return None
print(find(json.load(sys.stdin)) or "not reported")' 2>/dev/null)"; then
    echo "READY $HOST:$PORT max_total_num_tokens=$tokens"
    exit 0
  fi
  if [ -n "$CONTAINER" ]; then
    state="$(docker inspect -f '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo missing)"
    if [ "$state" = exited ] || [ "$state" = dead ] || [ "$state" = missing ]; then
      echo "FAILED $CONTAINER is $state; last log lines:" >&2
      docker logs --tail 20 "$CONTAINER" >&2 2>&1 || true
      exit 1
    fi
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "NOT READY after ${TIMEOUT}s: $HOST:$PORT" >&2
    exit 1
  fi
  sleep 15
done
