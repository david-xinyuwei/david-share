"""
TRIPLE:
  Skill: azure-cosmos-py
  Prompt: "Using azure-cosmos-py skill, write a Python script that connects to Cosmos DB
           with DefaultAzureCredential (NOT key), creates a database+container if not exists,
           upserts an agent registry document, and queries by partition key."
  Deliverable: This file — runnable Python script

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-cosmos-py
"""
import os
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, PartitionKey

endpoint = os.environ["COSMOS_ENDPOINT"]  # https://<account>.documents.azure.com:443/
credential = DefaultAzureCredential()
client = CosmosClient(url=endpoint, credential=credential)

db = client.create_database_if_not_exists("agent-db")
container = db.create_container_if_not_exists(
    id="agents",
    partition_key=PartitionKey(path="/agent_id"),
)

# Upsert agent
agent = {
    "id": "math-only",
    "agent_id": "math-only",
    "name": "Math agent (code_interpreter only)",
    "tools": ["code_interpreter"],
    "calls": 42,
}
container.upsert_item(agent)
print(f"Upserted: {agent['id']}")

# Query by partition key
results = list(container.query_items(
    query="SELECT * FROM c WHERE c.agent_id = @aid",
    parameters=[{"name": "@aid", "value": "math-only"}],
    partition_key="math-only",
))
print(f"Query returned {len(results)} item(s): {results[0]['name']}")
