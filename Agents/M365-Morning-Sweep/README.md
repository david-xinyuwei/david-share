# M365 Morning Sweep Agent

> An AI-powered executive assistant that reads your Microsoft 365 emails, calendar, and Teams chats via **Graph API**, analyzes them with **Azure OpenAI**, and produces a structured "Morning Sweep" briefing with prioritized emails, action items, contact profiles, relationship insights, and draft replies.

---

## Running on Azure

| Item | Details |
|---|---|
| **Azure OpenAI** | GPT-4o / GPT-4.1 or any chat completion deployment |
| **Microsoft Graph API** | Mail.Read, Calendars.Read, Chat.Read, User.Read, People.Read |
| **Azure AI Search** | (Optional) Vector + keyword search for email/chat history |
| **Azure Cosmos DB** | (Optional) Contact profiles and analysis history persistence |
| **Foundry IQ** | (Optional) Agentic retrieval across indexed emails and chats |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Graph API (M365)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Emails  │  │ Calendar │  │  Chats   │  │ People  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
└───────┼──────────────┼──────────────┼─────────────┼──────┘
        │              │              │             │
        └──────────────┴──────┬───────┴─────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Azure OpenAI     │
                    │  (Analysis Engine) │
                    └─────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
     ┌────────▼───┐  ┌───────▼──────┐  ┌─────▼──────┐
     │  JSON       │  │  Live Server │  │  Dashboard │
     │  Output     │  │  (SSE/Poll)  │  │  (HTML)    │
     └─────────────┘  └──────────────┘  └────────────┘

Optional Data Layer:
  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
  │  AI Search  │   │  Cosmos DB  │   │ Foundry IQ  │
  │  (History)  │   │ (Profiles)  │   │ (Agentic)   │
  └─────────────┘   └─────────────┘   └─────────────┘
```

---

## Features

### Core (No extra infra needed)
- **Priority Emails** — All emails sorted by urgency (high/medium/low) with suggested actions
- **Today's Schedule** — Calendar events with prep notes and key attendees
- **Action Items** — Extracted tasks with priority (P0/P1/P2), deadlines, and detailed context
- **Contact Profiles** — Communication style, relationship type, sentiment analysis
- **Relationship Network** — Inner circle identification and attention-needed alerts
- **Draft Replies** — AI-generated email replies tailored to each contact's communication style
- **Cross-Check Insights** — Correlations between emails, chats, and calendar events
- **File-Based History** — Cross-session memory via local JSON files (last 50 analyses)

### Enhanced Data Layer (Optional, requires AI Search + Cosmos DB)
- **Vector Search** — Semantic search across historical emails and chats
- **Foundry IQ** — Agentic retrieval with cross-source intelligence
- **Contact Persistence** — Profiles stored in Cosmos DB, enriched over time
- **Analysis History** — Past analyses queryable for trend detection

### Live Dashboard
- **SSE Push** — Server-Sent Events for instant browser updates (no page reload)
- **Smart Polling** — Only triggers Azure OpenAI when Graph API data actually changes (hash-based)
- **Basic Auth** — Simple username/password protection
- **Interactive To-Do** — Check off action items directly in the browser
- **Editable Drafts** — Modify AI-generated replies before sending

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- An Azure OpenAI resource with a chat completion deployment
- An Entra ID app registration with Graph API permissions

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. First Run (Interactive Login)

```bash
# Set environment variables
export $(grep -v '^#' .env | xargs)

# Interactive login (opens browser for device code flow)
python morning_sweep.py --login

# Subsequent runs use cached token
python morning_sweep.py --hours 48 -o output.json
```

### 5. Live Dashboard

```bash
export $(grep -v '^#' .env | xargs)
python live_server.py
# Open http://localhost:8088 in browser
```

---

## Usage

### CLI Options

```bash
python morning_sweep.py --help

  --login           Force interactive login
  --hours N         Look back N hours for emails (default: 24)
  --output FILE     Save output to JSON file
  --no-ai           Skip Azure OpenAI analysis, just fetch raw data
  --data-layer      Enable AI Search + CosmosDB enrichment
```

### Service Principal Mode (Unattended)

For automated/server deployment without interactive login:

```bash
export USE_SP_AUTH=true
export SP_TENANT=your-tenant-id
export SP_CLIENT_ID=your-sp-client-id
export SP_CLIENT_SECRET=your-sp-client-secret
export SP_TARGET_USER=user@yourtenant.onmicrosoft.com

python morning_sweep.py --hours 24 -o output.json
```

### Infrastructure Setup (Optional)

```bash
# Create AI Search indexes + CosmosDB containers + Foundry IQ Knowledge Base
python setup_infra.py --all
```

---

## Output Structure

The Azure OpenAI analysis produces a structured JSON with these sections:

| Section | Description |
|---------|-------------|
| `greeting` | Personalized morning greeting |
| `priority_emails` | All emails with urgency rating and suggested actions |
| `today_schedule` | Calendar events with prep notes |
| `action_items` | Extracted tasks with P0/P1/P2 priority and detailed context |
| `cross_check_insights` | Cross-source correlations (email ↔ chat ↔ calendar) |
| `contact_profiles` | Communication style and relationship analysis per person |
| `relationship_network` | Inner circle and attention-needed contacts |
| `draft_replies` | AI-generated reply drafts for each email |

---

## File Structure

```
M365-Morning-Sweep/
├── morning_sweep.py               # Core agent: Graph API → Azure OpenAI → JSON
├── live_server.py                  # Live dashboard server (SSE + smart polling)
├── auto_refresh_server.py          # Simple auto-refresh server (polling only)
├── dashboard.html                  # Rich dashboard with Foundry IQ integration
├── morning_sweep_dashboard_template.html  # Dashboard template for static mode
├── data_layer.py                   # AI Search + CosmosDB + Foundry IQ integration
├── setup_infra.py                  # One-click infrastructure setup
├── refresh_dashboard.sh            # One-click data refresh + dashboard rebuild
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variable template
└── .gitignore
```

---

## Entra ID App Registration

### Delegated Permissions (Interactive Login)
- `Mail.Read`
- `Mail.Send`
- `Calendars.Read`
- `Chat.Read`
- `User.Read`
- `People.Read`

### Application Permissions (Service Principal)
- `Mail.Read`
- `Calendars.Read`
- `Chat.Read.All`
- `User.Read.All`

---

## Known Issues / Troubleshooting

| Issue | Solution |
|-------|----------|
| `AADSTS65001` on login | Grant admin consent for the app registration permissions |
| Graph API 403 on `/me/chats` | `Chat.Read` permission requires admin consent in most tenants |
| CosmosDB firewall error | Add your VM/client IP to CosmosDB firewall allowlist, ensure `publicNetworkAccess` is `Enabled` |
| Empty calendar results | Check timezone — Graph API uses UTC, `calendarView` requires explicit start/end times |
| Token cache expired | Run with `--login` to re-authenticate |

---

*Author: Xinyu Wei (魏新宇)*
