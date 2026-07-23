# Managed Runtime 证据

本目录只保留脱敏后的验证摘要，不包含Live Service凭据，也不把历史状态写成永久当前状态。

- `artifact-validation.json`：两份不同输入的独立产物契约解析结果。
- `parity-manifest.json`：Classic与Managed共用模块的逐字节Hash。
- `toolbox-skill-validation.json`：带日期的Toolbox Skill验证Hash。
- `ui-live-validation.json`：带日期、已移除云资源标识的浏览器验证摘要。

Public Repo不包含原始HTTP Header、Tenant URL、Identity、Request Body、Runtime Log或本机绝对路径。部署后必须重新验证Cloud状态和Skill绑定。
