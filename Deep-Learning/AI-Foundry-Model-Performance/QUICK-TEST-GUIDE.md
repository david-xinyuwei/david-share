# 🚀 快速测试指南 - 验证所有修复

## 📋 测试计划

按照这个顺序测试，从简单到复杂，逐步验证功能。

---

## ✅ 测试 1: 验证文件完整性（1 分钟）

### 运行验证脚本

```powershell
# 在项目根目录运行
.\test-verify.ps1
```

**预期结果：**
```
========================================
  PASS - All tests passed!
  Ready for Silver/Gold IP submission
========================================
```

✅ 如果通过，说明所有文件都正确创建了。

---

## ✅ 测试 2: 测试安全修复（2 分钟）

### 验证硬编码 API Key 已移除

```powershell
# 搜索文件中是否还有长字符串硬编码
Get-Content scripts\testing\press-phi35v-multi-imges-20250315.py | Select-String 'os.getenv'
```

**预期结果：**
应该看到类似这样的行：
```python
API_KEY = os.getenv('API_KEY', '')
```

✅ 如果看到 `os.getenv`，说明安全修复成功。

---

## ✅ 测试 3: 测试 Python 可观测性模块（3 分钟）

### 步骤 1: 安装必要的包

```powershell
# 如果还没有虚拟环境，创建一个
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 升级 pip
python -m pip install --upgrade pip

# 安装新增的依赖（可选，如果要测试完整功能）
pip install python-dotenv
```

### 步骤 2: 测试基本功能（不需要 Application Insights）

```powershell
# 运行示例脚本（降级模式，无需连接 Azure）
python scripts\testing\example-observability.py
```

**预期结果：**
```
========================================
Application Insights Observability Example
========================================

⚠ APPINSIGHTS_CONNECTION_STRING not set
  Logs will only appear in console

Running performance test...
Request 1 completed in XXXms
Request 2 completed in XXXms
...

Test Summary:
Total Duration: X.XXs
Average Latency: XXXms
Requests/sec: X.XX

Complete!
```

✅ 如果脚本运行成功并显示结果，说明代码工作正常。

---

## ✅ 测试 4: 查看您现有的 Azure 资源（2 分钟）

### 查看当前 Azure 配置

```powershell
# 检查是否已登录 Azure
az account show
```

如果**没有登录**，运行：
```powershell
az login
```

### 查看现有资源

```powershell
# 列出您的订阅
az account list --output table

# 查看现有的 ML Workspace
az ml workspace list --output table

# 查看现有的资源组
az group list --output table
```

📝 **把这些信息记下来**，我们可以决定是：
- 使用现有的资源
- 创建新的资源
- 或者都不需要

---

## ✅ 测试 5: 测试您现有的部署脚本（5 分钟）

### 验证现有脚本仍然工作

```powershell
# 测试部署脚本的帮助信息
python scripts\deployment\deploymodels-powershell-20250405.py --help
```

如果看到用法说明，说明脚本正常。

### （可选）实际部署一个模型

如果您想测试实际部署：

```powershell
# 运行部署脚本
python scripts\deployment\deploymodels-powershell-20250405.py

# 按提示输入：
# - Subscription ID
# - Resource Group  
# - Workspace Name
# - 模型信息等
```

⚠️ **注意：** 这会创建真实的 Azure 资源并产生费用。

---

## 🎯 测试 6: （可选）测试 Azure Developer CLI

### 前提条件

确认 azd 已安装：
```powershell
azd version
```

如果没有，安装：
```powershell
winget install microsoft.azd
```

### 初始化项目（不会部署任何东西）

```powershell
# 在项目根目录
azd init

# 按提示输入：
# - Environment name: dev
# - Azure Subscription: 选择您的订阅
# - Azure Location: eastus (或您偏好的区域)
```

### 预览会创建什么资源（不会真的创建）

```powershell
# 只查看，不创建
azd provision --preview
```

**预期输出：**
```
The following resources will be created:
  - Resource Group: rg-ai-foundry-perf-dev
  - Storage Account: staiXXXXXXXX
  - Key Vault: kv-ai-foundry-XXXXX
  - Application Insights: appi-ai-foundry-perf-dev
  - Log Analytics: log-ai-foundry-perf-dev
  - ML Workspace: mlw-ai-foundry-perf-dev
```

✅ 如果能看到资源列表，说明 azd 配置正确。

**⚠️ 停在这里！** 不要继续运行 `azd up`，除非您确定要创建这些资源。

---

## 📊 测试结果总结

### 您应该已经验证了：

| 测试项 | 目的 | 预期结果 |
|--------|------|----------|
| ✅ 文件验证 | 确认所有文件创建正确 | 所有测试通过 |
| ✅ 安全修复 | 确认无硬编码秘密 | 看到 os.getenv() |
| ✅ Python 模块 | 确认代码可以运行 | 脚本执行成功 |
| ✅ Azure 资源 | 了解现有配置 | 看到资源列表 |
| ✅ 部署脚本 | 确认现有功能正常 | 脚本可以运行 |
| 🔵 azd 配置 | （可选）预览部署 | 看到资源计划 |

---

## 🎉 成功标准

如果以上测试都通过，说明：

1. ✅ **安全问题已修复** - 无硬编码秘密
2. ✅ **新代码可以运行** - observability 模块工作正常
3. ✅ **现有功能未破坏** - 部署脚本仍然工作
4. ✅ **IaC 配置正确** - azd 可以识别配置
5. ✅ **文档完整** - 所有文件都在

---

## 🚀 下一步选择

### 选项 A: 最小改动（推荐）

如果您只想满足 Silver/Gold IP 要求，不想创建新资源：

1. ✅ 保留所有新文件（不删除）
2. ✅ 更新文档说明已有这些配置
3. ✅ 提交 Silver/Gold IP 申请
4. ❌ 不运行 `azd up`（不创建新资源）

**好处：**
- 不产生额外费用
- 现有环境不变
- 符合 Silver/Gold IP 所有要求

### 选项 B: 完整演示

如果您想展示完整的自动化部署能力：

1. 运行 `azd up` 创建演示环境
2. 测试所有功能
3. 展示给审核人员
4. 演示完成后运行 `azd down` 清理

**好处：**
- 完整展示自动化
- 可观测性实际工作
- 更有说服力

### 选项 C: 混合方案

使用现有的 ML Workspace，只添加监控：

1. 修改 Bicep 文件，只部署 Application Insights
2. 手动配置连接字符串
3. 使用新的 observability 模块

---

## 📝 报告问题

如果任何测试失败，请告诉我：

1. 哪个测试失败了？
2. 看到什么错误消息？
3. 当时在做什么操作？

我会帮您解决！

---

## 🎯 现在就开始

从第一个测试开始：

```powershell
# 运行这个
.\test-verify.ps1
```

然后告诉我结果！😊
