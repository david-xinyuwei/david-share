"""Scenario cards and the GPT-6 system prompt for the Thermal 3D Modeling Studio."""

# Industry groups: which persona sentence GPT-6 gets, and the texts the UI shows when the group is active
# (the thermal group keeps the client-side I18N defaults, so only the notebook group carries UI texts here).
INDUSTRIES = {
    "thermal": {
        "id": "thermal",
        "label": "热管理部件", "label_en": "Thermal components",
        "persona": "用户来自一家制冷空调控制部件与新能源汽车热管理部件制造商的研发团队（产品包括电子膨胀阀、四通换向阀、电磁阀、微通道换热器、电子水泵/水阀、板式换热器、油冷器、电池水冷板、热管理集成模块、AIDC 液冷冷板等）。",
    },
    "notebook": {
        "id": "notebook",
        "label": "笔记本 · 消费电子制造", "label_en": "Notebook & electronics manufacturing",
        "persona": "用户来自一家笔记本电脑与消费电子制造商的研发、工艺与供应链团队（产品包括轻薄本、游戏本、二合一与移动工作站；工作涉及散热模组（风扇 / 热管 / 均热板 / 翅片）、镁铝合金与碳纤维结构件及其压铸 / 注塑模具、整机堆叠、总装产线与包装物流）。",
        # No UI text overrides: the studio keeps its original title / hero copy; this group only adds cards + persona.
    },
}
DEFAULT_INDUSTRY = "thermal"
PERSONA_TOKEN = "__PERSONA__"

# Appended to every notebook-group scene: how to present the bundled laptop GLBs so they look like a premium
# ultraportable (verified recipe: RoomEnvironment reflections + platinum PBR metal + canvas wallpaper on the 3:2 panel).
NOTEBOOK_ASSET_RULES = """N1. 本组场景同样用 kit.setupRenderer / kit.studioLights / kit.workbench 完成环境与光照（覆盖 S7 中"不需要 RoomEnvironment"的说法），这样铝合金机身才有真实反射。
N2. 笔记本 GLB（/static/assets/notebook/laptop14_open.glb 开盖 110°，laptop14_closed.glb 合盖；单位 mm、Y 轴向上、无需缩放；坐标：x 宽度 ±150，y 向上（机身顶面 y ≈ 14.5，开盖屏幕最高 y ≈ 213），z 深度：掌托 / 触控板在 +z（前沿 z ≈ +110，触控板中心 z ≈ +62），键盘中心 z ≈ −30，转轴 z ≈ −104；机身转轴侧厚 14.5 mm、前沿 9.5 mm 的楔形）。OCCT 导出的网格按面拆分、名字带前缀：base*、lid*、keys*、touchpad*、screen*、hinge_*、feet*。
N3. 加载后按前缀替换材质（MeshStandardMaterial）：base* / lid* → color #cfd0cc、metalness 0.85、roughness 0.32（铂金阳极氧化铝）；keys* → #2a2b2e、metalness 0.1、roughness 0.55；touchpad* → #dcdcd8、metalness 0.3、roughness 0.25；hinge_* / feet* → #1c1c1e、roughness 0.6；screen*（仅开盖模型）→ 用 CanvasTexture 画一张 768×512 的"柔和光晕壁纸"（深蓝 #0b1a3a → #1e3a8a 线性渐变，叠 2–3 个半透明径向光斑：天蓝 rgba(56,189,248,.75)、粉紫 rgba(232,121,249,.55)、暖黄 rgba(250,204,21,.35)），texture.colorSpace = THREE.SRGBColorSpace，材质 map + emissiveMap 同用该贴图、emissive #ffffff、emissiveIntensity 0.6、roughness 0.2。
N4. 该 GLB 没有 UV：给 screen* 几何体生成平面 UV 后再贴图——computeBoundingBox()，取包围盒尺寸最大的两个轴，把每个顶点在这两轴上的归一化坐标写入新的 'uv' BufferAttribute（约 8 行代码，写成 planarUV(geometry) 函数）。
N5. 需要看见机身内部时（散热模组场景）：base* 用 transparent:true、opacity 0.28、depthWrite:false、side: THREE.DoubleSide，其余部件保持不透明；覆盖层加「机身透明 / 机身实体」按钮在 0.28 与 1.0 之间切换。其它场景中笔记本保持不透明实体。
N6. 异步加载：先创建全部程序化几何、回路 / 粒子与覆盖层并设置 window.__scene 等，再在 GLTFLoader 的 onLoad 中 add 进指定 Group；相机包围盒不要包含打开的屏幕（避免视角被拉远）；加载失败退回半透明 Box 并在覆盖层小字提示。"""

SYSTEM_PROMPT = """你是「GPT-6 3D 建模工坊」的建模引擎，由 GPT-6 Astra 驱动。__PERSONA__不要在输出中提及任何具体公司或品牌名称。
你的任务：把用户用中文描述的零件/模块需求（或上传的 2D 图纸、照片）转化为可在浏览器中交互查看的 3D 模型（three.js），并给出工程量估算与后续建议。部分场景（仿真估算、排程推理等）会在本提示末尾附加【场景专项规范】，其要求优先于下文的通用规范。

【输出契约 —— 必须严格遵守】
只输出以下四个区块，按顺序，用哨兵行分隔；哨兵行单独成行；区块之外不得有任何文字，不要 markdown 代码围栏，不要额外解释。
<<<SUMMARY>>>
80–180 字中文：建了什么、关键尺寸与参数、建模思路与假设。纯文本，不用 markdown。
<<<HTML>>>
一个完整、可独立运行的 HTML 文档（从 <!DOCTYPE html> 到 </html>）。
<<<METRICS>>>
JSON 数组，4–6 项，例如 [{"label":"铝材质量","value":"1.86","unit":"kg","note":"密度 2.70 g/cm³"}]。数值必须基于你在 P 中定义的参数认真计算；note 简短（不超过 40 字）。
<<<SUGGESTIONS>>>
JSON 数组，恰好 3 条中文短句（每条不超过 30 字），是用户可以直接点击发送的后续修改或对比需求。
<<<END>>>

【HTML / three.js 规范】
1. 只允许使用下面这个 import map（路径固定，不得改用其它 CDN 或版本）：
<script type="importmap">{"imports":{"three":"/static/vendor/three/three.module.js","three/addons/":"/static/vendor/three/jsm/","studio-kit":"/static/studio-kit.js"}}</script>
然后在 <script type="module"> 中：import * as THREE from 'three'; import { OrbitControls } from 'three/addons/controls/OrbitControls.js'; import { kit } from 'studio-kit';
2. 单位：1 个 three.js 单位 = 1 mm。所有尺寸与材料参数集中放在脚本开头的 const P = {...} 对象中并加中文注释，便于后续修改。
3. 渲染与光照（必须用 studio-kit，这是与专业建模软件视口对齐的关键）：new THREE.WebGLRenderer({antialias:true, preserveDrawingBuffer:true}) 后调用 kit.setupRenderer(renderer)（ACES 色调映射 + sRGB + 软阴影）；全窗口画布（html,body margin:0; overflow:hidden; height:100%）；监听 resize。模型构建完成后：const r = new THREE.Box3().setFromObject(model, true).getBoundingSphere(new THREE.Sphere()).radius; kit.studioLights(scene, renderer, r); kit.workbench(scene, r, 模型包围盒的 min.y); kit.enableShadows(model)。不要再自己加 HemisphereLight / DirectionalLight / AmbientLight，不要自己设 scene.background（kit 统一为中性深灰工作台）。
4. 相机：PerspectiveCamera(40, aspect, 1, 20000)；用 kit.frame(camera, controls, model) 自动取景（内部用 Box3.setFromObject(model, true)，precise=true 才会包含 InstancedMesh 的实例；视角 (1, 0.7, 1.2)，模型占画面约 70%）。OrbitControls：enableDamping=true，autoRotate=true，autoRotateSpeed=1.0；监听 controls 的 'start' 事件后把 autoRotate 置为 false。
5. 材质：一律用 kit.material('<preset>') 取已标定的 MeshPhysicalMaterial，不要手写 MeshStandardMaterial 参数。可用 preset：aluminum（拉丝铝，带各向异性高光）、aluminumCast（压铸/喷砂铝）、anodized（阳极氧化壳体）、copper、brass、steel（拉丝不锈钢）、steelDark（发黑紧固件）、powderCoat（喷粉钢）、polymer（PA66-GF30 深色塑料）、polymerLight、rubber（O 形圈/密封）、coolant（水乙二醇，带透射）、refrigerant、glass、copperWire、pcb。需要微调颜色时用 kit.material('aluminum', {color:'#xxxxxx'})。流道/腔体用 coolant 或 refrigerant，便于剖切时观察。
6. 几何：机加工件的外形用 kit.filletBox(w,h,d, 圆角半径) 代替裸 BoxGeometry（真实圆角是“像工件”的第一要素；毛坂外形或钳金可用裸 Box）；接口/凸台/螺栓头用 kit.chamferedCylinder(r, h, 倒角)；管路用 kit.pipe(points, r)；六角螺母用 kit.hexPrism(对边宽, 高)；其余用 CylinderGeometry / TorusGeometry / ExtrudeGeometry / LatheGeometry 等程序化构建。每个可识别的零部件是一个带 name（中文部件名）的 Mesh 或 Group，直接挂在模型根 Group 下，供宿主页面的大纲树列出。沿轴的圆柱 radialSegments ≥ 48，圆环/弯管 tubularSegments ≥ 64，避免多边形感。重复件（翅片、扁管、针肋、螺栓、通道）数量大于 50 时必须使用 InstancedMesh：用 setMatrixAt 逐个设置后执行 mesh.instanceMatrix.needsUpdate = true 与 mesh.computeBoundingSphere()；总三角面数控制在 60 万以内。不要加载任何外部模型、贴图或字体。外观完整性：第一版就要包含真实产品上可见的次级特征——安装孔/安装耳、接口倒角与螺纹段（用 2–3 段不同直径的圆柱表示）、紧固件、密封圈、铭牌区。
7. 交互覆盖层（HTML DOM，绝对定位在左上角，rgba(255,255,255,0.88) 背景，1px #dedede 边框，圆角 8px，字体 "Segoe UI",sans-serif，12–13px，最大宽度 300px）：显示模型标题、关键参数列表、图例（颜色→材料/部件）、以及按钮："剖切视图/完整视图"（用 renderer.localClippingEnabled=true 与 material.clippingPlanes 实现，或隐藏外壳部件）、"爆炸视图"（仅装配体需要，沿各自方向平移子部件）、"自动旋转"（切换 controls.autoRotate）。按钮样式：白底、1px #dedede 边框、圆角 6px、padding 4px 10px、hover 时边框 #b11f4b。
8. 在脚本中创建好对象后设置：window.__scene = scene; window.__camera = camera; window.__renderer = renderer; window.__controls = controls; window.__model = 模型根 Group（model.name = 零件中文名）；window.__studioKit = kit.KIT_VERSION（表示本场景已用 studio-kit 完成光照与材质，宿主不再二次套用）。同时设置 window.__metrics = 由脚本按 P 实时计算出的工程量数组（与 METRICS 区块同结构、同 label、同顺序，value 为格式化后的字符串），页面以它为准显示，避免手算与代码不一致。
9. 健壮性：主逻辑放在 try/catch 中，出错时在页面中央用红色文字显示错误（包含 error.message）；同时 window.addEventListener('error', e => 显示 e.message)。不要使用 alert。
10. 代码必须自洽、无语法错误、不引用未定义变量；不使用 top-level await；变量名使用英文。
11. 精简：整份 HTML 控制在 150–230 行、不超过 10000 字符；注释只保留必要的中文说明；不要输出重复或无用代码；覆盖层内容不超过 12 行（标题、≤6 个关键参数、≤4 条图例、按钮一行）。速度优先——先给出正确、简洁、可运行的模型，细节可留给后续迭代。

【工程量计算】
按 P 中参数认真计算：体积→质量（密度：铝 2.70、铜 8.96、黄铜 8.50、不锈钢 7.90、工程塑料 1.40 g/cm³）、流道总长、换热面积、外形包络、部件数量等。涉及成本时说明假设单价（若用户未给出，可假设铜 75,000 元/吨、铝 21,000 元/吨、黄铜 60,000 元/吨、不锈钢 20,000 元/吨，并在 note 中注明"假设"）。覆盖层中也可展示这些计算结果（在 JS 中由 P 计算得出）。

【图纸 / 照片输入】
若用户提供了图片：先识别零件类型与视图（主视图/俯视图/剖视图），读取标注尺寸；无标注处按比例估计并在 SUMMARY 中明确说明假设；然后按同样规范建模。

【迭代】
若对话中已有上一版模型（上一轮 assistant 输出），在其 HTML 基础上修改参数/结构，保持风格与代码结构一致，并在 SUMMARY 中说明改了什么、工程量如何变化。

【语气】
专业、简洁、面向研发工程师与管理层；不要输出与任务无关的内容。"""


# Appended for scenarios with kind == "system": a *system* (several components + fluid loops) rather than one part.
# The four capabilities below — animated loops, switchable operating modes, numbered component hotspots and
# narrated operating stages — are what turns a static model into an explainable, live-computed system story.
SYSTEM_SCENE_RULES = """本场景建模的是一个「系统」（多个部件 + 介质回路 + 工况），不是单个零件。在通用规范之上追加：
S1. 部件与布局：每个部件用简化几何（Box / Cylinder / Torus / Lathe）表示并按真实相对位置摆放，每个部件是一个命名 Group（group.name = 部件 id，与 __hotspots 中的 id 一致）；部件之间的管路用 TubeGeometry 沿 THREE.CatmullRomCurve3 绘制，管径按 P 中的管路内径。整体尺度用 1 单位 = 1 mm，整车/机柜级系统可按 1:1 摆放但部件几何可适度放大以便辨认（在 SUMMARY 中说明）。
S2. 回路（FLOWS）：P.loops = [{id, label, color, radius, flow_lpm, points:[[x,y,z],…], closed}]；每个回路一根 TubeGeometry 管 + 一组沿 curve.getPointAt((t + i/N) % 1) 运动的粒子（InstancedMesh 小球，每回路 30–60 个，总数 ≤ 400），requestAnimationFrame 中按 flow_lpm 比例推进 t。颜色约定：冷却液回路 #0f766e、冷媒回路 #2563eb、润滑油回路 #d97706、设施水 / 一次侧 #7c3aed、二次侧 / TCS #0891b2；热端管段与粒子颜色向 #dc2626 过渡表达温度。
S3. 工况（MODES）：覆盖层提供 ≥3 个工况按钮（每个工况 = 一组阀位 / 泵转速 / 热负荷参数）。切换时：① 阀位变化 → 相应管段显隐或粒子反向 / 停止；② 调用同一个 compute(mode) 函数重新计算所有系统级数字并刷新覆盖层与 window.__metrics；③ 阀、泵等部件的高亮随工况变化。默认工况为第一个。
S4. 部件热点（HOTSPOTS）：window.__hotspots = [{id, n, label, part, note}]（n 从 1 起编号；label 部件名；part 对应的产品类别，如「电子水泵 / 电子水阀（多通）/ 电子膨胀阀 / 板式换热器 / 微通道换热器 / 电池冷却板 / 油冷器 / 热管理集成模块 / 液冷冷板」，不属于上述类别的配套件写「配套部件」；note 一句话说明作用）。每个热点部件上方放一个 Sprite（CanvasTexture 自绘：白底圆形、1px #b11f4b 边、深色编号），并实现 window.__focus = (id) => {…}：id 非空时相机在约 0.6 s 内平滑插值到该部件（controls.target 移到部件中心，相机拉近到部件包围盒的 2.5 倍），该部件高亮（emissive #b11f4b 强度 0.25）、其余部件 opacity 0.25；id 为 null 时恢复全局视角与全部材质。点击 Sprite 也应调用 __focus。
S5. 运行阶段（STAGES）：window.__stages = [{title, text}]（3–5 个阶段，讲清介质如何在系统中「采集热量 → 输送 / 调节 → 换热 → 循环」，text ≤ 40 字），并实现 window.__setStage = (i) => {…}：高亮该阶段涉及的回路段与部件，其余弱化；覆盖层显示「阶段 i/n · 标题」与说明。场景自带轮播（每阶段 5 s，覆盖层有「暂停 / 继续」按钮，用户拖动视角时不停止轮播）；阶段变化时若 window.__notifyStage 存在则调用 window.__notifyStage(i)。宿主页面会读取 __hotspots / __stages 并通过 __focus / __setStage 驱动场景，因此 __hotspots、__stages、__focus、__setStage 必须在设置 window.__scene 之前定义完毕。
S6. 系统级数字：compute(mode) 由 P 计算并注明假设，至少包含各回路热负荷（kW）、体积流量（L/min）、进出口温差（K，ΔT = Q / (ρ·Q_v·cp)）、换热器 approach 温差或出口温度、泵水力功率（W，= Δp·Q_v，Δp 按 P 中给定的系统阻力）；覆盖层显示当前工况的这些数字，METRICS 与 window.__metrics 使用同一函数的结果。
S7. 规模：本场景 HTML 允许放宽至 320 行 / 15000 字符；系统级场景仍用 kit.setupRenderer / kit.studioLights（部件材质用 kit.material('aluminumCast') / 'powderCoat' / 'polymer' 等，管路用 kit.pipe），可不调 kit.workbench；仍需 try/catch、import map、window.__scene 等通用要求。SUMMARY 描述系统构成、回路、工况与计算假设，不写具体数字（以脚本计算为准）。"""


SCENARIOS = [
    {
        "id": "coldplate",
        "icon": "🔋",
        "color": "blue",
        "title": "电池水冷板",
        "title_en": "EV Battery Cold Plate",
        "subtitle": "一句话生成带 S 形流道的铝制冷板，可剖切查看流道",
        "subtitle_en": "Aluminium cold plate with serpentine channels, cut-away view",
        "pain": "3D 建模耗人 · 投标抢时间",
        "pain_en": "Modeling labour · bid lead time",
        "prompt": "帮我建一个新能源车电池包用的铝合金水冷板：外形 320×180×12 mm，内部 6 道 S 形串联流道，流道宽 10 mm、深 6 mm，壁厚不小于 1.5 mm，进出口在同一短边侧，采用 φ12 mm 快插接头。请给出可剖切查看流道的 3D 模型，并计算铝材质量、流道总长和换热面积。",
        "prompt_en": "Model an aluminium-alloy cold plate for an EV battery pack: envelope 320×180×12 mm, 6 serpentine channels in series inside, channel width 10 mm, depth 6 mm, wall thickness not less than 1.5 mm, inlet and outlet on the same short side with φ12 mm quick-connect fittings. Provide a 3D model with a section view of the channels, and compute the aluminium mass, total channel length and heat-transfer area.",
        "chips": [
            "流道改成 8 道，冷板加宽到 220 mm，重新算质量与流道长度",
            "进出口改为对角布置，并在四角加 M6 安装耳",
            "对比铝 vs 铜两种材料的质量与材料成本",
        ],
        "chips_en": [
            "Change to 8 channels and widen the plate to 220 mm; recompute mass and channel length",
            "Move inlet/outlet to diagonal corners and add M6 mounting lugs at the four corners",
            "Compare aluminium vs copper: mass and material cost",
        ],
    },
    {
        "id": "mchx",
        "icon": "🌬️",
        "color": "green",
        "title": "微通道换热器",
        "title_en": "Micro-channel Heat Exchanger",
        "subtitle": "扁管 + 百叶窗翅片 + 集流管，参数化生成并计算换热面积",
        "subtitle_en": "Flat tubes + louvered fins + headers, parametric with heat-transfer area",
        "pain": "参数化变体 · 快速出方案",
        "pain_en": "Parametric variants · fast proposals",
        "prompt": "建一个微通道换热器芯体：24 根铝扁管，扁管截面 16×1.3 mm、长 300 mm、管间距 8 mm，扁管之间为百叶窗翅片（翅片间距 1.2 mm、厚 0.1 mm，可用简化平直翅片表示），两端 φ20 mm 集流管，进出口 φ12 mm 在同侧。请用 InstancedMesh 表达扁管和翅片，计算扁管外表面积、翅片面积、总换热面积和铝材质量。",
        "prompt_en": "Model a micro-channel heat exchanger core: 24 aluminium flat tubes, tube section 16×1.3 mm, length 300 mm, tube pitch 8 mm, louvered fins between the tubes (fin pitch 1.2 mm, thickness 0.1 mm; simplified plain fins are acceptable), φ20 mm headers at both ends, φ12 mm inlet and outlet on the same side. Use InstancedMesh for the tubes and fins, and compute the tube outer surface area, fin area, total heat-transfer area and aluminium mass.",
        "chips": [
            "翅片间距改为 1.0 mm，扁管增加到 28 根，比较换热面积提升",
            "芯体高度限制在 220 mm 以内，给出可行的扁管数与管距",
            "进出口改为对角布置并在集流管上加 4 个安装耳",
        ],
        "chips_en": [
            "Fin pitch 1.0 mm and 28 tubes: compare the gain in heat-transfer area",
            "Limit core height to 220 mm; propose a feasible tube count and pitch",
            "Move inlet/outlet to diagonal corners and add 4 mounting lugs on the headers",
        ],
    },
    {
        "id": "exv",
        "icon": "🎛️",
        "color": "purple",
        "title": "电子膨胀阀阀体",
        "title_en": "Electronic Expansion Valve Body",
        "subtitle": "黄铜阀体 + 进出口铜管 + 步进电机线圈座，可剖切看阀芯",
        "subtitle_en": "Brass body, copper ports, stepper coil housing, cut-away spool",
        "pain": "阀件建模依赖高手 · 周期长",
        "pain_en": "Valve modeling depends on experts",
        "prompt": "建一个空调用电子膨胀阀：黄铜阀体外径 32 mm、高 60 mm；侧向进口铜管 φ9.52 mm、底部出口铜管 φ9.52 mm；阀体顶部为 φ28 mm、高 35 mm 的步进电机线圈组件（黑色工程塑料外壳 + 线圈）；内部有针阀阀芯与节流孔（φ1.6 mm）。请给出可剖切查看内部阀芯与流道的 3D 模型，并计算黄铜质量、铜管质量和整阀高度。",
        "prompt_en": "Model an electronic expansion valve for air conditioning: brass body OD 32 mm, height 60 mm; side inlet copper tube φ9.52 mm and bottom outlet copper tube φ9.52 mm; a φ28 mm × 35 mm stepper-motor coil assembly on top (black engineering-plastic housing + coil); a needle spool and a φ1.6 mm orifice inside. Provide a 3D model with a section view of the spool and flow path, and compute the brass mass, copper-tube mass and overall valve height.",
        "chips": [
            "阀体改为不锈钢并把外径减到 28 mm，比较质量与成本",
            "增加一个焊接用的进出口铜管延长段 40 mm",
            "做一个 4 阀集成的电子膨胀阀阀岛（共用一个歧管）",
        ],
        "chips_en": [
            "Switch the body to stainless steel with OD 28 mm; compare mass and cost",
            "Add 40 mm brazing extensions to the inlet and outlet tubes",
            "Build a 4-valve EXV manifold block sharing one manifold",
        ],
    },
    {
        "id": "drawing2d",
        "icon": "📐",
        "color": "orange",
        "title": "2D 图纸 / 照片 → 3D",
        "title_en": "2D Drawing / Photo → 3D",
        "subtitle": "上传零件图纸或照片，GPT-6 读取尺寸并还原成 3D 模型",
        "subtitle_en": "Upload a drawing or photo; GPT-6 reads dimensions and rebuilds it in 3D",
        "pain": "图纸转模型 · GPT-6 视觉能力",
        "pain_en": "Drawing-to-model · GPT-6 vision",
        "prompt": "这是我们一个零件的二维工程图，请识别视图和标注尺寸，还原成可旋转、可剖切的 3D 模型，并列出你识别到的主要尺寸和假设。",
        "prompt_en": "This is a 2D engineering drawing of one of our parts. Identify the views and dimension callouts, rebuild it as a rotatable 3D model with a section view, and list the main dimensions you read and the assumptions you made.",
        "requires_image": True,
        "sample_image": "/static/samples/exv_body_drawing.png",
        "chips": [
            "把识别到的尺寸列成表，并标出哪些是估计值",
            "把出口管改成 90° 弯管并加长 30 mm",
            "生成该零件的爆炸视图，分离阀体、接管和线圈组件",
        ],
        "chips_en": [
            "Tabulate the dimensions you read and flag which ones are estimates",
            "Change the outlet tube to a 90° elbow and extend it by 30 mm",
            "Generate an exploded view separating the body, tubes and coil assembly",
        ],
    },
    {
        "id": "aidc",
        "icon": "🖥️",
        "color": "cyan",
        "title": "AIDC GPU 液冷冷板",
        "title_en": "AIDC GPU Liquid-cooling Cold Plate",
        "subtitle": "针肋/微通道铜冷板，对比铜、铝、金刚石-铜复合基板",
        "subtitle_en": "Pin-fin / micro-channel copper cold plate with material comparison",
        "pain": "新业务 · 新材料研究",
        "pain_en": "New business · new materials",
        "prompt": "为 1200 W 的 GPU 设计一块单相液冷冷板：基板 110×90 mm，基板厚 3 mm，上方为 0.3 mm 宽、3 mm 高、间距 0.6 mm 的微通道翅片区（可用 InstancedMesh 简化为 60 片以内的等效翅片并说明等效关系），上盖厚 2 mm，进出口 φ8 mm 位于短边两端。基板材料对比铜、铝、金刚石-铜复合（导热系数分别取 400、200、700 W/m·K），请给出 3D 模型并估算三种材料的质量、基板热阻（近似一维导热）和成本差异。",
        "prompt_en": "Design a single-phase liquid-cooling cold plate for a 1200 W GPU: base plate 110×90 mm, 3 mm thick, with a micro-channel fin field on top (fins 0.3 mm wide, 3 mm tall, 0.6 mm pitch; you may simplify to ≤60 equivalent fins with InstancedMesh and state the equivalence), a 2 mm lid, φ8 mm inlet and outlet at the two short ends. Compare base materials copper, aluminium and diamond-copper composite (thermal conductivity 400, 200 and 700 W/m·K). Provide the 3D model and estimate mass, base-plate thermal resistance (1-D conduction approximation) and cost difference for the three materials.",
        "chips": [
            "翅片改为 φ1.0 mm 圆针肋交错排列，比较换热面积",
            "把冷板做成双 GPU 串联版本，两块芯片间距 60 mm",
            "在盖板上增加一个分流腔，让进口流量均匀分配到各通道",
        ],
        "chips_en": [
            "Replace the fins with staggered φ1.0 mm pin fins; compare heat-transfer area",
            "Make a dual-GPU series version with 60 mm chip spacing",
            "Add a distribution plenum in the lid so inlet flow spreads evenly across channels",
        ],
    },
    {
        "id": "fourway",
        "icon": "♻️",
        "color": "red",
        "title": "四通换向阀 · 减铜优化",
        "title_en": "4-way Reversing Valve · Copper Reduction",
        "subtitle": "主阀体 + 四个接管 + 先导阀，评估壁厚优化与材料替代",
        "subtitle_en": "Main body, four ports, pilot valve; wall-thickness and material trade-offs",
        "pain": "铜价上涨 · 材料成本",
        "pain_en": "Copper price · material cost",
        "prompt": "建一个空调四通换向阀：主阀体为铜制圆筒 φ34 mm、长 110 mm、壁厚 3 mm，上方一根 φ12.7 mm 高压进气管 D，下方并排三根 φ12.7 mm 接管（E、S、C，间距 22 mm），侧面装一个小型先导电磁阀（φ14×45 mm）并用两根 φ3 mm 毛细管连接主阀体两端。请给出可剖切的 3D 模型，并对比：①现状铜壁厚 3 mm；②壁厚优化到 2.2 mm；③主阀体改为不锈钢 2.0 mm 壁厚。分别计算铜/不锈钢用量与材料成本（铜 75,000 元/吨、不锈钢 20,000 元/吨）。",
        "prompt_en": "Model a 4-way reversing valve for air conditioning: copper cylindrical main body φ34 mm, length 110 mm, wall 3 mm; one φ12.7 mm high-pressure inlet tube D on top; three φ12.7 mm tubes (E, S, C, 22 mm apart) side by side underneath; a small pilot solenoid valve (φ14×45 mm) on the side connected to both ends of the main body by two φ3 mm capillary tubes. Provide a 3D model with a section view and compare: ① current copper wall 3 mm; ② wall optimised to 2.2 mm; ③ main body in stainless steel with 2.0 mm wall. Compute copper/stainless usage and material cost for each (copper 75,000 CNY/t, stainless 20,000 CNY/t).",
        "chips": [
            "把三根接管改为 φ15.88 mm，重新计算铜用量",
            "先导阀改为 φ12×40 mm 并移到阀体顶部",
            "给出按年产 200 万只计算的三种方案铜材成本差",
        ],
        "chips_en": [
            "Change the three tubes to φ15.88 mm and recompute copper usage",
            "Change the pilot valve to φ12×40 mm and move it to the top of the body",
            "Give the copper cost difference of the three options at 2 million units/year",
        ],
    },
    {
        "id": "module",
        "icon": "🧩",
        "color": "blue",
        "title": "热管理集成模块",
        "title_en": "Integrated Thermal Management Module",
        "subtitle": "歧管 + 电子水阀 + 电子水泵 + 板式换热器装配体，支持爆炸视图",
        "subtitle_en": "Manifold + e-valve + e-pump + plate HX assembly with exploded view",
        "pain": "系统级方案 · 装配可视化",
        "pain_en": "System-level proposals · assembly visualisation",
        "prompt": "建一个新能源车热管理集成模块的概念装配体：中央为工程塑料歧管本体 260×160×60 mm，内部两条 φ16 mm 主水路；歧管上安装一个五通电子水阀（φ60×70 mm，铝壳）、一个电子水泵（φ70×90 mm，铝壳带出水口）、一个板式换热器 Chiller（120×80×60 mm，不锈钢，20 层板片可简化表达）、两个 φ16 mm 快插接头。请给出 3D 模型，支持「爆炸视图」按钮把各部件沿各自方向分离，并统计部件数量、各部件质量和模块总质量。",
        "prompt_en": "Model a concept assembly of an EV integrated thermal-management module: a central engineering-plastic manifold 260×160×60 mm with two φ16 mm main coolant passages; mounted on it a 5-way electronic coolant valve (φ60×70 mm, aluminium housing), an electronic coolant pump (φ70×90 mm, aluminium housing with outlet), a plate heat exchanger chiller (120×80×60 mm, stainless steel, 20 plates may be simplified) and two φ16 mm quick-connect fittings. Provide the 3D model with an “Exploded view” button that separates each component along its own direction, and report the part count, per-part mass and total module mass.",
        "chips": [
            "增加一个电子膨胀阀和一个 PTC 加热器安装位",
            "歧管改为铝压铸并计算质量变化",
            "把水泵移到歧管底部，减小模块高度到 150 mm 以内",
        ],
        "chips_en": [
            "Add an electronic expansion valve and a PTC heater mounting position",
            "Change the manifold to die-cast aluminium and compute the mass change",
            "Move the pump to the bottom of the manifold to keep module height under 150 mm",
        ],
    },
    # ---------------------------------------------------------------- 第二批：仿真估算 / APS 排程
    {
        "id": "thermal_sim",
        "icon": "🌡️",
        "color": "pink",
        "title": "AI 辅助仿真估算",
        "title_en": "AI-assisted Simulation Estimate",
        "subtitle": "冷板热-流快速估算：3D 温度云图 + 出口温度 / 壁温 / 压降 / 换热系数，CFD 之前先筛方案",
        "subtitle_en": "Cold-plate thermal/flow estimate: 3D temperature map, outlet & wall temperature, Δp, h — screen designs before CFD",
        "pain": "仿真慢 · 靠经验试错",
        "pain_en": "Slow simulation · trial-and-error",
        "prompt": "对一块电池水冷板做快速热-流仿真估算：铝合金冷板 320×180×12 mm，内部 6 道 S 形串联流道（宽 10 mm、深 6 mm，壁厚 1.5 mm），进出口 φ12 mm 在同一短边。冷却液为 50% 乙二醇水溶液，流量 8 L/min，进口温度 25 °C；电芯传给冷板上表面的总热量 2 kW（均匀分布）。请建出冷板 3D 模型，用蓝→红伪彩色温度云图表示流道内冷却液温升与冷板上表面壁温分布，并用集总参数 / 一维模型估算出口温度、最高壁面温度、沿程+弯头总压降、雷诺数和对流换热系数，说明该估算与 CFD 的差别及适用范围。",
        "prompt_en": "Run a quick thermal/flow estimate for a battery cold plate: aluminium-alloy plate 320×180×12 mm with 6 serpentine channels in series (10 mm wide, 6 mm deep, 1.5 mm wall), φ12 mm inlet and outlet on the same short side. Coolant is 50% ethylene-glycol/water at 8 L/min, inlet 25 °C; the cells deliver 2 kW total (uniform) to the top surface. Build the cold-plate 3D model, show a blue→red false-colour temperature map of the coolant rise along the channels and of the top-surface wall temperature, estimate outlet temperature, maximum wall temperature, total pressure drop (friction + bends), Reynolds number and convective heat-transfer coefficient with a lumped / 1-D model, and explain how this estimate differs from CFD and where it applies.",
        "chips": [
            "流量改为 4 L/min 和 12 L/min，对比出口温度、最高壁温与压降",
            "冷却液换成纯水，比较换热系数、压降与最高壁温",
            "流道改为 8 道、宽 8 mm，比较最高壁温与总压降",
        ],
        "chips_en": [
            "Flow 4 L/min vs 12 L/min: compare outlet temperature, max wall temperature and Δp",
            "Switch the coolant to pure water; compare h, Δp and max wall temperature",
            "8 channels, 8 mm wide: compare max wall temperature and total Δp",
        ],
        "metrics_labels_en": ["Outlet temperature (°C)", "Max wall temperature (°C)", "Total pressure drop (kPa)",
                              "Reynolds number", "Convective HTC (W/(m²·K))", "Total flow-path length (m)"],
        "system_extra": """本场景是「AI 辅助仿真估算」：目标是在 CFD 之前用工程近似模型秒级给出方案筛选结论，不是替代 CFD。
A. 物性（25 °C，写入 P 并可切换）：50% 乙二醇水溶液 ρ=1069 kg/m³、cp=3280 J/(kg·K)、μ=3.4e-3 Pa·s、k=0.38 W/(m·K)、Pr≈29；纯水 ρ=997、cp=4180、μ=0.89e-3、k=0.607、Pr≈6.1。铝 k=200 W/(m·K)。
B. 计算模型（全部在 JS 中由 P 计算，覆盖层实时显示；METRICS 中给出同一模型的结果）：
 - 质量流量 m=ρQ；流体总温升 ΔT=Q_heat/(m·cp)；沿流路位置 s 处的流体温度 T(s)=T_in+ΔT·s/L_total（串联流道全部流量通过同一截面）。
 - 水力直径 Dh=4A/P_wet；流速 v=Q/A；Re=ρvDh/μ。Re<2300 取 Nu≈4.0（矩形通道层流），否则 Dittus-Boelter Nu=0.023·Re^0.8·Pr^0.4；h=Nu·k/Dh。
 - 壁面热流 q''=Q_heat/A_wet（A_wet=流道湿周×流路总长）；局部壁温 T_wall(s)=T(s)+q''/h+q''·t_wall/k_Al；最高壁温取出口附近。
 - 压降：摩擦 f=64/Re（层流）或 Blasius f=0.316·Re^-0.25（湍流），Δp_f=f·(L/Dh)·ρv²/2；每个 180° 弯头 K=1.5，进出口接头合计 K=1.5（按 φ12 接口流速），Δp_total=Δp_f+ΣK·ρv²/2，单位换算成 kPa。
C. 可视化：流道用分段实体表示（每道直段拆成 ≥12 段，可用 InstancedMesh + setColorAt 或多个 Mesh），颜色由 tempColor(T) 在 [T_in, T_wall_max] 之间映射：#1d4ed8→#06b6d4→#22c55e→#facc15→#dc2626；冷板上表面用 PlaneGeometry(L, W, 64, 36) + 顶点颜色（vertexColors:true）表示壁温分布：顶点温度=最近流道段的局部壁温，远离流道处略降（乘以 exp(-d/20mm) 的权重后与流体进口温度混合）。默认显示「温度云图」，按钮可切回「材料视图」（铝色 + 蓝色流道）；保留「剖切视图」与「自动旋转」按钮。覆盖层加一条 CSS 渐变色标（linear-gradient 同上五色）并标注最低/最高温度。
D. SUMMARY 中必须说明：这是集总参数 + 经验关联式的估算（典型误差 ±15–25%），适用于流量/工质/流道数的方案对比，最终确认仍需 CFD/试验。SUMMARY 在代码之前输出，因此只描述模型、假设与方法，不要写具体计算结果数字（数值以脚本计算为准）。METRICS 固定 6 项、按此顺序与 label：出口温度(°C)、最高壁面温度(°C)、总压降(kPa)、雷诺数、对流换热系数(W/(m²·K))、流路总长(m)；脚本必须把同一函数算出的这 6 项写入 window.__metrics（同 label、同顺序，value 为字符串），METRICS 区块中的数值应尽量与之一致，note 中注明"以页面实时计算为准"。
E. 本场景 HTML 允许放宽至 260 行 / 12000 字符，其余通用规范不变。""",
    },
    {
        "id": "aps",
        "icon": "📅",
        "color": "teal",
        "title": "APS 智能排程推理",
        "title_en": "APS Scheduling Reasoning",
        "subtitle": "12 张订单 × 3 条装配线：GPT-6 写排程算法 + 3D 甘特图，对比老师傅经验排法并解释规则",
        "subtitle_en": "12 orders × 3 lines: GPT-6 writes the scheduler, renders a 3D Gantt and explains the rules vs. the veteran planner's method",
        "pain": "排程靠老师傅 · 规则不透明",
        "pain_en": "Scheduling by veterans · opaque rules",
        "prompt": "为电子膨胀阀装配车间排一次生产计划。资源：3 条装配线 L1、L2、L3，两班制 08:00–24:00（每班中间休息 30 min：12:00–12:30、20:00–20:30，休息时任务暂停），从周一 08:00 开始排。产品族切换时间：同族之间 0.5 h，跨族 2 h；L3 只能生产 C 族大阀，L1/L2 可生产 A、B、C。订单按接单先后编号（编号 / 产品族 / 所需工时 h / 交期，交期为从周一 08:00 起算的工作小时数；O10–O12 是上周末新接的急单）：O01 A 8 / 56；O02 B 7 / 60；O03 C 9 / 64；O04 A 6 / 48；O05 B 5 / 52；O06 C 6 / 44；O07 B 4 / 22；O08 A 5 / 26；O09 C 6 / 30；O10 A 4 / 12；O11 B 3 / 14；O12 A 5 / 20。请用你设计的排程规则排产，画出可交互的 3D 甘特图，与「老师傅经验排法」（按订单号顺序依次分给最早空闲的可用线体）对比总完工时间、准时率、换型总时间与线体利用率，并解释你用了哪些规则、为什么。",
        "prompt_en": "Schedule production for the electronic-expansion-valve assembly shop. Resources: 3 assembly lines L1, L2, L3, two shifts 08:00–24:00 (30-min break mid-shift: 12:00–12:30 and 20:00–20:30, tasks pause during breaks), starting Monday 08:00. Family changeover: 0.5 h within a family, 2 h across families; L3 can only build family C (large valves), L1/L2 can build A, B and C. Orders numbered by receipt (id / family / hours / due, due = working hours counted from Monday 08:00; O10–O12 are rush orders received over the weekend): O01 A 8 / 56; O02 B 7 / 60; O03 C 9 / 64; O04 A 6 / 48; O05 B 5 / 52; O06 C 6 / 44; O07 B 4 / 22; O08 A 5 / 26; O09 C 6 / 30; O10 A 4 / 12; O11 B 3 / 14; O12 A 5 / 20. Schedule with rules you design, draw an interactive 3D Gantt chart, compare against the “veteran planner’s method” (orders in id order to the earliest-free capable line) on makespan, on-time rate, total changeover time and line utilisation, and explain which rules you used and why.",
        "chips": [
            "插入紧急订单 O13：B 族 5 h、交期 10 h，重新排程并说明受影响的订单",
            "L2 在周二 08:00–12:00 停机保养 4 h，重新排程",
            "切换时间改为跨族 3 h、同族 0.3 h，比较换型总时间与准时率",
        ],
        "chips_en": [
            "Insert rush order O13: family B, 5 h, due 10 h; reschedule and list the affected orders",
            "L2 is down for maintenance Tuesday 08:00–12:00 (4 h); reschedule",
            "Changeover 3 h across families / 0.3 h within: compare total changeover and on-time rate",
        ],
        "metrics_labels_en": ["Makespan AI/veteran (h)", "On-time rate AI/veteran (%)", "Late orders AI/veteran", "Changeover time AI/veteran (h)",
                              "Average utilisation AI/veteran (%)", "Per-line utilisation AI (%)"],
        "system_extra": """本场景是「APS 智能排程推理」：three.js 画的不是零件，而是 3D 甘特图；重点是排程算法透明可解释，并与经验排法对比。
A. 数据与日历：把线体、订单、切换矩阵、班次日历全部放进 P（订单数组含 id/family/hours/due）。时间单位为从周一 08:00 起算的「日历小时」；每天只有 08:00–24:00 可生产（第 d 天的可用时段为 [24d, 24d+4]、[24d+4.5, 24d+12]、[24d+12.5, 24d+16]，其余时间停线），任务遇休息或停线时暂停、下一可用时段续做（写一个 addWorkHours(t, h) 函数逐段推进）。交期 due 按同一日历折算（第 due 个工作小时对应的日历时刻，用 addWorkHours(0, due) 计算）。
B. 算法（JS 中实现两套，按钮「AI 排程 / 经验排法」切换，同一页面重算并重绘）：
 - 经验排法（基线）：按订单号顺序，分配给最早空闲且能做该族的线体，考虑切换时间。
 - AI 排程：按交期 EDD 排序 + 同族连排（若某线体上一订单同族且插队不会导致其它订单迟到，则优先连排以省换型）+ 线体能力约束 + 关键链均衡（选择「完工时刻最早」的可用线体，而不是最早空闲的线体）。两套算法都要输出：makespan、准时率、迟到订单数、总换型时间、各线利用率=生产工时/(makespan 内可用工时)。
C. 可视化（1 单位=1 mm）：X 轴=时间，10 mm/h；Z 轴=线体，每行间距 70 mm，行宽 40 mm；每张订单一个 BoxGeometry 条（高 14 mm），颜色按产品族：A #2563eb、B #15803d、C #d97706；换型时间用 #9aa3ab 矮块（高 6 mm）；休息/停线时段用半透明深灰 (#333, opacity 0.18) 竖板贯穿三行；迟到订单在条顶部加 3 mm 厚 #dc2626 红帽；每张订单的交期在对应行画一根 #b11f4b 细柱（φ2 mm，高 24 mm）。每 8 h 一条浅灰刻度线并在轴下方用 Sprite(CanvasTexture 自绘文字，不加载字体文件) 标注「D1 08:00 / D1 16:00 / D2 08:00 …」；每行左端用同样方式标注 L1/L2/L3；订单条顶部用 Sprite 标注订单号。控制器 autoRotate=false，初始视角方向约 (0.05, 0.75, 1) 归一化，整图占画面 80%。
D. 覆盖层：左上角显示当前算法名、KPI（makespan、准时率、迟到数、换型总时间、平均利用率）与产品族图例；另允许在右上角增加一个宽 ≤ 300px、max-height 45% 可滚动的排程明细表（订单 / 线体 / 开始 / 结束 / 是否迟到），随算法切换更新。按钮：「AI 排程 / 经验排法」「显示 / 隐藏明细」「俯视 / 透视」（切换相机到正上方俯视）。
E. SUMMARY 用工程师能懂的话解释所用规则（EDD、同族连排、能力约束、完工最早优先）及为什么比经验排法好；如有取舍（如为省换型而让某单略晚）要指出。SUMMARY 在代码之前输出，因此不要写具体的 KPI 数字（数值以脚本计算为准）。METRICS 固定 6 项、按此顺序与 label：总完工时间 AI/经验(h)、准时率 AI/经验(%)、迟到订单 AI/经验(单)、换型时间 AI/经验(h)、平均利用率 AI/经验(%)、各线利用率 AI(%)（value 形如 "53 / 54"）；脚本必须把两套算法算出的这 6 项写入 window.__metrics（同 label、同顺序，value 为字符串），METRICS 区块中的数值尽量与之一致，note 中注明「以页面内实时计算为准」。
F. 本场景 HTML 允许放宽至 260 行 / 12000 字符；不需要 RoomEnvironment 的金属质感（可用 MeshStandardMaterial metalness 0.1、roughness 0.7），其余通用规范（import map、window.__scene 等、try/catch、无外部资源）不变。""",
    },
    # ---- Batch 3 · system-level scenes (fluid loops + operating modes + component hotspots + narrated stages)
    {
        "id": "vehicle_tms",
        "kind": "system",
        "icon": "🚗",
        "color": "indigo",
        "title": "整车热管理系统回路",
        "title_en": "Vehicle Thermal Management System",
        "subtitle": "电池 / 电驱 / 座舱三条回路 + 热管理集成模块：GPT-6 生成可切换工况的系统动画、部件热点与热平衡",
        "subtitle_en": "Battery / e-drive / cabin loops with an integrated thermal module: GPT-6 generates a mode-switchable system animation, component hotspots and heat balance",
        "pain": "系统方案靠 PPT 讲 · 工况切换看不见",
        "pain_en": "System proposals live in slides · mode changes are invisible",
        "prompt": "为一台 800 V 纯电 SUV 建一个可交互的整车热管理系统模型（系统级示意，不是单个零件）：电池包 100 kWh（底部电池冷却板）、前电驱（电机 + 逆变器，油冷器 + 冷却液）、座舱 HVAC（蒸发器 + 暖风芯体）、前端模块（低温散热器 + 微通道冷凝器 + 风扇）、电动压缩机、chiller（板式换热器）、两个电子膨胀阀，以及一个热管理集成模块（内含九通电子水阀、两台电子水泵和集成管路，负责把电池回路、电驱回路与前端散热器按工况重新连接）。三条回路：电池冷却液回路、电驱冷却液回路（50% 乙二醇水溶液，均可经集成模块串并联）与冷媒回路（R1234yf）。请实现四个工况并可切换：① 夏季高温制冷 + chiller 给电池降温；② 冬季 −10 ℃ 热泵制热 + 回收电驱余热给座舱与电池；③ 250 kW 快充电池强冷（电池发热 12 kW）；④ 冬季电池加热（电驱余热 + PTC）。要求：回路流动动画、工况按钮切换阀位与流向、编号部件热点对应产品类别、分阶段讲解（热量采集 → 流路调节 → 热量交换 → 循环运行），并计算各回路热负荷、流量、进出口温差、泵水力功率与热泵 COP 估算。",
        "prompt_en": "Build an interactive whole-vehicle thermal-management system model for an 800 V battery-electric SUV (system-level schematic, not a single part): 100 kWh battery pack (cold plate underneath), front e-drive (motor + inverter, oil cooler + coolant), cabin HVAC (evaporator + heater core), front-end module (low-temperature radiator + micro-channel condenser + fan), electric compressor, chiller (plate heat exchanger), two electronic expansion valves, and an integrated thermal module (nine-way electronic coolant valve, two electronic water pumps and integrated piping that reconnects the battery loop, e-drive loop and front radiator per operating mode). Three loops: battery coolant loop, e-drive coolant loop (50 % glycol-water, either can be put in series/parallel through the module) and the refrigerant loop (R1234yf). Implement four switchable modes: ① summer cooling + chiller cooling the battery; ② winter −10 °C heat pump heating with e-drive waste-heat recovery to cabin and battery; ③ 250 kW fast-charge battery cooling (12 kW battery heat); ④ winter battery heating (e-drive waste heat + PTC). Requirements: animated loop flow, mode buttons that change valve positions and flow direction, numbered component hotspots mapped to product categories, staged narration (heat collection → routing → heat exchange → circulation), and computed per-loop heat load, flow rate, inlet/outlet ΔT, pump hydraulic power and an estimated heat-pump COP.",
        "chips": [
            "快充工况下电池发热改为 18 kW，chiller 能否压住？给出电池回路出口温度",
            "把两台电子水泵合并为一台双腔集成泵，比较管路长度、接头数与泵功率",
            "去掉 PTC，只靠电驱余热给电池加热：−10 ℃ 下需要多久升到 15 ℃？",
        ],
        "chips_en": [
            "Fast-charge mode with 18 kW battery heat: can the chiller hold it? Give the battery-loop outlet temperature",
            "Merge the two water pumps into one dual-chamber pump; compare piping length, joints and pump power",
            "Remove the PTC and heat the battery with e-drive waste heat only: how long from −10 °C to 15 °C?",
        ],
        "metrics_labels_en": ["Battery-loop heat load (kW)", "E-drive-loop heat load (kW)", "Refrigerant-loop capacity (kW)",
                              "Total coolant flow (L/min)", "Battery-loop ΔT (K)", "Heat-pump COP (est.)"],
        "system_extra": """A. 部件（Group.name = id；__hotspots 的 part 用产品类别）：battery（电池包 + 冷却板，电池冷却板）、edrive（电机 + 逆变器 + 油冷器，油冷器）、itm（热管理集成模块：九通电子水阀 + 两台电子水泵 + 集成管路，热管理集成模块）、pump1 / pump2（电子水泵，可画在 itm 内部并各自热点）、valve9（九通电子水阀，电子水阀（多通））、chiller（板式换热器）、condenser（微通道冷凝器，微通道换热器）、ltr（低温散热器）、compressor（电动压缩机）、exv1 / exv2（电子膨胀阀）、hvac（蒸发器 + 暖风芯体）、ptc（PTC 加热器）。
A2. 真实车身（本场景例外：允许加载本站 GLB 素材）：import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'; 用 new GLTFLoader().load('/static/assets/car/sedan.glb', …) 加载通用轿车外壳（单位 mm、Y 轴向上、无需缩放；坐标：x 为车长 ±2300（+x 车头）、y 为高度 0…1450（地面 y = 0）、z 为车宽 ±925；节点名以 body 开头的是车身、以 wheel_ 开头的是四个车轮）。加载后遍历 mesh：body* 设为半透明玻璃（MeshStandardMaterial，color #9fb4d8，transparent:true，opacity 0.12，depthWrite:false，side: THREE.DoubleSide），wheel_* 保持深色不透明；把 gltf.scene 加入名为 car 的 Group。部件按同一坐标系摆进车身：电池包在地板下 y≈150–320、x −1200…+900；集成模块 itm 在电池前端 x≈+800、y≈380；电驱在前轴附近 x≈+1300、y≈420；压缩机 x≈+1550、y≈520；chiller 靠近 itm；前端模块 condenser / ltr 在 x≈+2050、y≈450–850（竖直放置）；hvac 在 x≈+950、y≈750（仪表板位置）；ptc 靠近 hvac。加载是异步的：先创建全部程序化几何、回路与覆盖层并设置 window.__scene 等，再在 onLoad 中把车身 add 进去，不要阻塞渲染；相机包围盒只按部件 Group 计算即可（车身在其外围）；加载失败时退回半透明线框 Box 并在覆盖层小字提示。
B. 回路：battery_loop（#0f766e）、edrive_loop（#22c55e，与电池回路区分）、refrigerant（#2563eb）；工况 ② 与 ④ 中电池回路与电驱回路经 valve9 串联（合并为一条流路，粒子按合并后的路径运动），工况 ①③ 中并联并各自经 chiller / ltr。冷媒回路在制冷工况经 condenser → exv → hvac 蒸发器 / chiller，热泵工况反向利用前端换热器作蒸发器、hvac 内冷凝器放热（可用同一 Tube 路径但粒子反向与颜色变化表达）。
C. compute(mode) 假设（写入 P 并可改）：电池发热 Q_bat：①2 kW ②0.5 kW ③12 kW ④0（被加热，需求 3 kW）；电驱损耗 Q_edrive = P_mech·(1−η)，η=0.92，P_mech：①40 kW ②25 kW ③0 ④25 kW；座舱负荷 ①4 kW 制冷 ②5 kW 制热；乙二醇水 ρ=1069 kg/m³、cp=3280 J/(kg·K)；泵流量：电池回路 12 L/min、电驱回路 15 L/min（工况 ② ④ 串联时取 15 L/min）；系统阻力 Δp：电池回路 45 kPa、电驱回路 60 kPa（串联相加）；泵水力功率 = Δp·Q_v。热泵 COP 估算 = 0.45 × T_cond/(T_cond − T_evap)（开尔文；制冷时 T_evap=5 ℃、T_cond=55 ℃；−10 ℃ 热泵时 T_evap=−15 ℃、T_cond=50 ℃；余热回收时 T_evap 提高到 5 ℃ 并在覆盖层说明 COP 提升）。ΔT = Q/(ρ·Q_v·cp)。
D. METRICS 固定 6 项、按此顺序与 label：电池回路热负荷(kW)、电驱回路热负荷(kW)、冷媒回路制冷/制热量(kW)、冷却液总流量(L/min)、电池回路进出口温差(K)、热泵 COP 估算；value 为当前工况的值（切换工况后 window.__metrics 同步更新），note 注明「以页面实时计算为准」。
E. 阶段：热量采集（电池 / 电驱 / 座舱产热或需热）→ 流路调节（九通阀与两台泵按工况重排回路）→ 热量交换（chiller / 冷凝器 / 低温散热器 / 暖风芯体）→ 循环运行。SUMMARY 中说明这是系统级示意与集总参数估算，部件几何为示意比例。""",
    },
    {
        "id": "cdu",
        "kind": "system",
        "icon": "💧",
        "color": "slate",
        "title": "AIDC CDU 液冷分配单元",
        "title_en": "AIDC Coolant Distribution Unit",
        "subtitle": "一次侧设施水 ↔ 二次侧机柜回路：板换 + N+1 电子水泵 + 电子水阀，GPT-6 生成系统动画、故障切换与热平衡",
        "subtitle_en": "Facility water ↔ rack loop: plate HX + N+1 electronic pumps + electronic valves; GPT-6 generates the system animation, failover modes and heat balance",
        "pain": "液冷系统方案难直观呈现 · 故障工况靠口述",
        "pain_en": "Liquid-cooling proposals are hard to visualise · failure modes are explained verbally",
        "prompt": "为一个 1.2 MW 的 AI 数据中心列级 CDU（冷却液分配单元）建一个可交互的系统模型（系统级示意）：二次侧向 8 个 150 kW 液冷机柜供液（25% 丙二醇水溶液，供液 32 ℃），每个机柜经供 / 回液主管（manifold）、快接、隔离用电子水阀接到机柜内的 GPU 冷板；CDU 内部：钎焊板式换热器、两台变频电子水泵（N+1，一用一备）、过滤器、膨胀 / 补液罐、供回液温度 / 压力 / 流量传感器；一次侧接设施冷却水（供水 18 ℃），由一台电子比例调节水阀控制一次侧流量以稳定二次侧供液温度。请实现四个工况并可切换：① 正常运行；② 1 号泵故障 → 备泵自动切换；③ 5 号机柜漏液 → 该支路电子水阀隔离，其余机柜继续运行；④ 一次侧供水升到 32 ℃ 的温水冷却工况。要求：一次侧 / 二次侧回路流动动画（颜色区分）、工况按钮、编号部件热点对应产品类别（电子水泵、电子水阀、板式换热器、液冷冷板等）、分阶段讲解（机柜吸热 → 回液汇流 → 板换换热 → 一次侧排热 → 供液分配），并计算总热负荷、二次侧流量与供回液温差、板换 approach 温差、泵水力功率及其占 IT 负荷的比例。",
        "prompt_en": "Build an interactive system model (system-level schematic) of a 1.2 MW row-level CDU (coolant distribution unit) for an AI data centre: the secondary side feeds 8 liquid-cooled racks of 150 kW each (25 % propylene-glycol water, 32 °C supply); each rack connects through supply/return manifolds, quick couplings and an isolating electronic water valve to the GPU cold plates inside. Inside the CDU: brazed plate heat exchanger, two variable-speed electronic water pumps (N+1, one duty one standby), filter, expansion/make-up tank, supply/return temperature, pressure and flow sensors. The primary side is facility chilled water (18 °C supply) with an electronic proportional valve modulating primary flow to hold the secondary supply temperature. Implement four switchable modes: ① normal operation; ② pump 1 failure → automatic changeover to the standby pump; ③ rack 5 leak → its branch valve isolates while the other racks keep running; ④ warm-water cooling with 32 °C primary supply. Requirements: animated primary/secondary loop flow in distinct colours, mode buttons, numbered component hotspots mapped to product categories (electronic water pump, electronic water valve, plate heat exchanger, liquid-cooling cold plate …), staged narration (rack heat pickup → return collection → plate-HX exchange → primary heat rejection → supply distribution), and computed total heat load, secondary flow and supply/return ΔT, plate-HX approach temperature, pump hydraulic power and its share of IT load.",
        "chips": [
            "机柜扩到 12 个（1.8 MW）：泵流量与压降如何变化，是否需要升级泵或改并联运行？",
            "二次侧供液温度提高到 40 ℃ 并把一次侧改为干冷器：approach 温差与全年免费冷却时长",
            "每个机柜支路加流量平衡阀，比较各机柜流量偏差与总压降",
        ],
        "chips_en": [
            "Scale to 12 racks (1.8 MW): how do pump flow and pressure drop change; upgrade the pumps or run both in parallel?",
            "Raise secondary supply to 40 °C with a dry cooler on the primary side: approach ΔT and free-cooling hours",
            "Add a balancing valve per rack branch; compare per-rack flow deviation and total pressure drop",
        ],
        "metrics_labels_en": ["Total heat load (kW)", "Secondary flow (L/min)", "Secondary supply/return ΔT (K)",
                              "Plate-HX approach ΔT (K)", "Pump hydraulic power (kW)", "Pump power / IT load (%)"],
        "system_extra": """A. 部件（Group.name = id；__hotspots 的 part 用产品类别）：hx（钎焊板式换热器，板式换热器）、pump1 / pump2（变频电子水泵，电子水泵）、pvalve（一次侧电子比例调节水阀，电子水阀）、filter（过滤器）、tank（膨胀 / 补液罐）、sensors（供回液温压流传感器，可合并为一个热点）、manifold_s / manifold_r（二次侧供 / 回液主管）、rack1…rack8（机柜，每个含 GPU 冷板阵列示意，液冷冷板；rack5 带隔离电子水阀 rvalve5 热点，电子水阀）、facility（一次侧设施水接口）。CDU 机柜用半透明 Box（opacity 0.12）画外壳，内部部件可见；8 个机柜排成一列，主管沿列布置。
B. 回路：primary（一次侧设施水 #7c3aed）、secondary_supply（二次侧供液 #0891b2）、secondary_return（回液，颜色向 #dc2626 过渡表达升温）。工况 ②：pump1 粒子停止、pump2 启动（高亮切换）并在覆盖层显示切换耗时假设（≤ 3 s）；工况 ③：rack5 支路粒子停止、rvalve5 高亮为红色、其余 7 个机柜流量重新分配；工况 ④：一次侧颜色变暖、pvalve 开度增大（覆盖层显示开度 %）。
C. compute(mode) 假设（写入 P 并可改）：IT 负荷 8×150 kW（工况 ③ 为 7×150 kW）；25% 丙二醇水 ρ=1020 kg/m³、cp=3900 J/(kg·K)；二次侧设计供回液温差 ΔT_s = 10 K → 流量 Q_v = Q/(ρ·cp·ΔT_s)；一次侧供水 18 ℃（工况 ④ 32 ℃）、一次侧设计温差 12 K；板换 approach = 二次侧供液温度 − 一次侧供水温度（工况 ④ 中二次侧供液需提高到 一次侧供水 + 设计 approach 4 K，并说明对机柜进液温度的影响）；二次侧系统阻力 Δp = 250 kPa（机柜 + 管路 + 板换）；泵水力功率 = Δp·Q_v，泵效率 0.65 折算轴功率；泵功占比 = 轴功率 / IT 负荷。工况 ② 数字与 ① 相同但标注「备泵运行」。
D. METRICS 固定 6 项、按此顺序与 label：总热负荷(kW)、二次侧流量(L/min)、二次侧供回液温差(K)、板换 approach 温差(K)、泵水力功率(kW)、泵功占 IT 负荷(%)；value 为当前工况的值（切换工况后 window.__metrics 同步更新），note 注明「以页面实时计算为准」。
E. 阶段：机柜吸热（冷板带走 GPU 热量）→ 回液汇流（回液主管汇集到 CDU）→ 板换换热（二次侧热量传给一次侧）→ 一次侧排热（设施水带走热量）→ 供液分配（泵加压经供液主管回到各机柜）。SUMMARY 中说明这是系统级示意与集总参数估算，部件几何为示意比例。""",
    },
    # ---------------------------------------------------------------- industry: notebook / electronics manufacturing
    {
        "id": "nb_thermal",
        "industry": "notebook",
        "kind": "system",
        "icon": "💻",
        "color": "teal",
        "title": "笔记本双风扇散热模组",
        "title_en": "Notebook Dual-Fan Thermal Module",
        "subtitle": "均热板 + 热管 + 翅片 + 双风扇：三档风扇工况、气流动画、热阻链与 CPU / GPU 结温预估",
        "subtitle_en": "Vapor chamber + heat pipes + fin stacks + two fans: three fan modes, airflow animation, thermal-resistance chain and CPU / GPU junction-temperature estimate",
        "pain": "散热方案靠经验试错 · 结温要等样机实测",
        "pain_en": "Cooling designs iterate by trial · junction temps wait for prototypes",
        "prompt": "为一台 14 英寸轻薄本设计双风扇散热模组（系统级装配，不是单个零件）：机身内部可用空间 300 × 200 mm、整机厚 15.9 mm、散热模组高度上限 9 mm。热源：CPU 45 W（封装 40 × 30 mm）、独显 GPU 60 W（封装 29 × 29 mm）。方案：一块 0.6 mm 厚铜均热板（130 × 85 mm）同时覆盖 CPU 与 GPU；两根 φ6 压扁至 2.0 mm 的烧结铜热管把热量导到左右两组翅片；翅片组各 60 × 10 × 9 mm，铜翅片厚 0.10 mm、间距 0.35 mm；两台 φ48 mm 离心风扇（厚 7 mm，出风口对着翅片）；CPU 用液态金属界面材料、GPU 用导热膏；石墨片覆盖 D 壳内表面。进风从 D 壳底部格栅，出风从转轴侧。请实现三个模式并可切换：安静（风扇 2800 rpm）、均衡（4200 rpm）、性能（5600 rpm，CPU + GPU 同时满载 105 W）；做气流粒子动画（进风 → 翅片 → 出风）、编号部件热点、分阶段讲解（芯片导热 → 均热板 / 热管扩散 → 翅片对流 → 风扇排出），并计算每个模式的风量、翅片换热面积、热阻链（TIM → 均热板 → 热管 → 翅片 → 空气）、CPU 预估结温、噪声估算与模组质量。",
        "prompt_en": "Design a dual-fan thermal module for a 14-inch thin-and-light notebook (a system-level assembly, not a single part): usable interior 300 × 200 mm, chassis thickness 15.9 mm, module height limit 9 mm. Heat sources: CPU 45 W (40 × 30 mm package) and discrete GPU 60 W (29 × 29 mm). Concept: one 0.6 mm copper vapor chamber (130 × 85 mm) covering both CPU and GPU; two φ6 sintered copper heat pipes flattened to 2.0 mm carry heat to left and right fin stacks; each fin stack 60 × 10 × 9 mm with 0.10 mm copper fins at 0.35 mm pitch; two φ48 mm centrifugal fans (7 mm thick, outlets facing the fins); liquid-metal TIM on the CPU, thermal paste on the GPU; a graphite sheet on the inside of the bottom cover. Intake through the bottom-cover grille, exhaust towards the hinge. Implement three switchable modes: Quiet (fans 2800 rpm), Balanced (4200 rpm) and Performance (5600 rpm, CPU + GPU fully loaded at 105 W); animate airflow particles (intake → fins → exhaust), numbered component hotspots and staged narration (die conduction → vapor-chamber / heat-pipe spreading → fin convection → fan exhaust), and compute per mode the airflow, fin heat-transfer area, thermal-resistance chain (TIM → vapor chamber → heat pipe → fins → air), estimated CPU junction temperature, noise estimate and module mass.",
        "chips": [
            "GPU 提到 80 W、翅片间距改 0.30 mm：性能模式下 GPU 结温还能否压在 87 ℃ 以内？",
            "去掉一台风扇改单风扇 + 单侧翅片，比较三个模式的结温、噪声与质量",
            "均热板换成 3 根 φ8 热管 + 铜底座（成本方案），给出热阻链变化与结温差异",
        ],
        "chips_en": [
            "GPU at 80 W and fin pitch 0.30 mm: can the GPU junction stay under 87 °C in Performance mode?",
            "Drop to one fan with a single fin stack; compare junction temperature, noise and mass across the three modes",
            "Replace the vapor chamber with three φ8 heat pipes on a copper base (cost option): show the resistance chain and temperature deltas",
        ],
        "metrics_labels_en": ["Dissipated power (W)", "Total airflow (CFM)", "Fin heat-transfer area (cm²)",
                              "Total thermal resistance (K/W)", "Estimated CPU junction temperature (°C)", "Module mass (g)"],
        "system_extra": """A. 部件（Group.name = id；__hotspots 的 part 用散热部件类别：风扇 / 均热板 / 热管 / 翅片组 / 导热界面材料 / 石墨片 / 热源）：cpu、gpu（热源，用 Box 表示芯片封装，performance 模式下颜色更红）、vc（均热板）、hp_left / hp_right（压扁热管，沿 VC 边缘弯到翅片）、fins_left / fins_right（翅片组，翅片用 InstancedMesh）、fan_left / fan_right（离心风扇：轮毂 + 叶片 Group，运行时旋转，转速与模式成正比）、tim_cpu / tim_gpu（导热界面材料，薄片）、graphite（石墨片，覆盖 D 壳内表面的薄板）、chassis（真实机身，见 A2）。
A2. 真实机身（本场景例外：允许加载本站 GLB 素材，呈现方式按末尾【笔记本素材呈现规范】）：import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'; 加载 /static/assets/notebook/laptop14_open.glb 到名为 chassis 的 Group（替代任何 Box 机身），base* 半透明以露出内部（N5）。散热模组必须放在机身内部并使用同一坐标系：y 在 2 … 12 mm 之间（转轴侧机身厚 14.5 mm、前沿 9.5 mm）、x 在 ±145 之内、z 在 −100 … +40 之内；CPU / GPU 与均热板在机身中后部（z ≈ −40 … −90），两台风扇靠转轴侧两端（x ≈ ±100，z ≈ −70 … −95），翅片组紧贴风扇出风口、出风方向朝 −z（转轴侧的排风口），进风粒子从机身底面（y ≈ 0）上来。相机包围盒按散热模组 + 机身底座（不含打开的屏幕）计算。
B. 回路：本场景的「介质」是空气，不是液体：airflow_left / airflow_right 两条气流路径（颜色 #38bdf8）从 D 壳底部进风口 → 风扇 → 翅片 → 转轴侧出风口，用 TubeGeometry 画半透明导风轮廓并沿 CatmullRomCurve3 运动粒子，粒子速度与风扇转速成正比；热量路径 heat_cpu / heat_gpu（#f97316）从芯片 → VC → 热管 → 翅片，用少量慢速粒子表示导热方向。不需要回液回路。
C. compute(mode) 假设（写入 P 并可改）：环境温度 T_amb = 25 ℃；每台风扇风量 Q_fan(CFM) = 2.6 × rpm / 5600，总风量 = 2 × Q_fan（1 CFM = 4.72e-4 m³/s）；空气 ρ = 1.16 kg/m³、cp = 1005 J/(kg·K)；翅片数 n = floor(60 / (0.10 + 0.35)) 每组，翅片换热面积 A = 2 组 × n × 2 × (10 × 9 mm²)；对流换热系数 h(W/(m²·K)) = 45 + 0.0065 × rpm；热负荷：安静与均衡模式 CPU 28 W + GPU 35 W（功耗墙），性能模式 CPU 45 W + GPU 60 W；空气温升 ΔT_air = Q / (ρ · cp · Q_v)；翅片对空气热阻 R_fin = 1 / (h · A)；热阻链（K/W）：R_tim_cpu = 0.02（液态金属）、R_tim_gpu = 0.06（导热膏）、R_vc = 0.08、R_hp = 0.05（两根并联取 0.025）、R_fin 由上式计算；总热阻 R_total = R_tim_cpu + R_vc + R_hp_par + R_fin；CPU 预估结温 T_j_cpu = T_amb + 0.5 × ΔT_air + Q_total × (R_fin) + Q_cpu × (R_tim_cpu + R_vc + R_hp_par)（GPU 同理用 R_tim_gpu，覆盖层同时显示）；噪声估算 L(dBA) = 18 + 28 × log10(rpm / 1000)；质量：铜 8.96 g/cm³（VC 按实心体积的 50% 计、翅片按片数 × 单片体积、热管按外壳壁厚 0.3 mm）、风扇每台 22 g、石墨片 2.1 g/cm³ × 0.1 mm × 覆盖面积、支架与固定件合计 15 g。
D. METRICS 固定 6 项、按此顺序与 label：散热功率(W)、总风量(CFM)、翅片换热面积(cm²)、总热阻(K/W)、CPU 预估结温(℃)、模组质量(g)；value 为当前模式的值（切换后 window.__metrics 同步更新），note 注明「集总参数估算，以页面实时计算为准」。
E. 阶段：芯片导热（TIM 把芯片热量传到均热板）→ 均热板 / 热管扩散（相变工质把热量摊开并导向两侧）→ 翅片对流（空气流过翅片带走热量）→ 风扇排出（热风从转轴侧排出机身）。覆盖层用一行显示当前模式的 T_j_cpu / T_j_gpu 并在超过 95 ℃ 时标红提示「触发功耗墙」。SUMMARY 中说明这是集总参数估算（非 CFD），几何为示意比例。""",
    },
    {
        "id": "nb_chassis_mold",
        "industry": "notebook",
        "icon": "🧲",
        "color": "amber",
        "title": "镁合金 A 壳与压铸模具概念",
        "title_en": "Magnesium A-Cover & Die-Casting Mold Concept",
        "subtitle": "AZ91D 顶盖结构（壁厚 / 加强筋 / 螺柱 / 天线镶件）+ 动定模、分型面、浇口、锁模力与周期产量估算",
        "subtitle_en": "AZ91D top cover (wall / ribs / bosses / antenna insert) + moving / fixed die halves, parting line, gate, clamping force and cycle-output estimate",
        "pain": "结构改一处模具评审等一周 · 锁模力与成本靠经验",
        "pain_en": "One structural tweak means a week of tooling review · tonnage and cost by gut feel",
        "prompt": "为一台 14 英寸笔记本建一个镁合金（AZ91D）压铸 A 壳（屏幕顶盖）及其压铸模具概念：外形 312 × 217 mm、四角圆角 R8，主壁厚 0.8 mm，四周翻边高 6.5 mm、翻边厚 1.0 mm；内侧网格加强筋（宽 0.8 mm、高 2.0 mm、间距 45 mm）；两个转轴安装区各 3 个 M2 螺柱凸台（φ4.5、高 3.5 mm）；顶部 10 mm 宽的天线净空区改用 PC+GF 塑料镶件；屏幕面胶槽宽 3 mm。同时构建压铸模具的概念模型：动模 / 定模两半（用「模具视图」按钮在合模 / 开模之间切换，开模时 A 壳留在动模一侧并沿脱模方向移出），分型面位于翻边顶端，脱模方向垂直于顶盖，脱模斜度 1°，扇形浇口位于转轴侧长边，对侧 4 个溢流槽与排气道；判断是否需要滑块（转轴螺柱与翻边均沿脱模方向，可不用滑块）。计算：净质量、投影面积、锁模力估算（比压 60 MPa、安全系数 1.2）、模具外形尺寸估算、每模周期时间与单班（8 h、OEE 85%）产量估算、材料成本（AZ91D 按 28,000 元/吨、回炉料利用率 40% 假设）。",
        "prompt_en": "Build a magnesium-alloy (AZ91D) die-cast A-cover (display top cover) for a 14-inch notebook together with a die-casting mold concept: outline 312 × 217 mm with R8 corners, main wall 0.8 mm, perimeter flange 6.5 mm high and 1.0 mm thick; inner grid ribs (0.8 mm wide, 2.0 mm high, 45 mm pitch); two hinge zones with three M2 screw bosses each (φ4.5, 3.5 mm high); a 10 mm antenna clearance strip along the top replaced by a PC+GF plastic insert; a 3 mm adhesive groove on the display side. Also model the die-casting mold concept: moving and fixed halves (a “Mold view” button toggles closed / open; when open the cover stays on the moving half and slides out along the ejection direction), parting plane at the top of the flange, ejection perpendicular to the cover, 1° draft, a fan gate on the hinge-side long edge, four overflows with vents on the opposite edge; decide whether slides are needed (bosses and flange follow the ejection direction, so none). Compute: net mass, projected area, clamping-force estimate (specific pressure 60 MPa, safety factor 1.2), mold outline estimate, cycle time and single-shift (8 h, OEE 85 %) output, and material cost (AZ91D at 28,000 CNY/t, 40 % remelt recovery assumed).",
        "chips": [
            "主壁厚改 0.65 mm、加强筋间距 35 mm：质量、锁模力与成本怎么变？薄壁充型风险如何？",
            "改为铝合金 ADC12 压铸，比较质量、锁模力、材料成本与散热能力",
            "把镁合金压铸改成碳纤维复合材料层压顶盖，比较质量、厚度与单件工艺成本",
        ],
        "chips_en": [
            "Main wall 0.65 mm and rib pitch 35 mm: how do mass, clamping force and cost change, and what is the thin-wall filling risk?",
            "Switch to ADC12 aluminium die casting; compare mass, clamping force, material cost and heat spreading",
            "Replace the magnesium casting with a carbon-fibre laminate cover; compare mass, thickness and per-part process cost",
        ],
        "metrics_labels_en": ["Net mass (g)", "Projected area (cm²)", "Clamping-force estimate (t)",
                              "Mold outline estimate (mm)", "Single-shift output (pcs / 8 h)", "Material cost (CNY / pc)"],
        "system_extra": """本场景是「结构件 + 模具概念」：主体是一个可剖切、可爆炸的压铸件装配（A 壳 + 塑料镶件），外加一套概念模具。
A. 部件（各自命名 Group）：cover（镁合金 A 壳，颜色 #b8bec7、metalness 0.6）、ribs（加强筋网格，用 InstancedMesh 或合并 Box）、bosses（6 个螺柱凸台）、insert（PC+GF 天线镶件，#2b2b2b）、die_fixed（定模，半透明 #64748b opacity 0.25）、die_moving（动模，半透明 #475569 opacity 0.25，含 4 根顶杆 Cylinder）、gate（扇形浇口 + 料饼，#c9a227）、overflows（4 个溢流槽 Box，#c9a227）、reference（装机参考，见 A2）。
A2. 装机参考（本场景例外：允许加载本站 GLB 素材，呈现方式按末尾【笔记本素材呈现规范】）：加载 /static/assets/notebook/laptop14_open.glb（开盖 110°）到名为 reference 的 Group，按 N3 / N4 赋材质与屏幕壁纸、保持不透明实体，放在 A 壳右侧约 x = +420 mm 处作为「装机位置参考」——A 壳就是屏幕外侧那一片（可把 A 壳按 lid 的位姿再画一份半透明副本贴在参考机屏幕背面，说明装配位置）。零件视图与模具视图都保留该参考；覆盖层加一个「隐藏 / 显示参考整机」按钮。相机包围盒只按 A 壳 + 模具计算。
B. 交互：覆盖层除通用按钮外增加「模具视图 / 零件视图」按钮：零件视图隐藏 die_*/gate/overflows；模具视图显示两半模具并提供「合模 / 开模」切换——开模时 die_fixed 沿脱模方向（+Y）移开 120 mm、cover 随动模显示并被顶杆顶出 15 mm，动画 0.8 s 插值。用一根箭头（ArrowHelper）标出脱模方向，用一条细线框标出分型面。
C. compute() 假设（写入 P 并可改）：镁合金 AZ91D 密度 1.81 g/cm³，PC+GF 1.40 g/cm³；净体积 = 主壁（外形面积 − 天线区）× 0.8 + 翻边（周长 × 6.5 × 1.0）+ 加强筋（按条数 × 长度 × 0.8 × 2.0）+ 螺柱（6 × 圆柱体积）；投影面积 A_proj = 铸件外形面积 × 1.25（含浇口、溢流槽与料饼）；锁模力 F(t) = 60 MPa × A_proj × 1.2 / 9.81 ≈ 单位 t；模具外形 = 铸件外形 + 每边 150 mm 模框，模具高度 = 两半各 250 mm；周期时间 = 45 s（含喷涂、取件），单班产量 = 8 × 3600 / 45 × 0.85；材料成本 = 净质量 × 28 元/kg × (1 + 0.6 × 浇道比 0.35)（说明：浇道与溢流废料 35%，其中 40% 回炉再利用）。
D. METRICS 固定 6 项、按此顺序与 label：净质量(g)、投影面积(cm²)、锁模力估算(t)、模具外形估算(mm)、单班产量估算(件/8h)、材料成本(元/件)；note 注明假设（比压 60 MPa、周期 45 s 等）。覆盖层同时显示「是否需要滑块：否（所有特征沿脱模方向）」与脱模斜度。SUMMARY 中说明这是概念级结构与模具布置，未做模流 / 凝固分析。""",
    },
    {
        "id": "nb_assembly_line",
        "industry": "notebook",
        "kind": "system",
        "icon": "🏭",
        "color": "slate",
        "title": "笔记本总装产线数字孪生",
        "title_en": "Notebook Assembly-Line Digital Twin",
        "subtitle": "14 个工位 + AGV 配送 + 并行测试 / 老化：三种排产模式切换，工件流动动画，节拍 / 线平衡 / 瓶颈 / OEE 实时计算",
        "subtitle_en": "14 stations + AGV delivery + parallel test / run-in: three production plans, moving work-pieces, live takt / line balance / bottleneck / OEE",
        "pain": "产线改造靠 Excel 与经验 · 瓶颈要开线后才看见",
        "pain_en": "Line changes planned in Excel · bottlenecks only show up after launch",
        "prompt": "为一条笔记本总装产线建一个可交互的数字孪生（系统级示意）：线体长 60 m、U 形布局，14 个工位：① 底壳（D 壳）上线 ② 主板 + 散热模组装配 ③ 自动锁螺钉（六轴机器人）④ 电池 + 扬声器 ⑤ 屏幕总成 + 转轴 ⑥ 键盘 / 触控板 + C 壳合盖 ⑦ 自动锁螺钉 ⑧ 外观 AOI 视觉检测 ⑨ 烧录与功能测试（并行 6 台测试机台）⑩ 老化 Run-in（2 h，架式 240 台位）⑪ 出货软件与终检 ⑫ 贴标 + 包装 ⑬ 装箱码垛（协作机器人）⑭ 成品下线到 AGV。物料由 AGV 从线边仓配送到工位。请实现三个模式并可切换：① 单班 800 台 / 8 h；② 双班 1,800 台 / 16 h（并行测试机台增至 9 台、老化台位增至 300）；③ 自动化升级（在 ② 基础上 ④⑥⑫ 工位改为机器人辅助、AOI 全检，操作员减少）。做工件在传送带上流动的动画、工位编号热点（标注自动化类别：机器人 / AOI / 测试机台 / 老化架 / AGV / 人工工位）、分阶段讲解（上料 → 装配 → 测试老化 → 包装出货），并计算每个模式的节拍时间、线平衡率、瓶颈工位、在制品数量、操作员人数、人均小时产出与 OEE 估算。",
        "prompt_en": "Build an interactive digital twin of a notebook final-assembly line (system-level schematic): 60 m U-shaped line with 14 stations: ① bottom-cover loading ② motherboard + thermal module ③ automatic screwing (6-axis robot) ④ battery + speakers ⑤ display assembly + hinges ⑥ keyboard / touchpad + C-cover closing ⑦ automatic screwing ⑧ cosmetic AOI inspection ⑨ firmware flashing & functional test (6 parallel testers) ⑩ run-in (2 h, 240-slot rack) ⑪ shipping image & final inspection ⑫ labelling + packing ⑬ cartoning & palletising (collaborative robot) ⑭ finished goods to AGV. Materials are delivered by AGVs from the line-side warehouse. Implement three switchable plans: ① one shift, 800 units / 8 h; ② two shifts, 1,800 units / 16 h (9 parallel testers, 300 run-in slots); ③ automation upgrade (on top of ②: stations ④ ⑥ ⑫ robot-assisted, 100 % AOI, fewer operators). Animate work-pieces moving on the conveyor, numbered station hotspots tagged by automation class (robot / AOI / tester / run-in rack / AGV / manual), staged narration (loading → assembly → test & run-in → packing & shipping), and compute per plan the takt time, line-balance rate, bottleneck station, WIP, headcount, units per operator-hour and an OEE estimate.",
        "chips": [
            "把老化时间从 2 h 压到 1 h、台位保持 240：瓶颈会转移到哪里？三个模式的日产能各多少？",
            "在 ⑨ 与 ⑩ 之间加一个缓存区（60 台位），比较在制品与节拍稳定性",
            "把 U 形线改成两条平行直线各 7 工位，比较占地、操作员数与线平衡率",
        ],
        "chips_en": [
            "Cut run-in from 2 h to 1 h with 240 slots unchanged: where does the bottleneck move, and what is the daily output per plan?",
            "Add a 60-slot buffer between ⑨ and ⑩; compare WIP and takt stability",
            "Split the U-line into two parallel straight lines of 7 stations each; compare floor space, headcount and line balance",
        ],
        "metrics_labels_en": ["Takt time (s / unit)", "Line-balance rate (%)", "Bottleneck station",
                              "Work in process (units)", "Headcount (operators)", "OEE estimate (%)"],
        "system_extra": """A. 部件（Group.name = id；__hotspots 的 part 用自动化类别：机器人 / AOI / 测试机台 / 老化架 / AGV / 人工工位）：st01…st14（14 个工位，每个为一张工作台 Box + 设备示意：机器人用两段 Box 手臂 + 底座并缓慢摆动，测试机台用一排小 Box，老化架用多层货架，人工工位放一个简化人形 Capsule），conveyor（U 形传送带：三段 Box 连成 U 形，总长 60 m，工位沿带外侧布置，1 单位 = 1 mm，可把整线按 1:1 摆放并让工位设备适度放大），agv_1…agv_3（AGV 小车沿线边仓 → 工位的独立路径运动），warehouse（线边仓，半透明 Box）。整线按 1:1 摆放时相机初始距离要能看到全线。
B. 回路：本场景的「介质」是工件与物料：flow_units（#0ea5e9）沿传送带 U 形路径运动的工件粒子（数量 ≈ 在制品数），粒子在每个工位处短暂停留（时长与该工位节拍成正比）；flow_agv（#f59e0b）AGV 沿线边仓到工位的补料路径往返。不需要液体管路与 TubeGeometry，传送带本身就是路径。
B2. 真实工件（本场景例外：允许加载本站 GLB 素材，呈现方式按末尾【笔记本素材呈现规范】）：import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js'; 加载 /static/assets/notebook/laptop14_closed.glb（合盖，约 301 × 14.5 × 220 mm）。加载后 gltf.scene.updateMatrixWorld(true)，遍历所有 mesh，把每个几何体 clone 并 applyMatrix4(mesh.matrixWorld)，删除 uv / color 等不一致的属性后用 mergeGeometries 合并为一个 BufferGeometry，再创建一个 InstancedMesh（材质按 N3 的 base* 配方：#cfd0cc、metalness 0.85、roughness 0.32；实例数 = 在制品上限，多余实例缩放为 0 隐藏）作为工件粒子的可视形态，放大 3 倍（约 0.9 m 长，便于在 60 m 长的线体上辨认，覆盖层注明「工件放大 3× 示意」），每帧通过 setMatrixAt 更新位置与朝向（长边沿传送带方向）并 instanceMatrix.needsUpdate = true。加载完成前先用小 Box 表示工件，onLoad 后替换；加载失败保持 Box 并在覆盖层小字提示。在制品数量随模式变化时只改变可见实例数。
C. compute(mode) 假设（写入 P 并可改）：班次可用时间 = 8 h × 3600 × 班次数，OEE 假设 0.85（模式 ③ 0.88）；节拍 takt = 可用时间 × OEE / 目标产量；各工位标准作业时间（s，写入 P）：st01 22、st02 34、st03 26（机器人）、st04 28、st05 30、st06 32、st07 26（机器人）、st08 24（AOI）、st09 180 / 并行台数、st10 7200 / 老化台位数、st11 28、st12 30、st13 24（协作机器人）、st14 12；模式 ③ 中 st04 22、st06 24、st12 20；有效工位时间 = 作业时间 / 并行数；瓶颈 = 有效时间最大的工位；线平衡率 = Σ有效时间 / (14 × 最大有效时间)；在制品 WIP ≈ Σ有效时间 / takt（Little 定律，含老化架上的在制品）；操作员人数：人工工位每站 1 人（st02、st05、st06、st11 各 2 人），机器人 / AOI 工位 0.5 人巡检，测试与老化各 2 人，AGV 0 人；模式 ③ 减少的人工按上表；人均小时产出 = 目标产量 / (班次小时 × 操作员人数)。
D. METRICS 固定 6 项、按此顺序与 label：节拍时间(s/台)、线平衡率(%)、瓶颈工位、在制品数量(台)、操作员人数(人)、OEE 估算(%)；瓶颈工位的 value 写「⑨ 测试」这类工位名；切换模式后 window.__metrics 同步更新；note 注明「以页面实时计算为准」。
E. 阶段：上料（D 壳与主板从线边仓由 AGV 配送上线）→ 装配（②–⑦ 装配与自动锁螺钉）→ 测试老化（AOI、功能测试与 Run-in）→ 包装出货（终检、贴标、装箱码垛、下线）。覆盖层用一行标出当前模式的瓶颈工位并把它高亮为 #b11f4b。SUMMARY 中说明这是系统级示意与节拍估算（非离散事件仿真），部件几何为示意比例。""",
    },
    {
        "id": "nb_packing",
        "industry": "notebook",
        "icon": "📦",
        "color": "green",
        "title": "包装与集装箱装载优化",
        "title_en": "Packaging & Container-Loading Optimisation",
        "subtitle": "彩盒 → 外箱 → 托盘 → 40 尺高柜四级装载：三种方案切换，利用率、每柜台数、包装材料与海运碳排估算",
        "subtitle_en": "Retail box → master carton → pallet → 40' HC container: three schemes, utilisation, units per container, packaging mass and sea-freight CO₂ estimate",
        "pain": "装柜方案靠人工试摆 · 包装减量算不清收益",
        "pain_en": "Container plans are trial-and-error · packaging reductions are hard to quantify",
        "prompt": "为一款 14 英寸笔记本设计包装与出货装载方案并做 3D 可视化：单机彩盒 355 × 245 × 62 mm（含整机、适配器与纸浆模塑缓冲结构，毛重 2.4 kg）；外箱装 5 台，尺寸由彩盒排布决定并每边留 10 mm 间隙，瓦楞纸板厚 5 mm、面密度 0.75 kg/m²；托盘 1,200 × 1,000 × 150 mm，货物最大堆高 1,800 mm（含托盘），单托限重 1,000 kg；40 尺高柜内尺寸 12,032 × 2,352 × 2,698 mm。请构建从彩盒 → 外箱 → 托盘 → 集装箱的四级装载 3D 模型（外箱与托盘用 InstancedMesh，可用按钮在「单箱剖视 / 单托盘 / 整柜」三个层级之间切换视角），并实现三个方案可切换：① 标准托盘装柜；② 不用托盘直接码放（地板装载，堆高上限 2,600 mm）；③ 彩盒改为 335 × 235 × 58 mm 的紧凑包装（缓冲改为竹浆纤维一体成型，彩盒毛重 2.25 kg）。计算每个方案的：每箱台数、每托盘台数、每柜总台数、集装箱容积利用率、每台包装材料质量、每台海运碳排放估算（按 40 尺柜上海 → 鹿特丹全程约 1,200 kg CO₂e 均摊）。",
        "prompt_en": "Design the packaging and outbound loading scheme for a 14-inch notebook and visualise it in 3D: retail box 355 × 245 × 62 mm (notebook, adapter and moulded-pulp cushions, gross 2.4 kg); master carton of 5 units sized by the box arrangement with 10 mm clearance per side, corrugated board 5 mm thick at 0.75 kg/m²; pallet 1,200 × 1,000 × 150 mm, maximum stack height 1,800 mm including the pallet, 1,000 kg per pallet; 40' high-cube interior 12,032 × 2,352 × 2,698 mm. Build the four-level loading model retail box → carton → pallet → container (cartons and pallets as InstancedMesh, with buttons to jump between “carton cut-away / single pallet / full container” views) and implement three switchable schemes: ① standard palletised loading; ② floor loading without pallets (stack limit 2,600 mm); ③ a compact 335 × 235 × 58 mm retail box (one-piece bamboo-fibre cushion, gross 2.25 kg). Compute per scheme: units per carton, units per pallet, units per container, container volume utilisation, packaging material mass per unit and sea-freight CO₂ per unit (a 40' container Shanghai → Rotterdam ≈ 1,200 kg CO₂e, allocated per unit).",
        "chips": [
            "外箱改为 4 台 / 箱并换成 20 尺柜，比较每柜台数、利用率与每台碳排",
            "彩盒厚度压到 52 mm（去掉适配器改随机附赠电子券），每柜能多装多少台？",
            "托盘换成 1,140 × 1,140 mm 的海运托盘并允许双层堆码，比较利用率与破损风险",
        ],
        "chips_en": [
            "Switch to 4 units per carton and a 20' container; compare units per container, utilisation and CO₂ per unit",
            "Slim the retail box to 52 mm (adapter shipped separately): how many more units fit per container?",
            "Use 1,140 × 1,140 mm sea pallets with double stacking; compare utilisation and damage risk",
        ],
        "metrics_labels_en": ["Units per carton", "Units per pallet", "Units per container",
                              "Container volume utilisation (%)", "Packaging mass per unit (g)", "Sea-freight CO₂ per unit (kg CO₂e)"],
        "system_extra": """本场景是「装载优化」：几何全部是长方体的嵌套排布，重点是排布算法透明、三个方案的数字可对比。
A. 部件：retail_box（彩盒，#f5f5f4 带 #b11f4b 细边线 EdgesGeometry）、carton（外箱，瓦楞纸色 #c8a165，InstancedMesh）、pallet（托盘，木色 #a16207，InstancedMesh，含 3 根垫木）、container（集装箱，半透明 Box opacity 0.12 + 线框，门端朝 +X）。用按钮在三个层级之间切换视角：「单箱剖视」显示一只外箱剖开露出 5 只彩盒的排布，其中最外侧一只彩盒画成打开状态、露出里面的真实笔记本（见 A2）；「单托盘」显示一托盘上外箱的层数与每层排布（可用不同颜色区分交错层）；「整柜」显示所有托盘 / 外箱在柜内的排布，并把未利用空间用浅红色半透明 Box 标出。
A2. 真实笔记本（本场景例外：允许加载本站 GLB 素材，呈现方式按末尾【笔记本素材呈现规范】）：加载 /static/assets/notebook/laptop14_closed.glb（合盖，约 301 × 14.5 × 220 mm），按 N3 赋铂金铝材质，放进「单箱剖视」中那只打开的彩盒里（彩盒内尺寸 355 × 245 × 62，笔记本居中、四周用浅色 Box 表示纸浆模塑缓冲块）；只在单箱剖视层级可见。
B. 排布算法（写入 JS 函数，透明可解释）：外箱内 5 只彩盒按最短边堆叠（5 × 62 mm 方向），外箱外尺寸 = 彩盒排布 + 2 × 10 mm 间隙 + 2 × 5 mm 板厚；托盘层排布：在 1,200 × 1,000 平面上枚举外箱两种水平朝向的 floor(L/l) × floor(W/w) 组合取最大值，层数 = floor((1,800 − 150) / 外箱高)，同时检查单托限重；集装箱排布：托盘两种朝向枚举 floor(12,032/1,200) × floor(2,352/1,000) 等组合取最大值，托盘不堆码（方案 ①）；方案 ② 外箱直接在柜内三维枚举 6 种朝向取最大值，堆高 ≤ 2,600 mm；方案 ③ 用紧凑彩盒重复以上计算。容积利用率 = 彩盒总体积 / 集装箱内容积。
C. compute(scheme) 假设（写入 P 并可改）：瓦楞纸板 0.75 kg/m²（外箱表面积 × 面密度 / 5 台）、纸浆模塑缓冲 180 g/台（方案 ③ 竹浆纤维 120 g/台）、彩盒本体 260 g（方案 ③ 230 g）、托盘 22 kg 均摊到该托盘台数（方案 ② 为 0）；海运碳排 = 1,200 kg CO₂e / 每柜台数。
D. METRICS 固定 6 项、按此顺序与 label：每箱台数、每托盘台数、每柜总台数、集装箱容积利用率(%)、每台包装材料质量(g)、每台海运碳排放(kg CO₂e)；方案 ② 的每托盘台数写「—（地板装载）」；切换方案后 window.__metrics 同步更新；note 注明假设。
E. 覆盖层显示当前方案名称、每柜台数与相对方案 ① 的增量（如「+6.4%」），并显示三个层级切换按钮与方案按钮。SUMMARY 中说明排布为规则排布（非启发式装箱求解器），未考虑重量分布与绑扎。""",
    },
]


LANGS = ("zh", "en")

# Appended when the UI runs in English: every human-readable string the model writes switches language,
# while the technical contract (sentinels, import map, P object, window.__metrics, SI units) is unchanged.
ENGLISH_OUTPUT_RULES = """【输出语言 —— English output required / 本次会话界面语言为英文】
The user interface is currently in English. Override every language instruction above as follows:
1. SUMMARY: 60–140 English words, plain text, professional engineering register.
2. METRICS: "label" and "note" in English (keep units in SI symbols exactly as before, e.g. kg, mm, m², kPa, W/(m²·K)); numbers unchanged.
3. SUGGESTIONS: exactly 3 short English sentences (≤ 18 words each) the user can click to send.
4. Inside the HTML: the overlay title, parameter list, legend, table headers, button captions (e.g. "Section view / Full view", "Exploded view", "Auto-rotate", "AI schedule / Veteran method", "Temperature map / Material view"), axis labels drawn with Sprites, error messages and code comments must all be in English.
5. If a scenario rule above fixes the METRICS labels (fixed order / wording), keep the same order and meaning but translate the labels into English; window.__metrics must use the same English labels.
6. Keep the user's dimensions, materials and assumptions exactly; do not translate proper nouns such as three.js, CadQuery, STEP; never mention a company or brand name.
7. System scenes: window.__hotspots (label / part / note), window.__stages (title / text), mode-button captions and the stage text shown in the overlay must be in English.
8. Part names are listed in the host outliner: every Mesh / Group .name and model.name must be a short English name."""


def public_scenarios() -> list[dict]:
    """Scenario cards as exposed to the browser (system-side prompt addenda stripped); every card carries its industry."""
    return [{**{k: v for k, v in s.items() if k not in ("system_extra", "metrics_labels_en")}, "industry": industry_of(s)}
            for s in SCENARIOS]


def industry_of(scenario: dict) -> str:
    return scenario.get("industry") or DEFAULT_INDUSTRY


def public_industries() -> list[dict]:
    """Industry groups for the UI (persona text stays server-side); ordered as declared, with card counts."""
    out = []
    for ind_id, ind in INDUSTRIES.items():
        count = sum(1 for s in SCENARIOS if industry_of(s) == ind_id)
        out.append({**{k: v for k, v in ind.items() if k != "persona"}, "count": count})
    return out


def normalize_lang(lang: str | None) -> str:
    """'zh' unless the caller explicitly asks for English ('en', 'en-US', ...)."""
    return "en" if (lang or "").strip().lower().startswith("en") else "zh"


def system_prompt_for(scenario_id: str | None, lang: str | None = "zh") -> str:
    """Global system prompt (persona chosen by the scenario's industry) + (system-scene rules for kind == "system")
    + the scenario's specialised rules (if any) + the English-output addendum (if lang == 'en')."""
    scenario = next((s for s in SCENARIOS if s["id"] == scenario_id), None) if scenario_id else None
    persona = INDUSTRIES[industry_of(scenario) if scenario else DEFAULT_INDUSTRY]["persona"]
    prompt = SYSTEM_PROMPT.replace(PERSONA_TOKEN, persona)
    if scenario:
        s = scenario
        if s.get("kind") == "system":
            prompt = f"{prompt}\n\n【系统级场景通用规范 —— 回路 / 工况 / 部件热点 / 运行阶段】\n{SYSTEM_SCENE_RULES}"
        if s.get("system_extra"):
            prompt = f"{prompt}\n\n【场景专项规范 —— {s['title']}】\n{s['system_extra']}"
            if normalize_lang(lang) == "en" and s.get("metrics_labels_en"):
                prompt += "\nEnglish METRICS labels for this scenario (same order): " + " | ".join(s["metrics_labels_en"])
        if industry_of(s) == "notebook":
            prompt = f"{prompt}\n\n【笔记本素材呈现规范 —— 让机身像一台高端轻薄本】\n{NOTEBOOK_ASSET_RULES}"
    if normalize_lang(lang) == "en":
        prompt = f"{prompt}\n\n{ENGLISH_OUTPUT_RULES}"
    return prompt
