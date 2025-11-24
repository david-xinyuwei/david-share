# Training Performance Notes

## GPU Utilization (Training Phase)
**Date:** November 22, 2025
**Context:** Training Math Agent with Agent Lightning (vLLM backend) on Azure A10 GPU.

### Nvidia-smi Output
```
Sat Nov 22 02:09:54 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.154.05             Driver Version: 535.154.05   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA A10-24Q                 On  | 00000002:00:00.0 Off |                    0 |
| N/A   N/A    P0              N/A /  N/A |   4955MiB / 24512MiB |     12%      Default |
|                                         |                      |             Disabled |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A    130605      C   ...Dict.actor_rollout_compute_log_prob     4935MiB |
+---------------------------------------------------------------------------------------+
```

### Observations
- **Memory Usage:** ~5GB (Low for A10 24GB).
- **Utilization:** ~12% (Low).
- **Throughput:** ~15.35s/it (from logs).
