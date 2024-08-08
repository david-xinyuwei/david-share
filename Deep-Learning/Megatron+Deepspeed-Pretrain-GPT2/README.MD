# Megatron+Deepspeed-Pretrain-GPT2
The pretraining of GPT-2 refers to training the GPT model using a large amount of unlabeled text data, enabling it to learn the patterns and knowledge of the language, thereby acquiring the ability to understand and generate natural language. In this stage, the GPT model needs to encode the text, which means converting the text into numbers for computation and operation. This process involves the use of a vocabulary and merging rules, which are the tokenization tools of the GPT model. These tools can segment the text into optimal subwords and then represent these subwords with numbers.


## Environment preparation

Azure GPU VM：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPnBMAREBNZib7BsfUryFiceYu5ibk8XAdiaghHhR3AmON7EEPxbPSib01xkA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Install docker：
```
#apt-get install nvidia-container-toolkit 

#systemctl restart docker

#docker run -d -t --network=host --gpus all --privileged --ipc=host --ulimit memlock=-1 --ulimit stack=67108864 --name megatron-deepspeed -v /etc/localtime:/etc/localtime -v /root/.ssh:/root/.ssh nvcr.io/nvidia/pytorch:21.10-py3

#docker exec -it megatron-deepspeed bash
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPrup3SrBpMs2u45AWWvJA5r9REqeGoLVe923SpYe7esRUfOvwXKPW5g/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Install Megatron-DeepSpeed Framework:
```
git clone https://github.com/bigscience-workshop/Megatron-DeepSpeed
cd Megatron-DeepSpeed
pip install -r requirements.txt
```

## Training data preparation
```
wget https://huggingface.co/bigscience/misc-test-data/resolve/main/stas/oscar-1GB.jsonl.xz
wget https://s3.amazonaws.com/models.huggingface.co/bert/gpt2-vocab.json
wget https://s3.amazonaws.com/models.huggingface.co/bert/gpt2-merges.txt
xz -d oscar-1GB.jsonl.xz
```
Execute the following command to preprocess the data:
```
python3 tools/preprocess_data.py \
    --input oscar-1GB.jsonl \
    --output-prefix meg-gpt2 \
    --vocab gpt2-vocab.json \
    --dataset-impl mmap \
    --tokenizer-type GPT2BPETokenizer \
    --merge-file gpt2-merges.txt \
    --append-eod \
    --workers 8
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPRRpvcJ8btbYyuTzL5CBr9xrC0iaJkdT1Fd8Fln6Nf3hbITjVvrCHMZA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Execute the following command to move the processed data to the data directory.
```
mkdir data
cp meg-gpt2* ./data
cp gpt2* ./data
```

### Create Pre-training scripts：

```
#vim pretrain_gpt2.sh
```
```
#! /bin/bash

# Runs the "345M" parameter model

GPUS_PER_NODE=1
# Change for multinode config
MASTER_ADDR=localhost
MASTER_PORT=6000
NNODES=1
NODE_RANK=0
WORLD_SIZE=$(($GPUS_PER_NODE*$NNODES))

DATA_PATH=data/meg-gpt2_text_document
CHECKPOINT_PATH=checkpoints/gpt2

DISTRIBUTED_ARGS="--nproc_per_node $GPUS_PER_NODE --nnodes $NNODES --node_rank $NODE_RANK --master_addr $MASTER_ADDR --master_port $MASTER_PORT"

python -m torch.distributed.launch $DISTRIBUTED_ARGS \
       pretrain_gpt.py \
       --tensor-model-parallel-size 1 \
       --pipeline-model-parallel-size 1 \
       --num-layers 24 \
       --hidden-size 1024 \
       --num-attention-heads 16 \
       --micro-batch-size 4 \
       --global-batch-size 8 \
       --seq-length 1024 \
       --max-position-embeddings 1024 \
       --train-iters 5000 \
       --lr-decay-iters 320000 \
       --save $CHECKPOINT_PATH \
       --load $CHECKPOINT_PATH \
       --data-path $DATA_PATH \
       --vocab-file data/gpt2-vocab.json \
       --merge-file data/gpt2-merges.txt \
       --data-impl mmap \
       --split 949,50,1 \
       --distributed-backend nccl \
       --lr 0.00015 \
       --lr-decay-style cosine \
       --min-lr 1.0e-5 \
       --weight-decay 1e-2 \
       --clip-grad 1.0 \
       --lr-warmup-fraction .01 \
       --checkpoint-activations \
       --log-interval 10 \
       --save-interval 500 \
       --eval-interval 100 \
       --eval-iters 10 \
       --fp16
```

There is an assertion in the Megatron source code that needs to be commented out to ensure the code runs correctly.
```
#vim /workspace/Megatron-DeepSpeed/megatron/model/fused_softmax.py +191
```
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPfUywm6qSw0xEjUfiazkYJFicXCWJ93z3nfk6NCYrrdyOCLIze6bbr6bg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## Run pre-training
```
#nohup sh ./pretrain_gpt2.sh & disown
#tail -f nohup.out
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPe3X4vme24ribVMlhD8ZMJPQ3pLUaa3ibe3SeicorlJgp02tVeWfYn78Mg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPOibkUp4Sf31ib8Iib2JomCPdfsWV2s9ia2PkHqMxxC1s0icJY8LbytAicjCw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

If you want to kill process:
```
ps -ef | awk '/pretrain_gpt/ {print $2}' | xargs kill -9
```


## Training Optimization - Enhancing Concurrency

Modify pre-train script:
```
root@gpuvm:/workspace/Megatron-DeepSpeed# vi ./pretrain_gpt2.sh

- GPUS_PER_NODE=4
- --tensor-model-parallel-size 4 
- --pipeline-model-parallel-size 1
```
We could see four GPU is working at the same time:
```
#nohup sh ./pretrain_gpt2.sh & disown
tail -f nohup.out
```
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPgA1TIGpxibdQnUkNwiciaicria3q9ibSsBJIkLAb8iaxIteGMfE8ibLtx7ezZg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## Use deepspeed ZeRO
In the section above, we accelerated the training speed by enhancing concurrency, but we did not enable DeepSpeed. This time, we will adjust the script.

```
root@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# rm -rf ./*
root@gpuvm:/workspace/Megatron-DeepSpeed/checkpoints/gpt2# cd ../..

```
```
#vim pretrain_gpt2.sh
```
```
!/bin/bash
# Adapted to use deepspeed on a single node
# Multi-node will require either a `hostfile` or switching to `torch.distributed.launch`

# adjust to the number of GPUs to use
N_GPUS=4

CHECKPOINT_PATH=checkpoints/gpt2
VOCAB_FILE=data/gpt2-vocab.json
MERGE_FILE=data/gpt2-merges.txt
DATA_PATH=data/meg-gpt2_text_document
CONFIG_JSON=deepspeed_config.json

GPT_ARGS=" \
    --num-layers 24 \
    --hidden-size 1024 \
    --num-attention-heads 16 \
    --seq-length 1024 \
    --max-position-embeddings 1024 \
    --tensor-model-parallel-size 4 \
    --pipeline-model-parallel-size 1 \
    --micro-batch-size 1 \
    --global-batch-size 4 \
    --lr-decay-iters 320000 \
    --lr 0.00015 \
    --min-lr 1.0e-5 \
    --lr-decay-style cosine \
    --train-iters 5000 \
    --vocab-file $VOCAB_FILE \
    --merge-file $MERGE_FILE \
    --data-impl mmap \
    --split 949,50,1 \
    --distributed-backend nccl \
    --weight-decay 1e-2 \
    --clip-grad 1.0 \
    --lr-warmup-fraction .01 \
    --fp16 \
    "

OUTPUT_ARGS=" \
    --log-interval 10 \
    --save-interval 500 \
    --eval-interval 100 \
    --eval-iters 10 \
    --checkpoint-activations \
    "

DATA_ARGS=" \
    --save $CHECKPOINT_PATH \
    --load $CHECKPOINT_PATH \
    --data-path $DATA_PATH \
    "

ALL_ARGS="$GPT_ARGS $OUTPUT_ARGS $DATA_ARGS  --deepspeed_config $CONFIG_JSON"

LAUNCHER="deepspeed --num_gpus $N_GPUS"

CMD="$LAUNCHER pretrain_gpt.py $ALL_ARGS"

echo $CMD

$CMD
```
```
root@gpuvm:/workspace/Megatron-DeepSpeed# cat  deepspeed_config.json
```
```
{
"fp16": {
"enabled": true
    },
"zero_optimization": {
"stage": 3,
"allgather_partitions": true,
"allgather_bucket_size": 2e8,
"overlap_comm": true,
"reduce_scatter": true,
"reduce_bucket_size": 2e8,
"contiguous_gradients": true,
"cpu_offload": true
    }
}
```

In the Shell script above, when the pretrain_gpt.py script is launched using the deepspeed command, DeepSpeed searches for and utilizes all DeepSpeed-related configurations within this script. However, it is only enabled when the zero setting is at 3.


We could check cotent of pretrain_gpt.py

```
root@gpuvm:/workspace/Megatron-DeepSpeed# vi pretrain_gpt.py
```
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmibziaceONiaI6h3lUM453G5jlHKwPSxbdy0oibx7ReBsqWRANj7U1358ZIQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

During training:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPYTuf6ADw9569v96eMI3pvibj5fMkqTJqsFmlj8O6pclakGn0vnz6XsQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



### Verify the effects after training

**![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmib7qll7YGN4KHiagwics0mDwhwuZPsmY8rQpJIHRKZicWZhRu3TGIMofIcA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)**

- Training Iterations: The model has completed 5000 training iterations.
- Learning Rate: The learning rate is 1.500E-04, which indicates the speed of the model's learning.
- Loss Function: The language model (lm) loss for the model's last iteration is 5.879755E+00. The loss function is a metric to measure the gap between the model's predictions and the actual results; the smaller the value, the better the model's performance.
- Gradient Norm: The gradient norm for the last iteration is 0.987. The gradient norm helps us understand the model's learning process; if the gradient norm is too high, it might lead to unstable model training.
- Validation Loss: After 5000 iterations, the language model loss on the validation set is 5.667873E+00.
- Test Loss: After training, the language model loss on the test set is 5.806615E+00.
- Performance Metrics: The model's performance can be measured by the number of samples processed per second and the number of floating-point operations per second (TFLOPs). In the last iteration, the number of samples processed per second is 6.159, and the number of floating-point operations per second is 4.94.
- There were no instances of gradient explosion or disappearance, as evidenced by the absence of skipped iterations (number of skipped iterations) and NaN iterations (number of nan iterations).
The generated model checkpoint path is set at /workspace/Megatron-DeepSpeed/checkpoints/gpt2.

```
# ll ./checkpoints/gpt2
```
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmibXBcWF0B32sRctcp8K7e4BDHib3qjHZicdlvCXUtFblibzHicusVFnJbupg/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## Appendix: Introduction to the Training Set
### 3 Files
- oscar-1GB.jsonl.xz File:
This is a dataset containing multilingual documents, suitable for training multilingual models (e.g., BART). However, this file only contains raw text data and cannot be directly used for model training. To enable the model to understand and process text data, we need to tokenize the text, splitting it into subwords and representing them with numbers. This way, the model can learn and generate text in a mathematical manner.
- gpt2-vocab.json File:
This is a JSON file containing the vocabulary for the GPT-2 model, mapping subwords to integer IDs. For example, the word "hello" has an ID of 31414, and "world" has an ID of 995, so "hello world" can be represented as [31414, 995]. This file is used by GPT-2's BPETokenizer to tokenize the text.
- gpt2-merges.txt File:
This is a text file that records the merge rules for the GPT-2 model, which define how two subwords are combined into a new word. For example, the word "lower" can be split into [lo, w, e, r], but if there is a merge rule "lo + w -> low", then "lower" can be represented as [low, e, r]. This file is also used by GPT-2's BPETokenizer to tokenize the text.

### BPE Tokenization Method
 
The steps of the BPE (Byte Pair Encoding) tokenization method are as follows:
- Initial Splitting: Split all words into their smallest units (letters). For example, "lower" and "newer" are split into [l, o, w, e, r] and [n, e, w, e, r], respectively.
- Frequency Counting: Count the frequency of all letter pairs, find the most common pair, and merge them into a new subword. For example, if [e, r] is the most common, merge it into "er", resulting in [l, o, w, er] and [n, e, w, er].
- Repeat Merging: Continue counting frequencies and merging letter pairs until the preset number of subwords is reached or no more pairs can be merged. For example, next merge [w, er] into "wer", resulting in [l, o, wer] and [n, e, wer].
- Final Vocabulary: The final vocabulary may include [a, b, c, …, z, er, wer, lo, ne], and the subword sequences are [lo, wer] and [ne, wer].

***Refer to:***
*https://github.com/bigscience-workshop/Megatron-DeepSpeed*
*https://help.aliyun.com/zh/ecs/use-cases/use-the-megatron-deepspeed-training-gpt-2-and-generate-text?spm=a2c4g.11186623.0.0.72a47e45epJ6T7*