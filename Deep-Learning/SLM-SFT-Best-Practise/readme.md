# SLM SFT Best practice

Through seven rounds of parameter optimization, the fine-tuned model's accuracy in answering questions was increased to 100%. Using Phi3.5 as the base model, fine-tune the model's coding capabilities. Since Phi-3.5 has not released a base model, only the Instruct model can be used.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/SLM-SFT-Best-Practise/images/3.png)

## First fine-tuning

Example of training corpus, all training data mentioned in the text has been desensitized：

Prompt

```
.NET Framework如何使用XXX SDK
```

Completion:

```

使用 Qaaa.PasS;
using （var scope = new xxx（User））
{
xxx context = 
}
```

After training, the responses were completely irrelevant.

Check the training loss function:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlCLf0SfxDILMmickbzgRBIbLiceicwkDJkic7ib9XIA04huEt8LScfSealaZg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The validation set loss is decreasing too slowly, indicating overfitting.



## Second round:

Set lora_dropout = 0.05

Adjust the number of epochs from 30 to 100 

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlCVfJOia8SibkzTBSdceZSQ4NG3zuDDmP48icga7CCHHJGlLXHU3Bk44lpQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The validation set loss function still has issues.

## Third round

Increase the dataset, expanding each of the 30 questions to over 100, making a total of 3000 entries in the dataset.

Reshuffle the dataset randomly

Change the training/validation split to 0.7/0.3 

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlCYk3CfariaRk5G7JErrVgR40J2ljTl1BTic0UYz14niakO56DN9ichfopYA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The overfitting issue during training seems to be resolved, but the trained model is still giving incorrect answers.

## Fourth round

Enhance the training corpus by adding Chain of Thought (COT) steps, change the training corpus to be written entirely in English. For example: 

Prompt

```
How to use NEBULA SDK to obtain the English name of CAMP User for .NET Framework project?
```

Completion

```
**Step-by-Step Analysis:**
1. **Define Purpose**: The code aims to use XXX SDK by retrieving data based on the user's identity.

2. **Code Structure**: Imports necessary namespaces and defines an MVC controller with authorization.

3. **Data Handling**: Retrieves the English name associated with the authenticated user identity.

**Augmented Code Sample**:
....
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlCDosIJht85fEqktibHrLUzhqraVupI6H1gMicJ0vJw29IQRcOicemtqmiaA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The capability of the trained model has improved, with half of the four questions answered correctly.

## Fifth round

Generate multiple training data entries for a single piece of knowledge using random insertion, random swapping, random deletion, and back-translation. 



![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlC9iaFSy7AXTM1xtUtUBbwE1roLEoEZoibEqLQX3HufVmiaJznCgNcicfnHw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Accuracy improved by more than 10% compared to the last time. 



## Sixth round

Add more diverse prompts to the training parameters and switch from LoRA fine-tuning to full fine-tuning.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlCaz55sheucaG30fPgfufe01lAictqL41lUIswnA867qBS1ibAoKIRuNrw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Accuracy improved significantly, but sometimes the answers to the same question are inconsistent. 



## Seventh round

Re-fine-tune the model, setting the learning rate to learning_rate=5e-4, previously it was learning_rate=5e-5.

During inference, set the following parameters:

- Set do_sample=False:

Disable random sampling to ensure the model always chooses the highest probability word.

- Set temperature=0.0:

The temperature parameter controls the randomness of sampling. The lower the value, the more the model tends to choose high-probability words.

When the temperature is 0, combined with do_sample=False, the model will generate text in the most deterministic way.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nW4ricicoQAQCyUh6BAwsVYlCZ36Zl9hCV5OHeYCIXTmiaFfgyniak6q1Uq7tiaGSm0bwsia6PG9tjetHQQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

After training, the model can accurately answer questions. 

## Final Training code

```
model_name = "microsoft/Phi-3.5-Mini-instruct"  
tokenizer = AutoTokenizer.from_pretrained(  
    model_name,  
    trust_remote_code=True,  
    add_eos_token=True,  
    use_fast=True  
)  
  
tokenizer.pad_token = tokenizer.eos_token  
tokenizer.pad_token_id = tokenizer.eos_token_id  
tokenizer.padding_side = 'left'  
  
system_prompt = (  
    "<|system|>\n"  
    "You are an expert in .NET/.NET Framework and are familiar with the functions provided by XXX SDK. You know how to use XXX SDK to develop application systems on the XXX platform.. "  
)  

special_tokens = {'additional_special_tokens': ['<|system|>', '<|user|>', '<|assistant|>']}  
tokenizer.add_special_tokens(special_tokens)  
  
# 读取 CSV 文件  
df = pd.read_csv("/home/david/Phi3.5_xxxquestion.csv")  
  
# 移除包含缺失值的行  
df = df.dropna(subset=['Question', 'Answer'])  
  
# 确保所有数据都是字符串类型  
df['Question'] = df['Question'].astype(str)  
df['Answer'] = df['Answer'].astype(str)  
  
# 定义函数：格式化数据集，包含系统提示  
def format_dataset(row):  
    # 返回字符串而不是字典  
    return f"{system_prompt}<|user|>\n{row['Question']}\n<|assistant|>\n{row['Answer']}\n"  
  
# 应用格式化函数  
df['text'] = df.apply(format_dataset, axis=1)  
  
# 检查缺失值  
print({col: df[col].isnull().sum() for col in df.columns})  
  
# 将处理后的 DataFrame 转换为 Dataset  
ds = Dataset.from_pandas(df)  
  
# 分割数据集  
train_df, eval_df = train_test_split(df, test_size=0.2, random_state=42)  
  
# 将 DataFrame 转换为 Dataset 格式  
train_data = Dataset.from_pandas(train_df)  
eval_data = Dataset.from_pandas(eval_df)  
  
# 定义数据预处理函数  
def tokenize_function(examples):  
    tokens = tokenizer(  
        examples["text"],  
        padding="max_length",  
        truncation=True,  
        max_length=1024,  
    )  
    tokens["labels"] = tokens["input_ids"].copy()  
    # 将填充位置的标签设置为 -100，以便在计算损失时忽略  
    tokens["labels"] = [  
        [-100 if token == tokenizer.pad_token_id else token for token in labels]  
        for labels in tokens["labels"]  
    ]  
    return tokens  
  
# 对数据集进行预处理  
train_data = train_data.map(tokenize_function, batched=True)  
eval_data = eval_data.map(tokenize_function, batched=True)  
  
# 设置模型，并调整嵌入层大小以适应新的特殊标记  
model = AutoModelForCausalLM.from_pretrained(  
    model_name,  
    trust_remote_code=True,  
)  
  
# 调整模型的嵌入层大小  
model.resize_token_embeddings(len(tokenizer))  
  
# 启用梯度检查点（可选，节省显存）  
# model.gradient_checkpointing_enable()  
  
# 根据硬件支持情况，设置 fp16 和 bf16  
if torch.cuda.is_bf16_supported():  
    bf16 = True  
    fp16 = False  
elif torch.cuda.is_available():  
    bf16 = False  
    fp16 = True  
else:  
    bf16 = False  
    fp16 = False  
  
# 定义训练参数  
training_args = TrainingArguments(  
    output_dir="/Phi35FineTuneResult/Phi-3.5-Mini_FullFineTune-r4",  
    eval_strategy="steps",  # 修改为 eval_strategy  
    eval_steps=25,  
    logging_steps=25,  
    save_steps=100,  
    per_device_train_batch_size=1,  # 根据显存大小调整  
    per_device_eval_batch_size=1,  
    num_train_epochs=100,  
    gradient_accumulation_steps=32,  # 根据需要调整  
    learning_rate=5e-4,  
    warmup_steps=100,  
    fp16=fp16,  
    bf16=bf16,  
    logging_dir='/Phi35FineTuneResult/logs',  
    report_to=[],  # 不使用任何日志记录工具，如 TensorBoard  
)  
  
# 初始化训练器  
trainer = Trainer(  
    model=model,  
    args=training_args,  
    train_dataset=train_data,  
    eval_dataset=eval_data,  
    tokenizer=tokenizer,  
)  
  
# 开始训练  
trainer.train()  
```

