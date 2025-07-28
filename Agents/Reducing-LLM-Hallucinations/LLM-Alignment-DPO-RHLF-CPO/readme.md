# LLM Alignment DPO RHLF CPO

**一、RLHF与DPO**

在训练大型语言模型（如聊天模型）时，人类反馈强化学习（RLHF）通常使用近端策略优化（Proximal Policy Optimization, PPO）方法。这种方法可以有效地使模型的行为与人类偏好保持一致。然而，RLHF的过程可能既不稳定又复杂。因此，研究人员正在探索更简单、更稳定的方法来训练这些模型，使其更好地符合人类的偏好，而无需依赖复杂的强化学习过程。

RLHF（Reinforcement Learning from Human Feedback）实际上在整个过程中涉及到四个不同的模型：

1. 参考模型（reference model），通过监督式精调（SFT）在指令数据集上训练得到。

2. 奖励模型（reward model），训练用来预测人类偏好的排名。

3. 价值模型（value model），通常由奖励模型初始化。

4. 我们希望通过RLHF训练的模型（policy），通常由参考模型初始化。

   

   DPO 直接偏好优化（Direct Preference Optimization）则需要两个模型：

1.参考模型，同样是使用SFT在指令数据集上精调得到的。

2.我们希望通过DPO训练的基础模型（base model）。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWkavyXUFb7YmV633SNtwPQA9RorrzDeH5NiaBm0TQC2qZukibcdrjLFB2M3aAW5ibLhOXjDwiaTVEGvw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

在DPO（Direct Preference Optimization）中，参考模型与基础模型的区别主要在于它们在优化过程中的角色和使用方法。

1. **参考模型（Reference Model）：**

   - 这是通过监督式学习（SFT）在一个指令数据集上训练得到的模型，它代表了对特定任务的基本理解和执行能力。
   - 参考模型在DPO中充当了一个基线，用来比较和评估其他模型生成的输出。
   - 在某些情况下，参考模型可以用作后续DPO训练过程的初始状态，尽管这不是必须的。

2. **基础模型（Base Model）：**

   - 这是我们想要通过DPO进行优化的模型，它可能是未经训练的，或者是已经在一些任务上有了初步训练的模型。

   - 基础模型在DPO过程中将直接根据人类的反馈进行训练，学习如何产生更符合人类偏好的输出。

   - 通过DPO的训练，基础模型将逐渐学会模仿那些被人类评价为高质量的输出。

     在DPO中，参考模型主要是用作比较的基准，而基础模型则是实际进行优化和学习的目标。通过这种方式，DPO旨在通过分类问题简化优化过程，使得基础模型能够直接从人类的偏好中学习，而无需依赖于复杂的奖励函数或强化学习算法。

     

**二、RLHF、RLAIF、DPO偏见**

RLHF（Reinforcement Learning with Human Feedback）和RLAIF（Reinforcement Learning with AI Feedback）是两种用于微调大型语言模型（LLM）的方法。它们的主要区别在于反馈的来源：RLHF依赖于人类提供反馈，而RLAIF则使用另一个LLM生成反馈。

RLHF的优点在于，它可以训练AI系统处理诸如内容审查等用例，其中人类对于构成仇恨言论、欺凌和其他不良行为的语言有比AI更好的判断。

RLHF依赖于人类提供反馈，这可能会带来一些挑战：

1. 成本和可扩展性：对于需要领域专家特定知识和技能集的反馈的用例，这个过程可能会变得昂贵和耗时。因此，RLHF可能在大规模应用中面临困难。
2. 反馈的一致性：人类反馈可能会受到个人偏见和主观性的影响，这可能会影响训练的一致性和质量。



RLAIF试图通过使用另一个大型语言模型（LLM）生成反馈来解决这些问题。这种方法的优点是，它可以大大降低反馈获取的成本，并提高反馈的一致性。然而，它也有自己的挑战，比如可能会复制和放大原始模型的偏见和错误。这就是为什么RLAIF和RLHF通常会结合使用，以充分利用两者的优点。



- DPO的偏见主要来自于用于生成反馈的AI模型。如果这个模型在训练数据中存在偏见，那么这种偏见可能会被复制到微调的模型中。

- RLAIF的偏见也主要来自于用于生成反馈的AI模型。如果这个模型在训练数据中存在偏见，那么这种偏见可能会被复制到微调的模型中。

- RHLF的偏见主要来自于人类提供反馈。如果提供反馈的人有某种偏见，那么这种偏见可能会被反馈到模型中。

  

总的来说，这三种方法都需要谨慎地处理偏见问题。这通常需要在数据收集和模型训练的过程中采取一些措施，如使用多元化的数据源，进行公平性和偏见的审核，以及在可能的情况下，使用透明和可解释的模型。这也是一个活跃的研究领域，研究人员正在寻找更好的方法来理解和减少AI偏见。



**三、在DPO的场景中参考模型的作用？**

**https://huggingface.co/docs/trl/dpo_trainer**

DPO（Direct Preference Optimization）训练框架中，参考模型的意义如下：

1. **隐式奖励计算**：参考模型用于计算所谓的隐式奖励。在DPO训练中，我们不直接训练一个奖励模型来输出奖励值；相反，我们使用参考模型来估计偏好和被拒绝回答的概率，并基于这些概率来计算隐式奖励。这种隐式奖励是用来指导基础模型（被训练的模型）的学习，使其更倾向于生成被认为是“好”的输出。

2. **损失函数的基础**：隐式奖励差异（即参考模型和基础模型对选定回答和被拒绝回答的概率差异）用作损失函数的基础。这个损失函数在DPO训练中被最大化，目的是提高模型生成偏好回答的概率。

3. **提供稳定性**：参考模型作为训练过程中的固定点，提供了稳定性，帮助避免基础模型在学习过程中偏离过远。它作为一个常数存在，使得基础模型的训练更加稳定和可预测。

4. **模型架构的一致性**：DPO训练要求参考模型和基础模型具有相同的架构。这是因为在计算隐式奖励时，参考模型和基础模型需要在同样的输入上输出可比较的概率值。

5. **简化训练流程**：与传统的强化学习方法相比，DPO通过使用参考模型来简化训练流程。这种方法避免了设计复杂的奖励模型和价值模型，从而降低了训练的复杂性。

6. **参数beta的作用**：在DPO训练中，beta是一个温度参数，用于缩放隐式奖励差异。这个参数控制了优化过程中对参考模型行为的依赖程度。beta值越小，基础模型在优化过程中越自由，对参考模型的依赖越小。

   总的来说，参考模型在DPO训练中提供了一个稳定的比较基准，使得基础模型能够在优化过程中有一个清晰的方向，并且通过隐式奖励的方式简化了优化流程。这使DPO成为一种高效的语言模型优化方法，特别是在处理偏好数据时。



我们来看一段DPO的代码。DPO的参考模型是之前使用监督式精调（SFT）在特定数据集上训练过的Mistral 7B模型。在这个上下文中，参考模型被用来初始化一个适配器（adapter），这个适配器随后被用于DPO训练。

```
model = PeftModel.from_pretrained(model, "kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", is_trainable=True, adapter_name="DPO")  
model.load_adapter("kaitchup/Mistral-7B-v0.1-SFT-ultrachat-v2", adapter_name="reference")
```


这里，`model` 是基础模型，即要通过DPO进行训练的模型。`load_adapter` 方法用来加载一个名为 "reference" 的适配器，这个适配器是在SFT过程中使用Mistral 7B训练得到的，并且其训练是基于 "ultrachat" 数据集的。在DPO训练中，这个 "reference" 适配器用作比较的基准，以帮助DPO评估生成的输出是否符合人类的偏好。

在DPO中，参考模型的作用是提供一个与被训练模型的输出相比较的标准。在训练期间，系统会计算参考模型输出和被训练模型输出的概率对数差异，并将其乘以一个系数（beta），这个差异用于指导DPO的训练过程，使得被训练模型能够生成更优选的响应。



实际上，在选择DPO（Direct Preference Optimization）的参考模型时，通常会选择与基础模型（在这种情况下是Mistral 7B）结构和参数设置相同或相似的模型。这样做的理由包括：

1. **相似性**：相同或相似的模型结构保证了在比较基础模型和参考模型的输出时，差异主要来自于模型权重的不同，而非模型架构的不同。

2. **一致性**：使用同一模型架构可以确保生成的输出有可比性，这对于训练过程中评估和提升模型性能至关重要。

3. **简化训练**：如果参考模型与基础模型在架构上一致，可以简化训练流程，因为可以共享部分模型组件，这有助于减少内存消耗和计算需求。

4. **适配器技术**：在某些实现中，如上文中的例子，使用了适配器技术来对模型进行微调。这种情况下，参考模型和基础模型之间的适配器可以共享，减少了资源的需求。

   

需要注意的是，在下面的代码演示中，训练参考模型和DPO训练基础模型，用的不同的数据集：

dataset_train_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="train_sft")

dataset_test_sft = load_dataset("HuggingFaceH4/ultrachat_200k", split="test_sft[:5%]")

dataset_train_dpo = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split="train_prefs")

dataset_test_dpo = load_dataset("HuggingFaceH4/ultrafeedback_binarized", split="test_prefs[:5%]")

两个数据集如下：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31Qg16gInAqzxm4XSQHf94ib3WaQTfbRKHYQXEpMOu2pJ7HUKBqbumvDA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31vBXuMoJbd2icF70YePHZpdBedtLx0oUTTIyKjVicMaOdG7ibKhB2SGP6Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**四、我们要用DPO训练一个mistral，但又用一个SFT的mistral做参考模型，****为什么不基于一个SFT的模型直接做微调呢？**

使用一个SFT（Supervised Fine-Tuning）的Mistral作为参考模型来训练另一个Mistral模型确实听起来有些重复，但在DPO（Direct Preference Optimization）的上下文中，这样做是有其特定目的和理由的。

DPO方法的核心在于直接优化模型以生成符合人类偏好的输出，这通常是通过对比人类标注的“优选”输出与“非优选”输出来实现的。DPO的目标是训练出一个模型，使其能够系统性地产生高质量的输出。

在这个过程中，SFT的Mistral模型作为参考模型的作用主要是提供一个性能基线。它代表了模型在没有接受特定偏好训练之前的能力水平。而DPO过程中的Mistral模型则是在这个基线之上进一步优化以生成符合人类偏好的输出。

为什么不直接在SFT的模型基础上继续微调，而是使用DPO？这里有几个原因：

1. **特定的优化目标**：DPO是为了优化一个特定的目标——与人类偏好一致的输出。这不仅仅是提升模型在一般性任务上的表现，而是让模型学会在给定的人类反馈框架内进行决策。

2. **分类问题的简化**：DPO将复杂的强化学习问题转化为一个相对简单的分类问题，这使得模型的训练更加直接和高效。

3. **避免奖励模型的不稳定性**：在传统的RLHF（Reinforcement Learning from Human Feedback）方法中，需要训练一个奖励模型来指导模型的训练，这个过程可能会很不稳定。DPO通过直接利用人类的反馈来避免这种不稳定性。

4. **计算效率**：DPO通常比传统的RLHF更高效，因为它避免了多个模型的训练和维护，减少了计算资源的需求。

5. **高质量的初始状态**：SFT模型提供了一个高质量的初始状态，理论上它已经对相关任务有了良好的表现。DPO在这个基础上进一步提升模型在特定偏好上的表现，而非从头开始训练。

   因此，尽管DPO使用SFT的Mistral作为参考模型可能看起来有些重复，但实际上这是为了实现更精确的优化目标，并提高训练的效率和稳定性。


总之，尽管SFT模型在很多情况下已经足够好，但DPO提供了一种基于人类的直接反馈进行模型微调的方法，这可以针对特定的应用场景进一步优化模型性能。这种基于人类偏好的微调方法在确保模型输出与人类评价者期望一致的同时，还可以提高模型的可适应性和泛化能力。

**五、DPO是不是更适合分类的场景？**

DPO（Direct Preference Optimization）方法虽然在本质上依赖于分类问题的框架（即区分人类偏好的高质量和低质量输出），但它并不局限于传统的分类任务。实际上，DPO是为了解决语言模型在生成任务中的优化问题而设计的。

在DPO中，"分类"不是指将实例分配给预先定义好的标签，而是指识别和优化模型输出以使其符合人类的直接偏好。这种偏好通常是基于比较两个输出响应的质量来定义的，而不是将输出分到固定的类别中。

DPO特别适用于以下几种场景：

1. **文本生成**：在诸如聊天机器人、文章或诗歌生成等任务中，DPO可以帮助模型学习如何生成更加自然、有吸引力或符合特定风格的文本。

2. **内容推荐**：DPO可以用来优化推荐系统的算法，使其更准确地反映用户的喜好。

3. **交互式应用**：在需要根据用户输入动态生成响应的应用中，DPO可以帮助模型更好地理解用户的意图和偏好。

4. **个性化服务**：DPO可以用于个性化服务，比如个性化新闻摘要或产品建议，它可以使模型学习用户的特定喜好。

   尽管DPO借鉴了分类问题的一些技术，但其目标是为了改善生成任务中的模型性能，使之能够创建出高度符合人类偏好的输出。这一点使其与传统的分类任务有着本质的区别。因此，DPO更多地被视为一种特定于生成任务的优化策略，而不仅仅是一种分类方法。

**六、核心代码参考**

第一步，SFT出参考模型（使用HuggingFaceH4/ultrachat_200k）：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31TRnRNZ1KTQBNQmFJvLiaNgtQ2sGFTEDzU8v83dRkYKxib3xpTeNONxuQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31PuTVUk3nlGATuQOy5PRE5FibmVIyJ7EADxOzVafzS2n068OotrWv9ow/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31sAhNG7fQ2pNpHRn8578j4VHmM6WuVdRSa5QzlqicfAXgYAmoCppia5wg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

微调过程中的资源消耗：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31DXj7XpFcgfGCcwkkkhCPgkwClsOicg7PmyZibnibvO9ic8vuiaR3DjDEUvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

接下来使用SFT后的模型作为参考模型，对基础模型进行DPO：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31tcnFcDhJ60icpRHzVaknNPT9UVo2Xwqo5I2Uq2EX0gvM6mpIBokHQDQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31qFmelfEAkT4xrcqkAmxICxbmROJnicGbUTto7LAYvyfGhJ7WHqoMMrQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31hQmrMLYvVxIibPNibVqJ2MNbEKM6lkJLOoxZ4sADSTm8yROVuBMUF10w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31EibScDruPpInR1dnjgYSvKFoSwfm1ZWE2dyHXqLo4Akz3Fq1IoRW5vA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

微调过程中的资源开销

bs=4:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31PLGFDxOAm0ZvUSyEADqs8IfyF60Dl7W7Ae6F3quo8Mex2BiaRkxNVvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

bs=16：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM311icJ9J9XMMtia73zuKkJGvnZ4UY9mmtjicvGnFxbWcxXVx7m6fewqAFsw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)把BS调整成32：![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31JiaDvRWfI53axaYC2IZBIFejPkhr5ibIRy3X4x8ozt6auGsXicbZ3fAfQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31yGktkn5WIczClZnJyoM9GDjicHFHJzFib3ZGCgAiav7fMIgBFhUyklhvQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUXuFTxdR1SWPoED75CVM31Y0okm1V2QqAjsUnkl2LhuzsR0QFKmxWfJWlC0VP1a5h8XibmWcO4sgA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

表格记录了一个机器学习模型训练过程中的不同指标和它们在不同训练步骤的值。每一列的含义如下：

1. **Step**：训练过程中的步骤编号，每个数字代表模型完成的一个批次(batch)的训练。
2. **Training Loss**：在每个训练步骤后计算的训练损失值，这是一个衡量模型在训练数据上表现的指标，值越小表示模型在训练集上的表现越好。
3. **Validation Loss**：验证损失值，它是在未参与训练的数据集（验证集）上计算的损失值，用以评估模型的泛化能力。
4. **Rewards/chosen**：在DPO训练中，这个指标可能表示被选择的输出（即人类偏好的输出）对应的奖励值。
5. **Rewards/rejected**：被拒绝的输出（即人类不偏好的输出）对应的奖励值。
6. **Rewards/accuracies**：奖励准确度，可能表示模型在区分人类偏好和不偏好的输出方面的准确性。
7. **Rewards/margins**：奖励边际，即被选择和被拒绝的输出间的奖励差距，这个值越大表示模型在区分偏好输出上的性能越好。
8. **Logps/rejected** 和 **Logps/chosen**：这可能是指对数概率（log probabilities）值，分别对应被拒绝和被选择输出的对数概率，通常用于概率的数值稳定性处理。
9. **Logits/rejected** 和 **Logits/chosen**：这些是在模型的最后一个线性层输出之前的值，即logits，也是对应于被拒绝和被选择输出的。在神经网络中，logits通常是经过最后一层线性变换但尚未应用激活函数的值。