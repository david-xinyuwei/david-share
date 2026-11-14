# LLM Inference Optimization on Azure GPU VMs

[![Hardware](https://img.shields.io/badge/Azure-ND%20MI300X%20v5-0078D4)](#purpose)
[![Runtime](https://img.shields.io/badge/SGLang-pinned%20public%20source-0078D4)](upstream/SOURCES.lock.json)
[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/llm-inference-optimization-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/llm-inference-optimization-ci.yml)

Author: Xinyu Wei — Microsoft AI Lead Senior System Engineer · [中文](README_CN.md) · [Start operating](#steps) · [How the optimizations work](docs/optimizations.md) · [Measured results](docs/results.md)

## Purpose

Deploy a pinned MiMo-V2.5-Pro serving stack on Azure MI300X VMs, understand which optimizations were actually measured, and check the GPU communication path before diagnosing serving performance. The serving path and the optional RCCL communication check are separate workloads.

| Task | Upstream building blocks | What this repository adds |
|---|---|---|
| Start inference | SGLang server, AITER and other kernels | A source-pinned build and one-VM / prefill-decode launch profiles |
| Choose an optimization | Configurable framework and kernel switches | Recorded comparisons, source changes and accuracy boundaries |
| Check interconnect access | RCCL `all_reduce_perf` | Host/container evidence and a failure-reporting benchmark route |

<img src="images/test-topology-en.png" width="800" alt="Azure MI300X prefill/decode serving arrangement, request path, KV transfer and measurement points">

The diagram is an original explanation of the recorded 1P1D arrangement, not runtime evidence. The benchmark client and its measurement points are not additional production services.

| Metric | Read it as |
|---|---|
| TTFT | Time to the first output token |
| TPOT | Time per output token; lower is better |
| Input/output tok/s | Serving throughput for the stated workload |
| RCCL busbw (GB/s) | Normalized collective bandwidth, not model throughput or measured NIC utilization |

Moby is the container-engine package; a ROCm container image supplies user-space libraries. It does not replace the VM's HPC operating system or its GPU kernel driver. The host RCCL route does not require a container.

## Steps

| Order | Where | Action | Entry |
|---|---|---|---|
| 1 | Each MI300X VM | Check GPUs, RDMA, storage and container tools | Native probes below |
| 2 | Build host, then each VM | Build once, push, pull the same digest | [Dockerfile](docker/Dockerfile) |
| 3 | One VM, or a prefill/decode pair | Render and start the serving roles | [render_launch.py](tools/render_launch.py), [run-role.sh](docker/run-role.sh) |
| 4 | Client / router host | Wait for readiness, then send a request | [wait-ready.sh](docker/wait-ready.sh) |
| 5 | Two idle GPU VMs, optional | Check host and Moby-container AllReduce | [run-rccl.sh](docker/run-rccl.sh) |

**Prerequisites.** Linux x86-64, Bash, Python 3.10+, Git, an authenticated model-download CLI, Azure CLI and Docker with BuildKit; one ND MI300X v5 VM for single-server inference, two for 1P1D or RCCL. You supply the model weights and a registry. Keep service/SSH ports private; external clients need an authenticated gateway. GPU roles require dedicated hosts because the recorded Mooncake path uses host privileges.

**1. Check each host and get the project.**

```bash
rocm-smi --showproductname
ibv_devinfo -l
show_gids
docker buildx version
git clone --filter=blob:none --depth 1 https://github.com/david-xinyuwei/david-share.git
cd david-share/Deep-Learning/LLM-Inference-Optimization-on-Azure-GPU-VMs
```

Expect eight MI300X GPUs and, for multi-node work, eight active IB devices. Confirm the valid GID for the selected device rather than copying a value from another fabric. Keep a durable copy of the weights: VM-local NVMe is temporary and can be lost on deallocation.

**2. Supply your values once.** Fill the empty values before running this block, then complete `docker/mimo.env` using the template comments and copy it to every serving host. Run the `hf download` line on every VM that runs a server, prefill or decode role, or stage the durable copy there: each of those containers mounts its own host's `$MODELS`.

```bash
export MODELS=/mnt/models
export MODEL_REPO=
export MODEL_REVISION=7208274e94787a92d7261675fb1de56ccb0e94b5
export ACR_NAME=
export REGISTRY="$ACR_NAME.azurecr.io"
cp docker/mimo.env.example docker/mimo.env
hf download "$MODEL_REPO" --revision "$MODEL_REVISION" --local-dir "$MODELS/MiMo-V2.5-Pro"
```

| Setting | Supply |
|---|---|
| `MODELS`, `MODEL_REPO` | Local weight directory and the model provider's repository; review its remote modelling code |
| `IMAGE` | The registry digest produced in step 3 |
| `PREFILL_HOST`, `DECODE_HOST` | Reachable private addresses for 1P1D |
| `IB_DEVICES`, `MC_GID_INDEX` | Devices and valid GID confirmed on your hosts; Mooncake settings, not a generic RCCL recipe |

**3. Build once and distribute the digest.**

```bash
az acr login --name "$ACR_NAME"
docker buildx build --platform linux/amd64 \
  --tag "$REGISTRY/mimo-mi300x:$(git rev-parse --short=12 HEAD)" \
  --metadata-file build-meta.json --push docker/
DIGEST=$(python3 -c 'import json; print(json.load(open("build-meta.json", encoding="utf-8"))["containerimage.digest"])')
sed -i "s|^IMAGE=.*|IMAGE=$REGISTRY/mimo-mi300x@$DIGEST|" docker/mimo.env
set -a; . docker/mimo.env; set +a
docker pull "$IMAGE"
```

Success means the build imports pass and every host pulls the same digest. Copy the completed settings file before pulling on the other host. A prior CPU build and router-wiring receipt exists; the rebuilt serving image's GPU roles and registry distribution were not exercised here. Do not read the historical throughput as a fresh deployment result.

**4. Render the route you need.** One VM:

```bash
mkdir -p run
python3 tools/render_launch.py --profile rocm-mi300x-single --role server > run/server.sh
```

For 1P1D, render the same files on both hosts:

```bash
mkdir -p run
python3 tools/render_launch.py --profile rocm-mi300x-pd --role prefill --ablate simulated-acceptance > run/prefill.sh
python3 tools/render_launch.py --profile rocm-mi300x-pd --role decode --ablate simulated-acceptance > run/decode.sh
python3 tools/render_launch.py --profile rocm-mi300x-pd --role router > run/router.sh
```

The 1P1D commands remove fixed MTP acceptance. They retain INT8 Quick Reduce from that profile; add `--ablate int8-quick-reduce` to both GPU roles when you need to disable it. FP8 KV and INT8 Quick Reduce can change outputs and require your workload's [accuracy checks](docs/benchmark.md#check-a-lossy-switch-on-your-model). All profiles, roles and `--ablate` names: [Launch profiles](docs/reference.md#launch-profiles).

**5. Start and wait.** One VM:

```bash
set -a; . docker/mimo.env; set +a
bash docker/run-role.sh server run/server.sh
bash docker/wait-ready.sh 127.0.0.1 30001 3600 mimo-server
export API_BASE=http://127.0.0.1:30001
```

For 1P1D, start prefill on VM A and decode on VM B, then wait and start the router on VM A:

```bash
set -a; . docker/mimo.env; set +a
bash docker/run-role.sh prefill run/prefill.sh                    # VM A
bash docker/run-role.sh decode run/decode.sh                      # VM B
bash docker/wait-ready.sh "$PREFILL_HOST" 30000 3600 mimo-prefill  # VM A
bash docker/wait-ready.sh "$DECODE_HOST" 30001 3600               # VM A
bash docker/run-role.sh router run/router.sh                      # VM A
export API_BASE=http://127.0.0.1:40000
```

Continue only after `READY` and a valid `/server_info` response. A named container exiting is an error, not a reason to wait indefinitely. Keep ports 30000/30001 between the VMs and port 40000 private. The first GPU start loads the weights and may compile kernels.

**6. Send a smoke request.**

```bash
curl --fail-with-body -sS "$API_BASE/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"default","messages":[{"role":"user","content":"What is 17 * 23? Reply with the number."}],"max_tokens":1024,"temperature":0}'
```

Expect `choices[0].message.content` containing `391` and `finish_reason=stop`. Both routes must show the expected kernels in native logs ([log checks](docs/deployment.md#step-6-confirm-the-optimizations-are-active)). Only the 1P1D route additionally requires Mooncake RDMA between the servers and no TCP fallback; a single-server route has no inter-server KV transfer to check.

**7. Optional: test communication without loading model weights.** On two otherwise idle VMs, copy `docker/rccl.env.example` to `docker/rccl.env`. Supply both node addresses, a dedicated absolute `RCCL_SSH_DIR` ending in `/rccl-ssh`, and the other settings. Host-to-host SSH must already be authenticated with verified host keys.

```bash
cp docker/rccl.env.example docker/rccl.env
docker buildx build --platform linux/amd64 -f docker/rccl.Dockerfile \
  --tag "$REGISTRY/rccl-mi300x:$(git rev-parse --short=12 HEAD)" \
  --metadata-file rccl-build-meta.json --push docker/
RCCL_DIGEST=$(python3 -c 'import json; print(json.load(open("rccl-build-meta.json", encoding="utf-8"))["containerimage.digest"])')
sed -i "s|^RCCL_IMAGE=.*|RCCL_IMAGE=$REGISTRY/rccl-mi300x@$RCCL_DIGEST|" docker/rccl.env
```

Copy the completed settings file to VM B. The new RCCL image recipe's source pin resolves, but this repackaged image has **not** been built or GPU-replayed here; see the [build boundary](evidence/rccl/build-status.json). The recorded results came from the earlier direct build on the same base.

```bash
bash docker/run-rccl.sh prepare-ssh                  # VM A
bash docker/run-rccl.sh start                        # each VM
RCCL_OUTPUT_DIR="$PWD/run/host-$(date -u +%s)" bash docker/run-rccl.sh host
RCCL_OUTPUT_DIR="$PWD/run/container-$(date -u +%s)" bash docker/run-rccl.sh container
RCCL_OUTPUT_DIR="$PWD/run/check-$(date -u +%s)" bash docker/run-rccl.sh check
```

Run the final three commands on VM A, one at a time. A successful run writes `output.log`, the actual command, its exit code and parsed `result.json` in a new directory. `check` additionally requires IB on every rank and GDRDMA markers, not merely a zero process exit code. The host route uses the HPC image's binary; the container route uses the separately built RCCL image, not the serving image.

**8. Stop only your processes when you choose.**

```bash
docker stop mimo-server                              # single-server route
docker stop mimo-router mimo-prefill                 # 1P1D, VM A
docker stop mimo-decode                              # 1P1D, VM B
bash docker/run-rccl.sh stop                         # optional RCCL container, each VM
```

Use only the commands for roles you started. Stopped containers retain their writable layer; removing them discards its caches. The serving restart policy handles up to three crashes, not host reboots or hung processes. Upgrade/rollback by digest requires a maintenance window unless you prepare a second serving pair. VM deallocation is a separate, explicitly authorized operator action; these scripts never perform it.

## Results

The inference comparisons below have different scopes: the 64K A/B changes two switches with two runs per arm; the MoE figures are one stage pair. Fixed MTP acceptance, FP8 KV and INT8 Quick Reduce were used in the corresponding recorded throughput runs.

<!-- BEGIN GENERATED: headline -->
| What changed | Before → after (tok/s) | Change |
|---|---|---:|
| CK FP8 GEMM + unified verify<br>64K/1K decode, batch 16, one VM<br>*A/B, two switches, N=2* | 743 → 934 | **+25.65%** |
| Tuned fused-MoE table<br>8K prefill, concurrency 4, 1P1D<br>*stage pair, N=1* | 16,716 → 20,781 | **+24.32%** |
| Tuned fused-MoE table<br>8K/1K decode, concurrency 128, 1P1D<br>*stage pair, N=1* | 2,209 → 2,487 | **+12.56%** |
<!-- END GENERATED: headline -->

The communication comparison uses the same pair of MI300X VMs, but different ROCm/RCCL software stacks. Values are busbw, not model throughput; the 16 GiB column is out-of-place.

<!-- BEGIN GENERATED: rccl-headline -->
| Route | Software | Average<br>GB/s | 16 GiB<br>GB/s |
|---|---|---:|---:|
| Host | ROCm 6.4.4<br>RCCL 2.22.3 | 354.57 | 361.31 |
| Moby container | ROCm 7.2.0<br>RCCL 2.27.7 | 359.24 | 364.28 |
<!-- END GENERATED: rccl-headline -->

Published run index (not every historical attempt; selected points for multi-point serving bundles, with full retained results in [Measured results](docs/results.md)):

<!-- BEGIN GENERATED: run-index -->
| Run | Scenario | Recorded result / scope |
|---|---|---|
| [S1](docs/results.md#moe-tuning-before-s1) | MoE tuning: before | 8K prefill: 16,715.80 input tok/s |
| [S2](docs/results.md#moe-tuning-after-s2) | MoE tuning: after | 8K prefill: 20,780.79 input tok/s |
| [S3](docs/results.md#decode-concurrency-ladder-s3) | Decode concurrency ladder | C=64: 2,198.77 output tok/s; fixed MTP 3 |
| [S4](docs/results.md#two-switch-64k-ab-s4) | Two-switch 64K A/B | +25.65%; N=2/arm |
| [S5](docs/results.md#graph-capture-ab-s5) | Graph capture A/B | 107.4 → 334.0 output tok/s |
| [S6](docs/results.md#baseline-stack-s6) | Baseline stack | C=64, 16K: TPOT 45.86 ms |
| [S7](docs/results.md#actual-mtp-acceptance-s7) | Actual MTP acceptance | C=64, 8K: TPOT 30.07 ms |
| [S8](docs/results.md#context-length-sweep-s8) | Context-length sweep | 64K, 1 request: 18,057.01 input tok/s |
| [S9](docs/results.md#prefill-replicas-s9) | Prefill replicas | 8K, 2 in flight: 41,201.86 input tok/s |
| [S10](docs/results.md#public-accuracy-subsets-s10) | Public accuracy subsets | 6 benchmark subsets; scores on the results page |
| [R1](docs/results.md#host-allreduce) | Host AllReduce | 354.57 GB/s; data check NOT_RUN |
| [R2](docs/results.md#moby-container-allreduce) | Moby container AllReduce | 359.24 GB/s; data check NOT_RUN |
| [R3](docs/results.md#container-correctness-and-transport) | Container correctness and transport | 345.307 GB/s; data check PASS |
| [R4](docs/results.md#no-ib-device-socket-fallback) | No IB device: Socket fallback | 11.3114 GB/s; data check PASS |
| [R5](docs/results.md#ib-device-mapped-ib-transport) | IB device mapped: IB transport | 335.588 GB/s; data check PASS |
| [R6](docs/results.md#one-vm-minimum-channels-112) | One VM: minimum channels 112 | 301.688 GB/s; data check PASS |
| [R7](docs/results.md#one-vm-minimum-channels-unset) | One VM: minimum channels unset | 321.714 GB/s; data check PASS |
<!-- END GENERATED: run-index -->

- `LOCAL_MEASUREMENT`: preserved observations on MI300X, not a comparison with another accelerator or proof that a newer serving image has the same performance.
- `LOCAL_MEASUREMENT`: AllReduce is a communication microbenchmark. Performance runs use `-c 0`; correctness and transport checks are separate `-c 1` runs.
- `NOT_MEASURED`: long-term stability, current serving-image GPU deployment, the repackaged RCCL image's build/start, and performance on the NVIDIA template.
- `NOT_MEASURED`: accuracy with FP8 KV enabled. Fixed MTP acceptance is not production acceptance; some historical inputs and complete raw logs are unavailable publicly.
- `SOURCE_FACT`: the container uses the host GPU kernel driver. ROCm software version strings do not establish that driver's package version.

More detail, by what you want to do:

| You want to | Read |
|---|---|
| Understand what each optimization changes, why it helps on MI300X and whether it can change output | [How the optimizations work](docs/optimizations.md) |
| Get more detail on a deployment step, confirm the optimizations are active, operate the service or diagnose a misleading failure | [Deployment details and operations](docs/deployment.md) |
| Reproduce a published point, measure one change, check a lossy switch or verify the numbers without a GPU | [Measure and verify](docs/benchmark.md) |
| Look up launch profiles and `--ablate` names, metric and log fields, the directory layout, pinned upstream commits or sources | [Reference](docs/reference.md) |
| See every run's recorded input, controlled variables, result and boundary | [Measured results](docs/results.md) |

Directories: [docs/](docs/) · [docker/](docker/) · [profiles/](profiles/) · [tools/](tools/) · [tests/](tests/) · [evidence/](evidence/) · [upstream/](upstream/) · [images/](images/).
