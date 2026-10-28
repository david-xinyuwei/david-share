# 复测与核验

[README](../README_CN.md) · [实测结果](results_CN.md) · [English](testing.md)

首页拥有当前 ACA 矩阵的执行顺序。本页区分离线复算、新答案评分、网关部署与独立透传诊断，并保留历史直连命令。每条路径只证明自己的阶段；离线通过不代表新部署、重新推理或生产验收。

<a id="aca-snapshot-replay"></a>

## 复算 ACA 全量结果

在仓库的本项目目录，用 Python 3.12 或 3.13 执行。下列离线命令不发送请求，也不需要凭据：

```bash
python -B gateway-cache/analyze_cache_matrix.py --run-dir evidence/gateway-cache-20261026 --out evidence/gateway-cache-20261026/interim-facts.json --check
python -B gateway-cache/swebench_score.py check-public --out evidence/gateway-score-20261027 --inference-dir evidence/gateway-cache-20261026
```

预期先输出 `facts match`，再输出 status PASS、denominator 624、resolved 245，退出码均为 0。这是在复算已保存指标与官方判定，不生成新答案、不重跑 Docker。缓存命中性能用 302 组配对，正确率保留每一份正式答案。

### 对公开补丁重新执行官方测试

在可访问 Docker 的 Linux x86-64 机器上，从本项目目录执行；磁盘须能容纳数据集的 12 个镜像。新建 run_id 前缀，避免误用旧评分缓存。这会真实测试公开的模型补丁，不重新调用模型；机器运行和镜像存储可能计费。原评分使用 Python 3.12.3、2 个并发 worker，每题超时 1,800 秒。

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

52 批各应生成 `logs/evaluation/<run_id>/results.json`。查看解决、未解决、空补丁和错误 ID，不能只看 CLI 退出码。补丁应用失败属于模型输出结果；基础设施失败应排查后复评同一份冻结补丁。对照[官方原始报告](../evidence/gateway-score-20261027/logs/evaluation)与[预测哈希](../evidence/gateway-score-20261027/manifest.json)。本次文档更新未在全新机器重跑这些公开命令。

## 离线检查

不需要 Azure 权限或模型密钥。在本目录用 Python 3.12 或 3.13 运行；流解析测试还需要客户端依赖包。

**Windows 先做一步。** `evidence/gateway-score-20261027/logs/` 下官方 SWE-bench 报告的路径超过 260 个字符。克隆前先启用长路径，否则检出不完整、`check-public` 会失败：`git clone -c core.longpaths=true https://github.com/david-xinyuwei/david-share.git`，或一次性执行 `git config --global core.longpaths true`。CI 设了同样的选项；Linux 和 macOS 不需要。

```bash
python -m pip install -r coding-matrix/requirements.txt
python -B coding-matrix/analyze.py --run-dir evidence/coding-matrix-20261026/matrix --check
python -B coding-matrix/cache_analyze.py --run-dir evidence/coding-matrix-20261026/cache --check
python -B scripts/analyze.py --check
python -B scripts/render_docs.py --check
python -B -m unittest discover -s tests -v
```

每条命令都以 0 退出、每个检查都输出 `"status": "PASS"`、测试最后输出 `OK`，即为通过。

- **`coding-matrix/analyze.py --check`** 用 2026-10-26 的运行记录重新计算每格、按题目和按语言的计数以及自助区间，与 `facts.json` 不一致即失败。
- **`coding-matrix/cache_analyze.py --check`** 对缓存测试和 `cache_facts.json` 做同样的检查。
- **`scripts/analyze.py --check`** 核验 2026-10-24 的网关记录：哈希、每个请求的出站日志、对话历史、token 计数和时间顺序。
- **`scripts/render_docs.py --check`** 如果 README、结果页、复测页或图与按证据重新生成的结果不同就失败。
- **测试** 还会检查导出清单的哈希、题目清单与实测提示是否一致、评分器的文件提取、流解析器在本地测试服务器下的行为（完整、截断、HTTP 429 和 `max_tokens` 的流）、篡改运行记录后检查会失败、没有公开私有名称或地址，以及装有 PowerShell 7 时的网关采集器。本地服务器只测试解析逻辑，不是关于 Foundry 的证据。

CI 在 Ubuntu 和 Windows 上用 Python 3.12 和 3.13 运行同样的检查（[workflow](https://github.com/david-xinyuwei/david-share/blob/master/.github/workflows/claude-foundry-performance-ci.yml)）。

<a id="fresh-aca-analysis"></a>

## 分析和评分新的 ACA 运行

输入重建、缓存检查与采集按首页执行；WORK、RUN、RUN_ID 指向本次私有目录。`analyze_cache_matrix.py --run-dir` 读取该次响应及已记录重试，不回退到已发布快照。采集完整仍可能有截断和错误答案。参数记录在模型别名转换之前，不是 provider 出站抓包。

**出站审计单独进行。** 网关部署章节的 50 请求诊断使用 `run_matrix.ps1` 和 `scripts/analyze.py --run-directory --trace-file` 逐条关联调用。它与 650 请求编码矩阵是不同工作负载。编码矩阵分析器不执行该 trace 关联；新采集时保留原生网关日志，不能把尚未实现的关联审计标为通过。

**评分新生成的答案，不使用公开指标投影。** 在可使用 Docker、磁盘足够容纳题目镜像的 Linux x86-64 环境中执行，复用兼容 Python 环境。本阶段会下载官方数据和镜像并运行测试，不调用模型，但消耗计算资源。驱动在 prepare 时冻结官方评分集；下方检查要求与已发布分数使用同一数据集版本。不一致时须另行限定评测范围，不能继续冒充同口径比较。

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

prepare 必须保留全部正式答案，只排除预热。完整协议应有 624 份答案、52 批，解决数没有预设值。读取本次 SCORE 的 score-summary.json、scored-responses.json 和 logs/evaluation 原生报告。NOT_GRADED 或 EVALUATION_ERROR 表示评分未完成，不能当成可静默删除的答案失败。本轮文档更新未在新云计算环境重跑这套命令。

<a id="gateway-setup"></a>

## 部署网关并核验透传

第 1-4 步在专用 Container App 上部署并检查 LiteLLM，完成后可回首页运行 650 请求矩阵。第 5-6 步是独立的 50 请求参数透传诊断，沿用 2026-10-24 的十组五轮工作负载，并非 650 请求矩阵。Container App 选择 Foundry 资源所在区域；要复现当前位置条件，使用 East US 2。历史诊断在 Japan East，时间包含跨区域往返。以下命令使用 PowerShell 7.6，部署环境不等于完成模型测试。

| 顺序 | 位置 | 操作 |
|---|---|---|
| 1 | 本机与 Foundry | 配置、登录、三个模型部署 |
| 2 | Azure CLI | 构建镜像和基础资源 |
| 3 | CLI 与 Portal | 身份、Secret、镜像和 Ingress |
| 4 | Portal 与本机 | revision 与元数据就绪 |
| 5 | 两个本机终端 | 保留日志并运行矩阵 |
| 6 | 本机 | 审计新运行、读取报告 |

以下主路径使用专用的新 Container App、ACR 和环境；不要将创建或停用步骤套到共享生产资源。需要 PowerShell 7.6、Python 3.13、Azure CLI，以及创建资源、运行 ACR Tasks、为指定资源分配角色和读取日志的权限。模型访问与 Marketplace 条款由订阅所有者确认。资源、构建、日志和模型调用可能计费，执行前确认预算。

**1. 设置上下文并部署模型**

先在 Foundry Portal 选择现有资源，或由有权限的用户创建资源并记录租户、订阅、资源组、资源名和 /anthropic 基础地址。然后在本项目目录启动 PowerShell。首次运行只输入一次非秘密配置；其他终端从 private/settings.json 读取。登录由用户在本机完成交互认证，不复制 token cache。

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

成功时显示所选 Foundry 资源。尚无资源时，在 Foundry Portal 创建资源并选择所需区域。在 **Discover → Models** 中分别选择 Opus 5.5、Sonnet 5.5、Haiku 5.5，进入 **Deploy → Custom settings**；首次部署由用户接受 Marketplace 条款。选 **Global** 与标为 **Hosted on Azure** 的版本 2，部署名分别为 claude-opus-5-5、claude-sonnet-5-5、claude-haiku-5-5；按已批准配额填写容量。待三个部署完成后，在 **Build → Models → Details** 核对名称、版本与 Target URI；baseUrl 只保留到 /anthropic。没有访问资格或配额就停在这一步，不换模型。

[Foundry provisioning and authentication](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#provisioning)

**2. 构建并固定镜像**

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

成功时 ACR Tasks 构建完成，image 为带 SHA-256 digest 的镜像地址。Dockerfile 里的 LiteLLM 基础镜像已固定版本。这套公开包装还没有从头构建并部署过一次。

**3. 配置身份、密钥和入口**

按微软系统分配身份流程，先以公开 quickstart 镜像创建无外部入口的临时 revision，再配置真实网关。临时镜像只用于取得身份，不是模型服务，也不进入测量。先解析其 digest，后续使用不可变地址。

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

在 Azure Portal 打开此 Container App，进入 **Application → Secrets → Add**，名称为 gateway-key，值由用户从自己的密码管理器输入；保存。保留原入口密钥，不在 CLI 参数、日志或 Git 中写明文。然后执行以下更新。

```powershell
az containerapp update --name $settings.app --resource-group $settings.group `
    --image $image --cpu 1 --memory 2Gi --min-replicas 1 --max-replicas 1 `
    --set-env-vars "FOUNDRY_ANTHROPIC_BASE=$($settings.baseUrl)" `
        'LITELLM_MASTER_KEY=secretref:gateway-key' 'PYTHONPATH=/app/claude-gateway' --output none
```

在 **Ingress** 启用来自外部的 HTTP 访问，目标端口 4000，关闭 Allow insecure connections；在 **IP security restrictions** 只允许 settings.clientCidr，并保存。不要添加 0.0.0.0/0。网关仍以入口密钥保护请求；调用 Foundry 使用该应用的 Managed Identity（托管身份），不是入口密钥。

[Managed-identity image pull](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull)

**4. 检查实际服务版本**

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

预期 METADATA_READY 并列出三个 standard 别名。该检查没有推理调用，不证明模型能成功回答。失败时查看 **Revision management** 和 **Log stream → System**，检查镜像拉取、角色传播和 Secret 引用后重做本步骤，不跳过就绪检查。

**5. 保存日志并运行矩阵**

先在第二个 PowerShell 终端切到同一项目目录，启动控制台日志流；记下输出的 TRACE_FILE 路径，终端保持打开。

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

回到第一个终端运行。固定十组、每组五轮、medium、流式、零重试，最多 50 次请求；2026-10-24 这样一轮按当时费率约 0.79 美元。调用前核对最新价目；模型费用之外，Container App、镜像仓库和日志另行计费。

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

预期 run.json 为 EXECUTED_PENDING_PROVIDER_TRACE_AUDIT，目录内有 50 份原始响应。结束后在日志终端按 Ctrl+C；日志来自一个 revision/replica/container，本路径固定单副本。如果日志流中断，保留文件并重新采集，不能用旧日志冒充缺失记录。运行器失败不自动重试或覆盖目录，先定位对应原始响应。

**6. 验收本次运行**

```powershell
$traceFile = Read-Host 'Full path of the console log captured for this run'
python -B scripts/analyze.py --run-directory $run --trace-file $traceFile
Get-Content -LiteralPath (Join-Path $run 'analysis.md')
```

预期 status=PASS、requests=50、providerCalls=50，analysis.json 与 analysis.md 的 run 对应本次目录。缺日志、错误模型、缺轮次、断流或 usage 不符会失败，不回退到仓库旧证据。多份日志可重复传 --trace-file；--check 只验算不写文件。

**升级、回滚与停用**：升级前读取并保存当前镜像 digest，更新为新 digest 后重复第 4 步；失败时用已保存的旧 digest 执行同一 update 命令并再次检查。单副本维护可能中断请求。Ctrl+C 仅停止客户端；容器临时文件可能在重启时丢失，先保留本地原始响应和 trace。只有资源所有者确认停止后，才在 Portal 的 Revision management 停用该专用应用所有 active revision，并核对副本为 0；ACR、环境和日志仍可能计费，按各自资源另行决定，不删除共享资源。

### 核验新的一次运行

run_matrix.ps1 保存原始响应；analyze.py --run-directory 必须同时给出 --trace-file，并按 x-litellm-call-id 核对出站模型、thinking、effort、stream、max_tokens 和缓存断点。它读取指定目录的 matrix.json、run.json、冻结采集器和 ACA_HTTP_*.json，重建 SSE、累计 usage 和完整历史；不会回退到已发布证据。日志缺失时失败，原 run.json 保持待审计状态。

trace 输入支持观察器原始 JSON/JSONL、控制台 CLAUDE_PROVIDER_TRACE 文本和 Azure CLI 的 Log 字段 JSONL；重复的完全相同日志会合并，同一 call ID 内容冲突则失败。其他运行的日志数量单独报告；不会拿它们补齐当前请求。analysis.json 和 analysis.md 是同一目录的派生输出；--check 不写文件。

必须同时检查：HTTP 200、end_turn、message_stop、非空回答、完整 usage、历史原样追加，以及关闭模式的零 thinking token。缓存读取占比 = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens)；分位数用最近秩法，N=5 时 P95=max。

部署命令的官方依据（2026-10-25 查阅）:
[Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest) · [Managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) · [Model deployments CLI](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account/deployment?view=azure-cli-latest) · [Claude in Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)

## 安全与未验证项

真实输入、模型回答、签名及认证信息可能敏感。live-runs、private、runs 与 .env 已忽略；不要上传运行目录。历史 coding-matrix-20261026 记录只替换了端点资源名和 VM 名称；新的 gateway-cache-20261026 是指标投影，保留数值但省略提示／回答正文、思考签名、私有端点和非区域响应头。各自的导出清单记录哈希与边界，不能把指标投影用于代码正确率评分。2026-10-24 的公开证据省略了签名，call ID 已假名化，不能拿它的历史重放签名。

本轮 ACA 的 650 条请求和 624 份正式答案评分已收齐；失败和六条官方模糊标记保留。未验证：公开包装在全新订阅中的端到端部署、并发压测、Azure 以外的客户端、display: "summarized"、带工具的请求，以及客户自己的任务。评分环境版本是评分后采集，不是运行时遥测。

<a id="historical-direct-procedure"></a>

## 历史直连步骤，仅供参考

**当前测试入口。** 新测试使用 [ACA 缓存运行器](../gateway-cache/aca_cache_matrix.py)及其[启动脚本](../gateway-cache/run.sh)，输入为 [12 道题清单](../data/gateway-cache-problems.json)。VM 客户端通过网关发送请求，并开启 `cache_control`；当前测试不使用旧直连客户端。

**已取缔的 VM 直连流程，仅供历史参考。** 以下命令记录旧证据的产生方式，不是当前部署或测试步骤，不能用于按 ACA 协议开展的新测试。历史流程和离线证据检查保留在 [docs/testing_CN.md](testing_CN.md)。

**执行边界：** 2026-10-26 的结果由这些脚本产生，所用 VM 由第 3 步的命令（换成我们自己的资源名）创建。仓库是事后整理的。整理后在同一台 VM 上用公开的 `claude_api.py`、`pricing.py` 和 `call_once.py` 运行了一次第 4 步：完成，HTTP 200，首个可见文字在 0.89 秒后出现（[记录](../evidence/coding-matrix-20261026/readme-step4.json)）。第 1 到 3 步还没有在全新订阅中重跑。

| 顺序 | 位置 | 操作 | 入口 |
|---|---|---|---|
| 1 | 装有 Azure CLI 的 Bash | 登录并填写资源名 | `az login` |
| 2 | Foundry 门户和 Azure CLI | 部署三个模型 | `az cognitiveservices account deployment create` |
| 3 | Azure CLI | 在同一区域创建 VM，并允许它的身份调用 Foundry | `az vm create`、`az role assignment create` |
| 4 | VM | 安装客户端并发一个请求 | [`coding-matrix/call_once.py`](../coding-matrix/call_once.py) |

**前提。** 装有 Azure CLI 的 Bash（我们用的是 2.91.0；Azure Cloud Shell 也可以）；位于提供 Claude 5.5 的区域的 Foundry 资源（这里是 East US 2）；部署模型、创建 VM 和在 Foundry 资源上分配角色的权限；Claude 5.5 配额；以及 Anthropic 模型的 Marketplace 条款，首次部署时由订阅所有者在门户中接受。模型调用、VM 和磁盘都会产生费用。

**1. 登录并填写资源名。** 填好五个值；`LOCATION` 是 Foundry 资源所在的区域。

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

成功时最后一条命令输出资源名和区域。失败时先核对订阅和资源名再继续。

**2. 部署三个模型。** capacity 的单位是每分钟千 token；这里用的是测试时的值（Opus 40，Sonnet 和 Haiku 各 80）。如果命令因 Marketplace 条款失败，先在 Foundry 门户部署一次该模型（**Discover → Models**，然后 **Deploy → Custom settings**，部署类型选 **Global**，版本 2），再重新运行命令。

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

成功时输出三行，都是 `GlobalStandard`、版本 `2`、`Succeeded`。没有配额就申请配额，不要换模型。测试客户端按这些容量控制发送速度（`bench.py` 和 `cache_test.py` 里的 `TPM`）；容量不同，重做测量前先改这两处。

**3. 在同一区域创建客户端 VM。** VM 带系统分配的托管身份；在 Foundry 资源上授予该身份 `Cognitive Services User`，它就能调用模型。`--nsg-rule NONE` 不开放任何入站端口：通过 Azure Bastion 连接（我们用的方式），或者添加一条只允许你自己 IP 的 SSH 规则。

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

成功时 `az vm create` 输出 `"powerState": "VM running"`，角色分配输出它的 JSON。新分配的角色可能要几分钟才生效。

**4. 安装客户端并发一个请求。** 在 VM 上运行。把 `FOUNDRY_ANTHROPIC_BASE` 设为你的资源以 `/anthropic` 结尾的端点。

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

成功时先输出回答，再输出一行类似 `{"status": "completed", "http_status": 200, "first_text_s": 0.8893, ...}` 的结果，退出码 0。HTTP 401 或 403：角色还没生效，或者分配到了别的资源上，稍等后重试。HTTP 400：模型不接受这个思考模式或推理档位（见第一张表）。HTTP 404：部署名或端点写错了。

**完成。** 三个部署已能用这里的参数回答同区域客户端的请求。要重做测量，按 [docs/testing_CN.md](testing_CN.md) 操作。

**只有在资源所有者同意后才删除资源；这不是部署步骤。** 每个代码块只删除一样东西，只运行需要的那一个。

删除客户端 VM 及其资源组（`az` 会要求确认）：

```bash
az group delete -n "$VM_RG"
```

删除三个模型部署：

```bash
for name in claude-opus-5-5 claude-sonnet-5-5 claude-haiku-5-5; do
  az cognitiveservices account deployment delete -g "$FOUNDRY_RG" -n "$FOUNDRY" --deployment-name "$name"
done
```

**仓库目录。** [`coding-matrix/`](../coding-matrix/) 客户端、参数探测、编码矩阵、评分、缓存测试和分析 · [`data/`](../data/) 实测题目清单和网关测试的对话 · [`evidence/coding-matrix-20261026/`](../evidence/coding-matrix-20261026/) 运行记录、汇总和来源 · [`evidence/`](../evidence/) 网关测试记录 · [`scripts/`](../scripts/) 网关采集、网关分析和页面生成 · [`deploy/`](../deploy/) 网关镜像 · [`images/`](../images/) 图和图标台账 · [`tests/`](../tests/) 离线测试（`python -B -m unittest discover -s tests -v`，CI 每次推送都会运行）· [`NOTICE.md`](../NOTICE.md) 第三方声明。

## 重做 2026-10-26 的测试

**开始之前。** 先完成本页历史直连步骤第 1 到 4 步。这些运行要花钱：按标价，我们的矩阵花了 $55.36，缓存测试 $6.70，参数探测 $0.05。`--budget-usd` 在达到上限时停止矩阵（默认 150）。客户端按 Opus 每分钟 40,000、Sonnet 和 Haiku 各 80,000 token 控制速率（`bench.py` 和 `cache_test.py` 里的 `TPM`）；容量不同就改这两处。以下命令都在 VM 的 `coding-matrix/` 目录运行。

**1. 准备 VM，构建评分镜像。** `vm_setup.sh` 安装 Docker 和客户端依赖，并克隆题库；Java 预热练习让 Gradle 能在镜像里离线运行。

```bash
cd ~/david-share/Agents/Claude-Foundry-LiteLLM-Performance/coding-matrix
bash vm_setup.sh
git -C ~/polyglot-benchmark checkout 7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f
cp -r ~/polyglot-benchmark/java/exercises/practice/affine-cipher judge/java-warmup
sudo docker build -t polyglot-judge:1 judge
export FOUNDRY_ANTHROPIC_BASE="https://<foundry-resource>.services.ai.azure.com/anthropic"
```

成功时 `vm_setup.sh` 输出 httpx 和 azure-identity 的版本以及每种语言的练习数，镜像构建最后输出 Python、Go、Rust、Node、Java 和 CMake 的版本。退出再重新登录一次，让当前用户不用 `sudo` 就能运行 `docker`，评分器需要这一点。

**2. 探测接受的取值。** 约 102 个请求。

```bash
~/venv/bin/python probe.py --out-dir runs/probe
```

成功时 `runs/probe/probe_summary.json` 列出接受的思考模式和推理档位，可与[我们的结果](../evidence/coding-matrix-20261026/probe/probe_summary.json)对比。列表不同说明部署的行为已与 2026-10-26 不同；矩阵会按你的列表运行。

**3. 重建实测题目。**

```bash
~/venv/bin/python prepare.py --ids ../data/coding-problems.json --out problems.json
```

成功时输出 18 行 `ACCEPT`。如果重建的提示与实测不同，或者参考答案在评分器里失败、未修改的待补全文件反而通过，脚本会停止。

**4. 运行编码矩阵和评分器。** 两者都在后台运行；评分器边收到回答边评分。

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

成功时每个请求在 `progress.log` 里有一行，结束时 `$RUN/run.json` 显示 `"status": "COMPLETED"`；我们的运行用了约五小时。如果到端点的 TCP 建连中位数达到 50 毫秒，`bench.py` 会立即退出，因为这说明客户端不在模型所在区域。要停止就结束两个进程（`pkill -f bench.py; pkill -f judge.py`）；用同一个 `RUN` 再运行这两条命令会续跑，并跳过已完成的请求。

**5. 分析运行结果。**

```bash
~/venv/bin/python analyze.py --run-dir "$RUN"
```

成功时输出 21 行的表格，并生成字段与[我们的](../evidence/coding-matrix-20261026/matrix/facts.json)相同的 `$RUN/facts.json`。回答不是确定的，延迟随负载变化，数字会不同；请与我们的区间比较，而不是与单个数值比较。

**6. 运行提示缓存测试。** 在矩阵结束后启动，或者加上 `--wait-run-dir "$RUN"`，让每个模型在自己的矩阵请求结束后再开始。空闲场景要等 6.5 分钟。

```bash
CACHE=runs/cache-$(date -u +%Y%m%d-%H%M%S)
HTTPX_DIR=$(~/venv/bin/python -c "import httpx, os; print(os.path.dirname(httpx.__file__))")
~/venv/bin/python cache_test.py --out-dir "$CACHE" --package-dir "$HTTPX_DIR" --repetitions 2
~/venv/bin/python cache_analyze.py --run-dir "$CACHE"
```

成功时 `cache_analyze.py` 每个场景的每一轮输出一行；httpx 为 0.28.1 时，`$CACHE/context.json` 的 `context_sha256` 与[我们的](../evidence/coding-matrix-20261026/cache/context.json)相同。

**这些步骤无法精确重现的部分。** 回答以及通过数每次都会不同；延迟取决于时间和负载；GlobalStandard 部署的路由可能不同。公开脚本与实测脚本的差异全部列在 [provenance.json](../evidence/coding-matrix-20261026/provenance.json)：`bench.py`、`probe.py`、`cache_test.py` 和评分镜像文件逐字节相同。
