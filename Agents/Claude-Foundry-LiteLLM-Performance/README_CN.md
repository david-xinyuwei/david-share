# Claude on Foundry：thinking、缓存与首字延迟

LiteLLM 1.106.2 · Claude 5.5 · 50 requests · [Other language](README.md)

## 目的

本项目把模型 thinking、缓存覆盖范围和客户端首字等待分开测量，避免把 HTTP 200、已开启流式或缓存标记存在当成性能达标。提供三模型的固定五轮输入、流式采集器、十组实际结果和离线验算。

这是一次固定资料问答实验，不是客户生产负载。没有答案质量评分、并发压测、AWS 对照或其他 effort 档位排名。

<img src="images/architecture-zh.svg" width="880" alt="Measured gateway architecture and timing points" />

原创解释图；Azure 图标来源见 images/icon-sources.json。图不是运行证据。

## 操作步骤

先准备自己的 Foundry 资源和三个 Azure-hosted 部署（版本 2），使用名称 claude-opus-5-5、claude-sonnet-5-5、claude-haiku-5-5。按实际配额分配容量；本次各为 40,000 TPM。需要 Windows PowerShell 7、Python 3.13、Docker 或 ACR Tasks，以及获授权的 Azure CLI 登录。

部署到已有的、仅用于此测试的 Azure Container App：启用系统分配 Managed Identity，在 Foundry 资源范围授予 Cognitive Services User；私有 ACR 拉取还需 AcrPull。将入口密钥保存为 ACA Secret（例如 gateway-key），不要放入 Git 或命令行。

在本项目目录运行以下命令。变量均为自己的资源；密钥由安全终端提示输入，脚本只在进程内使用。

**1. 构建自己的网关镜像**

```powershell
$env:ACR_NAME = Read-Host 'Your ACR name'
$env:APP_RG = Read-Host 'Your dedicated Container App resource group'
$env:APP_NAME = Read-Host 'Your dedicated Container App name'
$env:FOUNDRY_ANTHROPIC_BASE = Read-Host 'Your Foundry /anthropic base URL'
az acr build --registry $env:ACR_NAME --image claude-gateway:1.106.2 --file deploy/Dockerfile deploy
```

该 Dockerfile 从固定的公开 LiteLLM 镜像构建，不拉取作者的私有镜像。原测试容器的构建、启动和真实请求已验证；此公开包装的全新部署尚未实跑，不能把离线检查当成部署成功。

**2. 更新专用 Container App**

```powershell
$digest = az acr repository show --name $env:ACR_NAME --image claude-gateway:1.106.2 --query digest -o tsv
$server = az acr show --name $env:ACR_NAME --query loginServer -o tsv
$image = "$server/claude-gateway@$digest"
az containerapp update --resource-group $env:APP_RG --name $env:APP_NAME --image $image --set-env-vars "FOUNDRY_ANTHROPIC_BASE=$env:FOUNDRY_ANTHROPIC_BASE" 'LITELLM_MASTER_KEY=secretref:gateway-key' 'PYTHONPATH=/app/claude-gateway'
```

请在 ACA Ingress 中启用 HTTPS、目标端口 4000，并仅允许自己的测试客户端访问。保留原密钥；更新镜像前记录旧 digest 以便回滚。

**3. 验证入口，再执行矩阵**

```powershell
$env:CLAUDE_GATEWAY_URL = Read-Host 'Your HTTPS gateway URL'
$secureKey = Read-Host 'Your gateway key' -AsSecureString
$env:CLAUDE_GATEWAY_KEY = [Net.NetworkCredential]::new('', $secureKey).Password
try {
    $headers = @{Authorization='Bearer '+$env:CLAUDE_GATEWAY_KEY}
    (Invoke-RestMethod "$env:CLAUDE_GATEWAY_URL/v1/models" -Headers $headers).data.id
    $run = Join-Path 'live-runs' (Get-Date -Format 'yyyyMMdd-HHmmss')
    ./scripts/run_matrix.ps1 -RunDirectory $run
} finally {
    $env:CLAUDE_GATEWAY_KEY = $null
}
```

元数据接口应列出三个 standard 别名；矩阵应保存 50 份响应。Ctrl+C 停止本地测试，不会停止 Azure 资源。资源停用和访问规则恢复由资源所有者单独执行。

## 实现效果

本轮 **50/50 正常完成**，模型费用按公开费率估算 **US$0.78989513**。以下每行五轮；输出吞吐为 output_tokens/E2E，包含 thinking。

| 模型 | thinking | 缓存覆盖 | 样本 | 缓存读取占比 | 首字 P50（秒） | E2E P50（秒） | 输出 P50（token/秒） | 模型费（美元） |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Opus 5.5 | adaptive | system | 5 | 28.27% | 9.321 | 18.334 | 95.78 | 0.258394 |
| Sonnet 5.5 | adaptive | system | 5 | 33.52% | 8.051 | 15.233 | 117.84 | 0.110115 |
| Sonnet 5.5 | between_tools | system | 5 | 39.96% | 0.954 | 7.991 | 114.76 | 0.073466 |
| Haiku 5.5 | adaptive | system | 5 | 32.81% | 4.235 | 7.160 | 183.51 | 0.004840 |
| Haiku 5.5 | disabled | system | 5 | 47.47% | 0.810 | 3.553 | 153.96 | 0.002472 |
| Opus 5.5 | adaptive | system + history | 5 | 69.25% | 7.293 | 16.022 | 90.86 | 0.193501 |
| Sonnet 5.5 | adaptive | system + history | 5 | 67.68% | 1.434 | 8.604 | 115.29 | 0.081004 |
| Sonnet 5.5 | between_tools | system + history | 5 | 70.68% | 0.893 | 7.874 | 112.64 | 0.060174 |
| Haiku 5.5 | adaptive | system + history | 5 | 71.04% | 2.910 | 5.917 | 172.62 | 0.003642 |
| Haiku 5.5 | disabled | system + history | 5 | 72.44% | 0.781 | 3.983 | 156.55 | 0.002288 |

关闭模式在无工具任务中均为零 thinking token。Sonnet 的 between_tools 不是所有场景下的完全关闭；Opus 5.5 不支持关闭。P95 在五个样本下等于最大值，不代表生产尾延迟。

更高缓存占比不等于全部首字改善来自缓存：各会话独立生成，历史和 thinking 用量随之变化。所有计时在客户端，未分离服务端排队、网络和推理计算。

| 想要 | 入口 |
|---|---|
| 查看逐轮与分段计时 | [Results](docs/results_CN.md) |
| 核验、复测与限制 | [Testing](docs/testing_CN.md) |

目录: [deploy](deploy/), [scripts](scripts/), [data](data/), [evidence](evidence/), [images](images/), [tests](tests/). [Dependencies](requirements.txt).
