Benchmark data files are not included in this public repo. See the private repo for raw data.

The public README keeps a reproducibility ledger for the WebIQ and web_search runs. New local runs write JSON under `outputs/` by default and are intentionally ignored by git:

- `benchmark_websearch_guardrails_*.json`: S1 direct, S4 `web_search_preview`, and optional S5 WebIQ E2E records.
- `benchmark_webiq_personal_search_search_*.json`: WebIQ search-only retrieval latency and sanity checks.
- `benchmark_webiq_personal_search_e2e_*.json`: WebIQ retrieval plus AOAI Responses API generation.

For any web-grounded benchmark table, report S4 and S5 together or explicitly state why WebIQ was not run.
