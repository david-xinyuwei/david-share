# 4 Steps of AOAI E2E Fine-Tuning best practice

In this repository, I will start by introducing the process of synthesizing training data from Personas and then proceed step by step to fine-tune GPT-3.5 or other open-source models. This article will also discuss how to improve the fine-tuning results by adjusting the fine-tuning parameters.

## Step1: Obtain character description information from HF

argilla/FinePersonas-v0.1 is a high-quality, open dataset on HF (Hugging Face) containing 21 million detailed character descriptions, designed for generating diverse and controllable synthetic text.

By specifying a Persona, I can obtain character description information, and then use an LLM model to generate questions and answers respectively. In this repository, I obtain the Programmer's character information to ultimately fine-tune the model's coding ability.

The following image shows the initial information obtained based on the Programmer Persona from argilla/FinePersonas-v0.1.
At this stage, the dataset only contains the description of the Persona:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVtjAv87FxXtEsgloFeiahnPupcFLn55nWCn2lC0ac4nPTu9iaN84zKZI8M1O58uIwO4ibc7zqX3qeA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The code I used: 1.generatedata.py

```
(base) root@davidwei:/mnt/c/david-share/2# cat 1.generatedata.py
import sys
from tqdm import tqdm
from datasets import load_dataset
import json 

# 加载数据集
dataset = load_dataset("argilla/FinePersonas-v0.1", split="train", streaming=True)

# 过滤数据集以包含 "Programmer" 标签的条目
dataset = dataset.filter(lambda example: "Programmer" in example["labels"])

questions = []
counter = 0
max_personas = 500

# 遍历数据集并生成问题列表
for d in tqdm(dataset):
    questions.append([{      
        "role": "user",
        "content": "Generate a question that this persona can answer with expertise:\n\n"+d['persona']
    }])
    if max_personas == counter + 1:
        break
    counter += 1

print(len(questions))

# 将生成的问题列表持久化到本地的 JSON 文件中
with open('questions.json', 'w', encoding='utf-8') as f:
    json.dump(questions, f, ensure_ascii=False, indent=4)

print(f"Generated {len(questions)} questions and saved to questions.json")
```

## Step 2: Generate Questions and Answers based on Personas

In this step, based on the Personas descriptions obtained from HF and the Prompts I specified, I use GPT-4 to generate domain-specific Questions and Answers. Additionally, this step includes filtering out irrelevant data.

### Generate questions using 4o

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVtjAv87FxXtEsgloFeiahnjquZVnLicFMwSGzNrrgC8PU2bF8KCXM2jsOpEtyYRsA5Hta9wm0bBdA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Generate answers using 4o

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVtjAv87FxXtEsgloFeiahnE38zdJicGGsRXZibBvTNm2d8oicXkN6dclaoaiaZTq9gwumh2P6FwDA2Pw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The code I used: 2.generateanswer.py

```
import openai
import json
import re
import os  # Added to use environment variables

# Configure Azure OpenAI API key and endpoint
openai.api_type = "azure"
openai.api_base = "https://aoai*.azure.com/"
openai.api_version = "2024-02-15-preview"
openai.api_key ="*"

def generate_answer_with_aoai(question):
    print(f"Generating answer for question: {question[:50]}...")  # Print first 50 chars of the question
    response = openai.ChatCompletion.create(
        engine="gpt-4o-2",  # Using GPT-4 model
        messages=[
            {"role": "system", "content": "You are this persona: Programmer, Answer the following question."},
            {"role": "user", "content": question}
        ],
        temperature=0.7,
        max_tokens=1024,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0
    )
    answer = response.choices[0].message['content'].strip()

    # Use regular expression to remove sentences containing "a question", including newlines and double quotes
    pattern = r'\b[^.]*a question[^.]*[\.\n]*"'
    answer = re.sub(pattern, '', answer, flags=re.IGNORECASE).strip()

    print(f"Generated answer: {answer[:50]}...")  # Print first 50 chars of the answer
    return answer

def process_json_file(input_file, output_file, max_questions=50):
    print(f"Reading input file: {input_file}")
    # Read the input JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Create a list to store generated results
    results = []
    question_count = 0

    # Iterate through each conversation and generate answers
    for i, conversation in enumerate(data):
        for j, message in enumerate(conversation):
            if message['role'] == 'user':
                question = message['content']
                answer = generate_answer_with_aoai(question)

                # Add the result to the list
                results.append({
                    "question": question,
                    "answer": answer
                })
                print(f"Processed conversation {i+1}, message {j+1}")

                question_count += 1
                if question_count >= max_questions:
                    print(f"Reached the maximum number of questions: {max_questions}")
                    break
        if question_count >= max_questions:
            break

    # Save the results as a JSONL format file
    print(f"Writing output file: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        for result in results:
            json.dump(result, f, ensure_ascii=False)
            f.write('\n')
    print("Processing complete.")

def process_jsonl_file(input_file, output_file, max_questions=50):
    print(f"Reading input file: {input_file}")
    # Read the input JSONL file
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Create a list to store generated results
    results = []
    question_count = 0

    # Iterate through each line and generate answers
    for line in lines:
        if question_count >= max_questions:
            print(f"Reached the maximum number of questions: {max_questions}")
            break

        data = json.loads(line)
        if 'answer' in data:
            question = data['answer']
            answer = generate_answer_with_aoai(question)

            # Add the result to the list
            results.append({
                "prompt": question,
                "completion": answer
            })
            print(f"Processed question {question_count + 1}")

            question_count += 1
        else:
            print(f"Skipping line without 'answer' field: {line}")

    # Save the results as a JSONL format file
    print(f"Writing output file: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        for result in results:
            json.dump(result, f, ensure_ascii=False)
            f.write('\n')
    print("Processing complete.")

# Input and output file paths
input_file_1 = 'questions.json'
output_file_1 = 'answers.jsonl'
# Process the JSON file and generate answers, only process the first 50 questions
process_json_file(input_file_1, output_file_1, max_questions=300)

# Input and output file paths
input_file_2 = 'answers.jsonl'
output_file_2 = 'fine_tune_data.jsonl'
# Process the JSONL file and generate answers, only process the first 50 questions
process_jsonl_file(input_file_2, output_file_2, max_questions=300)

# Read fine_tune_data.jsonl file
with open('fine_tune_data.jsonl', 'r', encoding='utf-8') as f:
    fine_tune_data = [json.loads(line) for line in f]

# Read answers.jsonl file
with open('answers.jsonl', 'r', encoding='utf-8') as f:
    answers_data = [json.loads(line) for line in f]

# Generate answers and save to final-sft.jsonl file
with open('final-sft.jsonl', 'w', encoding='utf-8') as f:
    for answer_obj in answers_data:
        question = answer_obj['answer']

        # Use Azure OpenAI service to generate the answer
        response = openai.ChatCompletion.create(
            engine="gpt-4o-2",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=150,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0
        )
        answer = response.choices[0].message['content'].strip()

        # If the answer is the default assistant's greeting, skip it
        if answer == "Hello! How can I assist you today?":
            print(f"Skipping question due to undesired response: {question}")
            continue  # Skip this entry

        # Build new JSON object
        new_obj = {
            "prompt": question,
            "completion": answer
        }
        # Write to final-sft.jsonl file
        f.write(json.dumps(new_obj, ensure_ascii=False) + '\n')

print("Generated file saved as final-sft.jsonl")
```

## Step 3: Generate training data in a format that supports AOAI fine-tuning.

According to the requirements of AOAI fine-tuning corpora, generate JSONL files that can be directly used for fine-tuning.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXVtjAv87FxXtEsgloFeiahnpFib79mfQcYQibgSmOCbpSLncC58DPib8RZvvCkib37ajAVfUO76C0fVLA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

The code I used:

```
import json

# 定义输入和输出文件路径
input_file = 'final-sft.jsonl'
output_file = 'aoai-final-sft.jsonl'

try:
    # 打开输入和输出文件
    with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', encoding='utf-8') as outfile:
        total_lines = sum(1 for _ in infile)  # 计算总行数
        infile.seek(0)  # 重置文件指针到开头

        for i, line in enumerate(infile, start=1):
            # 读取每一行并解析为JSON对象
            data = json.loads(line)

            # 创建微调格式的消息列表
            messages = [
                {"role": "system", "content": "You are a professional and friendly programmer."},
                {"role": "user", "content": data["prompt"]},
                {"role": "assistant", "content": data["completion"]}
            ]

            # 将消息列表写入输出文件
            json.dump({"messages": messages}, outfile, ensure_ascii=False)
            outfile.write('\n')

            # 显示处理进度
            print(f"Processed {i}/{total_lines} lines")

    print(f"转换完成，输出文件为: {output_file}")

except FileNotFoundError:
    print(f"文件 {input_file} 未找到，请检查文件路径。")
except json.JSONDecodeError:
    print("JSON 解码错误，请检查输入文件格式。")
except Exception as e:
    print(f"发生错误: {e}")
```

## Step 4: AOAI SFT Best Practices

In this step, I use the file `aoai-final-sft.jsonl` generated in Step 3 to fine-tune AOAI GPT-3.5. During the fine-tuning process, I adjust training parameters and datasets to significantly improve the fine-tuning results. 

The comparison of the effects is as follows:

### Before Optimization

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbg7CrdYLajdp1p2Ez5Tvjy7BgGA6QXhK9W846P5HZIic1lKoQ7U6oF8PUOgsmLNGRzSDSmOYWh7g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbg7CrdYLajdp1p2Ez5TvjQiaxuAlQONWrJbByd0MD1pr02jjfy3s7EWUicRuWSacwuZHHfictcRicSw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### After Optimization

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbg7CrdYLajdp1p2Ez5Tvj1JUzRgpIBp7mPJHicKLbNF9ErIGhfAWVRSibXDne328IpnvTZeJ3dxnw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVbg7CrdYLajdp1p2Ez5Tvj5IV9E9QW4YooLMq8VfNAX95oe8icBShx1Kvcp9BBdHMqPkef1UnJbSw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### Things I Did During Optimization

The fluctuation of the loss function was mainly resolved by adjusting the batch size. Overfitting was primarily addressed by increasing the size of the training dataset. Through three rounds of optimization, a better fine-tuning effect was achieved.

### First SFT.

```
Number of epochs: 1
Batch size: 1
Learning rate multiplier: 1
100 Training data
```

### Second SFT.

```
Number of epochs: 3
Batch size: 1
Learning rate multiplier: 1
100 Training data
```

### Third SFT

```
Number of epochs: 5
Batch size: 12
Learning rate multiplier: 1
500 Training data
```



## Test results with same prompt

### Before SFT：

```
What are the key considerations when selecting a microcontroller for an embedded system in terms of power consumption, processing power, and peripheral support?

```

```
When selecting a microcontroller for an embedded system, there are several key considerations to keep in mind in terms of power consumption, processing power, and peripheral support. These considerations include:

Power Consumption: Power consumption is a critical factor, especially for battery-powered or energy-efficient devices. Look for microcontrollers with low power modes, sleep modes, and efficient power management features to minimize power consumption during idle or low activity periods.
Processing Power: The processing power of the microcontroller determines its ability to handle complex tasks and execute instructions quickly. Consider the required computational capabilities for your application and choose a microcontroller with an appropriate clock speed, number of cores, and performance-enhancing features like hardware accelerators or DSP capabilities.
Peripheral Support: Peripheral support is crucial as it determines the microcontroller's ability to interface with external devices and sensors. Consider the required peripherals for your application, such as UART, SPI, I2C, USB, Ethernet, ADC, PWM, etc. Ensure that the microcontroller has sufficient and compatible peripheral support to meet your system's requirements.
Memory: The amount of memory available on the microcontroller is essential for storing program code, data, and variables. Consider the size of your application and the required memory for efficient execution. Look for microcontrollers with sufficient Flash memory for program storage and RAM for data storage.
Development Tools and Ecosystem: Consider the availability and quality of development tools, software libraries, and community support for the microcontroller. A well-supported microcontroller with a robust ecosystem can significantly ease the development process and provide access to a wide range of resources and expertise.
Cost: Cost is an important consideration, especially for mass production or cost-sensitive projects. Evaluate the cost of the microcontroller, associated development tools, and any additional components required for your application.
Longevity and Availability: Consider the longevity and availability of the microcontroller. Ensure that the microcontroller is not at the end of its lifecycle and will be available for the desired duration of your product's lifecycle. This helps in avoiding potential issues with component availability and long-term support.

By considering these factors, you can select a microcontroller that best suits your embedded system's power consumption, processing power, and peripheral support requirements.
```

### After SFT：

```
What are the key considerations when selecting a microcontroller for an embedded system in terms of power consumption, processing power, and peripheral support?
```

```
Power Consumption:
Operating Voltage: Choose a microcontroller that operates at a voltage suitable for your application. Lower voltage typically means lower power consumption.
Sleep Modes: Look for microcontrollers with multiple sleep modes to minimize power consumption during idle periods.
Dynamic Power Management: Some microcontrollers have features like clock gating, which can reduce power consumption by turning off unused peripherals.
Low-Power Modes: Some microcontrollers have specific low-power modes designed for specific tasks, such as low-power timers or low-power analog-to-digital converters (ADCs).
Processing Power:
Clock Speed: Consider the clock speed of the microcontroller. A higher clock speed generally means more processing power, but it also typically results in higher power consumption.
Core Architecture: Different core architectures (e.g., ARM, AVR, PIC) have different performance characteristics. Choose one that best suits your processing needs.
Instruction Set: Some microcontrollers have specialized instruction sets for specific tasks, such as digital signal processing (DSP) or floating-point arithmetic.
```

### Training data

```
{"messages": [{"role": "system", "content": "You are a professional and friendly programmer."}, {"role": "user", "content": "What are the key considerations when selecting a microcontroller for an embedded system in terms of power consumption, processing power, and peripheral support?"}, {"role": "assistant", "content": "When selecting a microcontroller for an embedded system, several key considerations need to be taken into account to ensure optimal performance, efficiency, and compatibility with the intended application. Here are the primary factors to consider:\n\n### 1. Power Consumption\n- **Operating Voltage:** Choose a microcontroller that operates at a suitable voltage level for your application. Low-voltage microcontrollers are beneficial for battery-powered devices.\n- **Active and Sleep Modes:** Evaluate the current consumption in active mode as well as in various low-power or sleep modes. Microcontrollers with efficient power management features can significantly extend battery life.\n- **Power-Saving Features:** Look for features like dynamic voltage scaling, clock gating, and low-power peripherals, which can help reduce power consumption.\n\n###"}]}
```

### Result analyze

To evaluate the consistency between the SFT model(The second model) and the training set, we can analyze it from the following aspects:

1. Structure
Both the training set and the second model's response use a hierarchical structure, discussing the two main aspects of "Power Consumption" and "Processing Power" respectively.

2. Content
Power Consumption
Operating Voltage: The training set mentions "Operating Voltage," and the second model also mentions this.
Sleep Modes: The training set mentions "Active and Sleep Modes," and the second model mentions "Sleep Modes."
Power-Saving Features: The training set mentions "Power-Saving Features," and the second model mentions "Dynamic Power Management" and "Low-Power Modes," which fall under power-saving features.
Processing Power
Clock Speed: The training set does not explicitly mention "Clock Speed," but this is an important aspect of processing power, and the second model mentions it.
Core Architecture: The training set does not mention this, but it is another important aspect of processing power, and the second model mentions it.
Instruction Set: The training set does not mention this, but it is a specific aspect of processing power, and the second model mentions it.
3. Level of Detail
The second model's response is comparable in detail to the training set. Although it adds some specifics in the "Processing Power" section that are not mentioned in the training set (such as "Core Architecture" and "Instruction Set"), these details are reasonable and relevant.

4. Language Style
The language style of the second model is consistent with the training set, both being professional and friendly.

Consistency Score
Based on the above analysis, the consistency between the second model and the training set can be considered quite high. The specific scores can be as follows:

- Structural Consistency: 100%

- Content Consistency: 90% (because it adds some details in the "Processing Power" section that are not mentioned in the training set)

- Level of Detail: 95% (comparable to the training set)

- Language Style: 100%

  

### Training time reference

4o SFT，229,000 tokens，batchzize=12，41 minutes：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/4-Steps-of-AOAI-E2E-Fine-Tuning-best-practice/images/1.png)

#### Summary

The consistency score between the second model and the training set is approximately 95%. It is highly consistent with the training set in terms of structure, content, and language style, with only some additional details in the "Processing Power" section, but these details are reasonable and relevant.
