# Using LLMs as Judges: Evaluating Large Language Models with Large Language Models

*An effective evaluation method providing rapid feedback and monitoring*

In today's rapidly evolving field of artificial intelligence, evaluating large language models (LLMs) is becoming increasingly complex. These models possess a wide range of capabilities, making it challenging to establish clear and simple criteria for judging their generated responses. For instance, an LLM's answer might lack context, contain repetitions, grammatical errors, be overly verbose, or sometimes even be illogical.

To address this issue, an effective approach is to have large language models evaluate other large language models, known as the "LLM as Judge" method. This approach has already been applied in popular benchmarks like Chatbot Arena. By allowing one LLM to score or rank the responses of other models, we can reduce human involvement while obtaining valuable feedback. Since this process is automated, it enables us to evaluate and improve these models more easily without heavily relying on human reviewers. Additionally, compared to traditional public benchmarks (like MMLU) that the models might have already seen during training, using LLMs as judges is also an excellent alternative.

**Overview of the LLM as Judge Method**

The LLM as Judge method primarily involves using an external large language model to review and evaluate the outputs of other models based on predefined criteria. For example, when assessing a chatbot's reply, the judge model can evaluate aspects like politeness, bias, tone, sentiment, and accuracy.

**Different Implementations of the Judge Model**

- **Pairwise Comparison**: The judge model compares two responses to the same question or prompt and selects the better one. This method is particularly useful during model development, allowing for comparisons between different versions of models or testing various prompts to identify the most effective choices.

- **Single Evaluation**: The judge model evaluates a single response based on specific quality metrics (such as tone or clarity) without requiring additional contextual information. This reference-free evaluation is suitable for situations where the quality of a response needs to be assessed without a standard answer.

- **Reference-Based Evaluation**: The model's response is compared with a known reference answer (e.g., a human-written answer). This is especially useful in applications like summarization, where it's important to ensure the response accurately reflects the source material.

  **Designing an Effective Judge Model**

  To create an efficient LLM judge model, the following steps should be followed:

1. **Clarify Evaluation Criteria**: Define clear evaluation standards, such as accuracy, clarity, or politeness. The criteria should be simple and specific, ensuring the judge model focuses on a particular aspect of quality each time.

2. **Prepare a Labeled Dataset**: Build a labeled dataset as the foundation for evaluation, which helps measure how well the judge model's assessments match the expected results.

3. **Design Evaluation Prompts**: Craft clear prompts for the judge model, providing explicit instructions. The prompts should include direct scoring options, like binary choices (e.g., "Helpful" vs. "Unhelpful"), to improve consistency and accuracy in evaluations. Sometimes, you can also ask the judge model to explain its decisions to further enhance evaluation quality.

4. **Test and Optimize**: Test the judge model's performance on the labeled dataset, using metrics like precision and recall for evaluation. If the results are not as expected, you may need to adjust the prompts or model parameters.

5. **Expert Involvement**: Involve domain experts during prompt design and optimization to improve the relevance and accuracy of evaluations, meeting the specific needs of the product.

   **Advantages and Limitations of the Judge Model**

   **Advantages:**

- **High Flexibility**: The judge model can be adjusted according to different evaluation criteria and needs, suitable for real-time monitoring, fine-tuning new models, parameter optimization, and other scenarios.

- **Saves Human Resources**: The automated evaluation process reduces reliance on human reviewers, speeding up model development and iteration.

  **Limitations:**

- **Potential Bias**: The judge model may carry biases from its training data, and if the instructions are not clear enough, it could lead to inconsistent evaluation results.

- **Privacy Concerns**: Using third-party LLM APIs for evaluation may raise data privacy and security concerns, especially when handling sensitive information.

- **Need for Supplementary Methods**: The judge model's evaluation results are best combined with human annotations, user feedback, traditional machine learning models, and rule-based checks to achieve a more comprehensive quality assessment.

  **Considerations:**

- **Transparency Requirements**: When writing scientific papers that include LLM evaluations, unless the judge model is fully transparent (with all information about its pre-training data, training methods, and model architecture publicly disclosed), LLMs should not be used as judges. This helps assess potential overlaps in training data, architecture, or vocabulary between the judge model and the evaluated models, thereby avoiding biases in evaluation results.

## Code
I wrote a program to compare the performance of two models on a dataset and had GPT-4 evaluate them. Let's look at the results first. The code will be pushed to the corresponding GitHub repository later.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWic4X8iadAZcHdjIK2rNOfToRDhInZRzNoXFV1UdsicicEKQLicTnia2IfScGqFNRGbXnVn4PiaAribrOAJw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWic4X8iadAZcHdjIK2rNOfTogPDj7HtkCSr8JewUwT1npicDniabhpYGaPxCczVady6cwGeaaEU6HqFA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

```
# Import libraries  
from datasets import load_dataset    
from vllm import LLM, SamplingParams    
import openai    
import gc    
import torch    
import matplotlib.pyplot as plt    
import asyncio    
import aiohttp    
import nest_asyncio    
import matplotlib  

# Fix event loop issues  
nest_asyncio.apply()    

# Set default font family for Matplotlib  
matplotlib.rcParams['font.family'] = 'DejaVu Sans'  # Or another available font  

# Set up Azure OpenAI API configuration  
openai.api_type = "azure"    
openai.api_base = "https://***.openai.azure.com/"  # Replace with your Azure OpenAI resource name    
openai.api_version = "2024-02-15-preview"          # Use the API version that supports GPT-4    
openai.api_key = "***"            # Replace with your Azure OpenAI API key    

# Define model names  
model_a = "HuggingFaceTB/SmolLM-135M-Instruct"    
model_b = "microsoft/Phi-3.5-mini-instruct"    
# The evaluation model is Azure OpenAI's GPT-4    

# Load dataset  
dataset = load_dataset("fka/awesome-chatgpt-prompts", split="train")    
prompts = dataset["prompt"]    

# Double the number of prompts used, if possible  
total_prompts = len(prompts)  
desired_prompts = total_prompts * 2  # Attempt to double  
prompts = prompts[:desired_prompts]  

print(f"Using {len(prompts)} prompts for evaluation.")  

# Use a small amount of data for testing (optional)  
# prompts = prompts[:10]  # Uncomment to use the first 10 prompts for testing    

# Define sampling parameters  
sampling_params = SamplingParams(temperature=0.0, top_p=0.95, max_tokens=500)    

def generate_model_outputs(model_name, prompts):    
    """Generate outputs from the specified model."""    
    llm = LLM(model=model_name, gpu_memory_utilization=0.2,max_model_len=1024)    
    outputs = llm.generate(prompts, sampling_params)    
    completions = [output.outputs[0].text.strip() for output in outputs]    
    del llm    
    torch.cuda.empty_cache()    
    gc.collect()    
    return completions    

# Generate outputs for Model A and Model B  
model_a_completions = generate_model_outputs(model_a, prompts)    
model_b_completions = generate_model_outputs(model_b, prompts)    

# Define evaluation template  
DEFAULT_PAIRWISE_SYSTEM_PROMPT = """I need to create a ranking list for various large language models. I will provide you with prompts and corresponding outputs from these models. Your task is to evaluate these responses and choose the model that produces the best output from a human perspective.  

## Instruction  

{prompt}  

## Model Outputs  

Below are the outputs from the models, each labeled with a specific model identifier.  

Output from Model 0:    
{response0}  

Output from Model 1:    
{response1}  

## Task  

Please evaluate these two models based on the quality and relevance of the results, and choose the model that generates the best result. Please reply only with the identifier of the best model ("0" or "1"), nothing else.  
"""    

# Prepare evaluation prompts  
judge_prompts = [    
    DEFAULT_PAIRWISE_SYSTEM_PROMPT.format(prompt=prompt, response0=c0, response1=c1)    
    for prompt, c0, c1 in zip(prompts, model_a_completions, model_b_completions)    
]    

# Asynchronously get evaluation results  
async def get_judgments(prompts):    
    headers = {    
        "api-key": openai.api_key,    
        "Content-Type": "application/json"    
    }    
    async with aiohttp.ClientSession() as session:    
        tasks = []    
        for prompt in prompts:    
            messages = [    
                {"role": "system", "content": "You are an expert language model evaluator."},    
                {"role": "user", "content": prompt}    
            ]    
            task = asyncio.ensure_future(    
                call_openai_api(session, headers, messages)    
            )    
            tasks.append(task)    
        responses = await asyncio.gather(*tasks)    
    return responses    

async def call_openai_api(session, headers, messages):    
    try:    
        async with session.post(    
            url=f"{openai.api_base}openai/deployments/gpt-4/chat/completions?api-version={openai.api_version}",    
            headers=headers,    
            json={    
                "messages": messages,    
                "temperature": 0.0,    
                "max_tokens": 1,    
            },    
            timeout=30    
        ) as resp:    
            result = await resp.json()    
            return result['choices'][0]['message']['content'].strip()    
    except Exception as e:    
        return "-1"  # Return '-1' if an exception occurs    

# Get evaluation results  
ranks = asyncio.run(get_judgments(judge_prompts))    

# Process evaluation results  
model_a_wins = ranks.count("0")    
model_b_wins = ranks.count("1")    
valid_judgments = [r for r in ranks if r in ["0", "1"]]    
total_judgments = len(valid_judgments)    

print(f"Model A wins: {model_a_wins}")    
print(f"Model B wins: {model_b_wins}")    
print(f"Total valid evaluations: {total_judgments}")    
print(f"Model A win rate: {model_a_wins / total_judgments * 100:.2f}%")    
print(f"Model B win rate: {model_b_wins / total_judgments * 100:.2f}%")    

# Visualize win rates  
labels = ['Model A', 'Model B']    
wins = [model_a_wins, model_b_wins]    
win_rates = [win / total_judgments * 100 for win in wins]    

plt.bar(labels, win_rates, color=['blue', 'orange'])    
plt.xlabel('Model')    
plt.ylabel('Win Rate (%)')    
plt.title('Model Comparison: Win Rates')    
plt.show()    
```

