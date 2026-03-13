# LLM Fine-Tuning and Alignment: A Complete Guide

本文是一份 LLM 微调与对齐的完整技术指南，涵盖从 SFT 超参调优、各种微调方法对比（SFT/ReFT/RLHF/DPO/PPO/RLAIF/TPO）、LoRA/QLoRA/GaLore 机制、DPO 理论与实践、PPO 架构详解，到大模型 DPO 分布式训练（DeepSpeed ZeRO-3 / FSDP）的全流程。

> *This guide consolidates content from multiple previously separate articles into a single coherent resource.*

## Running on Azure

All experiments in this project were conducted on **Azure GPU VMs**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | DeepSpeed, FSDP, LoRA/PEFT |

---


# Part 1: SFT 超参调优最佳实践

> *原文来自 LLM-Fine-Tuning-Best-Practices*


LLM微调的超参大致有如下内容,在本文中，我们针对这些参数进行解释。

```
training_arguments = TrainingArguments(
        output_dir="./results",
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=2,
        optim="adamw_8bit",
        logging_steps=50,
        learning_rate=1e-4,
        evaluation_strategy="steps",
        do_eval=True,
        eval_steps=50,
        save_steps=100,
        fp16= not torch.cuda.is_bf16_supported(),
        bf16= torch.cuda.is_bf16_supported(),
        num_train_epochs=3,
        weight_decay=0.0,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        gradient_checkpointing=True,
）
```

**一、批大小batch size**

我们来讨论批大小的设置。在模型训练过程中，批大小指的是每一次训练步骤中所用的样本数目。我们会将数据集分割成多个批次，然后在每完成一个批次的处理——亦即完成一步训练之后——更新一次模型的权重。如何选择合适的批大小是模型训练过程中的一个关键考量，它直接关系到模型训练的收敛速度以及训练质量。

一般来说，较小的批大小能够带来规则化的效果，降低模型对新数据的泛化误差，这样可以使得模型更加稳定。但这同时可能会减慢训练速度，并增加模型陷入局部最小值的风险。而较大的批大小能够利用硬件优化——比如GPU的并行处理能力——来加快训练的速度，但这样做需要消耗更多的内存，并且可能会使得梯度的估算不够精确。在这里，“梯度”可以被视作一个指示箭头，它指向模型错误增长最快的方向。在模型训练的过程中，我们的目标是尽量减少错误。为了做到这一点，我们需要检查梯度来确定哪个方向是我们不希望模型去的，然后调整模型使其朝着相反方向移动，以此减少错误。

实际操作时，你可以不断增加批大小，直至出现GPU内存溢出的错误，这表示GPU已无法处理更大的批次。这样，我们就可以找到适合我们硬件的最大批大小。

在TrainingArguments中，你可以使用以下参数设置批大小：

```
[...]
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
[...]

```

第一个控制训练的批量大小，第二个控制评估的批量大小。对于评估，它只影响评估速度。通常，我们会为评估和训练的批次大小设置相同的值。GPU 针对特定的批次大小进行了优化。例如，避免使用奇数，将批量大小设置为 9或 13 可能会导致微调速度比批量大小为 8 时慢。

用批量大小 1、2、4 和 8 对 TinyLlama 进行了 1 个 epoch 的训练。


首先展示学习曲线，然后讨论结果。

对于批量大小为 1 的情况：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXbkq6buj5ThXTAegKtDOcbC6TK0DIiaK8y5SpOcxviaHyPAM1wJJwzV0qLAM8rfBtmt0ztcuH5m5nw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)对于批量大小为 2 的情况：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXbkq6buj5ThXTAegKtDOcbkVuaSWk3NXTmjK3559BBfTp31fIMY3H6XabjdNTCUqy2o4UicZkjSrw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)对于批量大小为 4 的情况：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXbkq6buj5ThXTAegKtDOcbwFqlM10maysPA4ySFnE27yXZzmbiaQhmPb1T704bm3ljraxblEsl0ZA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)对于批量大小为 8 的情况：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXbkq6buj5ThXTAegKtDOcbibmM6YO2yRByoGt2LLb1p6Gdfk3KH0Nf0XXUDVAQ9wic4X7QHJgmn3LQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

比较：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXbkq6buj5ThXTAegKtDOcbwPOZ58wOd20QGkG3cR0mj46iciaQMlDOTHquywjAfeIicEmr1ZEftXzFw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



批量大小对模型训练质量和效率有显著影响。较大的批量可以提升模型性能并加快训练过程，但同时也要考虑到整体训练时间，包括执行验证步骤所需的额外时间。使用小批量时，应相应减少验证步骤的频率，以减少总训练时间。


实验表明，即使在批量大小为32的情况下，也能获得较好的损失结果。但是，这会增加内存的使用量，在一些情况下，如16GB内存的GPU上，如果不采用如梯度累积等技术，实现这样的批量大小是不现实的。因此，而不是单纯追求更大的批量，应综合考虑硬件限制并通过实验确定最佳的批量大小。这种方法保证了在可用资源范围内，模型训练既高效又实用。


## Running on Azure

This project can be deployed on **Azure Virtual Machines** with GPU support.

| Item | Details |
|---|---|
| **Azure VMs** | [GPU-optimized VM sizes](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/overview) |
| **Compute** | Select VM size based on model requirements |


## **二、最大Sequence Length、Padding、Truncating**

在批处理中，需要对训练样本进行填充，以确保每一批数据中所有样本的形状或大小一致，这是并行处理数据的机器学习模型的基本要求。特别是在执行序列任务，如语言生成时，这种数据的统一性变得尤为重要。  在准备数据批次时，需要对较短的序列进行填充，增加一些无关紧要的值，以确保它们的长度与批次中最长序列相匹配。这种填充可以是在序列的前端（左填充），或者是尾端（右填充），有时还可能两端同时进行，这取决于具体的模型设计和任务需求。需要注意的是，并不是所有的技术都能适应任意一端的填充方式。例如，在使用**FlashAttention技术时，必须进行左填充。**  为了更好地控制批次大小，建议设定一个最长序列限制。例如，我们如果将这个最大长度设置为1,024个令牌，那么批次中的每个样本都会被处理到恰好有1,024个令牌。如果某个样本原本只有512个令牌，那么就会追加512个填充令牌。相反，如果某个样本的令牌数超过了1,024个，那么超出的部分就会被截断。通过这种方式，我们不仅能保证处理过程的一致性，也有助于优化内存的使用，从而提升训练的效率。


看一个例子。我们想将这 2 个句子放入一批中：

```
prompt1 = "You are not a chatbot."
prompt2 = "You are not."

prompt_test1 = [prompt1, prompt1]
prompt_test2 = [prompt1, prompt2]
```

我做了两批提示。第一个包含两次相同的序列，因此两个序列具有相同的长度。

如果我们使用 Llama 2 的分词器来分词prompt_test1

```
input = tokenizer(prompt_test1, return_tensors="pt");
print(input)
```

它产生输入 ID（令牌的 ID）和注意力掩码的张量：It yields tensors of input IDs (the IDs of the tokens) and attention mask:

```
{
    'input_ids': tensor([[    1,   887,   526,   451,   263, 13563,  7451, 29889],
        [    1,   887,   526,   451,   263, 13563,  7451, 29889]]),
    'attention_mask': tensor([[1, 1, 1, 1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1, 1, 1, 1]])
}
```

但是，如果尝试标记prompt_test2：

```
input = tokenizer(prompt_test2, return_tensors="pt");
print(input)
```

它会产生这个错误：

*ValueError: Unable to create tensor, you should probably activate truncation and/or padding with 'padding=True' and 'truncation=True' to have batched tensors with the same length. Perhaps your features (`input_ids` in this case) have excessive nesting (inputs type `list` where type `int` is expected)*

这个错误信息明确指出了我们需要对样本进行填充和截断。鉴于我们的样本长度较短，我们把分词器的最大长度设定为20。我选择了向左填充的策略，并且决定用“UNK”（未知）令牌作为填充令牌。通过这种设置，可以确保所有的输入长度一致，无论是在训练还是在模型推断过程中，使得模型处理过程更加高效。同时，使用UNK令牌作为填充，有助于模型在处理未知或不常见的输入时更为鲁棒。

```
tokenizer.padding_side = "left"
tokenizer.pad_token = tokenizer.unk_token
input = tokenizer(prompts, padding='max_length', max_length=20, return_tensors="pt");
print(input)
```

它产生：

```
{
    'input_ids': tensor([
        [    0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
             0,     0,     1,   887,   526,   451,   263, 13563,  7451, 29889],
        [    0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
             0,     0,     1,   887,   526,   451,   263, 13563,  7451, 29889],
        [    0,     0,     0,     0,     0,     0,     0,     0,     0,     0,
             0,     0,     0,     0,     0,     1,   887,   526,   451, 29889]]), 
    'attention_mask': tensor([
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1]])
}
```

现在序列的开头（左侧）出现了许多"0"，这代表着填充令牌的ID。在训练时，以确保这些填充标记不会干扰模型的学习，它们在注意力掩码中被标记为"0"，表示将被忽略。可以看到，最大序列长度对批次形状有决定性影响。例如，如果选择的批量大小是12，而最大序列长度是1,024，那么批次的形状就会是12*1,024，包含总共12,288个令牌。若最大序列长度设置为512，则批次大小会减半。

理想情况下，最大长度应设为与训练样例中最长序列的长度相匹配。如果GPU内存有限，这个长度也可以适当减少。通常，除了用于RAG应用和摘要任务外，超过4,096的最大长度并不常见；对于大多数的语言生成任务，最小推荐长度是512。这样的设定有助于在确保模型效能的同时，避免不必要的内存消耗。

## **三、Epochs和Steps**

模型在处理完一批数据后就会进行权重更新，这个过程称为训练步骤。例如，如果数据集含有1,000个样例，且批量大小设置为100，那么在整个数据集上进行一次完整的迭代就需要10个这样的训练步骤（1,000除以100等于10）。每一步涉及到数据的前向传播（即数据通过模型），损失的计算（即模型预测与实际情况的偏差），以及通过反向传播更新权重，尝试减少损失。  当数据集中的每个样例都已恰好被模型处理一遍时，就完成了一个训练周期，也就是一个epoch。所以，每个epoch包含的步骤数量取决于数据集的大小和批量大小。延续前面的例子，如果整个数据集有1,000个样例，批量大小为100，则完成一个epoch需要10个步骤。进行多个epoch的训练意味着让模型多次见到同样的数据，期望模型通过调整权重进行更准确的预测，每经过一个epoch都可能让模型有所学习和进步。

```
[...]
        num_train_epochs=3,
[...]
```

或者or

```
[...]
        max_steps=1000,
[...]
```

当设置了`num_train_epochs`参数时，`max_steps`参数会被覆盖。在这种设置下，训练将进行3个epoch，也就是说模型将三次完整地见到所有的训练数据。

假设在使用openassistant-guanaco训练TinyLlama模型时，若步骤总数为9,846，批量大小定为8，则一个epoch将包含大约1,231个训练步骤。如果仅在这个数据集上训练一个epoch，模型通常能够学到有效信息。然而，如果继续训练更多的epoch，就可能导致模型过度拟合，也就是它对训练数据过于敏感，可能影响其在新数据上的表现。如果观察到模型在两个epoch后的训练情况，就能发现这一过度拟合的迹象。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXyvuzhK1CR7Kb6yeGQvrdSaJNYpaLIictddYwEudrjpvzSZlzQCENnG277AChJEgtFmuI46t24Z8w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


即使没有观察验证损失，也可以注意到训练损失下降得异常迅速。如在下一节中所述，通过调整学习率和采用适当的预热比例，可以有效地解决这一问题。这种调整有助于模型学习得更为平稳，避免过拟合，同时保证模型在未知数据上的泛化能力。

## **四、梯度累积步骤Gradient Accumulation Steps**

梯度累积技术通过分割数据为更小的子批量来实现模拟大批量训练的效果。这一技巧并不在每个子批量处理后立即更新模型的权重，而是在一定数量的步骤中积累每个子批量的梯度。权重更新只有在累积到与较大批量相当的量时才会进行。例如，若目标批量大小是1,024，但设备每次只能处理256个样本，那么可以通过累积四个步骤中每个步骤的256个样本的梯度，来模拟出一个包含1,024个样本的批量更新。

这种方法在有限的内存资源下，平衡了对大批量的需求，有助于实现更稳定的梯度估计以及可能达到的更快收敛速度。举个例子，在TrainingArguments设置中，如果将`per_device_train_batch_size`设为4且`gradient_accumulation_steps`设为2，则最终的总批量大小实际上是8（4乘以2），这与将`per_device_train_batch_size`设为8，`gradient_accumulation_steps`设为1是一样的效果。这项技术不会对模型的性能本身造成影响，而是一种优化训练过程中资源使用的有效手段。

```
[...]
        per_device_train_batch_size=4,
        gradient_accumulation_steps=2,
[...]
```



## **五、梯度检查点Gradient Checkpointing**

在常规的训练过程中，所有的中间激活数据都会被保留在内存里，以便在反向传播时计算梯度。但是，考虑到大多数硬件（比如GPU）的内存限制，对于特别深的网络，这种方式很快就会显得不实用。梯度检查点技术通过只在网络的特定层面上保存激活数据来应对此挑战。对于那些没有保存激活数据的层，需要计算梯度时，会在反向传播过程中重新进行计算。

这种在计算量与内存使用之间的权衡意味着，尽管梯度检查点可以大幅降低训练所需的内存空间，但可能会因为需要重新计算某些激活数据而增加计算时间。这是一种平衡效率与资源的技术策略，特别适用于资源有限而模型又深且大的情况。

这在 TrainingArguments 中设置如下：

```
[...]
        gradient_checkpointing=True,
[...]
```

或者

```
model.gradient_checkpointing_enable()
```

## **六、学习率Learning Rate**

学习率是决定模型在训练期间如何更新其权重的关键超参数。它影响模型为最小化损失函数而在参数空间中迈出的步长大小。合理设定的学习率可以确保模型在学习过程中既能高效提升预测性能，又不会在达到最优化之前就发生过度调整或停滞不前。

对于大型语言模型（LLM）而言，选取合适的学习率尤为重要，因为这些模型有着庞大的参数量和复杂的数据模式。如果学习率过高，模型可能会快速收敛至次优解，或者在寻找最优点时产生振荡现象。反之，学习率太低可能会拖慢收敛速度，甚至造成训练进程的完全停滞。

在实际应用中，确定合适的学习率往往需要通过试验调整，也就是使用不同的学习率值进行数次微调尝试。针对LLM，较为理想的学习率通常落在1e-6到1e-3之间。例如，可以尝试如1e-3, 5e-4, 1e-4, 5e-5, 1e-5, 5e-6和1e-6等值。无需一一尝试所有这些值，通常建议围绕1e-4进行搜索。例如，如果发现5e-5的学习率带来的结果优于1e-5，那么更小的值如5e-6和1e-6很可能也不会获得更佳结果。通过这种方式，可以更高效地定位到一个使模型性能最佳化的学习率点。

学习率在TrainingArguments中设置如下：

```
[...]
        learning_rate=1-e4,
[...]
```

## **七、学习率调度器Learning Rate Scheduler**

学习率调度器的目的在于根据一个预先定义的方案，在训练过程中调整学习率。这样做有助于避免模型早期训练中陷入局部最小值，或者在接近最优解时跳过最小值。对于大型语言模型（LLM），最常见的调度器类型是含预热期的调度器。这种调度器从一个较低的学习率出发，在几个epoch或训练步骤后逐步将学习率提升到目标值。这个策略在从大规模预训练模型开始微调时特别有用，它可以有效预防早期训练中可能出现的剧烈权重更新，这种更新有碍于模型的稳定性。  在大多数场景下，我推荐使用含预热的线性调度器，因为它至少与其他类型的调度器一样有效，这一点在论文《何时、为何以及多少？通过细化自适应学习率调度》中有所展示。线性调度器在预热后会逐步降低学习率，这种逐渐减小学习率的策略有助于模型在训练后期更加稳定地收敛。

这在 TrainingArguments 中设置如下：

```
[...]
        lr_scheduler_type="linear",
[...]
```

## **八、热身步骤和热身比率Warmup Steps and Warmup Ratio、**

预热步骤是指在训练初期，学习率会按照设定的学习率调度计划从一个较低的初始值渐增至一个预定的目标值。例如，假设设定了1,000个预热步骤，学习率会从一个较低的起点开始，并随着每个步骤的完成逐步上升，直至第1,000步时达到既定的目标学习率。到达这个点之后，学习率可能会按照另一个计划进行调整，如保持不变或按比例衰减。

预热比率不是一个固定的步数，而是用来指定用于预热期的训练步骤数占总训练步数的比例。比如说，如果整个训练计划设为10,000步，而预热比率设为0.1，那么就意味着有10%的步骤，即前1,000步，将被用来预热学习率。这个比率有助于根据整个训练周期的长度调整预热阶段的长度，确保无论训练周期的总时长如何，预热期都能保持合适的比例。

比起设定具体的预热步数，使用预热比率通常更为常见。因为如果要设定具体的步数，就需要提前知道训练将会持续多少步。实际上，如果我们将预热步数固定为2,000步，但实际只进行了1,900步的训练，那么模型将永远不会达到目标学习率。通常，将预热比率设置为0.1是一个不错的起点。探索更适合的预热比率可能会对提升模型的性能有所帮助。

预热比率在TrainingArguments中设置，如下：

```
[...]
        warmup_ratio=0.1,
[...]
```

## **九、权重衰减Weight Decay**

权重衰减是一种鼓励模型维持较小权重值的技术，通过这种方式实现对模型的正则化，以避免复杂度过高的模型。这种技术通过将权重的平方和乘以一个正则化参数后添加到模型的损失函数中来实施。其效果是轻微地推动权重向零移动，这也有助于模型不过分依赖于任何单一的输入特征，因为这种过分依赖通常会造成对应特征权重值的显著增大。

正则化参数是控制权重衰减强度的关键：参数值为零意味着没有应用任何正则化，而较大的参数值则会对较大的权重施加较强的惩罚。在默认情况下，权重衰减的值通常设为0，这意味着在出发点上不对权重进行惩罚。

如果在微调过程中发现模型出现了过拟合的迹象，比如训练损失迅速下降而验证损失却上升，这时建议考虑调整权重衰减值。否则，如果模型表现良好，可以保持权重衰减为0，以确保模型训练过程的自然进展。

权重衰减在TrainingArguments中设置，如下：

```
[...]
        weight_decay=0.0,
[...]
```

## **十、优化器Optimizer**

优化器的作用在于引导模型训练过程，通过最小化误差或提升准确性来进行微调。众多优化器中，AdamW（一种基于Adam的变体）是目前使用最广泛的。另外，AdaFactor是一个内存效率更高的有趣选择。

Adam，即自适应矩估计，它为每个参数保持两个移动平均；一个记录梯度（第一时刻，指示参数更新的方向和速度），另一个记录梯度的平方（第二时刻，指示更新的幅度）。因此，Adam的内存消耗相对较大。这些移动平均有助于为每个参数调整学习率。

AdamW是Adam的一个变种，表示带权重衰减的Adam。它将权重衰减与优化步骤分离开来，通过直接应用权重衰减到参数上而不是和梯度更新混合，从而有助于更好的模型正则化。AdamW通常能带来更稳定的训练和更优的模型性能。

AdaFactor是为了减少内存使用和提升训练效率而设计的另一优化器，它通过对Adam中使用的二阶矩进行分解来实现这一点。与Adam和AdamW不同，AdaFactor的设计使其即使在没有明确的学习率调整下也能正常工作，这使得它成为大规模和资源限制训练环境中的一个实用选择。

在内存效率方面，AdaFactor是AdamW的一个很好的替代品。但是，现在我们已经实现了AdamW的内存高效实现，即8位量化版AdamW。AdamW的状态甚至可以分页到CPU RAM，以进一步减少GPU内存消耗。此外，虽然AdamW为模型的每个参数添加了两个状态以进行细致的微调，但在采用LoRA等参数效率微调（PEFT）方法时，这不成问题，因为此时只有少量参数可训练。结合8位分页AdamW与LoRA可以显著降低AdamW的总内存消耗，使其适合于资源较为有限的环境。

优化器在TrainingArguments中设置，如下：

```
[...]
        optim="adamw_8bit",
[...]
```

为了获得更好的模型，我建议将其设置为未量化的“adamw_torch”。如果内存不足，请尝试“adamw_8bit”。然后，作为最后的手段，尝试“paged_adamw_8bit”。它会比 AdamW 8 位慢，但会进一步减少内存消耗。

## **十一、Float16 和 Bfloat16**

传统上，机器学习模型使用float32数据类型进行训练，这种类型的每个参数占用4字节（32位）内存。对于参数量达到70亿（7B）的模型，仅使用float32就意味着至少需要一块具有28GB内存（7乘以4等于28）的GPU。对于更大的模型，这种内存要求难以满足。因此，半精度训练开始变得流行，它使用float16或bfloat16数据类型，将内存需求降低了一半。  float16和bfloat16之间的主要差异在于它们如何在指数和小数部分之间分配位。bfloat16的设计允许处理更广泛的数值范围，而不会显著牺牲计算精度，这使得bfloat16在执行高速且内存效率高的深度学习操作时具有优势。尽管bfloat16在性能上更佳，但它只受安培（Ampere）一代或更新版本的GPU支持。如果您的GPU支持bfloat16，请优先使用。如果不支持，您可以选择float16，但如果在训练中遇到溢出问题（例如损失突变为0.0或NaN），可能需要回退到float32。  您可以根据硬件自动设置这些参数，具体设置方法如下：[此处假设原文会提供具体代码或设置步骤]。

```
        fp16= not torch.cuda.is_bf16_supported(),
        bf16= torch.cuda.is_bf16_supported(),
```

## **十二、评估和保存步骤Evaluation and save steps**

评估是训练过程中的一个关键步骤，在此过程中，模型会定期对未曾见过的数据进行性能评估。这种评估对于确保模型没有过度拟合训练数据非常重要。如果观察到训练损失在减少，但验证损失保持不变或有所增加，这通常意味着模型出现了过拟合。

根据具体任务和模型大小，进行评估可能会消耗大量资源。如果总训练步骤数为X，建议至少每X/10步进行一次评估，以监控模型的进展和性能。

“保存步骤”（save_steps）参数决定了模型保存的频率，即创建检查点的频率。检查点是指那些中间状态但功能完备的模型版本。保存检查点非常重要，因为它们可以在训练出现问题时用于重新开始训练。有时候，这些中间检查点的性能甚至会优于最终的模型。

建议将save_steps设置为evaluation_steps的整数倍，这样可以确保每个保存的检查点都已针对验证数据进行了评估。这不仅有助于确保模型状态的有效性，还方便对模型在训练过程中的表现进行综合评估。

可以在 TrainingArguments 中设置它们，如下所示：

```
[...]
        evaluation_strategy="steps",
        do_eval=True,
        eval_steps=50,
        save_steps=100,
[...]
```

要注意的是，模型检查点会在硬盘上占用相当的存储空间。在使用参数效率微调（PEFT）方法，比如LoRA时，检查点主要包含模型的适配器参数。通常情况下，这些检查点大小不会超过500MB。然而，如果训练步骤为1,000，且将save_steps设置为50，那么因为频繁保存，这些检查点加起来将会占用大约10GB的存储空间。

这种情况下，虽然检查点对于保证训练过程中出现问题时可以从中断点恢复极为重要，但也需要考虑到硬盘空间的管理。因此，在训练设置中制定一个合适的save_steps值，既要确保能及时保存模型状态以便需要时恢复，也要考虑到存储资源的限制，尤其是当硬盘空间有限时。

---

## Appendix: Fine-tuning Base LLMs vs Instruct Version

> *原文来自 LLM-Fine-Tuning-Best-Practices*

In the application of large language models (LLMs), fine-tuning is a critical step. Fine-tuning allows the model to better adapt to specific tasks or datasets. However, with the development of LLMs, two main versions have emerged: base LLMs and instruct LLMs. This article will explore the differences between these two versions and discuss which version should be chosen for fine-tuning in practical applications.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nV2OasoxzlibKMkawNmnVETPsicGxQagJ5rklAAOJoUic5qYuCr0vEeoSiaNAicCvag9SHhXxVGLZpdq1Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## What are Base LLMs and Instruct LLMs?

### Base LLMs

Base LLMs are models pre-trained on a large amount of text data, with the training objective of predicting the next token. These models do not have specific format constraints and can generate highly diverse text. However, base LLMs may not directly answer user prompts and may repeat or deviate from the topic during generation.

### Instruct LLMs

Instruct LLMs are fine-tuned versions of base LLMs, processed through a complex pipeline to better respond to user instructions. These models undergo several post-training stages, including supervised fine-tuning (SFT), reinforcement learning with human feedback (RLHF), and direct preference optimization (DPO). They are capable of generating answers that align more closely with human preferences and are commonly used in chat applications.

## Differences Between Fine-Tuning Base LLMs and Instruct LLMs

 

### Fine-Tuning Base LLMs

When fine-tuning base LLMs, the model updates its weights based on new data, gradually adapting to new tasks or datasets. Since base LLMs do not have specific format constraints, they can more quickly learn new features and styles.

### Fine-Tuning Instruct LLMs

Instruct LLMs have already undergone a complex post-training process and have specific formats and system instructions. Fine-tuning instruct LLMs may introduce conflicts with the original system instructions and templates, leading to unexpected results. Additionally, instruct LLMs may partially lose their original safety and preference alignment capabilities during fine-tuning.

## Why Fine-Tuning Instruct LLMs is Not Recommended

- **Disruption of Original Training**: Fine-tuning instruct LLMs can partially undo the results of their original SFT and DPO training, causing the model to generate answers that no longer fully align with human preferences.

- **System Instruction Conflicts**: Fine-tuning instruct LLMs introduces new system instructions that may conflict with the original instructions, leading to inconsistent results.

- **Safety Issues**: Instruct LLMs undergo safety training, and fine-tuning may disrupt these safety constraints, resulting in the generation of unsafe content.

  In most cases, fine-tuning base LLMs is preferable to fine-tuning instruct LLMs. Base LLMs do not have specific format constraints and can more quickly adapt to new data and tasks. For applications requiring specific formats and safety, instruct LLMs can be considered, but potential conflicts and inconsistencies should be noted.
  
## SFT code

### Base Model
```
model_name = "meta-llama/Meta-Llama-3.1-8B"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 128004
tokenizer.padding_side = 'right'

ds = load_dataset("timdettmers/openassistant-guanaco")

#Add the EOS token
def process(row):
    row["text"] = row["text"]+"<|end_of_text|>"
    return row

ds = ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_QLoRA_right/",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=25,
        num_train_epochs=1,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=512,
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()

```
### Instruct Model
```
model_name = "meta-llama/Meta-Llama-3.1-8B-Instruct"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|finetune_right_pad_id|>"
tokenizer.pad_token_id = 128004
tokenizer.padding_side = 'right'

ds = load_dataset("timdettmers/openassistant-guanaco")

#Add the EOS token
def process(row):
    row["text"] = row["text"]+"<|end_of_text|>"
    return row

ds = ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation
)

model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})


peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Llama3.1_8b_Instruct_QLoRA_right/",
        eval_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=4,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_strategy="epoch",
        logging_steps=25,
        learning_rate=1e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        eval_steps=25,
        num_train_epochs=1,
        warmup_ratio=0.1,
        lr_scheduler_type="linear",
        dataset_text_field="text",
        max_seq_length=512,
)

trainer = SFTTrainer(
        model=model,
        train_dataset=ds['train'],
        eval_dataset=ds['test'],
        peft_config=peft_config,
        tokenizer=tokenizer,
        args=training_arguments,
)

trainer.train()
```

---

# Part 2: 各种微调方法全景对比

> *原文来自 Comparison-of-Various-Fine-Tuning-Methods*


本文将会对如下微调技术进行对比：SFT、ReFT、RHLF、RLAIF、DPO、PPO、TPO。




## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | LoRA/PEFT |


## 几种技术之间的关系

如果把复杂的问题简单理解，这些技术之间的关系大概是：

**ReFT（Reinforced Fine-Tuning，强化微调）：**

- **组成**：ReFT = SFT + PPO
- **过程**：在有监督微调（SFT）的基础上，使用 PPO（近端策略优化）进行强化学习。
- **评估方式**：通常通过**自动化程序**对模型输出进行评估，奖励信号来自程序的评价。

**RLHF（Reinforcement Learning from Human Feedback，基于人类反馈的强化学习）：**

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUZtF6XYK9EpTpg40XvUeRCHQFd39MdyIIIbGaFjQKZ8PDxic6faSnOGnITqdpvbznWY1Sp2aqIIcw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

- **组成**：RLHF = SFT + PPO + 人类反馈
- **过程**：在 SFT 的基础上，使用 PPO 进行强化学习，奖励信号来自**人类反馈**。
- **评估方式**：人类对模型输出进行评价，或者使用基于人类反馈训练的**奖励模型**来评估。

##### DPO 方法（Direct Preference Optimization，直接偏好优化）：

- **组成**：DPO 方法 = SFT + **参考模型** + DPO
- **过程**：在 SFT 的基础上，**引入参考模型**（通常是经过 SFT 的初始模型，参数固定不更新），使用 DPO（直接偏好优化）方法，利用参考模型和人类偏好数据，直接优化模型参数。
- **评估方式**：利用**人类偏好数据和参考模型**，构建损失函数，直接优化模型参数，使模型更倾向于生成被人类偏好的输出。

**RLAIF（Reinforcement Learning from AI Feedback，基于 AI 反馈的强化学习）：**

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUZtF6XYK9EpTpg40XvUeRCxfjelLwiaed6DNmzrv9LKwPYwaPAqFJ0qc9ddesiaDzsU9wgaEmettJg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

- **组成**：RLAIF = SFT + PPO + AI 反馈
- **过程**：在 SFT 的基础上，使用 PPO 进行强化学习，奖励信号来自**AI 模型的反馈**。
- **评估方式**：辅助的 AI 模型（可能是奖励模型）对模型输出进行评价，提供奖励信号。


**TPO（Thought Preference Optimization，思维偏好优化）：**

- **组成**：TPO = SFT + 思维生成（Thought Generation）+ DPO
- **过程**：在 SFT 的基础上，引入**思维生成**，即模型在输出回答前生成内部的思维过程。然后，使用 DPO 方法直接优化模型，偏好数据来自**AI 判别模型的反馈**。
- **评估方式**：利用**AI 判别模型**对模型输出的**回答部分**进行评价，形成偏好对（优选和劣选）。根据这些偏好对，使用 DPO 方法优化模型参数，提升模型性能。



**解释：**

- ReFT（强化微调）通过在监督微调后的模型上，使用PPO算法进行强化学习，奖励信号来自于自动化程序对模型输出与标准答案的比较。

- RLHF（基于人类反馈的强化学习）在SFT基础上，使用PPO算法进行强化学习，奖励信号来自人类对模型输出的评价。

- DPO方法（直接偏好优化）在SFT基础上，使用DPO算法直接优化模型参数以符合人类偏好，不使用PPO等传统强化学习算法。

- RLAIF（基于AI反馈的强化学习）类似于RLHF，但人类反馈替换为AI模型的反馈，使用PPO算法进行强化学习。




ReFT、RLHF、DPO和RLAIF。这些方法都是在监督微调（SFT）的基础上，进一步优化模型以提高性能，但它们在优化策略和反馈来源上有所不同。

1. **ReFT（Reinforced Fine-Tuning，强化微调）**：这是SFT和PPO（近端策略优化）的结合。在第一阶段，模型通过SFT在有标注的数据上进行训练，建立基本的语言理解和生成能力。第二阶段，引入PPO算法，对模型进行强化学习优化。此时，模型的输出由自动化程序进行评估，程序根据预设的规则或标准对模型的输出进行评价，并生成奖励信号。模型根据这些奖励信号，使用PPO算法调整自身参数，以产生更优的输出。ReFT的特点是评估过程自动化，无需人类参与，适用于有明确客观标准的任务，例如数学问题求解。

2. **RLHF（Reinforcement Learning from Human Feedback，基于人类反馈的强化学习）**：在SFT的基础上，结合PPO算法，但奖励信号来自人类反馈。具体而言，人类对模型的输出进行评价，指出更优的回答，或通过偏好对比的方式提供反馈。这些人类反馈可以直接用于指导模型优化，或者用于训练一个奖励模型，后续由奖励模型对模型输出进行评估。RLHF的优势在于引入了人类的主观判断，使模型的输出更符合人类偏好，适用于需要复杂评价和主观判断的任务。

3. **DPO（Direct Preference Optimization）方法：** 与前两种方法不同，DPO 不使用强化学习算法（如 PPO），而是采用监督学习的方法，直接优化模型。在 SFT（有监督微调）之后，**引入一个参考模型**（通常为经过 SFT 的初始模型，参数固定不更新），利用人类偏好数据和参考模型，构建损失函数，对模型进行微调。具体来说：

   - **收集人类偏好数据**：收集人类对模型输出的偏好数据，如在给定的多个回答中标注出人类更喜欢的那个，形成偏好对（首选和非首选响应）。

   - **参考模型的引入**：参考模型提供了一个稳定的概率基准，用于与当前模型的输出概率进行比较，防止模型在优化过程中过度偏离预训练的语言分布。

   - **构建损失函数**：设计一个损失函数，利用当前模型和参考模型对首选和非首选响应的对数概率，鼓励模型倾向于生成被人类偏好的输出。损失函数通常包含对数概率差和正则项，以确保训练的稳定性。

   - **直接优化模型参数**：通过最小化该损失函数，直接调整模型参数，使其更倾向于生成被人类偏好的输出。

     DPO 避免了强化学习中的试错过程，训练更稳定，效率更高，适用于有大量人类偏好数据的场景。**同时，参考模型的引入有助于保持模型生成质量的稳定性，防止模型偏离预训练分布过远。**

   ## Azure OpenAI的DPO

   目前AOAI支持DPO：

   *https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/fine-tuning?tabs=azure-openai%2Cturbo%2Cpython-new&pivots=programming-language-studio#direct-preference-optimization-dpo-preview*

   ```
   {  
     "input": {  
       "messages": {"role": "system", "content": ...},  
       "tools": [...],  
       "parallel_tool_calls": true  
     },  
     "preferred_output": [{"role": "assistant", "content": ...}],  
     "non_preferred_output": [{"role": "assistant", "content": ...}]  
   }  
   ```

   Jsonal format:

   ```
   {{"input": {"messages": [{"role": "system", "content": "You are a chatbot assistant. Given a user question with multiple choice answers, provide the correct answer."}, {"role": "user", "content": "Question: Janette conducts an investigation to see which foods make her feel more fatigued. She eats one of four different foods each day at the same time for four days and then records how she feels. She asks her friend Carmen to do the same investigation to see if she gets similar results. Which would make the investigation most difficult to replicate? Answer choices: A: measuring the amount of fatigue, B: making sure the same foods are eaten, C: recording observations in the same chart, D: making sure the foods are at the same temperature"}]}, "preferred_output": [{"role": "assistant", "content": "A: Measuring The Amount Of Fatigue"}], "non_preferred_output": [{"role": "assistant", "content": "D: making sure the foods are at the same temperature"}]}
   }
   ```

   

4. **RLAIF（Reinforcement Learning from AI Feedback，基于AI反馈的强化学习）**：这是SFT、PPO和AI反馈的结合。在SFT后，使用PPO进行强化学习，然而奖励信号不是来自人类，而是来自辅助的AI模型（如奖励模型）的反馈。AI模型对主模型的输出进行评估，提供奖励信号。这样的方法节省了人类评价的成本，但依赖于辅助AI模型的质量。

**总结：**

四种方法中，ReFT、RLHF和RLAIF都使用了PPO作为强化学习算法，区别在于奖励信号的来源不同：ReFT来自自动化程序的评估，RLHF来自人类反馈，RLAIF来自AI模型的反馈。只有DPO方法使用了监督学习的方式，不采用PPO等强化学习算法，而是直接利用人类偏好数据优化模型。



**那么，DPO的意义是什么？**

强化学习方法（如PPO）需要模型在环境中自行探索，通过试错学习获得奖励信号，这个过程复杂，训练不稳定，且调参困难。相比之下，监督学习的方法更直接高效：通过人类提供的偏好数据，直接告诉模型什么是好的输出，构建损失函数，调整模型参数。这样避免了强化学习的复杂性，训练过程更稳定，效率更高，特别适用于有大量人类偏好数据的情况。

举个例子，使用强化学习的模型就像是在黑暗中摸索前进，需要不断试错；而使用监督学习的DPO方法，就像是有人直接给了一张地图，告诉你正确的前进路线。采用监督学习，可以更快地达到目标。

选择方法的依据：如果任务有明确的客观评价标准，适合使用ReFT，通过自动化程序评估模型输出。如果希望模型的输出更符合人类主观偏好，并有大量人类反馈数据，可以选择RLHF或DPO方法。RLHF使用强化学习算法，需要模型与环境交互，训练复杂；DPO则采用监督学习，训练更简单高效。若人类反馈成本高，可以考虑RLAIF，用辅助AI模型提供反馈信号。



---

# Part 3: 强化学习与微调的本质区别

> *原文来自 Comparison-of-Various-Fine-Tuning-Methods*


## 强化学习类与有监督微调类的区别

**一、强化学习**

强化学习的基本框架

强化学习（Reinforcement Learning，RL）是一个智能体（Agent）与环境（Environment）互动的过程。智能体的目标是通过学习策略（Policy），在与环境的交互中最大化累积的奖励（Reward）。

 

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUmuCC75DMa6J6ZShqhcHx0wRmzErG3eIKhpxmNeHU4GyAm491eAhwXhibweP4qAHWqH4kuPLOIQSA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

#### **1. 关键组成部分**

##### **（1）状态空间（State Space，S）**

- **定义**：环境可能处于的所有状态的集合。
- **表示**：在时间步 t，环境的状态记为 **s_t**。

##### **（2）动作空间（Action Space，A）**

- **定义**：智能体能够执行的所有可能动作的集合。
- **表示**：在时间步 t，智能体采取的动作记为 **a_t**。

##### **（3）策略（Policy，π）**

- **定义**：策略是从状态到动作的映射，决定智能体在每个状态下选择哪个动作。
- **表示**：
  - **确定性策略**：a_t = π(s_t)，即在状态 s_t 下，总是选择相同的动作。
  - **随机性策略**：根据概率分布选择动作，a_t ~ π(a | s_t)。

##### **（4）奖励函数（Reward Function，R）**

- **定义**：定义了智能体在特定状态下采取某个动作后获得的即时奖励。
- **表示**：R(s_t, a_t)，表示在状态 s_t 采取动作 a_t 后获得的奖励。

##### **（5）状态转移概率（State Transition Probability，P）**

- **定义**：描述了智能体在当前状态采取某个动作后，环境转移到下一个状态的概率。
- **表示**：P(s_{t+1} | s_t, a_t)，表示在状态 s_t 采取动作 a_t 后，转移到状态 s_{t+1} 的概率。

##### **（6）折扣因子（Discount Factor，γ）**

- **定义**：用于平衡即时奖励和未来奖励的重要性，取值范围 0 ≤ γ ≤ 1。
- **特点**：
  - 当 γ 接近 0 时，更关注即时奖励。
  - 当 γ 接近 1 时，更关注长期累积奖励。

##### **（7）价值函数（Value Function）**

- **状态价值函数（V^π(s)）**：

  - **定义**：在策略 π 下，从状态 s 开始所能获得的期望累积奖励。

  - **表示**：

    ```
    V^π(s) = E_π [ R(s_t, a_t) + γ * V^π(s_{t+1}) | s_t = s ]
    ```

- **行动价值函数（Q^π(s, a)）**：

  - **定义**：在策略 π 下，从状态 s 采取动作 a 后所能获得的期望累积奖励。

  - **表示**：

    ```
    Q^π(s, a) = E_π [ R(s, a) + γ * Q^π(s_{t+1}, a_{t+1}) ]
    ```

#### **2. 举例说明**


**例子：自动驾驶小车**

- **环境**：一个简单的二维道路网格，小车需要从起点到达终点。
- **状态（s_t）**：小车当前的位置坐标，例如 (x, y)。
- **动作（a_t）**：小车可以选择的移动方向，例如：向上、向下、向左、向右。
- **策略（π）**：决定小车在每个位置选择哪个方向移动的规则。
- **奖励函数（R）**：
  - **到达终点**：奖励 +100。
  - **每移动一步**：惩罚 -1（鼓励尽快到达终点）。
  - **撞到障碍物**：惩罚 -50。
- **状态转移概率（P）**：确定性环境中，采取动作后，会确定地移动到相应的新位置。但如果引入随机性，例如，有一定概率因路面湿滑而滑动到其他位置，则需要用 P(s_{t+1} | s_t, a_t) 描述这种概率。
- **折扣因子（γ）**：设为 0.9，使得小车既关注即时奖励（避免无谓的移动），也重视最终到达终点的高额奖励。



#### **3. 强化学习的目标**

- **目标**：学习一个最优策略 π*，使得智能体在环境中行动时，累积的期望奖励最大化。

- **数学表示**：

  ```
  π* = arg max_π E_π [ ∑_{t=0}^∞ γ^t * R(s_t, a_t) ]
  ```

  其中，E_π 表示在策略 π 下，对所有可能的状态和动作序列的期望。



#### **4. 强化学习的关键要素总结**

- **状态（s_t）**：对环境的感知，智能体当前所处的位置。
- **动作（a_t）**：智能体可以执行的动作集合。
- **策略（π）**：指导智能体选择动作的规则。
- **奖励信号（R）**：即时反馈，评估智能体动作的好坏。
- **折扣因子（γ）**：衡量即时奖励和未来奖励的重要性。
- **价值函数（V^π(s), Q^π(s, a)）**：用于评估策略的优劣，指导策略改进。
- **学习算法**：用于更新策略和价值函数的方法，例如 Q-learning、SARSA、策略梯度方法、Actor-Critic 等。



#### **5. 总结**


在强化学习中，智能体通过不断与环境交互，根据奖励信号调整策略，目的是找到能使累积奖励最大化的最优策略。关键组件包括：

- **状态空间（S）\**和\**动作空间（A）**

- **策略（π）**

- **奖励函数（R）**

- **折扣因子（γ）**

- **价值函数（V^π(s), Q^π(s, a)）**

- **学习算法**

  

**二、奖励函数与奖励模型**

强化学习确实需要奖励信号来指导智能体（Agent）学习最优策略，以最大化累积奖励。但是，需要明确的是，强化学习需要奖励信号，但并不一定必须通过奖励模型来获得。奖励信号可以由预先定义的奖励函数直接提供，也可以通过奖励模型来获得，这取决于具体的任务和环境。

**奖励函数与奖励模型的区别**

**1. 奖励函数（Reward Function）**

- **定义**：由人类**手工设计的明确规则或公式**，根据智能体的状态和动作，直接计算即时的奖励值。

- **特点**：

  - **规则清晰**：明确规定了在特定情况下的奖励或惩罚。
  - **直接计算**：无需训练或学习过程，直接根据状态和动作计算奖励。
  - **可解释性强**：由于规则是手工制定的，容易理解和解释。

- **适用场景**：**评价标准明确、客观、易于量化**的任务。

- **示例**：

  在之前的**自动驾驶小车**的例子中，我们定义了如下奖励函数：

  这个奖励函数是由人类明确设计的，智能体可以根据这个函数直接计算每个动作的奖励。

  - **到达终点**：奖励 **+100**。
  - **每移动一步**：惩罚 **-1**，鼓励最短路径。
  - **撞到障碍物**：惩罚 **-50**，避免危险行为。

**2. 奖励模型（Reward Model）**

- **定义**：通过**机器学习方法训练得到的模型**，用于**预测或评估**智能体行为或输出的奖励值。

- **特点**：

  - **数据驱动**：依赖大量人类反馈数据进行训练。
  - **适应复杂评价**：能够捕捉**复杂、主观**的评价标准，适用于难以手工设计奖励函数的任务。
  - **需要训练**：模型需要通过学习过程来调整参数，以准确预测奖励。

- **适用场景**：**评价标准复杂、主观、难以量化**的任务。

- **示例**：

  在**对话生成模型**的训练中，例如ChatGPT，难以手工设计一个明确的奖励函数来评估回复的质量。因此，我们：

  - **收集人类反馈数据**：人类对模型生成的回复进行评价，如打分或偏好比较。
  - **训练奖励模型**：使用这些数据，训练一个模型，使其能够预测回复的质量评分。
  - **应用于强化学习**：在训练过程中，模型生成回复后，奖励模型对其进行评估，给予奖励信号，指导模型优化。

**总结**

- **强化学习必须有奖励信号**，它是智能体学习的关键驱动力。
- **奖励信号的来源**可以是：
  - **奖励函数**：手工设计，适用于评价标准明确的任务。
  - **奖励模型**：通过训练得到，适用于评价标准复杂、主观的任务。
- **是否需要奖励模型取决于具体的任务需求**：
  - **简单、规则明确的任务**：奖励函数足以满足需求。
  - **复杂、主观的任务**：需要奖励模型来捕捉人类的评价标准。



因此，强化学习一定需要奖励信号，但不一定必须使用奖励模型。**在很多传统的强化学习应用中，手工设计的奖励函数已经足够有效。然而，在某些复杂领域，特别是涉及人类主观评价的任务中，奖励模型变得必要。



**三、直接偏好优化（Direct Preference Optimization，DPO）**

直接偏好优化（DPO）是一种利用人类偏好数据直接优化策略的方法，旨在使模型的行为更符合人类的期望。与传统的强化学习相比，DPO不需要训练单独的奖励模型，而是直接使用人类的偏好来指导模型的优化。 

 

**1. 关键组成部分**

**（1）策略模型（Policy Model）**

- **定义**：需要优化的模型，决定智能体在每个状态下采取的动作。
- **表示**：策略模型记为 πₜθ，其中 θ 是模型的参数。

**（2）人类偏好数据**

- **定义**：由人类对模型行为的偏好反馈，通常以成对比较的形式。
- **表示**：给定同一输入，模型生成两个不同的输出，称为 A 和 B。人类评估者选择他们更喜欢的输出。

**（3）参考策略（Reference Policy）**

- **定义**：初始的未优化策略模型，用于在训练过程中稳定新策略的行为。
- **作用**：防止策略模型在优化过程中偏离初始行为过远，保持模型的稳定性。

**（4）损失函数（Loss Function）**

- **定义**：基于人类偏好数据构建的损失函数，用于优化策略模型的参数。
- **目标**：最大化策略模型生成被人类偏好选择的输出的概率。

**2. 举例说明**

**例子：通过DPO优化小车的导航策略**

**背景**：

- **环境**：一个二维的网格世界，智能小车需要从起点到达终点，途中可能有障碍物。

- **状态（s_t）**：小车当前的位置坐标 (x, y)。

- **动作（a_t）**：小车可以选择的移动方向：上、下、左、右。

- **目标**：不仅希望小车能够最短路径到达终点，还希望其行驶路径符合人类的偏好，例如避免特定区域（如危险地带）或经过风景优美的路线。

  **步骤**：

**（1）初始策略模型**

- **设定**：小车有一个初始的策略模型 π₀，它可能是基于最短路径算法生成的。
- **问题**：这个策略可能会让小车经过危险区域，或错过风景优美的路线，不符合人类的偏好。

**（2）收集人类偏好数据**

- **生成候选路径**：
  - 给定起点和终点，策略模型 π₀ 生成不同的行驶路径。
- **人类评估者进行比较**：
  - **安全性**：避免危险区域。
  - **美观性**：经过风景优美的地方。
  - **效率**：路径长度适中。
  - 对于每一对候选路径 A 和 B，人类评估者根据自己的偏好选择他们更喜欢的路径。
  - **偏好因素**可能包括：

**（3）构建数据集**

- **数据形式**：[(起点, 终点), 路径A, 路径B, 人类偏好]
- **示例**：
  - **起点**：坐标 (0, 0)
  - **终点**：坐标 (5, 5)
  - **路径A**：经过危险区域但路径最短。
  - **路径B**：稍长一些，但避开危险区域并经过美景。
  - **人类偏好**：选择路径B。

**（4）定义损失函数**

- **目标**：优化策略模型 πₜθ，使其更倾向于生成被人类偏好选择的路径。

- **损失函数设计**：

  - 如果人类偏好路径 B，但策略模型更倾向于路径 A，那么 Δ > 0，损失函数会较大，促使模型调整参数。

  - 通过最小化损失函数，使策略模型更倾向于生成被人类偏好的路径。

  - **Δ = s_θ(A) - s_θ(B)**，表示策略模型对路径 A 和 B 的偏好得分差异。

  - **s_θ(X)** 是策略模型给路径 X 计算的得分（例如，路径的对数概率）。

  - **σ(Δ)** 是 Sigmoid 函数，将差值映射到 (0,1) 区间。

  - 对于每个偏好数据：

    ```
    L(θ) = -log(σ(Δ))
    ```

    其中：

  - **直观理解**：

#### **（5）加入参考策略**

- **参考策略 π₀**：初始的策略模型。

- **正则化项**：防止策略模型偏离初始策略过远，保持路径的合理性。

  ```
  R(θ) = KL(πₜθ || π₀)
  ```

  其中：

  - **KL** 表示 Kullback-Leibler 散度，衡量策略模型与参考策略之间的差异。

- **总损失函数**：

  ```
  L_total(θ) = L(θ) + λ * R(θ)
  ```

  - **λ** 是权衡损失和正则化项的超参数，控制模型偏离初始策略的程度。

#### **（6）优化策略模型**

 

- **最小化总损失函数 L_total(θ)**，更新策略模型的参数 θ。
- **迭代训练**：重复上述过程，直到模型在验证数据上的表现达到预期。

#### **（7）结果**

- **优化后的策略模型 πₜθ**：
  - 更倾向于为小车规划符合人类偏好的路径。
  - 在遇到类似的导航问题时，能够自动选择既安全又美观的路线。

**3. DPO的优势**

- **直接利用人类偏好数据**：不需要额外训练奖励模型，减少了复杂性。
- **训练稳定**：通过引入参考策略，防止模型过度拟合，保持行为合理性。
- **效率更高**：相比于传统的强化学习方法，DPO的训练过程更简单，资源消耗更少。
- **适用性强**：适用于需要根据人类偏好调整策略的任务。

**4. 总结**

- **DPO**是一种有效的策略优化方法，通过直接利用人类的偏好数据，优化智能体的策略，使其行为更符合人类的期望。
- **在小车导航的例子中**，DPO方法帮助智能体学习如何规划既安全又美观的路径，提升了用户体验。
- **关键思想**：
  - **利用人类偏好数据构建损失函数**，直接优化策略模型。
  - **引入参考策略作为正则化**，确保模型的稳定性。

**四、各种训练/微调技术采用的技术**

1. **SFT（Supervised Fine-Tuning，有监督微调）**

   - 是否属于强化学习：不属于强化学习。

   - 归属：有监督学习。

   - **解释：**

     SFT是对预训练模型（如大型语言模型）进行有监督的微调。它使用已标注的数据（输入-输出对）对模型进行训练，使其在特定任务上表现更好。模型直接学习输入与期望输出之间的映射关系，不涉及强化学习的概念。



2. **ReFT（Reinforced Fine-Tuning，强化微调）**

- 是否属于强化学习：属于强化学习。

- **使用奖励函数还是奖励模型：\**使用\**奖励函数**。

- **解释：**

  ReFT在SFT的基础上，使用强化学习算法（如PPO）进一步优化模型。在ReFT中，奖励信号通常是通过**明确的奖励函数**计算的，例如根据模型输出与标准答案的匹配程度。模型根据奖励函数提供的即时奖励信号，使用强化学习算法调整参数，以提升性能。这种方法适用于有明确评价标准的任务，例如数学问题求解。



3. **RLHF（Reinforcement Learning from Human Feedback，基于人类反馈的强化学习）**

- 是否属于强化学习：属于强化学习。

- **使用奖励函数还是奖励模型：\**使用\**奖励模型**。

- **解释：**

  RLHF结合了SFT和强化学习。在SFT之后，模型通过收集**人类反馈**来了解其输出的质量。人类对模型的输出进行评分或排序，这些反馈用于训练一个**奖励模型**。该奖励模型可以预测人类对不同输出的偏好或满意度。在强化学习阶段，模型使用奖励模型提供的奖励信号，利用算法（如PPO）优化其策略，使输出更符合人类期望。



4. **RLAIF（Reinforcement Learning from AI Feedback，基于AI反馈的强化学习）**

- 是否属于强化学习：属于强化学习。

- **使用奖励函数还是奖励模型：\**使用\**奖励模型**。

- **解释：**

  RLAIF与RLHF类似，但区别在于奖励信号的来源。RLAIF使用预先训练的**AI模型**（而非人类）对主模型的输出进行评价，提供奖励信号。这个AI模型充当**奖励模型**的角色，通过预测输出的质量或符合性，引导主模型进行优化。这种方法减少了对人类反馈的依赖，但效果取决于AI反馈模型的质量。



5. **DPO（Direct Preference Optimization，直接偏好优化）**

- 是否属于强化学习：不属于强化学习。

- 归属：有监督学习，直接优化模型参数。

- **解释：**

  DPO方法不使用强化学习算法，而是直接利用人类偏好数据进行**监督学习**。在收集到人类对模型输出的偏好后，构建一个损失函数，使模型倾向于生成被人类偏好的输出。通过最小化这个损失函数，直接优化模型参数。这种方法避免了强化学习的复杂性，训练过程更稳定，适用于有大量人类偏好数据的场景。



6. **PPO（Proximal Policy Optimization，近端策略优化）**

- 是否属于强化学习：属于强化学习。

- **使用奖励函数还是奖励模型：\**取决于应用场景，可以使用\**奖励函数**或**奖励模型**。

- **解释：**

  PPO是一种强化学习算法，用于更新策略网络。它通过限制策略更新的幅度，确保训练的稳定性和效率。PPO本身是一种算法工具，常用于需要强化学习的模型，如ReFT和RLHF。它可以根据不同的奖励信号进行优化：

  - **使用奖励函数：**当奖励信号来自明确的计算（如ReFT中的正确答案比较）时，PPO使用奖励函数。
  - 使用奖励模型：当奖励信号来自训练的奖励模型（如RLHF中的人类反馈模型）时，PPO使用奖励模型。



## **ReFT简介**

### OpenAI的 ReFT

监督式微调 (SFT) 涉及采用预先训练的模型，并使用监督式学习技术利用额外数据对其进行调整。在实践中，当目标是使模型的输出或格式与特定数据集保持一致，或确保模型遵循某些指令时，SFT 效果最佳。

虽然监督微调和强化微调都依赖于标记数据，但它们的使用方式不同。在 SFT 中，标记数据直接驱动模型的更新。模型将其视为目标输出，并调整其参数以缩小其预测输出与已知正确答案之间的差异。

在 RFT 中，模型对标签的接触是间接的，因为它主要用于创建奖励信号，而不是直接目标。这就是为什么模型在 RFT 中需要的标记数据更少的原因——模型旨在寻找模式来产生我们想要的输出，而不是直接产生我们的输出，这保证了更强的*泛化倾向*。

我们用这张表来总结一下差异：

| 特征                   | 监督微调（SFT）                                        | 强化微调（RFT）                                              |
| ---------------------- | ------------------------------------------------------ | ------------------------------------------------------------ |
| **核心理念**           | 直接在标记数据上训练模型以匹配所需的输出。             | 使用“ Grader ”为模型提供奖励以生成所需的输出。               |
| **标签使用**           | 直接作为模型模仿的目标。                               | 间接用于为模型创建奖励信号。                                 |
| **数据效率**           | 需要更多标记数据。                                     | 由于泛化，可能需要较少的标记数据。                           |
| **人类参与**           | 仅在初始数据标记中。                                   | 仅在设计“评分器”功能。                                       |
| **概括**               | 可能过度拟合训练数据，限制泛化。                       | 由于关注模式和奖励，因此具有更高的概括潜力。                 |
| **与人类偏好保持一致** | 有限，因为它完全依赖于模仿标记数据。                   | 如果“评分器”准确反映人类偏好，则可以更好地进行调整。         |
| **示例**               | 微调语言模型以生成特定类型的文本格式（如诗歌或代码）。 | 训练语言模型来生成创意内容，并由“评分员”根据原创性和连贯性进行评判。 |

训练数据范例如下，训练中，并不把答案直接放入到训练集。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/3.png)

训练过程中，模型可能包含或者不包含正确答案：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/4.png)

创建训练集和校验集的jsonal文件：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/5.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/6.png)

构建奖励函数：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/7.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/8.png)

这个JSON文件（grader.json）的内容定义了一个评分系统的配置。具体来说，这个配置文件定义了如何对某个对象进行评分。让我们逐行解析这个文件的内容：

1. `"type": "object-grader"`：

   - 这行定义了评分器的类型为“object-grader”，表示这是一个用于评分对象的评分器。

2. `"property_graders": { ... }`：

   - 这个字段定义了对对象属性进行评分的具体规则。在这个例子中，针对对象的属性“genes”有特定的评分规则。

3. `"genes": { "type": "inverse-rank-grader" }`：

   - 这个定义了对属性“genes”的评分器类型为“inverse-rank-grader”。“inverse-rank-grader”通常意味着评分是基于逆序排名的。
   - 逆序排名评分器（inverse-rank-grader）通常的工作原理是根据元素在列表中的位置来计算得分。位置越靠前，得分越高。例如，排名第一的元素可能得分为1，第二名得分为0.5，第三名得分为0.33，等等。

4. `"calculate_output": "genes"`：

   - 这行定义了评分器最终输出的计算方式，是根据“genes”属性来计算输出的分数。

     

     总结：
     这个JSON配置文件定义了一个评分系统，使用“inverse-rank-grader”对对象的“genes”属性进行评分，并根据这个评分来计算最终的输出。具体来说，“inverse-rank-grader”评分器根据“genes”属性中的元素在列表中的位置来计算得分，位置越靠前得分越高。

     结合之前提到的得分情况（0.7分），可以推测评分机制可能是基于“inverse-rank-grader”的逆序排名得分。例如，如果“FOXE3”在列表中的排名较高（比如第一或第二位），那么它可能会得到一个较高的分数。具体的得分计算规则需要查看“inverse-rank-grader”的实现细节来确定。

设置训练超参：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/9.png)

训练结果：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/10.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/11.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/12.png)

### 字节的ReFT

先看ReFT论文中的流程图：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUpgIIJic3v3UHiaRriaapjX2omaoJWqB4dr3dQyGEkDMjjR5JeI8LibRVX9icuCAiarOA0kMgPfWhoqiamg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

如上图所示，ReFT，该框架结合了监督微调（Supervised Fine-Tuning, SFT）和强化微调（Reinforced Fine-Tuning, ReFT）的方法。以下是对图中各部分的详细解释：

1. **监督微调（Supervised Fine-Tuning）**：

   - **模型（Model）**：初始模型通过多个SFT周期（epochs）在训练数据上进行训练。训练数据包含问题（x），推理链（CoT，e）和答案（y）。
   - **SFT Epochs**：模型在训练数据上进行多个周期的训练，以学习如何从问题（x）和推理链（e）生成正确的答案（y）。
   - **不同阶段的模型**：图中展示了经过不同训练阶段后的模型表情变化，表示模型逐渐变得更好。

2. **强化微调（Reinforced Fine-Tuning）**：

   - **预热阶段（Warm-up）**：在进入强化学习之前，模型通过SFT进行预热。
   - **问题（question）**：模型接受一个输入问题（x）。
   - **On-Policy Sampling**：在策略内采样，模型生成一个推理链和答案（e', y'）。
   - **Golden Reward**：对生成的答案（y'）与正确答案（y）进行比较，给予奖励信号。如果答案正确，给予正奖励（√），否则给予负奖励（×）。
   - **强化学习（Reinforcement Learning）**：利用奖励信号来调整模型参数，以提高模型在相同数据上的表现。

3. **最终策略（Final Policy）**：

   - 经过SFT和ReFT训练后，模型形成最终策略，可以更准确地回答问题。

     图例说明了在GSM8K数据集上，一个问题（x）、推理链（e）和答案（y）的示例。通过多个SFT周期对训练数据进行迭代，并使用ReFT方法从SFT进行预热，然后在相同数据上进行强化学习训练。

## **TPO的流程**

先看Thought Preference Optimization（TPO）的流程：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUpgIIJic3v3UHiaRriaapjX2obrFTylPby9mlhw3NUiaJicSIAianv6WrYjTbaCe24w2nic8xrHLOUo4VLg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

- TPO 方法由三个主要部分组成：
  1. SFT（有监督微调）：提供了模型的基础。
  2. 思维生成（Thought Generation）：让模型在回答前进行内部思考。
  3. DPO（直接偏好优化）：利用 AI 判别模型生成的偏好对，直接优化模型参数。
- TPO 的创新之处在于：
  - 引入了思维生成，增强模型的推理和规划能力。
  - 利用 AI 判别模型的反馈，降低了对人类偏好数据的依赖。
  - 使用 DPO 方法，简化了训练流程，提高了训练效率。



**TPO = SFT + 思维生成（Thought Generation）+ DPO（偏好优化）**

需要指出的是，**DPO 方法（Direct Preference Optimization，直接偏好优化）** 通常直接使用人类的偏好数据，并且 **引入了参考模型**。在传统的应用中，DPO 方法依赖于人类对模型输出的偏好反馈，并通过 **参考模型** 来构建损失函数，直接优化模型参数。然而，**TPO 方法（Thought Preference Optimization，思维偏好优化）** 将 DPO 的应用扩展到了使用 **AI 模型生成的偏好数据**，这一创新使得模型能够在缺乏人类偏好数据的情况下，仍然利用偏好优化方法进行训练。需要强调的是，对于 DPO 方法而言，**参考模型和偏好数据的结合是关键**。无论偏好数据的来源是人类还是 AI 模型，DPO 方法都通过 **参考模型** 和偏好数据来构建损失函数，直接优化模型，而 **不涉及强化学习算法**。 
**上面 TPO 方法的具体解释如下：**

**1. SFT（Supervised Fine-Tuning，有监督微调）：**

- **起点模型（Seed Model）**：TPO 方法以一个已经过有监督微调的预训练模型作为基础（即经过 SFT 的模型），例如 Llama-3-8B-Instruct。

  **2. 思维生成（Thought Generation）：**

- **引入思维过程**：在生成最终回答之前，模型通过特定的提示（Prompt），被引导生成内部的思维过程（Thought）。

- **思维与回答的分离**：生成的输出分为 **思维部分** 和 **回答部分**，思维部分在最终呈现给用户时被隐藏。

  **3. DPO（Direct Preference Optimization，直接偏好优化）：**

- **参考模型的引入**：使用经过 SFT 的模型作为 **参考模型**，参数固定不更新。

- **偏好数据来源**：偏好对（Preference Pairs）来自于 **AI 判别模型** 对模型输出的评估，而非传统的人类偏好数据。

- **AI 判别模型**：

  - **Self-Taught Evaluator（STE）**：基于大型语言模型（如 Llama-3-70B-Instruct），用于对两个回答进行比较，输出偏好结果。

  - **ArmoRM**：一个奖励模型，直接对单个回答进行评分。

    **优化过程：**

- **生成候选输出**：模型针对每个输入指令，生成多个包含 **思维和回答** 的候选输出。

- **评估回答部分**：将 **回答部分** 输入到 **AI 判别模型**，进行评分或偏好比较。

- **构建偏好对**：根据评估结果，选出 **最佳和最差回答**，形成偏好对（Chosen 和 Rejected）。

- **使用 DPO 优化**：利用这些偏好对，结合 **参考模型**，使用 DPO 方法构建损失函数，直接优化模型参数。

## **PPO和DPO的本质区别**

### 1. 强化学习的本质


强化学习就像训练一只小狗做动作。

**比方说：**

- **训练小狗**：当小狗做对了动作（比如坐下、握手），我们就给它一块小零食作为奖励；当它做错了，我们就不给奖励。

- **目的**：经过多次训练，小狗会明白，做对了就有奖励，于是它会更愿意做我们希望的动作。

  **在机器学习中：**

- **模型与环境互动**：模型（相当于小狗）在某个环境中，根据当前的情况，选择一个动作。

- **获得奖励或惩罚**：环境会根据模型的动作，给出一个奖励（奖励值可以是正的，也可以是负的）。

- **优化目标**：模型的目标是学习到一种策略，使得它在与环境的长期互动中，累积的奖励最大化。

  **简单理解：**

- **强化学习 = 试错学习 + 奖励机制**

- 模型通过不断尝试不同的动作，学习到哪些行为能够获得更多的奖励。

  **举个例子：**

- 游戏中的机器人：想象一个机器人在迷宫中寻找出口。

  - **到达出口**：奖励 +10 分。
  - **撞墙**：奖励 -1 分。
  - **其他情况**：奖励 0 分。

- 行动选择：

  - 每走一步，机器人会根据当前的位置（状态），选择向上、下、左、右移动（动作）。

- 模型目标：

  - 学会一条最优路径，快速找到出口，获得最高的累计奖励。

### 2. 偏好数据的直接优化（DPO）的本质

**直接偏好优化（DPO）** 是一种直接利用偏好数据和参考模型来优化模型的方法。

**比方说：**

- **模型生成两个回答**：对于同一个问题，当前模型（Policy Model）生成了回答 A 和回答 B。

- **获得偏好反馈**：我们请人类评估者或辅助的 AI 模型告诉我们，哪个回答更好。

  - 例如，人类评估者说：“回答 A 比回答 B 好。”

- **引入参考模型**：

  - **参考模型（Reference Model）**：通常是经过监督微调（SFT）的初始模型，其参数在 DPO 训练过程中保持固定不变。
  - **作用**：提供一个稳定的概率基准，防止当前模型在优化过程中偏离预训练的语言分布。

- **构建损失函数**：

  - **利用当前模型和参考模型**，对两个回答的对数概率进行计算。
  - **损失函数**：设计一个损失函数，使当前模型更倾向于生成被人类偏好的回答，同时限制模型的更新幅度，保持训练稳定性。

- **直接优化模型**：

  - 通过最小化损失函数，直接调整当前模型的参数，使其更倾向于生成被偏好的回答 A。

    **与强化学习的区别：**

- **不需要复杂的奖励函数**：DPO 不需要设计一个数值化的奖励函数或与环境交互的机制，只需利用偏好比较的信息和参考模型的概率基准。

- **不需要环境交互**：DPO 直接使用已有的偏好数据和参考模型进行优化，无需模型与环境持续交互，也不涉及即时奖励信号。

  **简单理解：**

- **DPO = 利用偏好比较和参考模型直接调整模型参数**

- 模型根据哪些输出被偏好，结合参考模型的概率信息，直接优化自身，倾向于生成更符合人类偏好的输出。

  **举个例子：**

- **训练聊天机器人**：

  1. **模型生成两个回答**：针对用户提出的问题，当前模型生成了两个候选回答。

     - **回答 1**：“好的，我会帮您查询相关信息。”
     - **回答 2**：“我不知道，你自己去查吧。”

  2. **获取偏好数据**：人类评估者比较两个回答，选择更好的一个。

     - 人类评估者表示更喜欢 **回答 1**，因为它更有礼貌、服务态度更好。

  3. **引入参考模型**：

     - 使用经过 SFT 的初始模型作为参考模型，其参数固定。

  4. **构建损失函数**：

     - 计算 **当前模型** 和 **参考模型** 对 **回答 1** 和 **回答 2** 的对数概率。
     - 设计损失函数，鼓励当前模型提高对被偏好回答（回答 1）的概率，降低对不被偏好回答（回答 2）的概率，同时参考模型的信息用于稳定训练。

  5. **直接优化模型**：

     - 通过最小化损失函数，更新当前模型的参数，使其更倾向于生成类似 **回答 1** 的内容。

       **总结：**

- **DPO 方法** 通过结合 **人类偏好数据** 和 **参考模型**，在监督学习的框架下直接优化模型参数。

- **参考模型** 的作用是提供一个稳定的基准，防止模型过度偏离预训练的语言分布，确保训练过程的稳定性和生成质量。

- **与强化学习的区别**：

  - DPO 不涉及与环境的交互和即时奖励信号，避免了强化学习中的复杂性和不稳定性。
  - DPO 的优化过程更直接、更稳定，适合在有大量偏好数据的场景下使用。

### **3. 关于 DPO 中的“交互”**


在 DPO 的描述中，模型需要生成多个回答，然后人类评估者或辅助的 AI 判别模型提供偏好反馈（**注：在 TPO 的 DPO 部分，偏好数据可能来自 AI 模型**）。这似乎也涉及到一些交互。那么，DPO 不是也有交互吗？

**的确，DPO 涉及到模型与人类评估者或 AI 判别模型之间的“交互”，因为需要收集偏好数据。然而，这种交互与强化学习中的交互有本质的不同。**

#### **1. DPO 中的“交互”**

- 数据收集阶段的交互：
  - 在 DPO 中，模型会为每个输入生成多个候选输出（如回答）。
  - **人类评估者或 AI 判别模型**对这些候选输出进行偏好标注，形成偏好对（首选和非首选响应）。
  - **特点**：这种交互是一次性的、离线的，用于构建训练数据集。数据收集完成后，进入模型训练阶段。
- 训练阶段的优化：
  - 一旦偏好数据收集完成，模型的训练过程就是基于这些偏好对，**结合参考模型**，使用监督学习的方法直接优化模型参数。
  - **训练过程中不再需要与人类评估者或环境进行交互**，参考模型的参数在训练中保持固定。

#### **2. 强化学习中的交互**



- 持续的环境交互：
  - 在强化学习（如 PPO）中，模型在训练过程中需要与环境进行持续、动态的交互。
  - 模型根据当前状态选择动作，环境反馈新的状态和奖励信号，模型根据这些信息更新策略。
- 训练过程的复杂性：
  - 强化学习的训练是在线的、迭代的，模型需要不断地试错来学习最优策略。
  - 涉及到 **状态、动作、奖励、价值函数、策略更新** 等复杂概念。

#### **3. 两者的区别**

- 交互的性质和阶段不同：

  - **DPO** 的交互发生在训练前的数据收集阶段，是 **静态的、离线的**。在训练过程中，模型只需利用已获得的偏好数据和参考模型进行优化。
  - **强化学习** 的交互发生在训练过程中，是 **动态的、在线的**。模型需要与环境持续交互，获取即时奖励信号。

- 训练方法不同：

  - **DPO** 使用监督学习方法，结合 **参考模型**，利用偏好对构建损失函数，直接优化模型参数。
  - **强化学习** 需要策略梯度或价值函数等方法，根据环境反馈的奖励信号更新策略，通常采用强化学习算法（如 PPO）。

- 复杂性和稳定性：

  - **DPO** 的训练过程相对简单、稳定，因为它是基于监督学习，参考模型的引入进一步稳定了训练过程。
- **强化学习** 的训练过程更复杂，可能存在不稳定性，需要精心调整超参数和训练策略。

#### **4. 举个例子**


**DPO 的例子：**

- **步骤 1：数据收集**

  - 模型生成两个回答：

    - **回答 1**：“好的，我会帮您查询相关信息。”
  - **回答 2**：“我不知道，你自己去查吧。”
    
  - **人类评估者或 AI 判别模型**对这两个回答进行比较，偏好 **回答 1**。

- **步骤 2：模型优化**

  - **引入参考模型**：使用经过 SFT 的模型作为 **参考模型**，参数固定不更新。
  - 构建损失函数：
    - 利用 **当前模型** 和 **参考模型** 对 **回答 1** 和 **回答 2** 的对数概率进行计算。
    - 根据偏好数据，设计损失函数，鼓励当前模型提高对被偏好回答（回答 1）的概率，降低对不被偏好回答（回答 2）的概率。
  - **优化模型**：通过最小化损失函数，直接调整当前模型的参数，使其更倾向于生成被偏好的输出。

- **特点**：

  - **数据收集和模型训练是分开的**。

  - **训练过程中不需要与人类评估者或环境交互**，参考模型在训练中提供稳定的基准。

    **强化学习的例子：**

- **模型与环境持续交互**：

  - 模型在训练过程中，不断与环境交互，选择动作，观察反馈，获取即时奖励。
  - 例如，**训练一个游戏 AI**，模型需要在游戏环境中不断尝试不同的行动，根据得分（奖励）更新策略。

- **特点**：

  - **训练过程需要持续的、在线的交互**。
  - **模型的行为会影响后续的状态和奖励**，训练过程更加复杂，需要处理环境的不确定性。

#### **5. 总结**

- **直接偏好优化（DPO）**：
  - **交互发生在数据收集阶段**，是离线的、静态的。偏好数据收集完成后，训练过程不再需要交互。
  - **训练过程中使用监督学习方法**，结合参考模型，直接利用偏好数据优化模型。
  - **训练过程简单、稳定**，不涉及环境交互，参考模型的引入确保了训练的稳定性。
- **强化学习**：
  - **交互发生在训练过程中**，是在线的、动态的。模型需要与环境持续交互，获取即时奖励信号。
  - **模型通过与环境的持续交互**，基于奖励信号更新策略，需要处理环境的不确定性。
  - **训练过程复杂**，可能存在不稳定性，需要精心调整训练策略和超参数。



---

# Part 4: 七种微调技术对比总表

> *原文来自 Comparison-of-Various-Fine-Tuning-Methods*


## 几种技术对比

| **比较维度**   | **SFT（有监督微调）**                            | **ReFT（强化微调）**                                         | **RLHF（基于人类反馈的强化学习）**                        | **DPO（直接偏好优化）**                                      | **PPO（近端策略优化）**                            | **RLAIF（基于 AI 反馈的强化学习）**                          | **TPO（思维偏好优化）**                                      |
| -------------- | ------------------------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **概念**       | 使用标注数据对预训练模型进行有监督的微调         | 在 SFT 基础上，**结合参考模型**，使用自动化评估和 DPO 方法直接优化模型 | 在 SFT 基础上，结合人类反馈和 PPO 算法进行强化学习        | 使用人类偏好数据和**参考模型**，直接优化模型参数，避免强化学习复杂性 | 一种强化学习算法，限制策略更新幅度，保持训练稳定性 | 在 SFT 基础上，使用 AI 模型的反馈，结合 PPO 算法进行强化学习 | 模型在回答前进行内部思考，结合**参考模型**和偏好数据优化模型参数 |
| **实现方法**   | 收集标注数据，最小化模型输出与目标输出之间的损失 | SFT 后，采样模型输出，利用自动化评估或偏好数据，**结合参考模型**使用 DPO 方法直接优化 | SFT 后，收集人类反馈，训练奖励模型，使用 PPO 算法优化策略 | 收集人类偏好数据，**结合参考模型**，构建损失函数，直接优化模型参数 | 与环境交互，计算优势函数，使用剪辑目标函数优化策略 | SFT 后，使用辅助 AI 模型评估，训练奖励模型，使用 PPO 优化策略 | 使用提示引导模型生成思维和回答，利用**参考模型**和偏好数据，使用 DPO 方法优化 |
| **数据需求**   | 大量高质量标注数据                               | 标注数据 + 自动化评估程序或偏好数据 + **参考模型**           | 标注数据 + 大量人类反馈 + 奖励模型                        | 大量人类偏好数据 + **参考模型**                              | 与环境交互产生的数据                               | 标注数据 + 辅助 AI 模型 + 奖励模型                           | 输入数据 + 判别模型 + **参考模型**                           |
| **人类参与**   | 高，需要人类标注数据                             | 低，无需额外人类反馈（如偏好数据来自自动化评估）             | 高，需要大量人类反馈                                      | 高，需要人类偏好数据                                         | 取决于任务，一般无需人类参与                       | 低，无需人类反馈，依赖 AI 模型                               | 低，无需人类思维标注，偏好数据可来自 AI 模型                 |
| **参考模型**   | **否**                                           | **是**，利用参考模型稳定训练                                 | **否**                                                    | **是，关键组成部分**                                         | **否**                                             | **是**，用于稳定训练和对比                                   | **是，关键组成部分**                                         |
| **思维过程**   | 否                                               | 否                                                           | 否                                                        | 否                                                           | 否                                                 | 否                                                           | **是**，模型在回答前生成思维                                 |
| **奖励机制**   | 基于损失函数，最小化预测输出与目标输出的差异     | 利用自动化评估或偏好数据，**结合参考模型构建损失函数**，直接优化 | 人类反馈训练的奖励模型评估输出，给予奖励                  | 基于人类偏好数据和**参考模型**构建损失函数，直接优化模型参数 | 环境提供奖励，计算优势函数，指导策略更新           | 辅助 AI 模型评估输出，训练奖励模型，给予奖励                 | 通过评估回答质量，利用**参考模型构建损失函数**，优化模型参数 |
| **训练复杂度** | 低                                               | 中，需结合参考模型和偏好数据进行优化，训练稳定               | 高，多阶段训练，需要人类反馈和强化学习                    | 中，避免了强化学习的复杂性，训练稳定                         | 中，需要调整超参数，训练稳定                       | 中，需要辅助 AI 模型、奖励模型和强化学习                     | 高，多次迭代训练，优化思维和回答，需考虑参考模型和偏好数据   |
| **优势**       | 简单直接，易于实现                               | 训练稳定，直接优化目标，适用于有自动化评估的任务             | 输出更符合人类期望，提高安全性和自然度                    | 训练稳定，直接优化目标，效率高，避免强化学习复杂性           | 训练稳定性高，样本效率高                           | 降低人类反馈成本，可规模化训练                               | 提升复杂任务表现，无需人类思维数据，多任务适用               |
| **缺点**       | 数据需求高，泛化能力有限                         | 依赖自动化评估或偏好数据的质量，参考模型选择需谨慎           | 人力成本高，训练复杂，需要多阶段训练                      | 依赖偏好数据质量和参考模型的设计                             | 超参数调节复杂，样本效率较低                       | 依赖辅助模型质量，可能引入偏差                               | 训练复杂度高，判别模型质量影响大，思维过程可能不可控         |
| **适用场景**   | 有大量标注数据的任务                             | 有明确评估标准，可自动计算评估或有偏好数据的任务             | 需要高质量输出，强调人类价值观和主观评价的任务            | 有大量人类偏好数据，需简化训练流程的任务                     | 强化学习任务，需与环境交互                         | 无法获得人类反馈但有可靠的 AI 模型评估的任务                 | 复杂任务，多步骤推理，缺乏人类思维标注数据的任务             |

**ReFT（Reinforced Fine-Tuning，强化微调）：**

- **组成**：ReFT = SFT + **参考模型** + DPO
- **过程**：在有监督微调（SFT）的基础上，引入**参考模型**（通常为经过 SFT 的初始模型，参数固定不更新），使用 DPO（直接偏好优化）方法，结合自动化评估或偏好数据，直接优化模型参数。
- **评估方式**：通常通过**自动化程序或偏好数据**对模型输出进行评估，利用**参考模型**和评估结果构建损失函数，直接优化模型。


**RLHF（Reinforcement Learning from Human Feedback，基于人类反馈的强化学习）：**

- **组成**：RLHF = SFT + PPO + 人类反馈
- **过程**：在 SFT 的基础上，使用 PPO（近端策略优化）进行强化学习，**引入奖励模型**，其奖励信号来自**人类反馈**。模型通过与环境交互，利用奖励信号更新策略。
- **评估方式**：人类对模型输出进行评价，构建偏好数据，训练**奖励模型**。在强化学习过程中，奖励模型对模型输出进行评估，提供奖励信号，指导模型优化。


**DPO 方法（Direct Preference Optimization，直接偏好优化）：**

- **组成**：DPO 方法 = SFT + **参考模型** + DPO
- **过程**：在 SFT 的基础上，引入**参考模型**（参数固定不更新），使用 DPO 方法，利用**人类偏好数据**和参考模型，直接优化模型参数。
- **评估方式**：利用人类偏好数据，结合**参考模型**，构建损失函数，直接优化模型参数，使模型倾向于生成被人类偏好的输出。


**RLAIF（Reinforcement Learning from AI Feedback，基于 AI 反馈的强化学习）：**

- **组成**：RLAIF = SFT + PPO + **AI 反馈** + 奖励模型
- **过程**：在 SFT 的基础上，使用 PPO 进行强化学习，**引入奖励模型**，其奖励信号来自**AI 模型的反馈**。模型通过与环境交互，利用 AI 模型评估的奖励信号更新策略。
- **评估方式**：辅助的 AI 模型对模型输出进行评价，生成偏好数据，训练**奖励模型**。在强化学习过程中，奖励模型对模型输出进行评估，提供奖励信号，指导模型优化。


**TPO（Thought Preference Optimization，思维偏好优化）：**

- **组成**：TPO = SFT + 思维生成（Thought Generation）+ **参考模型** + DPO
- **过程**：在 SFT 的基础上，引入**思维生成**，即模型在输出回答前生成内部的思维过程。然后，使用 DPO 方法，结合**参考模型**，直接优化模型参数，偏好数据来自**AI 判别模型的反馈**。
- **评估方式**：利用**AI 判别模型**对模型输出的**回答部分**进行评价，形成偏好对（优选和劣选）。结合**参考模型**，使用 DPO 方法构建损失函数，直接优化模型参数，提升模型性能。

## LoRA/QLoRA 微调机制与 Adapter 合并策略

### LoRA 的原理

LoRA（Low-Rank Adaptation）的核心思想是：给预训练权重 W 增加一个低秩的增量 BA，而不是直接修改所有参数。

QLoRA 在此基础上进一步优化——将大型预训练模型先量化成较低精度（通常是4-bit），再在其之上训练规模很小的适配器（adapter）参数，从而在显著减少显存占用的同时，仍能对模型进行有效的微调。

其关键要素包括：

1. **预训练权重 (Pretrained Weights)**：原始预训练模型的权重 W，QLoRA 会将这些预训练权重量化到4-bit，大幅缩小模型体积并减少显存占用。

2. **适配器 (Adapter) 参数 (A 和 B)**：LoRA/QLoRA 中用到的两组小矩阵 A 和 B，以16-bit的形式存储和训练。适配器的参数规模远小于全部模型权重，训练时只需为这小部分参数保存梯度和优化器状态。在最初训练时，B 被初始化为 0 矩阵，A 则随机初始化。

3. **前向计算 (Forward Pass)**：h = W x + B A x，模型的输出不仅包含原来预训练权重 W 的贡献，也会额外加上由适配器 B A 乘以输入 x 得到的增量。

4. **权重合并 (Merged Weights)**：在推理阶段可以将 W 与 B A 合并成一个新的权重矩阵 W_merged 进行计算。

![images](images/qlora_perf_1.png)

### 低秩矩阵表示的数学示例

以 4×4 小矩阵为例说明 LoRA 的低秩更新原理：

**原始权重** W（4×4）：
```
W = [[1, 2, 3, 4],
     [2, 3, 4, 5],
     [3, 4, 5, 6],
     [4, 5, 6, 7]]
```

选择 r=2（低秩），则 B 为 (4×2)，A 为 (2×4)：
```
B = [[0.1, 0.2],    A = [[2.0, 0.0, 0.0, 1.5],
     [0.0, 0.3],         [0.0, 1.0, 2.0, 1.0]]
     [0.1, 0.1],
     [0.0, 0.2]]
```

BA 结果为 4×4 矩阵（秩不超过2）：
```
BA = [[0.2, 0.1, 0.4, 0.3],
      [0.0, 0.3, 0.6, 0.3],
      [0.2, 0.1, 0.4, 0.3],
      [0.0, 0.2, 0.4, 0.2]]
```

微调后权重 W_merged = W + BA，通过两个小矩阵的乘积完成对原始权重的修正。当 r 比 d 小很多时，B 和 A 的参数量远小于 d×d，节省大量训练开销与存储。

### Adapter 合并策略与量化对精度的影响

![images](images/qlora_perf_2.png)

以下是四种不同的 Adapter 部署策略及其效果对比：

| 策略 | 做法 | 困惑度(PPL) | 说明 |
|------|------|:-----------:|------|
| **不合并 Adapter** | 基础模型 4-bit + Adapter 16-bit | **3.55** | 效果最好，需额外管理 Adapter 文件 |
| **合并后 AWQ 量化** | 合并 → 16-bit → AWQ 4-bit | 3.88 | 部署简洁，效果略逊 |
| **合并后不量化** | 合并 → 保持 16-bit | 3.60 | 需 16-bit 显存，与不合并效果相当 |
| **合并后 BnB 量化** | 合并 → bitsandbytes 4-bit | 4.33 | **不推荐**，退回未微调水平 |

**结论**：
- 追求最佳效果 → 基础模型 4-bit + 不合并的 Adapter (16-bit)
- 追求部署简洁 → 合并后用 AWQ/AutoRound 量化到 4-bit
- 显存充足 → 合并后直接 16-bit 推理
- **避免**合并后再用 bitsandbytes 4-bit 量化

## GaLore 全量微调实验


---

# Part 5: LoRA/QLoRA 微调机制与 GaLore 全量微调

> *原文来自 Comparison-of-Various-Fine-Tuning-Methods*


## LoRA/QLoRA 微调机制与 Adapter 合并策略

### LoRA 的原理

LoRA（Low-Rank Adaptation）的核心思想是：给预训练权重 W 增加一个低秩的增量 BA，而不是直接修改所有参数。

QLoRA 在此基础上进一步优化——将大型预训练模型先量化成较低精度（通常是4-bit），再在其之上训练规模很小的适配器（adapter）参数，从而在显著减少显存占用的同时，仍能对模型进行有效的微调。

其关键要素包括：

1. **预训练权重 (Pretrained Weights)**：原始预训练模型的权重 W，QLoRA 会将这些预训练权重量化到4-bit，大幅缩小模型体积并减少显存占用。

2. **适配器 (Adapter) 参数 (A 和 B)**：LoRA/QLoRA 中用到的两组小矩阵 A 和 B，以16-bit的形式存储和训练。适配器的参数规模远小于全部模型权重，训练时只需为这小部分参数保存梯度和优化器状态。在最初训练时，B 被初始化为 0 矩阵，A 则随机初始化。

3. **前向计算 (Forward Pass)**：h = W x + B A x，模型的输出不仅包含原来预训练权重 W 的贡献，也会额外加上由适配器 B A 乘以输入 x 得到的增量。

4. **权重合并 (Merged Weights)**：在推理阶段可以将 W 与 B A 合并成一个新的权重矩阵 W_merged 进行计算。

![images](images/qlora_perf_1.png)

### 低秩矩阵表示的数学示例

以 4×4 小矩阵为例说明 LoRA 的低秩更新原理：

**原始权重** W（4×4）：
```
W = [[1, 2, 3, 4],
     [2, 3, 4, 5],
     [3, 4, 5, 6],
     [4, 5, 6, 7]]
```

选择 r=2（低秩），则 B 为 (4×2)，A 为 (2×4)：
```
B = [[0.1, 0.2],    A = [[2.0, 0.0, 0.0, 1.5],
     [0.0, 0.3],         [0.0, 1.0, 2.0, 1.0]]
     [0.1, 0.1],
     [0.0, 0.2]]
```

BA 结果为 4×4 矩阵（秩不超过2）：
```
BA = [[0.2, 0.1, 0.4, 0.3],
      [0.0, 0.3, 0.6, 0.3],
      [0.2, 0.1, 0.4, 0.3],
      [0.0, 0.2, 0.4, 0.2]]
```

微调后权重 W_merged = W + BA，通过两个小矩阵的乘积完成对原始权重的修正。当 r 比 d 小很多时，B 和 A 的参数量远小于 d×d，节省大量训练开销与存储。

### Adapter 合并策略与量化对精度的影响

![images](images/qlora_perf_2.png)

以下是四种不同的 Adapter 部署策略及其效果对比：

| 策略 | 做法 | 困惑度(PPL) | 说明 |
|------|------|:-----------:|------|
| **不合并 Adapter** | 基础模型 4-bit + Adapter 16-bit | **3.55** | 效果最好，需额外管理 Adapter 文件 |
| **合并后 AWQ 量化** | 合并 → 16-bit → AWQ 4-bit | 3.88 | 部署简洁，效果略逊 |
| **合并后不量化** | 合并 → 保持 16-bit | 3.60 | 需 16-bit 显存，与不合并效果相当 |
| **合并后 BnB 量化** | 合并 → bitsandbytes 4-bit | 4.33 | **不推荐**，退回未微调水平 |

**结论**：
- 追求最佳效果 → 基础模型 4-bit + 不合并的 Adapter (16-bit)
- 追求部署简洁 → 合并后用 AWQ/AutoRound 量化到 4-bit
- 显存充足 → 合并后直接 16-bit 推理
- **避免**合并后再用 bitsandbytes 4-bit 量化

## GaLore 全量微调实验

GaLore（Gradient Low-Rank）支持全量微调（Full Fine-tuning），即调整模型所有参数。与 LoRA 等参数效率微调（PEFT）不同，GaLore 通过创新的梯度低秩投影技术，在内存受限条件下也能进行大型模型的全量微调。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKcOCQgbecLaUwicOjXicJPWzZnlJ0B2MvaJ83J8iaID7iclibMISIRNeISKg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

GaLore 性能对比：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKwz1guKATOUib2rJ114icJYIBLtzK9CUBULRSgIMdp47GURH0B9a4iaWhg/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

GaLore 引入额外超参数：Rank r、Scale factor α、Subspace change frequency T。

### GaLore 优化器选项

| 优化器 | 显存需求 (Mistral 7B, BS=8) | 说明 |
|--------|:---------------------------:|------|
| galore_adamw | 较高 | 标准 GaLore，float32 参数 |
| galore_adamw_8bit | ~35 GB (rank=512), ~30 GB (rank=128) | 8位量化优化器 |
| galore_adamw_8bit_layerwise | ~22.5 GB | 分层更新，可在 24GB 消费级 GPU 运行 |

### 实验记录

以下在单 H100 上对 Mistral-7B 进行全量微调（trainable parameters = 7,241,732,096），使用 openassistant-guanaco 数据集。

**实验一**：BS=128, lr=1e-5, optim=galore_adamw_8bit_layerwise, rank=512

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVK6nTib0DBbecicLia529j7hxFIaciaqDzFjbXA8h5b8dcR25GT2Kd1ICaTA/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKKDPJiaQicKH5It9EiboXtAB5DWgwA4R14Qoyur8rLjawAHk3KZ58OibMPw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKicCibC0EJTsYSyauzvIWy6PUXMpFNLFlm7rMp7bGQ7I8q4mnpyNtd80w/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKuus30PiaOVDticlEeFo7uPXGfHw17W9j6ywvLhZToOtgQiakfdD4FkzOw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

从损失函数看，训练效果不理想。

**实验二**：BS=64, lr=2e-5, optim=galore_adamw_8bit_layerwise, rank=512

将学习率增加一倍，将 BS 减少一半：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKic9ezNVcbayBiazsy7fmZdkdLMADYlb6GlkXI6u8yKX4Uf2CUqicBwuhA/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVK8ibY7S3R9COHhOIIOtic0UfGZmRpk7sc7hyrdzQOuVh6rxibotETHTyMw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXBUWiajIRkWDFnAIVQEYeVKX29mtlRIPkUT8yLOjxjy6cQQRvC4BvqPsAEydSiasyhVrXuZT92Yia3A/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

效果好些，但依然不理想。

**实验三**：BS=128, lr=1e-5, optim=galore_adamw_8bit, rank=512

换用 galore_adamw_8bit（非 layerwise）优化器后，GPU 显存利用率更高：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODW2BibS0jEEuOuw1xm0pZ4EH4d572ScuXvnfaxia4mAN95hpKJAdGcNyw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODd4BtwnZQ3cIlicqaI6nnM36r8FUhwHOUlt3yXG1IHK382MTCh7209lQ/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

训练效果比上次好太多了，结果理想。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODEvAprYC3GDe1rFK91cb9HtF94rrzesJZub0gwEz6bfIOx0d3DNWPRw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

**实验四**：BS=128, lr=1e-5, optim=galore_adamw_8bit, rank=1024

保持 BS=128 和 galore_adamw_8bit 优化器，将 rank 从 512 提升到 1024：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODB3HGFPZcWR12jjWKiaolqDvuT8weWZicUxow2AOhAUCjwUr3c2t8yU1w/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

训练中，GPU 显存利用率飙升到87GB，但没有 OOM，充分体现大显存的好处：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODNfN4zibDVvMJIUHib1vPUHpFN9lib6DsyRRVUr6LzZ3Bmvop7MsUCPjfQ/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

查看训练结果，比实验三更理想，损失函数在 step50 直接降到 0.825400，且在 Step100 时降低到 0.71：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUTickEPG2OjjIKXgp96IsODkYRCfA3jyHotAtpa2pmibcquFauYqJlwotvIzOl2ib6ank3AmNd51wJw/640?wx_fmt=other&from=appmsg&wxfrom=5&wx_lazy=1&wx_co=1&tp=webp)

上图展示随着训练过程，损失函数正常下降，但 Validation Loss 上升，说明出现过拟合。

**实验五**：BS=128, lr=1e-6, optim=galore_adamw, rank=1024, weight_decay=0.05, warmup_ratio=0.2

针对实验四的过拟合，降低学习率，增加 weight_decay 和 warmup_ratio：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXYro4VNFxnL6o7LHiaDJL6QB6YGDsBAjVGqJ6gYHPtL1RX0pImFaPxhTLkIQHdEggnF0Ngq6UicbpA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

查看训练效果，过拟合问题解决：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXYro4VNFxnL6o7LHiaDJL6QG3Btgib4WkPCmPGwibyKCBkwGpdSDU8m1ibyBJgOwJBOkibDIn6tGAYK7Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### GaLore 实验总结

| 实验 | BS | LR | 优化器 | Rank | 结果 |
|:----:|:--:|:--:|--------|:----:|------|
| 1 | 128 | 1e-5 | galore_adamw_8bit_layerwise | 512 | 不理想 |
| 2 | 64 | 2e-5 | galore_adamw_8bit_layerwise | 512 | 稍好但不理想 |
| 3 | 128 | 1e-5 | galore_adamw_8bit | 512 | **理想** |
| 4 | 128 | 1e-5 | galore_adamw_8bit | 1024 | 更理想但过拟合 |
| 5 | 128 | 1e-6 | galore_adamw | 1024 | **最佳**（解决过拟合）|

关键发现：
- `galore_adamw_8bit` 优于 `galore_adamw_8bit_layerwise`
- 更高的 rank（1024 vs 512）产生更好的结果
- 过拟合可通过降低学习率、增加 weight_decay 和 warmup_ratio 解决



---

# Part 6: DPO 理论深入与对齐实践

> *原文来自 LLM-Alignment-DPO-PPO-CPO*


## Part I: 解读 DPO 和 PPO：从偏好反馈中学习的最佳实践解析

***Refer to ：Unpacking DPO and PPO: Disentangling Best Practices for Learning from Preference Feedback***

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/6.png)

这篇论文再次证实了 PPO 显著优于 DPO。值得注意的是，最初的 DPO 论文声称在结合强化学习与人类反馈（RLHF）的情况下，DPO 比 PPO 更好。然而，经过大量的实际测试、社区反馈以及后续研究，很明显事实并非如此。

简而言之，研究发现，合成的、多样化的数据集以及详细的分方面偏好信息对于从偏好数据中训练模型最为有效。此外，偏好注释的质量比生成的响应本身的质量更重要。在各种数据集上，PPO 的表现普遍优于 DPO。通过增大用于 PPO 的奖励模型规模以及增加训练数据量，可以显著提升奖励模型在直接评估中的性能，但这种提升主要针对特定任务（例如 GSM），而非模型的整体表现。此外，结合与测试环境高度匹配的未标注提示（prompts）可以提升特定领域的性能，例如数学任务，但对更广泛的性能指标影响有限。

DPO 的运行成本显著低于 PPO，因为它不需要奖励模型。其更简单的目标函数使优化更加容易，收敛速度更快。对于通用的后训练任务以及预算有限的 AI 项目，DPO 仍是比复杂的强化学习方法（如 PPO 或 GRPO）更强有力的替代方案。

### 详解PPO

 PPO 训练架构中，四个主要模型（Policy Model、Reference Model、Reward Model、Value Model）各自承担着不同的职责，简要说明如下：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/7.png)

1. Policy Model（策略模型）
   • 这是我们真正想要训练和更新的"生成模型"或"策略"，它给定输入（q）后，会输出某种动作（如下一步的文本 tokens）。
   • PPO 算法的目标是让该模型能在给定环境（如对话上下文或提示）时，产出更优的策略。
2. Reference Model（参考模型）
   • 一般是一个"冻结"的参考策略，用来在训练时对比当前 Policy 的输出分布。
   • 计算 KL 散度时需要用到 Reference Model：PPO 会惩罚（或限制）新策略与参考策略差别过大，从而避免训练中出现策略分布崩塌或"跑偏"的现象。
3. Reward Model（奖励模型）
   • 这个模型会根据 Policy Model 的输出内容来打分，给出一个"外部"或"对齐"的奖励信号。
   • 举例来说，在对话场景下，Reward Model 可能融合了人工反馈、任务完成度等信息，对输出文本做偏好评分。
   • 在 RLHF（基于人类反馈的强化学习）中，Reward Model 通常是人类标注数据训练而成，用来衡量对话回答的质量、可行性、礼貌等。
4. Value Model（价值函数模型）
   • 用于近似估计当前状态下的"价值"（长期累积奖励的期望），是 PPO 中的"critic"。
   • 在训练中，Value Model 会输出一个价值估计 v，帮助我们计算优势函数（Advantage），进而指导 Policy Model 的更新。
   • 具体实现中经常结合 GAE（Generalized Advantage Estimation）来稳定估计优势并降低方差。

综上所述，这四个模型彼此配合：
• Policy Model 负责产生动作（输出），
• 奖励由 Reward Model 给予，
• Value Model 估计价值函数来支持优势计算，
• Reference Model 则用于在训练中约束新旧策略的差异（KL 散度），
如此就可以通过 PPO 算法不断迭代、调优生成策略并保持策略的稳定性与可控性。



这四个模型的输出并不是"按顺序一个传给下一个"那样单线串行流动，而是"并行地产生各自的输出"，然后在最终的 PPO 损失函数里把这些输出都结合起来，一起指导参数更新。可以把它理解为"所有模型都看了同一个样本(状态+回答)，各自算出自己的结果，最后汇总到一个大公式里"。具体说来：

1. Policy Model 先产出回答
   • 给定输入(比如"7×8=?"，状态s)，Policy Model 生成一个动作(回答)"56"。
   • 这个回答(动作)然后会被送到下面的模型去做各自的计算。

2) 参考模型(Reference Model)计算 KL
   • 同样拿到"状态 s + 动作 a"，Reference Model 会算出参考策略下的概率 p_ref(a|s)，
   而 Policy Model 刚才也有自己的概率 p_new(a|s)。
   • KL 或者 ratio = p_new / p_ref 就被记录下来，用于 PPO 里的"政策约束"部分 (KL 罚项)。
   • 但是它并不是把"打分"传给 Reward Model 或 Value Model；它只是在自己的维度算一个分布对比结果。

3) 奖励模型(Reward Model)给当前回答打分
   • 奖励模型只关心："Policy 刚才输出的回答好不好？"。
   • 拿到回答"56"，它给打一个分数 r，比如说 r=1.0(全对)。
   • 这一步也不会把"得分"直接当输入送进 Value Model，而是最后在损失函数里会用到这个 r。

4) 价值模型(Value Model)对状态估计价值
   • 价值模型输入是"状态 s"（以及可能的动作 a 或上文信息），输出一个"预测的长期回报" v(s)。
   • 它并不会直接拿"奖励 r"做为输入，因为它的任务是去"预测"未来还能拿到多少奖励(而 r 是'真值')。
   • 等到我们做完这一回合，就会知道"真实的奖励 r"和"下一个状态的价值 v(s')"，于是可以对比"v(s)"与"r + γ·v(s')"之间的差异更新 Value Model。

5) 训练脚本(或PPO 算法)汇总以上结果，构建损失函数
   • 在代码层面上，我们往往是这样做：

1. 用 Policy Model 输出动作 a；
2. 从 Reference Model 得到 KL 差异(或者 ratio)；
3. 从 Reward Model 得到即时奖励 r；
4. 从 Value Model 得到当前价值估计 v(s) 和下一个状态的 v(s')；
5. 计算优势 A = r + γ·v(s') - v(s)；
6. 最终组装出 PPO 的目标函数，既包含"优势×策略概率比"的部分，又包含 KL 的惩罚项，还有 Value 的回归损失等。
   • 这时才把所有信息"汇合"到同一个大 loss 里，做一次反向传播更新 Policy Model 和 Value Model 的参数（Reference 仿佛是冻结的老师，Reward Model 也可能已是离线训练好的打分器，不更新）。



6. 训练输出中会记录什么？
   • 一般会记录以下信息(批量平均或每N步统计)：
   – Policy loss (策略梯度那部分损失)
   – Value loss (价值预测的均方误差等)
   – KL divergence (新旧策略或和参考模型的KL)
   – Average reward (Policy此时产出的回答得到的平均奖励)
   – Advantage mean (优势函数的平均值)
   – 以及可能的总 loss
   还可根据需要输出：学习率、梯度范数、GPU 使用率等等，以便监控训练效果。

   

   **总结**

   "看上去后一个模型没用到前一个模型的输出"是因为，它们并不是像流水线一样"一个的输出直接接到下一个模型作为输入"；而更像是"四位评委"各自针对同一个样本给出自己维度上的分数(或判断)：
   • Policy：给出动作(回答)
   • Reference：算出对比参考策略的差距
   • Reward：给出当前回答质量的分数
   • Value：预测长期价值

最后，这些信号由我们的训练逻辑(PPO)"统一整合"，形成损失并更新参数。它并非真正的"串行输入-输出"，而是"并行产出→综合生效"的模式。



### 摘要（Abstract）

从偏好反馈（preference feedback）中进行学习，已经成为当代大语言模型（LMs）提升生成质量与各种任务性能的关键途径。简单来说，"偏好反馈"通常让人类（或模拟系统）对两段不同的模型输出做出偏好判断，进而指导模型学习哪种回复更优。

然而，目前在应用中，对于偏好数据的来源、学习算法的选择，以及最终如何评估，做法各不相同，这使得人们不易分清究竟哪些部分对于最终性能影响最大。本研究将"偏好学习"过程拆分为四个核心要素：

1. 偏好数据（数据本身的来源与质量），

2. 学习算法（PPO、DPO 等），

3. 奖励模型（reward model），

4. 策略训练时所用的提示（policy training prompts）。

   我们对它们逐一进行系统性分析，发现所有要素都会影响最终性能，但影响程度并不一样：
   • 偏好数据质量最关键，好的数据能带来显著提升。
   • 之后是学习算法的差异，尤其是 PPO 与 DPO。
   • 再往后是一款更健全的奖励模型。
   • 最后，如果只关注单一领域，还可以在策略训练时加入更多有针对性的提示，但对全面多任务性能的增益相对有限。

   在我们的实验中：
   • 当聚焦数学任务时，**PPO 的性能最高可比 DPO 高 2.5 个百分点；在通用任务上也能领先 1.2 个百分点。**
   • 高质量的偏好数据在指令**遵从性（instruction following）和真值性（truthfulness）上带来高达 8% 的性能提升**。
   • 即便把奖励模型从中小规模升级到更大规模，在数学任务里可以获得显著**（最多 5%）提升，**但对其他通用任务帮助不大。

本研究开源了所有训练与评测代码，以及对应的模型与数据集。总体而言，高质量的偏好数据、合适的算法与奖励模型、再配合恰当的提示，是"偏好学习"能够取得更好下游性能的配方。

**名词解释**
• "偏好反馈"：假设我们给模型同一个问题，让它生成两个不同的回答，A 和 B。人类标注者对这两个答案做出比较，认为 A 更好。于是模型就会"知道"A 的样式或思路是更优的，从而在后续训练中朝这个方向微调。
• "指令遵从性"与"真值性": 如果系统设定了"请先列出解题思路，再给出最终答案"的指令，一个具备较高指令遵从性与真值性的模型，会提供正确且完整的思路，并避免无根据的胡编乱造。


### 引言（Introduction）

在现代大语言模型（LMs）的开发流程中，往往会额外添加一个阶段——**从偏好反馈中学习（有时也称 RLHF，reinforcement learning from human feedback）——再将模型投入实际使用。**先前有大量研究表明，该阶段能够显著增强模型，包括使模型在指令执行、代码生成、数学解题、文本摘要等方面都获得大幅度改善。

不过，由于各研究在具体实现中对数据、算法、评估方式的做法千差万别，我们难以弄清"究竟哪一环节是提质增效的主要来源"。尤其是在对比最常见的两种偏好学习算法——PPO（Proximal Policy Optimization）与 DPO（Direct Preference Optimization）——时，人们常困惑：两者有什么优劣？该如何选择？

PPO 与 DPO 都基于偏好数据进行模型训练，但过程并不相同：
• DPO：直接在偏好数据（prompt, chosen response, rejected response）上进行离线优化。
• PPO：先训练一个"奖励模型（reward model）"，再用该奖励模型在线给策略模型的输出打分，并通过强化学习更新策略。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/1.png)

因此，我们将这类偏好学习过程拆解为四部分：
1）偏好数据
2）学习算法
3）奖励模型
4）策略训练提示（训练时用于在线生成与打分的提示集合）。

若我们在同一个已训练好的（Supervised Fine-Tuned）模型基础上，分别改变上述任意一个要素，下游性能会发生什么变化？我们在实验中发现，各要素确实都会产生影响，但重要性和效果各异。

### 设置（Setup）

本节先简要介绍 PPO 与 DPO 的概念与原理，然后描述我们在实验与评测中的具体做法。呈现了 PPO 与 DPO 间的结构化对比。  

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/2.png)

**PPO 与 DPO（PPO and DPO）**
(1) PPO
在偏好学习中，PPO 常被视作"在线"强化学习方式：
• 首先训练一个"奖励模型（reward model）"Rψ(x, y)，该模型输入 (x, y) 后输出代表好坏的分数。
• 在策略训练阶段，我们针对每个提示 x，用当前策略模型 πθ 生成回答 y，再用奖励模型打分。模型根据分数进行策略更新，并在损失函数中加入 KL 惩罚项，以防止策略过度偏离初始参考策略 πref。

(2) DPO
相比之下，DPO 则是一种"离线"方法：
• 它不在训练过程中动态抽样新的回答；
• 也不需要在策略训练时额外维护一个价值网络或奖励模型。
• DPO 的核心思路是直接在现成的 (prompt, chosen, rejected) 数据上做优化。

**实验与评估设置（Experimental and Evaluation Setup）**

我们基于公开发布的 TÜLU 2 13B 模型系列来做进一步研究。评测涵盖以下能力：
• MMLU：测试知识准确度（factuality）。
• GSM8k、Big Bench Hard：测试推理（reasoning）能力。
• TruthfulQA：测试回答内容的真实与正确程度（truthfulness）。
• HumanEval+、MBPP+：测试编程（coding）能力。
• ToxiGen、XSTest：测试安全性（safety）。
• AlpacaEval 1 & 2、IFEval：测试模型对指令的跟随度（instruction following）。


### 基于偏好反馈的探索

在此我们从以下四个方面展开： (1) 偏好数据；(2) 学习算法；(3) 奖励模型；(4) 策略训练提示。  

**偏好数据（Preference Data）**

我们收集了 14 个有代表性的偏好数据集，用 DPO 分别进行训练，然后评估下游性能。主要发现包括：
• 对"指令遵从"与"真值"提升巨大，但对"知识准确"帮助不大。
• "合成 + 多维度标注"往往效果最好。
• 部分 Arena 数据在安全性上较差。

**学习算法：DPO 与 PPO**
![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/3.png)

在偏好数据相同、模型规模相同（13B）的条件下：
• PPO 整体略优于 DPO，优势约 0.7 个点。
• 推理、编程和安全性方面，PPO 提升更明显。
• 对数学、编程等需要探索空间较大的任务，PPO 的在线生成与打分机制更有优势。

**奖励模型（Reward Models）**

• 更大规模（70B）或更多训练数据确实能让奖励函数更精准。
• 但在综合多任务场景中，只有数学指标出现最显著改善。

**策略训练提示（Policy Training Prompts）**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/4.png)

• 针对性提示可大幅提升单一领域（如数学：46% → 62%）。
• 但混合提示对多任务综合性能改善有限。


### 基于偏好反馈的一份"食谱"（A Recipe）

综合上述分析，推荐的最佳实践：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/5.png)

- 偏好数据：使用高质量的合成偏好数据（如 UltraFeedback）。
- 学习算法：在大多数场景下，PPO 的性能普遍优于 DPO。
- 奖励模型：若有算力和资源，可选用更大规模的奖励模型。
- 策略训练提示：若只需在单一域中极致提升，则可强化相应领域的提示分布。


### 相关工作（Related Work）

(1) 从偏好反馈中学习：早期研究多将其视作强化学习思路，PPO 是最常用的实践方法之一。本研究系统性考察了数据、算法、奖励模型、策略提示等多维度的综合影响。

(2) 近期并行研究：Xu 等关注 DPO 性能不稳、PPO 更鲁棒；Tajwar 等强调在线采样和对负样本进行显式梯度更新的重要性。


### 结论（Conclusion）

本研究对偏好学习的四大核心环节作了系统探究。结果显示影响次序为：
- 偏好数据质量最先决定模型能达到的上限，
- 学习算法（PPO 较 DPO）带来更高的潜在上限，
- 奖励模型规模越大，对特定任务能有明显促进作用，
- 策略训练提示只在专域时能大幅度加成。

总体而言，有了更强大的奖励模型与有效的在线采样，PPO 训练就能够更好地利用高质量偏好数据，进一步提升模型表现。

---


## Part II: DPO 深入探讨与实践

### RLHF、RLAIF 与 DPO 的偏见问题

RLHF（Reinforcement Learning with Human Feedback）和 RLAIF（Reinforcement Learning with AI Feedback）是两种用于微调大型语言模型（LLM）的方法。它们的主要区别在于反馈的来源：RLHF 依赖于人类提供反馈，而 RLAIF 则使用另一个 LLM 生成反馈。

RLHF 的优点在于，它可以训练 AI 系统处理诸如内容审查等用例，其中人类对于构成仇恨言论、欺凌和其他不良行为的语言有比 AI 更好的判断。

RLHF 依赖于人类提供反馈，这可能会带来一些挑战：

1. 成本和可扩展性：对于需要领域专家特定知识和技能集的反馈的用例，这个过程可能会变得昂贵和耗时。因此，RLHF 可能在大规模应用中面临困难。
2. 反馈的一致性：人类反馈可能会受到个人偏见和主观性的影响，这可能会影响训练的一致性和质量。

RLAIF 试图通过使用另一个大型语言模型（LLM）生成反馈来解决这些问题。这种方法的优点是，它可以大大降低反馈获取的成本，并提高反馈的一致性。然而，它也有自己的挑战，比如可能会复制和放大原始模型的偏见和错误。这就是为什么 RLAIF 和 RLHF 通常会结合使用，以充分利用两者的优点。

三种方法的偏见来源对比：

- **DPO 的偏见**主要来自于用于生成反馈的 AI 模型。如果这个模型在训练数据中存在偏见，那么这种偏见可能会被复制到微调的模型中。
- **RLAIF 的偏见**也主要来自于用于生成反馈的 AI 模型。如果这个模型在训练数据中存在偏见，那么这种偏见可能会被复制到微调的模型中。
- **RLHF 的偏见**主要来自于人类提供反馈。如果提供反馈的人有某种偏见，那么这种偏见可能会被反馈到模型中。

总的来说，这三种方法都需要谨慎地处理偏见问题。这通常需要在数据收集和模型训练的过程中采取一些措施，如使用多元化的数据源，进行公平性和偏见的审核，以及在可能的情况下，使用透明和可解释的模型。这也是一个活跃的研究领域，研究人员正在寻找更好的方法来理解和减少 AI 偏见。



### DPO 中参考模型的深入解析

**https://huggingface.co/docs/trl/dpo_trainer**

在 DPO（Direct Preference Optimization）训练中，需要两个模型：

1. **参考模型（Reference Model）**：使用 SFT 在指令数据集上精调得到的模型。
2. **基础模型（Base Model）**：我们希望通过 DPO 训练的模型。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWkavyXUFb7YmV633SNtwPQA9RorrzDeH5NiaBm0TQC2qZukibcdrjLFB2M3aAW5ibLhOXjDwiaTVEGvw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**参考模型与基础模型的区别：**

1. **参考模型（Reference Model）：**
   - 通过监督式学习（SFT）在一个指令数据集上训练得到，代表了对特定任务的基本理解和执行能力。
   - 在 DPO 中充当基线，用来比较和评估其他模型生成的输出。
   - 在某些情况下，可以用作后续 DPO 训练过程的初始状态，尽管这不是必须的。

2. **基础模型（Base Model）：**
   - 这是我们想要通过 DPO 进行优化的模型，它可能是未经训练的，或是已经在一些任务上有了初步训练的模型。
   - 在 DPO 过程中将直接根据人类的反馈进行训练，学习如何产生更符合人类偏好的输出。
   - 通过 DPO 的训练，基础模型将逐渐学会模仿那些被人类评价为高质量的输出。

在 DPO 中，参考模型主要是用作比较的基准，而基础模型则是实际进行优化和学习的目标。DPO 通过分类问题简化优化过程，使得基础模型能够直接从人类的偏好中学习，而无需依赖于复杂的奖励函数或强化学习算法。

**参考模型的具体作用：**

1. **隐式奖励计算**：参考模型用于计算所谓的隐式奖励。在 DPO 训练中，我们不直接训练一个奖励模型来输出奖励值；相反，我们使用参考模型来估计偏好和被拒绝回答的概率，并基于这些概率来计算隐式奖励。这种隐式奖励是用来指导基础模型的学习，使其更倾向于生成被认为是"好"的输出。

2. **损失函数的基础**：隐式奖励差异（即参考模型和基础模型对选定回答和被拒绝回答的概率差异）用作损失函数的基础。这个损失函数在 DPO 训练中被最大化，目的是提高模型生成偏好回答的概率。

3. **提供稳定性**：参考模型作为训练过程中的固定点，提供了稳定性，帮助避免基础模型在学习过程中偏离过远。它作为一个常数存在，使得基础模型的训练更加稳定和可预测。

4. **模型架构的一致性**：DPO 训练要求参考模型和基础模型具有相同的架构。这是因为在计算隐式奖励时，参考模型和基础模型需要在同样的输入上输出可比较的概率值。

5. **简化训练流程**：与传统的强化学习方法相比，DPO 通过使用参考模型来简化训练流程。这种方法避免了设计复杂的奖励模型和价值模型，从而降低了训练的复杂性。

6. **参数 beta 的作用**：在 DPO 训练中，beta 是一个温度参数，用于缩放隐式奖励差异。这个参数控制了优化过程中对参考模型行为的依赖程度。beta 值越小，基础模型在优化过程中越自由，对参考模型的依赖越小。

总的来说，参考模型在 DPO 训练中提供了一个稳定的比较基准，使得基础模型能够在优化过程中有一个清晰的方向，并且通过隐式奖励的方式简化了优化流程。这使 DPO 成为一种高效的语言模型优化方法，特别是在处理偏好数据时。



### 为什么选择 DPO 而非直接 SFT 微调？

使用一个 SFT 的 Mistral 作为参考模型来训练另一个 Mistral 模型确实听起来有些重复，但在 DPO 的上下文中，这样做是有其特定目的和理由的。

DPO 方法的核心在于直接优化模型以生成符合人类偏好的输出，这通常是通过对比人类标注的"优选"输出与"非优选"输出来实现的。DPO 的目标是训练出一个模型，使其能够系统性地产生高质量的输出。

在这个过程中，SFT 的 Mistral 模型作为参考模型的作用主要是提供一个性能基线。它代表了模型在没有接受特定偏好训练之前的能力水平。而 DPO 过程中的 Mistral 模型则是在这个基线之上进一步优化以生成符合人类偏好的输出。

为什么不直接在 SFT 的模型基础上继续微调，而是使用 DPO？原因如下：

1. **特定的优化目标**：DPO 是为了优化一个特定的目标——与人类偏好一致的输出。这不仅仅是提升模型在一般性任务上的表现，而是让模型学会在给定的人类反馈框架内进行决策。

2. **分类问题的简化**：DPO 将复杂的强化学习问题转化为一个相对简单的分类问题，这使得模型的训练更加直接和高效。

3. **避免奖励模型的不稳定性**：在传统的 RLHF 方法中，需要训练一个奖励模型来指导模型的训练，这个过程可能会很不稳定。DPO 通过直接利用人类的反馈来避免这种不稳定性。

4. **计算效率**：DPO 通常比传统的 RLHF 更高效，因为它避免了多个模型的训练和维护，减少了计算资源的需求。

5. **高质量的初始状态**：SFT 模型提供了一个高质量的初始状态，理论上它已经对相关任务有了良好的表现。DPO 在这个基础上进一步提升模型在特定偏好上的表现，而非从头开始训练。

总之，尽管 SFT 模型在很多情况下已经足够好，但 DPO 提供了一种基于人类的直接反馈进行模型微调的方法，这可以针对特定的应用场景进一步优化模型性能。这种基于人类偏好的微调方法在确保模型输出与人类评价者期望一致的同时，还可以提高模型的可适应性和泛化能力。

### DPO 的应用场景

DPO 方法虽然在本质上依赖于分类问题的框架（即区分人类偏好的高质量和低质量输出），但它并不局限于传统的分类任务。实际上，DPO 是为了解决语言模型在生成任务中的优化问题而设计的。

在 DPO 中，"分类"不是指将实例分配给预先定义好的标签，而是指识别和优化模型输出以使其符合人类的直接偏好。这种偏好通常是基于比较两个输出响应的质量来定义的，而不是将输出分到固定的类别中。

DPO 特别适用于以下几种场景：

1. **文本生成**：在诸如聊天机器人、文章或诗歌生成等任务中，DPO 可以帮助模型学习如何生成更加自然、有吸引力或符合特定风格的文本。

2. **内容推荐**：DPO 可以用来优化推荐系统的算法，使其更准确地反映用户的喜好。

3. **交互式应用**：在需要根据用户输入动态生成响应的应用中，DPO 可以帮助模型更好地理解用户的意图和偏好。

4. **个性化服务**：DPO 可以用于个性化服务，比如个性化新闻摘要或产品建议，它可以使模型学习用户的特定喜好。

尽管 DPO 借鉴了分类问题的一些技术，但其目标是为了改善生成任务中的模型性能，使之能够创建出高度符合人类偏好的输出。这一点使其与传统的分类任务有着本质的区别。因此，DPO 更多地被视为一种特定于生成任务的优化策略，而不仅仅是一种分类方法。

### DPO 核心代码参考

以下以 Mistral 7B 模型为例，展示 DPO 训练的完整流程。

**数据集准备**

训练参考模型和 DPO 训练基础模型使用不同的数据集：

```python
dataset_train_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft")
dataset_test_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="test_sft[:5%]")

dataset_train_dpo = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split="train_prefs")
dataset_test_dpo = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split="test_prefs[:5%]")
```

两个数据集示意：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31Qg16gInAqzxm4XSQHf94ib3WaQTfbRKHYQXEpMOu2pJ7HUKBqbumvDA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31vBXuMoJbd2icF70YePHZpdBedtLx0oUTTIyKjVicMaOdG7ibKhB2SGP6Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**模型加载与适配器配置**

DPO 的参考模型是之前使用监督式精调（SFT）在特定数据集上训练过的 Mistral 7B 模型。参考模型被用来初始化一个适配器（adapter），这个适配器随后被用于 DPO 训练。

```python
model = PeftModel.from_pretrained(model, "kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", is_trainable=True, adapter_name="DPO")  
model.load_adapter("kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", adapter_name="reference")
```

这里 `model` 是基础模型，即要通过 DPO 进行训练的模型。`load_adapter` 方法用来加载一个名为 "reference" 的适配器，该适配器是在 SFT 过程中使用 Mistral 7B 训练得到的，基于 "ultrachat" 数据集。在 DPO 训练中，这个 "reference" 适配器用作比较的基准，帮助评估生成的输出是否符合人类的偏好。

在 DPO 中，参考模型的作用是提供一个与被训练模型的输出相比较的标准。在训练期间，系统会计算参考模型输出和被训练模型输出的概率对数差异，并将其乘以一个系数（beta），这个差异用于指导 DPO 的训练过程，使得被训练模型能够生成更优选的响应。

**选择参考模型的关键考量：**

1. **相似性**：相同或相似的模型结构保证了在比较基础模型和参考模型的输出时，差异主要来自于模型权重的不同，而非模型架构的不同。

2. **一致性**：使用同一模型架构可以确保生成的输出有可比性，这对于训练过程中评估和提升模型性能至关重要。

3. **简化训练**：如果参考模型与基础模型在架构上一致，可以简化训练流程，因为可以共享部分模型组件，有助于减少内存消耗和计算需求。

4. **适配器技术**：在某些实现中，使用了适配器技术来对模型进行微调。这种情况下，参考模型和基础模型之间的适配器可以共享，减少了资源的需求。

**第一步：SFT 训练参考模型**（使用 HuggingFaceH4/ultrachat_200k）

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31TRnRNZ1KTQBNQmFJvLiaNgtQ2sGFTEDzU8v83dRkYKxib3xpTeNONxuQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31PuTVUk3nlGATuQOy5PRE5FibmVIyJ7EADxOzVafzS2n068OotrWv9ow/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31sAhNG7fQ2pNpHRn8578j4VHmM6WuVdRSa5QzlqicfAXgYAmoCppia5wg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

微调过程中的资源消耗：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31DXj7XpFcgfGCcwkkkhCPgkwClsOicg7PmyZibnibvO9ic8vuiaR3DjDEUvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**第二步：DPO 训练基础模型**（使用 SFT 后的模型作为参考模型）

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31tcnFcDhJ60icpRHzVaknNPT9UVo2Xwqo5I2Uq2EX0gvM6mpIBokHQDQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31qFmelfEAkT4xrcqkAmxICxbmROJnicGbUTto7LAYvyfGhJ7WHqoMMrQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31hQmrMLYvVxIibPNibVqJ2MNbEKM6lkJLOoxZ4sADSTm8yROVuBMUF10w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31EibScDruPpInR1dnjgYSvKFoSwfm1ZWE2dyHXqLo4Akz3Fq1IoRW5vA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**DPO 训练过程中的资源开销**

bs=4:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31PLGFDxOAm0ZvUSyEADqs8IfyF60Dl7W7Ae6F3quo8Mex2BiaRkxNVvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

bs=16：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM311icJ9J9XMMtia73zuKkJGvnZ4UY9mmtjicvGnFxbWcxXVx7m6fewqAFsw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

bs=32：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31JiaDvRWfI53axaYC2IZBIFejPkhr5ibIRy3X4x8ozt6auGsXicbZ3fAfQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31yGktkn5WIczClZnJyoM9GDjicHFHJzFib3ZGCgAiav7fMIgBFhUyklhvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31Y0okm1V2QqAjsUnkl2LhuzsR0QFKmxWfJWlC0VP1a5h8XibmWcO4sgA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**DPO 训练指标解读**

训练日志中记录的各项指标含义：

1. **Step**：训练步骤编号，每个数字代表模型完成的一个批次(batch)的训练。
2. **Training Loss**：训练损失值，值越小表示模型在训练集上的表现越好。
3. **Validation Loss**：验证损失值，在未参与训练的数据集（验证集）上计算，用以评估模型的泛化能力。
4. **Rewards/chosen**：被选择的输出（即人类偏好的输出）对应的奖励值。
5. **Rewards/rejected**：被拒绝的输出（即人类不偏好的输出）对应的奖励值。
6. **Rewards/accuracies**：奖励准确度，表示模型在区分人类偏好和不偏好的输出方面的准确性。
7. **Rewards/margins**：奖励边际，即被选择和被拒绝的输出间的奖励差距，这个值越大表示模型在区分偏好输出上的性能越好。
8. **Logps/rejected** 和 **Logps/chosen**：对数概率（log probabilities）值，分别对应被拒绝和被选择输出的对数概率，通常用于概率的数值稳定性处理。
9. **Logits/rejected** 和 **Logits/chosen**：在模型的最后一个线性层输出之前的值，即 logits，是经过最后一层线性变换但尚未应用激活函数的值。

### SimPO 与 CPO 实践

在本项目的 Jupyter Notebook 中，还包含了使用 SimPO（Simple Preference Optimization）和 CPO（Contrastive Preference Optimization）对 Llama 3 进行内存高效对齐训练的完整代码示例，详见 `Memory_efficient_LLM_Alignment_with_SimPO_Example_with_Llama_3_and_Comparison_with_CPO.ipynb`。


---

# Part 7: DPO 微调代码与训练结果分析

> *原文来自 Comparison-of-Various-Fine-Tuning-Methods*


## DPO微调代码

定义要被微调的模型

```
model_name = "mistralai/Mistral-7B-v0.1"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = 'left' #Left is necessary for FlashAttention

#Better to use bf16 if supported (Ampere GPUs or more recent)
#If bf16 is supported, the GPU is also recent enough to support FlashAttention
if torch.cuda.is_bf16_supported():
  compute_dtype = torch.bfloat16
  attn_implementation = 'flash_attention_2'
else:
  compute_dtype = torch.float16
  attn_implementation = 'sdpa'
```

加载数据集：

```
dataset = load_dataset("UltraFeedback-prompt-chosen-rejected")
```

查看数据集的第一条，在数据集中，`chosen` 和 `rejected` 标签可以用于训练模型理解什么是好的回复，什么是不好的回复，从而优化模型的输出质量。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/1.png)

```
bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
          model_name, quantization_config=bnb_config, device_map={"": 0}, torch_dtype=compute_dtype, attn_implementation=attn_implementation
)
model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant':True})
#Configure the pad token in the model
model.config.pad_token_id = tokenizer.pad_token_id
```

下面这段代码的主要作用是：

1. **加载一个预训练的模型，并为它添加两个“小插件”（我们称之为“适配器”）：**
   - **第一个适配器**叫做 **"DPO"**，这个适配器是**可以训练的**，即在训练过程中会被更新和改进。
   - **第二个适配器**叫做 **"reference"**，这个适配器是**固定的，不会被训练**，用于作为对照参考。

```
model = PeftModel.from_pretrained(model, "kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", is_trainable=True, adapter_name="DPO")
model.load_adapter("kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", adapter_name="reference")
```

接下来，设置DPO训练的超参。`DPOConfig` 是一个特定名字的类，用于配置 **Direct Preference Optimization（DPO）** 训练过程的参数。

```
training_arguments = DPOConfig(
        output_dir="./results",
        evaluation_strategy="steps",
        do_eval=True,
        optim="paged_adamw_8bit",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=8,
        per_device_eval_batch_size=8,
        log_level="debug",
        save_steps=20,
        logging_steps=20,
        learning_rate=5e-7,
        eval_steps=20,
        max_steps=100,
        warmup_steps=20,
        lr_scheduler_type="linear",
        report_to='none'  
)
```

```
trainer = DPOTrainer(
    model,
    args=training_arguments,
    beta=0.1,
    model_adapter_name="DPO",
    ref_adapter_name="reference",
    train_dataset=dataset['train'],
    eval_dataset=dataset['test'],
    tokenizer=tokenizer,
)

trainer.train()
```

查看训练结果：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/2.png)

## 对DPO训练结果的解释

在使用 DPO（Direct Preference Optimization，直接偏好优化）方法进行模型训练时，我们涉及两个模型：


训练模型（Policy Model）：这是我们希望优化的模型，它的参数会在训练过程中更新。

参考模型（Reference Model）：这是一个固定的模型，其参数在训练过程中保持不变，用于提供参考和正则化。

训练目标：希望训练模型在给定 Prompt（输入）时，更倾向于生成 Chosen（偏好较高的回复），而避免生成 Rejected（偏好较低的回复）。

训练过程中的关键步骤和指标

#### 训练数据

每个训练样本包含：

- Prompt（输入）：模型需要回答的问题或指令。
- Chosen（理想回复）：我们希望模型生成的正确答案。
- Rejected（不理想回复）：我们希望模型避免生成的答案。

#### 模型评价

对于每个样本，我们需要计算以下内容：

- 训练模型 对 Prompt + Chosen 的评价。
- 训练模型 对 Prompt + Rejected 的评价。
- 参考模型 对 Prompt + Chosen 和 Prompt + Rejected 的评价（用于计算正则化项）。

#### 奖励值的计算

奖励函数（Reward Function）：用于评估训练模型对 Chosen 和 Rejected 的输出质量，给予数值评分（奖励值）。

- 奖励值的计算：
  - Rewards/chosen：训练模型对 Chosen 回复的奖励。
  - Rewards/rejected：训练模型对 Rejected 回复的奖励。

#### 损失函数的计算

损失函数的主要组成部分：

- 偏好损失：鼓励模型对 Chosen 回复给予更高的奖励，对 Rejected 回复给予更低的奖励。

- 正则化项：利用参考模型，限制训练模型不要偏离原始语言模型的分布过远。

  损失函数公式（简化版，用普通文本表示）：

```
损失 = -（训练模型对 Chosen 的奖励 - 训练模型对 Rejected 的奖励） + β * （训练模型与参考模型的差异）  
```

其中，β 是超参数，控制正则化项的权重。



### 通过示例解释训练过程和指标

 #### 示例训练数据


Prompt：

```
翻译以下英文句子为中文： "The quick brown fox jumps over the lazy dog."  
```


Chosen（理想回复）：

```
"敏捷的棕色狐狸跳过了懒狗。"  
```


Rejected（不理想回复）：

```
"我不知道如何翻译这个句子。"  
```

 **步骤 1：模型评价**

（a）训练模型对 Chosen 和 Rejected 的评价
计算对数概率（Logps）：

- Logps/chosen：训练模型对 Chosen 回复的对数概率之和。例如，假设计算得到 -50。

- Logps/rejected：训练模型对 Rejected 回复的对数概率之和。例如，计算得到 -70。

  （b）参考模型的输出
  参考模型 也会对 Chosen 和 Rejected 进行评价，计算对数概率（用于正则化项）。但这些值不直接出现在训练结果中。

**步骤 2：奖励值的计算**

（a）计算奖励值

- Rewards/chosen：

  ```
  Rewards/chosen = 训练模型对 Chosen 的对数概率 - β * （训练模型与参考模型在 Chosen 上的差异）  
  ```

  例如，假设训练模型和参考模型在 Chosen 上的差异为 5，β 为 0.1，则：

  ```
  Rewards/chosen = -50 - 0.1 * 5 = -50.5  
  ```

 

- Rewards/rejected：

  ```
  Rewards/rejected = 训练模型对 Rejected 的对数概率 - β * （训练模型与参考模型在 Rejected 上的差异）  
  ```

  例如，差异为 3，则：

  ```
  Rewards/rejected = -70 - 0.1 * 3 = -70.3  
  ```


（b）计算奖励差距（Rewards/margins）

```
Rewards/margins = Rewards/chosen - Rewards/rejected  
```

代入数值：

```
Rewards/margins = (-50.5) - (-70.3) = 19.8  
```

 

**步骤 3：计算损失**

```
损失 = -（Rewards/chosen - Rewards/rejected） = -（-50.5 - (-70.3)） = -19.8  
```

模型会根据这个损失值进行参数更新，目的是最小化损失，即最大化奖励差距。



**步骤 4：计算其他指标**

- Rewards/accuracies（奖励准确率）
  如果 Rewards/chosen > Rewards/rejected，则计为一次正确判断。在我们的例子中，-50.5 > -70.3，所以这是一次正确判断。
- Logits/chosen 和 Logits/rejected
  Logits 是在计算对数概率（Logps）之前的原始输出值。这些值反映了模型对每个词的未归一化的信心程度。



### 参考模型的作用

 

- 正则化：参考模型帮助计算正则化项，限制训练模型不要偏离原始语言模型的分布过远。
- 计算差异：通过比较训练模型和参考模型在 Chosen 和 Rejected 上的输出差异，调整奖励值。
- 隐式影响：虽然参考模型的输出不直接出现在训练结果中，但它在损失函数的计算中起到了关键作用，进而影响了训练模型的更新。

### 训练结果中的各指标


现在，我们将总结训练结果中的各个指标，以及它们是如何产生的：

- Rewards/chosen：由训练模型对 Chosen 回复的评价计算得到，考虑了参考模型的影响（通过正则化项）。
- Rewards/rejected：由训练模型对 Rejected 回复的评价计算得到，同样考虑了参考模型的影响。
- Rewards/accuracies：模型正确区分 Chosen 和 Rejected 的比例。
- Rewards/margins：Rewards/chosen 与 Rewards/rejected 之间的差值，反映了模型对偏好的区分能力。
- Logps/chosen 和 Logps/rejected：训练模型在 Chosen 和 Rejected 上的对数概率之和。
- Logits/chosen 和 Logits/rejected：训练模型在生成 Chosen 和 Rejected 时的未归一化输出值。

### 总结

- 参考模型的作用：虽然参考模型的输出不直接显示在训练结果的指标中，但它通过损失函数中的正则化项，间接地影响了训练模型的更新。
- 指标的产生：训练结果中的各项指标主要反映了训练模型的性能，通过对 Chosen 和 Rejected 的评价计算得到。
- 训练目标：通过最小化损失函数，使训练模型更倾向于生成 Chosen 回复，而避免生成 Rejected 回复，同时保持模型的语言能力不被破坏。

## DPO微调中的正则化与泛化

### 正则化


简单来说，正则化是一种防止模型过度拟合的方法。


过度拟合（Overfitting）是指模型在训练数据上表现很好，但在新数据（未见过的数据）上表现很差。这是因为模型“记住”了训练数据的细节和噪声，而不是学会了数据背后的一般规律。


正则化（Regularization）是为了解决过度拟合问题的一种技术。**它的作用是：**在训练过程中，对模型的某些特性进行约束，防止模型过于复杂，从而使模型在新数据上也能有良好的表现。


比喻：想象你在学习如何识别苹果和橘子。过度拟合的模型可能会记住训练集中每个苹果和橘子的具体特征，比如这个苹果有一个小斑点，那个橘子有一片叶子。正则化的模型则会关注苹果和橘子的一般特征，比如形状、颜色，而不会过分关注训练数据中特定的细节。

#### 在模型训练中的应用

- **限制模型复杂度**：正则化通过限制模型的参数，使模型不会变得过于复杂。例如，在神经网络中，可以对权重施加限制，不让它们变得过大。
- **防止参数过大**：如果模型的参数（如权重）变得过大，模型可能会过度关注训练数据的细节。正则化通过在损失函数中添加一个惩罚项，鼓励模型的参数保持较小的值。

在上面的训练中

- **参考模型的作用**：在 DPO（直接偏好优化）训练中，参考模型（Reference Model）用于正则化。

- 为什么需要正则化：

  - 平衡：我们希望模型既能学会用户的偏好，又不要失去原有的语言生成能力。
  - 防止过度偏离：如果只关注让模型更倾向于生成“正确”的回复，模型可能会过度调整，导致语言质量下降。

- 正则化的方法

  ：

  - 利用参考模型：通过在损失函数中加入一个项，测量训练模型与参考模型之间的差异（如 KL 散度）。
  - **作用**：这项差异作为正则化，防止模型过度偏离参考模型的行为，保持语言流畅性和多样性。

### 泛化


我们实际上已经在训练数据中提供了“应该怎么回答”和“不应该怎么回答”的示例，分别是 Chosen 和 Rejected 回复。但仅仅提供正确答案并让模型模仿是不够的，我们希望模型能够理解为什么某个回答是好的，某个回答是差的，从而在新的情况下做出正确的判断。

1. **模仿学习的局限性**

   - **直接模仿可能导致过度拟合**：
     如果模型只是机械地记住训练数据中的正确回答，它可能无法对新问题或稍有变化的输入做出良好的响应。
   - **缺乏区分能力**：
     模型可能不知道为什么一个回答是好的，另一个是差的，所以在面对新情况时，可能无法正确区分。

2. **引入不良回复的原因**

   - **明确模型的偏好**：
     通过提供 Rejected（不良回复），我们告诉模型哪些回答是不好的。
   - **对比学习**：
     模型通过对比 Chosen 和 Rejected，学会区分好的回复和坏的回复。这种方法能够让模型理解什么样的特征是好的，什么样的特征是坏的。

3. **提高模型的泛化能力**

   - **在新情况下做出正确判断**：
     我们希望模型不仅能记住正确的回答，还能在面对各种新问题时，基于学到的偏好，生成优质的回复。
   - **理解背后的原则**：
     通过对比好的和坏的回复，模型可以学到更深层次的模式和规律，而不是仅仅记住答案。

4. **防止偏差和不良行为**

   - **处理安全和道德问题**：
     通过明确标注不应该生成的回复，模型可以避免生成有害、偏见或不恰当的内容。
   - **强化正确的行为**：
     让模型学会哪些内容是应该避免的，哪些是应该鼓励的，提高模型的可靠性。

5. **举个例子**

   - **直接提供正确回答的风险**：
     如果我们只给模型一个问题和正确答案，例如：

     ```
     问题：请解释牛顿的第一定律。  
     回答：物体在没有受到外力作用时，会保持静止或匀速直线运动状态。  
     ```

     模型可能只能在遇到完全相同的问题时给出正确的回答。

   - **加入不良回复进行对比**：
     我们再提供一个不良回复：

     ```
     不良回答：我不知道牛顿的第一定律是什么。  
     ```

     通过对比，模型可以学到：

     - 好的回答应该是对问题的准确、完整的解释。
     - 不好的回答是无法回答问题或者提供错误信息。

     这样，模型在面对类似但不同的问题时，也能给出正确的回答：
     例如，遇到“请解释牛顿的第二定律”时，模型能够推断出应该提供该定律的解释，而不是说“我不知道”。

#### 总结

- **正则化**：
  是一种防止模型过度拟合的方法，确保模型在新数据上也有良好的表现。在您的训练中，参考模型用于正则化，防止训练模型过度偏离原有的语言模型分布，保持语言的质量和一致性。
- **训练方法的设计**：
  通过提供 Chosen 和 Rejected 回复，让模型学会区分好的和坏的回答。这种对比学习的方法让模型能够理解回答质量的差异，从而在新情况下也能生成优质的回复。直接让模型模仿正确答案，可能导致模型缺乏泛化能力，无法在新情境下做出正确的判断。


---

# Part 8: 大模型 DPO 分布式训练 (DeepSpeed & FSDP)

> *原文来自 DPO-DeepSpeed-FSDP*


**Direct Preference Optimization (DPO)** is currently one of the popular methods for aligning large language models (LLMs) with human preferences. With parameter-efficient fine-tuning techniques like **LoRA** and **QLoRA**, we can perform DPO training on models with 8 billion parameters (such as Llama 3.1 8B and Qwen2.5 7B) on a single GPU, though the training sequences might be shorter. However, for larger models, like 72B, multiple GPUs are required. 

 

### Technical Points

For example, suppose we want to perform DPO training on a 70 billion-parameter model on a machine with 8 H100 GPUs (totaling 640 GB of VRAM). We need to consider the following points:

- **Policy Model**: The model we want to train, which occupies about 140 GB of VRAM.

- **Reference Model**: DPO requires a reference model, usually with the same architecture as the policy model, also occupying about 140 GB of VRAM.

  Thus, just the model parameters alone consume 280 GB of VRAM, approximately 43.75% of the total VRAM. In addition, there are optimizer states. For example, using the AdamW optimizer, each parameter has two additional state variables. If these state variables are stored in 16-bit precision, they will take up an extra 280 GB of VRAM. Adding it all up, we've used 560 GB of VRAM, leaving only 80 GB. This remaining VRAM is needed to store activations and gradients. Without special methods, it's unlikely to train on a single machine.


## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | DeepSpeed, LoRA/PEFT |


## Distributed training technology 

To address the above challenges, we could use PyTorch's **Fully Sharded Data Parallel (FSDP)** technology, combined with parameter-efficient fine-tuning methods like LoRA and QLoRA. 

**FSDP is similar to DeepSpeed's ZeRO technology.** **Accelerate** is a library from Hugging Face (HF).  FSDP is a distributed training technique that shards the model's parameters, optimizer states, and gradients, distributing them across multiple devices (such as GPUs). During the forward and backward passes, only the required parameter shards are loaded into memory and released after computation. This greatly reduces memory requirements.  Of course, when training even larger models, **DeepSpeed** can be used. DeepSpeed requires a large amount of memory to store full-precision model parameters. 

In my repo, I used both DeepSpeed ZeRO-3 technology and FSDP technology, and the training results were the same. I will showcase the scripts and configuration files for both training methods. 

 ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVG8MCygzbO12sANWDsyJAcwEYpAcnqXWdicELzh4cFtibVKK8HonEFffN03MKhIluSb7lD8kxvmVA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

In the following DeepSpeed and Accelerate FSDP training, I use an adapter from HF:

```
(Multi-GPU-DPO-Training) root@YOUR-VM:~# ls -al ./SFT_LoRA/
total 838112
drwxr-xr-x  5 root root      4096 Dec 19 06:49 .
drwx------ 48 root root      4096 Dec 19 11:24 ..
drwxr-xr-x  9 root root      4096 Dec 19 06:49 .git
-rw-r--r--  1 root root      2345 Dec 19 06:48 .gitattributes
-rw-r--r--  1 root root       264 Dec 19 06:48 README.md
-rw-r--r--  1 root root       728 Dec 19 06:48 adapter_config.json
-rw-r--r--  1 root root 842289128 Dec 19 06:49 adapter_model.safetensors
-rw-r--r--  1 root root       605 Dec 19 06:48 added_tokens.json
drwxr-xr-x  4 root root      4096 Dec 19 06:48 checkpoint-10
drwxr-xr-x  4 root root      4096 Dec 19 06:48 checkpoint-5
-rw-r--r--  1 root root   1671853 Dec 19 06:48 merges.txt
-rw-r--r--  1 root root       499 Dec 19 06:48 special_tokens_map.json
-rw-r--r--  1 root root  11421896 Dec 19 06:48 tokenizer.json
-rw-r--r--  1 root root      7306 Dec 19 06:48 tokenizer_config.json
-rw-r--r--  1 root root      5496 Dec 19 06:48 training_args.bin
-rw-r--r--  1 root root   2776833 Dec 19 06:48 vocab.json

(Multi-GPU-DPO-Training) root@YOUR-VM:~/SFT_LoRA# cat adapter_config.json
{
  "alpha_pattern": {},
  "auto_mapping": null,
  "base_model_name_or_path": "Qwen/Qwen2.5-72B-Instruct",
  "bias": "none",
  "fan_in_fan_out": false,
  "inference_mode": true,
  "init_lora_weights": true,
  "layer_replication": null,
  "layers_pattern": null,
  "layers_to_transform": null,
  "loftq_config": {},
  "lora_alpha": 16,
  "lora_dropout": 0.05,
  "megatron_config": null,
  "megatron_core": "megatron.core",
  "modules_to_save": null,
  "peft_type": "LORA",
  "r": 16,
  "rank_pattern": {},
  "revision": null,
  "target_modules": [
    "up_proj",
    "q_proj",
    "k_proj",
    "down_proj",
    "gate_proj",
    "v_proj",
    "o_proj"
  ],
  "task_type": "CAUSAL_LM",
  "use_dora": false,
  "use_rslora": false
```



## DeepSpeed Training

Deepspeed Configuration file:

```
# cat deepspeed_config.json
{  
  "zero_optimization": {  
    "stage": 3,  
    "overlap_comm": true,  
    "contiguous_gradients": true,  
    "reduce_bucket_size": 104857600,  
    "stage3_prefetch_bucket_size": 104857600,  
    "stage3_param_persistence_threshold": 1048576  
  },  
  "bf16": {  
    "enabled": true  
  },  
  "train_micro_batch_size_per_gpu": 1,  
  "gradient_accumulation_steps": 16,  
  "steps_per_print": 10,  
  "wall_clock_breakdown": false  
}  
```

Training code:

```
#cat fsdp+QLoRA_deepspeed.py
import torch  
import os  
import multiprocessing  
from datasets import load_dataset  
from peft import PeftModel  
from transformers import (  
    AutoModelForCausalLM,  
    AutoTokenizer,  
    BitsAndBytesConfig,  
    set_seed  
)  
from trl import DPOTrainer, DPOConfig  
  
set_seed(1234)  
  
model_name = "Qwen/Qwen2.5-72B-Instruct"  
sft_adapter = "./SFT_LoRA/"  # 一个使用 SFT 微调的 LoRA 适配器  
  
compute_dtype = torch.bfloat16  
  
# 如果在使用 FlashAttention 时遇到问题，可以改用 'sdpa'  
attn_implementation = 'flash_attention_2'  
  
# 如果内存不足，可以修改以下三个训练参数  
bs = 1        # 每个设备的批大小（训练和验证）  
gas = 16      # 梯度累积步骤数  
mseqlen = 512 # 最大序列长度  
  
lr = 1e-5     # 学习率  
QLoRA = True  # 是否量化基模型  
  
output_dir = "/workspace/DPO_LoRA"  
  
# 初始化 Tokenizer  
tokenizer = AutoTokenizer.from_pretrained(model_name)  
tokenizer.pad_token = "<|image_pad|>"  
tokenizer.pad_token_id = 151655  
tokenizer.padding_side = 'right'  # 对于 Qwen2.5，左右 padding 都可以  
  
# 加载并处理数据集  
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)  
ds_train = ds['train']  
ds_test = ds['test']  
  
def process(row):  
    # 第一个消息是提示  
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)  
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token  
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token  
    row["prompt"] = prompt_messages  
    row["chosen"] = chosen_messages  
    row["rejected"] = rejected_messages  
    return row  
  
ds_train = ds_train.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
ds_test = ds_test.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
if QLoRA:  
    bnb_config = BitsAndBytesConfig(  
        load_in_4bit=True,  
        bnb_4bit_quant_type="nf4",  
        bnb_4bit_compute_dtype=compute_dtype,  
        bnb_4bit_use_double_quant=True,  
        bnb_4bit_quant_storage=compute_dtype,  
    )  
  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        quantization_config=bnb_config,  
        torch_dtype=compute_dtype,  
        attn_implementation=attn_implementation,  
    )  
  
    # 冻结基模型的参数  
    for name, param in model.named_parameters():  
        param.requires_grad = False  
  
    # 让输入嵌入支持梯度  
    def make_inputs_require_grad(module, input, output):  
        output.requires_grad_(True)  
  
    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)  
else:  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name,  
        torch_dtype=compute_dtype,  
        attn_implementation=attn_implementation,  
    )  
  
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': True})  
  
# 加载 LoRA 适配器  
model = PeftModel.from_pretrained(  
    model,  
    sft_adapter,  
    is_trainable=True,  
    adapter_name="DPO"  
)  
model.load_adapter(sft_adapter, adapter_name="reference")  
  
# 将模型移动到设备上  
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")  
model.to(device)  
  
training_arguments = DPOConfig(  
    output_dir=output_dir,  
    eval_strategy="steps",  
    do_eval=True,  
    optim="adamw_torch",  
    per_device_train_batch_size=bs,  
    gradient_accumulation_steps=gas,  
    per_device_eval_batch_size=bs,  
    log_level="debug",  
    save_strategy="steps",  
    save_steps=5,  
    logging_steps=2,  
    learning_rate=lr,  
    bf16=True,  
    beta=0.1,  
    eval_steps=2,  
    max_steps=10,  
    warmup_ratio=0.1,  
    lr_scheduler_type="linear",  
    max_length=mseqlen,  
    max_prompt_length=512,  
    dataset_num_proc=multiprocessing.cpu_count(),  
    model_adapter_name="DPO",  
    ref_adapter_name="reference",  
    deepspeed="deepspeed_config.json",  # 指定 DeepSpeed 配置文件  
)  
  
trainer = DPOTrainer(  
    model=model,  
    args=training_arguments,  
    train_dataset=ds_train,  
    eval_dataset=ds_test,  
    tokenizer=tokenizer,  
)  
  
# 开始训练  
trainer.train()  
  
# 保存模型  
trainer.save_model(output_dir)  
```

Launch training 

```
(dpo) root@h1002gpu:~# deepspeed fsdp+QLoRA_deepspeed.py
```

```
{'loss': 0.6914, 'grad_norm': 3.3615094645372428, 'learning_rate': 8.888888888888888e-06, 'rewards/chosen': 0.0, 'rewards/rejected': 0.0, 'rewards/accuracies': 0.0, 'rewards/margins': 0.0, 'logps/chosen': -536.0, 'logps/rejected': -532.0, 'logits/chosen': 0.1, 'logits/rejected': 0.0, 'epoch': 0.0}
 20%|████████████████████████████▊   
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/LLM-Fine-Tuning-and-Alignment/images/1.png)

## Accelerate FSDP training

 Configuration file:

```
(Multi-GPU-DPO-Training) root@YOUR-VM:~# cat config_fsdp.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch: BACKWARD_PRE
  fsdp_cpu_ram_efficient_loading: true
  fsdp_forward_prefetch: false
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_use_orig_params: False      # Set this to true
  mixed_precision:
    param_dtype: float16
    reduce_dtype: float16
    buffer_dtype: float16
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 2
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
```



Training code:

```
(Multi-GPU-DPO-Training) root@YOUR-VM:~# cat config_fsdp.yaml
compute_environment: LOCAL_MACHINE
debug: false
distributed_type: FSDP
downcast_bf16: 'no'
fsdp_config:
  fsdp_auto_wrap_policy: TRANSFORMER_BASED_WRAP
  fsdp_backward_prefetch: BACKWARD_PRE
  fsdp_cpu_ram_efficient_loading: true
  fsdp_forward_prefetch: false
  fsdp_offload_params: false
  fsdp_sharding_strategy: FULL_SHARD
  fsdp_state_dict_type: SHARDED_STATE_DICT
  fsdp_sync_module_states: true
  fsdp_use_orig_params: False      # Set this to true
  mixed_precision:
    param_dtype: float16
    reduce_dtype: float16
    buffer_dtype: float16
machine_rank: 0
main_training_function: main
mixed_precision: fp16
num_machines: 1
num_processes: 1
rdzv_backend: static
same_network: true
tpu_env: []
tpu_use_cluster: false
tpu_use_sudo: false
use_cpu: false
(Multi-GPU-DPO-Training) root@YOUR-VM:~# cat fsdp+QLoRA.py
import torch
import os
import multiprocessing
from datasets import load_dataset
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    set_seed,
)
from peft.utils.other import fsdp_auto_wrap_policy
from accelerate import Accelerator, FullyShardedDataParallelPlugin
from trl import DPOTrainer, DPOConfig

# Set seed for reproducibility
set_seed(1234)

# Configure FSDP Plugin
fsdp_plugin = FullyShardedDataParallelPlugin(
    sharding_strategy="FULL_SHARD",
    backward_prefetch="BACKWARD_PRE",
    forward_prefetch=False,
    cpu_offload=False,
    use_orig_params=True,  # Set use_orig_params to True
    auto_wrap_policy="TRANSFORMER_BASED_WRAP",
    mixed_precision_policy={
        "param_dtype": torch.float16,
        "reduce_dtype": torch.float16,
        "buffer_dtype": torch.float16,
    },
)

# Initialize accelerator with fsdp_plugin
accelerator = Accelerator(
    mixed_precision="no",
    fsdp_plugin=fsdp_plugin,
    log_with=None,
)

# Model and training configuration
model_name = "Qwen/Qwen2.5-72B-Instruct"
sft_adapter = "./SFT_LoRA/"  # Path to your LoRA adapter fine-tuned with SFT

compute_dtype = torch.float16  # Use torch.float16 for consistency

# If you have troubles with FlashAttention, use 'standard' or 'triton' instead
attn_implementation = 'eager'

# Modify the following training arguments if you run out of memory
bs = 1  # Batch size per device
gas = 1  # Gradient accumulation steps
mseqlen = 32  # Maximum sequence length

lr = 1e-6  # Learning rate
QLoRA = True  # Quantize the base model
lora_alpha = 16
lora_dropout = 0.0
lora_r = 4

output_dir = "/workspace/DPO_LoRA"

# Tokenizer setup
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = "<|image_pad|>"
tokenizer.pad_token_id = 151655
tokenizer.padding_side = 'right'  # Adjust as needed

# Load and process the dataset
ds = load_dataset("mlabonne/orpo-dpo-mix-40k", split="train").train_test_split(test_size=0.01)
ds_train = ds['train']
ds_test = ds['test']

def process(row):
    # The first message is the prompt
    prompt_messages = tokenizer.apply_chat_template([row["chosen"][0]], tokenize=False)
    chosen_messages = tokenizer.apply_chat_template(row["chosen"][1:], tokenize=False) + tokenizer.eos_token
    rejected_messages = tokenizer.apply_chat_template(row["rejected"][1:], tokenize=False) + tokenizer.eos_token
    row["prompt"] = prompt_messages
    row["chosen"] = chosen_messages
    row["rejected"] = rejected_messages
    return row

ds_train = ds_train.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)
ds_test = ds_test.map(process, num_proc=multiprocessing.cpu_count(), load_from_cache_file=False)

# Model loading and preparation
if QLoRA:
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_storage=compute_dtype,
    )

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )
    for name, param in model.named_parameters():
        param.requires_grad = False

    def make_inputs_require_grad(module, input, output):
        output.requires_grad_(True)

    model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
else:
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=compute_dtype,
        attn_implementation=attn_implementation,
    )

# Load the LoRA adapter
model = PeftModel.from_pretrained(model, sft_adapter, is_trainable=True, adapter_name="DPO")
model.load_adapter(sft_adapter, adapter_name="reference")

# Ensure all model parameters are in torch.float16
model.to(torch.float16)

# Ensure all model parameters are on the correct device
model.to(accelerator.device)

# Training arguments
training_arguments = DPOConfig(
    output_dir=output_dir,
    eval_strategy="steps",
    do_eval=True,
    optim="adamw_hf",  # Use the PyTorch fused optimizer
    per_device_train_batch_size=bs,
    gradient_accumulation_steps=gas,
    per_device_eval_batch_size=bs,
    log_level="debug",
    save_strategy="steps",
    save_steps=5,
    logging_steps=2,
    learning_rate=lr,
    bf16=True,
    fp16=False,
    beta=0.1,
    eval_steps=2,
    max_steps=10,
    warmup_ratio=0.1,
    lr_scheduler_type="linear",
    max_length=mseqlen,
    max_prompt_length=512,
    dataset_num_proc=multiprocessing.cpu_count(),
    model_adapter_name="DPO",
    ref_adapter_name="reference",
    report_to="none",
    max_grad_norm=1.0,
)

# Initialize the DPOTrainer
trainer = DPOTrainer(
    model=model,
    args=training_arguments,
    train_dataset=ds_train,
    eval_dataset=ds_test,
    processing_class=tokenizer,
)

# Start training
```

Launch training 

```
 accelerate launch --config_file config_fsdp.yaml fsdp+QLoRA.py
```

```
***** Running training *****
  Num examples = 43,802
  Num Epochs = 1
  Instantaneous batch size per device = 1
  Total train batch size (w. parallel, distributed & accumulation) = 1
  Gradient Accumulation steps = 1
  Total optimization steps = 10
  Number of trainable parameters = 210,534,400
{'loss': 0.6931, 'grad_norm': 0.0, 'learning_rate': 8.888888888888888e-07, 'rewards/chosen': 0.0, 'rewards/rejected': 0.0, 'rewards/accuracies': 0.0, 'rewards/margins': 0.0, 'logps/chosen': 0.0, 'logps/rejected': 0.0, 'logits/chosen': 0.1, 'logits/rejected': nan, 'epoch': 0.0}
 20%|████████████████████████████▊                                                                                                                   | 2/10 [00:07<00:26,  3.37s/it]The following columns in the evaluation set don't have a corresponding argument in `FullyShardedDataParallel.forward` and have been ignored: source, prompt, question, rejected, chosen. If source, prompt, question, rejected, chosen are not expected by `FullyShardedDataParallel.forward`,  you can safely ignore this message.

```



## Training result analyze

In DPO training, the model is provided with a set of conversations, each containing the same **"prompt"** or **"question"**, along with corresponding **"chosen"** and **"rejected"** replies. The model needs to learn to distinguish between these replies and prefer generating high-quality **"chosen"** responses.

### Training data and results

The training data includes:

- **Source**: Airoboros

- **Chosen Reply**: Contains multiple rounds of dialogue

- **Rejected Reply**: Contains multiple rounds of dialogue

- **Prompt**: A descriptive text

- **Question**: The same text as the prompt

  Sometimes in the data, the **"prompt"** and **"question"** may be identical, which can serve as the starting point for the conversation in certain training settings.

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVG8MCygzbO12sANWDsyJAl6sIF5iaooXZPcDtkfNgmDaYiczO6Kb9VMHuia3KzFAkEUTrUZGTRSmYg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

  Training results are as following:

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVG8MCygzbO12sANWDsyJAG0lGSUZEgnusjGQ4IIkqWJtvKJa6r42TJcKXguutu2xuuEATUibY3sg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Next, I will combine the training data to roughly introduce the DPO training process and results.

### DPO training process and results explanation


**Core Objective of DPO**

- **Objective:** Directly optimize the model parameters to reflect human preferences without the need for a separate reward model. DPO uses human preference data to adjust the model directly, making its generated responses more aligned with human expectations.

- **Introducing the Reference Model:** To prevent the model from **deviating from its original language capabilities** during optimization, DPO introduces a **reference model** (usually a copy of the initial model with fixed parameters) as a **regularization term**.

  **Role of the Reference Model:**

  - **Maintaining Language Capabilities:** The reference model provides a baseline of the model before adjustment. By comparing with the reference model, the trained model can learn human preferences while avoiding overfitting and deviation from its original abilities, ensuring that its language understanding and generation capabilities remain intact. This helps prevent the model from prioritizing human preferences at the expense of core language skills like grammatical correctness and factual accuracy.



#### Training Data

- **Prompt:** User input, for example: "Please explain the phase changes of water."

- **Chosen Reply:** Responses evaluated by humans as high-quality, fully answering the question, and meeting expectations. These replies are typically **accurate**, **complete**, **relevant**, and **fluent**, satisfying user needs.

- **Rejected Reply:** Responses evaluated by humans as lower quality, not adequately answering the question, or not meeting expectations. These replies may lack **accuracy**, contain **incomplete information**, be **irrelevant** to the prompt, or be **less fluent**.

  **Human Evaluation Criteria:**

- **Accuracy:** Is the content of the reply correct and free from misleading information?

- **Completeness:** Does the reply fully answer the user's question?

- **Relevance:** Is the reply closely related to the user's prompt?

- **Fluency:** Is the reply grammatically correct and clearly expressed?

  **Example:**

- **Prompt:** "Please explain the phase changes of water."

- **Chosen Reply:**

  ```
  Water exists in three states: solid, liquid, and gas. Through changes in temperature and pressure, water can transition between these states. For example, ice (solid) melts into water (liquid) when heated, and water vaporizes into steam (gas) upon further heating.  
  ```

  - **Evaluation Reasoning:** The reply **accurately** explains the process of water's phase changes, provides **complete** information, is **highly relevant** to the prompt, and is **fluent**.

- **Rejected Reply:**

  ```
  Water is a very common substance found everywhere in daily life.  
  ```

  - **Evaluation Reasoning:** The reply does not address the question about the phase changes of water; the information is **incomplete**, and the **relevance is insufficient**.



#### Training Process

**Step 1: Calculate Log Probabilities**

 
**For the trained model (parameters θ):**

- **Log probability of the chosen reply:**

  ```
  log_p_model(chosen | prompt) = log( π_θ(chosen | prompt) )  
  ```

 

- **Log probability of the rejected reply:**

  ```
  log_p_model(rejected | prompt) = log( π_θ(rejected | prompt) )  
  ```

 
**For the reference model (fixed parameters):**

- **Log probability of the chosen reply:**

  ```
  log_p_ref(chosen | prompt) = log( π_ref(chosen | prompt) )  
  ```

 

- **Log probability of the rejected reply:**

  ```
  log_p_ref(rejected | prompt) = log( π_ref(rejected | prompt) )  
  ```

 

**Step 2: Calculate Preference Differences**

 

- **Preference difference for the chosen reply:**

  ```
  Δ_chosen = log_p_model(chosen | prompt) - log_p_ref(chosen | prompt)  
  ```

 

- **Preference difference for the rejected reply:**

  ```
  Δ_rejected = log_p_model(rejected | prompt) - log_p_ref(rejected | prompt)  
  ```

 

**Step 3: Construct the Loss Function**

 

- **Loss function:**

  ```
  loss = -log( exp(Δ_chosen / β) / [ exp(Δ_chosen / β) + exp(Δ_rejected / β) ] )  
  ```

  Where **β** is the temperature hyperparameter controlling sensitivity to preference differences.

- **Objective:** Minimize the loss function **loss** to make the model more inclined to generate the "chosen" reply over the "rejected" reply.

#### Training Process Example


**Assumed Values (for Illustration):**

- `log_p_model(chosen | prompt) = -5`

- `log_p_model(rejected | prompt) = -7`

- `log_p_ref(chosen | prompt) = -6`

- `log_p_ref(rejected | prompt) = -6`

  **Calculate Preference Differences:**

- `Δ_chosen = (-5) - (-6) = 1`

- `Δ_rejected = (-7) - (-6) = -1`

  **Calculate the Loss Function (assuming β = 1):**

1. **Calculate the numerator:**

   ```
   exp(Δ_chosen / β) = exp(1) ≈ 2.718  
   ```

 

2. **Calculate the denominator:**

```
exp(Δ_chosen / β) + exp(Δ_rejected / β) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
```

 

3. **Calculate the loss:**

```
loss = -log( 2.718 / 3.086 ) = -log(0.880) ≈ 0.127  
```

 
**Result Analysis:**

- **The loss value is relatively small (approximately 0.127), indicating that the model tends to prefer the "chosen" reply.**
- **Optimize Model Parameters:**
  - Through backpropagation, minimize the loss function **loss** to further enhance the model's preference for the "chosen" reply.



#### Explanation of Training Log Fields

 
Based on the DPO training process, here's a detailed explanation of each field in the training log and their importance in evaluating training effectiveness:

**Example Training Log:**

```
{  
    'loss': 0.6931,  
    'grad_norm': 0.05,  
    'learning_rate': 1e-5,  
    'rewards/chosen': 0.0,  
    'rewards/rejected': 0.0,  
    'rewards/accuracies': 0.5,  
    'rewards/margins': 0.0,  
    'logps/chosen': -15.0,  
    'logps/rejected': -15.0,  
    'logits/chosen': [0.2, 0.3, ...],  
    'logits/rejected': [0.2, 0.3, ...],  
    'epoch': 0  
}  
```

 

#### 1. `loss`

- **Meaning:**
  - Represents the loss value at the current training step, measuring the model's ability to distinguish between the "chosen" and "rejected" replies.
- **Importance:**
  - **Core Indicator:** The primary metric to evaluate training effectiveness.
  - **Training Goal:** Minimizing **loss** indicates successful learning toward preferring the "chosen" reply.
- **Indicator Trend:**
  - **Initial Stage:** `loss` is typically higher (around `0.6931`), indicating no preference.
  - **During Training:** Should decrease over time, showing the model is learning to prefer the "chosen" reply.

#### 2. `grad_norm`

- **Meaning:**
  - Represents the gradient norm of the model parameters, indicating the overall magnitude of parameter updates.
- **Importance:**
  - **Learning Intensity:** Reflects how much the model is adjusting its parameters.
  - **Training Stability:** Helps detect issues like vanishing or exploding gradients.
- **Indicator Trend:**
  - **Normal Range:** Should be within a reasonable range (e.g., `0.01` to `1`).
  - Abnormal Situations:
    - **Too Small:** Near zero may indicate lack of learning.
    - **Too Large:** May require gradient clipping to prevent instability.

#### 3. `learning_rate`

- **Meaning:**
  - Controls the step size in parameter updates during training.
- **Importance:**
  - **Convergence Speed and Stability:** Affects how quickly and smoothly the model learns.
- **Adjustment Strategy:**
  - **Slow Loss Decrease:** Consider increasing the learning rate.
  - **Unstable Training:** If loss fluctuates, decreasing the learning rate might help.

#### 4. `rewards/chosen` and `rewards/rejected`

- **Meaning:**
  - `rewards/chosen`: Reward value for the "chosen" reply (`Δ_chosen`).
  - `rewards/rejected`: Reward value for the "rejected" reply (`Δ_rejected`).
- **Importance:**
  - **Model Preference:** Indicates the model's inclination towards each reply.
- **Indicator Trend:**
  - **Initial Stage:** Both may be around `0.0` (no preference).
  - During Training:
    - `rewards/chosen` should increase.
    - `rewards/rejected` should decrease.

#### 5. `rewards/accuracies`

- **Meaning:**
  - The proportion of times the model correctly prefers the "chosen" reply.
- **Importance:**
  - **Performance Measure:** Directly evaluates preference learning.
- **Indicator Trend:**
  - **Initial Stage:** Around `0.5` (random guess).
  - **During Training:** Should approach `1.0`, indicating improved preference accuracy.

#### 6. `rewards/margins`

- **Meaning:**

  - The difference between `rewards/chosen` and `rewards/rejected`.

  ```
  rewards/margins = rewards/chosen - rewards/rejected  
  ```

- **Importance:**
  - **Discrimination Ability:** Larger margins indicate better distinction between replies.
- **Indicator Trend:**
  - Should increase during training.

#### 7. `logps/chosen` and `logps/rejected`

- **Meaning:**
  - Total log probabilities of generating the "chosen" and "rejected" replies.
- **Importance:**
  - **Probability Basis:** Used in calculating preference differences and rewards.
- **Indicator Trend:**
  - **Increasing `logps/chosen`** indicates higher probability for the "chosen" reply.
  - **Stable or decreasing `logps/rejected`** shows reduced preference for the "rejected" reply.

#### 8. `logits/chosen` and `logits/rejected`

- **Meaning:**
  - Raw output scores from the final layer before applying softmax, for both replies.
- **Importance:**
  - **Probability Calculation:** Used to compute probabilities for each token, affecting log probabilities.
- **Indicator Trend:**
  - **Ensure Valid Values:** Avoid `nan` or `inf` values.
  - **Monitor Changes:** Changes in logits reflect learning progress.

#### 9. `epoch`

- **Meaning:**
  - Indicates the current training epoch or iteration over the training dataset.
- **Importance:**
  - **Training Progress:** Helps track how far along the training is.
- **Indicator Trend:**
  - As `epoch` increases, expect improvements in other metrics.

#### Summary 

- **Adjust Training Strategies Based on Indicators:**

  - **Slow Loss Decrease:** Increase learning rate or check data quality.
  - **Gradient Issues:** If `grad_norm` is abnormal, inspect gradient computations or adjust optimizer settings.
  - **Low Preference Accuracy:** Enhance data quality or quantity.
  - **Small Reward Margins:** Adjust the temperature parameter β to influence sensitivity.

- **Emphasize the Importance of the Reference Model:**

  - **Maintaining Language Capabilities:** Ensures the model doesn't overfit human preferences at the cost of language understanding and generation skills.
  - **Balancing Objectives:** Optimizes for human preference while retaining overall model performance.

- **Continuous Monitoring and Adjustment:**

  - **Regular Evaluation:** Use a validation set to assess performance and prevent overfitting.

  - **Dynamic Adjustment:** Modify training strategies based on log indicators to optimize the model.

    By understanding DPO's core concepts, training processes, and how to interpret key training metrics, you can effectively train a model that aligns with human preferences while maintaining strong language capabilities.



### DPO training process and results explanation in Chinese

- **目标：** 直接优化模型参数来反映人类偏好，而无需通过单独的奖励模型。DPO 利用人类偏好数据直接调整模型，使其生成的回复更符合人类期望。

- **引入参考模型：** 为了防止模型在优化过程中**偏离其原有的语言能力**，DPO 引入了一个**参考模型**（通常是初始模型的副本，参数固定）作为**正则化项**。

  **参考模型的作用：**

  - **保持语言能力：** 参考模型提供了模型在未调整前的基线。通过与参考模型的对比，被训练模型在学习人类偏好的同时，避免过度拟合和偏离原有能力，确保自身的语言理解和生成能力不受损。这有助于防止模型为追求符合人类偏好而忽视语言能力，例如语法正确性、知识准确性等。

**训练数据**

- **提示（Prompt）：** 用户输入，例如：“请解释水的物态变化。”

- **选择回复（Chosen Reply）：** 被人类评估为高质量、完整回答了问题且符合预期的回复。这些回复通常**准确**、**完整**、**相关**，并且语言**流畅**，满足用户需求。

- **拒绝回复（Rejected Reply）：** 被人类评估为质量较低、未充分回答问题或不符合预期的回复。这些回复可能**准确性不足**、**信息不完整**、**与提示不相关**，或语句**不流畅**。

  

  **人类评估的标准：**

- **准确性（Accuracy）：** 回复内容是否正确、无误导性。

- **完整性（Completeness）：** 回复是否全面地回答了用户的问题。

- **相关性（Relevance）：** 回复是否与用户的提示紧密相关。

- **语言流畅度（Fluency）：** 回复是否语言通顺、表达清晰。

  

  **示例：**

- **提示：**“请解释水的物态变化。”

- **选择回复：**

  ```
  水有三种物态：固态、液态和气态。通过温度和压力的变化，水可以在这三种物态之间转换。例如，冰（固态）受热会融化成水（液态），水加热会变成水蒸气（气态）。  
  ```

  - **评估理由：** 回复**准确**地解释了水的物态变化过程，信息**完整**，与提示**高度相关**，语言**流畅**。

- **拒绝回复：**

  ```
  水是一种非常常见的物质，生活中到处都有。  
  ```

  - **评估理由：** 回复没有针对提示回答物态变化的问题，信息**不完整**，**相关性不足**。



#### **训练过程**

#### **步骤 1：计算对数概率**

 
**对于被训练模型（参数为 θ）：**

- **选择回复的对数概率：**

  ```
  log_p_model(chosen | prompt) = log( π_θ(chosen | prompt) )  
  ```

 

- **拒绝回复的对数概率：**

  ```
  log_p_model(rejected | prompt) = log( π_θ(rejected | prompt) )  
  ```

 
**对于参考模型（参数固定）：**

- **选择回复的对数概率：**

  ```
  log_p_ref(chosen | prompt) = log( π_ref(chosen | prompt) )  
  ```

 

- **拒绝回复的对数概率：**

  ```
  log_p_ref(rejected | prompt) = log( π_ref(rejected | prompt) )  
  ```

 

#### **步骤 2：计算偏好差值**

 

- **选择回复的偏好差值：**

  ```
  Δ_chosen = log_p_model(chosen | prompt) - log_p_ref(chosen | prompt)  
  ```

 

- **拒绝回复的偏好差值：**

  ```
  Δ_rejected = log_p_model(rejected | prompt) - log_p_ref(rejected | prompt)  
  ```

 

#### **步骤 3：构建损失函数**

 

- **损失函数形式：**

  ```
  loss = -log( exp(Δ_chosen / β) / [ exp(Δ_chosen / β) + exp(Δ_rejected / β) ] )  
  ```

  其中，**β** 是温度超参数，控制对偏好差异的敏感程度。

- **目标：** 最小化损失函数 **loss**，使模型更倾向于生成“选择”回复而非“拒绝”回复。



### **训练过程示例**

 
**假设值（用于说明）：**

- `log_p_model(chosen | prompt) = -5`

- `log_p_model(rejected | prompt) = -7`

- `log_p_ref(chosen | prompt) = -6`

- `log_p_ref(rejected | prompt) = -6`

  **计算偏好差值：**

- `Δ_chosen = (-5) - (-6) = 1`

- `Δ_rejected = (-7) - (-6) = -1`

  **计算损失函数（假设 β = 1）：**

1. **计算分子：**

   ```
   exp(Δ_chosen / β) = exp(1) ≈ 2.718  
   ```

 

2. **计算分母：**

```
exp(Δ_chosen / β) + exp(Δ_rejected / β) = exp(1) + exp(-1) ≈ 2.718 + 0.368 ≈ 3.086  
```

 

3. **计算损失：**

```
loss = -log( 2.718 / 3.086 ) = -log(0.880) ≈ 0.127  
```

 
**结果分析：**

- **损失值较小（约 0.127），表明模型倾向于偏好“选择”回复。**
- **优化模型参数：**
  - 通过反向传播，最小化损失函数 **loss**，进一步增强模型对“选择”回复的偏好。 

### **训练日志字段解释**

 
结合上述 DPO 训练过程，以下是训练日志中每个字段的详细解释，以及它们在评估训练效果时的重要性。我们还将通过实际训练中的示例，说明这些指标的变化趋势。

**训练日志示例：**

```
{  
    'loss': 0.6931,  
    'grad_norm': 0.05,  
    'learning_rate': 1e-5,  
    'rewards/chosen': 0.0,  
    'rewards/rejected': 0.0,  
    'rewards/accuracies': 0.5,  
    'rewards/margins': 0.0,  
    'logps/chosen': -15.0,  
    'logps/rejected': -15.0,  
    'logits/chosen': [0.2, 0.3, ...],  
    'logits/rejected': [0.2, 0.3, ...],  
    'epoch': 0  
}  
```

 

#### **1. `loss`**

- **含义：**
  - **损失值**，衡量模型在当前训练步骤中对“选择”回复和“拒绝”回复的区分能力。
- **重要性：**
  - **核心指标：** 评估模型训练效果的主要依据。
  - **训练目标：** 最小化 **loss**，表示模型更成功地偏好“选择”回复。
- **指标变化趋势：**
  - **初始阶段：** `loss` 值通常较高，例如约 `0.6931`，对应于模型对两种回复没有偏好。
  - **训练过程中：** 随着训练进行，`loss` 应该逐渐降低，表明模型正在学习更偏好“选择”回复。

#### **2. `grad_norm`**

- **含义：**
  - **梯度范数**，表示模型参数更新的总体变化量。
- **重要性：**
  - **学习力度：** 反映模型在当前训练步骤中的学习强度。
  - **训练稳定性：** 监控梯度大小，防止梯度消失或爆炸。
- **指标变化趋势：**
  - **正常范围：** `grad_norm` 应保持在适当范围内，例如 `0.01` 到 `1`。
  - **异常情况：**
    - **过小（接近 0）：** 可能表示模型未在学习。
    - **过大：** 需要考虑梯度裁剪，防止梯度爆炸。

#### **3. `learning_rate`**

- **含义：**
  - **学习率**，控制模型参数更新步长的大小。
- **重要性：**
  - **收敛速度和稳定性：** 决定模型的学习速度和训练的稳定性。
- **指标调整策略：**
  - **根据训练效果：** 如果 `loss` 下降缓慢，可以适当增大学习率；如果损失震荡或增大，可能需要减小学习率。
- **示例：**
  - **初始学习率：** 常见设置为 `1e-5`。
  - **调整策略：** 根据训练效果，动态调整学习率。

#### **4. `rewards/chosen` 和 `rewards/rejected`**

- **含义：**
  - `rewards/chosen`：模型对“选择”回复的奖励值，即偏好差值 `Δ_chosen`。
  - `rewards/rejected`：模型对“拒绝”回复的奖励值，即偏好差值 `Δ_rejected`。
- **重要性：**
  - **模型倾向性：** 反映模型对两种回复的倾向程度。
- **指标变化趋势：**
  - **初始阶段：** 两者可能接近 `0.0`，表示无明显偏好。
  - **训练过程中：**
    - **`rewards/chosen` 应逐渐增大**，表示模型对“选择”回复的倾向增强。
    - **`rewards/rejected` 应逐渐减小**，表示模型对“拒绝”回复的倾向减弱。

#### **5. `rewards/accuracies`**

 **含义：**

- - **偏好准确率**，模型正确偏好“选择”回复的比例。
- **重要性：**
  - **性能衡量：** 直接评估模型是否成功地偏好高质量回复。
- **指标变化趋势：**
  - **初始阶段：** 可能接近 `0.5`，相当于随机选择。
  - **训练过程中：** 应逐渐提升，朝 `1.0` 逼近，表示模型越来越多地正确偏好“选择”回复。

#### **6. `rewards/margins`**

- **含义：**

  - **奖励差距**，即 `rewards/chosen` 和 `rewards/rejected` 之间的差值。

  - **计算公式：**

    ```
    rewards/margins = rewards/chosen - rewards/rejected  
    ```

- **重要性：**
  - **区分能力：** 差距越大，模型对两种回复的区分度越高。
- **指标变化趋势：**
  - **初始阶段：** 可能接近 `0.0`。
  - **训练过程中：** 应逐渐增大，表示模型更好地区分并偏好“选择”回复。

#### **7. `logps/chosen` 和 `logps/rejected`**

- **含义：**
  - `logps/chosen`：模型生成“选择”回复的总对数概率。
  - `logps/rejected`：模型生成“拒绝”回复的总对数概率。
- **重要性：**
  - **概率基础：** 用于计算偏好差值和奖励值。
- **指标变化趋势：**
  - **训练过程中：**
    - **`logps/chosen` 应逐渐增大（数值趋向于 0）**，表示模型对“选择”回复的生成概率增加。
    - **`logps/rejected` 可能保持不变或减小**，表示对“拒绝”回复的生成概率降低。

#### **8. `logits/chosen` 和 `logits/rejected`**

- **含义：**
  - **原始输出得分**，模型在最后一层对两种回复的未归一化得分（一般是一个向量）。
- **重要性：**
  - **概率计算：** `logits` 用于计算每个词元的概率分布，进而计算对数概率。
- **指标变化趋势：**
  - **数值正常：** 确保 `logits` 的数值没有异常（如 `nan` 或 `inf`）。

#### **9. `epoch`**

- **含义：**
  - **训练轮次**，模型遍历整个训练数据的次数。
- **重要性：**
  - **训练进度：** 了解模型当前所处的训练阶段。
- **指标变化趋势：**
  - **随着 `epoch` 增加：** 应该看到模型各项性能指标的提升。



### **总结**

- **根据指标调整训练策略：**
  - **损失下降缓慢：** 可以适当增大学习率或检查数据质量。
  - **梯度异常：** 如果 `grad_norm` 异常，检查梯度计算或调整优化器参数。
  - **偏好准确率低：** 增加训练数据量或改进数据质量。
  - **奖励差距小：** 调整温度参数 β，影响模型对偏好差异的敏感程度。
- **强调参考模型的重要性：**
  - **保持语言能力：** 参考模型确保被训练模型不会过度偏向人类偏好而丧失原有的知识和语言表达能力。
  - **平衡优化目标：** 在优化人类偏好的同时，保持模型的整体性能。
- **持续监控与调整：**
  - **定期评估：** 使用验证集评估模型性能，防止过拟合。
  - **动态调整：** 根据训练日志中的指标，适时调整训练策略以优化模型。
