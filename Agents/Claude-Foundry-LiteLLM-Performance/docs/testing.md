# Testing and Reproduction

[README](../README.md) · [Results](results.md) · [中文](testing_CN.md)

This page gives the complete commands for the offline checks, for repeating the 2026-10-26 tests and for repeating the 2026-10-24 gateway test. Deploying the three models and sending the first request are README steps 1 to 4.

## Offline checks

No Azure access or model key. Python 3.12 or 3.13 from this directory; the stream-parser tests also need the client packages.

```bash
python -m pip install -r coding-matrix/requirements.txt
python -B coding-matrix/analyze.py --run-dir evidence/coding-matrix-20261026/matrix --check
python -B coding-matrix/cache_analyze.py --run-dir evidence/coding-matrix-20261026/cache --check
python -B scripts/analyze.py --check
python -B scripts/render_docs.py --check
python -B -m unittest discover -s tests -v
```

Done when every command exits 0, each check prints `"status": "PASS"` and the tests end with `OK`.

- **`coding-matrix/analyze.py --check`** recomputes every cell, the per-problem and per-language counts and the bootstrap intervals from the 2026-10-26 run records and fails if `facts.json` differs.
- **`coding-matrix/cache_analyze.py --check`** does the same for the cache test and `cache_facts.json`.
- **`scripts/analyze.py --check`** verifies the 2026-10-24 gateway records: hashes, the outbound log of every request, history, token accounting and timing order.
- **`scripts/render_docs.py --check`** fails if a README, results or testing page or a figure differs from a fresh render of the evidence.
- **The tests** also check the export manifest hashes, the problem list against the measured prompts, the scorer's file extraction, the stream parser against a local test server (complete, truncated, HTTP 429 and `max_tokens` streams), that a tampered run record makes the check fail, that no private name or address is published, and the gateway collector with PowerShell 7 when it is installed. The local server tests the parser only; it is not evidence about Foundry.

CI runs the same on Ubuntu and Windows with Python 3.12 and 3.13 ([workflow](https://github.com/david-xinyuwei/david-share/blob/master/.github/workflows/claude-foundry-performance-ci.yml)).

## Repeat the 2026-10-26 tests

**Before you start.** Finish README steps 1 to 4. These runs cost money: at list prices our matrix cost $55.36, the cache test $6.70 and the probe $0.05. `--budget-usd` stops the matrix at a limit (default 150). The client paces itself to Opus 40,000 and Sonnet and Haiku 80,000 tokens per minute (`TPM` in `bench.py` and `cache_test.py`); change those values if your capacities differ. Run everything on the VM, in `coding-matrix/`.

**1. Prepare the VM and build the judge image.** `vm_setup.sh` installs Docker and the client packages and clones the problems; the Java warm-up exercise lets Gradle run offline inside the image.

```bash
cd ~/david-share/Agents/Claude-Foundry-LiteLLM-Performance/coding-matrix
bash vm_setup.sh
git -C ~/polyglot-benchmark checkout 7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f
cp -r ~/polyglot-benchmark/java/exercises/practice/affine-cipher judge/java-warmup
sudo docker build -t polyglot-judge:1 judge
export FOUNDRY_ANTHROPIC_BASE="https://<foundry-resource>.services.ai.azure.com/anthropic"
```

Success: `vm_setup.sh` prints the httpx and azure-identity versions and the number of exercises per language, and the build ends with the versions of Python, Go, Rust, Node, Java and CMake. Sign out and back in once so that your user can run `docker` without `sudo`; the judge needs it.

**2. Probe the accepted values.** About 102 requests.

```bash
~/venv/bin/python probe.py --out-dir runs/probe
```

Success: `runs/probe/probe_summary.json` lists the accepted modes and efforts; compare it with [ours](../evidence/coding-matrix-20261026/probe/probe_summary.json). A different list means the deployments behave differently from 2026-10-26; the matrix will follow your list.

**3. Rebuild the measured problems.**

```bash
~/venv/bin/python prepare.py --ids ../data/coding-problems.json --out problems.json
```

Success: 18 `ACCEPT` lines. It stops if a rebuilt prompt differs from the measured one, or if a reference solution fails or an unedited stub passes in the judge.

**4. Run the matrix and the judge.** Both run in the background; the judge scores answers as they arrive.

```bash
RUN=runs/matrix-$(date -u +%Y%m%d-%H%M%S)
mkdir -p "$RUN"
nohup ~/venv/bin/python bench.py --run-dir "$RUN" --problems problems.json \
  --probe-summary runs/probe/probe_summary.json --repeats 3 --max-tokens 128000 --budget-usd 150 \
  > "$RUN/bench.log" 2>&1 &
nohup ~/venv/bin/python judge.py --run-dir "$RUN" --problems problems.json --workers 2 --watch \
  > "$RUN/judge.log" 2>&1 &
tail -F "$RUN/progress.log"
```

Success: one `progress.log` line per request and `"status": "COMPLETED"` in `$RUN/run.json` at the end; ours took about five hours. `bench.py` exits at once if the median TCP connect time to the endpoint is 50 ms or more, because the client would not be in the models' region. To stop, end both processes (`pkill -f bench.py; pkill -f judge.py`); running the same two commands with the same `RUN` resumes and skips finished requests.

**5. Analyse the run.**

```bash
~/venv/bin/python analyze.py --run-dir "$RUN"
```

Success: a 21-row table and `$RUN/facts.json` with the same fields as [ours](../evidence/coding-matrix-20261026/matrix/facts.json). Answers are not deterministic and latency changes with load, so expect different numbers; compare them with our intervals rather than single values.

**6. Run the prompt-cache test.** Start it after the matrix, or add `--wait-run-dir "$RUN"` to let each model start when its matrix requests are done. The idle scenarios wait 6.5 minutes.

```bash
CACHE=runs/cache-$(date -u +%Y%m%d-%H%M%S)
HTTPX_DIR=$(~/venv/bin/python -c "import httpx, os; print(os.path.dirname(httpx.__file__))")
~/venv/bin/python cache_test.py --out-dir "$CACHE" --package-dir "$HTTPX_DIR" --repetitions 2
~/venv/bin/python cache_analyze.py --run-dir "$CACHE"
```

Success: `cache_analyze.py` prints one line per scenario and turn, and `$CACHE/context.json` has the same `context_sha256` as [ours](../evidence/coding-matrix-20261026/cache/context.json) when httpx is 0.28.1.

**What these steps cannot reproduce exactly.** The answers, and therefore pass counts, vary between runs; latency depends on time and load; GlobalStandard deployments may route requests differently. The public scripts differ from the measured ones only as listed in [provenance.json](../evidence/coding-matrix-20261026/provenance.json): `bench.py`, `probe.py`, `cache_test.py` and the judge image files are byte-identical.

## Repeat the 2026-10-24 gateway test

These steps deploy LiteLLM on a new Container App and send the ten-configuration conversation through it. Choose the Foundry resource's region for the Container App: the 2026-10-24 run used Japan East, so its times include a cross-region round trip. Commands run in PowerShell 7.6.

| Order | Where | Action |
|---|---|---|
| 1 | Client and Foundry | Settings, sign-in and three deployments |
| 2 | Azure CLI | Build image and infrastructure |
| 3 | CLI and Portal | Identity, secret, image and ingress |
| 4 | Portal and client | Revision and metadata readiness |
| 5 | Two client terminals | Capture logs and run matrix |
| 6 | Client | Audit the new run and read its report |

This path uses a dedicated new Container App, ACR and environment; do not apply creation or shutdown steps to shared production resources. Use PowerShell 7.6, Python 3.13 and Azure CLI, with permission to create resources, run ACR Tasks, assign scoped roles and read logs. The subscription owner confirms model access and Marketplace terms. Resources, builds, logs and model calls can incur charges; approve the budget first.

**1. Set the context and deploy models**

First select an existing resource in the Foundry portal, or have an authorized user create one and record its tenant, subscription, resource group, resource name and /anthropic base URL. Then start PowerShell in this project directory. Enter non-secret settings once; other terminals load private/settings.json. Sign in interactively on this machine; do not copy token caches.

```powershell
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
if ($PSVersionTable.PSVersion -lt [version]'7.6') { throw 'Use PowerShell 7.6 or later' }
$projectRoot = (Get-Location).ProviderPath
$private = Join-Path $projectRoot 'private'
[void][IO.Directory]::CreateDirectory($private)
$settings = @{
    tenant = Read-Host 'Tenant ID'
    subscription = Read-Host 'Subscription ID'
    group = Read-Host 'Dedicated resource group name'
    location = Read-Host 'Container Apps region'
    app = Read-Host 'New Container App name'
    environment = Read-Host 'New Container Apps environment name'
    registry = Read-Host 'New globally unique ACR name'
    foundryGroup = Read-Host 'Foundry resource group'
    foundry = Read-Host 'Foundry resource name'
    baseUrl = Read-Host 'Foundry base URL ending in /anthropic'
    clientCidr = Read-Host 'Test client public IPv4 address with /32'
}
$settings | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $private 'settings.json') -Encoding utf8
$env:AZURE_CONFIG_DIR = Join-Path $private 'azure-cli'
az login --tenant $settings.tenant --output none
az account set --subscription $settings.subscription
$account = az account show --output json | ConvertFrom-Json
if ($account.id -ne $settings.subscription -or $account.tenantId -ne $settings.tenant) {
    throw 'Unexpected Azure context'
}
az cognitiveservices account show --resource-group $settings.foundryGroup `
    --name $settings.foundry --query '{name:name,location:location}' --output table
```

Success displays the selected Foundry resource. If no resource exists, create one in the Foundry portal in the required region. In **Discover → Models**, select Opus 5.5, Sonnet 5.5 and Haiku 5.5 in turn, then **Deploy → Custom settings**; the user accepts Marketplace terms for the first deployment. Select **Global** and version 2 labeled **Hosted on Azure**, using deployment names claude-opus-5-5, claude-sonnet-5-5 and claude-haiku-5-5. Allocate only approved quota. After all three complete, verify names, versions and Target URI in **Build → Models → Details**; baseUrl ends at /anthropic. Stop here if access or quota is unavailable; do not substitute models.

[Foundry provisioning and authentication](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#provisioning)

**2. Build a pinned image**

```powershell
$deployments = @(az cognitiveservices account deployment list `
    --resource-group $settings.foundryGroup --name $settings.foundry --output json | ConvertFrom-Json)
foreach ($model in @('claude-opus-5-5','claude-sonnet-5-5','claude-haiku-5-5')) {
    $match = @($deployments | Where-Object { $_.name -eq $model })
    if ($match.Count -ne 1 -or $match[0].properties.provisioningState -ne 'Succeeded' -or
        $match[0].properties.model.name -ne $model -or $match[0].properties.model.version -ne '2' -or
        $match[0].properties.model.format -ne 'Anthropic' -or $match[0].sku.name -ne 'GlobalStandard') {
        throw "Deployment contract mismatch: $model"
    }
}
az group create --name $settings.group --location $settings.location --output none
az acr create --name $settings.registry --resource-group $settings.group `
    --location $settings.location --sku Basic --admin-enabled false --output none
az containerapp env create --name $settings.environment --resource-group $settings.group `
    --location $settings.location --output none
$tag = 'claude-gateway:' + (Get-Date -Format 'yyyyMMdd-HHmmss')
az acr build --registry $settings.registry --image $tag --file deploy/Dockerfile deploy
$digest = az acr repository show --name $settings.registry --image $tag --query digest --output tsv
$server = az acr show --name $settings.registry --query loginServer --output tsv
if ($digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Image digest missing' }
$image = "$server/claude-gateway@$digest"
```

Success is a completed ACR Tasks build and an image address with a SHA-256 digest. The LiteLLM base image in the Dockerfile is pinned. This public package has not yet been built and deployed from scratch.

**3. Configure identity, secret and ingress**

Following Microsoft's system-assigned identity flow, first create a temporary revision from the public quickstart image with no external ingress, then configure the real gateway. This image only bootstraps identity; it is not model serving or measurement. Resolve its digest before use.

```powershell
$manifest = Invoke-WebRequest -Method Head `
    -Uri 'https://mcr.microsoft.com/v2/k8se/quickstart/manifests/latest' `
    -Headers @{Accept='application/vnd.docker.distribution.manifest.v2+json'} -TimeoutSec 15
$bootstrapDigest = @($manifest.Headers['Docker-Content-Digest'])[0]
if ($bootstrapDigest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Bootstrap digest missing' }
az containerapp create --name $settings.app --resource-group $settings.group `
    --environment $settings.environment --system-assigned --revisions-mode single `
    --image "mcr.microsoft.com/k8se/quickstart@$bootstrapDigest" `
    --cpu 0.25 --memory 0.5Gi --min-replicas 0 --max-replicas 1 --output none
$principal = az containerapp identity show --name $settings.app `
    --resource-group $settings.group --query principalId --output tsv
$registryId = az acr show --name $settings.registry --query id --output tsv
$foundryId = az cognitiveservices account show --name $settings.foundry `
    --resource-group $settings.foundryGroup --query id --output tsv
az role assignment create --assignee-object-id $principal --assignee-principal-type ServicePrincipal `
    --role AcrPull --scope $registryId --output none
az role assignment create --assignee-object-id $principal --assignee-principal-type ServicePrincipal `
    --role 'Cognitive Services User' --scope $foundryId --output none
az acr config authentication-as-arm update --registry $settings.registry --status enabled --output none
az containerapp registry set --name $settings.app --resource-group $settings.group `
    --server $server --identity system --output none
```

Open this Container App in Azure Portal, then **Application → Secrets → Add**. Use the name gateway-key; the user enters its value from their password manager and saves it. Preserve the existing gateway key; never put it in CLI arguments, logs or Git. Then apply the following update.

```powershell
az containerapp update --name $settings.app --resource-group $settings.group `
    --image $image --cpu 1 --memory 2Gi --min-replicas 1 --max-replicas 1 `
    --set-env-vars "FOUNDRY_ANTHROPIC_BASE=$($settings.baseUrl)" `
        'LITELLM_MASTER_KEY=secretref:gateway-key' 'PYTHONPATH=/app/claude-gateway' --output none
```

In **Ingress**, enable external HTTP access to target port 4000 with Allow insecure connections off. In **IP security restrictions**, allow only settings.clientCidr and save; do not add 0.0.0.0/0. The gateway key protects client requests. The app's managed identity authenticates to Foundry; the gateway key does not.

[Managed-identity image pull](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull)

**4. Check the serving revision**

```powershell
$app = az containerapp show --name $settings.app --resource-group $settings.group --output json | ConvertFrom-Json
$revision = az containerapp revision show --name $settings.app --resource-group $settings.group `
    --revision $app.properties.latestRevisionName --output json | ConvertFrom-Json
if (-not $revision.properties.active -or $revision.properties.healthState -ne 'Healthy' -or
    $app.properties.latestReadyRevisionName -ne $app.properties.latestRevisionName -or
    $revision.properties.template.containers[0].image -ne $image) {
    throw 'Revision not ready: inspect Revision management and system logs, then repeat this step'
}
$env:CLAUDE_GATEWAY_URL = 'https://' + $app.properties.configuration.ingress.fqdn
$secureKey = Read-Host 'Gateway key (entered privately)' -AsSecureString
$env:CLAUDE_GATEWAY_KEY = [Net.NetworkCredential]::new('', $secureKey).Password
try {
    ./scripts/check_gateway.ps1
} finally {
    $env:CLAUDE_GATEWAY_KEY = $null
}
```

Expect METADATA_READY and the three standard aliases. This makes no inference request and does not prove a model can answer. On failure inspect **Revision management** and **Log stream → System** for image pull, role propagation and secret references, then repeat this step; do not bypass readiness.

**5. Capture logs and run the workload**

First open a second PowerShell terminal in the same project directory and start the console log stream. Record the printed TRACE_FILE path and leave this terminal open.

```powershell
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$private = Join-Path (Get-Location).ProviderPath 'private'
$env:AZURE_CONFIG_DIR = Join-Path $private 'azure-cli'
$settings = Get-Content -LiteralPath (Join-Path $private 'settings.json') -Raw | ConvertFrom-Json
$traceFile = Join-Path $private ('provider-console_' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.jsonl')
Write-Output "TRACE_FILE=$traceFile"
az containerapp logs show --name $settings.app --resource-group $settings.group `
    --type console --follow --format json --tail 300 | Tee-Object -FilePath $traceFile
```

Return to the first terminal. The frozen matrix has ten configurations of five turns, medium effort, streaming and no retries: at most 50 requests. The 2026-10-24 run cost about US$0.79 at its recorded rates; check current prices before calling. The Container App, registry and logs are billed separately.

```powershell
$run = Join-Path $projectRoot ('live-runs/' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$secureKey = Read-Host 'Gateway key (entered privately)' -AsSecureString
$env:CLAUDE_GATEWAY_KEY = [Net.NetworkCredential]::new('', $secureKey).Password
try {
    ./scripts/check_gateway.ps1
    ./scripts/run_matrix.ps1 -RunDirectory $run
} finally {
    $env:CLAUDE_GATEWAY_KEY = $null
}
```

Expect EXECUTED_PENDING_PROVIDER_TRACE_AUDIT in run.json and 50 raw responses. Then press Ctrl+C in the log terminal. Logs come from one revision/replica/container; this path uses one replica. If streaming breaks, preserve the file and capture again; never substitute older logs for missing calls. Failed runs are not silently retried or overwritten; inspect the recorded failing response first.

**6. Audit this run**

```powershell
$traceFile = Read-Host 'Full path of the console log captured for this run'
python -B scripts/analyze.py --run-directory $run --trace-file $traceFile
Get-Content -LiteralPath (Join-Path $run 'analysis.md')
```

Expect status=PASS, requests=50 and providerCalls=50, with analysis.json and analysis.md identifying this run directory. Missing logs, wrong models, missing turns, truncated streams or usage mismatch fail without falling back to published evidence. Repeat --trace-file for several log files; --check validates without writing.

**Upgrade, rollback and stop**: save the current image digest before upgrading, update to the new digest and repeat step 4. On failure update to the saved digest and recheck. Single-replica maintenance may interrupt requests. Ctrl+C stops only the client; temporary container files may be lost on restart, so retain local responses and traces first. Only after the resource owner approves stopping, deactivate all active revisions of this dedicated app in Portal Revision management and verify zero replicas. ACR, environment and logging may still incur charges; decide on those separately and never delete shared resources.

### Audit a new gateway run

run_matrix.ps1 saves raw responses. analyze.py --run-directory also requires --trace-file and correlates outbound model, thinking, effort, stream, max_tokens and cache markers by x-litellm-call-id. It reads that directory's matrix.json, run.json, frozen collector and ACA_HTTP_*.json, reconstructing SSE, cumulative usage and history. It never falls back to published evidence. Missing logs fail; the original run.json stays pending audit.

Trace input accepts observer JSON/JSONL, CLAUDE_PROVIDER_TRACE console text and Azure CLI JSONL with a Log field. Identical duplicate log entries merge; conflicting content for one call ID fails. Unrelated calls are counted separately and cannot replace current requests. analysis.json and analysis.md are derived files in the same directory; --check writes nothing.

Check HTTP 200, end_turn, message_stop, nonempty text, complete usage, append-only history and zero thinking tokens for off modes. Cache-read share = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens); nearest-rank percentiles, so at N=5 P95 is the maximum.

Deployment command references (consulted 2026-10-25):
[Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest) · [Managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) · [Model deployments CLI](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account/deployment?view=azure-cli-latest) · [Claude in Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)

## Security and gaps

Live inputs, responses, signatures and authentication can be sensitive. live-runs, private, runs and .env are ignored; do not upload run directories. The published 2026-10-26 records only replace the endpoint resource name and the VM name; every other byte matches the record written on the VM (see the hashes in the export manifest), and they contain no token or key. The 2026-10-24 evidence omits signatures and pseudonymizes call IDs; do not replay its history signatures.

Not verified: an end-to-end deployment of this public package in a fresh subscription, a gateway in the models' region, concurrency or load, a client outside Azure, display: "summarized", requests with tools, and customer tasks.
