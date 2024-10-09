# Pytorch PEFT SFT and convert to ONNX

ONNX (Open Neural Network Exchange) is an open format used to represent machine learning and deep learning models. It was introduced by Microsoft and Facebook in 2017, aiming to facilitate model interoperability between different deep learning frameworks. With ONNX, you can seamlessly convert models between different deep learning frameworks such as PyTorch and TensorFlow.

Currently, ONNX fine-tuning can be done using Olive, but it does not yet support LoRA. If you want to perform LoRA fine-tuning with PyTorch and use ORT for inference, how can this be achieved?

1. First, fine-tune the model using LoRA. Do not use QLoRA, as it may result in significant precision loss during subsequent merging.
2. Merge the Adapter with the PyTorch base model.
3. Convert the merged safetensors to ONNX.
4. Generate the genai_config.json file using ONNX Runtime GenAI Model Builder.
5. Perform inference using onnxruntime-genai.



## Overview of the Steps

LoRA SFT:

```
model_name = "microsoft/Phi-3.5-Mini-instruct"

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, add_eos_token=True, use_fast=True)
tokenizer.pad_token = tokenizer.unk_token
tokenizer.pad_token_id = tokenizer.convert_tokens_to_ids(tokenizer.pad_token)
tokenizer.padding_side = 'left'

ds = load_dataset("timdettmers/openassistant-guanaco")


model = AutoModelForCausalLM.from_pretrained(
          model_name, torch_dtype=compute_dtype, trust_remote_code=True,  device_map={"": 0}, attn_implementation=attn_implementation
)

model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':True})

peft_config = LoraConfig(
        lora_alpha=16,
        lora_dropout=0.05,
        r=16,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules= ['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]
)


training_arguments = SFTConfig(
        output_dir="./Phi-3.5/Phi-3.5-Mini_LoRA",
        eval_strategy="steps",
        do_eval=True,
        optim="adamw_torch",
        per_device_train_batch_size=4,
        gradient_accumulation_steps=8,
        per_device_eval_batch_size=4,
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
        max_seq_length=512
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



Merge adapter：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXv9KDNb16IfM5zia09B98H6ia1YjbIW8uuUlMwunYJ0LXwjvRia3Nib9pD0NJQhYXT1JPUOm9bw6NhKg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Consolidated results:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXv9KDNb16IfM5zia09B98H6I8MBzKeb0nhw7iaHJBfWq9MHB7qD27FtbvknTWRBwyUGUL6zhXt0pMw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**Export to ONNX:**

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXv9KDNb16IfM5zia09B98H6V4WfiaO03NjLJSVexasczvoyV9jSno3RIkHVk05AZXlH5k74VND2WFA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Export result：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXv9KDNb16IfM5zia09B98H6BvQpEI6EV8nFKF9vFFm1Oej9A0bl28pAPqaqDD4sDQFLDbu9lGd7SQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Generate genai_config.json. when doing the conversion, you need to use FP32.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXv9KDNb16IfM5zia09B98H6Laz9vJSGbsKqN4faXn7zrPzWR7eRqrIkMO9iciaqVkFc9iaxVEBDajI4g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Files needed during ONNX inference：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXv9KDNb16IfM5zia09B98H6gteJ7PvMBic6aPicauBudGsYwbUujRO3to8Aetn3mIvkwHz6xc7rlrVQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Detailed Code

Merge the adapter

```
model_name = "microsoft/Phi-3.5-Mini-instruct"  
adapter_path = "/root/Phi-3.5-Mini_LoRA/checkpoint-411/"  
  
# 加载 tokenizer  
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True, use_fast=True)  
  
# 加载模型  
model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)  
  
# 加载适配器  
model = PeftModel.from_pretrained(model, adapter_path)  
  
# 设置模型为评估模式  
model.eval()  
  
# 定义推理函数  
def generate_text(prompt, max_length=500):  
    inputs = tokenizer(prompt, return_tensors="pt")  
    attention_mask = inputs['attention_mask']  
    with torch.no_grad():  
        outputs = model.generate(  
            inputs.input_ids,  
            attention_mask=attention_mask,  
            max_length=max_length,  
            num_return_sequences=1,  
            do_sample=True,  
            top_k=50,  
            top_p=0.95  
        )  
    return tokenizer.decode(outputs[0], skip_special_tokens=True)  
  
# 示例推理  
prompt = ("1+1=?") 
generated_text = generate_text(prompt)  
print(generated_text)  
```

ONNX Export

```
model_checkpoint = "/root/Phi-3.5-Mini-LoRA-Merge"
save_directory = "/root/onnx1/"

# Load a model from transformers and export it to ONNX
ort_model = ORTModelForCausalLM.from_pretrained(model_checkpoint, export=True)
tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)

# Save the onnx model and tokenizer
ort_model.save_pretrained(save_directory)
tokenizer.save_pretrained(save_directory)
```

Generate genai_config.json

```
(phi3.5) root@h100vm:~/onnxruntime-genai/src/python/py/models# python3 builder.py -m  microsoft/Phi-3.5-mini-instruct -o /root/onnx4 -p fp16 -e cuda -c /root/onnx1 --extra_options config_only=true
```

```
Valid precision + execution provider combinations are: FP32 CPU, FP32 CUDA, FP16 CUDA, FP16 DML, INT4 CPU, INT4 CUDA, INT4 DML
Extra options: {'config_only': 'true'}
config.json: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3.45k/3.45k [00:00<00:00, 33.5MB/s]
configuration_phi3.py: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 11.2k/11.2k [00:00<00:00, 79.0MB/s]
A new version of the following files was downloaded from https://huggingface.co/microsoft/Phi-3.5-mini-instruct:
- configuration_phi3.py
. Make sure to double-check they do not contain any added malicious code. To avoid downloading new versions of the code file, you can pin a revision.
GroupQueryAttention (GQA) is used in this model.
generation_config.json: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 195/195 [00:00<00:00, 2.19MB/s]
Saving GenAI config in /root/onnx4
tokenizer_config.json: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3.98k/3.98k [00:00<00:00, 42.8MB/s]
tokenizer.model: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 500k/500k [00:00<00:00, 105MB/s]
tokenizer.json: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1.84M/1.84M [00:00<00:00, 2.13MB/s]
added_tokens.json: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 306/306 [00:00<00:00, 3.40MB/s]
special_tokens_map.json: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 665/665 [00:00<00:00, 7.23MB/s]
Saving processing files in /root/onnx4 for GenAI
```

Copy generated files to ONNX model file:

```
(phi3.5) root@h100vm:~/onnx4# ls
added_tokens.json  genai_config.json  special_tokens_map.json  tokenizer.json  tokenizer.model  tokenizer_config.json
(phi3.5) root@h100vm:~/onnx4# cp ./* /root/onnx1
```

Inference test with ONNX:

```
model = og.Model('/root/onnx1/1')
tokenizer = og.Tokenizer(model)
tokenizer_stream = tokenizer.create_stream()
 
# Set the max length to something sensible by default,
# since otherwise it will be set to the entire context length
search_options = {}
search_options['max_length'] = 2048

chat_template = '<|user|>\n{input} <|end|>\n<|assistant|>'

text = input("Input: ")
if not text:
   print("Error, input cannot be empty")
   exit

prompt = f'{chat_template.format(input=text)}'

input_tokens = tokenizer.encode(prompt)

params = og.GeneratorParams(model)
params.set_search_options(**search_options)
params.input_ids = input_tokens
generator = og.Generator(model, params)

print("Output: ", end='', flush=True)

try:
   while not generator.is_done():
     generator.compute_logits()
     generator.generate_next_token()

     new_token = generator.get_next_tokens()[0]
     print(tokenizer_stream.decode(new_token), end='', flush=True)
except KeyboardInterrupt:
    print("  --control+c pressed, aborting generation--")

print()
del generator
```

