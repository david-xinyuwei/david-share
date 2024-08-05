# Pretrain-on-Synthetic-Instructions

## Instruction Pre-Training
 
[Instruction Pre-Training](https://huggingface.co/instruction-pretrain/instruction-synthesizer) is a new pre-training method proposed by Microsoft, which details how to generate and use synthetic instruction-response pairs to pre-train large language models (LLMs). Below is a summary of the main content:

#### Concept of Instruction Pre-Training

Traditional pre-training methods involve directly pre-training on raw corpora. In contrast, instruction pre-training enhances the raw text by generating instruction-response pairs through an instruction synthesizer. Microsoft's evaluation shows that LLMs pre-trained with instruction pre-training significantly outperform those pre-trained with standard methods across various tasks.

#### Working Principle of the Instruction Synthesizer

Given raw text, the instruction synthesizer generates paired instructions and responses, which can be one-to-one or a few examples. Microsoft fine-tuned the instruction synthesizer using multiple datasets covering a wide range of tasks and domains.

#### Process of Generating Instructions

Microsoft extracted 200M segments (200B tokens) of text samples from the RefinedWeb dataset. The instruction synthesizer generated instruction-response pairs from these samples, which were then re-input into the synthesizer to generate more examples. Ultimately, 200M instruction-response pairs were generated and mixed with the original samples for pre-training.

#### Experimental Results

Microsoft conducted pre-training experiments on LLMs of different sizes. The results showed that models using instruction pre-training performed better on public benchmarks than those pre-trained only on raw text. They also conducted continued pre-training experiments, showing that the advantages of instruction pre-training vary by task.

#### Using the Instruction Synthesizer to Generate Data

Microsoft has released the instruction synthesizer on the Hugging Face Hub and provided code examples. The article demonstrates how to use this code to generate instruction-response pairs for a financial dataset, which can be used for training or continued pre-training of models.

#### Conclusion

The synthetic instruction-response pair method proposed by Microsoft is currently the best, outperforming previous methods like Ada-instruct. Future improvements can be made by fine-tuning larger models. The current synthesizer model is based on the Mistral-7B model.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUMSkAQiczzr9ldMddDev90QewnWVvkKCUNs1dFGpdXo4Jdcw9BO6op0XicSxzjhmEFFSUxdL9Ra7ibg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Can Instruction Pre-Training Generate Labeled Data from Unlabeled Data?

 
Microsoft's instruction pre-training method can be used to generate labeled data from unlabeled data. Specifically, the instruction synthesizer can convert raw, unlabeled text into paired instructions and responses, thereby generating labeled data. This method can be applied to various tasks and domains, including but not limited to question answering, text classification, and named entity recognition. Below is a brief step-by-step guide on how to use the instruction synthesizer to generate labeled data:

1. **Prepare Raw Data**: Collect raw, unlabeled text data, such as financial news, social media posts, technical documents, etc.
2. **Load the Instruction Synthesizer Model**: Use the instruction synthesizer model released by Microsoft, available for download on the Hugging Face Hub. Install necessary dependencies like vLLM.
3. **Generate Instruction-Response Pairs**: Process the raw text using the instruction synthesizer model to generate paired instructions and responses. These pairs can be considered labeled data. For example, for a financial news snippet, the synthesizer might generate a question (instruction) and a corresponding answer (response), thereby labeling the snippet.
4. **Save the Generated Data**: Save the generated instruction-response pairs as a new dataset, which can be used for subsequent model training or evaluation.

## Can Instruction Pre-Training Completely Replace Manual Labeling?

 While Microsoft's instruction pre-training method can generate a large number of question-answer pairs, thereby reducing the need for manual data labeling, it is still unrealistic to completely eliminate the need for manual labeling. Here are some factors to consider:

1. **Quality and Accuracy of Generated Data**: Automatically generated data may not be as accurate as manually labeled data. The generated question-answer pairs may contain errors or inaccuracies, especially when dealing with complex or ambiguous text. Therefore, manual review and correction of the generated data are still necessary.

2. **Domain-Specific Knowledge**: Some domains may require specific expertise, and automatically generated question-answer pairs may not fully capture these details. For example, texts in fields like medicine or law may require professional annotation to ensure data accuracy and reliability.

3. **Model Limitations**: Although instruction synthesizer models can generate high-quality question-answer pairs, they still have limitations. For example, the model may generate repetitive question-answer pairs or perform poorly when handling long texts. Human intervention can help identify and correct these issues.

4. **Diversity and Coverage**: Automatically generated question-answer pairs may lack diversity and coverage. Manual annotation can ensure that the dataset covers a wider range of scenarios and question types, thereby improving the model's generalization ability.

5. **Ethical and Legal Issues**: In some cases, automatically generated data may involve ethical and legal issues. For example, the generated question-answer pairs may contain sensitive information or violate privacy. Manual review can help identify and address these issues.

6. **Model Training and Evaluation**: Even if automatically generated data is used for initial training, manually labeled data is still needed for model evaluation and validation. This ensures the model's performance in the real world.

   Therefore, the best practice is to combine automatic generation and manual annotation methods to obtain high-quality training data. This approach leverages the efficiency of automatic generation while ensuring data accuracy and reliability.

## Code 
```
!pip install vllm
!git clone https://github.com/microsoft/LMOps.git
%cd LMOps/instruction_pretrain/
```
```
from vllm import LLM, SamplingParams
from utils.read_compre import get_dataset, cook_pt_entries, run
from datasets import load_dataset
```
```
raw_texts = load_dataset("ugursa/Yahoo-Finance-News-Sentences", split="train")
text_field = "text" #column of the dataset that contain the raw text

raw_texts = [text for text in raw_texts[text_field]]
print(f'Number of raw texts: {len(raw_texts)}')

STOP=5 # Stop after this many examples -- I set this to limit the number of sample generated for this notebook.
raw_texts = raw_texts[:STOP]
max_model_len = 4096
max_new_tokens = 1000
sampling_params = SamplingParams(temperature=0, max_tokens=max_new_tokens)
llm = LLM(model="instruction-pretrain/instruction-synthesizer", max_model_len=max_model_len)
```
```
N = len(raw_texts) # Number of raw texts
M = 2  # M-shot example

prev_examples = []
BSZ = (N+M-1)//M
for round in range(M):
    cur_raw_texts = raw_texts[round*BSZ: (round+1)*BSZ]
    # load data
    split = get_dataset(prev_examples=prev_examples,
                        cur_raw_texts=cur_raw_texts,
                        max_model_len=max_model_len,
                        max_new_tokens=max_new_tokens)
    prev_examples = run(split, llm, sampling_params)
```
```
instruction_augmented_texts = []
for idx, entry in enumerate(prev_examples):
    texts = cook_pt_entries(read_collection=entry, random_seed=idx+1345)
    instruction_augmented_texts.extend(texts)
```
```
for idx, text in enumerate(instruction_augmented_texts):
    print(f'## Instruction-augmented Text {idx+1}\n{text}\n')
```
In this context, M represents the number of examples generated, specifically the number of few-shot examples. More precisely, M indicates how many instruction-response pairs will be generated for each raw text segment during the pre-training process. Here is a detailed explanation of M:
- M = 2: This means that each raw text segment will generate 2 instruction-response pairs. This setting is used for general pre-training from scratch, aiming to enhance the model's multitask learning capability without significantly increasing the data volume.
- M = 3: This means that each raw text segment will generate 3 instruction-response pairs. This setting is used for domain-adaptive continual pre-training, aiming to generate more examples to better adapt to specific domain requirements while maintaining a certain level of generality.


Output:
```
## Instruction-augmented Text 1
China's CMOC Group, which boosted its cobalt output by 144% during the first three quarters of 2023, is now on track to become the world's biggest cobalt producer, overtaking commodity group Glencore. Curious minds, it's your turn! Answer these questions:

Problem: What is the CMOC Group?
Answer: China's CMOC Group

Problem: What did the CMOC Group increase by 144%?
Answer: its cobalt output

Problem: When did the CMOC Group increase its cobalt output by 144%?
Answer: during the first three quarters of 2023

Problem: Which company is the world's biggest cobalt producer?
Answer: Glencore

Problem: Which group is on track to become the world's biggest cobalt producer?
Answer: CMOC

## Instruction-augmented Text 2
Chinese-owned companies are aggressively expanding cobalt mining in Congo and Indonesia even while prices crash, as they bid to raise market share of the metal used in batteries for the country's electric vehicle (EV) industry. Curious minds, it's your turn! Answer these questions:


Q: What may be the reason for this expansion? ---- Available choices:
[+] They want to take over the EV industry.
[+] They can make more money that way.
[+] They own most of the cobalt mines.
[+] They need the metal for other uses.

A: They can make more money that way.

CMOC is due to lift its market share of the global mined cobalt market from 11% in 2022 to nearly 30% by 2025, said Jorge Uzcategui, an analyst at consultancy Benchmark Mineral Intelligence. Curious minds, it's your turn! Answer these questions:


Q: What may happen if CMOC does not meet it's goals? ---- Available choices:
[+] They will be put out of the company.
[+] They will be seen as incompetent.
[+] They will lose funding.
[+] They will be seen as unambitious.

A: They will be seen as incompetent.
```