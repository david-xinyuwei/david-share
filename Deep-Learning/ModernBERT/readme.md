# ModernBERT Model

A new encoder-only small model has been released and has gained high download volumes. Here is the link:  https://huggingface.co/answerdotai/ModernBERT-large  I tried it out, and it performs well in simple Q&A, classification, and similarity comparison tasks. 

 ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVZbeZF4zhUdVdhBRUiaPcReBxZhG6LEb8KcEmMKAsO7ZrpMFM9XVcxm1MCSkZrBLxbYgOGFRAyR2g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Inference task test

```
(ModernBERT-large) root@davidgpt:~# cat 1.py
from transformers import AutoTokenizer, AutoModelForMaskedLM

model_id = "answerdotai/ModernBERT-base"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForMaskedLM.from_pretrained(model_id)

#text = "The Chairman of China is [MASK]."
text = "The capital of China is [MASK]."
#text = "US is [MASK]."
inputs = tokenizer(text, return_tensors="pt")
outputs = model(**inputs)

# To get predictions for the mask:
masked_index = inputs["input_ids"][0].tolist().index(tokenizer.mask_token_id)
predicted_token_id = outputs.logits[0, masked_index].argmax(axis=-1)
predicted_token = tokenizer.decode(predicted_token_id)
print("Predicted token:", predicted_token)
# Predicted token:  Paris
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVZbeZF4zhUdVdhBRUiaPcRe95t2icWwBDfyibrzicLr06DLvBxZaB4Z9RYDwvlic7daFoiaBBxeD9qA7eg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

```
(ModernBERT-large) root@davidgpt:~# cat 2.py
from transformers import AutoTokenizer, AutoModelForMaskedLM
import torch

# 加载模型和分词器
model_id = "answerdotai/ModernBERT-base"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForMaskedLM.from_pretrained(model_id)

# 定义待分析的句子
sentences = [
    "I absolutely love this product!",
    "This is the worst experience I've ever had.",
    "The movie was okay, not great but not terrible either.",
    "I'm extremely happy with the service."
]

# 定义情感标签
labels = ["bad", "good", "great"]

# 获取每个标签的 token id
label_ids = tokenizer.convert_tokens_to_ids(labels)

# 对每个句子进行预测
for sentence in sentences:
    # 构建带有 [MASK] 的句子
    input_text = f"{sentence} Overall, it was a [MASK] experience."
    inputs = tokenizer(input_text, return_tensors="pt")
    mask_token_index = torch.where(inputs["input_ids"][0] == tokenizer.mask_token_id)[0]

    # 获取模型输出
    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    mask_token_logits = logits[0, mask_token_index, :]

    # 从候选标签中选取得分最高的
    label_scores = mask_token_logits[:, label_ids]
    predicted_index = torch.argmax(label_scores, dim=1)
    predicted_token = labels[predicted_index]

    print(f"句子：{sentence}")
    print(f"预测情感：{predicted_token}\n")
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVZbeZF4zhUdVdhBRUiaPcRe4rPyreyXeSCStLhXUv6roHJPh65sCicR4arjMG5ia6pKSqed1mguG2MQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

```
(ModernBERT-large) root@davidgpt:~# cat 3.py
from transformers import AutoTokenizer, AutoModelForMaskedLM
import torch

# 加载模型和分词器
model_id = "answerdotai/ModernBERT-base"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForMaskedLM.from_pretrained(model_id)

# 定义上下文和问题
context = "Albert Einstein was a theoretical physicist who developed the theory of relativity. He was born in Ulm, Germany in 1879."
question = "Where was Albert Einstein born?"

# 将问题和上下文合并，构建带有 [MASK] 的句子
input_text = f"{question} He was born in [MASK]."

inputs = tokenizer(input_text, return_tensors="pt")
mask_token_index = torch.where(inputs["input_ids"][0] == tokenizer.mask_token_id)[0]

# 获取模型输出
with torch.no_grad():
    outputs = model(**inputs)

logits = outputs.logits
mask_token_logits = logits[0, mask_token_index, :]

# 获取预测的词
top_k = 5  # 获取前五个候选词
top_k_ids = torch.topk(mask_token_logits, top_k, dim=1).indices[0].tolist()
predicted_tokens = tokenizer.convert_ids_to_tokens(top_k_ids)

print(f"问题：{question}")
print("模型预测的答案：")
for token in predicted_tokens:
    print(token)
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVZbeZF4zhUdVdhBRUiaPcRebjplTroZNnfzcMng2IE5bywAv5Ar1YYFE7sLC9IOib7n4VhHRCxicxfA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## What are Encoder and Decoder?

### Encoder

 
**Function:** Understand the input content.

**Analogy:** Think of it as a reader who reads and comprehends an article, extracting key points and meanings.

### Decoder

**Function:** Generate output content.  

**Analogy:** Imagine it as a writer who composes an article or sentence based on certain information. 

 

## Model Types and Examples

 

### (1) Encoder-Only Models

 
**Example:** BERT (Bidirectional Encoder Representations from Transformers)

**What does it do?**

- **Main Function:** Understand and analyze the input text rather than generate new text.

- **How it works:** Reads a piece of text and deeply understands its meaning, such as analyzing sentiment, classifying topics, finding keywords, etc.

  **Illustrative Examples:**

- **Sentiment Analysis Task:**

  - **Input:** "I had a fantastic day today!"
  - **BERT's Role:** Understands that the sentiment of this sentence is "positive."
  - **Application Scenario:** Social media monitoring to analyze whether user feedback is good or bad.

- **Text Classification Task:**

  - **Input:** A news article.

  - **BERT's Role:** Reads the article, understands the content, and determines its category (e.g., sports, technology, entertainment).

  - **Application Scenario:** Automatic news categorization and content recommendation systems.

    **Why Use Only an Encoder?**

- **Focus on Understanding:** The encoder can look at both preceding and following text to obtain complete semantic information.

- **No Need for Generation:** These tasks don't require generating new text, only analyzing existing text.

### (2) Decoder-Only Models

 
**Example:** GPT (Generative Pre-trained Transformer)

**What does it do?**

- **Main Function:** Generate new continuous text content based on existing text.

- **How it works:** Given some initial words or sentences, it continues to write.

  **Illustrative Examples:**

- **Text Completion Task:**

  - **Input:** "In the distant future, humanity finally mastered the secrets of interstellar travel."
  - **GPT's Role:** Continues the story, e.g., "They began exploring unknown galaxies, searching for new homes and life forms."
  - **Application Scenario:** Story creation, article continuation, content generation.

- **Dialogue Generation Task:**

  - **User Asks:** "How's the weather today?"

  - **GPT's Role:** Generates an appropriate response, such as, "It's sunny today, perfect for a stroll!"

  - **Application Scenario:** Chatbots and intelligent customer service.

    **Why Use Only a Decoder?**

- **Focus on Generation:** The decoder generates new text word by word based on existing context.

- **Sequential Generation:** It only needs to know the preceding content without considering subsequent words simultaneously.

### (3) Encoder-Decoder Models

 
**Examples:** T5 (Text-to-Text Transfer Transformer), Transformer (originally used for machine translation)

**What does it do?**

- **Main Function:** First understand the input content, then generate output related to the input.

- **How it works:** The encoder reads and understands the input text, and the decoder generates the corresponding output based on the encoder's understanding.

  **Illustrative Examples:**

- **Machine Translation Task:**

  - **Input:** English sentence: "Hello, how are you?"
  - **Encoder's Role:** Understands the meaning and grammatical structure of the sentence.
  - **Decoder's Role:** Generates the corresponding Chinese: "你好，你怎么样？"
  - **Application Scenario:** Translation software like Google Translate and Baidu Translate.

- **Text Summarization Task:**

  - **Input:** A lengthy article about the release of a new tech product.
  - **Encoder's Role:** Reads and understands the main content and details of the entire article.
  - **Decoder's Role:** Generates a concise summary, such as, "A company has released the latest tech product featuring the following new characteristics..."
  - **Application Scenario:** Automatic summarization tools to help quickly grasp the main points of an article.

- **Question-Answering System:**

  - **Given Background Information:** A passage describing a product.

  - **Question:** "What are the main features of this product?"

  - **Encoder's Role:** Understands both the background information and the question.

  - **Decoder's Role:** Generates an answer by extracting and organizing information, e.g., "The main feature is providing high-speed data processing capabilities."

  - **Application Scenario:** Intelligent Q&A and customer service bots.

    **Why Use Both Encoder and Decoder?**

- **Need for Deep Understanding and Generation:** Tasks require the model to first understand the input (encoder) and then generate related output (decoder).

- **Handling Complex Tasks:** Tasks like translation require understanding the source language and generating the target language; summarization requires understanding the full text and generating a brief summary.

------

 

## 3. Why Do These Different Model Architectures Exist?

 
**Choosing the Right Architecture Based on Task Requirements:**

- If the task mainly requires understanding the input:

   

  Use an

   

  Encoder Model

   

  (e.g., BERT, ModernBERT).

  - **Example:** To determine whether a review is positive or negative, using an encoder model like BERT is sufficient.

- If the task mainly requires generating output:

   

  Use a

   

  Decoder Model

   

  (e.g., GPT).

  - **Example:** To write a story, just provide a beginning and let a decoder model like GPT continue writing.

- If the task requires both understanding and generating:

   

  Use an

   

  Encoder-Decoder Model

   

  (e.g., T5, Transformer).

  - **Example:** To translate an English article into Chinese, the model needs to first understand English (encoder) and then generate Chinese (decoder).

------

 

## 4. Why Does GPT Use Only a Decoder?

 
**Focus on Generation Tasks:**

- **GPT's Design Goal:** Generate fluent and coherent text, such as articles and dialogues.

- **Using a Decoder Architecture Suffices:** A decoder model can generate subsequent text word by word based on preceding text without the need for deep understanding from an encoder.

  **Balance of Efficiency and Effectiveness:**

- **Higher Computational Efficiency:** Using only a decoder makes the model more concise, speeding up training and generation.

- **Adequate Performance:** For many generation tasks, decoder models can achieve excellent results.

  **Flexible Applications:**

- **Example:**

  - **Question:** "Please explain why the sky is blue."
  - **GPT's Answer:** "The sky appears blue because molecules in the atmosphere scatter blue light from the sun more than they scatter other wavelengths..."

- **Prompt Learning:** By providing different prompts, GPT can perform various tasks, such as answering questions and translating simple sentences.

------

 

## 5. The Emergence and Significance of ModernBERT

##   **What is ModernBERT?**  ModernBERT is a new **Encoder Model** developed by Answer.AI and LightOn. It integrates the latest technologies to enhance the performance and efficiency of encoder models in Large Language Model (LLM) applications. 

 
The following diagram explains how ModernBERT improves the attention mechanism, focusing on the alternating application of **Global Attention** and **Local Attention**:

- **Left Image:** Classic Global Attention

  - In each layer, all tokens establish global connections with other tokens in the sentence.
  - While it retains full context information, the computational cost is high, especially for long sequences.

- **Right Image:** ModernBERT's Alternating Attention Mechanism

  - ModernBERT alternates between **Global Attention** and **Local Attention** in its attention mechanism.

  - **Global Attention (Yellow Sections):** Focuses on all tokens to ensure global semantic consistency.

  - **Local Attention (Blue Sections):** Only attends to a few surrounding tokens, helping reduce computational burden when processing long sequences.

  - This design allows the model to be more efficient in handling long sequences without losing critical contextual information.

    **Summary:** This attention mechanism improvement significantly enhances ModernBERT's efficiency, especially when processing large-scale data and long-sequence tasks.

    *Image*

------

 
**Why Do We Need Encoder Models?**

**Advantages:**

- **Higher Efficiency:** Encoder models are usually smaller and faster than decoder models, with lower computational costs.

- **Bidirectional Understanding:** Can look at both preceding and following text to learn richer semantic representations.

- **Suitable for Non-Generation Tasks:** Such as classification, similarity computation, content moderation, etc.

  **Challenges:**

- **Underappreciated:** Encoder models haven't received much attention in the LLM field.

  **Innovations of ModernBERT:**

- **Extended Context Window:**

  - **Traditional BERT Limitation:** Can only process inputs up to 512 tokens.
  - **ModernBERT Enhancement:** Extends the context window to 8,000 tokens, enabling it to handle longer texts.

- **Richer Training Data:**

  - **Includes Extensive Code Data:** Enhances ModernBERT's performance in code-related tasks, such as code search.
  - **Outstanding Performance:** On the StackOverflow-QA dataset (containing code and natural language), ModernBERT outperforms all other open-source encoder models.

- **Performance Improvements:**

  - **Faster Speed:** Up to 2x faster than other encoder models like DeBERTa, and in some cases up to 4x faster.
  - **High Memory Efficiency:** Achieves higher accuracy with less memory usage.

- **Architectural Optimizations:**

  - **Incorporates Advanced Technologies:** Such as Rotary Position Embeddings (RoPE) to improve the model's ability to handle long sequences.

  - **Layer Adjustments:** Adds normalization layers, removes unnecessary biases, and uses more efficient activation functions (like GeGELU).

    **Significance of ModernBERT:**

- **Fills the Encoder Model Gap:** Applies the latest LLM technologies (usually used in decoder models) to encoder models, enhancing their performance.

- **Suitable for Resource-Constrained Environments:** Designed to run on smaller, cost-effective GPUs, making it ideal for edge devices like laptops and mobile phones.

------

 

## 6. Comprehensive Understanding

 
**Combining Encoders and ModernBERT:**

- **Importance of Encoder Models:** Encoder models like BERT are highly effective in tasks that require understanding and analyzing text.

- **Contribution of ModernBERT:** Through technological innovations, it enhances the capabilities of encoder models, enabling them to process longer texts and perform tasks more efficiently.

  **Practical Application Scenarios:**

- **Sentiment Analysis:** ModernBERT can handle longer texts, achieving more accurate sentiment analysis.

- **Retrieval Augmented Generation (RAG):** When matching user queries with a large number of documents, ModernBERT can generate high-quality embeddings to improve retrieval efficiency.

- **Code Search and Analysis:** Due to the inclusion of extensive code data, ModernBERT excels in code-related tasks, helping developers find needed code snippets more quickly.

------

 

## 7. Summary

 
**Model Architecture Choice Depends on Task Requirements:**

- **Only Need Understanding?** Use an **Encoder Model** (e.g., BERT, ModernBERT).

- **Only Need Generation?** Use a **Decoder Model** (e.g., GPT).

- **Need Both Understanding and Generation?** Use an **Encoder-Decoder Model** (e.g., T5, Transformer).

  **Significance of ModernBERT:**

- **Enhanced Encoder Model Capabilities:** By incorporating the latest technologies, encoder models can play a more significant role in LLM applications.

- **Meets Practical Needs:** ModernBERT is an ideal choice for tasks requiring efficient processing of long texts and code.

- **Promotes Model Diversity:** Emphasizes the importance of encoder models in the entire LLM ecosystem.