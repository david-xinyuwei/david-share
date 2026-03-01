# Pretraining Frameworks: Megatron-DeepSpeed & Nanotron

This repo demonstrates two popular pretraining frameworks for transformer models — **Megatron-DeepSpeed** and **Nanotron** — with hands-on examples of GPT-2 and TinyLlama pretraining on Azure GPU VMs.

---


## Running on Azure

All experiments in this project were conducted on an **Azure GPU VM**.

| Item | Details |
|---|---|
| **Azure VM** | [NC40ads_H100_v5](https://learn.microsoft.com/en-us/azure/virtual-machines/nc-h100-v5-series) |
| **GPU** | NVIDIA H100 80GB |
| **Frameworks** | DeepSpeed |


## Part I: Megatron+DeepSpeed — Pretrain GPT-2

The pretraining of GPT-2 refers to training the GPT model using a large amount of unlabeled text data, enabling it to learn the patterns and knowledge of the language, thereby acquiring the ability to understand and generate natural language. In this stage, the GPT model needs to encode the text, which means converting the text into numbers for computation and operation. This process involves the use of a vocabulary and merging rules, which are the tokenization tools of the GPT model. These tools can segment the text into optimal subwords and then represent these subwords with numbers.


### Environment Preparation

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

### Training Data Preparation
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

### Create Pre-training Scripts

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



### Run Pre-training
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


### Training Optimization — Enhancing Concurrency

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



### Use DeepSpeed ZeRO
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


We could check content of pretrain_gpt.py

```
root@gpuvm:/workspace/Megatron-DeepSpeed# vi pretrain_gpt.py
```
![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVOlkSPwLRLKFcNJkbOhVmibziaceONiaI6h3lUM453G5jlHKwPSxbdy0oibx7ReBsqWRANj7U1358ZIQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

During training:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUM2a1u2AxeHbulk7gvlGOPYTuf6ADw9569v96eMI3pvibj5fMkqTJqsFmlj8O6pclakGn0vnz6XsQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



### Verify the Effects After Training

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



### Appendix: Introduction to the Training Set

#### 3 Files
- oscar-1GB.jsonl.xz File:
This is a dataset containing multilingual documents, suitable for training multilingual models (e.g., BART). However, this file only contains raw text data and cannot be directly used for model training. To enable the model to understand and process text data, we need to tokenize the text, splitting it into subwords and representing them with numbers. This way, the model can learn and generate text in a mathematical manner.
- gpt2-vocab.json File:
This is a JSON file containing the vocabulary for the GPT-2 model, mapping subwords to integer IDs. For example, the word "hello" has an ID of 31414, and "world" has an ID of 995, so "hello world" can be represented as [31414, 995]. This file is used by GPT-2's BPETokenizer to tokenize the text.
- gpt2-merges.txt File:
This is a text file that records the merge rules for the GPT-2 model, which define how two subwords are combined into a new word. For example, the word "lower" can be split into [lo, w, e, r], but if there is a merge rule "lo + w -> low", then "lower" can be represented as [low, e, r]. This file is also used by GPT-2's BPETokenizer to tokenize the text.

#### BPE Tokenization Method
 
The steps of the BPE (Byte Pair Encoding) tokenization method are as follows:
- Initial Splitting: Split all words into their smallest units (letters). For example, "lower" and "newer" are split into [l, o, w, e, r] and [n, e, w, e, r], respectively.
- Frequency Counting: Count the frequency of all letter pairs, find the most common pair, and merge them into a new subword. For example, if [e, r] is the most common, merge it into "er", resulting in [l, o, w, er] and [n, e, w, er].
- Repeat Merging: Continue counting frequencies and merging letter pairs until the preset number of subwords is reached or no more pairs can be merged. For example, next merge [w, er] into "wer", resulting in [l, o, wer] and [n, e, wer].
- Final Vocabulary: The final vocabulary may include [a, b, c, …, z, er, wer, lo, ne], and the subword sequences are [lo, wer] and [ne, wer].

***Refer to:***
- *https://github.com/bigscience-workshop/Megatron-DeepSpeed*
- *https://help.aliyun.com/zh/ecs/use-cases/use-the-megatron-deepspeed-training-gpt-2-and-generate-text?spm=a2c4g.11186623.0.0.72a47e45epJ6T7*

---

## Part II: Nanotron — Pretrain TinyLlama

Nanotron (https://github.com/huggingface/nanotron.git) is a library for pretraining transformer models. It provides a simple and flexible API to pretrain models on custom datasets. Nanotron is designed to be easy to use, fast, and scalable. It is built with the following principles in mind:

- **Simplicity**: Nanotron is designed to be easy to use. It provides a simple and flexible API to pretrain models on custom datasets.
- **Performance**: Optimized for speed and scalability, Nanotron uses the latest techniques to train models faster and more efficiently.

Nanotron currently supports a variety of parallel technologies:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2bGicZEUULKeia4se9nS6icqgkicnWJt22ySgZmibrI34SOcPdotgZVKLGuYw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

And it's roadmap are all very useful features too. Personally, I have a feeling FSDP will be integrated soon.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2b9ZTsjDMPnrNibZaoTg14AWsGj7uu2bXCnjjvZuQHJ5HXZ6dQHd8g4IQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



### Installation

Installation is relatively simple, refer to the repo installation steps.

```
# Requirements: Python>=3.10
git clone https://github.com/huggingface/nanotron
cd nanotron
pip install --upgrade pip
pip install --pre torch --index-url https://download.pytorch.org/whl/nightly/cu121
pip install -e .

# Install dependencies if you want to use the example scripts
pip install datasets transformers
pip install triton "flash-attn>=2.5.0" --no-build-isolation
```

### Pre-train TinyLlama

My experimental environment is a single card H100, all slightly modified example script and then pre-trained tiny_llama.

```
#cat config_tiny_llama-david.yaml
```

```
checkpoints:
  checkpoint_interval: 10
  checkpoints_path: checkpoints
  checkpoints_path_is_shared_file_system: false
  resume_checkpoint_path: null
  save_initial_state: false

data_stages:
- data:
    dataset:
      dataset_overwrite_cache: false
      dataset_processing_num_proc_per_process: 1
      hf_dataset_config_name: null
      hf_dataset_or_datasets: stas/openwebtext-10k
      hf_dataset_splits: train
      text_column_name: text
    num_loading_workers: 1
    seed: 42
  name: Stable Training Stage
  start_training_step: 1
- data:
    dataset:
      dataset_overwrite_cache: false
      dataset_processing_num_proc_per_process: 1
      hf_dataset_config_name: null
      hf_dataset_or_datasets: stas/openwebtext-10k
      hf_dataset_splits: train
      text_column_name: text
    num_loading_workers: 1
    seed: 42
  name: Annealing Phase
  start_training_step: 10

general:
  benchmark_csv_path: null
  consumed_train_samples: null
  ignore_sanity_checks: true
  project: debug
  run: tiny_llama_%date_%jobid
  seed: 42
  step: null

lighteval: null

logging:
  iteration_step_info_interval: 1
  log_level: info
  log_level_replica: info

model:
  ddp_bucket_cap_mb: 25
  dtype: bfloat16
  init_method:
    std: 0.025
  make_vocab_size_divisible_by: 1
  model_config:
    bos_token_id: 1
    eos_token_id: 2
    hidden_act: silu
    hidden_size: 16
    initializer_range: 0.02
    intermediate_size: 64
    is_llama_config: true
    max_position_embeddings: 256
    num_attention_heads: 4
    num_hidden_layers: 2
    num_key_value_heads: 4
    pad_token_id: null
    pretraining_tp: 1
    rms_norm_eps: 1.0e-05
    rope_scaling: null
    tie_word_embeddings: true
    use_cache: true
    vocab_size: 256

optimizer:
  accumulate_grad_in_fp32: true
  clip_grad: 1.0
  learning_rate_scheduler:
    learning_rate: 0.0003
    lr_decay_starting_step: null
    lr_decay_steps: 13
    lr_decay_style: cosine
    lr_warmup_steps: 2
    lr_warmup_style: linear
    min_decay_lr: 1.0e-05
  optimizer_factory:
    adam_beta1: 0.9
    adam_beta2: 0.95
    adam_eps: 1.0e-08
    name: adamW
    torch_adam_is_fused: true
  weight_decay: 0.01
  zero_stage: 0

parallelism:
  dp: 1  # Data parallel size
  expert_parallel_size: 1
  pp: 1  # Pipeline parallel size
  pp_engine: 1f1b
  tp: 1  # Tensor parallel size
  tp_linear_async_communication: true
  tp_mode: REDUCE_SCATTER

profiler: null

tokenizer:
  tokenizer_max_length: null
  tokenizer_name_or_path: robot-test/dummy-tokenizer-wordlevel
  tokenizer_revision: null

tokens:
  batch_accumulation_per_replica: 1
  limit_test_batches: 0
  limit_val_batches: 0
  micro_batch_size: 2
  sequence_length: 256
  train_steps: 15
  val_check_interval: -1
```

Execute training:

```
#CUDA_DEVICE_MAX_CONNECTIONS=1 torchrun --nproc_per_node=1 run_train.py --config-file examples/config_tiny_llama-david.yaml
```

Training process:

```
[rank0]:[W831 14:37:22.051704988 ProcessGroupNCCL.cpp:4049] [PG ID 0 PG GUID 0 Rank 0]  using GPU 0 to perform barrier as devices used by this process are currently unknown. This can potentially cause a hang if this rank to GPU mapping is incorrect.Specify device_ids in barrier() to force use of a particular device,or call init_process_group() with a device_id.
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Config:
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Config(general=GeneralArgs(project='debug',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            run='tiny_llama_%date_%jobid',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            seed=42,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            step=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            consumed_train_samples=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            benchmark_csv_path=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            ignore_sanity_checks=True),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        parallelism=ParallelismArgs(dp=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    pp=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    tp=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    pp_engine=<nanotron.parallel.pipeline_parallel.engine.OneForwardOneBackwardPipelineEngine object at 0x7fcc5c65c910>,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    tp_mode=<TensorParallelLinearMode.REDUCE_SCATTER: 2>,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    tp_linear_async_communication=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    recompute_layer=False,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    tp_recompute_allgather=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    expert_parallel_size=1),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        model=ModelArgs(model_config=LlamaConfig(bos_token_id=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 eos_token_id=2,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 hidden_act='silu',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 hidden_size=16,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 initializer_range=0.02,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 intermediate_size=64,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 is_llama_config=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 max_position_embeddings=256,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 num_attention_heads=4,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 num_hidden_layers=2,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 num_key_value_heads=4,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 pad_token_id=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 pretraining_tp=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 rms_norm_eps=1e-05,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 rope_scaling=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 rope_theta=10000.0,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 tie_word_embeddings=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 use_cache=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                 vocab_size=256),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                        init_method=RandomInit(std=0.025),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                        dtype=torch.bfloat16,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                        make_vocab_size_divisible_by=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                        ddp_bucket_cap_mb=25),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        tokenizer=TokenizerArgs(tokenizer_name_or_path='robot-test/dummy-tokenizer-wordlevel',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                tokenizer_revision=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                tokenizer_max_length=None),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        checkpoints=CheckpointsArgs(checkpoints_path=PosixPath('checkpoints'),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    checkpoint_interval=10,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    save_initial_state=False,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    save_final_state=False,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    resume_checkpoint_path=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                    checkpoints_path_is_shared_file_system=False),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        logging=LoggingArgs(log_level='info',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            log_level_replica='info',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                            iteration_step_info_interval=1),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        tokens=TokensArgs(sequence_length=256,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                          train_steps=15,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                          micro_batch_size=2,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                          batch_accumulation_per_replica=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                          val_check_interval=-1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                          limit_val_batches=0,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                          limit_test_batches=0),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        optimizer=OptimizerArgs(optimizer_factory=AdamWOptimizerArgs(adam_eps=1e-08,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                     adam_beta1=0.9,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                     adam_beta2=0.95,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                     torch_adam_is_fused=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                     name='adamW'),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                zero_stage=0,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                weight_decay=0.01,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                clip_grad=1.0,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                accumulate_grad_in_fp32=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                learning_rate_scheduler=LRSchedulerArgs(learning_rate=0.0003,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                        lr_warmup_steps=2,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                        lr_warmup_style='linear',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                        lr_decay_style='cosine',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                        lr_decay_steps=13,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                        lr_decay_starting_step=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                        min_decay_lr=1e-05)),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        data_stages=[DatasetStageArgs(name='Stable Training Stage',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                      start_training_step=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                      data=DataArgs(dataset=PretrainDatasetsArgs(hf_dataset_or_datasets='stas/openwebtext-10k',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 hf_dataset_splits='train',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 hf_dataset_config_name=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 dataset_processing_num_proc_per_process=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 dataset_overwrite_cache=False,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 text_column_name='text'),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                    seed=42,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                    num_loading_workers=1)),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                     DatasetStageArgs(name='Annealing Phase',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                      start_training_step=10,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                      data=DataArgs(dataset=PretrainDatasetsArgs(hf_dataset_or_datasets='stas/openwebtext-10k',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 hf_dataset_splits='train',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 hf_dataset_config_name=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 dataset_processing_num_proc_per_process=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 dataset_overwrite_cache=False,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                                                 text_column_name='text'),
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                    seed=42,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:                                                    num_loading_workers=1))],
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        profiler=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:        lighteval=None)
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Model Config:
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: LlamaConfig(bos_token_id=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             eos_token_id=2,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             hidden_act='silu',
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             hidden_size=16,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             initializer_range=0.02,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             intermediate_size=64,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             is_llama_config=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             max_position_embeddings=256,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             num_attention_heads=4,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             num_hidden_layers=2,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             num_key_value_heads=4,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             pad_token_id=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             pretraining_tp=1,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             rms_norm_eps=1e-05,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             rope_scaling=None,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             rope_theta=10000.0,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             tie_word_embeddings=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             use_cache=True,
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]:             vocab_size=256)
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Building model..
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Setting PP block ranks...
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Total number of parameters: 12.4K (0.02MiB)
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Local number of parameters: 12.4K (0.02MiB)
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: [After model building] Memory usage: 0.04MiB. Peak allocated: 0.06MiB Peak reserved: 2.00MiB
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: No checkpoint path provided.
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: Parametrizing model parameters using StandardParametrizator
08/31/2024 14:37:22 [INFO|DP=0|PP=0|TP=0]: [Optimizer Building] Using LearningRateForSP as learning rate
08/31/2024 14:37:23 [INFO|DP=0|PP=0|TP=0]: [Training Plan] Stage Stable Training Stage has 9 remaining training steps and has consumed 0 samples
08/31/2024 14:37:23 [INFO|DP=0|PP=0|TP=0]: Using `datasets` library
08/31/2024 14:37:23 [INFO|DP=0|PP=0|TP=0]: Loading tokenizer from robot-test/dummy-tokenizer-wordlevel and transformers/hf_hub versions ('4.44.2', '0.24.6')
Downloading data: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████| 30.3M/30.3M [00:00<00:00, 39.7MB/s]
Generating train split: 100%|███████████████████████████████████████████████████████████████████████████████████████████| 10000/10000 [00:00<00:00, 72202.68 examples/s]
tokenizer_config.json: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████| 251/251 [00:00<00:00, 3.25MB/s]
tokenizer.json: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1.80k/1.80k [00:00<00:00, 25.5MB/s]
special_tokens_map.json: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████| 156/156 [00:00<00:00, 2.11MB/s]
/opt/miniconda/envs/nanotron/lib/python3.10/site-packages/transformers/tokenization_utils_base.py:1601: FutureWarning: `clean_up_tokenization_spaces` was not set. It will be set to `True` by default. This behavior will be depracted in transformers v4.45, and will be then set to `False` by default. For more details check this issue: https://github.com/huggingface/transformers/issues/31884
  warnings.warn(
Grouping texts in chunks of 257:   0%|                                                                                                 | 0/10000 [00:00<?, ? examples/s]Token indices sequence length is longer than the specified maximum sequence length for this model (972 > 10). Running this sequence through the model will result in indexing errors
Grouping texts in chunks of 257: 100%|███████████████████████████████████████████████████████████████████████████████████| 10000/10000 [00:01<00:00, 5374.47 examples/s]
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]: [Training Plan] Stage Annealing Phase has 5 remaining training steps and has consumed 0 samples
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]: [Training Plan] There are 2 training stages
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]: [Stage Stable Training Stage] start from step 1
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]: [Stage Annealing Phase] start from step 10
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]:
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]: [Start training] datetime: 2024-08-31 14:37:26.889276 | mbs: 2 | grad_accum: 1 | global_batch_size: 2 | sequence_length: 256 | train_steps: 15 | start_iteration_step: 0 | consumed_train_samples: 0
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]: Resuming training from stage Stable Training Stage, it has trained for 0 samples and has 9 remaining train steps
08/31/2024 14:37:26 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 0.14MiB. Peak allocated 0.14MiB. Peak reserved: 2.00MiB
huggingface/tokenizers: The current process just got forked, after parallelism has already been used. Disabling parallelism to avoid deadlocks...
To disable this warning, you can either:
        - Avoid using `tokenizers` before the fork if possible
        - Explicitly set the environment variable TOKENIZERS_PARALLELISM=(true | false)
/opt/miniconda/envs/nanotron/lib/python3.10/site-packages/flash_attn/ops/triton/layer_norm.py:959: FutureWarning: `torch.cuda.amp.custom_fwd(args...)` is deprecated. Please use `torch.amp.custom_fwd(args..., device_type='cuda')` instead.
  def forward(
/opt/miniconda/envs/nanotron/lib/python3.10/site-packages/flash_attn/ops/triton/layer_norm.py:1018: FutureWarning: `torch.cuda.amp.custom_bwd(args...)` is deprecated. Please use `torch.amp.custom_bwd(args..., device_type='cuda')` instead.
  def backward(ctx, dout, *args):
/opt/miniconda/envs/nanotron/lib/python3.10/site-packages/torch/autograd/graph.py:818: UserWarning: c10d::allreduce_: an autograd kernel was not registered to the Autograd key(s) but we are trying to backprop through it. This may lead to silently incorrect behavior. This behavior is deprecated and will be removed in a future version of PyTorch. If your operator is differentiable, please ensure you have registered an autograd kernel to the correct Autograd key (e.g. DispatchKey::Autograd, DispatchKey::CompositeImplicitAutograd). If your operator is not differentiable, or to squash this warning and use the previous behavior, please register torch::CppFunction::makeFallthrough() to DispatchKey::Autograd. (Triggered internally at ../torch/csrc/autograd/autograd_not_implemented_fallback.cpp:62.)
  return Variable._execution_engine.run_backward(  # Calls into the C++ engine to run the backward pass
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.15MiB. Peak allocated 309.29MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 1 / 15 | consumed_tokens: 512 | elapsed_time_per_iteration_ms: 4.71K | tokens_per_sec: 109 | tokens_per_sec_per_gpu: 109 | global_batch_size: 2 | lm_loss: 5.32 | lr: 0.00015 | model_tflops_per_gpu: 1.87e-05 | hardware_tflops_per_gpu: 1.87e-05 | grad_norm: 2.96 | cuda_memory_allocated: 67.4M | cuda_max_memory_reserved: 520M | hd_total_memory_tb: 2.13T | hd_used_memory_tb: 952G | hd_free_memory_tb: 1.18T
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.26MiB. Peak allocated 64.26MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.26MiB. Peak allocated 66.25MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 2 / 15 | consumed_tokens: 1.02K | elapsed_time_per_iteration_ms: 11.8 | tokens_per_sec: 43.2K | tokens_per_sec_per_gpu: 43.2K | global_batch_size: 2 | lm_loss: 5.29 | lr: 0.0003 | model_tflops_per_gpu: 0.00744 | hardware_tflops_per_gpu: 0.00744 | grad_norm: 3.29 | cuda_memory_allocated: 67.4M | cuda_max_memory_reserved: 520M | hd_total_memory_tb: 2.13T | hd_used_memory_tb: 952G | hd_free_memory_tb: 1.18T
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.26MiB. Peak allocated 64.27MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.26MiB. Peak allocated 66.25MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 3 / 15 | consumed_tokens: 1.54K | elapsed_time_per_iteration_ms: 10 | tokens_per_sec: 51.2K | tokens_per_sec_per_gpu: 51.2K | global_batch_size: 2 | lm_loss: 5.28 | lr: 0.000296 | model_tflops_per_gpu: 0.00881 | hardware_tflops_per_gpu: 0.00881 | grad_norm: 3.31 | cuda_memory_allocated: 67.4M | cuda_max_memory_reserved: 520M | hd_total_memory_tb: 2.13T | hd_used_memory_tb: 952G | hd_free_memory_tb: 1.18T
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.26MiB. Peak allocated 64.27MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]:  Memory usage: 64.26MiB. Peak allocated 66.25MiB. Peak reserved: 496.00MiB
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 4 / 15 | consumed_tokens: 2.05K | elapsed_time_per_iteration_ms: 10.2 | tokens_per_sec: 50.2K | tokens_per_sec_per_gpu: 50.2K | global_batch_size: 2 | lm_loss: 5.28 | lr: 0.000283 | model_tflops_per_gpu: 0.00863 | hardware_tflops_per_gpu: 0.00863 | grad_norm: 3.19 | cuda_memory_allocated: 67.4M | cuda_max_memory_reserved: 520M | hd_total_memory_tb: 2.13T | hd_used_memory_tb: 952G | hd_free_memory_tb: 1.18T
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 5 / 15 | consumed_tokens: 2.56K | elapsed_time_per_iteration_ms: 9.15 | tokens_per_sec: 55.9K | tokens_per_sec_per_gpu: 55.9K | global_batch_size: 2 | lm_loss: 5.27 | lr: 0.000264 | model_tflops_per_gpu: 0.00962 | hardware_tflops_per_gpu: 0.00962 | grad_norm: 3.2
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 6 / 15 | consumed_tokens: 3.07K | elapsed_time_per_iteration_ms: 9.09 | tokens_per_sec: 56.3K | tokens_per_sec_per_gpu: 56.3K | global_batch_size: 2 | lm_loss: 5.25 | lr: 0.000237 | model_tflops_per_gpu: 0.00969 | hardware_tflops_per_gpu: 0.00969 | grad_norm: 3.18
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 7 / 15 | consumed_tokens: 3.58K | elapsed_time_per_iteration_ms: 8.93 | tokens_per_sec: 57.3K | tokens_per_sec_per_gpu: 57.3K | global_batch_size: 2 | lm_loss: 5.26 | lr: 0.000206 | model_tflops_per_gpu: 0.00986 | hardware_tflops_per_gpu: 0.00986 | grad_norm: 3.09
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 8 / 15 | consumed_tokens: 4.1K | elapsed_time_per_iteration_ms: 8.95 | tokens_per_sec: 57.2K | tokens_per_sec_per_gpu: 57.2K | global_batch_size: 2 | lm_loss: 5.25 | lr: 0.000172 | model_tflops_per_gpu: 0.00984 | hardware_tflops_per_gpu: 0.00984 | grad_norm: 3.14
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: iteration: 9 / 15 | consumed_tokens: 4.61K | elapsed_time_per_iteration_ms: 8.73 | tokens_per_sec: 58.7K | tokens_per_sec_per_gpu: 58.7K | global_batch_size: 2 | lm_loss: 5.26 | lr: 0.000138 | model_tflops_per_gpu: 0.0101 | hardware_tflops_per_gpu: 0.0101 | grad_norm: 2.95
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: [Training Stage: Annealing Phase] Clearing the previous training stage's dataloader and datasets from memory
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: Using `datasets` library
08/31/2024 14:37:31 [INFO|DP=0|PP=0|TP=0]: Loading tokenizer from robot-test/dummy-tokenizer-wordlevel and transformers/hf_hub versions ('4.44.2', '0.24.6')
/opt/miniconda/envs/nanotron/lib/python3.10/site-packages/transformers/tokenization_utils_base.py:1601: FutureWarning: `clean_up_tokenization_spaces` was not set. It will be set to `True` by default. This behavior will be depracted in transformers v4.45, and will be then set to `False` by default. For more details check this issue: https://github.com/huggingface/transformers/issues/31884
  warnings.warn(
huggingface/tokenizers: The current process just got forked, after parallelism has already been used. Disabling parallelism to avoid deadlocks...
To disable this warning, you can either:
        - Avoid using `tokenizers` before the fork if possible
        - Explicitly set the environment variable TOKENIZERS_PARALLELISM=(true | false)
08/31/2024 14:37:32 [INFO|DP=0|PP=0|TP=0]: iteration: 10 / 15 | consumed_tokens: 5.12K | elapsed_time_per_iteration_ms: 673 | tokens_per_sec: 761 | tokens_per_sec_per_gpu: 761 | global_batch_size: 2 | lm_loss: 5.26 | lr: 0.000104 | model_tflops_per_gpu: 0.000131 | hardware_tflops_per_gpu: 0.000131 | grad_norm: 2.93
08/31/2024 14:37:32 [WARNING|DP=0|PP=0|TP=0]: Saving checkpoint at checkpoints/10
Saving weights: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 15/15 [00:00<00:00, 2484.58it/s]
08/31/2024 14:37:32 [INFO|DP=0|PP=0|TP=0]: iteration: 11 / 15 | consumed_tokens: 5.63K | elapsed_time_per_iteration_ms: 11.1 | tokens_per_sec: 46.3K | tokens_per_sec_per_gpu: 46.3K | global_batch_size: 2 | lm_loss: 5.22 | lr: 7.26e-05 | model_tflops_per_gpu: 0.00796 | hardware_tflops_per_gpu: 0.00796 | grad_norm: 3.21 | cuda_memory_allocated: 67.4M | cuda_max_memory_reserved: 520M | hd_total_memory_tb: 2.13T | hd_used_memory_tb: 952G | hd_free_memory_tb: 1.18T
08/31/2024 14:37:32 [INFO|DP=0|PP=0|TP=0]: iteration: 12 / 15 | consumed_tokens: 6.14K | elapsed_time_per_iteration_ms: 9.3 | tokens_per_sec: 55K | tokens_per_sec_per_gpu: 55K | global_batch_size: 2 | lm_loss: 5.22 | lr: 4.65e-05 | model_tflops_per_gpu: 0.00947 | hardware_tflops_per_gpu: 0.00947 | grad_norm: 3.24
08/31/2024 14:37:32 [INFO|DP=0|PP=0|TP=0]: iteration: 13 / 15 | consumed_tokens: 6.66K | elapsed_time_per_iteration_ms: 9.04 | tokens_per_sec: 56.6K | tokens_per_sec_per_gpu: 56.6K | global_batch_size: 2 | lm_loss: 5.22 | lr: 2.66e-05 | model_tflops_per_gpu: 0.00974 | hardware_tflops_per_gpu: 0.00974 | grad_norm: 3.19
08/31/2024 14:37:32 [INFO|DP=0|PP=0|TP=0]: iteration: 14 / 15 | consumed_tokens: 7.17K | elapsed_time_per_iteration_ms: 9.02 | tokens_per_sec: 56.8K | tokens_per_sec_per_gpu: 56.8K | global_batch_size: 2 | lm_loss: 5.22 | lr: 1.42e-05 | model_tflops_per_gpu: 0.00977 | hardware_tflops_per_gpu: 0.00977 | grad_norm: 3.21
08/31/2024 14:37:32 [INFO|DP=0|PP=0|TP=0]: iteration: 15 / 15 | consumed_tokens: 7.68K | elapsed_time_per_iteration_ms: 9.41 | tokens_per_sec: 54.4K | tokens_per_sec_per_gpu: 54.4K | global_batch_size: 2 | lm_loss: 5.22 | lr: 1e-05 | model_tflops_per_gpu: 0.00936 | hardware_tflops_per_gpu: 0.00936 | grad_norm: 3.19
```

### Run Inference

```
torchrun --nproc_per_node=1 run_generate.py --ckpt-path checkpoints/10/ --tp 1 --pp 1
```

GPU resource consumed during training:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2bAiaGgQHoGONe2iaFWKCbOghN2AuPMDSUT44hPOCLVEUUDCyGRI67jdBg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

---

***References:***
- *https://github.com/bigscience-workshop/Megatron-DeepSpeed*
- *https://help.aliyun.com/zh/ecs/use-cases/use-the-megatron-deepspeed-training-gpt-2-and-generate-text?spm=a2c4g.11186623.0.0.72a47e45epJ6T7*
- *https://github.com/huggingface/nanotron*
