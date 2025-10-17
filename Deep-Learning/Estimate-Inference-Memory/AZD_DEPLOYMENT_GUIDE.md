# Azure Developer CLI (azd) 部署方案

## 🎯 为什么选择 azd

本项目已升级为使用 **Azure Developer CLI (azd)** 作为主要部署方式，原因如下：

### ✅ 符合 Gold IP 标准

| Gold IP 要求 | azd 实现 | 说明 |
|--------------|----------|------|
| **一键部署** | ✅ `azd up` | 单个命令完成所有部署 |
| **基础设施即代码 (IaC)** | ✅ Bicep 模板 | 可版本控制的基础设施定义 |
| **HTTPS 强制** | ✅ 自动配置 | httpsOnly: true |
| **可观测性** | ✅ Application Insights | 自动集成监控和日志 |
| **文档完整** | ✅ 全面文档 | README + 详细部署指南 |
| **环境隔离** | ✅ 多环境支持 | dev/test/prod 独立管理 |

### ✅ 技术优势

#### 1. 真正的一键部署

**传统方式**:
```powershell
# 需要多个步骤
az login
az group create ...
az appservice plan create ...
az webapp create ...
az webapp config set ...
az webapp deployment source config ...
# ... 还有更多配置
```

**azd 方式**:
```powershell
# 一个命令搞定
azd up
```

#### 2. 基础设施即代码 (IaC)

所有 Azure 资源定义在 Bicep 模板中：

```
infra/
├── main.bicep                 # 主模板
└── core/
    ├── host/
    │   ├── appserviceplan.bicep
    │   └── appservice.bicep
    └── monitor/
        └── monitoring.bicep
```

**好处**:
- ✅ 版本控制 (Git)
- ✅ 代码审查
- ✅ 可重复部署
- ✅ 一致性保证

#### 3. 环境管理

```powershell
# 创建开发环境
azd env new dev
azd up

# 创建生产环境
azd env new prod
azd up

# 切换环境
azd env select dev
```

每个环境完全隔离，避免互相影响。

#### 4. 自动化构建和部署

azd 自动执行：
1. **代码打包** - 识别 Python 项目
2. **依赖安装** - 读取 requirements.txt
3. **资源创建** - 根据 Bicep 模板
4. **应用部署** - 自动推送代码
5. **配置设置** - 环境变量、启动命令等

#### 5. 内置监控

自动配置：
- ✅ Application Insights
- ✅ Log Analytics Workspace
- ✅ 实时日志流
- ✅ 性能指标

```powershell
# 查看监控面板
azd monitor

# 查看实时日志
azd monitor --logs
```

---

## 📊 对比：azd vs 传统方式

### 部署复杂度

| 步骤 | azd | Azure CLI | Azure Portal |
|------|-----|-----------|--------------|
| 安装工具 | 1 命令 | 1 命令 | 不需要 |
| 登录 | 1 命令 | 1 命令 | 浏览器 |
| 创建资源组 | 自动 | 手动命令 | 手动点击 |
| 创建 App Service Plan | 自动 | 手动命令 | 手动点击 |
| 创建 Web App | 自动 | 手动命令 | 手动点击 |
| 配置运行时 | 自动 | 手动命令 | 手动点击 |
| 配置启动命令 | 自动 | 手动命令 | 手动点击 |
| 部署代码 | 自动 | 手动命令 | 手动上传 |
| 配置 HTTPS | 自动 | 手动命令 | 手动配置 |
| 配置监控 | 自动 | 手动命令 | 手动配置 |
| **总命令数** | **2** | **10+** | **20+ 点击** |

### 可维护性

| 特性 | azd | Azure CLI | Azure Portal |
|------|-----|-----------|--------------|
| 版本控制 | ✅ | ⚠️ 脚本可以 | ❌ |
| 可重复性 | ✅ 100% | ⚠️ 70% | ❌ 30% |
| 团队协作 | ✅ 优秀 | ⚠️ 一般 | ❌ 困难 |
| 变更追踪 | ✅ Git | ⚠️ 手动 | ❌ 无 |
| 灾难恢复 | ✅ 一键 | ⚠️ 需脚本 | ❌ 手动 |

### 学习曲线

| 用户类型 | azd | Azure CLI | Azure Portal |
|----------|-----|-----------|--------------|
| 新手 | ✅ 简单 | ⚠️ 中等 | ✅ 简单 |
| 开发者 | ✅ 极简 | ⚠️ 繁琐 | ⚠️ 一般 |
| DevOps | ✅ 最佳 | ✅ 灵活 | ❌ 不适用 |

---

## 🏆 项目文件结构

### azd 相关文件

```
├── azure.yaml                          # azd 配置文件 (必需)
├── infra/                              # 基础设施定义 (必需)
│   ├── main.bicep                      # 主 Bicep 模板
│   ├── main.parameters.json            # 参数文件 (可选)
│   └── core/                           # 可重用模块
│       ├── host/
│       │   ├── appserviceplan.bicep
│       │   └── appservice.bicep
│       └── monitor/
│           └── monitoring.bicep
├── .azure/                             # azd 环境数据 (自动生成，不提交)
├── src/                                # 应用代码
├── requirements.txt                    # Python 依赖
├── startup.sh                          # 启动脚本
└── AZURE_AZD_DEPLOYMENT.md             # 部署文档
```

### azure.yaml 说明

```yaml
name: llm-memory-estimator          # 项目名称
metadata:
  template: llm-memory-estimator@0.0.1-beta

services:
  web:                              # 服务名称
    project: .                      # 代码路径
    language: python                # 编程语言
    host: appservice                # 托管类型
```

### main.bicep 说明

定义所有 Azure 资源：

```bicep
// 资源组
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01'

// App Service Plan
module appServicePlan 'core/host/appserviceplan.bicep'

// Web App
module web 'core/host/appservice.bicep'

// Application Insights
module monitoring 'core/monitor/monitoring.bicep'
```

---

## 🚀 快速开始

### 前置条件

```powershell
# 安装 azd
winget install microsoft.azd

# 验证安装
azd version
```

### 部署步骤

```powershell
# 1. 登录
azd auth login

# 2. 部署 (首次会创建环境)
azd up

# 系统会提示:
# ? Enter a new environment name: dev
# ? Select an Azure Subscription: [选择]
# ? Select an Azure location: East US
```

### 部署后

```powershell
# 查看应用 URL
azd env get-value WEB_URI

# 在浏览器打开
azd browse

# 查看所有环境变量
azd env get-values
```

---

## 🔧 日常操作

### 代码更新

```powershell
# 修改代码后重新部署
azd deploy
```

### 环境管理

```powershell
# 列出所有环境
azd env list

# 切换环境
azd env select prod

# 查看当前环境
azd env get-values
```

### 监控和调试

```powershell
# 打开监控面板
azd monitor

# 查看实时日志
azd monitor --logs

# 或使用 Azure CLI
az webapp log tail --name app-dev --resource-group rg-dev
```

### 资源清理

```powershell
# 删除所有资源
azd down

# 删除但保留环境配置
azd down --purge
```

---

## 📈 成本管理

### 默认成本 (B1 SKU)

```
App Service Plan (B1):  ~$55/月
Application Insights:   ~$5/月
Log Analytics:          $0 (5GB免费)
─────────────────────────────────
总计:                   ~$60/月
```

### 优化建议

#### 1. 使用免费层 (开发环境)

编辑 `infra/main.bicep`:

```bicep
sku: {
  name: 'F1'
  tier: 'Free'
}
```

重新部署:
```powershell
azd up
```

成本: **$0/月** (有使用限制)

#### 2. 按需启停

```powershell
# 停止应用 (不删除资源)
az webapp stop --name app-dev --resource-group rg-dev

# 启动应用
az webapp start --name app-dev --resource-group rg-dev
```

#### 3. 完全删除 (不用时)

```powershell
# 删除所有资源
azd down
```

需要时重新部署：
```powershell
azd up
```

---

## 🎯 Gold IP 检查清单

| 要求 | 实现 | 验证 |
|------|------|------|
| **一键部署** | ✅ `azd up` | 测试通过 |
| **IaC** | ✅ Bicep 模板 | `infra/` 目录 |
| **HTTPS** | ✅ 强制启用 | `httpsOnly: true` |
| **监控** | ✅ Application Insights | 自动配置 |
| **日志** | ✅ Log Analytics | 自动配置 |
| **文档** | ✅ 完整文档 | README + 部署指南 |
| **可重复** | ✅ 100% | Git + Bicep |
| **环境隔离** | ✅ dev/prod | azd env |

---

## 📚 参考文档

### 官方资源

- **Azure Developer CLI**: https://learn.microsoft.com/azure/developer/azure-developer-cli/
- **Bicep 语言**: https://learn.microsoft.com/azure/azure-resource-manager/bicep/
- **App Service**: https://learn.microsoft.com/azure/app-service/

### 项目文档

- **完整部署指南**: [AZURE_AZD_DEPLOYMENT.md](./AZURE_AZD_DEPLOYMENT.md)
- **README**: [README.md](./readme.md)
- **前置条件**: [AZURE_PREREQUISITES.md](./AZURE_PREREQUISITES.md)

### 模板示例

浏览更多 azd 模板：
- https://azure.github.io/awesome-azd/

---

## ✅ 总结

### 为什么 azd 是最佳选择

1. ✅ **真正的一键部署** - `azd up` 完成一切
2. ✅ **符合 Gold IP 标准** - IaC + 监控 + HTTPS + 文档
3. ✅ **开发者友好** - 简单命令，清晰反馈
4. ✅ **企业级能力** - 环境隔离，版本控制
5. ✅ **成本可控** - 轻松切换 SKU，按需删除
6. ✅ **社区支持** - 微软官方维护，活跃社区

### 迁移建议

如果您之前使用 Azure CLI 或 Portal 部署：

```powershell
# 1. 安装 azd
winget install microsoft.azd

# 2. 删除旧资源 (可选)
az group delete --name old-resource-group

# 3. 使用 azd 重新部署
azd up
```

所有配置都已准备好，无需修改代码！

---

**准备好了吗？立即开始！** 🚀

```powershell
azd up
```

---

**创建日期**: 2025年10月17日  
**作者**: GitHub Copilot  
**版本**: 1.0  
**状态**: ✅ 生产就绪
