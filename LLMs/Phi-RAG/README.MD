## Phi2+LlamaIndex to achieve RAG



LlamaIndex is an open-source framework that, when used with Hugging Face Transformers, effectively builds LLM applications, providing convenient methods for setting up databases and retrievers. The community around LlamaIndex is very active.



The advantages of the Phi2+LlamaIndex solution are as follows:

1. **Integration of Small Language Models**: Phi-2 is Microsoft's SLM with 2.7 billion parameters, providing powerful language understanding and generation capabilities. It is lightweight and has fast inference!

2. **Ollama Platform**: Ollama offers a growing collection of models and supports background process operation, making model deployment and management more flexible.

3. **LlamaIndex Technology**: Specifically designed for building Retrieval-Augmented Generation (RAG) systems, it allows users to ingest, index, and query data to build end-to-end generative AI applications.

4. **RAG Strategy**: By combining information retrieval with carefully crafted system prompts, the RAG strategy enhances the understanding and accuracy of LLMs, making it possible to develop domain-specific applications.

   Next, let's look at the code.



```
!curl https://ollama.ai/install.sh | sh
!curl https://ollama.ai/install.sh | sed 's#https://ollama.ai/download#https://github.com/jmorganca/ollama/releases/download/v0.1.28#' | sh


OLLAMA_MODEL='phi:latest'
# Start ollama as a backrgound process
command = "nohup ollama serve&"


# Use subprocess.Popen to start the process in the background
process = subprocess.Popen(command,
                            shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
print("Process ID:", process.pid)
# Let's use fly.io resources
#!OLLAMA_HOST=https://ollama-demo.fly.dev:443
time.sleep(5)  # Makes Python wait for 5 seconds
```

Load data:

```
# Load documents
reader = SimpleDirectoryReader("/root/BeijingTravelGuidebook")
docs = reader.load_data()
print(f"Loaded {len(docs)} docs")
```



The data is a PDF of a four-day tour in Beijing. This file is located in the /root/BeijingTravelGuidebook directory. The contents of the PDF are as follows:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOCcWnu0QjNFltr4u5YC7UO8XQ0PZpiaNnpHN860bJpBQb6pcpgf5C954w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOCbJEEV9OQOq9UZRqdXLcTcd4sorI9Fbg6DoHvxrFL0DlopavALkXJzg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOC5I9ibXyT0Id8RrMzDwAhlVUIicFcgAibbpDiaQnWHKRDfLky4UFYUeE4eQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Embedding uses HF's bge-small-en-v1.5.

```
# Initialize a HuggingFace Embedding model
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.llm = llm
Settings.embed_model = embed_model


# Create client and a new collection
db = chromadb.PersistentClient(path="./chroma_db")
chroma_collection = db.create_collection("poc-llamaindex-ops-thaipm2")
# Set up ChromaVectorStore and load in data
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_documents(
    docs,
    storage_context = storage_context,
    embed_model = embed_model
)
```

Then search:

```
query_engine = index.as_query_engine()
response = query_engine.query("How much will it take of 4 days Beijing City Highlights Tour")
display(Markdown(f"<b>{response}</b>"))
```

```
response = query_engine.query("How much will it take of 4 days Beijing City Highlights Tour")display(Markdown(f"<b>{response}</b>"))
```

We observed that the inference speed is very fast, 0.7 seconds. It also provided the correct answer, CN 2600.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOCDeYP8twxJW9K0lJeibbBZoDU6xu4A1rJfxgBS1mC4XyUEkoNVqwJAUQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

This matches the information in the document:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOCy6sJ8SIib97lGv7SNzwLicxibGSMTBx5JXrPKLZoibZJe0JZyLvAzdbl2Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

I asked again, The inference was very accurate, with an inference time of 1.3 seconds.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOCaichnTxZ4FfIXic27Cadj9YunbeRRbKzR5nPEpc887hPyxuuBNnOD0ibg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

Original document information:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWqp3TQz7p8dVaq37X6TvOCHia6OUdZKlicBHZPR7iaCqSjApO7SEKrTl8gmLs5ld7dufDaSJZtGjBpA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)
