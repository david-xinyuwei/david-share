# Managed Meeting Agent Feature Parity

The classic implementation remains at the repository root, fixed to baseline `david-xinyuwei/david-share@667357dac6ee2dc30102d572c458c77861112bea`. The Managed implementation lives in `managed-agent/` in the same repository and replaces the model-runtime ownership boundary.

| Capability | Earlier implementation | Managed implementation | Verification | Result |
|---|---|---|---|---|
| Event contract | Strict `MeetingEvent` schema | Same `MeetingEvent` behavior; Models module additionally defines optional `DeckPlan` | Model tests plus intentional-difference hashes | Equivalent event contract; Managed extension documented |
| Session ordering and idempotency | Ordering, duplicate handling, conflict rejection, final-only transcript, source hash | Same file SHA-256 | Module hash comparison and session tests | Equivalent |
| Transcript and visual inputs | Transcript TXT, ASR JSONL, Meeting JSON, visual summaries | Same input adapter SHA-256 | Node input tests and browser E2E | Equivalent |
| Structured analysis | Local AOAI key-auth client with GPT-5.4 | Foundry Managed Agent v9, GPT-5.4, GHCP, Entra, strict `MeetingAnalysis` and Agent-authored `DeckPlan` | Public-source deployment, Agent Reference validation, strict v9 invocation, live Meeting JSON browser E2E | Enhanced runtime ownership |
| Skills | Packaged local `SKILL.md` in the model request | Toolbox v5 provides `meeting-package` v3 and normalized `presentation-story` v3 (`SKILL.md`, `references/`, `assets/`) through Toolbox MCP | Cloud Skill ZIP inspection, strict v9 response, and live browser JSON-upload validation | Enhanced versioned lifecycle verified live |
| PowerPoint responsibility | Local Skill guides content; deterministic template/renderer creates the file | `presentation-story` owns writing; strict `DeckPlan`, reference/asset YAML, and template drive deterministic rendering | Skill/Schema/config/renderer tests plus live parseable six-slide PPTX | Presentation domain decoupled and live-validated |
| Streaming | Real Responses text deltas and completion stages | Real Managed Responses SSE deltas and same completion stages | Contract tests and live browser stream | Equivalent |
| Mind map | JSON, Mermaid, SVG, PNG | Same output contract | Independent Pillow parse, schema checks, desktop/mobile UI | Equivalent |
| PowerPoint | Editable six-slide template deck | Same OOXML template bytes stored with a OneDrive-safe `.zip` resource extension | Independent `python-pptx` parse, six nonempty slides | Equivalent |
| Email draft | HTML/plain EML, inline map, PNG/PPTX attachments | Identical draft module SHA-256 | MIME parse: `X-Unsent: 1`, zero recipients, two attachments | Equivalent |
| Outlook handoff | Atomic EML write and `olk.exe` launch | Identical Outlook module SHA-256 | Node tests and no-send audit | Equivalent |
| Browser UI | React/Vite, loopback BFF, downloads, rich-text copy | Same user workflow with Managed runtime label, Entra status, and Meeting JSON upload | Vitest 18/18; contract Playwright desktop/mobile 4/4; historical v6 desktop/mobile 2/2; v9 JSON-upload desktop 1/1 | Equivalent plus runtime transparency |
| Artifact security | Allowlisted paths and canonical path checks | Same BFF path controls | Node traversal and symlink tests | Equivalent |
| Mail safety | No Graph, SMTP, EWS, `.Send`, or Send-button automation | Same restriction | Static no-send audit | Equivalent |
| Authentication | AOAI API key in backend process | Tenant-scoped `AzureDeveloperCliCredential` for local Entra Responses calls plus `AgenticIdentityToken` for Toolbox; project-scoped `Foundry User` on the Agent identity | Production source scan, credential-mode tests, and live v9 invocation | Enhanced |
| Explicit persistent filesystem | Not required | Not required; no preview persistence claim | Architecture and README boundary | Equivalent boundary |

The current Parity Manifest records six byte-equal modules and two intentional differences with baseline/current hashes: Models adds the optional strict `DeckPlan`, and Hosted Pipeline resolves v6 compatibility before rendering. Artifact and UI changes are verified through executable contracts rather than represented as byte-equal modules.

The comparison establishes functional parity, not identical prose or model-quality parity. Both implementations now use GPT-5.4, but their orchestration owners remain different, so acceptance is based on strict contracts, evidence grounding, artifacts, safety, and user workflows rather than identical wording.