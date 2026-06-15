# Azure Portal 中配置 Azure AI Foundry RBAC 完整指南

## 目录
1. [访问 Azure Portal](#访问-azure-portal)
2. [查找您的 AI 资源](#查找您的-ai-资源)
3. [配置 RBAC 权限](#配置-rbac-权限)
4. [常用角色说明](#常用角色说明)
5. [验证权限](#验证权限)
6. [故障排查](#故障排查)

---

## 访问 Azure Portal

### 步骤 1: 登录 Azure Portal
1. 打开浏览器访问: https://portal.azure.com
2. 使用您的 Azure 账户登录
3. 确认您有访问相关订阅的权限

### 步骤 2: 导航到 AI Foundry 资源

#### 方法 1: 通过搜索栏
```
顶部搜索栏 → 输入您的资源名称 → 选择对应的 Azure OpenAI 或 AI Services 资源
```

#### 方法 2: 通过资源组
```
Home → Resource groups → 选择包含 AI 资源的资源组 → 点击资源名称
```

#### 方法 3: 通过所有资源
```
Home → All resources → 筛选或搜索您的 AI 资源
```

---

## 查找您的 AI 资源

### 识别正确的资源类型

**Azure OpenAI Service:**
- 类型: `Microsoft.CognitiveServices/accounts`
- Kind: `OpenAI`
- 图标: Azure OpenAI 标志

**Azure AI Services (多服务):**
- 类型: `Microsoft.CognitiveServices/accounts`
- Kind: `AIServices` 或 `CognitiveServices`

### 确认资源信息
点击资源后,在 **Overview (概述)** 页面查看:
- ✅ 资源名称
- ✅ 资源组
- ✅ 位置/区域
- ✅ 订阅
- ✅ 状态 (应该是 "Succeeded")

---

## 配置 RBAC 权限

### 步骤 1: 打开访问控制 (IAM)

1. 在您的 AI 资源页面,左侧菜单找到 **Access control (IAM)**
2. 点击进入 IAM 管理页面

```
资源页面 → 左侧菜单 → Access control (IAM)
```

### 步骤 2: 查看当前权限

点击 **Role assignments (角色分配)** 选项卡查看:
- 当前有哪些用户/组/服务主体有权限
- 他们分别有什么角色
- 权限的作用域

### 步骤 3: 添加新的角色分配

#### 方法 A: 通过 Add 按钮
```
Access control (IAM) → 点击 "+ Add" → 选择 "Add role assignment"
```

#### 方法 B: 通过快速访问
```
Access control (IAM) → 顶部点击 "+ Add" 下拉菜单 → Add role assignment
```

### 步骤 4: 选择角色

在 **Add role assignment** 页面:

#### Tab 1: Role (角色选择)

**搜索框搜索相关角色:**
```
搜索: "Cognitive Services" 或 "OpenAI"
```

**推荐角色 (按权限从高到低):**

1. **Cognitive Services OpenAI Contributor** ⭐ 最常用
   - 权限: 部署模型、管理配置、调用 API
   - 适用: 开发人员、数据科学家
   - 作用域: 完整的 OpenAI 资源管理

2. **Cognitive Services OpenAI User**
   - 权限: 调用已部署的模型 API
   - 适用: 应用程序、终端用户
   - 作用域: 仅 API 调用,无管理权限

3. **Cognitive Services Contributor**
   - 权限: 管理所有认知服务资源
   - 适用: 管理员
   - 作用域: 更广泛的权限

4. **Cognitive Services User**
   - 权限: 读取密钥和端点,调用 API
   - 适用: 只需要使用 API 的用户

**选择角色后,点击 "Next"**

### 步骤 5: 选择成员

#### Tab 2: Members (成员选择)

**分配对象类型:**
- ☑️ User (用户): 分配给具体的人
- ☑️ Group (组): 分配给 Azure AD 组
- ☑️ Service principal (服务主体): 分配给应用程序

**搜索和添加成员:**
```
1. 在搜索框输入用户名、邮箱或组名
2. 从搜索结果中选择
3. 点击 "Select" 添加
4. 可以添加多个成员
```

**示例:**
```
搜索: "john.doe@company.com"
选择: John Doe (john.doe@company.com)
点击: Select
```

点击 **"Next"** 继续

### 步骤 6: 配置条件 (可选)

#### Tab 3: Conditions (条件 - 高级配置)

通常可以跳过此步骤,除非需要:
- 基于资源标签的条件访问
- 基于时间的访问控制
- 特定操作的限制

**大多数情况下,直接点击 "Next"**

### 步骤 7: 审查和分配

#### Tab 4: Review + assign (审查与分配)

**确认信息:**
- ✅ 角色名称
- ✅ 成员列表
- ✅ 作用域 (通常是当前资源)

**完成分配:**
```
1. 检查所有信息正确
2. 点击 "Review + assign" 按钮
3. 等待几秒钟,权限将生效
```

**成功提示:**
```
"Successfully added role assignment" (成功添加角色分配)
```

---

## 常用角色说明

### 详细角色对比表

| 角色名称 | 部署模型 | 调用 API | 查看密钥 | 管理配置 | 查看指标 | 推荐场景 |
|---------|---------|---------|---------|---------|---------|---------|
| **Cognitive Services OpenAI Contributor** | ✅ | ✅ | ✅ | ✅ | ✅ | 开发和管理 |
| **Cognitive Services OpenAI User** | ❌ | ✅ | ✅ | ❌ | ✅ | 仅使用 API |
| **Cognitive Services Contributor** | ✅ | ✅ | ✅ | ✅ | ✅ | 完整管理权限 |
| **Cognitive Services User** | ❌ | ✅ | ✅ | ❌ | ✅ | 基础使用 |
| **Reader** | ❌ | ❌ | ❌ | ❌ | ✅ | 仅查看信息 |
| **Owner** | ✅ | ✅ | ✅ | ✅ | ✅ | 完全控制+管理权限 |

### 具体权限说明

#### 🔹 Cognitive Services OpenAI Contributor
```
可以执行的操作:
✅ 创建和删除部署
✅ 修改部署配置 (如 TPM、RPM)
✅ 调用所有模型 API
✅ 查看和重新生成 API 密钥
✅ 配置网络和防火墙规则
✅ 设置诊断日志
✅ 查看使用情况和配额

无法执行的操作:
❌ 删除整个资源 (需要 Owner 或 Contributor)
❌ 修改 RBAC 权限 (需要 Owner 或 User Access Administrator)
```

#### 🔹 Cognitive Services OpenAI User
```
可以执行的操作:
✅ 调用已部署的模型
✅ 查看 API 端点和密钥
✅ 查看部署列表
✅ 查看使用情况统计

无法执行的操作:
❌ 创建或删除部署
❌ 修改任何配置
❌ 管理网络设置
❌ 修改 API 密钥
```

### 推荐的权限分配策略

#### 场景 1: 开发团队
```
角色: Cognitive Services OpenAI Contributor
成员: 开发人员、数据科学家
理由: 需要部署模型和调试配置
```

#### 场景 2: 应用程序
```
角色: Cognitive Services OpenAI User
成员: 应用服务主体 (Service Principal)
理由: 只需要调用 API,不需要管理权限
```

#### 场景 3: 管理员
```
角色: Owner 或 Cognitive Services Contributor
成员: 团队负责人、DevOps
理由: 需要完整的管理和配置权限
```

#### 场景 4: 测试/审计人员
```
角色: Reader
成员: QA、审计人员
理由: 只需要查看配置和使用情况
```

---

## 验证权限

### 方法 1: 在 Portal 中验证

#### 检查角色分配
```
1. Access control (IAM)
2. Role assignments 选项卡
3. 搜索用户名
4. 确认角色列表
```

#### 检查有效权限
```
1. Access control (IAM)
2. 点击 "Check access" 按钮
3. 选择用户/组/服务主体
4. 点击 "View" 查看实际权限
```

### 方法 2: 测试 API 访问

#### 获取密钥和端点
```
资源页面 → Keys and Endpoint → 复制 Key 1 和 Endpoint
```

#### PowerShell 测试脚本
```powershell
# 设置变量
$apiKey = "your_api_key_here"
$endpoint = "https://<your-resource>.cognitiveservices.azure.com/"
$deploymentName = "your-deployment-name"

# 测试 API 调用
$headers = @{
    "api-key" = $apiKey
    "Content-Type" = "application/json"
}

$body = @{
    messages = @(
        @{
            role = "user"
            content = "Hello, this is a test."
        }
    )
    max_tokens = 10
} | ConvertTo-Json

$uri = "$endpoint/openai/deployments/$deploymentName/chat/completions?api-version=2024-08-01-preview"

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body
    Write-Host "✓ API 调用成功!" -ForegroundColor Green
    Write-Host "响应: $($response.choices[0].message.content)"
} catch {
    Write-Host "✗ API 调用失败: $_" -ForegroundColor Red
}
```

### 方法 3: Python SDK 测试

```python
import os
from openai import AzureOpenAI

# 配置
api_key = "your_api_key_here"
endpoint = "https://<your-resource>.cognitiveservices.azure.com/"
deployment = "your-deployment-name"

# 创建客户端
client = AzureOpenAI(
    api_key=api_key,
    azure_endpoint=endpoint,
    api_version="2024-08-01-preview"
)

# 测试调用
try:
    response = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("✓ API 调用成功!")
    print(f"响应: {response.choices[0].message.content}")
except Exception as e:
    print(f"✗ API 调用失败: {e}")
```

---

## 故障排查

### 问题 1: 找不到 "Access control (IAM)"

**可能原因:**
- 当前用户没有足够的权限查看 IAM
- 不在正确的资源页面

**解决方案:**
```
1. 确认您在资源的主页面 (不是资源组)
2. 检查左侧菜单是否完全展开
3. 确认您至少有 "Reader" 权限
4. 尝试刷新页面
```

### 问题 2: 无法添加角色分配

**错误提示:**
```
"You do not have permission to add role assignment at this scope"
```

**解决方案:**
```
1. 您需要以下角色之一才能分配权限:
   - Owner (所有者)
   - User Access Administrator (用户访问管理员)
   
2. 联系您的 Azure 管理员请求权限
3. 或者在更高层级 (订阅或资源组) 进行分配
```

### 问题 3: 用户搜索不到

**可能原因:**
- 用户不在同一个 Azure AD 租户
- 用户是外部来宾用户
- 搜索关键词不正确

**解决方案:**
```
1. 尝试完整的邮箱地址搜索
2. 对于外部用户,使用 "john.doe_external#EXT#@tenant.onmicrosoft.com" 格式
3. 确认用户已被邀请到 Azure AD
4. 尝试通过对象 ID 搜索
```

### 问题 4: 权限已分配但仍然无法访问

**检查清单:**
```
1. ⏱️ 等待 5-10 分钟 (权限传播需要时间)
2. 🔄 刷新浏览器或重新登录
3. 🌐 检查网络和防火墙设置
4. 🔑 确认使用了正确的 API Key
5. 📍 确认在正确的区域和端点
6. 📊 检查配额是否充足
```

### 问题 5: 部署权限错误 (BadArgument)

**这正是您遇到的错误!**

**完整排查步骤:**

```
1. ✅ 确认已分配 "Cognitive Services OpenAI Contributor" 角色
2. ✅ 等待 10 分钟让权限生效
3. ✅ 检查区域是否支持您要部署的模型:
   - GPT-4: East US, West Europe, France Central
   - GPT-4o: 大多数区域
   - GPT-5: East US 2, West Europe, Sweden Central
4. ✅ 确认配额充足:
   资源页面 → Quotas → 查看 TPM 配额
5. ✅ 检查网络设置:
   资源页面 → Networking → 确认 "All networks" 或您的 IP 在白名单
```

---

## 快速操作指南 (分步截图说明)

### 🎯 快速任务: 为开发人员添加权限

**时间: 约 2 分钟**

```
步骤 1: 登录 Portal
→ https://portal.azure.com

步骤 2: 找到资源
→ 搜索栏输入资源名 → 点击

步骤 3: 打开 IAM
→ 左侧菜单 → Access control (IAM)

步骤 4: 添加角色
→ "+ Add" → "Add role assignment"

步骤 5: 选择角色
→ 搜索 "OpenAI Contributor" → 选中 → Next

步骤 6: 添加成员
→ 输入邮箱 → 选择用户 → Select → Next

步骤 7: 完成
→ Review + assign → 完成!
```

### 🎯 快速任务: 查看自己的权限

```
步骤 1: 进入资源 IAM
→ Access control (IAM)

步骤 2: 检查访问
→ "Check access" 按钮

步骤 3: 选择自己
→ View my access
→ 或搜索您的邮箱 → View

步骤 4: 查看结果
→ 显示所有角色分配
→ 显示继承的权限
```

---

## 最佳实践

### 1. 最小权限原则
```
✅ 只授予完成任务所需的最小权限
✅ 定期审查和清理不必要的权限
✅ 使用组而不是单个用户 (便于管理)
```

### 2. 使用 Azure AD 组
```
推荐结构:
├── AI-Developers (Contributor 角色)
├── AI-Users (User 角色)  
└── AI-Admins (Owner 角色)

优势:
- 集中管理
- 便于审计
- 易于扩展
```

### 3. 服务主体管理
```
为应用程序使用服务主体:
1. Azure AD → App registrations → New registration
2. 创建后,在资源 IAM 中分配权限
3. 使用 Client ID + Client Secret 认证
4. 定期轮换密钥
```

### 4. 监控和审计
```
启用诊断日志:
资源 → Diagnostic settings → Add setting
→ 选择 "Audit" 和 "RequestResponse"
→ 发送到 Log Analytics 或 Storage Account

定期审查:
→ Access control (IAM) → Activity log
→ 查看谁做了什么操作
```

---

## 相关资源

### Microsoft 官方文档
- [Azure RBAC 文档](https://learn.microsoft.com/azure/role-based-access-control/)
- [Azure OpenAI RBAC](https://learn.microsoft.com/azure/ai-services/openai/how-to/role-based-access-control)
- [Cognitive Services 安全](https://learn.microsoft.com/azure/ai-services/security-features)

### 常用 Azure Portal 链接
- Azure Portal: https://portal.azure.com
- Azure AD 管理: https://portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade
- 成本管理: https://portal.azure.com/#blade/Microsoft_Azure_CostManagement/Menu/overview

### PowerShell 快速命令

```powershell
# 查看资源的角色分配
Get-AzRoleAssignment -Scope "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroup}/providers/Microsoft.CognitiveServices/accounts/{resourceName}"

# 添加角色分配
New-AzRoleAssignment `
    -ObjectId <用户或服务主体的 ObjectId> `
    -RoleDefinitionName "Cognitive Services OpenAI Contributor" `
    -Scope "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroup}/providers/Microsoft.CognitiveServices/accounts/{resourceName}"

# 移除角色分配
Remove-AzRoleAssignment `
    -ObjectId <ObjectId> `
    -RoleDefinitionName "Cognitive Services OpenAI Contributor" `
    -Scope <Scope>
```

---

## 总结

配置 Azure AI Foundry RBAC 的关键步骤:

1. ✅ **登录 Azure Portal** (portal.azure.com)
2. ✅ **找到您的 AI 资源**
3. ✅ **打开 Access control (IAM)**
4. ✅ **添加适当的角色分配**
5. ✅ **等待权限生效 (5-10分钟)**
6. ✅ **验证访问权限**

**针对您的部署错误:**
- 确保有 `Cognitive Services OpenAI Contributor` 角色
- 检查区域和配额
- 验证网络设置
- 等待权限传播后重试部署

如果问题仍然存在,请参考 `troubleshoot_deployment.md` 文件进行深度排查!
