GPT的pretrain是指用大量的无标签的文本数据来训练GPT模型，使其能够学习语言的规律和知识，从而具备自然语言理解和生成的能力。在这个阶段，GPT模型需要对文本进行编码，即将文本转换成数字，从而进行计算和操作。这个过程需要用到词汇表和合并规则，它们是GPT模型的分词工具，可以将文本切分成最优的子词，然后用数字来表示这些子词。

**1.环境准备**

Azure GPU VM：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPnBMAREBNZib7BsfUryFiceYu5ibk8XAdiaghHhR3AmON7EEPxbPSib01xkA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

\#apt-get install nvidia-container-toolkit 

\#systemctl restart docker

```
#docker run -d -t --network=host --gpus all --privileged --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 --name megatron-deepspeed -v /etc/localtime:/etc/localtime -v /root/.ssh:/root/.ssh nvcr.io/nvidia/pytorch:21.10-py3
```

\#docker exec -it megatron-deepspeed bash

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPrup3SrBpMs2u45AWWvJA5r9REqeGoLVe923SpYe7esRUfOvwXKPW5g/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

```
git clone https://github.com/bigscience-workshop/Megatron-DeepSpeedcd Megatron-DeepSpeedpip install -r requirements.txt
```

**2.训练数据准备**

```
wget https://huggingface.co/bigscience/misc-test-data/resolve/main/stas/oscar-1GB.jsonl.xzwget https://s3.amazonaws.com/models.huggingface.co/bert/gpt2-vocab.jsonwget https://s3.amazonaws.com/models.huggingface.co/bert/gpt2-merges.txt
```

```
xz -d oscar-1GB.jsonl.xz
```

```
python3 tools/preprocess_data.py \--input oscar-1GB.jsonl \--output-prefix meg-gpt2 \--vocab gpt2-vocab.json \--dataset-impl mmap \--tokenizer-type GPT2BPETokenizer \--merge-file gpt2-merges.txt \--append-eod \--workers 8
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPRRpvcJ8btbYyuTzL5CBr9xrC0iaJkdT1Fd8Fln6Nf3hbITjVvrCHMZA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



```
mkdir datacp meg-gpt2* ./datacp gpt2* ./data
```



预训练脚本：

```
#vim pretrain_gpt2.sh
#! /bin/bash
# Runs the "345M" parameter model
GPUS_PER_NODE=4# Change for multinode configMASTER_ADDR=localhostMASTER_PORT=6000NNODES=1NODE_RANK=0WORLD_SIZE=$(($GPUS_PER_NODE*$NNODES))
DATA_PATH=data/meg-gpt2_text_documentCHECKPOINT_PATH=checkpoints/gpt2
DISTRIBUTED_ARGS="--nproc_per_node $GPUS_PER_NODE --nnodes $NNODES --node_rank $NODE_RANK --master_addr $MASTER_ADDR --master_port $MASTER_PORT"
python -m torch.distributed.launch $DISTRIBUTED_ARGS \       pretrain_gpt.py \       --tensor-model-parallel-size 4 \       --pipeline-model-parallel-size 4 \       --num-layers 24 \       --hidden-size 1024 \       --num-attention-heads 16 \       --micro-batch-size 4 \       --global-batch-size 8 \       --seq-length 1024 \       --max-position-embeddings 1024 \       --train-iters 5000 \       --lr-decay-iters 320000 \       --save $CHECKPOINT_PATH \       --load $CHECKPOINT_PATH \       --data-path $DATA_PATH \       --vocab-file data/gpt2-vocab.json \       --merge-file data/gpt2-merges.txt \       --data-impl mmap \       --split 949,50,1 \       --distributed-backend nccl \       --lr 0.00015 \       --lr-decay-style cosine \       --min-lr 1.0e-5 \       --weight-decay 1e-2 \       --clip-grad 1.0 \       --lr-warmup-fraction .01 \       --checkpoint-activations \       --log-interval 10 \       --save-interval 500 \       --eval-interval 100 \       --eval-iters 10 \       --fp16
```

Megatron源码有一个断言需要注释掉，以保证代码正常运行。

\#vim /workspace/Megatron-DeepSpeed/megatron/model/fused_softmax.py +191

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPfUywm6qSw0xEjUfiazkYJFicXCWJ93z3nfk6NCYrrdyOCLIze6bbr6bg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**3.运行预训练**

\#nohup sh ./pretrain_gpt2.sh & disown

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPe3X4vme24ribVMlhD8ZMJPQ3pLUaa3ibe3SeicorlJgp02tVeWfYn78Mg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPOibkUp4Sf31ib8Iib2JomCPdfsWV2s9ia2PkHqMxxC1s0icJY8LbytAicjCw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

如果需要kill进程：

ps -ef | awk '/pretrain_gpt/ {print $2}' | xargs kill -9



**4.训练调优-提升并发（以及几个错误处理）**

root@gpuvm:/workspace/Megatron-DeepSpeed# vi ./pretrain_gpt2.sh

- GPUS_PER_NODE=4
- --tensor-model-parallel-size 4 
- --pipeline-model-parallel-size 1



\#nohup sh ./pretrain_gpt2.sh & disown

```
tail -f nohup.out
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPQH1RaibZwYhkna3dCdcvmeAxuRdNNniaUygp17mfgeVKHozlQVcFYmmQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

从日志中，我看到了一个错误信息：

AssertionError: padded_vocab_size value from checkpoint (50304) is not equal to the input argument value (50688).

这个错误表明从一个检查点（checkpoint）加载模型，但是检查点中的padded_vocab_size值（50304）与输入参数值（50688）不匹配。这可能是因为在不同的设置下训练了模型，然后尝试在一个新的设置下加载它。

需要确保输入参数与检查点中的参数匹配。可以尝试将padded_vocab_size参数设置为50304，或者找到一个与当前设置匹配的检查点。

另外，我还看到了一个CUDA错误：

terminate called after throwing an instance of 'c10::CUDAError' what(): CUDA error: driver shutting down

这可能是由于各种原因导致的，包括GPU内存不足，驱动程序问题，或者CUDA版本与PyTorch版本不兼容等。可能需要检查GPU状态，更新驱动程序，或者确保CUDA和PyTorch版本是兼容的。

```
root@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# ls
iter_0000500  iter_0001000  iter_0001500  iter_0002000  iter_0002500  latest_checkpointed_iteration.txtroot@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# rm -rf ./*root@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# cd ..
```

重新发起训练：

\#nohup sh ./pretrain_gpt2.sh & disown

\#tail -f nohup.out

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPgA1TIGpxibdQnUkNwiciaicria3q9ibSsBJIkLAb8iaxIteGMfE8ibLtx7ezZg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOP4YPpMUgoIrRAOffzJlGibTsqdOc5ZLmxdU48MxU5PWiablnjE2AyA8ibQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

从的错误日志来看，训练过程在结束时遇到了一个CUDA错误，导致程序崩溃。错误信息显示"CUDA error: driver shutting down"，这可能是由于以下几个原因：

1. GPU内存不足：模型可能太大，或者批量大小可能太大，导致GPU内存不足。可以尝试减小模型大小或批量大小。
2. CUDA驱动程序问题：CUDA驱动程序可能存在问题。可以尝试更新CUDA驱动程序到最新版本。
3. 硬件问题：GPU可能存在硬件问题。如果可能的话，可以尝试在另一块GPU上运行程序，看看问题是否仍然存在。

此外，错误日志还建议设置环境变量`CUDA_LAUNCH_BLOCKING=1`以进行调试。这将使CUDA操作同步执行，这样在出现错误时，可以得到更准确的堆栈跟踪。可以通过在脚本开始时添加以下Python代码来设置这个环境变量：

```
import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
```

或者在运行脚本之前在命令行中设置它：

```
export CUDA_LAUNCH_BLOCKING=1
```

然后再运行脚本，看看是否可以得到更多关于错误的信息。



后来调整参数后解决问题，正确的参数看下面。



**5.训练调优-使用deepspeed**

在上面的小节中，我们通过提升并发加快了训练速度，但我们并没有启用deepspeed。这次我们调整脚本。**
**

root@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# rm -rf ./*

root@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# cd ../..

```
!/bin/bash# Adapted to use deepspeed on a single node# Multi-node will require either a `hostfile` or switching to `torch.distributed.launch`
# adjust to the number of GPUs to useN_GPUS=4
CHECKPOINT_PATH=checkpoints/gpt2VOCAB_FILE=data/gpt2-vocab.jsonMERGE_FILE=data/gpt2-merges.txtDATA_PATH=data/meg-gpt2_text_documentCONFIG_JSON=deepspeed_config.json
GPT_ARGS=" \    --num-layers 24 \    --hidden-size 1024 \    --num-attention-heads 16 \    --seq-length 1024 \    --max-position-embeddings 1024 \    --tensor-model-parallel-size 4 \    --pipeline-model-parallel-size 1 \    --micro-batch-size 1 \    --global-batch-size 4 \    --lr-decay-iters 320000 \    --lr 0.00015 \    --min-lr 1.0e-5 \    --lr-decay-style cosine \    --train-iters 5000 \    --vocab-file $VOCAB_FILE \    --merge-file $MERGE_FILE \    --data-impl mmap \    --split 949,50,1 \    --distributed-backend nccl \    --weight-decay 1e-2 \    --clip-grad 1.0 \    --lr-warmup-fraction .01 \    --fp16 \    "
OUTPUT_ARGS=" \    --log-interval 10 \    --save-interval 500 \    --eval-interval 100 \    --eval-iters 10 \    --checkpoint-activations \    "
DATA_ARGS=" \    --save $CHECKPOINT_PATH \    --load $CHECKPOINT_PATH \    --data-path $DATA_PATH \    "
ALL_ARGS="$GPT_ARGS $OUTPUT_ARGS $DATA_ARGS  --deepspeed_config $CONFIG_JSON"
LAUNCHER="deepspeed --num_gpus $N_GPUS"
CMD="$LAUNCHER pretrain_gpt.py $ALL_ARGS"
echo $CMD
$CMD
```

```
root@gpuvm:/workspace/Megatron-DeepSpeed# cat  deepspeed_config.json{"fp16": {"enabled": true    },"zero_optimization": {"stage": 3,"allgather_partitions": true,"allgather_bucket_size": 2e8,"overlap_comm": true,"reduce_scatter": true,"reduce_bucket_size": 2e8,"contiguous_gradients": true,"cpu_offload": true    }}
```

上面的Shell脚本中，当使用`deepspeed`命令启动`pretrain_gpt.py`脚本时，DeepSpeed会在这个脚本中查找并使用所有与DeepSpeed相关的配置。但只有在zero设置为3的时候才启用。

root@gpuvm:/workspace/Megatron-DeepSpeed# vi pretrain_gpt.py

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmibziaceONiaI6h3lUM453G5jlHKwPSxbdy0oibx7ReBsqWRANj7U1358ZIQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPYTuf6ADw9569v96eMI3pvibj5fMkqTJqsFmlj8O6pclakGn0vnz6XsQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**6.验证训练后的效果**

**![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmib7qll7YGN4KHiagwics0mDwhwuZPsmY8rQpJIHRKZicWZhRu3TGIMofIcA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)**

1. 训练迭代次数：模型已经完成了5000次迭代的训练。
2. 学习率：学习率为1.500E-04，这是模型学习的速度。
3. 损失函数：模型的最后一次迭代的语言模型（lm）损失为5.879755E+00。损失函数是衡量模型预测与实际结果差距的指标，值越小表示模型的性能越好。
4. 梯度规范：最后一次迭代的梯度规范为0.987。梯度规范可以帮助我们理解模型的学习过程，如果梯度规范过大，可能会导致模型训练不稳定。
5. 验证损失：在5000次迭代后，验证集的语言模型损失为5.667873E+00。
6. 测试损失：在训练结束后，测试集的语言模型损失为5.806615E+00。
7. 性能指标：模型的性能可以通过每秒处理的样本数（samples per second）和每秒的浮点运算次数（TFLOPs）来衡量。在最后一次迭代中，每秒处理的样本数为6.159，每秒的浮点运算次数为4.94。
8. 没有出现梯度爆炸或消失的情况，因为没有跳过的迭代次数（number of skipped iterations）和NaN迭代次数（number of nan iterations）。

生成的模型checkpoint路径设置在/workspace/Megatron-DeepSpeed/checkpoints/gpt2。

ll ./checkpoints/gpt2

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmibXBcWF0B32sRctcp8K7e4BDHib3qjHZicdlvCXUtFblibzHicusVFnJbupg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

\#pip install mpi4py

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPLYRUxThqPzFhpQG7HWFIagVtY1JgtzoWd32O4f4dmCC0Xf6VVibVricw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

创建文本生成脚本。

```
#cat ./generate_text.sh#!/bin/bash
CHECKPOINT_PATH=checkpoints/gpt2VOCAB_FILE=data/gpt2-vocab.jsonMERGE_FILE=data/gpt2-merges.txt
python tools/generate_samples_gpt.py \       --tensor-model-parallel-size 1 \       --num-layers 24 \       --hidden-size 1024 \       --load $CHECKPOINT_PATH \       --num-attention-heads 16 \       --max-position-embeddings 1024 \       --tokenizer-type GPT2BPETokenizer \       --fp16 \       --micro-batch-size 2 \       --seq-length 1024 \       --out-seq-length 1024 \       --temperature 1.0 \       --vocab-file $VOCAB_FILE \       --merge-file $MERGE_FILE \       --genfile unconditional_samples.json \       --num-samples 2 \       --top_p 0.9 \       --recompute
sh ./generate_text.sh
```

如下所示，表示生成文本完成。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPl2JLDkiaGeLx1aicviccol4W2eZCCBhbcUvH6K7ISNeGuAshIGQ9H2gPg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

查看生成的JSON格式的文本文件。

vim unconditional_samples.json

回显信息类似如下所示。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPx3XdlRJ0dyZOdHQlibsW8TI6J23ntaqIgbdxcf03rUjBPQg3Cia7wSCQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



**附录：训练集介绍**

- oscar-1GB.jsonl.xz这个文件是一个包含了多语言文档的数据集，可以用于训练多语言的模型，例如BART。但是，这个文件只是原始的文本数据，还不能直接用于模型的训练。为了让模型能够理解和处理文本数据，我们需要对文本进行分词，即将文本切分成一个个的子词，然后用数字来表示这些子词。这样，模型就可以用数学的方式来学习和生成文本了。

  

- 第二个文件，gpt2-vocab.json，是一个JSON文件，包含了GPT-2模型的词汇表，即将子词映射到整数ID的字典。这个文件可以用于GPT-2的BPETokenizer，对文本进行分词。例如，单词“hello”在词汇表中的ID是31414，单词“world”在词汇表中的ID是995，那么文本“hello world”就可以用[31414, 995]这个数字序列来表示。

- 第三个文件，gpt2-merges.txt，是一个文本文件，包含了GPT-2模型的合并规则，即将两个子词合并为一个新词的规则。这个文件也可以用于GPT-2的BPETokenizer，对文本进行分词。例如，单词“low”可以被切分成“lo”和“w”，单词“er”可以被切分成“e”和“r”，那么文本“lower”就可以用[lo, w, e, r]这个子词序列来表示。但是，如果合并规则中有一条是“lo + w -> low”，那么文本“lower”就可以用[low, e, r]这个子词序列来表示，从而减少了一个子词。



没有这两个文件，我们就不能用GPT-2的BPETokenizer对文本进行分词，也就不能用GPT-2模型来训练或者生成文本了。所以，这两个文件是非常重要的，它们是GPT-2模型的基础。



BPE的分词方法是这样的：首先，它会将所有的单词切分成最小的单位，即字母。然后，它会统计所有的字母对出现的频率，找出最常见的字母对，将它们合并为一个新的子词，加入到词汇表中。接着，它会重复这个过程，直到达到预设的子词数量，或者没有更多的字母对可以合并为止。

例如，假设我们有一个很小的语料库，只包含了两个单词：lower和newer。那么，BPE的分词方法会按照以下的步骤进行：

- 第一步：将所有的单词切分成字母，得到[l, o, w, e, r]和[n, e, w, e, r]。
- 第二步：统计所有的字母对出现的频率，发现[e, r]是最常见的字母对，出现了两次。将[e, r]合并为一个新的子词er，加入到词汇表中。得到[l, o, w, er]和[n, e, w, er]。
- 第三步：再次统计所有的字母对出现的频率，发现[w, er]是最常见的字母对，出现了两次。将[w, er]合并为一个新的子词wer，加入到词汇表中。得到[l, o, wer]和[n, e, wer]。
- 第四步：继续统计所有的字母对出现的频率，发现[l, o]和[n, e]都是最常见的字母对，出现了一次。将[l, o]和[n, e]分别合并为两个新的子词lo和ne，加入到词汇表中。得到[lo, wer]和[ne, wer]。
- 第五步：没有更多的字母对可以合并了，停止分词过程。最终的词汇表是[a, b, c, …, z, er, wer, lo, ne]，最终的子词序列是[lo, wer]和[ne, wer]。

在这个例子中，我们可以看到，BPE的分词方法可以将单词lower和newer切分成两个子词，而不是五个字母。这样，模型就可以用更少的子词来表示更多的单词，从而提高模型的效率和泛化能力。

第三个文件，gpt2-merges.txt，就是记录了BPE的分词方法的合并规则的文件，即将两个子词合并为一个新词的规则。这个文件是按照合并的顺序排列的，每一行表示一条合并规则。例如，第一行是“e r -> er”，表示将子词e和r合并为一个新词er。第二行是“w er -> wer”，表示将子词w和er合并为一个新词wer。以此类推。



把oscar-1GB.jsonl中的内容转换成id的原因是，模型是用数学的方式来学习和生成文本的，它不能直接处理文字，而只能处理数字。所以，我们需要用一个词汇表来将文字和数字对应起来，这样模型就可以用数字来表示文字，从而进行计算和操作。例如，如果我们用一个简单的词汇表，将a映射到1，b映射到2，c映射到3，以此类推，那么文本“abc”就可以用[1, 2, 3]这个数字序列来表示，模型就可以对这个数字序列进行学习和生成。



GPT的pretrain是指用大量的无标签的文本数据来训练GPT模型，使其能够学习语言的规律和知识，从而具备自然语言理解和生成的能力。在这个阶段，GPT模型需要对文本进行编码，即将文本转换成数字，从而进行计算和操作。这个过程需要用到词汇表和合并规则，它们是GPT模型的分词工具，可以将文本切分成最优的子词，然后用数字来表示这些子词。所以，GPT的pretrain并不是不支持文字，而是需要对文字进行编码，才能让模型处理文字。

GPT的微调是指用少量的有标签的文本数据来调整GPT模型的参数，使其能够在特定的任务上表现更好，例如文本分类、文本摘要、文本生成等。在这个阶段，GPT模型仍然需要对文本进行编码，即将文本转换成数字，从而进行计算和操作。这个过程仍然需要用到词汇表和合并规则，它们是GPT模型的分词工具，可以将文本切分成最优的子词，然后用数字来表示这些子词。所以，GPT的微调也不是直接支持文字，而是需要对文字进行编码，才能让模型处理文字。

不过，GPT的微调有一个特点，就是它可以使用OpenAI的Fine-tuning API，它可以让您用自己的数据集来微调GPT模型，从而提高模型在特定任务上的性能。OpenAI的Fine-tuning API支持多种语言，包括英语、中文、法语、德语等。所以，您可以用英文语料来微调GPT模型，也可以用其他语言的语料来微调GPT模型，只要您的语料符合JSONL格式，每行一个样本。OpenAI的Fine-tuning API会自动地对您的语料进行编码，您不需要手动地进行编码，这可能是您觉得GPT的微调支持文字的原因。



在pretrain阶段，分词表是固定的，也就是说，模型使用的是预先定义好的词汇表和合并规则，来对文本进行分词和编码。这样做的好处是，可以保证模型的输入和输出都是一致的，也可以减少训练的复杂度和开销。如果使用不同的分词表，那么模型就需要重新学习新的词汇表和合并规则，这会增加训练的难度和时间，也可能影响模型的泛化能力。

https://github.com/bigscience-workshop/Megatron-DeepSpeed