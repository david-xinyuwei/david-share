# GPU Benchmarking
微调和运行大型语言模型（LLM）需要花费很多成本，主要是因为要用到大量的GPU。选择合适的GPU对节省时间和成本非常重要。A100和H100这样的高端GPU在分布式训练时速度很快，消费级的RTX 4090在微调和推理方面也是一个很划算的选择。


对比一下RTX 4090和H100的规格，会发现RTX 4090的时钟速度更高、CUDA核心更多，张量核心也稍微多一些。然而，H100的HBM内存带宽比RTX 4090的GDDR6x内存高很多。如果增加批处理大小，内存容量更高、内存带宽更大的GPU效率会大大提高。

对于参数超过30B的大型语言模型，即使模型经过量化，RTX 4090的内存也不够用，无法在标准超参数下进行微调和推理。

在推理方面,对于H100和A100如果资源有剩余，可以考虑配置MIG，这样其推理性价比就可以提升。

18 GPUs benchmarked: H100 PCI-E, A100 SXM, A100 PCI-E, RTX 4090, L40S, RTX 4090 community cloud, RTX 6000 Ada, L40, RTX A6000, A40, RTX A5000, RTX 3090, RTX 4000 Ada, RTX A4500, L4 RunPod, L4 Colab, RTX A4000, RTX 2000 Ada, RTX 4070 Ti, and RTX 4080.

以Llama3为例：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5rXXzfnvkwAnfHAt6PjLEyrp9nFL5vJKdd1zkqDHKXH88tib9K63ibSk2Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5r4dJWRibazeFZtib79mvLiaoU68Xwc7HG5prHkOfgS1rJoZpXOrpwCgmVg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5rccfibuxYmPHJToWiaPVgAnKmFubxjKtQHGKeibY8pX8zWjTQFzYGcPzGQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5rIq2jg9oiaMHa9Lia5Utv4sc5EU3uibq0TOQFAu0PI8Ue8f0k3dMNwntpw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5r6SDZgVtZbCG6CiaUnucOMvEBrJbAsnQPPzIDST6M9R41RP9UUUicbibGg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5rtTHR9M9uAFks5Eyq17CjyDianYJf9ExpgB1wVQon8zhUE86TuA9jexQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5rNJL9bdNrWQ2yvnibIhibUY5UBefbrhjMsRzzXo0t4ibCJqbBUZrXpyQSg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVJ73CJx6thdVkhrYomJm5rbVFL9XmvfET9vqq6CIawlAwFBBq9RiczTIlJ8kSgEGzrRbv5gIhLsEQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)




参考链接：https://kaitchup.substack.com/p/gpu-benchmarking-what-is-the-best