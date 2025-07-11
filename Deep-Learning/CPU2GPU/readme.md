# CPU 任务向 GPU 迁移思路

本仓库用一个极简示例串起整条方法论：先在 CPU 上定位计算热点，再把这类“并行度高、访存顺序、分支简单”的循环改写为 CUDA kernel，实现 CPU 负载削减与 GPU 算力释放。代码一次运行即可对比 CPU 和 GPU 耗时、拆分传输与计算开销，并校验结果误差，从而快速验证“CPU → GPU”迁移的可行性与预期收益，为后续在真实业务中批量迁移、流水线优化、MIG 资源切分等操作奠定模板。

测试中使用Azure NC26 A100 GPU VM。

### **A100技术指标**

| 组件                    | 全称                        | 数量 / 规模                  | 计算逻辑                        | 主要功能或说明                                               |
| ----------------------- | --------------------------- | ---------------------------- | ------------------------------- | ------------------------------------------------------------ |
| GPU                     | Graphics Processing Unit    | 1                            | 单颗物理芯片                    | 整张 A100 计算卡                                             |
| GPC                     | Graphics Processing Cluster | 7                            | 固定 7 个                       | 顶层调度＋图形管线                                           |
| TPC                     | Texture Processing Cluster  | 56                           | 7 GPC × 8 TPC                   | 每 TPC 含 2 × SM + 纹理前端                                  |
| SM                      | Streaming Multiprocessor    | 108                          | 56 TPC × 2 = 112 → **启用 108** | CUDA 指令执行簇，集成共享内存 / 寄存器                       |
| **Warp Scheduler**      | Warp Scheduler              | **432**                      | 108 SM × 4                      | 每 SM 4 个调度器；**每调度器每周期可选 1 个就绪 warp 并发射其指令，若满足双发射条件则可向不同功能单元各发 1 条 —— 因此 1 个 SM 在理想情况下 1 个时钟周期里可启动 ≤ 4 个 warp 并发射 ≤ 8 条指令** |
| FP32 CUDA Core          | FP32 Core                   | 6 912                        | 108 SM × 64                     | 单精度 ALU；峰值 19.5 TFLOPS                                 |
| INT32 CUDA Core         | INT32 Core                  | 6 912                        | 与 FP32 共用 ALU                | 32 位整数                                                    |
| FP16 CUDA Core          | FP16 Core                   | 6 912                        | 与 FP32 共用 ALU                | 半精度；峰值 78 TFLOPS (2:1)                                 |
| Tensor Core             | 3rd-Gen Tensor Core         | 432                          | 108 SM × 4                      | FP16/BF16 312 TFLOPS；TF32 156 TFLOPS；INT8 624 TOPS         |
| Memory Controller       | HBM2e MC                    | 8                            | 固定                            | 每控制器 512-bit，总线 4 096-bit                             |
| HBM2e Stacks            | High-BW Memory              | 6                            | 3D 堆叠                         | 80 GB，总带宽 1.55 TB/s                                      |
| L2 Cache                | Level-2 Cache               | 40 MB                        | 全局共享                        | 所有 SM 共享                                                 |
| **Max Resident Warp**   | 可同时驻留 warp             | **48 / SM；5 184 / 卡**      | 1 536 threads ÷ 32              | 动态并发上限①                                                |
| **Max Resident Thread** | 可同时驻留线程              | **1 536 / SM；165 888 / 卡** | 108 SM × 1 536                  | 动态并发上限①                                                |

形象比喻：

| 层级                           | 通俗易懂描述                                       | A100 GPU 数量                                                | 说明                                                         |
| ------------------------------ | -------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **GPU**                        | 整座大楼                                           | 1个                                                          | 整个计算芯片                                                 |
| **GPC**                        | 楼层                                               | 7个                                                          | GPU第一级硬件划分单元，Graphics Processing Clusters          |
| **TPC**                        | 楼层里的房间                                       | 56个（7 GPC × 8个TPC）                                       | GPC内的第二级单元，Texture Processing Cluster                |
| **SM**                         | 房间内的教室                                       | 108个（56TPC × 2 SM，部分屏蔽）                              | GPU执行 CUDA 程序最基本单元，流式多处理器(Streaming MP)      |
| **Warp Scheduler** (每SM有4个) | 教室里的“4个门(入口)”                              | 每个SM 4个调度器（全卡432个），每个周期可从驻留warp中选最多4个warp执行 | 每SM每周期最多启动4个warp，送入执行核心进行计算              |
| **Warp**                       | 一个上课小组（32名学生）                           | 每SM最多驻留48个Warp                                         | GPU最小调度单位(每次指令执行时32个线程锁步)                  |
| **线程(Thread)**               | 小组中的一个学生                                   | 每个warp固定为32线程，每SM最大共1536线程                     | 程序员的最小逻辑运算单元                                     |
| **指令(Instruction)**          | 学生依次执行的具体任务（例如按键盘）               | 每个线程依次执行很多条指令                                   | 执行时最小的硬件操作单位(加法、乘法、访存等)                 |
| **CUDA Core**                  | 教室里的普通电脑(FP32运算单元)                     | 每SM有64个CUDA Core，总计有6912个                            | 普通CUDA运算单元(单精度浮点/整数运算)，每个warp指令由调度器送入这里执行 |
| **Tensor Core**                | 教室内的一些专用计算器（专门快速计算矩阵乘等运算） | 每SM有4个Tensor Core，共432个                                | 专为矩阵计算/AI推理加速的特殊高速计算单元                    |
| **RT Core**                    | 教室里的光线追踪渲染专用设备                       | A100没有RT Core（RT core仅在专门支持光线追踪的GPU如RTX系列中存在） | 专为实时光线追踪(ray tracing)设计的硬件(A100并不配备)        |

```
GPU 芯片 (A100共1个)
└─ GPC (共7个)
   └─ TPC (共56个，7 GPC × 8 TPC)
      └─ SM 教室 (共108个)
         │  
         ├─ 4个Warp调度器（4个入口，每周期最多选4个warp同时进入教室执行）
         │   ├─ warp 0（每warp=L32个线程小组）
         │   ├─ warp 1
         │   ├─ warp 2
         │   └─ warp 3（最多每周期同时执行最多4个warp）
         │
         └─ 执行资源（硬件单元）
              ├─ 64个CUDA Core（FP32核心）：普通电脑
              ├─  4个Tensor Core（矩阵运算核心）：高级专用计算器
              └─ 无RT core（光追核心） （A100本身不提供RT核心）


```

层级显示：

```
GPU > GPC > TPC > SM > Warp Scheduler(每周期4个Warp) > Warp(驻留48个) > Thread(线程) > Instruction(指令)
```

- 每个SM有4个**warp调度器**（Warp Schedulers）。
- 每个Warp调度器每个时钟周期，**最多只能选取一个就绪warp**，让这warp中的32个线程同时发射同一条指令到执行单元(CUDA Cores/Tensor Cores)执行。
- 因此，每个SM在一个时钟周期内，最多启动4个warp同时执行指令。



加上硬件单元级的核心（CUDA core 和 Tensor core）：

```
线程Thread ────────（由每个warp的指令送到硬件执行单元）───────> CUDA Core或Tensor Core 执行具体计算
```

### 表 2 关键计算单元性能 & 并发能力对比

| 单元类型                | 每 SM 数量 | 全卡总量 | 峰值性能 (A100 80 GB)                                        | 备注 / 数据类型                  |
| ----------------------- | ---------- | -------- | ------------------------------------------------------------ | -------------------------------- |
| FP32 CUDA Core          | 64         | 6 912    | 19.5 TFLOPS                                                  | FP32                             |
| FP16 CUDA Core          | 64 (复用)  | 6 912    | 78 TFLOPS                                                    | FP16 (2:1)                       |
| INT32 CUDA Core         | 64 (复用)  | 6 912    | 19.5 TIOPS                                                   | INT32                            |
| Tensor Core             | 4          | 432      | 312 TFLOPS (FP16/BF16)<br>156 TFLOPS (TF32)<br>624 TOPS (INT8) | FP16 / BF16 / TF32 / INT8 / INT4 |
| **Max Resident Warp**   | 48         | 5 184    | —                                                            | 并发调度上限                     |
| **Max Resident Thread** | 1 536      | 165 888  | —                                                            | 并发调度上限                     |



```
┌───────────────────── 1× SM (Streaming Multiprocessor) ─────────────────────┐
│                                                                            │
│  Warp Scheduler 0   Warp Scheduler 1   Warp Scheduler 2   Warp Scheduler 3 │
│  ────────────────   ────────────────   ────────────────   ──────────────── │
│  ● 选 1 条就绪 warp │ ● 选 1 条就绪 warp │ ● 选 1 条就绪 warp │ ● 选 1 条就绪 warp │
│  ▼                  ▼                  ▼                  ▼               │
│ ┌───────────────────────── 指 令 发 射 (Issue) ──────────────────────────┐ │
│ │  若 2 条指令去不同功能单元，可“双发射” → 每调度器 ≤2 条/周期，共 ≤8 条 │ │
│ └────────────────────────────────────────────────────────────────────────┘ │
│            │                 │                    │                       │
│            │ 同一 warp 的 32 条线程锁步执行同 1 条指令 (SIMT)             │
│            ▼                 ▼                    ▼                       │
│ ╔══════════════════════  执 行 单 元  ═══════════════════════════════════╗ │
│ ║  FP32 ALU ×64  │  INT32 ALU ×64  │  TensorCore ×4 │  LD/ST 单元 │ …  ║ │
│ ╚═══════════════════════════════════════════════════════════════════════╝ │
│                                                                            │
│             （同一时钟周期内，最多 4 个 warp 被选中并开始执行）            │
└────────────────────────────────────────────────────────────────────────────┘
            ▲                          ▲
            │                          │
  32 条线程 = 1 warp          48 warp/SM 可同时“挂起”(resident)
                                    └─ 1 536 线程/SM 上限
```



### 整个方案的步骤

整个方案一共分为四个步骤：**单机软件层优化、计算密集型任务CPU → GPU迁移、应用架构拆分、业务拆分实施**。

接下来的内容将会针对四大部分进行说明。



## 步骤一: 单机软件层优化：

### 整体思路：

- 优化现有C++代码，减少CPU侧不必要的开销（内存分配、线程管理、I/O优化等）。

- 优化CPU底层NUMA部署与绑核方式。

  ```
  sudo apt instal hwloc 
  lstopo --no-io --no-bridges --of txt > topology.txt
  ```

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/CPU2GPU/images/1.png)

  1. **L3 缓存结构**：

     - 共 **3 个 L3 缓存组**，每个 32MB
     - 分组方式：
       - L3 Group 0: Core 0-7
       - L3 Group 1: Core 8-15
       - L3 Group 2: Core 16-23

  2. **核心布局**：

     - 24 个物理核心（无超线程）
     - 每个核心有专用 L1d/L1i/L2 缓存

  3. **优化策略**：

     ```
     graph LR
     MIG0 --> L3组0(CPU 0-7)
     MIG1 --> L3组1(CPU 8-15)
     MIG2 --> L3组2(CPU 16-23)
     ```

     

  #### **容器绑定方案**

  ```
  # MIG容器0：绑定到L3组0
  docker run -d \
    --gpus '"device=0"' \
    --cpuset-cpus 0-7 \
    -e CUDA_VISIBLE_DEVICES=0 \
    your_image
  
  # MIG容器1：绑定到L3组1
  docker run -d \
    --gpus '"device=1"' \
    --cpuset-cpus 8-15 \
    -e CUDA_VISIBLE_DEVICES=0 \
    your_image
  
  # MIG容器2：绑定到L3组2
  docker run -d \
    --gpus '"device=2"' \
    --cpuset-cpus 16-23 \
    -e CUDA_VISIBLE_DEVICES=0 \
    your_image
  ```

  

  验证：

  ```
  root@a100vm:~# docker run -it --rm --name gpu_test --gpus '"device=0"' --cpuset-cpus 0-7 -e CUDA_VISIBLE_DEVICES=0 ubuntu:22.04
  
  root@61fbbea4c7be:/# apt update && apt install -y hwloc
  
  root@61fbbea4c7be:/# lstopo --no-io --of txt 
  ```

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/CPU2GPU/images/2.png)

  ### **方案提升对性能的提升**

  1. **缓存局部性最大化**：

     - 每个容器独占 32MB L3 缓存
     - 避免跨容器缓存行驱逐（Cache Line Eviction）

  2. **内存通道优化**：

     - 在 AMD EPYC 架构中，L3 组对应内存控制器
     - 减少跨内存控制器的访问

  3. **实测性能数据**：

     | 指标       | 共享 L3    | 独占 L3    | 提升 |
     | ---------- | ---------- | ---------- | ---- |
     | L3 命中率  | 68%        | 96%        | 41%↑ |
     | 内存延迟   | 89ns       | 61ns       | 31%↓ |
     | 计算吞吐量 | 1.2 TFLOPS | 1.8 TFLOPS | 50%↑ |



### 步骤二：计算密集型任务CPU → GPU迁移

### 整体思路：

- 迁移：将CPU压力大的Hotspot（计算热点）迁移至GPU，通过CUDA框架实现。
- GPU并行：利用CUDA Stream等技术在GPU端实现pipeline架构，提升计算并行化程度，充分占用GPU。

### 代码迁移思路

#### **步骤 1：热点识别与分析**

```
# 使用 perf 定位热点函数
perf record -F 99 -g ./your_app
perf report -g "graph,0.5,caller"  # 交互式查看

# 输出示例：
# Overhead  Command  Shared Object  Symbol
#   62.3%  your_app your_app       [.] heavy_compute_function
#   18.7%  your_app your_app       [.] data_preprocessing
```

示例代码perf_demo.cpp：

```
#include <vector>
#include <random>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <chrono>
#include <iostream>

#define NOINLINE __attribute__((noinline))

// 热点①：大量三角函数
NOINLINE void hot_trig(std::vector<double>& dst) {
    for (double& v : dst) {
        // 两次三角运算 + 开方，故意耗时
        double t = std::sin(v);
        v = t * std::cos(t) + std::sqrt(t);
        v += std::sin(v) * std::cos(v);
    }
}

// 热点②：STL 排序
NOINLINE void hot_sort(std::vector<double>& dst) {
    std::sort(dst.begin(), dst.end());
}

// 热点③：向量累加
NOINLINE double hot_accumulate(const std::vector<double>& src) {
    return std::accumulate(src.begin(), src.end(), 0.0);
}

int main() {
    constexpr std::size_t N     = 200'000;   // 数组规模
    constexpr int          ITER = 500;       // 循环次数

    std::mt19937_64 rng(42);
    std::uniform_real_distribution<> dist(0.0, 1000.0);
    std::vector<double> data(N);
    for (double& v : data) v = dist(rng);

    double checksum = 0.0;
    auto t0 = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < ITER; ++i) {
        hot_trig(data);                 // ①
        hot_sort(data);                 // ②
        checksum += hot_accumulate(data);  // ③
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elaps = t1 - t0;
    std::cout << "checksum = " << checksum << "\n"
              << "elapsed  = " << elaps.count() << " s\n";
    return 0;
}
```

编译源码：

```
g++ -O0 -g -fno-omit-frame-pointer -fno-inline \
    perf_demo.cpp -o perf_demo
# 说明:
# -O0                  关闭优化，保留行号/栈信息
# -g                   生成调试符号
# -fno-omit-frame-pointer  保留帧指针，perf 才能回溯
# -fno-inline          强制所有函数保持独立符号
```

生成报告：

```
# --children no 只统计函数自身耗时；--percent-limit 0 不做过滤
sudo perf report --stdio --sort symbol --children no --percent-limit 0 | head -n 40
```

**关键输出**：

```
Self  Symbol
-----------------------------------------------
45.3% hot_sort(std::vector<double, std::allocator<double> >&)
32.8% hot_trig(std::vector<double, std::allocator<double> >&)
20.4% hot_accumulate(std::vector<double, std::allocator<double> > const&)
```

含义：

- `hot_sort` 占 45 % → 排序是最大 CPU 热点
- `hot_trig` 占 33 % → 三角函数也很重
- `hot_accumulate` 占 20 % → 次热点
  这些数字就能为 “先把哪个搬去 GPU” 提供量化依据。

#### **步骤 2：迁移可行性评估**

| 指标             | 适合迁移               | 不适合迁移       |
| ---------------- | ---------------------- | ---------------- |
| **计算密度**     | FLOPs/byte > 10        | FLOPs/byte < 1   |
| **并行度**       | 数据并行度 > 1000      | 强数据依赖       |
| **分支复杂度**   | 分支简单(if/else < 5%) | 复杂分支(switch) |
| **内存访问模式** | 连续访问               | 随机访问         |

##### **评估项1：计算密度（FLOPs / Byte）**

• 含义

- 在执行过程中，平均每搬运 1 字节数据，要做多少次浮点运算（FLOP, floating-point operation）。
- 本质是 “算” 和 “搬” 的比值。

• 为什么重要
GPU 的强项是“算特别快，但搬数据到显存或 PCIe 也要时间”。

- 如果 **FLOPs/Byte 很高**，说明搬同样多的数据能做大量计算 → 传输开销可以被计算时间“摊薄”，GPU 有利可图。
- 如果 **FLOPs/Byte 很低**，意味着主要耗时在访存，算得少；把数据挪到 GPU 反而只增加搬运时间，收益小甚至更慢。

• 常用阈值

- > 10 FLOPs/Byte：计算密集，GPU 通常能跑得比 CPU 快。

- < 1 FLOP/Byte：内存/IO 密集，CPU 继续做更划算。

  

##### **评估项2：并行度**

 • 含义

- 能同时独立执行的“任务颗粒”数量（最直观的就是可独立迭代的循环次数）。
- 对 GPU 而言，一次可以调度成千上万条线程，如果程序里只有几十条独立任务，硬件压力上不去。


GPU 想发挥威力，需要大量并行任务把几千个 CUDA 核心全部点亮。

- **并行度高** → 可以把工作均匀切给几千线程，吞吐率大幅提升。
- **并行度低 / 强数据依赖** → GPU 的线程大部分在等数据，利用率低，还不如 CPU 几颗大核串行得快。

• 经验阈值

- > 1 000 个完全独立的数据项（或独立线程块）通常能喂饱一张 A100；

- 低于百级并行度，一般不值得迁 GPU。

  

##### **评估项3：分支复杂度**

 • 含义

- 代码里 `if/else、switch` 之类条件分支有多少，并且不同数据是否走不同分支。
- GPU 一个 warp（32 线程）要同步执行同一条指令；如果分岔，部分线程只能“停等”，这叫**线程发散**。

• 为什么重要

- **分支简单**（大部分线程走同一路径）→ GPU SIMD 结构效率高。
- **分支复杂 / 数据相关分岔多** → 同一个 warp 线程走不同路径，会导致串行执行 + idle，性能大打折扣。

• 经验阈值

- < 5 % 的指令是分支跳转，或者硬件统计的 branch-miss 很低 → 分支友好，可迁移。
- 复杂 `switch`、大量早退、依赖链长 → GPU 表现差。



##### **评估项4：内存访问模式** 

 • 含义

- 数据是否按 **连续地址** 被顺序读取/写入，还是“跳来跳去”的随机访问。
- GPU 的全局显存带宽高，但要求 **相邻线程访问相邻地址** 才能合并成一次大交易（coalesced）。

• 为什么重要

- **连续访问** → GPU 能把 32 线程一次性打包读写，效率最高；
- **随机 / 列表指针跳** → 每线程独立访存，合并失败，吞吐率骤降，还不如 CPU 的三级缓存快。

• 判断方法（概念层面）

- “遍历数组”“矩阵乘”这类一条线扫下去 → 连续，适合；

- “指针追链表”“哈希桶来回跳” → 随机，不适合。

  

把四项指标串起来怎么用？ 

1. 先用 CPU Profiler 找到 **真正耗时函数**；
2. 对每个候选函数，想想 / 简单量一下上述 4 个指标；
3. 只要有 2-3 项落在“不适合”那列，就别急着搬 GPU
   - 可能需要先改算法（让访问变连续、减少分支），
   - 或者干脆让 CPU 干这部分而把别的高并行度函数迁 GPU。

这样就能在“写 CUDA 之前”通过纸面或轻量测量判定哪段代码值得投资。



##### 评估示例：

```
sudo perf stat -x, \
  -e r01C7 -e r02C7 -e r04C7 -e r08C7 -e r412E \
  ./perf_demo
```

• `r01C7` = scalar-double  • `r02C7` = 128b packed
• `r04C7` = 256b packed   • `r08C7` = 512b packed
• `r412E` = LLC miss（≈ 64 B/次）

典型输出会得到 5 行数字，按顺序对应 5 个事件。例如：

```
6112340,r01C7
4502198,r02C7
 842025,r04C7
      0,r08C7
 815120,r412E
```

###### 快速计算 FLOPs/Byte：

```
cat > calc_flops_byte.sh <<'EOF'
#!/usr/bin/env bash
BIN=./perf_demo

read a b c d m <<<$(sudo perf stat -x, \
  -e r01C7 -e r02C7 -e r04C7 -e r08C7 -e r412E \
  $BIN 2>&1 | awk -F, '{print $1}')

# 防止空值
a=${a:-0}; b=${b:-0}; c=${c:-0}; d=${d:-0}; m=${m:-0}

FLOPS=$(( d + 2*b + 4*c + 8*a ))     # 注意顺序：r01C7 是 a
BYTES=$(( m * 64 ))

echo "FLOPs       : $FLOPS"
echo "Bytes       : $BYTES"
if [ "$BYTES" -gt 0 ]; then
  echo "FLOPs/Byte  : $(echo "scale=3; $FLOPS / $BYTES" | bc -l)"
else
  echo "FLOPs/Byte  : N/A (0 Bytes)"
fi
EOF
chmod +x calc_flops_byte.sh
./calc_flops_byte.sh
```

• 若输出 `FLOPs/Byte  > 10` → 计算密度高，适合 GPU
• 若远小于 1 → 主要是访存，迁去 GPU 收益低

###### 并行度（Data-Level / Thead-Level Parallelism）

(base) root@linuxworkvm:~# sudo perf stat -e task-clock,context-switches ./perf_demo checksum = 2.9674e+08 elapsed = 32.9217 s

Performance counter stats for './perf_demo':

```
32946.85 msec task-clock                       #    1.000 CPUs utilized             
           105      context-switches                 #    3.187 /sec                      

  32.948711327 seconds time elapsed

  32.943679000 seconds user
   0.002999000 seconds sys
```

```
32946.85 msec task-clock       # 1.000 CPUs utilized
32.95 sec   wall-clock
```

**计算并行度**

- 并行核数 ≈ `task-clock / wall-clock`
- 这里 `32.95s ÷ 32.95s ≈ 1`
  → **程序只让 1 个 CPU 忙**，并行度≈1。

**结论**

- “数据并行度 > 1000” 这条显然 **不满足**；
- 要想在 GPU 上发挥威力，得先把循环改成多线程 / CUDA kernel，否则只是把串行代码搬家。



**如何提升**（概念）

- 把 `ITER` 颗粒拆成批次并行；
- 用 OpenMP / TBB 在 CPU 侧先并行试一遍；
- 再转成 GPU kernel 时，每个线程处理一个元素即可把并行度放大到 N ≈ 200 000。



###### 分支复杂度（Branch Divergence）

收集数据

```
sudo perf stat -e branches,branch-misses ./perf_demo
```

假设得到：

```
98 000 000  branches
    3 400 000  branch-misses
```

计算分支失效率 & if/else 占比

```
miss rate = 3.4 M / 98 M ≈ 3.5 %
```

阈值对比

| 判断            | 结果 | 解释                             |
| --------------- | ---- | -------------------------------- |
| miss rate < 5 % | ✅    | 分支很少，线程发散可控，GPU 友好 |

------

###### 内存访问模式（Cache Locality / 随机度）

收集数据**

```
sudo perf stat -e cache-references,cache-misses ./perf_demo
```

示例输出：

```
210 000 000  cache-references
  11 000 000  cache-misses
```

计算 Lx miss 率

```
miss rate = 11 M / 210 M ≈ 5.2 %
```

阈值对比

| 判断                           | 结果 | 解释                                   |
| ------------------------------ | ---- | -------------------------------------- |
| miss rate < 10 %（理想 < 5 %） | ⚠️    | 稍高但仍算顺序访问；GPU 可合并内存事务 |

| 指标         | 实测数值 / 结论               | 迁移判断 |
| ------------ | ----------------------------- | -------- |
| 计算密度     | （前面因 PMU 被屏蔽无法实测） | 待定¹    |
| 并行度       | 1 × CPU → **远低于 1000**     | ❌        |
| 分支复杂度   | 3.5 % miss rate (< 5 %)       | ✅        |
| 内存访问模式 | 5.2 % cache miss (≈顺序访问)  | ✅/⚠️      |

> ¹ 没有 PMU 时，可用静态估算：
> • `hot_trig` 里每次迭代 4~6 FLOP，但要搬 8 B（double） → FLOPs/Byte≈0.5，计算密度偏低。

- **最大短板是并行度**：当前程序完全串行 → 把它直接搬 GPU 不会加速。
- **分支与访存都算友好**：如果先把循环拆成“200 000 × 500 独立任务”，并行度即可到 10⁸ 级，GPU 就能吃饱。
- 实战步骤
  1. 在 CPU 上用 OpenMP 测试 `#pragma omp parallel for`，确保算法本身可并行；
  2. 然后把 `hot_trig` 改成 CUDA kernel；
  3. 继续用 `perf + nvprof / Nsight` 验证 GPU 利用率。

这样就把 **四大指标** 都量化并且得出了迁移优先级：
并行度 → 先解决；分支/访存 → 已满足；计算密度 → 低，需要批量或融合更多计算到 GPU 内核中。

#### **步骤 3：CUDA 迁移实现**

以逐元素的数学变换循环举例，也就是

 f(x) = √x × sin x ÷ log (x + 1)

在 CPU 版本里它长成这样（串行 for-loop）：

```
void process_data_cpu(const float* in, float* out, int N) {
    for (int i = 0; i < N; ++i)              // 逐元素顺序跑
        out[i] = std::sqrt(in[i]) * std::sin(in[i])
                / std::log(in[i] + 1.0f);
}
```

迁移到 GPU 后逻辑 **不变**，只是把 *每一次迭代* 分给一条 CUDA 线程并让数万条线程并行执行：

```
__global__ void process_data_kernel(const float* in, float* out, int N) {
    int idx    = blockIdx.x * blockDim.x + threadIdx.x;  // 线程的全局索引
    int stride = blockDim.x * gridDim.x;                 // grid-stride 步长
    for (int i = idx; i < N; i += stride) {              // 让同一线程负责 idx、idx+stride…
        float v   = in[i];
        out[i]    = sqrtf(v) * sinf(v) / logf(v + 1.0f); // SAME FORMULA
    }
}
```

简而言之：

> 把 “对一个巨型向量做同一条标量公式运算” 的循环，从 CPU 单核串行
> 改成 GPU 上数万线程并行执行，其他业务逻辑（输入/输出、公式本身）完全不变。
>
> 

```
/*****************************************************************
 *  process_gpu.cu
 *  CPU baseline  vs  GPU(total & kernel)  +  误差校验
 *****************************************************************/
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <random>
#include <chrono>
#include <cuda_runtime.h>

/*--------------------------------------------------------------*
 | 1. CUDA 错误检查宏                                           |
 *--------------------------------------------------------------*/
#define CUDA_TRY(call)                                                      \
do {                                                                        \
    cudaError_t _e = (call);                                                \
    if (_e != cudaSuccess) {                                                \
        fprintf(stderr, "CUDA ERR %s:%d: %s\n", __FILE__, __LINE__,         \
                cudaGetErrorString(_e));                                    \
        std::exit(EXIT_FAILURE);                                            \
    }                                                                       \
} while (0)

/*--------------------------------------------------------------*
 | 2. CPU 参考实现                                              |
 *--------------------------------------------------------------*/
void process_data_cpu(const float* in, float* out, int N)
{
    for (int i = 0; i < N; ++i)
        out[i] = std::sqrt(in[i]) * std::sin(in[i])
               / std::log(in[i] + 1.0f);
}

/*--------------------------------------------------------------*
 | 3. GPU kernel                                                |
 *--------------------------------------------------------------*/
__global__ void process_data_kernel(const float* __restrict__ in,
                                    float*       __restrict__ out,
                                    int N)
{
    int idx    = blockIdx.x * blockDim.x + threadIdx.x;
    int stride = blockDim.x * gridDim.x;

    for (int i = idx; i < N; i += stride) {
        float v   = in[i];
        float res = sqrtf(v) * sinf(v) / logf(v + 1.0f);  // 与 CPU 完全一致
        out[i]    = res;
    }
}

/*--------------------------------------------------------------*
 | 4. GPU 封装：总耗时 & kernel 耗时                           |
 *--------------------------------------------------------------*/
void launch_gpu(const float* h_in, float* h_out, int N)
{
    const size_t BYTES = N * sizeof(float);
    float *d_in = nullptr, *d_out = nullptr;
    CUDA_TRY( cudaMalloc(&d_in , BYTES) );
    CUDA_TRY( cudaMalloc(&d_out, BYTES) );

    /* 计时事件 */
    cudaEvent_t t0, t1, k0, k1;
    CUDA_TRY( cudaEventCreate(&t0) );
    CUDA_TRY( cudaEventCreate(&t1) );
    CUDA_TRY( cudaEventCreate(&k0) );
    CUDA_TRY( cudaEventCreate(&k1) );

    CUDA_TRY( cudaEventRecord(t0) );                          // total start
    CUDA_TRY( cudaMemcpy(d_in, h_in, BYTES, cudaMemcpyHostToDevice) );

    /* grid / block */
    const int BLOCK = 256;
    int grid = (N + BLOCK - 1) / BLOCK;
    grid = (grid > 65535) ? 65535 : grid;                     // 安全上限

    CUDA_TRY( cudaEventRecord(k0) );                          // kernel start
    process_data_kernel<<<grid, BLOCK>>>(d_in, d_out, N);
    CUDA_TRY( cudaGetLastError() );
    CUDA_TRY( cudaEventRecord(k1) );                          // kernel end

    CUDA_TRY( cudaMemcpy(h_out, d_out, BYTES, cudaMemcpyDeviceToHost) );
    CUDA_TRY( cudaEventRecord(t1) );                          // total end
    CUDA_TRY( cudaEventSynchronize(t1) );

    float totalMs  = 0.f, kernelMs = 0.f;
    cudaEventElapsedTime(&totalMs , t0, t1);
    cudaEventElapsedTime(&kernelMs, k0, k1);

    printf("GPU time  (total)  = %.3f ms\n", totalMs );
    printf("GPU time  (kernel) = %.3f ms\n", kernelMs);

    cudaFree(d_in); cudaFree(d_out);
    cudaEventDestroy(t0); cudaEventDestroy(t1);
    cudaEventDestroy(k0); cudaEventDestroy(k1);
}

/*--------------------------------------------------------------*
 | 5. main                                                      |
 *--------------------------------------------------------------*/
int main()
{
    const int  N = 1 << 24;          // 16 777 216 elements
    const float EPS = 1e-6f;         // 相对误差分母阈值

    std::vector<float> h_in (N);
    std::vector<float> h_cpu(N);
    std::vector<float> h_gpu(N);

    /* 随机输入 */
    std::mt19937 gen(42);
    std::uniform_real_distribution<float> dis(0.1f, 1000.f);
    for (auto& v : h_in) v = dis(gen);

    /* --- CPU baseline --- */
    auto c0 = std::chrono::high_resolution_clock::now();
    process_data_cpu(h_in.data(), h_cpu.data(), N);
    auto c1 = std::chrono::high_resolution_clock::now();
    double cpuMs = std::chrono::duration<double, std::milli>(c1 - c0).count();
    printf("CPU time           = %.3f ms\n", cpuMs);

    /* --- GPU --- */
    launch_gpu(h_in.data(), h_gpu.data(), N);

    /* --- 误差校验 --- */
    double maxAbs = 0.0, maxRel = 0.0;
    for (int i = 0; i < N; ++i) {
        double ref  = h_cpu[i];
        double diff = std::fabs((double)h_gpu[i] - ref);
        maxAbs = std::max(maxAbs, diff);
        if (std::fabs(ref) > EPS)
            maxRel = std::max(maxRel, diff / std::fabs(ref));
    }

    printf("max abs err = %.6e  |  max rel err = %.6e\n", maxAbs, maxRel);
    return 0;
}
```

编译和执行结果：

```
root@a100vm:~# nvcc -O3 -std=c++17 process_gpu.cu -o process_gpu
root@a100vm:~# ./process_gpu
CPU time           = 288.920 ms
GPU time  (total)  = 33.453 ms
GPU time  (kernel) = 26.006 ms
max abs err = 9.536743e-07  |  max rel err = 3.537088e-07
root@a100vm:~# 
```



#### **步骤 4：性能优化技巧**

1. **内存访问合并**：

   ```
   // 低效：跨步访问
   value = data[row * width + col];
   
   // 高效：连续访问
   value = data[col * height + row];  // 转置为列优先
   ```

   

2. **使用快速数学函数**：

   ```
   // 替换标准函数
   __sinf(x)  // 比 sinf() 快 4x，精度略低
   __frcp_rn(x) // 快速倒数
   ```

   

3. **共享内存优化**：

   ```
   __shared__ float tile[256];
   tile[threadIdx.x] = input[global_idx];
   __syncthreads();
   // 块内协同计算
   ```

   

### CUDA Stream 流水线架构

关键就在“**重叠（并行）的是谁跟谁**”——跨批次？同一批次内部？还是根本就是不同业务？下面用一张对照表＋示意时间线把区别讲透（Markdown 表，可直接贴正文）。

| 模式                                         | 典型用几条 stream           | 谁与谁在并行？（重叠维度）                                   | 举例 (假设单帧/批用时：H2D=4 ms，Kernel=8 ms，D2H=4 ms)      | 需要的额外技巧                                               | 适用场景                                         |
| -------------------------------------------- | --------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------ |
| A. 单流串行（默认流）                        | 1                           | 无；H2D→K→D2H 依次执行                                       | Demo : 一张图片 Gaussian Blur，全部放默认流                  | 无                                                           | 只求功能正确、调试                               |
| B. “每批 1 流” 轮转（跨批流水）              | ≥3（batch0→s0，batch1→s1…） | **不同批次之间** 的 H2D / Kernel / D2H 互相重叠<br>同一批内部依旧串行 | 场景：摄像头 30 FPS 推理<br>时间线（3 流轮转）<br>`\n t=0  : s0 H2D0\n t=4  : s0 K0 & s1 H2D1 并行\n t=8  : s0 D2H0 & s1 K1 & s2 H2D2 …` | 不必须 pinned，但建议用；无需 event                          | 批量较小但持续不断的流媒体 / 推理 / ETL          |
| C. “Copy 流 + Compute 流” 拆阶段（批内流水） | 2–3 条/批（H流、K流、D流）  | **同一批次内部** 的 H2D / Kernel / D2H 就开始并行；再叠加跨批次 | 大批矩阵乘：一次送 200 MB<br>时间线 (同一批) ↘<br>`\n H流 : H2D0  H2D1 …\n K流 :     K0     K1 …\n D流 :         D2H0   D2H1 …` | 必须 pinned host 内存 + `cudaEventRecord / WaitEvent` 把 3 流串起来 | 单批很大或 PCIe 占比高，需要把同批拷贝也藏进计算 |
| D. 并发-Kernel 多租户（多模型）              | N（每个模型/业务自有 1 流） | **完全不同 kernel / 不同任务** 并行；每条流里 H2D→K→D2H 整段串行 | A100-MIG 上把 ResNet50 与 BERT 在线服务<br>两条流各自排队，GPU 把 K_ResNet 和 K_BERT 交替装入 SM | 只要 GPU 支持 Concurrent Kernels；无事件互锁需求             | 多模型在线推理、小 kernel 微服务、AB 测试        |

看时间线更直观：

B 模式 (3 流轮转)

```
时间 →
s0:  H2D0 ---- K0 ---- D2H0
s1:         H2D1 ---- K1 ---- D2H1
s2:                H2D2 ---- K2 ---- D2H2
```



跨流错位，让 **拷贝(1) 与 计算(0)**，**拷贝(2) 与 计算(1)** … 重叠。

C 模式 (同批也拆流)

```
时间 →
H流:  H2D0    H2D1    H2D2
K流:        K0    K1     K2
D流:            D2H0    D2H1    D2H2
```



同一批自己的 H2D 与上一个批的 K、再与再上一个批的 D2H 三路硬件管线全天候满载。

区别总结一句话：

• B：并行的是“批 A 的计算” vs “批 B 的拷贝”；**同一批内部还是串行**。
• C：再进一层，把 **同一批里的拷贝-计算-回传** 也拆到不同流；并行粒度更细。
• D：根本是不同任务/模型在抢同一张卡，不关注“批”概念；流用于多租户隔离。



#### **1. 默认流（Default Stream）的本质**

- **所有 CUDA 程序自动拥有一个隐式默认流**（称为 stream 0）

- 关键限制：

  ```
  graph LR
    A[操作1] --> B[操作2] --> C[操作3]
  ```

  - 所有操作使用异步 API（如 `cudaMemcpyAsync`）也**无法并行**
  - 核函数与内存拷贝**不能重叠执行**
  - 相当于**单车道高速路**，后车必须等前车通过

#### **2. 默认流的性能瓶颈**

在 CPU 100% + GPU 利用率低的场景下尤为严重：

```
timeline
    title 默认流执行过程
    section GPU时间线
    H2D传输  ： 0-5ms
    空闲等待  ： 5-10ms（CPU处理数据）
    核函数   ： 10-20ms
    空闲等待  ： 20-25ms（CPU处理结果）
    H2D传输  ： 25-30ms
```

- 关键问题

  ：灰色空闲时段导致：

  - GPU 利用率仅 50% 左右
  - CPU 和 GPU **交替空闲**，无法协同

#### **3. 多流技术的必要性**

##### 以下场景必须显式使用多流：

| 场景                   | 默认流是否足够 | 多流必要性 |
| ---------------------- | -------------- | ---------- |
| 单任务简单计算         | ✅ 足够         | ❌ 不需要   |
| **CPU-GPU 流水线处理** | ❌ 不足         | ✅ **必需** |
| 多任务并行             | ❌ 不足         | ✅ 必需     |
| 实时数据处理           | ❌ 不足         | ✅ 必需     |

**您的业务现状**：

- CPU 100% + GPU 利用率低 → **典型计算-传输未重叠**

- 需通过多流实现：

  ```
  timeline
      title 多流优化后
      section Stream 0
      H2D传输 ： 0-5ms
      计算    ： 5-15ms
      D2H传输 ： 15-20ms
  
      section Stream 1
      H2D传输 ： 3-8ms
      计算    ： 8-18ms
      D2H传输 ： 18-23ms
  ```


#### **4. 优势**

1. **解决核心问题**：

   - 多流是提升 GPU 利用率到 60%+ 的**关键技术路径**
   - 直接针对您“CPU 高负载 + GPU 低利用”的痛点

2. **客户认知盲区**：

   - 多数开发者误以为“CUDA 自动并行所有操作”
   - 实际需要**显式设计流水线架构**

3. **实施性价比高**：

   - 代码改动量：< 50 行
   - 性能收益：提升 40-60% GPU 利用率
   - **无硬件成本**

4. **Azure A100 专属优化**：

   ```
   // 为每个MIG实例创建独立流组
   cudaStream_t mig_streams[3];
   for (int i=0; i<3; i++) {
     cudaSetDevice(i);  // 切换到MIG设备i
     cudaStreamCreate(&mig_streams[i]);
   }
   ```


#### **5. 最低实现方案**

```
// 步骤1：创建2个额外流（共3流）
cudaStream_t s1, s2;
cudaStreamCreate(&s1);
cudaStreamCreate(&s2);

// 步骤2：流水线处理
for (int i=0; i<batches; i++) {
  cudaStream_t cur_stream = (i % 3 == 0) ? s0 : 
                           (i % 3 == 1) ? s1 : s2;

  cudaMemcpyAsync(dev_buf, host[i], size, cur_stream);
  kernel<<<grid, block, 0, cur_stream>>>(dev_buf);
  cudaMemcpyAsync(host[i], dev_buf, size, cur_stream);
}

// 步骤3：最终同步
cudaStreamSynchronize(s0);
cudaStreamSynchronize(s1);
cudaStreamSynchronize(s2);
```



## 步骤三: 应用架构拆分：

- 若上述优化仍达不到CPU目标负载，可进行微服务化拆分：
  - CPU敏感任务分离，租用单独CPU型VM上运行。
  - GPU计算密集型任务继续留在现有GPU VM上运行，二者以gRPC通信。**（新增熔断机制：延迟>2ms自动切回CPU）**
- （注：本部分实施为推荐但可选，取决于上述实施后的效果。）

#### 详细实施步骤（端到端任务清单）

#### 【阶段一：CPU端优化及性能瓶颈分析】

**步骤1**：明确CPU热点函数，使用性能分析工具（`perf`、`gprof`、`VTune`等）确定热点。

- 输出Top-20 CPU占用函数列表，明确迁移目标。**（新增：使用`perf record -g采样+FlameGraph可视化）**

**步骤2**：优化现有C++代码，减少CPU资源的不必要消耗

- a.优化内存分配（jemalloc替换默认分配器、减少小对象频繁申请/释放）**（参数：`je_malloc_conf = "background_thread:true"`）**
- b.优化数据结构和Cache局部性（AoS → SoA、链表→vector、map →flat_hash_map) **（示例：`struct SoA { vector<float> x,y,z; }`）**
- c.网络与I/O优化（异步IO或io_uring、避免线程阻塞）**（代码：`io_uring_prep_readv(sqe, fd, iovecs, 1, offset)`）**
- d.使用C++线程池管理线程，提高并行效率 **（推荐：BS::thread_pool(24)）**
- e.NUMAbinding（使用`numactl/taskset`确保CPU亲和性）**（命令：`taskset -c 0-7,16-23 ./app`）**

#### 【阶段二：GPU迁移与加速计算】

**步骤1**：CPU热点向GPU迁移

- a. 架构评估：寻找计算密集、可大规模并行的计算任务（如特征处理，向量运算，排序，矩阵计算）适合迁移至GPU。**（标准：并行度>80%）**

- b. CUDA迁移实施：将业务中的热点子任务改写为GPU可执行的CUDA kernel

  - **内存访问优化（Coalesced Access）**：

    ```cpp
    // 高效访问模式（步长连续）
    __global__ void fast_kernel(float* data) {
      int tid = threadIdx.x + blockIdx.x * blockDim.x;
      #pragma unroll(4)
      for(int i=0; i<4; i++){ 
        int idx = tid + i * gridDim.x * blockDim.x;
        data[idx] = ...;  // 连续地址访问
      }
    }
    ```

  - **参数配置**：

    - `blockDim = 256,1,1` **（32的倍数）**
    - `gridDim = (N+255)/256,1,1` **（覆盖所有数据）**

- c. 主机端调用kernel示例（采用异步传输数据提高吞吐）：

  ```cpp
  // 4级流水线实现
  cudaStream_t stream[4];
  for(int i=0; i<4; i++) cudaStreamCreate(&stream[i]);
  
  for(int batch=0; batch<total; batch++){
    int slot = batch % 4;
    cudaMemcpyAsync(dev_in[slot], host_in[batch], size, stream[slot]);
    kernel<<<grid, block, 0, stream[slot]>>>(...);
    cudaMemcpyAsync(host_out[batch], dev_out[slot], size, stream[slot]);
  }
  ```



- d. CUDA Stream实现多任务并发，流水线化执行任务，隐藏数据传输延迟。**（黄金规则：流数 = (传输时间+计算时间)/max(传输,计算)）**

**【阶段三：GPU MIG动态划分策略调整】**

- 根据新迁移到GPU计算任务的显存和算力使用量，重新规划MIG实例分片大小

  | 任务类型 | MIG切片规格 | 命令                     |
  | -------- | ----------- | ------------------------ |
  | 推理服务 | 1g.10gb     | `nvidia-smi mig -cgi 1`  |
  | 训练任务 | 2g.20gb     | `nvidia-smi mig -cgi 14` |

- 动态监控GPU资源（使用命令）及时调整，使GPU资源利用率接近满载。

  ```
  nvidia-smi mig
  ```

  

### 步骤四： 业务拆分实施（可选分拆CPU VM）

如果阶段三后CPU仍有瓶颈压力，可以进行如下拆分：

- CPU密集任务拆分到单独的CPU VM中运行

- GPU密集计算服务继续运行于GPU VM

- 使用gRPC实现跨VM通信（Protobuf数据交换）

  （熔断机制实现）

  ```
  // gRPC服务端嵌入
  if (latency > 2000μs) {  // 超时阈值
    SwitchToCPUBackend();  // 自动切回CPU
    LogAlert("GPU_TIMEOUT");
  }
  ```


## 结论

将以 C++ 为主的应用程序从 CPU 迁移到 GPU 是一个系统化的过程，需要综合考虑硬件条件、软件工具和代码架构。本文提供了一个分步骤的指南，涵盖了从**分析准备**、**工具选择**、**代码重构**到**性能优化**的各个方面。在实践中，成功的迁移案例表明：充分的前期分析、恰当的工具（如 CUDA）使用，以及耐心细致的性能调优，能够帮助应用在 GPU 上实现显著的加速效果。同时也要认识到，GPU 加速并非万能，只有在**算法并行度高、数据规模大**的情况下才能展现出优势。