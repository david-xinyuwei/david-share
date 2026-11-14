# 测试

[English](TESTING.md) · [README](../README_CN.md)

测试分六层，从最便宜到最贵。前三层不需要 Azure 账号；浏览器检查和工程渲染图需要 Microsoft Edge；只有部署和在线检查会创建 Azure 资源或调用模型，要花钱。

## 每一层测什么

| 层 | 命令（未注明的都在 `studio/` 下执行） | 需要 | 检查内容 | 不检查 |
|---|---|---|---|---|
| Python 单元与契约测试，73 个 | `python -m unittest discover -s tests -p "test_*.py"` | 虚拟环境；`pregen_cad.py` 建好的 15 个参考实体 | 输出契约与解析、SSE 事件与心跳、登录与会话、输入上限、服务器托管连接（浏览器拿不到密钥）、CAD 白名单、把报错回传重试的循环、取消时终止 OCCT 子进程、预生成结果与实时结果同一格式返回、方案书 `.docx`、部署拒绝所选推理强度时（2026-11-14 的 400）改发接受的下一档 | 真实的模型回答（模拟）和真实的 OCCT 执行（模拟）；例外是每个参考脚本都必须通过和模型输出相同的白名单，并且有最新的构建结果 |
| Node 前端测试，38 个 | `node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs` | Node.js 18 及以上；`tools/vendor_three.py` 下载的 three.js | 服务器托管模式下的连接对话框、按真实 WebGL 绘制调用判断「渲染就绪」、失败上报、PNG 与 GLB 导出规则、四视图布局与取景 | 真实的 WebGL 像素（画布是模拟的） |
| 真实 OCCT 构建，15 个实体 | `python pregen_cad.py`，再 `python pregen_cad.py --lang en` | 虚拟环境 | 每个参考脚本都经 `cad_runner.run_script` 执行并写出 STEP、STL、GLB 和 `parts.json`；英文构建与中文构建是同一批实体，只换部件名 | GPT-6 写的 CadQuery 脚本（只在实时调用时执行） |
| 浏览器检查，23 步 | 工坊运行在 `127.0.0.1:8015` 时执行 `python tests/check_workspace_browser.py --headless --output <dir>`（见下） | Edge；`requirements-dev.txt` | 服务端返回的文件与源码一致；打开场景时带出预生成的 STEP 实体；环境光遮蔽确实压暗零件；着色、剖切、隔离和两种导出可用；英文界面；390 px 窄屏；按当前提示词写的场景能通过同一个 bridge 渲染；没有任何请求到达模型接口 | GPU 渲染（这里用软件 WebGL）；实时模型结果 |
| 工程渲染图，15 张 | `python pregen_engineering.py <ids> --out <dir> --no-install` | Edge；`requirements-dev.txt`；`pregen_cad.py` 建好的实体 | 每个 STEP 网格都能渲染、没有对不上材质的部件，并计算同一相机下画面与 STEP 轮廓的重合度（IoU） | gpt-image 效果图（那需要 Azure） |
| 端到端部署 | 在仓库根目录执行 `./infra/up.ps1`、`./infra/verify.ps1 -Full`、`./infra/down.ps1`（README 第 2、3、5 步） | 有配额的 Azure 订阅（见 README [操作步骤](../README_CN.md#操作步骤)）、Azure CLI、PowerShell 7.3 | 按 `infra/main.bicep` 在新资源组里创建全部资源；虚拟机从仓库安装工坊，用 Let's Encrypt 证书提供 HTTPS；再通过这个地址检查：健康检查、HTTP 跳转、错误密码被拒绝、登录、15 个场景、每个场景中英文两套预生成实体、用虚拟机托管身份调用一次 GPT-6、实时 **生成 STEP** 并下载 STEP 文件、生成一张 gpt-image 概念图；删除后既没有资源组，也没有软删除状态的 AI 资源 | 虚拟机上的浏览器界面（同样的页面由浏览器检查在本机覆盖）、实时生成 three.js 网页、**生成渲染图** 和方案书；费用 |
| 在线检查，手动 | 界面上的 **实时调用 GPT-6**、**生成渲染图**、**生成方案书** | 一套部署（README 第 2 步） | 真实模型路径端到端走通 | 没有自动化；每点一次都消耗 token。**生成 STEP** 和概念图由 `verify.ps1 -Full` 覆盖 |

### 浏览器检查

```powershell
$env:PORTAL_USERNAME = 'preview'; $env:PORTAL_PASSWORD = 'local-ui-test-only'
$env:AOAI_ENDPOINT = 'https://example.invalid'; $env:AOAI_REASONING_EFFORT = 'low'
Start-Process python -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8015'
python tests/check_workspace_browser.py --headless --output $env:TEMP\studio-browser-check
```

预期：23 行 `PASS <步骤>`，最后输出 `{"status": "PASS", "checks": 23, ...}`。只要有请求到达 `/api/generate`、`/api/cad`、`/api/render`、`/api/concept` 或 `/api/proposal`，检查就失败（它自己发出的 `/api/cad` 请求在浏览器内用 `tests/fixtures/` 的文件应答）。检查完记得停掉服务。

### 工程渲染图

```powershell
python pregen_engineering.py aidc aps cdu coldplate drawing2d exv fourway mchx module nb_assembly_line nb_chassis_mold nb_packing nb_thermal thermal_sim vehicle_tms --out $env:TEMP\studio-engineering --no-install
```

预期：每个场景一行 JSON，带 `"ok": true` 和 `iou_pct`。去掉 `--no-install` 时，图片还会写进 `render_cache/<id>/`，工坊的「渲染图」页会直接用上。
