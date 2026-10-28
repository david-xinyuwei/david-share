# Testing and Reproduction

[README](../README.md) · [Results](results.md) · [中文](testing_CN.md)

The README owns the current ACA matrix execution sequence. This page separates offline replay, new-answer grading, gateway deployment and a separate forwarding diagnostic, followed by historical direct commands. Each path proves only its own stage; offline success is not a fresh deployment, inference run or production acceptance.

<a id="aca-snapshot-replay"></a>

## Replay the complete ACA results

From the repository's project directory, use Python 3.12 or 3.13. This offline command sends no requests and needs no credentials:

```bash
python -B gateway-cache/analyze_cache_matrix.py --run-dir evidence/gateway-cache-20261026 --out evidence/gateway-cache-20261026/interim-facts.json --check
python -B gateway-cache/swebench_score.py check-public --out evidence/gateway-score-20261027 --inference-dir evidence/gateway-cache-20261026
```

Expect `facts match`, then status PASS with denominator 624 and resolved 245, and exit 0. This replays saved metrics and official judgments; it does not generate new answers or rerun Docker. Cache-hit performance uses 302 pairs, while grading retains every measured answer.

### Run the official tests on the published patches

On a Linux x86-64 machine with Docker access and sufficient disk for the 12 dataset images, run from this project directory. Use a new prefix to avoid reusing prior evaluation results. This executes the published model patches without generating new model answers; VM time and image storage may incur charges. The recorded setup used Python 3.12.3, two workers and a 1,800-second per-instance timeout.

```bash
python -m pip install 'git+https://github.com/SWE-bench/SWE-bench.git@02e7a74ffd0b707aab73d203fe87bdc7c76afc8e'
RUN_PREFIX="aca-regrade-$(date -u +%Y%m%d-%H%M%S)"
for prediction in evidence/gateway-score-20261027/predictions/*.jsonl; do
  label=$(basename "$prediction" .jsonl)
  python -u -m swebench.harness.run_evaluation \
     --dataset_name evidence/gateway-score-20261027/dataset.json \
     --predictions_path "$prediction" --max_workers 2 --timeout 1800 \
     --run_id "$RUN_PREFIX-$label" || break
done
```

Each of the 52 batches must produce `logs/evaluation/<run_id>/results.json`; inspect resolved, unresolved, empty-patch and error IDs, not just the CLI exit code. Patch-application failures are model-output outcomes; infrastructure failures require diagnosis and re-evaluating the same frozen patch. The published [official reports](../evidence/gateway-score-20261027/logs/evaluation) and [prediction hashes](../evidence/gateway-score-20261027/manifest.json) are the comparison reference. The public command blocks have not been replayed in a new machine during this documentation update.

## Offline checks

No Azure access or model key. Python 3.12 or 3.13 from this directory; the stream-parser tests also need the client packages.

**Windows first.** The official SWE-bench reports under `evidence/gateway-score-20261027/logs/` have paths longer than 260 characters. Enable long paths before cloning, or the checkout is incomplete and `check-public` fails: `git clone -c core.longpaths=true https://github.com/david-xinyuwei/david-share.git`, or `git config --global core.longpaths true` once. CI sets the same option; Linux and macOS need nothing.

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

<a id="fresh-aca-analysis"></a>

## Analyze and grade a new ACA run

Follow the owning README for input preparation, the cache gate and collection. Its WORK, RUN and RUN_ID variables identify your new private directory. `analyze_cache_matrix.py --run-dir` reads that run's responses, including recorded retry attempts; it does not substitute published fixtures. A complete collection can still contain truncations or incorrect answers. The parameter records precede model-alias mapping and are not provider-wire traces.

**Separate outbound audit.** The gateway setup section's 50-request diagnostic uses `run_matrix.ps1` plus `scripts/analyze.py --run-directory --trace-file` to correlate each call. It is a different workload from the 650-request coding matrix. The coding analyzer does not perform that trace correlation; retain native gateway logs when collecting new performance results, and do not label this unimplemented audit as PASS.

**Grade newly generated answers, not the public metrics projection.** On Linux x86-64 with Docker and space for the dataset images, reuse a compatible Python environment. This stage downloads official data/images and runs tests; it makes no model calls but consumes compute. The driver freezes the official evaluation dataset at prepare time. Before comparing with the published score, the following guard requires the same dataset revision. A mismatch requires a separately scoped evaluation, not a relabeled comparison.

```bash
python -m pip install 'git+https://github.com/SWE-bench/SWE-bench.git@02e7a74ffd0b707aab73d203fe87bdc7c76afc8e'
SCORE="$WORK/score"
python -B gateway-cache/swebench_score.py audit-input --run-dir "$RUN"
python -B gateway-cache/swebench_score.py prepare --run-dir "$RUN" \
  --problems "$WORK/problems.json" --out "$SCORE" --evaluation-id "$RUN_ID"
python -c 'import json,sys; record=json.load(open(sys.argv[1], encoding="utf-8")); assert record["dataset"]["revision"] == "b0dde1093fe417d83b7184254edf8199c1f0dff5", "Evaluation dataset revision changed"' "$SCORE/manifest.json"
python -u gateway-cache/swebench_score.py run --out "$SCORE" --workers 2
python -B gateway-cache/swebench_score.py collect --out "$SCORE"
```

Prepare must retain every measured answer and exclude only warm-ups. With the full protocol expect 624 answers and 52 batches; resolved counts are not predetermined. Read this SCORE's score-summary.json, scored-responses.json and native logs/evaluation reports. NOT_GRADED or EVALUATION_ERROR means incomplete evaluation, not an answer failure to silently discard. This command sequence was not rerun on fresh cloud compute during the documentation update.

<a id="gateway-setup"></a>

## Deploy a gateway and audit forwarding

Steps 1-4 deploy and check LiteLLM on a dedicated Container App; then return to the README for the 650-request matrix. Steps 5-6 are a separate 50-request forwarding diagnostic using the ten five-turn configurations from 2026-10-24, not the 650-request matrix. Choose the Foundry resource's region for the app; use East US 2 to reproduce the current placement. The historical diagnostic ran in Japan East and includes cross-region latency. These commands use PowerShell 7.6; a deployed environment is not a completed model test.

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

Live inputs, responses, signatures and authentication can be sensitive. live-runs, private, runs and .env are ignored; do not upload run directories. Historical coding-matrix-20261026 records replace only endpoint and VM names. New gateway-cache-20261026 records are a metrics projection: numbers are preserved but prompt/answer bodies, thinking signatures, private endpoints and non-region headers are omitted. Each export manifest records its hashes and scope; the metrics projection cannot score code correctness. The 2026-10-24 evidence omits signatures and pseudonymizes call IDs; do not replay its history signatures.

All 650 ACA request records and grading outcomes for 624 measured answers are retained, including failures and six official ambiguous flags. Not verified: an end-to-end deployment in a fresh subscription, concurrency or load, a client outside Azure, display: "summarized", tool use, and customer tasks. Environment versions were collected after grading, not as in-run telemetry.

<a id="historical-direct-procedure"></a>

## Historical direct procedure, reference only

**Current test entry.** New tests use the [ACA cache runner](../gateway-cache/aca_cache_matrix.py) and its [launcher](../gateway-cache/run.sh), with the [12-problem manifest](../data/gateway-cache-problems.json). Requests go from the VM client through the gateway, with `cache_control` enabled; do not use the old direct-VM client for the current test.

**Retired direct-VM procedure: reference only.** The commands below document how the historical evidence was produced. They are not the current deployment or test instructions and must not be used for a new run under the ACA protocol. Historical procedures and offline evidence checks remain in [docs/testing.md](testing.md).

**Execution boundary:** the 2026-10-26 results came from these scripts, on a VM created with the commands of step 3 under our own resource names. The repository was assembled afterwards. Step 4 was then run once from the same VM with the published `claude_api.py`, `pricing.py` and `call_once.py`: completed, HTTP 200, first visible text after 0.89 s ([record](../evidence/coding-matrix-20261026/readme-step4.json)). Steps 1 to 3 have not been re-run in a fresh subscription.

| Order | Where | Action | Entry |
|---|---|---|---|
| 1 | Bash with Azure CLI | Sign in and name the resources | `az login` |
| 2 | Foundry portal and Azure CLI | Deploy the three models | `az cognitiveservices account deployment create` |
| 3 | Azure CLI | Create a VM in the same region and let its identity call Foundry | `az vm create`, `az role assignment create` |
| 4 | The VM | Install the client and send one request | [`coding-matrix/call_once.py`](../coding-matrix/call_once.py) |

**Prerequisites.** Bash with Azure CLI (we used 2.91.0; Azure Cloud Shell works); a Foundry resource in a region that offers Claude 5.5 (East US 2 here); permission to deploy models, create a VM and assign roles on the Foundry resource; Claude 5.5 quota; and the Marketplace terms for Anthropic models, which the subscription owner accepts in the portal on the first deployment. Model calls, the VM and its disk are charged.

**1. Sign in and name the resources.** Fill in the five values; `LOCATION` is the Foundry resource's region.

```bash
SUBSCRIPTION_ID="<subscription-id>"
FOUNDRY_RG="<resource-group-of-the-Foundry-resource>"
FOUNDRY="<Foundry-resource-name>"
VM_RG="<new-resource-group-for-the-client-VM>"
LOCATION="eastus2"
az login
az account set --subscription "$SUBSCRIPTION_ID"
az cognitiveservices account show -g "$FOUNDRY_RG" -n "$FOUNDRY" --query "{name:name, location:location}" -o table
```

Success: the last command prints the resource and its region. If it fails, check the subscription and the resource names before going on.

**2. Deploy the three models.** Capacity is thousands of tokens per minute; these are the values of the test (Opus 40, Sonnet and Haiku 80). If a command fails on Marketplace terms, deploy that model once in the Foundry portal (**Discover → Models**, then **Deploy → Custom settings**, deployment type **Global**, version 2) and run the command again.

```bash
az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name claude-opus-5-5 \
  --model-name claude-opus-5-5 --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 40
az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name claude-sonnet-5-5 \
  --model-name claude-sonnet-5-5 --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 80
az cognitiveservices account deployment create -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name claude-haiku-5-5 \
  --model-name claude-haiku-5-5 --model-version 2 --model-format Anthropic --sku-name GlobalStandard --sku-capacity 80
az cognitiveservices account deployment list -g "$FOUNDRY_RG" -n "$FOUNDRY" \
  --query "[?properties.model.format=='Anthropic'].{name:name, sku:sku.name, capacity:sku.capacity, version:properties.model.version, state:properties.provisioningState}" -o table
```

Success: three rows with `GlobalStandard`, version `2` and `Succeeded`. Without quota, request it rather than switching models. The test client paces itself to these capacities (`TPM` in `bench.py` and `cache_test.py`); with other capacities, change those two values before repeating the measurements.

**3. Create the client VM in the same region.** The VM gets a system-assigned managed identity, and `Cognitive Services User` on the Foundry resource lets that identity call the models. `--nsg-rule NONE` opens no inbound port: connect through Azure Bastion (we used it), or add an SSH rule limited to your own IP address.

```bash
az group create -n "$VM_RG" -l "$LOCATION"
az vm create -g "$VM_RG" -n claude-client -l "$LOCATION" \
  --image Canonical:ubuntu-24_04-lts:server:latest --size Standard_D4s_v5 --os-disk-size-gb 128 \
  --admin-username azureuser --generate-ssh-keys --assign-identity '[system]' \
  --public-ip-sku Standard --nsg-rule NONE
PRINCIPAL_ID=$(az vm show -g "$VM_RG" -n claude-client --query identity.principalId -o tsv)
FOUNDRY_ID=$(az cognitiveservices account show -g "$FOUNDRY_RG" -n "$FOUNDRY" --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role "Cognitive Services User" --scope "$FOUNDRY_ID"
```

Success: `az vm create` prints `"powerState": "VM running"` and the role assignment prints its JSON. A new role assignment can take a few minutes to apply.

**4. Install the client and send one request.** Run this on the VM. Set `FOUNDRY_ANTHROPIC_BASE` to your resource's endpoint ending in `/anthropic`.

```bash
sudo apt-get update && sudo apt-get install -y python3-venv git
git clone --filter=blob:none --sparse --depth=1 https://github.com/david-xinyuwei/david-share.git
git -C david-share sparse-checkout set Agents/Claude-Foundry-LiteLLM-Performance
cd david-share/Agents/Claude-Foundry-LiteLLM-Performance/coding-matrix
python3 -m venv ~/venv && ~/venv/bin/pip install -r requirements.txt
export FOUNDRY_ANTHROPIC_BASE="https://<foundry-resource>.services.ai.azure.com/anthropic"
~/venv/bin/python call_once.py --model claude-sonnet-5-5 --thinking between_tools --effort low \
  "Write a Python function that returns the n-th Fibonacci number."
```

Success: the answer, then a line such as `{"status": "completed", "http_status": 200, "first_text_s": 0.8893, ...}`, and exit code 0. HTTP 401 or 403: the role has not applied yet or was assigned on another resource; wait and retry. HTTP 400: the model does not accept that thinking mode or effort (see the first table). HTTP 404: the deployment name or the endpoint is wrong.

**Done.** The three deployments answer a client in their own region with the parameters used here. To repeat the measurements, follow [docs/testing.md](testing.md).

**Remove resources only after the owner approves; this is not part of deployment.** Each block removes one thing; run only the one you need.

Delete the client VM and its resource group (`az` asks you to confirm):

```bash
az group delete -n "$VM_RG"
```

Delete the three model deployments:

```bash
for name in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5; do
  az cognitiveservices account deployment delete -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name "$name"
done
```

**Repository.** [`coding-matrix/`](../coding-matrix/) client, probe, matrix, judge, cache test and analysis · [`data/`](../data/) the measured problem list and the gateway workload · [`evidence/coding-matrix-20261026/`](../evidence/coding-matrix-20261026/) run records, facts and provenance · [`evidence/`](../evidence/) gateway records · [`scripts/`](../scripts/) gateway collector, gateway analysis and the page generator · [`deploy/`](../deploy/) gateway image · [`images/`](../images/) figures and icon ledger · [`tests/`](../tests/) offline tests (`python -B -m unittest discover -s tests -v`, run by CI) · [`NOTICE.md`](../NOTICE.md) third-party notices.

## Repeat the 2026-10-26 tests

**Before you start.** Finish the historical direct procedure above, steps 1 to 4. These runs cost money: at list prices our matrix cost $55.36, the cache test $6.70 and the probe $0.05. `--budget-usd` stops the matrix at a limit (default 150). The client paces itself to Opus 40,000 and Sonnet and Haiku 80,000 tokens per minute (`TPM` in `bench.py` and `cache_test.py`); change those values if your capacities differ. Run everything on the VM, in `coding-matrix/`.

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
