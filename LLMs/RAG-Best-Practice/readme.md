# RAG-Best-Practice

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

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/1.png)

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

**Refer to**: *https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity*

**(1) Service Tiers and Capacity**

- **Service Tiers**: For example, Azure AI Search's Standard S1 and S2 tiers offer different performance levels and storage capacities.

- **Replicas and Partitions**: Increasing replicas improves query throughput; increasing partitions enhances index capacity and query performance.

  

  **(2) Performance Optimization Tips**

- **Upgrade Service Tier**: Upgrading from Standard S1 to S2 can provide higher performance and storage capacity.

- **Increase Partitions and Replicas**: Adjust based on query load and index size.

- **Avoid Complex Queries**: Reduce the use of high-overhead queries, such as regular expression queries.

- **Query Optimization**: Retrieve only the required fields, limit the amount of data returned, and use search functions rather than complex filters.

  ![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/2.png)


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


## Application Case: RAG Practice in Azure AI Search

### Tips for Improving Azure AI Search Performance

- **Index Size and Architecture**: Regularly optimize the index; remove unnecessary fields and documents.
- **Query Design**: Optimize query statements to reduce unnecessary scanning and computation.
- **Service Capacity**: Adjust replicas and partitions appropriately based on query load and index size.
- **Avoid Complex Queries**: Reduce the use of high-overhead queries, such as regular expression queries.

### Chunking Large Documents

- **Use Built-in Text Splitting Skills**: Choose modes like `pages` or `sentences` based on needs.
- **Adjust Parameters**: Set appropriate `maximumPageLength`, `pageOverlapLength`, etc., based on document characteristics.
- **Use Tools Like LangChain**: For more flexible chunking and embedding operations.

### Query Rewriting and the New Semantic Reranker

- **Query Rewriting**: Improve recall rate and accuracy by rewriting user queries.
- **Semantic Reranker**: Use cross-encoders to re-rank candidate results, enhancing result relevance.

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/8.png)

## RAG demo of Lenovo ThinkPad Product

I have a Lenovo ThinkPad product manual, and I want to build a RAG (Retrieval-Augmented Generation) system based on it. The document includes up to dozens of product models, many of which have very similar names. Moreover, the document is nearly 900 pages long. Therefore, to construct a RAG system based on this document and provide precise answers, I need to address the following issues:

1. **How to split the document;**
2. **How to avoid loss of relevance;**
3. **How to resolve information discontinuity;**
4. **The problem of low search accuracy due to numerous similar products;**
5. **The challenge of diverse questioning on the system's generalization ability.**

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/6.png)

In the end, I chunked the document based on the product models and set more effective prompts, so that the RAG (Retrieval-Augmented Generation) system can accurately answer questions.

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/7.png)



System prompt

```
You are an AI assistant that helps people answer the question of Lenovo product.
Please be patient and try to answer your questions in as much detail as possible and give the reason. When you use reference documents, please list the file names directly, not only Citation 1, should be ThinkPad E14 Gen 4 (AMD).pdf.txt eg.

```

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/3.png)

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/4.png)

Index format is as following:

![images](https://github.com/xinyuwei-david/david-share/blob/master/LLMs/RAG-Best-Practice/images/4.png)



Final Result：

***Please click below pictures to see my demo vedios on Yutube***:
[![RAG-DEMO1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/4DyI6n5UrKw)