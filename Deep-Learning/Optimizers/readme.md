# AI Training Optimizers selection

Common optimizers include but are not limited to:  

- **SGD (Stochastic Gradient Descent):** The most basic gradient optimization method.  
- **Momentum SGD:** Adds momentum to SGD to accelerate convergence.  
- **Adagrad:** Features adaptive learning rates, adjusting to different parameter learning speeds.  
- **Adam (Adaptive Moment Estimation):** Combines momentum and adaptive learning rates, widely used.  
- **AdamW:** An improved version of Adam that addresses weight decay issues.  
  
## Principles and Memory Consumption of AdamW Optimizer 

During training, AdamW tracks two key parameters:  

- **First Moment (Momentum, denoted as \( m_t \)):** The exponential moving average of past gradients, helping guide optimization in the right direction. By accumulating previous gradient information, momentum makes parameter updates smoother and faster.  
- **Second Moment (Variance, denoted as \( v_t \)):** The exponential moving average of the squared gradients, used to adjust each parameter's learning rate and prevent excessive updates in any direction.  
  

Storing these two additional states for each model parameter significantly increases memory consumption. By default, these optimizer states use the float32 data type, meaning the memory usage of the optimizer is double that of the model parameters.  

Example: For the Llama 3.1 8B model with 8.03B parameters, the AdamW optimizer requires creating and storing:  
- **First Moment:** Momentum for 8.03B parameters.  
- **Second Moment:** Second moment for 8.03B parameters.  
  

In total, 16.06B additional parameters need to be stored. Since each parameter occupies 4 bytes (float32), the optimizer states consume 16.06B × 4 = 64.24 GB of memory.  

## Paged AdamW Optimizer  

Paged AdamW is a variant of AdamW, primarily differing in memory management strategy. It allows optimizer states to switch between GPU RAM and CPU RAM to save GPU memory.  

- **Memory Management Paging Mechanism:** When GPU memory is insufficient, optimizer states are "paged" to CPU memory. This is similar to OS memory paging, transferring data only when needed.  
- **Advantages:** Enables training of large models even with limited GPU memory. Due to NVIDIA GPU's unified memory technology, the paging process minimally impacts performance, ensuring training speed.  
  
## List of Specifiable Optimizers in Code  

During training, the following optimizers can be specified:  

['adamw_hf', 'adamw_torch', 'adamw_torch_fused', 'adamw_torch_xla', 'adamw_torch_npu_fused', 'adamw_apex_fused', 'adafactor', 'adamw_anyprecision', 'sgd', 'adagrad', 'adamw_bnb_8bit', 'adamw_8bit', 'lion_8bit', 'lion_32bit', 'paged_adamw_32bit', 'paged_adamw_8bit', 'paged_lion_32bit', 'paged_lion_8bit', 'rmsprop', 'rmsprop_bnb', 'rmsprop_bnb_8bit', 'rmsprop_bnb_32bit', 'galore_adamw', 'galore_adamw_8bit', 'galore_adafactor', 'galore_adamw_layerwise', 'galore_adamw_8bit_layerwise', 'galore_adafactor_layerwise', 'lomo', 'adalomo']



## Techniques to Address Memory Consumption: Quantization and Paging  

To manage the high memory consumption of the AdamW optimizer effectively, the following two techniques are introduced:  

1. **8-bit Quantization**  
  
   - **Principle:** Reduces optimizer states from float32 (32-bit precision) to int8 (8-bit precision), significantly decreasing memory usage.  
   - **Effect:** For the Llama 3.1 model, memory requirements for optimizer states drop from approximately 64 GB to 16 GB. Although quantization may introduce some numerical errors, its impact on training stability and loss is minimal.  
  
2. **Paging**  
  
   - **Principle:** Utilizes CUDA's unified memory feature to automatically page optimizer states to CPU memory when GPU memory is insufficient.  
   - **Advantages:**  
     - **Efficiency:** More efficient than manual CPU offloading, with no need for explicit data transfer management.  
     - **Flexibility:** If GPU memory is sufficient, optimizer states remain entirely in GPU memory, with almost no performance overhead.  

## Experimental Results and Analysis  

Experiments on different optimizer configurations were conducted on an A100 GPU, with the following results:  

- **Learning Curve Comparison (8-bit Quantization vs. 32-bit Precision):** Optimizer states using 8-bit quantization show almost no difference in learning curves compared to the 32-bit version. This demonstrates that 8-bit quantization significantly saves memory without negatively affecting the training process.  

- **Memory Consumption:**  
  - **Standard AdamW:** Unable to fully train the Llama 3.1 model on a single GPU due to memory limitations (exceeding 40 GB).  
  - **Paged Optimizer:** Only configurations using the paged optimizer can avoid out-of-memory issues. Through paging technology, training can be successfully completed on a 40 GB GPU.  
  
- **Training Time Performance of Paged Optimizer:** The impact of the paged optimizer on training time is not significant. Due to the smaller memory footprint of 8-bit quantized states, Paged AdamW 8-bit even runs faster than Paged AdamW 32-bit.  

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUVbeUKTR1HfW9WlRnPHUoFnMQkXMseDW2VNRibvQlfFcRWJmcyJ2KaadQx3qMm0rlzZn4q6cYCibGw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

  ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUVbeUKTR1HfW9WlRnPHUoFMdKIvqdOxNicJtntMKcq8Pltujv7RMLA2OLT331oNGLwyFEZ3pA1j8Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)
## Summary  

- **AdamW Optimizer:** Performs well in training large models, but high memory consumption is a major bottleneck.  
- **8-bit Quantization:** Reduces memory usage significantly by lowering the precision of optimizer states, with minimal impact on training effectiveness.  
- **Paging Technology:** Utilizes GPU's unified memory to automatically page optimizer states between GPU and CPU, effectively solving memory limitation issues.  
- **Practical Significance:** Combining 8-bit quantization and paging technology enables training of large models with limited hardware resources, providing a feasible solution for the popularization and promotion of model training. 


## Code of test
Training code:
```
def fine_tune_llama(model_name, optim, bs, gs):
  #Tokenizer
  tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
  tokenizer.pad_token = "<|finetune_right_pad_id|>"
  tokenizer.pad_token_id = 128004
  tokenizer.padding_side = 'right'

  ds = load_dataset("timdettmers/openassistant-guanaco")

  #Add the EOS token
  def process(row):
      row["text"] = row["text"]+tokenizer.eos_token
      return row

  ds = ds.map(
      process,
      num_proc= multiprocessing.cpu_count(),
      load_from_cache_file=False,
  )


  model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map={"": 0}, attn_implementation=attn_implementation, torch_dtype=compute_dtype
  )

  model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})


  training_arguments = SFTConfig(
          output_dir="./Llama-3.1-8B_"+optim,
          optim=optim,
          per_device_train_batch_size=bs,
          gradient_accumulation_steps=gs,
          log_level="debug",
          save_strategy="no",
          logging_steps=25,
          learning_rate=1e-5,
          bf16 = True,
          num_train_epochs=1,
          warmup_ratio=0.1,
          lr_scheduler_type="linear",
          dataset_text_field="text",   
          report_to=[],
          max_seq_length=512,
  )

  trainer = SFTTrainer(
          model=model,
          train_dataset=ds['train'],
          tokenizer=tokenizer,
          args=training_arguments
 )
```

```
fine_tune_llama("meta-llama/Llama-3.1-8B", "adamw_torch", 1, 32)    
```

```
fine_tune_llama("meta-llama/Llama-3.1-8B", "paged_adamw_32bit", 1, 32)
```

```
fine_tune_llama("meta-llama/Llama-3.1-8B", "adamw_8bit", 1, 32)
```

```
fine_tune_llama("meta-llama/Llama-3.1-8B", "paged_adamw_8bit", 1, 32)
```



**Refer to**: *https://newsletter.kaitchup.com/p/fine-tuning-llms-with-32-bit-8-bit*
