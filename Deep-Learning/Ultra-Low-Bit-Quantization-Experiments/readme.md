# Exploring 1-Bit LLMs: Efficient Large Language Models through Ternary Weight Quantization

In the current field of artificial intelligence, **Large Language Models (LLMs)** have become indispensable. However, their enormous number of parameters leads to significant computational and memory demands, limiting their applications on resource-constrained devices. Is it possible to reduce these demands without significantly compromising model performance? Microsoft's **BitNet** architecture and **1-Bit LLMs** provide an affirmative answer.  This article delves into the concept and implementation of 1-Bit LLMs from multiple perspectives, using examples to help readers better understand this cutting-edge technology. 

***Please click below picture to see my demo vedio on Yutube***:
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://www.youtube.com/watch?v=el7edql4Xug)


## I. What Are 1-Bit LLMs?


**1-Bit LLMs** are large language models that use low-bit-width parameters (weights) for representation and computation. Specifically, in 1-Bit LLMs, each weight is constrained to ternary values: **-1**, **0**, or **1**. This approach significantly reduces the model's memory footprint and computational complexity.

Although referred to as "1-Bit," each weight actually occupies about **1.58 bits** on average. This value is derived from entropy calculations in information theory, representing the minimal average number of bits needed to represent ternary values.

### 1. Differences Between 1-Bit LLMs and FP16/FP32 Models


In deep learning, we often mention **FP16** and **FP32**, referring to the precision of floating-point data types used in models:

- **FP32 (32-bit floating-point)**: Each number occupies 32 bits, offering high precision and a wide dynamic range.

- **FP16 (16-bit floating-point)**: Each number occupies 16 bits, reducing memory usage and increasing computation speed but with lower precision.

  **1-Bit LLMs** differ by emphasizing the reduction of weight bit-width. By quantizing weights to ternary values (-1, 0, 1) and representing them with low-bit-width data types (averaging about 1.58 bits per weight), they achieve extreme memory and computational efficiency.

  In traditional FP16 or FP32 models, parameters are stored and computed using 16-bit or 32-bit floating-point numbers. In contrast, 1-Bit LLMs quantize model parameters to ternary values, leading to lower memory usage and computational complexity during inference.

### 2. Precision of Other Components in 1-Bit LLMs


While 1-Bit LLMs achieve extreme compression in the weights, other parts of the model may use higher-precision data types:

- Activations:

  - Typically quantized to **8-bit** or **16-bit** to ensure sufficient numerical precision during forward propagation, preventing excessive information loss between layers.

- Gradients:

  - During training, gradients are often computed with **FP16** or **FP32** to maintain training stability.

- Optimizer States:

  - States maintained by optimizers (e.g., momentum terms) are usually stored in **FP32** to accurately capture parameter updates.

- Loss Values and Other Computations:

  - Critical computations like loss values and regularization terms usually remain at **FP32** precision to ensure numerical stability during training.

    Therefore, 1-Bit LLMs primarily achieve bit-width compression in the weights, while other components retain higher bit-width to maintain performance and training stability.

#### Example:

#### Suppose we have a traditional neural network model:

- **Weights**: Represented using FP32, each weight occupies 32 bits.

- **Activations**: Using FP32.

- **Gradients**: Using FP32.

  In a 1-Bit LLM:

- **Weights**: Quantized to ternary values (-1, 0, 1), averaging about 1.58 bits per weight.

- **Activations**: Possibly quantized to 8-bit integers (INT8).

- **Gradients**: Might still use FP16 or FP32.

  **Benefits**:

- **Reduced Storage and Computation**: Significantly lowers storage requirements and computational complexity since weights often occupy most of the model's storage space.

- **Maintained Performance**: Preserves model performance and training stability because critical computations still use higher precision.

  **Considerations**:

- **Training Complexity**: Training may become more complex due to quantization, requiring specific techniques like the Straight-Through Estimator (STE) to handle non-differentiability.

- **Hardware Support**: Existing hardware may need specific optimizations to fully utilize low-bit-width weight representations.

## II. Why Use Ternary Weights?


In neural network models, especially LLMs, weights consume a significant portion of memory during inference due to:

- **Large Model Size**: LLMs often contain hundreds of millions to tens of billions of parameters, all of which need to be loaded into memory during inference.

- **Data Type Precision**: Weights are typically stored as high-precision floating-point numbers (FP32 or FP16), each occupying more memory space.

- **Computational Needs**: All relevant weights must be accessed and computed during inference, increasing memory and computational resource consumption.

  **Using ternary weights offers several advantages**:

- **Memory Efficiency**: Each weight requires only about **1.58 bits**, greatly reducing storage needs compared to FP32 (32 bits) and FP16 (16 bits).

- **Computational Efficiency**: Multiplication operations with ternary weights can be simplified—multiplications by 0 can be skipped, and multiplications by 1 or -1 can be simplified to copying or negation.

- **Model Miniaturization**: Allows large models to run on standard CPUs or resource-constrained devices, expanding application scenarios.

## III. BitNet Architecture: The Key to Implementing 1-Bit LLMs


Developed by Microsoft Research, the **BitNet architecture** is central to implementing 1-Bit LLMs. It achieves efficiency through key techniques:

### 1. Ternary Weight Quantization


In BitNet, model weights are quantized to ternary values (-1, 0, 1). The quantization process involves:

- Computing the Scaling Factor:

  - Calculate the mean absolute value of the weight matrix as the scaling factor

    gamma (γ):

    - gamma = (1 / (n * m)) * sum of the absolute values of all weights
    - where n and m are the dimensions (rows and columns) of the weight matrix.

- Scaling the Weight Matrix:

  - Divide each element of the weight matrix by gamma to get the scaled weight matrix.

- Applying the RoundClip Function:

  - Quantize each element using:

    RoundClip(x, -1, 1) = max(-1, min(1, round(x)))

    This rounds values to the nearest integer and clips them between -1 and 1.

#### Example:


Suppose we have a weight matrix:

```
W = |  0.3   -0.7 |  
    |  0.5    0.1 |  
```

- **Compute gamma**:

  gamma = (1 / (2 * 2)) * ( |0.3| + |-0.7| + |0.5| + |0.1| )
  = 0.4

- **Scale the Weight Matrix**:

  Scaled W = W / gamma

  Scaled W = | 0.75 -1.75 |
  | 1.25 0.25 |

- **Apply RoundClip Function**:

  Quantized W = | 1 -1 |
  | 1 0 |

  - For 0.75: RoundClip(0.75, -1, 1) = 1
  - For -1.75: RoundClip(-1.75, -1, 1) = -1
  - For 1.25: RoundClip(1.25, -1, 1) = 1
  - For 0.25: RoundClip(0.25, -1, 1) = 0

### 2. Straight-Through Estimator (STE)


Due to the discontinuity and non-differentiability of the quantization function, standard backpropagation cannot be directly applied. BitNet uses the **Straight-Through Estimator (STE)** to address this:

- **Principle**: During forward propagation, discrete ternary weights are used for computation. During backpropagation, gradients are directly passed to the unquantized continuous weights, treating the quantization function as if it were the identity function in terms of gradient computation.
- **Effect**: Allows the model to update weights during training while maintaining weight discreteness.

### 3. Activation Quantization


To further improve efficiency, BitNet also quantizes activations to **8-bit precision**:

- **Layer Normalization**: Applied before activation quantization to ensure output stability and prevent gradient explosion or vanishing.
- **Scaling and Quantization**: Compute the maximum absolute value of activations as a scaling factor, scale activations accordingly, and then quantize.

## IV. Optimized Inference Kernels: `bitnet.cpp`


Since existing hardware is not optimized for ternary weights, Microsoft developed `bitnet.cpp`, which includes several optimized inference kernels such as **I2_S**, **TL1**, and **TL2**:

- **I2_S Kernel**: Packs ternary weights into 2-bit representations, suitable for multithreaded CPU environments.

- **TL1 Kernel**: Packs every two weights and uses lookup tables to accelerate computation, suitable for environments with limited threads.

- **TL2 Kernel**: Further compresses weights, suitable for memory and bandwidth-constrained environments.

  These optimizations enable efficient execution of 1-Bit LLMs on standard CPUs.

## V. The Essence of Neural Network Models: Static Components and Runtime States


To deeply understand 1-Bit LLMs, it's essential to revisit the essence of neural network models from the perspectives of **static components** and **runtime states**.

### 1. Static Components

 

- **Model Weight Files**: Store the learned weights and biases.
- **Configuration Files**: Define model architecture, including layers and parameters.
- **Vocabulary Files**: Map tokens to indices in language models.
- **Auxiliary Scripts**: Handle data preprocessing and postprocessing.
- **Training Scripts**: Define training procedures, loss functions, optimizers, and training epochs.

### 2. Runtime States

 

- **Input Data**: Raw data fed into the model.
- **Activations**: Outputs after passing through activation functions, serving as inputs for subsequent layers.
- **Intermediate States**: Outputs from layers like feature maps in convolutional layers.
- **Gradients**: Computed during backpropagation for updating parameters.
- **Loss Values**: Measure the difference between model outputs and true labels.
- **State Updates**: Parameter updates based on gradients and optimizer states.
- **Caches**: Values stored during forward propagation for efficient gradient computation during backpropagation.

### 3. Relationship Between Model Parameters and Runtime


Model parameters usually refer to the weights and biases in a neural network. They exist both in static storage and in runtime memory.

#### 1) Static Model Parameters

 

- Stored on Disk:
  - Weight files: After training, weights and biases are saved to disk (e.g., `.pt`, `.h5`, `.ckpt` formats).
  - Storage Formats: Parameters may be stored in different data types and precisions (e.g., FP32, FP16, INT8).
- Purpose:
  - **Persistent Storage**: Save the current state of the model for future loading, deployment, or sharing.
  - **No Computation on Disk**: Stored parameters are just data and do not involve computation.

#### 2) Runtime Model Parameters 

- Loaded into Memory:
  - When loading a model (e.g., using `model.load_state_dict()`), parameters are read from disk into memory (RAM, GPU memory).
- Representation and Computation:
  - **Inference Phase**: Parameters interact with input data to generate outputs.
  - **Training Phase**: Parameters are updated based on computed gradients during backpropagation.
- Data Types:
  - **FP32**: 32-bit floating-point for high-precision computation.
  - **FP16**: 16-bit floating-point to reduce memory usage and increase speed.
  - **Low Bit-Width Formats**: INT8, binary (1-bit), or ternary representations for further compression and acceleration.
- Impact:
  - **Calculations**: Runtime data types directly affect computational results and performance.
  - **Efficiency**: Lower bit-width can improve computation speed and reduce memory bandwidth usage.

#### 3) Parameters in 1-Bit LLMs

- Weight Quantization:
  - Ternary Representation: Weights are quantized to -1, 0, 1, averaging about 1.58 bits per weight.
- Runtime Computation:
  - These quantized weights are used during inference and training, represented in memory using low-bit-width data types.
- Relation to Runtime:
  - **Performance**: Quantized parameters reduce memory usage and computational load.
  - **Hardware Support**: Specialized hardware or software optimizations may be needed to fully utilize low-bit-width parameters.

#### 4) Summary

- **Model Parameters** refer to both static parameters stored on disk and runtime parameters involved in computation.
- Discussions about data types or bit-width (e.g., ternary weights in 1-Bit LLMs) usually focus on how parameters are represented and computed at runtime.

By understanding the relationship between model parameters and runtime, we can better grasp the advantages of 1-Bit LLMs. The bit-width and data type of model parameters directly affect computational performance, memory usage, and precision. 1-Bit LLMs achieve efficient computation and low memory usage at runtime by significantly reducing the bit-width of model parameters. 

 

## VI. Conclusion and Outlook


1-Bit LLMs leverage innovative weight quantization and computational optimization methods to significantly reduce storage and computational demands, making it feasible to run large language models in resource-constrained environments.

**Challenges**:

- Limited Expressiveness:

  - Constraining weights to ternary values may affect model expressiveness, potentially requiring deeper networks or improved training methods.

- Hardware Support:

  - Existing hardware lacks optimization for ternary weights, necessitating specialized software and kernel support.

- Training Complexity:

  - Special training techniques like the Straight-Through Estimator (STE) are needed to handle the non-continuity introduced by quantization.

    Despite these challenges, 1-Bit LLMs open new avenues for model compression and efficient computation. With ongoing advancements in technology and hardware support, these efficient models are poised to play a significant role in practical applications.

    **Understanding 1-Bit LLMs centers on grasping weight quantization and computational optimization techniques, as well as the fundamental structure of neural network models.** By integrating theory with practice, we can better appreciate the potential and value of this innovative approach.

    In the future, as research deepens and hardware progresses, 1-Bit LLMs are expected to find applications in more domains, bringing new possibilities to the development of artificial intelligence.

## Test code

Down load repo :

```
#git clone --recursive https://github.com/microsoft/BitNet.git
#cd BitNet
#pip install -r requirements.txt
```

Download model:

```
huggingface-cli download HF1BitLLM/Llama3-8B-1.58-100B-tokens --local-dir models/Llama3-8B-1.58-100B-tokens
```

Convert model to GGUF

```
python setup_env.py -md models/Llama3-8B-1.58-100B-tokens -q i2_s
```

Run inference, -t 16 means using 16 threads to do this job, cloud use lscpu check.

```
python run_inference.py -m models/Llama3-8B-1.58-100B-tokens/ggml-model-i2_s.gguf -p "What is the square root of 2+2?\nAnswer:" -n 20 -temp 0.7 -t 16
```
