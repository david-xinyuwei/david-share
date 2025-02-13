# GRPO-Phi-4-Training

***Please click below pictures to see my demo video on Youtube about GRPO of Microsoft/phi-4:***
[![BitNet-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/WXjJdsV2cbU)



## Code what I used

```
from unsloth import FastLanguageModel, PatchFastRL
PatchFastRL("GRPO", FastLanguageModel)
```

```
max_seq_length = 1024
lora_rank = 16

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "microsoft/phi-4",
    max_seq_length = max_seq_length,
    load_in_4bit = True, 
    fast_inference = True, 
    max_lora_rank = lora_rank,
    gpu_memory_utilization = 0.6, 
)
```

```
model = FastLanguageModel.get_peft_model(
    model,
    r = lora_rank,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha = lora_rank,
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)
```

```
SYSTEM_PROMPT = """
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
<aha>
No no no, this is my real answer:
...
</aha>
"""
import re

def very_loose_format_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion has a specific format."""
    responses = [completion[0]["content"] for completion in completions]
    return [0.5 if "<reasoning>" in r and "</reasoning>" in r else 0.0 for r in responses]

def strict_format_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion has a specific format."""
    pattern = r"^<reasoning>.*?</reasoning>\s*<answer>.*?</answer>\s*<aha>.*?</aha>$"
    responses = [completion[0]["content"] for completion in completions]
    matches = [re.match(pattern, r) for r in responses]
    return [0.5 if match else 0.0 for match in matches]

def aha_reward_func(completions, **kwargs) -> list[float]:
    """Reward function that checks if the completion contains "aha" times, 2 for the tags, and one more, wherever it wants."""
    responses = [completion[0]["content"] for completion in completions]
    matches = [re.findall(r'\baha\b', r, re.IGNORECASE) for r in responses]
    return [0.5 if len(match) == 3 else 0.0 for match in matches]
```

```
from datasets import load_dataset
import multiprocessing
ds = load_dataset("cognitivecomputations/dolphin-r1", "reasoning-deepseek", split="train[:10000]")
ds = ds.rename_columns({'messages':'prompt'})

def process(row):
  row['prompt'][0]['content'] += '\n'+SYSTEM_PROMPT
  return row

ds= ds.map(
    process,
    num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False,
)

def tokenize_with_template(example):
    """Tokenizes input text using the chat template of the tokenizer."""
    chat_template = tokenizer.apply_chat_template(example['prompt'], tokenize=False, add_generation_prompt=True)
    tokens = tokenizer(chat_template, truncation=False, add_special_tokens=True)["input_ids"]
    return {"token_length": len(tokens)}

ds = ds.map(tokenize_with_template,
    #num_proc= multiprocessing.cpu_count(),
    load_from_cache_file=False)
ds = ds.filter(lambda example: example["token_length"] <= max_seq_length)
ds = ds.remove_columns(["token_length"])
```

```
from trl import GRPOConfig, GRPOTrainer
training_args = GRPOConfig(
    use_vllm = True, # use vLLM for fast inference!
    learning_rate = 1e-6,
    warmup_ratio = 0.1,
    lr_scheduler_type = "linear",
    optim = "paged_adamw_8bit",
    logging_steps = 5,
    bf16 = True,
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 4, # Increase to 4 for smoother training
    num_generations = 6, # Decrease if out of memory (but avoid below 4)
    max_prompt_length = 256,
    max_completion_length = 512,
    # num_train_epochs = 1, # Set to 1 for a full training run
    max_steps = 250,
    save_steps = 250,
    report_to = "none", # Can use Weights & Biases
    output_dir = "outputs",
)
```

```
trainer = GRPOTrainer(
    model = model,
    processing_class = tokenizer,
    reward_funcs = [
        aha_reward_func,
        strict_format_reward_func,
        very_loose_format_reward_func
    ],
    args = training_args,
    train_dataset = ds,
)
trainer.train()
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Deep-Learning/GRPO-Phi-4-Training/images/1.png)

```
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import torch
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/phi-4",
    device_map="cuda",
)

tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-4")
model = PeftModel.from_pretrained(model, "outputs/checkpoint-50")
```

```
SYSTEM_PROMPT = """
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
<aha>
No no no, this is my real answer:
...
</aha>
"""

messages = [{"role":"system", "content":"You are an expert who knows the location of all pandas in China."+SYSTEM_PROMPT},
    {"role": "user", "content": "Make 10 possible equations to compute the number of panda in China."},
]

seq = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(seq)

encoded_input = tokenizer(seq, return_tensors="pt").to(model.device)
outputs = model.generate(
  encoded_input['input_ids'],
  max_new_tokens=2048,
  do_sample=True,
  temperature=0.6,
  top_p=0.9,
)


response = outputs[0][encoded_input['input_ids'].shape[-1]:]
print(tokenizer.decode(response))
```

Final result:

```
<|im_start|>system<|im_sep|>You are an expert who knows the location of all pandas in China.
Respond in the following format:
<reasoning>
...
</reasoning>
<answer>
...
</answer>
<aha>
No no no, this is my real answer:
...
</aha>
<|im_end|><|im_start|>user<|im_sep|>Make 10 possible equations to compute the number of panda in China.<|im_end|><|im_start|>assistant<|im_sep|>
<reasoning>
To create equations that could theoretically compute the number of pandas in China, we need to consider various factors that might influence the panda population. These factors could include birth rates, death rates, conservation efforts, habitat changes, and more. Here are some conceptual equations:

1. **Basic Population Model**:
   \[
   P(t) = P_0 + (B - D) \times t
   \]
   Where \( P(t) \) is the population at time \( t \), \( P_0 \) is the initial population, \( B \) is the average number of births per year, and \( D \) is the average number of deaths per year.

2. **Logistic Growth Model**:
   \[
   P(t) = \frac{K}{1 + \left(\frac{K - P_0}{P_0}\right) e^{-rt}}
   \]
   Where \( K \) is the carrying capacity of the environment, \( r \) is the intrinsic growth rate, and \( e \) is the base of the natural logarithm.

3. **Conservation Impact Model**:
   \[
   P(t) = P_0 + (B - D + C) \times t
   \]
   Where \( C \) represents the net effect of conservation efforts (e.g., increased births or decreased deaths due to conservation).

4. **Habitat Change Model**:
   \[
   P(t) = P_0 + (B - D) \times t - H(t)
   \]
   Where \( H(t) \) is the negative impact on the population due to habitat loss or degradation over time.

5. **Predation and Disease Model**:
   \[
   P(t) = P_0 + (B - D - P_d - P_c) \times t
   \]
   Where \( P_d \) is the number of deaths due to disease, and \( P_c \) is the number of deaths due to predation.

6. **Migration Model**:
   \[
   P(t) = P_0 + (B - D) \times t + M(t)
   \]
   Where \( M(t) \) is the net migration (immigration minus emigration) of pandas over time.

7. **Human Impact Model**:
   \[
   P(t) = P_0 + (B - D - H_i) \times t
   \]
   Where \( H_i \) is the impact of human activities (e.g., poaching, deforestation) on the panda population.

8. **Climate Change Model**:
   \[
   P(t) = P_0 + (B - D - C_c) \times t
   \]
   Where \( C_c \) is the impact of climate change on the panda population.

9. **Genetic Diversity Model**:
   \[
   P(t) = P_0 + (B - D) \times t + G(t)
   \]
   Where \( G(t) \) is the effect of genetic diversity on population growth (e.g., increased resilience).

10. **Combined Model**:
    \[
    P(t) = P_0 + (B - D + C - H - P_d - P_c + M - H_i - C_c + G) \times t
    \]
    This equation combines multiple factors to provide a more comprehensive model.

These equations are hypothetical and would require specific data to be accurately applied.
</reasoning>

<answer>
1. \( P(t) = P_0 + (B - D) \times t \)

2. \( P(t) = \frac{K}{1 + \left(\frac{K - P_0}{P_0}\right) e^{-rt}} \)

3. \( P(t) = P_0 + (B - D + C) \times t \)

4. \( P(t) = P_0 + (B - D) \times t - H(t) \)

5. \( P(t) = P_0 + (B - D - P_d - P_c) \times t \)

6. \( P(t) = P_0 + (B - D) \times t + M(t) \)

7. \( P(t) = P_0 + (B - D - H_i) \times t \)

8. \( P(t) = P_0 + (B - D - C_c) \times t \)

9. \( P(t) = P_0 + (B - D) \times t + G(t) \)

10. \( P(t) = P_0 + (B - D + C - H - P_d - P_c + M - H_i - C_c + G) \times t \)
</answer>

<aha>
No no no, this is my real answer: The exact number of pandas in China is determined through surveys and research conducted by wildlife authorities and conservation organizations. These numbers are updated periodically and are based on field data rather than equations.
</aha><|im_end|>
```



## Overview of the GRPO Method

### 1. Core Concepts of GRPO


The main goal of GRPO (Generative Relative Policy Optimization) is to optimize a model's policy through an online, self-generated approach, enabling it to improve performance without relying heavily on large amounts of external data or human feedback. Its core concepts include:

- **Online Generation and Learning**: During training, the model generates samples on its own and learns from them immediately.
- **Relative Advantage Evaluation**: By computing the relative advantage of generated samples, the model is guided towards optimal optimization directions.
- **Policy Regularization**: By constraining the difference between the new policy and the reference policy, the model is prevented from deviating from its original knowledge structure.

### 2. Workflow of GRPO

#### **Step 1: Sample Generation**


For each input (such as a prompt or question), the model generates multiple possible outputs (called "completions"). For example, given a question, the model might generate 8 different answers.

#### **Step 2: Reward Evaluation**


For each generated output, a reward function is defined to assess its quality. The reward function can be designed according to task requirements. For instance, the score can be based on the output's format, content accuracy, etc.

#### **Step 3: Calculating Relative Advantage**


For each generated output, calculate its relative advantage (Advantage) compared to other outputs in the same group, using the following formula:

```
A_i = (r_i - r̄) / σ(r)  
```


Where:

- `A_i`: Relative advantage of the `i`-th output.

- `r_i`: Reward value of the `i`-th output.

- `r̄`: Mean reward value of all outputs in the group.

- `σ(r)`: Standard deviation of the reward values in the group.

  **Example:**

  Suppose the model generates 4 outputs with reward values `[0.6, 0.8, 0.4, 0.7]`.

  Calculate the mean reward value:

```
r̄ = (0.6 + 0.8 + 0.4 + 0.7) / 4 = 0.625  
```


Calculate the standard deviation of the reward values:

```
σ(r) = sqrt( [(0.6 - 0.625)² + (0.8 - 0.625)² + (0.4 - 0.625)² + (0.7 - 0.625)²] / 4 )  
     ≈ sqrt( [0.000625 + 0.030625 + 0.050625 + 0.005625] / 4 )  
     ≈ sqrt(0.0875 / 4) ≈ 0.148  
```


Calculate the relative advantage for each output:

```
A_1 = (0.6 - 0.625) / 0.148 ≈ -0.169  
A_2 = (0.8 - 0.625) / 0.148 ≈ 1.182  
A_3 = (0.4 - 0.625) / 0.148 ≈ -1.519  
A_4 = (0.7 - 0.625) / 0.148 ≈ 0.507  
```


The relative advantage reflects how each output performs relative to the average level. Positive values indicate above-average performance, while negative values indicate below-average performance.

#### **Step 4: Policy Update**


Use the relative advantage to update the model's policy. To prevent the model's policy from deviating too much from the original policy, KL divergence is introduced as a regularization term. The loss function is defined as:

```
L = - E[ A_i * log π_θ(a_i | x_i) ] + β * D_KL [ π_θ || π_ref ]  
```


Where:

- `L`: Loss function.

- `E`: Expectation over all samples.

- `A_i`: Relative advantage of the `i`-th sample.

- `π_θ(a_i | x_i)`: Probability of the model generating output `a_i` given input `x_i` under policy `π_θ`.

- `β`: Regularization coefficient controlling the strength of the policy update.

- `D_KL [ π_θ || π_ref ]`: KL divergence between the new policy `π_θ` and the reference policy `π_ref`.

  **Explanation:**

- **First Term**: Encourages the model to assign higher probabilities to outputs with higher relative advantage by weighting the log probabilities with `A_i`.

- **Second Term**: Uses KL divergence to limit the difference between the new policy and the reference policy, preventing the model from forgetting prior knowledge.

### II. Advantages of GRPO

#### 1. Reducing Dependence on External Data

- **Self-Generated Training Data**: The model learns by generating samples online, reducing the need for large-scale annotated data.
- **Lowering Human Costs**: Eliminates the need for extensive human feedback or annotations, reducing training costs.

#### 2. Enhancing Training Efficiency

- **Fast Convergence**: By evaluating relative advantages, the model can more effectively identify and learn high-quality policies.
- **Policy Stability**: The introduction of policy regularization prevents drastic changes in the model's policy, ensuring a stable training process.

#### V. Key Technical Analysis

##### 1. Calculation and Application of Relative Advantage


Calculating the relative advantage allows the model to identify which outputs are better within a group of generated outputs, focusing on learning these high-quality outputs.

**Example:**

Suppose in one training step, the model generates multiple outputs for an input:

- **Output A**: Reward value 0.9

- **Output B**: Reward value 0.5

- **Output C**: Reward value 0.7

  Calculate the mean reward value:

```
r̄ = (0.9 + 0.5 + 0.7) / 3 ≈ 0.7  
```


Calculate the standard deviation:

```
σ(r) = sqrt( [(0.9 - 0.7)² + (0.5 - 0.7)² + (0.7 - 0.7)²] / 3 )  
     = sqrt( [0.04 + 0.04 + 0] / 3 ) ≈ 0.163  
```


Calculate the relative advantage:

```
A_A = (0.9 - 0.7) / 0.163 ≈ 1.225  
A_B = (0.5 - 0.7) / 0.163 ≈ -1.225  
A_C = (0.7 - 0.7) / 0.163 = 0  
```


In this way, the model knows that Output A is above average and should be given more weight during policy updates.

##### 2. Importance of Policy Regularization


Introducing KL divergence as a regularization term prevents the model from deviating too much from the original policy during updates, avoiding overfitting or forgetting previously learned knowledge.

**Explanation:**

- If the model focuses too much on current high-reward outputs, it may ignore diversity, causing the model to become monotonous.
- KL divergence limits the difference between the new policy and the reference policy, ensuring the model maintains a certain level of stability while gradually improving.

##### III. Design of the Reward Function


The design of the reward function is crucial to the success of GRPO. A good reward function should meet the following criteria:

- **Closely Related to Task Objectives**: Ensure that the reward values genuinely reflect the quality of the outputs.

- **Simple Calculation**: Avoid overly complex computations to save training time.

- **Discriminative**: Provide significantly different rewards to high-quality and low-quality outputs.

  **Example: Reward Function with Format Constraints**

  Suppose we want the model's output to contain a specific format, such as:

```
<reasoning>  
...  
</reasoning>  
<answer>  
...  
</answer>  
<aha>  
...  
</aha>  
```


We can design a reward function that checks whether the model's output conforms to the above format.

**Reward Function Definition:**

- If the output strictly follows the format, the reward value is **1**.

- If the output partially follows the format, the reward value is **0.5**.

- If the output does not follow the format, the reward value is **0**.

  **Application:**

  Through continuous attempts, the model discovers that outputs conforming to the format receive higher rewards, thus tending to generate content that matches the format.

#### IV. Challenges and Solutions in Practice

##### 1. Difficulty in Designing the Reward Function


**Challenge**: Designing a reward function that effectively guides the model without introducing bias is not easy.

**Solution**:

- **Iterative Optimization**: Start with a simple reward function and gradually adjust and refine it based on training results.
- **Multidimensional Consideration**: Combine multiple metrics, such as format correctness, content accuracy, and language fluency, to construct a comprehensive reward function.

##### 2. Stability of Model Training


**Challenge**: During training, the model may exhibit instability, such as oscillations or divergence.

**Solution**:

- **Adjust Hyperparameters**: Appropriately adjust the learning rate, regularization coefficient `β`, etc., to find the optimal balance point.
- **Increase Data Diversity**: Ensure diversity in inputs to prevent the model from overfitting to specific patterns.

##### 3. Resource Limitations


**Challenge**: Large models still require significant GPU memory resources, and how to train on consumer-grade GPUs remains a problem.

**Solution**:

- **Model Quantization**: Quantize model parameters to lower precision (e.g., 8-bit or 4-bit) to reduce memory usage.
- **Use Parameter-Efficient Fine-Tuning Techniques**: Such as LoRA (Low-Rank Adaptation), which fine-tunes only a portion of the parameters, reducing computational and storage demands.

### V. Future Outlook


The GRPO method provides a new approach for training large language models under limited resources. Future research directions include:

- **Automated Reward Function Generation**: Utilize machine learning techniques to automatically design and optimize reward functions, reducing human intervention.

- **Integration with Other Optimization Methods**: Combine GRPO with reinforcement learning, meta-learning, and other methods to further enhance model performance.

- **Expanding Application Domains**: Explore the application of GRPO in other types of models, such as image and speech models.

  The advantage of GRPO lies in reducing dependence on expensive hardware and large amounts of human-annotated data, allowing more researchers and developers to participate in the training and application of large models. Through reasonable reward function design and policy regularization, models can achieve desired performance under limited resources.



***Refer to: https://kaitchup.substack.com/p/grpo-train-llms-with-deepseek-r1s***