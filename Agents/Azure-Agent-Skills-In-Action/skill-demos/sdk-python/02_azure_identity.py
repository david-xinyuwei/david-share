"""
TRIPLE:
  Skill: azure-identity-py
  Prompt: "Using azure-identity-py skill, write a Python script that demonstrates
           DefaultAzureCredential with explicit scope selection (ai.azure.com for Foundry,
           cognitiveservices.azure.com for AOAI), shows token cache behavior, and falls
           back to AzureCliCredential when AZURE_AUTH_MODE=cli."
  Deliverable: This file — runnable Python script

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-identity-py
"""
import os
from azure.identity import DefaultAzureCredential, AzureCliCredential

def get_credential():
    if os.getenv("AZURE_AUTH_MODE", "").lower() == "cli":
        print("Using AzureCliCredential (local dev mode)")
        return AzureCliCredential()
    print("Using DefaultAzureCredential (managed identity → CLI → env fallback)")
    return DefaultAzureCredential()

credential = get_credential()

# Foundry scope (for hosted agents, toolbox, memory)
foundry_token = credential.get_token("https://ai.azure.com/.default")
print(f"Foundry token: ...{foundry_token.token[-20:]}  expires={foundry_token.expires_on}")

# Cognitive Services scope (for Azure OpenAI direct calls)
aoai_token = credential.get_token("https://cognitiveservices.azure.com/.default")
print(f"AOAI token:    ...{aoai_token.token[-20:]}  expires={aoai_token.expires_on}")

# Graph scope (for Entra Agent ID provisioning)
graph_token = credential.get_token("https://graph.microsoft.com/.default")
print(f"Graph token:   ...{graph_token.token[-20:]}  expires={graph_token.expires_on}")

print("\n✅ All three scopes acquired. Token cache is active (second call uses cached token).")
foundry_token2 = credential.get_token("https://ai.azure.com/.default")
print(f"Cached hit:    expires_on unchanged = {foundry_token2.expires_on == foundry_token.expires_on}")
