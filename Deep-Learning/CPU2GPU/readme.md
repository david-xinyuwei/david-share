# AI Inference Task Migration from CPU to GPU: Methodology Overview

This repository ties together the entire methodology with a minimalistic example: first identify computational hotspots on the CPU, then rewrite loops characterized by "high parallelism, sequential memory access, and simple branching" into CUDA kernels to offload CPU workload and unleash GPU computing power. Running the code once can compare CPU and GPU execution times, separate transfer and computation overheads, and verify result errors. This quickly validates the feasibility and expected gains of "CPU → GPU" migration, providing a template for subsequent large-scale migration, pipeline optimization, and MIG resource partitioning in a real business environment.

---

## Overall Approach Steps

The overall approach is divided into four steps:

1. Single-machine software optimization  
2. CPU-to-GPU migration of compute-intensive tasks  
3. Application architecture splitting  
4. High-level elasticity and disaster recovery extension

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/CPU2GPU/images/4.png)

The following content will explain these four parts in detail.

---

## A100 Technical Specifications

Testing was conducted using the Azure NC26 A100 GPU VM. The specification analysis of this GPU VM is as below.

| Component          | Full Name                 | Quantity / Scale       | Compute Logic               | Main Function or Description                                  |
|--------------------|---------------------------|-----------------------|----------------------------|-------------------------------------------------------------|
| GPU                | Graphics Processing Unit  | 1                     | Single physical chip       | Whole A100 compute card                                      |
| GPC                | Graphics Processing Cluster | 7                   | Fixed 7 clusters           | Top-level scheduling + graphics pipeline                    |
| TPC                | Texture Processing Cluster | 56 (7 GPC × 8 TPC)    | Each TPC contains 2×SM + texture frontend |                                                              |
| SM                 | Streaming Multiprocessor   | 108 (56 TPC × 2 = 112 → 108 enabled) | CUDA instruction execution cluster, integrates shared memory/registers |                   |
| Warp Scheduler     | Warp Scheduler             | 432 (108 SM × 4)      | Each SM has 4 schedulers; each scheduler can select 1 ready warp per cycle to issue instructions, supporting dual issue; a single SM can launch ≤4 warps and issue ≤8 instructions per clock cycle in ideal case |  |
| FP32 CUDA Core     | FP32 Core                  | 6,912 (108 SM × 64)   | Single-precision ALU       | Peak 19.5 TFLOPS                                            |
| INT32 CUDA Core    | INT32 Core                 | 6,912 (Shared with FP32 ALU) | 32-bit integer arithmetic                       |                                                               |
| FP16 CUDA Core     | FP16 Core                  | 6,912 (Shared with FP32 ALU) | Half precision            | Peak 78 TFLOPS (2:1 ratio)                                  |
| Tensor Core        | 3rd-Gen Tensor Core        | 432 (108 SM × 4)      | FP16/BF16 312 TFLOPS; TF32 156 TFLOPS; INT8 624 TOPS |                                                |
| Memory Controller  | HBM2e MC                   | 8                     | Fixed                     | Each controller is 512-bit; total bus width 4,096-bit       |
| HBM2e Stacks       | High-Bandwidth Memory      | 6 (3D stacked)        |                            | 80GB total capacity with 1.55 TB/s bandwidth                |
| L2 Cache           | Level-2 Cache              | 40 MB                 | Globally shared           | Shared among all SMs                                        |
| Max Resident Warp  | Maximum Resident Warps     | 48 per SM; 5,184 per card | 1,536 threads/SM ÷ 32    | Dynamic concurrency limit                                   |
| Max Resident Thread| Maximum Resident Threads   | 1,536 per SM; 165,888 per card | 108 SM × 1,536      | Dynamic concurrency limit                                   |

### Hardware structure diagram:

```
GPU Chip (Total: 1 A100)
└─ GPC (Total: 7)
└─ TPC (Total: 56, 7 GPC × 8 TPC)
└─ SM (Streaming Multiprocessor) (Total: 108)
│
├─ 4 Warp Schedulers (4 input ports; up to 4 warps can be selected and issued instructions simultaneously each cycle)
│ ├─ warp 0 (each warp = group of 32 threads)
│ ├─ warp 1
│ ├─ warp 2
│ └─ warp 3 (up to 4 warps can be active per cycle)
│ └─ Execution Resources (Hardware Units)
├─ 64 CUDA Cores (FP32 cores): standard floating-point cores like in regular computers
├─ 4 Tensor Cores (Matrix multiplication cores): advanced specialized matrix computation units
└─ No RT cores (Ray Tracing cores): the A100 does not include ray tracing hardware cores

```

## Azure NC A100 vs HC H100

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/CPU2GPU/images/3.png)

### Hierarchy view:

GPU > GPC > TPC > SM > Warp Scheduler (4 Warps per cycle) > Warp (48 warps resident) > Thread > Instruction  
Thread executes instructions delivered by warp to CUDA or Tensor Cores.

Each SM has 4 warp schedulers.  
Each scheduler selects one ready warp per cycle; each warp has 32 threads executing the same instruction synchronously (SIMT).  
Hence, a single SM can launch up to 4 warps per cycle.

### Single SM schematic:

```
┌───────────────────── 1× SM (Streaming Multiprocessor) ─────────────────────┐
│                                                                            │
│  Warp Scheduler 0   Warp Scheduler 1   Warp Scheduler 2   Warp Scheduler 3 │
│  ────────────────   ────────────────   ────────────────   ──────────────── │
│  ● Select 1 ready warp  │ ● Select 1 ready warp  │ ● Select 1 ready warp  │ ● Select 1 ready warp  │
│  ▼                      ▼                       ▼                      ▼               │
│ ┌──────────────────── Issue ──────────────────────┐                    │
│ │  If 2 instructions target different functional units, can perform "dual issue" → each scheduler issues up to 2 instructions per cycle, total up to 8 instructions │ │
│ └───────────────────────────────────────────────┘                     │
│            │                 │                        │                    │
│            │ Same warp's 32 threads execute same 1 instruction in lockstep (SIMT)          │
│            ▼                 ▼                        ▼                    │
│ ╔═════════════════  Execution Units  ══════════════════════════╗ │
│ ║  FP32 cores ×64    │  INT32 cores ×64  │  Tensor Cores ×4   │  Load/Store units  ║ │
│ ╚══════════════════════════════════════════════════════════════════╝ │
│                                                                            │
│  (Up to 4 warps can be selected and start execution in one clock cycle) │
└────────────────────────────────────────────────────────────────────────────┘
            ▲                          ▲
            │                          │
  32 threads = 1 warp     Up to 48 warps can be resident (active/suspended) per SM
                               └─ Max 1,536 threads per SM
```



## Step 1: Single-Machine Software Optimization

### Overall idea:
- Optimize existing C++ code to reduce unnecessary CPU overhead (memory allocation, thread management, I/O optimizations).  
- Optimize CPU NUMA deployment and core affinity.

```bash
sudo apt install hwloc
lstopo --no-io --no-bridges --of txt > topology.txt
```

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/CPU2GPU/images/1.png)

### Example system topology:

#### CPU Topology

#### L3 Cache Structure:

- 3 groups of L3 cache, each 32MB.
- Grouping:
  - L3 Group 0: Cores 0-7
  - L3 Group 1: Cores 8-15
  - L3 Group 2: Cores 16-23

#### Core layout:

- 24 physical cores with no hyperthreading.
- Each core has dedicated L1d/L1i/L2 caches.

#### Optimization strategy (graphviz notation):

```
graph LR
MIG0 --> L3Group0(Cores 0-7)
MIG1 --> L3Group1(Cores 8-15)
MIG2 --> L3Group2(Cores 16-23)
```



#### Container binding examples:

```
# MIG container 0 bound to L3 Group 0
docker run -d \
  --gpus '"device=0"' \
  --cpuset-cpus 0-7 \
  -e CUDA_VISIBLE_DEVICES=0 \
  your_image

# MIG container 1 bound to L3 Group 1
docker run -d \
  --gpus '"device=1"' \
  --cpuset-cpus 8-15 \
  -e CUDA_VISIBLE_DEVICES=0 \
  your_image

# MIG container 2 bound to L3 Group 2
docker run -d \
  --gpus '"device=2"' \
  --cpuset-cpus 16-23 \
  -e CUDA_VISIBLE_DEVICES=0 \
  your_image
```



#### Verification example:

```
docker run -it --rm --name gpu_test --gpus '"device=0"' --cpuset-cpus 0-7 -e CUDA_VISIBLE_DEVICES=0 ubuntu:22.04
apt update && apt install -y hwloc
lstopo --no-io --of txt
```

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/CPU2GPU/images/2.png)

### Container CPU affinity benefits:

| Metric             | Shared L3  | Dedicated L3 | Improvement |
| ------------------ | ---------- | ------------ | ----------- |
| L3 Cache Hit Rate  | 68%        | 96%          | +41%        |
| Memory Latency     | 89ns       | 61ns         | -31%        |
| Compute Throughput | 1.2 TFLOPS | 1.8 TFLOPS   | +50%        |

------

## Step 2: CPU-to-GPU Migration Assessment for Compute-Intensive Tasks

### Overall approach:

- Migration: identify CPU hotspots and migrate them to the GPU using CUDA.
- GPU parallelism: leverage CUDA Streams for pipeline architecture to increase GPU utilization.

### Migration Workflow

#### Step 1: Hotspot identification with perf tool

```
perf record -F 99 -g ./your_app
perf report -g "graph,0.5,caller"
```

#### Example perf output:

| Overhead | Command  | Shared Object | Symbol                       |
| -------- | -------- | ------------- | ---------------------------- |
| 62.3%    | your_app | your_app      | `[.] heavy_compute_function` |
| 18.7%    | your_app | your_app      | `[.] data_preprocessing`     |

#### Example code `perf_demo.cpp`:

```
#include <vector>
#include <random>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <chrono>
#include <iostream>

// Function annotations to disable inlining for perf clarity
#define NOINLINE __attribute__((noinline))

// Hotspot 1: heavy trigonometric usage
NOINLINE void hot_trig(std::vector<double>& dst) {
    for (double& v : dst) {
        double t = std::sin(v);
        v = t * std::cos(t) + std::sqrt(t);
        v += std::sin(v) * std::cos(v);
    }
}

// Hotspot 2: STL sorting
NOINLINE void hot_sort(std::vector<double>& dst) {
    std::sort(dst.begin(), dst.end());
}

// Hotspot 3: vector accumulation
NOINLINE double hot_accumulate(const std::vector<double>& src) {
    return std::accumulate(src.begin(), src.end(), 0.0);
}

int main() {
    constexpr std::size_t N = 200'000;
    constexpr int ITER = 500;

    std::mt19937_64 rng(42);
    std::uniform_real_distribution<> dist(0.0, 1000.0);
    std::vector<double> data(N);
    for (double& v : data) v = dist(rng);

    double checksum = 0.0;
    auto start = std::chrono::high_resolution_clock::now();

    for (int i = 0; i < ITER; ++i) {
        hot_trig(data);
        hot_sort(data);
        checksum += hot_accumulate(data);
    }

    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;
    std::cout << "checksum = " << checksum << "\n"
              << "elapsed  = " << elapsed.count() << " s\n";
    return 0;
}
```



#### Compile with:

```
g++ -O0 -g -fno-omit-frame-pointer -fno-inline perf_demo.cpp -o perf_demo
```



#### Perf report command:

```
sudo perf report --stdio --sort symbol --children no --percent-limit 0 | head -40
```



#### Key results:

| Symbol         | Time % |
| -------------- | ------ |
| hot_sort       | 45.3%  |
| hot_trig       | 32.8%  |
| hot_accumulate | 20.4%  |

------

### Step 2: Migration feasibility evaluation

| Metric                       | Suitable for GPU                | Not suitable for GPU       |
| ---------------------------- | ------------------------------- | -------------------------- |
| Compute Density (FLOPs/Byte) | > 10                            | < 1                        |
| Parallelism                  | Data parallelism > 1000         | Strong data dependency     |
| Branch Complexity            | Simple branching (if/else < 5%) | Complex branching (switch) |
| Memory Access Pattern        | Sequential/contiguous access    | Random access              |

**Compute Density:**

- Measures average number of floating-point operations per byte of data moved.
- High FLOPs/Byte implies computation can amortize data transfers, making GPU effective.
- Low FLOPs/Byte indicates memory-bound workload, CPU likely better.

**Parallelism:**

- Number of independent data elements or tasks to execute in parallel.
- GPU achieves high throughput by thousands of concurrent threads.
- Parallelism below hundreds is insufficient to saturate GPU.

**Branch Complexity:**

- Branch instructions cause thread divergence in GPU warps.
- Simple branching ensures high efficiency.

**Memory Access:**

- GPUs benefit from coalesced (contiguous) memory accesses.
- Random or irregular access patterns degrade performance.

------

### Quantitative example: calculate FLOPs/Byte using perf counters

```
sudo perf stat -x, -e r01C7 -e r02C7 -e r04C7 -e r08C7 -e r412E ./perf_demo
```



Where counters correspond to:

| Counter | Meaning                              |
| ------- | ------------------------------------ |
| r01C7   | scalar-double FLOPs                  |
| r02C7   | 128-bit packed FLOPs                 |
| r04C7   | 256-bit packed FLOPs                 |
| r08C7   | 512-bit packed FLOPs                 |
| r412E   | Last-level cache misses (bytes × 64) |

------

### Script to calculate FLOPs and bytes moved:

```
#!/usr/bin/env bash
BIN=./perf_demo
read a b c d m <<<$(sudo perf stat -x, -e r01C7 -e r02C7 -e r04C7 -e r08C7 -e r412E $BIN 2>&1 | awk -F, '{print $1}')

a=${a:-0}; b=${b:-0}; c=${c:-0}; d=${d:-0}; m=${m:-0}

FLOPS=$((d + 2*b + 4*c + 8*a))
BYTES=$((m * 64))

echo "FLOPs       : $FLOPS"
echo "Bytes       : $BYTES"
if [ "$BYTES" -gt 0 ]; then
  echo "FLOPs/Byte  : $(echo "scale=3; $FLOPS / $BYTES" | bc -l)"
else
  echo "FLOPs/Byte  : N/A (0 Bytes)"
fi
```



------

### Parallelism estimation

```
sudo perf stat -e task-clock,context-switches ./perf_demo
```



Example:

```
32946.85 ms task-clock        # 1 CPU utilized
```



Wall-clock ~32.95 sec → parallelism ≈ 1 (serial execution).

------

### Branch divergence

```
sudo perf stat -e branches,branch-misses ./perf_demo
```



Example:

- 98 million branches
- 3.4 million branch misses → miss rate ≈ 3.5% (<5%, good)

------

### Memory access pattern

```
sudo perf stat -e cache-references,cache-misses ./perf_demo
```



Example:

- 210 million cache references
- 11 million cache misses → miss rate ≈ 5.2% (fairly sequential)

------

### Summary

| Metric          | Measurement or Conclusion   | Migration Suitability |
| --------------- | --------------------------- | --------------------- |
| Compute Density | Approx 0.5 FLOPs/Byte (low) | Uncertain/low         |
| Parallelism     | 1 (serial)                  | ❌ Not suitable        |
| Branching       | 3.5% miss rate              | ✅ Suitable            |
| Memory Access   | 5.2% miss rate (sequential) | ✅ Suitable            |

------

## Step 3: CUDA Migration Implementation

### Example of migrating scalar element-wise mathematical transformation:

**CPU version:**

```
void process_data_cpu(const float* in, float* out, int N) {
    for (int i = 0; i < N; ++i)
        out[i] = std::sqrt(in[i]) * std::sin(in[i]) / std::log(in[i] + 1.0f);
}
```



**GPU kernel:**

```
__global__ void process_data_kernel(const float* in, float* out, int N) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int stride = blockDim.x * gridDim.x;
    for (int i = idx; i < N; i += stride) {
        float v = in[i];
        out[i] = sqrtf(v) * sinf(v) / logf(v + 1.0f);
    }
}
```



**Core idea:**
Transform the loop applying a scalar formula over large vector data from CPU sequential execution to thousands of GPU parallel threads, keeping input-output logic and formula same.

------

### Complete GPU-CPU comparison example `process_gpu.cu` provided, including error checking, timing, memory allocation, and correctness verification, achieving ~9x speedup with negligible numerical error.

Compile and run with:

```
nvcc -O3 -std=c++17 process_gpu.cu -o process_gpu
./process_gpu
```



Typical output:

```
CPU time           = 288.920 ms
GPU time  (total)  = 33.453 ms
GPU time  (kernel) = 26.006 ms
max abs err = 9.536743e-07  |  max rel err = 3.537088e-07
```



------

## Step 4: Performance Optimization Tips

### Memory coalescing

```
// Inefficient: strided access
value = data[row * width + col];

// Efficient: continuous access by rearranging layout
value = data[col * height + row];  // column-major style
```



### Use fast math intrinsics

```
__sinf(x);         // ~4x faster than sinf with slight precision loss
__frcp_rn(x);      // fast reciprocal
```



### Shared memory optimization

```
__shared__ float tile[256];
tile[threadIdx.x] = input[global_idx];
__syncthreads();
// Collaborative computations within block
```



------

## CUDA Stream Pipeline Architectures

The key lies in what overlaps with what — across batches? inside a batch? or different tasks? Below is a table describing common modes:

| Pattern                                                      | Typical Streams                                   | Overlapping Dimensions                                       | Example (times: H2D=4ms, Kernel=8ms, D2H=4ms)                | Extra Techniques                                             | Suitable Scenario                                 |
| ------------------------------------------------------------ | ------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ | ------------------------------------------------- |
| A. Single stream serial                                      | 1                                                 | None; H2D → Kernel → D2H serial                              | Single image Gaussian blur processing in default stream      | None                                                         | Debugging or functional verification              |
| B. Per-batch single stream rotation (pipeline across batches) | ≥3 streams (stream0 batch0, stream1 batch1, etc.) | Overlaps H2D/Kernel/D2H of different batches; serial inside batch | Camera 30FPS inference; Timeline overlaps transfers and compute across batches | Pinned memory recommended (not mandatory)                    | Continuous streaming inference or ETL             |
| C. Copy stream + Compute stream separated per batch          | 2–3 streams per batch (H2D, Kernel, D2H)          | Overlaps H2D/Kernel/D2H inside same batch plus across batches | Large matrices with 200MB batch data; High hardware utilization in 3 pipeline steps | Must use pinned host memory + event synchronization          | Large batch size or heavy PCIe usage              |
| D. Concurrent kernel multi-tenant                            | N streams (one per model/task)                    | Completely different kernels / tasks execute concurrently    | Multi-model A100 MIG service running ResNet50 and BERT concurrently | Requires concurrent kernel support; no need for event dependencies | Multi-model inference, microservices, A/B testing |

------

### 1. Default Stream Essence

- All CUDA programs have an implicit default stream (stream 0).
- Operations in default stream, including asynchronous APIs, execute serially.
- No overlap between kernel execution and data transfers.
- Comparable to single-lane highway: next op waits for previous.

### 2. Default stream bottlenecks

Typical timeline with CPU saturated but GPU underutilized:

```
0-5 ms: H2D copy
5-10 ms: idle wait (CPU processing)
10-20 ms: kernel execution
20-25 ms: idle wait (CPU postprocessing)
25-30 ms: H2D copy
```



Leads to under 50% GPU utilization; CPU and GPU alternate idling.

### 3. Necessity of multiple streams

| Scenario                  | Default Stream Enough | Multi-Stream Needed |
| ------------------------- | --------------------- | ------------------- |
| Simple single task        | ✅                     | ❌                   |
| CPU-GPU pipeline          | ❌                     | ✅                   |
| Multiple concurrent tasks | ❌                     | ✅                   |
| Real-time streaming       | ❌                     | ✅                   |

Multi-stream can overlap copies with kernel executions, improving GPU utilization >60%.

### 4. Advantages:

- Critical for boosting GPU utilization.
- Addresses CPU 100% plus low GPU utilization.
- Common developer misunderstanding: CUDA does not automatically parallelize everything.
- Code changes minimal (~50 lines).
- Zero hardware cost.
- Azure A100 supports per-MIG instance streams.

Example:

```
cudaStream_t mig_streams[3];
for (int i = 0; i < 3; ++i) {
    cudaSetDevice(i);
    cudaStreamCreate(&mig_streams[i]);
}
```



### 5. Minimal working example

```
cudaStream_t s0, s1, s2;
cudaStreamCreate(&s0);
cudaStreamCreate(&s1);
cudaStreamCreate(&s2);

for (int i = 0; i < batches; ++i) {
    cudaStream_t cur_stream;
    switch (i % 3) {
        case 0: cur_stream = s0; break;
        case 1: cur_stream = s1; break;
        case 2: cur_stream = s2; break;
    }

    cudaMemcpyAsync(dev_buf, host[i], size, cur_stream);
    kernel<<<grid, block, 0, cur_stream>>>(dev_buf);
    cudaMemcpyAsync(host[i], dev_buf, size, cur_stream);
}

cudaStreamSynchronize(s0);
cudaStreamSynchronize(s1);
cudaStreamSynchronize(s2);
```



------

## Step 3: Application Architecture Splitting

### Background:

After CPU optimization and GPU migration, issues remain:

- GPU utilization high but CPU stays >70%
- CPU/GPU peak loads misaligned, making single-node scaling hard
- Different tenants have varying CPU and GPU scaling demands

When any of the above appear, the CPU-intensive logic and GPU compute logic should be decoupled into separate microservices.

------

### 1. Splitting decision matrix

| Dimension       | Candidate A (Keep on CPU) | Candidate B (Keep on GPU) | Decision Criteria                       |
| --------------- | ------------------------- | ------------------------- | --------------------------------------- |
| Compute Density | FLOPs/Byte < 3            | FLOPs/Byte > 10           | GPU if B                                |
| Parallelism     | < 1k                      | > 10k                     | Only high parallelism suits GPU         |
| Call Latency    | P99 < 2 ms                | P99 < 5 ms                | Latency-sensitive logic on CPU          |
| State Coupling  | Strong                    | Weak                      | Strong coupling postpone splitting      |
| Data Size       | KB-level                  | MB-level                  | Large data prefers GPU batch processing |

If 3 or more criteria hit 'split' side → proceed with microservices.

------

### 2. Deployment process

#### Phase 1: Service boundaries & tech stack selection

- Design protobuf interfaces defining input/output.
- Measure serialization and gRPC RTT: packet < 1 MB, RTT < 1 ms.
- Communication modes:
  - Real-time: gRPC (Unary or bidirectional streaming)
  - Async batch: Kafka / AMQP

#### Phase 2: CPU-VM (Service-CPU)

- Extract CPU hotspot code into separate repo and Docker image.
- Use thread pools, NUMA affinity, jemalloc from step 1.
- Deploy on general-purpose VM (e.g., D8s v5), replicas scaled per CPU utilization (~70%).

#### Phase 3: GPU-VM (Service-GPU)

- Extract GPU kernel and streams to independent process.
- Assign MIG resources per tenant with 1:1 mapping.
- Expose gRPC supporting dynamic batch size.

#### Phase 4: Communication and fallback

```
sequenceDiagram
Client->>CPU-Svc: Business HTTP request (JSON/REST)
CPU-Svc->>GPU-Svc: gRPC call (<1 ms)
note right of CPU-Svc: start timer
GPU-Svc-->>CPU-Svc: Inference result
CPU-Svc-->>Client: Final response
CPU-Svc->>CPU-Svc: if latency > 2 ms\n  switch to local fallback
```



On latency > 2 ms, fallback to local CPU version and record `gpu_fallback_total`.
Trigger fallback after multiple timeouts; auto-recover after 30s of normal operation.

#### Phase 5: CI/CD & rollback

- Maintain paired images: `service-cpu:{sha}` and `service-gpu:{sha}`.
- Use Helm / Argo Rollouts for blue-green and canary deployments.
- Gradually ramp GPU side traffic from 10% to full.

#### Phase 6: Monitoring & autoscaling

| Component | Key Metrics                          | Scaling Strategy                                          |
| --------- | ------------------------------------ | --------------------------------------------------------- |
| CPU-Svc   | cpu_util, req_qps                    | HPA scale up when CPU >70% and QPS high                   |
| GPU-Svc   | nvidia_gpu_utilization, mig_mem_used | Scale down if GPU<50%, scale up if >80% or add MIG slices |
| Pipeline  | rpc_latency_p95, fallback_count      | Alert on rising fallback count                            |

------

### 3. Typical Implementation Cases

#### Case A: E-commerce Recommendation (Feature engineering + Transformer inference)

| Metric          | Monolith | After Splitting                           |
| --------------- | -------- | ----------------------------------------- |
| CPU Utilization | 90%      | 50%                                       |
| GPU Utilization | 40%      | 75%                                       |
| P99 Latency     | 10 ms    | 6 ms (GPU normal)<br>11 ms (GPU fallback) |

Proto example:

```
message InferenceReq  { 
  repeated float sparse = 1; 
  repeated int64 dense = 2; 
}
message InferenceResp { 
  repeated int64 item_id = 1; 
  repeated float score = 2; 
}
service RecGPU { 
  rpc Predict(InferenceReq) returns (InferenceResp); 
}
```



CPU fallback pseudo-code:

```
auto t0 = now();
auto status = stub->Predict(ctx, req, &resp);
if(!status.ok() || since_ms(t0) > 2.0) {
    FallbackPredictCPU(req, &resp);
    prometheus::inc("gpu_fallback_total");
}
```



#### Case B: Real-time Video (Demultiplexing + Super-Resolution)

- CPU VM: ffmpeg demux + H.264 decoding (e.g., c6i.4xlarge)
- GPU VM: A100 40GB, 3×1g.10gb MIG slices for super-res models
- Run 8 streams of 1080p 60fps each, end-to-end latency < 40 ms

gRPC bidirectional streaming excerpt:

```
auto stream = stub->Process(&ctx);
for (;;) {
    Frame f = pull_frame();   // CPU decode
    stream->Write(f);         // Async H2D
    Frame out;
    if (stream->Read(&out)) push_to_encoder(out);
}
```



------

### 4. Fallback / Circuit Breaker Strategy

| Trigger                         | Fallback Action                             | Recovery Conditions         | Monitoring Metrics                                   |
| ------------------------------- | ------------------------------------------- | --------------------------- | ---------------------------------------------------- |
| RTT > 2 ms x3 or error rate >5% | Use CPU version; enqueue to Kafka GPU queue | 30s of RTT<1ms and error<1% | gpu_fallback_total, rpc_latency_p95, rpc_error_ratio |

------

### 5. Grafana Core Dashboards

- **GPU-Svc:** GPU utilization per slice, gRPC latency histogram.
- **CPU-Svc:** CPU usage ratio, fallback counters.
- **Pipeline:** P99 RPC latency, RPC error ratio.

------

### 6. Common Issues

| Issue                                     | Symptom              | Mitigation                                           |
| ----------------------------------------- | -------------------- | ---------------------------------------------------- |
| gRPC deserialization takes >1ms           | CPU-Svc high latency | Use proto zero-copy and pinned host memory           |
| Batch too large causes tail latency spike | Elevated P95 latency | Use dynamic batching with latency target (e.g., 4ms) |
| MIG memory fragmentation                  | Inference crashes    | Fix slice size; nightly MIG rebuild                  |

------

### 7. Implementation Timeline (5 Weeks Template)

| Week | Focus                                                        |
| ---- | ------------------------------------------------------------ |
| W1   | Service boundaries and protobuf design                       |
| W2   | Extract CPU logic → Service-CPU                              |
| W3   | Extract GPU logic → Service-GPU                              |
| W4   | gRPC, circuit breaker, Prometheus monitoring                 |
| W5   | GPU service canary 10% → full rollout → decommission monolith |

------

You can replace parameters with your own business specifics and quickly achieve CPU-GPU microservice decoupling + fallback protection + full-link observability.

------

## Step 4: High-Level Elasticity and Disaster Recovery Extension

### Goal:

On top of the decoupled CPU-VM ↔ GPU-VM microservices, further implement:

- Cross-region disaster recovery
- Fully rollbackable canary deployments
- Serverless elastic scaling of CPU backend

If no global traffic or extreme availability requirements, any one can be selectively implemented.

------

### Multi-Region / Multi-Cluster Disaster Recovery

| Solution                     | Topology                 | Core Components                                              | Typical Latency | Suitable Scenario                            |
| ---------------------------- | ------------------------ | ------------------------------------------------------------ | --------------- | -------------------------------------------- |
| Active–Active                | 🇺🇸↔🇸🇬 Anycast GSLB       | Global DNS (Route 53/GSLB), Istio multi-primary, CockroachDB or Spanner | <100 ms         | Global users > 1 million, evenly distributed |
| Active–Passive               | 🇺🇸(Primary) ↔ 🇪🇺(Backup) | DNS weighted routing + health checks; periodic backups       | 30-60 s switch  | 95% traffic concentrated in single region    |
| Zonal Failover (Same Region) | AZ-A↔AZ-B                | Kubernetes topology spread, GPU VM image sync                | <10 s           | Multi-AZ within single cloud provider        |

------

### Implementation checklist:

- Global ingress: Anycast + GeoDNS with <5s health probe downtime failover.
- GPU model checkpoint: object storage + incremental rsync; primary→backup delay <60s.
- Data layer: cross-region Spanner / CockroachDB or async dual writes via Kafka + Debezium.
- Disaster drills: monthly manual failover for 15 min validating RPO=0 and RTO<60s.

------

### GPU & CPU Mixed Canary Deployment

Example traffic split:

```
Client
  │
  ├── Istio Ingress (v1 90%, v2 10%)
  │     ├── Service-CPU-v1 ←────┐
  │     └── Service-CPU-v2 ←───┤ Argo Rollouts
  │                           └─ Service-GPU-v1/v2
```



Sample `TrafficSplit` YAML:

```
apiVersion: split.smi-spec.io/v1alpha2
kind: TrafficSplit
spec:
  backends:
  - service: svc-cpu-v1
    weight: 90
  - service: svc-cpu-v2
    weight: 10
```



------

### Two-dimensional canary principle:

- Keep CPU and GPU versions in sync (`schemaVersion` label).
- Progressively rollout CPU 10% → GPU 10% → CPU 100% → GPU 100%.

### Auto rollback criteria:

- `gpu_fail_ratio` > 1% or `rpc_latency_p95` increases 30% in 2 minutes.

Argo Rollouts example:

```
successCondition: result.gpu_fail_ratio < 0.01
failureLimit: 1
metrics:
  - name: gpu_fail_ratio
    interval: 1m
```



------

## Conclusion

Migrating C++-dominant applications from CPU to GPU is a systematic process requiring comprehensive consideration of hardware conditions, software tools, and code architecture. This article provides step-by-step guidelines covering analysis, tool selection, code restructuring, and performance tuning.

Practical migration success demonstrates that thorough preliminary analysis, proper CUDA usage, and patient tuning yield significant GPU acceleration. Understand that GPU acceleration is not universal — advantages manifest in cases of high algorithm parallelism and large data scales.