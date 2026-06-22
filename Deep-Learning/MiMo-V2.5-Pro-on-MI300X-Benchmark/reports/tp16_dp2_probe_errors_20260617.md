# TP16 / DP2 Probe Error Excerpt

Captured: 2026-06-17

This is a sanitized excerpt. It preserves the technical failure class without publishing VM access details.

## Topology

```text
--tp-size 16
--dp-size 2
--enable-dp-attention
--enable-dp-lm-head
--moe-a2a-backend mori
--nnodes 2
--page-size 64
--chunked-prefill-size 32768
--attention-backend triton
```

## Readiness

```text
node0 grep -c "fired up" /data/bench_tp16_dp2/node0_server.log -> 0
node1 grep -c "fired up" /data/bench_tp16_dp2/node1_server.log -> 0
```

## Representative Failure Lines

```text
Out of heap memory while requesting roughly 822 MB from a 4 GB heap.
hip failed with invalid argument in dispatch_combine.cpp:150.
NCCL/RCCL all-reduce warnings appeared around the same failure window.
Node 1 terminated during startup; FastAPI lifespan later reported AttributeError on NoneType.server_args because the runtime engine never initialized.
```

## Interpretation

The launch reached `server_args` and passed the effective-attention-TP validation path. It failed later in MORI distributed dispatch/combine heap allocation before the HTTP server became ready. No TP16/DP2 benchmark numbers were produced.
