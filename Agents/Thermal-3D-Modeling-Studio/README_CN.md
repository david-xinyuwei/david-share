# 热管理 3D 建模工坊：Azure OpenAI GPT-6 Astra 写建模代码，OpenCascade 出 STEP

[![Model](https://img.shields.io/badge/model-GPT--6%20Astra%202026--09--03-0078D4)](#目的)
[![Deploy](https://img.shields.io/badge/deploy-Bicep%20%2B%20one%20script-0078D4)](#操作步骤)
[![CAD kernel](https://img.shields.io/badge/CAD-CadQuery%202.8%20%C2%B7%20OpenCascade-0078D4)](#本页用到的术语)
[![Scenarios](https://img.shields.io/badge/scenarios-15%20%C2%B7%20English%20%2B%20Chinese-0078D4)](#实现效果)
[![Offline tests](https://img.shields.io/badge/offline%20tests-Python%20%2B%20Node-0078D4)](docs/TESTING_CN.md)

作者：Xinyu Wei · [English](README.md)

## 目的

热管理研发工程师开一个新零件，手里往往只有一句话或一张二维图纸：「320 × 180 × 12 mm 的铝制水冷板，6 道 S 形流道」、一个电子膨胀阀阀体、一个带泵和阀的集成模块。打开 SolidWorks 之前，团队想先把这个想法转起来看看，估一下质量和换热面积，对比两个版本，再拿去评审。文生图、文生网格模型给出的是一张图或一个网格，没有尺寸、没有质量，也没有 STEP 文件。

这个工坊换了个做法：让 Microsoft Foundry 上的 **GPT-6 Astra** 写代码，而不是画图。**轨 A** 里它写一整页 three.js 代码，浏览器渲染成可交互的概念模型；**轨 B** 里它写一段 CadQuery 脚本，由 **OpenCascade** 内核建成 STEP 实体，体积和质量按精确几何算出。图像模型只用来出展示图（轨 C、轨 D）。

工坊由本仓库替你部署。一个脚本 `infra/up.ps1` 创建 Azure 资源（模型部署、托管身份及其角色、网络和一台 Ubuntu 虚拟机），把工坊装到虚拟机上并通过 HTTPS 对外服务；`infra/verify.ps1` 从外部检查部署结果，`infra/down.ps1` 删除全部资源（见[操作步骤](#操作步骤)）。

| 交付内容 | 位置 | 用途 |
|---|---|---|
| 自动化部署 | `infra/`：`main.bicep`、`up.ps1`、`verify.ps1`、`down.ps1`、`vm-install.sh` | 创建全部 Azure 资源和虚拟机，安装工坊并通过 HTTPS 对外服务，从外部检查，最后删除 |
| 工坊应用 | `studio/`：FastAPI 后端 + 浏览器前端 | 应用本体；15 张场景卡片分两组（热管理部件、笔记本制造），中英文界面 |
| 提示词与输出契约 | `studio/scenarios.py`、`studio/app.py` 里的 `CAD_PROMPT` | 看清 GPT-6 收到的规则：three.js 网页分四个标记区块输出，CadQuery 脚本要定义 `PARTS` / `MATERIALS` |
| CAD 执行器 | `studio/cad_runner.py` | 安全执行模型写的 CadQuery：白名单检查、单独进程、导出 STEP / STL / GLB、自动锐边倒钝 |
| 15 个 CadQuery 参考脚本 | `studio/cad_examples/`、`studio/cad_examples_en/` | 不调用模型就能建出 15 个 STEP 实体；`coldplate.py` 同时是 GPT-6 提示词里的示例 |
| 30 份已记录的 GPT-6 回答 | `studio/cache/` | 不调用 Azure 也能秒开每个场景 |
| 虚拟机安装脚本 | `studio/deploy/` | `infra/vm-install.sh` 在虚拟机上调用的主机初始化和安装脚本，以及 nginx 和 systemd 配置；`deploy.ps1` 通过 SSH 把本地工作副本推到已有的虚拟机 |
| 测试 | `studio/tests/` | 离线检查你的副本；每个测试查什么，见 [docs/TESTING_CN.md](docs/TESTING_CN.md) |

这个工坊不是什么：

- 轨 A 模型旁边的工程量是 GPT-6 自己估的。轨 B 的体积、质量、包络和表面积是精确计算的，但算的是 GPT-6（或参考脚本）按描述重建的实体：没有公差和图纸的概念件，不是经过校核的设计。
- gpt-image 出的图是示意图，模型可能改动比例和细节。轨 C 里和 STEP 对得上的是工程渲染图。
- 一次实时调用要等几分钟，并消耗 token。浏览 15 个已记录的示例不调用任何模型。

| 职责 | Microsoft Foundry | 本仓库 | 你 |
|---|---|---|---|
| 模型 | 运行 GPT-6 Astra、gpt-image-2.5，以及可选的 MAI-Image-2.6 | 提示词和输出契约；`infra/main.bicep` 创建模型部署 | 配额；支付 token 费用 |
| 运行工坊 | — | 应用、CAD 执行器，以及创建虚拟机并安装工坊的部署脚本 | 一个能创建资源、能分配角色的 Azure 订阅；虚拟机运行期间的费用 |
| 工程决策 | — | 生成实体的精确 B-rep 数据 | 设计评审、公差、发布 |

<img src="images/architecture-zh.png" width="900" alt="系统架构：四条轨经过浏览器、Azure 虚拟机和 Microsoft Foundry。轨 A：浏览器运行 GPT-6 写的 three.js 网页，后端组装提示词并流式转发 GPT-6 Astra 的回答。轨 B：CAD 执行器检查并执行 GPT-6 写的 CadQuery 脚本，由 OpenCascade 导出 STEP。轨 C：gpt-image-2.5 重画截图，工程渲染器直接渲染 STEP 网格、不调模型。轨 D：gpt-image-2.5 或 MAI-Image-2.6 出概念图。模型调用使用虚拟机的托管身份。">

图上画的是：四条轨各经过哪些组件、哪些代码是我们写的、各调用哪个模型；图中的虚拟机和 Foundry 一侧都由 `infra/up.ps1` 创建。这是原创解释图。

### 一次请求怎么走

1. **轨 A：3D 模型。** 浏览器把对话发到 `/api/generate`。后端加上系统提示词（输出契约 + 该场景的建模规范），通过 SSE 把 GPT-6 Astra 的回答流式转给浏览器。GPT-6 按四个标记区块输出：`<<<SUMMARY>>>` 摘要、`<<<HTML>>>` 里一整页 three.js 代码、`<<<METRICS>>>` 里 JSON 格式的工程量，以及 3 条后续建议。HTML 区块一结束，浏览器就在沙箱 iframe 里开始渲染，工程量接着往下流。对话里保留最近 3 轮模型回答，所以说「流道改成 8 道」就是在上一版上改。
2. **轨 B：CAD 实体。** 点 **生成 STEP**，同一个零件（你的需求、GPT-6 的摘要、three.js 网页里的 `const P = {...}` 参数块）发到 `/api/cad`。GPT-6 写一段 CadQuery 脚本。`cad_runner.py` 先解析，白名单之外的一律拒绝（只允许 `cadquery`、`math` 等少数标准模块，不允许 `open`、`exec` 和导出函数），再放进一个不带服务器 Azure 配置的单独 Python 进程执行，用 R0.3–1.2 mm 圆角给锐边倒钝，导出 `model.step`（带部件名的装配体）、`model.stl`、`model.glb` 和 `parts.json`。体积、质量、包络和表面积由 OpenCascade 按精确几何计算。脚本报错时，错误信息回传给 GPT-6 改写，最多 3 次。
3. **轨 C：渲染图。** **生成渲染图** 把当前 3D 视图的 WebGL 截图交给 gpt-image-2.5（`images.edit`）重画。工程渲染图则用 three.js 直接画 STEP 的网格，和 STEP 轮廓线用的是同一个相机，所以两者重合，全程不经过图像模型。
4. **轨 D：概念图。** 还没有 3D 的时候，一句话先变成一张概念图（gpt-image-2.5，或可以先上网检索再画的 MAI-Image-2.6）；点 **用这张图建 3D** 就把它作为参考图附到轨 A 的请求里。
5. **方案书。** **生成方案书** 用 python-docx 把需求、截图、工程量和 STEP 信息排成 Word 文档，再调用一次 GPT-6 写方案要点、风险和下一步。
6. **登录与密钥。** 访客登录工坊后，所有模型调用都走服务器自己的连接。虚拟机上，后端用托管身份换取 Microsoft Entra 令牌；本机用 `az login`。浏览器拿不到任何密钥或令牌。

### 本页用到的术语

| 术语 | 在这里的意思 |
|---|---|
| three.js、WebGL | 一个 JavaScript 3D 库，以及它调用的浏览器绘图接口；轨 A 的产出就是一页 three.js 代码 |
| B-rep（边界表示） | CAD 描述实体的方法：用精确的面（平面、圆柱面、自由曲面）围成一个封闭的体，面与面相交得到边。一个 Ø6 mm 的孔是半径 3 mm 的圆柱面，而不是一圈三角形 |
| OpenCascade（OCCT） | 开源几何内核：构建 B-rep 实体，做布尔运算和圆角，读写 STEP |
| CadQuery | 用 Python 代码描述零件的库，底层调用 OpenCascade |
| STEP（`.step`，ISO 10303） | CAD 软件之间交换模型的标准格式；把精确的 B-rep 和部件名带进 SolidWorks、NX、Creo |
| STL、GLB（glTF） | 三角网格格式。STL 用于 3D 打印和预览；GLB 用于网页，带材质和部件树。工坊通过 STEP 导出的 GLB 来显示 STEP |
| 工程渲染图 | 用 three.js 直接画出的 STEP 网格图片，不经过图像模型，和 STEP 对得上 |
| 推理强度（reasoning effort） | GPT-6 回答前思考多久：gpt-6-astra 接受 `low`、`medium`、`high`、`xhigh`。`.env.example` 把服务器默认值设为 `low`；发送按钮旁的下拉框可以按次修改 |
| SSE（服务器推送事件） | 后端把 token、进度和心跳持续推给浏览器的通道 |
| Bicep | Azure 用来声明资源的语言；`infra/main.bicep` 列出工坊需要的全部资源 |
| 托管身份（managed identity） | Azure 分配给虚拟机的身份。工坊用它换取 Microsoft Entra 令牌来调用模型，所以任何地方都不存密钥 |
| Run Command | 通过 Azure 控制面在虚拟机里执行脚本；`up.ps1` 用它安装工坊，不需要 SSH 连接 |

## 实现效果

**视频。** 两段英文讲解，长度分别为 7:22 和 6:21。两段都是工坊的录屏，经过剪辑，配了旁白和字幕。

*预生成示例。* 先讲架构，再打开保存好的 GPT-6 网页和预生成的 STEP 实体，全程不调用模型：电子膨胀阀的 three.js 网页和 GPT-6 写的代码、剖切开的 OCCT 实体、叠上 STEP 轮廓的 gpt-image 效果图与工程渲染图、四通阀的减铜方案对比，以及从图纸重建 3D。视频讲的是热管理组的卡片；架构图是剪进录屏之间的。

https://github.com/user-attachments/assets/66148365-f3aa-44a7-a129-cef898e68cb3

*实时生成。* 向部署在 Azure 虚拟机上的工坊实时发出一个请求：电池水冷板，流道从 6 道改成 8 道。GPT-6 Astra 流式写出 three.js 网页，**生成 STEP** 让它写 CadQuery 脚本、由 OpenCascade 建出实体，**生成渲染图** 调用 gpt-image-2.5。所有等待都按真实时间播放，没有剪掉。这是演示，不是测量。

https://github.com/user-attachments/assets/7ee81aaa-a5f8-46e3-aae7-0410739226ed

下面是 15 个场景之一「热管理集成模块」在工坊里的样子。截图和工程渲染图拍自预生成示例，没有调用模型；gpt-image 效果图是通过工坊页面调用一次生成的。所有图片都没有修过。

| 轨 A：GPT-6 写的 three.js 网页（已记录的回答） | 轨 B：同一个零件的 OCCT 实体，四视图 |
|---|---|
| <img src="images/track-a-concept-zh.jpg" width="440" alt="中文界面里的热管理集成模块，打开的是已记录的 GPT-6 回答。来源栏写着「当前模型：预生成示例（本次未调用 GPT-6）」；主视口显示 GPT-6 写的 three.js 概念模型，右侧大纲列出它的部件。"> | <img src="images/track-b-brep-quad-zh.jpg" width="440" alt="同一场景的 OCCT B-rep 实体，四视图显示顶视、透视、前视和右视。徽标说明这是与 STEP 一致的预生成 B-rep 实体，大纲列出歧管、阀、泵、换热器和快插接头等部件。"> |

| 轨 C：gpt-image-2.5 重画的 3D 截图（示意） | 轨 C：STEP 网格的工程渲染图，青色线是 STEP 的轮廓和棱线 |
|---|---|
| <img src="images/module-gpt-image-render.jpg" width="440" alt="gpt-image-2.5 生成的集成模块图片：影棚产品照风格，黑色带筋的歧管上装着铝制阀和水泵、不锈钢板式换热器和快插接头。这是图像模型根据 3D 截图重画的示意图，不是几何。"> | <img src="images/module-engineering-render-step-lines.jpg" width="440" alt="按 STEP 网格渲染的集成模块工程渲染图，浅色影棚背景，青色的 STEP 轮廓和棱线落在零件上。"> |

**怎么看这几张图。** 上面一行是同一个零件的两种形态：左边是 GPT-6 写的网页，形状和它给出的工程量都是模型自己的；右边是参考脚本建出的精确实体，由 OCCT 计量。下面一行，gpt-image-2.5 把 3D 视图的截图变成照片一样的图片，但零件是模型重画的，细节可能和 STEP 不一样；工程渲染图直接画 STEP 自己的网格，所以青色的 STEP 轮廓正好落在零件上。

### 更多场景

另外六个场景。左边是 GPT-6 为场景卡片写的网页，按原样显示：场景、数据面板和按钮都是模型自己写的；右边是参考脚本建出的 OCCT 实体，显示在工坊的视口里。部署好之后，全部 15 个场景都能在工坊里打开。

| 场景 | 轨 A：GPT-6 写的网页（已记录的回答） | 轨 B：参考脚本建出的 OCCT 实体 |
|---|---|---|
| 电池水冷板 | <img src="images/gallery-coldplate-gpt6-zh.jpg" width="360" alt="电池水冷板：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="images/gallery-coldplate-brep-zh.jpg" width="360" alt="电池水冷板：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> |
| 电子膨胀阀阀体 | <img src="images/gallery-exv-gpt6-zh.jpg" width="360" alt="电子膨胀阀阀体：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="images/gallery-exv-brep-zh.jpg" width="360" alt="电子膨胀阀阀体：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> |
| 微通道换热器 | <img src="images/gallery-mchx-gpt6-zh.jpg" width="360" alt="微通道换热器：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="images/gallery-mchx-brep-zh.jpg" width="360" alt="微通道换热器：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> |
| AIDC CDU 液冷分配单元 | <img src="images/gallery-cdu-gpt6-zh.jpg" width="360" alt="AIDC CDU 液冷分配单元：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="images/gallery-cdu-brep-zh.jpg" width="360" alt="AIDC CDU 液冷分配单元：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> |
| 整车热管理系统回路 | <img src="images/gallery-vehicle_tms-gpt6-zh.jpg" width="360" alt="整车热管理系统回路：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="images/gallery-vehicle_tms-brep-zh.jpg" width="360" alt="整车热管理系统回路：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> |
| 笔记本双风扇散热模组 | <img src="images/gallery-nb_thermal-gpt6-zh.jpg" width="360" alt="笔记本双风扇散热模组：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="images/gallery-nb_thermal-brep-zh.jpg" width="360" alt="笔记本双风扇散热模组：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> |

### 实体可以怎么看

视口通过和 STEP 一起导出的网格显示 B-rep 实体，所以查看器的工具作用在真实的零件几何上，而不是 GPT-6 写的场景上。

| 剖切：法向为 Y 的平面，四视图 | 独显选中：只显示实体的一个部件 |
|---|---|
| <img src="images/feature-section-zh.jpg" width="440" alt="电池水冷板 B-rep 的四视图，剖切选 Y：一个水平面切开水冷板，顶视图和透视图能看进板内的蛇形流道，前视图和右视图里是侧面看过去的薄板。大纲列出流道基板、上盖板、进口接头和出口接头。"> | <img src="images/feature-isolate-zh.jpg" width="440" alt="电池水冷板 B-rep 在透视图里执行独显选中之后：只显示带橙色轮廓的流道基板，能看到蛇形流道槽和安装耳；大纲里只有流道基板仍然勾选。"> |

**剖切** 选 Y 时，一个水平面切开电池水冷板，顶视图和透视图能看进板内的蛇形流道。**独显选中** 时，只剩在大纲里选中的部件，这里是流道基板，基板上的流道槽一目了然。

| 你想 | 去看 |
|---|---|
| 了解每层测试查什么、不查什么 | [docs/TESTING_CN.md](docs/TESTING_CN.md) |
| 查第三方组件的许可和图片来源 | [NOTICE.md](NOTICE.md) |

| 目录 | 内容 |
|---|---|
| `infra/` | 部署：`main.bicep`（全部 Azure 资源）、`up.ps1`（创建并安装）、`vm-install.sh`（在虚拟机上执行的安装）、`verify.ps1`（从外部检查）、`down.ps1`（删除） |
| `studio/` | 应用本体：FastAPI 后端（`app.py`）、前端（`static/`）、CAD 执行器、提示词（`scenarios.py`）、已记录的 GPT-6 回答（`cache/`）、CadQuery 参考脚本、虚拟机安装脚本（`deploy/`）和应用自己的测试（`tests/`） |
| `tools/` | `vendor_three.py`：下载 three.js 并按固定哈希校验（第 6 步） |
| `images/` | 本页用到的截图、渲染图和架构图 |
| `docs/` | 测试说明，中英文各一份 |

## 操作步骤

| 顺序 | 在哪里 | 做什么 | 命令 | 大约耗时 |
|---|---|---|---|---|
| 1 | 你的电脑 | 获取代码，登录 Azure | `git clone ...`、`az login` | — |
| 2 | 你的电脑 → Azure | 创建全部资源，把工坊装到一台新虚拟机上 | `./infra/up.ps1 -ResourceGroup <名称> -Location <区域>` | 14 min |
| 3 | 你的电脑 | 通过 HTTPS 地址检查部署结果 | `./infra/verify.ps1 -ResourceGroup <名称> -Full` | 2 min |
| 4 | 浏览器 | 登录，打开已记录的示例，做一次实时调用 | `https://thermal-<hash>.<区域>.cloudapp.azure.com/` | — |
| 5 | 你的电脑 | 删除全部资源 | `./infra/down.ps1 -ResourceGroup <名称>` | 4 min |
| 6 | 你的电脑（可选） | 在本机运行工坊，调用已部署的模型，用于开发 | `python -m uvicorn app:app --env-file .env` | — |

耗时随区域和虚拟机规格变化；第 2 步的大部分时间是虚拟机在建 15 个参考 STEP 实体（加 `-SkipReferenceSolids` 可跳过）。

**准备条件。**

- 一个能创建资源组、能分配角色的 Azure 订阅：所有者（Owner），或参与者（Contributor）加基于角色的访问控制管理员（Role Based Access Control Administrator）。模板要给虚拟机的身份在模型资源上分配一个角色。
- 该区域的配额：`gpt-6-astra` 每分钟 100K token（Global Standard 或 Data Zone Standard，`up.ps1` 选有空余配额的那种），`gpt-image-2.5-sunburst` 2 个单位（或者加 `-SkipImageModel`，这样轨 C、轨 D 不可用），以及虚拟机要用的 4 个 vCPU。`up.ps1` 在创建任何资源之前先检查这三项。
- Azure CLI（已用 2.92.0 测试；Bicep 第一次用时自动安装）、PowerShell 7.3 及以上（已用 7.7.0 测试），以及 OpenSSH 客户端里的 `ssh-keygen`，用来生成虚拟机的密钥对。已在 Windows 11 上测试；脚本里没有只能在 Windows 上用的命令，但没有在 macOS 和 Linux 上测试过。
- 本机不需要别的：虚拟机自己从本仓库下载工坊，所有构建都在虚拟机上完成。

### 1. 获取代码并登录

```powershell
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Agents/Thermal-3D-Modeling-Studio
cd Agents/Thermal-3D-Modeling-Studio
az login
az account set --subscription <订阅名称或 ID>
```

预期：`az account show -o table` 显示的是你要部署到的订阅。

### 2. 部署

```powershell
./infra/up.ps1 -ResourceGroup rg-thermal-studio -Location eastus2
```

输出示例（区域、配额、虚拟机规格、名称、时间和提交号以你的部署为准；省略了订阅那一行；`up.ps1` 打印的是本机时间，来自虚拟机的缩进行是 UTC 时间）：

```text
[15:08:49] 1/5 preflight: Azure CLI, sign-in, model quota
   models offered in eastus2: gpt-6-astra 2026-09-03, gpt-image-2.5-sunburst 2026-09-08
   gpt-6-astra GlobalStandard in eastus2: 0 K tokens/min free, 100 needed
   gpt-6-astra DataZoneStandard in eastus2: 333 K tokens/min free, 100 needed
   gpt-image-2.5-sunburst GlobalStandard in eastus2: 2 free, 2 needed
   VM sizes offered to this subscription in eastus2 (about a minute)
   VM size Standard_D4as_v6, disk controller NVMe
[15:11:33] 2/5 resource group rg-thermal-studio
   created in eastus2
[15:11:44] 3/5 Azure resources (infra/main.bicep): AI resource and models, identity and role, network, VM
   thermal-vm at thermal-<hash>.eastus2.cloudapp.azure.com; models on https://thermal-ai-<hash>.openai.azure.com: gpt-6-astra (DataZoneStandard), gpt-image-2.5-sunburst
[15:12:31] 4/5 install on the VM through Run Command (infra/vm-install.sh): the longest step, silent until it ends
   [07:12:43] install log: /var/log/thermal-install.log
   [07:12:43] 1/7 waiting for the first-boot package jobs
   [07:12:44] 2/7 fetching Agents/Thermal-3D-Modeling-Studio/studio from https://github.com/david-xinyuwei/david-share.git at master
   [07:12:45]    commit <commit>
   [07:12:45] 3/7 host setup: packages, Python venv with pinned packages, nginx, certificate for thermal-<hash>.eastus2.cloudapp.azure.com
   [07:14:23]    Python 3.12.3, cadquery 2.8.0
   [07:14:23] 4/7 settings: /opt/thermal-3d-studio/.env
   [07:14:23] 5/7 code, three.js and the systemd service
   [07:14:27] 6/7 building the 15 reference STEP solids with OpenCascade (no model call)
   [07:21:25]    failed in the edge-break pass: nb_thermal; building them again without the edge break
   [07:21:32]    Chinese part names: done in 425 s
   [07:22:45]    English part names: done in 73 s
   [07:22:45] 7/7 restart and health checks
   [07:22:47] THERMAL_INSTALL=PASS commit=<commit> solids_zh=15 solids_en=15 no_edge_break=nb_thermal https_from_vm=200 seconds=604
[15:22:50] 5/5 HTTPS check from this machine: https://thermal-<hash>.eastus2.cloudapp.azure.com/healthz
   {"ok":true,"deployment":"gpt-6-astra","uptime_s":3}

Thermal 3D Modeling Studio is running
  Open      https://thermal-<hash>.eastus2.cloudapp.azure.com/
  Sign in   user studio; password in ~/.thermal-3d-studio/rg-thermal-studio/portal-password.txt
  Check     ./infra/verify.ps1 -ResourceGroup rg-thermal-studio
  Remove    ./infra/down.ps1 -ResourceGroup rg-thermal-studio
  The VM bills while it runs; the model deployments bill per token.
receipt: ~/.thermal-3d-studio/rg-thermal-studio/up-20261114-150849.json (PASS)
```

它会在这一个资源组里创建：

| 资源 | 名称 | 用途 |
|---|---|---|
| Azure AI 资源及两个模型部署 | `thermal-ai-<hash>`：`gpt-6-astra`（版本 2026-09-03）、`gpt-image-2.5-sunburst`（2026-09-08） | 模型；只允许 Microsoft Entra 登录，本地密钥已禁用 |
| 用户分配的托管身份及其角色 | `thermal-vm-identity`，在 AI 资源上具有 **Cognitive Services OpenAI User** 角色 | 让虚拟机不用密钥就能调用模型 |
| 网络 | `thermal-vnet`、`thermal-nsg`（入站只放行 443 和 80）、`thermal-ip`，DNS 名称为 `thermal-<hash>.<区域>.cloudapp.azure.com` | 任何地方都能用 HTTPS 访问；80 端口用于申请 Let's Encrypt 证书和跳转到 HTTPS |
| 虚拟机 | `thermal-vm`：Ubuntu 24.04、4 个 vCPU、64 GB 磁盘、受信任启动 | 运行 nginx 和工坊；规格取该区域对你开放的第一个：`Standard_D4as_v5`、`Standard_D4s_v5`、`Standard_D4ads_v5`、`Standard_D4ds_v5`、`Standard_D4as_v6`、`Standard_D4ads_v6`、`Standard_D4s_v6`、`Standard_D4as_v4`、`Standard_D4s_v4` |

虚拟机上，Run Command 以 root 身份执行 [`infra/vm-install.sh`](infra/vm-install.sh)。它从本仓库下载 `-RepoRef`（默认 `master`）对应的 `studio/`，执行 `studio/deploy/bootstrap_vm.sh`（安装系统包、创建非特权用户 `studio`、按锁定版本建 Python 环境、配置 nginx、申请 Let's Encrypt 证书）和 `studio/deploy/remote_install.sh`（部署代码、three.js 和 systemd 服务），用部署输出写好 `/opt/thermal-3d-studio/.env`，再建出中英文两套 15 个参考 STEP 实体，整个过程不调用模型。Linux 上的 OpenCascade 7.9.3 在给笔记本双风扇散热模组锐边倒钝时会崩溃，每次都在同一位置发生段错误；安装脚本随即不倒钝重建这个实体，它的棱边保持锐利，并在输出里报告 `no_edge_break=nb_thermal`。完整日志留在虚拟机的 `/var/log/thermal-install.log`。

`up.ps1` 把状态放在仓库之外的 `~/.thermal-3d-studio/<资源组>/`：`outputs.json`（访问地址和资源名称）、`portal-password.txt`（自动生成的登录密码）、虚拟机的 SSH 密钥对，以及每次运行的回执。对同一个资源组再跑一次，会把虚拟机更新到当前的 `-RepoRef`，密码和已建好的实体保持不变。某一步失败时，脚本停下并说明原因；按提示改好后，重跑同一条命令即可。

| 参数 | 默认值 | 用途 |
|---|---|---|
| `-Gpt6Capacity` | `100` | gpt-6-astra 的容量，单位为每分钟千 token |
| `-SkipImageModel` | 关 | 不部署图像模型；轨 C、轨 D 随之隐藏 |
| `-VmSize` | 上表列表里该区域开放的第一个规格 | 自己指定虚拟机规格 |
| `-PortalPassword` | 自动生成 | 自己设登录密码：`-PortalPassword (Read-Host -AsSecureString)` |
| `-AllowSshFrom` | 不开放 | 只对一个地址开放 SSH（22 端口），例如 `203.0.113.7/32` |
| `-GrantDeployerAccess` | 关 | 同时给你自己的账号模型访问权限，第 6 步要用 |
| `-RepoUrl`、`-RepoRef` | 本仓库，`master` | 安装你自己的 fork 或分支 |
| `-SkipReferenceSolids` | 关 | 不建 15 个参考实体 |

### 3. 检查部署结果

```powershell
./infra/verify.ps1 -ResourceGroup rg-thermal-studio          # 只让 GPT-6 回一个 64 token 以内的短答，没有其他模型输出
./infra/verify.ps1 -ResourceGroup rg-thermal-studio -Full    # 另外实时生成一次 STEP、生成一张概念图
```

`-Full` 的输出示例（耗时、文件大小和 token 数每次都不同）：

```text
PASS  healthz over HTTPS                 {"deployment":"gpt-6-astra","uptime_s":4}
PASS  HTTP redirects to HTTPS            {"status":308,"location":"https://thermal-<hash>.eastus2.cloudapp.azure.com/"}
PASS  wrong password is rejected         {"status":401}
PASS  sign in                            {"user":"studio","role":"visitor"}
PASS  15 scenarios                       {"scenarios":15}
PASS  pre-generated STEP solids (zh)     {"solids":15}
PASS  pre-generated STEP solids (en)     {"solids":15}
PASS  GPT-6 round trip (managed identity) {"deployment":"gpt-6-astra","actual_model":"gpt-6-astra-2026-09-03","latency_s":2.1}
PASS  Generate STEP live (GPT-6 + OCCT)  {"attempts":<n>,"latency_s":<s>,"occt_s":<s>,"solids":<n>,"faces":<n>,"mass_kg":"<kg>","step_bytes":<bytes>,"reasoning_effort":"low","prompt_tokens":<n>,"completion_tokens":<n>,"reasoning_tokens":<n>,"saved":"~/.thermal-3d-studio/rg-thermal-studio/verify-live.step"}
PASS  concept image (gpt-image)          {"png_bytes":1408063,"latency_s":13.6,"model":"gpt-image-2.5-sunburst","saved":"~/.thermal-3d-studio/rg-thermal-studio/verify-concept.png"}

10 of 10 checks passed; report: ~/.thermal-3d-studio/rg-thermal-studio/verify-20261114-152251.json
```

所有检查都走公网 HTTPS 地址：健康检查、HTTP 跳转到 HTTPS、错误密码被拒绝、登录、15 个场景、每个场景中英文两套预生成实体、通过虚拟机托管身份调用一次 GPT-6；加 `-Full` 时再实时 **生成 STEP**（并下载 STEP 文件）和生成一张 gpt-image 概念图。报告 `verify-<时间>.json` 写在状态目录里；全部通过时退出码为 0。

### 4. 使用

1. 打开 `outputs.json` 里的地址，用户名 `studio`，密码在 `portal-password.txt` 里。
2. 点一张场景卡片。徽标先显示 **预生成示例**，参考实体出现后变成 **预生成 B-rep 实体（与 STEP 一致）**；来源栏写着「当前模型：预生成示例（本次未调用 GPT-6）」：已记录的 GPT-6 回答和参考 STEP 实体直接打开，不调用模型。
3. 点 **实时调用 GPT-6**。回答返回后，来源栏换成本次实时请求的 ID。要等多久取决于页面上选的推理强度：`low`（默认，来自 `.env.example`）、`medium`、`high` 或 `xhigh`，这是 gpt-6-astra 接受的取值，它不支持 `none`。如果部署拒绝所选取值，工坊改发部署接受的下一档，来源栏显示实际使用的取值。实时生成一页要几分钟。
4. 点 **生成 STEP**。「CAD 实体」页显示尝试次数、OCCT 耗时和 B-rep 数据，可以下载 STEP、STL 和 CadQuery 脚本。

虚拟机开着就计费。`az vm deallocate -g <资源组> -n thermal-vm` 停止计算资源的计费，`az vm start` 再启动，地址不变，工坊自动启动。模型部署按 token 计费，工坊空闲时模型侧不产生费用。

### 5. 删除

```powershell
./infra/down.ps1 -ResourceGroup rg-thermal-studio
```

它先让你输入资源组名称确认（加 `-Yes` 跳过），然后删除资源组，清除处于软删除状态的 AI 资源，使它的名称和配额重新可用，检查确实没有残留，最后删掉状态目录里的密码和密钥对。输出示例（加了 `-Yes`）：

```text
deleting resource group rg-thermal-studio (several minutes)
[15:30:38] resource group deleted: rg-thermal-studio
[15:31:26] AI resource purged: thermal-ai-<hash> (eastus2)
[15:31:40] nothing left: group rg-thermal-studio gone, no soft-deleted AI resource of it
receipt: ~/.thermal-3d-studio/rg-thermal-studio/down-20261114-152717.json (PASS)
```

### 6. 可选：在本机运行工坊

用于开发，调用第 2 步部署的模型。先用 `-GrantDeployerAccess` 跑一次 `up.ps1`：它给你自己的账号在 AI 资源上分配 **Cognitive Services OpenAI User** 角色。

需要 Python 3.11 或 3.12，虚拟环境约占 1.4 GB 磁盘。CadQuery 的内核包 `cadquery-ocp` 7.9.3.1.1 提供 Windows x64、macOS（Intel 和 Apple 芯片）、Linux（x64 和 Arm64）的 wheel；Windows on Arm 上请用 x64 版 Python，它以仿真方式运行。已在 Windows 11 Arm 版上用 x64 Python 3.11.9 测试；虚拟机上用的是 Ubuntu 24.04 自带的 Python 3.12。

```powershell
cd studio
py -3.11 -m venv .venv                      # Linux/macOS：python3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1                # Linux/macOS：source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c deploy/constraints.txt
python ../tools/vendor_three.py             # three.js r160，按锁定的哈希校验
python pregen_cad.py                        # 15 个参考实体，不调用模型
python pregen_cad.py --lang en              # 同一批实体，英文部件名
$o = Get-Content ~/.thermal-3d-studio/rg-thermal-studio/outputs.json | ConvertFrom-Json
(Get-Content .env.example) -replace '^AOAI_ENDPOINT=.*', "AOAI_ENDPOINT=$($o.aiEndpoint)" `
  -replace '^AOAI_IMAGE_DEPLOYMENT=.*', "AOAI_IMAGE_DEPLOYMENT=$($o.imageDeployment)" | Set-Content .env
# 编辑 .env：PORTAL_PASSWORD 和 PORTAL_SESSION_SECRET
python -m uvicorn app:app --host 127.0.0.1 --port 3005 --env-file .env
```

预期：pip 最后输出 `Successfully installed ... cadquery-2.8.0 ... fastapi-0.141.1 ...`；three.js 输出 `three.js 0.160.0: 15/15 files verified in ...`；两次构建每个场景各输出一行 `[<id>] OK`，并以 `done. failed: none` 结束；最后输出 `Uvicorn running on http://127.0.0.1:3005`。在 Linux 上，第一次构建会遇到第 2 步说的 `nb_thermal` 崩溃；在构建英文部件名之前，先关掉锐边倒钝单独建它（`CAD_EDGE_FINISH=0 python pregen_cad.py nb_thermal`）。打开 `http://127.0.0.1:3005`，用法同第 4 步。不设 `AZURE_CLIENT_ID` 时，后端从你的 `az login` 取 Entra 令牌。`.env` 不进 Git，浏览器也拿不到它。测试和每个测试查什么，见 [docs/TESTING_CN.md](docs/TESTING_CN.md)。
