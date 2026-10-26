# Testing and Reproduction

[README](../README.md) · [Results](results.md) · [中文](testing_CN.md)

## Offline Verification

No Azure or model key is required. Uses the Python standard library.

```powershell
python -B scripts/analyze.py --check
python -B scripts/render_docs.py --check
python -B -m unittest discover -s tests -v
./scripts/run_matrix.ps1 -RunDirectory live-runs/offline -ValidateOnly
```

Expect 50 published records and 10 configurations, matching generated files and passing unit tests. Without PowerShell 7 the runner tests are skipped, not validated. Negative tests alter in-memory or isolated test copies: tokens, thinking, prompts, timing, missing traces, duplicate call IDs or truncated streams. Originals remain unchanged. Synthetic SSE and test transport substitutes validate collector/analysis logic only, never new model-performance evidence.

## Live Acceptance

Deployment, log capture and fresh-run commands have one owner: README steps 1-6. run_matrix.ps1 saves raw responses. analyze.py --run-directory also requires --trace-file and correlates outbound model, thinking, effort, stream, max_tokens and cache markers by x-litellm-call-id. It reads that directory's matrix.json, run.json, frozen collector and ACA_HTTP_*.json, reconstructing SSE, cumulative usage and history. It never falls back to published evidence. Missing logs fail; the original run.json stays pending audit.

Trace input accepts observer JSON/JSONL, CLAUDE_PROVIDER_TRACE console text and Azure CLI JSONL with a Log field. Identical duplicate log entries merge; conflicting content for one call ID fails. Unrelated calls are counted separately and cannot replace current requests. analysis.json and analysis.md are derived files in the same directory; reanalysis updates only these outputs, while --check writes nothing. Actual private signatures are validated but not written into the Markdown report.

Check HTTP 200, end_turn, message_stop, nonempty text, complete usage, append-only history and zero thinking tokens for off modes. Classify first-turn cache state from usage, not a new session ID.

Cache-read share = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens). Output throughput = output_tokens/E2E; visible output throughput subtracts thinking tokens. Percentiles use nearest-rank without interpolation; at N=5, P95=max.

## Security, Support and Gaps

Live inputs, responses, signatures and authentication can be sensitive. live-runs and .env are ignored; do not upload them. Published signatures are omitted and call IDs pseudonymized. Do not replay published history signatures; a live run must carry its own actual responses.

Opus 5.5 does not accept disabled. Sonnet 5.5 uses between_tools and Haiku 5.5 uses disabled; these modes accept low/medium/high only. temperature/top_p/top_k are not tuning axes in this run. Unverified server tools or beta parameters are not enabled by default.

The public collector removes author-specific authentication and resource defaults while preserving the measured loop. Syntax, offline request construction and data tests are verified. A standalone fresh deployment of the public packaging was not executed; there is no public demo recording or customer desktop-client acceptance.

Deployment command references (consulted 2026-10-25):
[Container Apps CLI](https://learn.microsoft.com/en-us/cli/azure/containerapp?view=azure-cli-latest) · [Managed identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull) · [Model deployments CLI](https://learn.microsoft.com/en-us/cli/azure/cognitiveservices/account/deployment?view=azure-cli-latest) · [Claude in Foundry](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry)
