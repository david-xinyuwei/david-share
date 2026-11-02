#!/usr/bin/env python3
"""16-rank (2 nodes x 8 GPUs) RCCL all_reduce through torch.distributed, launched by torchrun from 07_rccl_probe.sh.

Prints one line from rank 0:
  RCCL_PROBE_OK=<bool> world=16 init_s=<s> first_allreduce_s=<s> avg_allreduce_ms=<ms> bytes=67108864 busbw_GBps=<x> nccl=(2, 30, 7)
OK means every rank's 64 MiB tensor of ones reduced to world**6 after six all_reduce calls, i.e. all 16 ranks took part.
busbw uses the ring formula 2*(n-1)/n * bytes / time.
"""
import datetime
import os
import time

import torch
import torch.distributed as dist

rank = int(os.environ["RANK"])
world = int(os.environ["WORLD_SIZE"])
local = int(os.environ["LOCAL_RANK"])
torch.cuda.set_device(local)

t0 = time.time()
dist.init_process_group("nccl", timeout=datetime.timedelta(seconds=240))
t1 = time.time()
x = torch.ones(64 * 1024 * 1024 // 4, device="cuda")  # 64 MiB of float32
dist.all_reduce(x)
torch.cuda.synchronize()
t2 = time.time()
for _ in range(5):
    dist.all_reduce(x)
torch.cuda.synchronize()
t3 = time.time()
ok = float(x[0].item()) == float(world) ** 6
if rank == 0:
    avg = (t3 - t2) / 5
    print(
        f"RCCL_PROBE_OK={ok} world={world} init_s={t1 - t0:.1f} first_allreduce_s={t2 - t1:.2f} "
        f"avg_allreduce_ms={avg * 1000:.1f} bytes=67108864 "
        f"busbw_GBps={(2 * (world - 1) / world * 67108864) / avg / 1e9:.1f} nccl={torch.cuda.nccl.version()}",
        flush=True,
    )
dist.barrier()
dist.destroy_process_group()
