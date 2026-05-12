"""
TRIPLE:
  Skill: azure-storage-blob-py
  Prompt: "Using azure-storage-blob-py skill, write a Python script that uploads a local file
           to Azure Blob Storage using DefaultAzureCredential (NOT account key), creates the
           container if it doesn't exist (handle 409), and generates a user-delegation SAS
           URL for download."
  Deliverable: This file — runnable Python script

Source: https://github.com/microsoft/skills/tree/main/.github/plugins/azure-sdk-python/skills/azure-storage-blob-py
"""
import os
from datetime import datetime, timedelta, timezone
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

account_url = os.environ["AZURE_STORAGE_ACCOUNT_URL"]  # https://<account>.blob.core.windows.net
container_name = "agent-uploads"
blob_name = "evaluation-results.json"
local_file = "evaluation/results/full_value_evaluation.json"

credential = DefaultAzureCredential()
service = BlobServiceClient(account_url=account_url, credential=credential)

# Create container (idempotent — handle 409 Conflict)
try:
    service.create_container(container_name)
    print(f"Created container: {container_name}")
except Exception as e:
    if "ContainerAlreadyExists" in str(e):
        print(f"Container already exists: {container_name}")
    else:
        raise

# Upload with overwrite
blob_client = service.get_blob_client(container_name, blob_name)
with open(local_file, "rb") as f:
    blob_client.upload_blob(f, overwrite=True)
print(f"Uploaded: {blob_name} ({os.path.getsize(local_file)} bytes)")

# Generate user-delegation SAS (per skill: use delegation key, not account key)
delegation_key = service.get_user_delegation_key(
    key_start_time=datetime.now(timezone.utc),
    key_expiry_time=datetime.now(timezone.utc) + timedelta(hours=1),
)
sas = generate_blob_sas(
    account_name=account_url.split("//")[1].split(".")[0],
    container_name=container_name,
    blob_name=blob_name,
    user_delegation_key=delegation_key,
    permission=BlobSasPermissions(read=True),
    expiry=datetime.now(timezone.utc) + timedelta(hours=1),
)
print(f"SAS URL: {account_url}/{container_name}/{blob_name}?{sas}")
