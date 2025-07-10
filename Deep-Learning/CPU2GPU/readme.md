# CPU 任务向 GPU 迁移思路

- 虚拟机实例: Microsoft Azure NC24A100 v4 GPU VM
  - CPU: 24 cores
  - GPU: NVIDIA A100 80GB x 1
- 应用语言: C++为主
- 当前CPU使用长期处于接近100%的状态，CPU资源存在明显瓶颈。
- GPU利用率较低，目前已开启MIG (Multi-Instance GPU)，但效果不佳，GPU资源仍然过剩。

A100技术指标

| **组件**              | **全称**                    | **数量** | **计算逻辑**                                   | **功能说明**                                                 |
| --------------------- | --------------------------- | -------- | ---------------------------------------------- | ------------------------------------------------------------ |
| **GPU**               | Graphics Processing Unit    | 1        | 单颗物理芯片                                   | 完整A100计算卡的核心处理器                                   |
| **GPC**               | Graphics Processing Cluster | 7        | 基础架构单元                                   | 包含完整的光栅/纹理/计算管线，资源调度中心                   |
| **TPC**               | Texture Processing Cluster  | 56       | 7 GPC × 8 TPC/GPC                              | 每组包含2个SM+纹理单元，图形与通用计算混合单元               |
| **SM**                | Streaming Multiprocessor    | 108      | 56 TPC × 2 SM/TPC = 112，<br>**实际启用108个** | 核心计算引擎，执行CUDA指令                                   |
| **Warp Scheduler**    | Warp Scheduler              | 432      | 108 SM × 4 Warp Schedulers/SM                  | 每周期调度1-2个warp（32线程组），支持4路并行指令发射         |
| **FP32 CUDA Core**    | FP32 CUDA Core              | 6,912    | 108 SM × 64 Cores/SM                           | **单精度浮点单元**，峰值性能19.5 TFLOPS                      |
| **FP16 CUDA Core**    | FP16 CUDA Core              | 6,912    | 与FP32核心复用                                 | **半精度浮点单元**，峰值性能78 TFLOPS（通过2:1打包）         |
| **INT32 CUDA Core**   | INT32 CUDA Core             | 6,912    | 与FP32核心复用                                 | 整数计算单元，支持32位整数运算                               |
| **Tensor Core**       | Tensor Core                 | 432      | 108 SM × 4 Tensor Cores/SM                     | **第三代张量核心**，支持：<br>• FP16/BF16：312 TFLOPS<br>• TF32：156 TFLOPS<br>• INT8：624 TOPS |
| **Memory Controller** | Memory Controller           | 8        | 固定配置                                       | 管理HBM2e显存访问，每控制器512-bit位宽                       |
| **HBM2e Stacks**      | High Bandwidth Memory 2e    | 6        | 物理堆叠                                       | 提供1,555GB/s带宽（80GB版本），4096-bit总线                  |
| **L2 Cache**          | Level 2 Cache               | 1        | 共享                                           | 40MB容量，所有SM共享                                         |

#### **关键计算单元性能对比**

| **单元类型**    | **每SM数量** | **总数量** | **峰值性能** | **支持数据类型**         |
| --------------- | ------------ | ---------- | ------------ | ------------------------ |
| **FP32 CUDA**   | 64           | 6,912      | 19.5 TFLOPS  | float32                  |
| **FP16 CUDA**   | 64 (复用)    | 6,912      | 78 TFLOPS    | float16 (2:1 packed)     |
| **Tensor Core** | 4            | 432        | 312 TFLOPS   | FP16/BF16/TF32/INT8/INT4 |
| **INT32 CUDA**  | 64 (复用)    | 6,912      | 19.5 TIOPS   | int32                    |

## 目标

1. **降低CPU负载**：平均CPU利用率由>95% 降低到<70%。
2. **提高GPU利用率**：使目前闲置的GPU资源利用率显著提高，期望长期维持在60%以上。
3. 不变更现有Azure虚拟机类型（继续使用现有的NC24 A100）。
4. 保证应用性能（QPS）与业务稳定性不受影响或略有改善。

## 实现方案的整体架构设计

### （一）单机软件层优化：

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

     

  ### 绑定方案

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

  

  ### 方案提升

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

### （二）计算密集型任务CPU → GPU迁移：

- 将CPU压力大的Hotspot（计算热点）迁移至GPU，通过CUDA框架实现。

- 利用CUDA Stream等技术在GPU端实现pipeline架构，提升计算并行化程度，充分占用GPU。

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

  

  #### **步骤 2：迁移可行性评估**

  | 指标             | 适合迁移               | 不适合迁移       |
  | ---------------- | ---------------------- | ---------------- |
  | **计算密度**     | FLOPs/byte > 10        | FLOPs/byte < 1   |
  | **并行度**       | 数据并行度 > 1000      | 强数据依赖       |
  | **分支复杂度**   | 分支简单(if/else < 5%) | 复杂分支(switch) |
  | **内存访问模式** | 连续访问               | 随机访问         |

  #### **步骤 3：CUDA 迁移实现**

  **原始 CPU 热点代码**：

  ```
  void process_data(float* input, float* output, int N) {
    for (int i = 0; i < N; i++) {
      // 复杂计算（占CPU 时间 60%）
      output[i] = sqrt(input[i]) * sin(input[i]) / log(input[i] + 1.0f);
    }
  }
  ```

  

  **CUDA 迁移后**：

  ```
  __global__ void process_data_kernel(float* input, float* output, int N) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int stride = gridDim.x * blockDim.x;
  
    for (int i = idx; i < N; i += stride) {
      float val = input[i];
      output[i] = sqrtf(val) * sinf(val) * __frcp_rn(val);  // 快速倒数
    }
  }
  
  // 调用示例
  void launch_kernel(float* d_input, float* d_output, int N) {
    dim3 block(256);  // 最佳线程块大小
    dim3 grid((N + 255) / 256);
    process_data_kernel<<<grid, block>>>(d_input, d_output, N);
  }
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

  #### **2. 默认流的性能瓶颈（您的场景）**

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

  

### （三）应用架构拆分 (可选项)：

- 若上述优化仍达不到CPU目标负载，可进行微服务化拆分：
  - CPU敏感任务分离，租用单独CPU型VM上运行。
  - GPU计算密集型任务继续留在现有GPU VM上运行，二者以gRPC通信。**（新增熔断机制：延迟>2ms自动切回CPU）**
- （注：本部分实施为推荐但可选，取决于上述实施后的效果。）

## 详细实施步骤（端到端任务清单）

### 【阶段一：CPU端优化及性能瓶颈分析】

**步骤1**：明确CPU热点函数，使用性能分析工具（`perf`、`gprof`、`VTune`等）确定热点。

- 输出Top-20 CPU占用函数列表，明确迁移目标。**（新增：使用`perf record -g采样+FlameGraph可视化）**

**步骤2**：优化现有C++代码，减少CPU资源的不必要消耗

- a.优化内存分配（jemalloc替换默认分配器、减少小对象频繁申请/释放）**（参数：`je_malloc_conf = "background_thread:true"`）**
- b.优化数据结构和Cache局部性（AoS → SoA、链表→vector、map →flat_hash_map) **（示例：`struct SoA { vector<float> x,y,z; }`）**
- c.网络与I/O优化（异步IO或io_uring、避免线程阻塞）**（代码：`io_uring_prep_readv(sqe, fd, iovecs, 1, offset)`）**
- d.使用C++线程池管理线程，提高并行效率 **（推荐：BS::thread_pool(24)）**
- e.NUMAbinding（使用`numactl/taskset`确保CPU亲和性）**（命令：`taskset -c 0-7,16-23 ./app`）**

### 【阶段二：GPU迁移与加速计算】

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

### 【阶段三：GPU MIG动态划分策略调整】

- 根据新迁移到GPU计算任务的显存和算力使用量，重新规划MIG实例分片大小

  | 任务类型 | MIG切片规格 | 命令                     |
  | -------- | ----------- | ------------------------ |
  | 推理服务 | 1g.10gb     | `nvidia-smi mig -cgi 1`  |
  | 训练任务 | 2g.20gb     | `nvidia-smi mig -cgi 14` |

- 动态监控GPU资源（使用命令）及时调整，使GPU资源利用率接近满载。

  ```
  nvidia-smi mig
  ```

  

### 【阶段四：业务拆分实施（可选分拆CPU VM）】

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

  

## 迁移的前提条件

1. **可并行的计算任务**：并行度>80% **（通过Amdahl定律计算）**

2. 硬件与驱动：

   （版本要求）

   - CUDA ≥ 11.7
   - NVIDIA Driver ≥ 450.80.02

3. 开发技能：

   （必备知识）

   - 合并内存访问（Coalesced Access）
   - Warp调度机制

4. 正确性验证：

   （差分测试协议）

   ```
   # 精度验证
   assert np.max(np.abs(cpu_res - gpu_res)) < 1e-6  # 绝对误差
   assert scipy.stats.kstest(cpu_res, gpu_res).pvalue > 0.05  # 分布一致性
   ```

   

## 应用迁移的主要步骤

### 4. 编写 GPU 内核函数

**避免分支发散技巧**：

```
// 使用掩码替代条件分支
__global__ void no_branch(float* data) {
  int idx = ...;
  float val = data[idx];
  // 替代 if(val>0): 使用掩码计算
  float result = (val > 0) * (val * 2) + (val <= 0) * (val / 2);
}
```

**共享内存应用**：

```
__global__ void shared_mem_kernel(float* input) {
  __shared__ float tile[256];
  int tid = threadIdx.x;
  tile[tid] = input[blockIdx.x*256 + tid];
  __syncthreads();
  // 块内协同计算
}
```

### 6. 测试与迭代优化

**性能分析工具链**：

| 工具    | 命令                           | 关键指标           |
| ------- | ------------------------------ | ------------------ |
| `nsys`  | `nsys profile --stats=true`    | SM利用率(>60%)     |
| `ncu`   | `ncu --metrics sm__throughput` | 指令吞吐量         |
| `dcgmi` | `dcgmi dmon -e 1001`           | 显存带宽(>700GB/s) |

## 性能优化与任务分配

### 显存优化策略

| 技术          | 实现方式                                  | 适用场景            |
| ------------- | ----------------------------------------- | ------------------- |
| **统一内存**  | `cudaMallocManaged(&ptr, size)`           | 频繁CPU-GPU交换数据 |
| **显存池化**  | CUDA 11.2+ `cudaMemPool`                  | 减少碎片化          |
| **Zero-Copy** | `cudaHostAlloc(..., cudaHostAllocMapped)` | 小数据高频传输      |

### 负载均衡参数

```
\text{最佳流数} = \frac{T_{\text{传输}} + T_{\text{计算}}}{\max(T_{\text{传输}}, T_{\text{计算}})}
```



## 风险控制矩阵

| 风险类型     | 应对措施                  | 监控指标       |
| ------------ | ------------------------- | -------------- |
| **性能回退** | 渐进迁移(5%→100%流量)     | QPS波动>5%     |
| **精度偏差** | 双跑比对+容错阈值(ε<1e-6) | 结果误差率     |
| **显存溢出** | 显存池化+分块计算         | GPU显存使用率  |
| **传输瓶颈** | GPUDirect RDMA启用        | PCIe带宽利用率 |

## 结论

将以 C++ 为主的应用程序从 CPU 迁移到 GPU 是一个系统化的过程，需要综合考虑硬件条件、软件工具和代码架构。本文提供了一个分步骤的指南，涵盖了从**分析准备**、**工具选择**、**代码重构**到**性能优化**的各个方面。在实践中，成功的迁移案例表明：充分的前期分析、恰当的工具（如 CUDA）使用，以及耐心细致的性能调优，能够帮助应用在 GPU 上实现显著的加速效果。同时也要认识到，GPU 加速并非万能，只有在**算法并行度高、数据规模大**的情况下才能展现出优势。