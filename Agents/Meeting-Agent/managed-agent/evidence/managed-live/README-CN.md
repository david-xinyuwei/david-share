# Managed Runtime 证据

本目录只保留脱敏后的验证摘要，不包含Live Service凭据，也不把历史状态写成永久当前状态。

- `public-v2-source-manifest.json`：把Public Agent、Instructions、Skill和部署声明Hash绑定到成功v2部署。
- `public-v2-agent-reference-validation.json`：非Stream与Stream调用均校验`managed-meeting-agent`版本`2`，包含真实Delta数量和脱敏Response ID Hash。
- `public-v2-deployment-validation.json`：两份明显不同v2输入的PNG、六页PPTX和未发送EML独立解析结果。
- `artifact-validation.json`：保留的历史v1产物验证，用于对照。
- `parity-manifest.json`：Classic与Managed共用模块的逐字节Hash。
- `toolbox-skill-validation.json`：带日期的Toolbox Skill验证Hash。
- `ui-live-validation.json`：带日期、已移除云资源标识的浏览器验证摘要。

Public Repo不包含原始HTTP Header、Tenant URL、Identity、Request Body、Runtime Log或本机绝对路径。v2证据带日期；源码或目标环境变化后必须重新验证。
