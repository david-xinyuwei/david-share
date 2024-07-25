# Function-Call-Training

Some models inherently have function call capabilities, such as OpenAI and Phi3. Some do not. We can enhance a model's function call capabilities through fine-tuning, which means enabling the model to natively possess more functions. 

In this repo, I will fine-tune Microsoft's Phi3 using the xlam-function-calling-60k dataset to enhance its native function call capabilities. The training method employed will be Q-LoRA

## Training Dataset Analysis
The labeled data in the training set is shown in the figure below. In the 'answers' column, 'name' represents the name of the function.

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Function-Call-Training/images/4.png)

After the model is completed, when we input a prompt, the trained model will search for the corresponding function based on the data in the training set.

## Define Model

```
#use bf16 and FlashAttention if supported
if torch.cuda.is_bf16_supported():
  os.system('pip install flash_attn')
  compute_dtype = torch.bfloat16
  attn_implementation = 'flash_attention_2'
else:
  compute_dtype = torch.float16
  attn_implementation = 'sdpa'

model_name = "microsoft/Phi-3-mini-128k-instruct"
#Tokenizer
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
tokenizer.pad_token = "<|eot_id|>"
tokenizer.pad_token_id = 128009
tokenizer.padding_side = 'left'
```
Explanation of the data types used in the above code:

- FP16: Uses 16 bits to represent a floating-point number, with 1 bit for the sign, 5 bits for the exponent, and 10 bits for the mantissa. This format provides high precision but has a smaller numerical range. It is commonly used in deep learning training and inference processes to accelerate computation and reduce memory usage, while generally having a minimal impact on model accuracy.
- BF16: Also uses 16 bits to represent a floating-point number, but with a different allocation: 1 bit for the sign, 8 bits for the exponent, and 7 bits for the mantissa. The design of BF16 allows it to maintain the same numerical range as FP32 but with lower precision. Because it can maintain the same numerical range as FP32, BF16 can offer better training stability compared to FP16, while still enjoying the computational and storage efficiency of FP16.


## Define Q-LoRA parameters
```
def QLoRA(ds):  
    bnb_config = BitsAndBytesConfig(  
        load_in_4bit=True,  
        bnb_4bit_quant_type="nf4",  
        bnb_4bit_compute_dtype=compute_dtype,  
        bnb_4bit_use_double_quant=True,  
    )  
    model = AutoModelForCausalLM.from_pretrained(  
        model_name, quantization_config=bnb_config, device_map={"": 0}, attn_implementation=attn_implementation  
    )  
    model = prepare_model_for_kbit_training(model, gradient_checkpointing_kwargs={'use_reentrant': True})  
  
    # Configure the pad token in the model  
    tokenizer.pad_token = tokenizer.eos_token  # Solution 1  
    # or  
    # tokenizer.add_special_tokens({'pad_token': '[PAD]'})  # Solution 2  
    # model.resize_token_embeddings(len(tokenizer))  # Uncomment if using Solution 2  
  
    model.config.pad_token_id = tokenizer.pad_token_id  
    model.config.use_cache = False  # Gradient checkpointing is used by default but not compatible with caching  
  
    peft_config = LoraConfig(  
        lora_alpha=16,  
        lora_dropout=0.05,  
        r=16,  
        bias="none",  
        task_type="CAUSAL_LM",  
        target_modules=['k_proj', 'q_proj', 'v_proj', 'o_proj', "gate_proj", "down_proj", "up_proj"]  
    )  
    training_arguments = SFTConfig(  
        output_dir="./Phi3_xLAM",  
        optim="adamw_8bit",  
        per_device_train_batch_size=60,  
        # gradient_accumulation_steps=1,  
        log_level="debug",  
        save_steps=250,  
        logging_steps=10,  
        learning_rate=1e-4,  
        fp16=not torch.cuda.is_bf16_supported(),  
        bf16=torch.cuda.is_bf16_supported(),  
        max_steps=1000,  
        warmup_ratio=0.1,  
        lr_scheduler_type="linear",  
        dataset_text_field="text",  
        max_seq_length=512,  
    )  
    trainer = SFTTrainer(  
        model=model,  
        train_dataset=ds,  
        peft_config=peft_config,  
        tokenizer=tokenizer,  
        args=training_arguments,  
    )  
    trainer.train()  
```

## Process the training set
```
# Load and process the dataset  
ds = load_dataset("Salesforce/xlam-function-calling-60k", split="train")  
  
def process(row):  
    row["query"] = "<user>" + row["query"] + "</user>\n\n"  
    tools = [str(t) for t in json.loads(row["tools"])]  
    answers = [str(a) for a in json.loads(row["answers"])]  
    row["tools"] = "<tools>" + "\n".join(tools) + "</tools>\n\n"  
    row["answers"] = "<calls>" + "\n".join(answers) + "</calls>"  
    row["text"] = row["query"] + row["tools"] + row["answers"] + tokenizer.eos_token  
    return row  
  
ds = ds.map(  
    process,  
    num_proc=multiprocessing.cpu_count(),  
    load_from_cache_file=False,  
)  
  
```
## Lanuch Training
```
QLoRA(ds)  
```
The model was trained for a total of 1000 steps, and the training took a total of 1.5 hours.

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Function-Call-Training/images/5.png)

The loss function is continuously decreasing during training:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Function-Call-Training/images/6.png)

Check the resource consumption during training:

![image](https://github.com/davidsajare/david-share/blob/master/Deep-Learning/Function-Call-Training/images/1.png)


## Conduct inference testing

Load the model：
```
if torch.cuda.is_bf16_supported():
  os.system('pip install flash_attn')
  compute_dtype = torch.bfloat16
  attn_implementation = 'flash_attention_2'
else:
  compute_dtype = torch.float16
  attn_implementation = 'sdpa'
quantization_config=BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=compute_dtype,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
)


adapter= "./Phi3_xLAM/checkpoint-1000"
model_name = "microsoft/Phi-3-mini-128k-instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
print(f"Starting to load the model {model_name} into memory")

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=quantization_config,
    torch_dtype=compute_dtype,
    device_map={"": 0},
    attn_implementation=attn_implementation,
)

print(model)
model = PeftModel.from_pretrained(model, adapter)
```
Next, perform three inference tests to verify that the fine-tuned model automatically calls the Function when processing prompts.

### Test1 ：Get the latest news from the China Daily source
Prompt：
```
prompt = "<user>Get the latest news from the China Daily source.</user>\n\n<tools>"
inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, do_sample=False, temperature=0.0, max_new_tokens=150)
result = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(result)
```
Result:
```
<user>Get the latest news from the China Daily source.</user>

<tools>{'name': 'get_latest_news', 'description': 'Fetches the latest news from a specified source using the RapidAPI service.', 'parameters': {'source': {'description': 'The source from which to fetch the latest news.', 'type': 'str', 'default': 'bbc-news'}}}</tools>

<calls>{'name': 'get_latest_news', 'arguments': {'source': 'china-daily'}}</calls>

<benchmarks>{'name': 'get_latest_news', 'description': 'Fetches the latest news from a specified source using the RapidAPI service.', 'parameters': {'source': {'
```
Could see that when the prompt asks for the latest news from the China Daily source, it will call the get_latest_news function.

### Test2 ：Check if the numbers 8 and 1233 are powers of two.
Prompt:
```
prompt = "<user>Check if the numbers 8 and 1233 are powers of two.</user>\n\n<tools>"
```
Result:
```
<user>Check if the numbers 8 and 1233 are powers of two.</user>

<tools>{'name': 'is_power_of_two', 'description': 'Checks if a number is a power of two.', 'parameters': {'num': {'description': 'The number to check.', 'type': 'int'}}}</tools>

<calls>{'name': 'is_power_of_two', 'arguments': {'num': 8}}
{'name': 'is_power_of_two', 'arguments': {'num': 1233}}</calls>

<response>{'is_power_of_two': True}
{'is_power_of_two': False}</response>
</response>
```
Could see that when asked if the numbers 8 and 1233 are powers of two, it will call the is_power_of_two function and provide the correct answer.

### Test3 ：Tell me the detailed information on the quote for Microsoft
```
prompt = "<user>Tell me the detailed information on the quote for Microsoft.</user>\n\n<tools>"
```
Result:
```
<user>Tell me the detailed information on the quote for Microsoft.</user>

<tools>{'name': 'get_quote_by_symbol', 'description': 'Fetches detailed information about a stock quote by its symbol using the Yahoo Finance API.', 'parameters': {'symbol': {'description': 'The stock symbol for which to retrieve the quote information.', 'type': 'str', 'default': 'AAPL'}}}</tools>

<calls>{'name': 'get_quote_by_symbol', 'arguments': {'symbol': 'MSFT'}}</calls>

<benchmarks>{'name': 'get_stock_quote', 'description': 'Fetches the stock quote for a given ticker symbol using the Yahoo Finance API.'
```
Could see that when asked for detailed information on the quote for Microsoft, the model correctly used the get_quote_by_symbol function


**Refer to:**

https://kaitchup.substack.com/p/function-calling-fine-tuning-llama