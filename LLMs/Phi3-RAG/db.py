import chromadb
from chromadb.utils import embedding_functions

CHROMA_DATA_PATH = "chroma_data/"
EMBED_MODEL = "Alibaba-NLP/gte-large-en-v1.5"

client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
print("Chroma DB connected")

embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBED_MODEL, trust_remote_code=True
)
print("Embedding function loaded")


def get_db_collection(collection_name: str) -> chromadb.Collection:

    try:
        collection = client.get_collection(
            collection_name,
            embedding_function=embedding_func,
        )
    except ValueError as e:
        print(e)
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_func,
            metadata={"hnsw:space": "cosine"},
        )

    return collection


def add_to_collection(
    collection: chromadb.Collection, documents: list, ids: list, metadata: list
):

    collection.add(
        documents=documents,
        ids=ids,
        metadatas=metadata,
    )
    print("Documents loaded to DB")


def query_collection(collection: chromadb.Collection, query_text: str):

    query_results = collection.query(
        query_texts=[query_text],
        n_results=3,
    )

    return query_results


def generate_context(query_result: dict):
    context = ""
    for doc in query_result["documents"]:
        for i in doc:
            context += i
    return context
