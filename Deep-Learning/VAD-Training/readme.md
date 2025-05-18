# VAD :**向量化场景表征**在多传感器 3D 感知中的落地

Vectorized Scene Representation for Efficient Autonomous Driving

自动驾驶 3D 感知技术这五年经历两次拐点：

1. 从 **单传感器**（纯相机或纯 LiDAR）走向 **多传感器融合**；
2. 从 **逐帧静态** 走向 **时序记忆**。



## 1.三大流派的核心理念

### 视觉派（Tesla Vision 的故事）

2016 年之前，视觉感知在自动驾驶里是配角：识别红绿灯、车道线即可。
2017 年后，YOLOv3 与 FPN 在端侧跑到 60 FPS，视觉派开始喊出“相机胜过激光”的口号。
2021 年 4 月，Tesla 把毫米波雷达移出 Model 3 & Y，并提出 **“全视觉 BEV”**：

1. 每帧 8 路相机图像经 CNN/Transformer 提特征；
2. 依靠单目深度估计把像素投影到鸟瞰平面（BEV）；
3. Transformer 在 BEV 上一次性推理 3D boxes、语义栅格、速度向量；

如此一来，感知、规划甚至部分预测都在 BEV 平面完成，整个软件栈**坐标系统一、信息密度高**。
不过，纯视觉在夜间、雨雾或远距深度衰减明显；深度网络再强，也无法“凭空”补出没有光子的场景。

### LiDAR 派（“我只相信毫米级深度”）

严格来说，LiDAR 的英文全称是 Light Detection And Ranging，它利用激光（光学波段）测量目标距离，因此更准确的中文叫法是“激光测距 / 激光探测”。

不过在中文行业语境里，人们常把 LiDAR 译作“激光雷达”——这里的“雷达”并非指传统 **RADAR**（Radio Detection And Ranging，采用无线电波），而是一种约定俗成的称呼，意在强调其与“毫米波雷达、超声波雷达”同属**主动测距**传感器家族。

| 传感器 | 英文全称                    | 工作波段                 | 常见中文叫法         |
| ------ | --------------------------- | ------------------------ | -------------------- |
| RADAR  | Radio Detection And Ranging | 无线电（毫米波、厘米波） | 毫米波雷达、车载雷达 |
| LiDAR  | Light Detection And Ranging | 激光（近红外、可见光）   | 激光雷达、激光测距仪 |

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/VAD-Training/images/1.png)

因此：

- LiDAR ≠ 传统意义上的雷达（电磁波），它用的是激光束；
- 在自动驾驶和机器人领域，“激光雷达”这个名称已被广泛接受，实质仍是 Light Detection And Ranging。

二者都属于“主动测距”：自己发射信号，再接收反射信号，根据“来回时间”算距离。不同之处是 **RADAR 发无线电波，LiDAR 发激光脉冲**。

### “一束光怎么变成三维坐标？”

1. **发送脉冲**
   内部激光器（通常 1550 nm 安全波段）发出一个极短脉冲，宽度纳秒级。

2. **光飞出去又飞回来**
   脉冲撞到障碍物表面后散射，极少量光子被传感器接收到。

3. **计时**
   电子时钟测量“发射 → 接收”所用时间 Δt，光速 c≈3×10⁸ m/s；
   距离 d = (c × Δt) / 2。除以 2 是因为光要走去和返回两段路。

4. **扫描**
   为了获得整幅场景，LiDAR 需要不断改变脉冲方向。有两种主流方式：

   - **机械旋转**：激光发射器和镜片整套转一圈（Velodyne 传统桶型）。
   - **MEMS/相控阵**：固定套壳，用微镜或光相移陣列快速摆动束向。

5. **同步测角**
   旋转部件含编码器，记录当前水平角度 θ、垂直角度 φ。
   于是就得到三维坐标：

   ```
   x = d · cosφ · cosθ
   y = d · cosφ · sinθ
   z = d · sinφ
   ```

   

   每发一个脉冲得到一个 (x,y,z,反射强度) 点；一帧数万个点，就是 **点云**。

   ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/VAD-Training/images/2.png)

### 为什么自动驾驶喜欢用 LiDAR

- **深度精度高**：2 cm 级误差，不随光照变化。
- **密度可控**：32-beam、64-beam、128-beam……光束越多，点云越稠密。
- **射线直观**：直接提供三维几何，后端算法更容易估算体积、轨迹。
- **缺点**：贵、在雨雪强雾时有效距离缩短；对颜色和纹理几乎无感知。
  因此融入相机就能“既看得真又看得清”。



Waymo 的第一代无人车装备 64-beam HDL64 激光，后来上 128-beam 花瓣盘，单台激光器成本曾高达 7.5 万美元。
LiDAR 模型大致分三类：

- **PointNet/PointPillars**：直接把 x,y,z,r 四维特征堆入柱体；
- **VoxelNet / SECOND**：0.1–0.2 m 的体素化，3D 卷积提局部语义；
- **SparseConv**：Sub-manifold 卷积，稀疏哈希表显著加速。

3D 检测指标上，单 LiDAR 至今仍优于同尺寸纯视觉；
但缺少颜色、纹理、上下文，对 traffic-sign、work-zone 识别力弱。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/VAD-Training/images/3.png)

### 融合派（VAD 代表）

融合派目标：“取相机所长，补激光之短”，分三档：

| 融合时机 | 代表                | 说明                                    |
| -------- | ------------------- | --------------------------------------- |
| 像素级   | UVTR                | LiDAR 深度投影到每个像素后拼接特征      |
| BEV级    | BEVFusion / **VAD** | 各自产 BEV，再 concat / Deformable Attn |
| 检测框级 | MV3D                | 两套检测→框级融合→NMS                   |

VAD 采用 **BEV 级融合 + 时序 ConvGRU**，最后通过 **Vectorization Head** 将密集的栅格或检测框数据转换成**折线向量**，这些向量可以直接用于规划决策。

具体而言，VAD 的关键优势可以分成两大层次：

------

## ⚙️ 一、融合层面（传感器数据整合）：

同时使用了「多摄像头」和「LiDAR 激光雷达」的信息进行融合：

- **摄像头数据**：通过深度估计、视角变换，构建出俯视视角（BEV）特征图，携带丰富的颜色、纹理信息，以及车道线等语义细节；
- **LiDAR 数据**：测距点云精准可靠（以厘米级精度记录物体距离与轮廓），经过体素化（Voxelization）或 SparseConv 处理后，也将信息嵌入至同一BEV网格。

接下来，通过 **Deformable Cross-Attention** 在 BEV 平面对两者精准匹配（几何对齐）。从而，系统获得：

- ✅ 远近均精准的语义密集特征；
- ✅ 稳定可靠的空间几何表示。

------

## 📌 二、规划层面（从密集栅格到向量化表示）：

融合后的密集栅格网格虽信息详尽，但数据量庞大且难以高效利用，VAD 随后进一步将这些数据**向量化**为折线表示：

- 静态道路数据（地图） → 道路边界折线，车道线折线；
- 周边动态车辆预测信息 → 车辆未来行驶折线；
- 自车规划的轨迹数据 → 自车未来行驶轨迹折线；

并明确建立三条清晰的**安全约束**：

- 防碰撞（与车辆之间留足距离）
- 防越界（车不离开安全车道边界）
- 方向一致约束（确保运动方向与车道、道路结构的一致性）

这种合理的向量化过程，带来了明显的优势：

- ✅ 数据尺寸从数十MB稠密栅格，大幅压缩成几十KB折线；
- ✅ 推理速度大幅提升（2~9 倍）；
- ✅ 输出结果明确易懂，每个折线都与现实世界清晰对应（容易解释、调试、维护）。

**需要特别提出的是**：

向量化**并非直接**从相机图像或LiDAR点云转换到折线，而是先经过融合成精细的BEV网格之后，再一步清晰地表示成具体实例的折线或轨迹。这种两步策略确保精确、清晰且高效易用。

------

## 📐 VAD向量化具体要素与实例举例：

| 被向量化的元素                  | 数据来源               | 为什么向量化                               | 实例举例（折线表示）                               |
| ------------------------------- | ---------------------- | ------------------------------------------ | -------------------------------------------------- |
| ① 静态道路几何                  | BEV 网格 + Map Query   | 原始栅格巨大繁琐，且需要清晰的车道实例表示 | `[(-10,0),(0,0),(10,0)]` 表示一条车道线            |
| ② 动态周边车辆未来运动轨迹      | BEV 网格 + Agent Query | 用折线清晰直接表示“车辆未来3秒去哪”        | 一条轨迹用6个预测点表示：`[(2,5),(4,7),(6,9)...] ` |
| ③ 自车（Ego车）规划轨迹         | Planning Transformer   | 折线便于控制器追踪及距离约束               | 自车轨迹6个Waypoint: `[(0,0),(1,0),(2,0)...]`      |
| ④ 安全约束边界区域（碰撞/越界） | 上述折线间的相互关系   | 折线格式方便快速计算“距离或角度约束”       | 横向安全边界1.5m、纵向安全距离3 m                  |

------

## ✨ 向量化前后数据量对比（直观表示）：

| 数据形式          | 数据表示形式                                                 | 数据大小（内存占用） | 易解释性 | 效率与速度    |
| ----------------- | ------------------------------------------------------------ | -------------------- | -------- | ------------- |
| 传统密集栅格表示  | BEV feature (256×200×200 float)等                            | 数十 MB              | 难解释   | 较慢          |
| ✅ **VAD向量化后** | ① Map vectors (100条×20点×2坐标)<br>② Motion Vectors (15车×6点×2 float)<br>③ Ego Vector (6个点×2 float) | <25 KB（极大压缩）   | 易解释   | 速度提升2–9倍 |

**完整明确的数据举例**：

```
Map Vectors     100条×20点×2坐标点(float)
Motion Vectors  15辆车×6点×2坐标点(float)
Ego Vector      自车轨迹6点×2坐标点(float)
```



------

## 📋 总结一句话（VAD 核心思想）：

VAD 真正的创新之处并不是简单旧式数据叠加，而是采用两个阶段清晰有效的流程：

```
摄像头多视角图像 + LiDAR点云
        ↓ 融合为BEV精确栅格表示（密集栅格形式）
        ↓ 进一步精简为折线“向量表示”
           • 道路轮廓
           • 动态车辆轨迹
           • 自车运动规划轨迹
        ↓ 使用规划器直接规划，并施加显式的3条安全约束（防碰撞、防越界、方向约束）
```



------

## 🚩 总结 VAD 核心创新与价值：

VAD 真正的“向量化”，并非直接处理原始图片或LiDAR点，而是：

从融合后的 BEV 栅格特征 ❌ → 提取清晰明确折线 ✔️ （体现道路、交通参与者和自车轨迹），再利用这些明确且精炼的折线，指导自动驾驶车辆后续的路径规划与安全约束计算。

这种方法的明确性与高效性，构成了VAD相较传统BEV密集栅格方法最显著的本质创新，也是其效率与性能提升的根本原因所在。

## VAD 总体工作流程

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/VAD-Training/images/5.png)

1. **左侧：感知 Backbone**
   - 多视角相机图片先进入 BEV Encoder（ResNet+Lift-Splat 已在前文解释）。
   - 输出一张融合后的 BEV 特征图（黄色网格）。
2. **中间：Vectorized Scene Learning**
   - **Map Query**（粉色小方块）喂给 *Vectorized Map Transformer*，把车道线、路沿等 HD 地图元素提炼成折线 *Map Vector*。
   - **Agent Query**（蓝色小方块）送入 *Vectorized Motion Transformer*，得到周围车辆未来 3 秒的多模态折线 *Motion Vector*。
   - 这两路输出都会把自身特征“回写”到查询里（图中 *Updated Map/Agent Query*），让后面的规划能直接使用。
3. **右侧：Planning Transformer（推理阶段）**
   - **Ego Query**（绿色）相当于“自车代表”，会同时读 *Agent* 和 *Map* 的 Key/Value（图中 k,v）来感知环境，最终解码出 *Ego Vector* —— 自车 3 秒、6 个 Waypoint 的折线。
   - 驾驶员意图由高层的文字指令输入（例：“Turn Left”）；实时车速、方向盘角等 **Ego Status** 信息也可附加给规划。
4. **最右：Vectorized Planning Constraints（仅在训练阶段生效）**
   - 三条规则（下一张图详解）会在训练时直接作用于折线，替代手写 Heuristic。

**时间线**：感知 + 场景向量化大约 50 ms；规划 Transformer 仅 3 ms 即可输出 Ego Vector。

## 三条向量级安全约束

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/VAD-Training/images/5.png)

1. **Ego-Agent Collision Constraint**
   - 黄色箭头给了横向（Lateral）和纵向（Longitudinal）两条安全线。
   - 当自车（蓝）折线与红车折线距离 < 阈值时，损失函数会线性增加，网络被迫调整规划点。
2. **Ego-Boundary Overstepping Constraint**
   - 若自车折线距车道实体边界 < 1 m，立即惩罚，使轨迹往内侧推。
   - 这样即便地图栅格很稀疏，也不会出现“轮胎擦路肩”的问题。
3. **Ego-Lane Directional Constraint**
   - 把最近车道中心线（黄箭头）当作航向参考。
   - 若自车折线整体方向与其夹角 > 10°，就加角度罚，防止逆行或走 S 线。

三条约束全是“实例级”的，可微分、无需后处理。这就是 VAD planning 坚持向量化的最大收益点。



## 真实跑车画面 & 折线输出

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/VAD-Training/images/6.png)

每一行展示 **六路原始相机画面 + BEV 折线图**，帮助你把“看到什么”与“VAD 输出什么”对齐。

### 第 1 行：直行通过十字路口

- BEV

   

  右图中：

  - 红/橙/黄 Motion 折线表示不同车辆 0 – 3 秒位移，颜色越浅代表越靠近当前时刻。
  - 绿色 Plan 折线是自车轨迹，笔直穿过路口。

### 第 2 行：左转主干道

- 可以看到蓝色粗折线路径先压到路口中心再左转，完美贴合道路几何。
- BEV 图中灰色细线是向量化车道边界；Planning 折线与其保持合理车道宽。

### 第 3 行：礼让行人

- 前视图里有两名行人刚踏入斑马线。
- BEV 里行人用短黄色箭头表示；自车轨迹被 Planner 向右微移并减速（曲线前段弯成 S 形），以保证碰撞距离满足上图 2-1 的规则。

整个过程无需稠密栅格或手写规则，**端到端就能把“看见 → 预测 → 规避”连成一气**，并且折线画面让工程师一眼就能定位是不是规划太紧或方向不正。

------

### 小结

- **图 1** 给你总览了 VAD 流程：相机+LiDAR → BEV 特征 → 向量化 → 规划。
- **图 2** 展示训练期如何用 3 条直观且可微的安全规则“约束”折线输出，让模型学会避车、压线、逆行都要被惩罚。
- **图 3** 告诉你模型跑在真实街景的效果：折线简洁、动作合理、人能看懂。

------

## 2 技术术语速查表

### 2.1 传感器与数据形态

| 术语               | 全称                                    | 通俗解释                                                     |
| ------------------ | --------------------------------------- | ------------------------------------------------------------ |
| Camera             | 摄像头                                  | 和手机摄像头一样，输出 2D 彩色图片（RGB 像素阵列）。         |
| LiDAR              | Light Detection And Ranging（激光雷达） | 通过高速旋转的激光束扫描环境，测量“光飞出去再弹回”所花时间，得到到物体表面的 **真实距离**。输出往往是一帧几万个 XYZ 点的集合。 |
| 点云 (Point Cloud) | ——                                      | LiDAR 原始输出。可把它想成“立体散点图”：一个点 = (x, y, z, 反射强度)。 |
| BEV                | Bird-Eye-View（鸟瞰视图）               | 把 3D 世界投影到平面俯视图，好像无人机正上方往下看。方便 2D 卷积和规划算法使用。 |
| 体素 (Voxel)       | Volumetric Pixel                        | 三维版的像素。把空间切成一格格小立方体，用来存 LiDAR 点或特征。 |

### 2.2 神经网络模块

| 模块                       | 全称 / 组成                  | 用一句人话解释                                               |
| -------------------------- | ---------------------------- | ------------------------------------------------------------ |
| CNN                        | Convolutional Neural Network | 卷积网络，擅长处理“像素网格”这类邻近元素高度相关的数据。     |
| ResNet-50                  | Residual Network, 50 层      | 一种经典 CNN，特点是用“残差连接”让 50 层也能学得稳。VAD 把它当图像特征提取器。 |
| SparseConv                 | Sparse Convolution           | “只在有点云的体素上做卷积”，跳过空体素，显著加速 3D 卷积。   |
| Transformer Self-Attention | ——                           | 每个位置自己跟自己对话，捕捉长距离依赖。VAD 的 BEV Encoder 可选用它。 |
| Deformable Attention       | “可变形注意力”               | 不是固定看网格正中央，而是学习“我该往哪里看”来提取最相关信息。VAD 用它把相机 BEV 和 LiDAR BEV 对齐。 |
| GRU                        | Gated Recurrent Unit         | 一种比 LSTM 更轻量的循环网络，用门控机制记忆时间序列。       |
| ConvGRU                    | Convolutional GRU            | 把 GRU 里的全连接换成卷积，更适合处理图像/BEV 这种空间数据。VAD 用它来记住过去 4 帧 BEV。 |

### 2.3 评价指标

| 缩写  | 含义                       | 如何读数                                                    |
| ----- | -------------------------- | ----------------------------------------------------------- |
| mAP   | mean Average Precision     | 检测框越准，mAP 越高（0–100%）。                            |
| NDS   | NuScenes Detection Score   | nuScenes 官方综合分，考虑位置、尺寸、朝向。56 分≈表现不错。 |
| IoU3D | 3D Intersection-over-Union | 3D 框和真值重叠体积 / 联合体积。1 表示完美重合。            |

------

## 3 LiDAR 原理

1. **发光**
   激光器（1550 nm，眼安全）发出纳秒级脉冲。

2. **飞行**
   光碰物体反射，少量光子返回探测器。

3. **计时**
   Δt·c/2 = 距离 d；c = 3×10⁸ m/s，除 2 是往返。

4. **扫描**

   - 机械旋转：Velodyne 桶。
   - MEMS/相控阵：固态振镜或光相移阵列。

5. **加角度**
   读编码器得 θ、φ，三角换算

   ```
   x = d·cosφ·cosθ
   y = d·cosφ·sinθ
   z = d·sinφ
   ```

   

   得到一帧点云。

**为什么爱用 LiDAR**

- 误差 <2 cm；
- 夜间/隧道无惧；
- 直接给 3D 几何；
- 缺点：贵、雨雾衰减、无颜色。

## 4 从像素到 3D：两个完整例子

### 4.1 例子 1：右侧并线轿车（单帧静态）

**已知**

- 像素 (u,v) = (920, 500)
- 相机内参 fx = fy = 820，cx = 800，cy = 450
- 深度网络预测该像素深度 d = 20 m
- 相机安装位移 (0, 0, 1.5 m)

**步骤**

1. 还原到相机坐标：

   ```
   X_cam = (u - cx) * d / fx = 2.9 m
   Y_cam = (v - cy) * d / fy = 1.2 m
   Z_cam = d = 20 m
   ```

   

2. 外参变换到车体坐标：

   ```
   X_car = 2.9,  Y_car = 1.2,  Z_car = 18.5
   ```

   

3. BEV 网格分辨率 0.2 m：

   ```
   i = round(X/0.2)=15,  j = round(Z/0.2)=92
   ```

   

4. 同步 LiDAR。若点云中出现 (2.95, 1.1, 18.4)，也会落到 (15, 92)。
   图像、LiDAR 特征现在能在同一 BEV 单元做加权融合。

### 4.2 例子 2：连续 4 帧遮挡行人（时序）

帧 t−3 到 t：车辆经过公交车，行人被遮挡 → 只有第一帧可见。
ConvGRU 将历史 BEV (H_{t−3} … H_{t−1}) 记忆成 H_t，纵向插值速度 1.5 m/s。
当当前帧几乎无行人像素/点云时，H_t 仍可输出预测框，避免 Planner 直接加速撞上行人。

------

## 5 十大可学习子模块——结构与张量形状

下表给出每层输入/输出形状（B=batch, N_cam=6, C=256, H=W=200）。

| #    | 模块                   | 输入 → 输出                                                  | 主要层级 / 备注                             |
| ---- | ---------------------- | ------------------------------------------------------------ | ------------------------------------------- |
| 1    | ResNet-50              | 6×3×900×1600 → 多尺度{C3 1/8, C4 1/16, C5 1/32}              | conv1-5；参数 23 M                          |
| 2    | FPN / 1×1              | 上述多尺度 → 6×C×H×W (1/8)                                   | lateral 1×1 + 上采样                        |
| 3    | DepthHead              | C×H×W → 1×H×W (连续) 或 80×H×W (离散 bin)                    | 3×3 Conv + ReLU + Up                        |
| 4    | SparseConv Enc         | 点云稀疏张量 → C×H×W                                         | SubMConv3D×3 + ResBlk；voxel 0.1 m          |
| 5    | X-Attn                 | Img-BEV + LiDAR-BEV → Fused                                  | Deformable Attn，offset×8                   |
| 6    | BEV Encoder            | Fused → C×H×W                                                | 6×(Conv 3×3 + BN + ReLU)                    |
| 7    | ConvGRU                | {H_{t-k}…H_t} → H'_t                                         | 门卷积 3×3，记忆 4 帧                       |
| 8    | 3D Det Head            | H'_t → Heatmap 10× + Box 8×                                  | Center-based                                |
| 9    | BEV Seg Head           | H'_t → Seg 10×                                               | 3×3 Conv×4                                  |
| 10   | **Vectorization Head** | H'_t + Query → Map Vector Nm×Np×2、Agent Motion Na×Tf×2、Ego Traj Tf×2 | Map/Agent/Ego Query + Two-stage Transformer |

张量形状示例（B=1）：

- Img-BEV shape = (6, 256, 200, 200)
- LiDAR-BEV shape = (256, 200, 200)
- Fused-BEV shape = (256, 200, 200)
- Map Query shape = (100, 256)
- Map Vector 输出 (100, 20, 2)

------

### 5.1 Vectorization Head 详细流程

1. **Map Query → BEV 特征**
   - Deformable Attn(Q_map, K=fused BEV, V=fused BEV)
   - MLP 将输出点坐标回归为 20 个折线顶点。
2. **Agent Query**
   - 初始 Query 长度 300；与 BEV Attn 得到特征；
   - Motion Decoder 预测 3 条多模态轨迹，每条 Tf=6 (3 s)。
3. **Ego Query + 交互**
   - EgoQuery 与 Agent/Map Query 双层交互 → 富含环境语义。
   - PlanningHead：MLP(fc512-fc256-fc12) → 6 个未来坐标。
4. **三大规划约束**
   - 碰撞：若 ego-agent 距离 < 1.5 m (横) & 3 m (纵) → 线性罚。
   - 越界：距 drivable boundary < 1 m → 线性罚。
   - 方向：ego 向量与最近车道向量夹角 >20° → 角度罚。

------

### 5.2 损失函数与超参表

| Loss                      | λ           | 备注           |
| ------------------------- | ----------- | -------------- |
| L_map (Manhattan + Focal) | 1.0         | 向量化地图     |
| L_motion (l1 + Focal)     | 1.0         | Agent Motion   |
| L_imi (Imitation)         | 1.0         | Ego vs GT      |
| L_col (碰撞)              | 5.0         | 取横纵最小距离 |
| L_bd (越界)               | 5.0         | δ_bd=1 m       |
| L_dir (方向)              | 2.0         | δ_dir=2 m      |
| L_total                   | Σ λ_i · L_i |                |

优化器 AdamW(lr 2e-4, wd 0.01)；Cosine Annealing 60 epoch；warm-up 1 000 iter。

------

## 6 数据集与标注差异

### 6.1 nuScenes 核心字段

```
{
  "translation": [35.4, -18.2, 1.01],   // xyz (m)
  "size": [4.21, 1.82, 1.55],           // l w h
  "rotation": [0.01, 0.00, 0.31, 0.95], // quat w x y z
  "velocity": [0.5, 0.1, 0],
  "name": "car",
  "attribute_name": "vehicle.moving"
}
```



- yaw = quaternion→欧拉需注意顺序；
- Z 原点在车轴下 0.73 m，需要补 0.73 才是地面高度 0。

### 6.2 Lyft-Level5 转换

脚本片段：

```
def lyft2nusc(box_lyft):
    # lyft yaw 0° 指 x-forward，nusc yaw 0° 指 y-forward
    swap = rot_z(pi/2)
    center = box_lyft[:3]
    size = box_lyft[3:6]
    quat = swap.multiply(Quaternion(box_lyft[6:10]))
    return nusc_box(center, size, quat)
```



### 6.3 Waymo & KITTI 差别速览

| 数据  | yaw 0° 方向 | z 原点 | 帧率  | 建议                     |
| ----- | ----------- | ------ | ----- | ------------------------ |
| KITTI | z-forward   | 车顶   | 10 Hz | 需旋转 +1.57 rad；补 z   |
| Waymo | x-forward   | 地面   | 20 Hz | 与 nuScenes 略差，易兼容 |



### Refer to：

*https://arxiv.org/pdf/2303.12077*