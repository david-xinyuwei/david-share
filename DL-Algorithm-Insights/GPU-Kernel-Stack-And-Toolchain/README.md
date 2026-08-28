# How Does One Line of PyTorch Reach the GPU? Operators, Kernels, Data Layout, and the Full Toolchain

[中文完整版](M01_gpu_kernel_stack_full_article.md) | English

This complete edition follows one line of PyTorch through the runtime stack, then follows the separate toolchain that produces GPU kernels. It covers operators, kernels, libraries, Triton, Gluon, FlyDSL, CK, HIP/CUDA C++, layout algebra, machine instructions, and data movement. Its evidence boundary is the five source articles assigned to M01; source hashes, normalization rules, and all 43 detail figures are traceable in [FULL_MERGE_LEDGER.md](FULL_MERGE_LEDGER.md). The MI300X backend incident is an operational example, not a universal benchmark; hypothetical percentages remain examples, while hardware, version, and source-code claims retain their original scope qualifiers.

**Repository:** <https://github.com/david-xinyuwei/david-share>  
**Series:** `DL-Algorithm-Insights/`  
**Author:** Xinyu Wei | Microsoft AI and Apps GBB Senior System Engineer

## Reading Map

1. Use the six overview figures to place each concept on the runtime chain, kernel build chain, software stack, layout path, programming-model spectrum, and debugging map.
2. Read Source #2 for Triton's role, backend selection, Prefill/Decode differences, and runtime verification.
3. Read Source #8 for explicit layout algebra in FlyDSL and its relationship to Triton, CK, HIP C++, and CuTe DSL.
4. Read Source #9 for the operator/kernel/library distinction and the separation between runtime invocation and kernel production.
5. Read Source #10 for the machine-code and data-movement mechanics behind tiling, bank conflicts, and iteration speed.
6. Read Source #11 for the complete eight-layer NVIDIA/AMD software-stack map and a layer-based troubleshooting method.

The six overview figures use English labels. The 43 detail figures preserve source-language labels where applicable so their evidence bytes remain unchanged; the English interpretation appears in each image's alt text, caption, and surrounding body.

## Six Overview Figures

![Runtime invocation chain and kernel build chain](images/m01_fig1_two_chains.png)

*Figure 1. Runtime selects and invokes an existing kernel; the build path produces that kernel. Triton, CuTe DSL, and FlyDSL do not remain as an extra layer in every runtime invocation.*

![GPU software stack with AMD and NVIDIA counterparts](images/m01_fig2_stack_map.png)

*Figure 2. Comparisons are meaningful only within the same layer. cuBLAS and cuDNN serve different operator domains on one platform; cuBLAS and CUTLASS relate as a finished library and a kernel-construction toolkit.*

![Mapping logical coordinates to addresses, threads, and values](images/m01_fig3_layout_ownership.png)

*Figure 3. Data layout has at least two layers: the mapping from coordinates to offsets, and the ownership mapping from blocks, threads, and values to elements.*

![Data movement from GMEM through shared storage and registers to matrix units](images/m01_fig4_memory_path.png)

*Figure 4. The same mathematical result can follow very different data paths. Layout, Copy Atom, Tiled Copy, MMA fragments, and pipeline scheduling together determine whether the machine stays busy.*

![Control granularity across six kernel implementation paths](images/m01_fig5_programming_models.png)

*Figure 5. This is a spectrum of control interfaces and engineering cost, not a performance ranking. Speed must be measured for a concrete implementation at the same shape, dtype, and hardware.*

![Debugging map from symptoms back to the responsible software layer](images/m01_fig6_debug_map.png)

*Figure 6. A configuration file being present, code compiling, a kernel loading, and a request actually hitting that kernel are four different stages. Evidence from one stage cannot substitute for evidence from the next.*

---

## Complete Technical Edition

<!-- SOURCE-BEGIN-EN id=02 -->
## Source #2: Why Do We Still Need Triton When CUDA and ROCm Already Exist?

> CUDA (Compute Unified Device Architecture, NVIDIA's GPU software platform) and ROCm (Radeon Open Compute, AMD's GPU software platform) can already run GPU programs. What does Triton add?

The preceding article, *What Is a 5D KV Cache?*, explained how data is arranged. The next question is: **what program reads and computes that data?**

The short answer is:

> **Triton is both a language for writing GPU programs in Python and a compiler that turns those programs into GPU machine code.**

It is not an attention mechanism, a KV (Key/Value) cache mechanism, or a complete inference engine. It can, however, be used to implement GPU operators such as Attention, matrix multiplication, and Softmax.

### Where Triton Came From

Triton's foundations were introduced by Philippe Tillet, H. T. Kung, and David Cox in their 2019 paper, *Triton: An Intermediate Language and Compiler for Tiled Neural Network Computations*.

Philippe Tillet later joined OpenAI. In July 2021, OpenAI released Triton 1.0 as open source, aiming to let researchers without years of CUDA experience write GPU programs that approach the performance of expert hand-tuned implementations.

The project began at `openai/triton` and later moved to `triton-lang/triton`, where the community continues to maintain it. The 2021 release primarily targeted NVIDIA GPUs; the current official repository lists support for both NVIDIA and AMD GPUs.

One namesake must be excluded immediately: **NVIDIA Triton Inference Server is a model-serving platform. It is not the Triton programming language discussed here.**

### Terms to Define First

| Term | Meaning here |
|---|---|
| **kernel** | The program that actually executes on a GPU. One operator can have multiple kernel implementations |
| **operator** | The name of a computation step, such as "run Attention once" |
| **Triton** | A language and compiler for writing high-performance GPU programs in Python |
| **CUDA C++** | A low-level GPU programming model for NVIDIA's CUDA platform |
| **HIP C++** | HIP (Heterogeneous-Compute Interface for Portability), the GPU C++ interface commonly used with AMD ROCm |
| **AITER** | AI (Artificial Intelligence) Tensor Engine for ROCm, AMD's high-performance operator library for ROCm |
| **CK** | Composable Kernel, AMD's C++ template operator library; it is not a programming language |
| **FA3** | FlashAttention-3, an Attention implementation for NVIDIA GPUs |
| **Prefill** | The stage that processes a span of input tokens at once |
| **Decode** | The stage in which each request normally generates one token at a time; a service can process multiple requests concurrently |
| **PagedAttention** | Often abbreviated `PA` in code: an algorithm and execution interface that lets Attention read noncontiguous KV Cache through a page table, primarily addressing server-side KV Cache memory management |
| **FlashAttention** | Input/Output-aware exact attention: an exact attention algorithm that uses tiling to reduce transfers between GPU high-bandwidth memory and on-chip storage |
| **layout** | The order in which data is arranged in memory |
| **backend** | The implementation to which a framework delegates a computation step |

When `pa_decode` appears later, it means an **Attention kernel that reads a paged KV Cache during Decode**.

#### The Most Common Confusion

```text
PagedAttention: first use the page table to locate the historical K/V
FlashAttention: then use tiling and I/O optimization to compute Attention efficiently
```

They optimize different things and can appear in the same inference path. PagedAttention is not a subset of FlashAttention, and FlashAttention does not allocate or reclaim KV Cache memory or maintain its page-table mapping.

### Why Triton Appeared

Neural-network frameworks already provide many operators, while CUDA and ROCm already let developers write GPU programs. Triton exists because a large engineering gap remains between those two levels:

```text
PyTorch: makes existing operators easy to invoke, but offers limited control over internal data movement and fusion

CUDA C++ / HIP C++: provides strong control, but threads, shared memory, synchronization, and tuning are all complex

Triton: writes custom GPU programs in a Python-like style while the compiler handles more low-level details
```

When OpenAI released Triton, it explicitly targeted high-performance custom operators with less code. Triton automates part of coalesced global-memory access, shared-memory management, and scheduling within a thread block. Developers still decide how to tile data and how program instances cooperate.

![Triton between high-level frameworks and low-level GPU programming](images/s02_02_triton_article_img01.png)

*Figure 1. Triton reduces the engineering cost of writing and maintaining GPU operators; it does not bypass CUDA or ROCm.*

### What Triton Can Implement

Attention is only one application. The official tutorials directly provide these implementations:

| Official tutorial | Problem it addresses |
|---|---|
| Vector Add | Element-wise vector addition, introducing basic parallelism and bounds masking |
| Fused Softmax | Fuses reads, normalization, and writes to reduce intermediate tensors and memory traffic |
| Matrix Multiplication | GEMM (General Matrix Multiply), demonstrating tiling and Tensor Core use |
| Low-Memory Dropout | Uses reproducible random numbers to reduce mask storage |
| Layer Normalization | Fuses normalization computation |
| Fused Attention | Implements the FlashAttention v2 algorithm in Triton |
| Grouped / Persistent / Block-scaled GEMM | Covers grouped, persistent, and block-scaled matrix multiplication |

Inference frameworks also use Triton for KV Cache movement, quantization or dequantization, and fused activation functions. Whether a particular implementation exists depends on the framework and version. The fact that Triton *can* implement something does not prove that a current runtime *did* use Triton for it.

### What Triton Does Not Replace

Triton primarily addresses GPU compute programs, not a complete inference service:

```text
Complete inference service
├─ Web service, request scheduling, batching       → Inference engine
├─ Tokenizer                                        → CPU-side text processing
├─ Paging, cache reclamation, process management    → Inference engine
├─ Cross-GPU and cross-node communication           → Collective communication and remote-memory access libraries
└─ GPU compute hot spots                            → Triton / CUDA C++ / HIP C++ / template libraries / assembly
```

Nor does Triton bypass the underlying platform: NVIDIA GPUs still depend on CUDA drivers, and AMD GPUs still depend on ROCm drivers. Triton replaces part of the labor of hand-writing CUDA C++ or HIP C++, not the platform itself.

### A Minimal Triton Example

Suppose the GPU needs to perform the simplest element-wise addition:

```text
C[i] = A[i] + B[i]
```

The following is not a complete program; it retains only the core logic:

```python
@triton.jit
def add_kernel(a, b, out, n, BLOCK: tl.constexpr):
   block_id = tl.program_id(0)
   offsets = block_id * BLOCK + tl.arange(0, BLOCK)
   mask = offsets < n
   x = tl.load(a + offsets, mask=mask)
   y = tl.load(b + offsets, mask=mask)
   tl.store(out + offsets, x + y, mask=mask)
```

Line by line:

1. `@triton.jit`: Triton compiles this program just in time on its first execution.
2. `program_id`: identifies the data block handled by the current program instance.
3. `offsets`: identifies the elements assigned to that block.
4. `mask`: prevents out-of-bounds reads and writes when the last block is not full.
5. `load / store`: loads from device memory and writes the result back.

The code never manually assigns element *i* to thread *j*. The developer describes how to process a block of data; the compiler maps that description onto GPU execution resources. This is the core reason Triton is easier to write than lower-level GPU code.

That does not mean "Python automatically becomes fastest." Block size, access order, parallelism, and hardware characteristics still have a major effect on performance.

### A Real Troubleshooting Case: What Actually Changed?

During one MI300X inference validation, the AITER Attention path hit a K/V layout error. To restore service first, the Attention backend was switched to Triton:

```text
--attention-backend aiter
→ AITER Attention path fails

--attention-backend triton
→ Switch to an Attention implementation written in Triton
```

![Switching one Attention implementation from AITER to Triton](images/s02_02_triton_article_img02.png)

*Figure 2. The change replaced one operator implementation path, not the entire AITER library.*

Think of the inference service as a restaurant:

| Computation step | Path used at the time | After the Triton switch |
|---|---|---|
| Attention | AITER Attention | **Changed to Triton Attention** |
| MoE expert computation | AITER-related operators | Unchanged |
| Quantization | AITER-related operators | Unchanged |
| Normalization | AITER-related operators | Unchanged |

The central kitchen did not close. One faulty station for the Attention dish was temporarily replaced.

Why not stay on Triton permanently? Because stable execution and maximum hardware-specific performance are different goals:

- A Triton path is often useful for implementing a new operator quickly, validating functionality, or providing a stable fallback.
- AITER can provide deeper hardware-specific customization and tuned programs for AMD GPUs, but it can still fail when a particular model shape, data layout, or runtime mode has not been adapted.
- After a fix, the AITER path can be restored for performance validation. One failure does not establish that every AITER operator is faulty.

The central engineering lesson is precise: **a backend change must be scoped to the operator, stage, model shape, and version. "We replaced AITER with Triton" is too broad.**

### One Configuration Value Expands into Four Layers

![Four layers hidden behind one backend setting](images/s02_02_triton_article_img03.png)

*Figure 3. Framework selection, operator library, inference stage, and concrete implementation can vary independently.*

From top to bottom, each layer can change on its own:

1. The launch script selects `aiter`.
2. AITER is an operator library containing many operators.
3. Prefill and Decode use **different operators**.
4. One operator can have **multiple implementations** written with different tools or languages.

Many explanations stop at layer 1 and imply that the choice is settled. The remaining three layers can still branch.

### Why Prefill and Decode Need Different Treatment

The third layer deserves its own explanation because it is the starting point for the later branches.

![Different computational shapes in Prefill and Decode](images/s02_02_triton_article_img04.png)

*Figure 4. Prefill and Decode both perform Attention, but their shapes and common bottlenecks differ.*

| | Prefill | Decode |
|---|---|---|
| Tokens processed at once | A span of input per request | Normally one generated token per request; a batch can contain multiple requests |
| Shape of Q | A request can have multiple rows | Normally one row per active request |
| K/V to read | Current input and any reusable prefix | Each request's own historical K/V |
| Common bottleneck | Usually more compute-intensive | Usually more memory-bandwidth-intensive |

Prefill is like reading the entire exam paper before writing; Decode is like writing the answer one character at a time while repeatedly consulting everything already read.

Different bottlenecks call for different optimizations. Prefill usually prioritizes efficient large-block computation. Decode usually prioritizes moving less data and reading it contiguously. The actual bottleneck still depends on batch size, context length, and hardware.

The two stages may therefore use not only **two different kernels, but kernels written in two different languages or toolchains**.

### Separate the Categories Before Comparing Them

These names are often confused because they do not denote the same kind of thing:

| Name | What it is | Analogy |
|---|---|---|
| FlashAttention / FA3 | **Attention algorithm and implementation**: defines tiling and reduces data movement | Efficient processing method |
| PagedAttention | **Paged KV Cache access mechanism**: locates and reads noncontiguous K/V through a page table | Warehouse shelves and a picking list |
| AITER, FlashInfer | **Operator libraries**: package finished operators | Central kitchens |
| Triton, Gluon, FlyDSL | **Domain-specific languages**: express GPU programs at a higher level | Tools and techniques |
| CK, Opus | **C++ template libraries**: compose and generate GPU programs | Molds and production lines |
| Hand-written assembly | **Low-level implementation method**: directly schedules GPU instructions | Hand finishing |
| `--attention-backend aiter` | **Framework switch**: chooses where to delegate this step | Choosing a kitchen when ordering |

In one sentence: **FlashAttention primarily optimizes how Attention is computed; PagedAttention primarily optimizes how historical K/V is stored and accessed; implementation tools determine how the GPU program is written; operator libraries package it; and framework switches choose a path.**

These layers can be combined. One operator can have several implementation paths, and one operator library can contain implementations produced by multiple technologies.

### What AITER Is

AITER stands for AI Tensor Engine for ROCm. It is AMD's high-performance operator library. One line in its official description is central to this discussion:

> Multiple kernel backends — Triton, Composable Kernel (CK), and hand-tuned ASM

ASM abbreviates Assembly. **AITER itself is not one way of writing kernels.** It packages implementations built with Triton, CK (Composable Kernel, AMD's C++ template operator library), hand-tuned assembly, and other paths behind unified Python/C++ interfaces.

Saying "we use AITER" carries about as much information as saying "we ordered from this central kitchen." It does not yet identify the operator, implementation, or fallback path.

### Six Common Implementation Paths

![Six common GPU kernel implementation paths](images/s02_02_triton_article_img05.png)

*Figure 5. These paths differ in abstraction and control; they are neither a strict hierarchy nor a performance ranking.*

| Implementation path | What it is | Suitable use |
|---|---|---|
| Native PyTorch composition | Builds computation from existing operators | Reference implementation, fallback, rapid validation |
| Triton | Python domain-specific language | Lets the compiler handle more layout and scheduling detail |
| Gluon | Lower-level language on the Triton compiler stack | Explicit control of layout, memory, and pipelines |
| FlyDSL | Python language based on MLIR (Multi-Level Intermediate Representation) and centered on layout algebra | Expresses tiling, partitioning, data movement, and instruction structure |
| CK / Opus | C++ template libraries | Compose and generate high-performance programs for specific shapes |
| Hand-written assembly | Direct GPU instruction programming | Extreme optimization of stable hot paths |

Operator libraries retain several paths because the best implementation can differ by shape, dtype, and hardware. Regular computations such as GEMM (General Matrix Multiply) often fit template generation well; memory-sensitive Decode programs depend more heavily on exact layouts and pipeline schedules.

### Triton and Gluon: Automatic and Manual Transmissions

These two are easy to confuse because they **share the same compiler stack**.

The official Triton tutorial defines Gluon directly:

> Gluon is a GPU programming language based on the same compiler stack as Triton. But unlike Triton, Gluon is a lower-level language that gives the user more control and responsibility.

![Triton and Gluon as different control levels on one compiler stack](images/s02_02_triton_article_img06.png)

*Figure 6. Triton delegates more decisions to the compiler; Gluon exposes more layout, memory, and pipeline decisions to the programmer.*

- **Triton is the automatic transmission**: you describe the matrix multiplication, while the compiler decides more of the tile decomposition, shared-memory allocation, and instruction ordering.
- **Gluon is the manual transmission**: the vehicle and engine are the same, but you control the shifts. Tile decomposition, memory allocation, and pipeline ordering become explicit responsibilities.

They share compiler front-end and JIT (Just-In-Time) infrastructure and ultimately emit machine code for the same GPU. The distinction is **who makes the decisions**.

That is why AITER contains paths such as `aiter.ops.triton.gluon.pa_decode_gluon`. AITER organizes its Gluon implementation under `triton/gluon`; the official Triton documentation confirms that Gluon shares Triton's compiler stack, front end, and JIT infrastructure.

### FlyDSL and Its Direct Connection to Data Layout

FlyDSL stands for **Flexible Layout Python DSL**. A DSL is a Domain-Specific Language, a language designed for a particular class of work. AMD open-sourced FlyDSL as its own MLIR-based compilation path. MLIR is general infrastructure for building compilers.

The important word in the name is **layout**.

FlyDSL starts from three abstractions:

```text
Shape   —— Size of each dimension
Stride  —— Distance between adjacent elements
Layout  —— Mapping formed by (Shape, Stride)
```

The mapping rule is one line:

```text
Index = dot(Coord, Stride)
```

A 5D KV Cache is, at its core, a set of shapes and strides. Address order that had to be derived manually in the earlier article becomes a first-class object in FlyDSL and can participate directly in algebraic operations such as `composition`, `product`, `divide`, and `partition`.

Put differently: the earlier article explained how data is arranged; FlyDSL is a language for describing that arrangement.

Two additional facts prevent common misunderstandings:

- FlyDSL is a **required dependency** of AITER; installing AITER installs it.
- Its official repository carries a disclaimer that it is experimental and is not part of the official ROCm distribution.

### How FA3 Relates to AITER

FA3 (FlashAttention-3) is sometimes treated as a universally newer and stronger algorithm that should be used everywhere. The platform grouping in SGLang's Attention backend choices shows why that is wrong:

```text
# Common
triton, torch_native, flex_attention, dsa, dsv4

# NVIDIA specific
cutlass_mla, fa3, fa4, flashinfer, flashmla,
trtllm_mla, cutedsl_mla, trtllm_mha, ...

# AMD specific
aiter, wave

# Other platforms
intel_amx, ascend, intel_xpu
```

`fa3` appears in the **NVIDIA specific** group; `aiter` appears in the **AMD specific** group.

They are peer command-line choices in SGLang, but they still name different categories underneath. `fa3` points to a particular Attention implementation; `aiter` points to a library containing many kinds of operators. Because the source groups `fa3` under NVIDIA and `aiter` under AMD, FA3 is not a direct AITER replacement on MI300X.

### Version Scope for the Following Implementation Details

The next two sections analyze only public SGLang fork commit `878fff156`. The `vectorized_5d` layout, Gluon/FlyDSL switch, and Draft worker override are concrete behavior in that snapshot. They must not be generalized to every SGLang or AITER version or to every model.

The earlier AITER-to-Triton troubleshooting case occurred on an older software stack. It illustrates the distinction between an operator library and a concrete implementation path; it is not the same run as this later snapshot.

### Source Evidence 1: One KV Cache, Kernels Written in Two Languages

The source comment for `vectorized_5d` states, in part:

> "vectorized_5d" allocates K as (num_blocks, H_kv, head_dim/x, page_size, x) and V as (num_blocks, H_kv, page_size/x, head_dim, x) (x = 16 / dtype_size), **matching the SHUFFLE layout that aiter's CK FmhaBatchPrefill kernel and `aiter.ops.triton.gluon.pa_decode_gluon` both consume natively.**

![One KV Cache layout consumed by CK in Prefill and Gluon in Decode](images/s02_02_triton_article_img07.png)

*Figure 7. The same SHUFFLE-layout KV Cache is consumed natively by kernels produced through two different programming models.*

- Prefill reads it with `FmhaBatchPrefill`, written with **CK**, a C++ template library. Fmha means Fused Multi-Head Attention.
- Decode reads it with `pa_decode_gluon`, written in **Gluon**, a Python domain-specific language.

Two kernels written in very different languages read the same data, and both expect to consume it directly without a runtime `permute`.

This is exactly what it means to call layout a data contract: the two ends of the contract can live in different programming worlds.

### Source Evidence 2: Different Layers Can Use Different Implementations in One Inference Run

AITER's paged Decode path has another switch:

```text
SGLANG_AITER_PA_DECODE_IMPL   default "gluon"; option "flydsl"
```

Its source comment contains the most important qualification in this article:

> "gluon" preserves the existing AITER path. "flydsl" is an opt-in ... path for sink-free full-attention target verification; **SWA/sink layers remain on AITER Gluon.**

![Layer-selective use of FlyDSL and Gluon](images/s02_02_triton_article_img08.png)

*Figure 8. Layer placement varies by model, so the diagram is illustrative. In this snapshot, eligible full-attention layers can use FlyDSL while SWA and sink-related layers remain on Gluon.*

Three terms need definitions before interpreting that comment:

- **full attention**: every token can attend to all preceding tokens.
- **SWA (Sliding Window Attention)**: each token attends only to a recent window, reducing memory and computation by excluding tokens outside the window.
- **attention sink**: a small number of initial tokens remain permanently visible as anchors; removing them can materially reduce accuracy.

Even when the switch is set to `flydsl`, **only the eligible full-attention layers change implementation**. Sliding-window and attention-sink layers continue to run on Gluon.

For this snapshot and model path, "we set FlyDSL" is still imprecise. The accurate statement is: "eligible full-attention layers switched to FlyDSL; the other related layers remained on Gluon."

The earlier question now has a concrete answer:

```text
--attention-backend aiter   identical on both sides
KV layout                   identical on both sides
but PA_DECODE_IMPL differs  → completely different Decode kernels
even the same value         → different layers still use different implementations
```

Identical configuration text can therefore lead to completely different executing kernels.

### How to Verify Which Implementation Actually Ran

Do not stop at the launch script. Verify each layer:

| Layer | What to verify |
|---|---|
| Framework switch | Effective value of `--attention-backend` |
| Implementation switch | Effective value of `SGLANG_AITER_PA_DECODE_IMPL`; its default is `gluon`, not an empty value |
| Dependency versions | `pip show aiter` / `pip show flydsl`, because implementations change with versions |
| Kernel logs | Names of the Prefill and Decode kernels actually loaded |
| Per-layer routing | Whether full-attention layers and sliding-window/attention-sink layers used different implementations |

A general verification sequence is:

```bash
# Effective environment-variable values (read the process environment, not your shell)
tr '\0' '\n' < /proc/<pid>/environ | grep -E 'ATTENTION|AITER|FLYDSL'

# Kernels actually loaded
grep -E 'mha_batch_prefill|pa_decode|gluon|flydsl' server.log
```

An environment variable proves only that an implementation was requested. Combine it with startup logs, loaded code paths, or a profiler to establish what executed. Performance numbers alone cannot identify the implementation.

### Five Common Misconceptions

| Misconception | Correct interpretation |
|---|---|
| AITER is one kernel | AITER is an operator library that can contain DSL, C++ template, assembly, and other implementation paths |
| AITER invented Gluon | Gluon is a lower-level language on the Triton compiler stack; AITER uses it |
| Triton and Gluon are competitors | They share a compiler stack and differ in who controls layout and scheduling |
| FA3 is newer than AITER, so it should replace AITER | In SGLang they target different hardware, and one names a specific implementation while the other is an operator-library entry point |
| Setting `flydsl` applies to the entire model | In the scoped snapshot, only eligible full-attention layers switch; other related layers remain on Gluon |

### Remember Three Things

**Layers:** an algorithm, an operator library, a language for writing kernels, and a concrete implementation are four different things.

**Relationships:** AITER is an operator library; Triton, Gluon, and FlyDSL are domain-specific languages at different control levels; CK is a C++ template library; FA3 is a particular Attention implementation.

**Verification:** identical configuration text can execute different kernels. Kernel logs are the decisive evidence.

### Public Sources

1. OpenAI background, goals, and programming model for the 2021 Triton 1.0 release  
   https://openai.com/index/triton/

2. Current official Triton repository: language, compiler, and hardware support  
   https://github.com/triton-lang/triton

3. Official Triton tutorials: vector addition, Softmax, matrix multiplication, LayerNorm, Attention, and more  
   https://triton-lang.org/main/getting-started/tutorials/

4. 2019 Triton paper, *An Intermediate Language and Compiler for Tiled Neural Network Computations*  
   https://www.eecs.harvard.edu/~htk/publication/2019-mapl-tillet-kung-cox.pdf

5. Official AITER repository, including its backend description  
   https://github.com/ROCm/aiter

6. Official FlyDSL repository, including layout algebra and the compilation pipeline  
   https://github.com/ROCm/FlyDSL

7. Official Triton Gluon tutorial, explaining how Gluon differs from Triton  
   https://github.com/triton-lang/triton/blob/main/python/tutorials/gluon/01-intro.py

8. ROCm Composable Kernel (CK)  
   https://github.com/ROCm/composable_kernel

9. Public SGLang fork snapshot, with Attention backend values grouped by platform  
   https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/server_args.py

10. Public SGLang fork snapshot, with KV layout and PA Decode implementation switch comments  
    https://github.com/sammysun0711/sglang/blob/878fff15647fe3dabb32aa3a335b0ad16e3ee878/python/sglang/srt/environ.py

11. Original FlashAttention paper on data-movement optimization across the GPU memory hierarchy  
    https://arxiv.org/abs/2205.14135

12. Original PagedAttention paper on paged KV Cache management for large-model serving  
    https://arxiv.org/abs/2309.06180
<!-- SOURCE-END-EN id=02 -->

---

<!-- SOURCE-BEGIN-EN id=08 -->
## Source #8: Triton, FlyDSL, CK, and HIP C++: The GPU Kernel Stack in 10 Figures

> ROCm is not a way to write kernels, and RoPE is not missing; it is often fused into a neighboring operator. This chapter separates the role of each tool and explains why FlyDSL appears in the ROCm inference stack.

The earlier AITER discussion listed several kernel implementation paths: Triton, FlyDSL, CK (Composable Kernel, a tiled kernel library built on HIP C++), and hand-written assembly. FlyDSL received only one line there; this chapter develops the full model.

The central distinction is:

> **Triton lets the compiler derive most thread-level layouts; FlyDSL gives explicit layout algebra to the developer.**
>
> This is the main line between their responsibilities, not an exhaustive account of every difference between the toolchains.

The professional term for "how the data is arranged" is **layout**. It is the subject of this chapter and appears directly in FlyDSL's full name: Flexible Layout Python DSL.

Another frequent misconception can be removed immediately: **ROCm is not a way of writing a kernel**. ROCm corresponds to CUDA; the AMD counterpart to CUDA C++ is **HIP C++**. Platform and programming model are different axes.

### Terms to Define First

| Term | Meaning here |
|---|---|
| **GPU** | Graphics Processing Unit, the accelerator chip discussed here |
| **kernel** | The program that actually executes on a GPU |
| **layout** | The order in which data is arranged in memory |
| **tile** | A small block cut from a larger matrix |
| **DSL** | Domain-Specific Language, a language designed for one class of problems |
| **MLIR** | Multi-Level Intermediate Representation, compiler infrastructure for representing and lowering programs at multiple levels |
| **IR** | Intermediate Representation, the compiler data structure between source code and machine code |
| **dialect** | An MLIR vocabulary containing custom operations and types |
| **LDS** | Local Data Share, AMD GPU on-chip shared memory; small and fast compared with device memory |
| **MFMA** | Matrix Fused Multiply-Add, AMD's fused matrix multiply-add instruction |
| **JIT / AOT** | Just-In-Time compilation / Ahead-Of-Time compilation |
| **wavefront** | A group of AMD GPU threads that execute together; NVIDIA calls the corresponding concept a warp |

### 1. What a Layout Actually Is

This is the foundation for everything that follows.

#### A Matrix Becomes a One-Dimensional Address Space

Device memory is one-dimensional: a long sequence of addresses. A matrix is two-dimensional in the programmer's model. A rule is therefore required to translate "row *r*, column *c*" into an address offset. **That rule is the layout.**

The official FlyDSL documentation expresses it as:

```
Index = dot(Coord, Stride) = Σ cᵢ × sᵢ
```

In plain terms, multiply each coordinate by the matching stride and add the products to obtain the address.

- **Shape**: the size of each dimension, for example `(2, 4)`.
- **Stride**: how far the address moves when a coordinate advances by one in each dimension.
- **Layout**: the pair formed by Shape and Stride.

#### A Concrete Example

![A logical 2 by 4 matrix under row-major and column-major layouts](images/s08_08_flydsl_article_img01.png)

*Figure 1. One logical matrix can map to different physical address orders. Adapted from the official FlyDSL Layout Guide.*

A 2-row, 4-column matrix has 8 logical cells, but memory can arrange them in very different orders.

For **row-major** order, `Stride = (4, 1)`:

- Advancing one row jumps four addresses; advancing one column jumps one.
- Coordinate `(1, 2)` maps to `1×4 + 2×1 = 6`.
- Memory order: `(0,0) (0,1) (0,2) (0,3) (1,0) (1,1) (1,2) (1,3)`.

For **column-major** order, `Stride = (1, 2)`:

- Advancing one row jumps one address; advancing one column jumps two.
- Coordinate `(1, 2)` maps to `1×1 + 2×2 = 5`.
- Memory order: `(0,0) (1,0) (0,1) (1,1) (0,2) (1,2) (0,3) (1,3)`.

The data and logical coordinates have not changed, yet changing the stride completely changes the physical access order.

#### Why Layout Controls Performance

When a group of GPU threads accesses contiguous, aligned addresses, the hardware can usually combine those requests into fewer memory transactions. Strided, scattered accesses tend to require more transactions.

The same algorithm can therefore achieve very different bandwidth utilization under different layouts. LDS bank conflicts and the alignment between register tiling and MFMA instruction shapes are also layout problems.

> In high-performance kernel work, much of the effort goes not into deciding *what* to compute, but into deciding *where the data goes and which thread owns each part*.

That is the problem FlyDSL addresses.

### 2. ROCm Is on a Different Axis

A common question is: if Triton determines layout, where do **ROCm** and **C++** fit? The question combines two independent axes.

![Platform axis versus kernel-control axis](images/s08_08_flydsl_article_img02.png)

*Figure 2. ROCm and CUDA form the platform axis; Triton, FlyDSL, CK, and HIP C++ describe kernel implementation and control. Organized from official documentation.*

| Axis | Question | Members |
|---|---|---|
| **Platform axis** | Which software platform manages the GPU? | CUDA (Compute Unified Device Architecture, NVIDIA's GPU platform) ↔ **ROCm** (Radeon Open Compute, AMD's open GPU software platform) |
| **Control axis** | Who decides layout? | PyTorch → Triton → FlyDSL → CK → HIP C++ → assembly |

**ROCm corresponds to CUDA.** Each includes drivers, runtimes, compilers, and foundational libraries. They are the substrate, not kernel authoring styles.

On NVIDIA, the precise statement is "this kernel was written in **CUDA C++**," not merely "in CUDA." On AMD, the corresponding statement is "written in **HIP C++**."

#### Two C++ Levels on AMD

AMD's C++ stack has two relevant levels.

**1. HIP (Heterogeneous-compute Interface for Portability) C++: the native kernel language corresponding to CUDA C++.**

```cpp
__global__ void gemm(const float* A, const float* B, float* C,
                     int M, int N, int K) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    float acc = 0.f;
    for (int k = 0; k < K; ++k)
        acc += A[row * K + k] * B[k * N + col];   // Layout is encoded in index arithmetic.
    C[row * N + col] = acc;
}
```

The developer expresses layout through index arithmetic such as `row * K + k`. Compilers such as LLVM can analyze and optimize some access patterns, but the source contains no directly composable or divisible layout object.

**2. CK (Composable Kernel): a template library built on HIP C++.**

The official CK README states:

> The CK library provides a **programming model** for writing performance-critical kernels... The CK library **uses general purpose kernel languages, such as HIP C++**.

**CK is therefore not a language. It is a programming model above HIP C++.** It pursues performance portability through two central ideas:

- a tile-based programming model;
- **Tensor Coordinate Transformation**.

The second is CK's form of layout algebra. It addresses the same class of problem as FlyDSL, but expresses the solution through C++ templates.

#### Three Ways to Express the Same Layout Control

![How HIP C++, CK, and FlyDSL expose layout semantics](images/s08_08_flydsl_article_img03.png)

*Figure 3. All three lower-level approaches can control address mapping. They differ in how layout semantics enter the compiler. Organized from the official CK and FlyDSL documentation.*

The valuable distinction is not whether the programmer can choose layout, but whether and how the compiler can understand the layout as a structured object:

| Approach | Representation of layout | What the compiler can do with it |
|---|---|---|
| **HIP C++** | Index arithmetic such as `A[row*K+k]` | Optimize address arithmetic, but without an explicit layout-algebra object |
| **CK** | C++ template parameters | Compile-time expansion and type checking |
| **FlyDSL** | A first-class IR type, `!fly.layout` | **Algebraic simplification and automatic derivation** |

> **FlyDSL is not valuable merely because it can control layout; HIP C++ has always been able to do that.**
> **Its value is making layout a composable, lowerable IR object while retaining a Python front end.**

### 3. How Triton Handles Layout

Triton's design philosophy is that **developers describe block-level computation and access patterns while the compiler handles most thread-level mapping and lowering**.

A Triton program says, in effect, "this program instance computes this region." Developers can still change block shape, access order, `num_warps`, and autotuning candidates. They do not normally compose a first-class layout expression directly as they would in FlyDSL.

This choice has two consequences:

**Advantage:** the entry cost is low. A developer familiar with NumPy can produce a useful Triton kernel in a few dozen lines.

**Tradeoff:** when thread-level mapping is poor, developers can influence it indirectly through tiling, access patterns, and tuning parameters, but visibility and control are usually lower than in an explicit-layout DSL.

That abstraction is practical for many custom operators. Teams are more likely to accept the extra complexity of fine-grained layout control for hot operators such as GEMM (General Matrix Multiplication) and Attention.

### 4. What FlyDSL Is

![Abstraction ladder from framework operators to assembly](images/s08_08_flydsl_article_img04.png)

*Figure 4. Developers take on progressively more scheduling and layout decisions toward the lower levels. This is an abstraction diagram, not a strict performance ranking.*

The official repository, `github.com/ROCm/FlyDSL`, is Apache-2.0 licensed and hosted by the official ROCm organization. It describes FlyDSL as:

> A Python DSL and a MLIR stack for authoring high-performance GPU kernels with **explicit layouts and tiling**.

The key word is **explicit**.

FlyDSL has two parts:

| Part | Role |
|---|---|
| **FlyDSL** | The Python front end used to write kernels |
| **Fly dialect** | A custom MLIR IR that makes layout a **first-class type** |

That second part is the fundamental distinction from Triton.

The Fly dialect includes types such as:

```
!fly.int_tuple      Integer tuple
!fly.layout         The layout itself is a type
!fly.coord_tensor   Tensor with coordinates
!fly.memref         Memory reference
```

Layout is not a comment or documentation. It is an IR type the compiler can understand, derive, and simplify.

When `divide(A, B)` splits a large matrix into tiles, the compiler knows what is being divided, where each tile lands, and how later accesses translate into addresses. It can simplify those layout expressions algebraically, much as an algebra system simplifies equations.

#### What the Code Looks Like

The following shows the API structure only and omits load, compute, and store operations. Use FlyDSL's official `examples/01-vectorAdd.py` for a runnable version.

```python
import flydsl.compiler as flyc
import flydsl.expr as fx

@flyc.kernel
def my_kernel(A: fx.Tensor, B: fx.Tensor, block_dim: fx.Constexpr[int]):
    tid = fx.thread_idx.x
    bid = fx.block_idx.x
    # Partition with layout algebra.
    tA = fx.logical_divide(A, fx.make_layout(block_dim, 1))
    tA = fx.slice(tA, (None, bid))
    ...

@flyc.jit
def launch(A: fx.Tensor, B: fx.Tensor, n: fx.Int32):
    block_dim = 64
    grid_x = (n + block_dim - 1) // block_dim
    my_kernel(A, B, block_dim).launch(grid=(grid_x, 1, 1), block=(block_dim, 1, 1))
```

The syntax is still Python, but calls such as `logical_divide` and `make_layout` explicitly manipulate layout instead of asking the compiler to infer everything.

#### How It Becomes a GPU Binary

![FlyDSL compilation pipeline from Python to a GPU binary](images/s08_08_flydsl_article_img05.png)

*Figure 5. FlyDSL lowers a Python front end through MLIR and the Fly dialect into the ROCm Device Library (ROCDL) dialect and a GPU binary. Organized from the official Architecture Guide.*

On the first invocation of an uncached signature, `@flyc.jit` rewrites and traces the Python function's AST (Abstract Syntax Tree) into an MLIR module, then lowers it through these stages:

1. **Python function** → AST rewriting + tracing.
2. **MLIR Module**, using dialects such as `fly`, `gpu`, `arith`, `scf`, `memref`, and `vector`.
3. **Fly → ROCDL** (ROCm Device Library, MLIR's low-level dialect for AMD GPUs). Passes such as `fly-layout-lowering` and `fly-canonicalize` lower layout into addresses and GPU operations.
4. **LLVM IR**.
5. **fatbin binary**, cached under `~/.flydsl/cache/`.

The same type signature hits the cache on the next call instead of compiling again.

### 5. Layout Algebra: Three Operations Build the Scheme

![Composition, product, and divide in layout algebra](images/s08_08_flydsl_article_img06.png)

*Figure 6. Composition, product, and divide are the three core classes of layout operation. Organized from the official FlyDSL Layout Guide.*

Once layout is a type, FlyDSL can define algebra over it:

| Operation | Purpose | Typical use |
|---|---|---|
| **composition** | Apply mapping B, then mapping A | View the same data differently, for example through a swizzle |
| **product** | Tile a larger layout with a smaller one | Build a full region from tiles |
| **divide** | Partition a large layout by a tile | Assign regions to blocks, warps, or threads |

Coordinate conversion complements those operations:

- `crd2idx(coord, layout)`: coordinate → address.
- `idx2crd(index, layout)`: address → coordinate.

The idea did not originate at AMD. FlyDSL's official acknowledgements explicitly credit NVIDIA CUTLASS's CuTe layout algebra and the mathematical framework in *Categorical Foundations for CuTe Layouts*.

> A useful approximation is that **FlyDSL occupies a CuTe-like role in the AMD ecosystem, implemented with MLIR and exposed through Python rather than C++ templates.**

The repository even includes `cute` among its topic labels.

### 6. One Algebra Across Four Levels

![Layout hierarchy from a full matrix to blocks, wavefronts, and threads](images/s08_08_flydsl_article_img07.png)

*Figure 7. The same layout relationships span matrix, block, wavefront, and thread levels. Organized from the FlyDSL Kernel Guide.*

High-performance GEMM and Attention kernels conventionally partition data in stages:

```
Full matrix (Global Memory)
    ↓ divide
Block tile (moved into LDS shared memory)
    ↓ divide
Warp tile (assigned to a group of wavefronts)
    ↓ divide
Thread fragment (placed in registers and fed to MFMA)
```

Every level uses the same `divide` operation with different parameters.

Because each level has an explicit layout, an optimization can be inserted at any point:

- Use a **vectorized copy** for Global → LDS transfers, moving 128 bits at a time.
- Apply an LDS **swizzle** to spread addresses and avoid bank conflicts.
- Align register tiles with the **MFMA** shape so matrix instructions stay fully occupied.
- Schedule **prefetch** operations so data movement overlaps computation.

Triton delegates these four levels to the compiler. FlyDSL exposes each level for direct control.

### 7. Triton and FlyDSL Side by Side

![Triton and FlyDSL compared by control interface](images/s08_08_flydsl_article_img08.png)

*Figure 8. Their primary difference is the control interface, not a simple ordering by performance. Organized from the official programming models.*

| | Triton | FlyDSL |
|---|---|---|
| **What you write** | Block-oriented computation | Layout-oriented partitioning and movement |
| **Who determines layout** | Compiler derivation | **Developer writes it explicitly** |
| **How you tune** | Change `BLOCK_SIZE` / `num_warps` | Change layout, swizzle, and MFMA arrangement |
| **Learning curve** | Lower | Higher |
| **Control granularity** | Block-level program plus compiler derivation | Explicit layout, tiling, and data movement |
| **Front end** | Python | Python |
| **Compiler stack** | Its own, based on MLIR | MLIR with the Fly dialect |

The broader implementation spectrum is:

| Approach | Who determines layout | Language |
|---|---|---|
| PyTorch operators | Framework | — |
| Triton | Compiler | Python |
| **FlyDSL** | **Developer** | **Python** |
| CK (Composable Kernel) | Developer | C++ templates built on HIP C++ |
| HIP C++ | Developer | C++ with hand-written index arithmetic |
| Hand-written assembly | Developer | Assembly |

**ROCm is deliberately absent from this table.** It is the platform on which every AMD-side row runs.

FlyDSL occupies an unusual position: Python expresses an explicit layout and exposes control commonly found in C++ template kernels.

That position explains why it exists. Engineering teams wanted an interface between a high-level Python DSL and C++ template kernels that could express layout and enter an MLIR compilation pipeline. Actual performance still depends on the concrete kernel, shape, compiler version, and hardware.

### 8. FlyDSL in a Real Inference Stack

FlyDSL is not isolated research code. It has been integrated into ROCm operator libraries.

AITER contains an `aiter.ops.flydsl` module. Examples under `aiter/ops/flydsl/` include:

| File | Operator |
|---|---|
| `fmha_kernels.py` | FMHA (Fused Multi-Head Attention) |
| `gemm_kernels.py` | GEMM |
| `moe_kernels.py` | MoE (Mixture of Experts) |
| `moe_sorting.py` | MoE sorting |
| `mla_reduce_kernels.py` | MLA (Multi-Head Latent Attention) reduce |
| `linear_attention_kernels.py` | Linear attention |

A common integration pattern makes the implementation optional and selects it through a switch:

```python
from aiter.ops.flydsl.utils import is_flydsl_available

if is_flydsl_available():
    # Use the FlyDSL implementation
else:
    # Fall back to the CK / HIP implementation
```

The MLA reduce file states the contract directly:

> Drop-in alternative for the HIP `aiter.mla_reduce_v1`: same signature and in/out contract. Opt-in via `AITER_MLA_REDUCE_FLYDSL=1`; **production keeps the HIP kernel by default.**

One operator therefore has two implementations. An environment variable chooses between them, while production retains the conservative path by default. This is the concrete form of the earlier rule that selecting `aiter` does not identify one kernel.

Inference frameworks such as SGLang expose similar switches, including selection of a FlyDSL Paged Attention Decode implementation and parameters such as partition count.

#### Three Engineering Failure Modes

**1. JIT compilation has a cost.**

The first invocation of a shape triggers compilation, so the first few requests after service startup can be noticeably slower.

AITER therefore provides **AOT precompilation** under `aiter/aot/flydsl/`. It collects kernel entries from tuned CSV (Comma-Separated Values) configurations and writes them into the cache ahead of time. A latency-sensitive service can verify and adopt that path for the kernel families it actually uses rather than assuming every operator was prewarmed.

**2. The cache can mislead you.**

Compiled artifacts live in `~/.flydsl/cache/`. Changes to a C++ pass or to a helper function outside a closure do **not necessarily** invalidate the cache automatically.

The official remedies are `rm -rf ~/.flydsl/cache` or `export FLYDSL_RUNTIME_ENABLE_CACHE=0`.

> Record the cache policy before a performance comparison. If source changed but the binary did not, the measurement can still be exercising the old implementation.

**3. Version drift is the most dangerous variable.**

FlyDSL is evolving rapidly. The transition from 0.2.x to 0.3.x has already included **breaking API changes**.

The `flydsl_compat.py` file in ROCm/mori records them explicitly:

> 0.3.0 dropped `flydsl.expr.vector` and `flydsl.expr.buffer_ops`, and turned `T.<dtype>` from a factory into a property.

ROCm/mori therefore documents two removed modules and a change in how `T.<dtype>` is invoked while supporting both 0.2.x and 0.3.x.

Two machines with different FlyDSL versions may not execute the same kernel implementation. A performance comparison that aligns only "AITER enabled" and "FlyDSL enabled," but not the FlyDSL version, is invalid.

> **Operational rule:** every ROCm inference performance manifest should record `flydsl.__version__` alongside the ROCm, SGLang, and AITER commits. Omitting any one of them weakens the conclusion.

### 9. Three Frequently Asked Questions

#### Q1: Is FlyDSL Only for KV Cache or Attention?

No. It is a general GPU kernel DSL with a much broader scope.

![Public FlyDSL coverage across multiple operator families](images/s08_08_flydsl_article_img09.png)

*Figure 9. Public repositories already contain several classes of FlyDSL kernels. The list describes current public coverage; it does not claim that any arbitrary program can be ported without conditions. Sources: ROCm/FlyDSL and ROCm/aiter.*

The official FlyDSL test surface includes:

| Category | Operators |
|---|---|
| Matrix multiplication | GEMM, MoE GEMM, Batched GEMM, Preshuffle GEMM |
| Attention | FlashAttention, PagedAttention, MLA reduce |
| Normalization / element-wise | LayerNorm, RMSNorm, Softmax, Quantization |
| Fused operators | Fused RoPE + KV cache |
| Communication | AllReduce, dispatch / combine |
| Fundamentals | **VecAdd, addition of two arrays** |

VecAdd makes the point clearly: FlyDSL can express even the most basic vector operation.

> **It is a DSL for GPU kernels, not for one particular operator.** C is not an "operating-system operator" merely because operating systems are often written in C.

Triton and CK are general in the same sense. Their public examples concentrate on GEMM and Attention because those are the inference workloads most often in need of optimization.

#### Q2: Why Does RoPE Seem to Be Missing?

**FlyDSL already has fused RoPE (Rotary Position Embedding) implementations.**

AITER exposes these examples:

| File | Contents |
|---|---|
| `aiter/ops/flydsl/kernels/qk_norm_rope_quant.py` | **QK (Query/Key) Norm + RoPE + quantization in one operator** |
| `qk_norm_rope_quant_gfx1250.py` | Specialized implementation for a particular architecture |
| `fused_compress_attn.py` | RMSNorm + GPT-J RoPE + write into paged KV cache |
| FlyDSL repository `test_fused_rope_cache.py` | Fused RoPE + KV cache |

The exported function is named `flydsl_qk_norm_rope_quant`.

Why is an independent kernel named `RoPE` often absent? When the adjacent dataflow permits fusion, one or more intermediate reads and writes can be removed.

RoPE applies a position-dependent rotation to pairs of channels and is usually less compute-intensive than the main Attention operation. A standalone kernel creates its own read and write path:

```
Read device memory → compute (quickly) → write device memory
```

When the intermediate tensor serves only the next step, the common optimization is to fuse it into the neighbor:

```
One device-memory read → QK-Norm → RoPE → quantization → write to KV cache → one device-memory write
```

Data enters and leaves device memory only once, while intermediate values remain in registers.

> The absence of a standalone RoPE kernel does not establish that RoPE was skipped. Public code proves that fused paths exist; whether a standalone kernel is used still depends on shape, reuse, framework scheduling, and target hardware.

This also explains why explicit-layout tools matter. A fused operator can combine the reduction layout of normalization, paired-channel layout of RoPE, tiled layout of quantization, and paged layout of the KV Cache. Explicit layout algebra makes those relationships easier to compose and audit.

#### Q3: What Is the NVIDIA Counterpart to FlyDSL?

**CuTe DSL is the closest counterpart.** Both provide a Python front end and explicit layout abstractions, but they are not API-compatible implementations or official one-to-one ports.

![CuTe DSL and FlyDSL in corresponding ecosystem positions](images/s08_08_flydsl_article_img10.png)

*Figure 10. CuTe DSL is the closest NVIDIA-side reference point for FlyDSL. They are neither the same project nor compatible APIs. Sources: official NVIDIA CUTLASS and ROCm/FlyDSL documentation.*

| Layer | NVIDIA | AMD |
|---|---|---|
| Platform | CUDA | ROCm |
| Kernel language | CUDA C++ | HIP C++ |
| C++ template library | CUTLASS / CuTe | CK |
| **Python DSL** | **CuTe DSL** | **FlyDSL** |
| Operator library | cuDNN / FlashInfer | AITER |
| Cross-platform DSL | Triton | Triton |

Their mechanisms also line up in several places:

| | CuTe DSL | FlyDSL |
|---|---|---|
| Decorators | `@cute.kernel` / `@cute.jit` | `@flyc.kernel` / `@flyc.jit` |
| Compilation route | AST rewriting + tracing → **MLIR** | AST rewriting + tracing → **MLIR** |
| JIT cache | `CUTE_DSL_CACHE_DIR` | `~/.flydsl/cache` |
| Disable cache | `CUTE_DSL_DISABLE_FILE_CACHING` | `FLYDSL_RUNTIME_ENABLE_CACHE=0` |

The official CUTLASS documentation says:

> CuTe DSL is the Python-native interface to CUTLASS 4.4+... It exposes the **same CuTe abstractions (layouts, tensors, thread-to-data mappings)** that power CUTLASS's C++ template library, but authored entirely in Python.

The official FlyDSL README explicitly acknowledges CuTe layout algebra among its intellectual sources. The careful statement is therefore: **CuTe DSL is the most useful NVIDIA-side reference point for understanding FlyDSL.**

> Both ecosystems reached a similar conclusion at this layer: layout should be a first-class object the compiler understands, and the entry point should be Python.

### 10. When to Use FlyDSL

Most people do not need to write FlyDSL.

| Situation | Practical choice |
|---|---|
| Building applications or adapting models | Use existing libraries; you may not need to write Triton either |
| Accelerating a custom operator | **Triton** usually offers the best cost-to-benefit ratio |
| A core operator has reached a performance ceiling | Consider FlyDSL |
| A hot kernel needs finer layout control and the team has kernel-engineering expertise | FlyDSL or CK |
| Investigating why two machines produce different performance | **At least know that this layer exists** |

For most readers, FlyDSL's value is not that they will write a kernel with it. The value is knowing that this layer exists beneath the inference stack, that it changes with versions, and that it can be one source of performance differences.

### Summary

1. **Layout is central.** Memory order determines whether bandwidth can be used effectively: `Index = Coord · Stride`.
2. **ROCm is not an authoring style.** It corresponds to CUDA as a platform; the counterpart to CUDA C++ is **HIP C++**.
3. **Triton derives more layout decisions; FlyDSL lets the developer write them explicitly.** This is the root of their division of responsibility.
4. **Three representations expose developer-controlled layout at different levels:** index arithmetic in HIP C++, template parameters in CK, and a first-class IR type in FlyDSL.
5. **FlyDSL = a Python front end + MLIR's Fly dialect.** Layout becomes a first-class type the compiler can derive and simplify.
6. **Three algebraic operations**, `composition`, `product`, and `divide`, span the block → warp → thread hierarchy.
7. **These are general kernel-development tools**, not KV Cache-specific tools; public code also contains fused RoPE implementations.
8. **CuTe DSL is the closest NVIDIA-side reference point.** The concepts are similar, but the implementations are not compatible.
9. **Three engineering hazards matter:** first-use JIT latency, cache entries that may not invalidate automatically, and breaking changes across minor versions. Pin the version.

### Five Self-Check Questions

1. For the same 2×4 matrix, where does coordinate `(1,2)` map under `Stride=(4,1)` and `Stride=(1,2)`?
2. Triton can influence performance through tiling, access order, and autotuning. How does that differ from manipulating a first-class layout expression directly?
3. HIP C++ already controls address mapping. What additional value does FlyDSL provide?
4. Why does the existence of a fused RoPE kernel not imply that every workload should avoid a standalone RoPE kernel?
5. Two machines both have AITER and enable FlyDSL, yet performance differs materially. Which variable should you check first besides the hardware?

### References

All sources below are public:

- Official FlyDSL repository: https://github.com/ROCm/FlyDSL (Apache-2.0)
- Official FlyDSL documentation: https://rocm.github.io/FlyDSL
- Official AITER repository: https://github.com/ROCm/aiter (MIT)
- Official Composable Kernel repository: https://github.com/ROCm/composable_kernel (MIT)
- NVIDIA CUTLASS / CuTe DSL: https://docs.nvidia.com/cutlass/latest/media/docs/pythonDSL/cute_dsl.html
- ROCm/mori FlyDSL 0.2.x/0.3.x compatibility record: https://github.com/ROCm/mori/blob/main/python/mori/ops/dispatch_combine_v2/flydsl_compat.py
- RoFormer / RoPE paper: https://arxiv.org/abs/2104.09864
- CuTe layout algebra: *Categorical Foundations for CuTe Layouts*
<!-- SOURCE-END-EN id=08 -->

---

<!-- SOURCE-BEGIN-EN id=09 -->
## Source #9: Operators, Kernels, and Functions: From Excel SUM to GPU Assembly

> These terms appear everywhere, yet simple questions expose the confusion. Is an operator a function? Is AITER an attention mechanism? Why does FlyDSL exist when HIP C++ already does? Starting from an everyday tool makes the six layers concrete.

The preceding chapter separated Triton, FlyDSL, CK, and HIP C++. It prompted three recurring questions:

- What exactly is an operator? Is it just a compiled function?
- Why is AITER an operator library rather than an attention mechanism?
- If HIP C++ exists, why did AMD create FlyDSL?

They are all versions of one question: **which layer does each term belong to?**

### Terms to Define First

| Abbreviation | Full name | Meaning here |
|---|---|---|
| **Kernel** | — | The compiled code that actually runs on the GPU; unrelated to an operating-system kernel |
| **GPU** | Graphics Processing Unit | An accelerator designed to perform very large numbers of small operations concurrently |
| **CUDA** | Compute Unified Device Architecture | NVIDIA's GPU software platform |
| **ROCm** | Radeon Open Compute platform | AMD's GPU software platform, occupying the corresponding role to CUDA |
| **HIP** | Heterogeneous-compute Interface for Portability | The native C++ interface for writing kernels on ROCm |
| **AITER** | AI Tensor Engine for ROCm | AMD's operator library, not one algorithm |
| **CK** | Composable Kernel | AMD's C++ template kernel library |
| **DSL** | Domain-Specific Language | A language designed for a particular class of work |
| **GEMM** | General Matrix Multiply | General matrix multiplication, one of deep learning's most compute-intensive operations |
| **MoE** | Mixture of Experts | A model structure in which each token is routed through only a subset of expert subnetworks |
| **cuBLAS** | CUDA Basic Linear Algebra Subprograms | NVIDIA's linear-algebra operator library |

If you retain only one distinction, retain this one: **an operator defines what to compute; a kernel defines how a particular implementation computes it.**

### 1. Start with Excel SUM

Enter this formula in Excel:

```
=SUM(A1:A100)
```

Pressing Enter hides six layers of work:

| Layer | What happens |
|---|---|
| ① What you write | `=SUM(A1:A100)` |
| ② What receives it | Excel's formula engine recognizes `SUM` |
| ③ Where the implementation lives | Excel's built-in function library |
| ④ Which implementation is selected | 100 values may use a simple loop; one million may use a parallel path |
| ⑤ What actually executes | A block of **machine code compiled long ago** |
| ⑥ Where it executes | CPU |

Two facts matter.

First, Microsoft engineers wrote and compiled the code at layer ⑤ years before the user pressed Enter.

Second, one `SUM` can map to more than one implementation. Different data sizes can select different paths.

Excel's internal implementation is not public; the analogy uses only this structural model.

### 2. The GPU Path Has the Same Structure

![Excel and GPU invocation chains mapped layer by layer](images/s09_09_operator_kernel_article_img01.png)

*Figure 1. The Excel invocation chain maps directly onto a GPU invocation chain.*

Now enter this in Python:

```python
C = torch.matmul(A, B)
```

The layers align:

| Layer | Excel | GPU |
|---|---|---|
| ① What you write | `=SUM(A1:A100)` | `torch.matmul(A, B)` |
| ② What receives it | Formula engine | **PyTorch**, or an engine such as vLLM / SGLang |
| ③ Where it looks | Built-in function library | **Operator library**, such as cuBLAS / AITER |
| ④ What it selects | Based on data size | Table lookup by **matrix dimensions, precision, and GPU model** |
| ⑤ What actually executes | Compiled machine code | A compiled **GPU kernel** |
| ⑥ Where it executes | CPU | **GPU**, launched through CUDA / ROCm |

The selection table at layer ④ was not improvised at runtime. Vendors benchmarked thousands of parameter combinations on physical hardware in advance and recorded which implementation to use under which conditions.

### 3. Operator, Kernel, and Operator Library

![One operator with multiple kernels selected by an operator library](images/s09_09_operator_kernel_article_img02.png)

*Figure 2. One operator can map to multiple kernels; an operator library stores and selects them.*

Three definitions establish the model:

| Term | Definition | Excel counterpart |
|---|---|---|
| **Operator** | A named computation and its input/output contract: what to compute | `SUM` |
| **Kernel** | The compiled code that actually executes | The machine-code implementation of SUM |
| **Operator library** | A collection of kernels plus selection logic | Excel as the software that contains the functions |

#### Is an Operator a Compiled Function?

Not exactly, although the intuition is partly right.

The "compiled function" corresponds to a **kernel**. An **operator** sits one level above it: the name and specification of the work, including its inputs and outputs.

One operator often has several kernels. Matrix multiplication might have:

- an FP16 kernel for H100;
- a BF16 kernel for MI300X;
- an implementation specialized for small matrices;
- an implementation specialized for large matrices.

The operator is one concept; the runtime chooses among many kernels.

The reverse also occurs: **one kernel can implement several operators at once** through fusion.

#### A Simple Classification Test

Ask whether it is something you can call:

- You can write `=SUM(...)`, so SUM is an operator.
- You cannot write `=Excel(...)`, because Excel contains operators rather than being one.
- You can write `torch.matmul(...)`, so `matmul` is an operator.
- You cannot call "AITER" as one operation. AITER is the library from which a specific operator is selected.

### 4. Is AITER an Attention Mechanism?

No. **AITER is an operator library.**

The confusion is understandable because many neighboring names contain "Attention." A quick view of AITER's operator tests shows its breadth:

| File | Operator |
|---|---|
| `test_mha.py` | Attention |
| `test_mla.py` | Another Attention variant |
| `test_moe.py` | Mixture of Experts |
| `test_gemm_a8w8.py` | Matrix multiplication |
| `test_rmsnorm2d.py` | Normalization |

AITER's own description includes Attention, MoE, GEMM, normalization, quantization, communication, and other operators. Attention is only one part of the library.

The Excel analogy makes the category error obvious: WPS is not SUM. In the same way, AITER is not Attention; it contains Attention implementations alongside matrix-multiplication and MoE implementations.

### 5. "Attention" Can Name Six Different Layers

![Six meanings of Attention across the stack](images/s09_09_operator_kernel_article_img03.png)

*Figure 3. The same word points to different layers in different contexts.*

| Layer | What it denotes | Concrete meaning |
|---|---|---|
| **① Mechanism** | A **modeling idea** | Lets a model processing one token attend to other relevant tokens in the sequence |
| **② Architecture variant** | Different forms of the mechanism | Multi-head (MHA), multi-query (MQA), grouped-query (GQA), latent attention (MLA), sliding window |
| **③ Mathematical expression** | A formula | softmax(Q·K transpose / √d)·V |
| **④ Framework operator** | A callable unit | `scaled_dot_product_attention()` |
| **⑤ Computational algorithm** | A method for faster computation or lower memory use | FlashAttention, PagedAttention |
| **⑥ Kernel** | The compiled executing code | `fmha_kernels` in AITER |

One word is doing six jobs:

- In a paper, Attention usually means layer ①.
- In model configuration, it usually means layer ②, such as MHA versus GQA.
- In framework code, it often means layer ④.
- In performance work, it often means layers ⑤ and ⑥.

The question "Is AITER Attention?" therefore mixes levels. The source places AITER's concrete implementations around layer ⑥ while the Attention mechanism is layer ①, five conceptual levels away. It is like asking whether an automobile factory is four-wheel drive.

#### Attention Is Not a Single SUM

`SUM` is one step. **Attention has five:**

```
Q @ K transpose  →  ÷√d  →  add mask  →  softmax  →  @ V
```

In Excel terms, it resembles a sheet with intermediate columns rather than a single `SUM`:

| Column A | Column B | Column C | Column D | Column E |
|---|---|---|---|---|
| Original data | Pairwise multiplication of A | Divide B by a constant | Normalize C | Multiply D by weights |

E is the answer; B, C, and D are intermediate results.

The naive GPU approach materializes B, C, and D. For a long sequence, the intermediate matrix at B can occupy tens of GB and must be written to device memory and read back.

FlashAttention removes those materialized columns. It fuses the five steps into one kernel and keeps intermediate results in fast on-chip storage.

> The saving is not arithmetic work; it is the time spent repeatedly moving data, one of the most expensive parts of large-model inference.

This is also an example of one kernel implementing several operators through fusion.

### 6. Why GPUs Need Specialized Programming Models

An ordinary C++ implementation is enough for Excel SUM. Why does GPU matrix multiplication involve Triton, FlyDSL, CK, and HIP C++?

The CPU and GPU execute work differently. A conventional high-level language by itself does not express the GPU's division of labor.

![CPU sequential work versus GPU parallel ownership](images/s09_09_operator_kernel_article_img04.png)

*Figure 4. CPU code primarily describes steps; GPU code must also describe work ownership.*

| | CPU | GPU |
|---|---|---|
| Number of cores | A few to a few dozen | **Tens of thousands** |
| Each core | Powerful enough for complex work | Individually simple |
| Execution style | Perform tasks sequentially | **Very many workers perform the same operation concurrently** |
| What the program must state | **Steps**: do this, then that | **Division of labor**: which worker owns which data |

A useful analogy is that a CPU resembles one graduate student who can follow a task list from start to finish. A GPU resembles ten thousand elementary-school students performing the same simple task; each must be told which item to handle and how the results come together.

#### One Line Exposes the Difference

![GPU code begins by calculating a worker identifier](images/s09_09_operator_kernel_article_img05.png)

*Figure 5. GPU code must first establish which worker the current thread represents.*

**CPU sum:**

```cpp
float sum = 0;
for (int i = 0; i < N; i++)
    sum += a[i];
```

One worker processes the array from beginning to end.

**GPU sum:**

```cpp
__global__ void sum_kernel(float* a, float* out) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    atomicAdd(out, a[i]);
}
```

The first statement computes "which worker am I?" Thousands of workers execute the same code, so each must identify the data it owns.

Ordinary C++, Python, and .NET do not natively contain that GPU worker-identity model. GPU-specific programming interfaces supply it.

### 7. Does FlyDSL Bypass ROCm?

No. **It still runs through ROCm.**

![HIP C++, Triton, and FlyDSL converge on AMD GPU machine code](images/s09_09_operator_kernel_article_img06.png)

*Figure 6. Three authoring paths compile to the same kind of machine code and are loaded by the same runtime.*

HIP C++, Triton, and FlyDSL all become AMD GPU machine code, which ROCm loads onto the GPU. FlyDSL is not a substitute for ROCm; it is another authoring path into the ROCm stack.

Word, Markdown, and LaTeX can all produce PDF. Their coexistence is unsurprising because different authoring models are efficient for different work. GPU programming tools differ for the same reason.

#### Why Not Write Everything in HIP C++?

HIP C++ can express all of it, but high-performance kernels become painful to maintain. This is an issue of **expressive efficiency**, not capability.

A high-performance matrix multiplication in HIP C++ requires manual work such as:

```cpp
// 1. Which data tile each thread owns -- calculated manually
int row = (blockIdx.y * 128) + (threadIdx.x / 16) * 8;
int col = (blockIdx.x * 128) + (threadIdx.x % 16) * 8;

// 2. Move data from device memory to shared memory -- addresses written manually
lds[threadIdx.x * 4 + 0] = A[row * K + k + 0];
// ... dozens more lines

// 3. Offset addresses to avoid bank conflicts -- bit operations written manually
int swizzled = (idx ^ ((idx >> 5) & 7)) * 4;

// 4. Double-buffered prefetching, synchronization, and matrix-instruction layout -- hundreds more lines
```

A high-performance GEMM can easily reach thousands of HIP C++ lines. The address expressions are error-prone, and changing one tiling parameter can require recalculating all of them.

The FlyDSL expression is much shorter:

```python
tile = logical_divide(A, make_layout((128, 32)))   # Specify how to tile
frag = tiled_copy.partition_S(tile)                # Specify who owns each tile
```

The developer describes the partition; the compiler generates the address arithmetic.

#### The Actual Division of Responsibility

![Who chooses tiling and who writes address arithmetic](images/s09_09_operator_kernel_article_img07.png)

*Figure 7. The three approaches expose different levels of control and code generation.*

| | Who chooses the tiling rule? | Who writes the address arithmetic? |
|---|---|---|
| **HIP C++** | Developer | **Developer, manually** |
| **FlyDSL** | Developer | Compiler |
| **Triton** | **Compiler** | Compiler |

HIP C++ and FlyDSL provide comparable control over the decomposition in this model; the difference is who writes the address calculations.

Triton delegates even the partitioning decision to the compiler in this simplified comparison. That is convenient for many operators. For especially performance-sensitive matrix multiplication and Attention kernels, engineers may want direct control over partitioning.

Assembly and C can both express a program, yet business applications are not normally written in assembly. Expressive efficiency matters even when capability is equivalent.

#### Is FlyDSL Faster Than CK?

No general language-level conclusion follows. **Their performance ceiling is the same in the source's model.**

All four paths eventually produce GPU machine code:

| Authoring path | Source language | Compiles to |
|---|---|---|
| HIP C++ | C++ | GPU machine code |
| CK | C++ templates | GPU machine code |
| Triton | Python | GPU machine code |
| FlyDSL | Python | GPU machine code |

The Python layer is absent at GPU runtime. It was syntax used during authoring and compilation; no Python interpreter executes on the GPU.

AMD gains **iteration speed**, not a faster source language.

Kernel tuning is a search over tile sizes, data arrangements, loop unrolling, and thousands of combinations. Nobody selects the optimum on the first attempt.

- Changing one C++ template parameter can require minutes of recompilation.
- Changing one Python line can produce a new test quickly.

In one afternoon, one engineer may test 5 combinations while another tests 50. The larger search is more likely to find a better implementation.

**The language is not faster; the iteration loop is faster.**

When a benchmark reports that FlyDSL beat CK, first ask:

> **Was the compared CK implementation tuned for the same case?**

Two common explanations are:

| Reported result | Possible actual cause |
|---|---|
| FlyDSL is faster than CK | The FlyDSL implementation was tuned for this matrix shape; the CK implementation was generic |
| FlyDSL is faster than CK | FlyDSL adopted a new hardware instruction before CK did |

The specific implementation is faster, not the language in the abstract. Change the matrix shape and the result can reverse.

"FlyDSL is faster than ROCm" is a category error: it compares a steering interface with the road and vehicle substrate.

### 8. Keep the Two Chains Separate

![Runtime invocation chain versus kernel production chain](images/s09_09_operator_kernel_article_img08.png)

*Figure 8. Invoking a kernel at runtime and building a kernel are different chains.*

**Runtime, every time a model executes:**

```
① Python call
② Framework: PyTorch / vLLM
③ Operator library: cuBLAS / AITER
④ Select a Kernel from a lookup table
⑤ Precompiled Kernel
⑥ ROCm / CUDA → GPU
```

**Library construction, months earlier in a vendor lab:**

```
Kernel engineer
    ↓ writes it with Triton / FlyDSL / CK / HIP C++ / assembly
    ↓ tunes thousands of parameter combinations on physical hardware
    ↓ packages it into an operator library
```

Triton and FlyDSL normally appear only in the second chain. A model invocation consumes the compiled product.

The exception is `torch.compile`, which can generate Triton code and compile it on the spot. That is just-in-time preparation rather than selection from an entirely prebuilt menu.

### Put Every Term in Its Layer

| Term | Layer | One-line meaning |
|---|---|---|
| **Attention mechanism** | Modeling concept | An architectural idea, not a node in the invocation chain |
| **Attention operator** | ①② | The callable framework unit |
| **FlashAttention** | Algorithm at ⑤ | A method that fuses five steps |
| **Operator** | ② | The specification of what to compute |
| **Kernel** | ⑤ | The compiled code that actually executes |
| **Operator library** | ③ | A collection of kernels plus selection logic |
| **cuBLAS / AITER** | ③ | Two concrete operator libraries |
| **Triton / FlyDSL / CK** | Build chain | Tools used to create kernels; normally absent from the runtime chain |
| **CUDA / ROCm** | ⑥ | The platform substrate that loads kernels onto the GPU |
| **Assembly** | Near ⑥ | The lowest-level authoring form; kernels ultimately become machine instructions |

### Summary

1. `torch.matmul` is a name that flows through a framework, an operator library, and selection logic before reaching precompiled GPU code. Structurally, it resembles Excel `SUM`.
2. An **operator** specifies what to compute; a **kernel** is compiled executing code; an **operator library** stores many kernels and selects among them. One operator can have many kernels, and one fused kernel can implement several operators.
3. **AITER is an operator library, not an Attention mechanism.** The word Attention itself spans six layers, so the intended layer must be stated.
4. GPUs need specialized programming models because the program must describe how very many workers divide the data, not only a sequence of steps.
5. **FlyDSL does not bypass ROCm.** Like HIP C++ and Triton, it eventually compiles to AMD GPU machine code.
6. The practical difference is who chooses tiling and who writes the address arithmetic. All paths have enough expressive power; they differ in code volume and error exposure.
7. The authoring language does not determine the performance ceiling; it changes how quickly engineers can search for a strong implementation. When "A beats B," ask whether B was tuned.
8. Runtime invocation and kernel production are different chains. Triton and FlyDSL normally belong to the production chain.

### Four Self-Check Questions

1. Why is an operator not the same thing as a compiled function? Which layer separates them?
2. Can one kernel implement several operators? Give an example.
3. Why is ordinary C++ sufficient for Excel SUM while GPU matrix multiplication needs a GPU programming model?
4. If FlyDSL and HIP C++ expose comparable control, what value does FlyDSL add?
5. Someone reports, "FlyDSL is 30% faster than CK." What should you ask first?

### References

All sources below are public:

- Official AITER repository: https://github.com/ROCm/aiter (MIT)
- Official FlyDSL repository: https://github.com/ROCm/FlyDSL (Apache-2.0)
- Official Composable Kernel repository: https://github.com/ROCm/composable_kernel (MIT)
- Official Triton repository: https://github.com/triton-lang/triton
- Official PyTorch repository: https://github.com/pytorch/pytorch
- RoFormer / RoPE paper: https://arxiv.org/abs/2104.09864
<!-- SOURCE-END-EN id=09 -->

---

<!-- SOURCE-BEGIN-EN id=10 -->
## Source #10: The Same Matrix Multiplication Can Be 32 Times Slower When Data Is Laid Out Poorly

> After the previous chapter, three questions kept returning: how can a Python-authored kernel avoid being slower than C++? What does the resulting "machine code" look like? If FlyDSL controls data placement, how does that control create speed? This chapter answers all three and places the corresponding NVIDIA tools beside the AMD stack.

### Terms to Define First

| Abbreviation | Full name | Meaning here |
|---|---|---|
| **Kernel** | — | The compiled code that actually runs on the GPU; unrelated to an operating-system kernel |
| **GPU** | Graphics Processing Unit | An accelerator designed to perform very large numbers of small operations concurrently |
| **ISA** | Instruction Set Architecture | The complete instruction vocabulary understood by a chip |
| **gfx942** | — | The instruction-set target used by the MI300X GPU |
| **HBM** | High Bandwidth Memory | Device memory: large, but physically farther from the compute units |
| **LDS** | Local Data Share | Small, fast on-chip shared memory; NVIDIA calls the corresponding storage shared memory |
| **CK** | Composable Kernel | AMD's C++ template kernel library |
| **DSL** | Domain-Specific Language | A language designed for one class of work |
| **GEMM** | General Matrix Multiply | General matrix multiplication, one of deep learning's most compute-intensive operations |
| **LLVM IR** | LLVM Intermediate Representation | A compiler intermediate form where multiple source languages converge |
| **MLIR** | Multi-Level Intermediate Representation | A multi-level compiler framework above LLVM IR |

If you retain only one point, retain this one: **matrix multiplication is often slow not because the arithmetic is slow, but because the data does not reach the arithmetic units in time.**

### 1. Why a Python-Authored Kernel Need Not Be Slower Than C++

FlyDSL uses Python syntax and is more concise than HIP C++. It is tempting to infer that the source language itself makes the kernel faster. That inference is wrong. **The performance ceiling is the same because the GPU ultimately executes the same kind of machine code.**

![Four authoring paths converging on one instruction set](images/s10_10_data_movement_article_img01.png)

*Figure 1. Four authoring paths ultimately produce the same kind of machine code.*

The paths converge earlier in compilation at **LLVM IR**. The same AMDGPU backend then lowers them to gfx942 instructions.

The Python layer does not exist at GPU runtime. Python is the authoring syntax; after compilation, no Python interpreter and no line of Python executes on the GPU.

If the source language does not survive into the machine code, it cannot by itself determine execution speed.

### 2. What the Machine Code Looks Like

The phrase "same machine code" is easier to understand when the instructions are visible.

![Representative MI300X machine instructions](images/s10_10_data_movement_article_img02.png)

*Figure 2. Instructions of the kind that execute on MI300X.*

A textual disassembly looks approximately like this:

```
global_load_dwordx4    v[8:11], v[2:3], off      move 16 bytes from device memory
ds_read_b128           v[12:15], v20             read a block from on-chip shared memory
v_mfma_f32_32x32x8f16  a[0:15], v[8:9], v[12:13] matrix multiply-add; one instruction replaces many
s_waitcnt              lgkmcnt(0)                wait for data to arrive before continuing
```

To inspect a compiled object directly, disassemble it with `llvm-objdump --disassemble --mcpu=gfx942`.

One common misconception must be corrected here:

> **gfx942 belongs to the hardware, not to ROCm.**

| | What it is | Who defines it |
|---|---|---|
| gfx942 | The instruction vocabulary understood by the chip | AMD hardware, fixed in the silicon |
| `v_mfma` | One instruction in gfx942 | AMD hardware |
| ROCm | Compiler + driver + runtime | AMD software |

ROCm is the translator; gfx942 is the chip's native language. Removing ROCm would not change the ISA understood by the silicon. ROCm translates source into that ISA and submits the resulting program for execution; it does not define the ISA.

### 3. If Language Does Not Set Speed, What Does?

The core constraint in matrix multiplication is straightforward:

> **Compute is abundant; getting data to the compute units on time is the problem.**

MI300X has powerful compute units, but without data they sit idle. An untuned matrix multiplication is often limited by movement rather than arithmetic.

The recurring optimization tasks are therefore: **move data fewer times** and **avoid serialization after it arrives**.

![HBM, LDS, and registers represented as three kitchen locations](images/s10_10_data_movement_article_img03.png)

*Figure 3. Three storage levels represented as three locations in a kitchen.*

The cooks are extremely fast, but they cannot work without ingredients. Much of matrix-multiplication time can be spent waiting for data rather than performing multiply-add operations.

### 4. First Principle: Move Data Fewer Times

The naive approach visits the warehouse for every single ingredient. Most of the cook's time is then spent waiting.

The better approach carries up a basket, reuses everything in it as much as possible, then fetches the next basket.

![One transfer per use versus tiled reuse](images/s10_10_data_movement_article_img04.png)

*Figure 4. Loading once for one use versus loading a tile once and reusing it fully.*

Matrix multiplication requires this because the same row of A contributes to an entire row of C and can be reused thousands of times. Loading once and using a thousand times is fundamentally different from loading once per use.

The on-chip work surface cannot hold the entire warehouse, so the size of each basket must be chosen carefully.

This is **tiling**.

### 5. Second Principle: Avoid Queues After Data Arrives

Once data reaches shared memory, its arrangement still matters.

Shared memory is divided into **32 banks** and can serve 32 requests to distinct banks concurrently.

![Bank-conflict serialization caused by data placement](images/s10_10_data_movement_article_img05.png)

*Figure 5. The same data under different placements can differ by a factor of 32 in the worst serialization pattern shown.*

Imagine 32 cooks around a work surface. If every cook needs something from one corner, they queue. If the ingredients are spread across 32 independent locations, they can all reach at once.

With the same data, computation, and instructions, one arrangement can complete the accesses in 1 turn while another serializes them across 32 turns. The compute units remain idle during that queue.

This is a **bank conflict**.

There is another concrete benefit to a compatible layout. The `v_mfma` instruction requires operands to be distributed across registers in a hardware-defined pattern: specific threads must own specific elements. If the layout loaded from shared memory does not match that requirement, an additional rearrangement is needed before the instruction can consume the values.

Laying out the data in the `v_mfma`-required form from the beginning removes that otherwise wasted rearrangement.

### 6. Who Controls Tiling and Layout?

FlyDSL does not control the mathematical matrix operation. It controls **how data is arranged and delivered to that operation**.

The hardware supplies the `v_mfma` instruction, which the programming model cannot change. FlyDSL controls the path that prepares data for that instruction.

![Responsibility for tiling, layout, and address arithmetic](images/s10_10_data_movement_article_img06.png)

*Figure 6. HIP C++, FlyDSL, and Triton divide responsibility for tiling, placement, and address generation differently.*

| | Tile size | Data layout after movement | Who writes address arithmetic? |
|---|---|---|---|
| **HIP C++** | Developer | Developer | **Developer, line by line** |
| **FlyDSL** | Developer | Developer | Compiler |
| **Triton** | Compiler | Compiler | Compiler |

**HIP C++ is not incapable.** As the lower-level interface, it can express every placement and offers even more freedom than FlyDSL. The difference is that the address calculations must be written manually. A high-performance GEMM can span thousands of lines, with a large portion devoted to address calculations and bit operations for swizzled placement.

Changing one tiling parameter can require recalculating all of those expressions. The barrier is not that the code cannot be written, but that changing it safely becomes difficult.

FlyDSL reduces "how to partition and who owns each tile" to compact layout descriptions and lets the compiler generate the arithmetic.

Triton takes the abstraction farther by letting the compiler choose both partition and layout in this simplified model. That is convenient for most operators. For the most performance-sensitive matrix-multiplication and Attention kernels, engineers may want an explicit control point instead.

### 7. The NVIDIA Side Solves the Same Problem

Nothing about the C++ maintenance problem is unique to AMD. A high-performance matrix multiplication in CUDA C++ can also span thousands of lines and require extensive recalculation when one parameter changes.

The ecosystems take corresponding paths under different names.

![AMD and NVIDIA kernel-stack counterparts](images/s10_10_data_movement_article_img07.png)

*Figure 7. Layer-by-layer correspondence between AMD and NVIDIA tools.*

| Layer | AMD | NVIDIA |
|---|---|---|
| Vendor operator library | AITER | cuBLAS / cuDNN |
| C++ template library | CK | CUTLASS |
| **Layout-aware Python DSL** | **FlyDSL** | **CuTe DSL** |
| Native C++ | HIP C++ | CUDA C++ |
| Platform | ROCm | CUDA |
| Cross-platform DSL | Triton | Triton, the same project on both platforms |

NVIDIA took this path earlier.

CUTLASS 3.0 introduced CuTe, whose central abstraction represents data placement as `Layout = (Shape, Stride)` algebra. A Python front end, CuTe DSL, later exposed the model through decorators such as `@cute.kernel`.

FlyDSL is AMD's solution in the same conceptual space, including a closely corresponding layout representation.

The precise conclusion is not that AMD invented an unrelated new tool. Both vendors met the same gap: C++ templates were expensive to iterate, while Triton did not expose enough layout control for these cases, so each added a middle layer.

FlyDSL remains experimental and is not part of the official ROCm distribution; it must be installed from its repository.

### 8. How to Read "A Is Faster Than B"

If source language does not determine the performance ceiling, a performance comparison must be interpreted at the implementation level.

![Questions required before accepting a kernel benchmark](images/s10_10_data_movement_article_img08.png)

*Figure 8. The first question to ask when reading a cross-implementation performance comparison.*

When a report says "FlyDSL is 30% faster than CK," ask:

> **Was the CK implementation tuned for the same matrix shape and conditions?**

Common explanations include:

| Reported result | Possible actual cause |
|---|---|
| FlyDSL is faster than CK | The FlyDSL implementation was tuned for this matrix shape; the CK implementation was generic |
| FlyDSL is faster than CK | FlyDSL adopted a new hardware instruction before CK did |

The concrete implementation is faster, not the language in the abstract. A different matrix shape can reverse the result.

The genuine value of a tool such as FlyDSL is **iteration speed**.

Kernel tuning searches a large space: tile size, data placement, loop-unroll depth, and thousands of combinations. No engineer chooses the optimum reliably in one attempt.

- A one-parameter C++ template change can require minutes of recompilation.
- A one-line Python change can be tested immediately.

In the same afternoon, one path may test 5 variants while another tests 50. The latter has a better chance of finding a stronger implementation.

**The language is not faster; the optimization loop is faster.**

### Put Every Term in Its Layer

| Term | What it is | What it is not |
|---|---|---|
| gfx942 | MI300X's hardware-defined instruction set | Not part of ROCm |
| ROCm | Compiler + driver + runtime | Not an instruction set or a language |
| `v_mfma` | A hardware matrix multiply-add instruction | Not a library function |
| LDS | On-chip shared memory | Not HBM device memory or a cache |
| Tiling | Choosing how much data to move and reuse at once | Not computing independent small matrix products |
| Layout | The on-chip arrangement of data | Not the row/column shape of the logical matrix |
| FlyDSL | A Python interface for describing tiling and layout | Not an inherently faster language and not a path around ROCm |

### Summary

1. **All four authoring approaches ultimately produce the same kind of machine code.** Python is absent at GPU runtime, so the source language does not set the performance ceiling.
2. **gfx942 is a hardware ISA; ROCm is the translator.** They are different things.
3. **Matrix multiplication often has enough arithmetic capacity but insufficient data delivery.** Time can be dominated by waiting for data.
4. **Two recurring optimizations matter:** move data fewer times through tiling, and avoid queues through layout.
5. **A worst-case bank conflict can serialize 32 accesses.** The data and instructions are the same; only placement changes.
6. **HIP C++ can express the solution, but its address arithmetic is manual.** Changing one parameter can force widespread recalculation.
7. **NVIDIA followed the same path earlier:** CUTLASS → CuTe → CuTe DSL.
8. **When "A is faster than B," first ask whether B's implementation was tuned.** The implementation is fast, not the language in isolation.

### Four Self-Check Questions

1. Why can a Python-authored kernel avoid being slower than C++? Which compilation layer matters?
2. What is the relationship between gfx942 and ROCm? If ROCm is removed, does the silicon understand a different ISA?
3. How can identical data and instructions differ by a factor of 32 solely because of placement?
4. What is FlyDSL's real advantage over HIP C++, and why is "the language is faster" the wrong answer?

### References

All sources below are public:

- AMD CDNA architecture and ISA documentation: https://www.amd.com/en/technologies/cdna.html
- Official FlyDSL repository: https://github.com/ROCm/FlyDSL (Apache-2.0)
- Official Composable Kernel repository: https://github.com/ROCm/composable_kernel (MIT)
- Official AITER repository: https://github.com/ROCm/aiter (MIT)
- Official CUTLASS / CuTe repository: https://github.com/NVIDIA/cutlass
- Official Triton repository: https://github.com/triton-lang/triton
- LLVM AMDGPU backend documentation: https://llvm.org/docs/AMDGPUUsage.html
<!-- SOURCE-END-EN id=10 -->

---

<!-- SOURCE-BEGIN-EN id=11 -->
## Source #11: cuBLAS, cuDNN, CUTLASS, and Every Layer of the GPU Software Stack

> These names appear constantly, but the relationships are easy to blur. Does cuBLAS sit above cuDNN? Is CUTLASS a peer of cuBLAS? Which NVIDIA library corresponds to AITER? An eight-layer map makes the AMD and NVIDIA stacks comparable without forcing false equivalences.

### Terms to Define First

| Abbreviation | Full name | Meaning here |
|---|---|---|
| **Kernel** | — | The compiled code that actually runs on the GPU; unrelated to an operating-system kernel |
| **BLAS** | Basic Linear Algebra Subprograms | A mathematical-library standard established in 1979 |
| **DNN** | Deep Neural Network | Deep neural network |
| **DSL** | Domain-Specific Language | A language designed for one class of work |
| **GEMM** | General Matrix Multiply | General matrix multiplication |
| **MoE** | Mixture of Experts | A model structure in which each token is routed through only a subset of expert subnetworks |
| **ISA** | Instruction Set Architecture | The complete instruction vocabulary understood by a chip |
| **SASS** | Streaming ASSembler | NVIDIA GPU machine code |
| **gfx942** | — | The instruction-set target used by the AMD MI300X GPU |
| **CK** | Composable Kernel | AMD's C++ template kernel library |
| **AITER** | AI Tensor Engine for ROCm | AMD's operator library for large-model workloads |

### 1. Why the Names Are Hard to Remember

The problem is not memory. The terms are often listed together even though they belong to different layers.

![Names that appear together but belong to four different layers](images/s11_11_gpu_stack_article_img01.png)

*Figure 1. Proximity in a sentence does not make technologies peers; these names span four layers.*

"We use CUDA, cuBLAS, CUTLASS, and Triton" sounds natural, but it combines a platform, an operator library, a template library, and a language. It resembles saying that an organization consists of a city, its finance department, one employee, and a computer: every noun can be true, but they do not describe one dimension.

Without the layers, the relationships remain difficult to retain. Start with the map.

### 2. The Full Eight-Layer Stack

![Eight-layer GPU software stack with NVIDIA and AMD counterparts](images/s11_11_gpu_stack_article_img02.png)

*Figure 2. The full GPU software stack, aligned by layer across NVIDIA and AMD.*

| Layer | NVIDIA | AMD |
|---|---|---|
| Application / inference engine | vLLM · SGLang · TensorRT-LLM | vLLM · SGLang |
| Deep-learning framework | PyTorch | PyTorch |
| Operator libraries | cuBLAS · cuDNN · FlashInfer | rocBLAS · MIOpen · AITER |
| C++ template libraries | CUTLASS | CK |
| Python DSLs | CuTe DSL · Triton | FlyDSL · Triton |
| Native C++ | CUDA C++ | HIP C++ |
| Platform / runtime | CUDA | ROCm |
| Hardware instruction set | SASS | gfx942 and related targets |

Moving downward approaches the hardware. **AMD has a counterpart at every layer; the differences are maturity and ecosystem inertia, not missing categories.**

The next sections separate the three groups most often confused.

### 3. cuBLAS and cuDNN: Same Layer, Different Domains

Their full names expose the distinction:

| | Keyword in the full name | Domain |
|---|---|---|
| cuBLAS | **Linear Algebra** | Matrix multiplication, matrix-vector multiplication |
| cuDNN | **Deep Neural Network** | Convolution, normalization, activation, pooling |

A durable memory hook is that **BLAS predates deep neural networks by about 40 years**.

BLAS was defined as a Fortran standard in 1979, before deep learning existed. It knows matrices and vectors, not a "convolution layer." cuDNN arrived in 2014 specifically for neural networks.

One is a general mathematical library; the other is an AI-specific library.

During model execution, a simplified division of work looks like this:

| Work at this layer | Typical library |
|---|---|
| Fully connected / feed-forward network, fundamentally matrix multiplication | cuBLAS |
| QKV projection in Attention, also matrix multiplication | cuBLAS |
| Convolution and pooling | cuDNN |
| Batch normalization and activation functions | cuDNN |

Some cuDNN paths also perform matrix multiplication because a convolution can be transformed into one. That does not imply that cuDNN always calls cuBLAS; in many cases cuDNN has its own implementation. The domains overlap, but neither library is simply above the other.

### 4. cuBLAS and CUTLASS: Finished Product Versus Components

Their names look related because both contain LAS, for Linear Algebra Subroutines, but their roles differ fundamentally.

![Finished operator library versus kernel-construction components](images/s11_11_gpu_stack_article_img03.png)

*Figure 3. cuBLAS/rocBLAS are finished products; CUTLASS/CK provide source components for building kernels.*

| | cuBLAS / rocBLAS | CUTLASS / CK |
|---|---|---|
| Form | Closed-source binary library | Open-source C++ template library |
| How it is used | **Called** | **Compiled and composed** |
| Can users modify it? | No; internals are opaque | Yes; the implementation is source code |
| Analogy | A finished dish | Ingredients plus a recipe |

Why keep components when a finished product exists? A closed cuBLAS binary exposes only the combinations it ships. It may not provide:

- **Operator fusion**, such as applying an activation immediately after matrix multiplication to avoid another device-memory round trip.
- **A special data type**, such as a new quantization format not yet supported.
- **An unusual shape** for which a general implementation is not competitive.

In those cases, developers compose a custom kernel from CUTLASS components.

**CUTLASS corresponds to CK, not to cuBLAS.** They occupy a separate row in the stack.

### 5. Operator Libraries Span Three Domains

The eight-layer map compresses all operator libraries into one row. Expanding that row reveals three domains:

![Three domains within the operator-library layer](images/s11_11_gpu_stack_article_img04.png)

*Figure 4. Operator libraries occupy one layer but serve three different domains.*

| Domain | NVIDIA | AMD |
|---|---|---|
| General linear algebra | cuBLAS | rocBLAS / hipBLAS |
| Neural-network layers | cuDNN | MIOpen |
| **Large-model operators** | **Distributed across several projects** | **AITER** |

The third row requires care: **AITER has no one-to-one NVIDIA equivalent.**

AITER covers Attention, MoE, matrix multiplication, normalization, quantization, and communication. It crosses the traditional boundary between BLAS and DNN libraries and was designed for large-model workloads rather than an older taxonomy based on mathematical domains.

The corresponding role on NVIDIA is distributed among:

- FlashInfer, a community project;
- fused Attention paths in cuDNN;
- kernels built into TensorRT-LLM.

"AITER corresponds to cuBLAS" is wrong, while "AITER corresponds to cuDNN" is also imprecise. Forcing a one-to-one mapping obscures the actual layer and domain boundaries.

### 6. Three Ways to Write a Kernel

![Kernel authoring approaches ordered by exposed control](images/s11_11_gpu_stack_article_img05.png)

*Figure 5. Control ranges from delegating more decisions to the compiler to managing address arithmetic directly.*

| | Who chooses tiling and layout? | Who writes address arithmetic? |
|---|---|---|
| **Triton** | Compiler | Compiler |
| **CuTe DSL / FlyDSL** | Developer | Compiler |
| **CUDA C++ / HIP C++** | Developer | **Developer, manually** |

All three paths ultimately compile to the same kind of platform-specific machine code. The distinction is not an inherent speed ranking; it is which decisions remain in the developer's hands.

Native C++ can express everything. Its cost is that address arithmetic must be written line by line and recalculated when tiling parameters change.

### 7. One Naming Trap: Two Unrelated Tritons

![OpenAI Triton and NVIDIA Triton Inference Server are unrelated products](images/s11_11_gpu_stack_article_img06.png)

*Figure 6. The names are identical, but the projects and roles are unrelated.*

| Name | What it is |
|---|---|
| **OpenAI Triton** | A language for writing GPU kernels; this is the Triton discussed in this series |
| **Triton Inference Server** | NVIDIA's inference-serving framework, unrelated to kernel authoring |

In a meeting, "we use Triton" can send one participant toward kernel implementation and another toward deployment architecture. Documents and messages should include the qualifier.

### 8. The Layers Traversed by One Call

With the concepts separated, follow one matrix multiplication.

![One matrix-multiplication call traversing the runtime stack](images/s11_11_gpu_stack_article_img07.png)

*Figure 7. The complete runtime path of one matrix-multiplication call.*

| Step | What happens |
|---|---|
| User code | `torch.matmul(A, B)` |
| Framework | PyTorch dispatches to the appropriate backend |
| Operator library | cuBLAS / rocBLAS selects an implementation by shape and precision |
| Kernel | A block of GPU code compiled in advance |
| Runtime | CUDA / ROCm loads and launches the kernel |
| Hardware | SASS / gfx942 instructions execute |

One point matters particularly:

> **CUTLASS, CuTe DSL, and FlyDSL are not nodes in this runtime chain.**

They belong to the other chain that produced the kernel in advance. Runtime invokes; the build chain manufactures.

The question "what does FlyDSL do during inference?" is therefore framed at the wrong stage. Its authoring and compilation work was already completed before that invocation.

### 9. Other Libraries and Tools in the Ecosystem

The main stack is surrounded by tools grouped by purpose:

![Additional GPU libraries and tools grouped by purpose](images/s11_11_gpu_stack_article_img08.png)

*Figure 8. Additional libraries and tools grouped by the problems they solve.*

| Purpose | Examples |
|---|---|
| Mathematical computation | cuSPARSE for sparse operations · cuFFT for Fourier transforms · cuSOLVER for solvers · cuRAND for random numbers |
| Multi-GPU communication | NCCL / RCCL · NVSHMEM |
| Data processing | cuDF, GPU-oriented pandas · cuML · DALI · nvJPEG |
| Performance tools | Nsight Systems · Nsight Compute · compute-sanitizer · rocprof |

The communication layer deserves separate attention. **NCCL corresponds to AMD's RCCL.** Multi-GPU training and inference depend on their collectives. When one GPU is fast but scaling across GPUs is poor, the communication layer is a leading suspect.

Profiling also has an order. Start with **Nsight Systems** to inspect the global timeline and identify who is waiting. Then use **Nsight Compute** to inspect the specific kernel in detail. Starting with one kernel can trap an investigation in a local view before the system-level bottleneck is known.

### 10. Use the Stack to Locate Problems

The goal of the layer map is diagnosis, not vocabulary memorization.

![Troubleshooting map from symptoms to software layers](images/s11_11_gpu_stack_article_img09.png)

*Figure 9. Common symptoms mapped to the layer most likely to own the problem.*

| Symptom | Likely layer |
|---|---|
| Results are wrong, but execution completes | Operator-library implementation selection / precision settings |
| One GPU is fast, multiple GPUs are slow | Communication: NCCL / RCCL |
| Compute units are underutilized while waiting for data | Kernel: tiling and layout |
| Performance drops for a different matrix shape | The operator library's selection table does not cover that shape well |
| Installation fails or the workload cannot start | Platform: CUDA / ROCm version compatibility |
| A required fused operator does not exist | Move down to a template library or DSL and build one |

Knowing what each layer owns tells an engineer where to search for the cause.

### Put Every Term in Its Layer

| Term | What it is | What it is not |
|---|---|---|
| CUDA / ROCm | Platform: compiler + driver + runtime | Not a language or an instruction set |
| SASS / gfx942 | Hardware instruction sets | Not part of CUDA / ROCm |
| cuBLAS / rocBLAS | Finished general linear-algebra libraries | Do not own convolution and are not template libraries |
| cuDNN / MIOpen | Finished neural-network-layer libraries | Not general mathematical libraries |
| AITER | Operator library for large-model workloads | Not an Attention algorithm and has no one-to-one counterpart |
| CUTLASS / CK | C++ template component libraries | Not finished black-box libraries; users compose and compile them |
| CuTe DSL / FlyDSL | Python DSLs with explicit layout control | Not part of the runtime invocation chain |
| OpenAI Triton | A language for writing kernels | Not Triton Inference Server |
| NCCL / RCCL | Multi-GPU collective communication | Do not manage computation within one GPU |

### Summary

1. The names are hard to remember when their layers are hidden. Technologies listed together often belong to different parts of the stack.
2. The stack has **eight layers**, from applications down to hardware instructions, with AMD counterparts at every layer.
3. **cuBLAS and cuDNN are peers serving different domains:** general mathematics versus neural-network layers. BLAS predates deep neural networks by about 40 years.
4. **cuBLAS and CUTLASS are finished product and components:** one is called, the other is compiled and composed. CUTLASS corresponds to CK.
5. **AITER crosses three operator domains.** Its NVIDIA-side role is distributed, so there is no one-to-one counterpart.
6. **Two unrelated projects are named Triton:** one is a kernel language; the other is an inference-serving framework.
7. **Runtime invocation and kernel construction are separate chains.** Template libraries and DSLs belong to the construction chain.
8. The layer map is useful because it localizes failures: each symptom points toward a different owner.

### Five Self-Check Questions

1. Does cuBLAS call cuDNN, or cuDNN call cuBLAS, or is that framing wrong?
2. Why is CUTLASS still needed when cuBLAS exists? Name one combination cuBLAS may not provide.
3. Which NVIDIA library corresponds to AITER, and what is wrong with demanding one answer?
4. A colleague says, "we optimized with Triton." What qualifier should you ask for first?
5. One GPU is fast, but eight GPUs deliver less than six times the throughput. Which layer should be investigated first?

### References

All sources below are public:

- NVIDIA CUDA libraries documentation: https://docs.nvidia.com/cuda/
- Official cuDNN documentation: https://docs.nvidia.com/deeplearning/cudnn/
- Official CUTLASS / CuTe repository: https://github.com/NVIDIA/cutlass
- Official NCCL repository: https://github.com/NVIDIA/nccl
- Official ROCm documentation: https://rocm.docs.amd.com/
- Official AITER repository: https://github.com/ROCm/aiter (MIT)
- Official Composable Kernel repository: https://github.com/ROCm/composable_kernel (MIT)
- Official FlyDSL repository: https://github.com/ROCm/FlyDSL (Apache-2.0)
- Official MIOpen repository: https://github.com/ROCm/MIOpen (MIT)
- Official RCCL repository: https://github.com/ROCm/rccl
- Official Triton repository: https://github.com/triton-lang/triton
<!-- SOURCE-END-EN id=11 -->

---

## Reversible Merge Ledger for This Edition

| Source | Original SHA-256 | Normalized body SHA-256 | Detail figures |
|---:|---|---|---:|
| #2 `02_triton_article.md` | `20555d5880250a7d973412cd26f62780fe7ac9835c532a8cfb6d3722b7fd7568` | `a2663407ef02f20fbd86d96e1829e84cb5ac2f2958382058f8ccbbbd1b327c2a` | 8 |
| #8 `08_flydsl_article.md` | `e2d0ddc01bd2399efe5fd8eabc0e27ed078276aa06cc46703afced60811c72cb` | `657b933e2fd59a8bb6fc0ccce97a28df5bef917294c12859270230660eb72615` | 10 |
| #9 `09_operator_kernel_article.md` | `13c3d46bd8683566a3798856eb7ef2c9585e01e6bf81426ad0edf92120b48ff4` | `5599e1a14116ca884f80f933b017b1cd0da3dc0f43a31e8994f5c214cc4cf7c9` | 8 |
| #10 `10_data_movement_article.md` | `a190d6e1b85ff5663800eca65bc503ccaa7e0e01a0f933263d1a5c72678819f2` | `219fe1abb6cb90a93de07c45bd779a2c0bb411bc26e1e4806340c644d45956ad` | 8 |
| #11 `11_gpu_stack_article.md` | `1d55790dee1a68efdaacda7b97b91efa98e5d176a063553e1ab0a72e4152a501` | `e9288bedfd18ab3b68a6f4d90b9572591db3ba6aed2863b4708fa64f077ddd93` | 9 |

The normalized-body hashes correspond to the deterministic Chinese source bodies after repeated publication scaffolding was removed, embedded images were extracted, and heading levels were shifted. [FULL_MERGE_LEDGER.md](FULL_MERGE_LEDGER.md) records every excluded line and every image SHA-256. The source merger can extract each Chinese source interval and compare it byte for byte; a missing line, changed order, or missing detail figure fails that check.