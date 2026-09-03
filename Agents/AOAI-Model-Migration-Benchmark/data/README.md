Benchmark data files are not included in this public repo. See the private repo for raw data.

The public README keeps a reproducibility ledger for the WebIQ and web_search runs. New local runs write JSON under `outputs/` by default and are intentionally ignored by git:

- `benchmark_websearch_guardrails_*.json`: S1 direct, S4 `web_search_preview`, and optional S5 WebIQ E2E records.
- `benchmark_webiq_personal_search_search_*.json`: WebIQ search-only retrieval latency and sanity checks.
- `benchmark_webiq_personal_search_e2e_*.json`: WebIQ retrieval plus AOAI Responses API generation.
- `benchmark_luna_knowledge_qa_*.json`: knowledge-only direct Responses API records (gpt-5.6 Luna / Sol / Terra, gpt-5.4 family) with per-request HTTP status, request id, `retries_taken`, TTFT / T2T / E2E and token usage; `meta.script_sha256` identifies the producing script.

For any web-grounded benchmark table, report S4 and S5 together or explicitly state why WebIQ was not run. For the knowledge-only tables, compute statistics from `success=true` records only and keep failed records (status, error body, request id) in the file.
