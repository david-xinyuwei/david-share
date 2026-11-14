# 测试

[English](TESTING.md) · [README](../README_CN.md) · [逐场景结果](RESULTS_CN.md)

测试分七层，从最便宜到最贵。前四层不需要 Azure 账号；浏览器检查和工程渲染图需要 Microsoft Edge；只有部署和在线检查会创建 Azure 资源或调用模型，要花钱。

## 每一层测什么

| 层 | 命令（未注明的都在 `studio/` 下执行） | 需要 | 检查内容 | 不检查 |
|---|---|---|---|---|
| Python 单元与契约测试，68 个 | `python -m unittest discover -s tests -p "test_*.py"` | 虚拟环境；`pregen_cad.py` 建好的 15 个参考实体 | 输出契约与解析、SSE 事件与心跳、登录与会话、输入上限、服务器托管连接（浏览器拿不到密钥）、CAD 白名单、把报错回传重试的循环、取消时终止 OCCT 子进程、预生成结果与实时结果同一格式返回、方案书 `.docx` | 真实的模型回答（模拟）和真实的 OCCT 执行（模拟）；例外是每个参考脚本都必须通过和模型输出相同的白名单，并且有最新的构建结果 |
| Node 前端测试，38 个 | `node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs` | Node.js 18 及以上；`tools/vendor_three.py` 下载的 three.js | 服务器托管模式下的连接对话框、按真实 WebGL 绘制调用判断「渲染就绪」、失败上报、PNG 与 GLB 导出规则、四视图布局与取景 | 真实的 WebGL 像素（画布是模拟的） |
| 真实 OCCT 构建，15 个实体 | `python pregen_cad.py`，再 `python pregen_cad.py --lang en` | 虚拟环境 | 每个参考脚本都经 `cad_runner.run_script` 执行并写出 STEP、STL、GLB 和 `parts.json`；英文构建与中文构建是同一批实体，只换部件名 | GPT-6 写的 CadQuery 脚本（只在实时调用时执行） |
| 仓库检查 | 在仓库根目录执行 `python -m unittest discover -s tests -v` | 只要 Python | 中英文 README 和文档的结构、链接与锚点、图片与 `images/SOURCES.json` 一致、每个结果数字都能在 `data/results.json` 里找到、架构图和测试拓扑图与各自的 HTML 源文件一致、没有私有主机名、路径或密钥 | 文字写得对不对，仍要有人读 |
| 浏览器检查，23 步 | 工坊运行在 `127.0.0.1:8015` 时执行 `python tests/check_workspace_browser.py --headless --output <dir>`（见下） | Edge；`requirements-dev.txt` | 服务端返回的文件与源码一致；打开场景时带出预生成的 STEP 实体；环境光遮蔽确实压暗零件；着色、剖切、隔离和两种导出可用；英文界面；390 px 窄屏；按当前提示词写的场景能通过同一个 bridge 渲染；没有任何请求到达模型接口 | GPU 渲染（这里用软件 WebGL）；实时模型结果 |
| 工程渲染图，15 张 | `python pregen_engineering.py <ids> --out <dir> --no-install` | Edge；`requirements-dev.txt`；`pregen_cad.py` 建好的实体 | 每个 STEP 网格都能渲染、没有对不上材质的部件，并计算同一相机下画面与 STEP 轮廓的重合度（IoU） | gpt-image 效果图（那需要 Azure） |
| 端到端部署 | 在仓库根目录执行 `./infra/up.ps1`、`./infra/verify.ps1 -Full`、`./infra/down.ps1`（README 第 2、3、5 步） | 有配额的 Azure 订阅（见 README [操作步骤](../README_CN.md#操作步骤)）、Azure CLI、PowerShell 7.3 | 按 `infra/main.bicep` 在新资源组里创建全部资源；虚拟机从仓库安装工坊，用 Let's Encrypt 证书提供 HTTPS；再通过这个地址检查：健康检查、HTTP 跳转、错误密码被拒绝、登录、15 个场景、每个场景中英文两套预生成实体、用虚拟机托管身份调用一次 GPT-6、实时 **生成 STEP** 并下载 STEP 文件、生成一张 gpt-image 概念图；删除后既没有资源组，也没有软删除状态的 AI 资源 | 虚拟机上的浏览器界面（同样的页面由浏览器检查在本机覆盖）、实时生成 three.js 网页、**生成渲染图** 和方案书；费用 |
| 在线检查，手动 | 界面上的 **实时调用 GPT-6**、**生成渲染图**、**生成方案书** | 一套部署（README 第 2 步） | 真实模型路径端到端走通 | 没有自动化；每点一次都消耗 token。**生成 STEP** 和概念图由 `verify.ps1 -Full` 覆盖 |

### 浏览器检查

```powershell
$env:PORTAL_USERNAME = 'preview'; $env:PORTAL_PASSWORD = 'local-ui-test-only'
$env:AOAI_ENDPOINT = 'https://example.invalid'; $env:AOAI_REASONING_EFFORT = 'none'
Start-Process python -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8015'
python tests/check_workspace_browser.py --headless --output ../evidence/my-browser-check
```

预期：23 行 `PASS <步骤>`，最后输出 `{"status": "PASS", "checks": 23, ...}`。只要有请求到达 `/api/generate`、`/api/cad`、`/api/render`、`/api/concept` 或 `/api/proposal`，检查就失败（它自己发出的 `/api/cad` 请求在浏览器内用 `tests/fixtures/` 的文件应答）。检查完记得停掉服务。

### 截图

按上面的方式启动工坊后，`tools/capture_screens.py` 用预生成的示例拍下 README 和 docs/RESULTS 里的截图：

```powershell
python ../tools/capture_screens.py http://127.0.0.1:8015 ../evidence/my-screens
python ../tools/capture_screens.py http://127.0.0.1:8015 ../evidence/my-screens --only features,gallery --scenarios coldplate,exv
```

第一条命令拍集成模块的六张截图。`--only` 选择其他分组：`features`（剖切和独显）、`gallery`（每个场景的 GPT-6 网页和实体）和 `render`（「渲染图」页）。`render` 需要 `render_cache/module/` 里有保存的渲染图：由 `pregen_render.py` 调用 gpt-image 部署生成，再由 `pregen_render_cad.py` 加上「与 CAD 叠放」显示的 STEP 轮廓。启动工坊时还要设置 `AOAI_IMAGE_DEPLOYMENT`，因为只有配置了图像模型部署名，「渲染图」页才会出现；`AOAI_ENDPOINT` 仍为 `https://example.invalid` 时不会调用任何模型。预期：每张截图一个 PNG，另有 `capture.json`，其中 `model_calls` 和 `page_errors` 都为空；否则工具以退出码 1 结束。

### 工程渲染图

```powershell
python pregen_engineering.py aidc aps cdu coldplate drawing2d exv fourway mchx module nb_assembly_line nb_chassis_mold nb_packing nb_thermal thermal_sim vehicle_tms --out ../evidence/my-engineering --no-install
```

预期：每个场景一行 JSON，带 `"ok": true` 和 `iou_pct`。去掉 `--no-install` 时，图片还会写进 `render_cache/<id>/`，工坊的「渲染图」页会直接用上。

## 运行记录

[`evidence/run-20261113/`](../evidence/run-20261113/) 记录了一次本机路径的完整重跑（README 第 6 步的安装和构建、README 附录里的测试），加上浏览器检查、截图和工程渲染图，在测试笔记本上的一个新建虚拟环境里执行。机器：Windows 11 Enterprise（Arm，版本 10.0.26300），Snapdragon X X1E80100 12 核，内存 63.5 GB，x64 Python 3.11.9 仿真运行，Node.js v24.18.0，Microsoft Edge 157.0.4341.57（[`machine.json`](../evidence/run-20261113/machine.json)、[`capture.json`](../evidence/run-20261113/browser/capture.json)、[`capture-gallery.json`](../evidence/run-20261113/browser/capture-gallery.json)）。第一次 Node 测试及之前的步骤在 2026-11-13 17:11（UTC+8）开始执行；下文的修复、各项重跑、浏览器检查、截图和渲染图在 2026-11-14 执行。全程没有调用模型。耗时包括 pip 下载和 x64 仿真的开销。

| 步骤 | 命令（除注明外在 `studio/` 里执行） | 结果 | 耗时（s） |
|---|---|---|---|
| 安装锁定版本的依赖 | `pip install -r requirements.txt -c deploy/constraints.txt` | 退出码 0 | 776.7 |
| 安装浏览器和图像工具 | `pip install -r ../requirements-dev.txt` | 退出码 0；此后 [`pip-freeze.txt`](../evidence/run-20261113/pip-freeze.txt) 共 82 个包 | 63.9 |
| 校验 three.js | `python ../tools/vendor_three.py --check` | 15 / 15 个文件校验通过 | 3.0 |
| 建 15 个 STEP 实体 | `python pregen_cad.py` | 15 / 15 成功，失败：无 | 1025.0 |
| 英文部件名，第一次 | `python pregen_cad.py --lang en` | **失败**：13 / 15 成功，失败：coldplate, module（见下文） | 406.7 |
| Python 测试 | `python -m unittest discover -s tests -p "test_*.py"` | 68 个测试，OK | 29.4 |
| Node 测试 | `node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs` | 38 个测试：38 通过，0 失败 | 2.0 |
| 修复后重建英文部件名 | `python pregen_cad.py --lang en --force` | 15 / 15 成功，失败：无 | 266.5 |
| 再跑 Python 测试 | 同上 | 68 个测试，OK | 14.0 |
| 再跑 Node 测试 | 同上 | 38 个测试：38 通过，0 失败 | 1.4 |
| 浏览器检查 | `python tests/check_workspace_browser.py --headless --output <dir>` | PASS：23 / 23 项通过，模型调用：0 | 230.4 |
| 截图 | `python ../tools/capture_screens.py http://127.0.0.1:8015 <dir>` | 6 张，模型调用：0 | 126.9 |
| 工程渲染图 | `python pregen_engineering.py <15 ids> --out <dir> --no-install` | 退出码 0；15 / 15 张的每个网格都对上了部件 | 192.0 |
| 更多截图 | `python ../tools/capture_screens.py http://127.0.0.1:8015 <dir> --only <group> --langs <lang> --scenarios <ids>` | 11 / 11 批完成，每批一个进程：新截图 66 张，另有重拍的 6 张模块截图（未发布）；模型调用：0；自身报错的 GPT-6 网页：1；3 批共失败 8 次，修复后重跑通过（见下文） | 3223.1 |

**哪一步失败了，改了什么。** 第一次构建英文部件名时，电池水冷板和热管理集成模块报 `STEP string count differs` 而中止。`pregen_cad.py --lang en` 会关掉锐边倒钝，同时构建中文脚本和英文脚本，确认两者建出的是同一个实体，再把两份 STEP 里的字符串按位置一一配对，把英文名写进中文 STEP。两个 OCCT 进程同时运行时，一份 STEP 把四个圆写成了 B 样条曲线，另一份写成圆。实体本身相同（体积、表面积和面数一致），但前一份文件多出 16 个无名（`''`）字符串，两份列表按位置对不齐，构建随即中止。两个脚本先后单独构建，各自三次得到的文件完全相同；同时构建，在这个环境和同一台笔记本上的另一个 Python 环境里都出现了差异。并发为什么会改变 OCCT 的输出，没有深究。修复的做法是只配对非空字符串（部件名、单位、上下文），它们的顺序不会变。[`fix-step-name-alignment.json`](../evidence/run-20261113/fix-step-name-alignment.json) 在两份用同样方式构建、能复现这个失败的冷板 STEP 上，分别用新旧两种配对方式：旧方式下字符串数 14,538 对 14,522；新方式下非空字符串 1,080 对 1,080，配对出 5 个名字，没有冲突，也没有残留中文。随后用 `--force` 重建了全部 15 个英文缓存。

**失败过的几批截图。** 更多截图按批运行，每批一种语言、最多五个场景，各用一个进程，失败后重试一次；表里的耗时包含每一次尝试，[`status_screens.json`](../evidence/run-20261113/status_screens.json) 逐次列出。有三批失败，都在修复后重跑；其中一次尝试在修复之前只会重复同一个失败，被手动停止（退出码 `-1`）：

- 笔记本组卡片，英文：在第一张笔记本卡片处中止，报 `Cannot read properties of null (reading 'click')`。工坊一次只列出一个行业分组（热管理或笔记本）的卡片，而 `capture_screens.py` 去找的是另一组的卡片。现在 `open_scenario()` 会先加载场景所在的分组。
- 笔记本组卡片，中文：GPT-6 为「笔记本总装产线数字孪生」写的中文网页在画出产线之后，从动画循环里抛出 `TypeError: Cannot read properties of undefined (reading 'x')`（[详情](RESULTS_CN.md#15-个场景一览)）。工坊随即报告场景没有渲染成功，布局按钮一直不可用，工具就一直在等。现在工具按网页当时的样子截图，并把工坊的报错文字作为 `scene_error` 和这张截图一起记入 `capture-gallery.json`；其他任何页面错误仍会让运行失败。
- 渲染页：这一批找不到 **渲染图** 页。只有服务器配置了图像模型部署名，工坊才显示这一页，而运行脚本没有设 `AOAI_IMAGE_DEPLOYMENT`。重跑时设上了它；端点仍是 `https://example.invalid`，不可能调用到任何图像模型。

之后用最终版工具把两批笔记本卡片又各拍了一遍。最终版只要 **原场景** 可用就点击它：网页刚渲染完时，这个按钮可能还显示着上一个状态。热管理组的几批用的是修复前的工具：它们的卡片属于工坊打开时的默认分组，每个网页都渲染成功并响应了 **原场景** 点击，所以这些修复不改变它们拍到的内容。

**环境。** `deploy/constraints.txt` 只锁定工坊直接导入的 10 个包；其余的包在 2026-11-13 从 PyPI 解析，例如 python-dateutil 4.0.0、multidict 7.2.1、trame 4.0.0。[`pip-freeze.txt`](../evidence/run-20261113/pip-freeze.txt) 列出了这次运行的全部版本；要把所有包都锁定，可以改为从这个文件安装（`pip install -r ../evidence/run-20261113/pip-freeze.txt`，没有在别的机器上试过）。`studio/app.py` 导入了 aiohttp，而 `requirements.txt` 没有列出它：它随 CadQuery 一起装进来（cadquery → trame → wslink → aiohttp）。

**这次运行不包括的：** Azure 部署（下面单独记录）和在线检查。30 份已记录的 GPT-6 回答和各场景的 gpt-image 效果图，是更早用工坊自己的部署生成的（2026-09-09 至 2026-09-12，以及 2026-11-10）。

## 部署记录

[`evidence/deploy-20261114/`](../evidence/deploy-20261114/) 记录了 README 第 2、3、5 步在 2026-11-14 的一次完整运行：`up.ps1`、`verify.ps1 -Full` 和 `down.ps1 -Yes`，在测试笔记本（Windows 11 Arm 版，Azure CLI 2.92.0，PowerShell 7.7.0）上执行，部署到 East US 2 的一个新资源组；事先只做了 `az login`。`up.json`、`verify.json`、`down.json` 记录每一步、每一项检查的状态和耗时；`up-output.txt`、`verify-output.txt`、`down-output.txt` 是各脚本的输出，去掉了显示订阅的那一行；`infra-sha256.json` 是这次运行用的五个 `infra/` 文件的 SHA-256，也就是本版本里的这些文件。所有文件里，部署名称中唯一的那段后缀都换成了 `<hash>`。

| 步骤 | 命令 | 结果 | 耗时（min） |
|---|---|---|---|
| 预检 | `up.ps1` 第 1/5 步 | East US 2 提供这两个模型；gpt-6-astra 用 Data Zone Standard，因为订阅的 Global Standard 配额已经用完；虚拟机规格 `Standard_D4as_v6`，即列表里该区域对订阅开放的第一个 | 2.7 |
| 资源组 | `up.ps1` 第 2/5 步 | 已创建 | 0.2 |
| Azure 资源 | `up.ps1` 第 3/5 步：`infra/main.bicep` | AI 资源及两个模型部署、身份与角色、网络、虚拟机 | 0.8 |
| 虚拟机上安装 | `up.ps1` 第 4/5 步：通过 Run Command 执行 `infra/vm-install.sh` | `studio/` 取自 `master` 的 `d32e1e6e`；中文部件名和英文部件名的参考实体各 15 个，其中笔记本双风扇散热模组没有锐边倒钝（见下文）；虚拟机上通过 HTTPS 访问 `/healthz`：200 | 10.3 |
| HTTPS 检查 | `up.ps1` 第 5/5 步 | 笔记本访问 `/healthz`：`{"ok":true,"deployment":"gpt-6-astra",...}` | < 0.1 |
| 通过公网地址检查 | `verify.ps1 -Full` | 10 项全部通过 | 2.1 |
| 删除 | `down.ps1 -Yes` | 资源组已删除，AI 资源已清除，没有残留 | 4.4 |

**`verify.ps1 -Full` 里的实时生成 STEP。** 向 `/api/cad` 发了一个请求：带 6 道 S 形流道的铝制电池水冷板，要求推理强度 `none`。结果：用了 1 次尝试、91.5 s，其中 OpenCascade 6.7 s，得到 4 个实体、315 个面、1.580 kg，STEP 文件 1.1 MB。部署没有接受 `none`：工坊回复里的推理强度为空（[`verify.json`](../evidence/deploy-20261114/verify.json) 里的 `"reasoning_effort": null`），而 `d32e1e6e` 的 `studio/app.py` 只有在部署拒绝这个参数、工坊去掉它重发请求之后才会留空。所以 GPT-6 是按部署的默认推理强度运行的，推理用了 1,472 个 token。现在的 `studio/app.py` 改发部署接受的下一档（`none` 改成 `low`，见 README 第 4 步）。这只是一个请求，用来确认这条路径走得通，不是典型耗时的测量。

**部署上的浏览器检查。** 在 `verify.ps1` 和 `down.ps1` 之间，作者用一个 Playwright 脚本（不在本仓库里）驱动无头 Microsoft Edge，在部署好的地址上走了一遍 README 第 4 步的开头。这个地址提供的前端与所装提交的文件逐字节一致，打开的是页面自带的登录表单，没有浏览器的身份验证弹窗；错误密码在页面上被拒绝；中英文界面的冷板和笔记本双风扇散热模组都以预生成示例打开，徽标、来源栏和部件与第 4 步的描述一致，下载链接背后是 STEP 文件。页面没有向模型接口发出请求，也没有报错。每项检查记录在 [`browser.json`](../evidence/deploy-20261114/browser.json)。

**这次之前失败过什么，改了什么。** 同一天更早的时候，`up.ps1` 在另一个资源组里运行了五次。前四次因为几处缺陷中途停下，每次都先修好再跑下一次；这些缺陷，旧 README 的手敲步骤是暴露不出来的。本次运行用的脚本已经包含修复：

- `up.ps1` 在预检阶段停下。资源组还不存在时，`az cognitiveservices account list -g` 什么也不返回，在 `Set-StrictMode` 下，管道里的这个空结果会报错。现在筛选时跳过空结果。
- 部署模板被拒绝，报 `SkuNotAvailable`。East US 2 对测试订阅不开放任何 `Standard_D4*_v5` 或 `_v4` 规格，只开放 `_v6` 规格，而 `_v6` 只支持 NVMe 磁盘控制器。现在 `up.ps1` 从候选列表里选第一个开放的规格，并相应设置磁盘控制器。
- 虚拟机上，第 1/7 步一直等到超时，因为它把常驻的 unattended-upgrades 守护进程当成了正在运行的软件包任务；第 3/7 步报 `Permission denied`：`bootstrap_vm.sh` 以用户 `studio` 的身份读取 `requirements.txt` 和 `constraints.txt`，而它们所在的临时目录只有 root 能读。现在 `vm-install.sh` 只等真正在运行的 apt 任务，并把这个目录设为可读。
- 第四次运行停在第 6/7 步：15 个实体建成了 14 个，笔记本双风扇散热模组在 131 s 后崩溃，退出码 -11。在同一台虚拟机上重建，又在同一位置崩溃了两次，是 OpenCascade 7.9.3 的 `libTKBRep` 段错误；关掉锐边倒钝后 7.2 s 建成。笔记本上的离线运行没有遇到这个崩溃：它用的是同一版本 OpenCascade 的 Windows 构建。现在 `vm-install.sh` 会把这一步失败的实体再建一次，不做锐边倒钝，并以 `no_edge_break` 报告。
- 第五次运行仍在同一个资源组里：`up.ps1` 保留了已有资源、虚拟机规格和密码，并完成了安装，这正是 README 第 2 步说的更新路径；之后 `verify.ps1 -Full` 和 `down.ps1 -Yes` 也都通过了。

**没有覆盖的：** 浏览器里第 4 步的其余部分：**实时调用 GPT-6**（实时生成 three.js 网页）、在页面上点击**生成 STEP**（`verify.ps1 -Full` 通过 API 发过同类请求）、**生成渲染图**和方案书；用 macOS 或 Linux 运行 `up.ps1`；以及这次运行的费用。
