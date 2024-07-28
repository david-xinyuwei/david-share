本文为阅读《NVIDIA H100 Tensor Core GPU Architecture》的读书笔记，该文档在NV官网可以下载。



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6EgupiaY2JWo0pyMSd3pcaMN7f6ZicfwO27AIibhzuZaZ0jPpFBMgvnZXg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**英伟达H100张量核心GPU概述**

H100采用为NVIDIA定制的TSMC 4N工艺，拥有800亿个晶体管，包括众多架构方面的进步，是世界上最先进的芯片。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6xJUUBJJIq79qPL2MXgicaojmN2FU62j1iaRovmyhpyt7EKTvZN3o6zyg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Figure 2 NVIDIA H100 GPU on new SXM5 Module



H100是英伟达第九代数据中心GPU，旨在为大规模人工智能和高性能计算提供比上一代英伟达A100张量核心GPU高出一个数量级的性能。H100继承了A100的主要设计重点，提高了AI和HPC工作负载的强大扩展能力，并在架构效率方面进行了大幅改进。



对于今天的主流AI和HPC模型，H100与InfiniBand互连的性能是A100的30倍。



新的NVLink交换系统互连针对一些最大和最具挑战性的计算工作负载，这些工作负载需要跨多个GPU-的模型并行化。在某些情况下，这些工作负载的性能比使用InfiniBand的H100又提高了两倍。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6KLDKJEuqCibAZdc0UdN2FHWDIupsmhpib1VAicjv2Q1lMgiaKb3J2HL8aw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

图3. H100实现了下一代人工智能和HPC的突破



在GTC 2022年春季会议上，NVIDIA发布了新的Grace Hopper超级芯片产品。Hopper H100 Tensor Core GPU将为NVIDIA Grace Hopper Superchip CPU+GPU架构提供动力，该架构专为TB级加速计算而打造，在大型模型AI和HPC上提供10倍的性能。



英伟达Grace CPU利用Arm架构的灵活性，创建了一个从头开始为加速计算设计的CPU和服务器架构。H100与Grace搭配的是英伟达的超高速芯片间互连，可提供900GB/s的带宽，比PCIe Gen5快7倍。与当今最快的服务器相比，这一创新设计将提供高达30倍的总带宽，并为运行TB级数据的应用提供高达10倍的性能。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6unAogsaIPmLTd3rXYh7uo3eUL5T3StrK4Rf4iaw6jqichy2sGibmu6p0g/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Figure 4. Grace Hopper Superchip



**英伟达H100 GPU的主要特点总结:**

新的SM有许多性能和效率的改进。主要的新功能包括:

- 新的第四代张量核心与A100相比，芯片到芯片的速度提高了6倍，包括每SM的速度提高，额外的SM数量，以及H100的更高的时钟。在每个SM的基础上，与上一代16位浮点选项相比，Tensor Cores在同等数据类型上提供2倍于A100 SM的MMA（矩阵乘法-累加）计算速率，在使用新的FP8数据类型上提供4倍于A100的速率。稀疏性功能利用深度学习网络中的细粒度结构化稀疏性，使标准张量核心操作的性能翻倍。
- 新的DPX指令对动态编程算法的加速比A100 GPU高7倍。两个例子包括用于基因组学处理的Smith-Waterman算法，以及用于在动态仓库环境中为机器人车队寻找最佳路线的Floyd-Warshall算法。
- 与A100相比，IEEE FP64和FP32的芯片间处理速度提高了3倍，这是由于每个SM的时钟对时钟性能提高了2倍，加上H100的额外SM数量和更高的时钟。
- 新的线程块集群功能允许以大于单个SM上的单个线程块的粒度来编程控制位置性。这扩展了CUDA编程模型，为编程层次增加了一个层次，现在包括线程、线程块、线程块集群和网格。集群使多个线程块在多个SM上并发运行，以同步和协作方式获取和交换数据。
- 新的异步执行功能包括一个新的张量内存加速器（TMA）单元，可以在全局内存和共享内存之间非常有效地传输大型数据块。TMA还支持集群中线程块之间的异步拷贝。还有一个新的异步事务屏障，用于做原子数据移动和同步。
- 新的Transformer Engine使用软件和定制的Hopper Tensor Core技术的组合，专门用于加速Transformer模型训练和推理。Transformer Engine智能管理并动态选择FP8和16位计算，自动处理每层中FP8和16位之间的重铸和缩放，与上一代A100相比，在大型语言模型上提供高达9倍的AI训练速度和高达30倍的AI推理速度。
- HBM3内存子系统比上一代产品提供了近2倍的带宽增长。H100 SXM5 GPU是世界上第一个采用HBM3内存的GPU，提供领先的3TB/秒的内存带宽。
- 50 MB 二级缓存架构缓存了大量的模型和数据集供重复访问，减少了对HBM3的访问。
- 第二代多实例GPU(MIG)技术为每个GPU实例提供约3倍的计算能力和近2倍的内存带宽，与A100相比。现在首次提供具有MIG级可信执行环境（TEE）的机密计算能力。支持多达七个独立的GPU实例，每个实例都有专门的NVDEC和NVJPG单元。每个实例现在都包括自己的一套性能监控器，可与NVIDIA开发人员工具一起使用。
- 新的保密计算支持可以保护用户数据，抵御硬件和软件攻击，并在虚拟化和MIG环境中更好地隔离和保护虚拟机。H100实现了世界上第一个原生保密计算GPU，并以全PCIe线速将可信执行环境与CPU进行了扩展。
- 第四代NVIDIA NVLink在all-reduce上提供了3倍的带宽，比上一代NVLink增加了50%的一般带宽，多GPU IO的总带宽为900 GB/秒，操作带宽是PCIe第五代的7倍。
- 第三代NVSwitch技术包括驻扎在节点内部和外部的交换机，用于连接服务器、集群和数据中心环境中的多个GPU。节点内的每个NVSwitch提供64个第四代NVLink链接端口，以加速多GPU连接。交换机的总吞吐量从上一代的7.2 Tbits/秒增加到13.6 Tbits/秒。New third-generation NVSwitch technology also provides hardware acceleration for collective operations with multicast and NVIDIA SHARP in-network reductions
- 新的NVLink Switch系统互连技术和基于第三代NVSwitch技术的新的二级NVLink Switches引入了地址空间隔离和保护，使多达32个节点或256个GPU能够通过NVLink以2:1的锥形胖树拓扑结构进行连接。这些连接的节点能够提供57.6TB/秒的全对全带宽，并能提供令人难以置信的FP8稀疏人工智能计算的exaFLOP。
-  PCIe第五代提供128GB/秒的总带宽（每个方向64GB/秒），而第四代PCIe的总带宽为64GB/秒（每个方向32GB/秒）。PCIe第5代使H100能够与最高性能的x86 CPU和SmartNICs/DPU连接。





此外，还包括许多其他新功能，以改善强大的扩展能力，减少延迟和开销，并普遍简化GPU编程。



**![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6Kc6tnBTkG8CHX84hMYJ8lZqh8dm6RNtE9SuhWy6b2vQPCqnQGoDUBA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)**



**H100 SXM5 GPU**

H100 SXM5配置采用了NVIDIA定制的SXM5板，该板容纳了H100 GPU和HBM3内存堆栈，还提供了第四代NVLink和PCIe Gen 5连接，可提供最高的应用性能。这种配置是客户的理想选择，可将应用扩展到一台服务器中的多个GPU，以及跨服务器。它可以通过HGX H100服务器板提供4-GPU和8-GPU配置。4-GPU配置包括GPU之间的点对点NVLink连接，并在服务器中提供更高的CPU-GPU比率，而8-GPU配置包括NVSwitch，以提供SHARP网络内缩减和任何一对GPU之间900 GB/s的全NVLink带宽。H100 SXM5 GPU也被用于强大的新DGX H100服务器和DGX SuperPOD系统中。



**H100 PCIe第5代GPU**

H100 PCIe Gen 5配置提供了H100 SXM5 GPU的所有功能，热设计功率（TDP）仅为350瓦。这种配置可以选择使用NVLink bridge，以600 GB/s的带宽连接多达两个GPU，几乎是PCIe Gen5的五倍。H100 PCIe非常适用于进入标准机架的主流加速服务器，提供较低的每台服务器功率，为同时扩展到1或2个GPU的应用提供了巨大的性能，包括AI推理和一些HPC应用。在10个顶级数据分析、人工智能和HPC应用中，单个H100 PCIe GPU有效地提供了H100 SXM5 GPU **65%**的交付性能，而消耗的功率只有50%。



**DGX H100和DGX SuperPOD**

NVIDIA DGX H100是一个通用的高性能AI系统，用于训练、推理和分析。DGX H100配备了Bluefield-3、NDR InfiniBand和第二代MIG技术。单个DGX H100系统可提供无与伦比的16 petaFLOPS的FP16稀疏AI计算性能。通过将多个DGX H100系统连接成被称为DGX PODs甚至DGX SuperPODs的集群，可以轻松提升这一性能。一个DGX SuperPOD从32个DGX H100系统开始，被称为 "可扩展单元"，它集成了256个H100 GPU，通过基于第三代NVSwitch技术的新二级NVLink交换机连接，提供前所未有的1 exaFLOP的FP8稀疏AI计算性能。DGX H100 SuperPOD将同时支持InfiniBand和NVLINK交换机网络选项。



**HGX H100**

随着工作负荷的复杂化，需要多个GPU一起工作，并在它们之间进行极快的通信。NVIDIA HGX H100将多个H100 GPU与由NVLink和NVSwitch驱动的高速互连相结合，从而能够创建世界上最强大的扩展型服务器。

HGX H100可作为服务器构件，以集成底板的形式提供四颗或八颗H100 GPU配置。四个GPU的HGX H100在GPU之间提供完全互连的点对点NVLink连接，而八个GPU的配置则通过NVSwitch提供完整的GPU对GPU带宽。利用H100多精度张量核心的力量，8路HGX H100使用稀疏FP8运算提供了超过32 petaFLOPS的深度学习计算性能。HGX H100实现了标准化的高性能服务器，为各种应用工作负载提供了可预测的性能，同时也为英伟达的合作伙伴服务器制造商的生态系统实现了更快的上市时间。



**H100 CNX 融合型加速器**

NVIDIA H100 CNX将NVIDIA H100 GPU的威力与NVIDIA ConnectX-7 SmartNIC的先进网络功能相结合，后者可提供高达400Gb/s的带宽，并包括NVIDIA ASAP2（加速交换和分组处理）等创新功能，以及针对TLS/IPsec/MACsec加密/解密的在线硬件加速。这种独特的架构为GPU驱动的I/O密集型工作负载提供了前所未有的性能，例如企业数据中心的分布式AI培训，或者边缘的5G信号处理。



**英伟达H100 GPU架构深入介绍**

基于全新Hopper GPU架构的NVIDIA H100 GPU具有多项创新。

- 新的第四代张量核心在更广泛的人工智能和HPC任务上执行比以往更快的矩阵计算。
- 与上一代A100相比，新的Transformer Engine使H100在大型语言模型上的人工智能训练速度提高了9倍，人工智能推理速度提高了30倍。
- 新的NVLink网络互连使多个计算节点上多达256个GPU之间能够进行GPU到GPU的通信。
- 安全MIG将GPU划分为孤立的、适当大小的实例，以最大限度地提高小型工作负载的QoS（服务质量）。
- 英伟达的H100是第一个真正的异步GPU。H100将A100的全局到共享的异步传输扩展到所有地址空间，并增加了对张量内存访问模式的支持。它使应用程序能够建立端到端的异步流水线，将数据移入和移出芯片，将数据移动与计算完全重叠和隐藏。
- 现在只需要少量的CUDA线程使用新的张量内存加速器来管理H100的全部内存带宽，而其他大多数CUDA线程可以专注于通用计算，例如为新一代张量核心预处理和后处理数据。
- H100将CUDA线程组的层次结构增加了一个新的层次，称为线程块集群。集群是一组线程块，它们被保证为并发调度，并在多个SM上实现线程的有效合作和数据共享。一个集群还可以合作地驱动异步单元，如张量内存加速器和张量核心，更有效地驱动。
- 协调越来越多的片上加速器和不同的通用线程组需要同步。例如，消耗输出的线程和加速器必须等待产生输出的线程和加速器。
- 英伟达的异步事务屏障使集群内的通用CUDA线程和片上加速器能够有效地进行同步，即使它们位于不同的SM上。所有这些新功能使每个用户和应用程序能够在任何时候都充分利用H100 GPU的所有单元，使H100成为迄今为止最强大、最易编程和最省电的GPU。
- 为H100 GPU提供动力的完整GH100 GPU采用台积电为NVIDIA定制的4N工艺制造，拥有800亿个晶体管，芯片尺寸为814平方毫米，并采用更高的频率设计。



NVIDIA GH100 GPU由多个GPC、TPC、SM、二级缓存和HBM3内存控制器组成：

GH100 GPU的完整实现包括以下单元。

● 8个GPC，72个TPC（9个TPC/GPC），2个SMs/TPC，每个完整的GPU有144个SMs

● 每个SM有128个FP32 CUDA核心，每个全GPU有18432个FP32 CUDA核心

- 每个SM有4个第四代Tensor Cores，每个全GPU有576个。

- 6个HBM3或HBM2e堆栈，12个512位内存控制器

- 60 MB L2 高速缓存

- 第四代NVLink和PCIe Gen 5

  

采用SXM5板型的NVIDIA H100 GPU包括以下单元：

- 8个GPC，66个TPC，2个SMs/TPC，每个GPU有132个SMs

- 每个SM有128个FP32 CUDA核心，每个GPU有16896个FP32 CUDA核心

- 每个SM有4个第四代Tensor Cores，每个GPU有528个。

- 80 GB HBM3，5个HBM3堆栈，10个512位内存控制器

- 50 MB L2 缓存

- 第四代NVLink和PCIe Gen 5

  

采用PCIe Gen 5板型的NVIDIA H100 GPU包括以下单元：

- 7或8个GPC，57个TPC，2个SMs/TPC，每个GPU有114个SMs
- ● 128个FP32 CUDA核心/SM，每个GPU有14592个FP32 CUDA核心
- 每个SM有4个第四代Tensor Cores，每个GPU有456个。
- 80 GB HBM2e，5个HBM2e堆栈，10个512位内存控制器
- 50 MB L2 高速缓存
- 第四代NVLink和PCIe Gen 5



使用台积电4N制造工艺使H100能够提高GPU核心频率，改善每瓦性能，并比基于台积电7nm N7工艺的上一代GA100 GPU集成更多的GPC、TPC和SM。



图6显示了具有144个SM的完整GH100 GPU。H100 SXM5 GPU有132个SM，而PCIe版本有114个SM。请注意，H100 GPU主要是为执行人工智能、高性能计算和数据分析的数据中心和边缘计算工作负载而构建的，而不是图形处理。SXM5和PCIe H100 GPU中只有两个TPC具有图形处理能力（也就是说，它们可以运行顶点、几何和像素着色器）。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6Th3B716ROc9GftUXqao2FDtvu9HwflrEE8QMjibNgBk06AfCvrwZrVw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Figure 6. GH100 Full GPU with 144 SMs

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6g7msIgia25wqagldxD47Hc6ibmB35LejdrdjUmCiayePkvmlOibeiad5kLA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



H100 SM架构

- 在英伟达A100张量核心GPU SM架构的基础上，由于引入了FP8，H100 SM将A100的每SM浮点峰值计算能力提高了四倍，并将A100在以前所有张量核心和FP32/FP64数据类型上的原始SM计算能力提高了一倍，而且是时钟对时钟。
- 与上一代A100相比，新的Transformer Engine与Hopper的FP8 Tensor Core相结合，在大型语言模型上提供了高达9倍的AI训练和30倍的AI推理速度。Hopper的新DPX指令使基因组学和蛋白质测序的Smith-Waterman算法处理速度提高7倍。
- Hopper新的第四代Tensor Core、Tensor Memory Accelerator以及许多其他新的SM和一般H100架构的改进，在许多其他情况下共同提供了高达3倍的HPC和AI性能。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6IGIia3X5YsCC9fKiaPg2HwzsHibq9JH0xm2JeFKZktHdARZoMS8dpUfYQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6icWVtroHMpuaSJV46yHrb919Jh5LsiagfkviaohSTnLEk6mS4uNf2gkOw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

H100 SM的主要特点总结

- 第四代Tensor Cores。
- 与A100相比，芯片到芯片的速度提高了6倍，包括每SM的速度提高，额外的SM数量，以及H100的更高的时钟。
- ○ 在每个SM的基础上，Tensor Cores在同等数据类型上提供2倍于A100 SM的MMA（Matrix Multiply-Accumulate）计算率，与前一代16位浮点选项相比，使用新的FP8数据类型的计算率是A100的4倍。
- ○ 稀疏性功能利用深度学习网络中的细粒度结构稀疏性，使标准Tensor Core操作的性能提高一倍。
- 新的DPX指令使动态编程算法比A100 GPU加速7倍。两个例子包括用于基因组学处理的Smith-Waterman算法，以及用于在动态仓库环境中为机器人车队寻找最佳路线的Floyd-Warshall算法。
- 与A100相比，IEEE FP64和FP32的处理率在芯片间快3倍，这是因为每个SM的时钟对时钟性能快2倍，加上H100的额外SM数量和更高的时钟。
- 256 KB的组合共享内存和L1数据缓存，比A100大1.33倍。
- 新的异步执行功能包括一个新的张量内存加速器（TMA）单元，可以在全局内存和共享内存之间有效传输大块数据。TMA还支持集群中线程块之间的异步拷贝。还有一个新的异步事务屏障，用于做原子数据移动和同步。
- 新的线程块集群功能暴露了跨多个SM的定位控制。
- 分布式共享内存允许在多个SM共享内存块上进行直接的SM-to-SM通信，用于加载、存储和原子化。



**H100张量核心架构**

Tensor Cores是专门用于矩阵乘法和累加（MMA）数学运算的高性能计算核心，为AI和HPC应用提供了突破性的性能。与标准的浮点运算(FP)、整数运算(INT)和FMA(Fused Multiply-Accumulate)运算相比，Tensor Core在一个NVIDIA GPU中的SMs之间并行运行，可大幅提高吞吐量和效率。Tensor Cores在NVIDIA Tesla V100 GPU中首次推出，并在每一代新的NVIDIA GPU架构中得到进一步增强。

与A100相比，H100中新的第四代Tensor Core架构的每个SM的原始密集和稀疏矩阵数学吞吐量是A100的两倍，如果考虑到H100比A100更高的GPU Boost时钟，其吞吐量甚至更大。支持FP8、FP16、BF16、TF32、FP64和INT8 MMA数据类型。新的张量核心还具有更有效的数据管理，可节省高达30%的操作数输送功率。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6UeWhT78ExCfdaT0nEicWR2aEoC5ec1P3umpnft9l6rIIVUzdiah4lW5Q/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

图8. 与A100 FP16 Tensor Core相比，H100 FP16 Tensor Core具有3倍的吞吐量



**Hopper FP8数据格式**

H100 GPU增加了FP8 Tensor Cores，以加速AI训练和推理。如图9所示，FP8张量核心支持FP32和FP16累积器，以及两种新的FP8输入类型。

● E4M3，有4个指数位、3个尾数位和1个符号位

- **E5M2，有5个指数位，2个尾数位和1个符号位。**
- **E4M3支持需要较小动态范围和较高精度的计算，而E5M2提供较宽的动态范围和较低的精度。与FP16或BF16相比，FP8的数据存储要求减半，吞吐量增加一倍。**

**新的转化器引擎（在下面一节中描述）同时利用FP8和FP16的精度来减少内存的使用并提高性能，同时仍然保持大型语言和其他模型的精度。**

**![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6WQrQ1iaakFnyPlVj67xNzNRV9dHlibeib0hHWr1CgiaibdtvtvKfibd5HpvQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)**

**![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6w9gheSRINOeuXqYickX4csQnxhe1TOHuUFtibbUulibjNbRgyeDr501Iw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)**

H100的数学速度超过A100的多种数据类型，具体见下表2：

**![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6XKrxdfwvLZgIuoLgtpXccNNlfDicx96erVEIRTLVNPO8ugqv8ibK2DDQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)**



**用于加速动态编程的新DPX指令**

许多 "蛮力 "优化算法具有这样的特性：在解决大问题时，子问题的解决方案被多次重复使用。动态编程是一种通过将复杂的递归问题分解为更简单的子问题来解决的算法技术。通过存储子问题的结果，以后需要时不需要重新计算，动态编程算法将指数级问题集的计算复杂性降低到线性规模。



动态编程常用于广泛的优化、数据处理和基因组学算法中。在快速增长的基因组测序领域，史密斯-沃特曼动态编程算法是正在使用的最重要方法之一。在机器人领域，Floyd-Warshall是一种关键的算法，用于为机器人车队在动态仓库环境中实时寻找最佳路线。



H100引入了DPX指令，与安培GPU相比，动态编程算法的性能最多加速7倍。这些新指令为许多DPX算法的内循环提供了对高级融合操作数的支持。这将使疾病诊断、物流路由优化、甚至图形分析的解决时间大大加快。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6wQHkc8DiajZp00TW6MgYmCssTOiaq3WkS9owtdVJz7iatng3Rj9tUQd0A/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在Volta V100中首次推出的NVIDIA组合式L1数据缓存和共享内存子系统架构大大提升了性能，同时也简化了编程，减少了达到或接近峰值应用性能所需的调整。



将数据缓存和共享内存功能结合到一个内存块中，为两种类型的内存访问提供了最佳的整体性能。

H100的L1数据缓存和共享内存的组合容量是256KB/SM，而A100是192KB/SM。

在H100中，SM共享内存的大小本身是可配置的，最高可达228KB。





**H100计算性能总结**

总的来说，如果考虑到H100中所有新的计算技术的进步，H100的计算性能比A100提高了大约6倍。图13以级联的方式总结了H100的改进，从132个SMs开始，比A100的108个SMs增加了22%。由于其新的第四代张量核心，H100的每个SMs都快了2倍。而在每个张量核心中，新的FP8格式和相关的变压器引擎又提供了2倍的改进。最后，H100中增加的时钟频率又提供了约1.3倍的性能改进。总的来说，这些改进使H100的峰值计算吞吐量约为A100的6倍，是世界上最需要计算的工作负载的一个重大飞跃。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6Ficg1GticBaGUyRiaQdfzdJfYCjYH7GQGbssFGTbibEoeHFrumibuELvvtA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**H100 GPU层次结构和异步性的改进**

在并行程序中实现高性能的两个基本关键是数据定位和异步执行。通过将程序数据尽可能地靠近执行单元，程序员可以利用对本地数据的低延迟和高带宽访问所带来的性能。异步执行包括寻找独立的任务，与内存传输和其他处理重叠。我们的目标是让GPU中的所有单元都得到充分的利用。我们将探讨在Hopper的GPU编程层次中增加的一个重要的新层级，该层级在一个单一的SM上暴露出比单一线程块更大的局部性。我们还将介绍新的异步执行功能，以提高性能并减少同步开销。



**Thread block集群**

CUDA编程模型长期以来一直依赖于GPU计算架构，该架构使用包含多个线程块的网格来利用程序中的局部性。一个线程块包含多个线程，这些线程在一个单一的SM上并发运行，线程可以与快速障碍同步，并使用SM的共享内存交换数据。然而，随着GPU的增长超过100个SM，计算程序变得更加复杂，线程块作为编程模型中表达的唯一定位单位，不足以最大限度地提高执行效率。



H100引入了一个新的线程块集群架构，在比单个SM上的单个线程块更大的颗粒度上暴露了对位置性的控制。线程块集群扩展了CUDA编程模型，为GPU的物理编程层次增加了一个层次，现在包括线程、线程块、线程块集群和网格。集群是一组线程块，它们被保证同时调度到一组SM上，其目的是使线程在多个SM上高效合作。

H100中的集群在一个GPC中的SM上并发运行。GPC是硬件层次结构中的一组SM，它们在物理上总是紧密相连。集群有硬件加速的障碍和新的内存访问协作能力，在以下章节中讨论。GPC中SM的专用SM-to-SM网络为集群中的线程提供快速的数据共享。在CUDA中，网格中的线程块可以选择在内核启动时被分组为集群，如图14所示，集群功能可以从CUDA cooperative_groups API中得到利用。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6j3SmKSXgvkHZr68qoO2nmX8GjFupFu20ZTQhzc4mgSFWhrl5Vqhpkg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在传统的CUDA编程模型中，网格是由线程块组成的，如A100，如上图左半部分所示。Hopper架构增加了一个可选的Cluster层次结构，如图右半部分所示。

Figure 14. Thread Block Clusters and Grids with Clusters





**分布式共享内存**

通过集群，所有线程都可以通过加载、存储和原子操作直接访问其他SM的共享内存。这个功能被称为分布式共享内存（DSMEM），因为共享内存的虚拟地址空间在逻辑上是分布在集群中的所有区块上。DSMEM使SM之间的数据交换更加有效，数据不再需要写入和读出全局内存来传递数据。集群的专用SM-to-SM网络确保了对远程DSMEM的快速、低延迟的访问。与使用全局内存相比，DSMEM使线程块之间的数据交换加速了约7倍。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp62aTqibp1KLtywPv2NYye8YYTP2JZ6sosFblCDianezhkuqNNXbbRjcIA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在CUDA层面，集群中所有线程块的所有DSMEM段都被映射到每个线程的通用地址空间中，这样，所有的DSMEM都可以用简单的指针直接引用。CUDA用户可以利用cooperative_groups API来构建指向集群中任何线程块的通用指针。DSMEM的传输也可以表示为异步复制操作，与基于共享内存的障碍物同步以跟踪完成。

下面的图16显示了在不同算法上使用集群的性能优势。集群通过允许程序员直接控制更大的GPU部分而不仅仅是单一的SM，来提高性能。集群允许与更多的线程合作执行，访问更大的共享内存池，而不是只使用单一的线程块。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp62YbUhDWDenuq2rfy1Z1nopnricIPcI4bnCRPJ9Ctypib9slC3p5sM9Vw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

H100的初步性能估计是基于目前的预期，并可能在运输产品中发生变化





**异步执行**

每一代新的NVIDIA GPU都包括大量的架构改进，以提高性能、可编程性、电源效率、GPU利用率以及其他许多因素。最近几代英伟达GPU都包含了异步执行功能，允许数据移动、计算和同步有更多重叠。Hopper架构提供了新的功能，改善了异步执行，允许内存拷贝与计算和其他独立工作进一步重叠，同时也最大限度地减少了同步点。



下面将介绍一个新的异步内存拷贝单元，称为张量内存加速器（TMA）和一个新的异步事务屏障。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6vnB8dXWeII2viahxibSSoG5lf1t1tYlakJeLibBtuTQeicpLFrn1ttic0aQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

数据移动、计算和同步的程序性重叠。异步并发和尽量减少同步点是性能的关键。

图17. 异步执行的并发性和Hopper的增强功能



**张量存储器加速器（TMA）**

为了帮助提供强大的新H100张量核心，通过新的张量内存加速器（TMA）提高了数据获取效率，该加速器可以将大型数据块和多维张量从全局内存传输到共享内存，反之亦然。

TMA操作是使用复制描述符启动的，该描述符使用张量尺寸和块坐标而不是每元素寻址来指定数据传输（见下图18）。大的数据块（达到共享内存的容量）可以被指定并从全局内存加载到共享内存，或者从共享内存存储到全局内存。TMA大大减少了寻址开销，并通过支持不同的张量布局（1D-5D张量）、不同的内存访问模式、还原和其他功能来提高效率。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6MkMsiahjl8ia4mw3HTicPVwV162sNGKgmX7dtjBcIzDZ3lRjVg1mLibc4w/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

TMA操作是异步的，利用了A100中引入的基于共享内存的异步障碍。此外，TMA编程模型是单线程的，在经线中选择一个单线程发出异步TMA操作（cuda::memcpy_async）来复制张量，随后多个线程可以在cuda::屏障上等待数据传输的完成。为了进一步提高性能，H100 SM增加了硬件来加速这些异步屏障等待操作。

TMA的一个关键优势是它释放了线程来执行其他独立的工作。在A100上，在图19的左边部分，异步内存拷贝是使用特殊的LoadGlobalStoreShared指令执行的，所以线程负责生成所有地址并在整个拷贝区域内循环。

在Hopper上，TMA负责处理一切。在启动TMA之前，单个线程会创建一个拷贝描述符，从那时起，地址生成和数据移动都由硬件处理。TMA提供了一个更简单的编程模型，因为它接管了在复制张量段时计算跨度、偏移量和边界计算的任务。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6JS2MlYFUibiahwJv8uXVAEafsmKicQGL2ibCpJxHKWLk7HAbiaXmo30J6dw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**Asynchronous Transaction Barrier**

异步障碍物最初是在Ampere GPU架构中引入的。见图20的左边部分。考虑一个例子，一组线程正在生产数据，它们都将在一个障碍后消耗。异步屏障将同步过程分成两步。首先，线程在生产完自己的那部分共享数据后发出信号 "Arrive"。这个 "到达 "是无阻塞的，所以线程可以自由地执行其他独立的工作。最终，这些线程需要所有其他线程产生的数据。在这一点上，他们做了一个 "等待 "的动作，阻止他们，直到每个线程都发出 "到达 "信号。

异步障碍物的优势在于它允许提前到达的线程在等待时执行独立的工作。这种重叠是额外性能的来源。如果所有线程都有足够的独立工作，障碍物就会有效地变得 "自由"，因为等待指令可以立即退出，因为所有线程都已经到达了。

对Hopper来说，新的功能是让 "等待 "线程在所有其他线程到达之前睡觉。在以前的芯片上，"等待 "线程会在共享内存中的屏障对象上旋转。

虽然异步屏障仍然是Hopper编程模型的一部分，但Hopper增加了一种新形式的屏障，称为异步事务屏障。异步事务障碍与异步障碍非常相似。请看图20的右边部分。它也是一个分离式屏障，但它不是只计算线程的到达，而是也计算事务。Hopper包括一个用于写入共享内存的新命令，它同时传递要写入的数据和事务计数。事务计数本质上是一个字节计数。异步事务屏障将在Wait命令处阻断线程，直到所有生产者线程都执行了Arrive，并且所有事务计数之和达到预期值。



**NVIDIA H100 Tensor Core GPU架构**

异步事务载体是一个强大的新基元，用于异步内存拷贝或数据交换。如前所述，集群可以进行线程块与线程块之间的通信，进行隐含同步的数据交换，而这种集群能力是建立在异步事务障碍之上的。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp60ibFrX6Dcj6u1yxnBt43M18bCtibYpWQiazXkamE6exn9GtVygFgz3b6w/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**H100 HBM和二级缓存内存架构**

GPU的内存架构和层次结构的设计对应用性能至关重要，并影响到GPU的大小、成本、功耗和可编程性。在GPU中存在许多不同的内存子系统，从大量的片外DRAM（帧缓冲器）设备内存，到不同级别和类型的片上内存，再到SM中用于计算的寄存器文件。

高性能的HBM3和HBM2e是分别用于H100 SXM5和PCIe H100 GPU的DRAM技术。HBM内存由位于与GPU相同的物理封装上的内存堆组成，与传统的GDDR5/6内存设计相比，可以节省大量的功率和面积，允许在系统中安装更多的GPU。

CUDA程序访问的全局和局部内存区域位于HBM内存空间中，在CUDA术语中被称为 "设备内存"。恒定内存空间位于设备内存中，并被缓存在恒定缓存中。纹理和表面内存空间驻留在设备内存中，并被缓存在纹理高速缓存中。二级（L2）缓存从HBM（设备）内存中读取和写入，并为来自GPU内各种子系统的内存请求提供服务。所有SM和在GPU上运行的所有应用程序都可以访问HBM和L2内存空间。

**H100 HBM3 和 HBM2e DRAM 子系统**

随着HPC、AI和数据分析数据集的规模不断扩大，计算问题也越来越复杂，更大的GPU内存容量和带宽是必要的。NVIDIA P100是世界上第一个支持高带宽HBM2内存技术的GPU架构，而NVIDIA V100提供了更快、更高效、更高容量的HBM2实现。NVIDIA A100 GPU进一步提高了HBM2的性能和容量。

H100 SXM5 GPU大大提升了标准，它支持80GB（5个堆栈）的快速HBM3内存，提供超过3TB/秒的内存带宽，与两年前刚推出的A100的内存带宽相比，有效地提高了2倍。PCIe H100提供80GB的快速HBM2e，内存带宽超过2TB/秒。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6XuPI4039n16wQ8iauwLQI3OO5u1LedicW0GNIpkpheh8rRH355xGMpnw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**H100二级缓存**

H100的50 MB二级缓存比A100的40 MB二级缓存大1.25倍。它可以对模型和数据集的更大部分进行缓存，以便重复访问，减少对HBM3或HBM2e DRAM的访问并提高性能。使用分区的横杆结构，L2高速缓存对直接连接到分区的GPC的SM的内存访问进行定位和缓存数据。二级缓存驻留控制优化了容量利用率，允许程序员有选择地管理应该留在缓存中或被驱逐的数据。



HBM3或HBM2e DRAM和二级缓存子系统都支持数据压缩和解压技术，以优化内存和缓存的使用和性能。





内存子系统RAS特性

以下两个主要的RAS(可靠性、可用性和可服务性)特性是为H100的HBM3和HBM2e内存子系统实现的。

ECC 内存的弹性

H100 HBM3/2e内存子系统支持单错纠错双错检测（SECDED）纠错代码（ECC）来保护数据。ECC 为对数据损坏敏感的计算应用提供更高的可靠性。它在大规模集群计算环境中尤为重要，在这种环境中，GPU处理非常大的数据集和/或长时间运行应用程序。H100为其HBM3/2e内存支持 "Sideband ECC"，其中一个小的内存区域，与主HBM内存分开，用于ECC位（这与 "Inline ECC "相反，其中主内存的一部分被划分出来用于存储ECC位）。H100的其他关键内存结构也受到SECDED ECC的保护，包括L2缓存和L1缓存以及所有SM内部的寄存器文件。



**内存行重映射**

H100 HBM3/HBM2e子系统可以使那些产生ECC错误的内存单元的内存行失效，并在启动时使用行重映射逻辑将这些行替换为保留的已知良好的行。每个HBM3/HBM2e内存组中的一些内存行被预留为备用行，如果需要，可以被激活以替换被确定为坏的行。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6Ucb96kiaonYjqeppU1oicG9O3F07PYBoRqribibNMRmpOZqOqYYuXZxKcQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6cAqLn5GbpGIt7UZD0tLoW84ygib9Y7OPHD2dceG8zibFvmR1lyW9FZZg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

注：由于H100和A100 Tensor Core GPU旨在安装在高性能服务器和数据中心机架上，为AI和HPC计算工作负载提供动力，因此它们不包括显示连接器、用于光线追踪加速的NVIDIA RT Cores或NVENC编码器。





**计算能力**

H100 GPU支持新的Compute Capability 9.0。表4比较了NVIDIA GPU架构的不同计算能力的参数

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6P1G8CQoAU2pXymc7dVBI4xjDkrGZEibrtzWrYrCVarf5PI81J5MCMiag/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**第二代安全MIG**

英伟达多实例GPU（MIG）技术是在基于英伟达安培架构的A100 Tensor Core GPU中推出的。MIG为共享同一GPU的多个用户提供独立的、完全隔离的、安全的GPU实例，已经成为扩展云服务提供商（CSP）数据中心的一项极其重要的功能。

**MIG技术回顾**

MIG技术允许将每个A100或H100 GPU（包括H100 SXM5和H100 PCIe版本）划分为多达7个GPU实例，以达到最佳的GPU利用率，并在不同客户（如虚拟机、容器和进程）之间提供一个定义的QoS和隔离。MIG对拥有多租户使用案例的云服务提供商特别有利，它确保一个客户不能影响其他客户的工作或调度，此外还提供增强的安全性，并允许为客户提供GPU利用率保证。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6icqtpvOJ5w1UCDGx0ddia42xjyZQvpI5qkbMOgoGEicKIFTVMQ8qy88kg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

MIG管理、调整、服务和负载平衡vGPU（虚拟GPU）虚拟机（VM）配置的一个重要功能是能够在单个GPU上的GPU实例之间迁移vGPU，以及在集群中的不同GPU之间更频繁地迁移。

每个GPU实例在整个内存系统中都有独立和隔离的路径--片上的横杆端口、二级缓存库、内存控制器和DRAM地址总线都是唯一分配给单个实例的。这确保了单个用户的工作负载可以以可预测的吞吐量和延迟运行，具有相同的二级缓存分配和DRAM带宽，即使其他任务正在刺激自己的缓存或使其DRAM接口饱和。

(关于基本MIG技术的更多细节，请参考NVIDIA A100 Tensor Core GPU白皮书）。



**H100 MIG的改进**

与A100相比，H100中新的第二代MIG技术为每个GPU实例提供了约3倍的计算能力和近2倍的内存带宽。英伟达Hopper架构通过提供完全安全的、云原生的多用户MIG配置，增强了MIG技术。利用硬件和管理程序层面的新保密计算功能，最多可以将七个GPU实例安全地相互隔离（关于保密计算的更多细节，请参见下文的安全增强和保密计算部分）。



图23显示了一个CPU和GPU合作提供多个可信执行环境（TEEs）的系统配置实例，多个用户共享一个GPU。CPU端提供多个带有安全NVIDIA驱动程序的保密虚拟机。本例中的H100 GPU被划分为四个安全MIG实例。加密的传输发生在CPU和GPU之间。使用PCIe SR-IOV提供GPU硬件虚拟化（每个MIG实例有一个虚拟功能（VF））。保密性和数据完整性由多个基于硬件的安全功能提供，硬件防火墙在GPU实例之间提供内存隔离。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6lWniahQUYZnZ3X3fia194xOshxuibZvibQZv09YymByR4H1nlTzAPAuykw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Hopper架构现在还允许为每个GPU实例提供专用的图像和视频解码器，以便在共享基础设施上提供安全、高通量的智能视频分析（IVA）。每个MIG GPU实例都可以接受至少一个NVDEC和NVJPG单元。

此外，H100 MIG实例现在还包括它们自己的性能监控器组，可以与NVIDIA开发人员工具一起使用。利用Hopper的并发剖析功能，管理员可以监控正确大小的GPU加速，并在用户之间无缝分配资源。



**Transformer Engine**

**模型面临的挑战是智能管理精度以保持准确性，同时获得更小、更快数值格式所能实现的性能。Transformer 引擎利用定制的、经NVIDIA调优的启发式算法来解决上述挑战，该算法可在 FP8 与 FP16 计算之间动态选择，并自动处理每层中这些精度之间的重新投射和缩放。**

**
**

Transformer models是目前从BERT*(* *BERT**基于transformer的双向编码表示，它是一个预训练模型，模型训练时的两个任务是预测句子中被掩盖的词以及判断输入的两个句子是不是上下句)*到GPT-3*(GPT-3是基于上下文的生成AI系统。当您向GPT-3提供提示或上下文时，它可以填写其余内容。如果您开始撰写文章，它将继续撰写文章)*广泛使用的语言模型的骨干，需要巨大的计算资源。最初为自然语言处理（NLP）开发的变形器越来越多地被应用于不同的领域，如计算机视觉、药物发现等等。它们的规模继续呈指数级增长，现在已达到数万亿的参数，并导致其训练时间延长到几个月，由于大量的计算要求，这对商业需求来说是不切实际的。例如，Megatron Turing NLG（MT-NLG）需要2048个NVIDIA A100 GPU运行8周来进行训练。总的来说，变压器模型在过去五年中以每两年275倍的速度增长，比大多数其他人工智能模型快得多（见图24）。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6A1pnHz9PbPtYj6u6gszHdD34osQMEndiaLTROMhWDvfibqJeBibHgd0EQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

H100包括一个新的Transformer Engine，它是一种定制的Hopper Tensor Core技术，可以极大地加速Transformer的AI计算。



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWRvqlicfB5IUnUYCLI8QTp6EToPcKOlHlLze2WsTZR6tDW5VYxfXDWFxVG17VMCr7EPRZ1XRyN7jA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

混合精度的目标是智能地管理精度以保持精度，同时仍然获得更小、更快的数字格式的性能。在Transformer模型的每一层，Transformer引擎分析由张量核心产生的输出值的统计数据。有了关于接下来是哪种类型的神经网络层以及它需要什么精度的知识，Transformer Engine还决定在将张量存储到内存之前将其转换为哪种目标格式。与其他数字格式相比，FP8的范围更为有限。为了最佳地利用可用的范围，转化器引擎还使用从张量统计中计算出的缩放因子，动态地将张量数据缩放到可表示的范围内。因此，每一层都在它所需要的范围内运行，并以最佳方式加速。



**第四代NVLink和NVLink网络 Fourth-Generation NVLink and NVLink Network**

新兴的超大规模HPC和万亿级参数的人工智能模型的任务，如超人的对话式人工智能，需要几个月的时间来训练，即使是在超级计算机上。将这种延长的训练时间从几个月压缩到几天，以便对企业更有用，这需要在服务器集群中的每个GPU之间进行高速、无缝通信。PCIe以其有限的带宽创造了一个瓶颈。为了建立最强大的端到端计算平台，需要更快、更可扩展的NVLink互连。(PCIe 5.0 x16模式下的双向带宽高达128GB/s; 3.0是32GB/s、4.0是64GB/s)



NVLink是NVIDIA的高带宽、高能效、低延迟、无损的GPU到GPU的互连，包括弹性功能，如链接级错误检测和数据包重放机制，以保证数据的成功传输。新的第四代NVLink在H100 GPU中实现，与之前NVIDIA A100 Tensor Core GPU中使用的第三代NVLink相比，其通信带宽提高了1.5倍。



新的NVLink在多GPU IO和共享内存访问方面的总带宽为900 GB/秒，提供了7倍于PCIe Gen 5的带宽。A100中的第三代NVLink在每个方向上使用四个差分对（4条通道）来创建一个单一的链接，在每个方向上提供25GB/秒的有效带宽，而第四代NVLink在每个方向上只使用两个高速差分对来形成一个单一的链接，在每个方向上也提供25GB/秒的有效带宽。H100包括18个第四代NVLink链接(一个GPU板子上8个GPU，4个NVS之间的18个NVlink)，提供900GB/秒的总带宽(900/18=50 50/2=25)，而A100包括12个第三代NVLink链接，提供600GB/秒的总带宽(600/12=50 50/2=25)。



在第四代NVLink的基础上，H100还引入了新的NVLink网络互连，这是NVLink的一个可扩展版本，可以在多个计算节点上实现GPU到GPU的通信，最多可达256个GPU(每个服务器8个GPU，一共32个服务器，共计256GPU)。



与普通的NVLink不同，所有的GPU共享一个共同的地址空间，请求直接使用GPU物理地址进行路由，NVLink网络引入了一个新的网络地址空间，由H100的新地址转换硬件支持，将所有GPU的地址空间彼此隔离，并与网络地址空间隔离。这使得NVLink网络能够安全地扩展到更多的GPU。



**第三代NVSwitch   Third-Generation NVSwitch Fourth-Generation NVLink and NVLink Network**

新的第三代NVSwitch技术包括驻扎在节点内部和外部的交换机，用于连接服务器、集群和数据中心环境中的多个GPU。节点内的每个新的第三代NVSwitch提供64个第四代NVLink链接端口，以加速多GPU连接。交换机的总吞吐量从上一代的7.2 Tbits/秒增加到13.6 Tbits/秒。



新的第三代NVSwitch还提供了 multicast and NVIDIA SHARP in-network reductions.的硬件加速。加速的集体操作包括write broadcast （all_gather）、reduce_scatter和 broadcast atomics.。与在A100上使用NCCL相比，In-fabric multicast和 reductions提供了高达2倍的吞吐量增益，同时大大降低了小块大小的集体的延迟时间。NVSwitch对集体通信进行加速，大大降低了集体通信对SM的负载。





**新型NVLink交换系统    New NVLink Switch System**

每个GPU节点暴露出节点中所有NVLink带宽的2:1的锥形水平。节点通过包含在NVLink交换机模块中的第二级NVSwitches连接在一起，这些模块位于计算节点之外，将多个节点连接在一起。



NVLink交换机系统最多支持256个GPU。连接的节点能够提供57.6TB的全对全带宽，并能提供令人难以置信的1 exaFLOP的FP8稀疏AI计算。参见图26，基于A100和H100的32个节点、256个GPU的DGX SuperPOD的比较。请注意，基于H100的SuperPOD可以选择使用新的NVLink交换机将DGX节点互连。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0vnlZ3EeIoMbdqRckIyKa7yUIOpRjegNW6OfvFPsFCic0Sicc4kx2NhJA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

DGX H100 SuperPODs可以跨越多达256个GPU，使用基于第三代NVSwitch技术的新型NVLink交换机通过NVLink交换系统完全连接。2:1锥形胖子树拓扑结构的NVLink网络互连使分切带宽惊人地增加，例如，全对全交换的带宽增加了9倍，全还原的吞吐量比上一代InfiniBand系统增加了4.5倍。DGX H100 SuperPOD将把NVLINK交换系统作为一个选项。

图26. DGX A100与DGX H100 256个节点的NVIDIA SuperPOD比较



交换机到交换机的最大电缆长度从5米增加到20米。现在已经支持英伟达公司生产的OSFP（八进制小尺寸可插拔）LinkX电缆。它们的特点是每个OSFP都有四端口光收发器，以及8通道100G PAM4信令。四端口OSFP收发器的创新使得一个1RU、32个笼子的NVLink交换机中总共有128个NVLink端口，每个端口以25GB/秒的速度传输数据。



**PCIe第5代**

H100集成了一个PCI Express Gen 5 x16通道接口，提供128GB/秒的总带宽（每个方向64GB/秒），而A100中的Gen 4 PCIe总带宽为64GB/秒（每个方向32GB/秒）。



使用其PCIe第5代接口，H100可以与最高性能的x86 CPU和SmartNICs / DPU（数据处理单元）连接。H100是为与NVIDIA BlueField-3 DPU的最佳连接而设计的，用于400 Gb/s以太网或NDR（下一个数据速率）400 Gb/s InfiniBand网络加速，以确保HPC和AI工作负载。



H100增加了对原生PCIe原子操作的支持，如原子CAS、原子交换和原子获取增加32和64位数据类型，加速了CPU和GPU之间的同步和原子操作。H100还支持SR-IOV，允许为多个进程或虚拟机（VM）共享和虚拟化单个PCIe连接的GPU。H100还允许单个SR-IOV PCIe-connected GPU的虚拟功能（VF）或物理功能（PF）通过NVLink访问同行的GPU。



**安全性增强和保密计算**

英伟达正越来越多地将更多的GPU卖给对安全敏感的市场。云服务提供商（CSP）、汽车制造商、国家实验室、医疗保健、金融以及许多其他行业和组织都对安全性有很高的要求。每一代NVIDIA GPU都在不断改进安全功能。



每天都有大量的敏感数据被生成、存储和处理，受到越来越多的监管和网络攻击的商业风险。虽然有先进的加密技术来保护存储中的静止数据以及网络中的传输数据，但在保护正在处理或使用中的数据方面，目前还存在很大差距。新的保密计算技术通过保护使用中的数据和应用程序来解决这一差距，并为管理敏感和受管制数据的组织提供更高的安全性。



NVIDIA H100包括许多安全功能，可以限制对GPU内容的访问，确保只有经授权的实体才能访问，提供安全启动和证明功能，并在系统运行时主动监测攻击。此外，专门的片上安全处理器，支持多种类型和级别的加密，硬件保护的内存区域，特权访问控制寄存器，片上传感器，以及许多其他功能，为我们的客户和他们的数据提供安全的GPU处理。



H100是世界上第一个具有保密计算能力的GPU。用户可以在访问H100 GPU前所未有的加速能力的同时，保护他们的数据和应用程序 "使用中 "的保密性和完整性。H100提供了广泛的其他安全功能，以保护用户数据，抵御硬件和软件攻击，并在虚拟化和MIG环境中更好地相互隔离和保护虚拟机。



英伟达H100 GPU全面安全功能的主要目标包括。

● 数据保护和隔离。防止未经授权的实体获取另一个用户的数据，其中的实体可以是用户、操作系统、管理程序或GPU固件。

● 内容保护。防止未经授权的实体访问存储在GPU上或由GPU处理的受保护内容。

● 物理损坏保护。防止对GPU的物理损坏，无论它是由恶意行为者还是由意外造成的。





**英伟达保密计算**

英伟达是保密计算联盟Confidential Computing Consortium (C3),的成员，C3是由供应商、学术机构、开源项目和软件开发人员组成的国际组合，他们合作开发各种倡议和技术，以减少安全威胁，保护公共云服务、内部数据中心以及边缘系统和设备中使用的敏感数据和应用程序。



保密计算一词的正式定义是 "通过在基于硬件的可信执行环境（TEE）中进行计算来保护使用中的数据"。该定义与数据的使用地点无关，无论是在云中，还是在终端用户设备中，还是在两者之间。它也与保护数据的处理器或使用的保护技术无关。C3将TEE定义为 "为数据保密性、数据完整性和代码完整性这三个关键属性提供一定程度保证的环境"。



今天，数据通常在休息、存储和网络传输中受到保护，但在使用中却没有受到操作系统/管理程序的保护。这种信任操作系统/管理程序的要求在保护用户的数据和代码方面留下了很大的空白。此外，在传统的计算基础设施中，保护正在使用中的数据和代码的能力是有限的。处理敏感数据的组织，如个人身份信息（PII）、金融和健康数据，或被要求满足数据本地化的规定，需要在所有阶段减轻针对其应用程序、模型和数据的保密性和完整性的威胁。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0NkTB3ZXwMRsF2hw75sGguWkriauLQLc7eCpTwzfyzvCgIBdpn0zoksg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

保密计算保护ISV客户数据和云端、内部和边缘的训练有素的AI模型的机密性

图27. 保密计算为多种ISV场景提供保护



现有的保密计算解决方案是基于CPU的，对于人工智能和HPC等计算密集型工作负载来说太慢了。基于CPU的保密计算通常会降低系统性能，这可能会影响生产力，或者在延迟敏感的数据处理工作负载中不可行。



借助英伟达保密计算--英伟达Hopper架构中引入的一项新的安全功能，H100是全球首款能够保护数据和代码在使用中的保密性和完整性的GPU。H100将加速计算带入保密计算的世界，并将CPU的可信执行环境扩展到GPU上。H100为许多用例打开了大门，在这些用例中，由于需要在使用时保护数据和代码，以及以前的保密计算解决方案对于许多工作负载来说性能或灵活性都不够，所以过去不可能使用共享基础设施（云、主机托管、边缘）。



英伟达保密计算创建了一个基于硬件的可信执行环境hardware-based Trusted Execution Environment（TEE），该环境可以保护和隔离在单个H100 GPU、一个节点内的多个H100 GPU或单个安全多实例GPU（MIG）实例上运行的整个工作负载。可信执行环境（TEE）在GPU上的保密虚拟机和CPU中的对应虚拟机之间建立了一个安全通道。TEE提供两种操作模式。

1. 整个GPU被专门分配给一个虚拟机（一个虚拟机也可以同时分配多个GPU）。
2. 一个NVIDIA H100 GPU被分区，使用MIG技术支持多个虚拟机，实现多用户保密计算。GPU加速的应用程序可以在TEE内不变地运行，不需要手动进行分区。



用户可以将用于人工智能和高性能计算的英伟达软件的丰富产品组合和功能与英伟达保密计算提供的硬件信任根的安全性结合起来，在最低的GPU架构层面提供安全和数据保护。用户可以在共享或远程基础设施上运行和验证应用程序，并确保任何未经授权的实体，包括管理程序、主机操作系统、系统管理员、基础设施所有者或任何具有物理访问权限的人，在TEE内使用时无法查看或修改应用程序代码和数据。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0ibFaGllAHhKxI8VH2ic688rnQfUmpExD3D38fEb2ianv89v98aXib5xKgw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Hopper架构的保密计算能力进一步放大和加速了协作式多方计算用例的安全性，如联合学习。联合学习使多个组织能够共同训练或评估人工智能模型，而不必分享每个小组的专有数据集。使用H100的机密联合学习确保数据和人工智能模型在每个参与的站点受到保护，不会受到外部或内部威胁的未经授权的访问，并且每个站点可以了解和证明在其同行处运行的软件。这增加了对安全合作的信心，推动了医学研究的进步，加快了药物开发，减轻了保险和金融欺诈，以及其他大量的应用--同时保持安全、隐私和监管合规。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0wRxgo0xxhVGCBS0CmpF9xJkREpkYic9YvGxp37abA8gUtYKcRAicgkJw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

图29. 保密的联合学习



尽管在GPU中提供保密计算能力涉及许多组件，但其中一个更重要的功能是安全和测量的启动，如下所述。



**衡量的成功**

虽然NVIDIA Ampere GPU架构包括安全启动技术，但它不支持测量启动，而测量启动是保密计算合规性的要求。我们将简要讨论H100中实现的安全和测量启动的概念和组成部分。



安全启动是一套硬件和软件系统，确保GPU从已知的安全状态启动，只允许经过认证的固件和微代码在GPU启动时运行，这些固件和微代码是由NVIDIA编写和审查的。测量性启动是收集、安全存储和报告启动过程中的特征的过程，这些特征决定了GPU的安全状态。证明和验证是将测量值与参考值进行比较的手段，以确保设备是一个预期的安全状态。英伟达提供证明人、参考值和认可签名。



部署工作流程利用通过实测启动提供的测量值，与英伟达或服务提供商提供的参考值进行比较，以确定系统是否处于准备就绪的安全状态，可以开始在客户数据上运行。一旦系统得到验证，客户就可以启动应用程序，就像他们在非保密的计算环境中运行相同的应用程序一样。





**英伟达保密计算实施概述**

如图30所示，在关闭NVIDIA CC的左侧显示了传统的PC架构，其中主机操作系统和管理程序可以完全访问设备，例如GPU。右侧为NVIDIA CC开启状态，显示了虚拟机与其他元素的完全隔离。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e057FYNmSk4PBAtIXskUhq0iaEoiaLia5fNVTnOickofPNmbsEicaVuqO7YgQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

完全的虚拟机TEE和GPU TEE隔离，形成一个保密的计算环境，是由强大的基于硬件的安全性提供的，包括前面部分解释的三个关键因素。



- 芯片上的信任根（RoT）--在操作系统可以与GPU通信之前，GPU使用RoT来确保设备上运行的固件是真实的，没有被设备所有者（CSP等）篡改过
- 设备认证 - 允许用户确保他们与启用保密计算的真实NVIDIA GPU进行通信，并且GPU的安全状态与已知的、可信任的安全状态相匹配，包括固件和硬件配置。
- AES-GCM 256 - CPU和H100 GPU之间的数据传输以PCIe线速进行加密/解密，使用AES256-GCM的硬件实现。这为在总线上传输的数据提供了保密性和完整性，密钥只对CPU和GPU的TEE有效，加密实现将被认证为FIPS 140-3级别。
- 

请注意，使用英伟达保密计算技术不需要修改CUDA应用代码。







**H100视频/IO功能**

用于DL的NVDEC

与A100相比，H100显著提高了视频解码能力。在DL平台中，输入视频以任何行业标准进行压缩，如H264/HEVC/VP9等。在DL平台中实现高的端到端吞吐量的重大挑战之一是要能够平衡视频解码性能与训练和推理性能。否则，GPU的全部DL性能就无法得到利用。H100通过支持八（8）个NVDEC（NVida DECode）单元，而A100中只有五（5）个NVDEC单元，显著提高了解码吞吐量。这也确保了在MIG操作中，每个MIG分区都能获得至少一个NVDEC单元。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0IFsibf3AabwFKzbVBxEhZQ7RjupibutfQGPa8djTCw1kFvpb3cfo6GyQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0dGZhfWLtWPvAtYIWOcTSoF4a3LexdMXTUlWvcd1jFpVIQ68Dk4SPPQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**NVJPG（JPEG）解码**

实现图像的DL训练和推理的高吞吐量的基本瓶颈之一是图像的JPEG解码过程（压缩->原始）。由于用于处理图像位的串行操作，CPU和GPU对JPEG解码的效率不高。另外，如果JPEG解码在CPU中完成，PCIe就成为另一个瓶颈。



H100包括八个单核NVJPG HW引擎来加速JPEG解码，而A100只有一个5核引擎。

H100 NVJPG引擎的亮点。

NVJPG支持YUV420, YUV422, YUV444, YUV400和RGBA格式。

● 从A100改进的JPEG架构：H100增加了8个单核引擎，而不是A100的5核引擎。这大大简化了软件的使用模式，因为JPEG图像可以独立地分配到各个引擎中，而不是收集成五个图像的批次。此外，它还提高了同一批次中异质图像分辨率情况下的吞吐量。

在MIG操作中，每个MIG分区可以得到至少一个NVJPG引擎。

JPEG的吞吐量比A100有很大的提高

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0emsoAMqLhYRsy1ICFLW806tMPQccXxIaEsPVQRxPCibDdnpGrHqsy6A/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

英伟达提供了一个数据加载库（DALI），通过自动调用NVDEC/NVJPG来管理视频/图像管道的硬件加速。它为人工智能开发者在DL工作负载中使用视频/图像硬件引擎提供了一种简单的方法。它还允许灵活的图形来创建自定义视频/图像管道。DALI的详细描述和用户指南可在https://docs.nvidia.com/deeplearning/dali/user-guide/docs/。DALI库可以从https://github.com/NVIDIA/DALI。







**NVIDIA DGX H100 - 全球最完整的AI平台**

NVIDIA DGX H100为商业创新和优化提供动力。DGX H100是NVIDIA传奇的DGX系统的最新迭代产品，也是NVIDIA DGX SuperPOD的基础，它是一个AI动力源，采用了开创性的NVIDIA H100 Tensor Core GPU。该系统的设计目的只有一个，那就是最大限度地提高人工智能的吞吐量，为企业提供一个高度精细、系统化和可扩展的平台，帮助他们在自然语言处理、推荐系统、数据分析等方面实现突破。DGX H100可以在企业内部使用，也可以通过各种访问和部署选项使用，它为企业解决人工智能的最大挑战提供了所需的性能。



**DGX H100概述**

NVIDIA DGX H100是一款用于训练、推理和分析的通用高性能AI系统。DGX H100采用Bluefield-3、NDR InfiniBand和第二代MIG技术，为云原生准备就绪。单个DGX H100系统可提供无与伦比的32 petaFLOPS的性能。通过将多个DGX H100系统连接成被称为DGX POD或甚至DGX SuperPOD的集群，这一性能可以被轻松提升。

每个DGX H100系统由以下部分组成

● 8 x H100 Tensor Core GPUs

● 4th gen Tensor Cores

● 4th gen NVLink

● 3rd gen NVSwitch (x4)

● 8x ConnectX-7 (400Gb/s InfiniBand / Ethernet)

● 2x Bluefield-3 DPUs

● PCIe Gen5 enabled





**无与伦比的数据中心可扩展性**

NVIDIA DGX H100是NVIDIA DGX SuperPOD等大型AI集群的基础构件，是企业可扩展AI基础设施的蓝图。DGX H100中的8个NVIDIA H100 GPU使用全新的高性能第四代NVLink技术，通过4个第三代NVSwitches进行互连。第四代NVLink技术的通信带宽是上一代的1.5倍，比PCIe Gen5快7倍。它提供了高达7.2TB/秒的GPU到GPU的总吞吐量，与上一代DGX A100相比，几乎提高了1.5倍。DGX H100系统包括8个NVIDIA ConnectX-7 InfiniBand/Ethernet适配器，每个适配器的运行速度为400Gb/sec，为大规模的AI工作负载提供了强大的高速结构。



每个DGX H100还包括两个NVIDIA BlueField-3 DPU（数据处理单元），用于智能、硬件加速的存储、安全和网络管理功能。BlueField-3 DPU将传统的计算环境转变为安全和加速的虚拟私有云，使企业能够在安全的多用户环境中运行应用工作负载。BlueField-3将数据中心基础设施与业务应用脱钩，增强了数据中心的安全性，简化了操作，并降低了总拥有成本。BlueField-3采用了英伟达的网内计算技术，实现了下一代超级计算平台，提供了最佳的裸机性能和对多节点租户隔离的本地支持。



大量GPU加速计算、最先进的网络硬件和软件优化的结合意味着NVIDIA DGX H100可以扩展到数百或数千个节点，以应对下一代AI应用的最大挑战。







NVIDIA DGX H100系统规格

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0Shk6X6lEIF2iaC3g7Fpy253ULOyRakS2u02LSWtBmol4A50hibBgtQmA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)





**英伟达CUDA平台更新**

英伟达™（NVIDIA®）CUDA是一个全面的、富有成效的、高性能的加速计算平台。它利用GPU、CPU、DPU和网络内计算，在各个层面加速终端用户的应用程序，从系统软件到特定的应用程序库和框架（见图31）。其成熟和用户友好的工具链、开发者工具和文档为加速的异构应用提供了最佳的开发者体验。

高性能的库和框架



CUDA库使普通数学（CUDA数学库）、并行算法（CUB和Thrust）、线性代数（cuBLAS）、密集和稀疏线性求解器（cuSOLVER和cuSPARSE）、FFT（cuFFT）、随机数生成（cuRAND）、张量操作（cuTENSOR）、图像和信号处理（NPP）、JPEG解码（nvJPEG）和GPU管理（NVML）的性能得到了最大化。cuNumeric通过Legate和Legion运行时透明地加速和分发NumPy程序到任何规模的机器上，而不需要修改任何代码。libcu++提供异构同步和数据移动基元，以实现高并发、异构、符合ISO标准的C++应用。



此外，CUDA平台的通信库实现了基于标准的可扩展系统编程。HPC-X是一个CUDA感知的MPI库，支持GPUDirect，可直接使用RDMA发送和接收GPU缓冲区。NVIDIA集体通信库（NCCL）实现了高度优化的多节点集体通信原语。NVSHMEM基于OpenSHMEM，为主机和设备线程提供异构多节点通信基元。cuFile和MAGNUM IO通过GPUDirect存储实现了异构应用的高性能文件I/O。



一套广泛的特定领域的库和框架进一步加速了广泛的应用领域的主要算法，例如，深度神经网络（cuDNN）、模拟和隐式非结构化方法的线性求解器（AmgX）、量子计算（cuQuantum）、数据科学和机器学习（RAPIDS）、机器学习的数据加载和预处理（DALI），以及实时3D模拟和设计协作（Omniverse）等等。150多个软件开发工具包利用这些库，帮助开发人员在大量的应用领域实现高生产力，包括高性能计算（NVIDIA HPC SDK）、AI、机器学习、深度学习。和数据科学、基因组学（NVIDIA CLARA）、智能城市（NVIDIA Metropolis）、自动驾驶（NVIDIA Drive SDKs）、电信（NVIDIA Aerial SDK）、机器人（NVIDIA Isaac SDK）、网络安全（NVIDIA Morpheus SDK）、计算机视觉等等。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0bU8O4kEjqSAeUicZ9NanTyCpQbbO22RvEdYOxsWp5ia1v3BGOxVtrn3Q/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**系统软件**

NVIDIA CUDA平台还提供了灵活的系统软件组件，帮助用户高效地部署、管理和优化大型异构系统。这些软件包括设备驱动程序（CUDA驱动程序）、设备管理软件（NVML、NVIDIA-smi、DCGM和Unified Fabric Manager）、用于异构网络和文件I/O的GPUDirect，以及容器感知的作业调度系统和操作系统（DGX OS）。





**语言和编译器**

CUDA平台通过NVIDIA的NVVM IR和NVIDIA的libNVVM，为生成高度优化的设备二进制文件提供了一个统一的、灵活的编译器栈。NVVM IR是一个基于LLVM 7的编译器中间代表（IR），为生成GPU计算内核提供了一个前端编译器目标。libNVVM是一个库，用于将NVVM IR编译并优化为PTX，即NVIDIA GPU的虚拟ISA。所有的NVIDIA计算编译器都使用libNVVM来针对NVIDIA GPU（图32），它使用户和框架能够将其选择的编程语言带到CUDA平台上，其代码生成质量和优化程度与CUDA C++本身相同。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0Ha9kQtsCkHyOGNDYv4tdOlqy2JibvO40FUn7yuPo1BwPZk9S77nvBBQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

前端使用libNVVM将NVVM IR程序编译为PTX并在GPU上运行。

图32. 高级语言前台



PTX是NVIDIA GPU的虚拟ISA，是由第三方生产商针对我们的目标架构有效运行的公共ISA。PTX还具有向前兼容的优点，可以离线或在运行时进行组装。



在许多应用中，要生成的GPU计算内核取决于程序输入。虽然这些应用程序可以生成NVVM IR，但英伟达运行时编译器允许这些应用程序生成熟悉的CUDA C++，从而显著提高了这些应用程序及其用户的生产力。NVRTC在运行时使用libNVVM将CUDA C++编译成PTX，或者使用嵌入式PTX汇编器将其编译成本地GPU二进制代码。这使得应用程序（例如Python程序）能够为用户输入的程序动态生成内核，而C++程序则能够在运行时根据程序输入专门计算内核。



NVIDIA HPC SDK是一套用于异构系统的工具链。NVCC是一个CUDA C++编译器，它提供了一个分离式编译模型，将GPU编译与外部主机编译器（如GCC）配对（图33：左）。英伟达HPC编译器--NVC、NVC++和NVFortran--提供了一个统一的异构编译模型（图33：右）。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0g3wGll78wbPCnIj1Mn3A9Ofe6OntN8ODCKWhcHm7sCicaE1Hvg9DPOg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

统一编译器只对程序进行一次解析和优化，然后再为不同的目标分割编译过程。这种模式可以实现nvcc中所没有的某些功能。例如，在nvcc中，CUDA C++设备代码需要__device__注释（图34，左）。而NVC++编译器不需要这些注解（图34，右），如果程序使用了某个特定目标的函数，并且其定义是可以达到的，编译器就会尝试编译它。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0DQTXgibP2EfA37M69AV6a3sHr46u9v5xgMCAg2De3gWUUjCzyH8IBhw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Figure 34. Unified toolchain supports execution-space inference统一编译简化了开发，使GPU编程对初学者来说更容易理解，同时使有经验的开发者更有成效。

它还增加了主机和设备目标之间的代码重用，简化了加速GPU应用程序的过程。





**使用DPX指令进行基因组学加速**

英伟达H100可以对众多不同类型的应用程序和算法进行加速，与之前的GPU和CPU相比有不同的X因素。在本节中，我们将重点介绍H100在基因组学领域提供的显著加速。基因组和蛋白质分析对人类来说从未像过去几年那样，随着传染病的兴起和全球大流行病的危险而变得更加关键。



H100引入了新的DPX指令，这是新的专用硬件指令，用于加速动态编程算法，如用于DNA基因测序的Smith-Waterman算法，以及用于蛋白质分类和折叠。与NVIDIA Ampere A100 GPU相比，H100为Smith-Waterman算法提供了高达7倍的速度，使疾病诊断、病毒突变研究和疫苗开发方面的解决方案的时间大大加快。下面是一个关于基因组学和基因测序的简短教程。



基因组学领域正在飞速发展，改变了医疗保健、农业和生命科学行业，同时也是我们对抗SARS-CoV-2和COVID-19的最犀利武器之一。对人类基因组进行测序--无论是整体还是选定的部分--对我们了解它的工作原理至关重要，这使我们能够确定可能导致疾病、提供保护和成为治疗目标的基因变异。随着各组织利用基因组来了解疾病、发现药物和加强病人护理，数据分析和管理正成为提取基因组价值的主要工具。



自2005年引入下一代测序（NGS）以来，该行业经历了数据爆炸，并创造了围绕人类基因组的新产业，从解决家族史到临床护理。基因组学受益于先进的计算系统，它可以加速将原始仪器数据转化为生物洞察力所需的计算密集型步骤。一个人的基因组的原始数据大小大约为100千兆字节（GB）。这在分析之后会增长到超过225GB的总数据量，这需要利用复杂的算法和应用，如深度学习和自然语言处理。用GPU加速数学模型为传统的基因组学分析提供了明显的好处，如测序读数处理和变体识别，但它也有可能彻底改变我们对特定基因组变体如何影响疾病和健康的理解。



NVIDIA Clara Parabricks是用于下一代测序数据的加速计算框架，支持DNA和RNA应用的端到端数据分析工作流程。在一套NVIDIA GPU平台上运行，Clara Parabricks提供了超过50种加速工具，其中包括GPU加速器。



加速工具，包括由GPU加速的Burrows-Wheeler Aligner（BWA-MEM）、Picard和Samtools，以及一套用于注释、过滤和结合多种变体调用格式（VCF）的实用程序。整个工作流程中的加速工具的组合意味着可以在几分钟内生成结果，而不是几小时或几天。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0w9ibicZTrmYj5Iof3yfPBceNOT9Bsm9NLoPxSoH31U1Vf6eQMWgwTT9Q/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

基因组是一个生物体的全套脱氧核糖核酸（DNA），这是一种含有发展和指导每个生物体活动所需的遗传指令的化合物。DNA分子由两条扭曲的成对的链组成。每条链由四个化学单位组成，称为核苷酸碱基。这些碱基是腺嘌呤（A）、胸腺嘧啶（T）、鸟嘌呤（G）和胞嘧啶（C）。相反链上的碱基专门配对；A总是与T配对，C总是与G配对。人类基因组包含大约30亿个这样的碱基对，它们存在于我们所有细胞核内的23对染色体中。基因组测序意味着确定一段DNA中碱基对的确切顺序。



一个人的DNA测序过程开始于将DNA分成互补对的化学过程，将DNA链切成特定大小的块（可能是100到2000个碱基对长），并通过测序机对这些小块（称为读数）进行测序，产生计算机可读的碱基对代码的序列。然后通过搜索参考基因组中的序列位置来重新组装这些测序块，或者通过De Novo方法，通过寻找碱基的重叠模式来组装测序块，而不是依赖参考基因组序列。



从计算的角度来看，这个问题可以归结为从参考基因组中搜索和匹配一组长达数十亿个碱基对的 "读数"，或者通过模式匹配算法从头开始组装基因组，该算法比较数百万个读数以找到重叠部分，并以正确的顺序对齐。在这个过程中，算法可能需要插入、编辑或删除序列以解决不匹配问题，还需要指定可能遇到的各种类型不匹配的代价。因此，模式匹配的计算硬件结构需要灵活地适应这些要求，同时支持用于基因组学中其他问题的其他类型的类似算法，如蛋白质测序。



用于DNA测序的Smith-Waterman算法被用于NVIDIA CLARA Parabricks加速计算框架的GPU加速BWA-MEM模块中。该算法基本上是通过比较两串碱读数来创建一个评分矩阵，然后根据矩阵中分数的回溯来确定两串的最佳匹配模式。关于这种算法在基因组测序中的应用，这里有一个很好的解释。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULQ5tPQXEvQQT75AicXx8e0TmuPnsI424FWgJOJAxbDzzcnpVV7Y97PGJV3KCQ39nKbLwGrticSoBw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在上面的插图中，矩阵的每个单元格更新需要5个基本计算。

1.从匹配的对角线元素中加入一个x值（本图中x=3）。

2.从不匹配的对角线元素中减去一个x的值

3.在垂直元素错位上减去y的值（本图中y=2）。

4.在水平元素上减去z的值（本图中z=2）。

5. 找出上述四项操作的最大值（如果结果为负数，则将该单元格清零）。



H100中新的DPX指令被优化以加速上述一组计算和其他类似的算法。