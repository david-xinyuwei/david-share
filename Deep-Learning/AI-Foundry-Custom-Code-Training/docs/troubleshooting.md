# Compatibility guide for the tested NC96ads A100 topology

This guide records the image, dependency, memory and interconnect choices used to run the
VERL sample on one managed NC96ads A100 v4 node. The observations are specific to the dated
stack below; other Foundry GPU families and newer curated images should be validated against
their own driver and package versions.

Environment for every observation: 4× A100 80GB **PCIe** (no NVLink), driver `570.195.03`,
max CUDA 12.8, `verl 0.7.1`, `transformers 5.8.1`, `torch 2.10+cu128`, `NCCL 2.27.5`,
`Qwen/Qwen3-14B` (vocab 151936, hidden 5120, intermediate 17408), LoRA rank 64, gradient
checkpointing enabled, `entropy_coeff=0`.

## Quick index

| Symptom you see | Jump to |
|---|---|
| `CUDA driver too old (found version 12080)` | [image matrix](#first-pick-an-image-whose-cuda-matches-the-node) |
| `Parameter.__new__() ... '_is_hf_initialized'` | [1](#1-align-accelerate-with-transformers-v5-parameter-metadata) |
| `'set' object is not subscriptable` | [2](#2-_no_split_modules-became-a-set) |
| `Cuda failure 217 'peer access is not supported'` | [3](#3-both-nccl-p2p-and-shm-call-peer-access) |
| `KV cache is needed, but only ... available` | [4](#4-vllm-has-no-room-left-for-its-kv-cache) |
| `too large for the 2048 MB bucket` | [5](#5-the-weight-transfer-bucket) |
| `OutOfMemoryError` inside `entropy_from_logits` | [6](#6-entropy-is-computed-even-when-its-coefficient-is-zero) |
| `SqueezeBackward1 is a view and is being modified inplace` | [7](#7-in-place-temperature-scaling) |

---

## First: pick an image whose CUDA matches the node

This one sits before the numbered list because it decides whether the container starts at
all. Five published tags, tested on the same compute, same driver, same day:

| Image | torch | compiled CUDA | `cuda_is_available` | Outcome |
|---|---|---|---|---|
| `acft-rft-training:20` *(template default at the measured commit)* | 2.11.0+cu130 | 13.0 | **false** | CUDA 13.0 requires a newer driver than the tested node exposes |
| `acft-rft-training:18` | 2.11.0+cu130 | 13.0 | **false** | Same driver/runtime boundary as `:20` |
| `acft-rft-training:19` | — | — | — | Startup import compatibility check stops with `ValueError: Either a revision or a version must be specified.` |
| `acft-rft-training:23` | — | — | — | Probe produced platform compute metadata but no user-process log |
| `acft-rft-training:15` | 2.10.0+cu128 | 12.8 | **true** | CUDA is available; verl/transformers versions require alignment |
| `acft-hf-nlp-gpu:122` *(SFT reference)* | 2.8.0+cu126 | 12.6 | **true** | included to show the node itself is healthy |

The node's driver is `570.195.03`, which supports CUDA up to **12.8**. A torch built against
CUDA 13.0 loads and then reports no usable device, and the traceback arrives from four
worker processes at once rather than from the loader. Reading the compiled-CUDA value first
separates this version boundary from a distributed-runtime issue.

`:15` is the tested tag whose CUDA matches, and it pairs verl 0.7.0 with transformers 5.8.1.
verl 0.7.0 still imports `AutoModelForVision2Seq`, which transformers v5 removed. The
validated combination therefore keeps the CUDA 12.8 base and aligns the pure-Python verl
package without replacing torch or vLLM.

The validated combination keeps `:15`'s CUDA stack and replaces only verl, which ships as
a pure Python wheel:

```dockerfile
FROM mcr.microsoft.com/azureml/curated/acft-rft-training:15@sha256:38f3766a5056d43a0be699986ad3613cec0d247405455046346c2051d62f65ac
RUN pip install --no-deps --no-cache-dir verl==0.7.1
```

`--no-deps` is what makes this safe: without it pip resolves a different torch underneath a
working CUDA build. Verify on the node rather than at build time — a build host has no GPU,
so `cuda_is_available` there tells you nothing:

```python
import torch
print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.device_count())
```

Everything below assumes that image.

---

## 1. Align accelerate with transformers v5 parameter metadata

```
TypeError: Parameter.__new__() got an unexpected keyword argument '_is_hf_initialized'
```

transformers v5 tags parameters with `_is_hf_initialized`. The `accelerate` release paired
with it passed that tag through to `torch.nn.Parameter`, which does not accept it. Model
initialization stopped after materialising 97 of 443 weights, so the traceback arrives well
after construction starts.

```bash
pip install --no-deps accelerate==1.14.0
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

> A single-variable probe without `NCCL_SHM_DISABLE=1` reproduced error 217 from
> `shm.cc:590`, confirming that both settings are required on the tested topology.

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
share to 0.6 leaves roughly 31 GB for the actor, which exposes the memory constraint in
section 6 below.
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

In the measured package version, the runtime config resolves this key one level deeper than
the short path shown in the message:

```
actor_rollout_ref.rollout.checkpoint_engine.update_weights_bucket_megabytes=4096
```

Passing the printed path makes Hydra suggest *"To append to your config use
`+actor_rollout_ref.rollout.update_weights_bucket_megabytes=...`"*. Taking that suggestion
creates a **legal new key that no dataclass reads**: composition succeeds, the run starts,
and configuration binding stops about two minutes later with

```
TypeError: RolloutConfig.__init__() got an unexpected keyword argument
           'update_weights_bucket_megabytes'
```

by which point Ray's workers have exited and NCCL has written roughly 200 lines of
`NET/Socket : unable to allocate requests` on top. Those transport errors are downstream
effects rather than the initiating exception.

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

Two diagnostic practices made the multi-process logs easier to interpret:

**The loudest error is usually the last one.** Issue 5's real cause is a one-line
`TypeError` buried under ~200 NCCL warnings from workers that had already died. Sorting by
frequency finds the symptom; sorting by call stack finds the cause.

**Elapsed time is not progress.** Control-plane job status lags container events by two to
three minutes. Two runs that both "failed at about three minutes" failed for entirely
different reasons.

[`tools/scan_job_log.ps1`](../tools/scan_job_log.ps1) collapses consecutive repeats so the
first real exception is visible without paging through several MB.
