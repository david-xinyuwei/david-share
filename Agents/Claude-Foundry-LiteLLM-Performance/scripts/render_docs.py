import argparse
import base64
import hashlib
import html
import json
import math
from pathlib import Path

from analyze import ROOT, read_json, require, validate


LABELS = {
    "opus55-standard": "Opus 5.5",
    "sonnet55-standard": "Sonnet 5.5",
    "haiku55-standard": "Haiku 5.5",
}


def case_label(config, chinese=False):
    mode = config["thinking"]
    if chinese:
        mode = {"adaptive": "自适应", "between_tools": "无前置思考", "disabled": "关闭思考"}[mode]
        cache = "仅系统" if config["cache"] == "system" else "系统与历史"
    else:
        cache = "system" if config["cache"] == "system" else "history"
    return LABELS[config["model"]], mode, cache


def comparison_table(groups, field, chinese=False, digits=3):
    header = "| 模型 / 模式 | 仅系统前缀 | 系统与历史 |" if chinese else "| Model / mode | System only | System + history |"
    lines = [header, "|---|---:|---:|"]
    for case_id, group in groups.items():
        if group["config"]["cache"] != "system":
            continue
        other = groups[case_id.removesuffix("system") + "conversation"]
        mode = group["config"]["thinking"]
        label = {"adaptive": "自适应思考", "between_tools": "无前置思考", "disabled": "关闭思考"}[mode] if chinese else mode
        values = [entry[field]["p50"] if isinstance(entry[field], dict) else entry[field] for entry in (group, other)]
        lines.append(f'| {LABELS[group["config"]["model"]]}<br>{label} | {values[0]:.{digits}f} | {values[1]:.{digits}f} |')
    return "\n".join(lines)


def deployment_steps(chinese=False):
    def heading(number, english, chinese_title):
        return f"**{number}. {chinese_title if chinese else english}**"

    parts = [
        ("| 顺序 | 位置 | 操作 |\n|---|---|---|\n| 1 | 本机与 Foundry | 配置、登录、三个模型部署 |\n| 2 | Azure CLI | 构建镜像和基础资源 |\n| 3 | CLI 与 Portal | 身份、Secret、镜像和 Ingress |\n| 4 | Portal 与本机 | revision 与元数据就绪 |\n| 5 | 两个本机终端 | 保留日志并运行矩阵 |\n| 6 | 本机 | 审计新运行、读取报告 |"
         if chinese else "| Order | Where | Action |\n|---|---|---|\n| 1 | Client and Foundry | Settings, sign-in and three deployments |\n| 2 | Azure CLI | Build image and infrastructure |\n| 3 | CLI and Portal | Identity, secret, image and ingress |\n| 4 | Portal and client | Revision and metadata readiness |\n| 5 | Two client terminals | Capture logs and run matrix |\n| 6 | Client | Audit the new run and read its report |"),
        ("以下主路径使用专用的新 Container App、ACR 和环境；不要将创建或停用步骤套到共享生产资源。需要 PowerShell 7.6、Python 3.13、Azure CLI，以及创建资源、运行 ACR Tasks、为指定资源分配角色和读取日志的权限。模型访问与 Marketplace 条款由订阅所有者确认。资源、构建、日志和模型调用可能计费，执行前确认预算。"
         if chinese else "This path uses a dedicated new Container App, ACR and environment; do not apply creation or shutdown steps to shared production resources. Use PowerShell 7.6, Python 3.13 and Azure CLI, with permission to create resources, run ACR Tasks, assign scoped roles and read logs. The subscription owner confirms model access and Marketplace terms. Resources, builds, logs and model calls can incur charges; approve the budget first."),
        heading(1, "Set the context and deploy models", "设置上下文并部署模型"),
        ("先在 Foundry Portal 选择现有资源，或由有权限的用户创建资源并记录租户、订阅、资源组、资源名和 /anthropic 基础地址。然后在本项目目录启动 PowerShell。首次运行只输入一次非秘密配置；其他终端从 private/settings.json 读取。登录由用户在本机完成交互认证，不复制 token cache。"
         if chinese else "First select an existing resource in the Foundry portal, or have an authorized user create one and record its tenant, subscription, resource group, resource name and /anthropic base URL. Then start PowerShell in this project directory. Enter non-secret settings once; other terminals load private/settings.json. Sign in interactively on this machine; do not copy token caches."),
        r'''```powershell
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
```''',
        ("成功时显示所选 Foundry 资源。尚无资源时，在 Foundry Portal 创建资源并选择所需区域。在 **Discover → Models** 中分别选择 Opus 5.5、Sonnet 5.5、Haiku 5.5，进入 **Deploy → Custom settings**；首次部署由用户接受 Marketplace 条款。选 **Global** 与标为 **Hosted on Azure** 的版本 2，部署名分别为 claude-opus-5-5、claude-sonnet-5-5、claude-haiku-5-5；按已批准配额填写容量。待三个部署完成后，在 **Build → Models → Details** 核对名称、版本与 Target URI；baseUrl 只保留到 /anthropic。没有访问资格或配额就停在这一步，不换模型。"
         if chinese else "Success displays the selected Foundry resource. If no resource exists, create one in the Foundry portal in the required region. In **Discover → Models**, select Opus 5.5, Sonnet 5.5 and Haiku 5.5 in turn, then **Deploy → Custom settings**; the user accepts Marketplace terms for the first deployment. Select **Global** and version 2 labeled **Hosted on Azure**, using deployment names claude-opus-5-5, claude-sonnet-5-5 and claude-haiku-5-5. Allocate only approved quota. After all three complete, verify names, versions and Target URI in **Build → Models → Details**; baseUrl ends at /anthropic. Stop here if access or quota is unavailable; do not substitute models."),
        "[Foundry provisioning and authentication](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#provisioning)",
        heading(2, "Build a pinned image", "构建并固定镜像"),
        r'''```powershell
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
```''',
        ("成功时 ACR Tasks 构建完成，image 为带 SHA-256 digest 的镜像地址。Dockerfile 的公开 LiteLLM base 已固定；本次修复未执行这套公开包装的全新构建和云部署，ENV_BUILD_STATUS=NOT_BUILT。"
         if chinese else "Success is a completed ACR Tasks build and an image address with a SHA-256 digest. The public LiteLLM base is pinned. This repair did not build and deploy the public package from scratch: ENV_BUILD_STATUS=NOT_BUILT."),
        heading(3, "Configure identity, secret and ingress", "配置身份、密钥和入口"),
        ("按微软系统分配身份流程，先以公开 quickstart 镜像创建无外部入口的临时 revision，再配置真实网关。临时镜像只用于取得身份，不是模型服务，也不进入测量。先解析其 digest，后续使用不可变地址。"
         if chinese else "Following Microsoft's system-assigned identity flow, first create a temporary revision from the public quickstart image with no external ingress, then configure the real gateway. This image only bootstraps identity; it is not model serving or measurement. Resolve its digest before use."),
        r'''```powershell
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
```''',
        ("在 Azure Portal 打开此 Container App，进入 **Application → Secrets → Add**，名称为 gateway-key，值由用户从自己的密码管理器输入；保存。保留原入口密钥，不在 CLI 参数、日志或 Git 中写明文。然后执行以下更新。"
         if chinese else "Open this Container App in Azure Portal, then **Application → Secrets → Add**. Use the name gateway-key; the user enters its value from their password manager and saves it. Preserve the existing gateway key; never put it in CLI arguments, logs or Git. Then apply the following update."),
        r'''```powershell
az containerapp update --name $settings.app --resource-group $settings.group `
    --image $image --cpu 1 --memory 2Gi --min-replicas 1 --max-replicas 1 `
    --set-env-vars "FOUNDRY_ANTHROPIC_BASE=$($settings.baseUrl)" `
        'LITELLM_MASTER_KEY=secretref:gateway-key' 'PYTHONPATH=/app/claude-gateway' --output none
```''',
        ("在 **Ingress** 启用来自外部的 HTTP 访问，目标端口 4000，关闭 Allow insecure connections；在 **IP security restrictions** 只允许 settings.clientCidr，并保存。不要添加 0.0.0.0/0。网关仍以入口密钥保护请求；调用 Foundry 使用该应用的 Managed Identity（托管身份），不是入口密钥。"
         if chinese else "In **Ingress**, enable external HTTP access to target port 4000 with Allow insecure connections off. In **IP security restrictions**, allow only settings.clientCidr and save; do not add 0.0.0.0/0. The gateway key protects client requests. The app's managed identity authenticates to Foundry; the gateway key does not."),
        "[Managed-identity image pull](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull)",
        heading(4, "Check the serving revision", "检查实际服务版本"),
        r'''```powershell
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
```''',
        ("预期 METADATA_READY 并列出三个 standard 别名。该检查没有推理调用，不证明模型能成功回答。失败时查看 **Revision management** 和 **Log stream → System**，检查镜像拉取、角色传播和 Secret 引用后重做本步骤，不跳过就绪检查。"
         if chinese else "Expect METADATA_READY and the three standard aliases. This makes no inference request and does not prove a model can answer. On failure inspect **Revision management** and **Log stream → System** for image pull, role propagation and secret references, then repeat this step; do not bypass readiness."),
        heading(5, "Capture logs and run the workload", "保存日志并运行矩阵"),
        ("先在第二个 PowerShell 终端切到同一项目目录，启动控制台日志流；记下输出的 TRACE_FILE 路径，终端保持打开。"
         if chinese else "First open a second PowerShell terminal in the same project directory and start the console log stream. Record the printed TRACE_FILE path and leave this terminal open."),
        r'''```powershell
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$private = Join-Path (Get-Location).ProviderPath 'private'
$env:AZURE_CONFIG_DIR = Join-Path $private 'azure-cli'
$settings = Get-Content -LiteralPath (Join-Path $private 'settings.json') -Raw | ConvertFrom-Json
$traceFile = Join-Path $private ('provider-console_' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.jsonl')
Write-Output "TRACE_FILE=$traceFile"
az containerapp logs show --name $settings.app --resource-group $settings.group `
    --type console --follow --format json --tail 300 | Tee-Object -FilePath $traceFile
```''',
        ("回到第一个终端运行。固定十组、每组五轮、medium、流式、零重试，最多 50 次请求；脚本预算为 50 美元，其中 3 美元为固定保守预留，不是本次实测费用。费率来自冻结采集器，调用前核对最新价目；该预算不覆盖基础设施，也不能保证当前实际账单。"
         if chinese else "Return to the first terminal. The frozen matrix has ten configurations of five turns, medium effort, streaming and no retries, at most 50 requests. Its USD 50 script budget includes a fixed USD 3 reserve, not measured usage. Rates come from the frozen collector; check current pricing before calling. This bound excludes infrastructure and is not a current billing guarantee."),
        r'''```powershell
$run = Join-Path $projectRoot ('live-runs/' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$secureKey = Read-Host 'Gateway key (entered privately)' -AsSecureString
$env:CLAUDE_GATEWAY_KEY = [Net.NetworkCredential]::new('', $secureKey).Password
try {
    ./scripts/check_gateway.ps1
    ./scripts/run_matrix.ps1 -RunDirectory $run
} finally {
    $env:CLAUDE_GATEWAY_KEY = $null
}
```''',
        ("预期 run.json 为 EXECUTED_PENDING_PROVIDER_TRACE_AUDIT，目录内有 50 份原始响应。结束后在日志终端按 Ctrl+C；日志来自一个 revision/replica/container，本路径固定单副本。如果日志流中断，保留文件并重新采集，不能用旧日志冒充缺失记录。运行器失败不自动重试或覆盖目录，先定位对应原始响应。"
         if chinese else "Expect EXECUTED_PENDING_PROVIDER_TRACE_AUDIT in run.json and 50 raw responses. Then press Ctrl+C in the log terminal. Logs come from one revision/replica/container; this path uses one replica. If streaming breaks, preserve the file and capture again; never substitute older logs for missing calls. Failed runs are not silently retried or overwritten; inspect the recorded failing response first."),
        heading(6, "Audit this run", "验收本次运行"),
        r'''```powershell
$traceFile = Read-Host 'Full path of the console log captured for this run'
python -B scripts/analyze.py --run-directory $run --trace-file $traceFile
Get-Content -LiteralPath (Join-Path $run 'analysis.md')
```''',
        ("预期 status=PASS、requests=50、providerCalls=50，analysis.json 与 analysis.md 的 run 对应本次目录。缺日志、错误模型、缺轮次、断流或 usage 不符会失败，不回退到仓库旧证据。多份日志可重复传 --trace-file；--check 只验算不写文件。"
         if chinese else "Expect status=PASS, requests=50 and providerCalls=50, with analysis.json and analysis.md identifying this run directory. Missing logs, wrong models, missing turns, truncated streams or usage mismatch fail without falling back to published evidence. Repeat --trace-file for several log files; --check validates without writing."),
        ("**升级、回滚与停用**：升级前读取并保存当前镜像 digest，更新为新 digest 后重复第 4 步；失败时用已保存的旧 digest 执行同一 update 命令并再次检查。单副本维护可能中断请求。Ctrl+C 仅停止客户端；容器临时文件可能在重启时丢失，先保留本地原始响应和 trace。只有资源所有者确认停止后，才在 Portal 的 Revision management 停用该专用应用所有 active revision，并核对副本为 0；ACR、环境和日志仍可能计费，按各自资源另行决定，不删除共享资源。"
         if chinese else "**Upgrade, rollback and stop**: save the current image digest before upgrading, update to the new digest and repeat step 4. On failure update to the saved digest and recheck. Single-replica maintenance may interrupt requests. Ctrl+C stops only the client; temporary container files may be lost on restart, so retain local responses and traces first. Only after the resource owner approves stopping, deactivate all active revisions of this dedicated app in Portal Revision management and verify zero replicas. ACR, environment and logging may still incur charges; decide on those separately and never delete shared resources."),
    ]
    return "\n\n".join(parts)


def architecture(chinese=False):
    icon_source = read_json(ROOT / "images/icon-sources.json")
    icons = {}
    for item in icon_source["icons"]:
        path = ROOT / item["file"]
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], "Icon changed")
        icons[path.name] = base64.b64encode(path.read_bytes()).decode()
    app_icon = icons["02989-icon-service-Container-Apps-Environments.svg"]
    foundry_icon = icons["036509415-icon-service-Foundry-Project.svg"]
    title = "实际测试路径与计时位置" if chinese else "Measured path and timing points"
    client = "Windows 客户端 / 固定五轮" if chinese else "Windows client / fixed five turns"
    gateway = "LiteLLM 1.106.2 / 单 worker" if chinese else "LiteLLM 1.106.2 / one worker"
    note = "客户端计时；GlobalStandard" if chinese else "Client timing; GlobalStandard"
    note_end = "不保证推理固定在资源所在区域。" if chinese else "does not pin inference to the resource region."
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="640" viewBox="0 0 520 640">
<rect width="520" height="640" fill="#ffffff"/>
<g font-family="Segoe UI,Microsoft YaHei,sans-serif" fill="#202020">
<text x="24" y="36" font-size="25" fill="#0078d4">{title}</text>
<rect x="24" y="62" width="448" height="118" rx="6" fill="#f5f5f5" stroke="#767676"/>
<text x="42" y="93" font-size="23">{client}</text>
<text x="42" y="127" font-size="21">PowerShell 7.6.7 / HTTPS</text>
<text x="42" y="160" font-size="21">{'响应头 / SSE / 文本 / 结束' if chinese else 'headers / SSE / text / end'}</text>
<path d="M248 180 V218" stroke="#0078d4" stroke-width="3"/><path d="M242 208 L248 220 L254 208" fill="#0078d4"/>
<text x="265" y="204" font-size="19">/v1/messages</text>
<rect x="24" y="224" width="448" height="124" rx="6" fill="#eef6fc" stroke="#0078d4"/>
<image x="42" y="239" width="32" height="32" href="data:image/svg+xml;base64,{app_icon}"/>
<text x="86" y="264" font-size="23">Azure Container Apps</text>
<text x="42" y="297" font-size="21">{gateway}</text>
<text x="42" y="330" font-size="21">{'Japan East / 托管身份' if chinese else 'Japan East / managed identity'}</text>
<path d="M248 348 V386" stroke="#0078d4" stroke-width="3"/><path d="M242 376 L248 388 L254 376" fill="#0078d4"/>
<text x="265" y="374" font-size="19">Entra token</text>
<rect x="24" y="392" width="448" height="124" rx="6" fill="#eef6fc" stroke="#0078d4"/>
<image x="42" y="407" width="32" height="32" href="data:image/svg+xml;base64,{foundry_icon}"/>
<text x="86" y="432" font-size="23">Microsoft Foundry</text>
<text x="42" y="465" font-size="21">Opus / Sonnet / Haiku 5.5</text>
<text x="42" y="498" font-size="20">{'East US 2 资源 / 全球推理' if chinese else 'East US 2 resource / global inference'}</text>
<path d="M472 454 H500 V122 H482" stroke="#107c10" stroke-width="2" fill="none"/>
<path d="M482 116 L470 122 L482 128" fill="#107c10"/>
<text x="24" y="552" font-size="21" fill="#107c10">{'绿色返回路径：SSE、usage、stop_reason' if chinese else 'Green return: SSE, usage, stop_reason'}</text>
<text x="24" y="590" font-size="20">{note}</text>
<text x="24" y="619" font-size="20">{note_end}</text></g></svg>'''


def latency_chart(groups, chinese=False):
    title = "首个可见文本：逐次请求分布" if chinese else "First visible text: each request"
    maximum = max(row["ttftSeconds"] for group in groups.values() for row in group["rows"])
    axis_limit = max(1, math.ceil(maximum))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="520" height="960" viewBox="0 0 520 960"><rect width="520" height="960" fill="white"/><g font-family="Segoe UI,Microsoft YaHei,sans-serif"><text x="22" y="36" font-size="24" fill="#202020">{title}</text>']
    for value in (0, axis_limit / 2, axis_limit):
        position = 260 + value / axis_limit * 225
        parts.append(f'<text x="{position:.1f}" y="78" text-anchor="middle" font-size="20">{value:g} s</text>')
    for index, group in enumerate(groups.values()):
        config = group["config"]
        model, mode, cache = case_label(config, chinese)
        top = 105 + index * 80
        colour = "#0078d4" if config["thinking"] == "adaptive" else "#107c10"
        parts.extend([f'<text x="22" y="{top+17}" font-size="22">{model}</text>',
                      f'<text x="22" y="{top+43}" font-size="19">{html.escape(mode)} / {cache}</text>',
                      f'<path d="M260 {top+27} H485" stroke="#cccccc" fill="none"/>'])
        for row in group["rows"]:
            position = 260 + row["ttftSeconds"] / axis_limit * 225
            vertical = top + 27 + (row["turn"] - 3) * 7
            parts.append(f'<circle cx="{position:.2f}" cy="{vertical}" r="4" fill="{colour}"><title>Turn {row["turn"]}: {row["ttftSeconds"]:.3f} s</title></circle>')
    note = "每行五轮，非独立样本，不代表质量排名。" if chinese else "Five dependent turns per row; not a quality ranking."
    parts.append(f'<text x="22" y="936" font-size="19" fill="#555">{note}</text></g></svg>')
    return "\n".join(parts)


def detailed_tables(groups, chinese=False):
    sections = []
    for case_id, group in groups.items():
        label = " / ".join(case_label(group["config"], chinese))
        lines = [f"### {label}", "", f"`{case_id}`", "",
                 (f'产生思考的请求：{group["thinkingRequests"]}/5。' if chinese else f'Requests with thinking: {group["thinkingRequests"]}/5.'), "",
                 "| 计时点 | P50 秒 | P95 秒 |" if chinese else "| Timing point | P50 s | P95 s |",
                 "|---|---:|---:|"]
        metrics = (("headersSeconds", "响应头", "Headers"), ("firstSseSeconds", "首个 SSE", "First SSE"),
                   ("ttftSeconds", "首个文本", "First text"), ("postFirstSseWaitSeconds", "SSE 后等待", "Post-SSE wait"),
                   ("e2eSeconds", "完整结束", "Full end"))
        for field, cn_label, en_label in metrics:
            lines.append(f'| {cn_label if chinese else en_label} | {group[field]["p50"]:.3f} | {group[field]["p95"]:.3f} |')
        for headers, fields in (
            (("轮次", "首字秒", "总耗时秒") if chinese else ("Turn", "First text s", "E2E s"), ("ttftSeconds", "e2eSeconds")),
            (("轮次", "总输入", "读取", "写入") if chinese else ("Turn", "Total input", "Read", "Written"), ("totalInputTokens", "cacheReadTokens", "cacheWriteTokens")),
            (("轮次", "输出", "思考") if chinese else ("Turn", "Output", "Thinking"), ("outputTokens", "thinkingTokens")),
        ):
            lines.extend(["", "| " + " | ".join(headers) + " |", "|" + "---:|" * len(headers)])
            for row in group["rows"]:
                values = [f'{row[field]:.3f}' if field.endswith("Seconds") else str(row[field]) for field in fields]
                lines.append(f'| {row["turn"]} | ' + " | ".join(values) + " |")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def pages(result):
    matrix = read_json(ROOT / "data/matrix.json")
    groups = result["groups"]
    output = {}
    for chinese in (False, True):
        suffix = "_CN" if chinese else ""
        language = "zh" if chinese else "en"
        readme_name = f"README{suffix}.md"
        other = "README.md" if chinese else "README_CN.md"
        title = "Claude on Foundry：thinking、缓存与首字延迟" if chinese else "Claude on Foundry: Thinking, Prompt Caching and First-Text Latency"
        purpose = "本项目把模型 thinking、缓存覆盖范围和客户端首字等待分开测量，避免把 HTTP 200、已开启流式或缓存标记存在当成性能达标。提供三模型的固定五轮输入、流式采集器、十组实际结果和离线验算。" if chinese else "Measure thinking mode, cache coverage and client-visible waiting separately. A successful HTTP response, streaming flag or cache marker is not a performance acceptance test. This project provides a fixed five-turn workload, a streaming collector, ten measured configurations and independent offline verification."
        limits = "这是一次固定资料问答实验，不是客户生产负载。没有答案质量评分、并发压测、AWS 对照或其他 effort 档位排名。" if chinese else "This is one fixed source-review workload, not customer production traffic. There is no answer-quality score, concurrent load test, AWS comparison or effort-level ranking."
        headings = ("目的", "操作步骤", "实现效果") if chinese else ("Purpose", "Steps", "Results")
        effect = f'2026-10-24 的原实验 **{result["requests"]}/50 正常完成**，按当时记录费率估算的模型费用为 **US${result["costUsd"]:.8f}**。每个缓存配置各有五轮；下表是历史实测，不是读者新运行的结果或当前价格。首字为发送请求到第一个非空 text_delta；P50 为五轮中位数。' if chinese else f'The recorded experiment on 2026-10-24 completed **{result["requests"]}/50 requests**. Model cost at its recorded rates: **US${result["costUsd"]:.8f}**. Each cache configuration has five turns. These are historical measurements, not a reader\'s new run or current prices. First text spans client send to the first nonempty text_delta; P50 is the median of five turns.'
        not_guarantee = "关闭模式在无工具任务中均为零 thinking token。Sonnet 的 between_tools 不是所有场景下的完全关闭；Opus 5.5 不支持关闭。P95 在五个样本下等于最大值，不代表生产尾延迟。" if chinese else "The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate."
        cache_explanation = ("缓存读取占比统计同一配置全部五轮：读取 token 总和 /（未缓存、写入、读取 token 总和）。首轮写入也在分母里，不算命中；新问题和新增历史仍需处理。仅系统前缀只复用固定资料，系统与历史额外启用随会话增长的自动缓存。这里不是末轮命中率，也不是平均每轮百分比。"
                     if chinese else "Cache-read share covers all five turns: total read tokens / (total uncached + written + read input tokens). Initial writes enter the denominator but are not hits; new prompts and history still need processing. System only reuses the fixed source; System + history also enables growing automatic conversation caching. This is neither last-turn hit rate nor the mean of per-turn percentages.")
        output[readme_name] = f'''# {title}

[![LiteLLM 1.106.2](https://img.shields.io/badge/LiteLLM-1.106.2-0078D4)](deploy/Dockerfile)
[![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](requirements.txt)
[![Claude 5.5](https://img.shields.io/badge/Claude-5.5-555555?logo=anthropic&logoColor=white)](data/matrix.json)
[![david-share stars](https://img.shields.io/github/stars/david-xinyuwei/david-share?style=flat&logo=github&label=david-share%20stars)](https://github.com/david-xinyuwei/david-share/stargazers)

{'作者' if chinese else 'Author'}: Xinyu Wei · [{'English' if chinese else '中文'}]({other})

{'Stars 属于整个 david-share 仓库，不代表本目录。' if chinese else 'Stars belong to the whole david-share repository, not this directory.'}

## {headings[0]}

{purpose}

{limits}

{'原实验为真实模型调用；本次公开包装的全新云部署未运行。离线核验不代表部署通过。' if chinese else 'The recorded experiment used real model calls. A fresh deployment of this public package has not been run; offline checks are not deployment proof.'}

<img src="images/architecture-{language}.svg" width="440" alt="{'实测网关路径与客户端计时位置' if chinese else 'Measured gateway path and client timing points'}" />

{'原创解释图。客户端负责提问、历史和计时；LiteLLM 负责协议及身份转发；模型服务负责生成与缓存。图只解释连接，不证明运行结果。' if chinese else 'Original explanatory diagram. The client owns prompts, history and timing; LiteLLM owns protocol and identity forwarding; model serving owns generation and caching. Connections explain the design, not execution proof.'} [Azure icons](images/icon-sources.json) · [Runtime](evidence/provenance.json)

{'自适应思考对应 adaptive；Sonnet 的无前置思考对应 between_tools，Haiku 的关闭思考对应 disabled。调用始终保留流式。' if chinese else 'Adaptive uses adaptive; Sonnet without up-front thinking uses between_tools, and Haiku with thinking off uses disabled. Streaming remains enabled in every case.'}

## {headings[1]}

{deployment_steps(chinese)}

## {headings[2]}

{effect}

**{'首个可见文本 P50，单位：秒' if chinese else 'First visible text P50, seconds'}**

{comparison_table(groups, 'ttftSeconds', chinese)}

**{'全部五轮的缓存读取占比，单位：%' if chinese else 'Cache-read share across all five turns, %'}**

{cache_explanation}

{comparison_table(groups, 'cacheReadSharePercent', chinese, 2)}

{not_guarantee}

{'更高缓存占比不等于全部首字改善来自缓存：各会话独立生成，历史和 thinking 用量随之变化。所有计时在客户端，未分离服务端排队、网络和推理计算。' if chinese else 'Higher cache share does not attribute all first-text improvements to caching: conversations generate independently, changing history and thinking usage. All timing is client-side; server queues, network time and model compute are not isolated.'}

| {'想要' if chinese else 'Goal'} | {'入口' if chinese else 'Read'} |
|---|---|
| {'查看逐轮与分段计时' if chinese else 'Inspect per-turn and timing results'} | [{'实测结果' if chinese else 'Results'}](docs/results{suffix}.md) |
| {'核验、复测与限制' if chinese else 'Verify, reproduce and understand limits'} | [{'复测与核验' if chinese else 'Testing'}](docs/testing{suffix}.md) |

{'目录' if chinese else 'Directories'}: [deploy](deploy/), [scripts](scripts/), [data](data/), [evidence](evidence/), [images](images/), [tests](tests/). [Dependencies](requirements.txt).
'''
        intro = "本轮比较关闭回答前的 thinking，以及扩大缓存覆盖范围，是否改变首个可见回答的等待。下面是实际发送的五个问题原文；所有配置使用同一材料和顺序。" if chinese else "This run asks whether disabling up-front thinking and extending cache coverage changes time to the first visible answer. The five prompts below are verbatim inputs; every configuration uses the same source material and order."
        questions = "\n\n".join(f'{index}. {question}' for index, question in enumerate(matrix["questions"], 1))
        output[f"docs/results{suffix}.md"] = f'''# {'实测结果' if chinese else 'Measured Results'}

[README](../{readme_name}) · [{'复测与核验' if chinese else 'Testing'}](testing{suffix}.md) · [{'English' if chinese else '中文'}](results{'' if chinese else '_CN'}.md)

## {'输入与方法' if chinese else 'Inputs and Method'}

{intro}

{questions}

[{'完整材料与矩阵' if chinese else 'Complete material and matrix'}](../data/matrix.json)

{'五种合法模型/模式组合，各做两种缓存配置，每组独立五轮。固定 medium、stream=true、max_tokens=4096、无工具、零重试、单请求串行。首先执行 system-only 阶段，再执行会话缓存阶段；未清缓存，也没有额外预热。两阶段的模型执行顺序均为 Haiku disabled、Sonnet between_tools、Opus adaptive、Sonnet adaptive、Haiku adaptive。后续历史来自各组自己的响应，不保证逐字相同。' if chinese else 'Five valid model/mode combinations, two cache configurations and five dependent turns per cell. Fixed medium, stream=true, max_tokens=4096, no tools, no retries and one in-flight request. System-only ran before conversation caching; no cache flush or extra pre-warming. Both phases used Haiku disabled, Sonnet between_tools, Opus adaptive, Sonnet adaptive, then Haiku adaptive. Later histories come from each cell itself and are not byte-identical across cells.'}

{'上述顺序属于原实验。公开运行器按 matrix.json 中的 case 顺序执行，默认顺序不同；新报告只描述自己的运行，不作为原实验的精确重演。' if chinese else 'That order belongs to the recorded experiment. The public runner uses the case order in matrix.json, whose default differs. A new report describes its own run, not an exact replay of the historical execution order.'}

## {'观察结果' if chinese else 'Observed Results'}

<img src="../images/latency-{language}.svg" width="520" alt="{'每组五次请求的首个可见文本时间分布' if chinese else 'First-text timing of five requests per configuration'}" />

{'图由本轮 50 条记录生成：每个圆点是一次请求，横轴为秒；纵向小偏移仅区分轮次，没有数值含义。蓝色为自适应思考，绿色为无前置思考。不是质量排名。' if chinese else 'Generated from the 50 recorded requests: each dot is one request and the horizontal axis is seconds. Small vertical offsets only distinguish turns and carry no metric value. Blue is adaptive; green has no up-front thinking. This is not a quality ranking.'} [Source](../evidence/requests.json)

{'首字与缓存摘要在 README；以下完整保留十组的其他指标。每格五轮，输出吞吐包含思考，可见输出吞吐则扣除 thinking tokens；两者均除以完整 E2E，不是独立解码速度。' if chinese else 'First-text and cache summaries are in the README. The following tables retain the other metrics for all ten configurations. Each cell covers five turns. Output rate includes thinking; visible rate subtracts thinking tokens. Both divide by full E2E, not isolated decode time.'}

**{'完整结束 P50，秒' if chinese else 'Full completion P50, seconds'}**

{comparison_table(groups, 'e2eSeconds', chinese)}

**{'输出 P50，token/秒，含思考' if chinese else 'Output P50, tokens/s, including thinking'}**

{comparison_table(groups, 'outputTokensPerSecond', chinese, 2)}

**{'可见输出 P50，token/秒' if chinese else 'Visible output P50, tokens/s'}**

{comparison_table(groups, 'visibleTokensPerSecond', chinese, 2)}

**{'模型估算费用，美元' if chinese else 'Estimated model cost, USD'}**

{comparison_table(groups, 'costUsd', chinese, 6)}

## {'分段时间' if chinese else 'Timing Boundaries'}

{'所有时间从客户端发出请求起算。Headers 是完整响应头到达，First body byte 是响应正文首 byte，不是完整 HTTP 首 byte。First SSE 包括 metadata/heartbeat，不等于可见回答。thinking 事件到达不等于推理开始；omitted 模式可能延后或合并事件。Post-SSE wait 是逐请求相减后取 P50，不是两个 P50 相减。' if chinese else 'Times start at client send. Headers means completed response headers; first body byte is the first response-body byte, not the first byte of the HTTP exchange. First SSE can be metadata/heartbeat, not visible text. A thinking event does not mark the start of model compute; omitted display can defer or group events. Post-SSE wait is computed per request before taking P50, not by subtracting medians.'}

## {'逐轮记录' if chinese else 'Per-Turn Records'}

{'下列总输入、读取、写入、输出和思考列单位均为 token；总输入等于未缓存 + 读取 + 写入，可见输出等于输出 - 思考。完整回答、请求及事件时间在证据文件内。每组 P95 为五轮中的最大值。' if chinese else 'Total input, read, written, output and thinking columns are token counts. Total input = uncached + read + written; visible output = output - thinking. Full requests, responses and event timing are in the evidence file. Each P95 is the maximum of five turns.'}

{detailed_tables(groups, chinese)}

## {'结论边界与来源' if chinese else 'Limits and Sources'}

{limits} {not_guarantee}

{'Sonnet adaptive 的两组分别只有 3/5 与 2/5 请求产生 thinking；不能把其首字变化全部归因缓存。关闭 thinking 后的回答更短或推理步骤更少也可能影响结果，尚未证明质量等价。' if chinese else 'Sonnet adaptive produced thinking in 3/5 and 2/5 requests in the two cache groups. Its latency difference cannot all be attributed to caching. Shorter answers or reduced reasoning can also affect timing; quality equivalence was not established.'}

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)
'''
        output[f"docs/testing{suffix}.md"] = f'''# {'复测与核验' if chinese else 'Testing and Reproduction'}

[README](../{readme_name}) · [{'实测结果' if chinese else 'Results'}](results{suffix}.md) · [{'English' if chinese else '中文'}](testing{'' if chinese else '_CN'}.md)

## {'离线核验' if chinese else 'Offline Verification'}

{'不需要 Azure 或模型密钥；Python 标准库即可。' if chinese else 'No Azure or model key is required. Uses the Python standard library.'}

```powershell
python -B scripts/analyze.py --check
python -B scripts/render_docs.py --check
python -B -m unittest discover -s tests -v
./scripts/run_matrix.ps1 -RunDirectory live-runs/offline -ValidateOnly
```

{'预期旧证据核验为 50 条记录、10 个配置，生成产物一致，单元测试通过。没有 PowerShell 7 时运行器测试会显示 skipped，不算该路径已通过。负例使用内存或隔离测试副本：改 token、thinking、问题、计时，移除 trace、重复 call ID 或截断流；不修改原始证据。合成 SSE 和测试传输替身仅验证采集/分析逻辑，不作为新的模型性能证据。' if chinese else 'Expect 50 published records and 10 configurations, matching generated files and passing unit tests. Without PowerShell 7 the runner tests are skipped, not validated. Negative tests alter in-memory or isolated test copies: tokens, thinking, prompts, timing, missing traces, duplicate call IDs or truncated streams. Originals remain unchanged. Synthetic SSE and test transport substitutes validate collector/analysis logic only, never new model-performance evidence.'}

## {'实际调用的验收' if chinese else 'Live Acceptance'}

{'主部署、日志采集和新运行命令统一在 README 第 1–6 步。run_matrix.ps1 保存原始响应；analyze.py --run-directory 必须同时给出 --trace-file，并按 x-litellm-call-id 核对出站模型、thinking、effort、stream、max_tokens 和缓存断点。它读取指定目录的 matrix.json、run.json、冻结采集器和 ACA_HTTP_*.json，重建 SSE、累计 usage 和完整历史；不会回退到已发布证据。日志缺失时失败，原 run.json 保持待审计状态。' if chinese else 'Deployment, log capture and fresh-run commands have one owner: README steps 1-6. run_matrix.ps1 saves raw responses. analyze.py --run-directory also requires --trace-file and correlates outbound model, thinking, effort, stream, max_tokens and cache markers by x-litellm-call-id. It reads that directory\'s matrix.json, run.json, frozen collector and ACA_HTTP_*.json, reconstructing SSE, cumulative usage and history. It never falls back to published evidence. Missing logs fail; the original run.json stays pending audit.'}

{'trace 输入支持观察器原始 JSON/JSONL、控制台 CLAUDE_PROVIDER_TRACE 文本和 Azure CLI 的 Log 字段 JSONL；重复的完全相同日志会合并，同一 call ID 内容冲突则失败。其他运行的日志数量单独报告；不会拿它们补齐当前请求。analysis.json 和 analysis.md 是同一目录的派生输出，重新分析只更新它们；--check 不写文件。私有文件中的真实签名用于本次核验，不写入 Markdown 报告。' if chinese else 'Trace input accepts observer JSON/JSONL, CLAUDE_PROVIDER_TRACE console text and Azure CLI JSONL with a Log field. Identical duplicate log entries merge; conflicting content for one call ID fails. Unrelated calls are counted separately and cannot replace current requests. analysis.json and analysis.md are derived files in the same directory; reanalysis updates only these outputs, while --check writes nothing. Actual private signatures are validated but not written into the Markdown report.'}

{'必须同时检查：HTTP 200、end_turn、message_stop、非空回答、完整 usage、历史原样追加，以及关闭模式的零 thinking token。首轮缓存状态按 usage 判断，不凭新会话 ID 判冷。' if chinese else 'Check HTTP 200, end_turn, message_stop, nonempty text, complete usage, append-only history and zero thinking tokens for off modes. Classify first-turn cache state from usage, not a new session ID.'}

{'输入缓存读取占比 = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens)。输出吞吐 = output_tokens/E2E；另列减去 thinking 的可见输出吞吐。nearest-rank 分位方法不插值，N=5 时 P95=max。' if chinese else 'Cache-read share = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens). Output throughput = output_tokens/E2E; visible output throughput subtracts thinking tokens. Percentiles use nearest-rank without interpolation; at N=5, P95=max.'}

## {'安全、支持与未验证项' if chinese else 'Security, Support and Gaps'}

{'真实输入、模型回答、签名及认证信息可能敏感。live-runs 与 .env 已忽略；不要上传运行目录。公开证据的签名已省略，call ID 已假名化，因此不能拿公开证据的历史重放签名；新运行必须使用自己的真实响应。' if chinese else 'Live inputs, responses, signatures and authentication can be sensitive. live-runs and .env are ignored; do not upload them. Published signatures are omitted and call IDs pseudonymized. Do not replay published history signatures; a live run must carry its own actual responses.'}

{'Opus 5.5 不支持 disabled。Sonnet 5.5 使用 between_tools，Haiku 5.5 使用 disabled，且这两种模式仅接受 low/medium/high。temperature、top_p、top_k 不作为本轮可调项；未验证的服务端工具或 beta 参数不加入默认配置。' if chinese else 'Opus 5.5 does not accept disabled. Sonnet 5.5 uses between_tools and Haiku 5.5 uses disabled; these modes accept low/medium/high only. temperature/top_p/top_k are not tuning axes in this run. Unverified server tools or beta parameters are not enabled by default.'}

{'公开采集器只去除了作者认证入口和资源默认值，测量循环保持与实测版本一致。它的语法、离线请求及数据测试已验证；公开包装的独立新部署未执行，没有录制公开视频，也没有客户桌面客户端验收。' if chinese else 'The public collector removes author-specific authentication and resource defaults while preserving the measured loop. Syntax, offline request construction and data tests are verified. A standalone fresh deployment of the public packaging was not executed; there is no public demo recording or customer desktop-client acceptance.'}

{'部署命令的官方依据（2026-10-25 查阅）' if chinese else 'Deployment command references (consulted 2026-10-25)'}:
[Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest) · [Managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) · [Model deployments CLI](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account/deployment?view=azure-cli-latest) · [Claude in Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)
'''
        output[f"images/architecture-{language}.svg"] = architecture(chinese)
        output[f"images/latency-{language}.svg"] = latency_chart(groups, chinese)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = pages(validate())
    for name, content in rendered.items():
        path = ROOT / name
        expected = content.rstrip() + "\n"
        if args.check:
            require(path.is_file() and path.read_text(encoding="utf-8") == expected, "Rendered output drift: " + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "PASS", "artifacts": len(rendered), "mode": "check" if args.check else "write"}))


if __name__ == "__main__":
    main()