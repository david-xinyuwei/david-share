# Multi LoRA adapter
When enabling a base model to acquire external capabilities and knowledge, you can use fine-tuning, Function, or RAG (Retrieval-Augmented Generation). For large language models, RAG is more suitable. For smaller language models, fine-tuning is more effective. So, how can we conveniently call multiple Adapters? This article discusses this topic.

## The Significance of Multi-LoRA Adapter Invocation

 
In modern Natural Language Processing (NLP) tasks, large language models (LLMs) such as GPT-3 and Llama have demonstrated powerful capabilities. However, to further enhance the performance of these models in specific tasks or domains, we often need to fine-tune the models. LoRA (Low-Rank Adaptation) adapters are an efficient fine-tuning method that optimizes model performance by adjusting a small number of parameters. This article will introduce how to use the vLLM framework to achieve unified management and invocation of multiple LoRA adapters, and will explore its principles, methods, implementation, and advantages.

LoRA adapters fine-tune pre-trained models through low-rank matrix decomposition techniques without adjusting all the model parameters. This method significantly reduces the computational resources and time required for fine-tuning. Multiple LoRA adapters can be fine-tuned for different tasks and dynamically switched during inference to optimize the model's performance in a multi-task environment.

```
outputs = llm.generate(prompts_oasst, sampling_params_oasst, lora_request=oasstLR)  
```

 

### Advantages of Using LoRA Adapters

1. **Resource Efficiency**: LoRA adapters significantly reduce the computational resources and time required for fine-tuning by adjusting only a small number of parameters. In contrast, RAG may need to maintain and query a large external knowledge base, potentially increasing system complexity and resource demands.
2. **Response Speed**: Since LoRA adapters are directly loaded into the model, the inference speed is usually faster. RAG requires both retrieval and generation steps, which may introduce some latency, especially in real-time applications.
3. **Offline Application**: LoRA adapters can operate completely offline without relying on external knowledge bases, which is very useful in scenarios with network limitations or high data security requirements.
4. **Task-Specific Optimization**: LoRA adapters can be finely tuned for specific tasks or data, enhancing the model's performance on these tasks. For example, by fine-tuning adapters, the model can perform better on specific types of questions.

## Memory Efficiency of Multiple LoRA Adapters

1. **Parameter-Efficient Fine-Tuning**: LoRA adapters fine-tune only a portion of the pre-trained model's parameters through low-rank matrix decomposition, rather than fully fine-tuning the entire model. This approach significantly reduces the number of parameters that need to be stored and updated, thereby reducing memory usage.
2. **Shared Base Model**: Multiple LoRA adapters can share the parameters of a single base model. The base model's parameters only need to be loaded once, and each adapter only requires additional storage for a small number of fine-tuned parameters. This sharing mechanism greatly reduces memory redundancy.
3. **Dynamic Loading and Unloading**: Although the vLLM framework supports loading multiple adapters simultaneously, it ensures minimal memory usage through efficient memory management. The parameters of the adapters are activated and used only when needed, and can remain in a low-memory state when not in use.

## Comparison of Multi-Adapter and RAG Solutions

1. **Dynamic Information Updates**: RAG can access and use the latest information in real-time, suitable for scenarios that require frequent data updates, such as product information and news. This dynamic capability is crucial for applications that need to handle real-time data.

2. **Rich Knowledge Base**: RAG can utilize large external knowledge bases to provide more extensive and detailed information. For issues requiring a large amount of background knowledge or long-tail information, RAG may be more effective.

3. **Flexibility**: The RAG method can flexibly integrate different information sources, such as documents, databases, and APIs, providing diverse information support.

   In practical applications, the choice between using LoRA adapters or the RAG method depends on specific application needs and environments:

- If your application requires efficient, fast responses and can significantly improve specific task performance through model fine-tuning, LoRA adapters may be more suitable.

- If your application needs real-time access to and use of the latest external information or needs to handle a large amount of background knowledge, the RAG method may be more appropriate.

  Of course, these two methods can also be used in combination. For example, LoRA adapters can be used to enhance the model's basic performance on specific tasks, while RAG can supplement and expand the model's knowledge base to achieve the best results. If dealing with edge small models, it is recommended to use the multi-adapter method. Fine-tune small models adapted to different scenarios and then invoke them according to the task.
  
  

## Multi LoRA adapter Code
Define base model:
```
model_id = "meta-llama/Meta-Llama-3-8B"
llm = LLM(model=model_id, enable_lora=True, max_lora_rank=16)
```
Load First LoRA Adapter
```
sampling_params_oasst = SamplingParams(temperature=0.7, top_p=0.9, max_tokens=500)
oasst_lora_id = "kaitchup/Meta-Llama-3-8B-oasst-Adapter"
oasst_lora_path = snapshot_download(repo_id=oasst_lora_id)
oasstLR = LoRARequest("oasst", 1, oasst_lora_path)
```
Load Second LoRA Adaptor
```
sampling_params_xlam = SamplingParams(temperature=0.0, max_tokens=500)
xlam_lora_id = "kaitchup/Meta-Llama-3-8B-xLAM-Adapter"
xlam_lora_path = snapshot_download(repo_id=xlam_lora_id)
xlamLR = LoRARequest("xlam", 2, xlam_lora_path)
```
Inference code
```
prompts_oasst = [
    "### Human: Check if the numbers 8 and 1233 are powers of two.### Assistant:",
    "### Human: What is the division result of 75 divided by 1555?### Assistant:",
]

outputs = llm.generate(prompts_oasst, sampling_params_oasst, lora_request=oasstLR)

for output in outputs:
    generated_text = output.outputs[0].text
    print(generated_text)
    print('------')
    
    
prompts_xlam = [
    "<user>Check if the numbers 8 and 1233 are powers of two.</user>\n\n<tools>",
    "<user>What is the division result of 75 divided by 1555?</user>\n\n<tools>",
]

outputs = llm.generate(prompts_xlam, sampling_params_xlam, lora_request=xlamLR)

for output in outputs:
    generated_text = output.outputs[0].text
    print(generated_text)
    print('------')    
```

### Refer to : 
*https://kaitchup.substack.com/p/serve-multiple-lora-adapters-with*