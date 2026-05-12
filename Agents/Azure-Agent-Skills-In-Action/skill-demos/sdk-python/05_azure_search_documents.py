"""
TRIPLE:
  Skill: azure-search-documents-py
  Prompt: "Using azure-search-documents-py skill, write a Python script that performs
           hybrid search (vector + BM25 keyword) with semantic ranker on Azure AI Search,
           using DefaultAzureCredential."
  Deliverable: This file — runnable Python script

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-search-documents-py
"""
import os
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

endpoint = os.environ["SEARCH_ENDPOINT"]  # https://<service>.search.windows.net
index_name = os.environ.get("SEARCH_INDEX", "agent-docs")
credential = DefaultAzureCredential()

client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

# Hybrid search: vector + keyword + semantic ranker
query_text = "How does Azure MCP Server authenticate?"
query_vector = [0.1] * 1536  # Replace with real embedding from Azure OpenAI

results = client.search(
    search_text=query_text,
    vector_queries=[VectorizedQuery(vector=query_vector, k_nearest_neighbors=5, fields="embedding")],
    query_type="semantic",
    semantic_configuration_name="default",
    top=5,
    select=["title", "content", "url"],
)

print(f"=== Hybrid search: '{query_text}' ===")
for r in results:
    print(f"  [{r['@search.score']:.2f}] {r.get('title', 'N/A')}")
    print(f"    {r.get('content', '')[:120]}...")
    print(f"    Source: {r.get('url', 'N/A')}")
