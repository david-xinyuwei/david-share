**一、如何让训练更快？**

我们反过来想，训练时间的长短由什么决定。

如果直观来考虑，可以得出如下公式：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW1icFAyCvRG1IBUXsUwiamgKep1a8sn7rOL0AFWiaa14TZLUxZJScibZzStocJlXLVny5OtJ06kxWCPw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

但我们需要细化决定因素。

在深度学习训练中，训练时间的算涉及到多个因素，包括Epochs数量、全局批次大小（Global Batch Size）、微批次大小（Micro Batch Size）以及计算设备的数量等。以下是这些参数之间关系的一个基本公式（注意只是一个基本示意公式，主要解释正比反比，实际训练需要考虑的因素可能更多）：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW1icFAyCvRG1IBUXsUwiamgKkUuMEb2Qbr7k5cK1pCrTtkVDjuZ4O3lmbRPia0P7uHwjXaDlnY06eEA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

其中：

- Epochs 是指模型处理整个训练数据集的次数。
- Total Number of Samples 是训练数据集中的样本总数。
- Global Batch Size 是在每次训练迭代中处理的数据样本总数。
- Time per Step 是每次训练迭代所需的时间，这取决于硬件性能、模型复杂性、优化算法等因素。
- Number of Devices 是进行训练的计算设备数量，例如GPU数量。



这个公式提供了一个基本的框架，但请注意，实际的训练时间可能会受到许多其他因素的影响，包括I/O速度、网络延迟（对于分布式训练）、CPU-GPU通信速度等。因此，这个公式只能作为一个粗略的估计，实际的训练时间可能会有所不同。



我们再细化上面的内容。

深度学习模型的训练时间由多个因素决定，包括但不限于以下几点：

1. Epochs数量：一个epoch意味着模型已经处理了整个训练数据集一次。Epochs的数量越多，模型需要处理的数据就越多，因此训练时间就会更长。
2. 全局批次大小：全局批次大小是在每次训练迭代中处理的数据样本总数。全局批次大小越大，每次迭代处理的数据就越多，因此每个epoch需要的迭代次数就会减少，这可能会缩短总的训练时间。然而，如果全局批次大小过大，可能会导致内存溢出。
3. 微批次大小：微批次大小是指在每次训练迭代中，每个计算设备处理的数据样本数量。微批次大小越大，每个设备每次迭代处理的数据就越多，这可能会提高计算效率，从而缩短训练时间。然而，如果微批次大小过大，可能会导致内存溢出。
4. 硬件性能：使用的计算设备（如CPU、GPU）的性能也会影响训练时间。性能更强的设备可以更快地进行计算，从而缩短训练时间。
5. 模型复杂性：模型的复杂性（如层数、参数数量等）也会影响训练时间。模型越复杂，需要的计算就越多，因此训练时间就会更长。
6. 优化算法：使用的优化算法（如SGD、Adam等）和学习率等超参数设置也会影响训练时间。
7. 并行策略：如数据并行、模型并行等并行计算策略的使用也会影响训练时间。



决定训练时间长短的因素有很多，需要根据具体的训练任务和环境来综合考虑。



那么，在这个公式中，

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW1icFAyCvRG1IBUXsUwiamgK32WIIEJMarNpEsD5ib3dn78Gvpq7nexmDaN0UgcVB0V11RDWOPiaS3wA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

time per step应该理解成主要和GPU的硬算力相关。

“Time per Step”，即每次训练step所需的时间，是由多个因素决定的，包括但不限于以下几点：

1. 硬件性能：使用的计算设备（如CPU、GPU）的性能会直接影响每次训练迭代的速度。性能更强的设备可以更快地进行计算。

2. 模型复杂性：模型的复杂性（如层数、参数数量等）也会影响每次训练迭代的时间。模型越复杂，需要的计算就越多。

3. 优化算法：使用的优化算法（如SGD、Adam等）也会影响每次训练迭代的时间。一些优化算法可能需要更复杂的计算步骤来更新模型参数。

   

   

那么total training steps由什么决定的呢？

Total Training Steps"是由训练的Epochs数量和每个Epoch中的Steps数量决定的。具体来说，它等于Epochs的数量乘以每个Epoch中的Steps数量。这可以用以下公式表示：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW1icFAyCvRG1IBUXsUwiamgKiaXlj0yo1PmBVCWtOf1YsnaOkmHfibwBWAxiac2QcRouRia404WBteyMzQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



那么，Global batch size由什么决定？

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVicfjXY6uPOAe218y2iapDgkOURhgyc4slqogfIy3q0dibia6pZqqSQujG2icrPxyxkfnrHzDQHKicS0tg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**global_batch_size =**

gradient_accumulation_steps

\* nnodes （节点数）

\* nproc_per_node （每个节点卡数）

\* per_device_train_batch_si（micro bs大小）



假设一个场景：

batch_size = 10 #每批次大小 total_num = 1000 #训练数据总量 按照训练一个批次数据，更新一次梯度（梯度累计为1）；

训练步数 train_steps = 1000 / 10 = 100，也就是说此时Steps per Epoch为100 

梯度更新步数 = 1000 / 10 = 100

还需要考虑梯度累计的情况，比如当显存不足以支持每次 10 的训练量，就需要需要减小 batch_size。

通过设置gradient_accumulation_steps = 2

batch_size = 10 / 2 =5

即训练2个批次数据，更新一次梯度，每个批次数据量为5（减小了显存压力，但未改变梯度更新数据量–10个数据一更新）

结果：训练步数 tran_steps = 1000 / 5 = 200 增加了一倍，也就是说Steps per Epoch为200 .

梯度更新步数 1000 / 10 = 100 未改变、

当设置了梯度累计，每个训练步骤处理的数据量会减少，但是为了处理相同数量的数据，需要进行更多的训练步骤。因此，总的训练时间可能会增加。

那么，梯度累计会增加训练的steps   那为啥不直接减小batch size呢？

实际上，梯度累积的主要目的就是在不减小全局批次大小的情况下，减小每个设备上的批次大小（即微批次大小），以适应硬件资源的限制。

全局批次大小对模型的训练效果有重要影响。一般来说，较大的全局批次大小可以提供更准确的梯度估计，从而有助于模型的收敛。然而，较大的全局批次大小也会增加每个设备上的内存压力。如果内存资源有限，可能无法使用较大的全局批次大小进行训练。

这时，我们可以使用梯度累积的策略。通过梯度累积，我们可以在每个设备上使用较小的微批次大小进行训练，从而减小内存压力，同时保持较大的全局批次大小，以获得准确的梯度估计。这样，我们就可以在有限的硬件资源上训练大型模型，而不需要牺牲全局批次大小。

总的来说，梯度累积是一种权衡策略，用于在内存资源有限的情况下，平衡全局批次大小和训练效果。



所以说，如果从这两个公式看：



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW1icFAyCvRG1IBUXsUwiamgKxbwTLd9lneETlM4kIVBibCkXuMmv45m8KBIlxMaqMyQj99qwicpZ382g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW1icFAyCvRG1IBUXsUwiamgKa7Ug9bylPZJe0haLRXYbFia8IGEiaum8j18xRiaCsnKGtn3MZtZpzRrZw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Global batch size越大，总训练时间就越小。前提是不出现OOM和GPU算力占满。这也是之前文章提到的H20增加内存大小、内存带宽、NVL的原因之一。

**二、数据并行与batchsize的关系**

**本小节的内容，实际上是对这个公式展开分析。**

global_batch_size =

gradient_accumulation_steps

\* nnodes （节点数，实际上就是PP）

\* nproc_per_node （每个节点卡数，实际上就是TP）

\* per_device_train_batch_si（micro bs大小）

在分布式深度学习中，数据并行是一种常见的并行策略。在数据并行中，训练数据被拆分（或者说是分割）成多个小批次，然后这些小批次被分发到不同的计算节点上。每个节点都有一个模型的副本，并且使用其接收到的数据子集进行训练。这样，每个节点都可以同时进行模型的训练，从而加速整个训练过程。

在每个训练步骤结束时，所有节点的模型权重会被同步。这个同步过程就是通过AllReduce操作来实现的。AllReduce是一种集合通信操作，它将所有节点的数据聚合在一起，并将结果广播回所有节点。在数据并行中，AllReduce操作用于聚合所有节点的梯度，并将聚合的梯度广播回所有节点。然后，每个节点都使用这个聚合的梯度来更新自己的模型参数。

在深度学习训练中，是否使用AllReduce操作取决于训练策略和所使用的硬件架构。如果你在单个设备（例如，一个GPU或CPU）上进行训练，那么通常不需要使用AllReduce，因为所有的计算和参数更新都在同一个设备上完成。然而，如果在多个设备上进行分布式训练，特别是使用数据并行策略，那么就需要使用AllReduce或其他类似的集合通信操作来同步各个设备上的模型参数。

在使用数据并行（Data Parallelism，DP）策略进行深度学习训练时，许多现代的深度学习框架（如PyTorch和TensorFlow）会使用NVIDIA的集合通信库（NCCL）来实现跨多个GPU的通信。在数据并行中，每个GPU都有模型参数的副本，并且使用自己的数据子集进行训练。然后，在每个训练步骤结束时，所有GPU的模型权重会被同步。这个同步过程就是通过调用NCCL的AllReduce操作来实现的。

总的来说，虽然AllReduce是数据并行中最常用的操作，但在实际的深度学习训练中，可能会根据需要使用到NCCL的其他操作。具体使用哪些操作，取决于深度学习框架和训练策略。

在深度学习训练中，数据并行（Data Parallelism）和微批次大小（Micro Batch Size）是两个相互关联的概念。数据并行是指在多个计算设备（如GPU）上同时进行模型训练，每个设备处理一部分数据。而微批次大小则是指每个设备在每次训练迭代中处理的数据样本数量。

如果配置了数据并行，那么实际上已经在使用微批次大小，即使没有明确地设置它。这是因为当将训练数据分配给多个设备进行并行处理时，你实际上已经将原始的批次大小分割成了多个“微批次”，每个设备处理一个微批次。

如果没有启用数据并行（Data Parallelism，DP）或模型并行（Model Parallelism，MP），也就是说，训练过程只在单个设备（如一个GPU或CPU）上进行，那么微批次大小（Micro Batch Size）和全局批次大小（Global Batch Size）实际上是相等的。

然而，如果启用了数据并行或模型并行，那么全局批次大小和微批次大小就可能不同了。在数据并行中，全局批次大小被分割成多个微批次，每个设备处理一个微批次。所以在这种情况下，全局批次大小是所有设备的微批次大小之和。

数据并行（Data Parallelism，DP）可以在单个服务器的多个设备（例如，多个GPU）之间进行，也可以跨越多个服务器。具体取决于你的硬件配置和你的深度学习框架。

当你设置DP等于8时，这意味着你的训练过程将在8个计算设备上并行进行。这些设备可以全部位于同一台服务器上，也可以分布在多台服务器上。具体的设备分配方式取决于你的深度学习框架和你的硬件配置。

至于流水线并行（Pipeline Parallelism，PP），这是一种不同的并行策略，它允许模型的不同部分在不同的设备上并行执行。在这种情况下，DP等于8意味着在每个流水线阶段，都会有8个设备并行处理数据。

总的来说，DP和PP是可以同时使用的，并且它们可以在单个服务器或跨多个服务器的设备上进行。