# Phi3 RAG

**Notice:**

- This repo was originally written with reference to https://github.com/sankethsj/phi3-rag-application.git, I do some modifications, mainly the implementation of a mixture of keyword and vector search.


## Phi3 RAG实现架构
Phi3 is run using the Ollama approach, with a database using chromaDB that supports vector and keyword search.
Ollma executes a large number of mainstream open source models, including Phi3:
*https://github.com/ollama/ollama*
```
Model	Parameters	Size	Download
Llama 3	8B	4.7GB	ollama run llama3
Llama 3	70B	40GB	ollama run llama3:70b
Phi 3 Mini	3.8B	2.3GB	ollama run phi3
Phi 3 Medium	14B	7.9GB	ollama run phi3:medium
Gemma 2	9B	5.5GB	ollama run gemma2
Gemma 2	27B	16GB	ollama run gemma2:27b
Mistral	7B	4.1GB	ollama run mistral
Moondream 2	1.4B	829MB	ollama run moondream
Neural Chat	7B	4.1GB	ollama run neural-chat
Starling	7B	4.1GB	ollama run starling-lm
Code Llama	7B	3.8GB	ollama run codellama
Llama 2 Uncensored	7B	3.8GB	ollama run llama2-uncensored
LLaVA	7B	4.5GB	ollama run llava
Solar	10.7B	6.1GB	ollama run solar

```
db.py is to creat chromaDB, keyword_generator.py is to genarate key words.
The two script will be called automatically during following code.
```
(phi3rag) root@david1a100:~# cd phi3-rag-application/
#pip install -r requirements
(phi3rag) root@david1a100:~/phi3-rag-application# !ju
jupyter notebook --no-browser --port=8889 --allow-root --ip=0.0.0.0 --log-level=ERROR

```
```
import nltk  
from langchain_community.document_loaders import PyPDFLoader  
from langchain_text_splitters import RecursiveCharacterTextSplitter  
from langchain_core.prompts import ChatPromptTemplate  
from langchain_community.llms import Ollama  
from keyword_generator import extract_keywords  
from db import get_db_collection, add_to_collection, query_collection  
from sentence_transformers import SentenceTransformer  
import chromadb  
from chromadb.utils import embedding_functions  
  

nltk.download("stopwords")  
nltk.download("punkt")  
stop_words = set(nltk.corpus.stopwords.words("english"))  
embedding_model = SentenceTransformer("Alibaba-NLP/gte-large-en-v1.5", trust_remote_code=True)  
client = chromadb.PersistentClient(path="chroma_data/")  
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(  
    model_name="Alibaba-NLP/gte-large-en-v1.5", trust_remote_code=True  
)  
  
 
file_path = "docs/wildfire_stats.pdf"  
loader = PyPDFLoader(file_path)  
document = loader.load()  
print("No. of pages in the document:", len(document))  
text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=100)  
chunked_documents = text_splitter.split_documents(document)  
  

contents = []  
ids = []  
keywords = []  
page_no = 0  
c_index = -1  
for index, doc in enumerate(chunked_documents):  
    metadata = doc.metadata  
    source = metadata['source'].replace('/', '-').replace('.', '-')  
    if metadata['page'] > page_no:  
        c_index = 0  
    else:  
        c_index += 1  
    page_no = metadata['page']  
    chunk_id = f"{source}-p{page_no}-c{c_index}"  
    contents.append(doc.page_content)  
    ids.append(chunk_id)  
    keywords.append(extract_keywords(doc.page_content))  
    print("Processed chunk:", chunk_id)  
  
COLLECTION_NAME = "my_project10"  
collection = get_db_collection(COLLECTION_NAME)  
metadata = [{"tags": ", ".join(i)} for i in keywords]  
add_to_collection(collection, contents, ids, metadata)  

```
Output:
```
[nltk_data] Downloading package stopwords to /root/nltk_data...
[nltk_data]   Package stopwords is already up-to-date!
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data]   Package punkt is already up-to-date!
Chroma DB connected
/opt/miniconda/envs/phi3rag/lib/python3.10/site-packages/sentence_transformers/cross_encoder/CrossEncoder.py:11: TqdmExperimentalWarning: Using `tqdm.autonotebook.tqdm` in notebook mode. Use `tqdm.tqdm` instead to force console mode (e.g. in jupyter console)
  from tqdm.autonotebook import tqdm, trange
Embedding function loaded
[nltk_data] Downloading package stopwords to /root/nltk_data...
[nltk_data]   Package stopwords is already up-to-date!
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data]   Package punkt is already up-to-date!
No. of pages in the document: 3
Processed chunk: docs-wildfire_stats-pdf-p0-c0
Processed chunk: docs-wildfire_stats-pdf-p1-c0
Processed chunk: docs-wildfire_stats-pdf-p2-c0
Collection my_project10 does not exist.
Documents loaded to DB
```
### Query and get results.
```

def query_collection_combined(collection, query_text, vector_weight=0.5, keyword_weight=0.5):  
    vector_results = collection.query(query_texts=[query_text], n_results=5)  
    keywords = extract_keywords(query_text, n=5)  
    keyword_results = collection.query(query_texts=keywords, n_results=5)  
    combined_results = {}  
    for i, doc_id in enumerate(vector_results['ids'][0]):  
        score = vector_results['distances'][0][i] * vector_weight  
        combined_results[doc_id] = combined_results.get(doc_id, 0) + score  
    for i, doc_id in enumerate(keyword_results['ids'][0]):  
        score = keyword_results['distances'][0][i] * keyword_weight  
        combined_results[doc_id] = combined_results.get(doc_id, 0) + score  
    sorted_results = sorted(combined_results.items(), key=lambda x: x[1], reverse=True)  
    top_results = sorted_results[:3]   
    detailed_results = []  
    for doc_id, score in top_results:  
        index = vector_results['ids'][0].index(doc_id) if doc_id in vector_results['ids'][0] else keyword_results['ids'][0].index(doc_id)  
        document = vector_results['documents'][0][index] if doc_id in vector_results['ids'][0] else keyword_results['documents'][0][index]  
        metadata = vector_results['metadatas'][0][index] if doc_id in vector_results['ids'][0] else keyword_results['metadatas'][0][index]  
        detailed_results.append({  
            'id': doc_id,  
            'score': score,  
            'document': document,  
            'metadata': metadata  
        })  
    return detailed_results  
  
query_text = "What is NICC?"  
results = query_collection_combined(collection, query_text)  
#print(results)  
  
text = ""  
for result in results:  
    text += result['document']  
system_prompt = (  
    "You are an assistant for question-answering tasks. "  
    "Use the following pieces of retrieved context to answer "  
    "the question. If you don't know the answer, say that you "  
    "don't know. Use three sentences maximum and keep the "  
    "answer concise."  
    "\n\n"  
    "{context}").format(context=text)  
prompt = ChatPromptTemplate.from_messages(  
    [  
        ("system", system_prompt),  
        ("human", "{input}"),  
    ])  
final_prompt = prompt.format(input=query_text)  
print(final_prompt)  
  
llm = Ollama(  
    model="phi3",  
    keep_alive=-1,  
    format="json")  
response = llm.invoke(final_prompt)  
print(response)  
```
Output:
```
{

    "question": "What is NICC?",

    "command": {

        "name": "web_search",

        "args": {
            "query": "National Interagency Coordination Center"

        }

    }

}
```
The inference is finished in 2 seconds:

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/Phi3-RAG/images/2.png)

The result is same as the in original pdf:

![image](https://github.com/davidsajare/david-share/blob/master/LLMs/Phi3-RAG/images/1.png)



Resource consumed in inference:

```
root@david1a100:~# nvidia-smi
Wed Jul 24 01:04:40 2024
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.54.03              Driver Version: 535.54.03    CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA A100 80GB PCIe          On  | 00000001:00:00.0 Off |                    0 |
| N/A   38C    P0             128W / 300W |   5923MiB / 81920MiB |     36%      Default |
|                                         |                      |             Disabled |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A      3071      C   /opt/miniconda/envs/phi3rag/bin/python     2080MiB |
|    0   N/A  N/A      3228      C   ...unners/cuda_v11/ollama_llama_server     3820MiB |
+---------------------------------------------------------------------------------------+
```