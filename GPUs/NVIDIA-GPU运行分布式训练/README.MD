##  NVIDIA GPU运行分布式训练

**一、多GPU训练的挑战**

我们知道，计算机集群是一组松散或紧密连接在一起工作的计算机，因此，在许多方面，它们可以被视为一个单一的系统。


我们需要集群原因是:

需要更快的计算、更大的job、更好的管理统一调度、高可用性。



那么，我们运行多GPU训练的挑战都有什么？

这来自算法和工程两方面的挑战。



算法的挑战

- 数据并行或模型并行

- 同步或异步

- 批量较大，影响模型精度

- 热身，调整学习速率(线性上升，LARC/LARS…)

- 给渐变添加噪声

- 优化器选择(SGD, Momentum, Adam, RMSProp…)

- 平衡速度和准确性

  ![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sAUbicib5yRvLMzg1nP4szPjsLHhHJs4qcPlrvTXAIWzWKHfhYwic4OcZw/640?wx_fmt=png)

工程的挑战

- CPU和GPU性能提升不平衡
- 最好先扩展，然后通过nic向外扩展
- V100/A100, NVLink, NVSwitch, DGX, 10G/25G/100G/200G的匹配和选择
- 混合精度，GPUDirect RDMA(IB/ROCE)
- 从CPU中卸载一些OPs到GPU(数据预处理，Allreduce)
- 梯度压缩，提高通信效率
- 训练框架(Horovod, TensorFlow, PaddlePaddle, PyTorch…)
- 构建分布式GPU训练集群，管理/调度

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sRPP6gdiaHlop4jvVqBTXebmIrMbeaNtOicQOK8XSJG0Rb9aviba5dMSkA/640?wx_fmt=png)



在算法方面的挑战，很大程度上通讯方面的挑战。NCCL可以解决很多问题。



**二、NCCL在多集群训练中的作用**

我们先看一下单GPU卡训练-训练数据。

在下图中，原始数据存在DB中，可以是图像、声音。梯度用于更新参数，更新后的参数和batch再运行，然后再度调整，周而复始，直到有个很好的结果。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sXic5LmMOYWw0SgjdMWMNlv6xZPLE9fxUDUASibqSn6ZLS7KrfLJEX3vg/640?wx_fmt=png)

数据并行的分布式训练，会有很多的GPU 。每个GPU产生梯度之后，产生的都是自己的数据。需要把梯度合并、求和。所以下图最下边需要做一个allreduce的操作。NCCL提供一个高效的并行梯度。allreduce以后，各个GPU又得到了reduce后的梯度，然后用这个梯度更新各自的参数，周而复始。



从下图我们可以看到，NCCL可以解决多节点、多任务的通讯问题。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhq6E1Eyqn1lf6RIbcxLWqE1LwOXSkibQIiahXlA9DZzSsxNu4FuKbnpeQ/640?wx_fmt=png)

NCCL上的buffer，都是GPU上的，支持多种网络互联。



**三、NCCL的在DL中的位置以及自身架构**

接下来，我们查看NCCL在深度学习堆栈中的位置。NCCL向下依赖于NV的GPU、CUDA,向上为框架提供通讯。它和CUDNN、CUBLAS一起提供一些深度学习的库。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhl3F6Q1HmagxxbJKk8GUgHsEicgWLSJusS59mnUT6v208waQTrtMariag/640?wx_fmt=png)

NCCL有五种集合通讯的方式，包括：All Reduce、AllGather、Broadcast、Reduce、ReduceScatter。除此之外还有send/receive的接口。



其中:

- All reduce=AllGather+ReduceScatter
- 而Broadcast和Reduce是互逆的



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhcVwzdicibucXEj4R2azUmMNfBThHURMsicNnyzkJZQMkqk9fPDd780YSQ/640?wx_fmt=png)



接下来，我们看NCCL的API，分为五大类/段。

- 前两类是 NCCL Communicater的创建、销毁、容错。
- 而上文提到的五个集合实现就在第三段。
- 五个接口可能不够，还提供点对点，send和receive。在第四段。
- NCCL提供合并接受和发送的方式，最后一段。它还可以合并其他集合通讯的操作。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRh7yzZ4Ry0G2BK7OyoriaicksvYcZrfRdpR3vDIxn9iaAYtCk80vvGONL3w/640?wx_fmt=png)



**四、MPI是什么**

在基于GPU的平台运行分布式作业，有以下几个因素/前提：

1. 硬件:计算服务器、网络。
2. 代码:并行性的划分和实现。

3.MPI，用于在多节点上启动多进程，消息传递。

4. SSH没密码访问。
5. 统一用户信息(UID和GID)。
6. 统一的文件系统。
7. 统一的软件栈。每个节点的NCCL和CUDA库的版本需要是一致的。
8. mpicc编译代码。
9. mpirun -np 16 -H node1:8,node2:8 ./application



分布式训练有两种运行方式：MPI和IP+Port



MPI全称为Message Passing Interface，是一个非常经典的并行的任务运行方式。过去几十年里HPC用得非常多。



MPI是经典的分布式进程关系和消息传递的协议。MPI有很多公司参与，有商业版和开源版MPI有6个基础函数，如下图所示：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s3ibmQQswsX3naPpFb5Wnx6sFuiahMHc8VAnibicltuMHE46OmZKlOE1euQ/640?wx_fmt=png)



MPI在多节点运行的时候，要配置节点间的无秘钥访问。MPI启动的时候，只需要在其中一台节点上启动。这个节点可以是计算节点，也可以是计算节点之外的其他节点。

MPI启动的时候，-H是指定计算节点的列表以及每个计算节点要运行进程的数量。





第二种方式的IP是计算节点的管理网即可。不需要是计算网的IB。端口是cli启动时任意指定的端口，未被占用即可。这种就比MPI方式简单很多。不需要设置SSH这种无密钥访问。SSH无秘钥访问结合容器有一些复杂度，不如第二种方式简便。 

第二种方式是需要分别登陆到每个节点上去执行cli。



\# 在节点1 NCCL_DEBUG-INFO python -m torch.distributed.launch --nproc_per_node=8 --nnodes=2 --node_rank=0 --master_addr="192.168.1.1" --master_port=12355 train.py

\##在节点2上 

NCCL_DEBUG-INFO python -m torch.distributed.launch --nproc_per_node=8 --nnodes-2node_rank=1 --master_addr="192.168.1.1" --master_port=12355 train.py



那么，我们常说的NCCL呢？

全称：NVIDIA Collective Communication Library (NCCL)。它是优化后的GPU在一个服务器上的内部通讯。而MPI负责跨服务器节点任务调度。NGC上，用mpi启动测试，底层都是调用NCCL。MPI只是做进程管理，启动的工作。只负责发起，通讯就不用了MPI负责了。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sVmqmTJHQ8cibGzpjiczGNe9Z0ICCn6WNdib4Nic7v7XNj4LMjT1nwKicgcg/640?wx_fmt=png)



NV_PEER_MEM是跨节点MPI所必需的，用于GDR。这个moduld在每个节点上都会加载。

在使用GDR时，要求GPU和网卡都在一个rc root下面去，如果离得太远，不仅性能不一定提升，还可能下降。DGX1和DGX A100都要求GPU和网卡在一个PCIe Switch下。



下面GDR性能提升是facebook测的，我们可以看到都有几倍的提升。https://github.com/Mellanox/nv_peer_memory

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4svZb9Ax2rZJ0zic6Dc8icLibpLMrlnYW46gSqYuJd1SRMnBRy62AicUwTQw/640?wx_fmt=png)



运行MPI，在裸金属/VM上运行是很方便的。在容器跑MPI有点复杂，因为需要保证容器间的ssh得走到容器里，而不是容器的主机上。

容器里运行MPI主要有两种方式。

- 由内而外:调用mpirun并在容器中运行application。
- 由外向内:在主机上调用mpirun，在容器中运行应用程序。



由于篇幅有限，而且很多客户直接在VM上运行MPI。因此在容器运行MPI的方式后文再讲。

IP+端口是简单，就是先运行容器，然后进入到容器里执行测试脚本。



**五、NCCL的启动过程与框架**

接下来，我们看NCCL的启动过程，有两种方式:

第一种是只在worker0上启动。nccl首先孵化出root线程，然后root线程把端口和IP给nccl，然后nccl通过broadcast广播给所有的ranks。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sUzdeJ0vC9ouFx2MIaQf2qeJDdS7ibxH9JMbvDzeiak8s29KBJXPC8e6A/640?wx_fmt=png)



第二种是在所有的并行worker上运行。在这种模式下，nccl自己初始化rand，然后将rand的ip和端口传给bootstrap root线程。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sEK52IjnHE4IBV6OYZA3h9n5zS1GrBWuWBM9mNnm6U246OMTs6y8vOg/640?wx_fmt=png)



然后，所有的rank相互传递自己的信息，以形成ring或者tree

架构。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sHO6EkAmKcZH9q3YKgVRZXia4MYLyr1J975dS6Y1dibQHVG0WpGc4NYBw/640?wx_fmt=png)





NCCL Bootstrap使用普通的TCP/IP socket来连接一个job中的不同rank。然后，它提供一个带外通道，根据需要在ranks之间交换信息。在NCCL communicator的整个生命周期内，Bootstrap操作都是可用的。它们主要用于初始化期间，同时也可以用于动态连接的send/recv操作。目前还没有加密，没有安全措施。使用NCCL_SOCKET_IFNAME来确保NCCL使用一个对并行作业私有的网络接口。



NCCL工作的四个步骤：

拓扑监测、Graph Search、Graph connect、CUDA kernel。



第一步，构建整个GPU集群的拓扑。

第二步，自动找到最佳的NCCL通讯架构，ring或者tree。

第三步,连接不同节点之间的GPU，使用PCI、NVLINK或GDR等。

在第四步中，优化缩减和拷贝，最小化SM使用。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRh7aewNj20GTRx4EsNpyK4GuFTVjYYziafDiaicjFzic7VGPNDKE40Fqjaxg/640?wx_fmt=png)



在第一步的拓扑发现中，NCCL会发现如下信息:

需要指出的是，互联方面有IB、nvlink，nvlink switch，还有一种nvlink可以接到CPU，例如Power9和后续的Grace CPU。



此外，虚拟机的配置也能看都能看链接，包括链接上的带宽信息。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhQwgdx0x29yEa36z8gCZ8doEGQMH6ianVZtPAicUzCiaZkh2psekpjv93w/640?wx_fmt=png)



第一步拓扑发现后，就要从拓扑生成graphs。NCCL默认会自己计算不同的模型，NCCL会根据硬件情况、网络情况、节点数量、估算延迟，选一个最快的运行。ring带宽高，tree延迟低。

Tree指的是节点之间，连接成一个树状的方式。Ring就是节点间串起来。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4svZo1dkCaXd7ANoCDEWiaGJibibostPXo3EFmUxpQQ989lknFUOwjwZtbQ/640?wx_fmt=png)



第二步完成后，都连好以后，要进行集合通讯，也就是graph connect，这些是通过GPU上的kernel。NCCL里都是采用写的方式，写的效率更高。

使用PCI、NVLINK或GDR等。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sq2Sd2BJnPGKjw0QLC2NgeGwK3fvxyGrx6zbficO4UdyLfH2uicAazCqg/640?wx_fmt=png)



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4srdbN26eeibIiagPiboOibrIPfMocgCD7fBOWiap61t9GmAO0ykZvVnBgQVg/640?wx_fmt=png)



有了GDR，跨节点的buffer就不需要再在host memory上开，直接用device上的就成。但还是需要一个CPU的进程启动rdma相关拷贝。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s4xoMicwxJv0LfbrCEfI8lSLvkykojZ6QmIQ5FK37THUUibFXvoEvhicQg/640?wx_fmt=png)



在第四步中，优化缩减和拷贝，最小化SM使用。这很好理解，不再赘述。



**六、DGX Superpod**

在NV GPU方面，DGX Superpod就是GPU集群。我们看集群的逻辑架构图。

整体上分为计算服务器和Admin管理服务器。在计算服务器我们看到OS向上是CUDA，然后是RoCE/IB，然后是RDMA。在网上就是NCCL/MPI。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s0p0icExPbhaYsTibs3IIFPbtCqxI1x4PMricnDBHzanoRY0rfoupqDwGQ/640?wx_fmt=png)

我们将上图继续分析，Admin管理服务器又分为：Provisioning Node、Login Node、Monitor Node、Load Balancing Node UFM Node等角色。虽然角色较多，但每个公司每个角色的数量都未必相同。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUn63lp6VzO4uaIl1PDBuRhTA2hs1zIicRFbRAkn68CeTS29ic2gibY3opxjoLbpoGA7JRrxDBxgMwug/640?wx_fmt=png)

如果从系统侧，分布式系统主要要求如下：

- SSH免密码、统一文件系统、统一用户信息(UID/GID)、统一软栈。
- MPI， NCCL， nv_peer_mem，SHARP（可选）
- Slurm，K8S调度器
- MPI + Containers

因为要执行多节点并行作业，所以强烈建议配置无密码访问。



**七、NCCL的三种架构**

上文提到NCCL的tree和ring架构，还有第三种：Collnet。

- Ring更容易高带宽，但延迟也高些。
- Tree更容易低延迟，但带宽不容易跑满。
- Collnet可以做in-network reductions，但需要专门的IB交换机。



ring比较容易实现full bandwith。为了让ring发挥好的性能，拓扑检测是很重的。需要做一条很好的链路。





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHkuV7piaXeicMM34dPQYibOFVn2A0SsR6hXJZorpege1xWrs5TLibLzZNdQ/640?wx_fmt=png)



接下来，我们查看节点间通讯双二叉树架构。

在这种架构中，每棵树有一半的数据经过，从而实现全带宽。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHqhK54dpOICQK7iaFSfxRiaL3ewZYMzQQQNRWyQMR3zpDtahEaMe70sNA/640?wx_fmt=png)

Collnet需要用到Sharp技术，相当于reduce在交换机内部就做完了。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHFXZBVoQuhN83uibibX0AbxVTIasqx1Mjq8MB5sogKfHzyZGYhfRT7awQ/640?wx_fmt=png)

我们对比tree和sharp。

Sharp的优势：发送一次数据，接收最终结果：没有中间结果；有效的双倍带宽—更少的跳数(每个交换机级别1跳)；更低的延迟

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s4CEvZrKJITC2DOuaLLlhu2AVlEYpaLYUibMVnLzInJ1HhHB2Uk9cCxw/640?wx_fmt=png)





**八、ring工作原理**

首先，我们看几类集合通讯的简单示意。

send receive是点对点，gather是多对一发送，scatter是一对多发送。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH6ADFVRkPWjQ9YNUicFruRY49j5ReBHBuuHiatKplu8bpgNJAuibH0gCzg/640?wx_fmt=png)





下面看一下ring算法。

在传统ring broadcast算法中，数据不分片，总延迟会和GPU数量有关，数量越多，延迟越大。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH0jLvG9hDYm5IEYM5eMbq3eALn8mtFzZb9XibCnONObOWVnGwOckYttg/640?wx_fmt=png)

可以针对Broadcast的优化，把数据拆成消息。如果数据量足够大，分的message足够多的情况下，基本可以忽略几点的个数。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHBguqNLsBqjveCW8Hy5qVaicfkR3dGSwEtQUcyU4FE2c3z5b4ZOMrpibg/640?wx_fmt=png)



**九、ALLreduce介绍**

Allreduce是最频繁使用NCCL的场景。深度学习，分布式训练都有很多人在用。

AllReduce目标是高效地将不同机器中的数据整合（reduce）之后再把结果分发给各个机器。在深度学习应用中，数据往往是一个向量或者矩阵，通常用的整合则有Sum（后文就是以求和为例）、Max、Min等。下图展示了AllReduce在有四台机器，每台机器有一个长度为四的向量时的输入和输出。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHEzWja9ibEzgFNS5LYdpH3p4Cciau7vWSiam13tnj86ibP9yTxxZtcqiaFtg/640?wx_fmt=png)

https://tech.preferred.jp/en/blog/technologies-behind-distributed-deep-learning-allreduce/



Allreduce这个场景依然需要把数据分成很多块，然后分别去处理。尽可能减少整个拷贝的overhead，带宽让大家同时用起来。例如一个有四个GPU的集群。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4spZzpPURXGnUqmhIc9iaT9Xf0RImZ5Q4ib5klo45YMMnIvAibEurnzU3aA/640?wx_fmt=png)

第一步，把自己的数据先拷贝到下一个GPU



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sKibbYyJ4jK1oZcZoBNnmnw06jt6BQw605HXOt1CHAoPhnMgzXbD58Fw/640?wx_fmt=png)

GPU将拿到的上一个GPU数据和自己的数据做一个累加，然后放到下一个GPU上，操作后，此时GPU2上有 GPU0和1reduce好的数据。同时GPU0也在拿GPU3上的数据做reduce，然后放到GPU1，所有GPU同步。





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sHN1W3cCnJicCfRaziaRqwRqnyJ1ibqMeucIHicmN1YP4GsFPIIuOwcOmAg/640?wx_fmt=png)



4个GPU，上面经过三次通讯，每个GPU已经拿到了所有的数据（前三个GPU求和后的数据）。例如GPU1已经有了0,2,3的求和结果。如果做scatter的话，利用0,2,3求和结果再加上本地的数据，如果做本地求和，scatter就完成了。但如果做allreduce的话，还不够，还需要继续做broadcast的操作。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sOe5AicyNnM1xw2Gy3QWxgwLLLqapqUFSqScp72oY2OwydY0mOKNpeqA/640?wx_fmt=png)



GPU1拿到的GPU0,GPU3,GPU2的求和结果，既要本地放一份，还要给下一个GPU2放一份。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sT1YBS63dIDxnicqjEjI5m0c9K0y1YKwo1X4uUV0tgt4AsKCkplYLmbw/640?wx_fmt=png)



GPU2把GPU1拿到的数据给GPU3发一份：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sNCf0ricXRqjeLBmkPIBZ1Mo1bogiaPELsYQ0GniakZu6NSuibC9QlAVv8Q/640?wx_fmt=png)

GPU3再传给GPU0传一份

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4s3eOjrliaIERibl8ImjOHB0ib0ePfbOTibH4WKpDibJamCPsDLLfZH9R0Giaw/640?wx_fmt=png)

接下来，针对chunk2做操作。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sLTk60Xnb1pdfdPYL8YKserDAgdaG4icB4icDCxZ3m1ZxiavgW7K23acPw/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4seHLejlbzV1vTl41uEZlZJuF2XXjN5uIRR6H5icyTHJ9AI01StFcpiadg/640?wx_fmt=png)

最终完成Allreduce过程：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nULvQVPF4kv6lZzjBvUvz4sl4wmLKWmAb9fUahJkCFZPV0Myp5k3HV14CS6m3RNVOsK7gdBV0Qialg/640?wx_fmt=png)

整个过程完成。先reduce，再scatter，再broadcast。



Allreduce中各步骤时间统计如下：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH6wBSgkvlwR9rYZMicia13VXLFuEvoQgbEPIFQ76GmT0LjAxxuIFOpAFA/640?wx_fmt=png)



**十、NVlInk的优势**

我们了解到了ring网络的诸多弊端，也就会理解DGX用NVlink的好处。通过NVlink通过数据做传输。



我们先看单节点NVLINK GPU系统。这是以V100举例。我们看到有两个NUMA节点，一共8个GPU。

每个GPU有6个NVLinks连接。总单向带宽是150GB/s。



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcH8p6ibOWHvuPoZ2f3dsiaMombolV2ghbiaeUeGKsibV4IlQxcxV4RDHsSFw/640?wx_fmt=png)





在多GPU通讯时，比较好的方法是节点内的GPU用NVLINK，节点间用RDMA。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHI2ILofaFtLch4XQLNPI4IM5IrrGk99riaYia3N7faYR1zMAqehwpTRLw/640?wx_fmt=png)









后面H100还会有NVlink switch连接方式，AlltoAll会成为一个新的方向。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUKWwMLsxDY8vSFcXmjnvcHllicI2zzH3icCO5lThF7DNCSQmWzBXh5PsvT535NYE0icYFsFs4WHDbqA/640?wx_fmt=png)



总结:NCCL默认会自己计算不同的模型，NCCL会根据硬件情况、网络情况、节点数量、估算延迟，选一个最快的运行。ring带宽高，tree延迟低。



前两篇关于NCCL的相关协议已经介绍了不少，我们先总结一下，NCCL的“3头15臂”（NCCL的三个层面、15种实现）。三头是：NCCL的通讯功能、NCCL的算法、NCCL的协议。其中NCCL的通讯功能是直接面向业务的，比如AllReduce，直接用在分布式训练中，和业务对接。



**十一、NCCL的3头15臂**

**NCCL的通讯功能：**

1. 集合通讯： "Broadcast", "Reduce", "AllGather", "ReduceScatter", "AllReduce"
2. 点对点通讯“send/recv”, "scatter", "gather", "all-to-all"



**NCCL 算法方面:**Ring, Tree, CollNet

**NCCL协议:** LL, LL128, Simple



在3头15臂中，NCCL算法和NCCL协议“这两个头”很多时候NCCL自动选择就可以。但第一个NCCL的通讯功能是比较关键的，需要深入理解、做出正确选择和配置。



我们再复习一下NCCL通讯功能中的集合通讯。

在NCCL中我们经常会说一下概念：rank。rank是NCCL里的一个job中的一个进程，而一个进程一般运行在一个GPU上，所以下图所示的rank数量，和参与到job中的GPU数量是一致的。



Reduce：一个rank接受跨rank的输入值的缩减。比如四个rank上的四个数值求和后的结果，发给root rank2。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1S97tqMTeZXVpfhn42uYjK1mpBCYn7ShfLuicVBSCcia1Xp0AXsAmSGqA/640?wx_fmt=png)



Broadcast：所有rank接受从一个root rank发过来的数据。





![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1L5K9YIdSQTBMmTIzcAw63yf533YJBpvxt7s7JS7yn3RsNeXLUcl3Og/640?wx_fmt=png)





Allreduce：每个rank都接受跨rank输入值的减少。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1t2ia9oSdYO8tguhOsKgjibhuI6r7YF86bUPuDEkMia6ojl6XtZs1zEdTA/640?wx_fmt=png)





AllGather：每个rank按照rank的顺序接收来自所有rank的数据的聚合。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1cJUHRLj9K9kibgyibMd3ykibxDlYHQ7RwUNxlClILAvn8CL3hTC2SnsSg/640?wx_fmt=png)





ReduceScatter：输入值跨rank缩减，每个rank收到缩减结果的一部分数据。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1CyKCvaEKoVmxG950rUZ9vq8prlp6RiatssG1bEmuI08FLVPUcljSB4w/640?wx_fmt=png)





接下来，我们再看NCCL通讯的几种点对点通讯：

send receive是一对一收发，gather是多对一发送，scatter是一对多发送。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1o6J3Azm063bFibrCwWh7riaOsaHq5kwjplxS56gueDX1DcSHf0XRVL2g/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1xEveo90ofk1Xy1LiaF9hToLENTG0bLfbjJOxx24icv3lbNico401fE1FA/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1zicyzrxxECD0OFuxuZA4vH18SPbEfFenwMEU10nwCkw96FibIFV4VbibA/640?wx_fmt=png)

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1aH2cYLoicMNwT62yBYMKx3GGDyModcFTXy758mUYBnN2sKV9IgFw7Kw/640?wx_fmt=png)





接下来，我们看NCCL的算法。

**十二、NCCL的算法**

NCCL的算法分的3臂为Ring、Tree、CollNet。



在ring的配置中，无论多少个服务器节点，都是一个环所有GPU串起来，形成一个扁平的2D ring，不会出现节点内部一个ring，外部一个ring。只能是一个环。



在节点间互联的时候，还有一个channel的概念。channle的数量是网卡数量的二倍。

在nvlink的连接数，channel的数量，就是nvlink接口的数量。



**节点内：**

对于基于NVLink的系统，总是创建双通道，以使NVLink带宽饱和。

例如。DGX-1V，6*2=12。

例子。DGX A100，12*2=24。



基于PCIe的系统，总是创建双通道。所以，总是2。



**节点间：**

根据网卡情况，总是创建双通道。

即2*网卡的数量。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1CEZSMgQg7Fs0QG12WVktAnbeiaia5JzgFt11CRyht5T6pdLnfjkklG1A/640?wx_fmt=png)



接下来，我们看NCCL算法中的tree。

在使用tree时，总是成对使用，即tree pair。

下图tree pair的目的，是保证一个节点的收发是均衡的。我们看到两棵树的节点数刚好差1，偏移了一位。这样除了根节点0和31，其他的都是两收两发，0和31是单收单发。这样主要是为了负载的均衡性。



即使每个节点有多个GPU，节点间的网络都是固定的，只是某个节点内部的入口出口未必相同。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1mgK7mic524dicCmenUavJcMkPXIPu2IoWTD1fCVZEWmJkp8uO3pMGN8A/640?wx_fmt=png)





在NCCL tree中，节点内，它是一个链。节点间，它是一棵树。

节点内还原数据流示例（4台DGX A100，使用NIC0，每个数字代表一个GPU）。

  节点0：7->6->5->4->3->2->1->0

  node1: 15->14->13->12->11->10->9->8

  node2: 23->22->21->20->19->18->17->16

  node3: 31->30->29->28->27->26->25->24



节点间的通信：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1rBHtISYeomRb2Tm75XYBiccpNSXItEBGo0eZhVJql76pxGibXKAiaWEEQ/640?wx_fmt=png)



对于节点间，NCCL使用1或2个GPU来发送或接收数据。

NCCL tree细分有三种类型：

- Basic Tree。所有的网卡流量都流向/流向同一个GPU

- Balanced Tree。在两个GPU之间分散网卡流量（树的父代+第一个GPU上的一个子代，第二个GPU上的第二个子代）

- Split Tree。在两个GPU之间分散网卡流量（树父在第一个GPU上，树子在第二个GPU上）。

  ![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1cwXwobycd1KMZRAwWsS22UbouB2h260IL0ib7CiaxMs4BrPoGicaqnhww/640?wx_fmt=png)

tree的三种方式中，balanced tree是最主流的，默认初始化就是这种模式，只有当GPU很少的时候用basic tree。



NCCL的第三种算法，CollNet依赖于交换机。

基于网络内树的聚合机制。

CollNet是NCCL中的一种新算法，允许多个节点上的GPU进行网内还原。

SHARP是用NCCL验证的。

NCCL_COLLNET_ENABLE=1，NCCL将检测加载的网络插件（libnccl-net.so）并使用其中实现的网内还原功能。







![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1HqiaGB5wDLwHQiaXj8OpA2zbFoJklOvYNkSUCvSHg12mlf2nomib4BurQ/640?wx_fmt=png)

这三种模式，nncl自己去选择。



**十三、NCCL协议**

最后我们看NCCL 3头15臂的最后一个头：NCCL协议。

- LL(low latency)依赖于8字节的存储是原子的(有4B的data/4B的flag)，使得LL的最大带宽为峰值的50%，因为50%的有效载荷是标志。
- LL128依赖于128字节的存储被依次看到（有120B data /8Bflag）。LL128可以达到95%的峰值带宽。
- Simple：第三种是没有flag。

\# 标志只是用来表示某个数据片的尾部已经交付，并准备在流水线的下一阶段被消耗。

\# LL128的功能和速度实际上取决于许多因素，如我们在GPU之间的通信方式（PCI或NVLink）以及缓冲区的位置（GPU内存或系统内存）。 



算法的8种选择 x 协议 {Ring,Tree,CollNet} x {LL,LL128,Simple}（CollNet不支持LL128）。

根据信道数量和速度为每种算法建立延迟和带宽模型



根据不同的链路类型带宽和nNodes, nRanks, nsteps计算出总线带宽busBw。



- 对于大的信息量来说，环是带宽最优的，但小的信息则被延迟所支配，而且随着规模的扩大，延迟会线性增加。
- 当规模扩大时，树对延迟更有利。但是对于非常大的消息，由于SM的开销，Trees不能达到峰值BW，所以使用Rings。





**十四、NCCL执行与日志查看**

在执行mpirun的时候，

\#mpirun -bind-to none -H node1:1,node2:1 -x CUDA_VISIBLE_DEVICES=** -x LD_LIBRARY_PATH -x NCCL_IB_HCA=* -x NCCL_DEBUG=INFO -mca btl_openib_allow_ib true ~/nccl-tests/build/all_reduce_perf -b 8 -e 128M -f2 –g8 



通过NCCL_IB_HCA，选择指定的IB卡进行通讯。-b 指的是message大小，从8byte到-128M，每次乘以二增加。-g是GPU的数量。可以一个进程8个GPU，也可以9个GPU，每次一个进程。



每个节点的每个GPU都会输出bootstrap。可以通过NCCL_SOCKET_IFNAME指定以太网卡做初始化。



我们可以查看NCCL test log：

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1aZXyCDrTtfTPEx9guGZCR60K1mTiciceVrJHUY4Ro9rEdts8IaLScvUg/640?wx_fmt=png)



channel的信息就是生成的ring的拓扑。

NCCL只会输出前20个rank的信息



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1ickzDBib5MGmPic4ibr205tSTHWxJrZNK2T8uVRvNeLdmHoxHM85Vibbacw/640?wx_fmt=png)

四个节点，每个节点上8张网卡，每张网卡形成两个tree，一共16个tree。方括号里是tree的编号，0-15。

NCCL INFO Trees [0] 19/-1/-1->18->17 [1] 19/-1/-1->18->16 [2] 19/26/-1->18->2 [3] 20/11/-1->18->19 [4] 19/-1/-1->18->17 [5] 19/-1/-1->18->17 [6] 19/-1/-1->18->17 [7] 19/-1/-1->18->17 [8] 19/-1/-1->18->17 [9] 19/-1/-1->18->16 [10] 19/-1/-1->18->11 [11] 20/-1/-1->18->19 [12] 19/-1/-1->18->17 [13] 19/-1/-1->18->17 [14] 19/-1/-1->18->17 [15] 19/-1/-1->18->17



下图链接是一个可视化脚本工具。8连到17，24连到16，16连到0。这就是一个splitted tree。虽然16,17都做通讯，但16和17GPU都是连接到同一张网卡。比如在DGX上的一张网卡，和16 17对同一张网卡的亲和力是相同的，同一张网卡出去的。



https://github.com/ROCmSoftwarePlatform/rccl/tree/develop/tools/TopoVisual



![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1F3jOiblvVJQavzN0p1wvco4iaQy88xb6djFia8bicaP7DF1w3KMJCJuWeQ/640?wx_fmt=png)





P2P transport是节点内的。pix表示连接到同一个PCIe switch上。pxb表示连接接到多个pcie swicth上或者NVlink

如果是PHB， node， sys，是PCIe机型  跨了不同GPU  numa node，需要借助share memory。



执行CLI的时候，NCCL_COLLNET_ENABLE表示NCCL启用了Collnet



下面日志显示使用了sharp。每个节点的哪个GPU，从哪个网卡出去。

每张网卡形成三个channel，但log中只显示一个。

例如每个网卡的GPU0通过MLX 5_0出去



NODE3:47239:47281 [0] NCCL INFO Sharp rank 3/4initialized on mlx5_0:1

NODE0:73825:73875 [7] NCCL INFO CollNet 07 : 7[send] via COLLNET/SHARP/7/GDRDMA

NODE1:64040:64089 [7] NCCL INFO CollNet 07 : 15[send] via COLLNET/SHARP/7/GDRDMA





没有SHARP时，Ring和Tree的通道是2 * NIC数量。



有SHARP时，Ring和Tree以及CollNet的通道是3 * NIC数量。







in place表示send和recive buffer用的同一个buffer，out-of-place 表示收发用的不同buffer。区别不是很大。



algbw是算法带宽，并不能表示是否完全体现硬件性能。busbw更体现性能。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1yu7iaqfcu25hRI7DC1Z4DFOqHdF6KIAP4OREC5BWp7h3Hb1LB9Gz3gA/640?wx_fmt=png)





**十五、NCCL中的两个xml**

第一个xml

NCCL_GRAPH_DUMP_FILE=graph.xml

NCCL_GRAPH_FILE=graph.xml

这将dump ring、tree、CollNet的信息。

id="0 "是Ring的信息。

in graph id="1" 是Tree的信息。

in graph id="2" 是CollNet的信息。

在每个通道中，它是数据流序列。

如果在多节点中运行，它从网卡输入开始，然后是GPU，然后是网卡输出。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1qibWibibFWCQ8qoDufJ6qtwpNxVPIq0V0qAR5VP60SLKT19CMgNUzgG4w/640?wx_fmt=png)

第二个xml

NCCL_TOPO_DUMP_FILE=topo.xml

转储服务器拓扑结构



这两个文件都可以自行修改，然后强制加载使用。但强烈不建议这样操作。绝大多数情况，这两个文件只是用于查阅配置。



**十六、NCCL中的环境变量**

**NCCL_SOCKET_IFNAME**

**指定使用哪个IP接口进行通信。**



**NCCL_IB_HCA**

指定使用哪些RDMA接口进行通信。例子。

mlx5 : 使用所有以mlx5开头的卡的所有端口。

mlx5_0:1,mlx5_1:1 : 使用mlx5_0和mlx5_1卡的端口1。

^mlx5_1:2 : 不使用卡mlx5_1的端口2。



**
**

**NCCL_CROSS_NIC**

控制NCCL是否应允许环/树使用不同的网卡，使节点间通信使用不同节点上的不同网卡。取决于网络拓扑结构。

0：始终使用相同的 NIC  

1: 不尝试使用相同的 NIC 

2: 尝试使用相同的NIC，仍然允许不同的NIC。



**
**

**NCCL_IB_GID_INDEX**

**定义了RoCE模式下使用的GID。**

**
**

**NCCL_IB_TC**

定义了InfiniBand流量类别字段。





**NCCL_COLLNET_ENABLE**

**启用CollNet插件的使用。**

**
**

**NCCL_P2P_LEVEL**

LOC或0 : 从不使用P2P（总是禁用）。

NVL : 当GPU通过NVLink连接时使用P2P。

PIX或1 : 当GPU在同一个PCI交换机上时使用P2P。

PXB或2 : 当GPU通过PCI交换机连接时，使用P2P（可能是多跳）。

PHB或3，或4：当GPU在同一个NUMA节点上时，使用P2P。流量将通过CPU。

SYS或5 : 在NUMA节点之间使用P2P，可能会跨越SMP互连（例如QPI/UPI）。



**
**

**NCCL_NET_GDR_LEVEL**

0 : 不使用GPU Direct RDMA。(总是禁用)

1 : 当GPU和NIC在同一个PCI交换机上时使用GDR。

2 : 当GPU和NIC通过PCI交换机连接时使用GDR 

3 : 当GPU和NIC在同一个PCI根复合体上时，使用GDR，可能会通过CPU。

4 : 只要GPU和NIC在同一个NUMA节点内，甚至跨PCI根复合体使用GDR。

5 : 使用GPU Direct RDMA，甚至跨越NUMA节点之间的SMP互连（例如QPI/UPI）。



**
**

**NCCL_MAX_NCHANNELS**

限制了NCCL可以使用的通道数量。减少通道的数量也减少了用于通信的CUDA块的数量，因此对GPU计算资源的影响。



**NCCL_DEBUG**

VERSION, WARN，INFO - 打印调试信息





**十七、NCCL的trouble shooting**

 https://docs.nvidia.com/deeplearning/sdk/nccl-developer-guide/docs/troubleshooting.html#



将NCCL_DEBUG设置为 "WARN "会使NCCL在返回错误之前打印一个明确的警告信息。



ncclUnhandledCudaError和ncclSystemError表示对一个外部库的调用失败。

ncclInvalidArgument和ncclInvalidUsage表示在使用NCCL的应用程序中有一个编程错误。

![img](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXOKibrtfyGNS8O1tW0iarVN1H3qKSjXGR9vicWyvxUNqiaiaeDueia8fD6QdicynZt5tick0pzKcEFuvUgjw/640?wx_fmt=png)





MPI遇到问题，首先确保节点内的GPU-GPU工作正常。

cd/usr/local/cuda/samples/1_Utilities/p2pBandwidthLatencyTest

sudomake

./p2pBandwidthLatencyTest



确保GDR对Mellanox IB/RoCE卡工作正常。

lsmod | grep nv_peer_mem



**PCI访问控制服务(ACS)**

   IO虚拟化（也被称为VT-d或IOMMU）可以通过将所有的PCI点对点流量重定向到CPU根复合物来干扰GPU Direct，导致性能大幅下降甚至挂起。当遇到性能问题时，请尝试禁用ACS。



NCCL依靠/sys来发现GPU的PCI拓扑结构、速度、CPU亲和力和网卡。

当在虚拟机或容器内运行时，确保/sys被正确安装。让/sys暴露一个虚拟的PCI拓扑结构会导致次优性能。





NCCL会自动检测哪些网络接口用于节点间的通信。

如果某些接口处于启动状态，但是不能在节点之间进行通信，NCCL可能会尝试使用它们，因此在初始化功能中失败，甚至挂掉。



开机接口通常使用IB或RoCE接口进行通信，当它们不能相互通信时，使用NCCL_SOCKET_IFNAME来指定使用哪个接口进行通信。



例如，在本地实验室的 DGX A100 上。

NCCL_SOCKET_IFNAME=enp226s0





NCCL通常会检测与GPU最亲近的网卡进行通信。但是在一些极端的调度情况下，会造成一些问题，比如说。

调度器启动一个1GPU*2节点的作业，GPU0在服务器1，而GPU7在服务器2。由于NCCL使用最亲和的网卡，所以服务器1的GPU0将使用mlx5_0，而服务器2的GPU7将使用mlx5_7。

Infiniband。

如果没有给Mellanox网卡设置任何IPoIB，就不会有任何问题。

如果设置了IPoIB，在大多数情况下，它将在不同的IP段中，如果启动接口使用这个接口，它将下降，需要将NCCL_SOCKET_IFNAME设置为一个可以相互通信的以太网接口。

ROCE。

IP必须在不同的IP段或vlans中，如果它们不能相互通信，我们需要使用NCCL_IB_HCA =mlx5_0(或mlx5_1)来强制两个服务器使用mlx5_0或mlx5_1。