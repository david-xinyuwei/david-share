# Method and evidence lineage

This repo is an engineering companion to the producer's sample, not a replacement training
method. The definition of Custom Code Training and the authoritative job path belong to
[`microsoft-foundry/custom-code-training`](https://github.com/microsoft-foundry/custom-code-training).

## Authority lock

| Stage | Authority | This run | Status |
|---|---|---|---|
| Product surface | Microsoft Foundry portal and official repository | project, datasets, managed Compute, `CommandJob`, Ray distribution | **EXECUTED** |
| Submission entry | Official `Retail_Customer_Agent_verl_RFT.ipynb` | `datasets.upload_folder` → `validate()` → `create_or_update()` | **EXECUTED** |
| Training payload | Official `code/` and `data/` at commit `018d095f508280efce9e79c4b19fc941d7361b30` | retail tools, reward, JSONL adapter, verl launcher | **REUSED_INPUT** |
| Base model | AzureML registry model from the official Configure cell | Qwen3-14B version 2 | **EXECUTED** |
| Image | Official `acft-rft-training:15` plus measured pure-Python compatibility layers | [`evidence/image-build.json`](../evidence/image-build.json) | **EXECUTED_AS_LAYERS** |
| Runtime overrides | This repo, derived from one-variable failure progression | [`configs/verified-overrides.json`](../configs/verified-overrides.json) | **EXECUTED** |
| Metrics | verl console output | [`evidence/training-metrics.jsonl`](../evidence/training-metrics.jsonl) | **14 STEPS CAPTURED** |
| Final output | post-training validation and exported model | four validation passes plus registered model/checkpoint assets | **EXECUTED** |

## Frozen upstream input

The offline preflight was run against the producer's sample at the commit above. These are
the identity-critical files, not a newly authored substitute:

| Upstream path | Bytes | SHA-256 |
|---|---:|---|
| `code/verl_rft_startup.sh` | 9,563 | `6068e57909376e1e88d3c9cfad6d63a6533bfbf5c39d464d0a6e18be54ff41c6` |
| `code/reasoning_train_rft.py` | 67,272 | `ff2b99cdf537f5111aebd44aed1920d4b0f4b3ff5251a6d1dc004f6148bc4ef9` |
| `code/jsonl_dataset.py` | 3,018 | `3437e7e366904117b69f2e3516669e34955cd7746319cc181b77c6f01e3952e2` |
| `code/retail_tool.py` | 3,703 | `d0a4c0e0a36db3660eb7232df3fd78ae8302e5b404166ed4f49358f17e81ed57` |
| `code/retail_tools.py` | 27,337 | `86ca1f537f4ed4cdc928e9f57d12d4419a029bef6a91124816842e2e6c535e74` |
| `code/retail_db.json` | 24,619 | `311e84f45a03f3707c7b8fe410a338564767fa3ba8d329e980f4c52dbbba44e3` |
| `code/retail_grader_rft_tools_v3.py` | 26,079 | `a298bce3de3bcf6f9b52747c08de7130214eb506f76ec601ea9c9c94f7b05fdb` |
| `code/retail_toolcall_reward.py` | 4,709 | `86284726df54071c16188952c888c06adbb86b4125e0cc20cb267a92dee2dd82` |
| `code/config/interaction_config/interaction_config_template.yaml` | 234 | `5c701cc09823073f3708893e4b5b17ff2614a5720f84afde5b95d9464d31c3aa` |
| `code/config/tool_config/tool_config_template.yaml` | 5,444 | `8ca14526300036332bab94d39650dec00081b37703c8eeb82e4f013e98321f64` |
| `data/train.jsonl` | 863,163 | `b1329f6b419617285c9cefe93f40e7015a6534196745b3f1568ddd2ce83885a1` |
| `data/validation.jsonl` | 196,329 | `6a587a65d2d29e4e40753488d4b25fc5c85aa41a15a5f99130f3000e7f874d59` |

The datasets contain **270 train records and 62 validation records**. Every record passed the
same offline contract: `data_source`, non-empty role/content messages including a user turn,
`reward_model.ground_truth`, and object-valued `extra_info`.

## What stayed identical

- Dataset content, reward function, tool definitions and model URI.
- `${{inputs.*}}` read-only mounts and per-run-suffixed `${{outputs.*}}` mounts.
- One-node `CommandJob`, Ray port 6379, Premium SLA and autoscale count of one.
- GRPO hyperparameters in the upstream launcher: batch 128, 2,048-token prompt/response,
  three rollouts per prompt, LoRA rank 64, `kl_coef=0.01`.
- SDK path: offline `client.beta.jobs.validate(job).try_raise()` before
  `client.beta.jobs.create_or_update()`.

## What changed, and why

| Difference from the upstream Configure cell | Evidence | Effect on identity |
|---|---|---|
| NC96ads A100 v4, 4 GPUs instead of the Notebook's ND96 8-GPU default | Portal screenshots; actual topology | documented SKU binding, permitted by upstream mapping |
| image `:15` instead of `:20` | measured tag matrix in `troubleshooting.md` | **DERIVED IMAGE**; keeps product training path, changes container bytes |
| verl 0.7.1, accelerate 1.14.0 | build gates in `image-build.json` | pure-Python compatibility layers; CUDA stack unchanged |
| FSDP2 set guard and out-of-place temperature scaling | patch tests and image gates | source backports; fail-closed and idempotent |
| P2P and SHM disabled | CUDA 217 from both NCCL transports | topology adaptation for PCIe A100 under the managed hypervisor |
| vLLM fraction 0.6 | 6.25 GiB required vs 1.96 GiB available at 0.4 | memory-budget adaptation |
| 4,096 MB checkpoint-engine bucket | 3.11 GB Qwen3 embedding vs 2,048 MB default | model-shape adaptation |
| chunked actor entropy | 4.37 GiB allocation failed without it | memory adaptation; numeric definition unchanged |
| console logger | PyPI verl has no `azureml` tracking backend | removes AzureML metric logging; console remains authoritative |

Because the image and runtime are adapted, the correct claim is **an executed Foundry Custom
Code Training job using the official payload with a derived compatibility image**. It is not
an exact replay of the Notebook default image.

## Claim boundary

The captured evidence proves that the product accepted the job, mounted the assets, started
Ray, loaded Qwen3-14B, ran all 14 planned GRPO optimizer steps, completed four validation
passes and registered the model/checkpoint outputs. It does **not** prove convergence, a
quality improvement, portability to another SKU, or production readiness. The validation
series at steps 0, 5, 10 and 14 is reported rather than interpreted.
