# Perplexity-test

Perplexity is one of the key metrics for evaluating large language models (LLMs). It measures the model's ability to predict a given sequence. Mathematically, perplexity is the exponentiated average of the negative log-likelihood. During training, the objective of an LLM is to minimize this negative log-likelihood, making perplexity an intuitive choice for assessing LLM performance. It is important to note that lower perplexity is better.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nXnMW358QMMjsZA9BGOzyIaibP2yOlPDPvUBQDRvrBRTUM6sft4FMiccHWKaG7sg96lOpXxARf8Z1ibg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

### 1. Probability of Predicting a Word**:

- The model predicts the probability of the next word based on all the words seen so far. For instance, if you have "The cat is sleeping," the model now predicts whether the next word is "." or some other word.
- This probability is denoted as ( p_{\theta}(x_i | x_{<i}) ), which represents the probability of predicting the current word given all the previous words.

### 2. **Taking the Logarithm ((\log))**:

- Using raw probabilities for calculations can be inconvenient, so we take the logarithm (log) of these probabilities. The advantage of using the logarithm is that it converts multiplication into addition, making the calculations simpler.

### 3. **Calculating the Average**:

- Since we have multiple words, we sum the log probabilities of all the words and then divide by the total number of words ( t ). This gives us an average value.

### 4. **Taking the Negative**:

- Logs are typically negative, so we take the negative of this value to make the result positive.

### 5. **Exponentiating ((\exp))**:

- In the final step, we use the exponential function ((\exp)) to convert the negative log average into perplexity. This step converts the log value back to the original probability scale, making it more intuitive.

### Summary:

- First, we evaluate the model's ability to predict the next word at each position (represented by the probability).
- We then take the logarithm of these probabilities, calculate their average, take the negative of this average, and finally use the exponential function to convert it back.
- The resulting number is the perplexity. A lower perplexity indicates better model performance and less "perplexity." A high perplexity means the model performs poorly and frequently makes incorrect predictions. We can test the same model before and after fine-tuning or quantization to measure the effectiveness of fine-tuning and the accuracy loss due to quantization.

### Can Perplexity Be Used to Compare Different LLMs?

No.

1. **Different Tokenization Methods**: Different models use different tokenizers that produce varying numbers of tokens. If one model's tokenizer generates more tokens, ( N ) will be higher, leading to a lower perplexity.
2. **Different Vocabulary Sizes**: Perplexity is calculated based on the entire vocabulary. The larger the vocabulary, the harder it is to find the most likely word. For example, comparing a model with a vocabulary of two words to one with 100,000 words, the latter's task is evidently more challenging. However, this doesn't mean its performance is worse.
3. **Different Maximum Context Lengths**: Different models have different maximum context lengths, which also affects the perplexity calculation. For instance, if one model has a context length of 8192 tokens and another has only 4096 tokens, the former can calculate perplexity over a longer sequence, while the latter needs to approximate using methods like sliding windows.



## Perplexity-test Code

```
import torch, gc
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer
)
def get_ppl(model_name, example):
  tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
  model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map={"": 0}, torch_dtype=torch.float16
  )
  inputs = tokenizer(example, return_tensors="pt").to("cuda")
  print(inputs)
  input_ids = inputs["input_ids"]
  tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
  print(tokens)

  target_ids = input_ids.clone()

  with torch.no_grad():
      outputs = model(input_ids, labels=target_ids)

  print("Negative log-likelihood: "+str(outputs.loss.item()))
  print("Perplexity: "+str(torch.exp(outputs.loss).item()))
  del model
  del tokenizer
  gc.collect()
  torch.cuda.empty_cache()
```

```
example = "The loss is calculated using CrossEntropyLoss which averages over valid labels."
get_ppl("meta-llama/Meta-Llama-3.1-8B", example)
```

