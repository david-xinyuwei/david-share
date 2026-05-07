"""
M365 Morning Sweep Agent
Graph API (Mail + Calendar + Chat) → Azure OpenAI Analysis → Structured Output

Usage:
    pip install msal requests openai
    python morning_sweep.py --login          # First time: interactive login
    python morning_sweep.py                  # Use cached token
    python morning_sweep.py --hours 48       # Look back 48 hours
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import msal
import requests
from openai import AzureOpenAI

# ============================================================
# Config — all from env or CLI args, no hardcoding
# ============================================================
TENANT_ID = os.getenv("TENANT_ID", "")
CLIENT_ID = os.getenv("CLIENT_ID", "")
SCOPES = ["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Mail.Send", "https://graph.microsoft.com/Calendars.Read", "https://graph.microsoft.com/Chat.Read", "https://graph.microsoft.com/User.Read", "https://graph.microsoft.com/People.Read"]
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_CACHE_FILE = os.path.expanduser("~/.morning_sweep_token_cache.json")

# Service Principal for unattended access (no user login needed)
SP_CLIENT_ID = os.getenv("SP_CLIENT_ID", "")
SP_CLIENT_SECRET = os.getenv("SP_CLIENT_SECRET", "")
SP_TENANT = os.getenv("SP_TENANT", "")
# Target user for SP mode (application permissions read a specific user's mailbox)
SP_TARGET_USER = os.getenv("SP_TARGET_USER", "")
USE_SP_AUTH = os.getenv("USE_SP_AUTH", "false").lower() == "true"

AOAI_ENDPOINT = os.getenv("AOAI_ENDPOINT", "")
AOAI_KEY = os.getenv("AOAI_KEY", "")
AOAI_DEPLOYMENT = os.getenv("AOAI_DEPLOYMENT", "gpt-5.4-mini")
AOAI_API_VERSION = os.getenv("AOAI_API_VERSION", "2025-04-01-preview")


# ============================================================
# Auth — MSAL with token cache
# ============================================================
def get_msal_app():
    cache = msal.SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE) as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else "https://login.microsoftonline.com/organizations",
        token_cache=cache,
    )
    return app, cache


def get_token(force_login=False):
    # SP mode: client credentials, no user login needed, never expires
    if USE_SP_AUTH:
        app = msal.ConfidentialClientApplication(
            SP_CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{SP_TENANT}",
            client_credential=SP_CLIENT_SECRET,
        )
        result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        else:
            print(f"❌ SP auth failed: {result.get('error_description', result)}")
            sys.exit(1)

    # Delegated mode: user login with token cache
    app, cache = get_msal_app()
    accounts = app.get_accounts()
    result = None

    if accounts and not force_login:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        print("🔐 Interactive login required...")
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            print(f"❌ Failed to create device flow: {flow.get('error_description', 'unknown')}")
            sys.exit(1)
        print(f"👉 Go to {flow['verification_uri']} and enter code: {flow['user_code']}")
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        # Save cache
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())
        return result["access_token"]
    else:
        print(f"❌ Auth failed: {result.get('error_description', result)}")
        sys.exit(1)


# ============================================================
# Graph API helpers
# ============================================================
def graph_get(token, endpoint, params=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # In SP mode, replace /me with /users/{target_user}
    if USE_SP_AUTH and endpoint.startswith("/me"):
        endpoint = f"/users/{SP_TARGET_USER}" + endpoint[3:]
    url = f"{GRAPH_BASE}{endpoint}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"⚠️  Graph API error {resp.status_code} on {endpoint}: {resp.text[:200]}")
        return None
    return resp.json()


def fetch_recent_emails(token, hours=24, top=30):
    """Fetch recent emails for the past N hours, deduplicated by subject+sender."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = graph_get(token, "/me/messages", {
        "$top": top,
        "$orderby": "receivedDateTime desc",
        "$filter": f"receivedDateTime ge {since}",
        "$select": "subject,from,receivedDateTime,bodyPreview,importance,isRead,conversationId"
    })
    if not data:
        return []
    # Deduplicate by subject + sender
    seen = set()
    unique = []
    for e in data.get("value", []):
        key = (e.get("subject", ""), e.get("from", {}).get("emailAddress", {}).get("address", ""))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def fetch_today_calendar(token, hours_ahead=48):
    """Fetch calendar events for the next N hours."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours_ahead)
    data = graph_get(token, "/me/calendarView", {
        "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "$top": 30,
        "$orderby": "start/dateTime",
        "$select": "subject,start,end,organizer,attendees,bodyPreview,location"
    })
    if not data:
        return []
    return data.get("value", [])


def fetch_recent_chats(token, top=10):
    """Fetch recent Teams chat messages."""
    chats = graph_get(token, "/me/chats", {
        "$top": top,
        "$orderby": "lastMessagePreview/createdDateTime desc",
        "$expand": "lastMessagePreview,members"
    })
    if not chats:
        return []
    chat_list = chats.get("value", [])

    # For each chat, fetch recent messages
    for chat in chat_list:
        chat_id = chat.get("id", "")
        if chat_id:
            msgs = graph_get(token, f"/me/chats/{chat_id}/messages", {
                "$top": 20,
                "$orderby": "createdDateTime desc",
            })
            chat["recentMessages"] = msgs.get("value", []) if msgs else []

    return chat_list


def fetch_user_profile(token):
    """Fetch current user profile."""
    return graph_get(token, "/me", {"$select": "displayName,mail,jobTitle,department"})


def fetch_people(token, top=10):
    """Fetch relevant people (for relationship network)."""
    data = graph_get(token, "/me/people", {
        "$top": top,
        "$select": "displayName,jobTitle,department,scoredEmailAddresses"
    })
    if not data:
        return []
    return data.get("value", [])


# ============================================================
# Data Layer Integration (AI Search + CosmosDB)
# ============================================================
USE_DATA_LAYER = os.getenv("USE_DATA_LAYER", "false").lower() == "true"

def ingest_to_search(token, user_id="default"):
    """Ingest current Graph API data into AI Search."""
    if not USE_DATA_LAYER:
        return
    try:
        from data_layer import ingest_emails, ingest_chats
        emails = fetch_recent_emails(token, hours=168)  # 7 days
        chats = fetch_recent_chats(token)
        ingest_emails(emails, user_id)
        ingest_chats(chats, user_id)
    except Exception as e:
        print(f"  ⚠️ Ingestion error: {e}")

def get_enriched_context(token, user_id="default", hours=24):
    """Get data from AI Search + Foundry IQ + CosmosDB instead of raw Graph API.
    Each component fails independently — partial enrichment is still useful.
    """
    if not USE_DATA_LAYER:
        return None

    enriched = {"emails": [], "chats": [], "stored_profiles": [], "historical_analyses": [], "foundry_iq_insights": []}

    # AI Search (emails + chats)
    try:
        from data_layer import search_recent_emails, search_recent_chats
        enriched["emails"] = search_recent_emails(user_id, hours=hours)
        enriched["chats"] = search_recent_chats(user_id)
    except Exception as e:
        print(f"  ⚠️ AI Search error (non-fatal): {e}")

    # CosmosDB (profiles + history) — graceful fallback to file history
    try:
        from data_layer import load_contact_profiles, load_recent_analyses
        enriched["stored_profiles"] = load_contact_profiles(user_id)
        enriched["historical_analyses"] = load_recent_analyses(user_id)
    except Exception as e:
        print(f"  ⚠️ CosmosDB read error (non-fatal, using file history): {e}")
        # Fallback: use file-based history instead
        file_history = load_recent_history()
        if file_history:
            enriched["historical_analyses"] = file_history

    # Foundry IQ (agentic retrieval)
    try:
        from data_layer import foundry_iq_enrich_context
        enriched["foundry_iq_insights"] = foundry_iq_enrich_context(
            [{"subject": e.get("subject", "")} for e in enriched["emails"]],
            [{"topic": c.get("topic", "")} for c in enriched["chats"]],
        )
    except Exception as e:
        print(f"  ⚠️ Foundry IQ error (non-fatal): {e}")

    # Return enriched if any component succeeded
    has_data = any(enriched[k] for k in enriched)
    return enriched if has_data else None

def save_to_cosmos(user_id, result):
    """Save analysis result + update contact profiles in CosmosDB. Silently skips on failure."""
    if not USE_DATA_LAYER:
        return
    try:
        from data_layer import update_profiles_from_analysis, save_analysis
        update_profiles_from_analysis(user_id, result)
        save_analysis(user_id, result)
    except Exception as e:
        print(f"  ⚠️ CosmosDB save error (non-fatal): {e}")


# ============================================================
# History persistence (file-based fallback)
# ============================================================
HISTORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history")

def save_history(result):
    """Save analysis result with timestamp for cross-session memory."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(HISTORY_DIR, f"sweep_{ts}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"timestamp": ts, "result": result}, f, ensure_ascii=False, default=str)
    # Keep only last 50 files
    files = sorted(os.listdir(HISTORY_DIR))
    for old in files[:-50]:
        os.remove(os.path.join(HISTORY_DIR, old))

def load_recent_history(days=7, max_entries=5):
    """Load recent analysis summaries for context."""
    if not os.path.exists(HISTORY_DIR):
        return []
    cutoff = datetime.now() - timedelta(days=days)
    entries = []
    for fname in sorted(os.listdir(HISTORY_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(HISTORY_DIR, fname), encoding="utf-8") as f:
                data = json.load(f)
            ts_str = data.get("timestamp", "")
            ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            if ts < cutoff:
                break
            r = data.get("result", {})
            summary = {
                "date": ts.strftime("%Y-%m-%d %H:%M"),
                "top_action_items": [a.get("task", "") for a in r.get("action_items", [])[:3]],
                "key_insights": [i.get("insight", "") for i in r.get("cross_check_insights", [])[:2]],
                "contacts_flagged": r.get("relationship_network", {}).get("attention_needed", []),
            }
            entries.append(summary)
            if len(entries) >= max_entries:
                break
        except:
            continue
    return entries


# ============================================================
# GPT-5.4 Analysis
# ============================================================
def analyze_with_gpt54(emails, calendar, chats, user_profile, people, enriched=None):
    """Send collected data to GPT-5.4 for Morning Sweep analysis.
    If enriched is provided (from AI Search + CosmosDB), use it for richer context.
    """
    if not AOAI_KEY:
        print("⚠️  AOAI_KEY not set, skipping GPT-5.4 analysis")
        return None

    client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_KEY,
        api_version=AOAI_API_VERSION,
    )

    # Build context
    context = {
        "user": user_profile,
        "emails": [
            {
                "subject": e.get("subject", ""),
                "from": e.get("from", {}).get("emailAddress", {}).get("name", ""),
                "from_email": e.get("from", {}).get("emailAddress", {}).get("address", ""),
                "time": e.get("receivedDateTime", ""),
                "preview": e.get("bodyPreview", "")[:200],
                "importance": e.get("importance", "normal"),
                "isRead": e.get("isRead", False),
            }
            for e in emails
        ],
        "calendar": [
            {
                "subject": ev.get("subject", ""),
                "start": ev.get("start", {}).get("dateTime", ""),
                "end": ev.get("end", {}).get("dateTime", ""),
                "organizer": ev.get("organizer", {}).get("emailAddress", {}).get("name", ""),
                "attendees": [a.get("emailAddress", {}).get("name", "") for a in ev.get("attendees", [])[:5]],
                "preview": ev.get("bodyPreview", "")[:150],
                "location": ev.get("location", {}).get("displayName", ""),
            }
            for ev in calendar
        ],
        "recent_chats": [
            {
                "topic": c.get("topic", "(1:1 chat)"),
                "last_message_from": c.get("lastMessagePreview", {}).get("from", {}).get("user", {}).get("displayName", "") if c.get("lastMessagePreview") else "",
                "last_message_preview": c.get("lastMessagePreview", {}).get("body", {}).get("content", "")[:150] if c.get("lastMessagePreview") else "",
                "last_message_time": c.get("lastMessagePreview", {}).get("createdDateTime", "") if c.get("lastMessagePreview") else "",
                "messages": [
                    {
                        "from": m.get("from", {}).get("user", {}).get("displayName", "") if m.get("from") else "",
                        "content": m.get("body", {}).get("content", "")[:300],
                        "time": m.get("createdDateTime", ""),
                    }
                    for m in c.get("recentMessages", [])
                    if m.get("body", {}).get("content", "").strip()
                ][:8],
            }
            for c in chats
        ],
        "key_contacts": [
            {
                "name": p.get("displayName", ""),
                "title": p.get("jobTitle", ""),
                "department": p.get("department", ""),
            }
            for p in people[:8]
        ],
    }

    # Enrich with AI Search + Foundry IQ + CosmosDB data if available
    if enriched:
        if enriched.get("stored_profiles"):
            context["stored_contact_profiles"] = [
                {k: v for k, v in p.items() if k not in ("_rid", "_self", "_etag", "_attachments", "_ts", "type")}
                for p in enriched["stored_profiles"]
            ]
        if enriched.get("historical_analyses"):
            context["historical_context"] = enriched["historical_analyses"]
        # Foundry IQ agentic retrieval insights
        if enriched.get("foundry_iq_insights"):
            context["foundry_iq_insights"] = enriched["foundry_iq_insights"]
        # Add semantic search results for each sender
        if enriched.get("emails"):
            senders = set(e.get("sender_name", "") for e in enriched["emails"] if e.get("sender_name"))
            sender_history = {}
            for s in list(senders)[:5]:
                from data_layer import search_emails_by_sender
                hist = search_emails_by_sender(s, top=3)
                if hist:
                    sender_history[s] = [{"subject": h.get("subject",""), "time": h.get("received_time","")} for h in hist]
            if sender_history:
                context["sender_email_history"] = sender_history

    system_prompt = """You are an intelligent executive assistant embedded in a productivity agent.
Your job is to produce a "Morning Sweep" briefing — a concise, actionable summary based on the user's emails, calendar, Teams chats, and historical context.

Output a JSON object with these sections:
{
  "greeting": "Good morning, [Name]! Here's your briefing for [date].",
  "priority_emails": [
    {"subject": "...", "from": "...", "from_email": "...", "urgency": "high|medium|low", "suggested_action": "...", "reason": "...", "source_ref": "email received at HH:MM from X"}
  ],
  "today_schedule": [
    {"time": "HH:MM-HH:MM", "title": "...", "prep_notes": "...", "key_attendees": ["..."], "context": "...", "source_ref": "calendar event"}
  ],
  "action_items": [
    {
      "task": "...",
      "source": "email|chat|calendar",
      "source_ref": "specific email subject or chat message that triggered this",
      "deadline": "...",
      "priority": "P0|P1|P2",
      "detail": {
        "background": "2-3 sentences of context: what is this about, why it matters",
        "prep_needed": ["specific preparation item 1", "specific preparation item 2"],
        "related_people": [{"name": "...", "role_in_task": "..."}],
        "related_history": "any relevant past interactions or context from history",
        "suggested_approach": "concrete recommendation on how to handle this"
      }
    }
  ],
  "cross_check_insights": [
    {"insight": "...", "sources": ["email: subject from X", "chat: message from Y"], "source_ref": "detailed reference"}
  ],
  "contact_profiles": [
    {
      "name": "...",
      "email": "...",
      "role": "...",
      "relationship": "key stakeholder|close collaborator|team member|external",
      "communication_style": "formal|direct|detail-oriented|casual",
      "recent_topics": ["..."],
      "interaction_frequency": "daily|weekly|occasional",
      "sentiment": "positive|neutral|needs-attention",
      "tip": "One-line advice on how to engage this person effectively"
    }
  ],
  "relationship_network": {
    "summary": "One paragraph describing the user's key relationships and dynamics",
    "inner_circle": ["names of closest/most frequent collaborators"],
    "attention_needed": ["names where relationship needs nurturing or has tension"]
  },
  "draft_replies": [
    {"to": "name", "to_email": "email@example.com", "subject": "...", "draft": "...", "tone_note": "Based on contact profile: ...", "source_ref": "replying to email: subject"}
  ]
}

Rules:
- priority_emails: list ALL emails, sorted by urgency. Include from_email address. Do NOT skip any email.
- action_items: MUST include detailed "detail" object for each item. The detail.background should explain context. detail.prep_needed should list specific things to prepare. detail.related_people should name who is involved. detail.suggested_approach should give concrete advice.
- source_ref: EVERY item must cite its source (which email subject, which chat message, which calendar event).
- Cross-check: if the same topic appears in email AND chat, flag it with specific source references.
- Contact profiles: include email address. Infer communication style from email tone and word choice.
- Relationship network: identify decision power, collaboration frequency, and tension.
- draft_replies: generate a draft reply for EVERY email in priority_emails. Do NOT skip any. Each reply must be tailored to the contact's communication style.
- If historical_context is provided, USE IT to enrich analysis (e.g., "Based on yesterday's analysis, this issue is recurring" or "This topic was first raised 3 days ago").
- If foundry_iq_insights is provided, USE IT for cross-source intelligence. These are AI-generated answers from a knowledge base spanning both emails and chats. Cite them in cross_check_insights when relevant.
- Be concise but specific. No fluff.
- Output ONLY valid JSON, no markdown wrapping."""

    # Load historical context
    history = load_recent_history()
    if history:
        context["historical_context"] = history

    print("\n🤖 Sending to GPT-5.4 for analysis...")
    response = client.chat.completions.create(
        model=AOAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
        ],
        temperature=0.3,
        max_completion_tokens=10000,
        response_format={"type": "json_object"},
    )

    result_text = response.choices[0].message.content
    usage = response.usage
    cost_info = {
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
        "total_tokens": (usage.prompt_tokens + usage.completion_tokens) if usage else 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(f"  📊 Tokens: {cost_info['prompt_tokens']} in / {cost_info['completion_tokens']} out = {cost_info['total_tokens']} total")
    try:
        result = json.loads(result_text)
        result["_meta"] = cost_info
        save_history(result)
        return result
    except json.JSONDecodeError:
        print("⚠️  GPT returned non-JSON. Dashboard will show error indicator.")
        return {"error": "LLM returned non-JSON response", "raw": result_text[:500], "_meta": cost_info}


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="M365 Morning Sweep Agent")
    parser.add_argument("--login", action="store_true", help="Force interactive login")
    parser.add_argument("--hours", type=int, default=24, help="Look back N hours for emails (default: 24)")
    parser.add_argument("--output", "-o", type=str, help="Save output to JSON file")
    parser.add_argument("--no-ai", action="store_true", help="Skip GPT-5.4 analysis, just fetch data")
    parser.add_argument("--data-layer", action="store_true", help="Use AI Search + CosmosDB data layer")
    args = parser.parse_args()

    if args.data_layer:
        os.environ["USE_DATA_LAYER"] = "true"
        global USE_DATA_LAYER
        USE_DATA_LAYER = True

    print("=" * 60)
    print("🌅 M365 Morning Sweep Agent")
    print("=" * 60)

    # 1. Auth
    token = get_token(force_login=args.login)
    print("✅ Authenticated")

    # 2. Fetch user profile
    profile = fetch_user_profile(token)
    if profile:
        print(f"👤 User: {profile.get('displayName', 'Unknown')} ({profile.get('mail', '')})")

    # 3. Fetch data in parallel-ish
    print(f"\n📧 Fetching emails (past {args.hours}h)...")
    emails = fetch_recent_emails(token, hours=args.hours)
    print(f"   → {len(emails)} emails")

    print("📅 Fetching calendar (next 48h)...")
    calendar = fetch_today_calendar(token)
    print(f"   → {len(calendar)} events")

    print("💬 Fetching recent Teams chats...")
    chats = fetch_recent_chats(token)
    print(f"   → {len(chats)} chats")

    print("👥 Fetching key contacts...")
    people = fetch_people(token)
    print(f"   → {len(people)} contacts")

    # 4. Data Layer: Ingest to AI Search + get enriched context
    enriched = None
    if USE_DATA_LAYER:
        print("\n🔍 Data Layer: AI Search + Foundry IQ + CosmosDB...")
        ingest_to_search(token)
        enriched = get_enriched_context(token, hours=args.hours)
        if enriched:
            print(f"   → AI Search: {len(enriched.get('emails',[]))} emails, {len(enriched.get('chats',[]))} chats")
            print(f"   → Foundry IQ: {len(enriched.get('foundry_iq_insights',[]))} cross-source insights")
            print(f"   → CosmosDB: {len(enriched.get('stored_profiles',[]))} profiles, {len(enriched.get('historical_analyses',[]))} history entries")

    # 5. GPT-5.4 Analysis
    result = None
    if not args.no_ai:
        result = analyze_with_gpt54(emails, calendar, chats, profile, people, enriched=enriched)
        if result:
            print("\n" + "=" * 60)
            print("📋 MORNING SWEEP BRIEFING")
            print("=" * 60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            # Save to CosmosDB
            if USE_DATA_LAYER:
                save_to_cosmos("default", result)
    else:
        print("\n📊 Raw data collected (--no-ai mode)")
        result = {
            "user": profile,
            "emails_count": len(emails),
            "calendar_count": len(calendar),
            "chats_count": len(chats),
            "people_count": len(people),
            "sample_email_subjects": [e.get("subject", "") for e in emails[:5]],
            "upcoming_meetings": [ev.get("subject", "") for ev in calendar[:5]],
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))

    # 5. Save output
    if args.output and result:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Saved to {args.output}")

    print("\n✅ Morning Sweep complete!")


if __name__ == "__main__":
    main()
