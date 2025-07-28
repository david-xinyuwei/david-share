# Five Levels of Chunking 
This article will first introduce the principles of five chunking methods, followed by the implementation of the code.


## Five Levels of Chunking Implementation principle

### Level 1: Fixed Size Chunking

#### Description

 
Fixed-size chunking is one of the simplest text segmentation methods. It divides text into chunks based on a fixed number of characters, without considering the content or structure of the text.

#### Implementation

 
This method is simple to implement, dividing text according to a specified number of characters. For example, if each chunk is set to a maximum of 100 characters, the text will be directly divided into segments of 100 characters each.

#### Advantages

 

- Simple to implement, suitable for scenarios with low requirements for text structure.

#### Disadvantages

 

- May split at inappropriate positions (e.g., in the middle of words or sentences), leading to incomplete semantics and affecting subsequent processing.

#### Example

 
Suppose we have a piece of text:

```
This is the first paragraph. This sentence is a bit long and needs to be split.  
This is the second paragraph. It also needs to be split.  
```

 
If we set each chunk to a maximum of 20 characters, the result might be:

```
Chunk 1: This is the first pa    
Chunk 2: ragraph. This senten    
Chunk 3: ce is a bit long and   
Chunk 4: needs to be split.  
```

 
As you can see, the split occurs in the middle of words and sentences, resulting in incomplete semantics.

### Level 2: Recursive Chunking

#### Description

 
Recursive chunking is a method that considers the structure of the text, dividing it into smaller chunks through layering and iteration. It uses a set of delimiters (such as paragraphs, sentences, words, etc.) to gradually segment the text.

#### Implementation

 
Start by using larger delimiters (such as paragraphs). If the resulting chunks are still too large, use smaller delimiters (such as sentences), and so on, until the desired chunk size is achieved.

#### Advantages

- Better preserves the structure and semantic relationships of the text, avoiding splits at inappropriate positions.

#### Disadvantages

- Relatively complex to implement, requiring consideration of multiple levels of delimiters and recursive calls.

#### Example

 
Suppose we have a piece of text:

```
This is the first paragraph. This sentence is a bit long and needs to be split.  
This is the second paragraph. It also needs to be split.  
```


Recursive chunking process:

**Step 1**: Use paragraph delimiters "\n\n" to split, resulting in two paragraphs:

```
Paragraph 1: This is the first paragraph. This sentence is a bit long and needs to be split.  
Paragraph 2: This is the second paragraph. It also needs to be split.  
```

 
**Step 2**: Check the length of each paragraph. If paragraph 1 is still too long, use sentence delimiters "." to split:

```
Sentence 1: This is the first paragraph.  
Sentence 2: This sentence is a bit long and needs to be split.  
```

 
**Step 3**: Check the length of each sentence. If sentence 2 is still too long, use word delimiters " " to split:

```
Word 1: This sentence is a bit long   
Word 2: and needs to be split.  
```

 
Through this layered splitting method, recursive chunking can divide the text into appropriately sized chunks while maintaining semantic integrity.

### Level 3: Document Based Chunking

#### Description


Document-based chunking divides text according to the natural structure of the document (such as chapters, paragraphs, headings, etc.). This method is particularly suitable for structured documents like books, reports, and papers.

#### Implementation

 
Identify natural delimiters in the document (such as chapter titles, paragraph markers, etc.) to segment the text.

#### Advantages

- Preserves the natural structure of the document, suitable for structured documents.
- Splits usually occur at natural semantic boundaries, maintaining the integrity of the text.

#### Disadvantages

- Depends on the structure of the document, with limited applicability.
- Less effective for unstructured text.

#### Example
Suppose we have an article:

```
# Chapter 1    
This is the content of the first chapter.  
# Chapter 2    
This is the content of the second chapter.  
```

 
Document-based chunking process:

1. **Identify Chapter Titles**: Use "#" as the marker for chapter titles.

2. **Split Text**: Segment the text based on chapter titles.

   Result:

```
Chunk 1: Chapter 1\nThis is the content of the first chapter.  
Chunk 2: Chapter 2\nThis is the content of the second chapter.  
```

 

### Level 4: Semantic Chunking

#### Description


Semantic chunking is an advanced text segmentation method that aims to divide text based on semantic content and contextual relationships, rather than simply relying on character count or fixed delimiters.

#### Implementation

 
Utilize embeddings to convert text into vector representations, then determine split points by calculating the similarity between these vectors.

#### Advantages

 

- Preserves semantic relationships in the text, enhancing information retrieval and processing.
- Suitable for various types of text, especially complex structured text.

#### Disadvantages

 

- Requires computation of embeddings and similarity, which is computationally intensive.
- Depends on pre-trained language models, potentially requiring significant computational resources.

#### Example

 
Suppose we have a piece of text:

```
Machine learning is a type of artificial intelligence. It enables computers to learn and improve from data. Deep learning is a subfield of machine learning, using neural networks for complex data analysis.  
```

 
Semantic chunking process:

1. **Text Embedding**: Convert text into embedding vectors.

2. **Similarity Calculation**: Calculate similarity scores between each sentence.

3. **Determine Split Points**: Identify split points based on similarity scores.

   Assume the similarity scores are as follows:

- High similarity between sentence 1 and sentence 2

- Low similarity between sentence 2 and sentence 3

  Based on similarity scores, the text can be divided into two chunks:

```
Chunk 1: Machine learning is a type of artificial intelligence. It enables computers to learn and improve from data.  
Chunk 2: Deep learning is a subfield of machine learning, using neural networks for complex data analysis.  
```

 

### Level 5: Agentic Chunking

#### Description


Agentic chunking is a method that uses large language models (LLMs) to dynamically determine text segmentation strategies. It relies on the intelligence and contextual understanding of LLMs to decide how to segment text based on specific tasks and contexts.

#### Implementation

 
Allow the LLM to act as an "agent" to analyze the text and generate or adjust chunking strategies as needed.

#### Advantages

 

- Leverages the intelligence and contextual understanding of LLMs to dynamically adjust chunking strategies.
- Suitable for various types of text and tasks, allowing for adjustments based on specific needs.

#### Disadvantages

 

- Relies on LLMs for analysis, which is computationally intensive.
- The implementation process is relatively complex, requiring the integration of multiple technologies and methods.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVrKpPt4AfhZd5LlvI4un2buoflDXYnibkeSUCjbicsNhqeFxf51DFtKRlMP58vMbuRmog5re3o2yNg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)


## Chunking code
There are many issue in source jupyter file in *https://github.com/FullStackRetrieval-com/RetrievalTutorials.git*, such as lake of python package, version mismatch, etc.

So wrote a code will could achieve Level 5: Agentic Chunking

My python code.
```
import uuid  
import requests  
from langchain_core.prompts import ChatPromptTemplate  
  
class AgenticChunker:  
    def __init__(self):  
        self.chunks = {}  
        self.id_truncate_limit = 5  
  
        self.generate_new_metadata_ind = True  
        self.print_logging = True  
  
        # Azure OpenAI 配置信息  
        self.endpoint = "https://eastus2xinyuwei.openai.azure.com/openai/deployments/eastus3xinyuwei/chat/completions?api-version=2024-02-15-preview"  
        self.api_key = "***"  
  
    def _invoke_llm(self, prompt):  
        headers = {  
            "Content-Type": "application/json",  
            "api-key": self.api_key  
        }  
        data = {  
            "messages": [{"role": "user", "content": prompt}],  
            "max_tokens": 100,  
            "temperature": 0  
        }  
        response = requests.post(self.endpoint, headers=headers, json=data)  
        response.raise_for_status()  
        return response.json()['choices'][0]['message']['content'].strip()  
  
    def add_propositions(self, propositions):  
        for proposition in propositions:  
            self._add_proposition_to_chunk(proposition)  
  
    def _add_proposition_to_chunk(self, proposition):  
        chunk_id = str(uuid.uuid4())[:self.id_truncate_limit]  
        self.chunks[chunk_id] = {  
            'propositions': [proposition],  
            'summary': self._update_chunk_summary({'propositions': [proposition], 'summary': ''})  
        }  
  
    def _update_chunk_summary(self, chunk):  
        PROMPT = ChatPromptTemplate.from_messages(  
            [  
                (  
                    "system",  
                    """  
                    You are the steward of a group of chunks which represent groups of sentences that talk about a similar topic  
                    A new proposition was just added to one of your chunks, you should generate a very brief 1-sentence summary which will inform viewers what a chunk group is about.  
  
                    A good summary will say what the chunk is about, and give any clarifying instructions on what to add to the chunk.  
  
                    You will be given a group of propositions which are in the chunk and the chunks current summary.  
  
                    Your summaries should anticipate generalization. If you get a proposition about apples, generalize it to food.  
                    Or month, generalize it to "date and times".  
  
                    Example:  
                    Input: Proposition: Greg likes to eat pizza  
                    Output: This chunk contains information about the types of food Greg likes to eat.  
  
                    Only respond with the chunk new summary, nothing else.  
                    """,  
                ),  
                ("user", "Chunk's propositions:\n{proposition}\n\nCurrent chunk summary:\n{current_summary}"),  
            ]  
        )  
  
        prompt = PROMPT.format(proposition="\n".join(chunk['propositions']), current_summary=chunk['summary'])  
        new_chunk_summary = self._invoke_llm(prompt)  
  
        return new_chunk_summary  
  
    def pretty_print_chunks(self):  
        for chunk_id, chunk in self.chunks.items():  
            print(f"Chunk ID: {chunk_id}")  
            print(f"Propositions: {chunk['propositions']}")  
            print(f"Summary: {chunk['summary']}\n")  
  
    def pretty_print_chunk_outline(self):  
        for chunk_id, chunk in self.chunks.items():  
            print(f"Chunk ID: {chunk_id} - Summary: {chunk['summary']}")  
  
    def get_chunks(self, get_type='list_of_strings'):  
        if get_type == 'list_of_strings':  
            return [f"Chunk ID: {chunk_id}, Summary: {chunk['summary']}" for chunk_id, chunk in self.chunks.items()]  
        return self.chunks  
  
if __name__ == "__main__":  
    ac = AgenticChunker()  
  
    propositions = [  
        'The month is October.',  
        'The year is 2023.',  
        "One of the most important things that I didn't understand about the world as a child was the degree to which the returns for performance are superlinear.",  
        'Teachers and coaches implicitly told us that the returns were linear.',  
        "I heard a thousand times that 'You get out what you put in.'",  
    ]  
      
    ac.add_propositions(propositions)  
    ac.pretty_print_chunks()  
    ac.pretty_print_chunk_outline()  
    print(ac.get_chunks(get_type='list_of_strings'))  

```
Execute results:
```
Chunk ID: 779b4
Propositions: ['The month is October.']
Summary: This chunk contains information about dates and times.

Chunk ID: 24891
Propositions: ['The year is 2023.']
Summary: This chunk contains information about dates and times.

Chunk ID: b7383
Propositions: ["One of the most important things that I didn't understand about the world as a child was the degree to which the returns for performance are superlinear."]
Summary: This chunk contains reflections on understanding the complexities of performance and its rewards.

Chunk ID: 152b9
Propositions: ['Teachers and coaches implicitly told us that the returns were linear.']
Summary: This chunk contains information about the implicit messages from teachers and coaches regarding performance expectations.

Chunk ID: e89cc
Propositions: ["I heard a thousand times that 'You get out what you put in.'"]
Summary: This chunk contains information about the principle of effort and reward.

Chunk ID: 779b4 - Summary: This chunk contains information about dates and times.
Chunk ID: 24891 - Summary: This chunk contains information about dates and times.
Chunk ID: b7383 - Summary: This chunk contains reflections on understanding the complexities of performance and its rewards.
Chunk ID: 152b9 - Summary: This chunk contains information about the implicit messages from teachers and coaches regarding performance expectations.
Chunk ID: e89cc - Summary: This chunk contains information about the principle of effort and reward.
['Chunk ID: 779b4, Summary: This chunk contains information about dates and times.', 'Chunk ID: 24891, Summary: This chunk contains information about dates and times.', 'Chunk ID: b7383, Summary: This chunk contains reflections on understanding the complexities of performance and its rewards.', 'Chunk ID: 152b9, Summary: This chunk contains information about the implicit messages from teachers and coaches regarding performance expectations.', 'Chunk ID: e89cc, Summary: This chunk contains information about the principle of effort and reward.']
```




Refer to ：https://github.com/FullStackRetrieval-com/RetrievalTutorials.git