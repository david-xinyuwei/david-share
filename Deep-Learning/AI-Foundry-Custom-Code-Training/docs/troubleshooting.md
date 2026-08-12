# Troubleshooting

Seven failures stand between a clean environment and a running GRPO loop on this hardware.
They are listed in the order they fire — fixing one reveals the next, so working top-down
is the fastest path.

Environment for every observation: 4× A100 80GB **PCIe** (no NVLink), driver `570.195.03`,
max CUDA 12.8, `verl 0.7.1`, `transformers 5.8.1`, `torch 2.10+cu128`, `NCCL 2.27.5`,
`Qwen/Qwen3-14B` (vocab 151936, hidden 5120, intermediate 17408), LoRA rank 64, gradient
checkpointing enabled, `entropy_coeff=0`.

## Quick index

| Symptom you see | Jump to |
|---|---|
| `Parameter.__new__() ... '_is_hf_initialized'` | [1](#1-accelerate-forwards-a-transformers-v5-kwarg) |
| `'set' object is not subscriptable` | [2](#2-_no_split_modules-became-a-set) |
| `Cuda failure 217 'peer access is not supported'` | [3](#3-both-nccl-p2p-and-shm-call-peer-access) |
| `KV cache is needed, but only ... available` | [4](#4-vllm-has-no-room-left-for-its-kv-cache) |
| `too large for the 2048 MB bucket` | [5](#5-the-weight-transfer-bucket) |
| `OutOfMemoryError` inside `entropy_from_logits` | [6](#6-entropy-is-computed-even-when-its-coefficient-is-zero) |
| `SqueezeBackward1 is a view and is being modified inplace` | [7](#7-in-place-temperature-scaling) |

---

## 1. accelerate forwards a transformers v5 kwarg

```
TypeError: Parameter.__new__() got an unexpected keyword argument '_is_hf_initialized'
```

transformers v5 tags parameters with `_is_hf_initialized`. The `accelerate` release paired
with it passed that tag through to `torch.nn.Parameter`, which does not accept it. The run
died after materialising 97 of 443 weights, so the traceback arrives well after model
construction starts and reads like a torch problem.

```bash
pip install --no-deps -U accelerate
```

`--no-deps` keeps pip from resolving a different torch or transformers underneath a working
CUDA build.

## 2. `_no_split_modules` became a set

```
TypeError: 'set' object is not subscriptable
  verl/utils/fsdp_utils.py, in apply_fsdp2
```

transformers v5 changed `_no_split_modules` from a list to a set. verl indexes element
`[0]` while choosing which transformer layer class to wrap for FSDP2.

[`patches/01-fsdp2-set-guard`](../patches/01-fsdp2-set-guard) coerces it to a list first,
matching upstream verl's own fix. It refuses to write unless exactly one anchor matches.

## 3. Both NCCL P2P and SHM call peer access

```
transport/shm.cc:590 NCCL WARN Cuda failure 217
  'peer access is not supported between these two devices'
```

On PCIe A100s under a hypervisor, `cudaDeviceEnablePeerAccess` fails. Disabling P2P is the
usual advice and it is **not sufficient**: NCCL 2.27.5's shared-memory transport calls the
same API from `shm.cc:590`, so the identical 217 returns through a different file. Setting
`NCCL_SHM_USE_CUDA_MEMCPY=0` does not avoid it.

```bash
export NCCL_P2P_DISABLE=1
export NCCL_SHM_DISABLE=1
export NCCL_DEBUG=INFO
```

Keep `NCCL_DEBUG=INFO`. It prints the transport actually selected, and the file name in the
warning — `shm.cc` versus `net_socket.cc` — is what lets you attribute a later failure
instead of guessing.

> We once removed `NCCL_SHM_DISABLE=1` on the theory that only P2P touched peer access. The
> next run reproduced 217 from `shm.cc:590`. Change one variable at a time; "this setting
> looks redundant" is not a hypothesis worth spending a GPU cycle on mid-investigation.

## 4. vLLM has no room left for its KV cache

```
ValueError: ... 6.25 GiB KV cache is needed, but only 1.96 GiB is available
```

The 14B weights load into each GPU before the KV cache is sized. At a low
`gpu_memory_utilization` the remainder cannot hold the cache the configured sequence length
requires.

```
actor_rollout_ref.rollout.gpu_memory_utilization=0.6
```

**This trade is not free.** vLLM and the FSDP actor share the same 80 GB — raising vLLM's
share to 0.6 leaves roughly 31 GB for the actor, which is what surfaces issue 6 below.
Treat the two as one budget. The full breakdown is in the
[main README](../README.md#the-memory-budget).

## 5. The weight-transfer bucket

```
Weight model.embed_tokens.weight(151936, 5120) fp32 = 3.11GB
  is too large for the 2048 MB bucket.
  Please increase rollout.update_weights_bucket_megabytes
```

`151936 × 5120 × 4 B ≈ 3.11 GB` against a 2048 MB default. Any wide-vocabulary model hits
this.

**The path in the message does not exist.** The key lives one level deeper:

```
actor_rollout_ref.rollout.checkpoint_engine.update_weights_bucket_megabytes=4096
```

Passing the printed path makes Hydra suggest *"To append to your config use
`+actor_rollout_ref.rollout.update_weights_bucket_megabytes=...`"*. Taking that suggestion
creates a **legal new key that no dataclass reads**: composition succeeds, the run starts,
and dies about two minutes later with

```
TypeError: RolloutConfig.__init__() got an unexpected keyword argument
           'update_weights_bucket_megabytes'
```

by which point Ray's workers are gone and NCCL has written roughly 200 lines of
`NET/Socket : unable to allocate requests` on top. Those transport errors are a
*consequence* of the workers dying, but they are the loudest thing in the file.

[`tools/inspect_config_path.ps1`](../tools/inspect_config_path.ps1) reconstructs the true
dotted path from the runtime config dump, so the error string never has to be trusted.

## 6. Entropy is computed even when its coefficient is zero

```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 4.37 GiB
  verl/utils/torch_functional.py, in entropy_from_logits
    entropy = torch.logsumexp(logits, dim=-1) - torch.sum(pd * logits, dim=-1)
```

`entropy_from_logits` materialises a `[tokens, vocab]` tensor. At vocab 151936 and roughly
7 700 packed tokens that is 4.37 GiB in fp32, against the ~3.9 GiB left after vLLM's
reservation. verl ships a chunked implementation for exactly this, off by default.

```
actor_rollout_ref.actor.entropy_from_logits_with_chunking=True
```

The key also exists under `ref` and `critic.model.fsdp_config`. The traceback arrives
through `fsdp_workers.compute_log_prob → self.actor.compute_log_prob`, so the **actor** copy
is the one that matters.

Worth noting: this configuration sets `entropy_coeff=0`, so the tensor is built to compute
a term that is then multiplied by zero.

## 7. In-place temperature scaling

```
RuntimeError: Output 0 of SqueezeBackward1 is a view and is being modified inplace.
  This view was created inside a custom Function ... This behavior is forbidden.
  You can fix this by cloning the output of the custom Function.
    verl/workers/actor/dp_actor.py, in _forward_micro_batch
      logits_rmpad.div_(temperature)
```

`logits.squeeze(0)` returns a view; `.div_()` edits it in place. Two callers reach this
line:

| Caller | Autograd | Result |
|---|---|---|
| `compute_log_prob` | inside `torch.no_grad()` | fine — no view tracking |
| `update_policy` | enabled | **rejected** |

With gradient checkpointing on, the logits come out of a custom autograd `Function`.
Editing its output in place would override the custom backward and silently produce wrong
gradients, so PyTorch raises instead of miscomputing.

Because `compute_log_prob` runs first and succeeds, this only appears once everything else
is fixed and the first optimizer step is reached — which is why it is last on this list.

[`patches/02-dp-actor-out-of-place`](../patches/02-dp-actor-out-of-place) rewrites each
statement to `x = x.div(temperature)`: numerically identical, allocates instead of aliasing.
It aborts if any occurrence is not a standalone statement.

---

## Reading the logs

Two habits, both learned by getting them wrong:

**The loudest error is usually the last one.** Issue 5's real cause is a one-line
`TypeError` buried under ~200 NCCL warnings from workers that had already died. Sorting by
frequency finds the symptom; sorting by call stack finds the cause.

**Elapsed time is not progress.** Control-plane job status lags container events by two to
three minutes. Two runs that both "failed at about three minutes" failed for entirely
different reasons.

[`tools/scan_job_log.ps1`](../tools/scan_job_log.ps1) collapses consecutive repeats so the
first real exception is visible without paging through several MB.
