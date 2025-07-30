# RAG Best Practice With AI Search

Although models like GPT-4 and GPT-3.5 are powerful, their knowledge cannot be the most up-to-date. Previously, we often introduced engineering techniques in the use of LLMs by treating prompt engineering, RAG, and fine-tuning as parallel methods. In fact, these three technologies can be combined.

##  Four stages of RAG

 The thinking in the paper I read is excellent—it divides RAG into four stages. 

 ![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nUtDdUuMGNicTShl7ib3NKD1NlRyzggptGGCpJs4YOreYt9tqTxjfGsvKlIkSVMHadX0tVKJT2PaP4A/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



## Level 1: Explicit Fact Queries

### Characteristics

**Simplicity**: Directly retrieving explicit factual information from provided data without the need for complex reasoning or multi-step processing.

**Requirement**: Efficiently and accurately retrieve relevant content and generate precise answers.

### Techniques and Engineering Suggestions

#### a. Basic RAG Methods

- Data Preprocessing and Chunking

  : Divide long texts or documents into appropriate chunks for indexing and retrieval. Common chunking strategies include:

  - **Fixed-Length Chunking**: Splitting the text by fixed lengths, which may interrupt sentences or paragraphs.
  - **Paragraph-Based or Semantic Chunking**: Chunking based on natural paragraphs or semantic boundaries to maintain content integrity.

- Index Construction:

  - **Sparse Indexing**: Use traditional information retrieval methods like TF-IDF or BM25 based on keyword matching.
  - **Dense Indexing**: Use pre-trained language models (e.g., BERT) to generate text vector embeddings for vector retrieval.

- Retrieval Techniques:

  - Utilize vector similarity calculations or keyword matching to retrieve the most relevant text fragments from the index.

- Answer Generation:

  - Input the retrieved text fragments as context into the LLM to generate the final answer.

#### b. Improving Retrieval and Generation Phases

- **Multimodal Data Processing**: If the data includes tables, images, or other non-text information, convert them into text form or use multimodal models for processing.
- Retrieval Optimization:
  - **Recursive Retrieval**: Perform multiple rounds of retrieval when a single retrieval isn't sufficient to find the answer, gradually narrowing down the scope.
  - **Retrieval Result Re-ranking**: Use models to score or re-rank retrieval results, prioritizing the most relevant content.
- Generation Optimization:
  - **Filtering Irrelevant Information**: Before the generation phase, filter out retrieved content unrelated to the question to avoid interfering with the model's output.
  - **Controlling Answer Format**: Through carefully designed prompts, ensure the model generates answers with correct formatting and accurate content.

### Engineering Practice Example

**Example**: Constructing a Q&A system to answer common questions about company products.

- Data Preparation:
  - Collect all relevant product documents, FAQs, user manuals, etc.
  - Clean, chunk, and index the documents.
- System Implementation:
  - After a user asks a question, use dense vector retrieval to find the most relevant text fragments from the index.
  - Input the retrieved fragments as context into the LLM to generate an answer.
- Optimization Strategies:
  - Regularly update documents and indexes to ensure information is current.
  - Monitor user feedback to improve retrieval strategies and prompt designs, enhancing answer quality.



## Level 2: Implicit Fact Queries

### Characteristics 

- **Increased Complexity**: Requires a certain degree of reasoning or multi-step derivation based on the retrieved data.
- **Requirement**: The model needs to decompose the question into multiple steps, retrieve and process them separately, and then synthesize the final answer.

### Techniques and Engineering Suggestions

#### a. Multi-Hop Retrieval and Reasoning

- Iterative RAG:
  - **IRCoT (Iterative Retrieval Chain-of-Thought)**: Use chain-of-thought reasoning to guide the model in retrieving relevant information at each step, gradually approaching the answer.
  - **RAT (Retrieve and Answer with Thought)**: Introduce retrieval steps during the answering process, allowing the model to retrieve new information when needed.
- Question Decomposition:
  - Break down complex questions into simpler sub-questions, retrieve and answer them individually, then synthesize the results.

#### b. Graph or Tree Structured Retrieval and Reasoning

- Building Knowledge Graphs:
  - Extract entities and relationships from data to construct knowledge graphs, helping the model understand complex dependencies.
- Graph Search Algorithms:
  - Use algorithms like Depth-First Search (DFS) or Breadth-First Search (BFS) to find paths or subgraphs related to the question within the knowledge graph.

#### c. Using SQL or Other Structured Queries

- Text-to-SQL Conversion:
  - Convert natural language questions into SQL queries to retrieve answers from structured databases.
- Tool Support:
  - Use existing text-to-SQL conversion tools (e.g., Chat2DB) to facilitate natural language to database query conversion.

### 2.3 Engineering Practice Example


**Scenario**: A user asks, "In which quarters over the past five years did company X's stock price exceed company Y's?"

**Question Decomposition**:

1. Obtain quarterly stock price data for company X and company Y over the past five years.

2. Compare the stock prices for each quarter.

3. Identify the quarters where company X's stock price exceeded company Y's.

   **Implementation Steps**:

- **Step 1**: Use text-to-SQL tools to convert the natural language query into SQL queries and retrieve relevant data from the database.

- **Step 2**: Use a programming language (e.g., Python) to process and compare the data.

- **Step 3**: Organize the results into a user-readable format.

  **Answer Generation**: Input the organized results as context into the LLM to generate a natural language response.

 

## Level 3: Interpretable Rationale Queries

### Characteristics

 

- **Application of Domain-Specific Rules and Guidelines**: The model needs to understand and follow rules typically not covered in pre-training data.
- **Requirement**: Integrate external rules, guidelines, or processes into the model so it can follow specified logic and steps when answering.

### Techniques and Engineering Suggestions

#### a. Prompt Engineering and Prompt Optimization

- Designing Effective Prompts:
  - Explicitly provide rules or guidelines within the prompt to guide the model in following specified steps when answering.
- Automated Prompt Optimization:
  - Use optimization algorithms (e.g., reinforcement learning) to automatically search and optimize prompts, improving the model's performance on specific tasks.
  - **OPRO (Optimization with Prompt Rewriting)**: The model generates and evaluates prompts on its own, iteratively optimizing to find the best prompt combination.

#### b. Chain-of-Thought (CoT) Prompts

- Guiding Multi-Step Reasoning:
  - Require the model to display its reasoning process within the prompt, ensuring it follows specified logic.
- Manual or Automated CoT Prompt Design:
  - Design appropriate CoT prompts based on task requirements or use algorithms to generate them automatically.

#### c. Following External Processes or Decision Trees

- Encoding Rules and Processes:
  - Convert decision processes into state machines, decision trees, or pseudocode for the model to execute.
- Model Adjustment:
  - Enable the model to parse and execute these encoded rules.

### Engineering Practice Example


**Example**: A customer service chatbot handling return requests.

**Scenario**: A customer requests a return. The chatbot needs to guide the customer through the appropriate process according to the company's return policy.

**Technical Implementation**:

- Rule Integration:

  - Organize the company's return policies and procedures into clear steps or decision trees.

- Prompt Design:

  - Include key points of the return policy within the prompt, requiring the model to guide the customer step by step.

- Model Execution:

  - The LLM interacts with the customer based on the prompt, following the return process to provide clear guidance.

    **Optimization Strategies**:

- Prompt Optimization:

  - Adjust prompts based on customer feedback to help the model more accurately understand and execute the return process.

- Multi-Turn Dialogue:

  - Support multiple rounds of conversation with the customer to handle various potential issues and exceptions.



## Level 4: Hidden Rationale Queries

### Characteristics

- **Highest Complexity**: Involves domain-specific, implicit reasoning methods; the model needs to discover and apply these hidden logics from data.
- **Requirement**: The model must be capable of mining patterns and reasoning methods from large datasets, akin to the thought processes of domain experts.

### Techniques and Engineering Suggestions

#### a. Offline Learning and Experience Accumulation

- Learning Patterns and Experience from Data:
  - Train the model to generalize potential rules and logic from historical data and cases.
- Self-Supervised Learning:
  - Use the model-generated reasoning processes (e.g., Chain-of-Thought) as auxiliary information to optimize the model's reasoning capabilities.

#### b. In-Context Learning (ICL)

- Providing Examples and Cases:
  - Include relevant examples within the prompt for the model to reference similar cases during reasoning.
- Retrieving Relevant Cases:
  - Use retrieval modules to find cases similar to the current question from a database and provide them to the model.

#### c. Model Fine-Tuning 

- Domain-Specific Fine-Tuning:
  - Fine-tune the model using extensive domain data to internalize domain knowledge.
- Reinforcement Learning:
  - Employ reward mechanisms to encourage the model to produce desired reasoning processes and answers.

### Engineering Practice Example



**Example**: A legal assistant AI handling complex cases.

**Scenario**: A user consults on a complex legal issue. The AI needs to provide advice, citing relevant legal provisions and precedents.

**Technical Implementation**:

- Data Preparation:

  - Collect a large corpus of legal documents, case analyses, expert opinions, etc.

- Model Fine-Tuning:

  - Fine-tune the LLM using legal domain data to equip it with legal reasoning capabilities.

- Case Retrieval:

  - Use RAG to retrieve relevant precedents and legal provisions from a database.

- Answer Generation:

  - Input the retrieved cases and provisions as context into the fine-tuned LLM to generate professional legal advice.

    **Optimization Strategies**:

- Continuous Learning:

  - Regularly update the model by adding new legal cases and regulatory changes.

- Expert Review:

  - Incorporate legal experts to review the model's outputs, ensuring accuracy and legality.



## Comprehensive Consideration: Combining Fine-Tuned LLMs and RAG


While fine-tuning LLMs can enhance the model's reasoning ability and domain adaptability, it cannot entirely replace the role of RAG. RAG has unique advantages in handling dynamic, massive, and real-time updated knowledge. Combining fine-tuning and RAG leverages their respective strengths, enabling the model to possess strong reasoning capabilities while accessing the latest and most comprehensive external knowledge.

### Advantages of the Combination

- Enhanced Reasoning Ability:
  - Through fine-tuning, the model learns domain-specific reasoning methods and logic.
- Real-Time Knowledge Access:
  - RAG allows the model to retrieve the latest external data in real-time when generating answers.
- Flexibility and Scalability:
  - RAG systems can easily update data sources without the need to retrain the model.

### Practical Application Suggestions

- Combining Fine-Tuning and RAG for Complex Tasks:
  - Use fine-tuning to enhance the model's reasoning and logic capabilities, while employing RAG to obtain specific knowledge and information.
- Evaluating Cost-Benefit Ratio:
  - Consider the costs and benefits of fine-tuning; focus on fine-tuning core reasoning abilities and let RAG handle knowledge acquisition.
- Continuous Update and Maintenance:
  - Establish data update mechanisms for the RAG system to ensure the external data accessed by the model is up-to-date and accurate.

## RAG Detailed technical explaination

Retrieval Augmented Generation (RAG) is a technique that combines large language models (LLMs) with information retrieval. It enhances the model's capabilities by retrieving and utilizing relevant information from external knowledge bases during the generation process. This provides the model with up-to-date, domain-specific knowledge, enabling it to generate more accurate and contextually relevant responses.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nV8iccIwibpABEdicffYMy77GDXFYUR4MEmsibdwPE4XzSudU52gQL0cBAJeiaId5EltiaHguq952P0e7xg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Purpose of RAG

**Why do we need RAG?**

- **Reducing Hallucinations**: LLMs may produce inaccurate or false information, known as "hallucinations," when they lack sufficient context. RAG reduces the occurrence of hallucinations by providing real-time external information.

- **Updating Knowledge**: The pre-training data of LLMs may lag behind current information. RAG allows models to access the latest data sources, maintaining the timeliness of information.

- **Enhancing Accuracy**: By retrieving relevant background information, the model's answers become more accurate and professional.

  

### How RAG Works

The core idea of RAG is to retrieve relevant information from a document repository and input it into the LLM along with the user's query, guiding the model to generate a more accurate answer. The general process is as follows:

- **User Query**: The user poses a question or request to the system.
- **Retrieval Phase**: The system uses the query to retrieve relevant document fragments (chunks) from a document repository or knowledge base.
- **Generation Phase**: The retrieved document fragments are input into the LLM along with the original query to generate the final answer.


### Key Steps to Building a RAG System

### Clarify Objectives

Before starting to build a RAG system, you need to first clarify your goals:

- **Upgrade Search Interface**: Do you want to add semantic search capabilities to your existing search interface?

- **Enhance Domain Knowledge**: Do you wish to utilize domain-specific knowledge to enhance search or chat functions?

- **Add a Chatbot**: Do you want to add a chatbot to interact with customers?

- **Expose Internal APIs**: Do you plan to expose internal APIs through user dialogues?

  Clear objectives will guide the entire implementation process and help you choose the most suitable technologies and strategies.

### Data Preparation

Data is the foundation of a RAG system, and its quality directly affects system performance. Data preparation includes the following steps:

**(1) Assess Data Formats**

- **Structured Data**: Such as CSV, JSON, etc., which need to be converted into text format to facilitate indexing and retrieval.

- **Tabular Data**: May need to be converted or enriched to support more complex searches or interactions.

- **Text Data**: Such as documents, articles, chat records, etc., which may need to be organized or filtered.

- **Image Data**: Including flowcharts, documents, photographs, and similar images.

  

  **(2) Data Enrichment**

- **Add Contextual Information**: Supplement data with additional textual content, such as knowledge bases or industry information.

- **Data Annotation**: Label key entities, concepts, and relationships to enhance the model's understanding capabilities.

  

  **(3) Choose the Right Platform**

- **Vector Databases**: Such as AI Search, Qdrant, etc., used for storing and retrieving embedding vectors.

- **Relational Databases**: The database schema needs to be included in the LLM's prompts to translate user requests into SQL queries.

- **Text Search Engines**: Like AI Search, Elasticsearch, Couchbase, which can be combined with vector search to leverage both text and semantic search advantages.

- **Graph Databases**: Build knowledge graphs to utilize the connections and semantic relationships between nodes.

## Document Chunking

In a RAG system, document chunking is a critical step that directly affects the quality and relevance of the retrieved information. Below are the best practices for chunking:

- Model Limitations: LLMs have a maximum context length limitation.
- Improve Retrieval Efficiency: Splitting large documents into smaller chunks helps to improve retrieval accuracy and speed.

**Methods to do chunking**

- **Fixed-Size Chunking**: Define a fixed size (e.g., 200 words) for chunks and allow a certain degree of overlap (e.g., 10-15%).
- **Content-Based Variable-Size Chunking**: Chunk based on content features (such as sentences, paragraphs, Markdown structures).
- **Custom or Iterative Chunking Strategies**: Combine fixed-size and variable-size methods and adjust according to specific needs.

**Importance of Content Overlap**

- **Preserve Context**: Allowing some overlap between chunks during chunking helps to retain contextual information.
- **Recommendation**: Start with about 10% overlap and adjust based on specific data types and use cases.



## Choosing the Right Embedding Model

Embedding models are used to convert text into vector form to facilitate similarity computation. When choosing an embedding model, consider:

- **Model Input Limitations**: Ensure the input text length is within the model's allowable range.

- **Model Performance and Effectiveness**: Choose a model with good performance and suitable effectiveness based on the specific application scenario.

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/1.png)

**New Embedding Models**: OpenAI has introduced two new embedding models: `text-embedding-3-small` and `text-embedding-3-large`.

**Model Size and Performance**: `text-embedding-3-large` is a larger and more powerful embedding model capable of creating embeddings with up to 3,072 dimensions.

**Performance Improvements**:

- **MIRACL Benchmark**: `text-embedding-3-large` scored **54.9** on the MIRACL benchmark, showing a significant improvement over `text-embedding-ada-002` which scored **31.4**.

- **MTEB Benchmark**: `text-embedding-3-large` scored **64.6** on the MTEB benchmark, surpassing `text-embedding-ada-002` which scored **61.0**.

  **Analysis of Improvements**:

- **Higher Dimensions**: The ability of `text-embedding-3-large` to create embeddings with up to 3,072 dimensions allows it to better capture and represent the concepts and relationships within the content.

- **Improved Training Techniques**: The new model employs more advanced training techniques and optimization methods, resulting in better performance on multilingual retrieval and English tasks.

- **Flexibility**: `text-embedding-3-large` allows developers to balance performance and cost by adjusting the dimensionality of the embeddings. For example, reducing the 3,072-dimensional embeddings to 256 dimensions can still outperform the uncompressed `text-embedding-ada-002` on the MTEB benchmark.

**Note**:

To migrate from `text-embedding-ada-002` to `text-embedding-3-large`, you'll need to manually generate new embeddings, as upgrading between embedding models is not automatic. The first step is to deploy the new model (text-embedding-3-large) within your Azure environment. After that, re-generate embeddings for all your data, as embeddings from the previous model will not be compatible with the new one.

## AI Search Service Capacity and Performance Optimization

### Service Tiers and Capacity

**Refer to**: *https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity*

- **Upgrade Service Tier**: Upgrading from Standard S1 to S2 can provide higher performance and storage capacity.

- **Increase Partitions and Replicas**: Adjust based on query load and index size.

- **Avoid Complex Queries**: Reduce the use of high-overhead queries, such as regular expression queries.

- **Query Optimization**: Retrieve only the required fields, limit the amount of data returned, and use search functions rather than complex filters.

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/2.png)

  ### Tips for Improving Azure AI Search Performance

  - **Index Size and Architecture**: Regularly optimize the index; remove unnecessary fields and documents.
  - **Query Design**: Optimize query statements to reduce unnecessary scanning and computation.
  - **Service Capacity**: Adjust replicas and partitions appropriately based on query load and index size.
  - **Avoid Complex Queries**: Reduce the use of high-overhead queries, such as regular expression queries.

  ### Chunking Large Documents

  - **Use Built-in Text Splitting Skills**: Choose modes like `pages` or `sentences` based on needs.
  - **Adjust Parameters**: Set appropriate `maximumPageLength`, `pageOverlapLength`, etc., based on document characteristics.
  - **Use Tools Like LangChain**: For more flexible chunking and embedding operations.

  ### L1+L2 Search + Query Rewriting and New Semantic Reranker

  - **L1 Hybrid Search+L2 Re-ranker**：Enhance search result

    ![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/9.png)

  - **Query Rewriting**: Improve recall rate and accuracy by rewriting user queries.
  
  - **Semantic Reranker**: Use cross-encoders to re-rank candidate results, enhancing result relevance.
  
  ![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/8.png)

***Please click below pictures to see my Query Rewriting demo video on Yutube***:
[![Query-Rwritting-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://www.youtube.com/watch?v=uMDOpPzFfsc)

In the demo above for reference, I increased the number of rewritten queries from 1 to 3, which significantly improved the accuracy of the search results. The complete answer should consist of four results. When the number of rewritten query vectors is 1, only three results can be retrieved.

Sample code：

```
import requests  
import json  
  
url = 'https://ai-search-eastus-xinyuwei.search.windows.net/indexes/wukong-doc1/docs/search'  
params = {  
    'api-version': '2024-11-01-preview'  
}  
  
headers = {  
    'Content-Type': 'application/json',  
    'api-key': '**'  
}  
  
payload = {  
    "search": "What the hell is Black Myth Goku?",  
    "semanticConfiguration": "wukong-doc1-semantic-configuration",  
    "queryType": "semantic",  
    "queryRewrites": "generative|count-5",  
    "queryLanguage": "en-US",  
    "debug": "queryRewrites",  
    "top": 1  
}  
  
response = requests.post(url, params=params, headers=headers, json=payload)  
  
print('Status Code:', response.status_code)  
print('Response Body:', json.dumps(response.json(), indent=2, ensure_ascii=False))  
```

Output:

```
Status Code: 200
Response Body: {
  "@odata.context": "https://ai-search-eastus-xinyuwei.search.windows.net/indexes('wukong-doc1')/$metadata#docs(*)",
  "@search.debug": {
    "semantic": null,
    "queryRewrites": {
      "text": {
        "inputQuery": "What the hell is Black Myth Goku?",
        "rewrites": [
          "Black Myth Goku game details",
          "What is Black Myth Goku?",
          "Explanation of Black Myth Goku",
          "Understanding Black Myth Goku",
          "Guide to Black Myth Goku"
        ]
      },
      "vectors": []
    }
  },
  "value": [
    {
      "@search.score": 10.368155,
      "@search.rerankerScore": 2.3498611450195312,
```

## Prompt Engineering

1. **Use Rich Examples**: Provide multiple examples to guide the model's learning and improve its responses.
2. **Provide Clear Instructions**: Ensure that instructions are explicit and unambiguous to avoid misunderstandings.
3. **Restrict Input and Output Formats**: Define acceptable input and output formats to prevent malicious content and protect model security.

**Note:** Prompt Engineering is not suitable for Azure OpenAI o1

Reference: *https://mp.weixin.qq.com/s/tLcAfPU6hUkFsNMjDFeklw?token=1531586958&lang=zh_CN*

```

Your task is to review customer questions and categorize them into one of the following 4 types of problems.

The review steps are as follows, please perform step by step:

1. Extract three keywords from customer questions and translate them into English. Please connect the three keywords with commas to make it a complete JSON value.

2. Summarize the customer’s questions in 15 more words and in English.

3. Categorize the customer’s questions based on Review text and summary. Category list:
    • Technical issue: customer is experiencing server-side issues, client errors or product limitations. Example: "I'm having trouble logging into my account. It keeps saying there's a server error."
    • Product inquiry: customer would like to know more details about the product or is asking questions about how to use it. Example: "Can you provide more information about the product and how to use it?"
    • Application status: customer is requesting to check the status of their Azure OpenAI, GPT-4 or DALLE application. Example: "What is the status of my Azure OpenAI application?"
    • Unknown: if you only have a low confidence score to categorize. Example: "I'm not sure if this is the right place to ask, but I have a question about billing."

Provide them in JSON format with the following keys: Case id; Key-words; Summary; Category. Please generate only one JSON structure per review.

Please show the output results - in a table, the table is divided into four columns: Case ID, keywords, Summary, Category.
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWf6Iogb0ScBpSFibiavMUk2TohHj9WylLC68Q6yDGOS8hG6PHWqiavicIVNbFbVCWYeKEBMDQ1eg3hRA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)




## Demo1: Lenovo ThinkPad Product

I have a Lenovo ThinkPad product manual, and I want to build a RAG (Retrieval-Augmented Generation) system based on it. The document includes up to dozens of product models, many of which have very similar names. Moreover, the document is nearly 900 pages long. Therefore, to construct a RAG system based on this document and provide precise answers, I need to address the following issues:

1. **How to split the document;**
2. **How to avoid loss of relevance;**
3. **How to resolve information discontinuity;**
4. **The problem of low search accuracy due to numerous similar products;**
5. **The challenge of diverse questioning on the system's generalization ability.**

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/6.png)

In the end, I chunked the document based on the product models and set more effective prompts, so that the RAG (Retrieval-Augmented Generation) system can accurately answer questions.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/7.png)



System prompt

```
You are an AI assistant that helps people answer the question of Lenovo product.
Please be patient and try to answer your questions in as much detail as possible and give the reason. When you use reference documents, please list the file names directly, not only Citation 1, should be ThinkPad E14 Gen 4 (AMD).pdf.txt eg.

```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/3.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/4.png)

Index format is as following:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/5.png)



Final Result：

***Please click below pictures to see my demo vedios on Yutube***:
[![RAG-DEMO1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/4DyI6n5UrKw)



## Demo 2: Text and Image Hybrid Search

There is a Microsoft D365 CSS support document.

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/10.png)

The doc has has words and images, I create 2 index for it, one is for whole doc, another is for images from this doc:

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/11.png)

Then I write a Python program, do hybrid search on 2 index

``` 
# Azure AI Search配置  
search_service_url = 'https://ai-search-eastus-xinyuwei.search.windows.net'  
search_api_version = '2024-11-01-preview'  
search_api_key = '*'  # 替换为您的实际 Search API 密钥  
text_index_name = 'azureblob-index'  
image_index_name = 'vector-1734168453283'  
  
# Azure OpenAI配置  
openai_endpoint = 'https://aoai-eastus2111.openai.azure.com/openai/deployments/gpt-4o-2/chat/completions?api-version=2024-08-01-preview'  
openai_api_key = '*'  # 替换为您的实际 OpenAI API 密钥  
  
# Azure Blob Storage配置  
blob_service_client = BlobServiceClient(  
    account_url="https://sasasasasa111111.blob.core.windows.net/",  
    credential="*"  # 替换为您的实际 Blob 存储账户密钥  
)  
  
def generate_sas_token(container_name, blob_name):  
    sas_token = generate_blob_sas(  
        account_name=blob_service_client.account_name,  
        container_name=container_name,  
        blob_name=blob_name,  
        account_key=blob_service_client.credential.account_key,  
        permission=BlobSasPermissions(read=True),  
        expiry=datetime.utcnow() + timedelta(hours=1)  # 设置SAS令牌的过期时间  
    )  
    return sas_token  
  
def search_index(index_name, query, top=2):  
    url = f"{search_service_url}/indexes/{index_name}/docs/search?api-version={search_api_version}"  
    headers = {  
        'Content-Type': 'application/json',  
        'api-key': search_api_key  
    }  
    data = {  
        "search": query,  
        "top": top  # 限制返回的结果数量  
    }  
    response = requests.post(url, headers=headers, data=json.dumps(data))  
    return response.json()  
  
def query_gpt4(messages):  
    headers = {  
        'Content-Type': 'application/json',  
        'api-key': openai_api_key  
    }  
    data = {  
        "messages": messages,  
        "max_tokens": 4096  
    }  
    response = requests.post(openai_endpoint, headers=headers, data=json.dumps(data))  
  
    # 检查响应状态码  
    if response.status_code != 200:  
        print(f"请求失败，状态码：{response.status_code}")  
        print(f"响应内容：{response.text}")  
        return None  
  
    return response.json()  
  
def process_question(question):  
    # 查询图片索引  
    image_results = search_index(image_index_name, question)  
  
    # 查询文本索引  
    text_results = search_index(text_index_name, question)  
  
    # 汇总结果并分配权重  
    combined_results = []  
  
    # 假设图片结果权重为0.6，文本结果权重为0.4  
    image_weight = 0.6  
    text_weight = 0.4  
  
    # 为结果添加类型标记  
    for result in image_results.get('value', []):  
        result['weighted_score'] = result.get('@search.score', 0) * image_weight  
        result['result_type'] = 'image'  # 添加类型标记  
        combined_results.append(result)  
  
    for result in text_results.get('value', []):  
        result['weighted_score'] = result.get('@search.score', 0) * text_weight  
        result['result_type'] = 'text'  # 添加类型标记  
        combined_results.append(result)  
  
    # 根据加权得分排序  
    combined_results.sort(key=lambda x: x['weighted_score'], reverse=True)  
  
    # 构建GPT-4的输入  
    system_prompt = {  
        "role": "system",  
        "content": (  
            "You are an AI chatbot that helps Lenovo employees answer questions related to Lenovo processes. "  
            "1. You need to respond in the same language as the user's question. For example, if the user asks in Chinese, you should respond in Chinese. "  
            "2. When answering questions, please proactively mention the name and link of the reference document. "  
            "If it is a flowchart, you need to specifically point out the location of the flowchart, as we need to render the image using markdown，So if it's a flowchart, you need to get the address of the flowchart image, not the address of the document it's in, otherwise you can't render it."  
        )  
    }  
  
    user_prompt = {"role": "user", "content": question}  
    combined_results_prompt = {"role": "system", "content": json.dumps(combined_results[:5], indent=2, ensure_ascii=False)}  
  
    messages = [system_prompt, user_prompt, combined_results_prompt]  
  
    # 提交给GPT-4  
    gpt4_response = query_gpt4(messages)  
  
    # 检查响应内容  
    if gpt4_response is None or 'choices' not in gpt4_response:  
        print("GPT-4响应中没有'choices'键")  
        return "无法获取答案，请稍后再试。", []  
  
    # 获取GPT-4的答案  
    answer = gpt4_response['choices'][0]['message']['content']  
  
    # 生成SAS URL  
    urls = []  
    for result in combined_results:  
        if result.get('result_type') == 'image' and 'metadata_storage_path' in result:  
            blob_url = result['metadata_storage_path']  
            if blob_url:  
                parts = blob_url.split('/')  
                if len(parts) >= 2:  
                    container_name, blob_name = parts[-2], parts[-1]  
                    try:  
                        sas_token = generate_sas_token(container_name, blob_name)  
                        sas_url = f"{blob_url}?{sas_token}"  
                        urls.append(sas_url)  
                    except Exception as e:  
                        print(f"生成SAS令牌时出错：{e}")  
                else:  
                    print(f"Blob URL '{blob_url}' 格式不正确。")  
            else:  
                print("Blob URL 为空。")  
  
    return answer, urls  
  
def display_image(url):  
    try:  
        # 发送HTTP请求获取图片  
        response = requests.get(url)  
  
        # 检查请求是否成功  
        if response.status_code == 200:  
            # 将图片数据转换为字节流  
            image_data = BytesIO(response.content)  
  
            # 使用PIL打开图片  
            image = Image.open(image_data)  
  
            # 使用matplotlib展示图片  
            plt.imshow(image)  
            plt.axis('off')  # 关闭坐标轴  
            plt.show()  
        else:  
            print(f"无法从 {url} 获取图片。HTTP 状态码：{response.status_code}")  
    except Exception as e:  
        print(f"从 {url} 获取图片时发生错误：{e}")  
  
def extract_image_urls_from_markdown(markdown_text):  
    # 使用正则表达式提取Markdown中的图片链接  
    pattern = r'!\[.*?\]\((.*?)\)'  
    return re.findall(pattern, markdown_text)  
```

Run following script and input question

```
if __name__ == "__main__":  
    question = input("请输入您的问题：")  
    answer, urls = process_question(question)  
    print(f"问题：{question}")  
    print(f"回答：{answer}")  
  
    # 提取并展示回答中的图片链接  
    image_urls = extract_image_urls_from_markdown(answer)  
    for image_url in image_urls:  
        display_image(image_url)  
  
    print("相关链接：")  
    for url in urls:  
        print(url)  
```

![images](https://github.com/xinyuwei-david/david-share/blob/master/Agents/RAG-Best-Practice/images/12.png)