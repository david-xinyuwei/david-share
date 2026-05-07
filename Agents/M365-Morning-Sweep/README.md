# M365 Morning Sweep Agent

> An AI-powered executive assistant that reads your Microsoft 365 emails, calendar, and Teams chats via **Microsoft Graph API**, analyzes them with **Azure OpenAI**, and produces a structured "Morning Sweep" briefing — prioritized emails, action items with detailed context, contact profiles, relationship network mapping, cross-source intelligence, and draft replies that you can edit and send directly from the dashboard.

---

## Running on Azure

| Component | Details |
|---|---|
| **Azure OpenAI** | Any chat completion deployment (GPT-4o, GPT-4.1, etc.) + `text-embedding-3-large` for vector search |
| **Microsoft Graph API** | Mail.Read, Mail.Send, Calendars.Read, Chat.Read, User.Read, People.Read |
| **Azure AI Search** | (Optional) Vector + keyword indexes for historical email/chat retrieval |
| **Azure Cosmos DB** | (Optional) Contact profile persistence and analysis history |
| **Foundry IQ** | (Optional) Agentic retrieval — cross-source intelligence across emails and chats |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Microsoft Graph API (M365)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐ │
│  │  Emails   │  │ Calendar │  │  Teams   │  │ People/Contacts │ │
│  │ (N hours) │  │ (48h)    │  │  Chats   │  │ (Top 10)        │ │
│  └─────┬─────┘  └─────┬────┘  └─────┬────┘  └──────┬──────────┘ │
└────────┼───────────────┼─────────────┼──────────────┼────────────┘
         └───────────────┴──────┬──────┴──────────────┘
                                │
                    ┌───────────▼────────────┐
                    │     Azure OpenAI       │
                    │   Structured Analysis  │
                    │   (JSON output mode)   │
                    └───────────┬────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
┌────────▼────────┐  ┌─────────▼─────────┐  ┌─────────▼─────────┐
│   JSON Output   │  │  Live Server      │  │  Static Dashboard │
│   (CLI mode)    │  │  (SSE + Polling)  │  │  (HTML embed)     │
└─────────────────┘  └─────────┬─────────┘  └───────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼──────┐ ┌──────▼──────┐ ┌───────▼───────┐
     │  /api/data    │ │ /api/send   │ │ /api/optimize │
     │  JSON API     │ │ Send Email  │ │ Persona Draft │
     └───────────────┘ └─────────────┘ └───────────────┘

Optional Data Layer (enables cross-session memory):
  ┌───────────────┐   ┌───────────────┐   ┌────────────────┐
  │  AI Search    │   │  Cosmos DB    │   │  Foundry IQ    │
  │ emails index  │   │ profiles      │   │ Knowledge Base │
  │ chats index   │   │ analyses      │   │ Agentic RAG    │
  │ vector+kw     │   │ history       │   │ cross-source   │
  └───────────────┘   └───────────────┘   └────────────────┘
```

---

## Features

### Core Agent (`morning_sweep.py`)

**Data Collection** — Fetches from 4 Graph API endpoints in a single sweep:
- **Emails**: Past N hours (configurable), deduplicated by subject+sender, with body preview
- **Calendar**: Next 48 hours of events with attendees, location, and agenda
- **Teams Chats**: Recent 10 chats with last 20 messages each, including group chats
- **People**: Top 10 relevant contacts via Microsoft Graph People API

**Azure OpenAI Analysis** — Sends all collected data to a chat completion model with structured JSON output. The system prompt instructs the model to produce:

| Output Section | What It Contains |
|---|---|
| `priority_emails` | **Every** email sorted by urgency (high/medium/low), with suggested action and reasoning. Includes sender email address |
| `today_schedule` | Calendar events with preparation notes, key attendees, and context |
| `action_items` | Extracted tasks with P0/P1/P2 priority. Each item includes a `detail` object: background (2-3 sentences), prep_needed (specific items), related_people (name + role), related_history, and suggested_approach |
| `cross_check_insights` | Cross-source correlations — when the same topic appears in email AND chat, it gets flagged with source references |
| `contact_profiles` | Per-person analysis: communication style (formal/direct/casual), relationship type, sentiment, interaction frequency, and engagement tips |
| `relationship_network` | Inner circle identification + attention-needed alerts |
| `draft_replies` | AI-generated reply for **every** email, tailored to the contact's communication style |

**Authentication** — Two modes:
- **Delegated** (interactive): MSAL device code flow with persistent token cache
- **Service Principal** (unattended): Client credentials for automated/server deployment

**Cross-Session Memory** — File-based history (last 50 analyses stored as JSON). Previous analyses are fed back into the prompt so the model can say things like "This issue was first raised 3 days ago" or "This is a recurring action item."

### Live Dashboard Server (`live_server.py`)

A self-contained Python HTTP server (no Flask/Django dependency) that serves a real-time dashboard:

- **Smart Polling**: Polls Graph API every 15 seconds, but only triggers Azure OpenAI analysis when data actually changes (MD5 hash comparison of email subjects + chat previews). This avoids unnecessary API costs
- **SSE Push**: Browser polls `/api/data` every 5-10 seconds for instant updates without page reload
- **Basic Auth**: Username/password protection for all endpoints except `/api/health` and `/api/schema`
- **Thread-Safe**: Analysis runs in background threads; server remains responsive

**REST API endpoints**:

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/` | GET | Yes | Dashboard HTML |
| `/api/data` | GET | Yes | Current analysis result as JSON |
| `/api/health` | GET | No | Status, metrics, data freshness |
| `/api/schema` | GET | No | API documentation with full JSON schema |
| `/api/send-mail` | POST | Yes | Send email via Graph API (supports attachments) |
| `/api/optimize-draft` | POST | Yes | Rewrite a draft for a specific persona/communication style |
| `/api/refresh` | POST | Yes | Force re-analysis with custom time range |
| `/api/insights` | GET | Yes | CosmosDB historical trends |

### Rich Dashboard (`dashboard.html`)

A single-file HTML dashboard with no build tools or external dependencies:

- **Hero Header**: Greeting + stats bar (email count, to-do count, chat count, profile count) + time range selector (24h to 30 days) + manual Sync button
- **Priority Emails**: Color-coded by urgency (red/orange/green border), collapsible to show suggested action and source reference
- **To-Do List**: Interactive checkboxes (checked items get strikethrough), collapsible detail panels showing background, preparation items, related people, and suggested approach
- **Teams Chats**: Recent messages grouped by chat topic, showing sender, content preview, and timestamp
- **Contact Profiles**: Avatar circles with initials, role/relationship tags, communication style badges, sentiment dots (green/orange/red), and engagement tips
- **Relationship Network**: Inner circle (green tags) and attention-needed (red tags) visualization
- **Cross-Source Insights**: Gradient cards showing correlations between emails, chats, and calendar
- **Foundry IQ Panel**: Agentic retrieval results — shows the query, AI-generated answer, reference count, and source types
- **AI-Drafted Replies**: Collapsible reply cards with:
  - Editable draft text (contentEditable)
  - Persona optimization buttons — click a contact name to rewrite the draft matching their communication style, with before/after comparison
  - File attachment via drag-and-drop or file picker (base64 encoded, max 3MB per file)
  - One-click send with confirmation modal
- **Insights Over Time**: CosmosDB-backed historical panel showing analysis timeline and contact profile evolution
- **Footer**: Token usage, timestamp, and technology stack badges

### Data Layer (`data_layer.py`)

Optional but recommended for production use. Each component fails independently (partial enrichment is still useful):

**AI Search Integration**:
- Two indexes: `emails` (with `body_vector` for semantic search) and `chats` (with `content_vector`)
- Ingestion: Graph API data → `text-embedding-3-large` embeddings → AI Search upload
- Retrieval: keyword search, semantic/vector search, and sender-specific history lookup
- Used to enrich GPT context with historical patterns

**Foundry IQ (Agentic Retrieval)**:
- Creates Knowledge Sources from the `emails` and `chats` AI Search indexes
- Creates a Knowledge Base that spans both sources
- Queries are auto-generated from current email subjects and chat topics
- Returns AI-generated cross-source answers with citations
- Example: "What do I know about: Q2 AI Strategy" → searches both email and chat indexes → returns synthesized answer

**CosmosDB Integration**:
- `profiles` container: Contact profiles (communication style, sentiment, topics) updated after each analysis
- `analyses` container: Historical analysis summaries for trend detection
- AAD authentication via Service Principal (no key in code)

### Infrastructure Setup (`setup_infra.py`)

One-command setup for all Azure resources:
```bash
python setup_infra.py --all
```
Creates:
- AI Search indexes (`emails`, `chats`) with vector search configuration (HNSW, 3072 dimensions)
- CosmosDB database `morning_sweep` with `profiles` and `analyses` containers
- Foundry IQ Knowledge Sources and Knowledge Base
- Initial data ingestion from Graph API

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- An Azure OpenAI resource with a chat completion deployment
- An Entra ID app registration with Graph API permissions (see [Entra ID Setup](#entra-id-app-registration))

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your Azure OpenAI endpoint, key, tenant ID, and client ID
```

### 4. First Run (Interactive Login)

```bash
# Load environment variables
export $(grep -v '^#' .env | xargs)

# Interactive login via device code flow
python morning_sweep.py --login --hours 24

# Output: structured JSON briefing printed to console
# Token is cached at ~/.morning_sweep_token_cache.json for subsequent runs
```

### 5. Subsequent Runs

```bash
# Use cached token, look back 48 hours, save to file
python morning_sweep.py --hours 48 -o briefing.json

# Fetch data only (no Azure OpenAI call)
python morning_sweep.py --no-ai

# Enable full data layer (AI Search + CosmosDB + Foundry IQ)
python morning_sweep.py --data-layer --hours 168
```

### 6. Live Dashboard

```bash
export $(grep -v '^#' .env | xargs)
python live_server.py
# Open http://localhost:8088 in browser
# Default credentials: admin / changeme (configurable via DASHBOARD_USER/DASHBOARD_PASSWORD)
```

### 7. Infrastructure Setup (Optional)

```bash
# Requires SEARCH_ENDPOINT, SEARCH_KEY, COSMOS_ENDPOINT, COSMOS_KEY
python setup_infra.py --setup    # Create indexes and containers
python setup_infra.py --ingest   # Ingest Graph API data into AI Search
python setup_infra.py --all      # Both
```

---

## Service Principal Mode (Unattended)

For automated/server deployment without interactive login:

```bash
export USE_SP_AUTH=true
export SP_TENANT=your-tenant-id
export SP_CLIENT_ID=your-sp-client-id
export SP_CLIENT_SECRET=your-sp-client-secret
export SP_TARGET_USER=user@yourtenant.onmicrosoft.com

# CLI mode
python morning_sweep.py --hours 24 -o output.json

# Or live server mode
python live_server.py
```

In SP mode, Graph API calls replace `/me` with `/users/{target_user}` automatically.

---

## File Structure

```
M365-Morning-Sweep/
├── morning_sweep.py                       # Core agent: Graph API → Azure OpenAI → JSON
│                                          #   Auth (MSAL delegated + SP), data collection,
│                                          #   GPT analysis, history persistence (611 lines)
├── live_server.py                         # Live dashboard server: SSE + smart polling +
│                                          #   REST API + embedded fallback HTML (693 lines)
├── dashboard.html                         # Rich dashboard: hero header, collapsible cards,
│                                          #   persona optimization, drag-drop attachments,
│                                          #   CosmosDB insights panel (598 lines)
├── data_layer.py                          # AI Search + CosmosDB + Foundry IQ integration:
│                                          #   ingestion, retrieval, profiles, history (365 lines)
├── setup_infra.py                         # One-click Azure resource setup (252 lines)
├── auto_refresh_server.py                 # Simple auto-refresh server (polling only, 94 lines)
├── morning_sweep_dashboard_template.html  # Dashboard template for static/offline mode
├── refresh_dashboard.sh                   # One-click: fetch data + rebuild static dashboard
├── requirements.txt                       # Python dependencies
├── .env.example                           # Environment variable template
├── .gitignore                             # Excludes .env, JSON data, token cache
├── README.md                              # This file
└── README-CN.md                           # Chinese version
```

---

## Entra ID App Registration

### Delegated Permissions (Interactive Login)

| Permission | Purpose |
|---|---|
| `Mail.Read` | Read user's emails |
| `Mail.Send` | Send emails from dashboard |
| `Calendars.Read` | Read calendar events |
| `Chat.Read` | Read Teams chat messages |
| `User.Read` | Get user profile (name, title, department) |
| `People.Read` | Get relevant contacts for relationship mapping |

### Application Permissions (Service Principal)

| Permission | Purpose |
|---|---|
| `Mail.Read` | Read target user's emails |
| `Calendars.Read` | Read target user's calendar |
| `Chat.Read.All` | Read Teams chats (requires admin consent) |
| `User.Read.All` | Get user profiles |

> **Note**: Application permissions require admin consent in the Azure portal.

---

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TENANT_ID` | Yes | — | Azure AD tenant ID |
| `CLIENT_ID` | Yes | — | App registration client ID |
| `AOAI_ENDPOINT` | Yes | — | Azure OpenAI endpoint URL |
| `AOAI_KEY` | Yes | — | Azure OpenAI API key |
| `AOAI_DEPLOYMENT` | No | `gpt-4o` | Chat completion deployment name |
| `AOAI_API_VERSION` | No | `2025-04-01-preview` | Azure OpenAI API version |
| `USE_SP_AUTH` | No | `false` | Enable Service Principal mode |
| `SP_TENANT` | SP mode | — | SP tenant ID |
| `SP_CLIENT_ID` | SP mode | — | SP client ID |
| `SP_CLIENT_SECRET` | SP mode | — | SP client secret |
| `SP_TARGET_USER` | SP mode | — | Target user UPN (e.g., `user@tenant.onmicrosoft.com`) |
| `USE_DATA_LAYER` | No | `false` | Enable AI Search + CosmosDB + Foundry IQ |
| `SEARCH_ENDPOINT` | Data layer | — | Azure AI Search endpoint |
| `SEARCH_KEY` | Data layer | — | Azure AI Search admin key |
| `COSMOS_ENDPOINT` | Data layer | — | Cosmos DB endpoint |
| `COSMOS_KEY` | Data layer | — | Cosmos DB key (for setup_infra.py only; runtime uses AAD) |
| `FOUNDRY_IQ_KB` | Data layer | `morning-sweep-kb` | Knowledge Base name |
| `PORT` | No | `8088` | Dashboard server port |
| `DASHBOARD_USER` | No | `admin` | Basic Auth username |
| `DASHBOARD_PASSWORD` | No | `changeme` | Basic Auth password |
| `POLL_INTERVAL` | No | `15` | Graph API polling interval (seconds) |
| `EMAIL_HOURS` | No | `168` | Default email lookback window (hours) |

---

## Known Issues / Troubleshooting

| Issue | Solution |
|-------|----------|
| `AADSTS65001` on login | Grant admin consent for the app registration permissions in Azure Portal |
| Graph API 403 on `/me/chats` | `Chat.Read` requires admin consent in most tenants |
| CosmosDB `(Forbidden) Request originated from IP...` | Add VM/client IP to CosmosDB firewall allowlist **and** ensure `publicNetworkAccess` is `Enabled` (both are required) |
| Empty calendar results | Graph API uses UTC; `calendarView` requires explicit `startDateTime`/`endDateTime` |
| Token cache expired | Run with `--login` to re-authenticate via device code flow |
| Azure OpenAI returns non-JSON | Model occasionally fails structured output; the agent saves the raw response and retries on next poll cycle |
| Dashboard shows "Loading..." | Check `/api/health` — if status is `warming_up`, the first Graph API poll hasn't completed yet |
| Send email fails from dashboard | Verify `Mail.Send` permission is granted and admin-consented |

---

*Author: Xinyu Wei (魏新宇)*
