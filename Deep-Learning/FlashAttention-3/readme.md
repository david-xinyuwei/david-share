# FlashAttention-3

*参考链接：https://medium.com/@jrodthoughts/understanding-flashattention-3-one-of-the-most-important-algortihms-to-make-transformers-fast-7d21b0f6e6a4*

来自Meta、普林斯顿大学、NVIDIA和其他AI实验室的一组AI研究人员发布了FlashAttention-3的论文和开源代码。新版本的方法使用了几种技术来加速H100 GPU中的注意力机制，利用了张量核心的异步性。结果很简单：FlashAttention-3非常快。新模型在H100中实现了75%的理论最大FLOP利用率，实际性能提高了1.5到2倍。新算法还能够使用更低精度的数字，从而减少了内存占用。

让我们深入了解一些细节，但在此之前，让我们回顾一下FlashAttention的一些细节。

**一、FlashAttention**

FlashAttention旨在通过重新排序步骤和利用分块和重计算来优化注意力机制的计算。假设你有一个长度为 1000 的序列，传统的注意力机制计算需要处理一个 1000x1000 的矩阵，这会占用大量的内存。

1. **传统方法**：
   - 需要处理一个 1000x1000 的矩阵，内存使用量为 1000^2 = 1,000,000。
   - 处理速度较慢，因为需要频繁地在 HBM 中读写数据。
2. **FlashAttention 方法**：
   - 将序列分成 10 个长度为 100 的小块，每次只处理一个 100x100 的矩阵。
   - 内存使用量为 10 * 100^2 = 100,000，比传统方法减少了一个数量级。
   - 通过将小块数据加载到更快的 SRAM 中处理，减少了 HBM 的读写操作，提高了处理速度。



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXhMib3ALx2JszDMxucnxLKbhGN4O7echjibCtynldd21ykxMFlibDibJyacHyaVDFnjWQRBVFkKuhHoQ/640?wx_fmt=png&from=appmsg&randomid=zzz71oy3&tp=webp&wxfrom=5&wx_lazy=1)

针对上图的公式，我们详细说明：

### FlashAttention 的分块和内存管理

1. **输入和分块**：

   - 输入序列 ( Q ) 被分成多个小块（图中展示了两个小块 ( Q{(1)} ) 和 ( Q{(2)} )）。
   - 同样，键 ( K ) 和值 ( V ) 也被分成相应的小块。

2. **计算注意力得分**：

   - ( S^{(1)} ) 是 ( Q^{(1)} ) 和 ( K^{(1)} ) 的乘积。
   - ( S^{(2)} ) 是 ( Q^{(2)} ) 和 ( K^{(2)} ) 的乘积。

3. 对于每个小块，计算注意力得分 ( S )：

   这些计算在更快的缓存（SRAM）中进行，而不是在较慢的 GPU 内存（HBM）中。

4. **Softmax 计算**：

   - ( A{(1)} ) 是 ( S{(1)} ) 经过 softmax 处理后的结果。
   - ( A{(2)} ) 是 ( S{(2)} ) 经过 softmax 处理后的结果。

5. 对每个小块的注意力得分 ( S ) 进行 softmax 计算：

   这些计算也在 SRAM 中进行。

6. **加权求和**：

   - ( O^{(1)} ) 是 ( A^{(1)} ) 和 ( V^{(1)} ) 的乘积。
   - ( O^{(2)} ) 是 ( A^{(2)} ) 和 ( V^{(2)} ) 的乘积。

7. 对每个小块的加权求和：

   这些计算在 SRAM 中完成后，结果写回 HBM。

8. **输出合并**：

   - 输出是 ( O{(1)} ) 和 ( O{(2)} ) 的和。

9. 最终的输出是各个小块输出的合并：

   在合并过程中，进行重缩放以确保正确的分母。

### 依据标准

1. **分块的依据**：
   - 分块的大小通常取决于硬件的缓存大小（SRAM 的大小）和计算资源的限制。分块的目的是确保每个小块可以完全放入快速缓存中进行处理，从而减少对较慢内存（HBM）的依赖。
2. **放入快速内存（SRAM）的数据**：
   - 在每个计算步骤中，当前处理的小块数据（如 ( Q^{(i)} )、( K^{(i)} )、( V^{(i)} )）会被加载到快速内存（SRAM）中。
   - 计算注意力得分 ( S{(i)} ) 和 softmax 结果 ( A{(i)} ) 也会在 SRAM 中进行。
   - 这些中间结果在计算完成后会被写回到较慢的 GPU 内存（HBM）中。

### 总结


通过分块技术，FlashAttention 将大规模的计算任务分成多个小块，每次只处理一个小块的数据。这些小块的数据会被加载到快速内存（SRAM）中进行计算，从而减少了对较慢内存（HBM）的读写操作，提高了整体的计算速度和效率。分块的大小和哪些数据被放入快速内存，主要依据硬件的缓存大小和计算资源的限制。



**二、H100 GPU和注意力**

尽管FlashAttention-2在Ampere（A100）GPU上实现了高达70%的理论最大FLOPS，但它并未充分利用Hopper GPU的新功能。以下是Hopper GPU的一些关键特性及其重要性：

1. **WGMMA（Warpgroup Matrix Multiply-Accumulate）**：

   - **解释**：WGMMA 是一种新的矩阵乘加操作，专门为 Hopper GPU 上的新型张量核心设计的。
   - **优势**：相比于之前在 Ampere GPU 上使用的 `mma.sync` 指令，WGMMA 提供了更高的计算吞吐量。这意味着在相同时间内，Hopper GPU 可以进行更多的矩阵运算，从而提高整体计算性能。
   - **例子**：假设你在做一个图像处理任务，需要对一张图片进行滤波操作。滤波操作可以看作是一个矩阵乘法运算。在旧的 Ampere GPU 上，这个操作可能需要 1 秒钟来完成。而在新的 Hopper GPU 上，使用 WGMMA 技术，这个操作可能只需要 0.5 秒钟，因为 WGMMA 提供了更高的计算吞吐量。

   

   ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXhMib3ALx2JszDMxucnxLKbGNHrFic6FQ7gUiaxq5rusVkJicTDyBhGv0ZpJgicicoVgo5eVMceOr3Alvw/640?wx_fmt=png&from=appmsg&randomid=czdv62d9&tp=webp&wxfrom=5&wx_lazy=1)

2. 

3. 

4. 

5. **2. TMA（Tensor Memory Accelerator）**：

6. - **解释**：TMA 是一个硬件单元，专门用于加速全局内存和共享内存之间的数据传输。
   - **优势**：
     - **索引计算和越界预测**：TMA 可以自动处理数据传输中的索引计算和越界预测。TMA 可以自动计算数据在内存中的位置，简化了编程过程。数据传输在合法范围内，避免错误。这样可以减少编程的复杂性。
     - **释放寄存器**：通过加速数据传输，TMA 可以减少对寄存器的需求，从而释放更多的寄存器资源用于其他计算任务。
     - **增强分块大小和效率**：TMA 还可以优化数据传输的分块大小，提高数据传输的效率。
   - **例子**：假设你在训练一个深度学习模型，需要频繁地从全局内存中读取数据并将其传输到共享内存中进行计算。在没有 TMA 的情况下，你需要手动编写代码来处理数据传输的索引计算和越界检查，这不仅复杂还会占用大量寄存器资源。而有了 TMA，硬件会自动处理这些操作，你只需要简单地告诉它要传输的数据块大小和位置。这样不仅简化了编程，还提高了数据传输的效率。

7. ![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXhMib3ALx2JszDMxucnxLKbASwxIXeUjcfO8m9kBJdTMlXEHvBicicnn9ibxOFvKlqgciaqslr4Oveicmw/640?wx_fmt=png&from=appmsg&randomid=fblb1f54&tp=webp&wxfrom=5&wx_lazy=1)3. **低精度的FP8：**

8. 

9. 解释：FP8 是一种低精度的浮点数表示方法，使用8位来表示一个浮点数。

10. 

    优势：

    

11. 

12. 

13. 吞吐量加倍：由于FP8使用的位数更少，张量核心可以在相同时间内处理更多的浮点运算。例如，从FP16的989 TFLOPS（每秒万亿次浮点运算）提升到FP8的1978 TFLOPS。

14. 速度提升：虽然使用FP8会在精度上有所牺牲，但它可以显著提高计算速度，适用于对精度要求不高的任务。

- 例子：假设你在做一个语音识别任务，需要对大量的音频数据进行快速处理。使用高精度的 FP16 浮点数可以得到非常精确的结果，但处理速度较慢。现在你决定使用低精度的 FP8 浮点数，虽然精度有所降低，但处理速度大大提高。例如，原来使用   FP16 需要 2 秒钟完成的任务，现在使用 FP8   只需要 1 秒钟。这对于实时语音识别等对速度要求高的应用非常有用。



![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXhMib3ALx2JszDMxucnxLKbtcGI8KVxUBeZdj2aNkRCRer5wrfYE2GEpI96c0acIgMVeLvicvQOYOg/640?wx_fmt=png&from=appmsg&randomid=hdlmbemv&tp=webp&wxfrom=5&wx_lazy=1)

**三、FlashAttention-3**
FlashAttention-3 使用 NVIDIA 的 CUTLASS 库中的抽象来整合这些新的 Hopper 特性。像 ThunderKitten 2 和 cuDNN 9 这样的研究表明，这些硬件特性可以显著加速注意力计算。通过调整 FlashAttention 以利用这些特性，其性能显著提高（例如，从 FlashAttention-2 FP16 前向传递的 350 TFLOPS 到约 540-570 TFLOPS）。Hopper 上的异步指令（WGMMA 和 TMA）进一步提供了算法优化的机会。FlashAttention-3 引入了三种关键技术来增强现代 GPU 架构上的性能：

1. **生产者-消费者异步（Producer-Consumer Asynchrony）**：
   - **解释**：这种方法采用 warp 专用的软件流水线，将数据生产者和消费者分成不同的 warp。
   - **优势**：这种分离利用异步执行来更好地隐藏内存和指令发出延迟。
   - **例子**：假设你在做一个复杂的计算任务，任务分为两个部分：数据准备和数据处理。传统方法中，这两个部分是顺序执行的，数据准备完成后才开始数据处理。而使用生产者-消费者异步技术，数据准备和数据处理可以同时进行。比如，当一个 warp 在准备数据时，另一个 warp 已经在处理之前准备好的数据，这样可以更好地利用 GPU 资源，提高整体效率。
2. **在异步块状 GEMM 下隐藏 Softmax（Hiding Softmax Under Asynchronous Block-wise GEMMs）**：
   - **解释**：通过将低吞吐量的 softmax 操作与异步 WGMMA 指令重叠，FlashAttention-3 可以绕过 softmax 和 GEMM 之间的顺序依赖。
   - **优势**：这种方法可以显著提高计算效率。例如，在一个两阶段版本中，当 softmax 处理分数矩阵的一个块时，WGMMA 计算下一个块。
   - **例子**：假设你在做一个神经网络的前向传递，需要进行矩阵乘法（GEMM）和 softmax 操作。传统方法中，这两个操作是顺序执行的，必须等待 GEMM 完成后才能进行 softmax。而使用这种技术，当 softmax 处理第一个数据块时，WGMMA 已经开始计算下一个数据块的 GEMM，这样可以更好地利用计算资源，提高整体速度。
3. **硬件加速的低精度 GEMM（Hardware-accelerated Low-precision GEMM）**：
   - **解释**：这种调整针对 FP8 张量核心进行 GEMM，几乎将测量的 TFLOPS/s 翻倍。
   - **优势**：通过块量化和不一致处理来管理 FP32 累加器和 FP8 操作数矩阵的不同布局要求，以减轻精度降低带来的影响。
   - **例子**：假设你在做一个大规模的矩阵乘法运算，使用高精度的 FP32 浮点数可以得到非常精确的结果，但处理速度较慢。现在你决定使用低精度的 FP8 浮点数，虽然精度有所降低，但处理速度大大提高。例如，原来使用 FP32 需要 2 秒钟完成的任务，现在使用 FP8 只需要 1 秒钟。这对于对速度要求高且对精度要求不高的应用非常有用。

**四、结论**

FlashAttention-3团队测量了其在各种序列长度上的运行时间，并与标准PyTorch实现、FlashAttention-2、在Triton中的FlashAttention-2（使用H100特定指令）以及供应商的H100优化FlashAttention-2（来自cuDNN）进行了比较。结果发现，FlashAttention-3比FlashAttention-2快2倍，比在Triton中的FlashAttention-2快1.5倍，达到了740 TFLOPS/s，即H100 GPU理论最大值的75%。

![Image](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXhMib3ALx2JszDMxucnxLKbVc0maBwxI6moKiaYvvM6ulJs1E1BibE4Qu6HM0KOCS8PY64eI3f8mYug/640?wx_fmt=png&from=appmsg&randomid=yxsfqfae&tp=webp&wxfrom=5&wx_lazy=1)