"""
Morning Sweep — Data Layer
AI Search (retrieval) + Foundry IQ (agentic retrieval) + CosmosDB (profiles/history) + Graph API (ingestion)
"""
import json
import os
from datetime import datetime, timedelta, timezone

import requests as http_requests
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient, PartitionKey
from openai import AzureOpenAI

# ============================================================
# Config
# ============================================================
SEARCH_ENDPOINT = os.getenv("SEARCH_ENDPOINT", "")
SEARCH_KEY = os.getenv("SEARCH_KEY", "")
FOUNDRY_IQ_KB = os.getenv("FOUNDRY_IQ_KB", "morning-sweep-kb")
FOUNDRY_IQ_API_VERSION = "2025-11-01-preview"

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT", "")

# Service Principal for CosmosDB AAD auth
SP_TENANT = os.getenv("SP_TENANT", "")
SP_CLIENT_ID = os.getenv("SP_CLIENT_ID", "")
SP_CLIENT_SECRET = os.getenv("SP_CLIENT_SECRET", "")

AOAI_ENDPOINT = os.getenv("AOAI_ENDPOINT", "")
AOAI_KEY = os.getenv("AOAI_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-large"

# Clients (lazy init)
_search_emails = None
_search_chats = None
_cosmos_db = None
_openai = None


def _get_search_client(index_name):
    return SearchClient(SEARCH_ENDPOINT, index_name, AzureKeyCredential(SEARCH_KEY))


def _get_cosmos_db():
    global _cosmos_db
    if _cosmos_db is None:
        from azure.identity import ClientSecretCredential
        cred = ClientSecretCredential(tenant_id=SP_TENANT, client_id=SP_CLIENT_ID, client_secret=SP_CLIENT_SECRET)
        client = CosmosClient(COSMOS_ENDPOINT, credential=cred)
        _cosmos_db = client.get_database_client("morning_sweep")
    return _cosmos_db


def _get_openai():
    global _openai
    if _openai is None:
        _openai = AzureOpenAI(azure_endpoint=AOAI_ENDPOINT, api_key=AOAI_KEY, api_version="2025-04-01-preview")
    return _openai


def _embed(text):
    """Generate embedding vector for text."""
    resp = _get_openai().embeddings.create(model=EMBEDDING_MODEL, input=text[:8000])
    return resp.data[0].embedding


# ============================================================
# Ingestion: Graph API → AI Search
# ============================================================
def ingest_emails(emails, user_id="default"):
    """Write emails to AI Search index with embeddings."""
    client = _get_search_client("emails")
    docs = []
    for e in emails:
        subject = e.get("subject", "")
        body = e.get("bodyPreview", "")
        text = f"{subject}\n{body}"
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
            "body_vector": _embed(text),
        }
        docs.append(doc)
    if docs:
        result = client.upload_documents(docs)
        ok = sum(1 for r in result if r.succeeded)
        print(f"  📥 Indexed {ok}/{len(docs)} emails")
        return ok
    return 0


def ingest_chats(chats, user_id="default"):
    """Write chat messages to AI Search index with embeddings."""
    client = _get_search_client("chats")
    docs = []
    for c in chats:
        for m in c.get("recentMessages", []):
            content = m.get("body", {}).get("content", "").strip()
            if not content or len(content) < 5:
                continue
            msg_id = m.get("id", "")
            doc = {
                "id": msg_id.replace("=", "").replace("+", "").replace("/", "")[:128],
                "user_id": user_id,
                "content": content[:2000],
                "sender_name": m.get("from", {}).get("user", {}).get("displayName", "") if m.get("from") else "",
                "topic": c.get("topic", ""),
                "timestamp": m.get("createdDateTime", ""),
                "content_vector": _embed(content[:2000]),
            }
            docs.append(doc)
    if docs:
        result = client.upload_documents(docs)
        ok = sum(1 for r in result if r.succeeded)
        print(f"  📥 Indexed {ok}/{len(docs)} chat messages")
        return ok
    return 0


# ============================================================
# Retrieval: AI Search → structured data for GPT
# ============================================================
def search_recent_emails(user_id="default", hours=24, top=20):
    """Keyword search for recent emails."""
    client = _get_search_client("emails")
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    results = client.search(
        search_text="*",
        filter=f"user_id eq '{user_id}' and received_time ge {since}",
        order_by=["received_time desc"],
        top=top,
        select=["subject", "body", "sender_name", "sender_email", "received_time", "importance", "is_read"],
    )
    return [dict(r) for r in results]


def search_emails_by_sender(sender_name, user_id="default", top=5):
    """Find historical emails from a specific sender."""
    client = _get_search_client("emails")
    results = client.search(
        search_text=sender_name,
        filter=f"user_id eq '{user_id}'",
        order_by=["received_time desc"],
        top=top,
        select=["subject", "body", "sender_name", "received_time"],
    )
    return [dict(r) for r in results]


def search_emails_semantic(query, user_id="default", top=5):
    """Semantic/vector search for emails matching a natural language query."""
    client = _get_search_client("emails")
    vector = _embed(query)
    results = client.search(
        search_text=query,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top, fields="body_vector")],
        filter=f"user_id eq '{user_id}'",
        top=top,
        select=["subject", "body", "sender_name", "sender_email", "received_time", "importance"],
    )
    return [dict(r) for r in results]


def search_recent_chats(user_id="default", top=20):
    """Get recent chat messages."""
    client = _get_search_client("chats")
    results = client.search(
        search_text="*",
        filter=f"user_id eq '{user_id}'",
        order_by=["timestamp desc"],
        top=top,
        select=["content", "sender_name", "topic", "timestamp"],
    )
    return [dict(r) for r in results]


def search_chats_semantic(query, user_id="default", top=5):
    """Semantic search for chat messages."""
    client = _get_search_client("chats")
    vector = _embed(query)
    results = client.search(
        search_text=query,
        vector_queries=[VectorizedQuery(vector=vector, k_nearest_neighbors=top, fields="content_vector")],
        filter=f"user_id eq '{user_id}'",
        top=top,
        select=["content", "sender_name", "topic", "timestamp"],
    )
    return [dict(r) for r in results]


# ============================================================
# Foundry IQ: Agentic Retrieval (Knowledge Base)
# ============================================================
def foundry_iq_retrieve(query, reasoning_effort="low"):
    """Query Foundry IQ Knowledge Base for agentic retrieval across emails + chats.

    Args:
        query: Natural language question.
        reasoning_effort: "low" | "medium" | "high". Higher = more thorough but slower.

    Returns:
        dict with keys: answer (str), references (list), activity (list), error (str|None)
    """
    if not SEARCH_KEY or not FOUNDRY_IQ_KB:
        return {"answer": "", "references": [], "activity": [], "error": "SEARCH_KEY or FOUNDRY_IQ_KB not set"}

    url = f"{SEARCH_ENDPOINT}/knowledgebases('{FOUNDRY_IQ_KB}')/retrieve?api-version={FOUNDRY_IQ_API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": SEARCH_KEY}
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": query}]}],
        "queryReasoningEffort": reasoning_effort,
    }

    try:
        resp = http_requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            return {"answer": "", "references": [], "activity": [], "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
        data = resp.json()
        # Extract answer text
        answer = ""
        for r in data.get("response", []):
            for c in r.get("content", []):
                if c.get("type") == "text":
                    answer += c.get("text", "")
        # Extract references
        references = []
        for ref in data.get("references", []):
            references.append({
                "title": ref.get("title", ""),
                "chunk": ref.get("chunkText", ref.get("content", ""))[:300],
                "source": ref.get("knowledgeSourceName", ""),
            })
        activity = data.get("activity", [])
        return {"answer": answer, "references": references, "activity": activity, "error": None}
    except Exception as e:
        return {"answer": "", "references": [], "activity": [], "error": str(e)}


def foundry_iq_enrich_context(emails, chats):
    """Use Foundry IQ to generate cross-source insights from current emails + chats.

    Builds queries from email subjects and chat topics, retrieves agentic answers.
    Returns a list of insights to inject into GPT context.
    """
    insights = []

    # Build queries from top email subjects
    subjects = [e.get("subject", "") for e in emails[:5] if e.get("subject")]
    topics = list(set(c.get("topic", "") for c in chats if c.get("topic")))[:3]

    queries = []
    for s in subjects[:3]:
        queries.append(f"What do I know about: {s}")
    for t in topics[:2]:
        queries.append(f"What recent discussions happened about: {t}")

    for q in queries:
        result = foundry_iq_retrieve(q, reasoning_effort="low")
        if result["error"]:
            print(f"  ⚠️ Foundry IQ error: {result['error']}")
            continue
        if result["answer"] and result["references"]:
            insights.append({
                "query": q,
                "answer": result["answer"][:500],
                "sources": [r["source"] for r in result["references"][:3]],
                "reference_count": len(result["references"]),
            })

    if insights:
        print(f"  🔍 Foundry IQ: {len(insights)} cross-source insights from {len(queries)} queries")
    return insights


# ============================================================
# CosmosDB: Contact Profiles
# ============================================================
def load_contact_profiles(user_id="default"):
    """Load all contact profiles for a user."""
    container = _get_cosmos_db().get_container_client("profiles")
    query = "SELECT * FROM c WHERE c.user_id = @uid AND c.type = 'contact'"
    params = [{"name": "@uid", "value": user_id}]
    items = list(container.query_items(query=query, parameters=params, partition_key=user_id))
    return items


def save_contact_profile(user_id, contact_name, profile_data):
    """Upsert a contact profile."""
    container = _get_cosmos_db().get_container_client("profiles")
    doc_id = f"{user_id}_{contact_name}".replace(" ", "_").replace("@", "_")[:200]
    doc = {
        "id": doc_id,
        "user_id": user_id,
        "type": "contact",
        "contact_name": contact_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **profile_data,
    }
    container.upsert_item(doc)


def update_profiles_from_analysis(user_id, analysis_result):
    """Extract contact profiles from GPT analysis and save to CosmosDB."""
    profiles = analysis_result.get("contact_profiles", [])
    for p in profiles:
        name = p.get("name", "")
        if not name:
            continue
        save_contact_profile(user_id, name, {
            "email": p.get("email", ""),
            "role": p.get("role", ""),
            "relationship": p.get("relationship", ""),
            "communication_style": p.get("communication_style", ""),
            "recent_topics": p.get("recent_topics", []),
            "interaction_frequency": p.get("interaction_frequency", ""),
            "sentiment": p.get("sentiment", ""),
            "tip": p.get("tip", ""),
        })
    if profiles:
        print(f"  👥 Saved {len(profiles)} contact profiles to CosmosDB")


# ============================================================
# CosmosDB: Analysis History
# ============================================================
def save_analysis(user_id, result):
    """Save analysis result to CosmosDB."""
    container = _get_cosmos_db().get_container_client("analyses")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    doc = {
        "id": f"{user_id}_{ts}",
        "user_id": user_id,
        "timestamp": ts,
        "action_items": [a.get("task", "") for a in result.get("action_items", [])[:5]],
        "insights": [i.get("insight", "") for i in result.get("cross_check_insights", [])[:3]],
        "contacts_flagged": result.get("relationship_network", {}).get("attention_needed", []),
        "token_cost": result.get("_meta", {}),
    }
    container.upsert_item(doc)
    print(f"  📊 Analysis saved to CosmosDB: {doc['id']}")


def load_recent_analyses(user_id="default", days=7, max_entries=5):
    """Load recent analysis summaries from CosmosDB."""
    container = _get_cosmos_db().get_container_client("analyses")
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y%m%d")
    query = "SELECT TOP @max * FROM c WHERE c.user_id = @uid AND c.timestamp >= @cutoff ORDER BY c.timestamp DESC"
    params = [
        {"name": "@uid", "value": user_id},
        {"name": "@cutoff", "value": cutoff},
        {"name": "@max", "value": max_entries},
    ]
    items = list(container.query_items(query=query, parameters=params, partition_key=user_id))
    return items
