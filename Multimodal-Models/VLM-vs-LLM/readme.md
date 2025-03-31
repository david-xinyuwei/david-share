# VLM and LLM 文本生成能力对比

本Repo阐述VLM与SLM的区别，并以Phi3.5v和Florance2举例，如何微调SLM的指定模块。

## 文本生成能力对比

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/VLM-vs-LLM/images/2.png)

1. – 对 7B 小模型来说，引入多模态后语言任务表现下降明显；
   – 对 72B 大模型来说，VLM 版本的语言任务表现优于纯语言模型，且量化 (AWQ) 后也仍然保持优势。
2. 推理成本与内存占用比较
   • VLM 模型的参数量会多出一部分（因为新增了视觉编码器和相关输入处理），但其实比同规模 LLM 只多占不到 1.5 GB 左右的显存；推理速度也没有明显差异。
   • 对于有足够 GPU 资源的人来说，使用 VLM 替代 LLM 在纯文本任务上也许更好，因为它语言能力不减反增；而如果硬件资源有限或只使用小模型 (例如 7B)，则 VLM 可能拖慢语言任务的成绩。



**原因分析：**

之所以在 72B 这种较大规模模型上，VLM（多模态版本）反而能在语言任务上超越纯语言模型，根本原因主要有以下几点：

1. 额外的训练与数据增益
   大多数多模态后训练（post-training）并非只接入视觉 encoder 那么简单，往往还会在引入图像数据的同时继续加入新文本数据，并对模型进行进一步的语言训练。对于大模型而言，这就相当于模型经历了“二次强化”——不仅接受了新的多模态数据，也接受了更多文本数据。在足够大的参数空间里，这些额外的训练步骤往往能带来语言能力的进一步提升。

2. 大模型容量更容易吸收多模态训练
   对于 7B 这样相对小的模型，加入视觉编码和多模态能力后，很可能会产生“挤占”或“遗忘”现象：模型有限的参数容量需要在原有语言能力和新增视觉能力之间分配，导致语言能力有所退化。在 72B 这样的大模型中，模型参数量更充裕，学习能力更强，能够更好地同时吸收视觉和语言信息，最终反映在对语言任务的表现上不但没有下降，反而提升了。

3. 多模态训练策略对语言也有正面影响
   如果多模态训练策略是“继续训练 LLM 自身的参数”，而不是“冻结原有 LLM + 只训练视觉适配器”，那么原本的语言部分也会随新数据一起被进一步调整、优化。在大模型中，这种同步更新往往会巩固并拓展语言能力，让模型在理解上下文、生成文本等方面得到强化。

4. 更丰富的上下文与表征能力
   大模型在处理多模态信息的时候，如果视觉与语言模块之间有较好的融合机制，模型可能会对语言信息建立更广泛、更深层次的关联。例如，处理图片描述和 OCR 场景时，模型会进一步强化语义理解和世界知识，这些在语言任务中也能起到正向的迁移作用。

   综合来看，72B 级别的大模型拥有更充足的“容量”去应对多模态后训练带来的新知识和新任务，不仅不会牺牲原有的语言能力，反而会因额外的再训练过程而进一步提升语言表现。相较之下，小模型在多模态后训练中更容易出现“舍此取彼”的现象，导致语言任务表现退化。

## Phi-3.5v的架构

以Phi为例。

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/VLM-vs-LLM/images/1.png)

查看模型层级

```
======== Model Config ========
{'_attn_implementation_autoset': False,
 '_attn_implementation_internal': 'flash_attention_2',
 '_commit_hash': '4a0d683eba9f1d0cbfb6151705d1ee73c25a80ca',
 '_name_or_path': 'microsoft/Phi-3.5-vision-instruct',
 'add_cross_attention': False,
 'architectures': ['Phi3VForCausalLM'],
 'attention_dropout': 0.0,
 'auto_map': {'AutoConfig': 'microsoft/Phi-3.5-vision-instruct--configuration_phi3_v.Phi3VConfig',
              'AutoModelForCausalLM': 'microsoft/Phi-3.5-vision-instruct--modeling_phi3_v.Phi3VForCausalLM'},
 'bad_words_ids': None,
 'begin_suppress_tokens': None,
 'bos_token_id': 1,
 'chunk_size_feed_forward': 0,
 'cross_attention_hidden_size': None,
 'decoder_start_token_id': None,
 'diversity_penalty': 0.0,
 'do_sample': False,
 'early_stopping': False,
 'embd_layer': {'embedding_cls': 'image',
                'hd_transform_order': 'sub_glb',
                'projection_cls': 'mlp',
                'use_hd_transform': True,
                'with_learnable_separator': True},
 'embd_pdrop': 0.0,
 'encoder_no_repeat_ngram_size': 0,
 'eos_token_id': 2,
 'exponential_decay_length_penalty': None,
 'finetuning_task': None,
 'forced_bos_token_id': None,
 'forced_eos_token_id': None,
 'hidden_act': 'silu',
 'hidden_size': 3072,
 'id2label': {0: 'LABEL_0', 1: 'LABEL_1'},
 'img_processor': {'image_dim_out': 1024,
                   'model_name': 'openai/clip-vit-large-patch14-336',
                   'name': 'clip_vision_model',
                   'num_img_tokens': 144},
 'initializer_range': 0.02,
 'intermediate_size': 8192,
 'is_decoder': False,
 'is_encoder_decoder': False,
 'label2id': {'LABEL_0': 0, 'LABEL_1': 1},
 'length_penalty': 1.0,
 'max_length': 20,
 'max_position_embeddings': 131072,
 'min_length': 0,
 'model_type': 'phi3_v',
 'no_repeat_ngram_size': 0,
 'num_attention_heads': 32,
 'num_beam_groups': 1,
 'num_beams': 1,
 'num_hidden_layers': 32,
 'num_key_value_heads': 32,
 'num_return_sequences': 1,
 'original_max_position_embeddings': 4096,
 'output_attentions': False,
 'output_hidden_states': False,
 'output_scores': False,
 'pad_token_id': 32000,
 'prefix': None,
 'problem_type': None,
 'pruned_heads': {},
 'remove_invalid_values': False,
 'repetition_penalty': 1.0,
 'resid_pdrop': 0.0,
 'return_dict': True,
 'return_dict_in_generate': False,
 'rms_norm_eps': 1e-05,
 'rope_theta': 10000.0,
 'sep_token_id': None,
 'sliding_window': 262144,
 'suppress_tokens': None,
 'task_specific_params': None,
 'temperature': 1.0,
 'tf_legacy_loss': False,
 'tie_encoder_decoder': False,
 'tie_word_embeddings': False,
 'tokenizer_class': None,
 'top_k': 50,
 'top_p': 1.0,
 'torch_dtype': torch.bfloat16,
 'torchscript': False,
 'transformers_version': '4.38.1',
 'typical_p': 1.0,
 'use_bfloat16': False,
 'use_cache': True,
 'vocab_size': 32064}

======== Full Model Structure ========
Phi3VForCausalLM(
  (model): Phi3VModel(
    (embed_tokens): Embedding(32064, 3072, padding_idx=32000)
    (embed_dropout): Dropout(p=0.0, inplace=False)
    (vision_embed_tokens): Phi3ImageEmbedding(
      (drop): Dropout(p=0.0, inplace=False)
      (wte): Embedding(32064, 3072, padding_idx=32000)
      (img_processor): CLIPVisionModel(
        (vision_model): CLIPVisionTransformer(
          (embeddings): CLIPVisionEmbeddings(
            (patch_embedding): Conv2d(3, 1024, kernel_size=(14, 14), stride=(14, 14), bias=False)
            (position_embedding): Embedding(577, 1024)
          )
          (pre_layrnorm): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
          (encoder): CLIPEncoder(
            (layers): ModuleList(
              (0-23): 24 x CLIPEncoderLayer(
                (layer_norm1): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
                (mlp): CLIPMLP(
                  (activation_fn): QuickGELUActivation()
                  (fc1): Linear(in_features=1024, out_features=4096, bias=True)
                  (fc2): Linear(in_features=4096, out_features=1024, bias=True)
                )
                (layer_norm2): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
                (self_attn): CLIPAttentionFA2(
                  (k_proj): Linear(in_features=1024, out_features=1024, bias=True)
                  (v_proj): Linear(in_features=1024, out_features=1024, bias=True)
                  (q_proj): Linear(in_features=1024, out_features=1024, bias=True)
                  (out_proj): Linear(in_features=1024, out_features=1024, bias=True)
                )
              )
            )
          )
          (post_layernorm): LayerNorm((1024,), eps=1e-05, elementwise_affine=True)
        )
      )
      (img_projection): Sequential(
        (0): Linear(in_features=4096, out_features=3072, bias=True)
        (1): GELU(approximate='none')
        (2): Linear(in_features=3072, out_features=3072, bias=True)
      )
    )
    (layers): ModuleList(
      (0-31): 32 x Phi3DecoderLayer(
        (self_attn): Phi3FlashAttention2(
          (o_proj): Linear(in_features=3072, out_features=3072, bias=False)
          (qkv_proj): Linear(in_features=3072, out_features=9216, bias=False)
          (rotary_emb): Phi3SuScaledRotaryEmbedding()
        )
        (mlp): Phi3MLP(
          (gate_up_proj): Linear(in_features=3072, out_features=16384, bias=False)
          (down_proj): Linear(in_features=8192, out_features=3072, bias=False)
          (activation_fn): SiLU()
        )
        (input_layernorm): Phi3RMSNorm()
        (resid_attn_dropout): Dropout(p=0.0, inplace=False)
        (resid_mlp_dropout): Dropout(p=0.0, inplace=False)
        (post_attention_layernorm): Phi3RMSNorm()
      )
    )
    (norm): Phi3RMSNorm()
  )
  (lm_head): Linear(in_features=3072, out_features=32064, bias=False)
)

======== Immediate Child Modules ========
model -> Phi3VModel
lm_head -> Linear

======== Modules Potentially Related to Vision or Text ========
model.vision_embed_tokens -> Phi3ImageEmbedding
model.vision_embed_tokens.drop -> Dropout
model.vision_embed_tokens.img_processor -> CLIPVisionModel
model.vision_embed_tokens.img_processor.vision_model -> CLIPVisionTransformer
model.vision_embed_tokens.img_processor.vision_model.embeddings -> CLIPVisionEmbeddings
model.vision_embed_tokens.img_processor.vision_model.embeddings.patch_embedding -> Conv2d
model.vision_embed_tokens.img_processor.vision_model.embeddings.position_embedding -> Embedding
model.vision_embed_tokens.img_processor.vision_model.pre_layrnorm -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder -> CLIPEncoder
model.vision_embed_tokens.img_processor.vision_model.encoder.layers -> ModuleList
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.0.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.1.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.2.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.3.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.4.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.5.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.6.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.7.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.8.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.9.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.10.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.11.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.12.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.13.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.14.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.15.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.16.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.17.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.18.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.19.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.20.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.21.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.22.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23 -> CLIPEncoderLayer
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.layer_norm1 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp -> CLIPMLP
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp.activation_fn -> QuickGELUActivation
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp.fc1 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.mlp.fc2 -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.layer_norm2 -> LayerNorm
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn -> CLIPAttentionFA2
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.k_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.v_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.q_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.encoder.layers.23.self_attn.out_proj -> Linear
model.vision_embed_tokens.img_processor.vision_model.post_layernorm -> LayerNorm
model.vision_embed_tokens.img_projection -> Sequential
model.vision_embed_tokens.img_projection.0 -> Linear
model.vision_embed_tokens.img_projection.1 -> GELU
model.vision_embed_tokens.img_projection.2 -> Linear
model.layers.0 -> Phi3DecoderLayer
model.layers.1 -> Phi3DecoderLayer
model.layers.2 -> Phi3DecoderLayer
model.layers.3 -> Phi3DecoderLayer
model.layers.4 -> Phi3DecoderLayer
model.layers.5 -> Phi3DecoderLayer
model.layers.6 -> Phi3DecoderLayer
model.layers.7 -> Phi3DecoderLayer
model.layers.8 -> Phi3DecoderLayer
model.layers.9 -> Phi3DecoderLayer
model.layers.10 -> Phi3DecoderLayer
model.layers.11 -> Phi3DecoderLayer
model.layers.12 -> Phi3DecoderLayer
model.layers.13 -> Phi3DecoderLayer
model.layers.14 -> Phi3DecoderLayer
model.layers.15 -> Phi3DecoderLayer
model.layers.16 -> Phi3DecoderLayer
model.layers.17 -> Phi3DecoderLayer
model.layers.18 -> Phi3DecoderLayer
model.layers.19 -> Phi3DecoderLayer
model.layers.20 -> Phi3DecoderLayer
model.layers.21 -> Phi3DecoderLayer
model.layers.22 -> Phi3DecoderLayer
model.layers.23 -> Phi3DecoderLayer
model.layers.24 -> Phi3DecoderLayer
model.layers.25 -> Phi3DecoderLayer
model.layers.26 -> Phi3DecoderLayer
model.layers.27 -> Phi3DecoderLayer
model.layers.28 -> Phi3DecoderLayer
model.layers.29 -> Phi3DecoderLayer
model.layers.30 -> Phi3DecoderLayer
model.layers.31 -> Phi3DecoderLayer

```

**结构分析：**

模型整体结构梳理

1. **图片编码器 (CLIP Vision)**
   • 在打印结果里，你可以看到 model.vision_embed_tokens.img_processor -> CLIPVisionModel(vision_model)。
   • 这实际上就是一个 CLIP 的视觉分支（ClipVit-Large-Patch14-336），用来把图像转成高维视觉特征。官方给它命名为 CLIPVisionModel，这部分只负责处理图像，没有对应的 CLIP 文本编码器。
   • 输出的视觉特征再经过一个 img_projection 的 MLP（model.vision_embed_tokens.img_projection），把维度从 1024 投影到与文本同样的 hidden_size(3072)。

"model_name": "openai/clip-vit-large-patch14-336"
这正是 CLIP 的 ViT-L 模型（patch size 为 14、输入分辨率 336）。



2. 文本解码器 (Phi3DecoderLayer × 32)
   •  model.layers 内含 32 个 Phi3DecoderLayer，用于文本生成或对多模态信息进行解码；最后再经过 lm_head (model.lm_head) 映射到词表完成输出。
   • 这部分就是 Phi-3.5 模型专门的“语言模型”或称“decoder”。

在名字上：
• “model.vision_embed_tokens.*” → 视觉端(编码器)相关，包括 CLIPVisionModel 和后续 MLP 的投影部分(img_projection)。
• “model.layers.” (Phi3DecoderLayer) → 文本解码器(Decoder)层。
• “model.embed_tokens” → 文本输入的词向量 (Embedding)。
• “model.norm” → 文本最后一层归一化，一般也属于文本部分。
• “lm_head” → 文本输出投射层，也属于文本解码侧。

## 微调的模块

1) **“只微调视觉，冻结文本解码器”的思路**


如果你想 **“只更新视觉编码器”**，需要让 `vision_embed_tokens` 下的参数保持 `requires_grad = True`，而文本侧（包括 `decoder`、`embedding`、`lm_head` 等）全部 `requires_grad = False`。

以下是伪代码示例：

```
for name, param in model.named_parameters():  
    # 如果名字里包含 "vision_embed_tokens" 就微调，否则冻结  
    if "vision_embed_tokens" in name:  
        param.requires_grad = True  
    else:  
        param.requires_grad = False  
  
# 只把可训练参数传给优化器  
optimizer = optim.AdamW(  
    filter(lambda p: p.requires_grad, model.parameters()),   
    lr=5e-5  
)  for name, param in model.named_parameters():  
    # 如果名字里包含 "vision_embed_tokens" 就微调，否则冻结  
    if "vision_embed_tokens" in name:  
        param.requires_grad = True  
    else:  
        param.requires_grad = False  
  
# 只把可训练参数传给优化器  
optimizer = optim.AdamW(  
    filter(lambda p: p.requires_grad, model.parameters()),   
    lr=5e-5  
)  
```

这样，`model.vision_embed_tokens.*` 会更新，而文本部分（如 `model.layers.*`、`model.embed_tokens`、`lm_head`）不会变动。 



2. **“只微调文本，冻结视觉编码器”的思路**


反过来，如果你想 **“只更新文本解码器”**，而冻结 `CLIPVisionModel` 等视觉部分，则需要让 `vision_embed_tokens` 相关的所有参数 `requires_grad = False`，文本侧（如 `embedding`、`decoder layer`、`lm_head`）设置为 `True`。

以下是伪代码示例：

```
for name, param in model.named_parameters():  
    # 如果名字里包含 "vision_embed_tokens" 就冻结，否则训练  
    if "vision_embed_tokens" in name:  
        param.requires_grad = False  
    else:  
        param.requires_grad = True  
  
optimizer = optim.AdamW(  
    filter(lambda p: p.requires_grad, model.parameters()),   
    lr=5e-5  
)  
```



完整微调步骤参考：

*https://github.com/xinyuwei-david/david-share/tree/master/Multimodal-Models/Phi3-vision-Fine-tuning*

 	