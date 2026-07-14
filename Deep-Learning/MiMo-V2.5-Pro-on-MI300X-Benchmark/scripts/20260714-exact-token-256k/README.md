# Exact-Token 1P1D 256K Validation

This bundle validates a real 262,144-token 1P1D Prefill workload instead of relying on client-only HTTP success accounting.

## Required Service Change

Apply the following change to both the Prefill and Decode launch commands while preserving the remaining AMD launch parameters:

```diff
-  --context-length 262144
+  --context-length 262151
```

With EAGLE enabled, the runtime reserves four draft-token slots. This SGLang build also exposes `max_req_input_len=context_length-6` and rejects an input when its length is greater than or equal to that value. Context length 262151 is therefore the minimum setting that exposes `max_req_input_len=262145` and accepts a 262,144-token prompt.

Before measurement, capture `/server_info` directly from both workers and require:

```text
context_length=262151
max_req_input_len>=262145
```

## Run

Start the Prefill, Decode, and PD router services, then run on the Prefill node:

```bash
LOG_DIR=/data/mimo-exact-token-256k \
  bash benchmark_256k_exact_tokens.sh
```

`--tokenize-prompt` sends token IDs directly and eliminates text decode/re-encode length drift.

## Validate

```bash
python3 validate_exact_256k.py \
  /data/mimo-exact-token-256k/benchmark_262144_con4.log \
  --prefill-info /data/mimo-exact-token-256k/prefill_server_info.json \
  --decode-info /data/mimo-exact-token-256k/decode_server_info.json \
  --service-logs \
    /data/mimo-exact-token-256k/prefill_outer.log \
    /data/mimo-exact-token-256k/decode_outer.log \
    /data/mimo-exact-token-256k/router_outer.log \
  --output /data/mimo-exact-token-256k/validation.json
```

Acceptance requires 16 successful requests, 16 retokenized outputs, exactly 4,194,304 accounted input tokens, valid direct-worker capacity, and zero fatal/context markers. The measured accepted result was 12,864.96 input tok/s over 326.03 seconds.