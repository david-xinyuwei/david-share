# Run timeline

Nine attempts on the same 4× A100 80GB PCIe node, same model, same dataset. Only the
variable named in "change" differs between consecutive rows.

`Running` is container runtime, measured from the state transition to the terminal state.
It is a useful ordering signal — each fix pushes the failure later — but **not a progress
metric**: control-plane status lags container events by two to three minutes, so the real
error precedes the terminal state.

| # | Change under test | Running | Died in | Signature |
|---|---|---|---|---|
| 1 | baseline, vendor-default image | — | model load | `driver too old (found version 12080)` |
| 2 | image with torch cu128 | 4m03s | model load | `Parameter.__new__() ... '_is_hf_initialized'` |
| 3 | `accelerate` upgraded | 3m03s | FSDP2 wrap | `'set' object is not subscriptable` |
| 4 | fsdp2 set guard applied | 2m13s | NCCL init | `Cuda failure 217 'peer access is not supported'` |
| 5 | `NCCL_P2P_DISABLE=1` + `NCCL_SHM_DISABLE=1` | 5m04s | vLLM init | `6.25 GiB KV cache needed, 1.96 GiB available` |
| 6 | `gpu_memory_utilization=0.6` | 6m06s | `trainer.fit()` entry | logger backend assertion |
| 7 | logger backend set to console | 6m06s | `update_weights` | `3.11GB too large for 2048 MB bucket` |
| 8 | bucket override on the **correct** config path | 9m33s | first `compute_log_prob` | `OutOfMemoryError: Tried to allocate 4.37 GiB` |
| 9 | `entropy_from_logits_with_chunking=True` | 19m31s | first `update_policy` | `SqueezeBackward1 ... modified inplace` |
| 10 | dp_actor temperature scaling out-of-place | 70m+ | — | *in progress at time of writing* |

## Two rows worth reading twice

**Rows 7 → 8 are not consecutive fixes of the same thing.** Row 7's fix was applied with
the config path printed in verl's own error message. That path does not exist, Hydra
accepted it as a new key when given a `+` prefix, and the run died on
`RolloutConfig.__init__()` — under roughly 200 lines of NCCL noise, which briefly looked
like a transport problem. Row 8 is the same numeric value written to the path the runtime
config actually uses.

**Row 4 tempts you to change two variables.** Disabling NCCL P2P is the common advice for
CUDA 217 and it is not sufficient — the shared-memory transport calls the same API. We
later removed `NCCL_SHM_DISABLE=1` on the theory that it was redundant, and 217 came back
from `shm.cc:590`. That cost one full cycle and is the clearest argument in this table for
changing exactly one variable per run.

## Progression

The useful reading of this table is not "nine failures". It is that runtime grows
monotonically once the first fix lands, and each stage reached is one the previous run
never got to:

```
model load → FSDP2 wrap → NCCL init → vLLM init → trainer.fit()
  → update_weights → compute_log_prob → update_policy → training loop
```

Row 9 is the first run to produce real evaluation metrics before failing: the reward
function scored the validation set, and rollout generation ran for 12m10s, before the
backward pass rejected the in-place view edit.
