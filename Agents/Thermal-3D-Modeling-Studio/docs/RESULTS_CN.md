# 逐场景结果

[English](RESULTS.md) · [README](../README_CN.md) · [测试](TESTING_CN.md)

本页每个数字都抄自 [`data/results.json`](../data/results.json)。这个文件由 `tools/build_results.py` 生成，输入是 `studio/cache/` 里 30 份已记录的回答，以及 [`evidence/run-20261113/`](../evidence/run-20261113/) 里记录的那次运行。本页出现的数字只要在该文件里找不到，`tests/test_repo.py` 就会失败。每个数字在哪台机器上测得，见 README 的[这些数字是怎么测的](../README_CN.md#这些数字是怎么测的)。

## 15 个场景一览

下面是 15 个场景在工坊里的样子。轨 A、轨 B 是已记录运行（2026-11-14，没有调用模型）的截图：GPT-6 为场景卡片写的网页，按原样显示；参考脚本建出的 OCCT 实体，显示在工坊的视口里。轨 C 是 gpt-image-2.5 根据这个实体的截图画的图片，2026-11-10 通过工坊页面为每个场景调用一次。它是示意图：图像模型会重画零件，细节可能和 STEP 不一样（集成模块的偏差有多大，见[轨 C](#轨-c工程渲染图与-step-的对照)）。「2D 图纸 / 照片 → 3D」卡片会把示例图纸 `studio/static/samples/exv_body_drawing.png` 和提示词一起发出。

| 场景 | 轨 A：GPT-6 写的网页 | 轨 B：OCCT 实体 | 轨 C：gpt-image-2.5 重画的图片（示意） |
|---|---|---|---|
| 电池水冷板 | <img src="../images/gallery-coldplate-gpt6-zh.jpg" width="260" alt="电池水冷板：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-coldplate-brep-zh.jpg" width="260" alt="电池水冷板：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-coldplate.jpg" width="260" alt="电池水冷板：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 微通道换热器 | <img src="../images/gallery-mchx-gpt6-zh.jpg" width="260" alt="微通道换热器：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-mchx-brep-zh.jpg" width="260" alt="微通道换热器：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-mchx.jpg" width="260" alt="微通道换热器：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 电子膨胀阀阀体 | <img src="../images/gallery-exv-gpt6-zh.jpg" width="260" alt="电子膨胀阀阀体：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-exv-brep-zh.jpg" width="260" alt="电子膨胀阀阀体：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-exv.jpg" width="260" alt="电子膨胀阀阀体：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 2D 图纸 / 照片 → 3D | <img src="../images/gallery-drawing2d-gpt6-zh.jpg" width="260" alt="2D 图纸 / 照片 → 3D：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-drawing2d-brep-zh.jpg" width="260" alt="2D 图纸 / 照片 → 3D：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-drawing2d.jpg" width="260" alt="2D 图纸 / 照片 → 3D：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| AIDC GPU 液冷冷板 | <img src="../images/gallery-aidc-gpt6-zh.jpg" width="260" alt="AIDC GPU 液冷冷板：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-aidc-brep-zh.jpg" width="260" alt="AIDC GPU 液冷冷板：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-aidc.jpg" width="260" alt="AIDC GPU 液冷冷板：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 四通换向阀 · 减铜优化 | <img src="../images/gallery-fourway-gpt6-zh.jpg" width="260" alt="四通换向阀 · 减铜优化：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-fourway-brep-zh.jpg" width="260" alt="四通换向阀 · 减铜优化：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-fourway.jpg" width="260" alt="四通换向阀 · 减铜优化：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 热管理集成模块 | <img src="../images/gallery-module-gpt6-zh.jpg" width="260" alt="热管理集成模块：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-module-brep-zh.jpg" width="260" alt="热管理集成模块：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/module-gpt-image-render.jpg" width="260" alt="热管理集成模块：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| AI 辅助仿真估算 | <img src="../images/gallery-thermal_sim-gpt6-zh.jpg" width="260" alt="AI 辅助仿真估算：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-thermal_sim-brep-zh.jpg" width="260" alt="AI 辅助仿真估算：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-thermal_sim.jpg" width="260" alt="AI 辅助仿真估算：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| APS 智能排程推理 | <img src="../images/gallery-aps-gpt6-zh.jpg" width="260" alt="APS 智能排程推理：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-aps-brep-zh.jpg" width="260" alt="APS 智能排程推理：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-aps.jpg" width="260" alt="APS 智能排程推理：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 整车热管理系统回路 | <img src="../images/gallery-vehicle_tms-gpt6-zh.jpg" width="260" alt="整车热管理系统回路：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-vehicle_tms-brep-zh.jpg" width="260" alt="整车热管理系统回路：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-vehicle_tms.jpg" width="260" alt="整车热管理系统回路：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| AIDC CDU 液冷分配单元 | <img src="../images/gallery-cdu-gpt6-zh.jpg" width="260" alt="AIDC CDU 液冷分配单元：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-cdu-brep-zh.jpg" width="260" alt="AIDC CDU 液冷分配单元：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-cdu.jpg" width="260" alt="AIDC CDU 液冷分配单元：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 笔记本双风扇散热模组 | <img src="../images/gallery-nb_thermal-gpt6-zh.jpg" width="260" alt="笔记本双风扇散热模组：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-nb_thermal-brep-zh.jpg" width="260" alt="笔记本双风扇散热模组：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-nb_thermal.jpg" width="260" alt="笔记本双风扇散热模组：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 镁合金 A 壳与压铸模具概念 | <img src="../images/gallery-nb_chassis_mold-gpt6-zh.jpg" width="260" alt="镁合金 A 壳与压铸模具概念：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-nb_chassis_mold-brep-zh.jpg" width="260" alt="镁合金 A 壳与压铸模具概念：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-nb_chassis_mold.jpg" width="260" alt="镁合金 A 壳与压铸模具概念：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 笔记本总装产线数字孪生 | <img src="../images/gallery-nb_assembly_line-gpt6-zh.jpg" width="260" alt="笔记本总装产线数字孪生：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）；网页运行时抛出脚本错误，画面上是它自己的「场景错误」提示"> | <img src="../images/gallery-nb_assembly_line-brep-zh.jpg" width="260" alt="笔记本总装产线数字孪生：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-nb_assembly_line.jpg" width="260" alt="笔记本总装产线数字孪生：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |
| 包装与集装箱装载优化 | <img src="../images/gallery-nb_packing-gpt6-zh.jpg" width="260" alt="包装与集装箱装载优化：GPT-6 为这张场景卡片写的 three.js 网页，按原样显示（已记录的回答）"> | <img src="../images/gallery-nb_packing-brep-zh.jpg" width="260" alt="包装与集装箱装载优化：参考脚本建出的 OCCT B-rep 实体，显示在工坊的 3D 视口里"> | <img src="../images/render-nb_packing.jpg" width="260" alt="包装与集装箱装载优化：gpt-image-2.5 根据实体截图重画的图片，是示意图，不是几何"> |

**有一个已记录的网页运行出错。** GPT-6 为「笔记本总装产线数字孪生」写的中文网页，在这次运行的每一次尝试里都会报 `TypeError: Cannot read properties of undefined (reading 'x')`：它的动画循环调用 three.js 的 `CatmullRomCurve3.getPointAt` 取曲线上的点，而这条曲线有一个控制点是 undefined。产线已经画出来，但被网页自己的「场景错误」提示挡住（见上表这一行的轨 A 截图），工坊也报告场景没有渲染成功。同一张卡片的英文网页可以正常运行。这些截图展示的就是 GPT-6 写出来的东西，包括它的错误。

## 轨 A：GPT-6 写 three.js 网页

**输入。** 15 张场景卡片各自的提示词（`studio/scenarios.py` 里中文界面用 `prompt`，英文界面用 `prompt_en`），作为唯一一条用户消息，配上该场景的系统提示词。每个场景、每种语言各请求一次。下面是「热管理集成模块」中文提示词原文：

> 建一个新能源车热管理集成模块的概念装配体：中央为工程塑料歧管本体 260×160×60 mm，内部两条 φ16 mm 主水路；歧管上安装一个五通电子水阀（φ60×70 mm，铝壳）、一个电子水泵（φ70×90 mm，铝壳带出水口）、一个板式换热器 Chiller（120×80×60 mm，不锈钢，20 层板片可简化表达）、两个 φ16 mm 快插接头。请给出 3D 模型，支持「爆炸视图」按钮把各部件沿各自方向分离，并统计部件数量、各部件质量和模块总质量。

**测了什么。** `pregen.py` 通过线上 `/api/generate` 用的同一个 `run_generation` 函数发出每个请求，把回答存进 `studio/cache/`。*总耗时* 从发出请求算到回答解析完毕；*首个可见 token* 是回答的第一个 token 到达的时刻。*输出 token* 是 API 返回的 `completion_tokens`（有推理 token 时也算在内）；*输出速度* 是可见输出 token 数除以首个可见 token 之后的时间。网页长度是 three.js HTML 的行数。

| 场景 | 总耗时（s）：中文 / 英文 | 首个可见 token（s）：中文 / 英文 | 输出 token：中文 / 英文 | 首 token 之后的输出速度（token/s）：中文 / 英文 | 网页长度（行）：中文 / 英文 |
|---|---|---|---|---|---|
| 电池水冷板 | 356.2 / 170.4 | 182.8 / 25.8 | 8,463 / 3,757 | 34.0 / 26.0 | 416 / 207 |
| 微通道换热器 | 148.1 / 110.0 | 53.7 / 7.4 | 4,195 / 3,805 | 37.6 / 37.1 | 216 / 203 |
| 电子膨胀阀阀体 | 144.8 / 120.0 | 16.4 / 5.8 | 3,849 / 4,103 | 30.0 / 35.9 | 188 / 205 |
| 2D 图纸 / 照片 → 3D | 101.0 / 123.9 | 10.8 / 16.7 | 3,347 / 3,680 | 37.1 / 34.3 | 190 / 203 |
| AIDC GPU 液冷冷板 | 152.6 / 164.0 | 13.8 / 11.2 | 4,070 / 4,032 | 29.3 / 26.4 | 204 / 203 |
| 四通换向阀 · 减铜优化 | 155.1 / 184.4 | 13.7 / 11.2 | 4,281 / 4,620 | 30.3 / 26.7 | 197 / 195 |
| 热管理集成模块 | 142.6 / 127.1 | 9.1 / 19.9 | 4,244 / 3,927 | 31.8 / 36.6 | 213 / 191 |
| AI 辅助仿真估算 | 290.6 / 193.1 | 75.0 / 7.1 | 5,238 / 4,774 | 24.3 / 25.7 | 253 / 251 |
| APS 智能排程推理 | 180.2 / 151.4 | 14.3 / 6.7 | 4,888 / 4,942 | 29.5 / 34.2 | 233 / 246 |
| 整车热管理系统回路 | 314.3 / 277.4 | 26.7 / 14.3 | 7,914 / 6,320 | 27.5 / 24.0 | 287 / 281 |
| AIDC CDU 液冷分配单元 | 320.1 / 249.4 | 53.8 / 30.1 | 6,874 / 6,783 | 25.8 / 30.9 | 300 / 293 |
| 笔记本双风扇散热模组 | 162.5 / 143.0 | 48.9 / 29.7 | 7,845 / 7,313 | 69.1 / 64.5 | 330 / 291 |
| 镁合金 A 壳与压铸模具概念 | 85.0 / 84.0 | 8.6 / 4.8 | 5,473 / 5,533 | 71.6 / 69.9 | 219 / 213 |
| 笔记本总装产线数字孪生 | 113.4 / 116.0 | 5.6 / 6.7 | 7,457 / 6,929 | 69.2 / 63.4 | 344 / 323 |
| 包装与集装箱装载优化 | 87.5 / 76.1 | 8.4 / 7.3 | 5,624 / 4,913 | 71.1 / 71.4 | 213 / 211 |

- **推理强度。** 只有 2026-09-10 09:11 UTC 之后保存的 12 次运行记录了实际发送的推理强度，12 次都是 `none`，当时部署接受这个取值（2026-11-14 部署不再接受 `none`，所以工坊现在默认 `low`）；更早的 18 次没有记录。这 18 次里有两次用了推理 token：中文电池水冷板（2,559 个）和中文微通道换热器（650 个）。推理 token 产生在首个可见 token 之前，而中文电池水冷板等首个可见 token 的时间也最长，182.8 s。
- **两种速度。** 2026-09-12 记录的 8 次笔记本场景运行，输出速度在 63.4–71.6 token/s；其余各次都在 24.0–37.6 token/s。全部 30 次调用的都是部署 `gpt-6-astra`；记录了模型版本的运行返回的都是 `gpt-6-astra-2026-09-03`，最早的七次（2026-09-09 保存）没有记录。速度差异的原因没有查明（服务负载是一种可能，未验证）。
- **都是单次运行。** 每个格子只有一次回答。同一提示词再请求一次，网页、工程量和耗时都会不同。

## 轨 B：OpenCascade 建出参考实体

**输入。** `studio/cad_examples/<场景>.py`：15 个手写的 CadQuery 脚本，遵守和 GPT-6 相同的契约（`PARTS`、`MATERIALS`、真实圆角、孔、槽），也通过同一套白名单检查。它们不是 GPT-6 写的。

**测了什么。** 2026-11-13 在测试笔记本上执行 `python pregen_cad.py`，每个脚本都经过 `cad_runner.run_script`，也就是在线 **生成 STEP** 用的同一个函数。*OCCT 耗时* 从启动单独的 Python 进程算起，到它写完 STEP、STL 和 GLB 后退出为止：包括启动 Python、导入 CadQuery、建实体、锐边倒钝和导出。倒钝有时间预算 `CAD_EDGE_FINISH_BUDGET_S`：`pregen_cad.py` 里每个场景 `200` s；在线请求用默认值 `40` s。*倒钝的棱* 是在找到的候选锐棱里实际倒上圆角的条数；由 `12` 个以上实体组成的部件（翅片组、扁管阵列、托盘）跳过不倒。

<img src="../images/track-b-cad-tab-zh.jpg" width="800" alt="中文界面里集成模块的「CAD 实体」页：STEP、STL 和 CadQuery 脚本的下载按钮，实体的 STL 预览，以及 OCCT 算出的 STEP 实体体积、质量、包络和表面积。">

这是集成模块的「CAD 实体」页，显示的是预生成实体；实时 **生成 STEP** 的结果也显示在这里。页面提供 STEP、STL 和 CadQuery 脚本下载、STL 预览，以及 OCCT 按 B-rep 算出的体积、质量、包络和表面积。下表列出每个场景的这些数据。

| 场景 | 部件 | 实体 | 面 | 质量（kg） | 外形包络（mm） | 倒钝的棱 / 候选棱 | OCCT 耗时（s） | 其中倒钝（s） | STEP 大小（MB） |
|---|---|---|---|---|---|---|---|---|---|
| 电池水冷板 | 4 | 1 | 284 | 1.582 | 360 × 180 × 13.5 | 77 / 238 | 68.7 | 52.0 | 1.2 |
| 微通道换热器 | 8 | 306 | 3,504 | 0.384 | 371 × 49.5 × 216.8 | 484 / 484 | 86.3 | 61.6 | 16.2 |
| 电子膨胀阀阀体 | 6 | 2 | 181 | 0.488 | 68 × 36 × 124 | 87 / 112 | 49.0 | 38.6 | 1.4 |
| 2D 图纸 / 照片 → 3D | 4 | 4 | 59 | 0.384 | 72 × 32 × 136 | 29 / 35 | 14.1 | 6.1 | 0.3 |
| AIDC GPU 液冷冷板 | 5 | 1 | 570 | 0.511 | 140 × 90 × 10 | 98 / 252 | 138.0 | 54.9 | 1.9 |
| 四通换向阀 · 减铜优化 | 12 | 2 | 304 | 0.656 | 116 × 50 × 92 | 134 / 154 | 46.7 | 31.3 | 2.3 |
| 热管理集成模块 | 7 | 25 | 796 | 4.023 | 322 × 168 × 152 | 277 / 542 | 110.5 | 86.4 | 4.1 |
| AI 辅助仿真估算 | 12 | 12 | 432 | 1.750 | 362 × 180 × 20 | 228 / 248 | 34.6 | 5.8 | 1.4 |
| APS 智能排程推理 | 15 | 121 | 2,308 | 12.503 | 1105 × 530 × 32 | 964 / 964 | 59.1 | 10.3 | 6.9 |
| 整车热管理系统回路 | 29 | 202 | 1,901 | 879.344 | 3316 × 1480 × 870 | 0 / 0 | 19.7 | 0.0 | 6.9 |
| AIDC CDU 液冷分配单元 | 32 | 289 | 1,928 | 2,943.824 | 8410 × 1205 × 2100 | 0 / 0 | 31.5 | 0.0 | 6.1 |
| 笔记本双风扇散热模组 | 14 | 278 | 3,302 | 0.096 | 280 × 190 × 9 | 283 / 588 | 199.2 | 131.6 | 11.2 |
| 镁合金 A 壳与压铸模具概念 | 4 | 2 | 500 | 14.680 | 392 × 297 × 73.3 | 194 / 304 | 76.9 | 59.2 | 1.9 |
| 笔记本总装产线数字孪生 | 31 | 151 | 1,571 | 9,855.507 | 28850 × 18450 × 2700 | 0 / 0 | 12.0 | 0.0 | 5.2 |
| 包装与集装箱装载优化 | 11 | 1038 | 7,022 | 13,348.454 | 14696 × 2498 × 2896 | 240 / 240 | 70.9 | 8.1 | 19.6 |

- **有五个场景是布局，不是零件。** APS 排产沙盘、整车热管理系统、带 8 个机柜的 CDU 机柜排、笔记本总装线、包装与装箱，建的是一个系统或一份方案。它们的质量是每个实体的体积乘以脚本给它的密度，描述的是这个布局模型，不是一件能拿去称重的产品。
- **整车系统、CDU 机柜排和总装线的 `0 / 0` 是有意为之。** 这三个脚本设置了 `EDGE_FINISH = 0`，因为米级尺度上看不出亚毫米的倒钝。倒上的棱少于找到的棱，是 OCCT 拒绝了其余的棱，或者时间预算用完了；每倒一批圆角都会检查结果（只有一个有效实体、体积变化不超过 `5` %），所以每个部件仍是有效实体。
- **时间花在哪里。** 每个场景都要新起一个 Python 进程、导入 CadQuery，然后才开始建模。最慢的笔记本双风扇散热模组共用 199.2 s，其中 131.6 s 花在倒钝上。

## 轨 C：工程渲染图与 STEP 的对照

轨 C 出两类图。**生成渲染图** 把 3D 视图的截图交给 gpt-image-2.5，由它重画成一张展示用的图片，也就是[上面表格](#15-个场景一览)最后一列的那些图。打开 **与 CAD 叠放**，「渲染图」页会把截图所对应的 STEP 视图的外轮廓和棱线叠在图上。图像模型会重新构图，所以轮廓只用统一缩放和平移去对齐，不拉伸、不旋转；青色线没有落在零件上的地方，就是这张图偏离 STEP 的地方。图旁的说明给出这次对齐的外形重合度 IoU，并说明它只供参考。

<img src="../images/render-tab-zh.jpg" width="800" alt="中文界面里集成模块的「渲染图」页：预生成的 gpt-image-2.5 图片打开了「与 CAD 叠放」，STEP 视图的青色外轮廓和棱线叠在重画的零件上。旁边是 gpt-image 效果图与工程渲染图的切换按钮，以及说明对齐方式、给出外形重合度的文字。">

工程渲染图是另一类：three.js 直接画 STEP 自己的网格，用的就是画轮廓的那台相机，不需要任何对齐。本节下面测的就是它。

**输入。** 上面每个实体的 `model.glb`，也就是 STEP 自己的三角网格。

**测了什么。** `python pregen_engineering.py <15 个场景> --out <dir> --no-install` 在无头 Edge 里以 2048×1152、累积 256 帧渲染每个网格，用同一个相机画出 STEP 的外轮廓和棱线，再把从成图里分割出的零件区域与 STEP 外形对比。*IoU* 是重叠面积除以两者合起来的面积；*轮廓偏差* 是 STEP 轮廓上每个像素到分割轮廓的像素距离。没有做任何缩放或平移去凑重合。

| 场景 | 与 STEP 的外形重合度 IoU（%） | 轮廓偏差中位数（px） | 轮廓偏差 90 分位（px） | 渲染耗时（s） |
|---|---|---|---|---|
| 电池水冷板 | 17.2 | 10.6 | 369.6 | 2.5 |
| 微通道换热器 | 95.1 | 3.0 | 17.0 | 14.0 |
| 电子膨胀阀阀体 | 94.1 | 3.2 | 4.0 | 2.4 |
| 2D 图纸 / 照片 → 3D | 93.8 | 3.2 | 4.0 | 2.1 |
| AIDC GPU 液冷冷板 | 91.1 | 11.4 | 45.8 | 3.9 |
| 四通换向阀 · 减铜优化 | 94.7 | 3.2 | 15.6 | 2.5 |
| 热管理集成模块 | 97.5 | 3.2 | 4.1 | 3.6 |
| AI 辅助仿真估算 | 15.1 | 13.0 | 314.5 | 4.5 |
| APS 智能排程推理 | 94.4 | 3.6 | 4.1 | 10.8 |
| 整车热管理系统回路 | 90.2 | 3.6 | 22.8 | 8.9 |
| AIDC CDU 液冷分配单元 | 90.4 | 3.6 | 17.0 | 10.3 |
| 笔记本双风扇散热模组 | 97.7 | 3.2 | 3.6 | 13.6 |
| 镁合金 A 壳与压铸模具概念 | 97.5 | 3.6 | 6.3 | 2.7 |
| 笔记本总装产线数字孪生 | 68.0 | 8.5 | 38.6 | 8.6 |
| 包装与集装箱装载优化 | 96.3 | 3.2 | 5.0 | 30.0 |

- **IoU 查的是什么。** 成图和青色的 STEP 线来自同一个网格、同一个相机，二者不会错开。IoU 检查的是：成图里的零件是否出现在 STEP 外形所在的位置。它准不准，取决于在成图里找零件的分割算法：`studio/pregen_render_cad.py` 里的 `part_area()`，它靠零件相对纯色背景的边缘和明暗来找。
- **十二张图在 90.2–97.7 %。** 分割找到了整个 STEP 外形，外加周围一小圈。
- **三张偏低，原因在分割，不在渲染。** 电池水冷板（17.2 %）和仿真估算里的冷板（15.1 %）是大面积、光滑、浅色的平板：分割找到了边缘和小特征，却漏掉了大部分平整的顶面。总装线（68.0 %）由细框架组成，分割把框架周围和框架之间的区域也算了进去。电池水冷板的 IoU 最低，但它的 STEP 轮廓仍然落在板上：

<img src="../images/coldplate-engineering-render-step-lines.jpg" width="800" alt="电池水冷板的工程渲染图，浅色背景上一块大而平的浅灰色板，带两个接口和安装耳。青色的 STEP 轮廓和棱线落在板的外缘、槽和安装耳上。">

- **怎么自己复核。** `python tools/segmentation_check.py <dir>` 读取 `pregen_engineering.py --out <dir>` 写出的图片，逐个场景给出：分割找到了多少 STEP 外形，以及找到的区域有多少落在外形之内。本次运行的输出是 [`segmentation-check.json`](../evidence/run-20261113/engineering/segmentation-check.json)。
- **渲染耗时** 在笔记本的集成显卡上每张 2.1–30.0 s；包装场景有 1,038 个实体，用时最长。

## 局限

- 轨 B、轨 C 只在一台机器上测：Windows on Arm 笔记本，x64 Python 在仿真下运行。原生 x64 机器或 Linux 虚拟机上的耗时，本仓库没有测。轨 A 只有一个资源、一个部署。
- 轨 A 展示的是模型对每个场景的一次回答，不代表它的平均质量或平均速度。
- 实时的轨 B（GPT-6 写 CadQuery 脚本、OCCT 执行）在本仓库的证据里没有计时。自己点一次 **生成 STEP**，「CAD 实体」页会显示你那次的尝试次数和耗时。
- 每个场景的 gpt-image 效果图都是 2026-11-10 通过工坊页面生成一次，按保存时的样子展示。
