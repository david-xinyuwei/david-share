# Nanotron 

Nanotron (https://github.com/huggingface/nanotron.git) is a library for pretraining transformer models. It provides a simple and flexible API to pretrain models on custom datasets. Nanotron is designed to be easy to use, fast, and scalable. It is built with the following principles in mind:

- **Simplicity**: Nanotron is designed to be easy to use. It provides a simple and flexible API to pretrain models on custom datasets.
- **Performance**: Optimized for speed and scalability, Nanotron uses the latest techniques to train models faster and more efficiently.

Nanotron currently supports a variety of parallel technologies:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2bGicZEUULKeia4se9nS6icqgkicnWJt22ySgZmibrI34SOcPdotgZVKLGuYw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

And it's roadmap are all very useful features too. Personally, I have a feeling FSDP will be integrated soon.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2b9ZTsjDMPnrNibZaoTg14AWsGj7uu2bXCnjjvZuQHJ5HXZ6dQHd8g4IQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## Pre-train tiny_llama

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
  dp: 1  # 数据并行大小
  expert_parallel_size: 1
  pp: 1  # 流水线并行大小
  pp_engine: 1f1b
  tp: 1  # 张量并行大小
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

Run inference:

```
torchrun --nproc_per_node=1 run_generate.py --ckpt-path checkpoints/10/ --tp 1 --pp 1
```

GPU resource consumed during training:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2bAiaGgQHoGONe2iaFWKCbOghN2AuPMDSUT44hPOCLVEUUDCyGRI67jdBg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

