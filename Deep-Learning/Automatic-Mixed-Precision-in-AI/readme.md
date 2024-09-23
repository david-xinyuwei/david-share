# Automatic Mixed Precision (AMP) in AI

## Introduction to AMP

AMP (Automatic Mixed Precision) refers to a mixed training method that uses both single precision (FP32) and half precision (FP16) during the training process. Specifically, Automatic Mixed Precision (AMP) is a method that uses 32-bit (float32), 16-bit, and 8-bit data types. Specifically:

- **float32 (32-bit)**: Used for operations requiring a larger dynamic range, such as reduction operations.

- **16-bit and 8-bit**: Used for operations that can be executed faster at lower precision, such as linear layers and convolutional layers.

  The main features of AMP include:

- **Mixed Precision Computation**: During training, certain computations (like matrix multiplication) use half precision (FP16) to improve computation speed and reduce memory usage. Other computations requiring higher precision (like reduction operations, loss calculation) still use single precision (FP32) to ensure accuracy.

- **Loss Scaling**: Due to the lower precision of FP16, directly using FP16 for gradient computation may lead to gradient vanishing issues. To address this, AMP uses loss scaling to amplify the loss value, ensuring the gradient remains within the FP16 representable range.

- **Automatic Handling**: AMP libraries (such as PyTorch's `torch.cuda.amp`) can automatically handle most details of mixed precision training, including loss scaling and weight copying. Users only need to add a few lines of code to achieve mixed precision training.

  **Benefits of Using AMP**:

- **Increased Training Speed**: Since FP16 computations are faster, using AMP can significantly speed up model training.

- **Reduced Memory Usage**: FP16 uses only half the memory of FP32, allowing for training larger models or using larger batch sizes within the same GPU memory.

## Common Operations and Precision in AI Training


The term "reduction" in Chinese can be split into "规" and "约" to understand:

- **规 (Rule)**: Refers to the rules or methods for processing data, such as summation, averaging, finding the maximum value, etc.

- **约 (Simplify)**: Refers to simplifying a large amount of data into one or a few useful results, such as summing a group of numbers to get a total or averaging a group of numbers to get an average.

  Combining these, "reduction" is the process of processing data according to certain rules (规) to simplify (约) the data into one or a few useful results.

  **Reduction Operations**: These usually require higher precision to avoid numerical error accumulation and meet dynamic range requirements. Common reduction operations and their precision choices include:

- **Sum**: Usually uses FP32 to avoid numerical error accumulation when adding multiple values.

- **Mean**: Usually uses FP32 as it involves summation, which can lead to numerical error accumulation at lower precision.

- **Max/Min**: Usually uses FP32 to accurately find the maximum or minimum value.

- **Normalization**: Usually uses FP32 for precise numerical calculations.

- **Softmax**: Usually uses FP32 as it converts values to probability distributions, where lower precision can lead to numerical instability.

- **Variance**: Usually uses FP32 as it involves summation and squaring operations, which can lead to numerical error accumulation at lower precision.

- **Standard Deviation**: Usually uses FP32 as it involves variance calculation, which can lead to numerical error accumulation at lower precision.

- **L2 Norm**: Usually uses FP32 as it involves squaring and summation operations, which can lead to numerical error accumulation at lower precision.

- **L1 Norm**: Usually uses FP32 as it involves summation operations, which can lead to numerical error accumulation at lower precision.

  **Non-Reduction Operations**: These have lower precision requirements and can use lower precision to improve computation speed and reduce memory usage. Common non-reduction operations and their precision choices include:

- **Matrix Multiplication**: Usually uses FP16 or FP8 as these operations have lower precision requirements and can be executed faster at lower precision.

- **Convolution**: Usually uses FP16 or FP8 as these operations have lower precision requirements and can be executed faster at lower precision.

- **Activation Functions**: Usually uses FP16 or FP8 as these operations have lower precision requirements and can be executed faster at lower precision.

- **Backpropagation**: Usually uses FP16 or FP8 as these operations have lower precision requirements and can be executed faster at lower precision.

## Why Not Force 16-bit Precision


Directly choosing FP16 or BF16 for training is also a common practice, especially when supported by hardware. Each precision format has its pros and cons, and the choice depends on the specific application scenario and hardware support.

**FP16 (Half Precision Floating Point)**

- Advantages:

  - **Lower Memory Usage**: FP16 uses only half the memory of FP32, allowing for training larger models or using larger batch sizes within the same GPU memory.
  - **Faster Computation**: FP16 computations are usually faster than FP32, especially on hardware that supports FP16 (like Nvidia's Tensor Cores).

- Disadvantages:

  - **Precision Issues**: FP16's lower precision can lead to gradient vanishing or overflow issues, especially when training deep neural networks.

    **BF16 (Brain Floating Point)**

- Advantages:

  - **Better Numerical Stability**: BF16 retains the same exponent range as FP32 but with fewer mantissa bits, providing better numerical stability than FP16.
  - **Hardware Support**: Many modern hardware (like Google's TPU and Nvidia's A100 GPU) support BF16.

- Disadvantages:

  - **Memory Usage**: While BF16 uses less memory than FP32, it uses more than FP16.

    Although directly using FP16 or BF16 for training is feasible, AMP (Automatic Mixed Precision) offers additional advantages:

- **Automatic Handling of Precision Issues**: AMP can automatically handle FP16 precision issues, such as gradient vanishing and overflow, through techniques like loss scaling to ensure training stability.

- **Flexibility**: AMP can automatically choose between FP16 and FP32 based on the operation type, maximizing performance while maintaining numerical stability.

  **Summary**:

- **Directly Using FP16 or BF16**: Suitable for scenarios where hardware support is available and numerical stability requirements are not high.

- **Using AMP**: Suitable for scenarios requiring a balance between performance and numerical stability, especially when you don't want to manually handle precision issues.

## Issues with Forcing 16-bit Precision

Imagine you are baking a cake, and the taste and quality of the cake depend on the proportion and quantity of the ingredients you use. Here, the proportion of ingredients is like the gradients in neural network training.

**FP32 vs FP16**

- **FP32**: Like using a precise kitchen scale to measure each ingredient. You can measure to the gram, ensuring the cake tastes the same every time.

- **FP16**: Like using an imprecise measuring cup. The cup can only measure approximate quantities, so the cake's taste may vary each time.

  **Gradient Explosion and Vanishing**

  In neural network training, gradients are used to update model parameters. If the gradients are too large or too small, it will affect the training results.

- Gradient Explosion:

  - **Analogy**: Imagine suddenly pouring a large amount of sugar into the batter. The cake becomes overly sweet and inedible.
  - **FP16**: Due to FP16's lower precision, it may not accurately represent large gradient values, leading to gradient explosion.
  - **FP32**: FP32's higher precision can accurately represent large gradient values, avoiding gradient explosion.

- Gradient Vanishing:

  - **Analogy**: Imagine adding only a tiny bit of sugar, resulting in a cake with almost no sweetness.

  - **FP16**: Due to FP16's lower precision, it may not accurately represent small gradient values, leading to gradient vanishing.

  - **FP32**: FP32's higher precision can accurately represent small gradient values, avoiding gradient vanishing.

    **Why FP16 Has These Issues and FP32 Does Not**

- **Precision**: FP16 has lower precision, with only 16 bits, including 5 bits for the exponent and 10 bits for the mantissa. This means FP16 has a smaller representable range and precision than FP32.

- **Numerical Range**: FP32 has 32 bits, including 8 bits for the exponent and 23 bits for the mantissa, providing a larger representable range and precision than FP16.

  **Solutions**

- **Loss Scaling**: To avoid FP16 issues, loss scaling can be used. By amplifying the loss value, gradients can be kept within the FP16 representable range, avoiding gradient vanishing and explosion.

- **Mixed Precision Training**: Using AMP (Automatic Mixed Precision) can automatically handle these issues by using FP32 where high precision is needed and FP16 elsewhere, balancing performance and stability.

  **FP16 as an "Imprecise Measuring Cup"**

  FP16 is compared to an imprecise measuring cup due to its lower representable range and precision. Let's delve deeper:

- Precision and Representable Range:

  - FP16 (Half Precision Floating Point):

    - **Bits**: 16 bits
    - **Exponent Bits**: 5 bits
    - **Mantissa Bits**: 10 bits
    - **Representable Range**: Approximately (10{-5}) to (10{5})
    - **Precision**: With only 10 mantissa bits, FP16 can represent limited precision, leading to significant errors when representing very small or very large values.

  - FP32 (Single Precision Floating Point):

    - **Bits**: 32 bits

    - **Exponent Bits**: 8 bits

    - **Mantissa Bits**: 23 bits

    - **Representable Range**: Approximately (10{-38}) to (10{38})

    - **Precision**: With 23 mantissa bits, FP32 can represent higher precision, accurately representing very small or very large values.

      **Why FP16 is an Imprecise Measuring Cup**

- **Limited Mantissa Bits**: FP16 has only 10 mantissa bits, meaning it can only retain a limited number of significant digits. Like an imprecise measuring cup, it can only measure approximate quantities, not to the gram.

- **Numerical Errors**: Due to lower precision, FP16 calculations are prone to numerical errors, which can accumulate during deep learning training, leading to gradient explosion or vanishing.

- **Limited Representable Range**: FP16's 5 exponent bits limit its representable range. For very large or very small values, FP16 may not accurately represent them, leading to inaccurate calculations.

  **Analogy Explanation**

- **FP16**: Like an imprecise measuring cup, it may cause the cake's taste to vary each time due to imprecise ingredient proportions.

- **FP32**: Like a precise kitchen scale, it ensures the cake tastes the same every time due to precise ingredient proportions.

  **Solutions**

- **Loss Scaling**: By amplifying the loss value, gradients can be kept within the FP16 representable range, avoiding gradient vanishing and explosion.

- **Mixed Precision Training**: Using AMP (Automatic Mixed Precision) can automatically handle these issues by using FP32 where high precision is needed and FP16 elsewhere, balancing performance and stability.

## Microsoft AMP

 MS-AMP is an automatic mixed precision package developed by Microsoft for deep learning.

**Features**:

- **Supports O1 Optimization**: Applies FP8 to weights and weight gradients and supports FP8 communication.

- **Supports O2 Optimization**: Supports FP8 for two optimizers (Adam and AdamW).

- **Supports O3 Optimization**: Supports FP8 for distributed parallel training and ZeRO optimizer, crucial for training large-scale models.

- **Provides Four Training Examples Using MS-AMP**: Swin-Transformer, DeiT, RoBERTa, and GPT-3.

  **Advantages Over Transformer Engine**:

- **Memory Access**: Accelerates memory-bound operations by accessing one byte instead of half or single precision.

- **Reduced Memory Demand**: Reduces memory demand for training models, allowing for training larger models.

- **Accelerated Communication**: Accelerates distributed model communication by transmitting low-precision gradients.

- **Reduced Training Time**: Reduces training time for large-scale language models with larger batch data.

  The table below shows operations not involving reduction. **GEMM** refers to General Matrix Multiplication.

## Microsoft AMP Test

### Install MS-AMP

Follow *https://azure.github.io/MS-AMP/docs/getting-started/installation*

```
sudo docker run -it -d --name=msamp --privileged --net=host --ipc=host --gpus=all nvcr.io/nvidia/pytorch:23.10-py3 bash
sudo docker exec -it msamp bash
git clone https://github.com/Azure/MS-AMP.git
cd MS-AMP
git submodule update --init --recursive
```

If you want to train model with multiple GPU, you need to install MSCCL to support FP8. Please note that the compilation of MSCCL may take ~40 minutes on A100 nodes and ~7 minutes on H100 node.

```bash
cd third_party/msccl
# A100make -j src.build NVCC_GENCODE="-gencode=arch=compute_80,code=sm_80"# H100make -j src.build NVCC_GENCODE="-gencode=arch=compute_90,code=sm_90"
apt-get updateapt install build-essential devscripts debhelper fakerootmake pkg.debian.builddpkg -i build/pkg/deb/libnccl2_*.debdpkg -i build/pkg/deb/libnccl-dev_2*.deb
cd -
```

Then, you can install MS-AMP from source.

```bash
python3 -m pip install --upgrade pippython3 -m pip install .make postinstall
```

Before using MS-AMP, you need to preload msampfp8 library and it's depdencies:

```bash
NCCL_LIBRARY=/usr/lib/x86_64-linux-gnu/libnccl.so # Change as neededexport LD_PRELOAD="/usr/local/lib/libmsamp_dist.so:${NCCL_LIBRARY}:${LD_PRELOAD}"
```

After that, you can verify the installation by running:

```bash
python3 -c "import msamp; print(msamp.__version__)"
```

```
[2024-09-23 10:07:27,359] [INFO] [real_accelerator.py:191:get_accelerator] Setting ds_accelerator to cuda (auto detect)
0.4.0
```







```
root@h100vm:/workspace/MS-AMP# cd examples/
root@h100vm:/workspace/MS-AMP/examples# python mnist.py --enable-msamp --opt-level=O2
```







```
msamp is enabled, opt_level: O2
Train Epoch: 1 [0/60000 (0%)]   Loss: 2.299661
Train Epoch: 1 [640/60000 (1%)] Loss: 1.658558
Train Epoch: 1 [1280/60000 (2%)]        Loss: 1.168246
Train Epoch: 1 [1920/60000 (3%)]        Loss: 0.913748
Train Epoch: 1 [2560/60000 (4%)]        Loss: 0.580088
Train Epoch: 1 [3200/60000 (5%)]        Loss: 0.539106
Train Epoch: 1 [3840/60000 (6%)]        Loss: 0.500326
Train Epoch: 1 [4480/60000 (7%)]        Loss: 0.750634
Train Epoch: 1 [5120/60000 (9%)]        Loss: 0.609780
Train Epoch: 1 [5760/60000 (10%)]       Loss: 0.491282
Train Epoch: 1 [6400/60000 (11%)]       Loss: 0.422410
Train Epoch: 1 [7040/60000 (12%)]       Loss: 0.524504
Train Epoch: 1 [7680/60000 (13%)]       Loss: 0.547503
Train Epoch: 1 [8320/60000 (14%)]       Loss: 0.297933
Train Epoch: 1 [8960/60000 (15%)]       Loss: 0.395627
Train Epoch: 1 [9600/60000 (16%)]       Loss: 0.234251
Train Epoch: 1 [10240/60000 (17%)]      Loss: 0.379520
Train Epoch: 1 [10880/60000 (18%)]      Loss: 0.281372
Train Epoch: 1 [11520/60000 (19%)]      Loss: 0.349127
Train Epoch: 1 [12160/60000 (20%)]      Loss: 0.240814
Train Epoch: 1 [12800/60000 (21%)]      Loss: 0.209846
Train Epoch: 1 [13440/60000 (22%)]      Loss: 0.305113
Train Epoch: 1 [14080/60000 (23%)]      Loss: 0.325098
Train Epoch: 1 [14720/60000 (25%)]      Loss: 0.161219
Train Epoch: 1 [15360/60000 (26%)]      Loss: 0.589074
Train Epoch: 1 [16000/60000 (27%)]      Loss: 0.281410
Train Epoch: 1 [16640/60000 (28%)]      Loss: 0.204650
Train Epoch: 1 [17280/60000 (29%)]      Loss: 0.152525
Train Epoch: 1 [17920/60000 (30%)]      Loss: 0.290945
Train Epoch: 1 [18560/60000 (31%)]      Loss: 0.330578
Train Epoch: 1 [19200/60000 (32%)]      Loss: 0.215437
Train Epoch: 1 [19840/60000 (33%)]      Loss: 0.213923
Train Epoch: 1 [20480/60000 (34%)]      Loss: 0.233051
Train Epoch: 1 [21120/60000 (35%)]      Loss: 0.142723
Train Epoch: 1 [21760/60000 (36%)]      Loss: 0.457661
Train Epoch: 1 [22400/60000 (37%)]      Loss: 0.185735
Train Epoch: 1 [23040/60000 (38%)]      Loss: 0.234830
Train Epoch: 1 [23680/60000 (39%)]      Loss: 0.204375
Train Epoch: 1 [24320/60000 (41%)]      Loss: 0.110013
Train Epoch: 1 [24960/60000 (42%)]      Loss: 0.128131
Train Epoch: 1 [25600/60000 (43%)]      Loss: 0.172580
Train Epoch: 1 [26240/60000 (44%)]      Loss: 0.234568
Train Epoch: 1 [26880/60000 (45%)]      Loss: 0.257909
Train Epoch: 1 [27520/60000 (46%)]      Loss: 0.054251
Train Epoch: 1 [28160/60000 (47%)]      Loss: 0.188978
Train Epoch: 1 [28800/60000 (48%)]      Loss: 0.087670
Train Epoch: 1 [29440/60000 (49%)]      Loss: 0.077402
Train Epoch: 1 [30080/60000 (50%)]      Loss: 0.231409
Train Epoch: 1 [30720/60000 (51%)]      Loss: 0.235593
Train Epoch: 1 [31360/60000 (52%)]      Loss: 0.258365
Train Epoch: 1 [32000/60000 (53%)]      Loss: 0.197230
Train Epoch: 1 [32640/60000 (54%)]      Loss: 0.128071
Train Epoch: 1 [33280/60000 (55%)]      Loss: 0.206129
Train Epoch: 1 [33920/60000 (57%)]      Loss: 0.123018
Train Epoch: 1 [34560/60000 (58%)]      Loss: 0.137504
Train Epoch: 1 [35200/60000 (59%)]      Loss: 0.223426
Train Epoch: 1 [35840/60000 (60%)]      Loss: 0.139901
Train Epoch: 1 [36480/60000 (61%)]      Loss: 0.200205
Train Epoch: 1 [37120/60000 (62%)]      Loss: 0.163435
Train Epoch: 1 [37760/60000 (63%)]      Loss: 0.096402
Train Epoch: 1 [38400/60000 (64%)]      Loss: 0.071706
Train Epoch: 1 [39040/60000 (65%)]      Loss: 0.087951
Train Epoch: 1 [39680/60000 (66%)]      Loss: 0.447814
Train Epoch: 1 [40320/60000 (67%)]      Loss: 0.260939
Train Epoch: 1 [40960/60000 (68%)]      Loss: 0.180550
Train Epoch: 1 [41600/60000 (69%)]      Loss: 0.151379
Train Epoch: 1 [42240/60000 (70%)]      Loss: 0.207344
Train Epoch: 1 [42880/60000 (71%)]      Loss: 0.108654
Train Epoch: 1 [43520/60000 (72%)]      Loss: 0.080621
Train Epoch: 1 [44160/60000 (74%)]      Loss: 0.162784
Train Epoch: 1 [44800/60000 (75%)]      Loss: 0.092147
Train Epoch: 1 [45440/60000 (76%)]      Loss: 0.150746
Train Epoch: 1 [46080/60000 (77%)]      Loss: 0.059836
Train Epoch: 1 [46720/60000 (78%)]      Loss: 0.121394
Train Epoch: 1 [47360/60000 (79%)]      Loss: 0.078257
Train Epoch: 1 [48000/60000 (80%)]      Loss: 0.090393
Train Epoch: 1 [48640/60000 (81%)]      Loss: 0.259247
Train Epoch: 1 [49280/60000 (82%)]      Loss: 0.164246
Train Epoch: 1 [49920/60000 (83%)]      Loss: 0.099269
Train Epoch: 1 [50560/60000 (84%)]      Loss: 0.108184
Train Epoch: 1 [51200/60000 (85%)]      Loss: 0.086916
Train Epoch: 1 [51840/60000 (86%)]      Loss: 0.185346
Train Epoch: 1 [52480/60000 (87%)]      Loss: 0.110255
Train Epoch: 1 [53120/60000 (88%)]      Loss: 0.035543
Train Epoch: 1 [53760/60000 (90%)]      Loss: 0.082091
Train Epoch: 1 [54400/60000 (91%)]      Loss: 0.026007
Train Epoch: 1 [55040/60000 (92%)]      Loss: 0.254455
Train Epoch: 1 [55680/60000 (93%)]      Loss: 0.140955
Train Epoch: 1 [56320/60000 (94%)]      Loss: 0.135735
Train Epoch: 1 [56960/60000 (95%)]      Loss: 0.084605
Train Epoch: 1 [57600/60000 (96%)]      Loss: 0.150209
Train Epoch: 1 [58240/60000 (97%)]      Loss: 0.122805
Train Epoch: 1 [58880/60000 (98%)]      Loss: 0.091303
Train Epoch: 1 [59520/60000 (99%)]      Loss: 0.116538

Test set: Average loss: 0.0538, Accuracy: 9818/10000 (98%)

Train Epoch: 2 [0/60000 (0%)]   Loss: 0.106577
Train Epoch: 2 [640/60000 (1%)] Loss: 0.075147
Train Epoch: 2 [1280/60000 (2%)]        Loss: 0.078607
Train Epoch: 2 [1920/60000 (3%)]        Loss: 0.157173
Train Epoch: 2 [2560/60000 (4%)]        Loss: 0.035629
Train Epoch: 2 [3200/60000 (5%)]        Loss: 0.084960
Train Epoch: 2 [3840/60000 (6%)]        Loss: 0.159891
Train Epoch: 2 [4480/60000 (7%)]        Loss: 0.104043
Train Epoch: 2 [5120/60000 (9%)]        Loss: 0.160765
Train Epoch: 2 [5760/60000 (10%)]       Loss: 0.065120
Train Epoch: 2 [6400/60000 (11%)]       Loss: 0.040306
Train Epoch: 2 [7040/60000 (12%)]       Loss: 0.038905
Train Epoch: 2 [7680/60000 (13%)]       Loss: 0.062089
Train Epoch: 2 [8320/60000 (14%)]       Loss: 0.068782
Train Epoch: 2 [8960/60000 (15%)]       Loss: 0.034926
Train Epoch: 2 [9600/60000 (16%)]       Loss: 0.138813
Train Epoch: 2 [10240/60000 (17%)]      Loss: 0.148368
Train Epoch: 2 [10880/60000 (18%)]      Loss: 0.100874
Train Epoch: 2 [11520/60000 (19%)]      Loss: 0.103685
Train Epoch: 2 [12160/60000 (20%)]      Loss: 0.040336
Train Epoch: 2 [12800/60000 (21%)]      Loss: 0.066466
Train Epoch: 2 [13440/60000 (22%)]      Loss: 0.059597
Train Epoch: 2 [14080/60000 (23%)]      Loss: 0.128494
Train Epoch: 2 [14720/60000 (25%)]      Loss: 0.027818
Train Epoch: 2 [15360/60000 (26%)]      Loss: 0.149626
Train Epoch: 2 [16000/60000 (27%)]      Loss: 0.018560
Train Epoch: 2 [16640/60000 (28%)]      Loss: 0.274478
Train Epoch: 2 [17280/60000 (29%)]      Loss: 0.032222
Train Epoch: 2 [17920/60000 (30%)]      Loss: 0.061621
Train Epoch: 2 [18560/60000 (31%)]      Loss: 0.158734
Train Epoch: 2 [19200/60000 (32%)]      Loss: 0.062242
Train Epoch: 2 [19840/60000 (33%)]      Loss: 0.111444
Train Epoch: 2 [20480/60000 (34%)]      Loss: 0.136797
Train Epoch: 2 [21120/60000 (35%)]      Loss: 0.078705
Train Epoch: 2 [21760/60000 (36%)]      Loss: 0.080837
Train Epoch: 2 [22400/60000 (37%)]      Loss: 0.077213
Train Epoch: 2 [23040/60000 (38%)]      Loss: 0.066617
Train Epoch: 2 [23680/60000 (39%)]      Loss: 0.106067
Train Epoch: 2 [24320/60000 (41%)]      Loss: 0.015600
Train Epoch: 2 [24960/60000 (42%)]      Loss: 0.202157
Train Epoch: 2 [25600/60000 (43%)]      Loss: 0.109476
Train Epoch: 2 [26240/60000 (44%)]      Loss: 0.048099
Train Epoch: 2 [26880/60000 (45%)]      Loss: 0.050753
Train Epoch: 2 [27520/60000 (46%)]      Loss: 0.085549
Train Epoch: 2 [28160/60000 (47%)]      Loss: 0.041693
Train Epoch: 2 [28800/60000 (48%)]      Loss: 0.273292
Train Epoch: 2 [29440/60000 (49%)]      Loss: 0.118760
Train Epoch: 2 [30080/60000 (50%)]      Loss: 0.170979
Train Epoch: 2 [30720/60000 (51%)]      Loss: 0.079564
Train Epoch: 2 [31360/60000 (52%)]      Loss: 0.022114
Train Epoch: 2 [32000/60000 (53%)]      Loss: 0.024172
Train Epoch: 2 [32640/60000 (54%)]      Loss: 0.049111
Train Epoch: 2 [33280/60000 (55%)]      Loss: 0.042748
Train Epoch: 2 [33920/60000 (57%)]      Loss: 0.134117
Train Epoch: 2 [34560/60000 (58%)]      Loss: 0.103861
Train Epoch: 2 [35200/60000 (59%)]      Loss: 0.028360
Train Epoch: 2 [35840/60000 (60%)]      Loss: 0.022952
Train Epoch: 2 [36480/60000 (61%)]      Loss: 0.101560
Train Epoch: 2 [37120/60000 (62%)]      Loss: 0.064199
Train Epoch: 2 [37760/60000 (63%)]      Loss: 0.094824
Train Epoch: 2 [38400/60000 (64%)]      Loss: 0.097547
Train Epoch: 2 [39040/60000 (65%)]      Loss: 0.081294
Train Epoch: 2 [39680/60000 (66%)]      Loss: 0.022462
Train Epoch: 2 [40320/60000 (67%)]      Loss: 0.083735
Train Epoch: 2 [40960/60000 (68%)]      Loss: 0.045151
Train Epoch: 2 [41600/60000 (69%)]      Loss: 0.081950
Train Epoch: 2 [42240/60000 (70%)]      Loss: 0.047900
Train Epoch: 2 [42880/60000 (71%)]      Loss: 0.043229
Train Epoch: 2 [43520/60000 (72%)]      Loss: 0.016031
Train Epoch: 2 [44160/60000 (74%)]      Loss: 0.035868
Train Epoch: 2 [44800/60000 (75%)]      Loss: 0.102944
Train Epoch: 2 [45440/60000 (76%)]      Loss: 0.035198
Train Epoch: 2 [46080/60000 (77%)]      Loss: 0.101788
Train Epoch: 2 [46720/60000 (78%)]      Loss: 0.039883
Train Epoch: 2 [47360/60000 (79%)]      Loss: 0.121418
Train Epoch: 2 [48000/60000 (80%)]      Loss: 0.107532
Train Epoch: 2 [48640/60000 (81%)]      Loss: 0.165804
Train Epoch: 2 [49280/60000 (82%)]      Loss: 0.143464
Train Epoch: 2 [49920/60000 (83%)]      Loss: 0.046109
Train Epoch: 2 [50560/60000 (84%)]      Loss: 0.099891
Train Epoch: 2 [51200/60000 (85%)]      Loss: 0.046321
Train Epoch: 2 [51840/60000 (86%)]      Loss: 0.056405
Train Epoch: 2 [52480/60000 (87%)]      Loss: 0.095421
Train Epoch: 2 [53120/60000 (88%)]      Loss: 0.266824
Train Epoch: 2 [53760/60000 (90%)]      Loss: 0.109738
Train Epoch: 2 [54400/60000 (91%)]      Loss: 0.068318
Train Epoch: 2 [55040/60000 (92%)]      Loss: 0.032689
Train Epoch: 2 [55680/60000 (93%)]      Loss: 0.167101
Train Epoch: 2 [56320/60000 (94%)]      Loss: 0.018892
Train Epoch: 2 [56960/60000 (95%)]      Loss: 0.145077
Train Epoch: 2 [57600/60000 (96%)]      Loss: 0.141078
Train Epoch: 2 [58240/60000 (97%)]      Loss: 0.074805
Train Epoch: 2 [58880/60000 (98%)]      Loss: 0.115343
Train Epoch: 2 [59520/60000 (99%)]      Loss: 0.106614

Test set: Average loss: 0.0397, Accuracy: 9864/10000 (99%)

Train Epoch: 3 [0/60000 (0%)]   Loss: 0.069292
Train Epoch: 3 [640/60000 (1%)] Loss: 0.044671
Train Epoch: 3 [1280/60000 (2%)]        Loss: 0.038313
Train Epoch: 3 [1920/60000 (3%)]        Loss: 0.108172
Train Epoch: 3 [2560/60000 (4%)]        Loss: 0.040344
Train Epoch: 3 [3200/60000 (5%)]        Loss: 0.060696
Train Epoch: 3 [3840/60000 (6%)]        Loss: 0.019324
Train Epoch: 3 [4480/60000 (7%)]        Loss: 0.043728
Train Epoch: 3 [5120/60000 (9%)]        Loss: 0.037958
Train Epoch: 3 [5760/60000 (10%)]       Loss: 0.046901
Train Epoch: 3 [6400/60000 (11%)]       Loss: 0.047915
Train Epoch: 3 [7040/60000 (12%)]       Loss: 0.050677
Train Epoch: 3 [7680/60000 (13%)]       Loss: 0.048815
Train Epoch: 3 [8320/60000 (14%)]       Loss: 0.105492
Train Epoch: 3 [8960/60000 (15%)]       Loss: 0.061945
Train Epoch: 3 [9600/60000 (16%)]       Loss: 0.188865
Train Epoch: 3 [10240/60000 (17%)]      Loss: 0.022122
Train Epoch: 3 [10880/60000 (18%)]      Loss: 0.163498
Train Epoch: 3 [11520/60000 (19%)]      Loss: 0.022859
Train Epoch: 3 [12160/60000 (20%)]      Loss: 0.083400
Train Epoch: 3 [12800/60000 (21%)]      Loss: 0.033851
Train Epoch: 3 [13440/60000 (22%)]      Loss: 0.012424
Train Epoch: 3 [14080/60000 (23%)]      Loss: 0.069556
Train Epoch: 3 [14720/60000 (25%)]      Loss: 0.031442
Train Epoch: 3 [15360/60000 (26%)]      Loss: 0.050348
Train Epoch: 3 [16000/60000 (27%)]      Loss: 0.274206
Train Epoch: 3 [16640/60000 (28%)]      Loss: 0.068391
Train Epoch: 3 [17280/60000 (29%)]      Loss: 0.104070
Train Epoch: 3 [17920/60000 (30%)]      Loss: 0.136303
Train Epoch: 3 [18560/60000 (31%)]      Loss: 0.085279
Train Epoch: 3 [19200/60000 (32%)]      Loss: 0.143739
Train Epoch: 3 [19840/60000 (33%)]      Loss: 0.165779
Train Epoch: 3 [20480/60000 (34%)]      Loss: 0.006965
Train Epoch: 3 [21120/60000 (35%)]      Loss: 0.031690
Train Epoch: 3 [21760/60000 (36%)]      Loss: 0.065237
Train Epoch: 3 [22400/60000 (37%)]      Loss: 0.245035
Train Epoch: 3 [23040/60000 (38%)]      Loss: 0.171532
Train Epoch: 3 [23680/60000 (39%)]      Loss: 0.056561
Train Epoch: 3 [24320/60000 (41%)]      Loss: 0.024486
Train Epoch: 3 [24960/60000 (42%)]      Loss: 0.081291
Train Epoch: 3 [25600/60000 (43%)]      Loss: 0.084563
Train Epoch: 3 [26240/60000 (44%)]      Loss: 0.069468
Train Epoch: 3 [26880/60000 (45%)]      Loss: 0.045520
Train Epoch: 3 [27520/60000 (46%)]      Loss: 0.087142
Train Epoch: 3 [28160/60000 (47%)]      Loss: 0.062932
Train Epoch: 3 [28800/60000 (48%)]      Loss: 0.241528
Train Epoch: 3 [29440/60000 (49%)]      Loss: 0.038127
Train Epoch: 3 [30080/60000 (50%)]      Loss: 0.157644
Train Epoch: 3 [30720/60000 (51%)]      Loss: 0.119052
Train Epoch: 3 [31360/60000 (52%)]      Loss: 0.121110
Train Epoch: 3 [32000/60000 (53%)]      Loss: 0.138711
Train Epoch: 3 [32640/60000 (54%)]      Loss: 0.028795
Train Epoch: 3 [33280/60000 (55%)]      Loss: 0.033930
Train Epoch: 3 [33920/60000 (57%)]      Loss: 0.025953
Train Epoch: 3 [34560/60000 (58%)]      Loss: 0.042950
Train Epoch: 3 [35200/60000 (59%)]      Loss: 0.115884
Train Epoch: 3 [35840/60000 (60%)]      Loss: 0.178442
Train Epoch: 3 [36480/60000 (61%)]      Loss: 0.068271
Train Epoch: 3 [37120/60000 (62%)]      Loss: 0.143876
Train Epoch: 3 [37760/60000 (63%)]      Loss: 0.114486
Train Epoch: 3 [38400/60000 (64%)]      Loss: 0.077184
Train Epoch: 3 [39040/60000 (65%)]      Loss: 0.044233
Train Epoch: 3 [39680/60000 (66%)]      Loss: 0.028880
Train Epoch: 3 [40320/60000 (67%)]      Loss: 0.136192
Train Epoch: 3 [40960/60000 (68%)]      Loss: 0.146052
Train Epoch: 3 [41600/60000 (69%)]      Loss: 0.117999
Train Epoch: 3 [42240/60000 (70%)]      Loss: 0.075927
Train Epoch: 3 [42880/60000 (71%)]      Loss: 0.091046
Train Epoch: 3 [43520/60000 (72%)]      Loss: 0.015768
Train Epoch: 3 [44160/60000 (74%)]      Loss: 0.084175
Train Epoch: 3 [44800/60000 (75%)]      Loss: 0.013997
Train Epoch: 3 [45440/60000 (76%)]      Loss: 0.088690
Train Epoch: 3 [46080/60000 (77%)]      Loss: 0.086683
Train Epoch: 3 [46720/60000 (78%)]      Loss: 0.099416
Train Epoch: 3 [47360/60000 (79%)]      Loss: 0.056337
Train Epoch: 3 [48000/60000 (80%)]      Loss: 0.091352
Train Epoch: 3 [48640/60000 (81%)]      Loss: 0.106782
Train Epoch: 3 [49280/60000 (82%)]      Loss: 0.022478
Train Epoch: 3 [49920/60000 (83%)]      Loss: 0.037793
Train Epoch: 3 [50560/60000 (84%)]      Loss: 0.026040
Train Epoch: 3 [51200/60000 (85%)]      Loss: 0.168085
Train Epoch: 3 [51840/60000 (86%)]      Loss: 0.026550
Train Epoch: 3 [52480/60000 (87%)]      Loss: 0.057223
Train Epoch: 3 [53120/60000 (88%)]      Loss: 0.289324
Train Epoch: 3 [53760/60000 (90%)]      Loss: 0.132689
Train Epoch: 3 [54400/60000 (91%)]      Loss: 0.052605
Train Epoch: 3 [55040/60000 (92%)]      Loss: 0.072443
Train Epoch: 3 [55680/60000 (93%)]      Loss: 0.049246
Train Epoch: 3 [56320/60000 (94%)]      Loss: 0.142484
Train Epoch: 3 [56960/60000 (95%)]      Loss: 0.009450
Train Epoch: 3 [57600/60000 (96%)]      Loss: 0.028935
Train Epoch: 3 [58240/60000 (97%)]      Loss: 0.171060
Train Epoch: 3 [58880/60000 (98%)]      Loss: 0.052875
Train Epoch: 3 [59520/60000 (99%)]      Loss: 0.037833

Test set: Average loss: 0.0351, Accuracy: 9879/10000 (99%)

Train Epoch: 4 [0/60000 (0%)]   Loss: 0.032983
Train Epoch: 4 [640/60000 (1%)] Loss: 0.016670
Train Epoch: 4 [1280/60000 (2%)]        Loss: 0.098418
Train Epoch: 4 [1920/60000 (3%)]        Loss: 0.019896
Train Epoch: 4 [2560/60000 (4%)]        Loss: 0.080707
Train Epoch: 4 [3200/60000 (5%)]        Loss: 0.131215
Train Epoch: 4 [3840/60000 (6%)]        Loss: 0.044431
Train Epoch: 4 [4480/60000 (7%)]        Loss: 0.021734
Train Epoch: 4 [5120/60000 (9%)]        Loss: 0.016801
Train Epoch: 4 [5760/60000 (10%)]       Loss: 0.027567
Train Epoch: 4 [6400/60000 (11%)]       Loss: 0.018743
Train Epoch: 4 [7040/60000 (12%)]       Loss: 0.086326
Train Epoch: 4 [7680/60000 (13%)]       Loss: 0.012632
Train Epoch: 4 [8320/60000 (14%)]       Loss: 0.025232
Train Epoch: 4 [8960/60000 (15%)]       Loss: 0.064803
Train Epoch: 4 [9600/60000 (16%)]       Loss: 0.048574
Train Epoch: 4 [10240/60000 (17%)]      Loss: 0.017140
Train Epoch: 4 [10880/60000 (18%)]      Loss: 0.061686
Train Epoch: 4 [11520/60000 (19%)]      Loss: 0.024956
Train Epoch: 4 [12160/60000 (20%)]      Loss: 0.104067
Train Epoch: 4 [12800/60000 (21%)]      Loss: 0.169216
Train Epoch: 4 [13440/60000 (22%)]      Loss: 0.111012
Train Epoch: 4 [14080/60000 (23%)]      Loss: 0.031446
Train Epoch: 4 [14720/60000 (25%)]      Loss: 0.049984
Train Epoch: 4 [15360/60000 (26%)]      Loss: 0.007248
Train Epoch: 4 [16000/60000 (27%)]      Loss: 0.036388
Train Epoch: 4 [16640/60000 (28%)]      Loss: 0.017943
Train Epoch: 4 [17280/60000 (29%)]      Loss: 0.032785
Train Epoch: 4 [17920/60000 (30%)]      Loss: 0.126666
Train Epoch: 4 [18560/60000 (31%)]      Loss: 0.049946
Train Epoch: 4 [19200/60000 (32%)]      Loss: 0.018177
Train Epoch: 4 [19840/60000 (33%)]      Loss: 0.026083
Train Epoch: 4 [20480/60000 (34%)]      Loss: 0.144403
Train Epoch: 4 [21120/60000 (35%)]      Loss: 0.045252
Train Epoch: 4 [21760/60000 (36%)]      Loss: 0.015793
Train Epoch: 4 [22400/60000 (37%)]      Loss: 0.035754
Train Epoch: 4 [23040/60000 (38%)]      Loss: 0.050909
Train Epoch: 4 [23680/60000 (39%)]      Loss: 0.167108
Train Epoch: 4 [24320/60000 (41%)]      Loss: 0.013929
Train Epoch: 4 [24960/60000 (42%)]      Loss: 0.048417
Train Epoch: 4 [25600/60000 (43%)]      Loss: 0.089966
Train Epoch: 4 [26240/60000 (44%)]      Loss: 0.045441
Train Epoch: 4 [26880/60000 (45%)]      Loss: 0.035128
Train Epoch: 4 [27520/60000 (46%)]      Loss: 0.191105
Train Epoch: 4 [28160/60000 (47%)]      Loss: 0.065759
Train Epoch: 4 [28800/60000 (48%)]      Loss: 0.056485
Train Epoch: 4 [29440/60000 (49%)]      Loss: 0.081021
Train Epoch: 4 [30080/60000 (50%)]      Loss: 0.162680
Train Epoch: 4 [30720/60000 (51%)]      Loss: 0.235770
Train Epoch: 4 [31360/60000 (52%)]      Loss: 0.007725
Train Epoch: 4 [32000/60000 (53%)]      Loss: 0.016277
Train Epoch: 4 [32640/60000 (54%)]      Loss: 0.048443
Train Epoch: 4 [33280/60000 (55%)]      Loss: 0.114999
Train Epoch: 4 [33920/60000 (57%)]      Loss: 0.024478
Train Epoch: 4 [34560/60000 (58%)]      Loss: 0.035609
Train Epoch: 4 [35200/60000 (59%)]      Loss: 0.091434
Train Epoch: 4 [35840/60000 (60%)]      Loss: 0.014785
Train Epoch: 4 [36480/60000 (61%)]      Loss: 0.082030
Train Epoch: 4 [37120/60000 (62%)]      Loss: 0.037182
Train Epoch: 4 [37760/60000 (63%)]      Loss: 0.013195
Train Epoch: 4 [38400/60000 (64%)]      Loss: 0.059536
Train Epoch: 4 [39040/60000 (65%)]      Loss: 0.112017
Train Epoch: 4 [39680/60000 (66%)]      Loss: 0.004864
Train Epoch: 4 [40320/60000 (67%)]      Loss: 0.027821
Train Epoch: 4 [40960/60000 (68%)]      Loss: 0.101282
Train Epoch: 4 [41600/60000 (69%)]      Loss: 0.007805
Train Epoch: 4 [42240/60000 (70%)]      Loss: 0.007703
Train Epoch: 4 [42880/60000 (71%)]      Loss: 0.102813
Train Epoch: 4 [43520/60000 (72%)]      Loss: 0.073287
Train Epoch: 4 [44160/60000 (74%)]      Loss: 0.036122
Train Epoch: 4 [44800/60000 (75%)]      Loss: 0.007843
Train Epoch: 4 [45440/60000 (76%)]      Loss: 0.020743
Train Epoch: 4 [46080/60000 (77%)]      Loss: 0.104495
Train Epoch: 4 [46720/60000 (78%)]      Loss: 0.029794
Train Epoch: 4 [47360/60000 (79%)]      Loss: 0.076501
Train Epoch: 4 [48000/60000 (80%)]      Loss: 0.070763
Train Epoch: 4 [48640/60000 (81%)]      Loss: 0.028860
Train Epoch: 4 [49280/60000 (82%)]      Loss: 0.019709
Train Epoch: 4 [49920/60000 (83%)]      Loss: 0.066465
Train Epoch: 4 [50560/60000 (84%)]      Loss: 0.008928
Train Epoch: 4 [51200/60000 (85%)]      Loss: 0.018843
Train Epoch: 4 [51840/60000 (86%)]      Loss: 0.035815
Train Epoch: 4 [52480/60000 (87%)]      Loss: 0.060984
Train Epoch: 4 [53120/60000 (88%)]      Loss: 0.053025
Train Epoch: 4 [53760/60000 (90%)]      Loss: 0.057212
Train Epoch: 4 [54400/60000 (91%)]      Loss: 0.060626
Train Epoch: 4 [55040/60000 (92%)]      Loss: 0.004556
Train Epoch: 4 [55680/60000 (93%)]      Loss: 0.010698
Train Epoch: 4 [56320/60000 (94%)]      Loss: 0.024416
Train Epoch: 4 [56960/60000 (95%)]      Loss: 0.031671
Train Epoch: 4 [57600/60000 (96%)]      Loss: 0.124095
Train Epoch: 4 [58240/60000 (97%)]      Loss: 0.083385
Train Epoch: 4 [58880/60000 (98%)]      Loss: 0.039730
Train Epoch: 4 [59520/60000 (99%)]      Loss: 0.077822

Test set: Average loss: 0.0343, Accuracy: 9879/10000 (99%)
```



```
root@h100vm:/workspace/MS-AMP/examples# deepspeed cifar10_deepspeed.py --deepspeed --deepspeed_config ds_config.json
[2024-09-23 10:10:13,831] [INFO] [real_accelerator.py:191:get_accelerator] Setting ds_accelerator to cuda (auto detect)
```



```
[2024-09-23 10:11:01,021] [INFO] [fused_optimizer.py:345:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:11:01,021] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  2400] loss: 1.209
[2,  2600] loss: 1.222
[2024-09-23 10:11:02,257] [INFO] [fused_optimizer.py:352:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:11:02,257] [INFO] [fused_optimizer.py:353:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2,  2800] loss: 1.247
[2024-09-23 10:11:02,482] [INFO] [logging.py:96:log_dist] [Rank 0] step=6000, skipped=10, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:11:02,482] [INFO] [timer.py:260:stop] epoch=0/micro_step=6000/global_step=6000, RunningAvgSamplesPerSec=6493.909488298559, CurrSamplesPerSec=5892.428132408464, MemAllocated=0.06GB, MaxMemAllocated=0.06GB
[2024-09-23 10:11:02,541] [INFO] [fused_optimizer.py:344:_update_scale]
Grad overflow on iteration 6023
[2024-09-23 10:11:02,542] [INFO] [fused_optimizer.py:345:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:11:02,542] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  3000] loss: 1.203
Finished Training
GroundTruth:    cat  ship  ship plane
Predicted:    cat   car  ship  ship
Accuracy of the network on the 10000 test images: 55 %
Accuracy of plane : 61 %
Accuracy of   car : 74 %
Accuracy of  bird : 48 %
Accuracy of   cat : 40 %
Accuracy of  deer : 39 %
Accuracy of   dog : 48 %
Accuracy of  frog : 55 %
Accuracy of horse : 68 %
Accuracy of  ship : 77 %
Accuracy of truck : 44 %
[2024-09-23 10:11:09,910] [INFO] [launch.py:347:main] Process 67374 exits successfully.
```



```
root@h100vm:/workspace/MS-AMP/examples# deepspeed cifar10_deepspeed.py --deepspeed --deepspeed_config ds_config_msamp.json
```



```
  self._dummy_overflow_buf = get_accelerator().IntTensor([0])
[2024-09-23 10:11:49,606] [INFO] [logging.py:96:log_dist] [Rank 0] Using DeepSpeed Optimizer param name adam as basic optimizer
[2024-09-23 10:11:49,850] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Basic Optimizer = DSAdam
[2024-09-23 10:11:49,850] [INFO] [logging.py:96:log_dist] [Rank 0] Creating fp8 optimizer with dynamic loss scale
[2024-09-23 10:11:49,859] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Final Optimizer = adam
[2024-09-23 10:11:49,859] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed using configured LR scheduler = WarmupLR
[2024-09-23 10:11:49,859] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed LR Scheduler = <deepspeed.runtime.lr_schedules.WarmupLR object at 0x7fb1c839d570>
[2024-09-23 10:11:49,859] [INFO] [logging.py:96:log_dist] [Rank 0] step=0, skipped=0, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:11:49,859] [INFO] [config.py:984:print] DeepSpeedEngine configuration:
[2024-09-23 10:11:49,859] [INFO] [config.py:988:print]   activation_checkpointing_config  {
    "partition_activations": false,
    "contiguous_memory_optimization": false,
    "cpu_checkpointing": false,
    "number_checkpoints": null,
    "synchronize_checkpoint_boundary": false,
    "profile": false
}
[2024-09-23 10:11:49,859] [INFO] [config.py:988:print]   aio_config ................... {'block_size': 1048576, 'queue_depth': 8, 'thread_count': 1, 'single_submit': False, 'overlap_events': True}
[2024-09-23 10:11:49,859] [INFO] [config.py:988:print]   amp_enabled .................. False
[2024-09-23 10:11:49,859] [INFO] [config.py:988:print]   amp_params ................... False
[2024-09-23 10:11:49,859] [INFO] [config.py:988:print]   autotuning_config ............ {
    "enabled": false,
    "start_step": null,
    "end_step": null,
    "metric_path": null,
    "arg_mappings": null,
    "metric": "throughput",
    "model_info": null,
    "results_dir": "autotuning_results",
    "exps_dir": "autotuning_exps",
    "overwrite": true,
    "fast": true,
    "start_profile_step": 3,
    "end_profile_step": 5,
    "tuner_type": "gridsearch",
    "tuner_early_stopping": 5,
    "tuner_num_trials": 50,
    "model_info_path": null,
    "mp_size": 1,
    "max_train_batch_size": null,
    "min_train_batch_size": 1,
    "max_train_micro_batch_size_per_gpu": 1.024000e+03,
    "min_train_micro_batch_size_per_gpu": 1,
    "num_tuning_micro_batch_sizes": 3
}
[2024-09-23 10:11:49,859] [INFO] [config.py:988:print]   bfloat16_enabled ............. False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   checkpoint_parallel_write_pipeline  False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   checkpoint_tag_validation_enabled  True
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   checkpoint_tag_validation_fail  False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   comms_config ................. <deepspeed.comm.config.DeepSpeedCommsConfig object at 0x7fb5369277f0>
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   communication_data_type ...... None
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   compression_config ........... {'weight_quantization': {'shared_parameters': {'enabled': False, 'quantizer_kernel': False, 'schedule_offset': 0, 'quantize_groups': 1, 'quantize_verbose': False, 'quantization_type': 'symmetric', 'quantize_weight_in_forward': False, 'rounding': 'nearest', 'fp16_mixed_quantize': False, 'quantize_change_ratio': 0.001}, 'different_groups': {}}, 'activation_quantization': {'shared_parameters': {'enabled': False, 'quantization_type': 'symmetric', 'range_calibration': 'dynamic', 'schedule_offset': 1000}, 'different_groups': {}}, 'sparse_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'row_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'head_pruning': {'shared_parameters': {'enabled': False, 'method': 'topk', 'schedule_offset': 1000}, 'different_groups': {}}, 'channel_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'layer_reduction': {'enabled': False}}
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   curriculum_enabled_legacy .... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   curriculum_params_legacy ..... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   data_efficiency_config ....... {'enabled': False, 'seed': 1234, 'data_sampling': {'enabled': False, 'num_epochs': 1000, 'num_workers': 0, 'curriculum_learning': {'enabled': False}}, 'data_routing': {'enabled': False, 'random_ltd': {'enabled': False, 'layer_token_lr_schedule': {'enabled': False}}}}
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   data_efficiency_enabled ...... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   dataloader_drop_last ......... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   disable_allgather ............ False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   dump_state ................... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   dynamic_loss_scale_args ...... {'init_scale': 32768, 'scale_window': 500, 'delayed_shift': 2, 'consecutive_hysteresis': False, 'min_scale': 1}
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_enabled ........... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_gas_boundary_resolution  1
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_layer_name ........ bert.encoder.layer
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_layer_num ......... 0
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_max_iter .......... 100
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_stability ......... 1e-06
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_tol ............... 0.01
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   eigenvalue_verbose ........... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   elasticity_enabled ........... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   flops_profiler_config ........ {
    "enabled": false,
    "recompute_fwd_factor": 0.0,
    "profile_step": 1,
    "module_depth": -1,
    "top_modules": 1,
    "detailed": true,
    "output_file": null
}
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   fp16_auto_cast ............... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   fp16_enabled ................. True
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   fp16_master_weights_and_gradients  False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   global_rank .................. 0
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   grad_accum_dtype ............. None
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   gradient_accumulation_steps .. 1
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   gradient_clipping ............ 1
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   gradient_predivide_factor .... 1.0
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   graph_harvesting ............. False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   hybrid_engine ................ enabled=False max_out_tokens=512 inference_tp_size=1 release_inference_cache=False pin_parameters=True tp_gather_partition_size=8
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   initial_dynamic_scale ........ 32768
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   load_universal_checkpoint .... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   loss_scale ................... 0
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   memory_breakdown ............. False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   mics_hierarchial_params_gather  False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   mics_shard_size .............. -1
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   monitor_config ............... tensorboard=TensorBoardConfig(enabled=False, output_path='', job_name='DeepSpeedJobName') wandb=WandbConfig(enabled=False, group=None, team=None, project='deepspeed') csv_monitor=CSVConfig(enabled=False, output_path='', job_name='DeepSpeedJobName') enabled=False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   msamp_enabled ................ True
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   msamp_optlevel ............... O2
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   msamp_use_te ................. False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   nebula_config ................ {
    "enabled": false,
    "persistent_storage_path": null,
    "persistent_time_interval": 100,
    "num_of_version_in_retention": 2,
    "enable_nebula_load": true,
    "load_path": null
}
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   optimizer_legacy_fusion ...... False
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   optimizer_name ............... adam
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   optimizer_params ............. {'lr': 0.001, 'betas': [0.8, 0.999], 'eps': 1e-08, 'weight_decay': 3e-07}
[2024-09-23 10:11:49,860] [INFO] [config.py:988:print]   pipeline ..................... {'stages': 'auto', 'partition': 'best', 'seed_layers': False, 'activation_checkpoint_interval': 0, 'pipe_partitioned': True, 'grad_partitioned': True}
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   pld_enabled .................. False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   pld_params ................... False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   prescale_gradients ........... False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   scheduler_name ............... WarmupLR
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   scheduler_params ............. {'warmup_min_lr': 0, 'warmup_max_lr': 0.001, 'warmup_num_steps': 1000}
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   seq_parallel_communication_data_type  torch.float32
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   sparse_attention ............. None
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   sparse_gradients_enabled ..... False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   steps_per_print .............. 2000
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   train_batch_size ............. 16
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   train_micro_batch_size_per_gpu  16
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   use_data_before_expert_parallel_  False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   use_node_local_storage ....... False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   wall_clock_breakdown ......... False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   weight_quantization_config ... None
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   world_size ................... 1
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   zero_allow_untested_optimizer  False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   zero_config .................. stage=0 contiguous_gradients=True reduce_scatter=True reduce_bucket_size=50000000 use_multi_rank_bucket_allreduce=True allgather_partitions=True allgather_bucket_size=50000000 overlap_comm=True load_from_fp32_weights=True elastic_checkpoint=False offload_param=None offload_optimizer=None sub_group_size=1,000,000,000 cpu_offload_param=None cpu_offload_use_pin_memory=None prefetch_bucket_size=50,000,000 param_persistence_threshold=100,000 model_persistence_threshold=sys.maxsize max_live_parameters=1,000,000,000 max_reuse_distance=1,000,000,000 gather_16bit_weights_on_model_save=False stage3_gather_fp16_weights_on_model_save=False ignore_unused_parameters=True legacy_stage1=False round_robin_gradients=False zero_hpz_partition_size=1 zero_quantized_weights=False zero_quantized_nontrainable_weights=False zero_quantized_gradients=False mics_shard_size=-1 mics_hierarchical_params_gather=False memory_efficient_linear=True pipeline_loading_checkpoint=False override_module_apply=True
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   zero_enabled ................. False
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   zero_force_ds_cpu_optimizer .. True
[2024-09-23 10:11:49,861] [INFO] [config.py:988:print]   zero_optimization_stage ...... 0
[2024-09-23 10:11:49,861] [INFO] [config.py:974:print_user_config]   json = {
    "train_batch_size": 16,
    "steps_per_print": 2.000000e+03,
    "optimizer": {
        "type": "Adam",
        "params": {
            "lr": 0.001,
            "betas": [0.8, 0.999],
            "eps": 1e-08,
            "weight_decay": 3e-07
        }
    },
    "scheduler": {
        "type": "WarmupLR",
        "params": {
            "warmup_min_lr": 0,
            "warmup_max_lr": 0.001,
            "warmup_num_steps": 1000
        }
    },
    "gradient_clipping": 1,
    "prescale_gradients": false,
    "fp16": {
        "enabled": true,
        "fp16_master_weights_and_grads": false,
        "loss_scale": 0,
        "loss_scale_window": 500,
        "hysteresis": 2,
        "min_loss_scale": 1,
        "initial_scale_power": 15
    },
    "msamp": {
        "enabled": true,
        "opt_level": "O2"
    },
    "wall_clock_breakdown": false,
    "zero_optimization": {
        "stage": 0,
        "allgather_partitions": true,
        "reduce_scatter": true,
        "allgather_bucket_size": 5.000000e+07,
        "reduce_bucket_size": 5.000000e+07,
        "overlap_comm": true,
        "contiguous_gradients": true,
        "cpu_offload": false
    }
}
model: Net(
  (conv1): Conv2d(3, 6, kernel_size=(5, 5), stride=(1, 1))
  (pool): MaxPool2d(kernel_size=2, stride=2, padding=0, dilation=1, ceil_mode=False)
  (conv2): Conv2d(6, 16, kernel_size=(5, 5), stride=(1, 1))
  (fc1): FP8Linear(in_features=400, out_features=120, bias=True)
  (fc2): FP8Linear(in_features=120, out_features=84, bias=True)
  (fc3): FP8Linear(in_features=84, out_features=10, bias=True)
)
fp16=True
[1,   200] loss: 2.104
[1,   400] loss: 1.873
[2024-09-23 10:11:54,722] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:11:54,722] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 32768 to 65536
[2024-09-23 10:11:54,729] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 501
[2024-09-23 10:11:54,729] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 65536 to 32768.0
[2024-09-23 10:11:54,730] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 65536, reducing to 32768.0
[2024-09-23 10:11:55,092] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 553
[2024-09-23 10:11:55,092] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:11:55,092] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,   600] loss: 1.730
[1,   800] loss: 1.702
[1,  1000] loss: 1.662
[2024-09-23 10:11:58,695] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:11:58,695] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[1,  1200] loss: 1.597
[1,  1400] loss: 1.613
[2024-09-23 10:12:02,110] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 1522
[2024-09-23 10:12:02,110] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:02,110] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  1600] loss: 1.579
[1,  1800] loss: 1.519
[2024-09-23 10:12:05,611] [INFO] [logging.py:96:log_dist] [Rank 0] step=2000, skipped=3, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:12:05,611] [INFO] [timer.py:260:stop] epoch=0/micro_step=2000/global_step=2000, RunningAvgSamplesPerSec=2200.6575978356914, CurrSamplesPerSec=2140.4970655779534, MemAllocated=0.03GB, MaxMemAllocated=0.03GB
[1,  2000] loss: 1.502
[2024-09-23 10:12:05,783] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:05,783] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[1,  2200] loss: 1.502
[2024-09-23 10:12:07,308] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 2233
[2024-09-23 10:12:07,308] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:07,308] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  2400] loss: 1.430
[1,  2600] loss: 1.425
[2024-09-23 10:12:10,948] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:10,948] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2024-09-23 10:12:11,116] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 2757
[2024-09-23 10:12:11,116] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:11,116] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  2800] loss: 1.443
[1,  3000] loss: 1.423
[2024-09-23 10:12:14,816] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:14,817] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2,   200] loss: 1.369
[2024-09-23 10:12:15,889] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 3405
[2024-09-23 10:12:15,889] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:15,889] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,   400] loss: 1.363
[2,   600] loss: 1.355
[2024-09-23 10:12:19,544] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:19,544] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2,   800] loss: 1.332
[2024-09-23 10:12:20,221] [INFO] [logging.py:96:log_dist] [Rank 0] step=4000, skipped=6, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:12:20,221] [INFO] [timer.py:260:stop] epoch=0/micro_step=4000/global_step=4000, RunningAvgSamplesPerSec=2205.4183259109254, CurrSamplesPerSec=2144.806928952667, MemAllocated=0.03GB, MaxMemAllocated=0.03GB
[2024-09-23 10:12:20,241] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 4002
[2024-09-23 10:12:20,241] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:20,241] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  1000] loss: 1.321
[2,  1200] loss: 1.309
[2024-09-23 10:12:23,871] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:23,872] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2024-09-23 10:12:23,937] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 4512
[2024-09-23 10:12:23,937] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:23,937] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  1400] loss: 1.343
[2,  1600] loss: 1.317
[2,  1800] loss: 1.266
[2024-09-23 10:12:27,562] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:27,562] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2024-09-23 10:12:27,763] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 5042
[2024-09-23 10:12:27,763] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:27,763] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  2000] loss: 1.266
[2,  2200] loss: 1.298
[2,  2400] loss: 1.237
[2024-09-23 10:12:31,214] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:31,214] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2024-09-23 10:12:32,023] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 5661
[2024-09-23 10:12:32,023] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:32,023] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  2600] loss: 1.250
[2,  2800] loss: 1.255
[2024-09-23 10:12:34,465] [INFO] [logging.py:96:log_dist] [Rank 0] step=6000, skipped=10, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:12:34,465] [INFO] [timer.py:260:stop] epoch=0/micro_step=6000/global_step=6000, RunningAvgSamplesPerSec=2222.5069820121303, CurrSamplesPerSec=2180.3458202020856, MemAllocated=0.03GB, MaxMemAllocated=0.03GB
[2,  3000] loss: 1.238
[2024-09-23 10:12:35,647] [INFO] [fused_optimizer.py:462:_update_scale] No Grad overflow for 500 iterations
[2024-09-23 10:12:35,647] [INFO] [fused_optimizer.py:463:_update_scale] Increasing dynamic loss scale from 16384.0 to 32768.0
[2024-09-23 10:12:36,168] [INFO] [fused_optimizer.py:454:_update_scale]
Grad overflow on iteration 6210
[2024-09-23 10:12:36,169] [INFO] [fused_optimizer.py:455:_update_scale] Reducing dynamic loss scale from 32768.0 to 16384.0
[2024-09-23 10:12:36,169] [INFO] [logging.py:96:log_dist] [Rank 0] Overflow detected. Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
Finished Training
GroundTruth:    cat  ship  ship plane
Predicted:   bird plane  ship  ship
Accuracy of the network on the 10000 test images: 55 %
Accuracy of plane : 61 %
Accuracy of   car : 72 %
Accuracy of  bird : 36 %
Accuracy of   cat : 36 %
Accuracy of  deer : 46 %
Accuracy of   dog : 46 %
Accuracy of  frog : 51 %
Accuracy of horse : 71 %
Accuracy of  ship : 78 %
Accuracy of truck : 49 %
[2024-09-23 10:12:47,108] [INFO] [launch.py:347:main] Process 68106 exits successfully.
```



```
root@h100vm:/workspace/MS-AMP/examples# deepspeed cifar10_deepspeed.py --deepspeed --deepspeed_config ds_config_zero_msamp.json
```



```
2024-09-23 10:15:22,063] [INFO] [launch.py:165:main] Setting CUDA_VISIBLE_DEVICES=0
[2024-09-23 10:15:24,031] [INFO] [real_accelerator.py:191:get_accelerator] Setting ds_accelerator to cuda (auto detect)
[2024-09-23 10:15:26,103] [INFO] [comm.py:637:init_distributed] cdb=None
[2024-09-23 10:15:26,103] [INFO] [comm.py:668:init_distributed] Initializing TorchBackend in DeepSpeed with backend nccl
Files already downloaded and verified
Files already downloaded and verified
plane  ship  deer  frog
[2024-09-23 10:15:28,213] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed info: version=0.13.1, git-hash=unknown, git-branch=unknown
[2024-09-23 10:15:28,214] [WARNING] [config_utils.py:69:_process_deprecated_field] Config parameter cpu_offload is deprecated use offload_optimizer instead
[2024-09-23 10:15:28,290] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Flops Profiler Enabled: False
Using /root/.cache/torch_extensions/py310_cu122 as PyTorch extensions root...
Detected CUDA files, patching ldflags
Emitting ninja build file /root/.cache/torch_extensions/py310_cu122/fused_adam/build.ninja...
Building extension module fused_adam...
Allowing ninja to set a default number of workers... (overridable by setting the environment variable MAX_JOBS=N)
ninja: no work to do.
Loading extension module fused_adam...
Time to load fused_adam op: 0.05582547187805176 seconds
/usr/local/lib/python3.10/dist-packages/deepspeed/ops/adam/fused_adam.py:96: UserWarning: The torch.cuda.*DtypeTensor constructors are no longer recommended. It's best to use methods such as torch.tensor(data, dtype=*, device='cuda') to create tensors. (Triggered internally at /opt/pytorch/pytorch/torch/csrc/tensor/python_tensor.cpp:83.)
  self._dummy_overflow_buf = get_accelerator().IntTensor([0])
[2024-09-23 10:15:28,631] [INFO] [logging.py:96:log_dist] [Rank 0] Using DeepSpeed Optimizer param name adam as basic optimizer
[2024-09-23 10:15:28,870] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Basic Optimizer = DSAdam
[2024-09-23 10:15:28,870] [INFO] [utils.py:56:is_zero_supported_optimizer] Checking ZeRO support for optimizer=DSAdam type=<class 'msamp.optim.adam.DSAdam'>
[2024-09-23 10:15:28,870] [INFO] [logging.py:96:log_dist] [Rank 0] Creating fp16 ZeRO stage 2 optimizer
[2024-09-23 10:15:28,871] [INFO] [stage_1_and_2.py:143:__init__] Reduce bucket size 50000000
[2024-09-23 10:15:28,871] [INFO] [stage_1_and_2.py:144:__init__] Allgather bucket size 50000000
[2024-09-23 10:15:28,871] [INFO] [stage_1_and_2.py:145:__init__] CPU Offload: False
[2024-09-23 10:15:28,871] [INFO] [stage_1_and_2.py:146:__init__] Round robin gradient partitioning: False
[2024-09-23 10:15:28,979] [INFO] [utils.py:791:see_memory_usage] Before initializing optimizer states
[2024-09-23 10:15:28,980] [INFO] [utils.py:792:see_memory_usage] MA 0.0 GB         Max_MA 0.0 GB         CA 0.0 GB         Max_CA 0 GB
[2024-09-23 10:15:28,980] [INFO] [utils.py:799:see_memory_usage] CPU Virtual Memory:  used = 6.68 GB, percent = 2.1%
[2024-09-23 10:15:29,079] [INFO] [utils.py:791:see_memory_usage] After initializing optimizer states
[2024-09-23 10:15:29,079] [INFO] [utils.py:792:see_memory_usage] MA 0.0 GB         Max_MA 0.0 GB         CA 0.0 GB         Max_CA 0 GB
[2024-09-23 10:15:29,079] [INFO] [utils.py:799:see_memory_usage] CPU Virtual Memory:  used = 6.68 GB, percent = 2.1%
[2024-09-23 10:15:29,079] [INFO] [stage_1_and_2.py:533:__init__] optimizer state initialized
[2024-09-23 10:15:29,178] [INFO] [utils.py:791:see_memory_usage] After initializing ZeRO optimizer
[2024-09-23 10:15:29,178] [INFO] [utils.py:792:see_memory_usage] MA 0.0 GB         Max_MA 0.0 GB         CA 0.0 GB         Max_CA 0 GB
[2024-09-23 10:15:29,178] [INFO] [utils.py:799:see_memory_usage] CPU Virtual Memory:  used = 6.68 GB, percent = 2.1%
[2024-09-23 10:15:29,181] [INFO] [fp8_stage_1_and_2.py:177:_pad_and_flat] [DeepSpeed ZeRO for MSAMP] group: 0, partitions: [58920], paddings: [0]
[2024-09-23 10:15:29,184] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Final Optimizer = adam
[2024-09-23 10:15:29,184] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed using configured LR scheduler = WarmupLR
[2024-09-23 10:15:29,184] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed LR Scheduler = <deepspeed.runtime.lr_schedules.WarmupLR object at 0x7fcd3fdeff10>
[2024-09-23 10:15:29,184] [INFO] [logging.py:96:log_dist] [Rank 0] step=0, skipped=0, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:15:29,184] [INFO] [config.py:984:print] DeepSpeedEngine configuration:
[2024-09-23 10:15:29,184] [INFO] [config.py:988:print]   activation_checkpointing_config  {
    "partition_activations": false,
    "contiguous_memory_optimization": false,
    "cpu_checkpointing": false,
    "number_checkpoints": null,
    "synchronize_checkpoint_boundary": false,
    "profile": false
}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   aio_config ................... {'block_size': 1048576, 'queue_depth': 8, 'thread_count': 1, 'single_submit': False, 'overlap_events': True}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   amp_enabled .................. False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   amp_params ................... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   autotuning_config ............ {
    "enabled": false,
    "start_step": null,
    "end_step": null,
    "metric_path": null,
    "arg_mappings": null,
    "metric": "throughput",
    "model_info": null,
    "results_dir": "autotuning_results",
    "exps_dir": "autotuning_exps",
    "overwrite": true,
    "fast": true,
    "start_profile_step": 3,
    "end_profile_step": 5,
    "tuner_type": "gridsearch",
    "tuner_early_stopping": 5,
    "tuner_num_trials": 50,
    "model_info_path": null,
    "mp_size": 1,
    "max_train_batch_size": null,
    "min_train_batch_size": 1,
    "max_train_micro_batch_size_per_gpu": 1.024000e+03,
    "min_train_micro_batch_size_per_gpu": 1,
    "num_tuning_micro_batch_sizes": 3
}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   bfloat16_enabled ............. False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   checkpoint_parallel_write_pipeline  False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   checkpoint_tag_validation_enabled  True
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   checkpoint_tag_validation_fail  False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   comms_config ................. <deepspeed.comm.config.DeepSpeedCommsConfig object at 0x7fcd3fdef7c0>
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   communication_data_type ...... None
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   compression_config ........... {'weight_quantization': {'shared_parameters': {'enabled': False, 'quantizer_kernel': False, 'schedule_offset': 0, 'quantize_groups': 1, 'quantize_verbose': False, 'quantization_type': 'symmetric', 'quantize_weight_in_forward': False, 'rounding': 'nearest', 'fp16_mixed_quantize': False, 'quantize_change_ratio': 0.001}, 'different_groups': {}}, 'activation_quantization': {'shared_parameters': {'enabled': False, 'quantization_type': 'symmetric', 'range_calibration': 'dynamic', 'schedule_offset': 1000}, 'different_groups': {}}, 'sparse_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'row_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'head_pruning': {'shared_parameters': {'enabled': False, 'method': 'topk', 'schedule_offset': 1000}, 'different_groups': {}}, 'channel_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'layer_reduction': {'enabled': False}}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   curriculum_enabled_legacy .... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   curriculum_params_legacy ..... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   data_efficiency_config ....... {'enabled': False, 'seed': 1234, 'data_sampling': {'enabled': False, 'num_epochs': 1000, 'num_workers': 0, 'curriculum_learning': {'enabled': False}}, 'data_routing': {'enabled': False, 'random_ltd': {'enabled': False, 'layer_token_lr_schedule': {'enabled': False}}}}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   data_efficiency_enabled ...... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   dataloader_drop_last ......... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   disable_allgather ............ False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   dump_state ................... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   dynamic_loss_scale_args ...... {'init_scale': 32768, 'scale_window': 500, 'delayed_shift': 2, 'consecutive_hysteresis': False, 'min_scale': 1}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_enabled ........... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_gas_boundary_resolution  1
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_layer_name ........ bert.encoder.layer
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_layer_num ......... 0
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_max_iter .......... 100
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_stability ......... 1e-06
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_tol ............... 0.01
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   eigenvalue_verbose ........... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   elasticity_enabled ........... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   flops_profiler_config ........ {
    "enabled": false,
    "recompute_fwd_factor": 0.0,
    "profile_step": 1,
    "module_depth": -1,
    "top_modules": 1,
    "detailed": true,
    "output_file": null
}
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   fp16_auto_cast ............... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   fp16_enabled ................. True
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   fp16_master_weights_and_gradients  False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   global_rank .................. 0
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   grad_accum_dtype ............. None
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   gradient_accumulation_steps .. 1
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   gradient_clipping ............ 1
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   gradient_predivide_factor .... 1.0
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   graph_harvesting ............. False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   hybrid_engine ................ enabled=False max_out_tokens=512 inference_tp_size=1 release_inference_cache=False pin_parameters=True tp_gather_partition_size=8
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   initial_dynamic_scale ........ 32768
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   load_universal_checkpoint .... False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   loss_scale ................... 0
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   memory_breakdown ............. False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   mics_hierarchial_params_gather  False
[2024-09-23 10:15:29,185] [INFO] [config.py:988:print]   mics_shard_size .............. -1
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   monitor_config ............... tensorboard=TensorBoardConfig(enabled=False, output_path='', job_name='DeepSpeedJobName') wandb=WandbConfig(enabled=False, group=None, team=None, project='deepspeed') csv_monitor=CSVConfig(enabled=False, output_path='', job_name='DeepSpeedJobName') enabled=False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   msamp_enabled ................ True
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   msamp_optlevel ............... O3
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   msamp_use_te ................. False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   nebula_config ................ {
    "enabled": false,
    "persistent_storage_path": null,
    "persistent_time_interval": 100,
    "num_of_version_in_retention": 2,
    "enable_nebula_load": true,
    "load_path": null
}
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   optimizer_legacy_fusion ...... False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   optimizer_name ............... adam
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   optimizer_params ............. {'lr': 0.001, 'betas': [0.8, 0.999], 'eps': 1e-08, 'weight_decay': 3e-07}
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   pipeline ..................... {'stages': 'auto', 'partition': 'best', 'seed_layers': False, 'activation_checkpoint_interval': 0, 'pipe_partitioned': True, 'grad_partitioned': True}
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   pld_enabled .................. False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   pld_params ................... False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   prescale_gradients ........... False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   scheduler_name ............... WarmupLR
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   scheduler_params ............. {'warmup_min_lr': 0, 'warmup_max_lr': 0.001, 'warmup_num_steps': 1000}
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   seq_parallel_communication_data_type  torch.float32
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   sparse_attention ............. None
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   sparse_gradients_enabled ..... False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   steps_per_print .............. 2000
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   train_batch_size ............. 16
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   train_micro_batch_size_per_gpu  16
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   use_data_before_expert_parallel_  False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   use_node_local_storage ....... False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   wall_clock_breakdown ......... False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   weight_quantization_config ... None
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   world_size ................... 1
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   zero_allow_untested_optimizer  False
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   zero_config .................. stage=2 contiguous_gradients=True reduce_scatter=True reduce_bucket_size=50000000 use_multi_rank_bucket_allreduce=True allgather_partitions=True allgather_bucket_size=50000000 overlap_comm=True load_from_fp32_weights=True elastic_checkpoint=False offload_param=None offload_optimizer=None sub_group_size=1,000,000,000 cpu_offload_param=None cpu_offload_use_pin_memory=None prefetch_bucket_size=50,000,000 param_persistence_threshold=100,000 model_persistence_threshold=sys.maxsize max_live_parameters=1,000,000,000 max_reuse_distance=1,000,000,000 gather_16bit_weights_on_model_save=False stage3_gather_fp16_weights_on_model_save=False ignore_unused_parameters=True legacy_stage1=False round_robin_gradients=False zero_hpz_partition_size=1 zero_quantized_weights=False zero_quantized_nontrainable_weights=False zero_quantized_gradients=False mics_shard_size=-1 mics_hierarchical_params_gather=False memory_efficient_linear=True pipeline_loading_checkpoint=False override_module_apply=True
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   zero_enabled ................. True
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   zero_force_ds_cpu_optimizer .. True
[2024-09-23 10:15:29,186] [INFO] [config.py:988:print]   zero_optimization_stage ...... 2
[2024-09-23 10:15:29,186] [INFO] [config.py:974:print_user_config]   json = {
    "train_batch_size": 16,
    "steps_per_print": 2.000000e+03,
    "optimizer": {
        "type": "Adam",
        "params": {
            "lr": 0.001,
            "betas": [0.8, 0.999],
            "eps": 1e-08,
            "weight_decay": 3e-07
        }
    },
    "scheduler": {
        "type": "WarmupLR",
        "params": {
            "warmup_min_lr": 0,
            "warmup_max_lr": 0.001,
            "warmup_num_steps": 1000
        }
    },
    "gradient_clipping": 1,
    "prescale_gradients": false,
    "fp16": {
        "enabled": true,
        "fp16_master_weights_and_grads": false,
        "loss_scale": 0,
        "loss_scale_window": 500,
        "hysteresis": 2,
        "min_loss_scale": 1,
        "initial_scale_power": 15
    },
    "msamp": {
        "enabled": true,
        "opt_level": "O3"
    },
    "wall_clock_breakdown": false,
    "zero_optimization": {
        "stage": 2,
        "allgather_partitions": true,
        "reduce_scatter": true,
        "allgather_bucket_size": 5.000000e+07,
        "reduce_bucket_size": 5.000000e+07,
        "overlap_comm": true,
        "contiguous_gradients": true,
        "cpu_offload": false
    }
}
model: Net(
  (conv1): Conv2d(3, 6, kernel_size=(5, 5), stride=(1, 1))
  (pool): MaxPool2d(kernel_size=2, stride=2, padding=0, dilation=1, ceil_mode=False)
  (conv2): Conv2d(6, 16, kernel_size=(5, 5), stride=(1, 1))
  (fc1): FP8Linear(in_features=400, out_features=120, bias=True)
  (fc2): FP8Linear(in_features=120, out_features=84, bias=True)
  (fc3): FP8Linear(in_features=84, out_features=10, bias=True)
)
fp16=True
[1,   200] loss: 2.085
[2024-09-23 10:15:33,253] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:15:33,253] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 32768
[1,   400] loss: 1.841
[2024-09-23 10:15:35,014] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:15:35,015] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384.0
[1,   600] loss: 1.725
[1,   800] loss: 1.680
[1,  1000] loss: 1.647
[2024-09-23 10:15:39,343] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:15:39,343] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:15:39,856] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:15:39,856] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  1200] loss: 1.574
[1,  1400] loss: 1.602
[1,  1600] loss: 1.583
[2024-09-23 10:15:44,058] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:15:44,059] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:15:44,306] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:15:44,307] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  1800] loss: 1.523
[2024-09-23 10:15:47,101] [INFO] [logging.py:96:log_dist] [Rank 0] step=2000, skipped=6, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:15:47,101] [INFO] [timer.py:260:stop] epoch=0/micro_step=2000/global_step=2000, RunningAvgSamplesPerSec=1913.7882416777227, CurrSamplesPerSec=1893.911610317774, MemAllocated=0.03GB, MaxMemAllocated=0.31GB
[1,  2000] loss: 1.507
[2024-09-23 10:15:48,674] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:15:48,674] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[1,  2200] loss: 1.516
[2024-09-23 10:15:49,634] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:15:49,634] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  2400] loss: 1.452
[1,  2600] loss: 1.432
[1,  2800] loss: 1.448
[2024-09-23 10:15:53,924] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:15:53,924] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:15:54,033] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:15:54,033] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  3000] loss: 1.422
[2,   200] loss: 1.393
[2024-09-23 10:15:58,828] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:15:58,828] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:15:58,988] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:15:58,988] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,   400] loss: 1.388
[2,   600] loss: 1.356
[2,   800] loss: 1.346
[2024-09-23 10:16:03,214] [INFO] [logging.py:96:log_dist] [Rank 0] step=4000, skipped=12, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:16:03,215] [INFO] [timer.py:260:stop] epoch=0/micro_step=4000/global_step=4000, RunningAvgSamplesPerSec=1956.7228882800182, CurrSamplesPerSec=1868.8071289334448, MemAllocated=0.03GB, MaxMemAllocated=0.31GB
[2024-09-23 10:16:03,743] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:16:03,743] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:16:04,068] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:16:04,068] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  1000] loss: 1.347
[2,  1200] loss: 1.320
[2,  1400] loss: 1.340
[2024-09-23 10:16:08,658] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:16:08,658] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2,  1600] loss: 1.323
[2024-09-23 10:16:09,922] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:16:09,923] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  1800] loss: 1.279
[2,  2000] loss: 1.286
[2,  2200] loss: 1.292
[2024-09-23 10:16:15,665] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:16:15,665] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2,  2400] loss: 1.245
[2,  2600] loss: 1.241
[2024-09-23 10:16:17,821] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:16:17,821] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,  2800] loss: 1.266
[2024-09-23 10:16:19,978] [INFO] [logging.py:96:log_dist] [Rank 0] step=6000, skipped=18, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:16:19,979] [INFO] [timer.py:260:stop] epoch=0/micro_step=6000/global_step=6000, RunningAvgSamplesPerSec=1943.2317380089737, CurrSamplesPerSec=1930.1350053208319, MemAllocated=0.03GB, MaxMemAllocated=0.31GB
[2,  3000] loss: 1.242
Finished Training
GroundTruth:    cat  ship  ship plane
Predicted:    cat   car   car plane
Accuracy of the network on the 10000 test images: 55 %
Accuracy of plane : 66 %
Accuracy of   car : 67 %
Accuracy of  bird : 44 %
Accuracy of   cat : 33 %
Accuracy of  deer : 46 %
Accuracy of   dog : 53 %
Accuracy of  frog : 46 %
Accuracy of horse : 70 %
Accuracy of  ship : 73 %
Accuracy of truck : 53 %
[2024-09-23 10:16:32,140] [INFO] [launch.py:347:main] Process 68755 exits successfully.
```



```
root@h100vm:/workspace/MS-AMP/examples# deepspeed cifar10_deepspeed_te.py --deepspeed --deepspeed_config ds_config_zero_te_msamp.json
```



```
[2024-09-23 10:18:51,855] [INFO] [launch.py:165:main] Setting CUDA_VISIBLE_DEVICES=0
[2024-09-23 10:18:55,480] [INFO] [real_accelerator.py:191:get_accelerator] Setting ds_accelerator to cuda (auto detect)
[2024-09-23 10:18:56,235] [INFO] [comm.py:637:init_distributed] cdb=None
[2024-09-23 10:18:56,235] [INFO] [comm.py:668:init_distributed] Initializing TorchBackend in DeepSpeed with backend nccl
Files already downloaded and verified
Files already downloaded and verified
truck   car  frog   cat
[2024-09-23 10:18:58,591] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed info: version=0.13.1, git-hash=unknown, git-branch=unknown
[2024-09-23 10:18:58,593] [WARNING] [config_utils.py:69:_process_deprecated_field] Config parameter cpu_offload is deprecated use offload_optimizer instead
[2024-09-23 10:18:58,675] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Flops Profiler Enabled: False
Using /root/.cache/torch_extensions/py310_cu122 as PyTorch extensions root...
Detected CUDA files, patching ldflags
Emitting ninja build file /root/.cache/torch_extensions/py310_cu122/fused_adam/build.ninja...
Building extension module fused_adam...
Allowing ninja to set a default number of workers... (overridable by setting the environment variable MAX_JOBS=N)
ninja: no work to do.
Loading extension module fused_adam...
Time to load fused_adam op: 0.05585932731628418 seconds
/usr/local/lib/python3.10/dist-packages/deepspeed/ops/adam/fused_adam.py:96: UserWarning: The torch.cuda.*DtypeTensor constructors are no longer recommended. It's best to use methods such as torch.tensor(data, dtype=*, device='cuda') to create tensors. (Triggered internally at /opt/pytorch/pytorch/torch/csrc/tensor/python_tensor.cpp:83.)
  self._dummy_overflow_buf = get_accelerator().IntTensor([0])
[2024-09-23 10:18:59,066] [INFO] [logging.py:96:log_dist] [Rank 0] Using DeepSpeed Optimizer param name adam as basic optimizer
/usr/local/lib/python3.10/dist-packages/msamp/common/tensor/meta.py:111: UserWarning: nvfuser integration in TorchScript is deprecated. (Triggered internally at /opt/pytorch/pytorch/torch/csrc/jit/codegen/cuda/interface.cpp:235.)
  sf = ScalingMeta.compute_scaling_factor(self.amax[0], self.scale, fp_max, 0)
[2024-09-23 10:18:59,566] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Basic Optimizer = DSAdam
[2024-09-23 10:18:59,566] [INFO] [utils.py:56:is_zero_supported_optimizer] Checking ZeRO support for optimizer=DSAdam type=<class 'msamp.optim.adam.DSAdam'>
[2024-09-23 10:18:59,566] [INFO] [logging.py:96:log_dist] [Rank 0] Creating fp16 ZeRO stage 2 optimizer
[2024-09-23 10:18:59,566] [INFO] [stage_1_and_2.py:143:__init__] Reduce bucket size 50000000
[2024-09-23 10:18:59,566] [INFO] [stage_1_and_2.py:144:__init__] Allgather bucket size 50000000
[2024-09-23 10:18:59,566] [INFO] [stage_1_and_2.py:145:__init__] CPU Offload: False
[2024-09-23 10:18:59,566] [INFO] [stage_1_and_2.py:146:__init__] Round robin gradient partitioning: False
[2024-09-23 10:18:59,686] [INFO] [utils.py:791:see_memory_usage] Before initializing optimizer states
[2024-09-23 10:18:59,687] [INFO] [utils.py:792:see_memory_usage] MA 0.0 GB         Max_MA 0.0 GB         CA 0.0 GB         Max_CA 0 GB
[2024-09-23 10:18:59,687] [INFO] [utils.py:799:see_memory_usage] CPU Virtual Memory:  used = 6.82 GB, percent = 2.2%
[2024-09-23 10:18:59,796] [INFO] [utils.py:791:see_memory_usage] After initializing optimizer states
[2024-09-23 10:18:59,796] [INFO] [utils.py:792:see_memory_usage] MA 0.0 GB         Max_MA 0.0 GB         CA 0.0 GB         Max_CA 0 GB
[2024-09-23 10:18:59,796] [INFO] [utils.py:799:see_memory_usage] CPU Virtual Memory:  used = 6.82 GB, percent = 2.2%
[2024-09-23 10:18:59,796] [INFO] [stage_1_and_2.py:533:__init__] optimizer state initialized
[2024-09-23 10:18:59,905] [INFO] [utils.py:791:see_memory_usage] After initializing ZeRO optimizer
[2024-09-23 10:18:59,905] [INFO] [utils.py:792:see_memory_usage] MA 0.0 GB         Max_MA 0.0 GB         CA 0.0 GB         Max_CA 0 GB
[2024-09-23 10:18:59,906] [INFO] [utils.py:799:see_memory_usage] CPU Virtual Memory:  used = 6.82 GB, percent = 2.2%
[2024-09-23 10:18:59,913] [INFO] [fp8_stage_1_and_2.py:177:_pad_and_flat] [DeepSpeed ZeRO for MSAMP] group: 0, partitions: [49152], paddings: [0]
[2024-09-23 10:18:59,913] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed Final Optimizer = adam
[2024-09-23 10:18:59,913] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed using configured LR scheduler = WarmupLR
[2024-09-23 10:18:59,913] [INFO] [logging.py:96:log_dist] [Rank 0] DeepSpeed LR Scheduler = <deepspeed.runtime.lr_schedules.WarmupLR object at 0x7fba35be54e0>
[2024-09-23 10:18:59,913] [INFO] [logging.py:96:log_dist] [Rank 0] step=0, skipped=0, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:18:59,914] [INFO] [config.py:984:print] DeepSpeedEngine configuration:
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   activation_checkpointing_config  {
    "partition_activations": false,
    "contiguous_memory_optimization": false,
    "cpu_checkpointing": false,
    "number_checkpoints": null,
    "synchronize_checkpoint_boundary": false,
    "profile": false
}
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   aio_config ................... {'block_size': 1048576, 'queue_depth': 8, 'thread_count': 1, 'single_submit': False, 'overlap_events': True}
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   amp_enabled .................. False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   amp_params ................... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   autotuning_config ............ {
    "enabled": false,
    "start_step": null,
    "end_step": null,
    "metric_path": null,
    "arg_mappings": null,
    "metric": "throughput",
    "model_info": null,
    "results_dir": "autotuning_results",
    "exps_dir": "autotuning_exps",
    "overwrite": true,
    "fast": true,
    "start_profile_step": 3,
    "end_profile_step": 5,
    "tuner_type": "gridsearch",
    "tuner_early_stopping": 5,
    "tuner_num_trials": 50,
    "model_info_path": null,
    "mp_size": 1,
    "max_train_batch_size": null,
    "min_train_batch_size": 1,
    "max_train_micro_batch_size_per_gpu": 1.024000e+03,
    "min_train_micro_batch_size_per_gpu": 1,
    "num_tuning_micro_batch_sizes": 3
}
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   bfloat16_enabled ............. False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   checkpoint_parallel_write_pipeline  False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   checkpoint_tag_validation_enabled  True
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   checkpoint_tag_validation_fail  False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   comms_config ................. <deepspeed.comm.config.DeepSpeedCommsConfig object at 0x7fba9363b880>
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   communication_data_type ...... None
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   compression_config ........... {'weight_quantization': {'shared_parameters': {'enabled': False, 'quantizer_kernel': False, 'schedule_offset': 0, 'quantize_groups': 1, 'quantize_verbose': False, 'quantization_type': 'symmetric', 'quantize_weight_in_forward': False, 'rounding': 'nearest', 'fp16_mixed_quantize': False, 'quantize_change_ratio': 0.001}, 'different_groups': {}}, 'activation_quantization': {'shared_parameters': {'enabled': False, 'quantization_type': 'symmetric', 'range_calibration': 'dynamic', 'schedule_offset': 1000}, 'different_groups': {}}, 'sparse_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'row_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'head_pruning': {'shared_parameters': {'enabled': False, 'method': 'topk', 'schedule_offset': 1000}, 'different_groups': {}}, 'channel_pruning': {'shared_parameters': {'enabled': False, 'method': 'l1', 'schedule_offset': 1000}, 'different_groups': {}}, 'layer_reduction': {'enabled': False}}
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   curriculum_enabled_legacy .... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   curriculum_params_legacy ..... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   data_efficiency_config ....... {'enabled': False, 'seed': 1234, 'data_sampling': {'enabled': False, 'num_epochs': 1000, 'num_workers': 0, 'curriculum_learning': {'enabled': False}}, 'data_routing': {'enabled': False, 'random_ltd': {'enabled': False, 'layer_token_lr_schedule': {'enabled': False}}}}
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   data_efficiency_enabled ...... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   dataloader_drop_last ......... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   disable_allgather ............ False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   dump_state ................... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   dynamic_loss_scale_args ...... {'init_scale': 32768, 'scale_window': 500, 'delayed_shift': 2, 'consecutive_hysteresis': False, 'min_scale': 1}
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_enabled ........... False
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_gas_boundary_resolution  1
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_layer_name ........ bert.encoder.layer
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_layer_num ......... 0
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_max_iter .......... 100
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_stability ......... 1e-06
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_tol ............... 0.01
[2024-09-23 10:18:59,914] [INFO] [config.py:988:print]   eigenvalue_verbose ........... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   elasticity_enabled ........... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   flops_profiler_config ........ {
    "enabled": false,
    "recompute_fwd_factor": 0.0,
    "profile_step": 1,
    "module_depth": -1,
    "top_modules": 1,
    "detailed": true,
    "output_file": null
}
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   fp16_auto_cast ............... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   fp16_enabled ................. True
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   fp16_master_weights_and_gradients  False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   global_rank .................. 0
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   grad_accum_dtype ............. None
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   gradient_accumulation_steps .. 1
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   gradient_clipping ............ 1
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   gradient_predivide_factor .... 1.0
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   graph_harvesting ............. False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   hybrid_engine ................ enabled=False max_out_tokens=512 inference_tp_size=1 release_inference_cache=False pin_parameters=True tp_gather_partition_size=8
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   initial_dynamic_scale ........ 32768
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   load_universal_checkpoint .... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   loss_scale ................... 0
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   memory_breakdown ............. False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   mics_hierarchial_params_gather  False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   mics_shard_size .............. -1
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   monitor_config ............... tensorboard=TensorBoardConfig(enabled=False, output_path='', job_name='DeepSpeedJobName') wandb=WandbConfig(enabled=False, group=None, team=None, project='deepspeed') csv_monitor=CSVConfig(enabled=False, output_path='', job_name='DeepSpeedJobName') enabled=False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   msamp_enabled ................ True
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   msamp_optlevel ............... O3
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   msamp_use_te ................. True
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   nebula_config ................ {
    "enabled": false,
    "persistent_storage_path": null,
    "persistent_time_interval": 100,
    "num_of_version_in_retention": 2,
    "enable_nebula_load": true,
    "load_path": null
}
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   optimizer_legacy_fusion ...... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   optimizer_name ............... adam
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   optimizer_params ............. {'lr': 0.001, 'betas': [0.8, 0.999], 'eps': 1e-08, 'weight_decay': 3e-07}
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   pipeline ..................... {'stages': 'auto', 'partition': 'best', 'seed_layers': False, 'activation_checkpoint_interval': 0, 'pipe_partitioned': True, 'grad_partitioned': True}
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   pld_enabled .................. False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   pld_params ................... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   prescale_gradients ........... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   scheduler_name ............... WarmupLR
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   scheduler_params ............. {'warmup_min_lr': 0, 'warmup_max_lr': 0.001, 'warmup_num_steps': 1000}
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   seq_parallel_communication_data_type  torch.float32
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   sparse_attention ............. None
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   sparse_gradients_enabled ..... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   steps_per_print .............. 2000
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   train_batch_size ............. 16
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   train_micro_batch_size_per_gpu  16
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   use_data_before_expert_parallel_  False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   use_node_local_storage ....... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   wall_clock_breakdown ......... False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   weight_quantization_config ... None
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   world_size ................... 1
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   zero_allow_untested_optimizer  False
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   zero_config .................. stage=2 contiguous_gradients=True reduce_scatter=True reduce_bucket_size=50000000 use_multi_rank_bucket_allreduce=True allgather_partitions=True allgather_bucket_size=50000000 overlap_comm=True load_from_fp32_weights=True elastic_checkpoint=False offload_param=None offload_optimizer=None sub_group_size=1,000,000,000 cpu_offload_param=None cpu_offload_use_pin_memory=None prefetch_bucket_size=50,000,000 param_persistence_threshold=100,000 model_persistence_threshold=sys.maxsize max_live_parameters=1,000,000,000 max_reuse_distance=1,000,000,000 gather_16bit_weights_on_model_save=False stage3_gather_fp16_weights_on_model_save=False ignore_unused_parameters=True legacy_stage1=False round_robin_gradients=False zero_hpz_partition_size=1 zero_quantized_weights=False zero_quantized_nontrainable_weights=False zero_quantized_gradients=False mics_shard_size=-1 mics_hierarchical_params_gather=False memory_efficient_linear=True pipeline_loading_checkpoint=False override_module_apply=True
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   zero_enabled ................. True
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   zero_force_ds_cpu_optimizer .. True
[2024-09-23 10:18:59,915] [INFO] [config.py:988:print]   zero_optimization_stage ...... 2
[2024-09-23 10:18:59,916] [INFO] [config.py:974:print_user_config]   json = {
    "train_batch_size": 16,
    "steps_per_print": 2.000000e+03,
    "optimizer": {
        "type": "Adam",
        "params": {
            "lr": 0.001,
            "betas": [0.8, 0.999],
            "eps": 1e-08,
            "weight_decay": 3e-07
        }
    },
    "scheduler": {
        "type": "WarmupLR",
        "params": {
            "warmup_min_lr": 0,
            "warmup_max_lr": 0.001,
            "warmup_num_steps": 1000
        }
    },
    "gradient_clipping": 1,
    "prescale_gradients": false,
    "fp16": {
        "enabled": true,
        "fp16_master_weights_and_grads": false,
        "loss_scale": 0,
        "loss_scale_window": 500,
        "hysteresis": 2,
        "min_loss_scale": 1,
        "initial_scale_power": 15
    },
    "msamp": {
        "enabled": true,
        "opt_level": "O3",
        "use_te": true
    },
    "wall_clock_breakdown": false,
    "zero_optimization": {
        "stage": 2,
        "allgather_partitions": true,
        "reduce_scatter": true,
        "allgather_bucket_size": 5.000000e+07,
        "reduce_bucket_size": 5.000000e+07,
        "overlap_comm": true,
        "contiguous_gradients": true,
        "cpu_offload": false
    }
}
model: FP8VisionTransformer(
  (patch_embed): PatchEmbed(
    (proj): Conv2d(3, 32, kernel_size=(2, 2), stride=(2, 2))
    (norm): Identity()
  )
  (pos_drop): Dropout(p=0.0, inplace=False)
  (blocks): ModuleList(
    (0-3): 4 x FP8Block(
      (m): TransformerLayer(
        (self_attention): MultiheadAttention(
          (layernorm_qkv): MSAMPLayerNormLinear()
          (core_attention): DotProductAttention(
            (flash_attention): FlashAttention()
            (fused_attention): FusedAttention()
            (unfused_attention): UnfusedDotProductAttention(
              (scale_mask_softmax): FusedScaleMaskSoftmax()
              (attention_dropout): Dropout(p=0.0, inplace=False)
            )
          )
          (proj): MSAMPLinear()
        )
        (layernorm_mlp): MSAMPLayerNormMLP()
      )
    )
  )
  (norm): LayerNorm((32,), eps=1e-05, elementwise_affine=True)
  (head): Linear(in_features=32, out_features=10, bias=True)
)
fp16=True
/usr/local/lib/python3.10/dist-packages/transformer_engine/pytorch/attention.py:853: UserWarning: TypedStorage is deprecated. It will be removed in the future and UntypedStorage will be the only storage class. This should only matter to you if you are using storages directly.  To access UntypedStorage directly, use tensor.untyped_storage() instead of tensor.storage()
  data_ptr = grad_outputs[0].storage().data_ptr()
[1,   200] loss: 2.163
[2024-09-23 10:19:15,489] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:19:15,489] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 32768
[1,   400] loss: 2.045
[2024-09-23 10:19:25,806] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:19:25,806] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384.0
[1,   600] loss: 1.945
[1,   800] loss: 1.898
[1,  1000] loss: 1.849
[2024-09-23 10:19:45,551] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:19:45,551] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:19:45,610] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:19:45,610] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2024-09-23 10:19:45,668] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 16384, reducing to 8192
[2024-09-23 10:19:45,668] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 16384.0, reducing to 8192.0
[1,  1200] loss: 1.799
[1,  1400] loss: 1.776
[1,  1600] loss: 1.705
[1,  1800] loss: 1.685
[2024-09-23 10:20:15,626] [INFO] [logging.py:96:log_dist] [Rank 0] step=2000, skipped=5, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:20:15,626] [INFO] [timer.py:260:stop] epoch=0/micro_step=2000/global_step=2000, RunningAvgSamplesPerSec=466.6882446505076, CurrSamplesPerSec=459.18427895010535, MemAllocated=0.09GB, MaxMemAllocated=0.63GB
[1,  2000] loss: 1.653
[2024-09-23 10:20:20,311] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:20:20,311] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:20:21,828] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:20:21,828] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  2200] loss: 1.636
[1,  2400] loss: 1.611
[1,  2600] loss: 1.556
[2024-09-23 10:20:42,192] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:20:42,192] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[1,  2800] loss: 1.578
[2024-09-23 10:20:48,605] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:20:48,605] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[1,  3000] loss: 1.535
[2,   200] loss: 1.517
[2024-09-23 10:21:07,665] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:21:07,665] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 32768.0
[2024-09-23 10:21:08,564] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768, reducing to 16384
[2024-09-23 10:21:08,565] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 32768.0, reducing to 16384.0
[2,   400] loss: 1.519
[2,   600] loss: 1.461
[2,   800] loss: 1.468
[2024-09-23 10:21:24,988] [INFO] [logging.py:96:log_dist] [Rank 0] step=4000, skipped=11, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:21:24,988] [INFO] [timer.py:260:stop] epoch=0/micro_step=4000/global_step=4000, RunningAvgSamplesPerSec=464.53450756587995, CurrSamplesPerSec=474.0900157538166, MemAllocated=0.09GB, MaxMemAllocated=0.63GB
[2,  1000] loss: 1.484
[2,  1200] loss: 1.456
[2024-09-23 10:21:42,493] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:21:42,493] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 65536.0
[2024-09-23 10:21:42,519] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, reducing to 32768
[2024-09-23 10:21:42,519] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 32768.0
[2,  1400] loss: 1.462
[2,  1600] loss: 1.401
[2,  1800] loss: 1.419
[2024-09-23 10:21:59,936] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:21:59,936] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 65536.0
[2024-09-23 10:21:59,962] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, reducing to 32768
[2024-09-23 10:21:59,962] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 32768.0
[2,  2000] loss: 1.407
[2,  2200] loss: 1.386
[2024-09-23 10:22:17,455] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:22:17,455] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 65536.0
[2024-09-23 10:22:17,481] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, reducing to 32768
[2024-09-23 10:22:17,481] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 32768.0
[2,  2400] loss: 1.363
[2,  2600] loss: 1.338
[2,  2800] loss: 1.380
[2024-09-23 10:22:34,209] [INFO] [logging.py:96:log_dist] [Rank 0] step=6000, skipped=17, lr=[0.001], mom=[[0.8, 0.999]]
[2024-09-23 10:22:34,209] [INFO] [timer.py:260:stop] epoch=0/micro_step=6000/global_step=6000, RunningAvgSamplesPerSec=463.9593057910259, CurrSamplesPerSec=458.50036210595357, MemAllocated=0.09GB, MaxMemAllocated=0.63GB
[2024-09-23 10:22:34,859] [INFO] [loss_scaler.py:190:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, but hysteresis is 2. Reducing hysteresis to 1
[2024-09-23 10:22:34,859] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 65536.0
[2024-09-23 10:22:34,884] [INFO] [loss_scaler.py:183:update_scale] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536, reducing to 32768
[2024-09-23 10:22:34,885] [INFO] [fp8_stage_1_and_2.py:676:step] [deepspeed] OVERFLOW! Rank 0 Skipping step. Attempted loss scale: 65536.0, reducing to 32768.0
[2,  3000] loss: 1.355
Finished Training
GroundTruth:    cat  ship  ship plane
Predicted:    dog  ship  ship  ship
Accuracy of the network on the 10000 test images: 50 %
Accuracy of plane : 50 %
Accuracy of   car : 66 %
Accuracy of  bird : 43 %
Accuracy of   cat : 31 %
Accuracy of  deer : 33 %
Accuracy of   dog : 47 %
Accuracy of  frog : 52 %
Accuracy of horse : 67 %
Accuracy of  ship : 77 %
Accuracy of truck : 40 %
[2024-09-23 10:23:27,151] [INFO] [launch.py:347:main] Process 69712 exits successfully.
```

