# 清理 Azure 资源后重新部署

## 方案 1: 删除整个资源组 (推荐,最干净)
```bash
# 列出资源组
az group list --query "[?starts_with(name, 'rg-ai-foundry')].name" -o table

# 删除资源组(会删除所有资源)
az group delete --name rg-ai-foundry-perf-dev --yes --no-wait

# 等待 2-3 分钟,然后重新运行
azd up
```

## 方案 2: 删除 azd 环境重新开始
```bash
# 删除 azd 环境
azd env delete xinyuwei

# 重新初始化
azd up
```

## 方案 3: 使用不同的环境名称
```bash
# 创建新环境
azd env new xinyuwei-v2

# 重新部署
azd up
```

## 方案 4: 手动清理已删除的 Key Vault
```bash
# 列出软删除的 Key Vault
az keyvault list-deleted --subscription 08f95cfd-64fe-4187-99bb-7b3e661c4cde

# 永久删除(如果有)
az keyvault purge --name kv-zumihoz4vxz3a --subscription 08f95cfd-64fe-4187-99bb-7b3e661c4cde
```

---

## 推荐步骤:
```bash
# 1. 删除资源组
az group delete --name rg-ai-foundry-perf-dev --yes --no-wait

# 2. 等待 2-3 分钟

# 3. 检查是否删除完成
az group exists --name rg-ai-foundry-perf-dev

# 4. 如果返回 false,重新部署
azd up
```

---

## 为什么会出现这个错误?
- Storage Account 已经创建: `staizumihoz4vxz3a`
- 第二次运行 `azd up` 时,Bicep 尝试更新它
- 某些 Storage Account 属性不支持更新操作
- 需要删除重建或使用新的资源组

## 最快解决方案
**删除资源组,1 条命令:**
```bash
az group delete --name rg-ai-foundry-perf-dev --yes --no-wait && sleep 180 && azd up
```
