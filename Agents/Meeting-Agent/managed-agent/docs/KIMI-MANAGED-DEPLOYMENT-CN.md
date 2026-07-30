# Kimi Managed Agent部署

**中文** | [English](KIMI-MANAGED-DEPLOYMENT.md) | [Managed实现说明](MANAGED-IMPLEMENTATION-CN.md)

本Runbook用于复现当前Public Managed源码合同，只使用占位符。真实Tenant、Subscription、Project与Endpoint值必须保存在隔离的本机CLI Profile和被忽略的`.azure`状态中。

## 已验证合同

| 字段 | 已验证值 | 范围 |
|---|---|---|
| Azure Developer CLI Service Key | `managed-meeting-agent` | 本机`azure.yaml`中的Service Selector，不是云端Agent名称 |
| 云端Agent名称 | `true-meeting-managed-agent` | 由`agent_reference`选择的Foundry Agent资源 |
| Agent Version | `6` | 已验证不可变版本；重新部署可能生成更新版本 |
| Agent Kind / Harness | `prompt` / `ghcp` | Foundry托管的Prompt Agent Runtime |
| 模型 | `Kimi-K2.7-Code` | 既有Model Deployment |
| Model Format / Version | `MoonshotAI` / `2026-06-12` | Public部署声明 |
| SKU / Capacity | `GlobalStandard` / `50` | 一个跑通配置，不是通用容量建议 |
| Toolbox | `my-toolbox` v7 | 已验证Live Toolbox |
| Public Meeting Skills | `meeting-package`、`mind-map-story`、`presentation-story` | 本Repo中的可复现Source Package |
| 认证 | Entra + `AgenticIdentityToken` | Managed客户路径不使用模型API Key |

已验证Live Toolbox还包含`incident-triage`。由于没有完成Public Source Package证明，本Repo不发布本地`incident-triage`包；当前Evidence只把它记录为已观察的Toolbox能力。

## 从Public源码部署

已提交源码有意分离Public声明与Private值：

- `agent.yaml`声明`true-meeting-managed-agent`与Kimi。
- `azure.yaml`保留部署命令需要的`managed-meeting-agent` **Service Key**。
- `scripts/render_deployment_source.py`只把Private azd值写入被忽略的`.azure`状态。
- `scripts/deploy-managed-agent.sh`要求Azure CLI与Azure Developer CLI双隔离，部署Service，恢复Public YAML，再Reconcile Toolbox与Agent Runtime状态。

在获授权Shell中设置项目专属值后执行，禁止打印Secret：

```bash
export AZURE_CONFIG_DIR="$HOME/.azure-<tenant>-<subscription>"
export AZD_CONFIG_DIR="$HOME/.azd-<tenant>-<subscription>"
export AZURE_TENANT_ID="<tenant-id>"
export AZURE_SUBSCRIPTION_ID="<subscription-id>"

bash scripts/deploy-managed-agent.sh
```

部署脚本执行：

```text
azd deploy managed-meeting-agent
```

不要把这个Service Key替换为`true-meeting-managed-agent`。云端Agent名称由`agent.yaml`声明，并在Reconcile完成后写入被忽略的Runtime Manifest。

## 启动本机客户UI

部署完成后，在Windows原生PowerShell中使用同一个隔离Azure CLI Profile：

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-<tenant>-<subscription>"
.\scripts\start-ui.ps1 -AzureConfigDir $env:AZURE_CONFIG_DIR
```

Launcher从`.azure/managed-runtime.json`读取Endpoint、Agent Name、不可变Version、Model Label与严格DeckPlan要求。Foundry Endpoint、Agent Reference、Entra Token或Runtime Manifest任一无效都会Fail Closed。

## 验收

有效部署必须分别证明以下项目：

1. Agent为`active`，并且`kind=prompt`、`harness=ghcp`、模型为`Kimi-K2.7-Code`。
2. Toolbox访问使用`AgenticIdentityToken`，三个Public Meeting Skill都存在。
3. Direct与Browser调用锁定预期Agent Name和不可变Version。
4. 结构化Meeting JSON生成严格Analysis与`DeckPlan`。
5. 本机Pipeline生成非空思维导图、可编辑六页PPTX，以及包含`X-Unsent: 1`和两个附件的EML。
6. 代码中不存在自动发送邮件路径。
7. Hand/Sandbox只能写成单次Session Observation，不能写成固定SKU、Quota、Image、持久化合同或SLA。

详见[脱敏Kimi v6验证](../evidence/managed-live-westus2/kimi-v6-runtime-validation.json)。历史GPT-5.4 v6/v9记录继续保留在`evidence/managed-live-gpt54/`，不得改标为当前Kimi证据。
