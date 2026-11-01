# Validation: Component Precision and Resource Accounting

[中文](VALIDATION_CN.md) · [Main guide](README.md) · [Data](data/model-evidence.json)

## Scope

The executable tool reads public metadata or replays a saved snapshot and calculates tensor payload bytes. It does not run models, provision GPUs, determine production GPU counts, or generate throughput/quality scores.

Capture times are `2026-11-01T12:49:24.528Z` for model metadata and `2026-11-01T12:51:18.489Z` for original NVFP4 configuration summaries, both UTC. The data retains model IDs, pinned revisions, observed read status and scope. A checkpoint publisher and an original model developer are different identities.

## Replay and tests

Requires Node.js 20+ with no npm dependencies. Use PowerShell or Bash from this directory. Absolute script paths also work from another working directory because data is resolved relative to the module, not the current directory.

```bash
node tools/inspect.mjs
node --test tests/inspect.test.mjs
```

Successful replay emits JSON with `result_type=CALCULATED_FROM_PUBLIC_METADATA` and inference status `NOT_RUN`. `tensor_payload_bytes` sums per-dtype element counts times storage bytes. GB is decimal and GiB binary. Headers, non-tensor files, KV/state caches, runtime workspaces and communication buffers are excluded.

The eight tests cover model variants plus the nine-column bilingual matrix/local links, packed U8 accounting, the six observed payloads, retained Muse HTTP 401, Nemotron router exclusions, unknown dtypes, fresh revisions invalidating old configuration evidence, and HTTP failure without silently replaying old data. HTTP objects in tests are unit-test stubs, not live model evidence.

## Fresh metadata

```bash
node tools/inspect.mjs --live
```

This rereads the public API for the six model IDs. Check the returned capture time and revisions before comparing payloads. The refresh clears old configuration summaries because it does not re-inspect the large quantization files. HTTP errors, unknown dtypes or identity changes fail rather than masquerading as current data.

No model-download credentials are needed or expected. Muse's gated raw quantization configuration is a separate disclosed gap; do not bypass it through another account or mirror.

## Preserve source anomalies

Nemotron BF16's reported `safetensors.total` differs from the sum of its per-dtype counts. The tool reports both values and `metadata_total_matches=false`, calculates bytes from per-dtype counts and does not modify the source record. Packed `U8` elements and scale tensors in a quantized export are not the original logical parameter count.

## Model acceptance

Follow the model's own official recipe linked from the [main guide](README.md#select-a-verifiable-path-before-starting-a-service). Record weight SHA, engine commit/image digest, GPUs, parallel topology, selected kernels, cache/state dtypes, exact business requests and results. Use the same real tasks across BF16, FP8 and NVFP4; unexecuted combinations remain `NOT_RUN` rather than borrowing another model's results.

Cover required modalities, structured output, tool calls, quality, long context, target concurrency, peak VRAM and sustained operation. Loading is not business success, and low-bit storage is not native low-bit computation.

## Current status

| Check | Status and scope |
|---|---|
| Public identities and six pinned revisions | Read from the API; weights not downloaded |
| Original NVFP4 configuration | Nemotron and Inkling parsed; Muse returned 401 and was not parsed |
| File diagnostics | Editor checks executed; not evidence that Node tests passed |
| Node tests and CLI | Executed: 8 passed, 0 failed; includes current matrix/source/link assertions and six payload calculations |
| Page preview | Four pages checked at 1280/390 pixels; each matrix has 25 content rows and nine release columns, with no missing images/anchors or page-level overflow; not GitHub live-page acceptance |
| Model inference, performance and production stability | NOT_RUN |
| Independent Chinese and bilingual semantic review | PASS: read-only independent review completed; ambiguous English wording for unverified states was corrected and independently rechecked |
| GitHub publication and live pages | Refer to this project's public commit and check results; local preview does not establish live-page acceptance |

An unexecuted check cannot be labeled PASS. Public-source analysis, mechanism explanation and executable tools have separate acceptance boundaries.

Independent text review covered the four bilingual documents, component matrix and data/visual provenance summaries, with targeted source checks. It did not execute models, rerun performance tests or establish the still-unverified component precisions. `AI_NATIVE_CHINESE_AUDIT=PASS` and `AI_BILINGUAL_SEMANTIC_AUDIT=PASS` describe this text review only.

## Rebuild the document preview

Use PowerShell 7's built-in `ConvertFrom-Markdown`; no npm packages are installed. Browser-side Mermaid and KaTeX rendering requires the pinned public CDN assets in the script. From this project directory:

```powershell
./tools/preview.ps1 -OutputDirectory "$env:TEMP/large-moe-guide-preview"
```

One entry generates all four pages and records source/HTML SHA-256 values. All table columns are retained; narrow screens scroll inside the table instead of receiving selected rows. Official figure provenance, dimensions and SHA-256 are in [visual-evidence.json](data/visual-evidence.json). Local preview is not GitHub publication acceptance or independent bilingual semantic review.

## Subsequent GPU validation

Documentation and tools are completed first. BF16 validation on MI300X follows a separate environment check and is not covered by the eight tests above. Confirm the target VM, available memory, ROCm/engine version, weight access, request inputs and resource-use authorization before execution. Later measurements extend this project rather than creating a competing results page.