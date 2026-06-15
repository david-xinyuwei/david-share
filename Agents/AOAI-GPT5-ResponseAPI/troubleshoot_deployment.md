# AI Foundry 部署错误排查指南

## 错误信息
```
2025-10-17T01:14:55Z Startup task failed due to authorization error. 
Please see troubleshooting guide: https://aka.ms/oe-tsg#error-badargument
```

## 排查步骤

### 1. 检查 API Key 和 Endpoint
```bash
# PowerShell 中检查环境变量
$env:AZURE_OPENAI_API_KEY
$env:AZURE_OPENAI_ENDPOINT
```

确认:
- API Key 是否正确且未过期
- Endpoint 格式是否正确
- 是否指向正确的 Azure 资源

### 2. 验证 Azure 门户配置

#### 在 Azure Portal 检查:
1. 资源是否已成功创建
2. 部署名称是否正确
3. API 版本是否支持 (推荐: `2025-03-01-preview`)
4. 区域选择:
   - GPT-5: 建议使用 East US, West Europe
   - GPT-5-Codex: Sweden Central 已验证可用

### 3. 权限检查

确保您的账户具有以下权限之一:
- `Cognitive Services OpenAI Contributor`
- `Cognitive Services Contributor`
- `Owner` (订阅级别)

#### 在 Azure Portal 中添加权限:
```
Resource → Access control (IAM) → Add role assignment → 
选择角色 → 选择用户 → Review + assign
```

### 4. 配额检查

#### 查看配额:
```
Azure Portal → Your AI Resource → Quotas and Limits
```

常见配额需求:
- TPM (Tokens Per Minute): 至少 10,000
- RPM (Requests Per Minute): 至少 100
- 部署实例数: 至少 1

#### 申请配额增加:
```
Portal → Support → New support request → 
Issue type: Technical → Service: Cognitive Services
```

### 5. 网络和防火墙

检查:
- 资源是否启用了网络限制
- 防火墙规则是否阻止了访问
- 是否需要配置 Private Endpoint

#### 临时禁用网络限制测试:
```
Resource → Networking → 
Firewalls and virtual networks → Allow access from: All networks
```

### 6. API 版本兼容性

使用最新的 API 版本:
```python
API_VERSION = "2025-03-01-preview"
```

如果使用 Responses API 特性,确保:
- `reasoning` 参数支持
- `previous_response_id` 支持
- `store` 参数支持

### 7. 部署参数验证

#### 最小化配置测试:
```python
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="your_key",
    azure_endpoint="https://<your-resource>.cognitiveservices.azure.com/",
    api_version="2025-03-01-preview"
)

# 简单测试
try:
    response = client.chat.completions.create(
        model="your_deployment_name",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=10
    )
    print("部署成功!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"错误: {e}")
```

### 8. 日志和诊断

#### 启用诊断日志:
```
Azure Portal → Resource → Diagnostic settings → 
Add diagnostic setting → 选择日志类别 → 保存
```

查看日志内容:
- 请求和响应日志
- 错误详细信息
- 授权失败记录

### 9. 区域特定问题

某些区域可能有限制,尝试:
1. East US 2
2. West Europe
3. Sweden Central

重新创建资源到不同区域测试

### 10. SDK 版本

确保使用最新的 SDK:
```bash
pip install --upgrade openai
```

当前推荐版本: `openai>=1.0.0`

## 常见错误代码

| 错误代码 | 含义 | 解决方案 |
|---------|------|---------|
| 401 | 未授权 | 检查 API Key |
| 403 | 禁止访问 | 检查权限和配额 |
| 404 | 资源不存在 | 检查部署名称和 Endpoint |
| 429 | 速率限制 | 增加配额或减少请求频率 |
| 500 | 服务器错误 | 联系 Azure 支持 |

## 联系支持

如果以上步骤都无法解决问题:

1. **创建支持工单**:
   ```
   Azure Portal → Help + support → New support request
   ```

2. **提供的信息**:
   - 订阅 ID
   - 资源名称和区域
   - 部署名称
   - 错误发生的准确时间 (UTC)
   - 完整的错误消息
   - 请求 ID (如果有)

3. **社区资源**:
   - Microsoft Learn: https://learn.microsoft.com/azure/ai-services/openai/
   - GitHub Issues: https://github.com/Azure/azure-sdk-for-python/issues
   - Stack Overflow: [azure-openai] 标签

## 快速诊断脚本

运行此脚本进行快速诊断:

```python
import os
from openai import AzureOpenAI

def diagnose_deployment():
    """诊断 Azure OpenAI 部署配置"""
    
    print("=== Azure OpenAI 部署诊断 ===\n")
    
    # 1. 环境变量检查
    print("1. 检查环境变量...")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    if not api_key:
        print("❌ AZURE_OPENAI_API_KEY 未设置")
    else:
        print(f"✓ API Key: {'*' * 10}{api_key[-4:]}")
    
    if not endpoint:
        print("❌ AZURE_OPENAI_ENDPOINT 未设置")
    else:
        print(f"✓ Endpoint: {endpoint}")
    
    if not deployment:
        print("❌ AZURE_OPENAI_DEPLOYMENT 未设置")
    else:
        print(f"✓ Deployment: {deployment}")
    
    if not all([api_key, endpoint, deployment]):
        print("\n请先设置所有必需的环境变量!")
        return
    
    # 2. 连接测试
    print("\n2. 测试连接...")
    try:
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version="2025-03-01-preview"
        )
        
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5
        )
        
        print("✓ 连接成功!")
        print(f"✓ 响应: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        
        # 提供具体建议
        if "401" in str(e):
            print("   建议: 检查 API Key 是否正确")
        elif "403" in str(e):
            print("   建议: 检查权限和配额")
        elif "404" in str(e):
            print("   建议: 检查 Endpoint 和部署名称")
        elif "429" in str(e):
            print("   建议: 配额不足或请求过快")

if __name__ == "__main__":
    diagnose_deployment()
```

保存为 `diagnose.py` 并运行:
```bash
python diagnose.py
```
