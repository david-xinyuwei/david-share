"""
TRIPLE:
  Skill: azure-ai-projects-py
  Prompt: "Using azure-ai-projects-py skill, write a Python script that connects to a Foundry
           project, lists available deployments, and sends a chat completion to gpt-4.1-mini.
           Use AIProjectClient.from_endpoint + DefaultAzureCredential. Print deployment names
           and the model's response."
  Deliverable: This file — runnable Python script

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-ai-projects-py
"""
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]
credential = DefaultAzureCredential()
client = AIProjectClient.from_endpoint(endpoint=endpoint, credential=credential)

# List deployments
print("=== Deployments ===")
for d in client.deployments.list():
    print(f"  {d.name} ({d.properties.model.name} {d.properties.model.version})")

# Chat completion via the project's OpenAI-compatible client
oai = client.inference.get_chat_completions_client()
response = oai.complete(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": "Summarize Azure Agent Skills in one sentence."}],
)
print(f"\n=== Response ===\n{response.choices[0].message.content}")
