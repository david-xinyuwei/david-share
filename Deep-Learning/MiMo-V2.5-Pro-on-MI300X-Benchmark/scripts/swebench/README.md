# SWE-bench accuracy bundle

Executable assets behind the two 499-case SWE-bench Verified runs recorded in
[`data/swebench/summary.json`](../../data/swebench/summary.json). Files copied from the
runtime bundle delivered to the customer on 2026-08-10 are byte-identical to that bundle;
repository-authored files are marked.

| Path | Origin | Role |
|---|---|---|
| `runtime-recipe/Dockerfile` | delivered bundle | Rebuilds the serving image on top of the digest-pinned `rocm/sgl-dev` base; copies the SGLang fork, AITER fork, prebuilt AITER JIT objects and the AMD script set |
| `runtime-recipe/docker-run.sh` | delivered bundle | Starts the container with the host configuration used by both runs (`--privileged`, `/dev/mem`, `CAP_SYS_ADMIN`) |
| `runtime-recipe/STACK.txt` | delivered bundle | Exact commits: SGLang `878fff156`, AITER `3f4ab482a`, composable_kernel `af7118e34` + `ck_tile.patch`, FlyDSL `0.2.4`, `mimo-flydsl-kernels 0.1.0+c99d5cd` |
| `runtime-recipe/ck_tile.patch` | delivered bundle | Adds the `page_size=64` / `head_dim=192` `fmha_batch_prefill` tile so MiMo's 192/128 head dims do not need V padding |
| `launch_tp8_noep_aiter_mtp_accuracy.sh` | delivered bundle (AMD, sealed 2026-07-29) | Single-node TP8 server with real MTP acceptance: AITER, FP8 E4M3 KV, `vectorized_5d`, FlyDSL PA with 16 partitions, EAGLE 3 steps / top-k 1 / 4 draft tokens, page 64 |
| `launch_mtp_nongreedy_wrapper.sh` | delivered bundle | Exports `SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1`, `ROCM_QUICK_REDUCE_QUANTIZATION=NONE`, `SGLANG_SCHEDULER_SKIP_ALL_GATHER=1`, `SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION=0`, `MEM_FRACTION_STATIC=0.95`, then execs the AMD launcher — this is the **MTP on** run |
| `launch_tp8_no_mtp_accuracy.sh` | repository (sanitized copy of the launcher that served the run) | Same stack with every `--speculative-*` flag removed — this is the **MTP off** run; only the node-name check and fixed log path became variables |
| `verify_runtime_contract.py` | repository | Fail-closed check of `/v1/models`, the server process command line and its environment before the harness is started |

Not distributed here: model weights, the private FlyDSL wheels (`flydsl-0.2.4-cp310-cp310-manylinux_2_27_x86_64.whl`,
`mimo_flydsl_kernels-0.1.0+c99d5cd-py3-none-any.whl`), the prebuilt AITER JIT tree and the
customer's mini-swe-agent image. The Dockerfile expects them under `runtime/` and
`decode_server_scripts/` next to it, exactly as in the delivered bundle.

Verify the copies:

```bash
cd scripts/swebench
sha256sum -c SHA256SUMS.txt
bash -n launch_tp8_no_mtp_accuracy.sh launch_mtp_nongreedy_wrapper.sh launch_tp8_noep_aiter_mtp_accuracy.sh runtime-recipe/docker-run.sh
python3 verify_runtime_contract.py --help
```
