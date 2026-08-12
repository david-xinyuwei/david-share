# Reproduce the verified path

The workflow deliberately separates an offline plan, the SDK validation gate, and the
billable job submission. Nothing in `plan` contacts Azure. `validate` uploads versioned code
and data assets but does not create a job. Only `submit` requests GPU execution.

## 1. Get the producer's sample at the measured commit

```bash
git init upstream-custom-code-training
cd upstream-custom-code-training
git remote add origin https://github.com/microsoft-foundry/custom-code-training.git
git fetch --depth 1 origin 018d095f508280efce9e79c4b19fc941d7361b30
git checkout --detach FETCH_HEAD
cd ..
```

The expected sample directory is:

```text
upstream-custom-code-training/code-samples/sdk/training/rft-with-verl
```

The preflight prints bytes and SHA-256 for the six identity-critical files. Compare those
with [`method-and-lineage.md`](method-and-lineage.md) before using evidence from this repo as
a reference.

## 2. Install the pinned client

```bash
python -m venv .venv
source .venv/bin/activate            # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` pins the preview SDK and Azure Identity versions used by the verified
submission. The requirements file includes the public Azure SDK package feed.

## 3. Create a fail-closed config

```bash
cp configs/foundry-job.example.json configs/foundry-job.local.json
```

Replace every `<...>` value. The local file is ignored by Git. Important distinctions:

- `computeId` is the Foundry Compute ARM ID, not an AML compute name.
- `computeClusterSku` is the Azure SKU; the script maps it to the Singularity instance type.
- `uamiId` is the ARM ID, not the client ID.
- `environmentImage` must be pinned by tag or digest and cannot be `:latest`.
- the project identity needs `AcrPull` on the image registry and data-write access through
  `storageConnectionName`.

## 4. Offline preflight and plan

```bash
python scripts/preflight.py \
  --config configs/foundry-job.local.json \
  --overrides configs/verified-overrides.json \
  --sample-dir upstream-custom-code-training/code-samples/sdk/training/rft-with-verl \
  --write-plan run-output/preflight.json

python scripts/submit_job.py --action plan \
  --config configs/foundry-job.local.json \
  --overrides configs/verified-overrides.json \
  --sample-dir upstream-custom-code-training/code-samples/sdk/training/rft-with-verl
```

Done-when: `PREFLIGHT_PASS`, zero placeholders, 270 train and 62 validation records, six
input hashes, and a rendered `CommandJob` contract. These commands do not import the Azure
SDK or touch cloud state.

## 5. Build the compatibility image

The Docker build context is the root of this repo:

```bash
az acr build \
  --registry <your-registry-name> \
  --image verl-rft:cu128-verified \
  --file docker/Dockerfile \
  .
```

The Dockerfile pins the versions shown in [`evidence/image-build.json`](../evidence/image-build.json),
runs the transformers/accelerate probe, applies both patches, reads them back, and checks
that torch was compiled for CUDA 12.8. The final `torch.cuda.is_available()` gate must run
on the real Foundry node; an ACR build worker has no GPU.

## 6. Run the SDK validation gate

Authenticate in the owning shell first. The official Notebook uses
`DefaultAzureCredential`; `--credential azure-cli` is available when an isolated Azure CLI
profile is the explicit owner.

```bash
python scripts/submit_job.py --action validate \
  --config configs/foundry-job.local.json \
  --overrides configs/verified-overrides.json \
  --sample-dir upstream-custom-code-training/code-samples/sdk/training/rft-with-verl \
  --evidence run-output/validate.json
```

This uploads versioned code/data assets, then calls
`client.beta.jobs.validate(job).try_raise()`. It does **not** submit a job, but the dataset
uploads are real side effects.

## 7. Submit one job

```bash
python scripts/submit_job.py --action submit \
  --config configs/foundry-job.local.json \
  --overrides configs/verified-overrides.json \
  --sample-dir upstream-custom-code-training/code-samples/sdk/training/rft-with-verl \
  --evidence run-output/submission.json
```

The result prints the job name and portal URL. Monitor without opening a blocking stream:

```bash
python scripts/job_status.py \
  --config configs/foundry-job.local.json \
  --job-name <job-name>
```

Do not use `client.beta.jobs.stream()` as a status probe: it is a foreground log stream and
correctly waits while the job is running.

## 8. Extract metrics after the console log is available

```bash
python tools/extract_training_evidence.py \
  --log <captured-console-log> \
  --out run-output/metrics

python tools/make_steps_table.py \
  --metrics run-output/metrics/training-metrics.jsonl
```

The extractor handles UTF-16LE PowerShell captures and carriage-return-delimited tqdm
frames. It redacts run IDs, registry coordinates and IPs without modifying numeric values.
Use a new evidence directory for your run; do not overwrite the measured files committed in
this repo.
