# Validation Checklist

- [x] Official repository and immutable commit identified
- [x] All 25 executable upstream Git blob contents pinned with SHA-256
- [x] Verified Git blob bytes materialized into a private run directory and invoked without modification
- [x] ARM deployment, AOAI model/cache binding, and Context Cache container contract verified
- [x] Exact Windows AMD64 CPython 3.11 wheel artifacts locked with SHA-256
- [x] Six real Responses API calls completed
- [x] Cache result independently recomputed from call rows
- [x] No-cache, zero-threshold, zero-latency, missing-row, HTTP-error, partial-hit, failed-ARM, and wrong-binding branches tested
- [x] PowerShell runner behavior tested with process-level Azure CLI doubles, bounded timeout, and junction rejection
- [x] Public evidence stripped of cloud and identity identifiers
- [x] Runtime has no mock, API-key fallback, automatic login, or automatic cleanup
- [x] English and Chinese documentation share structure, commands, images, and boundaries
- [x] Static validators and cross-platform CI included

The live capability result is a single-run observation. CI validates code, contracts, and
sanitized evidence offline; CI does not deploy Azure resources.