"""
Morning Sweep — Infrastructure Setup
Creates AI Search indexes + CosmosDB database/containers + initial data ingestion
"""
import json
import os
import sys
from datetime import datetime, timezone

# ============================================================
# Config
# ============================================================
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "")
SEARCH_KEY = os.getenv("SEARCH_KEY", "")

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")
COSMOS_KEY = os.getenv("COSMOS_KEY", "")

AOAI_ENDPOINT = os.getenv("AOAI_ENDPOINT", "")
AOAI_KEY = os.getenv("AOAI_KEY", "")

# ============================================================
# 1. Create AI Search Indexes
# ============================================================
def setup_search_indexes():
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SearchField, SearchFieldDataType,
        VectorSearch, HnswAlgorithmConfiguration, VectorSearchProfile,
        SearchableField, SimpleField,
    )
    from azure.core.credentials import AzureKeyCredential

    client = SearchIndexClient(SEARCH_ENDPOINT, AzureKeyCredential(SEARCH_KEY))

    # emails index
    emails_fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="user_id", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="subject", type=SearchFieldDataType.String),
        SearchableField(name="body", type=SearchFieldDataType.String),
        SimpleField(name="sender_name", type=SearchFieldDataType.String, filterable=True, searchable=True),
        SimpleField(name="sender_email", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="received_time", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        SimpleField(name="importance", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="is_read", type=SearchFieldDataType.Boolean, filterable=True),
        SimpleField(name="conversation_id", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="body_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    vector_search_dimensions=3072, vector_search_profile_name="default-profile"),
    ]

    # chats index
    chats_fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="user_id", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="sender_name", type=SearchFieldDataType.String, filterable=True, searchable=True),
        SimpleField(name="topic", type=SearchFieldDataType.String, filterable=True, searchable=True),
        SimpleField(name="timestamp", type=SearchFieldDataType.DateTimeOffset, filterable=True, sortable=True),
        SearchField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    vector_search_dimensions=3072, vector_search_profile_name="default-profile"),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="default-algo")],
        profiles=[VectorSearchProfile(name="default-profile", algorithm_configuration_name="default-algo")],
    )

    for name, fields in [("emails", emails_fields), ("chats", chats_fields)]:
        index = SearchIndex(name=name, fields=fields, vector_search=vector_search)
        try:
            client.delete_index(name)
        except:
            pass
        client.create_index(index)
        print(f"  ✅ Index '{name}' created")


# ============================================================
# 2. Create CosmosDB Database + Containers
# ============================================================
def setup_cosmos():
    from azure.cosmos import CosmosClient, PartitionKey

    client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
    db = client.create_database_if_not_exists("morning_sweep")
    print(f"  ✅ Database 'morning_sweep' ready")

    for container_name in ["profiles", "analyses"]:
        db.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/user_id"),
        )
        print(f"  ✅ Container '{container_name}' ready")

    return db


# ============================================================
# 3. Create Foundry IQ Knowledge Base
# ============================================================
def setup_foundry_iq():
    """Create Knowledge Sources + Knowledge Base via REST API."""
    import requests

    if not SEARCH_ENDPOINT or not SEARCH_KEY:
        print("  ⚠️ SEARCH_ENDPOINT/SEARCH_KEY not set, skipping Foundry IQ")
        return

    api_ver = "2025-11-01-preview"
    headers = {"Content-Type": "application/json", "api-key": SEARCH_KEY}
    base = SEARCH_ENDPOINT.rstrip("/")

    # Create Knowledge Sources
    for ks_name, index_name in [("emails-ks", "emails"), ("chats-ks", "chats")]:
        url = f"{base}/knowledgesources('{ks_name}')?api-version={api_ver}"
        body = {"type": "azureSearchIndex", "azureSearchIndexParameters": {"indexName": index_name}}
        resp = requests.put(url, headers=headers, json=body, timeout=30)
        if resp.status_code in (200, 201):
            print(f"  ✅ Knowledge Source '{ks_name}' ready")
        else:
            print(f"  ⚠️ Knowledge Source '{ks_name}': {resp.status_code} {resp.text[:100]}")

    # Create Knowledge Base
    kb_name = os.getenv("FOUNDRY_IQ_KB", "morning-sweep-kb")
    aoai_deployment = os.getenv("AOAI_DEPLOYMENT", "gpt-5.4-mini")
    url = f"{base}/knowledgebases('{kb_name}')?api-version={api_ver}"
    body = {
        "description": "Morning Sweep Knowledge Base",
        "knowledgeSources": [{"name": "emails-ks"}, {"name": "chats-ks"}],
        "models": [{"kind": "azureOpenAI", "azureOpenAIParameters": {
            "resourceUri": AOAI_ENDPOINT.rstrip("/"),
            "deploymentId": aoai_deployment,
            "apiKey": AOAI_KEY,
            "modelName": aoai_deployment,
        }}],
    }
    resp = requests.put(url, headers=headers, json=body, timeout=30)
    if resp.status_code in (200, 201):
        print(f"  ✅ Knowledge Base '{kb_name}' ready")
    else:
        print(f"  ⚠️ Knowledge Base '{kb_name}': {resp.status_code} {resp.text[:100]}")


# ============================================================
# 4. Ingest emails from Graph API → AI Search
# ============================================================
def ingest_emails(token, user_id="default"):
    from azure.search.documents import SearchClient
    from azure.core.credentials import AzureKeyCredential
    from openai import AzureOpenAI
    sys.path.insert(0, os.path.dirname(__file__))
    from morning_sweep import fetch_recent_emails, fetch_recent_chats

    search_client = SearchClient(SEARCH_ENDPOINT, "emails", AzureKeyCredential(SEARCH_KEY))
    openai_client = AzureOpenAI(azure_endpoint=AOAI_ENDPOINT, api_key=AOAI_KEY, api_version="2025-04-01-preview")

    # Fetch emails
    emails = fetch_recent_emails(token, hours=168)  # 7 days
    print(f"  📧 Fetched {len(emails)} emails")

    # Index emails with embeddings
    docs = []
    for e in emails:
        subject = e.get("subject", "")
        body = e.get("bodyPreview", "")
        text = f"{subject}\n{body}"

        # Generate embedding
        emb_resp = openai_client.embeddings.create(model="text-embedding-3-large", input=text)
        vector = emb_resp.data[0].embedding

        msg_id = e.get("id", "")
        doc = {
            "id": msg_id.replace("=", "").replace("+", "").replace("/", "")[:128],
            "user_id": user_id,
            "subject": subject,
            "body": body,
            "sender_name": e.get("from", {}).get("emailAddress", {}).get("name", ""),
            "sender_email": e.get("from", {}).get("emailAddress", {}).get("address", ""),
            "received_time": e.get("receivedDateTime", ""),
            "importance": e.get("importance", "normal"),
            "is_read": e.get("isRead", False),
            "conversation_id": e.get("conversationId", ""),
            "body_vector": vector,
        }
        docs.append(doc)

    if docs:
        result = search_client.upload_documents(docs)
        succeeded = sum(1 for r in result if r.succeeded)
        print(f"  ✅ Indexed {succeeded}/{len(docs)} emails to AI Search")

    # Ingest chats
    chats_client = SearchClient(SEARCH_ENDPOINT, "chats", AzureKeyCredential(SEARCH_KEY))
    chats = fetch_recent_chats(token, top=10)
    print(f"  💬 Fetched {len(chats)} chats")

    chat_docs = []
    for c in chats:
        for m in c.get("recentMessages", []):
            content = m.get("body", {}).get("content", "").strip()
            if not content or len(content) < 5:
                continue
            emb_resp = openai_client.embeddings.create(model="text-embedding-3-large", input=content[:2000])
            vector = emb_resp.data[0].embedding
            msg_id = m.get("id", "")
            doc = {
                "id": msg_id.replace("=", "").replace("+", "").replace("/", "")[:128],
                "user_id": user_id,
                "content": content[:2000],
                "sender_name": m.get("from", {}).get("user", {}).get("displayName", "") if m.get("from") else "",
                "topic": c.get("topic", ""),
                "timestamp": m.get("createdDateTime", ""),
                "content_vector": vector,
            }
            chat_docs.append(doc)

    if chat_docs:
        result = chats_client.upload_documents(chat_docs)
        succeeded = sum(1 for r in result if r.succeeded)
        print(f"  ✅ Indexed {succeeded}/{len(chat_docs)} chat messages to AI Search")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="Create indexes and containers")
    parser.add_argument("--ingest", action="store_true", help="Ingest data from Graph API")
    parser.add_argument("--all", action="store_true", help="Setup + Ingest")
    args = parser.parse_args()

    if args.setup or args.all:
        print("📦 Setting up AI Search indexes...")
        setup_search_indexes()
        print("\n📦 Setting up CosmosDB...")
        setup_cosmos()
        print("\n🧠 Setting up Foundry IQ Knowledge Base...")
        setup_foundry_iq()

    if args.ingest or args.all:
        print("\n📥 Ingesting data from Graph API...")
        sys.path.insert(0, os.path.dirname(__file__))
        from morning_sweep import get_token
        token = get_token()
        ingest_emails(token)

    if not (args.setup or args.ingest or args.all):
        print("Usage: python setup_infra.py --setup | --ingest | --all")
