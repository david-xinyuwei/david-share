import argparse
import html
import json
import math

import coding_data
import render_coding
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
        ("成功时 ACR Tasks 构建完成，image 为带 SHA-256 digest 的镜像地址。Dockerfile 里的 LiteLLM 基础镜像已固定版本。这套公开包装还没有从头构建并部署过一次。"
         if chinese else "Success is a completed ACR Tasks build and an image address with a SHA-256 digest. The LiteLLM base image in the Dockerfile is pinned. This public package has not yet been built and deployed from scratch."),
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
        ("回到第一个终端运行。固定十组、每组五轮、medium、流式、零重试，最多 50 次请求；2026-10-24 这样一轮按当时费率约 0.79 美元。调用前核对最新价目；模型费用之外，Container App、镜像仓库和日志另行计费。"
         if chinese else "Return to the first terminal. The frozen matrix has ten configurations of five turns, medium effort, streaming and no retries: at most 50 requests. The 2026-10-24 run cost about US$0.79 at its recorded rates; check current prices before calling. The Container App, registry and logs are billed separately."),
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
        lines = [f"#### {label}", "", f"`{case_id}`", "",
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


def gateway_results(result, chinese):
    groups = result["groups"]
    matrix = read_json(ROOT / "data/matrix.json")
    language = "zh" if chinese else "en"
    questions = "\n\n".join(f'{index}. {question}' for index, question in enumerate(matrix["questions"], 1))
    not_guarantee = "关闭模式在无工具任务中均为零 thinking token。Sonnet 的 between_tools 不是所有场景下的完全关闭；Opus 5.5 不支持关闭。P95 在五个样本下等于最大值，不代表生产尾延迟。" if chinese else "The no-up-front-thinking modes produced zero thinking tokens in this tool-free workload. Sonnet between_tools is not a universal full-off switch; Opus 5.5 cannot disable thinking. With five samples, P95 is the maximum, not a production-tail estimate."
    cache_explanation = ("缓存读取占比统计同一配置全部五轮：读取 token 总和 /（未缓存、写入、读取 token 总和）。首轮写入也在分母里，不算命中；新问题和新增历史仍需处理。仅系统前缀只复用固定资料，系统与历史额外启用随会话增长的自动缓存。这里不是末轮命中率，也不是平均每轮百分比。"
                         if chinese else "Cache-read share covers all five turns: total read tokens / (total uncached + written + read input tokens). Initial writes enter the denominator but are not hits; new prompts and history still need processing. System only reuses the fixed source; System + history also enables growing automatic conversation caching. This is neither last-turn hit rate nor the mean of per-turn percentages.")
    return f'''## {'网关测试' if chinese else 'Gateway test, 2026-10-24'}

{'**问题。** 经过 LiteLLM 网关时，关闭回答前的思考、扩大缓存覆盖范围，是否改变首个可见文字的等待？（2026-10-24）' if chinese else '**Question.** Through a LiteLLM gateway, does disabling up-front thinking or extending cache coverage change the time to the first visible text?'}

{'**拓扑。** Windows 客户端（PowerShell 7.6.7，位置未记录）→ Japan East 的 Azure Container Apps 上的 LiteLLM 1.106.2（1 vCPU、2 GiB、单副本、单 worker，用托管身份）→ East US 2 的 Foundry 资源。网关和模型不在同一区域，所以下面的时间包含日本到美国东部的往返，不能代表网关本身增加的延迟。' if chinese else '**Topology.** A Windows client (PowerShell 7.6.7, location not recorded) → LiteLLM 1.106.2 on Azure Container Apps in Japan East (1 vCPU, 2 GiB, one replica, one worker, managed identity) → the Foundry resource in East US 2. The gateway and the models were in different regions, so the times below include a round trip between Japan and the eastern United States and do not measure the gateway\'s own overhead.'}

### {'输入与方法' if chinese else 'Input and method'}

{'下面是实际发送的五个问题原文；所有配置使用同一材料和顺序。' if chinese else 'The five prompts below are verbatim inputs; every configuration uses the same source material and order.'}

{questions}

[{'完整材料与矩阵' if chinese else 'Complete material and matrix'}](../data/matrix.json)

{'五种合法模型/模式组合，各做两种缓存配置，每组独立五轮。固定 medium、stream=true、max_tokens=4096、无工具、零重试、单请求串行。先执行仅系统前缀阶段，再执行会话缓存阶段；未清缓存，也没有额外预热。两阶段的模型执行顺序均为 Haiku disabled、Sonnet between_tools、Opus adaptive、Sonnet adaptive、Haiku adaptive。后续历史来自各组自己的响应，不保证逐字相同。公开运行器按 matrix.json 中的顺序执行，与这次的执行顺序不同。' if chinese else 'Five valid model/mode combinations, two cache configurations and five dependent turns per cell. Fixed medium, stream=true, max_tokens=4096, no tools, no retries and one in-flight request. System-only ran before conversation caching; no cache flush or extra pre-warming. Both phases used Haiku disabled, Sonnet between_tools, Opus adaptive, Sonnet adaptive, then Haiku adaptive. Later histories come from each cell itself and are not byte-identical across cells. The public runner follows the case order in matrix.json, which differs from this execution order.'}

### {'观察结果' if chinese else 'Observed results'}

{f'2026-10-24 的原实验 **{result["requests"]}/50 正常完成**，按当时记录费率估算的模型费用为 **US${result["costUsd"]:.2f}**。首字为发送请求到第一个非空 text_delta；P50 为五轮中位数。' if chinese else f'The recorded experiment on 2026-10-24 completed **{result["requests"]}/50 requests**; model cost at its recorded rates was **US${result["costUsd"]:.2f}**. First text spans client send to the first nonempty text_delta; P50 is the median of five turns.'}

<img src="../images/latency-{language}.svg" width="520" alt="{'每组五次请求的首个可见文字时间分布' if chinese else 'First-text timing of five requests per configuration'}" />

{'图由本轮 50 条记录生成：每个圆点是一次请求，横轴为秒；纵向小偏移仅区分轮次，没有数值含义。蓝色为自适应思考，绿色为无前置思考。不是质量排名。' if chinese else 'Generated from the 50 recorded requests: each dot is one request and the horizontal axis is seconds. Small vertical offsets only distinguish turns and carry no metric value. Blue is adaptive; green has no up-front thinking. This is not a quality ranking.'} [Source](../evidence/requests.json)

**{'首个可见文字 P50，单位：秒' if chinese else 'First visible text P50, seconds'}**

{comparison_table(groups, 'ttftSeconds', chinese)}

**{'全部五轮的缓存读取占比，单位：%' if chinese else 'Cache-read share across all five turns, %'}**

{cache_explanation}

{comparison_table(groups, 'cacheReadSharePercent', chinese, 2)}

{'输出吞吐包含思考，可见输出吞吐扣除 thinking tokens；两者均除以完整耗时，不是独立解码速度。' if chinese else 'Output rate includes thinking; visible rate subtracts thinking tokens. Both divide by full E2E time, not isolated decode time.'}

**{'完整结束 P50，秒' if chinese else 'Full completion P50, seconds'}**

{comparison_table(groups, 'e2eSeconds', chinese)}

**{'输出 P50，token/秒，含思考' if chinese else 'Output P50, tokens/s, including thinking'}**

{comparison_table(groups, 'outputTokensPerSecond', chinese, 2)}

**{'可见输出 P50，token/秒' if chinese else 'Visible output P50, tokens/s'}**

{comparison_table(groups, 'visibleTokensPerSecond', chinese, 2)}

**{'模型估算费用，美元' if chinese else 'Estimated model cost, USD'}**

{comparison_table(groups, 'costUsd', chinese, 6)}

{not_guarantee}

{'更高缓存占比不等于全部首字改善来自缓存：各会话独立生成，历史和 thinking 用量随之变化。Sonnet adaptive 的两组分别只有 3/5 与 2/5 请求产生 thinking。所有计时在客户端，未分离服务端排队、网络和推理计算。' if chinese else 'Higher cache share does not attribute all first-text improvements to caching: conversations generate independently, changing history and thinking usage. Sonnet adaptive produced thinking in 3/5 and 2/5 requests in the two cache groups. All timing is client-side; server queues, network time and model compute are not isolated.'}

### {'分段时间' if chinese else 'Timing boundaries'}

{'所有时间从客户端发出请求起算。Headers 是完整响应头到达，First body byte 是响应正文首 byte，不是完整 HTTP 首 byte。First SSE 包括 metadata/heartbeat，不等于可见回答。thinking 事件到达不等于推理开始；omitted 模式可能延后或合并事件。Post-SSE wait 是逐请求相减后取 P50，不是两个 P50 相减。' if chinese else 'Times start at client send. Headers means completed response headers; first body byte is the first response-body byte, not the first byte of the HTTP exchange. First SSE can be metadata/heartbeat, not visible text. A thinking event does not mark the start of model compute; omitted display can defer or group events. Post-SSE wait is computed per request before taking P50, not by subtracting medians.'}

### {'逐轮记录' if chinese else 'Per-turn records'}

{'下列总输入、读取、写入、输出和思考列单位均为 token；总输入等于未缓存 + 读取 + 写入，可见输出等于输出 - 思考。完整回答、请求及事件时间在证据文件内。每组 P95 为五轮中的最大值。' if chinese else 'Total input, read, written, output and thinking columns are token counts. Total input = uncached + read + written; visible output = output - thinking. Full requests, responses and event timing are in the evidence file. Each P95 is the maximum of five turns.'}

{detailed_tables(groups, chinese)}

### {'边界与来源' if chinese else 'Limits and sources'}

{'这是一次固定资料问答实验，不是客户生产负载。没有答案质量评分、并发压测或其他 effort 档位。关闭 thinking 后的回答更短或推理步骤更少也可能影响结果，尚未证明质量等价。' if chinese else 'This is one fixed source-review workload, not production traffic. There is no answer-quality score, concurrency test or other effort level. Shorter answers or reduced reasoning can also affect timing; quality equivalence was not established.'}

[Requests and responses](../evidence/requests.json) · [Summary](../evidence/summary.json) · [Provenance and hashes](../evidence/provenance.json)

[Claude thinking](https://platform.claude.com/docs/en/build-with-claude/thinking) · [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) · [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) · [LiteLLM v1.106.2 source](https://github.com/BerriAI/litellm/blob/v1.106.2/litellm/llms/anthropic/chat/transformation.py)'''


def gateway_testing(chinese):
    return f'''## {'重做 2026-10-24 的网关测试' if chinese else 'Repeat the 2026-10-24 gateway test'}

{'下面在新的 Container App 上部署 LiteLLM，并让十种配置的对话经过它。Container App 的区域请选 Foundry 资源所在区域：2026-10-24 的运行用的是 Japan East，所以它的时间包含跨区域往返。命令在 PowerShell 7.6 中运行。' if chinese else 'These steps deploy LiteLLM on a new Container App and send the ten-configuration conversation through it. Choose the Foundry resource\'s region for the Container App: the 2026-10-24 run used Japan East, so its times include a cross-region round trip. Commands run in PowerShell 7.6.'}

{deployment_steps(chinese)}

### {'核验新的一次运行' if chinese else 'Audit a new gateway run'}

{'run_matrix.ps1 保存原始响应；analyze.py --run-directory 必须同时给出 --trace-file，并按 x-litellm-call-id 核对出站模型、thinking、effort、stream、max_tokens 和缓存断点。它读取指定目录的 matrix.json、run.json、冻结采集器和 ACA_HTTP_*.json，重建 SSE、累计 usage 和完整历史；不会回退到已发布证据。日志缺失时失败，原 run.json 保持待审计状态。' if chinese else 'run_matrix.ps1 saves raw responses. analyze.py --run-directory also requires --trace-file and correlates outbound model, thinking, effort, stream, max_tokens and cache markers by x-litellm-call-id. It reads that directory\'s matrix.json, run.json, frozen collector and ACA_HTTP_*.json, reconstructing SSE, cumulative usage and history. It never falls back to published evidence. Missing logs fail; the original run.json stays pending audit.'}

{'trace 输入支持观察器原始 JSON/JSONL、控制台 CLAUDE_PROVIDER_TRACE 文本和 Azure CLI 的 Log 字段 JSONL；重复的完全相同日志会合并，同一 call ID 内容冲突则失败。其他运行的日志数量单独报告；不会拿它们补齐当前请求。analysis.json 和 analysis.md 是同一目录的派生输出；--check 不写文件。' if chinese else 'Trace input accepts observer JSON/JSONL, CLAUDE_PROVIDER_TRACE console text and Azure CLI JSONL with a Log field. Identical duplicate log entries merge; conflicting content for one call ID fails. Unrelated calls are counted separately and cannot replace current requests. analysis.json and analysis.md are derived files in the same directory; --check writes nothing.'}

{'必须同时检查：HTTP 200、end_turn、message_stop、非空回答、完整 usage、历史原样追加，以及关闭模式的零 thinking token。缓存读取占比 = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens)；分位数用最近秩法，N=5 时 P95=max。' if chinese else 'Check HTTP 200, end_turn, message_stop, nonempty text, complete usage, append-only history and zero thinking tokens for off modes. Cache-read share = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens); nearest-rank percentiles, so at N=5 P95 is the maximum.'}

{'部署命令的官方依据（2026-10-25 查阅）' if chinese else 'Deployment command references (consulted 2026-10-25)'}:
[Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest) · [Managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) · [Model deployments CLI](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account/deployment?view=azure-cli-latest) · [Claude in Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)'''


def security(chinese):
    return f'''## {'安全与未验证项' if chinese else 'Security and gaps'}

{'真实输入、模型回答、签名及认证信息可能敏感。live-runs、private、runs 与 .env 已忽略；不要上传运行目录。历史 coding-matrix-20261026 记录只替换了端点资源名和 VM 名称；新的 gateway-cache-20261026 是指标投影，保留数值但省略提示／回答正文、思考签名、私有端点和非区域响应头。各自的导出清单记录哈希与边界，不能把指标投影用于代码正确率评分。2026-10-24 的公开证据省略了签名，call ID 已假名化，不能拿它的历史重放签名。' if chinese else 'Live inputs, responses, signatures and authentication can be sensitive. live-runs, private, runs and .env are ignored; do not upload run directories. Historical coding-matrix-20261026 records replace only endpoint and VM names. New gateway-cache-20261026 records are a metrics projection: numbers are preserved but prompt/answer bodies, thinking signatures, private endpoints and non-region headers are omitted. Each export manifest records its hashes and scope; the metrics projection cannot score code correctness. The 2026-10-24 evidence omits signatures and pseudonymizes call IDs; do not replay its history signatures.'}

{'本轮 ACA 的 650 条请求和 624 份正式答案评分已收齐；失败和六条官方模糊标记保留。未验证：公开包装在全新订阅中的端到端部署、并发压测、Azure 以外的客户端、display: "summarized"、带工具的请求，以及客户自己的任务。评分环境版本是评分后采集，不是运行时遥测。' if chinese else 'All 650 ACA request records and grading outcomes for 624 measured answers are retained, including failures and six official ambiguous flags. Not verified: an end-to-end deployment in a fresh subscription, concurrency or load, a client outside Azure, display: "summarized", tool use, and customer tasks. Environment versions were collected after grading, not as in-run telemetry.'}'''


def pages(result):
    d = coding_data.load()
    output = {}
    for chinese in (False, True):
        suffix = "_CN" if chinese else ""
        language = "zh" if chinese else "en"
        readme_name = f"README{suffix}.md"
        other = "README.md" if chinese else "README_CN.md"
        if chinese:
            title = "Microsoft Foundry 上的 Claude 5.5：思考模式、推理档位、提示缓存、延迟与编码正确率"
            headings = ("目的", "实现效果", "操作步骤")
            anchors = ("#目的", "#实现效果")
            author = "作者：魏新宇 · [English](README.md)"
        else:
            title = "Claude 5.5 on Microsoft Foundry: Thinking, Effort, Prompt Caching, Latency and Coding Accuracy"
            headings = ("Purpose", "Results", "Steps")
            anchors = ("#purpose", "#results")
            author = "Author: Xinyu Wei · [中文](README_CN.md)"
        badges = "\n".join([
            f"[![Models](https://img.shields.io/badge/models-Opus%20%C2%B7%20Sonnet%20%C2%B7%20Haiku%205.5-0078D4)]({anchors[0]})",
            f"[![Measured](https://img.shields.io/badge/measured-2026--10--26%20to%2010--27-0078D4)]({anchors[1]})",
            "[![CI](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml/badge.svg)](https://github.com/david-xinyuwei/david-share/actions/workflows/claude-foundry-performance-ci.yml)",
        ])
        output[readme_name] = "\n\n".join([
            f"# {title}", badges, author,
            f"## {headings[0]}", render_coding.purpose(d, chinese, language),
            f"## {headings[1]}", render_coding.results(d, result, chinese),
            f"## {headings[2]}", render_coding.steps(d, chinese),
        ])
        nav_results = f"[README](../{readme_name}) · [{'复测与核验' if chinese else 'Testing'}](testing{suffix}.md) · [{'English' if chinese else '中文'}](results{'' if chinese else '_CN'}.md)"
        intro_results = ("先看本轮 East US 2 ACA 全量性能结果，再看 624 份正式答案的代码正确率；全部配置、失败和限制均保留。已取缔直连方案的历史编码矩阵、参数探测、缓存测试和早期网关检查放在后面，不与本轮混算。"
             if chinese else "Current East US 2 ACA performance comes first, followed by correctness for all 624 measured answers. Every configuration, failure and limitation is retained. Retired direct-VM matrix, probe, cache and earlier gateway evidence follow, without pooling runs.")
        output[f"docs/results{suffix}.md"] = "\n\n".join([
            f"# {'实测结果' if chinese else 'Measured Results'}", nav_results, intro_results,
            render_coding.gateway_snapshot(chinese, detailed=True),
            render_coding.results_page(d, chinese), gateway_results(result, chinese),
        ])
        nav_testing = f"[README](../{readme_name}) · [{'实测结果' if chinese else 'Results'}](results{suffix}.md) · [{'English' if chinese else '中文'}](testing{'' if chinese else '_CN'}.md)"
        intro_testing = ("本页给出离线核验、重做 2026-10-26 测试和重做 2026-10-24 网关测试的完整命令。部署三个模型和发出第一个请求见 README 的操作步骤。"
                         if chinese else "This page gives the complete commands for the offline checks, for repeating the 2026-10-26 tests and for repeating the 2026-10-24 gateway test. Deploying the three models and sending the first request are README steps 1 to 4.")
        output[f"docs/testing{suffix}.md"] = "\n\n".join([
            f"# {'复测与核验' if chinese else 'Testing and Reproduction'}", nav_testing, intro_testing,
            render_coding.gateway_snapshot_replay(chinese),
            render_coding.testing_offline(chinese), render_coding.testing_repeat(d, chinese),
            gateway_testing(chinese), security(chinese),
        ])
        output[f"images/topology-{language}.svg"] = render_coding.topology(d, chinese)
        output[f"images/latency-{language}.svg"] = latency_chart(result["groups"], chinese)
        output[f"images/parameter-support-{language}.svg"] = render_coding.support_figure(d, chinese)
        output[f"images/cache-settings-{language}.svg"] = render_coding.cache_settings_figure(d, chinese)
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