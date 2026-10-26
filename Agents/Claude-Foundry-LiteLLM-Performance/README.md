# Claude on Foundry: Thinking, Prompt Caching and First-Text Latency

[![LiteLLM 1.106.2](https://img.shields.io/badge/LiteLLM-1.106.2-0078D4)](deploy/Dockerfile)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](requirements.txt)
[![Claude 5.5](https://img.shields.io/badge/Claude-5.5-555555?logo=anthropic&logoColor=white)](data/matrix.json)
[![david-share stars](https://img.shields.io/github/stars/david-xinyuwei/david-share?style=flat&logo=github&label=david-share%20stars)](https://github.com/david-xinyuwei/david-share/stargazers)

Author: Xinyu Wei · [中文](README_CN.md)

Stars belong to the whole david-share repository, not this directory.

## Purpose

Measure thinking mode, cache coverage and client-visible waiting separately. A successful HTTP response, streaming flag or cache marker is not a performance acceptance test. This project provides a fixed five-turn workload, a streaming collector, ten measured configurations and independent offline verification.

This is one fixed source-review workload, not customer production traffic. There is no answer-quality score, concurrent load test, AWS comparison or effort-level ranking.

The recorded experiment used real model calls. A fresh deployment of this public package has not been run; offline checks are not deployment proof.

<img src="images/architecture-en.svg" width="440" alt="Measured gateway path and client timing points" />

Original explanatory diagram. The client owns prompts, history and timing; LiteLLM owns protocol and identity forwarding; model serving owns generation and caching. Connections explain the design, not execution proof. [Azure icons](images/icon-sources.json) · [Runtime](evidence/provenance.json)

Adaptive uses adaptive; Sonnet without up-front thinking uses between_tools, and Haiku with thinking off uses disabled. Streaming remains enabled in every case.

## Steps

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

Success is a completed ACR Tasks build and an image address with a SHA-256 digest. The public LiteLLM base is pinned. This repair did not build and deploy the public package from scratch: ENV_BUILD_STATUS=NOT_BUILT.

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

Return to the first terminal. The frozen matrix has ten configurations of five turns, medium effort, streaming and no retries, at most 50 requests. Its USD 50 script budget includes a fixed USD 3 reserve, not measured usage. Rates come from the frozen collector; check current pricing before calling. This bound excludes infrastructure and is not a current billing guarantee.

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

## Results

The recorded experiment on 2026-10-24 completed **50/50 requests**. Model cost at its recorded rates: **US$0.78989513**. Each cache configuration has five turns. These are historical measurements, not a reader's new run or current prices. First text spans client send to the first nonempty text_delta; P50 is the median of five turns.

**First visible text P50, seconds**

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 9.321 | 7.293 |
| Sonnet 5.5<br>adaptive | 8.051 | 1.434 |
| Sonnet 5.5<br>between_tools | 0.954 | 0.893 |
| Haiku 5.5<br>adaptive | 4.235 | 2.910 |
| Haiku 5.5<br>disabled | 0.810 | 0.781 |

**Cache-read share across all five turns, %**

Cache-read share covers all five turns: total read tokens / (total uncached + written + read input tokens). Initial writes enter the denominator but are not hits; new prompts and history still need processing. System only reuses the fixed source; System + history also enables growing automatic conversation caching. This is neither last-turn hit rate nor the mean of per-turn percentages.

| Model / mode | System only | System + history |
|---|---:|---:|
| Opus 5.5<br>adaptive | 28.27 | 69.25 |
| Sonnet 5.5<br>adaptive | 33.52 | 67.68 |
| Sonnet 5.5<br>between_tools | 39.96 | 70.68 |
| Haiku 5.5<br>adaptive | 32.81 | 71.04 |
| Haiku 5.5<br>disabled | 47.47 | 72.44 |

The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate.

Higher cache share does not attribute all first-text improvements to caching: conversations generate independently, changing history and thinking usage. All timing is client-side; server queues, network time and model compute are not isolated.

| Goal | Read |
|---|---|
| Inspect per-turn and timing results | [Results](docs/results.md) |
| Verify, reproduce and understand limits | [Testing](docs/testing.md) |

Directories: [deploy](deploy/), [scripts](scripts/), [data](data/), [evidence](evidence/), [images](images/), [tests](tests/). [Dependencies](requirements.txt).
