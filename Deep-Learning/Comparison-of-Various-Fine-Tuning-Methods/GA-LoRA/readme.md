# GA-LoRA-implements-full-fine-tuning-and-addresses-overfitting

GaLore（Gradient Low-Rank）支持全量微调（Full Fine-tuning）。全量微调指的是在微调过程中调整模型所有参数，而不是只调整模型的一小部分参数。这与参数效率微调（Parameter-Efficient Fine-Tuning, PEFT）方法如LoRA（低秩适应）相对，后者只调整或优化模型参数的一个子集。 

GaLore通过其创新的梯度低秩投影技术，使得即使是在内存限制较大的情况下，也能够进行大型模型的全量微调。它识别出训练过程中梯度的低秩结构，并利用这一特性压缩梯度，从而大幅降低了存储这些梯度所需的内存量。这意味着即便是对那些拥有大量参数的庞大模型，GaLore也能在普通消费级硬件上实现全量微调，而不需要牺牲模型性能或显著增加所需的计算资源。

GaLore提供了一种高效的方式来在资源有限的设置下实现大型语言模型的全量微调，打破了传统上对高端硬件的依赖。在实践中，GaLore 可以在消费级硬件上实现 7B LLM 的预训练和全面微调：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKcOCQgbecLaUwicOjXicJPWzZnlJ0B2MvaJ83J8iaID7iclibMISIRNeISKg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

我们看一下性能对比：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKwz1guKATOUib2rJ114icJYIBLtzK9CUBULRSgIMdp47GURH0B9a4iaWhg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

GaLore 引入了额外的超参数：

- Rank  r：与 LoRA 一样，等级越高，内存消耗越大，但也能提高模型的性能。如上图所示，等级为 1,024 的结果明显优于等级为 512 的结果。还要注意的是，GaLore 的秩通常要高于 LoRA 的秩。看来，128 级是最低限度。
- 比例因子 Scale factor α：我们在 LoRA 中还发现了另一个调整低等级更新强度的因子。根据作者的说法，GaLore 对 α 的变化非常稳健。0.2 到 2.0 之间的值似乎效果不错。
- 子空间变化频率 Frequency of subspace change T：虽然 T 的理想频率因训练长度和任务复杂程度而异，但将 T 设置在 50 到 1000 之间对结果的影响最小。



我进行了五次实验，分别进行介绍。

**实验一:** 

**BS=128; learningrate=1e-5；**

**optim：galore_adamw_8bit_layerwise\**，rank=512\****

通过GA-LoRA,用单H100卡做Mistral-7B做全量微调（trainable parameters = 7,241,732,096）。因为显存够大，可以把BS从8增加到128：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVK6nTib0DBbecicLia529j7hxFIaciaqDzFjbXA8h5b8dcR25GT2Kd1ICaTA/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

ds = load_dataset("timdettmers/openassistant-guanaco")

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKKDPJiaQicKH5It9EiboXtAB5DWgwA4R14Qoyur8rLjawAHk3KZ58OibMPw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

查看训练过程中H100的资源开销（如果BS=8，那么显存占用量在23G左右。）：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKicCibC0EJTsYSyauzvIWy6PUXMpFNLFlm7rMp7bGQ7I8q4mnpyNtd80w/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKuus30PiaOVDticlEeFo7uPXGfHw17W9j6ywvLhZToOtgQiakfdD4FkzOw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

从损失函数看，训练效果显然不理想。

**实验二:** 

**BS=64； \**learningrate\**=2e-5；**

**optim：galore_adamw_8bit_layerwise\**，rank=512\****

将学习率增加一倍，将BS减少一半：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKic9ezNVcbayBiazsy7fmZdkdLMADYlb6GlkXI6u8yKX4Uf2CUqicBwuhA/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVK8ibY7S3R9COHhOIIOtic0UfGZmRpk7sc7hyrdzQOuVh6rxibotETHTyMw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKX29mtlRIPkUT8yLOjxjy6cQQRvC4BvqPsAEydSiasyhVrXuZT92Yia3A/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

效果好点，但依然不理想.

**实验三:** 

**BS=128；learningrate=1e-5；**

**optim：galore_adamw_8bit；rank=512**

当我们使用“galore_adamw_8bit_layerwise”配置进行训练时，模型似乎没有学到太多东西，因为训练损失没有显著减少，同时验证损失也没有任何改变。

实际上，对于优化器“optim”，我们提供了几种针对 AdamW 的“丰富”选项：

1. **galore_adamw**：这是标准的 GaLore，带有 float32 参数。尽管如此，它对消费级硬件而言仍然消耗过多内存。

2. **galore_adamw_8bit（BS=8）**：此版本将优化器的参数量化为 8 位。为了微调 Mistral 7B 模型，此配置需要 35 GB 的 GPU RAM，如果使用较低的等级 128，则需要大约 30 GB。

3. **galore_adamw_8bit_layerwise（BS=8）**：与 galore_adamw_8bit 相同，但进行了分层更新。此配置消耗 22.5 GB 内存，能够在 24 GB 的消费级 GPU 上运行。

   至于超参数“optim_args”，上面实验中，我们选择的rank为 512。GaLore 的作者指出，对于 7B 模型，1,024 的等级会产生更好的结果，但这样的配置无法在不减少批量大小的情况下适应 24 GB 的 GPU RAM。值得注意的是，GaLore 当前的实现不支持梯度累积步骤。

   我将“update_proj_gap”设置为 200。我没有尝试其他值；作者提到，50 到 1,000 之间的任何值都应该可以正常工作。我将 alpha 设置为 1.8，尽管 0.25 到 2 之间的其他值似乎也有效，这表明 GaLore 对于超参数的更改具有相当的鲁棒性。

   最后，类似于 LoRA，我们需要针对应用 GaLore 的模块进行设置。这是通过“optim_target_modules”实现的。我们的目标是尽可能针对大多数模块来减少内存消耗。对于像 Mistral 7B 这样的模型，这意味着目标是所有自注意力和 MLP 模块。然而，GaLore 只能针对 PyTorch 的 nn.Linear 层。对于 Mistral 7B，我们可以通过设置正则表达式 [r".*attn.*", r".*mlp.*"] 来匹配兼容层。对于所有使用 Llama 2 架构的模型，您可以进行相同的设置。

当然，换了优化器以后，GPU显存利用率比相同配置下（BS=128）比换之前要高些。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODW2BibS0jEEuOuw1xm0pZ4EH4d572ScuXvnfaxia4mAN95hpKJAdGcNyw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODd4BtwnZQ3cIlicqaI6nnM36r8FUhwHOUlt3yXG1IHK382MTCh7209lQ/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

我们看到换了优化器以后，训练的效果比上次好太多了。这个结果是理想的。![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODEvAprYC3GDe1rFK91cb9HtF94rrzesJZub0gwEz6bfIOx0d3DNWPRw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**实验四:** 

**BS=128；learningrate=1e-5；**

**optim：galore_adamw_8bit，rank=1024**

接下来，在保持BS=128和优化器为galore_adamw_8bit的前提下，我把rank从512提升到1024.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODB3HGFPZcWR12jjWKiaolqDvuT8weWZicUxow2AOhAUCjwUr3c2t8yU1w/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

训练中，GPU的显存利用率飙升到87GB，但没有OOM，充分体现大显存的好处。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODNfN4zibDVvMJIUHib1vPUHpFN9lib6DsyRRVUr6LzZ3Bmvop7MsUCPjfQ/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

查看训练结果，比实验三的结果更理想，损失函数在step50的时候直接降到：0.825400而且在Step100时降低到0.71。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODkYRCfA3jyHotAtpa2pmibcquFauYqJlwotvIzOl2ib6ank3AmNd51wJw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)



上图展示随着训练的过程，损失函数正常下降，但Validation Loss却提升了，说明出现过拟合。因此进行下一个实验。



**实验五:** 

**针对实验四出现的过拟合情况，降低学习率，增加 \**weight_decay和\*\*warmup_ratio\*\**\*
**

**BS=128；learningrate=1e-6；**

**op****tim：galore_adamw，r****ank=1024**

 **weight_decay=0.05, warmup_ratio=0.2**

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXYro4VNFxnL6o7LHiaDJL6QB6YGDsBAjVGqJ6gYHPtL1RX0pImFaPxhTLkIQHdEggnF0Ngq6UicbpA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

查看训练效果，过拟合问题解决：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXYro4VNFxnL6o7LHiaDJL6QG3Btgib4WkPCmPGwibyKCBkwGpdSDU8m1ibyBJgOwJBOkibDIn6tGAYK7Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)