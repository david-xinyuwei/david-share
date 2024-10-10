# The-reason-vLLM-High-Performance

### 1. vLLM

 
vLLM (Virtual Large Language Model) technology was introduced by Kwon et al. in their September 2023 paper, "Efficient Memory Management for Large Language Model Serving with PagedAttention." vLLM addresses the challenges of memory allocation when using GPUs, particularly the inefficiencies in managing key-value (KV) cache memory in current large language model (LLM) service systems. These inefficiencies lead to underutilized GPU resources, slower inference speeds, and high memory usage.

To tackle these challenges, the authors were inspired by memory and paging techniques used in operating systems and proposed an attention algorithm called PagedAttention. PagedAttention employs paging, a method of mapping hardware addresses to virtual addresses. This approach allows for efficient memory management by enabling non-contiguous storage of attention keys and values (KV) in memory.

In terms of batching inference requests, there are two main techniques:

- **Client-Side (Static) Batching**: Typically, when a client sends requests to a server, the server processes each request sequentially, which is inefficient. To improve efficiency, the client can bundle multiple inference requests into a single batch and send it to the server, which then splits the batch into individual requests for processing. This method requires the client to modify its code to implement batching and is closely tied to the batch size.

- **Server-Side (Dynamic) Batching**: Another approach is for the server to handle batching. When independent inference requests arrive at the server, it can dynamically combine them into larger batches. The server manages these batches to meet specified latency targets, maximizing throughput while maintaining the required latency range. This process is handled automatically by the server, so no client code modifications are needed. Server-side batching includes various techniques to further optimize the throughput of generating language models, such as dynamic batching, continuous batching, and PagedAttention (vLLM) batching. vLLM also uses continuous batching, dynamically adjusting batch sizes during model output generation.

  Continuous batching is a specialized optimization technique for text generation. It increases throughput without adding first-byte latency. Continuous batching (also known as iterative or rolling batching) addresses GPU idle time by continuously adding new requests to the batch, improving efficiency. The diagram below illustrates how continuous batching works. When requests 2 and 3 are completed, another set of requests is scheduled.

### 2. Paged Attention

 
The primary reason for vLLM's fast inference speed is the Paged Attention technology. vLLM is a high-throughput, low-latency large language model (LLM) inference and serving engine designed to improve model efficiency during the inference phase.

Paged Attention is an attention mechanism optimization method introduced by vLLM. It achieves efficient memory utilization by paging the attention key-value pairs (key-value caches). When handling long sequences or a large number of concurrent requests, Paged Attention can temporarily move inactive key-value pairs out of VRAM and store them in lower-cost memory, bringing them back when needed. This mechanism avoids excessive VRAM usage, allowing vLLM to handle larger models and longer sequences without sacrificing performance.

![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nUUjqTQTNOmZcBhGCGpZfWa8BRSUq5c5UhxZY4ibKgkLiclXy4MkqYjZAcJaPXx5OiaZUrZvaBRaotvw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

The image below describes a memory management technique called "PagedAttention" used for natural language processing tasks. In this example, we have a sentence: "the cat is sleeping in the kitchen and the dog is." This sentence is broken down into a series of tokens, each associated with a pair of key-value tensors used for attention computation. The attention mechanism allows the model to focus more on certain parts of the sentence.

In the diagram, we see two main parts:

- **Contiguous Virtual Blocks**: These are logically contiguous memory blocks used to store the key-value tensors for each word. In this example, there are three virtual blocks (#0, #1, #2), each containing a portion of the sentence.

- **Non-Contiguous Blocks in the GPU Memory**: These are physically non-contiguous blocks in GPU memory used to store data. Due to memory constraints or optimization, these blocks may not be stored sequentially.

  In the middle of the diagram, we see an index table showing the mapping between virtual blocks and physical GPU memory blocks. For example, virtual block #0 (containing "the cat is sleeping") maps to physical block #5, virtual block #1 (containing "in the kitchen and") maps to physical block #2, and virtual block #2 (containing "the dog is") maps to physical block #3.

  This mapping allows the computer to efficiently handle large amounts of data, even if the data is not stored contiguously in physical memory. This is crucial for handling large models and complex tasks like machine translation and speech recognition, which require significant memory and computational resources.

  In summary, the image demonstrates how to efficiently organize and access data for natural language processing in GPU memory.

  PagedAttention aims to store key-value tensors more efficiently in the non-contiguous space of GPU VRAM. The idea behind PagedAttention is to create contiguous virtual blocks mapped to physical blocks in GPU memory.

  Each block is designed to store key-value tensors for a predefined number of tokens. All blocks are logically contiguous and mapped to physically non-contiguous blocks, allocated on-demand during inference in fragmented GPU memory. A simple index table is created in memory to associate virtual blocks with physical blocks.

  PagedAttention's kernel fetches these blocks as needed. This is efficient because the system fetches fewer key-value tensors due to the limited block size.

  Let's illustrate with the following prompt:

  "the cat is sleeping in the kitchen and the dog is"

  We set key-value tensors for each token. Using PagedAttention, we can arbitrarily set the block size to 4. Each block contains 4 key-value tensors, but the last one contains only 3 key-value tensors. These blocks are logically contiguous but not necessarily contiguous in GPU memory.

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUUjqTQTNOmZcBhGCGpZfWaKzvqvAxicIEKv1pibab2ovCDPZ7vQF5gOJFVjQ7pAYjVy54na9w3zxibw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

  To compute attention, for each query token, the system fetches blocks one by one, as shown in the diagram below.

  By fetching key-value tensors by blocks rather than the entire tensor sequence, attention computation is much faster.

  Another advantage of PagedAttention is that virtual blocks can be shared during sampling in the inference process. All sequences generated in parallel through sampling or beam search can use the same virtual blocks, avoiding duplication.

  Sharing virtual blocks is a technique of PagedAttention. PagedAttention divides VRAM into multiple small blocks and uses virtual memory and paging techniques to manage these blocks. During inference, all parallel-generated sequences (e.g., through sampling or beam search) can share these virtual blocks, avoiding redundant storage of the same data.

  This method not only saves VRAM but also improves memory management efficiency. By sharing virtual blocks, PagedAttention can handle more parallel requests without increasing VRAM usage, thus improving overall inference performance.

  Berkeley reported the performance of PagedAttention implemented in vLLM compared to the text generation inference library developed by Hugging Face.

  ![图片](https://mmbiz.qpic.cn/mmbiz_jpg/akGXyic486nUUjqTQTNOmZcBhGCGpZfWaAnia8aF2VvlicicQlePNGdkYM4S8Qh8A615hegBYuOZdZ42U4cHuEiacnw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

  The results indicate that vLLM is significantly faster, especially when multiple outputs are completed. The difference between TGI and vLLM increases with larger models. This is expected because larger models require more memory and are more affected by memory fragmentation.

### 3. vLLM Default Pre-Allocation of 90% VRAM

 
The primary reason vLLM pre-allocates 90% of VRAM is to optimize memory management and improve inference efficiency. Specifically, vLLM uses a mechanism called PagedAttention to manage attention key-value (KV) caches. Inspired by virtual memory and paging in operating systems, this mechanism divides VRAM into multiple small blocks and allocates memory on-demand, reducing memory fragmentation and waste.

By default, vLLM's `gpu_memory_utilization` parameter is set to 0.9, meaning it pre-allocates 90% of VRAM to store these KV caches. This pre-allocation ensures sufficient VRAM to store all necessary intermediate results when handling long sequences or large batches of data, thus improving inference speed and efficiency. Additionally, pre-allocating 90% of VRAM reduces memory management overhead, avoiding frequent memory allocation and release operations.

PagedAttention indeed optimizes memory usage. By dividing VRAM into multiple small blocks and allocating memory on-demand, it reduces memory fragmentation and waste. This method not only saves memory but also improves memory management efficiency.

However, the main reason vLLM pre-allocates 90% of VRAM is to ensure sufficient VRAM to store all necessary intermediate results when handling long sequences or large batches of data, thus improving inference speed and efficiency. This pre-allocation reduces memory management overhead, avoiding frequent memory allocation and release operations.

### 4. Flash Attention

 
FlashAttention: Fast and Memory-Efficient Exact Attention with IO Awareness

Let's look at the diagram from the paper:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nV05nf7w6xCM6iaiczQxhYz4ib4DKdNPb2mSUwJywNL3znA3eV7mqQJB5eswmcZUJG7ia0iaw2G1TEIZ1A/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

The left chart ranks three types of GPU memory by speed and capacity from top to bottom:

- **GPU SRAM (Static Random-Access Memory)**: This is the fastest type of memory, with a bandwidth of up to 19TB/s, but it has the smallest capacity, only 20MB.

- **HBM (High Bandwidth Memory)**: This memory has a bandwidth of 1.5TB/s and a capacity of 40GB, used for high-performance computing in GPUs.

- **DRAM (Dynamic Random-Access Memory)**: This is a type of main memory with a bandwidth of 12.8GB/s and a capacity of over 1TB.

  FlashAttention is an optimized attention mechanism computation method that processes data in chunks, avoiding the generation of large attention matrices on the GPU's HBM. The flowchart shows how blocks of K and V matrices are copied to fast SRAM and computed through blocks of the Q matrix, then written back to HBM.

  The right bar chart compares the performance of FlashAttention and traditional PyTorch implementations on the GPT-2 model. It shows the time taken for operations like matrix multiplication, Dropout, Softmax, Mask, and fused kernels. The results indicate that FlashAttention significantly reduces the time for all these operations, achieving an overall 7.6x speedup, greatly improving model computation efficiency.

  In traditional attention mechanism implementations, the model needs to compute a large attention matrix, typically the square of the input sequence length (N x N). This computation is very memory and resource-intensive, especially for long sequences.

  FlashAttention optimizes this process through a method called "tiling." Instead of computing the entire large attention matrix at once, it divides the input sequence into smaller chunks and computes attention for each chunk separately. This reduces the amount of data that needs to be stored at once in the GPU's high-bandwidth memory (HBM), reducing memory usage and improving computation efficiency.

  In the described flowchart, the outer loop (red arrows) iterates over blocks of the K (key) and V (value) matrices, copying these blocks to fast on-chip SRAM (a type of high-speed cache memory). Then, for each block of K and V, the inner loop (blue arrows) iterates over blocks of the Q (query) matrix, performing computations and storing results back in SRAM. Finally, the computed attention output is written back to HBM.

  Overall, FlashAttention significantly reduces the time required for attention mechanism computation through this tiling and optimized memory management, improving the model's overall performance. The right bar chart shows the performance improvement of this method in practical applications compared to traditional methods, highlighting the speedup in operations like matrix multiplication, Dropout, Softmax, etc.

  Imagine you have a very thick book, and your task is to find all sentences mentioning "apple." The book is too thick to remember all the content at once, so you decide to use a strategy:

- **Outer Loop (Red Arrows)**: You divide the book into several parts (called "blocks"). Each time, you only take out one part (one block) to look for "apple." This is like having a small memory space (SRAM) in your brain where you only process a part of the book's content.

- **Inner Loop (Blue Arrows)**: While processing each part, you go page by page (or paragraph by paragraph) to look for "apple." Each time you find an "apple," you make a note in a small notebook, representing your workspace (SRAM), which can quickly record and update information.

- **Write Back to HBM**: After completing the search in this part of the book, you organize the notes in your small notebook and transfer them to a large notebook (HBM), freeing up the small notebook's space to prepare for the next block.

  In this process, your small notebook (SRAM) is used for quickly processing and recording information, while the large notebook (HBM) stores all the completed work. This way, you can efficiently manage your memory and recording space, making the task of finding "apple" more efficient.

  In FlashAttention, blocks of the K (key) and V (value) matrices are like different parts of the book, and blocks of the Q (query) matrix are like the pages or paragraphs you search in each part. Through this tiling and looping method, FlashAttention can efficiently handle large amounts of data without exceeding memory limits, speeding up attention mechanism computation.

  **Underlying Principle**

  The main idea behind FlashAttention is to perform as much attention computation as possible on the GPU's SRAM (the top of the pyramid in the diagram). SRAM is an on-chip memory that is much faster than GPU HBM memory (commonly referred to as "VRAM") but is much more expensive, so only a small amount (usually less than 100 MB) is available.

  FlashAttention breaks down attention computation into small chunks that can be loaded onto SRAM. In other words, it avoids writing large attention matrices to HBM, as shown in the middle part of the diagram.

  **Reducing Non-Mathematical Operations**

  FlashAttention-2 further speeds up attention computation by reducing the number of non-matmul operations.

  What is a matmul operation?

  When training and running LLMs, GPUs perform a large number of matrix multiplication operations, known as matmul operations.

  Recent GPUs have specialized cores for accelerating computations. For example, NV GPU tensor cores are specifically designed for matrix multiplication operations. Tensor cores have been used since the RTX 20xx generation, but recent GPUs (like the RTX 40xx) have more tensor cores and are faster. However, note that only Ampere or newer GPUs (RTX 30xx) support FlashAttention.

  The A100 GPU's FP16/BF16 matmul has a maximum theoretical throughput of 312 TFLOPs/s, but non-matmul FP32 throughput is only 19.5 TFLOPs/s. Another way to understand this is that each non-matmul FLOP costs 16 times more than a matmul FLOP. To maintain high throughput, we want to spend as much time as possible on matmul FLOPs.

  **Improving Parallelization of Long Sequences**

  The first version of FlashAttention was optimized for parallel computation of batch size and attention heads. It performed well when processing large batches of data. However, in many cases, we cannot process large batches, such as when handling long sequences of tokens.

  Now, FlashAttention-2 can also parallelize sequence length. Therefore, even when using small batches of long sequences, we can still benefit from FlashAttention.

  **Improved Partitioning and Support for More LLMs**

  FlashAttention-2 can better partition computation among threads. It reduces the amount of communication and synchronization between threads (more accurately, between "warps" of 32 threads).

  Now, models with up to 256 heads also support FlashAttention-2. Models using multi-query attention (MQA) and grouped-query attention (GQA) can also benefit from FlashAttention-2.

  While FlashAttention is also a method for optimizing Transformer model attention computation, aiming to reduce computation and memory usage and improve training and inference efficiency, vLLM's core acceleration technology is primarily based on Paged Attention.

### 5. Continuous Batching

 
In addition to Paged Attention, Continuous Batching in vLLM also significantly speeds up inference.

The diagram below shows how Continuous Batching works when handling multiple inference requests. It illustrates how three requests (Request 1, Request 2, and Request 3) are processed and generate responses over time.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVkls1zIviaJzB6ZOOgkG2tyPPpsMfGXmaupbx742CHv3Czb7VribZT1CQ7tsLFP4hRvVquPvsicaWNw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**Diagram Explanation:**

- Request Inputs:

  - Request 1: "Capital of"
  - Request 2: "The diamondback turtle is"
  - Request 3: "Largest Mammal is"

- Timeline (T1 to T7):

  - Request 1: From T3 to T6, the system generates response tokens until T7.
  - Request 2: From T3 to T5, the system generates response tokens, ending at T6.
  - Request 3: From T3 to T5, the system generates response tokens, ending at T5.

- **Request 1**: "of"

- **Request 2**: "diamondback"

- **Request 3**: "mammal"

- **Request 1**: "Capital"

- **Request 2**: "The"

- **Request 3**: "Largest"

- **T1**: In the first time step (T1), the system starts processing the first word of the three requests:

- **T2**: In the second time step (T2), the system processes the second word of the three requests:

- **T3 to T7**: From the third time step (T3), the system starts generating response tokens:

  **Detailed Explanation**:

- **Continuous Batching**: The diagram illustrates the concept of continuous batching, where the system continuously adds new requests to the batch while processing requests, rather than waiting for all requests to complete before starting new ones. This method maximizes GPU utilization, reduces idle time, and increases overall throughput.

- **Response Generation**: From T3 to T7, the system starts generating response tokens for each request. The response generation time varies for each request, depending on the complexity and length of the request. For example, Request 1 takes the longest to generate a response, ending at T7, while Request 3 ends at T5.

- **Parallel Processing**: The diagram shows multiple requests being processed in parallel within the same time step. This parallel processing significantly improves system efficiency and reduces the waiting time for each request.

  **Summary**:

  This diagram illustrates how continuous batching works to improve system efficiency when handling multiple inference requests. By continuously adding new requests to the batch, the system maximizes GPU utilization, reduces idle time, and increases overall throughput and response speed.

  

  **Reference**: [Deploy LLM with vLLM on SageMaker in Only 13 Lines of Code](https://mrmaheshrajput.medium.com/deploy-llm-with-vllm-on-sagemaker-in-only-13-lines-of-code-1601f780c0cf)