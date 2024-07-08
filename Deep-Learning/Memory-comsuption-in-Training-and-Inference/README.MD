## Calculate Model Memory consumption in Training and Inference
The specific proportion of model memory consumption can vary greatly under different models and configurations, but a general overview can help understand the relative importance of each part:

- Model Parameters: This part usually occupies a relatively fixed amount of memory, depending on the size of the model (number of layers, number of parameters). For larger models, this can take up a significant proportion of memory, especially when there are many model parameters. In inference scenarios, the main memory consumption is the loading of model parameters.
- Optimizer State: In inference processes, if there is no model updating, the memory consumption of the optimizer state can be negligible. However, in training scenarios, this part consumes a significant amount of memory, even higher than Model Parameters
- Gradients: In the training phase, gradients are a significant part of memory consumption. Each parameter in the model has an associated gradient which is used to update the parameter during backpropagation. Especially in large models, the memory required to store these gradients can be substantial. This is crucial for understanding the overall memory requirements during model training. It should be noted that the memory consumption of the gradients usually calculate into the optimizer's memory usage.
- Activations: During inference, activations are not the main part of memory consumption. However, in training scenarios, especially when the batch size is large or the model depth is significant, this part consumes a lot of memory.
- KV cache in vLLM inference: During inference with vLLM, when handling long sequences, it will occupy lots of memory，This is the additional memory required beyond the KV cache memory for normal model training and inference.
- Framework Overhead: This usually occupies a smaller proportion of memory, but in cases of poor memory management or a complex framework itself, it can also become a non-negligible factor.

**Overall**
- In training phase: ***Memory need = Model Parameters + Optimizer State + Gradients + Activations***. 
- In inference phase： ***Memory need =  Model Parameters + Activations + vLLM KV Cache(In case you use vLLM)***

For example in Inference：

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/4.webp)


For example in Training(Gradients are calculated into the optimizer)，

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/9.webp)


There is also an example for a quick assessment of the amount of memory sold while the model is being trained, this is a quick reference and may not be 100% accurate. Refer below for the exact steps.
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in%20Training%20and%20Inference/images/example.png)


## Memory comsuption in Model Parameters Loading

For Training and inference，Memory comsuption in Model Parameters Loading is same.

For example, to calculate the GPU RAM needed to load the Llama 3 70B model, we can follow these steps:

- Determine the Number of Parameters: The Llama 3 70B model has 70 billion (i.e., 70 billion or 70,000,000,000) parameters.

- Calculate the Total Memory Required for Parameters: Each parameter uses 16 bits (or 2 bytes) of memory (since the parameters are stored in bfloat16 format, 16 bits equals 2 bytes).

Total Memory = Number of Parameters x Memory per Parameter

- Total Memory = 70,000,000,000 parameters x 2 bytes/parameter = 140,000,000,000 bytes
- Convert Bytes to GB:
1 GB = 1,073,741,824 bytes (note that this uses the binary conversion, i.e., 2^30)
Total Memory (GB) = 140,000,000,000 bytes ÷ 1,073,741,824 bytes/GB ≈ 130.4 GB

This value is very close to the result from the HF (Hugging Face) tool.
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/3.webp)


## Memory comsuption in Optimizer State and Gradients
The memory increase due to the optimizer during the training process mainly includes the following two parts:
- New parameters created by the optimizer
- Copies of model parameters

### New parameters created by the optimizer
AdamW is a commonly used optimizer, notable for considering the historical update data of parameters while adjusting the model parameters. This is similar to an experienced engineer who, when tuning a machine, not only considers the current performance but also refers to past adjustment records for more precise tuning. Now, let's examine the memory consumption. When using the AdamW optimizer, each model parameter has two additional pieces of information recorded: momentum and variance.

- Momentum: This reflects the trend of parameter changes during previous training processes, helping the optimizer understand how to smoothly change parameters during adjustments.
- Variance: This helps the optimizer understand the stability of each parameter at different training stages, making the adjustments more robust.

These two additional pieces of information require extra memory for storage, as the optimizer records both for each model parameter. Next, let's look at the memory consumption during fine-tuning of the model. Taking the Mixtral-8x22B model as an example, the optimizer creates and stores two new parameters (momentum and variance) for each parameter of the model, which requires additional memory. Specifically.

This includes momentum and variance; we have 282 billion of these new parameters, each of which is a float32 type, occupying 4 bytes of memory. Similarly, we can calculate the total memory occupied by the new parameters created by the optimizer using the following formula:
Memory = Number of New Parameters × Memory Size per New Parameter
Substituting the specific values into the formula, we get:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/7.webp)

Converted to GB, we find that the new parameters created by the optimizer occupy approximately 1050.53 GB of memory.

### Copies of Model Parameters by the optimizer
We have 141 billion (141B) parameters, each of which is a float32 type, occupying 4 bytes of memory. Thus, the total memory occupied by the copies of model parameters can be calculated using the following formula:
Memory = Number of Parameters × Memory Size per Parameter
Substituting the specific values into the formula, we get:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/5.webp)


This result is in bytes, and we usually convert it to GB for easier understanding. 1GB equals 1,024^3 bytes, so we can determine that the total memory occupied by the copies of model parameters is approximately 525.27 GB.

### Memory comsuption in Gradients
We have 141 billion gradients, each of which is of type float16, occupying 2 bytes of memory. Similarly, we can calculate the total memory occupied by the gradients using the following formula:
Memory = Number of Gradients × Memory Size per Gradient
Substituting the specific values into the formula, we get:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/6.webp)

Converted to GB, we find that the gradients occupy approximately 262.63 GB of memory.

## Memory comsuption in Activations
In this part when calculating the memory consumption of Activations, the formula does not consider the detailed Data Type. This means that if FP16 is used, the formula below needs to be multiplied by 2.

We need to know the following information to estimate the activation memory consumption:
s: Maximum sequence length (number of tokens in the input)
b: Batch size
h: Model's hidden dimension
a: Number of attention heads

A standard Transformer layer consists of a self-attention block and an MLP block, each connected through two layer normalizations.
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/1.webp)

#### For Inference
The memory overhead of activations during inference requires storing the activations of a single layer and then passing them to the next layer. 

The memory consumption for each component is estimated as follows:
1. Self-Attention Block
The attention block includes the self-attention mechanism and linear projections. The memory requirements include:
· Linear Projection: Retains its input activations, with a size of 2sbh.
· Linear Projection and Self-Attention Input Activations: Each requires 2sbh.
· Self-Attention Query (Q) and Key (K) Matrices: Requires a total of 4sbh.
· Softmax: Requires 2as²b.
· Storing the Attention Applied to the Values (V) of Self-Attention: Requires a total of 2as²b + 2sbh.

The total memory required for the attention block is： 10sbh + 4as²b.

2. MLP Block
The MLP block contains two linear layers:
. Linear Layers: Store input, requiring 2sbh and 8sbh respectively.
. GeLU Non-linearity: Also requires 8sbh.
Overall, the MLP blck requires 18sbh of storage.

3 Layer Normalization
Each layer normalization stores its input, requiring 2sbh each, totaling 4sbh for two normalizations.
Total Memory for a Transformer Layer
The total memory required to store activations for one Transformer layer is:
- From the attention block: 10sbh + 4as²b
- From the MLP block: 18sbh
- From layer normalization: 4sbh

Total activation memory per layer = 32sbh + 4as²b

Conclusion
The memory overhead for activations during inference is:

Activation memory consumption per Layer in inference = 32 sbh + 4as²b

Depending on the data type used, you will need to adjust the total memory consumption accordingly.



#### For Training
While the activation calculation for training and inference appears similar, training requires storing the activations of all layers to perform backpropagation and gradient computation, which demands more memory. In contrast, during inference, we only need to compute layer by layer and can release the activations of each layer once its computation is complete, thereby saving memory.For the activation overhead of each layer, we also need to consider the dropout masks in the self-attention and MLP modules, which add an additional 2sbh.

Activation memory consumption per Layer in training = L(34sbh + 5as²b)



## KV cache in vLLM:
When vLLM performs inference, it utilizes the HF accelerate library, which causes it to pre-allocate 90% of the GPU memory by default when loading the model.

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/10.webp)

To address this issue, specify gpu_memory_utilization during inference. Of course, this percentage must satisfy the model's inference requirements. Based on practical tests, setting gpu_memory_utilization does not reduce inference performance as long as the GPU memory can meet the inference needs. Here are the analyses of two test results: in the first test, gpu_memory_utilization was set to 0.2, while in the second test, it was not set. The tests were conducted using H100 + vLLM + Phi3 Mini 4K.

However, vLLM team is working on FP8 of KV cache now with AMMO, but it supports limited Models. It is very useful when it supports most of HF models.

### Model Loading and Memory Allocation
 
#### Model Loading:
- First Test: Loading model weights occupied 7.1183 GB of memory.
- Second Test: Loading model weights also occupied 7.1183 GB of memory.

#### Memory Usage:
- First Test:
Maximum RAM Usage: 6085.128192 MB
Maximum Global VRAM Usage: 21886.861312 MB
Maximum Process VRAM Usage: 21254.635520 MB
- Second Test:
Maximum RAM Usage: 6089.269248 MB
Maximum Global VRAM Usage: 91814.297600 MB
Maximum Process VRAM Usage: 91182.071808 MB

From the memory usage data, the VRAM usage in the second test is significantly higher than in the first test.
### Latency and Throughput
 
#### Prefill Latency:

Prefill latency in both tests is very close, with average latency and standard deviation nearly identical.
##### First Test:
Total: 9.958572 s
Average: 0.026276 s
Standard Deviation: 0.000201 s (0.77%)
p50: 0.026256 s
p90: 0.026402 s
p95: 0.026436 s
p99: 0.027318 s
##### Second Test:
Total: 9.958938 s
Average: 0.026346 s
Standard Deviation: 0.000212 s (0.80%)
p50: 0.026328 s
p90: 0.026469 s
p95: 0.026500 s
p99: 0.027580 s

#### Decode Latency:

Decode latency is also very close, with average latency and standard deviation nearly identical in both tests.
##### First Test:
Total: 9.272923 s
Average: 0.299127 s
Standard Deviation: 0.000345 s (0.12%)
p50: 0.299020 s
p90: 0.299618 s
p95: 0.299694 s
p99: 0.299866 s
##### Second Test:
Total: 9.259893 s
Average: 0.298706 s
Standard Deviation: 0.000405 s (0.14%)
p50: 0.298628 s
p90: 0.299288 s
p95: 0.299376 s
p99: 0.299385 s

#### Throughput:

Throughput in both tests is also very close, with very minimal differences.
##### Prefill Throughput:
19485.523696 tokens/s (First Test)
19433.397122 tokens/s (Second Test)
##### Decode Throughput:
163.810265 tokens/s (First Test)
164.040766 tokens/s (Second Test)

### Summary
 
##### Memory Usage:

The VRAM usage in the second test is significantly higher than in the first test, possibly due to more GPU resources being used in the second test.

##### Latency and Throughput:

The latency and throughput in both tests are almost identical, showing very stable performance.

Overall, except for the significant difference in VRAM usage, the performance metrics in both tests are very close, indicating that the model's performance is stable under the same testing environment and configuration.


## DeepSpeed ZeRO policy for saving memory
### Deepspeed ZeRO stage
This image is from the DeepSpeed paper, illustrating the memory consumption on each device during different optimization stages (ZeRO-DP optimization). It details how parameters, gradients, and optimizer states are partitioned during the model training process, and the impact of each partitioning method on memory consumption. Memory consumption for each GPU is represented in different colors:

- Blue: Parameters
- Orange: Gradients
- Green: Optimizer State
![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Memory-comsuption-in-Training-and-Inference/images/zero3stage.png)

Several optimization strategies include:
- Baseline (unoptimized): All GPUs store complete parameters, gradients, and optimizer states: 120GB in above image.
- P_os: Partitioning only the optimizer state, i.e., Stage 1: 31.4GB in above image.
- P_os+g: Partitioning both the optimizer state and gradients, i.e., Stage 2: 16.6GB in above image.
- P_os+g+p: Partitioning optimizer state, gradients, and parameters, i.e., Stage 3: 1.9GB in above image.


#### Communication in ZeRO stage
1. P_os: After backpropagation, each device calculates local gradients based on local data. Then, local gradients are averaged across all devices. Each device uses the averaged gradient for weight updates. Since all devices have the same averaged gradient, they perform the same updates, thus all devices have a consistent model copy. For efficiency, this all-reduce operation on gradients is implemented in two steps, and for a model with P parameters, it requires a total of 2P communication:
- reduce-scatter: Each process averages part of the gradients (for a model with P parameters, the communication size of the gradient is O(P)).
- all-gather: Each process collects all other processes' reduced gradients (also O(P) communication). These two steps are pipelined, so the process is communication-bound, and GPUs are not idle.


2. P_os+g: The required communication is the same as classic data parallelism. The reduce-scatter operation needs P communication to reduce the part of the gradients each process owns. Each process only needs to update the part of the parameters it owns. Then it passes the updated parameters to all other devices, a total communication of P in the all-gather operation. The total communication is still 2P.

3. P_os+g+p: In this optimization stage, only 1/N of the P model parameters are stored on each device. Thus, each process needs to communicate P/N (part of the parameters) to all N devices for forward and backward propagation. That is, each propagation's communication volume is P/N * N = P, a total of 2P. The gradient's reduce-scatter operation requires P communication. The total communication is 3P, 1.5 times that of classic data parallelism. Communication is distributed, so parameters are only present on nodes when needed and are immediately discarded after use, maintaining the discussed memory-saving characteristics.

Today，when we want to use DeepSpeed to do CPT for FT, we could easily use Axolotl, please refer to:

***https://github.com/davidsajare/david-share/tree/master/Deep-Learning/Fine-tuning-with-Axolotl***
## **Refer：**

***https://kaitchup.substack.com/p/estimate-the-memory-consumption-of***

***https://github.com/microsoft/DeepSpeed***

