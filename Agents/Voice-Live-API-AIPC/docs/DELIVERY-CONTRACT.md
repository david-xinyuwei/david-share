# Delivery Contract

## Exemplar alignment

Exemplar: [`Agents/Meeting-Agent`](https://github.com/david-xinyuwei/david-share/tree/6de8ca0b890a7227143befd4e2daf0b4b5088380/Agents/Meeting-Agent), fixed at commit `6de8ca0b890a7227143befd4e2daf0b4b5088380`.

The exemplar is used for reader flow, evidence boundaries, and executable public gates. Its meeting-specific artifact pipeline, React UI, managed-agent deployment, and Outlook-draft contract are intentionally not copied.

| Exemplar slot | Voice Live AIPC implementation | Evidence | Executable gate |
|---|---|---|---|
| First-screen identity | Five fact badges, one positioning paragraph, author, bilingual switch, direct navigation | `README.md`, `README-CN.md` | `scripts/validate_readmes.py` |
| Truth boundary | Real service/device execution, caller-owned configuration, side effects, and non-claims | README truth table; `scenario-manifest.json` | `scripts/validate_evidence.py` |
| Product walkthrough | Real sanitized application window | `images/voice-live-aipc-ui.png` | `scripts/validate_readmes.py` |
| Responsibility architecture | Azure voice coordination versus Windows-local tools and external providers | `images/voice-live-aipc-architecture.svg` | `scripts/validate_readmes.py` |
| Executable assets | Runtime paths and contracts appear before Quick Start | README executable-assets table | Local-link validation |
| Measured evidence | One bounded sanitized live summary, six provider smoke checks, explicit non-claims | `evidence/live-validation.json` | `scripts/validate_evidence.py` |
| Quick Start | Clone/install, local config, offline gate, live acceptance, GUI; side effects increase by stage | README and customer start pages | Bilingual README and customer-page validation |
| Tests and refusal paths | Tool registry, one-time confirmation, redirect SSRF, executable resolution, mail bounds, Graph cache ACL/atomicity, log redaction, package self-check | `tests/` | `pytest` through `scripts/pre_delivery_check.py` |
| Public safety | Placeholder-only configuration, credential exclusions, private-identifier scan | `.env.example`, `.gitignore`, `PUBLIC-MANIFEST.md` | `scripts/audit_public_content.py` |
| Authenticity | Production tool definitions must have bodies and real-service markers; mock fallback is prohibited | `src/`, `scenario-manifest.json` | `scripts/demo_code_validator.py` |
| CI and package | Monorepo-root Windows Python matrix plus PyInstaller onedir build and packaged self-check | `../../../.github/workflows/voice-live-aipc-ci.yml` | README validator and GitHub Actions |

## Content ledger

| Fact or claim | Canonical location | Supporting asset | Other locations |
|---|---|---|---|
| 24 tools register by default; optional image generation is the twenty-fifth definition | README local-tool section | `tests/test_contracts.py`, `src/tools/` | Other sections link or state only the required acceptance count |
| Azure coordinates voice; Windows executes device tools | README architecture section | Architecture SVG, source boundaries | First screen uses one summary sentence |
| Live validation accepted 24 tools and six smoke cases | README measured-validation section | `evidence/live-validation.json` | Customer page includes only the 24-tool Done-When |
| High-impact actions require an exact-argument, later-turn confirmation | README truth boundary and security section | `src/confirmation.py`, `tests/test_confirmation.py` | Security policy links to canonical behavior |
| Credentials and raw logs are not public | `PUBLIC-MANIFEST.md` | `.gitignore`, public audit | README states the user-facing consequence only |
| CI is side-effect free | README testing section | Workflow and deterministic gates | CONTRIBUTING repeats only the contributor command |

## Claim boundary

The repository demonstrates a real, bounded Windows voice-agent workflow. It does not claim production certification, service SLA, universal hardware compatibility, continuous provider availability, or comparative model quality.
