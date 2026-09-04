# Level 5 exemplar alignment

The user-selected reference is the public
[`Meeting-Agent@f1c72653`](https://github.com/david-xinyuwei/david-share/tree/f1c72653c900dba73cc272ed006dc26add75203f/Agents/Meeting-Agent)
repository. The portable contract is one product question, explicit proof
requirements, a measured result, real-versus-boundary language, executable
entry points, and evidence-first quality gates. Its dual Agent implementations,
browser UI, Outlook handoff, and meeting artifacts are domain-specific and are
not copied here.

| Slot | Why the exemplar has it | This repository | Deterministic gate |
|---|---|---|---|
| S0 | Establish scope and measured result immediately | Headline `200 → 403` outside and steady private `200`, followed by explicit non-claims | Intro facts and navigation tokens |
| S0.5 | Give every reader one entry point before the report | `Start here` / `从这里开始` routes audit, offline tests, production planning, and live reproduction | First-H2, first-80-lines, route-table, dependency, and mutation checks |
| S1 | Separate platform responsibility from customer responsibility | Two-column platform/customer table plus benefit and trade-off | Required table header and bilingual reader-flow gate |
| S2 | Connect every capability claim to evidence | 200 public baseline, 200 private preflight, 403 public block, 200 private allow, 200 restored | `connectivity-run.json` assertions |
| S3 | Show the actual product surface | Same-run Foundry model, deployment type, status, and accelerator field crops | Image hash validation |
| S4 | Make the repository executable | Bicep, endpoint probe, guarded public network access control | Required path checks and unit tests |
| S5 | Present one complete measured run | Dedicated account; one fixed deployment/endpoint/identity/payload across five stages | Run contract and scenario matrix |
| S6 | Explain only the mechanism needed to interpret the run | DNS classification, authenticated response semantics, public-access control, client access paths, and three misconception corrections | Function links, official DNS sources, bilingual facts, and retired-phrase gate |
| S7 | Put the runnable path in the main README | Account guard, what-if, deploy, private-IP ACI preflight, disable/save, public `403`, private `200`, restore original, conditional public `200` | Ordered fenced-command contract plus CLI entry-point test |
| S8 | Test rejection paths, not only success | Dedicated Tests section; invalid PE/probe variants perform zero PATCH calls; evidence, rule, reader-flow, and language mutations fail closed | Offline test contract plus executed mutation evaluators |
| S9 | Keep compatibility, evidence, and official sources one click away | Compatibility limits, evidence classes, generated transcript, UI hash, immutable source commits, and retained-resource state | Repository validator and source lock |
| S10 | Give each directory one clear owner | Repository map for `infra`, `scripts`, `tests`, `evidence`, `images`, and `docs` | Required heading/order and path checks |

| Meeting-Agent portable gate | Applied here | Not applicable here |
|---|---|---|
| Bilingual evidence alignment | Fact ledger, command/image parity, native Chinese audit, and live Azure AI Translator back-translation | Sentence-by-sentence translation or identical paragraph structure |
| Evidence integrity | Raw/derived separation, source locks, visual ledger, live Translator receipts, and mutation tests | Meeting artifact manifests and browser-rendered outputs |
| Public-content audit | Dedicated secret, identifier, endpoint, and email scan | Outlook no-send audit |
| Script compatibility | Windows/Linux CI on Python 3.11 and 3.13, compile, unit tests, Bicep build | Wheel build, npm, Playwright, and package dependency audit because this repo has no Python package or UI |

`READER_ONBOARDING=PASS` requires both language entry points and all reader-flow
mutations to pass. `AI_NATIVE_CHINESE_AUDIT` is recorded only after an
independent Chinese-only review reports zero material findings.

Language audit record, 2026-09-04:

- `AI_NATIVE_CHINESE_AUDIT=PASS`: independent Chinese-only review, material findings `0`.
- `AI_BILINGUAL_SEMANTIC_AUDIT=PASS`: independent fact-ledger comparison, numeric drift `0`.
- `DETERMINISTIC_BILINGUAL_GATE`: `RUN-014` checks facts, command blocks, images, reader flow, official-term introductions, and retired translation phrases.
- `AZURE_TRANSLATOR_BACK_TRANSLATION=PASS`: Azure AI Translator `TextTranslation/F0/global` translated 161 Chinese prose units in 2 HTTP `200` calls (10,957 metered characters); English↔Chinese and Chinese→back-translation numeric drift are both `0`. Request IDs are retained only as SHA-256 digests in `evidence/translator-back-translation.json`.
