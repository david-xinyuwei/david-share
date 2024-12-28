
# graphrag configure and validation
**Notice:**
graphrag is a Microsoft opensource project, link:
***https://github.com/microsoft/graphrag.git***


## Result show
The final graph generated during the test is under ***results*** directory：
- results/graph.graphml is a graph that  could loaded by Gephi software.

This knowledge graph was created by using the Chinese novel *Romance of the Three Kingdoms* as the foundational data.

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/1.png)

***Please click below pictures to see my demo vedios on Yutube***:
[![GraphRAG-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/CvCONQzhrp8)


## graphrag implementation logic
Global Query：
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/5.png)

##### Input:
- User Query
- Conversation History

##### Processing Flow:

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/12.png)

The user query and conversation history are divided into multiple batches (Shuffled Community Report Batch 1, 2, ..., N).
Each batch generates an intermediate response (Rated Intermediate Response 1, 2, ..., N).
These intermediate responses are ranked and filtered (Ranking + Filtering).
The final intermediate responses are aggregated (Aggregated Intermediate Responses).
The final response is returned (Response).

- Characteristics:

Global search involves processing multiple batches, with each batch independently generating an intermediate response.

Multiple intermediate responses need to be aggregated to generate the final response.
Suitable for scenarios that require searching and aggregating information on a large scale.

Local Query：
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/6.png)

##### Input:
- User Query
- Conversation History

##### Processing Flow:
The user query and conversation history are used to extract entities (Extracted Entities).
The extracted entities are mapped to different candidates (Candidate Text Units, Candidate Community Reports, Candidate Entities, Candidate Relationships, Candidate Covariates).
Each candidate is ranked and filtered (Ranking + Filtering), generating prioritized candidates (Prioritized Text Units, Prioritized Community Reports, Prioritized Entities, Prioritized Relationships, Prioritized Covariates).
The final prioritized candidates are integrated, and the final response is returned (Response).

##### Characteristics:
Local search focuses more on entity extraction and mapping.
The processing flow is more detailed, involving multiple different types of candidates.
Suitable for scenarios that require detailed search and analysis of specific entities or relationships.

#### Summary
- Global Search:

Broader processing scope, involving multiple batches of processing and aggregation.
Suitable for scenarios that require searching and aggregating information on a large scale.
- Local Search:

More detailed processing flow, focusing on entity extraction and mapping.
Suitable for scenarios that require detailed search and analysis of specific entities or relationships.

These two search methods have significant differences in their underlying implementation, mainly in the processing flow and data aggregation methods. Global search is more suitable for large-scale search and information aggregation, while local search is more suitable for detailed entity and relationship search.

## graphrag Search system Prompt
The search process of GlobalSearch and LocalSearch primarily relies on a large language model (LLM) to generate answers. Below is how it guides the LLM in generating search results.

```
(gg3) root@davidgpt:~/ragtest/prompts# ls
claim_extraction.txt  drift_search_system_prompt.txt  global_search_knowledge_system_prompt.txt  global_search_reduce_system_prompt.txt  question_gen_system_prompt.txt
community_report.txt  entity_extraction.txt           global_search_map_system_prompt.txt        local_search_system_prompt.txt          summarize_descriptions.txt
```

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/11.png)

###  graphrag Search system input and output file

```
(gg3) root@davidgpt:~/ragtest# ls -al input/
total 1784
drwxr-xr-x 2 root root    4096 Dec 26 12:32 .
drwxr-xr-x 7 root root    4096 Dec 27 13:55 ..
-rw-r--r-- 1 root root 1806411 Dec 26 12:31 book.txt
(gg3) root@davidgpt:~/ragtest# ls -al output/
total 10124
drwxr-xr-x 3 root root    4096 Dec 26 14:40 .
drwxr-xr-x 7 root root    4096 Dec 27 13:55 ..
-rw-r--r-- 1 root root  482476 Dec 26 14:31 create_final_communities.parquet
-rw-r--r-- 1 root root 3941374 Dec 26 14:40 create_final_community_reports.parquet
-rw-r--r-- 1 root root 1335205 Dec 26 14:09 create_final_documents.parquet
-rw-r--r-- 1 root root  650393 Dec 26 14:31 create_final_entities.parquet
-rw-r--r-- 1 root root  263620 Dec 26 14:32 create_final_nodes.parquet
-rw-r--r-- 1 root root 1126498 Dec 26 14:31 create_final_relationships.parquet
-rw-r--r-- 1 root root 1855868 Dec 26 14:32 create_final_text_units.parquet
-rw-r--r-- 1 root root  679181 Dec 26 14:31 graph.graphml
drwxr-xr-x 5 root root    4096 Dec 26 14:42 lancedb
-rw-r--r-- 1 root root    1764 Dec 26 14:42 stats.json
```



### Global Search System
The global search system typically needs to handle large volumes of data, which may be distributed across multiple sources or batches. To efficiently process and integrate this data, the global search system employs two stages: MAP and REDUCE.
#### MAP Stage
MAP_SYSTEM_PROMPT: In this stage, the system generates a list of key points, each with a description and an importance score. The main purpose of this stage is to extract useful information from large datasets and organize it into a manageable format (e.g., JSON).
Goal: Extract and preliminarily process data to generate a structured list of key points.
#### REDUCE Stage
REDUCE_SYSTEM_PROMPT: In this stage, the system synthesizes reports from multiple analysts, removes irrelevant information, and merges the cleaned information into a comprehensive answer. The main purpose of this stage is to integrate and refine the data to produce the final response.
Goal: Integrate and refine data to generate a comprehensive and detailed answer.

By processing data in stages, the global search system can more effectively handle large and complex datasets, ensuring that the final response is both comprehensive and accurate.
### Local Search System
The local search system typically deals with smaller volumes of data, and the data sources are relatively concentrated. Therefore, the local search system only needs one prompt to complete data processing and response generation:

#### LOCAL_SEARCH_SYSTEM_PROMPT
This prompt is responsible for extracting information from the provided data tables, generating a response that meets the target length and format, and incorporating relevant general knowledge.
Goal: Directly extract information from the data tables and generate a response.

Since the local search system handles smaller datasets, data processing and response generation can be completed in a single step, eliminating the need for separate MAP and REDUCE stages.

### Summary
The global search system uses both MAP and REDUCE prompts to efficiently process and integrate large and complex datasets, while the local search system only requires one prompt due to the smaller volume of data it handles. This design allows each system to work efficiently within its specific application context.

## Global and Local Query differences in Code Implementation
##### URL Differences:
The URL for the global_search function is endpoint + "/query/global".
The URL for the local_search function is endpoint + "/query/local".
This means that global_search and local_search use different API endpoints.
##### Function Comments:
The comment for global_search indicates that it performs a global query on the knowledge graph.
The comment for local_search indicates that it performs a local query on the knowledge graph.

##### Similarities in Code Implementation
- Parameters:

Both functions accept index_name and query as parameters.
index_name can be a string or a list of strings, representing the index names to query.
query is the query string.
- Request Method:

Both functions use the requests.post method to send an HTTP POST request.
The request body (json=request) for both functions includes index_name and query.
- Return Value:

Both functions return a requests.Response object.

##### Summary
The main difference between global_search and local_search is the API endpoint they call: one performs a global query, and the other performs a local query.In other aspects, such as parameters, request method, and return value, the two functions are identical.

## How to fast install
Graphrag is a rapidly developing open-source project with frequent version updates. If you want to quickly create a Proof of Concept (PoC) to understand its features, you can refer to: https://microsoft.github.io/graphrag/get_started/. With this deployment method, Parquet files won't be stored in the database but will exist on the local file system. However, in my PoC, I found that if you use AOAI GPT-4O, the query speed is also very fast. If you want to deploy Graphrag into a production environment, you need to consider high availability and storing Parquet files in a database. You can refer to: https://github.com/Azure-Samples/graphrag-accelerator.

The architecture diagram is shown below:
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/2.png)



### Note

- **Schema Changes in Version 0.5.0**: Starting from Graphrag version 0.5.0, the schema has undergone changes due to the introduction of features like **drift search** and **community embedding**. This has resulted in differences in fields such as `name` and `title`.

- **Incremental Updates**: Version 0.5.0 and above support incremental updates by maintaining consistent entity IDs. This allows for **insert-update merge operations** in the database, enabling incremental updates without the need to delete and reload data. In earlier versions, IDs were not consistent, necessitating a complete reload for updates.

- **Drift Search and Global Search Performance**: Drift search was added to improve the performance of global searches by utilizing local search methods to achieve global search effects. However, both global search and drift search can consume a large number of tokens, leading to **429 errors** (Too Many Requests), especially when dealing with large graphs. This makes them inefficient for very large datasets.

- **Version Stability Concerns**: The Graphrag project is evolving rapidly, and versions after **1.0** may have addressed some of the token consumption and performance issues. However, the fast pace of changes may introduce other challenges, and thorough testing is recommended.

- **Parquet File Generation**: After updating the original data files, it's necessary to **rerun the processing pipeline** to regenerate the Parquet files. In some versions, the intermediary Parquet files may not be generated automatically as before.

- **Localization and Prompt Tuning**: By default, Graphrag indexes content in English, even if the source material is in another language (e.g., Chinese). To have the generated relationship graphs display in the desired language, it's important to adjust the prompts in Graphrag, possibly through **command-line prompt tuning**.

- **Token Consumption Issues**: Both global search and drift search consume a significant number of tokens, making them inefficient for large-scale graphs. This necessitates careful consideration when deploying Graphrag in production environments with extensive datasets.

  

### Simple Installation

Refer to: https://microsoft.github.io/graphrag/get_started/

When installing the Graphrag library, please note that its version often changes; it is now at version 1.0.

```
pip install graphrag
```

```
(gg3) root@davidgpt:~/ragtest# pip show graphrag
Name: graphrag
Version: 1.0.1
Summary: GraphRAG: A graph-based retrieval-augmented generation (RAG) system.
Home-page:
Author: Alonso Guevara Fernández
Author-email: alonsog@microsoft.com
License: MIT
Location: /root/anaconda3/envs/gg3/lib/python3.11/site-packages
Requires: aiofiles, azure-identity, azure-search-documents, azure-storage-blob, datashaper, devtools, environs, fnllm, future, graspologic, httpx, json-repair, lancedb, matplotlib, networkx, nltk, numpy, openai, pandas, pyaml-env, pyarrow, pydantic, python-dotenv, pyyaml, rich, tenacity, tiktoken, tqdm, typer, typing-extensions, umap-learn
Required-by:
```

Create a directory and place text `.txt` files inside; you can include any text documents in `.txt` format, but you need to pay attention to the encoding.

```
mkdir -p ./ragtest/input
curl https://www.gutenberg.org/cache/epub/24022/pg24022.txt -o ./ragtest/input/book.txt
```

Sometimes, Chinese documents use the GB18030 encoding, which is a commonly used encoding that supports both traditional and simplified Chinese characters. You can convert `book.txt` to UTF-8 encoding so that you don't need to specify a special encoding in your program.

Use the `iconv` tool to convert the file encoding:

```
#iconv -f gb18030 -t utf-8 book.txt -o book_utf8.txt  
```

```

(gg3) root@davidgpt:~/ragtest/input# cat 2.py
encodings = ['utf-8', 'gb18030', 'gbk', 'gb2312', 'big5']

for enc in encodings:
    try:
        with open('book.txt', 'r', encoding=enc) as f:
            content = f.read()
            print(f"\n使用编码 {enc} 读取成功！")
            print("文件内容预览：")
            print(content[:500])  # 打印前500个字符
            break
    except Exception as e:
        print(f"使用编码 {enc} 读取失败：{e}")
(gg3) root@davidgpt:~/ragtest/input#
(gg3) root@davidgpt:~/ragtest/input# python 2.py

使用编码 utf-8 读取成功！
文件内容预览：
《三国演义》（精校版全本）作者：罗贯中


内容简介
```

To initialize your workspace, first run the `graphrag init` command. Since we have already configured a directory named `./ragtest` in the previous step, run the following command:

```
graphrag init --root ./ragtest
```

This will create two files: `.env` and `settings.yaml` in the `./ragtest` directory.

```
(gg3) root@davidgpt:~/ragtest# cat  .env
GRAPHRAG_API_KEY=A***vw
```

```
(gg3) root@davidgpt:~/ragtest# cat  settings.yaml
### This config file contains required core defaults that must be set, along with a handful of common optional settings.
### For a full list of available settings, see https://microsoft.github.io/graphrag/config/yaml/

### LLM settings ###
## There are a number of settings to tune the threading and token limits for LLM calls - check the docs.

encoding_model: cl100k_base # this needs to be matched to your model!

llm:
  api_key: ${GRAPHRAG_API_KEY} # set this in the generated .env file
  type: azure_openai_chat
  model: gpt-4o
  model_supports_json: true # recommended if this is available for your model.
  # audience: "https://cognitiveservices.azure.com/.default"
  api_base: https://ai-xinyuwei8714ai888427144375.cognitiveservices.azure.com/
  api_version: '2024-08-01-preview'
  # organization: <organization_id>
  deployment_name: gpt-4o-1120

parallelization:
  stagger: 0.3
  # num_threads: 50

async_mode: threaded # or asyncio

embeddings:
  async_mode: threaded # or asyncio
  vector_store:
    type: lancedb
    db_uri: 'output/lancedb'
    container_name: default
    overwrite: true
  llm:
    api_key: ${GRAPHRAG_API_KEY}
    type: azure_openai_embedding
    model: text-embedding-3-small
    api_base: https://ai-xinyuwei8714ai888427144375.cognitiveservices.azure.com/
    api_version: '2023-05-15'
    # audience: "https://cognitiveservices.azure.com/.default"
    # organization: <organization_id>
    deployment_name: text-embedding-3-small

### Input settings ###

input:
  type: file # or blob
  file_type: text # or csv
  base_dir: "input"
  file_encoding: utf-8
  file_pattern: ".*\\.txt$"

chunks:
  size: 1200
  overlap: 100
  group_by_columns: [id]

### Storage settings ###
## If blob storage is specified in the following four sections,
## connection_string and container_name must be provided

cache:
  type: file # or blob
  base_dir: "cache"

reporting:
  type: file # or console, blob
  base_dir: "logs"

storage:
  type: file # or blob
  base_dir: "output"

## only turn this on if running `graphrag index` with custom settings
## we normally use `graphrag update` with the defaults
update_index_storage:
  # type: file # or blob
  # base_dir: "update_output"

### Workflow settings ###

skip_workflows: []

entity_extraction:
  prompt: "prompts/entity_extraction.txt"
  entity_types: [organization,person,geo,event]
  max_gleanings: 1

summarize_descriptions:
  prompt: "prompts/summarize_descriptions.txt"
  max_length: 500

claim_extraction:
  enabled: false
  prompt: "prompts/claim_extraction.txt"
  description: "Any claims or facts that could be relevant to information discovery."
  max_gleanings: 1

community_reports:
  prompt: "prompts/community_report.txt"
  max_length: 2000
  max_input_length: 8000

cluster_graph:
  max_cluster_size: 10

embed_graph:
  enabled: true # if true, will generate node2vec embeddings for nodes

umap:
  enabled: true # if true, will generate UMAP embeddings for nodes

snapshots:
  graphml: true
  embeddings: false
  transient: false

### Query settings ###
## The prompt locations are required here, but each search method has a number of optional knobs that can be tuned.
## See the config docs: https://microsoft.github.io/graphrag/config/yaml/#query

local_search:
  prompt: "prompts/local_search_system_prompt.txt"

global_search:
  map_prompt: "prompts/global_search_map_system_prompt.txt"
  reduce_prompt: "prompts/global_search_reduce_system_prompt.txt"
  knowledge_prompt: "prompts/global_search_knowledge_system_prompt.txt"

drift_search:
  prompt: "prompts/drift_search_system_prompt.txt"
```

Finally we'll run the pipeline!

```
graphrag index --root ./ragtest
```

I write a script to check the parquet file:

```
(gg3) root@davidgpt:~/ragtest/output# cat inspect_parquet2.py
import pyarrow.parquet as pq
import pandas as pd

def inspect_parquet_file(parquet_file_path):
    print(f"正在检查文件：{parquet_file_path}\n")

    # 使用 PyArrow 读取 Parquet 文件的模式
    try:
        parquet_file = pq.ParquetFile(parquet_file_path)
        schema = parquet_file.schema
        print("Parquet 文件的模式：")
        print(schema)
        print("\n")
    except Exception as e:
        print(f"读取 Parquet 文件模式时出错：{e}")
        return

    # 使用 Pandas 加载 Parquet 文件并打印列名
    try:
        df = pd.read_parquet(parquet_file_path)
        print("数据框的列名：")
        print(df.columns.tolist())
        print("\n")

        # 设置 Pandas 显示选项，确保完整显示所有数据
        pd.set_option('display.max_columns', None)       # 显示所有列
        pd.set_option('display.max_colwidth', None)      # 列内容不截断
        pd.set_option('display.width', 1000)             # 设置显示的总宽度为1000

        # 选择指定的列
        selected_columns = ['id', 'human_readable_id', 'source', 'target', 'description', 'weight', 'combined_degree', 'text_unit_ids']
        df_selected = df[selected_columns]

        # 显示前十五行数据
        print("前十五行数据：")
        print(df_selected.head(15))

        # 将选定的字段保存为新的 Parquet 文件（可选）
        output_parquet = '/root/ragtest/output/selected_columns.parquet'
        df_selected.to_parquet(output_parquet, index=False)
        print(f"\n选定的字段已保存到 {output_parquet}")

        # 将前十五行数据保存到文本文件
        output_text = '/root/ragtest/output/output.txt'
        with open(output_text, 'w', encoding='utf-8') as f:
            f.write(df_selected.head(15).to_string(index=False))
        print(f"\n前十五行数据已保存到 {output_text}")

    except Exception as e:
        print(f"读取 Parquet 文件数据时出错：{e}")

if __name__ == "__main__":
    # 修改为您的 Parquet 文件路径
    parquet_file_path = '/root/ragtest/output/create_final_relationships.parquet'

    inspect_parquet_file(parquet_file_path)
(gg3) root@davidgpt:~/ragtest/output#
(gg3) root@davidgpt:~/ragtest/output# python inspect_parquet2.py
正在检查文件：/root/ragtest/output/create_final_relationships.parquet

Parquet 文件的模式：
<pyarrow._parquet.ParquetSchema object at 0x79d1c73bf880>
required group field_id=-1 schema {
  optional binary field_id=-1 id (String);
  optional int64 field_id=-1 human_readable_id;
  optional binary field_id=-1 source (String);
  optional binary field_id=-1 target (String);
  optional binary field_id=-1 description (String);
  optional double field_id=-1 weight;
  optional int64 field_id=-1 combined_degree;
  optional group field_id=-1 text_unit_ids (List) {
    repeated group field_id=-1 list {
      optional binary field_id=-1 element (String);
    }
  }
}



数据框的列名：
['id', 'human_readable_id', 'source', 'target', 'description', 'weight', 'combined_degree', 'text_unit_ids']


前十五行数据：
                                      id  human_readable_id source target         description  weight  combined_degree
                                                         text_unit_ids
0   b8294119-a80d-400d-8a82-02151e970d00                  0    罗贯中   三国演义       罗贯中是《三国演义》的作者    10.0                7  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
1   aab04773-c063-4922-a886-7e76279c76b8                  1     东汉   黄巾起义         黄巾起义发生在东汉末年     9.0               43  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
2   71d42882-800a-4b3b-9a5b-dea030cac458                  2     东汉      魏  魏是东汉末年分裂后形成的政治军事集团     8.0               39  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
3   ea998eb7-5eb5-47a7-9737-02e782e43f2a                  3     东汉      蜀  蜀是东汉末年分裂后形成的政治军事集团     8.0               53  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
4   9a966936-5bad-4d1f-a85a-89c39d1bf3f8                  4     东汉      吴  吴是东汉末年分裂后形成的政治军事集团     8.0               31  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
5   5a807ad7-c432-4399-a737-89f42da1c764                  5     东汉     洛阳            洛阳是东汉的都城     7.0               61  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
6   d1c28321-b588-4ed9-9d27-eb4b724021fc                  6     东汉     桓帝          桓帝是东汉末年的皇帝     7.0               24  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
7   c6a4f7b8-5a8d-4819-951c-aab5eaa24aec                  7     东汉     灵帝          灵帝是东汉末年的皇帝     7.0               34  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
8   1c1e381b-dc4e-4803-844d-5c07102adb03                  8     东汉     窦武         窦武是东汉末年的大将军     6.0               24  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
9   ba730216-ed35-435c-bdd3-5d15ec098813                  9     东汉     陈蕃          陈蕃是东汉末年的太傅     6.0               24  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
10  8cb073ee-5e07-4bbc-bf2e-dd506ddff65b                 10     东汉     曹节          曹节是东汉末年的宦官     6.0               27  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
11  1998adde-6bc1-4285-9dc2-be7e9c340a52                 11     东汉     献帝        献帝是东汉的最后一位皇帝     8.0               46  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
12  155214fd-5c1f-4db7-bd60-6906de5fd265                 12     东汉    光武帝         光武帝是东汉的开国皇帝     8.0               22  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
13  95a5c7d3-15e1-4fc0-8516-bc8bcfb46d7b                 13     东汉     建宁          建宁是东汉的一个年号     7.0               24  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]
14  e0620b66-5a10-4193-a099-c06f380719de                 14     东汉   洛阳地震      洛阳地震是东汉末年的一场灾害     6.0               22  [7ca24114b9a3c2bba48438bb3029d8e317b3f76e7d429881d5f5a5594860c7fffa1041f3ebdf1f7241127a99292ea771a82c2f29bfdab7b094ffc07c4e8b6875]

选定的字段已保存到 /root/ragtest/output/selected_columns.parquet

前十五行数据已保存到 /root/ragtest/output/output.txt
```





Next, we can perform global and local search.

```\
graphrag query \ --root ./ragtest \ --method global \ --query "What are the top themes in this story?"
graphrag query \ --root ./ragtest \ --method local \ --query "Who is Scrooge and what are his main relationships?"
```

 Refer to the following steps to generate graph diagrams using Gephi software:

https://microsoft.github.io/graphrag/visualization_guide/

### graphrag-accelerator

####  Step1: follow this guide to install env on Azure.

Deploy guide:
***https://github.com/Azure-Samples/graphrag-accelerator/blob/main/docs/DEPLOYMENT-GUIDE.md***

When onfigure deploy parameters, refer to following:
```
(base) root@davidwei:~/graphrag-accelerator/infra# cat deploy.parameters.json
{
  "GRAPHRAG_API_BASE": "https://****.openai.azure.com/",
  "GRAPHRAG_API_VERSION": "2024-02-15-preview",
  "GRAPHRAG_EMBEDDING_DEPLOYMENT_NAME": "text-embedding-ada-002",
  "GRAPHRAG_EMBEDDING_MODEL": "text-embedding-ada-002",
  "GRAPHRAG_LLM_DEPLOYMENT_NAME": "4turbo",
  "GRAPHRAG_LLM_MODEL": "gpt-4",
  "LOCATION": "eastus2",
  "RESOURCE_GROUP": "davidAI"
```

Installation will take ~40-50 minutes to deploy.Don't worry that the installation didn't work all at once, when the install command is initiated again, the script will first check for already installed components and then continue with the installation.


####  Step2: Get the URL and key to APIM as an API for Graphrag.
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/3.png)

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/4.png)

####  Step3: run test
Refer to following link to create a dataset:

***https://github.com/Azure-Samples/graphrag-accelerator/tree/main/notebooks***

Then run ipynb file 


## Ipynb file Results analyze

### In 1-Quickstart.ipynb
In this ipynb file, apart from the basic configuration, the main comparison is made by global and local search.



In response to an identical question:
prompt："Who are the primary actors in Alaska and California communities?"  

Global query result：
```
### Primary Actors in Alaska

#### Government and Legislative Influence
In Alaska, the Alaska State Legislature holds significant responsibilities, managing both legislative and judicial duties. This body plays a crucial role in overseeing the distribution of dividends from the Permanent Fund's growth to eligible Alaskans, directly impacting the financial well-being of the residents [Data: Reports (135, 133)].

#### Educational and Cultural Institutions
The University of Alaska system is a key educational actor, with initiatives like the Alaska Scholars Program aimed at retaining high-achieving students within the state [Data: Reports (107, 54)]. Cultural influences include the Russian Orthodox Church, which plays a central role in the cultural communities of Alaska [Data: Reports (61)].

#### Environmental and Land Management
Environmental management and land use are significantly influenced by entities such as the Arctic National Wildlife Refuge, Pebble Mine, and various U.S. federal agencies including the United States Fish and Wildlife Service and the Bureau of Land Management [Data: Reports (55)].

#### Transportation and Infrastructure
Alaska Airlines and the Essential Air Service Program are crucial for providing air connectivity, especially to remote areas and regional hubs, facilitating both local and external mobility [Data: Reports (98)].

#### Indigenous and Cultural Representation
The Tsimshian people and the settlement on Annette Island represent key cultural and historical actors, embodying the interests of indigenous communities in Alaska [Data: Reports (114)].

### Primary Actors in California

#### Political and Legislative Dominance
The Democratic Party holds a supermajority in the California state legislature, significantly shaping state policies and governance. Governor Gavin Newsom also plays a pivotal role in representing the state government and influencing policies [Data: Reports (130)].

#### Judicial and Legal Framework
The State Judiciary, the Judicial Council, and the State Bar of California are significant actors in governing California's judiciary system, affecting legal outcomes and practices across the state [Data: Reports (136, 134)].

#### Energy Infrastructure
Entities like PATH 46 and natural gas-fired power plants are crucial for energy transmission and form a vital part of the state's energy infrastructure, influencing both economic and environmental aspects [Data: Reports (29)].

#### Media and Economic Influence
Major American Television Commercial Broadcast Networks impact the media landscape, while the Congressional Research Service plays a role in shaping economic policies [Data: Reports (117, 127)].

#### Cultural and Social Movements
The proponents of the English-Only Movement and California Proposition 63 have significantly shaped language policies and social dynamics within the state [Data: Reports (34)].

These actors collectively contribute to the unique political, environmental, cultural, and economic landscapes of Alaska and California, each playing specialized roles that influence various aspects of life in these states.

### Primary Actors in California

California's landscape of primary actors is diverse, spanning economic, technological, educational, and entertainment sectors. The State of California, Silicon Valley, and the University of California system are pivotal in driving the state's economy and technological and educational advancements [Data: Reports (42, 41, 30)]. Caltrans manages state transportation, while the Judicial Council oversees judiciary administration [Data: Reports (8, 26)]. The entertainment industry is significantly influenced by Hollywood and the 'Big Five' film studios [Data: Reports (12)]. Historical contributions are noted with Father-President Serra's establishment of Spanish missions, which influenced the development of major cities [Data: Reports (22)]. The California Community Colleges System and the California State University system are key in providing educational services and pathways for higher education [Data: Reports (13)].

These actors collectively contribute to the robust functionality and development of their respective states, addressing various sectoral needs and enhancing regional connectivity and growth.

```
Local query result：
```
# Analysis of Primary Actors in Alaska and California Communities

## Alaska

### Indigenous Communities
Indigenous peoples, including Alaska Natives, are pivotal actors in Alaska. They are deeply engaged in local politics and manage significant tracts of land through Native corporations [Data: Entities (535); Relationships (803)].

### Political Entities
Alaskan politicians and the Alaska Statehood Committee have historically played significant roles in shaping state policies and advocating for state investments [Data: Entities (339, 100); Relationships (862, 698)].

### Economic Contributors
Employment sectors such as government, natural resource extraction, and tourism are major players in Alaska's economy. Military bases also contribute significantly to employment in certain boroughs [Data: Entities (306); Relationships (854, 855)].

### Cultural and Social Organizations
Organizations like the Anchorage Opera and various native corporations contribute to the cultural and social fabric of the state [Data: Entities (402); Relationships (593)].

## California

### Indigenous Peoples
Indigenous groups in California have a tragic history of displacement and violence but remain integral to the state's historical narrative [Data: Entities (30); Sources (181)].

### Religious Organizations
Major religious denominations such as the Southern Baptist Convention and The Church of Jesus Christ of Latter-day Saints, along with diverse minority religious communities like Buddhists and Hindus, play significant roles in community dynamics and policies in California [Data: Entities (270, 269, 297, 293); Relationships (421, 420, 417, 416)].

### Demographic and Policy Influencers
Organizations like the American Community Survey and HUD's Annual Homeless Assessment Report provide critical data influencing public policy and community planning in California [Data: Entities (240, 239); Relationships (373, 362)].

### Economic and Social Impact Groups
Entities involved in addressing homelessness and demographic shifts, such as HUD, are crucial in developing interventions to improve life quality for vulnerable populations in California [Data: Entities (239); Relationships (362)].

## Conclusion
Both Alaska and California feature a diverse array of primary actors ranging from indigenous communities and political entities to economic sectors and cultural organizations. These actors play crucial roles in shaping the social, economic, and political landscapes of their respective states.
```

#### Compare result between first segment(global query）  and second segment(local query) 
Upon comparing the two segments provided, it is evident that both offer a comprehensive analysis of the primary actors in Alaska and California, but they differ in structure and detail:
##### Structure and Focus:
- The first segment is organized by categories such as government, education, environmental management, and cultural representation for each state. It provides a broad overview of the key actors and their roles within these categories.
- The second segment is structured around community-specific actors and their impacts, focusing more on the interactions and relationships between different entities and groups within Alaska and California.

##### Detail and Data Reference:
- The first segment includes specific references to data reports, which adds credibility and a basis for the claims made about the roles of various actors. Each actor's influence is backed by numbered reports, providing a clear trail for verification.
- The second segment also references data entities and relationships but uses a different notation (e.g., Entities (535); Relationships (803)). This approach highlights the interconnectedness of the actors and their roles but might be less straightforward for readers unfamiliar with this notation.

##### Content Coverage:
- The first segment covers a wide range of sectors and their key actors, from political bodies to cultural institutions and environmental management. It provides a holistic view of the influential forces in each state.
- The second segment delves deeper into the societal impacts and historical contexts, particularly emphasizing the roles of indigenous communities and economic contributors in Alaska, and demographic influencers and social impact groups in California. This segment offers a more in-depth look at the social dynamics and historical influences.

##### Analytical Depth:
- The first segment is more descriptive, listing key actors and their roles without much analysis of how these roles interact or the broader implications.
- The second segment provides more analysis on how these actors influence and shape the states' policies, economies, and social structures, giving a more dynamic and interconnected view of the states' landscapes.

#### Summary
The first segment is useful for obtaining a clear and structured overview of the primary actors in Alaska and California, while the second segment offers a more nuanced and interconnected analysis, focusing on the impacts and relationships among the actors. Both segments are informative, but the choice between them would depend on whether the reader prefers a straightforward listing or a deeper analytical perspective.



## In 2-Advanced_Getting_Started.ipynb
![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/7.png)

In this ipynb, in addition to performing the comparison between global query and local query, the API was called to generate Graphrag knowledge.

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/graphrag/images/8.png)

In this Jupyter notebook, the process of generating a GraphML file is implemented through the save_graphml_file function. This function retrieves knowledge graph data from the GraphRAG API and saves it as a GraphML file.
###  GraphML file generation logic
#### Function Definition
The save_graphml_file function accepts two parameters: index_name (index name) and graphml_file_name (the name of the GraphML file to be saved).
#### URL Construction
```
url = endpoint + f"/graph/graphml/{index_name}"
```
Constructs the API endpoint URL for retrieving the GraphML file.

#### File Extension Check
```
if Path(graphml_file_name).suffix != ".graphml"
```
Checks if the file name ends with .graphml, and if not, raises a warning.

#### Sending Request and Saving File
- with requests.get(url, headers=headers, stream=True) as r::Sends a GET request to stream the data.
- r.raise_for_status(): Checks if the request was successful, and if not, raises an exception.
- with open(graphml_file_name, "wb") as f:: Opens the file in binary write mode.
- for chunk in r.iter_content(chunk_size=1024):: Iterates over the response content in chunks of 1024 bytes.
- f.write(chunk): Writes each chunk to the file.

#### Final Generated File
The generated file is a GraphML file, with the file name specified by the graphml_file_name parameter. This file contains the knowledge graph data and can be used for further analysis and visualization using graph visualization tools like Gephi.

### Underlying Logic for Generating GraphML
In the file ***graphrag/index/verbs/graph/create.py***, the create_graph function uses the NetworkX library's generate_graphml method to generate the GraphML file. Below is a detailed explanation of the relevant code:
Code Snippet for Generating GraphML
```
@verb(name="create_graph")  
def create_graph(  
    input: VerbInput,  
    callbacks: VerbCallbacks,  
    to: str,  
    type: str,  # noqa A002  
    graph_type: str = "undirected",  
    **kwargs,  
) -> TableContainer:  
    ...  
    out_graph: nx.Graph = _create_nx_graph(graph_type)  
    ...  
    for _, row in progress_iterable(input_df.iterrows(), callbacks.progress, num_total):  
        item_attributes = {  
            clean_str(key): _clean_value(row[value])  
            for key, value in in_attributes.items()  
            if value in row  
        }  
        if type == "node":  
            id = clean_str(row[id_col])  
            out_graph.add_node(id, **item_attributes)  
        elif type == "edge":  
            source = clean_str(row[source_col])  
            target = clean_str(row[target_col])  
            out_graph.add_edge(source, target, **item_attributes)  
      
    # Generate GraphML string  
    graphml_string = "".join(nx.generate_graphml(out_graph))  
    output_df = pd.DataFrame([{to: graphml_string}])  
    return TableContainer(table=output_df)  
```

#### Detailed Explanation

- Creating Graph Object:
out_graph: nx.Graph = _create_nx_graph(graph_type): Creates a NetworkX graph object based on the graph_type parameter, which can be a directed graph (DiGraph) or an undirected graph (Graph).
- Adding Nodes and Edges:
Based on the rows of the input DataFrame input_df, nodes and edges are added to the graph object using out_graph.add_node and out_graph.add_edge methods.
- Generating GraphML String:
graphml_string = "".join(nx.generate_graphml(out_graph)): Uses NetworkX's generate_graphml method to generate a GraphML formatted string. The generate_graphml method returns a generator, and each part generated is concatenated into a complete string using "".join.
- Output DataFrame:
output_df = pd.DataFrame([{to: graphml_string}]): Stores the generated GraphML string in a new DataFrame and returns a TableContainer object.

### Related Helper Functions
- _create_nx_graph: Creates a NetworkX graph object based on the graph_type parameter.
- _get_node_attributes and _get_edge_attributes: Retrieve attribute mappings for nodes and edges.
- _get_attribute_column_mapping: Converts attribute mappings to dictionary format.
- _clean_value: Cleans attribute values.

### GraphML file generation logicSummary

In this code, the create_graph function generates a GraphML file using the NetworkX library. The specific steps include creating a graph object, adding nodes and edges, generating a GraphML string, and storing it in a DataFrame. The final GraphML file can be used for further graph analysis and visualization.

















































