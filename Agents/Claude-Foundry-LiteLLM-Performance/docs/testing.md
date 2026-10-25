# Testing and Reproduction

[README](../README.md) · [Results](results.md) · [Other language](testing_CN.md)

## Offline Verification

No Azure or model key is required. Uses the Python standard library.

```powershell
python scripts/analyze.py --check
python scripts/render_docs.py --check
python -m unittest discover -s tests -v
./scripts/run_matrix.ps1 -RunDirectory live-runs/offline -ValidateOnly
```

Expect 50 records, 10 configurations and passing checks. Tests deliberately corrupt in-memory token, thinking, question and timing values and require rejection; original evidence is not edited.

## Live Acceptance

Deployment and execution commands have one owner: the README. Use a fresh run directory. Completion alone is not parameter acceptance: correlate each response x-litellm-call-id with CLAUDE_PROVIDER_TRACE logs for model, thinking, effort, stream, max_tokens and cache_control. Missing traces mean passthrough is unverified.

Check HTTP 200, end_turn, message_stop, nonempty text, complete usage, append-only history and zero thinking tokens for off modes. Classify first-turn cache state from usage, not a new session ID.

Cache-read share = sum(cache_read_input_tokens) / sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens). Output throughput = output_tokens/E2E; visible output throughput subtracts thinking tokens. Percentiles use nearest-rank without interpolation; at N=5, P95=max.

## Security, Support and Gaps

Live inputs, responses, signatures and authentication can be sensitive. live-runs and .env are ignored; do not upload them. Published signatures are omitted and call IDs pseudonymized. Do not replay published history signatures; a live run must carry its own actual responses.

Opus 5.5 does not accept disabled. Sonnet 5.5 uses between_tools and Haiku 5.5 uses disabled; these modes accept low/medium/high only. temperature/top_p/top_k are not tuning axes in this run. Unverified server tools or beta parameters are not enabled by default.

The public collector removes author-specific authentication and resource defaults while preserving the measured loop. Syntax, offline request construction and data tests are verified. A standalone fresh deployment of the public packaging was not executed; there is no public demo recording or customer desktop-client acceptance.
